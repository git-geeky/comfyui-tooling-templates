import json
import tempfile
import unittest
from pathlib import Path

from scripts.model_inventory_audit import build_report, load_template_coverage


class Args:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class ModelInventoryAuditTests(unittest.TestCase):
    def test_template_coverage_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            payload = {
                "generated_at": "2026-01-01T00:00:00Z",
                "template_count": 1,
                "templates": [
                    {
                        "path": "example.json",
                        "models": [{"directory": "diffusion_models", "name": "example.safetensors", "installed": True}],
                    }
                ],
            }
            path.write_text("\ufeff" + json.dumps(payload), encoding="utf-8")
            coverage = load_template_coverage(path)
            self.assertTrue(coverage["available"])
            self.assertEqual(coverage["installed_refs"]["diffusion_models/example.safetensors"], ["example.json"])

    def test_report_classifies_workflow_reference_as_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            models = root / "models"
            workflows = root / "workflows"
            (models / "checkpoints").mkdir(parents=True)
            workflows.mkdir()
            model = models / "checkpoints" / "sample.safetensors"
            model.write_bytes(b"x" * 1024)
            (workflows / "sample.json").write_text('{"model": "sample.safetensors"}', encoding="utf-8")
            report = build_report(
                Args(
                    models_dir=str(models),
                    workflows_dir=str(workflows),
                    template_coverage=None,
                    large_gb=0.0,
                )
            )
            self.assertEqual(report["classification_counts"]["used"], 1)


if __name__ == "__main__":
    unittest.main()
