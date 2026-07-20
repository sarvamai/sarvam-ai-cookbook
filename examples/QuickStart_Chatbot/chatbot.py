# Import necessary libraries
import argparse  # This is for parsing command-line arguments (like your API key).
import requests  # This is for making HTTP requests to the Sarvam AI API.


# This function sends the full conversation to the Sarvam AI API and gets a response.
def get_chat_response(api_key, messages):
    """
    Get a response from the Sarvam AI Chat Completions API.

    `messages` is the full conversation history so the bot remembers context.
    """
    # These are the headers for the API request, including your API key for authorization.
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    # This is the data payload for the API request.
    data = {
        "model": "sarvam-105b",  # Specifies the model to use.
        "max_tokens": 2000,  # reasoning model needs a token budget or content is empty
        "messages": messages,  # The full conversation history.
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

    # The conversation history. The system message guides the bot's behavior and
    # is kept at the top so context is preserved across turns.
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
    ]

    print("Chatbot initialized. Type your question (or 'exit'/'quit' to stop).")

    # Keep chatting until the user decides to quit.
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        # Add the user's message to the conversation.
        messages.append({"role": "user", "content": user_input})

        try:
            # Get the bot's response using the full conversation history.
            bot_response = get_chat_response(args.api_key, messages)
            print(f"Bot: {bot_response}")
            # Remember the bot's reply so it has context for the next turn.
            messages.append({"role": "assistant", "content": bot_response})
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            # Drop the failed user turn so history stays consistent.
            messages.pop()


# This ensures that the main() function is called when the script is run directly.
if __name__ == "__main__":
    main()
