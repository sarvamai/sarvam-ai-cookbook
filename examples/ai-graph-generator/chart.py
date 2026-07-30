import os
import openai
import streamlit as st
from dotenv import load_dotenv
from e2b_code_interpreter import Sandbox
import base64
import re

load_dotenv()

class VisualizationAgent:
    def __init__(self):
        self.client = openai.OpenAI(
            base_url="https://api.sarvam.ai/v1/",
            api_key=os.environ.get("SARVAM_API_KEY")
        )
        self.last_generated_code = None
        
    def clean_generated_code(self, code):
        """Clean up the generated code by removing markdown and code fence markers"""
        # Remove markdown code fence markers
        code = re.sub(r'```\w*\n?', '', code)
        code = code.strip()
        # Normalize indentation to use spaces
        lines = code.splitlines()
        cleaned_lines = []
        for line in lines:
            # Replace tabs with spaces and strip trailing whitespace
            cleaned_line = line.replace('\t', '    ').rstrip()
            cleaned_lines.append(cleaned_line)
        return '\n'.join(cleaned_lines)
        
    def generate_visualization(self, user_request):
        system_message = """You are an expert data visualization assistant. 
        Generate only Python code without any markdown formatting or explanations.
        The code must:
        1. Import required libraries (matplotlib.pyplot, numpy, etc.)
        2. Create sample data if needed
        3. Create the visualization
        4. Save it using: plt.savefig('plot.png', bbox_inches='tight', dpi=300)
        5. Close the figure using: plt.close()
        
        Do not include any markdown, comments, or explanations - just the code."""
        
        try:
            # Get code generation from Sarvam
            response = self.client.chat.completions.create(
                model="sarvam-m",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_request}
                ]
            )
            
            # Extract and clean the generated code
            raw_code = response.choices[0].message.content
            self.last_generated_code = self.clean_generated_code(raw_code)
            
            # Create sandbox and execute code
            sandbox = Sandbox(api_key=os.environ.get("E2B_API_KEY"))
            
            # Prepare the code with proper imports and error handling
            visualization_code = """
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import sys

def generate_plot():
{code}

try:
    generate_plot()
    print('Visualization completed successfully')
except Exception as e:
    print(f'Error in visualization: {{str(e)}}', file=sys.stderr)
    sys.exit(1)
""".format(code='\n'.join('    ' + line for line in self.last_generated_code.splitlines()))

            # Execute code and get results
            execution = sandbox.run_code(visualization_code)
            
            if execution.error:
                print(f"Code execution error: {execution.error}")
                st.error(f"Error executing code: {execution.error.value}")
                return None

            # Look for the PNG file in results
            for result in execution.results:
                if result.png:
                    return base64.b64decode(result.png)
            
            if not any(result.png for result in execution.results):
                st.warning("No visualization was generated. The code executed successfully but didn't create a plot.")
            
            return None
                
        except Exception as e:
            st.error(f"Error in visualization generation: {str(e)}")
            return None

def main():
    st.set_page_config(page_title="AI Visualization Generator", layout="wide")
    
    st.title("AI Visualization Generator 🎨")
    st.write("Describe the visualization you want, and I'll create it using the power of AI!")
    
    # Initialize session state for storing generated code
    if 'generated_code' not in st.session_state:
        st.session_state.generated_code = None
    
    # Add example suggestions
    with st.sidebar:
        st.header("Example Prompts")
        examples = [
    "Create a bar chart showing quarterly revenue for five products. Use this data: Products = ['Product A', 'Product B', 'Product C', 'Product D', 'Product E'], Revenue = [12000, 9500, 7800, 10200, 8600]",

    "Generate a line chart showing website traffic over 7 days. Use: Days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], Visitors = [320, 410, 390, 450, 520, 610, 580]",

    "Make a scatter plot showing the relationship between age and income. Sample data: Ages = [22, 25, 30, 35, 40, 45, 50], Income = [25000, 32000, 40000, 48000, 55000, 62000, 70000]",

    "Create a pie chart displaying the market share of 4 smartphone brands: Brands = ['Apple', 'Samsung', 'Xiaomi', 'Others'], Market Share = [40, 30, 20, 10]",

    "Create a stacked bar chart showing monthly expenses broken into categories. Use this data: Months = ['January', 'February', 'March'], Rent = [1200, 1200, 1200], Food = [300, 350, 320], Utilities = [150, 130, 140]",

    "Generate an area chart showing daily water usage over 10 days: Days = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], Usage = [120, 130, 115, 160, 170, 150, 140, 180, 190, 175]"
]

        st.write("Try these examples:")
        for i, example in enumerate(examples):
            if st.button(f"Example {i+1}", key=f"example_{i}"):
                st.session_state.user_request = example
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        user_request = st.text_area(
            "What kind of visualization would you like?",
            value=st.session_state.get('user_request', ""),
            height=100,
            key="viz_input"
        )
        
        if st.button("🎨 Generate Visualization", key="generate_btn"):
            if user_request:
                with st.spinner("🎨 Creating your visualization..."):
                    agent = VisualizationAgent()
                    visualization_data = agent.generate_visualization(user_request)
                    
                    if visualization_data:
                        st.image(visualization_data, caption="Generated Visualization", use_container_width=True)
                        st.session_state.generated_code = agent.last_generated_code
                    else:
                        st.error("Failed to generate visualization. Please try again with a different request.")
            else:
                st.warning("Please enter a visualization request.")
    
    with col2:
        st.markdown("""
        💡 **Tips for better results:**
        - Be specific about the type of chart you want
        - Mention if you want specific colors or styles
        - Specify any data ranges or categories
        - Ask for labels and legends if needed
        """)
        
        if st.session_state.generated_code:
            st.subheader("Generated Python Code")
            st.code(st.session_state.generated_code, language="python")

if __name__ == "__main__":
    main()