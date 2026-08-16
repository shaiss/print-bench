"""model-registry — the provider/model registry for agentic workflows (issue #206).

``.github/models/registry.conf`` is the single source of truth for which models
the agentic workflows run, in what preference order, and why.  This package parses
it (fail-loud, stdlib-only) and resolves a named chain into the ordered
``(model, provider)`` links a workflow consumes — so reordering or swapping a model
is a registry edit, not a hunt through every job's YAML.

The registry is the *decision*; the workflow still supplies the *literal* secret
wiring per provider, because GitHub Actions can only reference a secret by its
literal name (the same constraint ``backlog-burn.yml`` documents).  This tool
picks which model and in what order; the YAML owns the secrets.
"""

from .registry import Chain, Model, Provider, Registry, ResolvedLink

__all__ = ["Registry", "Provider", "Model", "Chain", "ResolvedLink"]
