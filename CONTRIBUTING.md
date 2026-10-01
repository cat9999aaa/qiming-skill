# Contributing

Python 3.11+; the default JSON workflow has no third-party runtime dependency.

```sh
python -m pip install pytest==8.3.5 PyYAML==6.0.3
python -m pytest -q
python site/build.py --out site/dist
```

Linux/macOS can use python3; Windows can use py -3. The CI matrix runs Python 3.11–3.13 on Linux, macOS and Windows. A green test matrix proves these automated checks, not that every AI host follows project instructions.

Keep changes small, add a failing regression before fixing a defect, and include the observed result. Test fixtures must be synthetic. Never publish project management records, raw session logs, local paths, personal project names or credentials.

The runtime Skill describes when to act, scope, evidence and recovery. Model-specific writing advice (including keeping prompts concise for GPT-6 Astra) belongs here, not in every user's runtime context. Do not promise behavior from a model name.

Project-local customizations are user-owned. Changes to the installation package do not authorize overwriting those customizations. Preview upgrades, preserve modified resources, and treat profile migrations separately.
