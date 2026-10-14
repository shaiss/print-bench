"""provenance — the keyless, deterministic harvester behind every design's "How it was made".

Design of record: ``docs/provenance.md``. Closed contract:
``site/lib/provenance-contract.json``. Policy: ``.github/provenance.conf``.
Workflow: ``.github/workflows/provenance.yml``.

The harvester freezes structured facts about how each design was made — who
filed its brief, which routine and model built it, every review round, which
sign-offs are trustworthy, when it merged and deployed — once, after a settle
window, onto two data refs:

* ``provenance`` — EVIDENCE, linear and add-only: run receipts (the complete
  Actions jobs response of every agent-bearing run, because GitHub now deletes
  runs after 90 days), digested API payloads per frozen PR / brief / release
  (bodies replaced by digests — prose is never stored), the ingested #843
  snapshot, and ``state.json`` (cursors, pending units). Every push is a
  fast-forward guarded by a diff-tree check (no deletes, no modifications
  except ``state.json``) and by tip continuity (the tip must be a sha a
  previous default-branch run declared in an intent artifact).
* ``provenance-site`` — DERIVED, one squashed parentless commit: records,
  per-design views and the single ``site/bundle.json`` the site reads at
  deploy time, recomputed every run as a pure function of (evidence tip,
  main sha, extractor version).

No LLM runs anywhere; the workflow holds no secret but ``GITHUB_TOKEN``.

Module map (owner after the scaffold in brackets; ``*`` = implemented in full
by the scaffold because every builder's fixtures depend on its bytes):

==============  =====  ==========================================================
module          owner  role
==============  =====  ==========================================================
protocols *     arch   the seams: GitReader, TreeReader, GitHubAPI, CodeBasis, Basis
canonical *     H2     canonical JSON, deterministic gzip, the event sort key
digest *        H2     body / commit-message digests (what replaces prose)
steps *         H4     the agent-step grammar (four naming eras, fail-safe)
rawdoc *        H3     REST payload → raw@1 projections
github          H1     the ONLY network module: GET-only + one GraphQL query
gitstore        H1     the ONLY git module: read primitives, add-only writer,
                       diff-tree guard, pushes, tip continuity
receipts        H1     runs-list selection → receipt@1 (full or stub)
ingest          H1     the #843 snapshot → receipts/ and raw/snapshot/
state           H1     state.json model: cursors, pending, frozen
cli             H1     argparse + orchestration of every mode
contract        H2     Python validator for the closed contract
trust           H2     the reviewer-posted.sh / coach-lock-check.sh port
markers         H2     marker parsing, the five marker eras, unknown.marker
membership      H2     the refined file-kind rule (PR × design membership)
extract         H3     raw@1 → record@1 events (pr, brief, release, commit)
episodes        H3     rounds, regen/merge folds, stale_sha, verifies, decision rows
serving         H4     the serving-model join + window trust (pure)
codebasis       H4     CodeBasis over git: head / merge-tree / main + registry parse
views           H5     records → view@1 per design
bundle          H5     view@1s → bundle@1; the derived tree's files
freeze          H6     settle/defer policy and the PR/brief/release capture sequences
conf            H6     strict parser for .github/provenance.conf
selftest        H6     the offline negative-control suite behind scripts/provenance.sh
==============  =====  ==========================================================

Purity (tests/test_purity.py, real from day one): only ``github.py`` imports
anything network-capable; only ``gitstore.py`` runs a subprocess; no module
but ``cli.py`` and ``github.py`` reads the clock; nothing imports ``random``.
Stdlib-only: the workflow runs this from the checkout on the system Python
(``PYTHONPATH=tools/provenance/src:tools/model-registry/src``).
"""

__version__ = "0.1.0"

#: The harvester's own version string, recorded in ``captured.harvester``
#: and ``state.json`` ``versions.harvester``.
HARVESTER = f"provenance {__version__}"

__all__ = [
    "bundle", "canonical", "cli", "codebasis", "conf", "contract", "digest", "episodes",
    "extract", "freeze", "github", "gitstore", "ingest", "markers", "membership",
    "protocols", "rawdoc", "receipts", "selftest", "serving", "state", "steps",
    "trust", "views",
]
