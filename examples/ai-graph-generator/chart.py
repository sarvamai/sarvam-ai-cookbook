import os
import openai
import streamlit as st
from dotenv import load_dotenv
import matplotlib
matplotlib.use("Agg")  # headless backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import re

load_dotenv()

# Indic scripts → (Unicode range, fonts that can render them). Matplotlib's
# default font shows boxes (□□□) for these scripts, so when a prompt is written
# in an Indic language we switch to one of these fonts to render native labels.
INDIC_SCRIPTS = [
    ("Devanagari", 0x0900, 0x097F, ["Nirmala UI", "Noto Sans Devanagari", "Mangal", "Lohit Devanagari"]),
    ("Bengali",    0x0980, 0x09FF, ["Nirmala UI", "Noto Sans Bengali", "Vrinda", "Lohit Bengali"]),
    ("Gurmukhi",   0x0A00, 0x0A7F, ["Nirmala UI", "Noto Sans Gurmukhi", "Raavi"]),
    ("Gujarati",   0x0A80, 0x0AFF, ["Nirmala UI", "Noto Sans Gujarati", "Shruti"]),
    ("Oriya",      0x0B00, 0x0B7F, ["Nirmala UI", "Noto Sans Oriya", "Kalinga"]),
    ("Tamil",      0x0B80, 0x0BFF, ["Nirmala UI", "Noto Sans Tamil", "Latha"]),
    ("Telugu",     0x0C00, 0x0C7F, ["Nirmala UI", "Noto Sans Telugu", "Gautami"]),
    ("Kannada",    0x0C80, 0x0CFF, ["Nirmala UI", "Noto Sans Kannada", "Tunga"]),
    ("Malayalam",  0x0D00, 0x0D7F, ["Nirmala UI", "Noto Sans Malayalam", "Kartika"]),
]


def detect_indic_script(text):
    """Return (script_name, font_candidates) for the dominant Indic script in
    `text`, or (None, None) if the text has no Indic characters."""
    counts = {}
    for ch in text:
        cp = ord(ch)
        for name, lo, hi, _ in INDIC_SCRIPTS:
            if lo <= cp <= hi:
                counts[name] = counts.get(name, 0) + 1
                break
    if not counts:
        return None, None
    top = max(counts, key=counts.get)
    for name, lo, hi, fonts in INDIC_SCRIPTS:
        if name == top:
            return name, fonts
    return None, None


def resolve_font(candidates):
    """Return the first font from `candidates` that is installed, else None."""
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None

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
        # Detect whether the request is written in an Indic language. If so, pick a
        # font that can render that script and ask the model to label the chart in
        # the same language — showcasing Sarvam's multilingual understanding.
        script, font_candidates = detect_indic_script(user_request)
        localize_instruction = ""
        if script:
            font = resolve_font(font_candidates)
            if font:
                matplotlib.rcParams["font.family"] = font
                localize_instruction = (
                    f"\nThe user's request is written in {script} script. Write ALL chart "
                    f"text (title, axis labels, legend, tick labels, annotations) in the "
                    f"SAME language and script as the user's request — not in English."
                )
            else:
                st.info(
                    f"No {script}-capable font is installed, so chart labels will be in "
                    f"English. Install a font like 'Noto Sans {script}' for native labels."
                )
                localize_instruction = "\nWrite all chart text in clear English."
        else:
            # Latin/English request — use matplotlib's default font.
            matplotlib.rcParams["font.family"] = matplotlib.rcParamsDefault["font.family"]

        system_message = (
            "You are an expert data visualization assistant.\n"
            "Generate only Python code without any markdown formatting or explanations.\n"
            "The code must:\n"
            "1. Import required libraries (matplotlib.pyplot, numpy, etc.)\n"
            "2. Create sample data if needed\n"
            "3. Create the visualization\n"
            "4. Save it using: plt.savefig('plot.png', bbox_inches='tight', dpi=300)\n"
            "5. Close the figure using: plt.close()\n"
            "Do NOT set or change the matplotlib font family — the app configures it.\n"
            "Do not include any markdown, comments, or explanations - just the code."
            + localize_instruction
        )

        try:
            # Get code generation from Sarvam
            response = self.client.chat.completions.create(
                model="sarvam-105b",
                max_tokens=3000,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_request}
                ]
            )

            # Extract and clean the generated code
            raw_code = response.choices[0].message.content
            self.last_generated_code = self.clean_generated_code(raw_code)

            # Execute the generated code locally to produce the chart.
            # NOTE: this runs model-generated Python in-process, so only use it
            # with trusted prompts. (The original ran it in an E2B sandbox; local
            # execution keeps the example self-contained — only a Sarvam key is needed.)
            plot_path = "plot.png"
            if os.path.exists(plot_path):
                os.remove(plot_path)

            exec(self.last_generated_code, {"__name__": "__main__"})

            # The system prompt asks the model to save to plot.png; if it didn't,
            # fall back to saving whatever figure is currently open.
            if not os.path.exists(plot_path) and plt.get_fignums():
                plt.savefig(plot_path, bbox_inches="tight", dpi=300)
            plt.close("all")

            if os.path.exists(plot_path):
                with open(plot_path, "rb") as f:
                    return f.read()

            st.warning("The code executed but didn't produce a plot. Try rephrasing your request.")
            return None

        except Exception as e:
            st.error(f"Error in visualization generation: {str(e)}")
            return None

