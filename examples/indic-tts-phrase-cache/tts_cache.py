"""A canonical cache key for Indic text-to-speech requests, plus a small disk cache.

The same Indic phrase can be spelled several ways that look identical on screen and
are meant to be read aloud the same way. A byte-exact cache treats each spelling as
a separate phrase and pays for a separate synthesis call. This module builds one key
for all of them, under a normalisation policy the caller can read, switch off layer
by layer, and measure.

Design notes and the evidence behind every default live in
docs/specs/indic-tts-phrase-cache.md.

What this module does NOT claim
-------------------------------
It never claims two texts sound the same. It claims they map to one key under a
stated policy. Proving the audio question needs a subscription key and two calls to
the server, and neither was available when this was written.

The rule that sets every default: a layer is on by default only when the difference
it folds cannot change what is spoken by any conforming engine -- because Unicode
defines the two forms as the same text, or because the characters removed are
invisible format controls with no phonetic role. A layer whose fold could change the
sound is off by default, whatever it would save. A false miss costs one call; a false
hit plays the wrong audio to somebody who cannot see the screen.

  nfc                on   Unicode canonical equivalence. The strongest ground here:
                          an engine that spoke two canonically equivalent strings
                          differently would be non-conforming.
  nukta_fold         off  A nukta is phonemic. Devanagari JA and ZA are different
                          consonants, and so are Odia DDA and RRA. Folding them is
                          a large saving and a real risk.
  zero_width_space   on   U+200B and U+FEFF are a line-break opportunity and a byte
                          order mark. No script gives either a phonetic role.
  zero_width_joiner  off  U+200C and U+200D change which conjunct is rendered. This
                          module's position is that they should not change the sound,
                          but a position is not a measurement.
  whitespace         on   Leading, trailing and doubled spaces come from templating
                          engines and editors, not from writers.
  punctuation_tail   on   THE ONE ASSUMPTION. A trailing danda and a trailing full
                          stop are treated as the same end-of-statement mark. That is
                          an assumption about two orthographic traditions, not a
                          Unicode definition, and it is one flag away from off. The
                          double danda U+0965 ends a verse and is never folded, and
                          text with no terminator keeps its own key.
  digit_form         off  Native Indic digits may well be spoken exactly like their
                          ASCII forms. May well is not good enough: the engine does
                          its own numeric preprocessing and its documentation warns
                          that 10000 and 10,000 are read differently, which is direct
                          evidence that surface form matters to it.

Two orderings are load-bearing rather than cosmetic:

  * zero_width_space runs before whitespace, because str.split() does not treat
    U+200B as whitespace. A zero-width space sitting between two real spaces blocks
    the collapse if the strip has not already run.
  * nukta_fold runs after nfc, because the nukta inside a precomposed letter is not
    a separate character until NFC has decomposed it. The other order does half the
    job in silence.

And one invariant matters more than any of them: the canonical form is only ever
hashed. What gets sent for synthesis on a miss is the caller's original text, byte
for byte. That is what makes aggressive folding survivable at all.

Everything here is standard library. Nothing except speak() touches a client, and
speak() takes the client as an argument, so the whole key, cache and simulator run
with the network unreachable.
"""
from __future__ import annotations

import base64
import hashlib
import json
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

KEY_VERSION: int = 1
INDEX_SCHEMA: int = 1
DEFAULT_MAX_ENTRIES: int = 128
INDIC_FIRST: int = 0x0900
INDIC_LAST: int = 0x0DFF

LAYER_NFC: str = "nfc"
LAYER_NUKTA_FOLD: str = "nukta_fold"
LAYER_ZERO_WIDTH_SPACE: str = "zero_width_space"
LAYER_ZERO_WIDTH_JOINER: str = "zero_width_joiner"
LAYER_WHITESPACE: str = "whitespace"
LAYER_PUNCTUATION_TAIL: str = "punctuation_tail"
LAYER_DIGIT_FORM: str = "digit_form"

LAYER_ORDER: tuple[str, ...] = (
    LAYER_NFC,
    LAYER_NUKTA_FOLD,
    LAYER_ZERO_WIDTH_SPACE,
    LAYER_ZERO_WIDTH_JOINER,
    LAYER_WHITESPACE,
    LAYER_PUNCTUATION_TAIL,
    LAYER_DIGIT_FORM,
)

