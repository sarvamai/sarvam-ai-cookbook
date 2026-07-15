# Sarvam AI Podcast Generator

A powerful AI-driven document analysis and podcast generation tool built with Next.js 15 and Sarvam AI APIs. Upload PDF documents and generate AI-powered podcasts in multiple Indian languages with advanced background processing and real-time status tracking.

## ✨ Features

- 📄 **Advanced PDF Parsing**: Document parsing using Sarvam Document Intelligence (Sarvam Vision)
- 🤖 **AI Script Generation**: Intelligent podcast script generation using Sarvam 105B
- 🌐 **Multi-Language Support**: Support for 11 Indian languages including Hindi, Tamil, Telugu, Bengali, and more
- 🎙️ **High-Quality TTS**: AI-powered text-to-speech using Sarvam Bulbul v3 TTS API
- ⚡ **Background Processing**: Reliable background job processing with Inngest
- 📊 **Real-time Status Tracking**: Live updates on podcast generation progress
- 🎧 **Interactive Audio Player**: Built-in audio player with transcript display and segment navigation
- 📱 **Modern Responsive UI**: Built with Next.js 15, React 19, and Tailwind CSS 4
- 💾 **Smart File Management**: Automatic audio file storage and cleanup with UploadThing
- ⬇️ **Download Support**: Download generated audio files for offline listening
- 🔄 **Automatic Cleanup**: Scheduled cleanup of temporary audio files

## Demo Video
https://github.com/user-attachments/assets/71574674-85bf-4b59-a40c-f2f48980b751

## 🛠️ Tech Stack

### Frontend
- **Framework**: Next.js 15 with App Router
- **UI Library**: React 19, TypeScript
- **Styling**: Tailwind CSS v4, Shadcn UI Components
- **Icons**: Lucide React, React Icons

### Backend & Processing
- **Background Jobs**: Inngest for reliable async processing
- **Job Tracking**: In-memory job store (see note below); swap in Redis for production
- **File Storage**: UploadThing for audio file management (currently stubbed to in-memory data URLs — see note below)
- **APIs**: 
  - Sarvam 105B (Script Generation)
  - Sarvam Bulbul v3 TTS (Text-to-Speech)
  - Sarvam Document Intelligence / Sarvam Vision (PDF Parsing)

### File Handling
- **Upload**: React Dropzone
- **Processing**: Multi-step background processing pipeline
- **Storage**: Temporary audio file management with automatic cleanup

## 🚀 Quick Start

### Prerequisites

