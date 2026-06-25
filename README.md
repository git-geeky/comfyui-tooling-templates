# ComfyUI Tooling Templates

Generic helper scripts and prompt templates for ComfyUI automation.

This extract contains only portable pieces:

- structured JSON prompt validation for Qwen-style image workflows;
- a small template registry with neutral examples;
- tests that do not require a running ComfyUI server.

It intentionally excludes local workflow registries, generated outputs, model
inventories, review databases, machine paths, and private service configuration.

## Quick Start

```powershell
python -m unittest discover -s tests
python scripts/qwen_structured_prompt.py --template architecture-wood-joinery --templates templates/qwen_structured_templates.json
```

Use the JSON output as an input to your own ComfyUI workflow runner.
