from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Input model
class UserAnswers(BaseModel):
    answers: list[str]

@app.post("/generate-song")
async def generate_song(data: UserAnswers):
    name = data.answers[0]
    color = data.answers[1]
    hobby = data.answers[2]
    friend = data.answers[3]
    food = data.answers[4]
    place = data.answers[5]
    memory = data.answers[6]
    habit = data.answers[7]
    nickname = data.answers[8]
    wish = data.answers[9]

    prompt = f"""
        Generate a joyful birthday song in simple English.
        Make it a bit offensive, roasting, and rhyming using the given details. Try to use all of this information and give me a funny 12-line song. No need for chorus:
        Full name and age: {name}
        If your friend was a color, what color would they be and why?: {color}
        Favorite hobby or something they do all the time: {hobby}
        Best buddy and a funny memory: {friend}
        Favorite food: {food}
        Dream travel destination: {place}
        Recent funny or happy moment: {memory}
        Quirky or adorable habit: {habit}
        Funny nickname: {nickname}
        Embarrassing moment they secretly enjoy: {wish}
    """

    response = requests.post(
        "https://api.sarvam.ai/v1/chat/completions",
        headers={
            "api-subscription-key": SARVAM_API_KEY
        },
        json={
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "sarvam-m"
        },
    )

    result = response.json()
    content = result["choices"][0]["message"]["content"]
    print(content)

    return {"quotes": content}
