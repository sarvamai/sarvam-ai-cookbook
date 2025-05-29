# Multilingual Feedback Analyzer

This tool analyzes customer feedback in various Indian languages using the Sarvam AI API. It performs the following operations:

1. Detects the language of each feedback
2. Translates the feedback to English
3. Analyzes the sentiment and key points
4. Generates a comprehensive report

## Features

- 🌐 Supports multiple Indian languages
- 🔄 Automatic language detection
- 📝 English translation of feedback
- 🎯 Sentiment analysis
- 📊 Key points extraction
- 📈 Comprehensive analysis reports

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
git clone https://github.com/yourusername/feedback-analyzer.git
cd feedback-analyzer
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Get your Sarvam AI API key from the [Sarvam AI Dashboard](https://docs.sarvam.ai)

## Usage

Run the script with your API key:

```bash
python feedback_analyzer.py --api-key YOUR_API_KEY
```

### Optional Arguments

- `--input-file`: Path to the input CSV file (default: dummy.csv)
- `--output-file`: Path to save the analysis results (default: feedback_analysis.csv)

Example:

```bash
python feedback_analyzer.py --api-key YOUR_API_KEY --input-file customer_feedback.csv --output-file analysis_results.csv
```

## Input Format

The input CSV file should have a column named 'feedback' containing the customer feedback text. Example:

```csv
feedback
"मैं आपके उत्पाद से बहुत खुश हूं। सेवा बहुत अच्छी है।"
"Your service is excellent but the pricing needs improvement."
```

## Output Format

The script generates a CSV file with the following columns:

- original_feedback: The original feedback text
- detected_language: The detected language code
- translated_feedback: English translation of the feedback
- sentiment: Overall sentiment (positive/negative/neutral)
- main_topic: Main topic of the feedback
- key_points: Key points extracted from the feedback

Additionally, a summary of the analysis is printed to the console, including:

- Total number of feedback analyzed
- Language distribution
- Sentiment distribution
- Top main topics

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
