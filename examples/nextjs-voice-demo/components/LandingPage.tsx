"use client";

import { Volume2, Mic, Languages, ArrowRight } from "lucide-react";

interface LandingPageProps {
  onGetStarted: () => void;
}

const CARDS = [
  {
    icon:        <Volume2  className="w-6 h-6 text-white" />,
    iconBg:      "bg-[#60A5FA]",
    glow:        "rgba(96,165,250,0.25)",
    title:       "Text to Speech",
    description: "Convert any text into natural-sounding speech across 10 Indian languages with two distinct voices.",
    model:       "Bulbul v3",
    modelColor:  "#3B82F6",
  },
  {
    icon:        <Mic       className="w-6 h-6 text-white" />,
    iconBg:      "bg-[#A78BFA]",
    glow:        "rgba(167,139,250,0.28)",
    title:       "Speech to Text",
    description: "Transcribe microphone recordings or uploaded audio files with high accuracy.",
    model:       "Saarika v2",
    modelColor:  "#7C3AED",
  },
  {
    icon:        <Languages className="w-6 h-6 text-white" />,
    iconBg:      "bg-[#34D399]",
    glow:        "rgba(52,211,153,0.22)",
    title:       "Transliterate",
    description: "Instantly convert Roman-script text into native Indian language scripts.",
    model:       "Transliterate API",
    modelColor:  "#059669",
  },
];

export function LandingPage({ onGetStarted }: LandingPageProps) {
  return (
    <div className="fade-in flex-1 flex flex-col items-center px-4 pt-12 pb-16">

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="text-center max-w-2xl mx-auto mb-16">

        {/* Motif */}
        <div className="text-xl text-[#C4BFDA] mb-6 tracking-widest select-none">
          ✦ &nbsp;&nbsp; ✦ &nbsp;&nbsp; ✦
        </div>

        {/* Label */}
        <p className="text-xs font-semibold uppercase tracking-widest text-[#9CA3AF] mb-4">
          Sarvam AI · Open-Source Cookbook Example
        </p>

        {/* Headline */}
        <h1 className="text-5xl sm:text-6xl font-bold text-[#111827] tracking-tight leading-tight mb-5">
          Voice AI for
          <br />
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage: "linear-gradient(135deg, #6366F1 0%, #A78BFA 50%, #EC4899 100%)",
            }}
          >
            every Indian language
          </span>
        </h1>

        {/* Sub */}
        <p className="text-lg text-[#6B7280] leading-relaxed mb-10 max-w-lg mx-auto">
          Text-to-Speech, Speech-to-Text, and Transliteration —
          all in one demo. Powered by Sarvam&apos;s Bulbul &amp; Saarika models.
        </p>

        {/* CTA */}
        <button
          onClick={onGetStarted}
          className="inline-flex items-center gap-2.5 px-8 py-4 bg-[#111827] hover:bg-[#1F2937]
                     text-white text-base font-semibold rounded-full transition-all duration-200
                     shadow-[0_4px_14px_0_rgba(17,24,39,0.35)] hover:shadow-[0_6px_20px_0_rgba(17,24,39,0.45)]
                     hover:-translate-y-0.5"
        >
          Get Started
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>

      {/* ── 3D Feature cards ─────────────────────────────────────────────── */}
      <div className="w-full max-w-4xl grid grid-cols-1 sm:grid-cols-3 gap-6 sm:gap-5">
        {CARDS.map((card) => (
          <div
            key={card.title}
            className="relative bg-white rounded-2xl p-6 cursor-default"
            style={{
              boxShadow: `0 1px 3px rgba(0,0,0,0.04),
                          0 8px 24px rgba(0,0,0,0.07),
                          0 0 0 1px rgba(0,0,0,0.04)`,
              background: `radial-gradient(ellipse at 60% 0%, ${card.glow} 0%, transparent 65%), #ffffff`,
            }}
          >
            {/* Icon */}
            <div className={`w-12 h-12 ${card.iconBg} rounded-xl flex items-center justify-center mb-5 shadow-sm`}>
              {card.icon}
            </div>

            {/* Text */}
            <h3 className="text-base font-semibold text-[#111827] mb-2">{card.title}</h3>
            <p className="text-sm text-[#6B7280] leading-relaxed mb-5">{card.description}</p>

            {/* Model tag */}
            <div className="flex items-center gap-1.5">
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: card.modelColor }}
              />
              <span className="text-xs font-medium" style={{ color: card.modelColor }}>
                {card.model}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Trust strip ──────────────────────────────────────────────────── */}
      <div className="mt-16 flex flex-wrap items-center justify-center gap-x-8 gap-y-2">
        {[
          "10 Indian Languages",
          "Bulbul v3 · Saarika v2",
          "Server-side API key",
          "Open Source",
        ].map((item, i, arr) => (
          <span key={item} className="flex items-center gap-8">
            <span className="text-xs text-[#9CA3AF] font-medium">{item}</span>
            {i < arr.length - 1 && (
              <span className="hidden sm:inline text-[#DDD9EC] text-xs">·</span>
            )}
          </span>
        ))}
      </div>
    </div>
  );
}
