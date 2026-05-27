"use client";

import { useState, useEffect } from "react";
import { Volume2, Mic, Languages } from "lucide-react";
import { TTSPanel } from "./TTSPanel";
import { STTPanel } from "./STTPanel";
import { TransliteratePanel } from "./TransliteratePanel";
import { LandingPage } from "./LandingPage";
import { OnboardingTooltip, type TourStep } from "./OnboardingTooltip";

type View = "landing" | "demo";
type Tab  = "tts" | "stt" | "transliterate";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "tts",           label: "Text to Speech",  icon: <Volume2   className="w-3.5 h-3.5" /> },
  { id: "stt",           label: "Speech to Text",  icon: <Mic        className="w-3.5 h-3.5" /> },
  { id: "transliterate", label: "Transliterate",   icon: <Languages  className="w-3.5 h-3.5" /> },
];

const TOUR_STEPS: TourStep[] = [
  // ── TTS tab ─────────────────────────────────────────────────────────────
  {
    targetId:    "onboard-tab-bar",
    tab:         "tts",
    title:       "Text to Speech",
    description:
      "This tab lets you convert written text into spoken audio. Sarvam's Bulbul model supports 10 Indian languages with natural-sounding voices.",
  },
  {
    targetId:    "onboard-tts-textarea",
    tab:         "tts",
    title:       "Type Your Text",
    description:
      "Enter any text here in Hindi, Tamil, Telugu, or any of the 10 supported Indian languages. Bulbul v3 will convert it into natural-sounding speech.",
  },
  {
    targetId:    "onboard-language",
    tab:         "tts",
    title:       "Choose Your Language",
    description:
      "Select the language that matches your input text. The generated voice automatically adapts its pronunciation and tone to the chosen language.",
  },
  {
    targetId:    "onboard-speak-btn",
    tab:         "tts",
    title:       "Generate & Play Audio",
    description:
      "Hit Speak to generate audio. Stop playback anytime, and replay the clip using the audio player that appears below.",
  },

  // ── STT tab ─────────────────────────────────────────────────────────────
  {
    targetId:    "onboard-tab-stt",
    tab:         "stt",
    title:       "Speech to Text",
    description:
      "Switch to this tab to transcribe audio into text using Sarvam's Saarika v2 model. Works with live recordings and uploaded audio files.",
  },
  {
    targetId:    "onboard-stt-input",
    tab:         "stt",
    title:       "Record or Upload Audio",
    description:
      "Click Start Recording to capture your voice from the mic, or upload a WAV / MP3 / WebM file. Both inputs are sent to the Saarika STT API.",
  },
  {
    targetId:    "onboard-transcribe-btn",
    tab:         "stt",
    title:       "Run Transcription",
    description:
      "Once you have audio ready, hit Transcribe. The full transcript appears on the right — you can copy it with one click.",
  },

  // ── Transliterate tab ────────────────────────────────────────────────────
  {
    targetId:    "onboard-tab-transliterate",
    tab:         "transliterate",
    title:       "Transliterate",
    description:
      "This tab converts Roman-script text (typed in English letters) into the correct native script for any of the 10 supported Indian languages.",
  },
  {
    targetId:    "onboard-transliterate-input",
    tab:         "transliterate",
    title:       "Type Romanised Text",
    description:
      "Type phonetically, e.g. \"namaste\" or \"vanakkam\". The API intelligently maps each word to the right script characters.",
  },
  {
    targetId:    "onboard-convert-btn",
    tab:         "transliterate",
    title:       "Convert to Native Script",
    description:
      "Hit Convert and the transliterated output appears instantly on the right. Use the language selector below to switch between scripts.",
  },
];

