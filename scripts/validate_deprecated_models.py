#!/usr/bin/env python3
"""Audit cookbook for deprecated Sarvam API models.

Scans all example and notebook files to detect usage of deprecated models.
Useful for ensuring cookbook examples stay up-to-date.

Usage:
    python scripts/validate_deprecated_models.py
    python scripts/validate_deprecated_models.py --fix  # Auto-replace deprecated models
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


def load_api_rules() -> Dict:
    """Load current API rules from sarvam_api_rules.json."""
    rules_path = Path(__file__).parent / "sarvam_api_rules.json"
    with open(rules_path, 'r') as f:
        return json.load(f)


def get_deprecated_models(rules: Dict) -> Dict[str, str]:
    """Extract deprecated models and their replacements.
    
    Returns:
        Dict mapping deprecated model to recommended replacement.
    """
    deprecated_map = {}
    
    # Chat models
    if 'sarvam-m' in rules['models']['chat']['deprecated']:
        deprecated_map['sarvam-m'] = 'sarvam-30b'
    
    # STT models
    if 'saarika:v2.5' in rules['models']['stt']['deprecated']:
        deprecated_map['saarika:v2.5'] = 'saaras:v3'
    if 'saarika:v2' in rules['models']['stt']['deprecated']:
        deprecated_map['saarika:v2'] = 'saaras:v3'
    
    # TTS models
    if 'bulbul:v2' in rules['models']['tts']['deprecated']:
        deprecated_map['bulbul:v2'] = 'bulbul:v3'
    
    return deprecated_map


def scan_file(file_path: Path, deprecated_models: Dict[str, str]) -> List[Tuple[int, str, str]]:
    """Scan a single file for deprecated model usage.
    
    Args:
        file_path: Path to file to scan
        deprecated_models: Map of deprecated to current models
    
    Returns:
        List of (line_number, deprecated_model, context_line) tuples
    """
    findings = []
    
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return findings
    
    for line_no, line in enumerate(content.split('\n'), 1):
        for deprecated, current in deprecated_models.items():
            if deprecated in line and 'deprecated' not in line.lower():
                findings.append((line_no, deprecated, line.strip()))
    
    return findings


def main():
    """Main audit function."""
    rules = load_api_rules()
    deprecated_models = get_deprecated_models(rules)
    
    print(f"🔍 Scanning for deprecated models: {list(deprecated_models.keys())}\n")
    
    repo_root = Path(__file__).parent.parent
    search_dirs = [repo_root / 'examples', repo_root / 'notebooks']
    
    all_findings = []
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        for file_path in search_dir.rglob('*'):
            if file_path.suffix in {'.py', '.ipynb', '.md'}:
                findings = scan_file(file_path, deprecated_models)
                if findings:
                    rel_path = file_path.relative_to(repo_root)
                    for line_no, model, context in findings:
                        all_findings.append((rel_path, line_no, model, context))
    
    if all_findings:
        print(f"❌ Found {len(all_findings)} deprecated model usage(s):\n")
        for file_path, line_no, model, context in all_findings:
            replacement = deprecated_models[model]
            print(f"  📄 {file_path}:{line_no}")
            print(f"     ❌ Deprecated: {model}")
            print(f"     ✅ Use instead: {replacement}")
            print(f"     Line: {context}")
            print()
        return 1
    else:
        print("✅ All examples use current API models!")
        return 0


if __name__ == '__main__':
    exit(main())
