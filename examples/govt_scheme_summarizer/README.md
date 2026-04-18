# Government scheme summarizer
The Government Scheme Summarizer is a web-based application that helps Indian citizens understand complex Indian government welfare schemes. Users can enter the name or description of a scheme and receive a summarized explanation in bullet points along with reliable official links. The summary can then be translated into 10 Indian languages using Sarvam's Translation API.

## Features

Optional category selection for scheme types

Uses Sarvam’s Chat Completion API to generate scheme summaries

Translates the summary into 10 Indian languages using Sarvam's Translarte API

Works with both scheme names and scheme descriptions

Uses secure API key-based authentication

## Getting Started

### Prerequisites

- Python 3.7 or higher
- A Sarvam AI API key

### Getting Your API Key

1. Visit [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2. Sign up for a new account
3. Get 1,000 free credits upon signup
4. Navigate to the API Keys section to generate your key

### Installation

1. Clone this repository:

```bash
git clone https://github.com/sarvamai/sarvam-ai-cookbook/govt_scheme_summarizer.git
cd govt_scheme_summarizer
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```
## Usage

Run the govt_scheme_summarizer  with your Sarvam API key:

```bash
python govt_scheme_summarizer.py
SARVAM_API_KEY= your_sarvam_api_key
```
## Example 

```python
scheme_name = "Pradhan Mantri Jan Dhan Yojana"
category = "Banking, Financial Services & Insurance (BFSI)"

summary = summarize_scheme(scheme_name, api_key)
print(summary)

translated = translate_summary(summary, "hi-IN", api_key)
print(translated)
```

## Additional Resources

- **Documentation**: [docs.sarvam.ai](https://docs.sarvam.ai/)
- **Community**: [Join the Discord Community](https://discord.gg/hTuVuPNF)
- **API Dashboard**: [dashboard.sarvam.ai](https://dashboard.sarvam.ai/)