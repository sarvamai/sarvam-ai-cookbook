import requests
import os
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

def speech_to_text(audio_blob):
    """
    Sends audio data to Sarvam ASR API and returns the transcript.
    """
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY not found in environment variables.")

    files = {'file': ('input.wav', audio_blob, 'audio/wav')}
    data = {
        'model': 'saarika:v2',
        'language_code': 'unknown'
    }
    headers = {'api-subscription-key': SARVAM_API_KEY}

    response = requests.post('https://api.sarvam.ai/speech-to-text', files=files, data=data, headers=headers)

    if not response.ok:
        raise Exception(f"ASR API request failed with status {response.status_code}: {response.text}")

    return response.json().get("transcript") 