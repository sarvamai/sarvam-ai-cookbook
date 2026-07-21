import asyncio
import base64
import json
import logging
import threading
import time
import urllib.parse

import websockets
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from sarvamai import AsyncSarvamAI

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins=config.CORS_ALLOWED_ORIGINS)

SARVAM_API_KEY = config.SARVAM_API_KEY

# saaras:v3-realtime, gated by the enable_saaras_v3_realtime_streaming_users
# beta flag. Not yet wrapped by the sarvamai SDK (0.1.28), so this connects
# directly with `websockets` against the documented wire protocol instead of
# `client.speech_to_text_streaming.connect(...)`.
REALTIME_WS_URL = "wss://api.sarvam.ai/speech-to-text-realtime/ws"

# The realtime endpoint's own language_code enum spells Odia "or-IN", while
# every other Sarvam API this app talks to (Translate, TTS) spells it
# "od-IN" -- confirmed against both APIs' published schemas, this is a real
# inconsistency between Sarvam's own APIs, not a typo on either side. Only
# the realtime STT connection needs the override; the Translate API calls in
# _translate() keep using "od-IN" (self.language_code / self.target_language
# are never touched by this).
STT_LANGUAGE_CODE_OVERRIDES = {"od-IN": "or-IN"}


def _build_realtime_url(language_code, mode):
    """`language_code=unknown` is this app's "auto-detect" sentinel from the
    older API; the realtime endpoint's equivalent is `auto`.

    `stream_type=fast` (not the `balanced` default) is what actually makes
    this feel "real-time" -- `balanced`/`simulated` trade latency for
    accuracy by buffering more audio before emitting `transcript.partial`,
    which is exactly what showed up as captions arriving several seconds
    late during testing.

    `silence_duration_ms`/`min_speech_duration_ms` are pulled well below
    their documented defaults (500ms / 250ms) so VAD calls a segment
    finished on a much shorter pause. This matters most for the
    translated-caption path (see CaptionSession._receive), which relies on
    `transcript.final` firing regularly -- with the default gap, a real
    speaker's normal pauses between sentences often weren't long enough to
    trigger one at all, leaving translated captions to lean entirely on the
    periodic partial-translate fallback instead of ever settling on a
    proper, complete-sentence translation.
    """
    if language_code in (None, "unknown"):
        stt_language_code = "auto"
    else:
        stt_language_code = STT_LANGUAGE_CODE_OVERRIDES.get(language_code, language_code)

    params = {
        "model": "saaras:v3-realtime",
        "language_code": stt_language_code,
        "mode": mode,
        "stream_type": "fast",
        "endpointing": "vad",
        "silence_duration_ms": "300",
        "min_speech_duration_ms": "150",
        "encoding": "linear16",
        "sample_rate": "16000",
        "return_timestamps": "false",
    }
    return f"{REALTIME_WS_URL}?{urllib.parse.urlencode(params)}"


def _strip_wav_header(audio_b64):
    """The browser sends each chunk as a full 44-byte-header WAV file (see
    encodeWAV() in index.html), but the realtime endpoint's `encoding` /
    `sample_rate` query params already declare the format, so `audio_input`
    expects headerless PCM -- send the raw sample bytes only."""
    raw = base64.b64decode(audio_b64)
    return base64.b64encode(raw[44:]).decode("ascii")


# mayura:v1's documented language set (Sarvam's Translate API reference lists
# exactly these 11 -- "12 core languages" in the docs' prose, but the schema
# only ever enumerates 11). Every other language in the dropdown is only
# covered by sarvam-translate:v1. Calling mayura:v1 with a target language
# outside this set is very likely why some translations were coming out
# wrong: it's silently the wrong model for that language, not a quality
# issue with translation itself.
MAYURA_LANGUAGES = frozenset({
    "bn-IN", "en-IN", "gu-IN", "hi-IN", "kn-IN", "ml-IN",
    "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
})


