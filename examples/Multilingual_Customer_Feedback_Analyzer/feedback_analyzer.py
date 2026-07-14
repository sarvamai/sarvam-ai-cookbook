import argparse
import csv
import json
import requests
from typing import List, Dict
import pandas as pd
from collections import Counter

class FeedbackAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sarvam.ai"
        self.headers = {
            "api-subscription-key": api_key,
            "Content-Type": "application/json"
        }

    def detect_language(self, text: str) -> Dict:
        """Detect the language and script of the given text."""
        url = f"{self.base_url}/text-lid"
        headers = {**self.headers, "Content-Type": "application/json"}  
        response = requests.post(
            url,
            headers=headers,
            json={"input": text}
        )
        response.raise_for_status()
        return response.json()

    def translate_text(self, text: str, source_lang: str) -> str:
        """Translate text from source language to English."""
        # If source language is already English, return the original text
        if source_lang == "en-IN":
            return text
            
        url = f"{self.base_url}/translate"
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Format request body as per API documentation
        payload = {
            "input": text,
            "source_language_code": source_lang,
            "target_language_code": "en-IN"
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            print(f"Translation error response: {response.text}")
            response.raise_for_status()
            
        return response.json()["translated_text"]

    def analyze_text(self, text: str) -> Dict:
        """Analyze feedback using the Chat Completions API.

        Returns a dict with keys: sentiment, main_topic, key_points,
        improvement_areas. (Sarvam has no dedicated text-analytics endpoint,
        so we prompt a chat model to return structured JSON.)
        """
        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        system_prompt = (
            "You are a customer-feedback analyst. Analyze the feedback and respond with "
            "ONLY a valid JSON object (no markdown, no code fences) with exactly these keys:\n"
            '- "sentiment": one of "positive", "negative", "neutral"\n'
            '- "main_topic": a short phrase naming the main topic\n'
            '- "key_points": the key points mentioned in the feedback\n'
            '- "improvement_areas": areas of improvement mentioned, or "None" if none'
        )

        payload = {
            "model": "sarvam-105b",
            "max_tokens": 2000,  # reasoning model needs budget or it returns empty content
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            response.raise_for_status()

        content = (response.json()["choices"][0]["message"]["content"] or "").strip()

        # Strip code fences if the model wrapped the JSON despite instructions.
        if content.startswith("```"):
            content = content.strip("`").lstrip()
            if content.lower().startswith("json"):
                content = content[4:].lstrip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fall back gracefully if the model didn't return clean JSON.
            return {
                "sentiment": None,
                "main_topic": None,
                "key_points": content,
                "improvement_areas": None,
            }

    def process_feedback(self, feedback_file: str) -> pd.DataFrame:
        """Process all feedback from the CSV file."""
        results = []
        
        with open(feedback_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                feedback = row['feedback']
                
                # Detect language and script
                lang_info = self.detect_language(feedback)
                lang_code = lang_info["language_code"]
                script_code = lang_info["script_code"]
                
                # Translate to English
                translated = self.translate_text(feedback, lang_code)
                
                # Analyze the translated text
                analysis = self.analyze_text(translated)

                results.append({
                    'original_feedback': feedback,
                    'detected_language': lang_code,
                    'detected_script': script_code,
                    'translated_feedback': translated,
                    'sentiment': analysis.get('sentiment'),
                    'main_topic': analysis.get('main_topic'),
                    'key_points': analysis.get('key_points'),
                    'improvement_areas': analysis.get('improvement_areas')
                })
        
        return pd.DataFrame(results)

def main():
    parser = argparse.ArgumentParser(description='Analyze multilingual customer feedback')
    parser.add_argument('--api-key', required=True, help='Sarvam API key')
    parser.add_argument('--input-file', default='dummy.csv', help='Input CSV file with feedback')
    parser.add_argument('--output-file', default='feedback_analysis.csv', help='Output CSV file for analysis results')
    args = parser.parse_args()

    analyzer = FeedbackAnalyzer(args.api_key)
    
    try:
        # Process feedback
        results_df = analyzer.process_feedback(args.input_file)
        
        # Save results
        results_df.to_csv(args.output_file, index=False)
        
        # Print summary
        print("\nFeedback Analysis Summary:")
        print("-" * 50)
        print(f"Total feedback analyzed: {len(results_df)}")
        print("\nLanguage Distribution:")
        print(results_df['detected_language'].value_counts())
        print("\nScript Distribution:")
        print(results_df['detected_script'].value_counts())
        print("\nSentiment Distribution:")
        print(results_df['sentiment'].value_counts())
        print("\nTop Main Topics:")
        print(results_df['main_topic'].value_counts().head())
        print("\nCommon Improvement Areas:")
        print(results_df['improvement_areas'].value_counts().head())
        
    except Exception as e:
        print(f"Error processing feedback: {str(e)}")

if __name__ == "__main__":
    main() 