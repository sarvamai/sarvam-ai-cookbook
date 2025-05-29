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
    """Detect the language of the input text."""
    headers = {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"{BASE_URL}/detect-language",
        headers=headers,
        json={"text": text}
    )
    return response.json()

def translate_text(text, target_language, mode="formal"):
    """Translate text to target language using Sarvam's translation API."""
    headers = {
        "api-subscription-key": SARVAM_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Convert language code to Sarvam format
    target_lang_code = LANGUAGE_CODES.get(target_language, 'en-IN')
    
    response = requests.post(
        "https://api.sarvam.ai/translate",
        headers=headers,
        json={
            "input": text,
            "source_language_code": "auto",
            "target_language_code": target_lang_code,
            "mode": mode,
            "enable_preprocessing": True,
            "output_script": "fully-native",
            "numerals_format": "international"
        }
    )
    return response.json()

def transliterate_text(text, target_script):
    """Transliterate text to target script."""
    headers = {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        f"{BASE_URL}/transliterate",
        headers=headers,
        json={
            "text": text,
            "target_script": target_script
        }
    )
    return response.json()

def generate_itinerary(destination, duration, interests, budget, language="en"):
    """Generate a personalized travel itinerary using Sarvam's Chat Completions API."""
    headers = {
        "Authorization": f"Bearer {SARVAM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = f"""You are an expert travel planner specializing in {destination}. Please only generate the itinerary in {language}. Don't use any other language. Especially skip english.
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
            "model": "sarvam-m",
            "temperature": 0.7,
            "max_tokens": 5000
        }
    )
    
    return response.json() 