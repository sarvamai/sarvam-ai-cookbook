import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
SARVAM_API_KEY = os.getenv('SARVAM_API_KEY')
SARVAM_API_URL = "https://api.sarvam.ai/v1/chat/completions"
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"

# Supported Languages with their native names
SUPPORTED_LANGUAGES = {
    'en-IN': 'English',
    'hi-IN': 'हिंदी',
    'ta-IN': 'தமிழ்',
    'te-IN': 'తెలుగు',
    'bn-IN': 'বাংলা',
    'kn-IN': 'ಕನ್ನಡ'
}

# System Prompts
SYSTEM_PROMPTS = {
    'concept_explanation': """You are a helpful programming tutor. Explain the given programming concept in simple terms.
    Use analogies and real-life examples relevant to Indian context.
    Provide examples in both English and the selected Indian language.
    Keep the explanation clear and suitable for high school/college students.""",
    
    'code_debugging': """You are a helpful programming tutor. Analyze the provided code and:
    1. Identify any errors or bugs
    2. Explain the cause of the error
    3. Provide the corrected code
    4. Explain the solution in both English and the selected Indian language
    Keep the explanation clear and suitable for high school/college students.""",
    
    'code_sample': """You are a helpful programming tutor. Provide a working code sample for the requested task.
    Include detailed comments and explanations in both English and the selected Indian language.
    Make sure the code is well-documented and follows best practices."""
} 