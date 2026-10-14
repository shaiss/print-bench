"""CLI for the provenance harvester — argparse plus the orchestration of every mode.

The workflow (``.github/workflows/provenance.yml``) runs these subcommands
from the default-branch checkout with ``PYTHONPATH=tools/provenance/src:
tools/model-registry/src``. Dispatch inputs reach the code ONLY through
``env:`` and are passed as arguments here, where :func:`validate_inputs`
regex-checks every one before use (docs/actions-security.md: a value from
``${{ inputs.* }}`` is never interpolated into a ``run:`` script).

Dispatch modes are exactly ``harvest``, ``refreeze`` and ``recover`` (owner
decision 12). The #843 snapshot ingest is not a mode: ``harvest`` performs it
when ``state.ingested`` lacks it (critique item 17).

Subcommands (docs/provenance.md §Workflow):

``harvest``
    schedule, or dispatch ``mode=harvest``: ``[--since D] [--until D]
    [--pr N,N…] [--receipts-only] [--max-requests N] [--dry-run] [--scheduled]
    [--bootstrap] [--snapshot-dir DIR] --out-dir DIR``. Steps, in order:

    1. **fetch** — ``gitstore.Git.fetch_all()``, token-less: both data refs and
       every PR head. A failed PR-head fetch sets ``derive_skipped`` (the
       evidence half still runs; no derived push this run).
    2. **continuity** — ``gitstore.scan_marks`` then
       ``gitstore.continuity_verdict`` for both refs. Evidence verdict:
       ``ok`` → build on the tip; ``bootstrap`` → create the root ONLY with
       ``--bootstrap`` (else ``::error::``, exit 3); ``foreign`` / ``deleted`` /
       ``unanchored`` → ``foreign_tip=true``: steps 3–6 are skipped (no
       evidence change is planned) and derive runs from the newest
       checkpointed evidence commit ``C``
       (fetched with the foreign tip when it is an ancestor; derive is skipped
       if ``C`` is not local), so a forged derived tip is replaced even while
       the evidence ref is forged (critique item 5). ``--bootstrap`` with any
       other verdict is an error (exit 1). The derived verdict only decides the
       message: a non-``ok`` derived tip is overwritten with ``::error::``
       (``foreign``/``deleted``) or ``::notice::`` (``bootstrap``/``unanchored``).
    3. **ingest** — ``ingest.needs_ingest(state, snapshot_id)`` → ``ingest.
       read_snapshot(snapshot_dir, …, pin)`` + ``plan_ingest`` (≈ 0 requests).
    4. **receipts** — ``receipts.harvest_receipts`` over every watched
       workflow from its cursor (or ``--since``), day-windowed.
    5. unless ``--receipts-only``: **freeze** — ``freeze.plan_freezes``
       (settle/defer, re-capture of a changed terminal state, PR/brief/release
       capture; ``--pr`` restricts it to the named PRs).
    6. **evidence commit** — ``gitstore.TreeBuilder`` (add-only; guard files
       only at bootstrap) + ``gitstore.guard_diff`` against the old tip
       (``[]`` → evidence unchanged). Guard drift from main → ``::warning::``.
    7. **derive** — ``bundle.derive`` from the evidence commit just built
       (or ``C`` when foreign) + main, ``gitstore.DerivedTreeBuilder``, and
       ``site_changed = not derived_continuity.accepted or not
       bundle.same_content(<current derived tree>, new files)`` — the tip's
       actual blobs are compared, never its ``content_sha256`` field.
    8. **plan** — ``<out-dir>/plan.json``, ``<out-dir>/intent-<ref>.json`` per
       ref that will move, ``<out-dir>/summary.md``, and ``$GITHUB_OUTPUT``
       lines (below).

    Nothing is pushed: the workflow uploads the intents, then runs
    ``publish``. ``--dry-run`` plans and outputs both ``*_changed`` false.
    A ``github.BudgetExhausted`` in 3–5 ends capture cleanly: what was
    captured is planned, the cursors record where to resume, exit 0 with a
    ``::notice::``. A dispatch's capture deadline is job start +
    ``dispatch_max_minutes`` − ``derive_reserve_minutes`` (critique item 22);
    ``now`` is read once here and passed down.
``refreeze``
    ``--pr N [--dry-run] --out-dir DIR`` — capture PR ``N`` again as
    ``raw/pr/<N>.r<K+1>.json.gz`` (no settle wait; retention-bound sections
    carried from revision K — freeze.refreeze), then steps 6–8 (after 1–2;
    a non-``ok`` evidence verdict refuses).
``recover``
    ``--confirm-sha SHA --out-dir DIR`` — break-glass, evidence ref only.
    Refused (exit 3) unless the evidence verdict is ``foreign`` or ``deleted``
    AND ``SHA`` equals the newest evidence checkpoint ``C`` (critique item
    4): it can only restore the state the harvester itself last verified, so
    a write-access dispatcher — an agent included — gains nothing by running
    it. ``C`` is fetched by sha if not local (``recover`` only). Plans a
    ``--force-with-lease`` of ``C`` over the current tip (or a create when
    absent); ``publish`` performs it.
``publish``
    ``--out-dir DIR`` — push what ``plan.json`` says, IN ORDER (critique item
    21): (1) ``provenance`` fast-forward only (``gitstore.push_fast_forward``;
    recover: force-with-lease); (2) only if (1) pushed, was unchanged, or the
    plan derived from ``C`` (``foreign_tip``): ``provenance-site`` with
    ``--force-with-lease`` on the planned old tip. Each remote tip is
    re-checked == the planned old tip first. Any rejection or moved tip →
    ``::error::``, exit 3, nothing further pushed; a transport failure after
    retries → exit 1. On success writes ``<out-dir>/checkpoints.json`` and the
    outputs ``evidence_tip`` / ``site_tip`` — the VERIFIED tips the workflow
    uploads as ``tip-<ref>-<sha>`` checkpoints (empty for a ref left foreign or
    unpublished) — and ``foreign_tip``; the workflow's final verdict step fails
    the job when ``foreign_tip`` is true, after the checkpoints are uploaded.
``gate``
    ``[--scheduled] [--armed-var VALUE]`` — the workflow's ``gate`` job.
    ``go`` = conf ``enabled`` (a dispatch — the house convention, critique
    item 20) AND, on a schedule, ``conf.armed(enabled, PROVENANCE_ENABLED)``
    AND no other provenance.yml run is waiting: ONE unfiltered runs-list GET
    (``/actions/workflows/provenance.yml/runs``, newest 100), filtered
    client-side to runs other than this one whose ``status`` ∈ {queued,
    in_progress, pending, waiting, requested} — a run blocked on the
    concurrency group reports ``pending``/``waiting``, not ``queued`` — so a
    scheduled harvest never evicts an operator's pending dispatch.
``check``
    ``--dir DIR --kind evidence|derived`` — validate a tree against the
    contract: FORMAT, guard-file presence and mode (``::warning::`` on drift
    from main's ``.github/data-branch-guard/*``), every blob's shape, receipt
    paths agreeing with their run ids, raw revisions contiguous from 1, the
    bundle's ``views_sha256`` / ``content_sha256`` recomputed from the tree.
    Exit 1 on the first class of failure, listing them all. (No ``--ref``:
    the integrator checks out a ref into a directory — critique item 31.)
``selftest``
    the offline negative-control suite (``selftest.run``) — what
    ``scripts/provenance.sh --selftest`` and check.sh run.

``$GITHUB_OUTPUT`` (``--gh-output``): ``mode``, ``dry_run``, ``foreign_tip``,
``evidence_changed``, ``evidence_sha``, ``site_changed``, ``site_sha``,
``derive_skipped``, ``budget_stopped`` (plan modes); ``evidence_tip``,
``site_tip``, ``foreign_tip`` (publish); ``go`` (gate). Every sha output is
validated 40-hex before it is written (the workflow puts them in artifact
names).

Common options: ``--repo OWNER/NAME`` (default ``$GITHUB_REPOSITORY``),
``--run-id`` / ``--run-attempt`` (default ``$GITHUB_RUN_ID`` /
``$GITHUB_RUN_ATTEMPT``; recorded in intents and ``captured.run_id``),
``--gh-output FILE`` (default ``$GITHUB_OUTPUT``), ``--conf FILE`` (default
``.github/provenance.conf``), ``--repo-dir DIR`` (default ``.``). The API
token is ``$GH_TOKEN`` (read scopes for the plan modes; ``contents: write``
is used by ``publish`` alone, through ``gitstore``'s env-only credential).

Exit codes: 0 ok (including a clean budget stop, "nothing to do", and a plan
with ``foreign_tip`` — the workflow fails the job after publishing); 1
validation/contract failure, bad input, or a push transport failure; 2
argparse error; 3 tip-continuity refusal (bootstrap without the flag,
recover refused, a rejected or raced push); 4 guard violation (an add-only
rule would have been broken — nothing pushed).

Owner: H1. This module (with ``github.py``) is the only one that may read the
clock (``datetime.now``), which it passes down as ``now`` everywhere.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Optional, Sequence

#: Dispatch-input patterns (docs/provenance.md §Workflow inputs). Validated
#: with ``fullmatch``; an empty string means "not given".
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}Z)?")
PR_LIST_RE = re.compile(r"[0-9]{1,7}(,[0-9]{1,7}){0,49}")
SHA_RE = re.compile(r"[0-9a-f]{40}")
CAP_RE = re.compile(r"[0-9]{1,5}")
REPO_RE = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_FOREIGN_TIP = 3
EXIT_GUARD = 4

#: Run statuses that mean "another provenance.yml run is waiting for the group".
WAITING_STATUSES = frozenset({"queued", "in_progress", "pending", "waiting", "requested"})


class InputError(ValueError):
    """A dispatch input failed its pattern (message names the input, never echoes control bytes)."""


@dataclass(frozen=True)
class Inputs:
    """Validated harvest/refreeze/recover inputs."""

    since: Optional[str] = None
    until: Optional[str] = None
    prs: tuple[int, ...] = ()
    max_requests: Optional[int] = None
    confirm_sha: Optional[str] = None


def _check(name: str, value: Optional[str], rx: re.Pattern[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or rx.fullmatch(value) is None:
        raise InputError(f"input {name} does not match {rx.pattern}")
    return value


def validate_inputs(*, since: Optional[str] = None, until: Optional[str] = None,
                    pr: Optional[str] = None, max_requests: Optional[str] = None,
                    confirm_sha: Optional[str] = None) -> Inputs:
    """Regex-validate every free-text dispatch input (implemented by the scaffold; H1 keeps it).

    There is no ref, path or snapshot input (critique item 2): the snapshot is
    read from the default-branch checkout only. Booleans (``receipts_only``,
    ``dry_run``, ``bootstrap``) are workflow ``type: boolean`` inputs mapped to
    flags by the workflow, never free text.
    """
    s = _check("since", since, DATE_RE)
    u = _check("until", until, DATE_RE)
    p = _check("pr", pr, PR_LIST_RE)
    c = _check("max_requests", max_requests, CAP_RE)
    sha = _check("confirm_sha", confirm_sha, SHA_RE)
    return Inputs(
        since=s, until=u,
        prs=tuple(sorted({int(x) for x in p.split(",")})) if p else (),
        max_requests=int(c) if c is not None else None,
        confirm_sha=sha,
    )


def build_parser() -> argparse.ArgumentParser:
    """The complete argument parser (implemented by the scaffold)."""
    ap = argparse.ArgumentParser(prog="provenance", description="print-bench provenance harvester")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    common.add_argument("--repo-dir", default=".")
    common.add_argument("--conf", default=".github/provenance.conf")
    common.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID", "0"))
    common.add_argument("--run-attempt", default=os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    common.add_argument("--gh-output", default=os.environ.get("GITHUB_OUTPUT", ""))
    common.add_argument("--out-dir", default=".provenance")
    sub = ap.add_subparsers(dest="cmd", required=True)

    h = sub.add_parser("harvest", parents=[common], help="ingest (once) + receipts + freeze + derive (plan only)")
    h.add_argument("--since", default="")
    h.add_argument("--until", default="")
    h.add_argument("--pr", default="")
    h.add_argument("--receipts-only", action="store_true")
    h.add_argument("--max-requests", default="")
    h.add_argument("--dry-run", action="store_true")
    h.add_argument("--scheduled", action="store_true",
                   help="apply the scheduled cap (scheduled_max_requests) and never sleep")
    h.add_argument("--bootstrap", action="store_true",
                   help="create the evidence root (only when the ref is absent and no checkpoint exists)")
    h.add_argument("--snapshot-dir", default="",
                   help="tests/local only: read the snapshot from DIR instead of the conf's snapshot_dir")

    r = sub.add_parser("refreeze", parents=[common], help="capture one PR again as a new revision")
    r.add_argument("--pr", required=True)
    r.add_argument("--dry-run", action="store_true")

    sub.add_parser("publish", parents=[common], help="push what plan.json says")

    rc = sub.add_parser("recover", parents=[common],
                        help="break-glass: restore provenance to its newest checkpoint")
    rc.add_argument("--confirm-sha", required=True)

    g = sub.add_parser("gate", parents=[common], help="should this run's harvest job run?")
    g.add_argument("--scheduled", action="store_true")
    g.add_argument("--armed-var", default=os.environ.get("PROVENANCE_ENABLED", ""),
                   help="the PROVENANCE_ENABLED repo variable's raw value (schedule's second key)")

    c = sub.add_parser("check", parents=[common], help="validate a data-ref tree (a directory) against the contract")
    c.add_argument("--dir", required=True)
    c.add_argument("--kind", choices=("evidence", "derived"), required=True)

    sub.add_parser("selftest", help="offline negative-control suite")
    return ap


def utcnow() -> str:
    """The one clock read of a run (RFC3339 UTC seconds). Tests monkeypatch it. H1."""
    raise NotImplementedError("builder H1: clock")


def make_client(args: argparse.Namespace, conf: object, *, scheduled: bool,
                deadline_epoch: Optional[float]) -> object:
    """The ``protocols.GitHubAPI`` for this run (``github.Client`` with ``$GH_TOKEN``, the
    budget from the conf / ``--max-requests``, the ETag cache under ``--out-dir``). The
    orchestration tests monkeypatch it to return a ``tests.fakes.FakeGitHub``. H1."""
    raise NotImplementedError("builder H1: client factory")


def cmd_harvest(args: argparse.Namespace) -> int:
    """``harvest`` — steps 1–8 of the module docstring. H1."""
    raise NotImplementedError("builder H1: harvest orchestration")


def cmd_refreeze(args: argparse.Namespace) -> int:
    """``refreeze`` — ``freeze.refreeze`` then steps 6–8. H1 (wiring) / H6 (freeze.refreeze)."""
    raise NotImplementedError("builder H1: refreeze orchestration")


def cmd_publish(args: argparse.Namespace) -> int:
    """``publish`` — ordered pushes per ``plan.json``, then checkpoints.json. H1."""
    raise NotImplementedError("builder H1: publish")


def cmd_recover(args: argparse.Namespace) -> int:
    """``recover`` — plan the break-glass restore to the newest checkpoint. H1."""
    raise NotImplementedError("builder H1: recover")


def cmd_gate(args: argparse.Namespace) -> int:
    """``gate`` — go/no-go for this run's harvest job. H1."""
    raise NotImplementedError("builder H1: gate")


def cmd_check(args: argparse.Namespace) -> int:
    """``check`` — tree validation via ``contract.validate_tree``. H1 (wiring) / H2 (contract)."""
    raise NotImplementedError("builder H1: check")


def cmd_selftest(args: argparse.Namespace) -> int:
    """``selftest`` — ``selftest.run()``. H6."""
    from . import selftest
    return selftest.run()


COMMANDS = {
    "harvest": cmd_harvest, "refreeze": cmd_refreeze, "publish": cmd_publish,
    "recover": cmd_recover, "gate": cmd_gate, "check": cmd_check, "selftest": cmd_selftest,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point: parse, dispatch, map :class:`InputError` to exit 1."""
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except InputError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return EXIT_INVALID
