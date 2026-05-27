"use client";

import { useState, useRef, useCallback } from "react";
import { Play, Square, Loader2, CheckCircle2 } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import { TTS_SPEAKERS, MAX_TTS_CHARS } from "@/lib/constants";
import type { LanguageCode, TTSSpeaker, TTSApiResponse } from "@/lib/types";

type Status = "idle" | "loading" | "playing" | "done" | "error";

const VOICE_META: Record<TTSSpeaker, { bg: string; dot: string; tags: string }> = {
  priya: { bg: "bg-[#C084FC]", dot: "#A855F7", tags: "Conversational · Warm" },
  shubh: { bg: "bg-[#60A5FA]", dot: "#3B82F6", tags: "Conversational · Friendly" },
};

export function TTSPanel() {
  const [text, setText]       = useState("");
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");
  const [speaker, setSpeaker] = useState<TTSSpeaker>("shubh");
  const [status, setStatus]   = useState<Status>("idle");
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
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), language, speaker }),
      });
      const data: TTSApiResponse = await res.json();
      if (!res.ok || data.error) throw new Error(data.error ?? `HTTP ${res.status}`);
      if (!data.audioBase64)     throw new Error("No audio received");

      const bytes = Uint8Array.from(atob(data.audioBase64), (c) => c.charCodeAt(0));
      const blob  = new Blob([bytes], { type: "audio/wav" });
      const url   = URL.createObjectURL(blob);
      setAudioSrc(url);
      setStatus("playing");

      const audio = new Audio(url);
      audioRef.current = audio;
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
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_260px]">

      {/* ────────────── Left: text input ────────────── */}
      <div className="flex flex-col px-6 pt-6 pb-5 border-b lg:border-b-0 lg:border-r border-[#F0EEF8]">

        {/* Textarea — tour target 1 */}
        <textarea
          id="onboard-tts-textarea"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type or paste text here…&#10;e.g. नमस्ते, आप कैसे हैं?"
          rows={7}
          className={`w-full bg-transparent text-[#111827] text-[15px] leading-[1.75]
                      placeholder:text-[#C4BFDA] resize-none focus:outline-none
                      ${isOverLimit ? "text-red-500" : ""}`}
        />

        {/* Divider */}
        <div className="h-px bg-[#F0EEF8] my-4" />

        {/* Bottom controls */}
        <div className="flex items-center justify-between gap-3 flex-wrap">

          {/* Left: language + word count — tour target 2 */}
          <div id="onboard-language" className="flex items-center gap-3">
            <LanguageSelector value={language} onChange={setLanguage} id="tts-language" />
            <span className="text-xs text-[#C4BFDA] tabular-nums hidden sm:block">
              {wordCount} {wordCount === 1 ? "word" : "words"}
            </span>
          </div>

          {/* Right: char count + speak/stop */}
          <div className="flex items-center gap-3">
            <span className={`text-xs tabular-nums font-medium ${isOverLimit ? "text-red-500" : "text-[#C4BFDA]"}`}>
              {charCount}/{MAX_TTS_CHARS}
            </span>

            {status === "playing" ? (
              <button
                id="onboard-speak-btn"
                onClick={handleStop}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-600
                           text-white text-sm font-semibold rounded-full transition-colors
                           shadow-[0_2px_8px_rgba(239,68,68,0.35)]"
              >
                <Square className="w-3.5 h-3.5 fill-current" /> Stop
              </button>
            ) : (
              <button
                id="onboard-speak-btn"
                onClick={handleGenerate}
                disabled={status === "loading" || !text.trim() || isOverLimit}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#111827] hover:bg-[#1F2937]
                           disabled:bg-[#E9E7F4] disabled:text-[#B0AABF] disabled:cursor-not-allowed
                           text-white text-sm font-semibold rounded-full transition-all
                           shadow-[0_2px_8px_rgba(17,24,39,0.25)] hover:shadow-[0_4px_14px_rgba(17,24,39,0.35)]
                           hover:-translate-y-px"
              >
                {status === "loading"
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
                  : <><Play className="w-3.5 h-3.5 fill-current" /> Speak</>
                }
              </button>
            )}
          </div>
        </div>

        {/* Status / error / replay */}
        {status === "done" && !errorMsg && (
          <div className="flex items-center gap-2 mt-4 text-xs text-emerald-600 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" /> Done
          </div>
        )}
        {status === "error" && errorMsg && (
          <p className="mt-3 text-xs text-red-500">{errorMsg}</p>
        )}
        {audioSrc && (status === "done" || status === "error") && (
          <audio controls src={audioSrc} className="mt-3 w-full h-9" />
        )}
      </div>

      {/* ────────────── Right: voice picker ────────────── */}
      <div className="px-5 pt-6 pb-5 flex flex-col">

        <p className="text-xs font-semibold uppercase tracking-widest text-[#C4BFDA] mb-4">
          Voices
        </p>

        <div className="space-y-2.5 flex-1">
          {TTS_SPEAKERS.map((v) => {
            const meta     = VOICE_META[v.value];
            const selected = speaker === v.value;
            return (
              <button
                key={v.value}
                onClick={() => setSpeaker(v.value)}
                className={`w-full flex items-center gap-3.5 p-3.5 rounded-2xl text-left transition-all duration-150
                  ${selected
                    ? "bg-[#F5F3FF] ring-1 ring-[#6366F1]/15"
                    : "hover:bg-[#FAFAFA] ring-1 ring-transparent hover:ring-[#F0EEF8]"
                  }`}
              >
                {/* Coloured icon */}
                <div className={`w-11 h-11 ${meta.bg} rounded-xl flex items-center justify-center shrink-0
                                 shadow-sm`}>
                  <Play className="w-4 h-4 fill-white text-white" />
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-[#111827]">{v.label}</span>
                    <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold
                      ${v.value === "priya"
                        ? "bg-[#FCE7F3] text-[#BE185D]"
                        : "bg-[#DBEAFE] text-[#1D4ED8]"
                      }`}>
                      {v.value === "priya" ? "Female" : "Male"}
                    </span>
                  </div>
                  <p className="text-[11px] text-[#9CA3AF]">{meta.tags}</p>
                </div>

                {/* Selected indicator */}
                {selected && (
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ background: meta.dot }} />
                )}
              </button>
            );
          })}
        </div>

        {/* Model footer */}
        <div className="pt-4 mt-4 border-t border-[#F0EEF8]">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#A78BFA]" />
            <p className="text-xs text-[#9CA3AF]">
              Powered by <span className="text-[#6B7280] font-medium">Bulbul v3</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
