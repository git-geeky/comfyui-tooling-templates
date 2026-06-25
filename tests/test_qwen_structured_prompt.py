import json
import unittest

from scripts import qwen_structured_prompt as qsp


class StructuredPromptTests(unittest.TestCase):
    def test_plain_prompt_wrapper_normalizes_fields(self):
        payload = qsp.structured_prompt_from_text(
            "  architectural study  ",
            style_domain="PHOTOREAL",
            safety_scope="sfw",
            aspect_hint="LANDSCAPE",
            era="historical",
            required_elements=["timber"],
        )

        self.assertEqual(payload["positive_prompt"], "architectural study")
        self.assertEqual(payload["style_domain"], "photoreal")
        self.assertEqual(payload["aspect_hint"], "landscape")
        self.assertEqual(payload["required_elements"], ["timber"])

    def test_template_registry_loads_default_template(self):
        payload = qsp.load_template("architecture-wood-joinery")

        self.assertEqual(payload["prompt_hardener_version"], qsp.PROMPT_PROFILE_VERSION)
        self.assertEqual(payload["safety_scope"], "sfw")
        self.assertIn("wooden architecture", payload["positive_prompt"])

    def test_invalid_json_rejected(self):
        with self.assertRaises(qsp.StructuredPromptError):
            qsp.load_structured_prompt("{not-json")

    def test_dump_roundtrip_is_valid_json(self):
        payload = qsp.load_template("product-text-poster")
        text = qsp.dumps_structured_prompt(payload)

        self.assertEqual(json.loads(text)["exact_text"], ["SAMPLE SOAP"])


if __name__ == "__main__":
    unittest.main()
