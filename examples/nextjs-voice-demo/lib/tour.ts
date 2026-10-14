import { Volume2, Mic, Languages } from "lucide-react";
import type { TourStep } from "./types";

export type Tab = "tts" | "stt" | "transliterate";

export const TABS: { id: Tab; label: string; Icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "tts",           label: "Text to Speech", Icon: Volume2   },
  { id: "stt",           label: "Speech to Text", Icon: Mic        },
  { id: "transliterate", label: "Transliterate",  Icon: Languages  },
];

export const TOUR_STEPS: TourStep[] = [
  // ── TTS tab ─────────────────────────────────────────────────────────────
  {
    targetId:    "onboard-tab-bar",
    tab:         "tts",
    title:       "Text to Speech",
    description:
      "This tab converts written text into spoken audio. Sarvam's Bulbul v3 model supports 10 Indian languages with natural-sounding voices.",
  },
  {
    targetId:    "onboard-tts-textarea",
    tab:         "tts",
    title:       "Type Your Text",
    description:
      "Enter any text in Hindi, Tamil, Telugu, or any of the 10 supported Indian languages. Bulbul v3 converts it into natural-sounding speech.",
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
      "Switch here to transcribe audio using Sarvam's Saarika v2 model. Works with live mic recordings and uploaded audio files.",
  },
  {
    targetId:    "onboard-stt-input",
    tab:         "stt",
    title:       "Record or Upload Audio",
    description:
      "Click Start Recording to capture your voice, or upload a WAV / MP3 / WebM file. Both are sent to the Saarika STT API.",
  },
  {
    targetId:    "onboard-transcribe-btn",
    tab:         "stt",
    title:       "Run Transcription",
    description:
      "Once you have audio ready, hit Transcribe. The full transcript appears on the right — copy it with one click.",
  },

  // ── Transliterate tab ────────────────────────────────────────────────────
  {
    targetId:    "onboard-tab-transliterate",
    tab:         "transliterate",
    title:       "Transliterate",
    description:
      "This tab converts Roman-script text (English letters) into the correct native script for any of the 10 supported Indian languages.",
  },
  {
    targetId:    "onboard-transliterate-input",
    tab:         "transliterate",
    title:       "Type Romanised Text",
    description:
      "Type phonetically, e.g. \"namaste\" or \"vanakkam\". The API maps each word to the right native script characters.",
  },
  {
    targetId:    "onboard-convert-btn",
    tab:         "transliterate",
    title:       "Convert to Native Script",
    description:
      "Hit Convert and the transliterated output appears on the right. Use the language selector to switch between scripts.",
  },
];
