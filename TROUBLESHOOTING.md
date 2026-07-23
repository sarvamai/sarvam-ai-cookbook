# Troubleshooting Guide – Sarvam AI Cookbook

This guide addresses common issues found in the cookbook and provides solutions.

---

## 📋 Issues & Fixes

### **1. [URGENT] Issue #84 – Dubbing Workflow Broken (Creator Studio)**

**Problem**: After completing a dubbing job in Creator Studio, clicking "View Project" doesn't load the project. Users can't access completed dubbed videos or download content.

**Status**: This is a **Creator Studio UI issue** (web app, not cookbook code). 

**Workaround – Access Dubbed Videos Programmatically**:

If the Creator Studio UI is not working, you can access your dubbed videos via the Sarvam API:

```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("SARVAM_API_KEY")

headers = {
    "api-subscription-key": api_key,
    "Content-Type": "application/json"
}

# List all your dubbing projects
try:
    response = requests.get(
        "https://api.sarvam.ai/dubbing/projects",
        headers=headers
    )
    response.raise_for_status()
    projects = response.json()
    
    print("Your Dubbing Projects:")
    for project in projects:
        print(f"- Project ID: {project['id']}")
        print(f"  Title: {project.get('title', 'Untitled')}")
        print(f"  Status: {project.get('status', 'unknown')}")
        print(f"  Download URL: {project.get('download_url', 'N/A')}")
        print()
        
except requests.exceptions.RequestException as e:
    print(f"Error fetching projects: {e}")

# Download a specific dubbed video
project_id = "your_project_id_here"
try:
    response = requests.get(
        f"https://api.sarvam.ai/dubbing/projects/{project_id}/download",
        headers=headers,
        stream=True
    )
    response.raise_for_status()
    
    # Save the dubbed video
    with open(f"dubbed_video_{project_id}.mp4", "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"✓ Video downloaded successfully: dubbed_video_{project_id}.mp4")
    
except requests.exceptions.RequestException as e:
    print(f"Error downloading video: {e}")
```

**Report To**: File an issue directly with the Sarvam team at https://github.com/sarvamai/ (Creator Studio repo)

---

### **2. [HIGH] PR #101 – STT Model Migration (saarika:v2.5 → saaras:v3)**

**Problem**: Some notebooks and examples still use deprecated STT model `saarika:v2.5`. The current API only supports `saaras:v3`.

**Status**: PR #101 is ready but awaiting maintainer approval.

**Current Deprecated Models**:
- ❌ `saarika:v2.5` → ✅ Use `saaras:v3`
- ❌ `saarika:v2` → ✅ Use `saaras:v3`

**How to Fix In Your Notebooks**:

1. **Search for deprecated models** in your code:
```bash
grep -r "saarika" examples/ notebooks/
grep -r "bulbul:v2" examples/ notebooks/
grep -r "sarvam-m" examples/ notebooks/
```

2. **Replace with current models**:

| Old (Deprecated) | New (Current) |
|------------------|---------------|
| `saarika:v2.5` | `saaras:v3` |
| `saarika:v2` | `saaras:v3` |
| `bulbul:v2` | `bulbul:v3` |
| `sarvam-m` | `sarvam-30b` or `sarvam-105b` |

**Example Fix**:

```python
# BEFORE (Deprecated)
response = requests.post(
    'https://api.sarvam.ai/speech-to-text',
    files={'file': audio_data},
    data={'model': 'saarika:v2.5', 'language_code': 'en-IN'},
    headers=headers
)

# AFTER (Current)
response = requests.post(
    'https://api.sarvam.ai/speech-to-text',
    files={'file': audio_data},
    data={'model': 'saaras:v3', 'language_code': 'en-IN'},
    headers=headers
)
```

**Validate Your Changes**:
```bash
make check  # Runs pytest and validation scripts
```

---

### **3. [HIGH] Standardize Error Handling Across API Calls**

**Problem**: Error handling is inconsistent across examples. Some use broad `Exception` catches, others don't validate API responses properly.

**Best Practices for API Error Handling**:

#### **Create a Custom Exception Handler** (`scripts/api_exceptions.py`):

```python
class SarvamAPIError(Exception):
    """Base exception for Sarvam API errors"""
    pass

class SarvamAuthenticationError(SarvamAPIError):
    """Raised when API key is missing or invalid"""
    pass

class SarvamRateLimitError(SarvamAPIError):
    """Raised when rate limit is exceeded (429)"""
    pass

class SarvamValidationError(SarvamAPIError):
    """Raised when response doesn't match expected structure"""
    pass

class SarvamServerError(SarvamAPIError):
    """Raised for 5xx server errors"""
    pass
```

#### **Use Proper Error Handling** in your code:

