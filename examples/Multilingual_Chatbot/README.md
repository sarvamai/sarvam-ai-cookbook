# Multilingual Chatbot

A powerful chatbot that supports both English and regional languages, with context preservation and translation fallback capabilities. Built using Sarvam AI's advanced language models.

## Features

- 🌐 Supports both English and regional language conversations
- 🔄 Preserves conversation context across 5 turns
- 🎯 Automatic language detection
- 🔄 Translation fallback for unsupported queries
- 📝 JSON response format with language information

## Getting Started

### Prerequisites

- Python 3.7 or higher
- A Sarvam AI API key

### Getting Your API Key

1. Visit [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for a new account
3. Get 1,000 free credits upon signup
4. Navigate to the API Keys section to generate your key

## Installation

1. Clone this repository:

```bash
git clone https://github.com/yourusername/multilingual-chatbot.git
cd multilingual-chatbot
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

Run the chatbot with your Sarvam API key:

```bash
python chatbot.py --api-key YOUR_API_KEY
```

### Example Usage

1. Start the chatbot
2. Type your message in either English or regional language
3. The bot will respond in the same language
4. Type 'quit' to exit the conversation

### Response Format

The chatbot returns responses in the following JSON format:

```json
{
    "response": "The bot's response text",
    "language": "english" or "regional"
}
```

## Notes

- The chatbot automatically detects the language of your input
- Conversation context is preserved for the last 5 turns
- If the API call fails, the chatbot will fall back to a translated error message
- Free tier includes 1,000 credits per month
- Credits are consumed based on the length of conversations

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
