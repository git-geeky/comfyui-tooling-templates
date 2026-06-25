import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts import local_restore
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

    def test_local_restore_file_is_optional_and_explicit(self):
        old_local_app_data = os.environ.get("LOCALAPPDATA")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["LOCALAPPDATA"] = tmp
            try:
                self.assertEqual(local_restore.load_restore_config(env_var="MISSING_RESTORE_ENV_FOR_TEST"), {})
            finally:
                if old_local_app_data is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old_local_app_data

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "restore.local.json"
            path.write_text(json.dumps({"paths": {"comfyui_root": "D:/ComfyUI"}}), encoding="utf-8")
            old = os.environ.get("COMFYUI_TOOLING_RESTORE_FILE")
            os.environ["COMFYUI_TOOLING_RESTORE_FILE"] = str(path)
            try:
                payload = local_restore.load_restore_config()
            finally:
                if old is None:
                    os.environ.pop("COMFYUI_TOOLING_RESTORE_FILE", None)
                else:
                    os.environ["COMFYUI_TOOLING_RESTORE_FILE"] = old

        self.assertEqual(payload["paths"]["comfyui_root"], "D:/ComfyUI")


if __name__ == "__main__":
    unittest.main()
