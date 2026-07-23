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

**Solution**: See `scripts/api_exceptions.py` for standardized error handling patterns.

**Best Practices**:

```python
import requests
from requests.exceptions import Timeout, ConnectionError
import os
from dotenv import load_dotenv

# Import custom exceptions
from scripts.api_exceptions import (
    SarvamAPIError,
    SarvamAuthenticationError,
    SarvamValidationError
)

load_dotenv()

def text_to_speech(text, lang_code):
    """Convert text to speech with proper error handling"""
    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        raise SarvamAuthenticationError("SARVAM_API_KEY not found in environment")
    
    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            "https://api.sarvam.ai/text-to-speech",
            headers=headers,
            json={
                "text": text,
                "target_language_code": lang_code,
                "model": "bulbul:v3"
            },
            timeout=30
        )
        
        if response.status_code == 401:
            raise SarvamAuthenticationError("Invalid API key")
        elif response.status_code == 429:
            raise SarvamAPIError("Rate limited. Please wait and retry.")
        elif response.status_code >= 500:
            raise SarvamAPIError(f"Server error ({response.status_code})")
        elif not response.ok:
            raise SarvamAPIError(f"API error ({response.status_code}): {response.text}")
        
        data = response.json()
        if "audios" not in data or not data["audios"]:
            raise SarvamValidationError("No audio data in response")
        
        return data["audios"][0]
    
    except (Timeout, ConnectionError) as e:
        raise SarvamAPIError(f"Network error: {e}")
    except SarvamAPIError:
        raise  # Re-raise custom exceptions
    except Exception as e:
        raise SarvamAPIError(f"Unexpected error: {e}")
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

**Run Audit Script**:

```bash
python scripts/validate_deprecated_models.py
```

This will flag any deprecated model usage in examples.

---

### **5. [MEDIUM] Fix Dark Theme Code Block Visibility (Issue #47)**

**Problem**: Code blocks have invisible text in dark theme mode.

**Solution**: See `docs/styles/dark-theme.css` for complete styling.

**Quick Fix for Streamlit Apps**:

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
- **scripts/api_exceptions.py** - Standardized error handling
- **scripts/validate_deprecated_models.py** - Model validation script
- **docs/styles/dark-theme.css** - Dark theme fixes
- **Issue #84**: https://github.com/sarvamai/sarvam-ai-cookbook/issues/84
- **Issue #47**: https://github.com/sarvamai/sarvam-ai-cookbook/issues/47
- **PR #101**: https://github.com/sarvamai/sarvam-ai-cookbook/pull/101

---

## ❓ Need Help?

- Report bugs: https://github.com/sarvamai/sarvam-ai-cookbook/issues
- Suggest fixes: https://github.com/sarvamai/sarvam-ai-cookbook/pulls
- Join Discord: https://discord.com/invite/8ka56wQaT3