OFF_BY_DEFAULT: frozenset[str] = frozenset(
    {LAYER_NUKTA_FOLD, LAYER_ZERO_WIDTH_JOINER, LAYER_DIGIT_FORM}
)
DEFAULT_LAYERS: frozenset[str] = frozenset(LAYER_ORDER) - OFF_BY_DEFAULT


def _derive_composition_exclusions() -> dict[str, str]:
    """Find the Indic characters NFC decomposes and refuses to put back together.

    A composition exclusion has a canonical decomposition, so NFD splits it, and it
    is on the exclusion list, so the composition step may not rejoin it. Its
    canonical form is therefore the multi-character sequence, which is the opposite
    of what "NFC composes" suggests.

    Derived from the installed Unicode data rather than typed out, so the day a
    Python release changes the table, the pinned test says so.
    """
    table: dict[str, str] = {}
    for code_point in range(INDIC_FIRST, INDIC_LAST + 1):
        char = chr(code_point)
        decomposition = unicodedata.decomposition(char)
        if not decomposition or decomposition.startswith("<"):
            continue
        decomposed = unicodedata.normalize("NFD", char)
        if unicodedata.normalize("NFC", decomposed) != char:
            table[char] = decomposed
    return table


INDIC_COMPOSITION_EXCLUSIONS: Mapping[str, str] = _derive_composition_exclusions()

# An explicit list, never a category or a combining-class test. TELUGU VOWEL SIGN AA
# is category Mn exactly like a nukta, so a category-based fold silently eats it.
NUKTA_SIGNS: str = "".join(
    chr(code_point)
    for code_point in (0x093C, 0x09BC, 0x0A3C, 0x0ABC, 0x0B3C, 0x0CBC)
)

ZERO_WIDTH_SPACES: str = chr(0x200B) + chr(0xFEFF)
ZERO_WIDTH_JOINERS: str = chr(0x200C) + chr(0x200D)

DANDA: str = chr(0x0964)
DOUBLE_DANDA: str = chr(0x0965)          # ends a verse, deliberately never folded
TERMINATORS: str = DANDA + "."

DIGIT_BLOCK_STARTS: tuple[int, ...] = (
    0x0966,   # Devanagari
    0x09E6,   # Bengali
    0x0A66,   # Gurmukhi
    0x0AE6,   # Gujarati
    0x0B66,   # Oriya
    0x0BE6,   # Tamil
    0x0C66,   # Telugu
    0x0CE6,   # Kannada
    0x0D66,   # Malayalam
)

DIGIT_FOLD: Mapping[str, str] = {
    chr(block_start + offset): str(offset)
    for block_start in DIGIT_BLOCK_STARTS
    for offset in range(10)
}

# The eleven parameters of the synthesis call that change the audio. The server
# cache flag is a transport hint and request options are timeouts and retries, so
# neither belongs in the key; text is normalised separately.
KEY_FIELDS: tuple[str, ...] = (
    "language_code",
    "model",
    "speaker",
    "pace",
    "pitch",
    "loudness",
    "speech_sample_rate",
    "output_audio_codec",
    "temperature",
    "enable_preprocessing",
    "dict_id",
)

_NUKTA_TABLE = {ord(char): None for char in NUKTA_SIGNS}
_ZERO_WIDTH_SPACE_TABLE = {ord(char): None for char in ZERO_WIDTH_SPACES}
_ZERO_WIDTH_JOINER_TABLE = {ord(char): None for char in ZERO_WIDTH_JOINERS}
_DIGIT_TABLE = {ord(char): value for char, value in DIGIT_FOLD.items()}


# ---------------------------------------------------------------------------
# The layers
# ---------------------------------------------------------------------------


def _apply_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _fold_nuktas(text: str) -> str:
    return text.translate(_NUKTA_TABLE)


def _strip_zero_width_spaces(text: str) -> str:
    return text.translate(_ZERO_WIDTH_SPACE_TABLE)


def _strip_zero_width_joiners(text: str) -> str:
    return text.translate(_ZERO_WIDTH_JOINER_TABLE)


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _fold_punctuation_tail(text: str) -> str:
    """Fold a trailing run of terminators, and the whitespace around it, to one danda.

    Text that ends in no terminator is returned untouched, because whether a sentence
    terminates at all is the part most likely to change prosody.
    """
    end = len(text)
    found_terminator = False
    while end:
        char = text[end - 1]
        if char in TERMINATORS:
            found_terminator = True
        elif not char.isspace():
            break
        end -= 1
    if not found_terminator:
        return text
    return text[:end] + DANDA