def main():
    st.set_page_config(page_title="AI Visualization Generator", layout="wide")
    
    st.title("AI Visualization Generator 🎨")
    st.write("Describe the visualization you want, and I'll create it using the power of AI!")
    
    # Initialize session state for storing generated code and the input prompt
    if 'generated_code' not in st.session_state:
        st.session_state.generated_code = None
    if 'viz_input' not in st.session_state:
        st.session_state.viz_input = ""
    
    # Add example suggestions. Each entry is (button label, full prompt) so the
    # sidebar shows what each example does instead of a generic "Example N".
    with st.sidebar:
        st.header("Example Prompts")
        examples = [
            ("📊 Bar — quarterly revenue",
             "Create a bar chart showing quarterly revenue for five products. Use this data: Products = ['Product A', 'Product B', 'Product C', 'Product D', 'Product E'], Revenue = [12000, 9500, 7800, 10200, 8600]"),
            ("📈 Line — website traffic",
             "Generate a line chart showing website traffic over 7 days. Use: Days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], Visitors = [320, 410, 390, 450, 520, 610, 580]"),
            ("🔵 Scatter — age vs income",
             "Make a scatter plot showing the relationship between age and income. Sample data: Ages = [22, 25, 30, 35, 40, 45, 50], Income = [25000, 32000, 40000, 48000, 55000, 62000, 70000]"),
            ("🥧 Pie — smartphone market share",
             "Create a pie chart displaying the market share of 4 smartphone brands: Brands = ['Apple', 'Samsung', 'Xiaomi', 'Others'], Market Share = [40, 30, 20, 10]"),
            ("📚 Stacked bar — monthly expenses",
             "Create a stacked bar chart showing monthly expenses broken into categories. Use this data: Months = ['January', 'February', 'March'], Rent = [1200, 1200, 1200], Food = [300, 350, 320], Utilities = [150, 130, 140]"),
            ("🌊 Area — daily water usage",
             "Generate an area chart showing daily water usage over 10 days: Days = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], Usage = [120, 130, 115, 160, 170, 150, 140, 180, 190, 175]"),
            ("🇮🇳 हिंदी — तिमाही आय (बार चार्ट)",
             "पाँच उत्पादों की तिमाही आय का बार चार्ट बनाइए। डेटा: उत्पाद = ['उत्पाद A', 'उत्पाद B', 'उत्पाद C', 'उत्पाद D', 'उत्पाद E'], आय = [12000, 9500, 7800, 10200, 8600]। शीर्षक और लेबल हिंदी में रखें।"),
            ("🇮🇳 தமிழ் — வார வருகை (கோடு)",
             "7 நாட்களில் இணையதள வருகையைக் காட்டும் கோட்டு வரைபடம் உருவாக்கவும். தரவு: நாட்கள் = ['திங்கள்','செவ்வாய்','புதன்','வியாழன்','வெள்ளி','சனி','ஞாயிறு'], பார்வையாளர்கள் = [320, 410, 390, 450, 520, 610, 580]."),
        ]

        st.write("Try these examples:")
        for i, (label, prompt) in enumerate(examples):
            if st.button(label, key=f"example_{i}", use_container_width=True):
                # Populate the input box (same key the text area uses).
                st.session_state.viz_input = prompt

    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        user_request = st.text_area(
            "What kind of visualization would you like?",
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