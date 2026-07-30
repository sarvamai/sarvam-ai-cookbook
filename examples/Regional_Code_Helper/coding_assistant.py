import requests
import json
import streamlit as st
from config import (
    SARVAM_API_KEY,
    SARVAM_API_URL,
    SUPPORTED_LANGUAGES,
    SYSTEM_PROMPTS
)

class CodingAssistant:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {SARVAM_API_KEY}",
            "Content-Type": "application/json"
        }

    def call_sarvam_api(self, messages, temperature=0.7):
        """Make a call to the Sarvam API."""
        try:
            payload = {
                "messages": messages,
                "model": "sarvam-m",
                "temperature": temperature
            }
            
            response = requests.post(
                SARVAM_API_URL,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                return f"Error: {response.status_code} - {response.text}"
                
        except Exception as e:
            return f"Error calling Sarvam API: {str(e)}"

    def explain_concept(self, concept, language):
        """Explain a programming concept in the selected language.Don't use English language. Keep code elements in the same language as the code."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS['concept_explanation']},
            {"role": "user", "content": f"Explain the concept of {concept} in {SUPPORTED_LANGUAGES[language]}. "
             f"Also provide a simple code example."}
        ]
        return self.call_sarvam_api(messages)

    def debug_code(self, code, language):
        """Debug the provided code and explain in the selected language. Don't use English language. Keep code elements in the same language as the code."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS['code_debugging']},
            {"role": "user", "content": f"Debug this code and explain in {SUPPORTED_LANGUAGES[language]}:\n{code}"}
        ]
        return self.call_sarvam_api(messages)

    def provide_code_sample(self, topic, language):
        """Provide a code sample for the requested topic.Don't use English language. Keep code elements in the same language as the code."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS['code_sample']},
            {"role": "user", "content": f"Provide a code sample for {topic} with explanations in {SUPPORTED_LANGUAGES[language]}"}
        ]
        return self.call_sarvam_api(messages)

def main():
    st.title("AI Coding Assistant for Indian Students")
    
    # Initialize the assistant
    assistant = CodingAssistant()
    
    # Language selection
    language = st.selectbox(
        "Select your preferred language",
        options=list(SUPPORTED_LANGUAGES.keys()),
        format_func=lambda x: SUPPORTED_LANGUAGES[x]
    )
    
    # Feature selection
    feature = st.radio(
        "What would you like to do?",
        ["Explain a Concept", "Debug Code", "Get Code Sample"]
    )
    
    if feature == "Explain a Concept":
        concept = st.text_input("Enter the programming concept you want to learn about")
        if st.button("Explain"):
            with st.spinner("Generating explanation..."):
                explanation = assistant.explain_concept(concept, language)
                st.markdown(explanation)
    
    elif feature == "Debug Code":
        code = st.text_area("Paste your code here")
        if st.button("Debug"):
            with st.spinner("Analyzing code..."):
                debug_result = assistant.debug_code(code, language)
                st.markdown(debug_result)
    
    else:  # Get Code Sample
        topic = st.text_input("Enter the topic or problem you want a code sample for")
        if st.button("Get Sample"):
            with st.spinner("Generating code sample..."):
                sample = assistant.provide_code_sample(topic, language)
                st.markdown(sample)

if __name__ == "__main__":
    main()