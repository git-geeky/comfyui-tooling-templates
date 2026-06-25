import unittest

from scripts import workflow_catalog


class WorkflowCatalogTests(unittest.TestCase):
    def test_example_catalog_summarizes(self):
        result = workflow_catalog.summarize_catalog(
            workflow_catalog.load_catalog("examples/workflow-catalog.json")
        )

        self.assertEqual(result["workflow_count"], 2)
        self.assertEqual(result["category_counts"]["text-to-image"], 1)
        self.assertEqual(result["category_counts"]["upscale"], 1)

    def test_rejects_absolute_template_path(self):
        with self.assertRaises(workflow_catalog.WorkflowCatalogError):
            workflow_catalog.validate_workflow(
                {
                    "workflow_id": "bad-path",
                    "display_name": "Bad path",
                    "category": "test",
                    "template_path": "/absolute/path.json",
                    "required_models": [],
                    "inputs": {},
                }
            )


if __name__ == "__main__":
    unittest.main()