def _fold_digit_forms(text: str) -> str:
    return text.translate(_DIGIT_TABLE)


_LAYER_FUNCTIONS: Mapping[str, Callable[[str], str]] = {
    LAYER_NFC: _apply_nfc,
    LAYER_NUKTA_FOLD: _fold_nuktas,
    LAYER_ZERO_WIDTH_SPACE: _strip_zero_width_spaces,
    LAYER_ZERO_WIDTH_JOINER: _strip_zero_width_joiners,
    LAYER_WHITESPACE: _collapse_whitespace,
    LAYER_PUNCTUATION_TAIL: _fold_punctuation_tail,
    LAYER_DIGIT_FORM: _fold_digit_forms,
}


# ---------------------------------------------------------------------------
# Policy and request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NormalisationPolicy:
    """The set of layers that are switched on. Order of application is LAYER_ORDER."""

    layers: frozenset[str]

    @classmethod
    def default(cls) -> NormalisationPolicy:
        return cls(layers=DEFAULT_LAYERS)

    @classmethod
    def none(cls) -> NormalisationPolicy:
        return cls(layers=frozenset())

    @classmethod
    def all_layers(cls) -> NormalisationPolicy:
        return cls(layers=frozenset(LAYER_ORDER))

    def with_layer(self, name: str) -> NormalisationPolicy:
        _check_layer_name(name)
        return NormalisationPolicy(layers=self.layers | {name})

    def without_layer(self, name: str) -> NormalisationPolicy:
        _check_layer_name(name)
        return NormalisationPolicy(layers=self.layers - {name})

    def fingerprint(self) -> str:
        return ",".join(sorted(self.layers))


def _check_layer_name(name: str) -> None:
    if name not in LAYER_ORDER:
        raise ValueError(
            "unknown layer %r; the layers are %s" % (name, ", ".join(LAYER_ORDER))
        )


@dataclass(frozen=True)
class SynthesisRequest:
    """One synthesis request: the text plus every parameter that changes the audio."""

    text: str
    language_code: str
    model: str = "bulbul:v3"
    speaker: str = "shubh"
    pace: float = 1.0
    pitch: float | None = None
    loudness: float | None = None
    speech_sample_rate: int = 24000
    output_audio_codec: str = "wav"
    temperature: float = 0.6
    enable_preprocessing: bool | None = None
    dict_id: str | None = None

    def to_convert_kwargs(self) -> dict[str, object]:
        """Arguments for the synthesis call: the ORIGINAL text, and no None values.

        The canonical form never leaves this module. The server cache flag is never
        sent, because nothing this repo may use supports it.
        """
        kwargs: dict[str, object] = {"text": self.text}
        for field in KEY_FIELDS:
            value = getattr(self, field)
            if value is not None:
                kwargs[field] = value
        return kwargs


# ---------------------------------------------------------------------------
# The key
# ---------------------------------------------------------------------------


def _resolve(policy: NormalisationPolicy | None) -> NormalisationPolicy:
    return NormalisationPolicy.default() if policy is None else policy


def canonical_text(text: str, policy: NormalisationPolicy | None = None) -> str:
    """Apply the policy's layers, in LAYER_ORDER. The result is only ever hashed."""
    active = _resolve(policy).layers
    for layer in LAYER_ORDER:
        if layer in active:
            text = _LAYER_FUNCTIONS[layer](text)
    return text


def canonical_key(
    request: SynthesisRequest, policy: NormalisationPolicy | None = None
) -> str:
    """The cache key: 64 lowercase hex characters, and nothing else in the process.

    The key version and the policy fingerprint are both inside the digest, so
    entries built under one normalisation algorithm or one layer set can never be
    served to a caller asking under another.
    """
    resolved = _resolve(policy)
    parts = [
        "tts-cache/v%d" % KEY_VERSION,
        "layers=" + resolved.fingerprint(),
        "text=" + canonical_text(request.text, resolved),
    ]
    parts.extend("%s=%r" % (field, getattr(request, field)) for field in KEY_FIELDS)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The disk cache
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheEntry:
    key: str
    filename: str
    sha256: str
    byte_length: int
    last_used: int
    language_code: str


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    evictions: int
    dropped: int


