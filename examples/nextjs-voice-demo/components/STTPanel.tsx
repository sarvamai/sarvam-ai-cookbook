"use client";

import {
  useState, useRef, useCallback, type ChangeEvent,
} from "react";
import { Mic, MicOff, Upload, FileAudio, Loader2, ClipboardCopy, CheckCircle2, X } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import { ACCEPTED_AUDIO_TYPES } from "@/lib/constants";
import type { LanguageCode, STTApiResponse } from "@/lib/types";

type RecordingState  = "idle" | "recording" | "recorded";
type TranscribeState = "idle" | "loading" | "done" | "error";

export function STTPanel() {
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");

  // Recording
  const [recordingState, setRecordingState]   = useState<RecordingState>("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef  = useRef<MediaRecorder | null>(null);
  const audioChunksRef    = useRef<Blob[]>([]);
  const timerRef          = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordedBlobRef   = useRef<Blob | null>(null);

  // File upload
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Output
  const [transcribeState, setTranscribeState] = useState<TranscribeState>("idle");
  const [transcript, setTranscript]     = useState("");
  const [errorMsg, setErrorMsg]         = useState("");
  const [copied, setCopied]             = useState(false);

  // ── Recording ────────────────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      recorder.onstop = () => {
        recordedBlobRef.current = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start(250);
      mediaRecorderRef.current = recorder;
      setRecordingState("recording");
      setRecordingSeconds(0);
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000);
    } catch (err) {
      setErrorMsg(err instanceof Error ? `Mic error: ${err.message}` : "Microphone unavailable");
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

  // ── File upload ───────────────────────────────────────────────────────────

  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setUploadedFile(file);
    if (file) { clearRecording(); setTranscript(""); setTranscribeState("idle"); }
  }, [clearRecording]);

  const clearFile = useCallback(() => {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setTranscript("");
    setTranscribeState("idle");
  }, []);

  // ── Transcribe ────────────────────────────────────────────────────────────

  const handleTranscribe = useCallback(async () => {
    const audioFile = uploadedFile ?? recordedBlobRef.current;
    if (!audioFile) return;
    setTranscribeState("loading");
    setErrorMsg("");
    setTranscript("");

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
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [transcript]);

  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const hasAudio = uploadedFile !== null || recordingState === "recorded";

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 min-h-[420px]">

      {/* ── Left: input ── */}
      <div className="flex flex-col p-6 border-b lg:border-b-0 lg:border-r border-[#E5E3EE]">
        <p className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF] mb-5">
          Audio Input
        </p>

        {/* Microphone card */}
        <div id="onboard-stt-input" className="flex-1 space-y-3">
          <div className="p-4 rounded-2xl bg-[#F9F8FC] border border-[#E5E3EE]">
            <p className="text-xs text-[#9CA3AF] mb-3">Record from microphone</p>

            {recordingState === "idle" && (
              <button
                onClick={startRecording}
                className="flex items-center gap-2 px-4 py-2.5 bg-[#111827] hover:bg-[#1F2937]
                           text-white text-sm font-medium rounded-full transition-colors w-full justify-center"
              >
                <Mic className="w-4 h-4" /> Start Recording
              </button>
            )}

            {recordingState === "recording" && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-red-500 font-medium">
                    <span className="recording-dot w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                    Recording
                  </span>
                  <span className="font-mono text-sm text-[#6B7280] tabular-nums">{fmtTime(recordingSeconds)}</span>
                </div>
                <button
                  onClick={stopRecording}
                  className="flex items-center gap-2 px-4 py-2.5 bg-red-500 hover:bg-red-600
                             text-white text-sm font-medium rounded-full transition-colors w-full justify-center"
                >
                  <MicOff className="w-4 h-4" /> Stop
                </button>
              </div>
            )}

            {recordingState === "recorded" && (
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm text-emerald-600 font-medium">
                  <CheckCircle2 className="w-4 h-4" />
                  Recorded ({fmtTime(recordingSeconds)})
                </span>
                <button onClick={clearRecording} className="text-[#9CA3AF] hover:text-[#6B7280]">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* File upload */}
          <div className="p-4 rounded-2xl bg-[#F9F8FC] border border-[#E5E3EE]">
            <p className="text-xs text-[#9CA3AF] mb-3">Upload audio file</p>
            <input ref={fileInputRef} type="file" accept={ACCEPTED_AUDIO_TYPES}
              onChange={handleFileChange} className="hidden" id="audio-upload" />

            {!uploadedFile ? (
              <label
                htmlFor="audio-upload"
                className="flex items-center gap-2 px-4 py-2.5 border border-dashed border-[#DDD9EC]
                           hover:border-[#111827]/40 hover:bg-white text-[#6B7280] hover:text-[#111827]
                           text-sm font-medium rounded-full cursor-pointer transition-all w-full justify-center"
              >
                <Upload className="w-4 h-4" /> Choose File
              </label>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-sm text-[#111827] font-medium truncate">
                  <FileAudio className="w-4 h-4 text-[#6B7280] shrink-0" />
                  <span className="truncate">{uploadedFile.name}</span>
                </span>
                <button onClick={clearFile} className="text-[#9CA3AF] hover:text-[#6B7280] shrink-0">
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
            <p className="text-xs text-[#C4BFDA] mt-2">WAV · MP3 · OGG · WebM</p>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="flex items-center justify-between pt-4 mt-4 border-t border-[#E5E3EE]">
          <LanguageSelector value={language} onChange={setLanguage} id="stt-language" />

          <button
            id="onboard-transcribe-btn"
            onClick={handleTranscribe}
            disabled={!hasAudio || transcribeState === "loading"}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#111827] hover:bg-[#1F2937]
                       disabled:bg-[#E5E3EE] disabled:text-[#9CA3AF] disabled:cursor-not-allowed
                       text-white text-sm font-medium rounded-full transition-colors"
          >
            {transcribeState === "loading" ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Transcribing…</>
            ) : (
              <><Mic className="w-4 h-4" /> Transcribe</>
            )}
          </button>
        </div>

        {transcribeState === "error" && errorMsg && (
          <p className="mt-2 text-xs text-red-500">{errorMsg}</p>
        )}
      </div>

      {/* ── Right: transcript output ── */}
      <div className="flex flex-col p-6">
        <div className="flex items-center justify-between mb-5">
          <span className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF]">
            Transcript
          </span>
          {transcribeState === "done" && transcript && (
            <button
              onClick={copyTranscript}
              className="flex items-center gap-1.5 text-xs text-[#6B7280] hover:text-[#111827] transition-colors"
            >
              {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          )}
        </div>

        {transcribeState === "idle" && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-2xl bg-[#F5F3FF] flex items-center justify-center mx-auto">
                <Mic className="w-5 h-5 text-[#9CA3AF]" />
              </div>
              <p className="text-sm text-[#9CA3AF]">Transcript will appear here</p>
            </div>
          </div>
        )}

        {transcribeState === "loading" && (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-[#9CA3AF] animate-spin" />
          </div>
        )}

        {transcribeState === "done" && (
          <div className="flex-1 p-4 bg-[#F9F8FC] rounded-2xl border border-[#E5E3EE]">
            <p className="text-base text-[#111827] leading-relaxed whitespace-pre-wrap">
              {transcript || <em className="text-[#9CA3AF] not-italic text-sm">No speech detected.</em>}
            </p>
          </div>
        )}

        {/* Model badge */}
        <div className="mt-auto pt-4 border-t border-[#E5E3EE]">
          <p className="text-xs text-[#9CA3AF]">
            Powered by <span className="text-[#6B7280] font-medium">Saarika v2</span>
          </p>
        </div>
      </div>
    </div>
  );
}
