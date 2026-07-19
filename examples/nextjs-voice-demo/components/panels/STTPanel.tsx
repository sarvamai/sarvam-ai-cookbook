"use client";

import { useState, useRef, useCallback, type ChangeEvent } from "react";
import { Mic, MicOff, Upload, FileAudio, Loader2, ClipboardCopy, CheckCircle2, X } from "lucide-react";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { ACCEPTED_AUDIO_TYPES } from "@/lib/constants";
import { fmtTime } from "@/lib/utils";
import type { LanguageCode, STTApiResponse } from "@/lib/types";

type RecordingState  = "idle" | "recording" | "recorded";
type TranscribeState = "idle" | "loading" | "done" | "error";

export function STTPanel() {
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");

  const [recordingState,   setRecordingState]   = useState<RecordingState>("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef   = useRef<Blob[]>([]);
  const timerRef         = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordedBlobRef  = useRef<Blob | null>(null);

  const [uploadedFile,    setUploadedFile]    = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [transcribeState, setTranscribeState] = useState<TranscribeState>("idle");
  const [transcript,      setTranscript]      = useState("");
  const [errorMsg,        setErrorMsg]        = useState("");
  const [copied,          setCopied]          = useState(false);

  const startRecording = useCallback(async () => {
    try {
      const stream   = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop = () => {
        recordedBlobRef.current = new Blob(audioChunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
      };
      recorder.start(250);
      mediaRecorderRef.current = recorder;
      setRecordingState("recording");
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } catch (err) {
      const isDenied = err instanceof DOMException &&
        (err.name === "NotAllowedError" || err.name === "PermissionDeniedError");
      setErrorMsg(isDenied ? "permission_denied" : "unavailable");
      setTranscribeState("error");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    mediaRecorderRef.current?.stop();
    setRecordingState("recorded");
    setUploadedFile(null);
  }, []);

  const clearRecording = useCallback(() => {
    recordedBlobRef.current = null;
    setRecordingState("idle");
    setRecordingSeconds(0);
    setTranscript("");
    setTranscribeState("idle");
  }, []);

  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setUploadedFile(file);
    if (file) { clearRecording(); setTranscript(""); setTranscribeState("idle"); }
  }, [clearRecording]);

  const clearFile = useCallback(() => {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setTranscript(""); setTranscribeState("idle");
  }, []);

  const handleTranscribe = useCallback(async () => {
    const audioFile = uploadedFile ?? recordedBlobRef.current;
    if (!audioFile) return;
    setTranscribeState("loading"); setErrorMsg(""); setTranscript("");
    try {
      const fd = new FormData();
      if (uploadedFile) {
        fd.append("file", uploadedFile, uploadedFile.name);
      } else {
        const ext = (audioFile as Blob).type.includes("webm") ? "webm" : "wav";
        fd.append("file", audioFile, `recording.${ext}`);
      }
      fd.append("language_code", language);
      const res  = await fetch("/api/stt", { method: "POST", body: fd });
      const data: STTApiResponse = await res.json();
      if (!res.ok || data.error) throw new Error(data.error ?? `HTTP ${res.status}`);
      setTranscript(data.transcript ?? "");
      setTranscribeState("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Transcription failed");
      setTranscribeState("error");
    }
  }, [uploadedFile, language]);

  const copyTranscript = useCallback(async () => {
    await navigator.clipboard.writeText(transcript);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  }, [transcript]);

  const hasAudio = uploadedFile !== null || recordingState === "recorded";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 min-h-[560px]">

      {/* ── Left: input ─────────────────────────────────────────────────── */}
      <div id="onboard-stt-input" className="flex flex-col px-7 pt-7 pb-6 border-b lg:border-b-0 lg:border-r border-slate-100">
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400 mb-5">Audio Input</p>

        <div className="flex-1 space-y-3">
          {/* Microphone card */}
          <div className="rounded-2xl border border-slate-100 bg-slate-50/60 p-5">
            <p className="text-xs font-medium text-slate-400 mb-4">Record from microphone</p>

            {recordingState === "idle" && (
              <button
                onClick={startRecording}
                className="w-full flex items-center justify-center gap-2 py-2.5 text-white text-sm
                           font-semibold rounded-full transition-all hover:-translate-y-px active:scale-95 cursor-pointer"
                style={{ background: "linear-gradient(135deg,#6366f1,#4f46e5)", boxShadow: "0 4px 14px rgba(99,102,241,0.3)" }}
              >
                <Mic className="w-4 h-4" /> Start Recording
              </button>
            )}

            {recordingState === "recording" && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-red-500 font-semibold">
                    <span className="recording-dot w-2 h-2 rounded-full bg-red-500 inline-block" />
                    Recording
                  </span>
                  <span className="font-mono text-sm font-semibold text-slate-500 tabular-nums">
                    {fmtTime(recordingSeconds)}
                  </span>
                </div>
                <button
                  onClick={stopRecording}
                  className="w-full flex items-center justify-center gap-2 py-2.5 text-white text-sm
                             font-semibold rounded-full transition-all active:scale-95 cursor-pointer"
                  style={{ background: "linear-gradient(135deg,#f87171,#ef4444)", boxShadow: "0 4px 14px rgba(239,68,68,0.3)" }}
                >
                  <MicOff className="w-4 h-4" /> Stop Recording
                </button>
              </div>
            )}

            {recordingState === "recorded" && (
              <div className="flex items-center justify-between px-1">
                <span className="flex items-center gap-2 text-sm text-emerald-600 font-semibold">
                  <CheckCircle2 className="w-4 h-4" />
                  Recorded — {fmtTime(recordingSeconds)}
                </span>
                <button onClick={clearRecording} className="text-slate-400 hover:text-slate-600 transition-colors p-1 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* File upload card */}
          <div className="rounded-2xl border border-slate-100 bg-slate-50/60 p-5">
            <p className="text-xs font-medium text-slate-400 mb-4">Upload audio file</p>
            <input ref={fileInputRef} type="file" accept={ACCEPTED_AUDIO_TYPES}
              onChange={handleFileChange} className="hidden" id="audio-upload" />

            {!uploadedFile ? (
              <label
                htmlFor="audio-upload"
                className="w-full flex items-center justify-center gap-2 py-2.5 border border-dashed
                           border-slate-200 hover:border-indigo-300 hover:bg-white text-slate-500
                           hover:text-indigo-600 text-sm font-semibold rounded-full cursor-pointer transition-all"
              >
                <Upload className="w-4 h-4" /> Choose File
              </label>
            ) : (
              <div className="flex items-center justify-between gap-2 px-1">
                <span className="flex items-center gap-2 text-sm text-slate-700 font-medium truncate">
                  <FileAudio className="w-4 h-4 text-indigo-400 shrink-0" />
                  <span className="truncate">{uploadedFile.name}</span>
                </span>
                <button onClick={clearFile} className="text-slate-400 hover:text-slate-600 shrink-0 p-1 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
            <p className="text-[11px] text-slate-300 mt-3 text-center">WAV · MP3 · OGG · WebM</p>
          </div>
        </div>

        <div className="flex items-center justify-between pt-5 mt-4 border-t border-slate-100 gap-3 flex-wrap">
          <LanguageSelector value={language} onChange={setLanguage} id="stt-language" />
          <button
            id="onboard-transcribe-btn"
            onClick={handleTranscribe}
            disabled={!hasAudio || transcribeState === "loading"}
            className="flex items-center gap-2 px-5 py-2.5 text-white text-sm font-semibold rounded-full
                       transition-all hover:-translate-y-px active:scale-95 cursor-pointer
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0"
            style={{ background: "linear-gradient(135deg,#6366f1,#4f46e5)", boxShadow: "0 4px 14px rgba(99,102,241,0.3)" }}
          >
            {transcribeState === "loading"
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Transcribing…</>
              : <><Mic    className="w-4 h-4" /> Transcribe</>
            }
          </button>
        </div>
        {transcribeState === "error" && errorMsg === "permission_denied" && (
          <div className="mt-3 flex items-start gap-2.5 p-3 bg-amber-50 border border-amber-100 rounded-xl">
            <span className="text-amber-500 mt-0.5 shrink-0">🎙️</span>
            <div>
              <p className="text-xs font-semibold text-amber-700 mb-0.5">Microphone access blocked</p>
              <p className="text-[11px] text-amber-600 leading-relaxed">
                Allow microphone access in your browser settings, then reload the page.
              </p>
            </div>
          </div>
        )}
        {transcribeState === "error" && errorMsg === "unavailable" && (
          <p className="mt-2 text-xs text-red-500">Microphone unavailable on this device.</p>
        )}
        {transcribeState === "error" && errorMsg !== "permission_denied" && errorMsg !== "unavailable" && errorMsg && (
          <p className="mt-2 text-xs text-red-500">{errorMsg}</p>
        )}
      </div>

      {/* ── Right: transcript ────────────────────────────────────────────── */}
      <div className="flex flex-col px-7 pt-7 pb-6">
        <div className="flex items-center justify-between mb-5">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Transcript</p>
          {transcribeState === "done" && transcript && (
            <button
              onClick={copyTranscript}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
            >
              {copied
                ? <><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> Copied</>
                : <><ClipboardCopy className="w-3.5 h-3.5" /> Copy</>
              }
            </button>
          )}
        </div>

        {transcribeState === "idle" && (
          <div className="flex-1 flex items-center justify-center rounded-2xl border border-dashed border-slate-100">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center mx-auto">
                <Mic className="w-5 h-5 text-slate-300" />
              </div>
              <p className="text-sm text-slate-400">Transcript will appear here</p>
            </div>
          </div>
        )}
        {transcribeState === "loading" && (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
          </div>
        )}
        {transcribeState === "done" && (
          <div className="flex-1 p-5 bg-slate-50 rounded-2xl border border-slate-100 overflow-auto">
            <p className="text-[15px] text-slate-800 leading-relaxed whitespace-pre-wrap">
              {transcript || <em className="text-slate-400 not-italic text-sm">No speech detected.</em>}
            </p>
          </div>
        )}

        <div className="pt-4 mt-4 border-t border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
            <p className="text-xs text-slate-400">
              Powered by <span className="text-slate-600 font-semibold">Saarika v2.5</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
