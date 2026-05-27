"use client";

import { useState, useRef, useCallback } from "react";
import { Volume2, Play, Square, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import { TTS_SPEAKERS, MAX_TTS_CHARS } from "@/lib/constants";
import type { LanguageCode, TTSSpeaker, TTSApiResponse } from "@/lib/types";

type Status = "idle" | "loading" | "playing" | "done" | "error";

export function TTSPanel() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");
  const [speaker, setSpeaker] = useState<TTSSpeaker>("priya");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [audioSrc, setAudioSrc] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  const charsRemaining = MAX_TTS_CHARS - text.length;
  const isOverLimit = text.length > MAX_TTS_CHARS;

  const handleGenerate = useCallback(async () => {
    if (!text.trim() || isOverLimit) return;

    setStatus("loading");
    setErrorMsg("");
    setAudioSrc(null);

    // Stop any currently playing audio
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

      if (!res.ok || data.error) {
        throw new Error(data.error ?? `HTTP ${res.status}`);
      }

      if (!data.audioBase64) {
        throw new Error("No audio data received");
      }

      // Decode base64 WAV and create an object URL
      const bytes = Uint8Array.from(atob(data.audioBase64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: "audio/wav" });
      const url = URL.createObjectURL(blob);
      setAudioSrc(url);
      setStatus("playing");

      // Auto-play
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => setStatus("done");
      audio.onerror = () => {
        setErrorMsg("Failed to play audio");
        setStatus("error");
      };
      await audio.play();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong");
      setStatus("error");
    }
  }, [text, language, speaker, isOverLimit]);

  const handleStop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setStatus("done");
  }, []);

  return (
    <div className="space-y-5">
      {/* Text input */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
            Input Text
          </label>
          <span
            className={`text-xs font-medium tabular-nums ${
              isOverLimit ? "text-red-500" : charsRemaining <= 50 ? "text-amber-500" : "text-slate-400"
            }`}
          >
            {charsRemaining} chars left
          </span>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type something in the selected language…&#10;e.g. नमस्ते, आप कैसे हैं?"
          rows={4}
          className={`w-full px-3 py-2.5 bg-white border rounded-lg text-sm text-slate-800
                      placeholder:text-slate-400 resize-none
                      focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                      transition-colors ${
                        isOverLimit ? "border-red-400 bg-red-50" : "border-slate-200"
                      }`}
        />
      </div>

      {/* Controls row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <LanguageSelector
          value={language}
          onChange={setLanguage}
          label="Target Language"
          id="tts-language"
        />

        {/* Voice selector */}
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
            Voice
          </label>
          <div className="flex gap-2">
            {TTS_SPEAKERS.map((s) => (
              <button
                key={s.value}
                onClick={() => setSpeaker(s.value)}
                className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition-all ${
                  speaker === s.value
                    ? "bg-indigo-600 border-indigo-600 text-white shadow-sm"
                    : "bg-white border-slate-200 text-slate-700 hover:border-indigo-300 hover:text-indigo-600"
                }`}
              >
                {s.label}
                <span className="block text-xs font-normal opacity-70">{s.description}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Generate / Stop button */}
      <div className="flex items-center gap-3">
        {status === "playing" ? (
          <button
            onClick={handleStop}
            className="flex items-center gap-2 px-5 py-2.5 bg-red-500 hover:bg-red-600
                       text-white text-sm font-semibold rounded-lg transition-colors shadow-sm"
          >
            <Square className="w-4 h-4 fill-current" />
            Stop
          </button>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={status === "loading" || !text.trim() || isOverLimit}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700
                       disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed
                       text-white text-sm font-semibold rounded-lg transition-colors shadow-sm"
          >
            {status === "loading" ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Volume2 className="w-4 h-4" />
                Generate Speech
              </>
            )}
          </button>
        )}

        {/* Status badge */}
        {status === "playing" && (
          <div className="flex items-center gap-2 text-indigo-600 text-sm font-medium">
            <span className="flex gap-0.5 h-4 items-end">
              {[...Array(5)].map((_, i) => (
                <span
                  key={i}
                  className="waveform-bar w-1 bg-indigo-500 rounded-full"
                  style={{ height: "100%" }}
                />
              ))}
            </span>
            Playing…
          </div>
        )}
        {status === "done" && (
          <span className="flex items-center gap-1.5 text-green-600 text-sm font-medium">
            <CheckCircle2 className="w-4 h-4" /> Done
          </span>
        )}
      </div>

      {/* Error message */}
      {status === "error" && errorMsg && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Replay controls (shown after playback finishes) */}
      {audioSrc && (status === "done" || status === "error") && (
        <div className="flex items-center gap-3 p-3 bg-slate-50 border border-slate-200 rounded-lg">
          <Play className="w-4 h-4 text-slate-500 shrink-0" />
          <audio controls src={audioSrc} className="w-full h-8" />
        </div>
      )}
    </div>
  );
}
