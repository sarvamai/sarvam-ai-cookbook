
import sys
from pathlib import Path

# Add the presentation example directory to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRESENTATION_DIR = PROJECT_ROOT / "examples" / "AI_Presentation_Architect"
sys.path.insert(0, str(PRESENTATION_DIR))

from json_parser import parse_json_response


def test_parse_plain_json():
    response = '[{"title": "Introduction"}]'
    assert parse_json_response(response) == [
        {"title": "Introduction"}
    ]


def test_parse_markdown_json():
    response = '```json\n[{"title": "Introduction"}]\n```'
    assert parse_json_response(response) == [
        {"title": "Introduction"}
    ]


def test_parse_json_with_preamble():
    response = 'Here is your presentation:\n[{"title": "Introduction"}]'
    assert parse_json_response(response) == [
        {"title": "Introduction"}
    ]


def test_invalid_json():
    response = "This response contains no valid JSON."

    try:
        parse_json_response(response)
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "No valid JSON found" in str(error)


def test_empty_response():
    try:
        parse_json_response("")
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "empty response" in str(error)