class PhraseCache:
    """A content-addressed disk cache of synthesised phrases, capped and LRU.

    Single process. No file locking, no expiry, no re-encoding: bytes in, bytes out.
    Recency is an integer tick rather than a wall clock, because two writes in the
    same millisecond would tie on a timestamp and make eviction depend on dict
    iteration order.
    """

    def __init__(
        self,
        root: Path,
        *,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        policy: NormalisationPolicy | None = None,
    ) -> None:
        self._root = Path(root)
        self._max_entries = max_entries
        self._policy = _resolve(policy)
        self._entries: dict[str, CacheEntry] = {}
        self._tick = 0
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._dropped = 0
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    # -- layout ------------------------------------------------------------

    @property
    def index_path(self) -> Path:
        return self._root / "index.json"

    @property
    def audio_dir(self) -> Path:
        return self._root / "audio"

    @property
    def stats(self) -> CacheStats:
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            dropped=self._dropped,
        )

    # -- index -------------------------------------------------------------

    def _load(self) -> None:
        """Read the index, or start empty. A damaged index is never a crash.

        Anything that is not this cache's own index -- wrong shape, wrong schema,
        wrong key version, a different layer set -- is discarded rather than
        repaired, because keys from two policies are not comparable and serving
        one to the other would play the wrong audio.
        """
        try:
            raw = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        if raw.get("schema") != INDEX_SCHEMA or raw.get("key_version") != KEY_VERSION:
            return
        if raw.get("layers") != sorted(self._policy.layers):
            return
        tick = raw.get("tick")
        entries = raw.get("entries")
        if not isinstance(tick, int) or not isinstance(entries, dict):
            return

        loaded: dict[str, CacheEntry] = {}
        for key, record in entries.items():
            if not isinstance(record, dict):
                return
            try:
                loaded[key] = CacheEntry(
                    key=key,
                    filename=record["filename"],
                    sha256=record["sha256"],
                    byte_length=record["byte_length"],
                    last_used=record["last_used"],
                    language_code=record["language_code"],
                )
            except KeyError:
                return

        self._entries = loaded
        self._tick = tick

    def _save(self) -> None:
        payload = {
            "schema": INDEX_SCHEMA,
            "key_version": KEY_VERSION,
            "layers": sorted(self._policy.layers),
            "max_entries": self._max_entries,
            "tick": self._tick,
            "entries": {
                key: {
                    "filename": entry.filename,
                    "sha256": entry.sha256,
                    "byte_length": entry.byte_length,
                    "last_used": entry.last_used,
                    "language_code": entry.language_code,
                }
                for key, entry in self._entries.items()
            },
        }
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def flush(self) -> None:
        self._save()

    # -- reads and writes --------------------------------------------------

    def get(self, request: SynthesisRequest) -> bytes | None:
        digest = canonical_key(request, self._policy)
        entry = self._entries.get(digest)
        if entry is None:
            self._misses += 1
            return None

        try:
            audio = (self.audio_dir / entry.filename).read_bytes()
        except OSError:
            audio = None

        damaged = (
            audio is None
            or len(audio) != entry.byte_length
            or hashlib.sha256(audio).hexdigest() != entry.sha256
        )
        if damaged:
            self._discard(digest)
            self._dropped += 1
            self._misses += 1
            self._save()
            return None

        self._tick += 1
        self._entries[digest] = replace(entry, last_used=self._tick)
        self._hits += 1
        self._save()
        return audio

    def put(self, request: SynthesisRequest, audio: bytes) -> str:
        digest = canonical_key(request, self._policy)
        filename = digest + "." + request.output_audio_codec
        (self.audio_dir / filename).write_bytes(audio)
        self._tick += 1
        self._entries[digest] = CacheEntry(
            key=digest,
            filename=filename,
            sha256=hashlib.sha256(audio).hexdigest(),
            byte_length=len(audio),
            last_used=self._tick,
            language_code=request.language_code,
        )
        self._evict()
        self._save()
        return digest

    def keys(self) -> tuple[str, ...]:
        """Every key in LRU order, oldest first."""
        return tuple(entry.key for entry in self._in_lru_order())

    def speak(self, request: SynthesisRequest, client: object) -> bytes:
        """Return the phrase's audio, calling the API only when the cache misses.

        The ORIGINAL text is what goes to the server. The canonical form was only
        ever used to find the entry.
        """
        cached = self.get(request)
        if cached is not None:
            return cached
        response = client.text_to_speech.convert(**request.to_convert_kwargs())
        audio = base64.b64decode(response.audios[0])
        self.put(request, audio)
        return audio

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, request: SynthesisRequest) -> bool:
        return canonical_key(request, self._policy) in self._entries

    # -- internals ---------------------------------------------------------

    def _in_lru_order(self) -> list[CacheEntry]:
        # The key is in the sort only so that a hand-edited index with duplicate
        # ticks still evicts deterministically.
        return sorted(self._entries.values(), key=lambda e: (e.last_used, e.key))

    def _discard(self, digest: str) -> None:
        entry = self._entries.pop(digest, None)
        if entry is not None:
            (self.audio_dir / entry.filename).unlink(missing_ok=True)

    def _evict(self) -> None:
        while len(self._entries) > self._max_entries:
            victim = self._in_lru_order()[0]
            self._discard(victim.key)
            self._evictions += 1


