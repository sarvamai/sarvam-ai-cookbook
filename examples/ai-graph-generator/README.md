## AI Graph Generator
An intelligent graph and chart generator that transforms natural language prompts into visual representations using Python and Matplotlib, powered by Sarvam AI. This tool can be run locally or within a secure E2B sandbox environment.

### ✨ Features
- Intelligent Conversion: Converts simple English prompts into detailed visual charts.
- Diverse Chart Types: Supports the generation of bar, line, pie, and scatter plots.
- AI-Powered Understanding: Leverages the Sarvam AI API to accurately interpret user intent.
- Flexible Data Handling: Includes capabilities for random and sample data generation.
- Secure Cloud Execution: Fully compatible with E2B Sandboxes for secure, cloud-based operations.

### 🚀 Getting Started

**Prerequisites**
Before you begin, ensure you have:

- Python 3.7 or newer installed.
- A valid Sarvam AI API key.
- A valid E2B APi KEY 

**Installation**

```
git clone https://github.com/sarvamai/sarvam-ai-cookbook.git
cd sarvam-ai-cookbook/examples/ai-graph-generator
pip install -r requirements.txt
```

**Configure your API key:**

```
cp .env.example .env
Open .env and add your SARVAM_API_KEY and E2B_API_KEY.
```

**Run the script:**

```
streamlit run  chart.py
```

### 📌 Example Prompts

Here are some examples of prompts you can use:

"Create a bar chart showing sales data for different products"

"Generate a line plot showing temperature trends over time"

"Make a scatter plot showing height vs weight"

"Create a pie chart showing market share of companies"

### 🖼️ Example Output

The script will generate and save your chart as output.png in the current directory.

### 📦 Files Included

```
ai-graph-generator/
├── chart.py               # The main script for chart generation.
├── .env.example           # Template file for your Sarvam API key.
├── requirements.txt       # Lists all Python dependencies.
├── README.md              # This documentation file.
└── sample-chart.png       # An optional sample chart output.
```

### 📚 Additional Resources

Sarvam Docs: docs.sarvam.ai

Sarvam API Dashboard: dashboard.sarvam.ai

Join Sarvam Discord: discord.gg/hTuVuPNF

E2B Developer Sandboxes: e2b.dev

### 🪪 License

This project is released under the MIT License. Feel free to use, extend, and contribute back!
