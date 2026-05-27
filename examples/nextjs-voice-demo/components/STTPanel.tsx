"use client";

import {
  useState,
  useRef,
  useCallback,
  type ChangeEvent,
} from "react";
import {
  Mic,
  MicOff,
  Upload,
  FileAudio,
  Loader2,
  AlertCircle,
  ClipboardCopy,
  CheckCircle2,
  X,
} from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import { ACCEPTED_AUDIO_TYPES } from "@/lib/constants";
import type { LanguageCode, STTApiResponse } from "@/lib/types";

type RecordingState = "idle" | "recording" | "recorded";
type TranscribeState = "idle" | "loading" | "done" | "error";

export function STTPanel() {
  const [language, setLanguage] = useState<LanguageCode>("hi-IN");

  // Recording
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const recordedBlobRef = useRef<Blob | null>(null);

  // File upload
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Transcription result
  const [transcribeState, setTranscribeState] = useState<TranscribeState>("idle");
  const [transcript, setTranscript] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [copied, setCopied] = useState(false);

  // ── Recording helpers ─────────────────────────────────────────────────────

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Prefer opus/webm for broad browser support
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";

      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        recordedBlobRef.current = blob;
        stream.getTracks().forEach((t) => t.stop());
      };

      recorder.start(250); // collect in 250 ms intervals
      mediaRecorderRef.current = recorder;
      setRecordingState("recording");
      setRecordingSeconds(0);

      timerRef.current = setInterval(() => {
        setRecordingSeconds((s) => s + 1);
      }, 1000);
    } catch (err) {
      setErrorMsg(
        err instanceof Error
          ? `Microphone access denied: ${err.message}`
          : "Could not access microphone"
      );
      setTranscribeState("error");
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    mediaRecorderRef.current?.stop();
    setRecordingState("recorded");
    setUploadedFile(null); // clear any uploaded file
  }, []);

  const clearRecording = useCallback(() => {
    recordedBlobRef.current = null;
    setRecordingState("idle");
    setRecordingSeconds(0);
    setTranscript("");
    setTranscribeState("idle");
  }, []);

  // ── File upload helpers ───────────────────────────────────────────────────

  const handleFileChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    setUploadedFile(file);
    if (file) {
      clearRecording();
      setTranscript("");
      setTranscribeState("idle");
    }
  }, [clearRecording]);

  const clearFile = useCallback(() => {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setTranscript("");
    setTranscribeState("idle");
  }, []);

  // ── Transcribe ────────────────────────────────────────────────────────────

  const handleTranscribe = useCallback(async () => {
    const audioFile: File | Blob | null = uploadedFile ?? recordedBlobRef.current;
    if (!audioFile) return;

    setTranscribeState("loading");
    setErrorMsg("");
    setTranscript("");

    try {
      const formData = new FormData();
      if (uploadedFile) {
        formData.append("file", uploadedFile, uploadedFile.name);
      } else {
        const ext = (audioFile as Blob).type.includes("webm") ? "webm" : "wav";
        formData.append("file", audioFile, `recording.${ext}`);
      }
      formData.append("language_code", language);

      const res = await fetch("/api/stt", {
        method: "POST",
        body: formData,
      });

      const data: STTApiResponse = await res.json();

      if (!res.ok || data.error) {
        throw new Error(data.error ?? `HTTP ${res.status}`);
      }

      setTranscript(data.transcript ?? "");
      setTranscribeState("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Transcription failed");
      setTranscribeState("error");
    }
  }, [uploadedFile, language]);

  // ── Copy helper ───────────────────────────────────────────────────────────

  const copyTranscript = useCallback(async () => {
    await navigator.clipboard.writeText(transcript);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [transcript]);

  // ── Derived state ─────────────────────────────────────────────────────────

  const hasAudio = uploadedFile !== null || recordingState === "recorded";
  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="space-y-5">
      {/* Language selector */}
      <LanguageSelector
        value={language}
        onChange={setLanguage}
        label="Speech Language"
        id="stt-language"
        className="max-w-xs"
      />

      {/* Input section */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* ── Record from mic ── */}
        <div className="p-4 border border-slate-200 bg-white rounded-xl space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Record from microphone
          </p>

          {recordingState === "idle" && (
            <button
              onClick={startRecording}
              className="flex items-center gap-2 w-full justify-center py-3 bg-indigo-600 hover:bg-indigo-700
                         text-white text-sm font-semibold rounded-lg transition-colors"
            >
              <Mic className="w-4 h-4" />
              Start Recording
            </button>
          )}

          {recordingState === "recording" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-2 text-sm text-red-600 font-medium">
                  <span className="recording-dot w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
                  Recording
                </span>
                <span className="text-sm font-mono text-slate-600 tabular-nums">
                  {fmtTime(recordingSeconds)}
                </span>
              </div>
              <button
                onClick={stopRecording}
                className="flex items-center gap-2 w-full justify-center py-3 bg-red-500 hover:bg-red-600
                           text-white text-sm font-semibold rounded-lg transition-colors"
              >
                <MicOff className="w-4 h-4" />
                Stop Recording
              </button>
            </div>
          )}

          {recordingState === "recorded" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-sm text-green-600 font-medium">
                  <CheckCircle2 className="w-4 h-4" />
                  Recorded ({fmtTime(recordingSeconds)})
                </span>
                <button
                  onClick={clearRecording}
                  className="text-slate-400 hover:text-slate-600 transition-colors"
                  aria-label="Clear recording"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── Upload file ── */}
        <div className="p-4 border border-slate-200 bg-white rounded-xl space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Upload audio file
          </p>

          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_AUDIO_TYPES}
            onChange={handleFileChange}
            className="hidden"
            id="audio-upload"
          />

          {!uploadedFile ? (
            <label
              htmlFor="audio-upload"
              className="flex items-center gap-2 w-full justify-center py-3 border-2 border-dashed border-slate-300
                         hover:border-indigo-400 hover:bg-indigo-50 text-slate-600 hover:text-indigo-600
                         text-sm font-semibold rounded-lg transition-all cursor-pointer"
            >
              <Upload className="w-4 h-4" />
              Choose File
            </label>
          ) : (
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-sm text-slate-700 font-medium truncate min-w-0">
                <FileAudio className="w-4 h-4 text-indigo-500 shrink-0" />
                <span className="truncate">{uploadedFile.name}</span>
              </span>
              <button
                onClick={clearFile}
                className="text-slate-400 hover:text-slate-600 transition-colors shrink-0"
                aria-label="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          <p className="text-xs text-slate-400">WAV · MP3 · OGG · WebM · M4A</p>
        </div>
      </div>

      {/* Transcribe button */}
      <button
        onClick={handleTranscribe}
        disabled={!hasAudio || transcribeState === "loading"}
        className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700
                   disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed
                   text-white text-sm font-semibold rounded-lg transition-colors shadow-sm"
      >
        {transcribeState === "loading" ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Transcribing…
          </>
        ) : (
          <>
            <Mic className="w-4 h-4" />
            Transcribe
          </>
        )}
      </button>

      {/* Error */}
      {transcribeState === "error" && errorMsg && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Transcript output */}
      {transcribeState === "done" && (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Transcript
            </span>
            <button
              onClick={copyTranscript}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600 transition-colors"
            >
              {copied ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
              ) : (
                <ClipboardCopy className="w-3.5 h-3.5" />
              )}
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
          <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap break-words">
            {transcript || (
              <em className="text-slate-400">No speech detected in the audio.</em>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
