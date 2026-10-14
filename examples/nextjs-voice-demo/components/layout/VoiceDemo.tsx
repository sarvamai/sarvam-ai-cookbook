"use client";

import { useState, useEffect } from "react";
import { TTSPanel }           from "@/components/panels/TTSPanel";
import { STTPanel }           from "@/components/panels/STTPanel";
import { TransliteratePanel } from "@/components/panels/TransliteratePanel";
import { LandingPage }        from "@/components/layout/LandingPage";
import { OnboardingTooltip }  from "@/components/ui/OnboardingTooltip";
import { TABS, TOUR_STEPS }   from "@/lib/tour";
import { TOUR_SEEN_KEY }      from "@/lib/constants";
import type { Tab }           from "@/lib/tour";

type View = "landing" | "demo";

export function VoiceDemo() {
  const [view,      setView]      = useState<View>("landing");
  const [activeTab, setActiveTab] = useState<Tab>("tts");
  const [showTour,  setShowTour]  = useState(false);
  const [tourStep,  setTourStep]  = useState(0);

  // Switch tab whenever the current tour step targets a different tab
  useEffect(() => {
    if (!showTour) return;
    const tab = TOUR_STEPS[tourStep]?.tab as Tab | undefined;
    if (tab && tab !== activeTab) setActiveTab(tab);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourStep, showTour]);

  /** Persist the tour as seen and close it. */
  const markTourSeen = () => {
    try { localStorage.setItem(TOUR_SEEN_KEY, "1"); } catch { /* SSR / private browsing */ }
    setShowTour(false);
    setTourStep(0);
  };

  const handleTourNext = () => {
    tourStep < TOUR_STEPS.length - 1
      ? setTourStep((s) => s + 1)
      : markTourSeen();
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: `
          radial-gradient(ellipse 85% 48% at 50% 0%, rgba(230,145,55,0.72) 0%, rgba(195,165,230,0.38) 46%, transparent 66%),
          linear-gradient(180deg, #D8DBF2 0%, #E4E5F5 50%, #ECEEF8 100%)
        `,
      }}
    >
      {/* ── Navbar ──────────────────────────────────────────────────────── */}
      <header className="pt-6 px-5">
        <div className="max-w-5xl mx-auto">
          <div
            className="flex items-center justify-between rounded-[32px] px-10 py-6 shadow-lg border border-slate-200"
            style={{ background: "linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%)" }}
          >
            <button
              onClick={() => setView("landing")}
              className="text-slate-900 font-semibold text-4xl tracking-tight leading-tight
                         flex items-center py-1 hover:opacity-80 transition-opacity cursor-pointer outline-none"
            >
              sarvam
            </button>

            <nav className="hidden md:flex items-center gap-7">
              <a
                href="https://docs.sarvam.ai/api-reference-docs/introduction"
                target="_blank" rel="noopener noreferrer"
                className="text-xs font-semibold uppercase tracking-widest text-[#6B7280]
                           hover:text-[#111827] transition-colors"
              >
                Docs
              </a>
              <a
                href="https://docs.sarvam.ai"
                target="_blank" rel="noopener noreferrer"
                className="text-xs font-semibold uppercase tracking-widest text-[#6B7280]
                           hover:text-[#111827] transition-colors"
              >
                Developers
              </a>
            </nav>
          </div>
        </div>
      </header>

      {/* ── Landing ─────────────────────────────────────────────────────── */}
      {view === "landing" && (
        <LandingPage
          onGetStarted={() => {
            setView("demo");
            setActiveTab("tts");
            setTourStep(0);
            const alreadySeen = (() => {
              try { return !!localStorage.getItem(TOUR_SEEN_KEY); } catch { return false; }
            })();
            setShowTour(!alreadySeen);
          }}
        />
      )}

      {/* ── Demo ────────────────────────────────────────────────────────── */}
      {view === "demo" && (
        <div className="fade-in flex-1 px-4 pt-8 pb-10 max-w-4xl mx-auto w-full">

          {/* Card */}
          <div
            className="rounded-3xl overflow-hidden min-h-[560px] transition-all duration-200"
            style={{
              boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 12px 40px rgba(0,0,0,0.09), 0 0 0 1px rgba(0,0,0,0.04)",
              background: "linear-gradient(180deg, #FFFFFF 0%, #FAFBFF 100%)",
            }}
          >
            {/* Card header + tabs */}
            <div
              className="px-6 pt-5 pb-0"
              style={{ background: "linear-gradient(to bottom, #FFFFFF, #FAFBFC)" }}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-[#C4BFDA] mb-0.5">
                    Interactive Demo
                  </p>
                  <h2 className="text-lg font-bold text-[#111827] tracking-tight">Try the APIs</h2>
                </div>
                <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#F5F3FF] text-xs font-medium text-[#6366F1]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#6366F1]" />
                  Sarvam APIs
                </span>
              </div>

              {/* Segmented tabs */}
              <div className="flex items-center gap-1 p-1 bg-[#F5F3FF] rounded-xl w-fit">
                {TABS.map(({ id, label, Icon }) => {
                  const tabId =
                    id === "tts"           ? "onboard-tab-bar"
                    : id === "stt"         ? "onboard-tab-stt"
                    : "onboard-tab-transliterate";
                  return (
                    <button
                      key={id}
                      id={tabId}
                      onClick={() => setActiveTab(id)}
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer
                        ${activeTab === id
                          ? "bg-white text-[#111827] shadow-sm"
                          : "text-[#9CA3AF] hover:text-[#6B7280]"
                        }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">{label}</span>
                      <span className="sm:hidden">{label.split(" ")[0]}</span>
                    </button>
                  );
                })}
              </div>

              <div className="h-px bg-[#F0EEF8] mt-4" />
            </div>

            {activeTab === "tts"           && <TTSPanel />}
            {activeTab === "stt"           && <STTPanel />}
            {activeTab === "transliterate" && <TransliteratePanel />}
          </div>

          {/* Onboarding tour */}
          {showTour && (
            <OnboardingTooltip
              steps={TOUR_STEPS}
              currentStep={tourStep}
              onNext={handleTourNext}
              onDone={markTourSeen}
            />
          )}

          {/* Footer */}
          <p className="text-center text-xs text-slate-500 mt-5">
            API key is server-side only · No audio stored ·{" "}
            <a
              href="https://github.com/sarvamai/sarvam-ai-cookbook"
              target="_blank" rel="noopener noreferrer"
              className="text-slate-600 hover:text-slate-900 transition-colors"
            >
              sarvam-ai-cookbook
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
