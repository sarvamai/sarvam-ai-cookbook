import argparse
import requests
import json
import os
from typing import Dict, Any

# Constants
LID_API_URL = "https://api.sarvam.ai/text-lid"
CHAT_API_URL = "https://api.sarvam.ai/v1/chat/completions"

def identify_language(text: str, api_key: str) -> Dict[str, Any]:
    """Identify the language of the input text using Sarvam's LID API."""
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": text
    }
    
    response = requests.post(LID_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def get_explanation(question: str, language_code: str, grade_level: int, api_key: str) -> Dict[str, Any]:
    """Get a detailed explanation using Sarvam's Chat Completions API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    system_prompt = f"""You are a helpful teacher explaining concepts to a {grade_level}th grade student in {language_code}.
    Always explain concepts in detail but in simple terms.
    Break down complex topics into easy-to-understand steps.
    Provide examples and analogies where appropriate.
    End with 2-3 practice questions to reinforce learning."""
    
    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "model": "sarvam-m",
        "temperature": 0.7
    }
    
    response = requests.post(CHAT_API_URL, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()

def main():
    parser = argparse.ArgumentParser(description="Homework Helper - Get detailed explanations for student questions")
    parser.add_argument("question", help="The homework question or topic to explain")
    parser.add_argument("--grade", type=int, default=5, help="Student's grade level (default: 5)")
    parser.add_argument("--api-key", help="Sarvam API key (can also be set via SARVAM_API_KEY environment variable)")
    
    args = parser.parse_args()
    
    # Get API key from args or environment variable
    api_key = args.api_key or os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise ValueError("API key must be provided either via --api-key or SARVAM_API_KEY environment variable")
    
    try:
        # First identify the language
        lid_result = identify_language(args.question, api_key)
        language_code = lid_result.get("language_code", "en-IN")
        
        print(f"\nDetected Language: {language_code}")
        print("\nGenerating explanation...\n")
        
        # Get the explanation
        explanation = get_explanation(args.question, language_code, args.grade, api_key)
        
        # Extract and print the response
        if explanation.get("choices"):
            content = explanation["choices"][0]["message"]["content"]
            print("Explanation:")
            print("=" * 50)
            print(content)
            print("=" * 50)
        else:
            print("No explanation generated. Please try again.")
            
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main() 