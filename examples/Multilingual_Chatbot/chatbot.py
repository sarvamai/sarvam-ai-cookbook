import argparse
import json
import requests
from typing import List, Dict, Any


class MultilingualChatbot:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sarvam.ai/chat/completions"
        self.translate_url = (
            "https://api.sarvam.ai/translate/text"  # Add translation endpoint
        )
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self.conversation_history: List[Dict[str, str]] = []
        self.max_history = 5

        # Common error messages in different languages
        self.error_messages = {
            "english": "I apologize, but I'm having trouble processing your request. Please try again.",
            "hindi": "मुझे खेद है, लेकिन मैं आपके अनुरोध को संसाधित करने में परेशानी का सामना कर रहा हूं। कृपया पुनः प्रयास करें।",
            "tamil": "மன்னிக்கவும், உங்கள் கோரிக்கையை செயலாக்குவதில் சிக்கல் ஏற்பட்டுள்ளது. மீண்டும் முயற்சிக்கவும்.",
            "telugu": "క్షమించండి, మీ అభ్యర్థనను ప్రాసెస్ చేయడంలో ఇబ్బంది ఎదురవుతోంది. దయచేసి మళ్లీ ప్రయత్నించండి.",
            "kannada": "ಕ್ಷಮಿಸಿ, ನಿಮ್ಮ ವಿನಂತಿಯನ್ನು ಸಂಸ್ಕರಿಸುವಲ್ಲಿ ತೊಂದರೆ ಎದುರಾಗುತ್ತಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
            "malayalam": "ക്ഷമിക്കണം, നിങ്ങളുടെ അഭ്യർത്ഥന സംസ്കരിക്കുന്നതിൽ പ്രശ്നം നേരിടുന്നു. ദയവായി വീണ്ടും ശ്രമിക്കുക.",
        }

    def detect_language(self, text: str) -> str:
        # Enhanced language detection based on character ranges
        devanagari_range = range(0x0900, 0x097F)  # Hindi
        tamil_range = range(0x0B80, 0x0BFF)  # Tamil
        telugu_range = range(0x0C00, 0x0C7F)  # Telugu
        kannada_range = range(0x0C80, 0x0CFF)  # Kannada
        malayalam_range = range(0x0D00, 0x0D7F)  # Malayalam

        for char in text:
            code = ord(char)
            if code in devanagari_range:
                return "hindi"
            elif code in tamil_range:
                return "tamil"
            elif code in telugu_range:
                return "telugu"
            elif code in kannada_range:
                return "kannada"
            elif code in malayalam_range:
                return "malayalam"

        return "english"

    def translate_text(self, text: str, target_lang: str) -> str:
        try:
            # If we have a pre-translated error message, use it
            if (
                text in self.error_messages.values()
                and target_lang in self.error_messages
            ):
                return self.error_messages[target_lang]

            # Otherwise, use the translation API
            response = requests.post(
                self.translate_url,
                headers=self.headers,
                json={"text": text, "target_language": target_lang},
            )
            response.raise_for_status()
            return response.json()["translated_text"]
        except Exception as e:
            # If translation fails, return the error message in the target language if available
            return self.error_messages.get(target_lang, self.error_messages["english"])

    def get_chat_response(self, user_input: str) -> Dict[str, Any]:
        # Detect language of user input
        detected_lang = self.detect_language(user_input)

        # Add user message to conversation history
        self.conversation_history.append({"role": "user", "content": user_input})

        # Prepare messages for API call
        messages = [
            {
                "role": "system",
                "content": "You are a helpful multilingual assistant. Respond in the same language as the user's input.",
            }
        ]

        # Add conversation history (limited to last 5 turns)
        messages.extend(self.conversation_history[-self.max_history :])

        # Make API call
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json={"model": "sarvam-m", "messages": messages, "temperature": 0.7},
            )
            response.raise_for_status()

            # Extract assistant's response
            assistant_response = response.json()["choices"][0]["message"]["content"]

            # Add assistant's response to conversation history
            self.conversation_history.append(
                {"role": "assistant", "content": assistant_response}
            )

            return {"response": assistant_response, "language": detected_lang}

        except requests.exceptions.RequestException as e:
            # Get appropriate error message in the detected language
            error_message = self.error_messages.get(
                detected_lang, self.error_messages["english"]
            )
            return {"response": error_message, "language": detected_lang}


def main():
    parser = argparse.ArgumentParser(description="Multilingual Chatbot")
    parser.add_argument("--api-key", required=True, help="Sarvam API key")
    args = parser.parse_args()

    chatbot = MultilingualChatbot(args.api_key)

    print("Chatbot initialized. Type 'quit' to exit.")
    print("You can chat in English or regional language.")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == "quit":
            break

        response = chatbot.get_chat_response(user_input)
        print(f"\nBot ({response['language']}): {response['response']}")


if __name__ == "__main__":
    main()