def parse_caption_choice(raw_choice):
    """Map a frontend "Captions" dropdown value to (stt_mode, target_language).

    Saaras natively supports "translate" (to English only -- the realtime
    endpoint's `mode` param has no way to target any other language) and
    "codemix" as connection-level `mode`s, used directly here as a single
    API hop. For any other target language the dropdown sends
    "xlate:<lang-code>": there is no native equivalent for that at all, so
    Saaras runs in plain "transcribe" mode and the finalized (and
    periodically, the growing partial) text is translated into that
    language with a separate call to the Translate API
    (client.text.translate) -- see CaptionSession._receive/_translate.

    Note: per the realtime endpoint's own spec, `mode` is "applied on the
    final transcript, not on partial transcripts -- streaming partials are
    always straight transcription regardless of this value." So with
    "translate" (English), partials will show native-language text and only
    flip to English once each sentence's transcript.final arrives -- a
    known tradeoff of using Saaras' native mode directly instead of the
    Translate API pipeline that "xlate:<code>" gets.
    """
    if raw_choice and raw_choice.startswith("xlate:"):
        return "transcribe", raw_choice.split(":", 1)[1]
    return raw_choice or "transcribe", None


class CaptionSession:
    """One persistent saaras:v3-realtime connection for a single browser tab.

    saaras:v3-realtime (beta, gated by enable_saaras_v3_realtime_streaming_users)
    expects one long-lived WebSocket connection that raw PCM frames are
    continuously fed into as `audio_input` events, emitting `transcript.partial`
    / `transcript.final` events as speech segments are recognized and finalize.
    `language_code` and `mode` are connection-level query params, so changing
    either from the UI tears down the old connection and opens a fresh one
    rather than reconfiguring it mid-stream.

    A dedicated asyncio loop runs in a background thread: one task pulls
    audio frames off a queue and forwards them, another loops on recv() and
    pushes captions back to the browser as they arrive.

    Two things keep captions feeling live rather than laggy: `endpointing=vad`
    (the default) tells Saaras to end a speech segment (and finalize its
    transcript) on a natural pause, and a periodic `flush` event forces out
    whatever's been recognized so far every couple of seconds even during
    continuous, pause-free speech.

    If `target_language` is set, Saaras runs in plain "transcribe" mode and
    each finalized line is additionally translated into that language via
    the Translate API before being sent to the browser -- see
    `parse_caption_choice` and `_translate`.
    """

    # How often to force-finalize the current segment during continuous
    # speech, so a caption shows up even if the speaker never pauses.
    FLUSH_INTERVAL_SECONDS = 1.5

    # The cross-language translate hop (_translate) does noticeably better
    # on a complete-ish sentence than on a half-finished fragment, so give it
    # a bit more runway before force-flushing than the native STT modes get
    # -- but not so much that it feels laggy on top of the translate call
    # itself.
    FLUSH_INTERVAL_TRANSLATE_SECONDS = 2.2

    # Minimum gap between translating the *growing partial* for translated
    # mode. `transcript.final` only fires once VAD detects a real pause --
    # for continuous speech (or a noisy mic that never reads as truly
    # silent) that may never happen, which left translated captions stuck
    # showing only the original-language interim text forever. This timer
    # translates whatever's been recognized so far periodically regardless,
    # the same way FLUSH_INTERVAL_SECONDS keeps native captions moving.
    # Lowered from 2.5s -- translated captions were noticeably laggier than
    # native ones, and the Translate API round trip (~0.3-0.5s) leaves
    # enough headroom below this that overlapping calls stay rare even at
    # this tighter interval (see _partial_translate_inflight guard).
    PARTIAL_TRANSLATE_INTERVAL_SECONDS = 1.5

    def __init__(self, sid, language_code, mode, target_language=None):
        self.sid = sid
        self.language_code = language_code
        self.mode = mode
        self.target_language = target_language
        self.client = None
        self.loop = asyncio.new_event_loop()
        self.queue = asyncio.Queue()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self._stopped = False
        # time.monotonic() is an arbitrary-epoch clock (often seconds since
        # boot, not since this session) -- seeding this at 0.0 made
        # `now - 0.0 >= PARTIAL_TRANSLATE_INTERVAL_SECONDS` true on the very
        # first partial, firing a translate call on a 1-2 word fragment
        # before there's enough text for reliable language detection. Seed
        # it at session start instead so the interval is measured from here.
        self._last_partial_translate_time = time.monotonic()
        self._partial_translate_inflight = False

    def start(self):
        self.thread.start()

    def send_audio(self, audio_b64):
        if self._stopped:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.queue.put(audio_b64), self.loop)
        except RuntimeError:
            self._stopped = True  # loop died (e.g. connection never opened)

    def stop(self):
        if self._stopped:
            return
        self._stopped = True
        try:
            asyncio.run_coroutine_threadsafe(self.queue.put(None), self.loop)
        except RuntimeError:
            pass  # loop already dead, nothing to stop

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._session())
        except Exception as e:
            logger.error(f"[{self.sid}] session loop error: {e}")
            self._stopped = True
            caption_sessions.pop(self.sid, None)
            with app.app_context():
                socketio.emit(
                    "error", {"message": f"Captioning failed to start: {e}"}, to=self.sid
                )
        finally:
            self.loop.close()

    async def _session(self):
        self.client = AsyncSarvamAI(api_subscription_key=SARVAM_API_KEY)
        url = _build_realtime_url(self.language_code, self.mode)
        logger.info(
            f"[{self.sid}] opening realtime streaming connection (language={self.language_code}, "
            f"mode={self.mode}, target_language={self.target_language})"
        )

        async with websockets.connect(
            url, additional_headers={"API-SUBSCRIPTION-KEY": SARVAM_API_KEY}
        ) as ws:
            logger.info(f"[{self.sid}] connected")
            receiver = asyncio.create_task(self._receive(ws))
            try:
                flush_interval = (
                    self.FLUSH_INTERVAL_TRANSLATE_SECONDS
                    if self.target_language
                    else self.FLUSH_INTERVAL_SECONDS
                )
                last_flush = time.monotonic()
                while True:
                    audio_b64 = await self.queue.get()
                    if audio_b64 is None:  # stop sentinel
                        break
                    await ws.send(json.dumps({
                        "event": "audio_input",
                        "audio": _strip_wav_header(audio_b64),
                    }))

                    # Force out whatever's been recognized so far every couple
                    # of seconds, rather than waiting for the speaker to pause
                    # or for the stream to end -- this is what keeps captions
                    # showing up during a long, continuous sentence.
                    now = time.monotonic()
                    if now - last_flush >= flush_interval:
                        await ws.send(json.dumps({"event": "flush"}))
                        last_flush = now

                # Flush any buffered audio so the final segment is emitted,
                # then tell the server this session is done.
                await ws.send(json.dumps({"event": "flush"}))
                await ws.send(json.dumps({"event": "end"}))
                # Give the receiver a moment to drain remaining captions.
                await asyncio.sleep(1.5)
            finally:
                receiver.cancel()
                logger.info(f"[{self.sid}] connection closed")

    async def _receive(self, ws):
        """Continuously read caption messages and push them to the browser."""
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (TypeError, ValueError):
                    continue
                event = msg.get("event")

                if event == "error":
                    message = msg.get("message") or str(msg)
                    logger.error(f"[{self.sid}] stream error ({msg.get('code')}): {message}")
                    with app.app_context():
                        socketio.emit(
                            "error", {"message": f"Captioning error: {message}"}, to=self.sid
                        )
                    if msg.get("is_fatal"):
                        break
                    continue

                if event == "session.begin":
                    logger.info(f"[{self.sid}] session began: {msg.get('request_id')}")
                    continue
                if event == "session.end":
                    logger.info(f"[{self.sid}] session ended: {msg}")
                    continue
                if event not in ("transcript.partial", "transcript.final"):
                    continue  # vad.speech_start/end, config.updated, pong -- nothing to show

                text = (msg.get("text") or "").strip()
                if not text:
                    continue

                logger.debug(
                    f"[{self.sid}] {event} utterance_idx={msg.get('utterance_idx')} "
                    f"len={len(text)} text={text!r}"
                )

                if event == "transcript.partial":
                    # In translated mode, never show the raw original-
                    # language partial at all -- only ever the translated
                    # text (below). Showing it as a brief placeholder before
                    # the first translation landed was a deliberate
                    # instant-feedback tradeoff, but it meant every utterance
                    # opened with a flash of the wrong language, which reads
                    # as "English is interfering" just as much as a
                    # long-lived wrong-language caption would. A translated
                    # mode session would rather wait the ~1-2s for real
                    # translated text than show anything untranslated.
                    if not self.target_language:
                        with app.app_context():
                            socketio.emit("caption", {"text": text}, to=self.sid)

                    # For translated mode, ALSO periodically translate the
                    # growing partial itself rather than only ever
                    # translating on transcript.final. A final only fires
                    # once VAD detects a real pause -- for continuous speech
                    # (or a mic that never reads as truly silent) that can
                    # simply never happen, which left translated captions
                    # stuck on the original language forever. This is
                    # throttled (interval + inflight guard) since it's an
                    # extra Translate API call per firing.
                    # A 1-2 word fragment doesn't give the Translate API's
                    # own language-detection enough signal to work with, and
                    # it's more likely to just echo the text back unchanged
                    # (see the passthrough check in _translate_and_emit) --
                    # wait for a bit more context before spending a call on it.
                    if (
                        self.target_language
                        and not self._partial_translate_inflight
                        and len(text.split()) >= 3
                    ):
                        now = time.monotonic()
                        if now - self._last_partial_translate_time >= self.PARTIAL_TRANSLATE_INTERVAL_SECONDS:
                            # Only _translate_partial_and_emit resets this
                            # timestamp, and only when a translation actually
                            # came back (not a passthrough skip) -- a
                            # rejected attempt shouldn't cost a fresh full
                            # cooldown, or a couple of early passthrough
                            # misses on short text compounds into several
                            # extra seconds of visible delay before anything
                            # ever shows up.
                            asyncio.create_task(
                                self._translate_partial_and_emit(text, self.language_code)
                            )
                    continue

                # transcript.final
                if self.target_language:
                    # Translate in the background instead of awaiting it here.
                    # Awaiting it inline would block this loop from reading
                    # the *next* STT message until the Translate API round
                    # trip finishes, which serializes every caption behind
                    # the previous one's translation latency -- exactly what
                    # was making translated captions feel slow. Firing it as
                    # a task lets Saaras keep streaming while translations
                    # resolve concurrently.
                    #
                    # Deliberately NOT using msg.get("language") here: that's
                    # Saaras's own per-chunk auto-LID guess, which can be
                    # transiently wrong (e.g. defaults to English for the
                    # first second or two of non-English speech before
                    # locking on -- see the Auto-detect hint in the UI).
                    # Trusting it as the Translate API's source language was
                    # exactly what caused Auto-detect + "Captions: Hindi" to
                    # translate correctly sometimes and pass through
                    # untranslated/wrong other times. self.language_code is
                    # either the user's own explicit selection (always
                    # correct) or "unknown", which _translate() below
                    # already turns into a proper source_language_code="auto"
                    # for mayura:v1 -- far more reliable than Saaras's guess.
                    asyncio.create_task(self._translate_and_emit(text, self.language_code))
                else:
                    with app.app_context():
                        socketio.emit("caption", {"text": text}, to=self.sid)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.info(f"[{self.sid}] receiver ended: {e}")

    async def _translate_and_emit(self, text, source_language_code):
        translated = await self._translate(text, source_language_code)
        if translated is None:
            return  # skip rather than show an untranslated/wrong-language line
        with app.app_context():
            socketio.emit("caption", {"text": translated}, to=self.sid)

    async def _translate_partial_and_emit(self, text, source_language_code):
        """Same as _translate_and_emit, but for a not-yet-finalized partial --
        guards against overlapping calls piling up if the Translate API is
        slower than PARTIAL_TRANSLATE_INTERVAL_SECONDS."""
        self._partial_translate_inflight = True
        try:
            translated = await self._translate(text, source_language_code)
            if translated is None:
                return  # don't reset _last_partial_translate_time -- retry on the next partial instead of waiting out a fresh cooldown
            self._last_partial_translate_time = time.monotonic()
            with app.app_context():
                socketio.emit("caption", {"text": translated}, to=self.sid)
        finally:
            self._partial_translate_inflight = False

    async def _translate(self, text, source_language_code):
        """Translate a caption line (partial or final) into self.target_language.

        Picks the Translate model based on the target language rather than
        hardcoding mayura:v1: mayura:v1 only covers 11 languages (see
        MAYURA_LANGUAGES) and using it outside that set is the wrong model,
        not a translation-quality problem. Returns None (rather than the
        untranslated source text) on failure, or when we can't resolve a
        usable source language -- callers must skip emitting a caption for
        None instead of showing it, since a stray line in the wrong language
        reads as "the translation isn't working" just as much as no caption
        at all would.
        """
        target = self.target_language
        use_mayura = target in MAYURA_LANGUAGES

        if use_mayura:
            model = "mayura:v1"
            # "modern-colloquial" over "formal": this app's captions want
            # natural spoken-Hindi output, which in practice means common
            # English loanwords mixed in where that's how people actually
            # talk (Hinglish) -- "formal" avoids that entirely but reads
            # stiff/literal for captions. The random flashes of raw English
            # some testing showed were a separate display-priority bug (now
            # fixed in _receive/showCaption), not caused by this mode
            # choice -- don't conflate the two again.
            mode = "modern-colloquial"
            source = "auto" if source_language_code in (None, "unknown") else source_language_code
        else:
            model = "sarvam-translate:v1"
            mode = None  # sarvam-translate:v1 is formal-only, no mode choice
            if source_language_code in (None, "unknown"):
                # sarvam-translate:v1 has no source_language_code="auto" --
                # passing it would just fail. Without a confirmed source,
                # skip rather than guess one.
                logger.warning(
                    f"[{self.sid}] no confirmed source language for {model} "
                    f"(target={target}); skipping this caption"
                )
                return None
            source = source_language_code

        try:
            kwargs = dict(
                input=text,
                source_language_code=source,
                target_language_code=target,
                model=model,
            )
            if mode:
                kwargs["mode"] = mode
            result = await self.client.text.translate(**kwargs)
            translated = result.translated_text
            # With source_language_code="auto" on a short/ambiguous fragment
            # (most likely early in an utterance, before there's much text
            # to work with), the Translate API can fail to detect a source
            # language different from the target and just echo the input
            # back unchanged -- showing that as a "translated" caption is
            # exactly the "English is interfering" symptom, just from the
            # Translate API this time rather than the earlier display bug.
            if translated.strip().lower() == text.strip().lower():
                logger.warning(
                    f"[{self.sid}] translation to {target} came back unchanged "
                    f"(likely a source-detection miss on short text); skipping"
                )
                return None
            return translated
        except Exception as e:
            logger.error(f"[{self.sid}] translation to {target} ({model}) failed: {e}")
            return None