- Node.js 18+ installed
- Sarvam AI API key ([get one here](https://www.sarvam.ai/))
- Inngest account ([get one here](https://inngest.com/))
- Redis instance and UploadThing account — optional for local dev (see note below); required for a real deployment

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd sarvam-notebooklm-clone
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   # Sarvam AI API Configuration
   SARVAM_API_KEY=your_sarvam_api_key_here
   
   # Redis Configuration (for job tracking) — optional locally, see note below
   REDIS_URL=your_redis_url
   
   # UploadThing Configuration (for file storage) — optional locally, see note below
   UPLOADTHING_TOKEN=your_uploadthing_token

   # Inngest Configuration (required in production)
   INNGEST_SIGNING_KEY=your_inngest_signing_key
   ```

   > **Note:** As shipped, `lib/job-store.ts` always uses an in-memory job map (no Redis client wired up yet) and `lib/upload-audio.ts`/`lib/uploadthing.ts` always store audio as in-memory base64 data URLs regardless of `REDIS_URL`/`UPLOADTHING_TOKEN`. This is fine for local single-process development but won't survive a server restart or work across multiple serverless instances — wire up real Redis and UploadThing clients before deploying.
   >
   > This stub also has a side effect during generation: each TTS segment's "URL" is actually its full base64 audio data (several hundred KB), and Inngest persists that as the step's return value. This occasionally trips Inngest's per-step output size limit (`output_too_large` in the `inngest dev` logs) — verified during testing, where a 22-segment Hindi podcast hit it 4 times but recovered via automatic retry with no data loss, just extra latency. Wiring up a real UploadThing token resolves this, since steps would then store a short real URL instead of the raw audio data.

4. **Run the development servers**
   
   Start the Next.js development server:
   ```bash
   npm run dev
   ```
   
   In a separate terminal, start the Inngest development server:
   ```bash
   npm run inngest
   ```

5. **Open your browser**
   Navigate to [http://localhost:3000](http://localhost:3000)

## 📖 How to Use

1. **Select Language**: Choose your preferred language for the podcast from the dropdown selector
2. **Upload PDF**: Drag and drop or click to upload a PDF document
3. **Background Processing**: The app will automatically:
   - Parse the PDF content using Sarvam Document Intelligence
   - Generate a conversational script using Sarvam 105B
   - Generate high-quality audio using Sarvam Bulbul v3 TTS API
   - Process everything in the background using Inngest
4. **Real-time Updates**: Monitor the progress with live status updates
5. **Listen & Interact**: Use the built-in audio player with features like:
   - Play/pause controls
   - Segment navigation
   - Transcript view toggle
   - Speed controls
6. **Download**: Download the complete audio file for offline listening

## 🌍 Supported Languages

- 🇮🇳 Hindi (हिंदी) - `hi-IN`
- 🇮🇳 English (India) - `en-IN`
- 🇮🇳 Tamil (தமிழ்) - `ta-IN`
- 🇮🇳 Telugu (తెలుగు) - `te-IN`
- 🇮🇳 Bengali (বাংলা) - `bn-IN`
- 🇮🇳 Gujarati (ગુજરાતી) - `gu-IN`
- 🇮🇳 Marathi (मराठी) - `mr-IN`
- 🇮🇳 Malayalam (മലയാളം) - `ml-IN`
- 🇮🇳 Kannada (ಕನ್ನಡ) - `kn-IN`
- 🇮🇳 Punjabi (ਪੰਜਾਬੀ) - `pa-IN`
- 🇮🇳 Odia (ଓଡ଼ିଆ) - `od-IN`

## 🔌 API Endpoints

### `POST /api/parse-pdf`
Parses PDF documents using Sarvam Document Intelligence.

**Request**: FormData with PDF file
**Response**: Extracted text content, images, and metadata

### `POST /api/generate-podcast`
Initiates podcast generation process and returns job ID.

**Request**: JSON with content, language, and title
**Response**: Job ID for tracking progress

### `GET /api/job-status/[jobId]`
Gets the current status of a podcast generation job.

**Response**: Job status, progress, and result when completed

### `POST /api/cleanup-audio`
Handles cleanup of temporary audio files.

**Request**: Cleanup configuration
**Response**: Cleanup status

### Background Processing Routes
- `/api/inngest` - Inngest webhook endpoint for background jobs
- `/api/uploadthing` - UploadThing file upload endpoint

## 🏗️ Architecture

```
├── app/
│   ├── api/
│   │   ├── parse-pdf/route.ts           # PDF parsing with Sarvam Document Intelligence
│   │   ├── generate-podcast/route.ts    # Podcast generation initiation
│   │   ├── job-status/[jobId]/route.ts  # Job status tracking
│   │   ├── cleanup-audio/route.ts       # Audio file cleanup
│   │   ├── inngest/route.ts             # Inngest webhook handler
│   │   └── uploadthing/route.ts         # File upload handling
│   ├── globals.css                      # Global styles
│   ├── layout.tsx                       # Root layout
│   └── page.tsx                         # Main application page
├── components/
│   ├── FileUpload.tsx                   # PDF upload component
│   ├── LanguageSelector.tsx             # Language selection
│   ├── PodcastControls.tsx              # Audio player and controls
│   ├── PodcastGenerator.tsx             # Main application component
│   ├── ProcessingStatus.tsx             # Status tracking display
│   └── ui/                              # Shadcn UI components
├── inngest/
│   ├── podcast-generation.ts            # Background podcast processing
│   └── audio-cleanup.ts                 # Automatic file cleanup
├── lib/
│   ├── inngest.ts                       # Inngest client configuration
│   ├── job-store.ts                     # In-memory job store (swap for Redis in production)
│   ├── uploadthing.ts                   # UploadThing configuration
│   ├── upload-audio.ts                  # Audio file upload utilities
│   ├── cleanup-audio-files.ts           # File cleanup utilities
│   ├── poll-job-status.ts               # Client-side job polling
│   └── utils.ts                         # General utilities
└── public/                              # Static assets
```

## 🔧 Development

### Running in Development Mode

1. **Start the main application**:
   ```bash
   npm run dev
   ```

2. **Start Inngest development server** (in separate terminal):
   ```bash
   npm run inngest
   ```

3. **Access the application**:
   - Main app: http://localhost:3000
   - Inngest dashboard: http://localhost:8288

### Key Development Features

- **Hot Reload**: Both Next.js and Inngest support hot reloading
- **Background Job Testing**: Use Inngest dashboard to monitor and debug jobs
- **File Upload Testing**: UploadThing provides development URLs (once wired up to a real client)

## ⚠️ Important Notes

**PDF Size Limitations**: For optimal performance, please upload PDFs with moderate content length. Very large PDFs or documents with extensive text may cause podcast generation to fail due to the context length limitations of the Sarvam 105B model. The system automatically chunks large content but very extensive documents may still face limitations.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Links

- [Sarvam AI Documentation](https://docs.sarvam.ai/)
- [Inngest Documentation](https://www.inngest.com/docs)
- [UploadThing Documentation](https://docs.uploadthing.com/)
- [Next.js Documentation](https://nextjs.org/docs)

---

Built with ❤️ using Sarvam AI's powerful multilingual models