```python
import requests
from requests.exceptions import Timeout, ConnectionError
import os
from dotenv import load_dotenv

load_dotenv()

# Custom exceptions (import from scripts/api_exceptions.py)
class SarvamAPIError(Exception): pass
class SarvamAuthenticationError(SarvamAPIError): pass
class SarvamValidationError(SarvamAPIError): pass

def make_sarvam_api_call(endpoint, method="POST", **kwargs):
    """
    Safely call Sarvam API with proper error handling.
    
    Args:
        endpoint: API endpoint URL
        method: HTTP method (GET, POST, etc.)
        **kwargs: Additional arguments for requests
    
    Returns:
        dict: Parsed JSON response
    
    Raises:
        SarvamAuthenticationError: If API key is missing
        SarvamValidationError: If response structure is invalid
        SarvamAPIError: For other API errors
    """
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise SarvamAuthenticationError("SARVAM_API_KEY not found in environment")
    
    headers = kwargs.get("headers", {})
    headers["api-subscription-key"] = api_key
    headers["Content-Type"] = "application/json"
    kwargs["headers"] = headers
    
    try:
        if method.upper() == "POST":
            response = requests.post(endpoint, timeout=30, **kwargs)
        elif method.upper() == "GET":
            response = requests.get(endpoint, timeout=30, **kwargs)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Handle status codes
        if response.status_code == 401:
            raise SarvamAuthenticationError(f"Authentication failed: {response.text}")
        elif response.status_code == 429:
            raise SarvamAPIError("Rate limited. Please wait and retry.")
        elif response.status_code >= 500:
            raise SarvamAPIError(f"Server error ({response.status_code}): {response.text}")
        elif not response.ok:
            raise SarvamAPIError(f"API error ({response.status_code}): {response.text}")
        
        # Validate response structure
        try:
            data = response.json()
        except ValueError:
            raise SarvamValidationError(f"Invalid JSON response: {response.text}")
        
        return data
    
    except (Timeout, ConnectionError) as e:
        raise SarvamAPIError(f"Network error: {e}")
    except SarvamAPIError:
        raise  # Re-raise custom exceptions
    except Exception as e:
        raise SarvamAPIError(f"Unexpected error: {e}")


# Example Usage:
def text_to_speech(text, lang_code):
    """Convert text to speech with proper error handling"""
    try:
        response = make_sarvam_api_call(
            "https://api.sarvam.ai/text-to-speech",
            json={
                "text": text,
                "target_language_code": lang_code,
                "model": "bulbul:v3"
            }
        )
        
        # Validate response has required fields
        if "audios" not in response or not response["audios"]:
            raise SarvamValidationError("No audio data in response")
        
        return response["audios"][0]
    
    except SarvamAuthenticationError as e:
        print(f"❌ Authentication error: {e}")
        raise
    except SarvamValidationError as e:
        print(f"❌ Invalid response: {e}")
        raise
    except SarvamAPIError as e:
        print(f"❌ API error: {e}")
        raise
```

---

### **4. [MEDIUM] Validate All Examples Use Current API Models**

**Problem**: Some examples reference deprecated models.

**Current Valid Models** (from `scripts/sarvam_api_rules.json`):

```json
{
  "chat": {
    "allowed": ["sarvam-30b", "sarvam-105b"],
    "deprecated": ["sarvam-m"]
  },
  "stt": {
    "allowed": ["saaras:v3"],
    "deprecated": ["saarika:v2.5", "saarika:v2"]
  },
  "tts": {
    "allowed": ["bulbul:v3", "bulbul:v3-beta"],
    "deprecated": ["bulbul:v2"]
  },
  "translate": {
    "allowed": ["mayura:v1", "sarvam-translate:v1"],
    "deprecated": []
  }
}
```

**Audit Script** – Run this to find deprecated models:

```python
import json
import os
import re
from pathlib import Path

# Load current API rules
with open("scripts/sarvam_api_rules.json") as f:
    rules = json.load(f)

# Collect all deprecated models
deprecated = set()
for api_type, models in rules["models"].items():
    deprecated.update(models.get("deprecated", []))

print(f"Deprecated models to replace: {deprecated}\n")

# Search codebase
found_issues = []
for ext in ["*.py", "*.ipynb", "*.md"]:
    for file in Path("examples").rglob(ext):
        content = file.read_text(encoding="utf-8", errors="ignore")
        for model in deprecated:
            if model in content:
                found_issues.append((file, model))
                print(f"❌ {file}: uses deprecated model '{model}'")

if not found_issues:
    print("✅ All examples use current API models!")
```

**Fix Birthday Song Generator** (uses `sarvam-m`):

```python
# examples/Birthday_Song_Generator/README.md - Line 16

# BEFORE:
# Uses those answers to generate a **12-line personalized birthday song** using SarvamAI's `sarvam-m` model.

# AFTER:
# Uses those answers to generate a **12-line personalized birthday song** using SarvamAI's `sarvam-105b` model.
```

