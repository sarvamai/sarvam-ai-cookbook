"use client";

import { useState } from "react";
import { Volume2, Mic, Languages } from "lucide-react";
import { TTSPanel } from "./TTSPanel";
import { STTPanel } from "./STTPanel";
import { TransliteratePanel } from "./TransliteratePanel";

type Tab = "tts" | "stt" | "transliterate";

const TABS: {
  id: Tab;
  label: string;
  shortLabel: string;
  icon: React.ReactNode;
  description: string;
  model: string;
}[] = [
  {
    id: "tts",
    label: "Text → Speech",
    shortLabel: "TTS",
    icon: <Volume2 className="w-4 h-4" />,
    description: "Convert text into natural-sounding speech in Indian languages",
    model: "Bulbul v3",
  },
  {
    id: "stt",
    label: "Speech → Text",
    shortLabel: "STT",
    icon: <Mic className="w-4 h-4" />,
    description: "Transcribe recorded or uploaded audio in Indian languages",
    model: "Saarika v2",
  },
  {
    id: "transliterate",
    label: "Transliterate",
    shortLabel: "Script",
    icon: <Languages className="w-4 h-4" />,
    description: "Convert Roman-script text into native Indian language scripts",
    model: "Transliterate API",
  },
];

export function VoiceDemo() {
  const [activeTab, setActiveTab] = useState<Tab>("tts");

  const activeTabData = TABS.find((t) => t.id === activeTab)!;

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Header ── */}
      <header className="bg-gradient-to-r from-indigo-600 to-violet-600 text-white">
        <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
          <div className="flex items-center gap-3 mb-3">
            {/* Sarvam-inspired logo mark */}
            <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center font-bold text-lg">
              स
            </div>
            <span className="text-white/70 font-medium text-sm tracking-wide">
              Sarvam AI
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight mb-2">
            Voice API Demo
          </h1>
          <p className="text-indigo-200 text-sm sm:text-base max-w-xl">
            Interactive playground for Sarvam&apos;s multilingual voice APIs —
            TTS, STT, and Transliteration across 10 Indian languages.
          </p>

          {/* API pills */}
          <div className="flex flex-wrap gap-2 mt-4">
            {TABS.map((tab) => (
              <span
                key={tab.id}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full
                           bg-white/15 backdrop-blur-sm text-xs font-medium text-white/90"
              >
                {tab.icon}
                {tab.model}
              </span>
            ))}
          </div>
        </div>
      </header>

      {/* ── Tab bar ── */}
      <div className="border-b border-slate-200 bg-white sticky top-0 z-10 shadow-sm">
        <div className="max-w-3xl mx-auto px-4">
          <nav className="flex gap-1 -mb-px" role="tablist">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`group flex items-center gap-2 px-4 py-4 text-sm font-medium border-b-2 transition-all
                  ${
                    activeTab === tab.id
                      ? "border-indigo-600 text-indigo-600"
                      : "border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300"
                  }`}
              >
                <span
                  className={
                    activeTab === tab.id
                      ? "text-indigo-600"
                      : "text-slate-400 group-hover:text-slate-600"
                  }
                >
                  {tab.icon}
                </span>
                {/* Full label on larger screens, short on mobile */}
                <span className="hidden sm:inline">{tab.label}</span>
                <span className="sm:hidden">{tab.shortLabel}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* ── Main content ── */}
      <main className="flex-1 max-w-3xl mx-auto w-full px-4 py-8">
        {/* Panel description */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-slate-800 mb-1">
            {activeTabData.label}
          </h2>
          <p className="text-sm text-slate-500">{activeTabData.description}</p>
          <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 text-xs font-medium">
            Model: {activeTabData.model}
          </span>
        </div>

        {/* Panel card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          {activeTab === "tts" && <TTSPanel />}
          {activeTab === "stt" && <STTPanel />}
          {activeTab === "transliterate" && <TransliteratePanel />}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t border-slate-200 bg-white py-5">
        <div className="max-w-3xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-400">
          <span>
            Built with{" "}
            <a
              href="https://docs.sarvam.ai"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-500 hover:underline"
            >
              Sarvam AI APIs
            </a>{" "}
            + Next.js 15 App Router
          </span>
          <span>
            <a
              href="https://github.com/sarvamai/sarvam-ai-cookbook"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-500 hover:underline"
            >
              sarvam-ai-cookbook
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}
