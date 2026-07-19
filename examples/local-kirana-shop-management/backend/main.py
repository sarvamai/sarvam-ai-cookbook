from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List

import database
import schemas
from services.sarvam_api import sarvam_stt, extract_transaction_json, sarvam_tts

app = FastAPI(title="VendorVoice Backend")

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get Database Session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Welcome to VendorVoice Backend API"}

@app.post("/voice-transaction/")
async def process_voice_transaction(
    file: UploadFile = File(...), 
    language: str = Form("hi-IN"),
    speaker: str = Form("shubh"),
    db: Session = Depends(get_db)
):
    """
    The main AI Flow Endpoint:
    Receives Audio -> STT -> LLM JSON Extraction -> DB Update -> TTS Confirmation
    """
    try:
        # Read the audio file sent from frontend
        audio_bytes = await file.read()
        
        # 1. Convert Voice to Text
        transcript = sarvam_stt(audio_bytes)
        print(f"Transcript: {transcript}")
        
        # 2. Extract Data using LLM
        trans_data = extract_transaction_json(transcript)
        print(f"Extracted JSON: {trans_data}")
        
        # 3. Save to Database
        db_item = database.Transaction(
            customer_name=trans_data.get("customer_name", "Unknown"),
            amount=float(trans_data.get("amount", 0.0)),
            item_description=trans_data.get("item_description", ""),
            transaction_type=trans_data.get("transaction_type", "credit")
        )
        db.add(db_item)
        db.flush() # Gets the ID without committing permanently
        
        # 4. Generate Confirmation Voice
        CONFIRMATION_TEMPLATES = {
            "hi-IN": {"credit": "{name} का {amount} रुपये का उधार लिख दिया गया है।", "settled": "{name} का {amount} रुपये जमा कर लिया गया है।"},
            "en-IN": {"credit": "{name}'s credit of {amount} rupees has been recorded.", "settled": "{name}'s payment of {amount} rupees has been received."},
            "bn-IN": {"credit": "{name}-এর {amount} টাকার বাকি লেখা হয়েছে।", "settled": "{name}-এর {amount} টাকা জমা নেওয়া হয়েছে।"},
            "ta-IN": {"credit": "{name} என்பவரின் {amount} ரூபாய் கடன் பதிவு செய்யப்பட்டுள்ளது.", "settled": "{name} என்பவரின் {amount} ரூபாய் வரவு வைக்கப்பட்டுள்ளது."},
            "te-IN": {"credit": "{name} యొక్క {amount} రూపాయల అప్పు నమోదు చేయబడింది.", "settled": "{name} యొక్క {amount} రూపాయలు జమ చేయబడ్డాయి."},
            "mr-IN": {"credit": "{name} ची {amount} रुपयांची उधारी नोंदवली आहे.", "settled": "{name} चे {amount} रुपये जमा केले आहेत."},
            "gu-IN": {"credit": "{name} ના {amount} રૂપિયા ઉધાર લખાઈ ગયા છે.", "settled": "{name} ના {amount} રૂપિયા જમા થઈ ગયા છે."},
            "kn-IN": {"credit": "{name} ಅವರ {amount} ರೂಪಾಯಿ ಸಾಲವನ್ನು ಬರೆಯಲಾಗಿದೆ.", "settled": "{name} ಅವರ {amount} ರೂಪಾಯಿ ಜಮಾ ಮಾಡಲಾಗಿದೆ."},
            "ml-IN": {"credit": "{name} ന്റെ {amount} രൂപ കടം രേഖപ്പെടുത്തിയിട്ടുണ്ട്.", "settled": "{name} ന്റെ {amount} രൂപ ലഭിച്ചു."},
            "pa-IN": {"credit": "{name} ਦਾ {amount} ਰੁਪਏ ਦਾ ਉਧਾਰ ਲਿਖ ਲਿਆ ਗਿਆ ਹੈ।", "settled": "{name} ਦਾ {amount} ਰੁਪਏ ਜਮ੍ਹਾਂ ਕਰ ਲਿਆ ਗਿਆ ਹੈ।"},
            "or-IN": {"credit": "{name} ଙ୍କର {amount} ଟଙ୍କା ବାକି ଲେଖାଗଲା।", "settled": "{name} ଙ୍କର {amount} ଟଙ୍କା ଜମା ହେଲା।"}
        }
        
        templates = CONFIRMATION_TEMPLATES.get(language, CONFIRMATION_TEMPLATES["hi-IN"])
        template = templates.get(db_item.transaction_type, templates["credit"])
        confirmation_text = template.format(name=db_item.customer_name, amount=int(db_item.amount))
        audio_base64 = sarvam_tts(confirmation_text, target_language_code=language, speaker=speaker)
        
        # 5. Only commit if everything succeeded
        db.commit()
        db.refresh(db_item)
        
        return {
            "success": True,
            "transcript": transcript,
            "transaction": {
                "id": db_item.id,
                "customer_name": db_item.customer_name,
                "amount": db_item.amount,
                "item_description": db_item.item_description,
                "transaction_type": db_item.transaction_type,
                "created_at": db_item.created_at.isoformat() if db_item.created_at else None
            },
            "audio_base64": audio_base64
        }
    except Exception as e:
        db.rollback() # Important: Rollback the transaction if anything fails
        print(f"Error processing voice transaction: {str(e)}")
        
        error_messages = {
            "hi-IN": "माफ़ कीजिए, मैं ठीक से समझ नहीं पाया। कृपया एक बार फिर से साफ-साफ बोलें।",
            "en-IN": "Sorry, I couldn't understand that clearly. Please try speaking again.",
            "bn-IN": "দুঃখিত, আমি ঠিকমতো বুঝতে পারিনি। অনুগ্রহ করে আবার একটু পরিষ্কার করে বলুন।",
            "mr-IN": "माफ करा, मला नीट समजले नाही. कृपया पुन्हा एकदा स्पष्टपणे सांगा.",
            "ta-IN": "மன்னிக்கவும், எனக்கு சரியாக புரியவில்லை. தயவுசெய்து மீண்டும் தெளிவாக பேசவும்.",
            "te-IN": "క్షమించండి, నాకు సరిగా అర్థం కాలేదు. దయచేసి మళ్ళీ స్పష్టంగా మాట్లాడండి.",
            "gu-IN": "માફ કરશો, મને બરાબર સમજાયું નથી. કૃપા કરીને ફરીથી સ્પષ્ટ બોલો.",
            "kn-IN": "ಕ್ಷಮಿಸಿ, ನನಗೆ ಸರಿಯಾಗಿ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಸ್ಪಷ್ಟವಾಗಿ ಮಾತನಾಡಿ.",
            "ml-IN": "ക്ഷമിക്കണം, എനിക്ക് കൃത്യമായി മനസ്സിലായില്ല. ദയവായി ഒന്നുകൂടി വ്യക്തമായി പറയുക.",
            "pa-IN": "ਮਾਫ਼ ਕਰਨਾ, ਮੈਨੂੰ ਠੀਕ ਤਰ੍ਹਾਂ ਸਮਝ ਨਹੀਂ ਆਇਆ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਸਾਫ਼-ਸਾਫ਼ ਬੋਲੋ।",
            "or-IN": "କ୍ଷମା କରିବେ, ମୁଁ ଠିକ୍ ଭାବରେ ବୁଝିପାରିଲି ନାହିଁ। ଦୟାକରି ପୁଣି ଥରେ ସ୍ପଷ୍ଟ ଭାବରେ କୁହନ୍ତୁ।"
        }
        
        fallback_msg = error_messages.get(language, error_messages["hi-IN"])
        error_audio = None
        try:
            error_audio = sarvam_tts(fallback_msg, target_language_code=language, speaker=speaker)
        except Exception as tts_e:
            print(f"Failed to generate error TTS: {str(tts_e)}")
            
        return {
            "success": False,
            "error_message": "Sorry, I didn't catch that clearly. Please try again.",
            "audio_base64": error_audio
        }

@app.get("/transactions/", response_model=List[schemas.TransactionResponse])
def get_transactions(db: Session = Depends(get_db), skip: int = 0, limit: int = 100):
    return db.query(database.Transaction).offset(skip).limit(limit).all()
