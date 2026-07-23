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
2. Uses those answers to generate a **12-line personalized birthday song** using SarvamAI's `sarvam-105b` model.
3. Displays the song in a colorful UI ready to sing, screenshot, or roast! 🥳

---

## 🛠️ How It Works

- FastAPI handles routing and API interaction.
- Frontend sends the 10 responses to the `/generate-song` POST endpoint.
- Backend crafts a prompt for SarvamAI and fetches the song.
- The result is rendered beautifully in your browser.

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.8+
- A Sarvam AI API Key (get one from [Sarvam AI Dashboard](https://dashboard.sarvam.ai/))

### Installation Steps

```bash
# Clone the repository
git clone https://github.com/sarvamai/sarvam-ai-cookbook.git
cd sarvam-ai-cookbook/examples/Birthday_Song_Generator

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "SARVAM_API_KEY=your_api_key_here" > .env
```

### Running the Application

```bash
# Start the FastAPI server
python backend/app.py

# Open your browser and navigate to:
# http://localhost:8000
```

---

## 📝 API Endpoints

### `POST /generate-song`

Generates a personalized birthday song.

**Request Body:**
```json
{
  "friend_name": "Alice",
  "hobby": "coding",
  "favorite_food": "pizza",
  "quirky_habit": "talks to plants",
  "best_quality": "kind-hearted",
  "funny_story": "once forgot their birthday",
  "inside_joke": "always late",
  "dream_job": "astronaut",
  "favorite_movie": "Inception",
  "gift_idea": "a telescope"
}
```

**Response:**
```json
{
  "song": "🎵 Alice, Alice, coding queen...",
  "model": "sarvam-105b",
  "timestamp": "2024-07-23T10:30:00Z"
}
```

---

## 📸 Demo Screenshots

### 🧾 User Input Form
![Input Form](./backend/screenshots/inputs.jpeg)

### 🎵 Generated Birthday Song Output
![Song Output](./backend/screenshots/output.jpeg)

---

## 🔐 Security

- Never commit your `.env` file. Add it to `.gitignore`.
- Always load the API key from environment variables, not hardcoded.
- Validate all user inputs before sending to the API.

---

## 🐛 Troubleshooting

### Issue: "API key not found"

**Solution**: Ensure your `.env` file exists and contains:
```bash
SARVAM_API_KEY=your_actual_api_key_here
```

### Issue: "Connection refused"

**Solution**: Make sure FastAPI server is running:
```bash
python backend/app.py
```

### Issue: "Invalid response from API"

**Solution**: Check that you're using the current model `sarvam-105b`. See [TROUBLESHOOTING.md](../../TROUBLESHOOTING.md#2-high-pr-101--stt-model-migration) for model migration guidance.

---

## 📚 Resources

- [Sarvam AI Documentation](https://docs.sarvam.ai)
- [Sarvam AI Chat API Reference](https://docs.sarvam.ai/api-reference-docs/chat-completions)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Troubleshooting Guide](../../TROUBLESHOOTING.md)

---

## 🤝 Contributing

Found a bug? Want to improve the song generator? Check out [CONTRIBUTING.md](../../CONTRIBUTING.MD) for guidelines.

---

## 📄 License

Apache License 2.0 - See [LICENSE](../../LICENSE) for details.
