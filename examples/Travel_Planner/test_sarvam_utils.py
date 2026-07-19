import unittest
from unittest.mock import patch

import sarvam_utils


class FakeResponse:
    def json(self):
        return {"choices": [{"message": {"content": "tips"}}]}


class GenerateTravelTipsTest(unittest.TestCase):
    @patch("sarvam_utils.requests.post")
    def test_generate_travel_tips_uses_tip_specific_prompt(self, mock_post):
        mock_post.return_value = FakeResponse()

        response = sarvam_utils.generate_travel_tips(
            destination="Mysuru",
            budget="Budget",
            language="kn"
        )

        self.assertEqual(response, {"choices": [{"message": {"content": "tips"}}]})
        mock_post.assert_called_once()

        call_args = mock_post.call_args
        self.assertEqual(call_args.args[0], f"{sarvam_utils.BASE_URL}/chat/completions")

        payload = call_args.kwargs["json"]
        system_prompt = payload["messages"][0]["content"]
        user_prompt = payload["messages"][1]["content"]

        self.assertIn("travel tips in kn", system_prompt)
        self.assertIn("Mysuru", system_prompt)
        self.assertIn("Budget", system_prompt)
        self.assertIn("Best time to visit", system_prompt)
        self.assertIn("Local transportation options", system_prompt)
        self.assertIn("Cultural etiquette and customs", system_prompt)
        self.assertIn("Safety considerations", system_prompt)
        self.assertIn("Essential local phrases", system_prompt)
        self.assertIn("Packing recommendations", system_prompt)
        self.assertNotIn("Daily activities with timing", system_prompt)
        self.assertEqual(user_prompt, "Please provide practical travel tips for Mysuru.")


if __name__ == "__main__":
    unittest.main()
