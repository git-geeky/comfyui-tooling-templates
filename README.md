# ComfyUI Tooling Templates

Generic helper scripts and prompt templates for ComfyUI automation.

This extract contains only portable pieces:

- structured JSON prompt validation for Qwen-style image workflows;
- a generic SQLite preference-lab for local output review;
- benchmark JSON ranking helpers with configurable score weights;
- workflow manifest validation for keeping private workflow inventories thin;
- a small template registry with neutral examples;
- tests that do not require a running ComfyUI server.

It intentionally excludes local workflow registries, generated outputs, model
inventories, review databases, machine paths, and private service configuration.

Machine-specific values can be supplied through a private restore file outside
git. Copy `config/restore.example.json` to a private path such as
`%LOCALAPPDATA%\comfyui-tooling-templates\restore.local.json`, edit it for your
machine, and set `COMFYUI_TOOLING_RESTORE_FILE` if you use another location.

## Quick Start

```powershell
python -m unittest discover -s tests
python scripts/qwen_structured_prompt.py --template architecture-wood-joinery --templates templates/qwen_structured_templates.json
python scripts/preference_lab.py --db out/preferences.sqlite init
python scripts/model_benchmark.py --input examples/benchmark-runs.json
python scripts/workflow_catalog.py --input examples/workflow-catalog.json
```

Use the JSON output as an input to your own ComfyUI workflow runner.
