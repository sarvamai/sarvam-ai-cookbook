import type { Language, TTSSpeaker, LanguageCode } from "./types";

export const LANGUAGES: Language[] = [
  { code: "hi-IN", name: "Hindi",            nativeName: "हिंदी",       flag: "🇮🇳" },
  { code: "en-IN", name: "English (India)",  nativeName: "English",     flag: "🇮🇳" },
  { code: "ta-IN", name: "Tamil",            nativeName: "தமிழ்",       flag: "🇮🇳" },
  { code: "te-IN", name: "Telugu",           nativeName: "తెలుగు",      flag: "🇮🇳" },
  { code: "bn-IN", name: "Bengali",          nativeName: "বাংলা",       flag: "🇮🇳" },
  { code: "kn-IN", name: "Kannada",          nativeName: "ಕನ್ನಡ",       flag: "🇮🇳" },
  { code: "ml-IN", name: "Malayalam",        nativeName: "മലയാളം",      flag: "🇮🇳" },
  { code: "mr-IN", name: "Marathi",          nativeName: "मराठी",       flag: "🇮🇳" },
  { code: "gu-IN", name: "Gujarati",         nativeName: "ગુજરાતી",     flag: "🇮🇳" },
  { code: "pa-IN", name: "Punjabi",          nativeName: "ਪੰਜਾਬੀ",     flag: "🇮🇳" },
];

export const TTS_SPEAKERS: { value: TTSSpeaker; label: string; description: string }[] = [
  { value: "priya", label: "Priya", description: "Female voice" },
  { value: "shubh", label: "Shubh", description: "Male voice"   },
];

/** Sarvam TTS model identifier */
export const TTS_MODEL = "bulbul:v3";

/** Sarvam STT model identifier */
export const STT_MODEL = "saarika:v2";

/** Character limit per TTS request (Sarvam recommendation) */
export const MAX_TTS_CHARS = 500;

/** Audio formats accepted by the STT file-upload input */
export const ACCEPTED_AUDIO_TYPES = "audio/wav,audio/mpeg,audio/ogg,audio/webm,audio/mp4";

/** localStorage key used to remember that the user has seen the onboarding tour */
export const TOUR_SEEN_KEY = "sarvam_tour_seen";

/** Voice metadata for TTS speaker cards */
export const VOICE_META: Record<TTSSpeaker, { gradient: string; shadow: string; gender: string; tags: string }> = {
  priya: {
    gradient: "linear-gradient(135deg, #C084FC, #A855F7)",
    shadow:   "0 4px 14px rgba(168,85,247,0.40)",
    gender:   "Female",
    tags:     "Conversational · Warm",
  },
  shubh: {
    gradient: "linear-gradient(135deg, #60A5FA, #3B82F6)",
    shadow:   "0 4px 14px rgba(59,130,246,0.40)",
    gender:   "Male",
    tags:     "Conversational · Friendly",
  },
};

/** Sample romanised phrases for each language (Transliterate panel) */
export const TRANSLITERATE_SAMPLES: Partial<Record<LanguageCode, string>> = {
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
