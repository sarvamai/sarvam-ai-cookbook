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
            "Content-Type": "application/x-www-form-urlencoded" 
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
        """Analyze text using text analytics API."""
        url = f"{self.base_url}/text-analytics"
        
        # Define questions as per API documentation
        questions = [
            {
                "id": "q001",
                "text": "What is the overall sentiment of this feedback?",
                "type": "enum",
                "properties": {
                    "options": ["positive", "negative", "neutral"]
                }
            },
            {
                "id": "q002",
                "text": "What is the main topic of this feedback?",
                "type": "short answer"
            },
            {
                "id": "q003",
                "text": "What are the key points mentioned in this feedback?",
                "type": "long answer"
            },
            {
                "id": "q004",
                "text": "What areas of improvement are mentioned in this feedback?",
                "type": "long answer"
            }
        ]
        
        # Format data as per API documentation
        data = {
            "text": text,
            "questions": json.dumps(questions)  # Convert questions to JSON string
        }
        
        # Set headers for this specific request
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        response = requests.post(
            url,
            headers=headers,
            data=data  
        )
        
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            response.raise_for_status()
            
        return response.json()

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
                
                # Extract answers
                answers = {ans['id']: ans['response'] for ans in analysis['answers']}
                
                results.append({
                    'original_feedback': feedback,
                    'detected_language': lang_code,
                    'detected_script': script_code,
                    'translated_feedback': translated,
                    'sentiment': answers.get('q001'),  # Updated to use question IDs
                    'main_topic': answers.get('q002'),
                    'key_points': answers.get('q003'),
                    'improvement_areas': answers.get('q004')
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