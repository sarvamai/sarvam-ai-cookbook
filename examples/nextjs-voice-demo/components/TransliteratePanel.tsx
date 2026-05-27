"use client";

import { useState, useCallback } from "react";
import { Languages, Loader2, ClipboardCopy, CheckCircle2, ArrowRight } from "lucide-react";
import { LanguageSelector } from "./LanguageSelector";
import type { LanguageCode, TransliterateApiResponse } from "@/lib/types";

type State = "idle" | "loading" | "done" | "error";

const SAMPLES: Partial<Record<LanguageCode, string>> = {
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
  const [targetLanguage, setTargetLanguage] = useState<LanguageCode>("hi-IN");
  const [state, setState] = useState<State>("idle");
  const [result, setResult] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [copied, setCopied] = useState(false);

  const handleTransliterate = useCallback(async () => {
    if (!text.trim()) return;
    setState("loading"); setErrorMsg(""); setResult("");

    try {
      const res  = await fetch("/api/transliterate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim(), sourceLanguage: "en-IN", targetLanguage }),
      });
      const data: TransliterateApiResponse = await res.json();
      if (!res.ok || data.error) throw new Error(data.error ?? `HTTP ${res.status}`);
      setResult(data.transliterated_text ?? "");
      setState("done");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed");
      setState("error");
    }
  }, [text, targetLanguage]);

  const loadSample = useCallback(() => {
    const s = SAMPLES[targetLanguage] ?? SAMPLES["hi-IN"]!;
    setText(s); setResult(""); setState("idle");
  }, [targetLanguage]);

  const copyResult = useCallback(async () => {
    await navigator.clipboard.writeText(result);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  }, [result]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 min-h-[420px]">

      {/* ── Left: Roman input ── */}
      <div className="flex flex-col p-6 border-b lg:border-b-0 lg:border-r border-[#E5E3EE]">
        <div className="flex items-center justify-between mb-5">
          <span className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF]">
            Romanised Input
          </span>
          <button
            onClick={loadSample}
            className="text-xs text-[#6B7280] hover:text-[#111827] transition-colors font-medium"
          >
            Load sample →
          </button>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Type romanised text…\ne.g. ${SAMPLES[targetLanguage] ?? SAMPLES["hi-IN"]}`}
          rows={7}
          className="flex-1 w-full bg-transparent text-[#111827] text-base leading-relaxed
                     placeholder:text-[#C4BFDA] resize-none focus:outline-none"
        />

        {/* Bottom bar */}
        <div className="flex items-center justify-between pt-4 mt-auto border-t border-[#E5E3EE]">
          {/* Source language label */}
          <div className="flex items-center gap-2">
            <span className="px-3 py-2 text-sm text-[#9CA3AF] bg-[#F9F8FC] rounded-full border border-[#E5E3EE] font-medium">
              English (Roman)
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-[#C4BFDA]" />
            <LanguageSelector
              value={targetLanguage}
              onChange={(l) => { setTargetLanguage(l); setResult(""); setState("idle"); }}
              id="transliterate-target"
            />
          </div>

          <button
            onClick={handleTransliterate}
            disabled={!text.trim() || state === "loading"}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#111827] hover:bg-[#1F2937]
                       disabled:bg-[#E5E3EE] disabled:text-[#9CA3AF] disabled:cursor-not-allowed
                       text-white text-sm font-medium rounded-full transition-colors"
          >
            {state === "loading" ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Converting…</>
            ) : (
              <><Languages className="w-4 h-4" /> Convert</>
            )}
          </button>
        </div>

        {state === "error" && errorMsg && (
          <p className="mt-2 text-xs text-red-500">{errorMsg}</p>
        )}
      </div>

      {/* ── Right: native script output ── */}
      <div className="flex flex-col p-6">
        <div className="flex items-center justify-between mb-5">
          <span className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF]">
            Native Script
          </span>
          {state === "done" && result && (
            <button
              onClick={copyResult}
              className="flex items-center gap-1.5 text-xs text-[#6B7280] hover:text-[#111827] transition-colors"
            >
              {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <ClipboardCopy className="w-3.5 h-3.5" />}
              {copied ? "Copied" : "Copy"}
            </button>
          )}
        </div>

        {state === "idle" && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-2">
              <div className="w-12 h-12 rounded-2xl bg-[#F5F3FF] flex items-center justify-center mx-auto">
                <Languages className="w-5 h-5 text-[#9CA3AF]" />
              </div>
              <p className="text-sm text-[#9CA3AF]">Transliterated text will appear here</p>
            </div>
          </div>
        )}

        {state === "loading" && (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-[#9CA3AF] animate-spin" />
          </div>
        )}

        {state === "done" && (
          <div className="flex-1 p-4 bg-[#F9F8FC] rounded-2xl border border-[#E5E3EE]">
            <p className="text-2xl text-[#111827] leading-relaxed font-medium">
              {result || <em className="text-[#9CA3AF] text-base not-italic">No output returned.</em>}
            </p>
          </div>
        )}

        {/* Model badge */}
        <div className="mt-auto pt-4 border-t border-[#E5E3EE]">
          <p className="text-xs text-[#9CA3AF]">
            Powered by <span className="text-[#6B7280] font-medium">Sarvam Transliterate</span>
          </p>
        </div>
      </div>
    </div>
  );
}
