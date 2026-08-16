"""``python -m model_registry`` — the workflow invokes the tool this way (no install).

Stdlib-only, so a workflow runs it straight from the checkout with
``PYTHONPATH=tools/model-registry/src python3 -m model_registry ...`` — no pip
step in front of the review pipeline.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
