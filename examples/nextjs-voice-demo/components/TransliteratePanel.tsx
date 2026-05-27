"use client";

import { useState, useCallback } from "react";
import { Languages, Loader2, AlertCircle, ClipboardCopy, CheckCircle2, ArrowRight } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import type { LanguageCode, TransliterateApiResponse } from "@/lib/types";

type TransliterateState = "idle" | "loading" | "done" | "error";

// Sample hints for different target languages
const SAMPLE_TEXTS: Record<string, string> = {
  "hi-IN": "namaste, aap kaise hain?",
  "ta-IN": "vanakkam, neenga eppadi irukkeenga?",
  "te-IN": "namaskaram, meeru ela unnaru?",
  "bn-IN": "namaskar, apni kemon achen?",
  "kn-IN": "namaskara, neevu hege iddira?",
  "ml-IN": "namaskaram, ningalku sukhamaano?",
  "mr-IN": "namaskar, tumhi kase ahat?",
  "gu-IN": "namaste, tame keva cho?",
  "pa-IN": "sat sri akal, tusi kive ho?",
};

export function TransliteratePanel() {
  const [text, setText] = useState("");
  const [sourceLanguage] = useState<LanguageCode>("en-IN"); // always Roman input
  const [targetLanguage, setTargetLanguage] = useState<LanguageCode>("hi-IN");
  const [state, setTransliterateState] = useState<TransliterateState>("idle");
  const [result, setResult] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [copied, setCopied] = useState(false);

  const handleTransliterate = useCallback(async () => {
    if (!text.trim()) return;

    setTransliterateState("loading");
    setErrorMsg("");
    setResult("");

    try {
      const res = await fetch("/api/transliterate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: text.trim(),
          sourceLanguage,
          targetLanguage,
        }),
      });

      const data: TransliterateApiResponse = await res.json();

      if (!res.ok || data.error) {
        throw new Error(data.error ?? `HTTP ${res.status}`);
      }

      setResult(data.transliterated_text ?? "");
      setTransliterateState("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Transliteration failed");
      setTransliterateState("error");
    }
  }, [text, sourceLanguage, targetLanguage]);

  const loadSample = useCallback(() => {
    const sample = SAMPLE_TEXTS[targetLanguage] ?? SAMPLE_TEXTS["hi-IN"];
    setText(sample);
    setResult("");
    setTransliterateState("idle");
  }, [targetLanguage]);

  const copyResult = useCallback(async () => {
    await navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [result]);

  return (
    <div className="space-y-5">
      {/* Language config row */}
      <div className="flex items-end gap-3">
        {/* Source is always "English (Romanised)" */}
        <div className="flex-1">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5">
            Source (Romanised)
          </label>
          <div className="px-3 py-2.5 bg-slate-100 border border-slate-200 rounded-lg text-sm text-slate-500 cursor-default">
            🇬🇧 English — Romanised input
          </div>
        </div>

        <ArrowRight className="w-5 h-5 text-slate-400 mb-2.5 shrink-0" />

        <LanguageSelector
          value={targetLanguage}
          onChange={(lang) => {
            setTargetLanguage(lang);
            setResult("");
            setTransliterateState("idle");
          }}
          label="Target Script"
          id="transliterate-target"
          className="flex-1"
        />
      </div>

      {/* Input area */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
            Romanised Input
          </label>
          <button
            onClick={loadSample}
            className="text-xs text-indigo-600 hover:text-indigo-700 font-medium transition-colors"
          >
            Load sample
          </button>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type Roman text here…&#10;e.g. namaste, aap kaise hain?"
          rows={3}
          className="w-full px-3 py-2.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-800
                     placeholder:text-slate-400 resize-none
                     focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
                     transition-colors"
        />
      </div>

      {/* Transliterate button */}
      <button
        onClick={handleTransliterate}
        disabled={!text.trim() || state === "loading"}
        className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700
                   disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed
                   text-white text-sm font-semibold rounded-lg transition-colors shadow-sm"
      >
        {state === "loading" ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Transliterating…
          </>
        ) : (
          <>
            <Languages className="w-4 h-4" />
            Transliterate
          </>
        )}
      </button>

      {/* Error */}
      {state === "error" && errorMsg && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Result */}
      {state === "done" && (
        <div className="p-4 bg-indigo-50 border border-indigo-200 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-600">
              Transliterated
            </span>
            <button
              onClick={copyResult}
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
          <p className="text-xl font-medium text-slate-800 leading-relaxed">
            {result || <em className="text-slate-400 text-sm">No output returned.</em>}
          </p>
        </div>
      )}
    </div>
  );
}