---

### **5. [MEDIUM] Fix Dark Theme Code Block Visibility (Issue #47)**

**Problem**: Code blocks have invisible text in dark theme mode.

**Root Cause**: CSS missing contrast or dark background for code blocks in dark mode.

**Solution – Add Dark Theme CSS**:

Create/update `docs/styles/dark-theme.css` (if using web documentation):

```css
/* Dark Theme Code Block Styling */

/* For Markdown/Documentation sites */
@media (prefers-color-scheme: dark) {
    /* Code blocks in dark mode */
    code,
    pre,
    .highlight {
        background-color: #1e1e1e !important;
        color: #e0e0e0 !important;
    }
    
    pre {
        border: 1px solid #404040;
        padding: 12px;
        border-radius: 4px;
    }
    
    pre code {
        color: #d4d4d4 !important;
    }
    
    /* Syntax highlighting for code blocks */
    .hljs-string { color: #ce9178 !important; }
    .hljs-number { color: #b5cea8 !important; }
    .hljs-literal { color: #569cd6 !important; }
    .hljs-attr { color: #9cdcfe !important; }
    .hljs-title { color: #dcdcaa !important; }
    .hljs-built_in { color: #4ec9b0 !important; }
    .hljs-keyword { color: #569cd6 !important; }
    .hljs-comment { color: #6a9955 !important; }
    .hljs-function { color: #dcdcaa !important; }
}

/* For Jupyter Notebooks */
@media (prefers-color-scheme: dark) {
    .highlight pre {
        background-color: #272822 !important;
        color: #f8f8f2 !important;
    }
    
    .output_text pre {
        background-color: #1e1e1e !important;
        color: #cccccc !important;
        border: 1px solid #404040;
    }
}

/* For Streamlit apps */
@media (prefers-color-scheme: dark) {
    .stCode {
        background-color: #1e1e1e !important;
    }
    
    .stCode code {
        color: #d4d4d4 !important;
    }
}

/* For web apps using highlight.js */
.hljs-dark {
    background: #1e1e1e !important;
    color: #e0e0e0 !important;
}

.hljs-dark .hljs-string { color: #ce9178; }
.hljs-dark .hljs-number { color: #b5cea8; }
.hljs-dark .hljs-literal { color: #569cd6; }
.hljs-dark .hljs-attr { color: #9cdcfe; }
.hljs-dark .hljs-title { color: #dcdcaa; }
```

**For Streamlit Apps** (add to your Streamlit app):

```python
import streamlit as st

# Add dark theme CSS
dark_theme_css = """
<style>
    @media (prefers-color-scheme: dark) {
        .stCode {
            background-color: #1e1e1e !important;
        }
        .stCode code {
            color: #d4d4d4 !important;
        }
    }
</style>
"""

st.markdown(dark_theme_css, unsafe_allow_html=True)
```

**For HTML/JavaScript Pages**:

```html
<!DOCTYPE html>
<html>
<head>
    <!-- Use highlight.js for syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css">
    <link rel="stylesheet" href="docs/styles/dark-theme.css">
</head>
<body>
    <pre><code class="language-python">
# Your code here
print("Hello, Sarvam!")
    </code></pre>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script>hljs.highlightAll();</script>
</body>
</html>
```

---

## 📊 Summary Table

| Issue | Priority | Type | Location | Status |
|-------|----------|------|----------|--------|
| Dubbing workflow | URGENT | Product bug | Creator Studio | External (report to Sarvam) |
| STT model migration | HIGH | Deprecation | PR #101 | Awaiting merge |
| Error handling | HIGH | Code quality | Multiple examples | Create standards |
| Deprecated models | MEDIUM | Validation | Birthday Song example | Fix required |
| Dark theme CSS | MEDIUM | UI/UX | Documentation | CSS fix needed |

---

## 🔗 References

- **CONTRIBUTING.md** - Contribution guidelines
- **scripts/sarvam_api_rules.json** - Current API models/language codes
- **CONTRIBUTING.md#Sarvam-API-Standards** - Preferred models and endpoints
- **Issue #84**: https://github.com/sarvamai/sarvam-ai-cookbook/issues/84
- **Issue #47**: https://github.com/sarvamai/sarvam-ai-cookbook/issues/47
- **PR #101**: https://github.com/sarvamai/sarvam-ai-cookbook/pull/101

---

## ❓ Need Help?

- Report bugs: https://github.com/sarvamai/sarvam-ai-cookbook/issues
- Suggest fixes: https://github.com/sarvamai/sarvam-ai-cookbook/pulls
- Join Discord: https://discord.com/invite/8ka56wQaT3
