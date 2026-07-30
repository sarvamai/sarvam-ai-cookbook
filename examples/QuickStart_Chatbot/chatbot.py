# Import necessary libraries
import argparse  # This is for parsing command-line arguments (like your API key).
import requests  # This is for making HTTP requests to the Sarvam AI API.

# This function sends your message to the Sarvam AI API and gets a response.
def get_chat_response(api_key, user_input):
    """
    Get a response from the Sarvam AI Chat Completions API.
    """
    # These are the headers for the API request, including your API key for authorization.
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # This is the data payload for the API request.
    data = {
        "model": "sarvam-m",  # Specifies the model to use.
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},  # System message to guide the bot's behavior.
            {"role": "user", "content": user_input},  # Your question.
        ],
        "temperature": 0.7,  # Controls the creativity of the response.
    }
    # This sends the request to the Sarvam AI API.
    response = requests.post(
        "https://api.sarvam.ai/v1/chat/completions", headers=headers, json=data
    )
    response.raise_for_status()  # This will raise an error if the request fails.
    # This extracts the bot's message from the JSON response.
    return response.json()["choices"][0]["message"]["content"]

# This is the main function that runs when you execute the script.
def main():
    # This sets up the command-line argument parser to accept your API key.
    parser = argparse.ArgumentParser(description="Basic Sarvam AI Chatbot")
    parser.add_argument("--api-key", required=True, help="Your Sarvam AI API key.")
    args = parser.parse_args()

    # This prompts you to enter your question.
    print("Chatbot initialized. Enter your question.")
    user_input = input("You: ").strip()

    if user_input:
        try:
            # This calls the function to get the bot's response.
            bot_response = get_chat_response(args.api_key, user_input)
            # This prints the bot's response.
            print(f"Bot: {bot_response}")
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")

# This ensures that the main() function is called when the script is run directly.
if __name__ == "__main__":
    main()