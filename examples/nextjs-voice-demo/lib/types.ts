// ─── Language ────────────────────────────────────────────────────────────────

export type LanguageCode =
  | "hi-IN"  // Hindi
  | "ta-IN"  // Tamil
  | "te-IN"  // Telugu
  | "bn-IN"  // Bengali
  | "kn-IN"  // Kannada
  | "ml-IN"  // Malayalam
  | "mr-IN"  // Marathi
  | "gu-IN"  // Gujarati
  | "pa-IN"  // Punjabi
  | "en-IN"; // English (India)

export interface Language {
  code: LanguageCode;
  name: string;
  nativeName: string;
  flag: string;
}

// ─── Text-to-Speech (Bulbul) ─────────────────────────────────────────────────

export type TTSSpeaker = "priya" | "shubh";

export interface TTSRequest {
  text: string;
  language: LanguageCode;
  speaker: TTSSpeaker;
}

/** Returned by /api/tts */
export interface TTSApiResponse {
  audioBase64?: string;
  error?: string;
}

/** Shape returned by Sarvam TTS endpoint */
export interface SarvamTTSResponse {
  audios: string[]; // base64-encoded WAV chunks
  request_id?: string;
}

// ─── Speech-to-Text (Saarika) ─────────────────────────────────────────────────

/** Returned by /api/stt */
export interface STTApiResponse {
  transcript?: string;
  language_code?: string;
  error?: string;
}

/** Shape returned by Sarvam STT endpoint */
export interface SarvamSTTResponse {
  transcript: string;
  language_code?: string;
  request_id?: string;
}

// ─── Transliteration ─────────────────────────────────────────────────────────

export interface TransliterateRequest {
  text: string;
  sourceLanguage: LanguageCode;
  targetLanguage: LanguageCode;
}

/** Returned by /api/transliterate */
export interface TransliterateApiResponse {
  transliterated_text?: string;
  error?: string;
}

/** Shape returned by Sarvam Transliterate endpoint */
export interface SarvamTransliterateResponse {
  transliterated_text: string;
  request_id?: string;
}

// ─── Onboarding Tour ─────────────────────────────────────────────────────────

export interface TourStep {
  /** id of the DOM element to spotlight */
  targetId:    string;
  title:       string;
  description: string;
  /** Tab that must be active before this step is measured */
  tab?:        string;
}