# ---------------------------------------------------------------------------
# The replay simulator
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayResult:
    requests: int
    hits: int
    misses: int
    calls_saved: int
    distinct_keys: int      # distinct keys across the whole log, whatever the capacity
    final_size: int         # entries still resident at the end
    evictions: int

    @property
    def hit_rate(self) -> float:
        if not self.requests:
            return 0.0
        return self.hits / self.requests


@dataclass(frozen=True)
class LadderRung:
    index: int
    layer: str | None
    policy: NormalisationPolicy
    result: ReplayResult
    additional_calls_saved: int


def replay(
    log: Sequence[SynthesisRequest],
    policy: NormalisationPolicy | None = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> ReplayResult:
    """Count the calls a cache of this size, under this policy, would have made.

    No audio, no disk, no network: the same LRU decisions PhraseCache makes, over
    the same keys, which is what makes the two agree.
    """
    resolved = _resolve(policy)
    live: OrderedDict[str, bool] = OrderedDict()
    seen: set[str] = set()
    hits = 0
    misses = 0
    evictions = 0
    for request in log:
        digest = canonical_key(request, resolved)
        seen.add(digest)
        if digest in live:
            live.move_to_end(digest)
            hits += 1
            continue
        misses += 1
        live[digest] = True
        if len(live) > max_entries:
            live.popitem(last=False)
            evictions += 1
    return ReplayResult(
        requests=len(log),
        hits=hits,
        misses=misses,
        calls_saved=hits,
        distinct_keys=len(seen),
        final_size=len(live),
        evictions=evictions,
    )


def layer_ladder(
    log: Sequence[SynthesisRequest], max_entries: int = DEFAULT_MAX_ENTRIES
) -> tuple[LadderRung, ...]:
    """Switch the layers on one at a time, in order, and measure each one's share."""
    active: frozenset[str] = frozenset()
    policy = NormalisationPolicy(layers=active)
    rungs = [
        LadderRung(
            index=0,
            layer=None,
            policy=policy,
            result=replay(log, policy, max_entries=max_entries),
            additional_calls_saved=0,
        )
    ]
    for index, layer in enumerate(LAYER_ORDER, start=1):
        active = active | {layer}
        policy = NormalisationPolicy(layers=active)
        result = replay(log, policy, max_entries=max_entries)
        rungs.append(
            LadderRung(
                index=index,
                layer=layer,
                policy=policy,
                result=result,
                additional_calls_saved=result.calls_saved - rungs[-1].result.calls_saved,
            )
        )
    return tuple(rungs)


def format_ladder(rungs: Sequence[LadderRung]) -> str:
    """A plain-text version of the ladder. No colour, no symbols, no emoji."""
    header = "%-4s %-19s %6s %7s %8s %10s" % (
        "rung", "layer added", "hits", "misses", "keys", "extra saved",
    )
    lines = [header, "-" * len(header)]
    for rung in rungs:
        lines.append(
            "%-4d %-19s %6d %7d %8d %10s"
            % (
                rung.index,
                rung.layer if rung.layer is not None else "none (byte-exact)",
                rung.result.hits,
                rung.result.misses,
                rung.result.distinct_keys,
                "-" if rung.layer is None else str(rung.additional_calls_saved),
            )
        )
    return "\n".join(lines)
