"""``CodeBasis`` over local git — what code a run executed, and the registry chain it resolved.

Implements ``protocols.CodeBasis`` for the serving join (docs/provenance.md
§Serving-model join, step 3):

* :meth:`GitCodeBasis.basis_for` — schedule/dispatch → ``Basis("head",
  run_head_sha)``; ``auto-review.yml`` + ``pull_request`` →
  ``Basis("merge", head, main@created_at)``; ``oracle.yml`` +
  ``pull_request`` → ``Basis("main", None, main@checkout.started_at)`` (the
  job checks out ``base.ref`` by name when its checkout step runs — critique
  item 26; without a checkout interval: ``created_at``, marked ambiguous);
  any other workflow/event → ``head``. ``main@T`` comes from
  ``GitReader.first_parent_log("refs/remotes/origin/main")`` (last commit
  with committer epoch ``<= T``). ``ambiguous`` (with ``reason``) when a
  first-parent main commit touching ``.github/models/registry.conf`` or the
  run's workflow file lies in ``(created_at − window, created_at]`` (merge)
  or ``[checkout start − window, checkout end + window]`` (main), or
  (``merge``) when ``merge_tree_read`` reports a conflict on either file.
  A needed commit absent locally (``has_commit`` false after the job-start
  fetch — never fetched here, critique item 9) → ``unavailable=<sha>``; the
  join answers basis ``none`` and adds ``codebasis-unavailable:<sha8>``.
  Memoized per ``(workflow, kind, main8, head8)``.
* :meth:`GitCodeBasis.file_at` — ``show(head, path)``, or the merge-tree
  result, or ``show(main, path)``; cached per (basis, path).
* :meth:`GitCodeBasis.chain_models` — parses the registry text with
  tools/model-registry's OWN parser (``model_registry.registry.Registry.load``
  on a temp file; the parser is strict, so a historical registry that fails
  it yields ``None`` → basis ``none``, never a lenient re-parse). Cached per
  blob sha256.

**What the memo holds.** The memo per ``(workflow, kind, main, head)`` (full
shas — the 8-char forms name the same partition without a collision risk)
holds what is a function of those four alone: the head's availability and,
for ``merge``, the two ``merge_tree_read`` results (content + conflict) —
so a run of reviews on one PR head at one main costs one merge-tree per
file. The time-window ambiguity is NOT memoized: it depends on the run's own
``created_at`` / checkout interval, so two runs that share ``(main, head)``
but were created minutes vs hours after a registry commit get different
answers (a memo of the whole ``Basis`` would hand the second run the first
run's verdict).

**Reasons** (``Basis.reason``, closed): ``merge-conflict`` (a conflict on the
registry or the workflow in the merge tree), ``main-changed-before-created``
(merge window), ``main-changed-near-checkout`` (main window),
``no-checkout-step`` (an oracle run whose receipt job has no checkout step),
``no-main`` (no first-parent main commit at or before T — main's local
history does not reach back that far), ``no-head-sha`` (the run carries no
head sha). The last two answer basis ``none`` without an ``unavailable`` sha.

Imports ``model_registry`` lazily (the workflow's PYTHONPATH carries
``tools/model-registry/src``; tests add it in conftest). Runs no git itself:
all history comes through the ``GitReader`` it is given.

Owner: H4.
"""

from __future__ import annotations

import configparser
import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from typing import Optional

from .protocols import Basis, GitReader
from .serving import ts_epoch

REGISTRY_PATH = ".github/models/registry.conf"
WORKFLOW_DIR = ".github/workflows/"
MAIN_REF = "refs/remotes/origin/main"

#: Workflows whose ``pull_request`` runs resolve the chain on a merge ref / on main by name.
MERGE_WORKFLOWS = frozenset({"auto-review.yml"})
MAIN_WORKFLOWS = frozenset({"oracle.yml"})
#: Events that run the default branch's head as recorded in ``run.head_sha``.
HEAD_EVENTS = frozenset({"schedule", "workflow_dispatch"})


def basis_kind(workflow: str, event: str) -> str:
    """``head`` | ``merge`` | ``main`` for one run (module docstring)."""
    if event in HEAD_EVENTS:
        return "head"
    if event == "pull_request" and workflow in MERGE_WORKFLOWS:
        return "merge"
    if event == "pull_request" and workflow in MAIN_WORKFLOWS:
        return "main"
    return "head"


