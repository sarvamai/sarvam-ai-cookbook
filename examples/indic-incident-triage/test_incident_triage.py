"""Offline regression tests; no Sarvam key or network connection needed."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from pydantic import ValidationError

from incident_triage import TRIAGE_JSON_SCHEMA, classify_incident


VALID_OUTPUT = {
    "language": "hi-IN",
    "category": "network",
    "urgency": "high",
    "summary": "The office Wi-Fi has been unavailable for two hours.",
    "needs_follow_up": True,
    "missing_details": ["affected location"],
}


def fake_client(payload):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=payload))]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=Mock(return_value=response)))
    return client


class IncidentTriageTests(unittest.TestCase):
    def test_api_request_uses_strict_schema_and_current_model(self):
        client = fake_client(json.dumps(VALID_OUTPUT))
        result = classify_incident(client, "  ऑफिस का वाई-फ़ाई बंद है  ")
        self.assertEqual(result.category, "network")
        kwargs = client.chat.completions.call_args.kwargs
        self.assertEqual(kwargs["model"], "sarvam-105b")
        self.assertEqual(kwargs["messages"][1]["content"], "ऑफिस का वाई-फ़ाई बंद है")
        self.assertTrue(kwargs["response_format"]["json_schema"]["strict"])
        self.assertEqual(kwargs["response_format"]["json_schema"]["schema"], TRIAGE_JSON_SCHEMA)

    def test_valid_tamil_example(self):
        output = {**VALID_OUTPUT, "language": "ta-IN", "urgency": "medium"}
        result = classify_incident(fake_client(json.dumps(output)), "எனது கணினி திறக்கவில்லை")
        self.assertEqual(result.language, "ta-IN")

    def test_rejects_empty_input_before_api_call(self):
        client = fake_client(json.dumps(VALID_OUTPUT))
        with self.assertRaisesRegex(ValueError, "non-empty"):
            classify_incident(client, "  ")
        client.chat.completions.assert_not_called()

    def test_rejects_oversized_input_before_api_call(self):
        client = fake_client(json.dumps(VALID_OUTPUT))
        with self.assertRaisesRegex(ValueError, "2000"):
            classify_incident(client, "a" * 2001)
        client.chat.completions.assert_not_called()

    def test_rejects_invalid_json(self):
        with self.assertRaises(json.JSONDecodeError):
            classify_incident(fake_client("not-json"), "Wi-Fi is down")

    def test_rejects_missing_response_content(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            classify_incident(fake_client(None), "Wi-Fi is down")

    def test_rejects_unsupported_category(self):
        invalid = {**VALID_OUTPUT, "category": "billing"}
        with self.assertRaises(ValidationError):
            classify_incident(fake_client(json.dumps(invalid)), "Wi-Fi is down")

    def test_rejects_extra_fields(self):
        invalid = {**VALID_OUTPUT, "secret_note": "extra"}
        with self.assertRaises(ValidationError):
            classify_incident(fake_client(json.dumps(invalid)), "Wi-Fi is down")

    def test_rejects_non_boolean_follow_up(self):
        invalid = {**VALID_OUTPUT, "needs_follow_up": "yes"}
        with self.assertRaises(ValidationError):
            classify_incident(fake_client(json.dumps(invalid)), "Wi-Fi is down")

    def test_rejects_overlong_summary(self):
        invalid = {**VALID_OUTPUT, "summary": "x" * 281}
        with self.assertRaises(ValidationError):
            classify_incident(fake_client(json.dumps(invalid)), "Wi-Fi is down")


if __name__ == "__main__":
    unittest.main()
