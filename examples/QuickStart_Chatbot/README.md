# Basic Chatbot

A simple command-line chatbot that keeps the conversation history and demonstrates how to use the Sarvam AI Chat Completions API.

## Features

- Takes the user's questions as input in a chat loop.
- Sends the full conversation history to the Sarvam AI API, so the bot remembers context.
- Prints the model's response.

## Getting Started

### Prerequisites

- Python 3.7 or higher
- A Sarvam AI API key

### Getting Your API Key

1.  Visit [Sarvam AI Dashboard](https://dashboard.sarvam.ai/)
2.  Sign up for a new account.
3.  Navigate to the API Keys section to generate your key.

## Installation

1.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the chatbot with your Sarvam API key:

```bash
python chatbot.py --api-key YOUR_API_KEY
```