export function VoiceDemo() {
  const [view,      setView]      = useState<View>("landing");
  const [activeTab, setActiveTab] = useState<Tab>("tts");
  const [showTour,  setShowTour]  = useState(false);
  const [tourStep,  setTourStep]  = useState(0);

  // Switch tab whenever the current tour step requires a different tab
  useEffect(() => {
    if (!showTour) return;
    const tab = TOUR_STEPS[tourStep]?.tab as Tab | undefined;
    if (tab && tab !== activeTab) setActiveTab(tab);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tourStep, showTour]);

  const handleTourNext = () => {
    if (tourStep < TOUR_STEPS.length - 1) {
      setTourStep((s) => s + 1);
    } else {
      setShowTour(false);
      setTourStep(0);
    }
  };

  const handleTourDone = () => {
    setShowTour(false);
    setTourStep(0);
  };

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        background: `
          radial-gradient(ellipse 70% 55% at 15% 60%, rgba(192,180,240,0.30) 0%, transparent 55%),
          radial-gradient(ellipse 60% 45% at 85% 20%, rgba(253,214,183,0.35) 0%, transparent 50%),
          radial-gradient(ellipse 55% 50% at 55% 85%, rgba(179,198,255,0.25) 0%, transparent 55%),
          #EAE8F3
        `,
      }}
    >

      {/* ── Navbar (always visible) ────────────────────────────────────── */}
      <header className="pt-5 px-4">
        <div className="max-w-5xl mx-auto">
          <div
            className="flex items-center justify-between rounded-2xl px-7 py-4 shadow-sm border border-[#E8E6F0]"
            style={{
              background: "linear-gradient(to right, #FDF6EE, #FFFFFF 40%, #F0EDFB)",
            }}
          >
            {/* Wordmark */}
            <button
              onClick={() => setView("landing")}
              className="text-[#111827] font-bold text-2xl tracking-tight hover:opacity-70 transition-opacity"
            >
              sarvam
            </button>

            {/* Nav links */}
            <nav className="hidden md:flex items-center gap-7">
              <a
                href="https://docs.sarvam.ai/api-reference-docs/introduction"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-semibold uppercase tracking-widest text-[#6B7280]
                           hover:text-[#111827] transition-colors"
              >
                Docs
              </a>
              <a
                href="https://www.sarvam.ai/about"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-semibold uppercase tracking-widest text-[#6B7280]
                           hover:text-[#111827] transition-colors"
              >
                Company
              </a>
            </nav>

            {/* Right slot */}
            <div className="w-[110px] flex justify-end">
              {view === "demo" && (
                <button
                  onClick={() => setView("landing")}
                  className="text-xs text-[#9CA3AF] hover:text-[#6B7280] transition-colors font-medium"
                >
                  ← Back
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* ── Landing ───────────────────────────────────────────────────────── */}
      {view === "landing" && (
        <LandingPage
          onGetStarted={() => {
            setView("demo");
            setActiveTab("tts");
            setTourStep(0);
            setShowTour(true);
          }}
        />
      )}

      {/* ── Demo ─────────────────────────────────────────────────────────── */}
      {view === "demo" && (
        <div className="fade-in flex-1 px-4 pt-8 pb-10 max-w-4xl mx-auto w-full">

          {/* Card */}
          <div
            className="bg-white rounded-3xl overflow-hidden"
            style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 12px 40px rgba(0,0,0,0.09), 0 0 0 1px rgba(0,0,0,0.04)" }}
          >
            {/* ── Card header with segmented tabs ── */}
            <div
              className="px-6 pt-5 pb-0"
              style={{ background: "linear-gradient(to bottom, #FDFCFF, #FFFFFF)" }}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-[#C4BFDA] mb-0.5">
                    Interactive Demo
                  </p>
                  <h2 className="text-lg font-bold text-[#111827] tracking-tight">Try the APIs</h2>
                </div>
                {/* API badge */}
                <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#F5F3FF] text-xs font-medium text-[#6366F1]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#6366F1]" />
                  Sarvam APIs
                </span>
              </div>

              {/* Segmented tab control */}
              <div className="flex items-center gap-1 p-1 bg-[#F5F3FF] rounded-xl w-fit">
                {TABS.map((tab) => {
                  // Each tab button gets its own tour ID
                  const tabId =
                    tab.id === "tts"           ? "onboard-tab-bar"
                    : tab.id === "stt"         ? "onboard-tab-stt"
                    : "onboard-tab-transliterate";

                  return (
                    <button
                      key={tab.id}
                      id={tabId}
                      onClick={() => setActiveTab(tab.id)}
                      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                        ${activeTab === tab.id
                          ? "bg-white text-[#111827] shadow-sm"
                          : "text-[#9CA3AF] hover:text-[#6B7280]"
                        }`}
                    >
                      {tab.icon}
                      <span className="hidden sm:inline">{tab.label}</span>
                      <span className="sm:hidden">{tab.label.split(" ")[0]}</span>
                    </button>
                  );
                })}
              </div>

              {/* Divider */}
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
              onDone={handleTourDone}
            />
          )}

          {/* Footer note */}
          <p className="text-center text-xs text-[#B0AABF] mt-5">
            API key is server-side only · No audio stored ·{" "}
            <a
              href="https://github.com/sarvamai/sarvam-ai-cookbook"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-[#6B7280] transition-colors"
            >
              sarvam-ai-cookbook
            </a>
          </p>
        </div>
      )}
    </div>
  );
}
