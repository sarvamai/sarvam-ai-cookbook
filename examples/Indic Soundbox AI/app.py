import os
from flask import Flask, request, jsonify, render_template, Response
from dotenv import load_dotenv
import uuid # For generating unique IDs
import base64 # Ensure base64 is imported

# Import your modules
from modules.asr import speech_to_text
from modules.lid import identify_language
from modules.llm import get_chat_completion
from modules.tts import text_to_speech

load_dotenv()

app = Flask(__name__)

# Temporary in-memory store for audio data
# For a production app, consider a more robust solution (e.g., Redis, temp files with cleanup)
temp_audio_store = {}

# Check for API key at startup
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
if not SARVAM_API_KEY:
    print("ERROR: SARVAM_API_KEY not found in .env file or environment variables.")
    print("Please create a .env file with SARVAM_API_KEY='your_key'")
    # You might want to exit or raise an error here in a real app
    # For this prototype, we'll let it run but API calls will fail.

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/detailed')
def detailed_view():
    return render_template('detailed.html')

@app.route('/asr', methods=['POST'])
def asr_route():
    if 'file' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['file']
    
    try:
        transcript = speech_to_text(audio_file.read())
        if transcript is None:
             return jsonify({'error': 'ASR failed to transcribe audio'}), 500
        return jsonify({'transcript': transcript})
    except Exception as e:
        print(f"ASR Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/lid', methods=['POST'])
def lid_route():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided for LID'}), 400
    
    text = data['text']
    try:
        lid_result = identify_language(text)
        return jsonify(lid_result)
    except Exception as e:
        print(f"LID Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat_route():
    data = request.get_json()
    if not data or 'text' not in data:
        print("/chat route: Error - No text provided for chat")
        return jsonify({'error': 'No text provided for chat'}), 400
    
    user_text = data['text']
    print(f"/chat route: Received user text: '{user_text}'")
    try:
        bot_reply_text = get_chat_completion(user_text)
        print(f"/chat route: LLM generated bot reply: '{bot_reply_text}'")
        return jsonify({'reply': bot_reply_text})
    except Exception as e:
        print(f"/chat route: Error during LLM call: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/tts', methods=['POST'])
def tts_route():
    data = request.get_json()
    if not data or 'text' not in data or 'lang_code' not in data:
        print("/tts route: Error - Missing text or lang_code for TTS")
        return jsonify({'error': 'Missing text or lang_code for TTS'}), 400
    
    text_to_synthesize = data['text']
    lang_code = data['lang_code']
    print(f"/tts route: Received request to synthesize text for TTS: '{text_to_synthesize}' (length: {len(text_to_synthesize)}) in lang: {lang_code}")
    
    try:
        audio_base64_content = text_to_speech(text_to_synthesize, lang_code)
        if not audio_base64_content:
            print("/tts route: Error - TTS module returned no audio data.")
            return jsonify({'error': 'TTS module returned no audio data'}), 500
        
        print(f"/tts route: Received base64 audio content from TTS module, length: {len(audio_base64_content)}")

        audio_id = str(uuid.uuid4())
        temp_audio_store[audio_id] = f"data:audio/wav;base64,{audio_base64_content}"
        
        # Optional: Add a simple cleanup mechanism for old entries if server runs long
        # This is a very basic example; a proper TTL cache would be better.
        if len(temp_audio_store) > 100: # Keep store size manageable
            # Remove the oldest item (dictionaries are ordered in Python 3.7+)
            try:
                oldest_key = next(iter(temp_audio_store))
                del temp_audio_store[oldest_key]
                print(f"/tts route: Cleaned up oldest audio_id: {oldest_key}")
            except StopIteration:
                pass # Store is empty

        print(f"/tts route: Stored audio with id: {audio_id}")
        return jsonify({'audio_id': audio_id})
    except Exception as e:
        print(f"/tts route: Error during TTS processing: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/get_audio/<audio_id>', methods=['GET'])
def get_audio_route(audio_id):
    print(f"/get_audio route: Request for audio_id: {audio_id}")
    audio_data_uri = temp_audio_store.pop(audio_id, None)

    if audio_data_uri:
        try:
            header, base64_data = audio_data_uri.split(',', 1)
            audio_bytes = base64.b64decode(base64_data)
            mimetype = header.split(':')[1].split(';')[0]
            print(f"/get_audio route: Found audio for {audio_id}. Decoded bytes length: {len(audio_bytes)}. Mimetype: {mimetype}")
            return Response(audio_bytes, mimetype=mimetype)
        except Exception as e:
            print(f"/get_audio route: Error processing stored audio data for {audio_id}: {e}")
            return jsonify({'error': 'Error processing stored audio data'}), 500
    else:
        print(f"/get_audio route: Audio ID {audio_id} not found or already retrieved.")
        return jsonify({'error': 'Audio not found or already retrieved'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5001) 