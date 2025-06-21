import requests
import os
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

def identify_language(text):
    """
    Sends text to Sarvam LID API and returns the language and script codes.
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not found in environment variables.")

    headers = {
        'api-subscription-key': SARVAM_API_KEY,
        'Content-Type': 'application/json'
    }
    payload = {'input': text}

    response = requests.post('https://api.sarvam.ai/text-lid', json=payload, headers=headers)

    if not response.ok:
        raise Exception(f"LID API request failed with status {response.status_code}: {response.text}")

    return response.json() 