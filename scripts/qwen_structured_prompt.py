#!/usr/bin/env python3
"""Structured prompt helpers for Qwen-style ComfyUI workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


PROMPT_PROFILE_VERSION = "qwen-structured-v1"
DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "qwen_structured_templates.json"
REQUIRED_KEYS = {
    "prompt_hardener_version",
    "positive_prompt",
    "negative_prompt",
    "aspect_hint",
    "style_domain",
    "era",
    "safety_scope",
    "required_elements",
    "forbidden_elements",
    "exact_text",
    "uncertain_assumptions",
    "warnings",
}
LIST_KEYS = {"required_elements", "forbidden_elements", "exact_text", "uncertain_assumptions", "warnings"}
ALLOWED_ASPECT_HINTS = {"square", "portrait", "landscape", "wide", "unknown"}
ALLOWED_STYLE_DOMAINS = {"anime", "photoreal", "illustration", "mixed", "unknown"}
ALLOWED_ERAS = {"edo", "historical", "meiji", "modern", "timeless", "unknown"}
ALLOWED_SAFETY_SCOPES = {"sfw", "adult-nonsexual-nsfw", "nsfw", "unknown"}


class StructuredPromptError(ValueError):
    """Raised when a structured prompt is invalid."""


def normalize_string_list(value: Any, key: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise StructuredPromptError(f"{key} must be a list of strings")
    normalized = []
    for item in value:
        if not isinstance(item, str):
            raise StructuredPromptError(f"{key} must be a list of strings")
        text = item.strip()
        if text:
            normalized.append(text)
    return normalized


def validate_structured_prompt(value: Mapping[str, Any], *, allow_future_version: bool = False) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise StructuredPromptError("structured prompt must be a JSON object")
    missing = sorted(REQUIRED_KEYS - set(value))
    if missing:
        raise StructuredPromptError(f"structured prompt missing keys: {', '.join(missing)}")

    version = str(value.get("prompt_hardener_version") or "").strip()
    if not version:
        raise StructuredPromptError("prompt_hardener_version must be a non-empty string")
    if version != PROMPT_PROFILE_VERSION and not allow_future_version:
        raise StructuredPromptError(f"unsupported prompt_hardener_version: {version}")

    positive = value.get("positive_prompt")
    if not isinstance(positive, str) or not positive.strip():
        raise StructuredPromptError("positive_prompt must be a non-empty string")
    negative = value.get("negative_prompt")
    if negative is None:
        negative = ""
    if not isinstance(negative, str):
        raise StructuredPromptError("negative_prompt must be a string")

    aspect_hint = str(value.get("aspect_hint") or "unknown").strip().lower()
    style_domain = str(value.get("style_domain") or "unknown").strip().lower()
    era = str(value.get("era") or "unknown").strip().lower()
    safety_scope = str(value.get("safety_scope") or "unknown").strip().lower()
    if aspect_hint not in ALLOWED_ASPECT_HINTS:
        raise StructuredPromptError(f"unsupported aspect_hint: {aspect_hint}")
    if style_domain not in ALLOWED_STYLE_DOMAINS:
        raise StructuredPromptError(f"unsupported style_domain: {style_domain}")
    if era not in ALLOWED_ERAS:
        raise StructuredPromptError(f"unsupported era: {era}")
    if safety_scope not in ALLOWED_SAFETY_SCOPES:
        raise StructuredPromptError(f"unsupported safety_scope: {safety_scope}")

    result = dict(value)
    result["prompt_hardener_version"] = version
    result["positive_prompt"] = positive.strip()
    result["negative_prompt"] = negative.strip()
    result["aspect_hint"] = aspect_hint
    result["style_domain"] = style_domain
    result["era"] = era
    result["safety_scope"] = safety_scope
    for key in LIST_KEYS:
        result[key] = normalize_string_list(value.get(key), key)
    return result


def structured_prompt_from_text(
    prompt: str,
    *,
    style_domain: str = "unknown",
    safety_scope: str = "sfw",
    aspect_hint: str = "unknown",
    era: str = "unknown",
    required_elements: list[str] | None = None,
    forbidden_elements: list[str] | None = None,
    exact_text: list[str] | None = None,
) -> dict[str, Any]:
    text = prompt.strip()
    if not text:
        raise StructuredPromptError("prompt must be non-empty")
    payload = {
        "prompt_hardener_version": PROMPT_PROFILE_VERSION,
        "positive_prompt": text,
        "negative_prompt": "",
        "aspect_hint": aspect_hint,
        "style_domain": style_domain,
        "era": era,
        "safety_scope": safety_scope,
        "required_elements": required_elements or [],
        "forbidden_elements": forbidden_elements or [],
        "exact_text": exact_text or [],
        "uncertain_assumptions": ["constructed by wrapper; no LLM hardening was applied"],
        "warnings": [],
    }
    return validate_structured_prompt(payload)


def load_structured_prompt(source: str | Path) -> dict[str, Any]:
    text = str(source)
    path = Path(text)
    try:
        is_file = not text.lstrip().startswith("{") and path.exists()
    except OSError:
        is_file = False
    raw = path.read_text(encoding="utf-8") if is_file else text
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StructuredPromptError(f"structured prompt is not valid JSON: {exc}") from exc
    return validate_structured_prompt(payload)


def load_template_registry(template_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(template_path) if template_path else DEFAULT_TEMPLATE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StructuredPromptError(f"unable to read template registry {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise StructuredPromptError(f"template registry is not valid JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise StructuredPromptError("template registry must be a JSON object")
    templates = payload.get("templates")
    if not isinstance(templates, Mapping):
        raise StructuredPromptError("template registry must contain a templates object")
    return dict(payload)


def load_template(template_id: str, template_path: str | Path | None = None) -> dict[str, Any]:
    template_id = str(template_id or "").strip()
    if not template_id:
        raise StructuredPromptError("template id must be non-empty")
    registry = load_template_registry(template_path)
    templates = registry["templates"]
    template = templates.get(template_id)
    if template is None:
        available = ", ".join(sorted(str(key) for key in templates))
        raise StructuredPromptError(f"unknown template id: {template_id}; available: {available}")
    return validate_structured_prompt(template)


def dumps_structured_prompt(prompt: Mapping[str, Any]) -> str:
    return json.dumps(validate_structured_prompt(prompt), indent=2, ensure_ascii=True, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or emit structured Qwen-style prompt JSON.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="Plain prompt text to wrap in structured JSON.")
    group.add_argument("--structured-json", help="Structured prompt JSON string or file path to validate.")
    group.add_argument("--template", help="Template id from the template registry.")
    parser.add_argument("--templates", default=None, help="Template registry path.")
    parser.add_argument("--style-domain", default="unknown", choices=sorted(ALLOWED_STYLE_DOMAINS))
    parser.add_argument("--safety-scope", default="sfw", choices=sorted(ALLOWED_SAFETY_SCOPES))
    parser.add_argument("--aspect-hint", default="unknown", choices=sorted(ALLOWED_ASPECT_HINTS))
    parser.add_argument("--era", default="unknown", choices=sorted(ALLOWED_ERAS))
    args = parser.parse_args()

    if args.template:
        payload = load_template(args.template, args.templates)
    elif args.structured_json:
        payload = load_structured_prompt(args.structured_json)
    else:
        payload = structured_prompt_from_text(
            args.prompt or "",
            style_domain=args.style_domain,
            safety_scope=args.safety_scope,
            aspect_hint=args.aspect_hint,
            era=args.era,
        )
    print(dumps_structured_prompt(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
