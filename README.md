# Sarvam AI Cookbook

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Example code, guides, and end-to-end projects for building with the [Sarvam AI API](https://docs.sarvam.ai): chat completions, speech to text, text to speech, translation, transliteration, language identification, and document intelligence, all with first-class support for Indian languages.

## Contents

- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [API tutorials](#api-tutorials)
- [Example projects](#example-projects)
- [Integrations](#integrations)
- [Contributing](#contributing)
- [Resources](#resources)
- [License](#license)

## Getting started

You will need a Sarvam API key. Sign up for a free account at [dashboard.sarvam.ai](https://dashboard.sarvam.ai/) to get one.

Set it as an environment variable:

```bash
export SARVAM_API_KEY=<your API key>
```

Or create a `.env` file in your project root:

```plaintext
SARVAM_API_KEY=<your API key>
```

Most notebooks and scripts are written in Python 3.9+, but the underlying API calls translate directly to any language with an HTTP client or the [Sarvam AI SDKs](https://docs.sarvam.ai).

## Repository layout

| Folder | Contents |
|---|---|
| [`getting-started/`](getting-started/) | Focused, single-API tutorial notebooks: chat, speech to text, text to speech, translation, transliteration, language identification, document intelligence |
| [`examples/`](examples/) | Complete example projects and apps built on top of the Sarvam AI API |
| [`integrations/`](integrations/) | Guides for using Sarvam AI with third-party frameworks and platforms |
| [`scripts/`](scripts/) | CI validation tooling and the Sarvam model allowlist (`sarvam_api_rules.json`) |
| [`tests/`](tests/) | Unit tests for the validation scripts |

## API tutorials

| Capability | Notebook | Covers |
|---|---|---|
| Chat completions | [Chat_Completion.ipynb](<getting-started/chat completion/Chat_Completion.ipynb>) | Sending messages, tuning temperature and reasoning effort, multi-turn conversations, wiki grounding |
| Speech to text | [STT_API_Tutorial.ipynb](getting-started/stt/STT_API_Tutorial.ipynb) | Transcribing short and long audio with the Saaras model |
| Speech to text, batch | [stt-batch-api/](getting-started/stt/stt-batch-api/) | Transcribing audio files at scale with synchronous and asynchronous jobs |
| Speech to text translation | [STT_Translate_API_Tutorial.ipynb](getting-started/stt-translate/STT_Translate_API_Tutorial.ipynb) | Translating spoken audio directly into English text |
| Speech to text translation, batch | [stt-translate-batch-api/](getting-started/stt-translate/stt-translate-batch-api/) | Translating audio files at scale |
| Text to speech | [TTS_Tutorial.ipynb](getting-started/tts/TTS_Tutorial.ipynb) | Converting text into natural-sounding speech |
| Translation | [translate/](getting-started/translate/) | Translating text with Mayura and Sarvam-Translate, including streaming |
| Transliteration | [Transliterate_API_Tutorial.ipynb](getting-started/transliterate/Transliterate_API_Tutorial.ipynb) | Converting text between scripts while preserving pronunciation |
| Language identification | [Language_Identification.ipynb](<getting-started/language identification/Language_Identification.ipynb>) | Detecting the language and script of input text |
| Document intelligence | [Document_Intelligence.ipynb](getting-started/doc-intelligence/Document_Intelligence.ipynb) | Extracting structured data from documents with Sarvam Vision |

## Example projects

| Project | Description |
|---|---|
| [AI Presentation Architect](examples/AI_Presentation_Architect/) | Generates multilingual PowerPoint presentations, with narrated audio, from a single topic |
| [AI Graph Generator](examples/ai-graph-generator/) | Turns natural language prompts into charts, rendered in the requested Indian language |
| [Birthday Song Generator](examples/Birthday_Song_Generator/) | FastAPI app that writes and narrates a custom birthday song |
| [WAV to MP3 Converter](examples/converting_wav_into_mp3/) | Converts `.wav` audio files to `.mp3` |
| [Government Scheme Summarizer](examples/govt_scheme_summarizer/) | Summarizes Indian government welfare schemes and translates the summary into 10 languages |
| [Indic Soundbox AI](<examples/Indic Soundbox AI/>) | Voice agent for merchant soundboxes that reports sales insights in the merchant's language |
| [Live Video Transcription](examples/Live_Video_Transcription/) | Real-time transcription and translation of video audio over WebSocket |
| [Multilingual Chatbot](examples/Multilingual_Chatbot/) | Chatbot with context preservation and translation fallback across English and Indian languages |
| [Multilingual Feedback Analyzer](examples/Multilingual_Customer_Feedback_Analyzer/) | Detects language, translates, and analyzes sentiment in customer feedback |
| [QuickStart Chatbot](examples/QuickStart_Chatbot/) | Minimal single-turn chatbot built on the Chat Completions API |
| [Realtime Speech Captioning](examples/Realtime_Speech_Captioning/) | Live captions from streaming speech to text over WebSocket |
| [Regional Code Helper](examples/Regional_Code_Helper/) | Coding assistant that explains and debugs code in Indian languages |
| [Regional Doubt Solver](examples/Regional_Doubt_Solver/) | Homework helper with automatic language detection and age-appropriate explanations |
| [Sarvam Podcast Generator](examples/sarvam-podcast-generator/) | Next.js app that turns uploaded PDFs into narrated podcasts |
| [Song Lyrics Generator](examples/stt/) | Transcribes song audio into lyrics with the Speech to Text API |
| [Subtitles Generator](examples/stt-translate/) | Detects speech segments with voice activity detection and produces an SRT subtitle file |
| [Travel Planner](examples/Travel_Planner/) | Builds personalized, multilingual travel itineraries |
| [Book Summary Narrator](examples/tts/) | Narrates book summaries with the Text to Speech API |

## Integrations

| Integration | Description |
|---|---|
| [LiveKit](integrations/build_voice_agent_with_livekit.ipynb) | Real-time multilingual voice agent over WebRTC |
| [Pipecat](integrations/build_voice_agent_with_pipecat.ipynb) | Voice agent pipeline with Daily or browser WebRTC transport |
| [Twilio](integrations/build_voice_agent_with_twilio.ipynb) | Phone voice agent over Twilio Media Streams |
| [Exotel](integrations/build_voice_agent_with_exotel.ipynb) | Phone voice agent over Exotel Voice Streaming |
| [n8n](integrations/n8n_workflow_automation.ipynb) | No-code workflows for speech to text, text to speech, and chat completions |
| [Vercel AI SDK](integrations/vercel_ai_sdk_integration.ipynb) | Using Sarvam models through the Vercel AI SDK's standard functions |
| [OpenLIT](integrations/openlit_monitoring.ipynb) | OpenTelemetry-native monitoring for Sarvam AI API calls |

## Contributing

We welcome new examples and fixes. Before opening a pull request:

1. Read [CONTRIBUTING.MD](CONTRIBUTING.MD) for security requirements and API standards.
2. Copy [`examples/TEMPLATE/`](examples/TEMPLATE/) as the starting point for new notebook recipes.
3. Run local validation with `make check`.

CI checks every pull request for secret leaks and structure compliance for new notebook recipes. Current models are tracked in [`scripts/sarvam_api_rules.json`](scripts/sarvam_api_rules.json) and refreshed weekly from [docs.sarvam.ai](https://docs.sarvam.ai).

## Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai)
- [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
- [Sarvam AI Discord](https://discord.com/invite/8ka56wQaT3)
- [Sarvam AI on GitHub](https://github.com/sarvamai/)
- [Sarvam AI on Hugging Face](https://huggingface.co/sarvamai)

## License

This repository is licensed under the [Apache License 2.0](LICENSE).
