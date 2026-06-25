#!/usr/bin/env python3
"""Generic benchmark ranking helpers for ComfyUI-style candidate outputs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

try:
    from . import local_restore
except ImportError:
    import local_restore  # type: ignore


DEFAULT_WEIGHTS = {
    "human_preference": 0.35,
    "preference_model": 0.25,
    "prompt_adherence": 0.20,
    "technical_quality": 0.10,
    "text_fidelity": 0.10,
}


class BenchmarkError(ValueError):
    """Raised when benchmark input is invalid."""


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def default_records_path() -> Path | None:
    restore = local_restore.load_restore_config()
    paths = restore.get("paths", {}) if isinstance(restore, Mapping) else {}
    value = paths.get("benchmark_records") if isinstance(paths, Mapping) else None
    return Path(str(value)).expanduser() if value else None


def normalize_weight_map(weights: Mapping[str, float] | None = None) -> dict[str, float]:
    raw = dict(DEFAULT_WEIGHTS if weights is None else weights)
    total = sum(float(value) for value in raw.values() if float(value) > 0)
    if total <= 0:
        raise BenchmarkError("at least one positive weight is required")
    return {key: float(value) / total for key, value in raw.items() if float(value) > 0}


def validate_run(record: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = str(record.get("candidate_id") or "").strip()
    prompt_id = str(record.get("prompt_id") or "").strip()
    if not candidate_id:
        raise BenchmarkError("run missing candidate_id")
    if not prompt_id:
        raise BenchmarkError("run missing prompt_id")
    scores = record.get("scores", {})
    if not isinstance(scores, Mapping):
        raise BenchmarkError("run scores must be an object")
    normalized_scores: dict[str, float] = {}
    for key, value in scores.items():
        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise BenchmarkError(f"score {key!r} must be numeric") from exc
        if score < 0.0 or score > 1.0:
            raise BenchmarkError(f"score {key!r} must be between 0 and 1")
        normalized_scores[str(key)] = score
    return {
        "candidate_id": candidate_id,
        "prompt_id": prompt_id,
        "status": str(record.get("status") or "scored"),
        "scores": normalized_scores,
        "metadata": dict(record.get("metadata", {})) if isinstance(record.get("metadata", {}), Mapping) else {},
    }


def weighted_score(scores: Mapping[str, float], weights: Mapping[str, float] | None = None) -> float:
    normalized_weights = normalize_weight_map(weights)
    present = {key: float(scores[key]) for key in normalized_weights if key in scores}
    if not present:
        return 0.0
    present_total = sum(normalized_weights[key] for key in present)
    return sum(present[key] * normalized_weights[key] for key in present) / present_total


def load_runs(path: str | Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    raw_runs = payload.get("runs") if isinstance(payload, Mapping) else payload
    if not isinstance(raw_runs, list):
        raise BenchmarkError("benchmark input must be a list or an object with a runs array")
    return [validate_run(item) for item in raw_runs]


def summarize_runs(runs: list[Mapping[str, Any]], weights: Mapping[str, float] | None = None) -> dict[str, Any]:
    by_candidate: dict[str, list[float]] = defaultdict(list)
    by_candidate_prompts: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        candidate_id = str(run["candidate_id"])
        score = weighted_score(run["scores"], weights)
        by_candidate[candidate_id].append(score)
        by_candidate_prompts[candidate_id].add(str(run["prompt_id"]))

    ranking = []
    for candidate_id, scores in by_candidate.items():
        ranking.append(
            {
                "candidate_id": candidate_id,
                "run_count": len(scores),
                "prompt_count": len(by_candidate_prompts[candidate_id]),
                "average_score": mean(scores),
            }
        )
    ranking.sort(key=lambda item: (-item["average_score"], item["candidate_id"]))
    return {
        "weights": normalize_weight_map(weights),
        "run_count": len(runs),
        "candidate_count": len(by_candidate),
        "ranking": ranking,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize generic benchmark JSON records.")
    parser.add_argument("--input", default=None, help="Benchmark JSON path. Defaults to restore overlay if set.")
    parser.add_argument("--weights", default=None, help="Optional JSON object with score weights.")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser() if args.input else default_records_path()
    if input_path is None:
        parser.error("--input is required when restore overlay has no paths.benchmark_records")
    weights = json.loads(args.weights) if args.weights else None
    if weights is not None and not isinstance(weights, Mapping):
        raise BenchmarkError("--weights must be a JSON object")
    result = summarize_runs(load_runs(input_path), weights)
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

