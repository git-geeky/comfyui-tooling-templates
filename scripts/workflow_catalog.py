#!/usr/bin/env python3
"""Validate and summarize a generic ComfyUI workflow catalog."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

try:
    from . import local_restore
except ImportError:
    import local_restore  # type: ignore


WORKFLOW_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,80}$")
ALLOWED_INPUT_TYPES = {"boolean", "float", "integer", "path", "string"}


class WorkflowCatalogError(ValueError):
    """Raised when a workflow catalog is invalid."""


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def default_catalog_path() -> Path | None:
    restore = local_restore.load_restore_config()
    paths = restore.get("paths", {}) if isinstance(restore, Mapping) else {}
    value = paths.get("workflow_catalog") if isinstance(paths, Mapping) else None
    return Path(str(value)).expanduser() if value else None


def validate_workflow(record: Mapping[str, Any]) -> dict[str, Any]:
    workflow_id = str(record.get("workflow_id") or "").strip()
    if not WORKFLOW_ID_RE.match(workflow_id):
        raise WorkflowCatalogError(f"invalid workflow_id: {workflow_id!r}")
    display_name = str(record.get("display_name") or "").strip()
    if not display_name:
        raise WorkflowCatalogError(f"{workflow_id}: display_name is required")
    category = str(record.get("category") or "").strip()
    if not category:
        raise WorkflowCatalogError(f"{workflow_id}: category is required")
    template_path = str(record.get("template_path") or "").strip()
    if (
        not template_path
        or Path(template_path).is_absolute()
        or template_path.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:[/\\]", template_path)
    ):
        raise WorkflowCatalogError(f"{workflow_id}: template_path must be a relative path")
    required_models = record.get("required_models", [])
    if not isinstance(required_models, list) or not all(isinstance(item, str) and item for item in required_models):
        raise WorkflowCatalogError(f"{workflow_id}: required_models must be a list of strings")
    inputs = record.get("inputs", {})
    if not isinstance(inputs, Mapping):
        raise WorkflowCatalogError(f"{workflow_id}: inputs must be an object")
    normalized_inputs = {}
    for key, value in inputs.items():
        input_type = str(value)
        if input_type not in ALLOWED_INPUT_TYPES:
            raise WorkflowCatalogError(f"{workflow_id}: unsupported input type {input_type!r}")
        normalized_inputs[str(key)] = input_type
    return {
        "workflow_id": workflow_id,
        "display_name": display_name,
        "category": category,
        "template_path": template_path,
        "required_models": sorted(required_models),
        "inputs": dict(sorted(normalized_inputs.items())),
    }


def load_catalog(path: str | Path) -> list[dict[str, Any]]:
    payload = load_json(path)
    workflows = payload.get("workflows") if isinstance(payload, Mapping) else payload
    if not isinstance(workflows, list):
        raise WorkflowCatalogError("catalog must be a list or an object with a workflows array")
    normalized = [validate_workflow(item) for item in workflows]
    ids = [item["workflow_id"] for item in normalized]
    duplicates = sorted(item for item, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise WorkflowCatalogError(f"duplicate workflow_id values: {', '.join(duplicates)}")
    return sorted(normalized, key=lambda item: item["workflow_id"])


def summarize_catalog(workflows: list[Mapping[str, Any]]) -> dict[str, Any]:
    categories = Counter(str(item["category"]) for item in workflows)
    model_count = len({model for item in workflows for model in item["required_models"]})
    return {
        "workflow_count": len(workflows),
        "category_counts": dict(sorted(categories.items())),
        "unique_required_model_count": model_count,
        "workflow_ids": [str(item["workflow_id"]) for item in workflows],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and summarize a generic workflow catalog.")
    parser.add_argument("--input", default=None, help="Workflow catalog JSON path. Defaults to restore overlay.")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser() if args.input else default_catalog_path()
    if input_path is None:
        parser.error("--input is required when restore overlay has no paths.workflow_catalog")
    result = summarize_catalog(load_catalog(input_path))
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