@dataclass
class GitCodeBasis:
    """``protocols.CodeBasis`` backed by a ``GitReader`` and the model-registry parser."""

    git: GitReader
    ambiguity_window_seconds: int = 900
    main_ref: str = MAIN_REF
    _cache: dict = field(default_factory=dict)

    # -- history -----------------------------------------------------------

    def _log(self, paths: tuple[str, ...] = ()) -> list[tuple[str, int]]:
        key = ("log", paths)
        if key not in self._cache:
            self._cache[key] = list(self.git.first_parent_log(self.main_ref, paths))
        return self._cache[key]

    def _main_at(self, epoch: int) -> Optional[str]:
        for sha, e in self._log():
            if e is not None and e <= epoch:
                return sha
        return None

    def _touched_between(self, workflow: str, lo: int, hi: int, *, lo_open: bool) -> bool:
        """A first-parent main commit touching the registry or the workflow lies in the interval."""
        for _sha, e in self._log((REGISTRY_PATH, WORKFLOW_DIR + workflow)):
            if e is None:
                continue
            if (lo < e if lo_open else lo <= e) and e <= hi:
                return True
        return False

    # -- the memoized, time-independent part ---------------------------------

    def _content(self, workflow: str, kind: str, main: Optional[str], head: Optional[str]) -> dict:
        key = ("content", workflow, kind, main, head)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        out: dict = {"unavailable": None, "conflicts": []}
        need = [s for s in ((head,) if kind == "head" else (main,) if kind == "main" else (main, head)) if s]
        missing = [s for s in need if not self.git.has_commit(s)]
        if missing:
            # The head is the commit a force-push can take away; name it first.
            out["unavailable"] = head if head in missing else missing[0]
        elif kind == "merge" and main and head:
            for path in (REGISTRY_PATH, WORKFLOW_DIR + workflow):
                if self._merge_read(main, head, path)[1]:
                    out["conflicts"].append(path)
        self._cache[key] = out
        return out

    def _merge_read(self, main: str, head: str, path: str) -> tuple[Optional[bytes], bool]:
        """``merge_tree_read(main, head, path)``, once per (main, head, path)."""
        key = ("merge", main, head, path)
        if key not in self._cache:
            self._cache[key] = self.git.merge_tree_read(main, head, path)
        return self._cache[key]

    # -- protocols.CodeBasis --------------------------------------------------

    def basis_for(self, workflow: str, event: str, run_head_sha: Optional[str],
                  run_created_at: str, checkout: Optional[tuple[str, str]] = None) -> Basis:
        kind = basis_kind(workflow, event)
        head = run_head_sha or None
        created = ts_epoch(run_created_at)
        window = self.ambiguity_window_seconds
        if kind == "head":
            if head is None:
                return Basis("head", None, None, reason="no-head-sha")
            c = self._content(workflow, kind, None, head)
            return Basis("head", head, None, unavailable=c["unavailable"])
        if kind == "merge":
            main = self._main_at(created) if created is not None else None
            if head is None:
                return Basis("merge", None, main, reason="no-head-sha")
            if main is None:
                return Basis("merge", head, None, reason="no-main")
            c = self._content(workflow, kind, main, head)
            if c["unavailable"]:
                return Basis("merge", head, main, unavailable=c["unavailable"])
            if c["conflicts"]:
                return Basis("merge", head, main, ambiguous=True, reason="merge-conflict")
            if self._touched_between(workflow, created - window, created, lo_open=True):
                return Basis("merge", head, main, ambiguous=True, reason="main-changed-before-created")
            return Basis("merge", head, main)
        # kind == "main" (oracle pull_request): main at the checkout step's start.
        interval = None
        if checkout is not None:
            t0, t1 = ts_epoch(checkout[0]), ts_epoch(checkout[1])
            if t0 is not None and t1 is not None:
                interval = (t0, max(t0, t1))
        if interval is None:
            if created is None:
                return Basis("main", None, None, reason="no-main")
            main = self._main_at(created)
            if main is None:
                return Basis("main", None, None, reason="no-main")
            c = self._content(workflow, kind, main, None)
            if c["unavailable"]:
                return Basis("main", None, main, unavailable=c["unavailable"])
            return Basis("main", None, main, ambiguous=True, reason="no-checkout-step")
        main = self._main_at(interval[0])
        if main is None:
            return Basis("main", None, None, reason="no-main")
        c = self._content(workflow, kind, main, None)
        if c["unavailable"]:
            return Basis("main", None, main, unavailable=c["unavailable"])
        if self._touched_between(workflow, interval[0] - window, interval[1] + window, lo_open=False):
            return Basis("main", None, main, ambiguous=True, reason="main-changed-near-checkout")
        return Basis("main", None, main)

    def file_at(self, basis: Basis, path: str) -> Optional[bytes]:
        if basis.unavailable:
            return None
        key = ("file", basis.kind, basis.head_sha, basis.main_sha, path)
        if key in self._cache:
            return self._cache[key]
        data: Optional[bytes] = None
        if basis.kind == "head" and basis.head_sha:
            data = self.git.show(basis.head_sha, path)
        elif basis.kind == "main" and basis.main_sha:
            data = self.git.show(basis.main_sha, path)
        elif basis.kind == "merge" and basis.head_sha and basis.main_sha:
            content, conflicted = self._merge_read(basis.main_sha, basis.head_sha, path)
            data = None if conflicted else content
        self._cache[key] = data
        return data

    def chain_models(self, basis: Basis, chain: str) -> Optional[tuple[str, ...]]:
        text = self.file_at(basis, REGISTRY_PATH)
        if text is None:
            return None
        key = ("registry", hashlib.sha256(text).hexdigest())
        if key not in self._cache:
            self._cache[key] = parse_registry_chains(text)
        chains = self._cache[key]
        if chains is None:
            return None
        return chains.get(chain)


def main_at(git: GitReader, main_ref: str, epoch: int) -> Optional[str]:
    """The last first-parent main commit with committer epoch ``<= epoch``."""
    for sha, e in git.first_parent_log(main_ref):
        if e is not None and e <= epoch:
            return sha
    return None


def parse_registry_chains(text: bytes) -> Optional[dict[str, tuple[str, ...]]]:
    """``{chain id: model ids}`` via ``model_registry``'s parser, ``None`` when it refuses the text."""
    from model_registry.registry import Registry  # lazy: PYTHONPATH carries tools/model-registry/src

    with tempfile.TemporaryDirectory(prefix="provenance-registry-") as tmp:
        path = os.path.join(tmp, "registry.conf")
        with open(path, "wb") as fh:
            fh.write(text)
        try:
            reg = Registry.load(path)
        except (ValueError, KeyError, UnicodeDecodeError, configparser.Error):
            return None
    return {cid: tuple(reg.chains[cid].models) for cid in sorted(reg.chains)}
