import requests
import json

# API Configuration
SCHEME_API_URL = "https://api.sarvam.ai/v1/chat/completions"
TRANSLATION_API_URL = "https://api.sarvam.ai/translate"

supported_languages = [
    {"code": "hi-IN", "name": "Hindi", "nativeName": "हिन्दी"},
    {"code": "ta-IN", "name": "Tamil", "nativeName": "தமிழ்"},
    {"code": "te-IN", "name": "Telugu", "nativeName": "తెలుగు"},
    {"code": "bn-IN", "name": "Bengali", "nativeName": "বাংলা"},
    {"code": "ml-IN", "name": "Malayalam", "nativeName": "മലയാളം"},
    {"code": "kn-IN", "name": "Kannada", "nativeName": "ಕನ್ನಡ"},
    {"code": "mr-IN", "name": "Marathi", "nativeName": "मराठी"},
    {"code": "gu-IN", "name": "Gujarati", "nativeName": "ગુજરાતી"},
    {"code": "pa-IN", "name": "Punjabi", "nativeName": "ਪੰਜਾਬੀ"},
    {"code": "or-IN", "name": "Odia", "nativeName": "ଓଡ଼ିଆ"}
]

def chunk_text(text: str, max_length: int = 1000) -> list[str]:
    """
    Splits a given text into chunks of a specified maximum length.
    Attempts to split at the last space before the max_length to avoid breaking words.
    """
    chunks = []
    remaining_text = text

    while len(remaining_text) > max_length:
        split_at = remaining_text.rfind(" ", 0, max_length)
        if split_at == -1:  # No space found, force split
            split_at = max_length
        chunks.append(remaining_text[0:split_at].strip())
        remaining_text = remaining_text[split_at:].strip()

    if remaining_text:
        chunks.append(remaining_text)
    return chunks

def summarize_scheme(user_input: str, api_key: str, category: str = "") -> str:
    """
    Summarizes a government scheme using the SARVAM AI API.
    """
    if not api_key:
        raise ValueError("API key is required")

    system_prompt = "You're an Indian government official who is expert in this scheme category and helps Indian citizens understand Indian government schemes"
    user_prompt = f"Summarize the scheme '{user_input}' in bullet points in not more than 1500 characters and also include official links or reliable government sources for further information."

    if category:
        system_prompt += f" Category: {category}"

    payload = {
        "model": "sarvam-m",
        "wiki_grounding": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        response = requests.post(SCHEME_API_URL, headers=headers, data=json.dumps(payload))
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Scheme summary request failed: {e}") from e
    except KeyError as e:
        raise ValueError(f"Unexpected API response format for scheme summary: {e}") from e

def translate_summary(summary: str, target_lang_code: str, api_key: str) -> str:
    """
    Translates a given text summary to a target language using the SARVAM AI translation API.
    Handles text chunking for longer inputs.
    """
    if not api_key:
        raise ValueError("API key is required")
    if not summary:
        return ""

    chunks = chunk_text(summary, 1000)
    translations = []

    headers = {
        "Content-Type": "application/json",
        "api-subscription-key": api_key
    }

    for chunk in chunks:
        payload = {
            "input": chunk,
            "source_language_code": "en-IN",
            "target_language_code": target_lang_code,
            "speaker_gender": "Male",
            "mode": "classic-colloquial",
            "model": "mayura:v1",
            "enable_preprocessing": False
        }
        try:
            response = requests.post(TRANSLATION_API_URL, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            data = response.json()
            translations.append(data["translated_text"])
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Translation request failed for chunk: {e}") from e
        except KeyError as e:
            raise ValueError(f"Unexpected API response format for translation chunk: {e}") from e

    return "\n".join(translations)

# --- Example Usage ---
if __name__ == "__main__":
    # Replace with your actual SARVAM API Key
    SARVAM_API_KEY = "YOUR_SARVAM_API_KEY" 

    if SARVAM_API_KEY == "YOUR_SARVAM_API_KEY":
        print("Please replace 'YOUR_SARVAM_API_KEY' with your actual API key to run the examples.")
    else:
        # Example 1: Summarize a scheme
        print("--- Summarizing Scheme ---")
        try:
            scheme_name = "Pradhan Mantri Jan Dhan Yojana"
            scheme_summary = summarize_scheme(scheme_name, SARVAM_API_KEY)
            print(f"\nSummary for '{scheme_name}':\n{scheme_summary}\n")
            
            # Example 2: Translate the summary
            print("--- Translating Summary to Hindi ---")
            hindi_code = "hi-IN"
            translated_summary = translate_summary(scheme_summary, hindi_code, SARVAM_API_KEY)
            print(f"\nTranslated Summary (Hindi):\n{translated_summary}\n")

            # Example 3: Summarize another scheme with category
            print("--- Summarizing Scheme with Category ---")
            scheme_name_2 = "Ayushman Bharat"
            category_2 = "Social Welfare & Empowerment"
            scheme_summary_2 = summarize_scheme(scheme_name_2, SARVAM_API_KEY, category_2)
            print(f"\nSummary for '{scheme_name_2}' (Category: {category_2}):\n{scheme_summary_2}\n")

        except (ValueError, ConnectionError) as e:
            print(f"An error occurred: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")