# Active caption sessions keyed by socket session id. One per client: unlike
# examples/Live_Video_Transcription this UI shows a single caption track at a
# time, so a new start_stream simply replaces whatever was running before.
caption_sessions = {}


@app.route("/")
def index():
    """Serve the main page (no-cache so JS updates always load)."""
    resp = app.make_response(render_template("index.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@socketio.on("connect")
def handle_connect():
    logger.info(f"Client connected: {request.sid}")
    emit("status", {"message": "Connected to captioning service"})


@socketio.on("disconnect")
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")
    session = caption_sessions.pop(request.sid, None)
    if session:
        session.stop()


@socketio.on("start_stream")
def handle_start_stream(data):
    """Open (or restart) the captioning session for this client."""
    language_code = (data or {}).get("language_code", "unknown")
    raw_choice = (data or {}).get("mode", "transcribe")
    stt_mode, target_language = parse_caption_choice(raw_choice)

    existing = caption_sessions.pop(request.sid, None)
    if existing:
        existing.stop()

    logger.info(
        f"Starting caption stream for {request.sid} "
        f"(language={language_code}, stt_mode={stt_mode}, target_language={target_language})"
    )
    session = CaptionSession(request.sid, language_code, stt_mode, target_language)
    caption_sessions[request.sid] = session
    session.start()


@socketio.on("stop_stream")
def handle_stop_stream(data=None):
    session = caption_sessions.pop(request.sid, None)
    if session:
        logger.info(f"Stopping caption stream for {request.sid}")
        session.stop()


@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    """Forward an incoming audio chunk into the active captioning session."""
    try:
        audio_base64 = (data or {}).get("audio")
        if not audio_base64:
            return

        session = caption_sessions.get(request.sid)
        if session is None:
            # No active session -- client may not have sent start_stream yet.
            return

        session.send_audio(audio_base64)

    except Exception as e:
        logger.error(f"Error forwarding audio chunk: {e}")
        emit("error", {"message": f"Processing error: {str(e)}"})


if __name__ == "__main__":
    logger.info("Starting Real-Time Speech Captioning demo server...")
    logger.info(f"Open http://{config.HOST}:{config.PORT} in your browser")
    socketio.run(
        app, debug=config.DEBUG, host=config.HOST, port=config.PORT, allow_unsafe_werkzeug=True
    )
