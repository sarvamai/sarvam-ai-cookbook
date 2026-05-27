"use client";

import { useState } from "react";
import { Volume2, Mic, Languages } from "lucide-react";
import { TTSPanel } from "./TTSPanel";
import { STTPanel } from "./STTPanel";
import { TransliteratePanel } from "./TransliteratePanel";

type Tab = "tts" | "stt" | "transliterate";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "tts",          label: "Text to Speech",  icon: <Volume2  className="w-3.5 h-3.5" /> },
  { id: "stt",          label: "Speech to Text",  icon: <Mic       className="w-3.5 h-3.5" /> },
  { id: "transliterate",label: "Transliterate",   icon: <Languages className="w-3.5 h-3.5" /> },
];

export function VoiceDemo() {
  const [activeTab, setActiveTab] = useState<Tab>("tts");

  return (
    <div className="min-h-screen bg-[#EAE8F3] flex flex-col">

      {/* ── Top nav — matches Sarvam's floating pill navbar ── */}
      <header className="pt-6 px-4">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between bg-white rounded-2xl px-5 py-3.5 shadow-sm border border-[#E5E3EE]">
            {/* Wordmark */}
            <div className="flex items-center gap-2">
              <span className="text-[#111827] font-semibold text-lg tracking-tight">sarvam</span>
              <span className="text-[#9CA3AF] text-sm font-normal">/ voice demo</span>
            </div>

            {/* Links */}
            <div className="hidden sm:flex items-center gap-1">
              <a
                href="https://docs.sarvam.ai/api-reference-docs/introduction"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 text-sm text-[#6B7280] hover:text-[#111827] transition-colors rounded-lg hover:bg-[#F9F8FC]"
              >
                Docs
              </a>
              <a
                href="https://github.com/sarvamai/sarvam-ai-cookbook"
                target="_blank"
                rel="noopener noreferrer"
                className="px-3 py-1.5 text-sm text-[#6B7280] hover:text-[#111827] transition-colors rounded-lg hover:bg-[#F9F8FC]"
              >
                Cookbook
              </a>
              <a
                href="https://dashboard.sarvam.ai"
                target="_blank"
                rel="noopener noreferrer"
                className="ml-2 px-4 py-2 bg-[#111827] hover:bg-[#1F2937] text-white text-sm font-medium rounded-full transition-colors"
              >
                Get API key
              </a>
            </div>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <div className="pt-12 pb-8 px-4 text-center">
        {/* Decorative motif — matches the swirl on sarvam.ai */}
        <div className="text-2xl text-[#C4BFDA] mb-4 select-none">〰 ✦ 〰</div>

        <p className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF] mb-3">
          Voice APIs · Open-source example
        </p>
        <h1 className="text-3xl sm:text-4xl font-semibold text-[#111827] tracking-tight mb-4">
          AI for all from India
        </h1>
        <p className="text-[#6B7280] text-base max-w-md mx-auto">
          Text-to-Speech, Speech-to-Text, and Transliteration across 10 Indian languages —
          powered by Sarvam&apos;s Bulbul &amp; Saarika models.
        </p>
      </div>

      {/* ── Main card ── */}
      <div className="flex-1 px-4 pb-10 max-w-4xl mx-auto w-full">
        <div className="bg-white rounded-3xl border border-[#E5E3EE] shadow-sm overflow-hidden">

          {/* Tab bar */}
          <div className="flex items-center gap-1 px-4 pt-4 pb-0 border-b border-[#E5E3EE]">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-xl
                            border-b-2 transition-all -mb-px
                  ${activeTab === tab.id
                    ? "border-[#111827] text-[#111827] bg-white"
                    : "border-transparent text-[#9CA3AF] hover:text-[#6B7280] hover:bg-[#F9F8FC]"
                  }`}
              >
                {tab.icon}
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.label.split(" ")[0]}</span>
              </button>
            ))}
          </div>

          {/* Panel content */}
          {activeTab === "tts"          && <TTSPanel />}
          {activeTab === "stt"          && <STTPanel />}
          {activeTab === "transliterate"&& <TransliteratePanel />}
        </div>

        {/* Footer note */}
        <p className="text-center text-xs text-[#9CA3AF] mt-5">
          API key is server-side only · No audio stored · Built with{" "}
          <a
            href="https://nextjs.org"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#6B7280] hover:text-[#111827] transition-colors"
          >
            Next.js 15
          </a>{" "}
          ·{" "}
          <a
            href="https://github.com/sarvamai/sarvam-ai-cookbook"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[#6B7280] hover:text-[#111827] transition-colors"
          >
            sarvam-ai-cookbook
          </a>
        </p>
      </div>
    </div>
  );
}
