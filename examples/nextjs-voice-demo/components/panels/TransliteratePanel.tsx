"use client";

import { useState, useCallback } from "react";
import { Languages, Loader2, ClipboardCopy, CheckCircle2, ArrowRight } from "lucide-react";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { TRANSLITERATE_SAMPLES } from "@/lib/constants";
import type { LanguageCode, TransliterateApiResponse } from "@/lib/types";

type State = "idle" | "loading" | "done" | "error";

export function TransliteratePanel() {
  const [text,           setText]           = useState("");
  const [targetLanguage, setTargetLanguage] = useState<LanguageCode>("hi-IN");
  const [state,          setState]          = useState<State>("idle");
  const [result,         setResult]         = useState("");
  const [errorMsg,       setErrorMsg]       = useState("");
  const [copied,         setCopied]         = useState(false);

  const handleTransliterate = useCallback(async () => {
    if (!text.trim()) return;
    setState("loading"); setErrorMsg(""); setResult("");
    try {
      const res  = await fetch("/api/transliterate", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ text: text.trim(), sourceLanguage: "en-IN", targetLanguage }),
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
    const s = TRANSLITERATE_SAMPLES[targetLanguage] ?? TRANSLITERATE_SAMPLES["hi-IN"]!;
    setText(s); setResult(""); setState("idle");
  }, [targetLanguage]);

  const copyResult = useCallback(async () => {
    await navigator.clipboard.writeText(result);
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  }, [result]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 min-h-[560px]">

      {/* ── Left: Roman input ───────────────────────────────────────────── */}
      <div className="flex flex-col px-7 pt-7 pb-6 border-b lg:border-b-0 lg:border-r border-slate-100">
        <div className="flex items-center justify-between mb-5">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Romanised Input</p>
          <button
            onClick={loadSample}
            className="text-xs text-indigo-500 hover:text-indigo-700 font-semibold transition-colors cursor-pointer"
          >
            Load sample →
          </button>
        </div>

        <textarea
          id="onboard-transliterate-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Type romanised text…\ne.g. ${TRANSLITERATE_SAMPLES[targetLanguage] ?? TRANSLITERATE_SAMPLES["hi-IN"]}`}
          rows={8}
          className="flex-1 w-full bg-transparent text-slate-800 text-[15px] leading-[1.8]
                     placeholder:text-slate-300 resize-none focus:outline-none"
        />

        <div className="pt-4 mt-auto border-t border-slate-100">
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <span className="px-3 py-1.5 text-xs font-semibold text-slate-500 bg-slate-50
                             border border-slate-200 rounded-full whitespace-nowrap">
              English (Roman)
            </span>
            <ArrowRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />
            <LanguageSelector
              value={targetLanguage}
              onChange={(l) => { setTargetLanguage(l); setResult(""); setState("idle"); }}
              id="transliterate-target"
            />
          </div>

          <button
            id="onboard-convert-btn"
            onClick={handleTransliterate}
            disabled={!text.trim() || state === "loading"}
            className="w-full flex items-center justify-center gap-2 py-2.5 text-white text-sm
                       font-semibold rounded-full transition-all hover:-translate-y-px active:scale-95 cursor-pointer
                       disabled:opacity-40 disabled:cursor-not-allowed disabled:translate-y-0"
            style={{ background: "linear-gradient(135deg,#6366f1,#4f46e5)", boxShadow: "0 4px 14px rgba(99,102,241,0.3)" }}
          >
            {state === "loading"
              ? <><Loader2   className="w-4 h-4 animate-spin" /> Converting…</>
              : <><Languages className="w-4 h-4" /> Convert to Native Script</>
            }
          </button>

          {state === "error" && errorMsg && (
            <p className="mt-2 text-xs text-red-500">{errorMsg}</p>
          )}
        </div>
      </div>

      {/* ── Right: native script output ─────────────────────────────────── */}
      <div className="flex flex-col px-7 pt-7 pb-6">
        <div className="flex items-center justify-between mb-5">
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">Native Script</p>
          {state === "done" && result && (
            <button
              onClick={copyResult}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
            >
              {copied
                ? <><CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> Copied</>
                : <><ClipboardCopy className="w-3.5 h-3.5" /> Copy</>
              }
            </button>
          )}
        </div>

        {state === "idle" && (
          <div className="flex-1 flex items-center justify-center rounded-2xl border border-dashed border-slate-100">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center mx-auto">
                <Languages className="w-5 h-5 text-slate-300" />
              </div>
              <p className="text-sm text-slate-400">Transliterated text will appear here</p>
            </div>
          </div>
        )}
        {state === "loading" && (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
          </div>
        )}
        {state === "done" && (
          <div className="flex-1 p-5 bg-slate-50 rounded-2xl border border-slate-100 overflow-auto">
            <p className="text-2xl text-slate-800 leading-relaxed font-medium">
              {result || <em className="text-slate-400 not-italic text-sm">No output returned.</em>}
            </p>
          </div>
        )}

        <div className="pt-4 mt-4 border-t border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            <p className="text-xs text-slate-400">
              Powered by <span className="text-slate-600 font-semibold">Sarvam Transliterate</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
