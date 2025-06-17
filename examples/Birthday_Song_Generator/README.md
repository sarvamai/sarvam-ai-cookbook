# 🎂 Birthday Song Generator (FastAPI + SarvamAI)

A quirky, fun project where you can generate a **custom birthday song** for your friend — a little roasting, totally rhyming, and full of heart ❤️🎶

Built with:
- 🧠 [SarvamAI](https://sarvam.ai/) (Indian LLMs FTW 🇮🇳)
- ⚡ FastAPI for backend
- 🌐 HTML + JS frontend
- 🎨 Styled for joy

---

## 🔍 What It Does

1. Asks you 10 fun questions about your friend (name, hobby, fav food, quirky habits, etc.)
2. Uses those answers to generate a **12-line personalized birthday song** using SarvamAI's `sarvam-m` model.
3. Displays the song in a colorful UI ready to sing, screenshot, or roast! 🥳

---

## 🛠️ How It Works

- FastAPI handles routing and API interaction.
- Frontend sends the 10 responses to the `/generate-song` POST endpoint.
- Backend crafts a prompt for SarvamAI and fetches the song.
- The result is rendered beautifully in your browser.

---

##  Demo Screenshots – Birthday Song Generator

### 🧾 User Input Form
![Input Form](./backend/screenshots/inputs.jpeg)

### 🎵 Generated Birthday Song Output
![Song Output](./backend/screenshots/output.jpeg)
