"use client";

import { useState, useRef, useCallback } from "react";
import { Play, Square, Loader2 } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import { TTS_SPEAKERS, MAX_TTS_CHARS } from "@/lib/constants";
import type { LanguageCode, TTSSpeaker, TTSApiResponse } from "@/lib/types";

type Status = "idle" | "loading" | "playing" | "done" | "error";

// Sarvam voice colours — matches their website cards
const VOICE_COLORS: Record<TTSSpeaker, string> = {
  priya: "bg-[#C084FC]",   // purple
  shubh: "bg-[#60A5FA]",   // blue
};

const VOICE_ICONS: Record<TTSSpeaker, string> = {
  priya: "P",
  shubh: "S",
};

export function TTSPanel() {
  const [text, setText] = useState(
    "भारत की सुबह का नज़ारा ही कुछ और होता है। चाय की चुस्की के साथ अखबार।"
  );
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");
  const [speaker, setSpeaker] = useState<TTSSpeaker>("shubh");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [audioSrc, setAudioSrc] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const charCount = text.length;
  const isOverLimit = charCount > MAX_TTS_CHARS;

  const handleGenerate = useCallback(async () => {
    if (!text.trim() || isOverLimit) return;
    setStatus("loading");
    setErrorMsg("");

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    try {
      const res = await fetch("/api/tts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), language, speaker }),
      });
      const data: TTSApiResponse = await res.json();
      if (!res.ok || data.error) throw new Error(data.error ?? `HTTP ${res.status}`);
      if (!data.audioBase64) throw new Error("No audio received");

      const bytes = Uint8Array.from(atob(data.audioBase64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: "audio/wav" });
      const url = URL.createObjectURL(blob);
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
    audioRef.current?.pause();
    audioRef.current = null;
    setStatus("done");
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-0 min-h-[420px]">

      {/* ── Left: text input ── */}
      <div className="flex flex-col p-6 border-b lg:border-b-0 lg:border-r border-[#E5E3EE]">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type text to convert to speech…"
          className={`flex-1 w-full bg-transparent text-[#111827] text-base leading-relaxed
                      placeholder:text-[#C4BFDA] resize-none focus:outline-none
                      ${isOverLimit ? "text-red-500" : ""}`}
          rows={8}
        />

        {/* Bottom bar */}
        <div className="flex items-center justify-between pt-4 mt-auto">
          <div className="flex items-center gap-4">
            <LanguageSelector value={language} onChange={setLanguage} id="tts-language" />
          </div>

          <div className="flex items-center gap-3">
            <span className={`text-xs tabular-nums ${isOverLimit ? "text-red-500 font-medium" : "text-[#9CA3AF]"}`}>
              {charCount}/{MAX_TTS_CHARS}
            </span>

            {status === "playing" ? (
              <button
                onClick={handleStop}
                className="flex items-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-600
                           text-white text-sm font-medium rounded-full transition-colors"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                Stop
              </button>
            ) : (
              <button
                onClick={handleGenerate}
                disabled={status === "loading" || !text.trim() || isOverLimit}
                className="flex items-center gap-2 px-5 py-2.5 bg-[#111827] hover:bg-[#1F2937]
                           disabled:bg-[#E5E3EE] disabled:text-[#9CA3AF] disabled:cursor-not-allowed
                           text-white text-sm font-medium rounded-full transition-colors"
              >
                {status === "loading" ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Generating…</>
                ) : (
                  <><Play className="w-3.5 h-3.5 fill-current" /> Speak</>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Error */}
        {status === "error" && errorMsg && (
          <p className="mt-3 text-xs text-red-500">{errorMsg}</p>
        )}

        {/* Audio replay */}
        {audioSrc && (status === "done" || status === "error") && (
          <audio controls src={audioSrc} className="mt-3 w-full h-9" />
        )}
      </div>

      {/* ── Right: voice selection ── */}
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF]">
            Voices
          </span>
        </div>

        <div className="space-y-2">
          {TTS_SPEAKERS.map((v) => (
            <button
              key={v.value}
              onClick={() => setSpeaker(v.value)}
              className={`w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all
                ${speaker === v.value
                  ? "bg-[#F5F3FF] ring-1 ring-[#111827]/10"
                  : "hover:bg-[#F9F8FC]"
                }`}
            >
              {/* Coloured icon */}
              <div className={`w-10 h-10 rounded-xl ${VOICE_COLORS[v.value]} flex items-center justify-center shrink-0`}>
                <Play className="w-4 h-4 fill-white text-white" />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-[#111827]">{v.label}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium
                    ${v.value === "priya"
                      ? "bg-[#FCE7F3] text-[#BE185D]"
                      : "bg-[#DBEAFE] text-[#1D4ED8]"
                    }`}>
                    {v.value === "priya" ? "Female" : "Male"}
                  </span>
                </div>
                <p className="text-xs text-[#9CA3AF] mt-0.5">{v.description}</p>
              </div>

              {speaker === v.value && (
                <div className="w-2 h-2 rounded-full bg-[#111827] shrink-0" />
              )}
            </button>
          ))}
        </div>

        {/* Model badge */}
        <div className="mt-6 pt-4 border-t border-[#E5E3EE]">
          <p className="text-xs text-[#9CA3AF]">
            Powered by{" "}
            <span className="text-[#6B7280] font-medium">Bulbul v3</span>
          </p>
        </div>
      </div>
    </div>
  );
}
