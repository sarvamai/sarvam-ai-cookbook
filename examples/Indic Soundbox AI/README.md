# Sarvam Indic Soundbox AI (Inspired from Paytm and PhonePe soundboxes)
This Agent enables Indian merchants via their Soundbox (lets say Paytm or PhonePe Soundbox) to get insights about their Sales, How to grow their busines? in their local language of choice and also enables organisations like Paytm and PhonePe to connect with their merchants in a easier manner in indic languages.

This uses Sarvam ASR (`saaras:v3`), Language Identification, the Sarvam-105B chat model and TTS (`bulbul:v3`) - all built on the Indic Stack.

## Project Structure

```
.
├── app.py                # Main Flask application
├── merchant_context.md   # Context file for the LLM
├── requirements.txt      # Python dependencies
├── modules/              # Backend Python modules
│   ├── asr.py
│   ├── lid.py
│   ├── llm.py
│   └── tts.py
├── static/               # Frontend static files
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── templates/            # Frontend HTML templates
    └── index.html
```

## Setup

1.  **Clone the repository (or create the files as listed above).**

2.  **Create a virtual environment (recommended):**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Sarvam API Key:**
    Create a file named `.env` in the root of the project directory (next to `app.py`).
    Add your [Sarvam API key](https://dashboard.sarvam.ai) to this file:
    ```
    SARVAM_API_KEY='YOUR_SARVAM_API_KEY_HERE'
    ```
    Replace `YOUR_SARVAM_API_KEY_HERE` with your actual key.

5.  **Modify `merchant_context.md`:**
    Update the `merchant_context.md` file with any specific sales data, product combos, or other information relevant to the merchant.

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Run the Flask development server:**
    ```bash
    python app.py
    ```
3.  Open your web browser and navigate to `http://127.0.0.1:5001`.

## How it Works

1.  The user clicks the "Record" button in the web interface.
2.  The browser records audio from the microphone.
3.  When "Stop" is clicked, the audio is sent to the Flask backend's `/asr` endpoint.
4.  The backend calls the Sarvam ASR API to get the transcript.
5.  The transcript is sent to the `/lid` endpoint.
6.  The backend calls Sarvam LID API to detect the language.
7.  The transcript is then sent to the `/chat` endpoint.
8.  The backend loads context from `merchant_context.md`, prepends it to a system prompt, and then sends the user's transcript to the Sarvam Chat Completion API (LLM).
9.  The LLM's text response and the detected language code are sent to the `/tts` endpoint.
10. The backend calls the Sarvam TTS API to generate audio.
11. The audio (as a base64 data URI) is returned to the frontend.
12. The user can click "Play Response" to hear the bot's reply.

## Example Usage Scenarios

*   **Merchant:** "आज मेरी सेल्स कितनी है?" (What are my sales today?)
    *   **Bot:** (Based on `merchant_context.md`) "आपकी आज की सेल्स ₹1500 है, कल से 15% ज़्यादा। आप चाय के साथ समोसा भी ऑफर कर सकते हैं — अच्छा कॉम्बो है।" (Your sales today are ₹1500, 15% more than yesterday. You can also offer samosa with tea - it's a good combo.)

*   **Merchant:** "आज कौन सा IPL मैच है?" (Which IPL match is today?)
    *   **Bot:** (Based on `merchant_context.md`) "आज चेन्नई सुपर किंग्स vs मुंबई इंडियंस का मैच है।" (Today's match is Chennai Super Kings vs Mumbai Indians.) 