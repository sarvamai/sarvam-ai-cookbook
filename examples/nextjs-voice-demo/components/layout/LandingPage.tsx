"use client";

import { Volume2, Mic, Languages, ArrowRight } from "lucide-react";

interface LandingPageProps {
  onGetStarted: () => void;
}

const CARDS = [
  {
    icon:        <Volume2  className="w-6 h-6 text-white" />,
    iconBg:      "bg-[#4F46E5]",
    glow:        "rgba(79,70,229,0.12)",
    title:       "Text to Speech",
    description: "Convert any text into natural-sounding speech across 10 Indian languages with two distinct voices.",
    model:       "Bulbul v3",
    modelColor:  "#4F46E5",
  },
  {
    icon:        <Mic       className="w-6 h-6 text-white" />,
    iconBg:      "bg-[#0284C7]",
    glow:        "rgba(2,132,199,0.12)",
    title:       "Speech to Text",
    description: "Transcribe microphone recordings or uploaded audio files with high accuracy.",
    model:       "Saarika v2.5",
    modelColor:  "#0284C7",
  },
  {
    icon:        <Languages className="w-6 h-6 text-white" />,
    iconBg:      "bg-[#16A34A]",
    glow:        "rgba(22,163,74,0.12)",
    title:       "Transliterate",
    description: "Instantly convert Roman-script text into native Indian language scripts.",
    model:       "Transliterate API",
    modelColor:  "#16A34A",
  },
];

export function LandingPage({ onGetStarted }: LandingPageProps) {
  return (
    <div className="fade-in flex-1 flex flex-col items-center px-4 pt-12 pb-16">

      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className="text-center max-w-3xl mx-auto mb-24">
        <h1 className="text-5xl sm:text-6xl font-bold uppercase tracking-wider leading-tight mb-8 text-[#1A1B3A]">
          VOICE AI FOR
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{ backgroundImage: "linear-gradient(135deg, #5B5EA6 0%, #C47C2B 100%)" }}
          >
            EVERY INDIAN LANGUAGE
          </span>
        </h1>

        <button
          onClick={onGetStarted}
          className="inline-flex items-center gap-2 px-9 py-3.5 hover:-translate-y-0.5 active:translate-y-0
                     text-white text-sm font-bold uppercase tracking-widest rounded-xl transition-all duration-200 cursor-pointer"
          style={{
            background: "linear-gradient(135deg, #5B5EA6 0%, #C47C2B 100%)",
            boxShadow:  "0 4px 20px rgba(91,94,166,0.38)",
          }}
        >
          Get Started
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* ── Feature cards ─────────────────────────────────────────────────── */}
      <div className="w-full max-w-5xl grid grid-cols-1 sm:grid-cols-3 gap-7">
        {CARDS.map((card) => (
          <div
            key={card.title}
            className="relative rounded-2xl p-7 cursor-default group transition-all duration-300 hover:-translate-y-1"
            style={{
              background:       `radial-gradient(ellipse at 60% 0%, ${card.glow} 0%, transparent 60%), rgba(255,255,255,0.72)`,
              backdropFilter:   "blur(16px)",
              WebkitBackdropFilter: "blur(16px)",
              border:           "1px solid rgba(255,255,255,0.8)",
              boxShadow: `
                0 2px 0 rgba(255,255,255,0.9) inset,
                0 8px 24px rgba(91,94,166,0.10),
                0 1px 4px rgba(0,0,0,0.06),
                0 0 0 1px rgba(180,180,220,0.18)
              `,
            }}
          >
            {/* Top-edge shine */}
            <div
              className="absolute inset-x-6 top-0 h-px rounded-full"
              style={{ background: "linear-gradient(90deg, transparent, rgba(255,255,255,1) 50%, transparent)" }}
            />

            {/* Icon */}
            <div
              className={`w-12 h-12 ${card.iconBg} rounded-xl flex items-center justify-center mb-5
                          group-hover:scale-110 transition-transform duration-300`}
              style={{ boxShadow: `0 6px 18px ${card.glow.replace("0.12", "0.45")}` }}
            >
              {card.icon}
            </div>

            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-900 mb-2">{card.title}</h3>
            <p className="text-sm text-slate-500 leading-relaxed mb-5">{card.description}</p>

            <div className="flex items-center gap-2 pt-3 border-t border-white/60">
              <span className="inline-block w-2 h-2 rounded-full" style={{ background: card.modelColor }} />
              <span className="text-xs font-semibold text-slate-500">{card.model}</span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Trust strip ───────────────────────────────────────────────────── */}
      <div className="mt-20 flex flex-wrap items-center justify-center gap-x-10 gap-y-3">
        {["10 Indian Languages", "Bulbul v3 · Saarika v2.5", "Server-side Security", "MIT License"].map(
          (item, i, arr) => (
            <span key={item} className="flex items-center gap-10">
              <span className="text-xs text-[#6366A8] font-medium">{item}</span>
              {i < arr.length - 1 && (
                <span className="hidden sm:inline text-[#A0A3CC] text-xs">·</span>
              )}
            </span>
          )
        )}
      </div>
    </div>
  );
}
