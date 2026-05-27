# Sarvam AI Voice Demo — Next.js

An interactive, production-ready Next.js 15 app that showcases Sarvam AI's three core voice APIs across 10 Indian languages. No external state-management library, no Inngest, no Redis — just Next.js App Router + Tailwind CSS v4. Perfect starting point for any web application that needs Indian-language voice features.

## ✨ Features

| Feature | Sarvam API | Model |
|---|---|---|
| 🔊 **Text → Speech** | `/text-to-speech` | Bulbul v3 |
| 🎙️ **Speech → Text** | `/speech-to-text` | Saarika v2 |
| 🔤 **Transliteration** | `/transliterate` | — |

- **10 Indian languages**: Hindi, Tamil, Telugu, Bengali, Kannada, Malayalam, Marathi, Gujarati, Punjabi, English (India)
- **Two TTS voices**: Priya (female) and Shubh (male)
- **Browser microphone recording** (+ audio file upload) for STT
- API key stays **server-side only** — all calls proxied through Next.js Route Handlers
- Clean, responsive UI with Tailwind CSS v4
- Full TypeScript — no `any` casts

## 📸 Screenshot

```
┌─────────────────────────────────────────────────┐
│  स  Sarvam AI           Voice API Demo          │
│  Interactive playground · 10 Indian languages   │
│                                                 │
│  [Text → Speech]  [Speech → Text]  [Transliterate]  │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────────────────────────────────────┐ │
│  │  Input text …                             │ │
│  │  Language ▾    Voice: [Priya] [Shubh]     │ │
│  │  [▶ Generate Speech]                      │ │
│  └───────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- **Node.js 18+**
- A **Sarvam AI API key** — get one at [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)

### Installation

1. **Navigate to this example**

   ```bash
   cd examples/nextjs-voice-demo
   ```

2. **Install dependencies**

   ```bash
   npm install
   ```

3. **Configure your API key**

   ```bash
   cp .env.example .env.local
   ```

   Then edit `.env.local` and add your key:

   ```env
   SARVAM_API_KEY=your_sarvam_api_key_here
   ```

4. **Run the development server**

   ```bash
   npm run dev
   ```

5. **Open** [http://localhost:3000](http://localhost:3000)

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript 5 (strict mode) |
| Styling | Tailwind CSS v4 |
| Icons | Lucide React |
| Runtime | Node.js 18+ |

## 📁 Project Structure

```
nextjs-voice-demo/
├── app/
│   ├── api/
│   │   ├── tts/route.ts          # Proxy → Sarvam /text-to-speech
│   │   ├── stt/route.ts          # Proxy → Sarvam /speech-to-text
│   │   └── transliterate/route.ts # Proxy → Sarvam /transliterate
│   ├── globals.css               # Tailwind v4 import + keyframes
│   ├── layout.tsx                # Root layout + metadata
│   └── page.tsx                  # Entry point
├── components/
│   ├── VoiceDemo.tsx             # Tab shell (TTS / STT / Transliterate)
│   ├── TTSPanel.tsx              # Text-to-Speech UI + playback
│   ├── STTPanel.tsx              # Record mic or upload file → transcript
│   ├── TransliteratePanel.tsx    # Roman input → native script
│   └── LanguageSelector.tsx     # Reusable language <select>
├── lib/
│   ├── types.ts                  # Shared TypeScript interfaces
│   └── constants.ts              # Languages, models, limits
├── .env.example                  # Environment variable template
└── README.md
```

## 🌍 Supported Languages

| Language | Code | Native |
|---|---|---|
| Hindi | `hi-IN` | हिंदी |
| English (India) | `en-IN` | English |
| Tamil | `ta-IN` | தமிழ் |
| Telugu | `te-IN` | తెలుగు |
| Bengali | `bn-IN` | বাংলা |
| Kannada | `kn-IN` | ಕನ್ನಡ |
| Malayalam | `ml-IN` | മലയാളം |
| Marathi | `mr-IN` | मराठी |
| Gujarati | `gu-IN` | ગુજરાતી |
| Punjabi | `pa-IN` | ਪੰਜਾਬੀ |

## 🔌 API Routes

All three Route Handlers act as a thin, secure proxy — your `SARVAM_API_KEY` never leaves the server.

### `POST /api/tts`

**Request body (JSON)**

```json
{
  "text": "नमस्ते, आप कैसे हैं?",
  "language": "hi-IN",
  "speaker": "priya"
}
```

| Field | Type | Notes |
|---|---|---|
| `text` | `string` | Max 500 characters |
| `language` | `LanguageCode` | One of the 10 supported codes |
| `speaker` | `"priya" \| "shubh"` | Female / Male voice |

**Response**

```json
{ "audioBase64": "<base64-encoded WAV>" }
```

---

### `POST /api/stt`

**Request**: `multipart/form-data`

| Field | Type | Notes |
|---|---|---|
| `file` | `File` | WAV, MP3, OGG, WebM, or M4A |
| `language_code` | `string` | e.g. `"hi-IN"` |

**Response**

```json
{ "transcript": "नमस्ते", "language_code": "hi-IN" }
```

---

### `POST /api/transliterate`

**Request body (JSON)**

```json
{
  "text": "namaste, aap kaise hain?",
  "sourceLanguage": "en-IN",
  "targetLanguage": "hi-IN"
}
```

**Response**

```json
{ "transliterated_text": "नमस्ते, आप कैसे हैं?" }
```

## 🔑 Sarvam API Reference

| API | Endpoint | Header |
|---|---|---|
| Text-to-Speech | `POST https://api.sarvam.ai/text-to-speech` | `api-subscription-key` |
| Speech-to-Text | `POST https://api.sarvam.ai/speech-to-text` | `api-subscription-key` |
| Transliterate | `POST https://api.sarvam.ai/transliterate` | `api-subscription-key` |

Full documentation: [docs.sarvam.ai](https://docs.sarvam.ai/api-reference-docs/introduction)

## ⚙️ Configuration

| Variable | Required | Description |
|---|---|---|
| `SARVAM_API_KEY` | ✅ | Your Sarvam AI subscription key |

Store it in `.env.local` for local development. For deployment (Vercel, etc.), add it as an environment variable in the platform dashboard.

## 📝 License

MIT — see the root [LICENSE](../../LICENSE) file.

---

Built with ❤️ using [Sarvam AI's voice APIs](https://docs.sarvam.ai/)
