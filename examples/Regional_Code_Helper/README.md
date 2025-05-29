# AI Coding Assistant for Indian Students

A powerful AI-powered coding assistant designed to support students in regional colleges and schools across India. Built using Sarvam AI's advanced language models, it provides comprehensive programming help in multiple Indian languages and English.

## Features

- 📚 Explain programming concepts in simple, clear language
- 🐛 Debug code snippets with detailed explanations
- 💻 Provide code samples with step-by-step explanations
- 🌐 Support for multiple Indian languages
- 🎯 Interactive web interface with real-time responses
- 🔄 Context-aware assistance

## Getting Started

### Prerequisites

- Python 3.7 or higher
- A Sarvam AI API key
- Internet connection

### Getting Your API Key

1. Visit [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for a new account
3. Get 1,000 free credits upon signup
4. Navigate to the API Keys section to generate your key

## Installation

1. Clone this repository:

```bash
git clone https://github.com/sarvamai/sarvam-ai-cookbook/regional-code-helper.git
cd regional-code-helper
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your Sarvam API key:

```bash
SARVAM_API_KEY=your_api_key_here
```

## Running the Application

1. Start the Streamlit application:
   ```bash
   streamlit run coding_assistant.py
   ```
2. Open your web browser and navigate to the URL shown in the terminal (usually http://localhost:8501)

## Usage

1. Select your preferred language from the dropdown menu
2. Choose the feature you want to use:
   - Explain a Concept: Get explanations of programming concepts
   - Debug Code: Get help with debugging your code
   - Get Code Sample: Request code samples for specific topics

## Supported Languages

- English (en)
- Hindi (hi)
- Tamil (ta)
- Telugu (te)
- Bengali (bn)
- Kannada (kn)

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
