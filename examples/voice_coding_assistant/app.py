import os
import re
import tempfile

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from sarvamai import SarvamAI

load_dotenv()

app = Flask(__name__)

# =============================
# CONFIG
# =============================

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

if not SARVAM_API_KEY:
    raise RuntimeError(
        "SARVAM_API_KEY is not set. Copy .env.example to .env and add your key."
    )

client = SarvamAI(
    api_subscription_key=SARVAM_API_KEY
)


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

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_file.read())
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                response = client.speech_to_text.transcribe(
                    file=f,
                    model="saaras:v3",
                    mode="transcribe"
                )
        finally:
            os.remove(tmp_path)

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

        response = client.chat.completions(
            model="sarvam-105b",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_tokens=2000,
            top_p=0.9
        )

        if not response.choices:
            return jsonify({
                "code": "Error generating code"
            }), 500

        code = response.choices[0].message.content

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
