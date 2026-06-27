#!/usr/bin/env python3
"""Portable ComfyUI model inventory audit helpers.

The script intentionally keeps host-specific paths out of source control. Pass
paths on the command line or through a private restore file.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".gguf"}


def read_json(path: Path) -> Any:
    """Read JSON that may include a UTF-8 BOM."""
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model_inventory(models_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(models_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
            continue
        stat = path.stat()
        rows.append(
            {
                "relative": str(path.relative_to(models_dir)).replace("\\", "/"),
                "name": path.name,
                "bytes": stat.st_size,
                "gb": round(stat.st_size / (1024**3), 3),
                "last_write": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return rows


def workflow_refs(workflows_dir: Path, inventory: list[dict[str, Any]]) -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    if not workflows_dir.exists():
        return refs
    for path in sorted(workflows_dir.glob("*.json")):
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        for item in inventory:
            if item["name"] in text:
                refs.setdefault(item["name"], []).append(path.name)
    return refs


def load_template_coverage(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"available": False, "reason": "template coverage path not provided"}
    if not path.exists():
        return {"available": False, "path": str(path), "reason": "template coverage file not found"}

    coverage = read_json(path)
    installed_refs: dict[str, list[str]] = {}
    for template in coverage.get("templates", []):
        template_path = template.get("path", "")
        for model in template.get("models", []):
            if not model.get("installed"):
                continue
            key = f"{model.get('directory', '')}/{model.get('name', '')}".strip("/")
            installed_refs.setdefault(key, []).append(template_path)

    return {
        "available": True,
        "path": str(path),
        "generated_at": coverage.get("generated_at"),
        "template_count": coverage.get("template_count"),
        "templates_all_models_installed": coverage.get("templates_all_models_installed"),
        "templates_with_missing_models": coverage.get("templates_with_missing_models"),
        "unique_installed_model_count": coverage.get("unique_installed_model_count"),
        "unique_model_count": coverage.get("unique_model_count"),
        "installed_refs": installed_refs,
    }


def classify_models(
    inventory: list[dict[str, Any]],
    refs: dict[str, list[str]],
    coverage: dict[str, Any],
    large_gb: float,
) -> list[dict[str, Any]]:
    installed_refs = coverage.get("installed_refs") or {}
    classified: list[dict[str, Any]] = []
    for item in inventory:
        rel = item["relative"]
        name = item["name"]
        template_refs = installed_refs.get(rel) or installed_refs.get(rel.replace("\\", "/")) or []
        workflow_ref_names = refs.get(name, [])
        if workflow_ref_names or template_refs:
            classification = "used"
        elif item["gb"] >= large_gb:
            classification = "cleanup candidate"
        else:
            classification = "unreferenced"
        classified.append(
            {
                **item,
                "classification": classification,
                "workflow_refs": workflow_ref_names,
                "official_template_refs": template_refs,
            }
        )
    return classified


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    models_dir = Path(args.models_dir)
    workflows_dir = Path(args.workflows_dir)
    coverage_path = Path(args.template_coverage) if args.template_coverage else None
    inventory = model_inventory(models_dir)
    refs = workflow_refs(workflows_dir, inventory)
    coverage = load_template_coverage(coverage_path)
    classified = classify_models(inventory, refs, coverage, args.large_gb)
    counts: dict[str, int] = {}
    for item in classified:
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models_dir": str(models_dir),
        "workflows_dir": str(workflows_dir),
        "template_coverage": coverage,
        "model_count": len(inventory),
        "classification_counts": counts,
        "models": classified,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ComfyUI model references without host-specific source.")
    parser.add_argument("--models-dir", required=True, help="ComfyUI models directory")
    parser.add_argument("--workflows-dir", required=True, help="ComfyUI user workflows directory")
    parser.add_argument("--template-coverage", help="Optional official template model coverage JSON")
    parser.add_argument("--large-gb", type=float, default=1.0, help="Size threshold for cleanup candidates")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    report = build_report(args)
    text = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
