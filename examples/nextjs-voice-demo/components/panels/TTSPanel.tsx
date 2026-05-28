"use client";

import { useState, useRef, useCallback } from "react";
import { Play, Square, Loader2, CheckCircle2 } from "lucide-react";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { TTS_SPEAKERS, VOICE_META, MAX_TTS_CHARS } from "@/lib/constants";
import { base64ToAudioUrl } from "@/lib/utils";
import type { LanguageCode, TTSSpeaker, TTSApiResponse } from "@/lib/types";

type Status = "idle" | "loading" | "playing" | "done" | "error";

export function TTSPanel() {
  const [text,     setText]     = useState("");
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");
  const [speaker,  setSpeaker]  = useState<TTSSpeaker>("shubh");
  const [status,   setStatus]   = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const wordCount   = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charCount   = text.length;
  const isOverLimit = charCount > MAX_TTS_CHARS;

  const handleGenerate = useCallback(async () => {
    if (!text.trim() || isOverLimit) return;
    setStatus("loading"); setErrorMsg("");
    audioRef.current?.pause(); audioRef.current = null;
    try {
      const res  = await fetch("/api/tts", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ text: text.trim(), language, speaker }),
      });
      const data: TTSApiResponse = await res.json();
      if (!res.ok || data.error) throw new Error(data.error ?? `HTTP ${res.status}`);
      if (!data.audioBase64)     throw new Error("No audio received");

      const url = base64ToAudioUrl(data.audioBase64);
      setAudioSrc(url);
      setStatus("playing");
      const audio = new Audio(url);
      audioRef.current  = audio;
      audio.onended = () => setStatus("done");
      audio.onerror = () => { setErrorMsg("Playback failed"); setStatus("error"); };
      await audio.play();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong");
      setStatus("error");
    }
  }, [text, language, speaker, isOverLimit]);

  const handleStop = useCallback(() => {
    audioRef.current?.pause(); audioRef.current = null;
    setStatus("done");
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] min-h-[560px]">

      {/* ── Left: text input ────────────────────────────────────────────── */}
      <div className="flex flex-col px-7 pt-7 pb-6 border-b lg:border-b-0 lg:border-r border-slate-100">
        <textarea
          id="onboard-tts-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"Type or paste text here…\ne.g. नमस्ते, आप कैसे हैं?"}
          rows={8}
          className={`w-full flex-1 bg-transparent text-slate-800 text-[15px] leading-[1.8]
                      placeholder:text-slate-300 resize-none focus:outline-none
                      ${isOverLimit ? "text-red-500" : ""}`}
        />

        <div className="h-px bg-slate-100 mt-4 mb-4" />

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div id="onboard-language" className="flex items-center gap-3">
            <LanguageSelector value={language} onChange={setLanguage} id="tts-language" />
            <span className="text-xs text-slate-300 tabular-nums hidden sm:block">
              {wordCount} {wordCount === 1 ? "word" : "words"}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className={`text-xs tabular-nums font-medium ${isOverLimit ? "text-red-500" : "text-slate-300"}`}>
              {charCount}/{MAX_TTS_CHARS}
            </span>

            {status === "playing" ? (
              <button
                id="onboard-speak-btn"
                onClick={handleStop}
                className="flex items-center gap-2 px-5 py-2.5 text-white text-sm font-semibold
                           rounded-full transition-all active:scale-95"
                style={{ background: "linear-gradient(135deg,#f87171,#ef4444)", boxShadow: "0 4px 14px rgba(239,68,68,0.35)" }}
              >
                <Square className="w-3.5 h-3.5 fill-current" /> Stop
              </button>
            ) : (
              <button
                id="onboard-speak-btn"
                onClick={handleGenerate}
                disabled={status === "loading" || !text.trim() || isOverLimit}
                className="flex items-center gap-2 px-5 py-2.5 text-white text-sm font-semibold
                           rounded-full transition-all hover:-translate-y-px active:scale-95
                           disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0"
                style={{ background: "linear-gradient(135deg,#6366f1,#4f46e5)", boxShadow: "0 4px 14px rgba(99,102,241,0.35)" }}
              >
                {status === "loading"
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
                  : <><Play   className="w-3.5 h-3.5 fill-current" /> Speak</>
                }
              </button>
            )}
          </div>
        </div>

        {status === "done" && !errorMsg && (
          <div className="flex items-center gap-2 mt-3 text-xs text-emerald-600 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" /> Audio ready
          </div>
        )}
        {status === "error" && errorMsg && (
          <p className="mt-3 text-xs text-red-500">{errorMsg}</p>
        )}
        {audioSrc && (status === "done" || status === "error") && (
          <audio controls src={audioSrc} className="mt-3 w-full h-9 rounded-lg" />
        )}
      </div>

      {/* ── Right: voice picker ─────────────────────────────────────────── */}
      <div className="flex flex-col px-6 pt-7 pb-6">
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-4">Voices</p>

        <div className="space-y-3 flex-1">
          {TTS_SPEAKERS.map((v) => {
            const meta     = VOICE_META[v.value];
            const selected = speaker === v.value;
            return (
              <button
                key={v.value}
                onClick={() => setSpeaker(v.value)}
                className={`w-full flex items-center gap-4 p-4 rounded-2xl text-left transition-all duration-200
                  ${selected
                    ? "bg-slate-50 ring-2 ring-indigo-200 shadow-sm"
                    : "hover:bg-slate-50 ring-1 ring-slate-100"
                  }`}
              >
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: meta.gradient, boxShadow: selected ? meta.shadow : "none" }}
                >
                  <Play className="w-4 h-4 fill-white text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-slate-800">{v.label}</span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold tracking-wide
                      ${v.value === "priya" ? "bg-purple-100 text-purple-600" : "bg-blue-100 text-blue-600"}`}>
                      {meta.gender}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">{meta.tags}</p>
                </div>
                {selected && <div className="w-2.5 h-2.5 rounded-full shrink-0 bg-indigo-500" />}
              </button>
            );
          })}
        </div>

        <div className="pt-4 mt-4 border-t border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
            <p className="text-xs text-slate-400">
              Powered by <span className="text-slate-600 font-semibold">Bulbul v3</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
