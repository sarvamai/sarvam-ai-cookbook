import os
import requests
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv('SARVAM_API_KEY')
BASE_URL = "https://api.sarvam.ai/v1"

# Language code mapping
LANGUAGE_CODES = {
    'en': 'en-IN',
    'hi': 'hi-IN',
    'bn': 'bn-IN',
    'ta': 'ta-IN',
    'te': 'te-IN',
    'mr': 'mr-IN',
    'gu': 'gu-IN',
    'kn': 'kn-IN',
    'ml': 'ml-IN',
    'pa': 'pa-IN'
}

def detect_language(text):
    """Detect the language of the input text using Sarvam's Text LID API."""
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.post(
        "https://api.sarvam.ai/text-lid",
        headers=headers,
        json={"input": text}
    )
    return response.json()

def _chunk_text(text, max_length=900):
    """Split text into chunks under the translation API's per-request limit,
    breaking at paragraph/line boundaries where possible."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        # If a single line is itself too long, hard-split it.
        while len(line) > max_length:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:max_length])
            line = line[max_length:]
        if len(current) + len(line) > max_length:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks


def translate_text(text, target_language, mode="formal"):
    """Translate text to target language using Sarvam's translation API.

    Long inputs are chunked because mayura:v1 accepts a limited number of
    characters per request; chunks are translated separately and rejoined.
    """
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }

    # Convert language code to Sarvam format
    target_lang_code = LANGUAGE_CODES.get(target_language, 'en-IN')

    translated_parts = []
    for chunk in _chunk_text(text):
        response = requests.post(
            "https://api.sarvam.ai/translate",
            headers=headers,
            json={
                "input": chunk,
                "source_language_code": "auto",
                "target_language_code": target_lang_code,
                "model": "mayura:v1",
                "mode": mode,
                "output_script": "fully-native",
                "numerals_format": "international"
            }
        )
        data = response.json()
        # On any chunk failure, fall back to the original text for that chunk.
        translated_parts.append(data.get("translated_text", chunk))

    return {"translated_text": "".join(translated_parts)}

def transliterate_text(text, source_language_code, target_language_code):
    """Transliterate text from one Indic script to another using Sarvam's API."""
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    response = requests.post(
        "https://api.sarvam.ai/transliterate",
        headers=headers,
        json={
            "input": text,
            "source_language_code": source_language_code,
            "target_language_code": target_language_code
        }
    )
    return response.json()

def generate_itinerary(destination, duration, interests, budget, language="en"):
    """Generate a personalized travel itinerary using Sarvam's Chat Completions API."""
    headers = {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = f"""You are an expert travel planner specializing in {destination}. Generate the itinerary in {language}.
    Create a detailed {duration}-day itinerary that includes:
    - Daily activities with timing
    - Local attractions and hidden gems
    - Cultural experiences
    - Food recommendations
    - Transportation tips
    - Budget considerations ({budget} level)
    Focus on the following interests: {', '.join(interests)}
    Format the response in a clear, structured way with sections for each day. Keep each section short and concise. Don't blabber a lot"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please create a {duration}-day itinerary for {destination}."}
    ]
    
    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=headers,
        json={
            "messages": messages,
            "model": "sarvam-105b",
            "temperature": 0.7,
            "max_tokens": 4000
        }
    )
    
    return response.json() 