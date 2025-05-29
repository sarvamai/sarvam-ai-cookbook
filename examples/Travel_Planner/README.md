# AI Travel Assistant

A multilingual travel planning application that helps users create personalized travel itineraries in their preferred Indian language. Built with Streamlit and powered by Sarvam AI's language processing capabilities.

## Features

- Multilingual support for 10 Indian languages
- Personalized travel itineraries
- Cultural insights and travel tips
- Language detection and translation
- Script transliteration
- User-friendly interface

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory and add your Sarvam API key:
   ```
   SARVAM_API_KEY=your_api_key_here
   ```
4. Run the application:
   ```bash
   streamlit run app.py
   ```

## Usage

1. Select your preferred language from the sidebar
2. Enter your travel destination
3. Specify travel dates and duration
4. Select your interests and budget
5. Click "Plan My Trip!" to generate your personalized itinerary

## Supported Languages

- English (en)
- Hindi (hi)
- Bengali (bn)
- Tamil (ta)
- Telugu (te)
- Marathi (mr)
- Gujarati (gu)
- Kannada (kn)
- Malayalam (ml)
- Punjabi (pa)

## Requirements

- Python 3.8+
- Streamlit
- Requests
- Python-dotenv
- Pandas

## License

MIT License 