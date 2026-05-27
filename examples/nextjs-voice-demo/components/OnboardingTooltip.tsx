"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { ArrowRight } from "lucide-react";

export interface TourStep {
  targetId: string;
  title: string;
  description: string;
  tab?: string; // which tab must be active before measuring this step
}

interface Props {
  steps:       TourStep[];
  currentStep: number;          // controlled externally
  onNext:      () => void;      // caller advances the step
  onDone:      () => void;
}

const PAD    = 10;
const TIP_W  = 300;
const RADIUS = 12;

export function OnboardingTooltip({ steps, currentStep, onNext, onDone }: Props) {
  const [rect,    setRect]    = useState<DOMRect | null>(null);
  const [tipTop,  setTipTop]  = useState(0);
  const [mounted, setMounted] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => { setMounted(true); }, []);

  // When step changes, keep retrying until the target element appears in the DOM
  // (it may not exist yet if a tab switch just happened)
  useEffect(() => {
    if (!mounted) return;
    setRect(null); // clear previous highlight while tab switches

    let raf: number;
    let attempts = 0;
    const MAX = 40; // ~660 ms at 60fps

    const tryFind = () => {
      const el = document.getElementById(steps[currentStep]?.targetId);
      if (el) {
        const measure = () => setRect(el.getBoundingClientRect());
        measure();
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        window.addEventListener("resize", measure);
        window.addEventListener("scroll", measure, true);
        return () => {
          window.removeEventListener("resize", measure);
          window.removeEventListener("scroll", measure, true);
        };
      }
      if (attempts++ < MAX) raf = requestAnimationFrame(tryFind);
    };

    raf = requestAnimationFrame(tryFind);
    return () => cancelAnimationFrame(raf);
  }, [currentStep, steps, mounted]);

  // After the card renders, measure its real height and reposition
  useEffect(() => {
    if (!rect || !cardRef.current) return;
    const cardH = cardRef.current.getBoundingClientRect().height;
    const vh    = window.innerHeight;
    const GAP   = 16;
    if (rect.top >= cardH + GAP + 20) {
      setTipTop(rect.top - cardH - GAP);
    } else {
      setTipTop(rect.bottom + GAP);
    }
  }, [rect]);

  if (!mounted || !rect) return null;

  const step   = steps[currentStep];
  const vw     = window.innerWidth;
  const sx     = rect.left   - PAD;
  const sy     = rect.top    - PAD;
  const sw     = rect.width  + PAD * 2;
  const sh     = rect.height + PAD * 2;
  const isBelow = tipTop > rect.bottom;
  const tipLeft = Math.max(
    16,
    Math.min(rect.left + rect.width / 2 - TIP_W / 2, vw - TIP_W - 16)
  );

  return createPortal(
    <div className="fixed inset-0 z-[100]">

      {/* ── SVG overlay with transparent cut-out ── */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ display: "block" }}>
        <defs>
          <mask id="tour-mask">
            <rect width="100%" height="100%" fill="white" />
            <rect x={sx} y={sy} width={sw} height={sh} rx={RADIUS} ry={RADIUS} fill="black" />
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="rgba(8,6,20,0.62)" mask="url(#tour-mask)" />
      </svg>

      {/* Click outside to skip */}
      <div className="absolute inset-0" onClick={onDone} />

      {/* Spotlight ring */}
      <div
        className="absolute pointer-events-none transition-all duration-300"
        style={{
          top: sy, left: sx, width: sw, height: sh, borderRadius: RADIUS, zIndex: 2,
          outline:     "2px solid rgba(255,255,255,0.55)",
          outlineOffset: "1px",
          boxShadow:   "0 0 0 3px rgba(99,102,241,0.30), 0 0 40px rgba(99,102,241,0.18)",
        }}
      />

      {/* Tooltip card */}
      <div
        className="absolute fade-in"
        style={{ top: tipTop, left: tipLeft, width: TIP_W, zIndex: 3 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Arrow */}
        {!isBelow && (
          <div className="absolute bottom-[-5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-white rotate-45"
            style={{ boxShadow: "2px 2px 4px rgba(0,0,0,0.06)", zIndex: -1 }} />
        )}

        <div
          ref={cardRef}
          className="bg-white rounded-2xl p-5 relative"
          style={{ boxShadow: "0 2px 6px rgba(0,0,0,0.04), 0 20px 60px rgba(0,0,0,0.20), 0 0 0 1px rgba(0,0,0,0.05)" }}
        >
          {isBelow && (
            <div className="absolute top-[-5px] left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-white rotate-45"
              style={{ boxShadow: "-1px -1px 4px rgba(0,0,0,0.05)", zIndex: -1 }} />
          )}

          {/* Progress pills */}
          <div className="flex items-center gap-1.5 mb-3">
            {steps.map((_, i) => (
              <div key={i} className="h-1.5 rounded-full transition-all duration-300"
                style={{
                  width:      i === currentStep ? 24 : 6,
                  background: i <= currentStep  ? "#6366F1" : "#E9E7F4",
                  opacity:    i < currentStep   ? 0.45 : 1,
                }} />
            ))}
            <span className="ml-auto text-[11px] text-[#C4BFDA] font-medium tabular-nums">
              {currentStep + 1} / {steps.length}
            </span>
          </div>

          <h3 className="text-sm font-bold text-[#111827] mb-1.5 leading-snug">{step.title}</h3>
          <p className="text-[13px] text-[#6B7280] leading-relaxed mb-4">{step.description}</p>

          <div className="flex items-center justify-between">
            <button onClick={onDone}
              className="text-xs text-[#C4BFDA] hover:text-[#9CA3AF] font-medium transition-colors">
              Skip tour
            </button>
            <button onClick={onNext}
              className="flex items-center gap-1.5 px-4 py-2 bg-[#111827] hover:bg-[#1F2937]
                         text-white text-xs font-semibold rounded-full transition-all
                         shadow-[0_2px_8px_rgba(17,24,39,0.25)]">
              {currentStep === steps.length - 1
                ? "Got it ✓"
                : <> Next <ArrowRight className="w-3 h-3" /> </>}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
