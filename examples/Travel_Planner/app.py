import streamlit as st
import pandas as pd
from sarvam_utils import detect_language, translate_text, transliterate_text, generate_itinerary

# Set page config
st.set_page_config(
    page_title="AI Travel Assistant",
    page_icon="✈️",
    layout="wide"
)

# Initialize session state
if 'preferred_language' not in st.session_state:
    st.session_state.preferred_language = 'en'

# Title and description
st.title("✈️ AI Travel Assistant")
st.markdown("""
Your personalized travel companion for exploring India and beyond! 
Get customized itineraries, local insights, and cultural guidance in your preferred language.
""")

# Language selection
languages = {
    'en': 'English',
    'hi': 'हिंदी',
    'bn': 'বাংলা',
    'ta': 'தமிழ்',
    'te': 'తెలుగు',
    'mr': 'मराठी',
    'gu': 'ગુજરાતી',
    'kn': 'ಕನ್ನಡ',
    'ml': 'മലയാളം',
    'pa': 'ਪੰਜਾਬੀ'
}

selected_language = st.sidebar.selectbox(
    "Select your preferred language",
    options=list(languages.keys()),
    format_func=lambda x: languages[x]
)

# Update session state if language changes
if selected_language != st.session_state.preferred_language:
    st.session_state.preferred_language = selected_language

# Main input form
with st.form("travel_planner"):
    col1, col2 = st.columns(2)
    
    with col1:
        destination = st.text_input("Where would you like to go?")
        travel_dates = st.date_input("When are you planning to travel?")
        duration = st.number_input("How many days?", min_value=1, max_value=30, value=3)
    
    with col2:
        interests = st.multiselect(
            "What are your interests?",
            ["Culture", "Food", "Nature", "Adventure", "History", "Shopping", "Relaxation"]
        )
        
        budget = st.select_slider(
            "What's your budget range?",
            options=["Budget", "Moderate", "Luxury"]
        )
    
    submit_button = st.form_submit_button("Plan My Trip!")

# Process the form submission
if submit_button and destination:
    with st.spinner("Creating your personalized itinerary..."):
        # Detect language of input
        lang_detection = detect_language(destination)
        detected_lang = lang_detection.get('language', 'en')
        
        # Generate itinerary using Sarvam Chat Completions
        itinerary_response = generate_itinerary(
            destination=destination,
            duration=duration,
            interests=interests,
            budget=budget,
            language=detected_lang
        )
        
        # Extract the generated itinerary
        itinerary = itinerary_response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # Translate itinerary to preferred language if needed
        if st.session_state.preferred_language != 'en':
            translated_itinerary = translate_text(
                itinerary,
                st.session_state.preferred_language,
                mode="formal"
            )
            itinerary = translated_itinerary.get('translated_text', itinerary)
        
        # Display the itinerary
        st.markdown("### Your Personalized Itinerary")
        st.markdown(itinerary)
        
        # Generate and display travel tips
        tips_prompt = f"""Based on the destination {destination} and budget level {budget}, 
        provide practical travel tips including:
        - Best time to visit
        - Local transportation options
        - Cultural etiquette and customs
        - Safety considerations
        - Essential local phrases
        - Packing recommendations"""
        
        tips_response = generate_itinerary(
            destination=destination,
            duration=1,
            interests=["Practical Tips"],
            budget=budget,
            language=detected_lang
        )
        
        tips = tips_response.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        if st.session_state.preferred_language != 'en':
            translated_tips = translate_text(
                tips,
                st.session_state.preferred_language,
                mode="formal"
            )
            tips = translated_tips.get('translated_text', tips)
        
        st.markdown("### Travel Tips")
        st.markdown(tips)

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Powered by Sarvam AI | Your trusted travel companion</p>
</div>
""", unsafe_allow_html=True) 