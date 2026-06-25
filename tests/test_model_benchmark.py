import json
import tempfile
import unittest
from pathlib import Path

from scripts import model_benchmark


class ModelBenchmarkTests(unittest.TestCase):
    def test_summarize_runs_ranks_by_weighted_average(self):
        runs = [
            {
                "candidate_id": "candidate-a",
                "prompt_id": "p1",
                "scores": {"human_preference": 0.9, "prompt_adherence": 0.8},
            },
            {
                "candidate_id": "candidate-b",
                "prompt_id": "p1",
                "scores": {"human_preference": 0.4, "prompt_adherence": 0.9},
            },
        ]

        result = model_benchmark.summarize_runs(runs)

        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["ranking"][0]["candidate_id"], "candidate-a")

    def test_load_runs_accepts_runs_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.json"
            path.write_text(
                json.dumps(
                    {
                        "runs": [
                            {
                                "candidate_id": "candidate-a",
                                "prompt_id": "p1",
                                "scores": {"technical_quality": 0.7},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            runs = model_benchmark.load_runs(path)

        self.assertEqual(runs[0]["candidate_id"], "candidate-a")

    def test_invalid_score_range_rejected(self):
        with self.assertRaises(model_benchmark.BenchmarkError):
            model_benchmark.validate_run(
                {"candidate_id": "candidate-a", "prompt_id": "p1", "scores": {"x": 2.0}}
            )


if __name__ == "__main__":
    unittest.main()

