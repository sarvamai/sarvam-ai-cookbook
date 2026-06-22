import streamlit as st
import pandas as pd
from sarvam_utils import generate_itinerary

# Language names used in the generation prompt (the model produces well-structured
# markdown directly in these languages, which avoids translating markdown).
LANG_NAMES = {
    'en': 'English', 'hi': 'Hindi', 'bn': 'Bengali', 'ta': 'Tamil',
    'te': 'Telugu', 'mr': 'Marathi', 'gu': 'Gujarati', 'kn': 'Kannada',
    'ml': 'Malayalam', 'pa': 'Punjabi'
}

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

# On submit, store the trip inputs and clear any cached itineraries.
if submit_button and destination:
    st.session_state.trip = {
        'destination': destination,
        'duration': duration,
        'interests': interests,
        'budget': budget,
    }
    st.session_state.itineraries = {}  # cache keyed by language code

# Display results. This block runs on every rerun (including when the sidebar
# language changes). The itinerary is generated DIRECTLY in the selected
# language by the multilingual model — which yields clean, structured markdown —
# rather than translating English markdown after the fact. Results are cached
# per language so switching back and forth doesn't regenerate.
if st.session_state.get('trip'):
    trip = st.session_state.trip
    lang = st.session_state.preferred_language
    cache = st.session_state.setdefault('itineraries', {})

    if lang not in cache:
        with st.spinner("Creating your personalized itinerary..."):
            itinerary_response = generate_itinerary(
                destination=trip['destination'],
                duration=trip['duration'],
                interests=trip['interests'],
                budget=trip['budget'],
                language=LANG_NAMES.get(lang, 'English')
            )
            itinerary = itinerary_response.get('choices', [{}])[0].get('message', {}).get('content', '')

            tips_response = generate_itinerary(
                destination=trip['destination'],
                duration=1,
                interests=["Practical Tips"],
                budget=trip['budget'],
                language=LANG_NAMES.get(lang, 'English')
            )
            tips = tips_response.get('choices', [{}])[0].get('message', {}).get('content', '')
            cache[lang] = {'itinerary': itinerary, 'tips': tips}

    result = cache[lang]
    st.markdown(f"### Your Personalized Itinerary for {trip['destination']}")
    st.markdown(result['itinerary'])
    st.markdown("### Travel Tips")
    st.markdown(result['tips'])

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center'>
    <p>Powered by Sarvam AI | Your trusted travel companion</p>
</div>
""", unsafe_allow_html=True) 