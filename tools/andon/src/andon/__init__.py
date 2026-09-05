"""andon — the reconciler behind print-bench's AI andon cord status issue.

The AI andon cord (docs/andon-cord.md) is ONE repo variable,
``AI_ANDON_CORD``: set to ``pulled`` it bypasses every AI-consuming workflow
job in the repository — grey, never red, no provider API call, no
escalation. A skipped job is mute, though, so this package gives the pulled
state a visible, timestamped record: a sticky status issue that the hourly
``andon.yml`` workflow opens ONCE the first time it observes the cord pulled
and closes ONCE (with the observed timespan) the first time it observes the
cord released. A re-pull opens a fresh issue, so the closed issues are the
episode history.

Modules:

* :mod:`andon.policy` — PURE: the constants (marker, labels, title, the
  variable name), ``is_pulled`` (GitHub's case-insensitive ``==``, mirrored),
  ``decide`` (the four-branch open/close/none decision) and every rendered
  byte (the issue body, the closing comment, the humanised duration).
* :mod:`andon.github` — the ONLY module allowed to import ``urllib``: one
  GET-only seam (``_get``) and the paged listing that finds the open status
  issue. It never writes to GitHub.
* :mod:`andon.cli` — ``andon decide`` (the workflow's step), plus
  ``render-open`` / ``render-close`` for docs and tests.

The purity rule (tests/test_purity.py, the backlog-groomer's shape): the
package performs no GitHub or network write — no HTTP write verb appears
anywhere in it, not even in a comment — and only ``github.py`` may import
anything network-capable. (Its only writes are local scratch: the rendered
``body.md`` / ``comment.md`` under ``--out-dir`` and the ``KEY=VALUE`` lines
appended to ``--gh-output``, both consumed by the workflow's write step.) The single GitHub write (create / comment+close the issue)
lives in a ``github-script`` step of ``.github/workflows/andon.yml``, driven
by this package's decision and rendered text, so the tool scans clean and
the write surface is one reviewed workflow step.

Stdlib-only, like tools/lineage and tools/reeve: the workflow reads the
policy straight from the checkout with no pip step in front of it.
"""

__all__ = ["cli", "github", "policy"]
