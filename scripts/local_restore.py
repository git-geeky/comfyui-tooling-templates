"""Optional local restore overlay for public ComfyUI tooling.

The public repo stays generic. Machine-specific paths can be loaded from a JSON
file outside git when a local wrapper needs them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


RESTORE_FILE_ENV = "COMFYUI_TOOLING_RESTORE_FILE"


def default_restore_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "comfyui-tooling-templates" / "restore.local.json"
    return Path.home() / ".config" / "comfyui-tooling-templates" / "restore.local.json"


def load_restore_config(env_var: str = RESTORE_FILE_ENV) -> dict[str, Any]:
    explicit = os.environ.get(env_var)
    path = Path(explicit).expanduser() if explicit else default_restore_path()
    if not path.exists():
        if explicit:
            raise FileNotFoundError(f"{env_var} points to a missing file")
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("restore file must be a JSON object")
    return dict(payload)
