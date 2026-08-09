import os
import requests
import json
import re
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

def sarvam_stt(audio_bytes: bytes) -> str:
    """1. Speech-to-Text: Converts vendor's voice to Hindi/regional text."""
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY is missing in .env file")
    
    files = {'file': ('input.wav', audio_bytes, 'audio/wav')}
    data = {'model': 'saarika:v2.5', 'language_code': 'unknown'}
    headers = {'api-subscription-key': SARVAM_API_KEY}
    
    response = requests.post('https://api.sarvam.ai/speech-to-text', files=files, data=data, headers=headers)
    if not response.ok:
        raise Exception(f"ASR failed: {response.text}")
    
    return response.json().get("transcript", "")

def extract_transaction_json(transcript: str) -> dict:
    """2. LLM Extraction: Parses the transcript into strict JSON data."""
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY is missing in .env file")
    
    system_prompt = '''You are an AI assistant for a local shop owner or merchant in India.
The vendor will speak a transaction in Hindi, English or a mixed regional language.
Extract the transaction details into a strict JSON format with exactly these keys:
- "customer_name" (string, TRANSLATE/TRANSLITERATE to English. If unknown use "Unknown")
- "amount" (number)
- "item_description" (string, TRANSLATE to English)
- "transaction_type" (string, must be strictly either "credit" or "settled")

IMPORTANT: Maintain language consistency by always translating or transliterating all text (names and items) into standard English. Do not use regional scripts in the output.

Examples:
Input: "Raju ko 50 rupaye ka aalu udhaar diya"
Output: {"customer_name": "Raju", "amount": 50, "item_description": "aalu", "transaction_type": "credit"}

Input: "Sharma ji ne 500 rupaye paint ke jama kar diye"
Output: {"customer_name": "Sharma ji", "amount": 500, "item_description": "paint", "transaction_type": "settled"}

Input: "Madam ki saree silayi ke 300 rupaye baki hain"
Output: {"customer_name": "Madam", "amount": 300, "item_description": "saree silayi", "transaction_type": "credit"}

Input: "Bhaiya ko do chai aur biscuit diya cash mein, 30 rupaye"
Output: {"customer_name": "Bhaiya", "amount": 30, "item_description": "chai aur biscuit", "transaction_type": "settled"}

Output ONLY the JSON object. Do not include any markdown formatting like ```json or anything else. Just the raw JSON.'''
    
    headers = {
        'Authorization': f"Bearer {SARVAM_API_KEY}",
        'Content-Type': 'application/json'
    }
    payload = {
        'model': 'sarvam-m',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': transcript}
        ],
        'stream': False
    }
    
    response = requests.post('https://api.sarvam.ai/v1/chat/completions', json=payload, headers=headers)
    if not response.ok:
        raise Exception(f"Chat API failed: {response.text}")
        
    content = response.json()['choices'][0]['message']['content']
    try:
        # Remove <think> chain-of-thought blocks if present
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        # Strip markdown if the LLM accidentally includes it
        content = content.replace('```json', '').replace('```', '').strip()
        
        # Extract just the JSON object
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group(0)
            
        return json.loads(content)
    except Exception as e:
        raise Exception(f"Failed to parse JSON from LLM: {content}")

def sarvam_tts(text: str, target_language_code: str = 'hi-IN', speaker: str = 'shubh') -> str:
    """3. Text-to-Speech: Generates a voice confirmation for the vendor."""
    if not SARVAM_API_KEY:
        raise ValueError("SARVAM_API_KEY is missing in .env file")
        
    headers = {
        'api-subscription-key': SARVAM_API_KEY,
        'Content-Type': 'application/json'
    }
    payload = {
        'text': text,
        'target_language_code': target_language_code,
        'speaker': speaker,
        'model': 'bulbul:v3'
    }
    
    response = requests.post('https://api.sarvam.ai/text-to-speech', json=payload, headers=headers)
    if not response.ok:
        raise Exception(f"TTS failed: {response.text}")
        
    audios = response.json().get('audios')
    if audios and len(audios) > 0:
        return audios[0] # Returns base64 encoded audio string
    raise Exception("No audio returned from TTS")
