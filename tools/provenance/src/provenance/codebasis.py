"""``CodeBasis`` over local git — what code a run executed, and the registry chain it resolved.

Implements ``protocols.CodeBasis`` for the serving join (docs/provenance.md
§Serving-model join, step 3):

* :meth:`GitCodeBasis.basis_for` — schedule/dispatch → ``Basis("head",
  run_head_sha)``; ``auto-review.yml`` + ``pull_request`` →
  ``Basis("merge", head, main@created_at)``; ``oracle.yml`` +
  ``pull_request`` → ``Basis("main", None, main@created_at)``; any other
  workflow/event → ``head``. ``main@T`` comes from
  ``GitReader.first_parent_log("refs/remotes/origin/main")`` (last commit
  with committer epoch ``<= T``). ``ambiguous`` (with ``reason``) when a
  first-parent main commit touching ``.github/models/registry.conf`` or the
  run's workflow file lies in ``(T - window, T]``, or (``merge``) when
  ``merge_tree_read`` reports a conflict on either file, or when a needed
  commit cannot be fetched (``ensure_commit`` false → ``reason:
  "missing-commit"``).
* :meth:`GitCodeBasis.file_at` — ``show(head, path)``, or the merge-tree
  result, or ``show(main, path)``; cached per (basis, path).
* :meth:`GitCodeBasis.chain_models` — parses the registry text with
  tools/model-registry's OWN parser (``model_registry.registry.Registry.load``
  on a temp file; the parser is strict, so a historical registry that fails
  it yields ``None`` → basis ``none``, never a lenient re-parse). Cached per
  blob sha256.

Imports ``model_registry`` lazily (the workflow's PYTHONPATH carries
``tools/model-registry/src``; tests add it in conftest). Runs no git itself:
all history comes through the ``GitReader`` it is given.

Owner: H4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .protocols import Basis, GitReader

REGISTRY_PATH = ".github/models/registry.conf"
WORKFLOW_DIR = ".github/workflows/"
MAIN_REF = "refs/remotes/origin/main"


@dataclass
class GitCodeBasis:
    """``protocols.CodeBasis`` backed by a ``GitReader`` and the model-registry parser."""

    git: GitReader
    ambiguity_window_seconds: int = 900
    main_ref: str = MAIN_REF
    _cache: dict = field(default_factory=dict)

    def basis_for(self, workflow: str, event: str, run_head_sha: Optional[str],
                  run_created_at: str) -> Basis:
        raise NotImplementedError("builder H4")

    def file_at(self, basis: Basis, path: str) -> Optional[bytes]:
        raise NotImplementedError("builder H4")

    def chain_models(self, basis: Basis, chain: str) -> Optional[tuple[str, ...]]:
        raise NotImplementedError("builder H4")


def main_at(git: GitReader, main_ref: str, epoch: int) -> Optional[str]:
    """The last first-parent main commit with committer epoch ``<= epoch``."""
    raise NotImplementedError("builder H4")


def parse_registry_chains(text: bytes) -> Optional[dict[str, tuple[str, ...]]]:
    """``{chain id: model ids}`` via ``model_registry``'s parser, ``None`` when it refuses the text."""
    raise NotImplementedError("builder H4")
