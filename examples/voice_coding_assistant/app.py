import os
import re
import requests
from flask import Flask, render_template, request, jsonify
from sarvamai import SarvamAI

app = Flask(__name__)

# =============================
# CONFIG
# =============================

SARVAMAI_API_KEY = "YOUR_SARVAMAI_API_KEY"

client = SarvamAI(
    api_subscription_key=SARVAMAI_API_KEY
)

SARVAM_CHAT_URL = "https://api.sarvam.ai/v1/chat/completions"


# =============================
# UTIL: Detect language
# =============================

def detect_language(prompt: str) -> str:

    prompt = prompt.lower()

    if "java" in prompt:
        return "Java"
    elif "python" in prompt:
        return "Python"
    elif "c++" in prompt or "cpp" in prompt:
        return "C++"
    elif "c#" in prompt:
        return "C#"
    elif "javascript" in prompt or "js" in prompt:
        return "JavaScript"
    elif "typescript" in prompt:
        return "TypeScript"
    elif "go" in prompt:
        return "Go"
    elif "rust" in prompt:
        return "Rust"
    elif "php" in prompt:
        return "PHP"
    else:
        return "Java"   # default


# =============================
# UTIL: Clean markdown
# =============================

def clean_code(code: str) -> str:

    code = re.sub(r"```[a-zA-Z]*", "", code)
    code = code.replace("```", "")
    return code.strip()


# =============================
# ROUTES
# =============================

@app.route("/")
def home():
    return render_template("index.html")


# =============================
# SPEECH TO TEXT
# =============================

@app.route("/speech-to-text", methods=["POST"])
def speech_to_text():

    try:

        audio_file = request.files["audio"]

        with open("temp.wav", "wb") as f:
            f.write(audio_file.read())

        response = client.speech_to_text.transcribe(
            file=open("temp.wav", "rb"),
            model="saaras:v3",
            mode="transcribe"
        )

        return jsonify({
            "text": response.transcript
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =============================
# CODE GENERATION
# =============================

@app.route("/generate-code", methods=["POST"])
def generate_code():

    try:

        data = request.get_json()

        if not data or "prompt" not in data:
            return jsonify({"code": "Invalid request"}), 400

        prompt = data["prompt"]

        language = detect_language(prompt)

        headers = {
            "Authorization": f"Bearer {SARVAMAI_API_KEY}",
            "Content-Type": "application/json"
        }

        system_prompt = f"""
You are a strict code generation engine.

Rules:
- Output ONLY {language} code
- No explanation
- No theory
- No markdown
- No extra text
- No headings
- Only pure executable {language} code

If user asks theory, convert to practical {language} code example.

Output code only.
"""

        payload = {
            "model": "sarvam-m",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
            "top_p": 0.9
        }

        response = requests.post(
            SARVAM_CHAT_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        result = response.json()

        print("Sarvam response:", result)

        if "choices" not in result:
            return jsonify({
                "code": "Error generating code"
            }), 500

        code = result["choices"][0]["message"]["content"]

        code = clean_code(code)

        return jsonify({
            "code": code,
            "language": language
        })

    except Exception as e:

        print("Error:", e)

        return jsonify({
            "code": f"Error: {str(e)}"
        }), 500


# =============================
# MAIN
# =============================

if __name__ == "__main__":
    app.run(debug=True)