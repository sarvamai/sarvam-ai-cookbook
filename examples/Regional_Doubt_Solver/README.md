# Homework Helper

A command-line tool that helps students get detailed explanations for their homework questions in their preferred language. The tool automatically detects the language of the question and provides age-appropriate explanations with practice questions.

## Features

- Automatic language detection
- Age-appropriate explanations
- Step-by-step solutions
- Practice questions included
- Support for multiple Indian languages

## Installation

1. Clone this repository
2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

You can use the tool in two ways:

1. Using command-line arguments:
```bash
python homework_helper.py "Explain the water cycle" --grade 5 --api-key YOUR_API_KEY
```

2. Using environment variable for API key:
```bash
export SARVAM_API_KEY=your_api_key
python homework_helper.py "Explain the water cycle" --grade 5
```

### Arguments

- `question`: The homework question or topic to explain (required)
- `--grade`: Student's grade level (default: 5)
- `--api-key`: Sarvam API key (optional if set via SARVAM_API_KEY environment variable)

## Examples

1. English question:
```bash
python homework_helper.py "Explain photosynthesis" --grade 7
```

2. Hindi question:
```bash
python homework_helper.py "जल चक्र क्या है?" --grade 6
```

3. Tamil question:
```bash
python homework_helper.py "நீர் சுழற்சி என்றால் என்ன?" --grade 8
```

## Supported Languages

The tool supports multiple Indian languages including:
- English (en-IN)
- Hindi (hi-IN)
- Bengali (bn-IN)
- Gujarati (gu-IN)
- Kannada (kn-IN)
- Malayalam (ml-IN)
- Marathi (mr-IN)
- Odia (od-IN)
- Punjabi (pa-IN)
- Tamil (ta-IN)
- Telugu (te-IN)

## Note

Make sure you have a valid Sarvam API key to use this tool. You can get one by signing up at [Sarvam AI](https://sarvam.ai). 