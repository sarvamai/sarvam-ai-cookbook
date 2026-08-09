# VendorVoice AI

VendorVoice is an intelligent, voice-driven local shop (Kirana) management system. It allows shop owners to record and manage daily ledger transactions using just their voice, completely hands-free.

Powered by the **Sarvam API** for speech-to-text, translation, and intent parsing, and backed by a robust **PostgreSQL** database, VendorVoice bridges the gap between traditional bookkeeping and modern AI technology.

## 🌟 Features
- **Voice-Ledger System:** Record transactions ("Raju ka 50 rupaye jama karlo") seamlessly via a microphone interface.
- **Multilingual Support:** Supports 11 Indian languages (Hindi, Bengali, Tamil, Telugu, Marathi, etc.) with real-time AI translation to English for consistent database storage.
- **Responsive Dashboard:** A premium, glassmorphism-inspired responsive UI that works flawlessly on mobile devices, tablets, and large desktop screens.
- **Advanced Filtering:** Instantly search through transaction histories by Name, Month, and Year.
- **Audio Feedback:** Provides voice confirmations (TTS) of the recorded transaction so the vendor doesn't have to look at the screen.

## 🏗️ Project Structure
The project is divided into a decoupled Frontend and Backend:

- **[Backend API](./backend/)**: Built with Python & FastAPI, integrating PostgreSQL and the Sarvam API.
- **[Frontend App](./frontend/)**: Built with Next.js, React, and Tailwind CSS for a highly responsive, app-like experience.

## 🚀 Quick Start

To run this project locally, you will need to start both the backend and frontend development servers.

1. **Setup Backend:** See the [Backend README](./backend/README.md) for database and environment setup.
2. **Setup Frontend:** See the [Frontend README](./frontend/README.md) for UI setup.

---
*Built as part of the Sarvam AI Cookbook.*
