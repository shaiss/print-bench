"""CLI for the provenance harvester — argparse plus the orchestration of every mode.

The workflow (``.github/workflows/provenance.yml``) runs these subcommands
from the default-branch checkout with ``PYTHONPATH=tools/provenance/src:
tools/model-registry/src``. Dispatch inputs reach the code ONLY through
``env:`` and are passed as arguments here, where :func:`validate_inputs`
regex-checks every one before use (docs/actions-security.md: a value from
``${{ inputs.* }}`` is never interpolated into a ``run:`` script).

Subcommands (docs/provenance.md §Workflow):

``harvest``
    the default mode (schedule, or dispatch with ``mode=harvest``):
    ``[--since D] [--until D] [--pr N,N…] [--receipts-only] [--max-requests N]
    [--dry-run] [--scheduled] --out-dir DIR``. Steps, in order:

    1. fetch both data refs (``gitstore.Git.fetch``); read the evidence tip;
    2. **tip continuity** — ``gitstore.declared_intents`` +
       ``gitstore.check_tip_continuity``; a foreign evidence tip is an
       ``::error::`` and exit 3 with nothing written;
    3. receipts pass (``receipts.harvest_receipts``) over every watched
       workflow from its cursor (or ``--since``);
    4. unless ``--receipts-only``: the freeze pass (``freeze.plan_freezes``:
       settle/defer decisions, PR/brief/release capture; ``--pr`` restricts
       it to the named PRs and skips the settle wait for none of them);
    5. assemble the new evidence commit with ``gitstore.TreeBuilder`` (add-only)
       and run ``gitstore.guard_diff`` against the old tip;
    6. derive (``extract`` → ``serving`` → ``episodes`` → ``views`` →
       ``bundle``) from the NEW evidence tree + main, build the
       ``provenance-site`` commit, and compare content with the current
       derived tip (``bundle.same_content``);
    7. write ``<out-dir>/plan.json`` (refs, old tips, new commits, counts) and
       one ``<out-dir>/intent-<ref>.json`` per ref that will move, and append
       ``evidence_changed``/``evidence_sha``/``site_changed``/``site_sha``/
       ``summary`` lines to ``$GITHUB_OUTPUT`` (``--gh-output``).

    Nothing is pushed: the workflow uploads the intent artifacts, then runs
    ``publish``. ``--dry-run`` stops after step 7 and sets both ``*_changed``
    outputs false. A ``github.BudgetExhausted`` anywhere in 3–4 ends the pass
    cleanly: whatever was captured is planned, the cursors record where to
    resume, exit 0 with a ``::notice::``.
``ingest``
    ``(--snapshot-dir DIR | --ref REF [--path P]) [--dry-run] --out-dir DIR``
    — the #843 snapshot ingest (``ingest.plan_ingest``), then steps 5–7 as in
    ``harvest``. Idempotent: a second ingest of the same snapshot plans no
    evidence change.
``refreeze``
    ``--pr N [--dry-run] --out-dir DIR`` — capture PR ``N`` again as
    ``raw/pr/<N>.r<K+1>.json.gz`` (no settle wait), then steps 5–7.
``publish``
    ``--out-dir DIR`` — push what ``plan.json`` says: ``provenance``
    fast-forward only (``gitstore.push_fast_forward``), ``provenance-site``
    with ``--force-with-lease`` on the planned old tip
    (``gitstore.push_force_with_lease``). Re-checks that each remote tip
    still equals the planned old tip first.
``recover``
    ``--confirm-sha SHA`` — break-glass: reset ``provenance`` to ``SHA``,
    which must itself be a declared intent (``declared_intents``) and a
    descendant-or-equal of nothing foreign; force-with-lease on the current
    tip. The only non-fast-forward write to the evidence ref; needs a human
    dispatch (docs/provenance.md §Tip continuity, recovery).
``gate``
    ``--scheduled [--armed-var VALUE]`` — the workflow's ``gate`` job. A
    schedule needs both keys (``conf.armed(enabled, PROVENANCE_ENABLED)``);
    then one runs-list GET for
    queued/in-progress ``workflow_dispatch`` runs of provenance.yml; appends
    ``go=false`` when any exists (a scheduled harvest must not evict an
    operator's pending dispatch from the concurrency group), else
    ``go=true``. Without ``--scheduled`` (a dispatch) always ``go=true``.
``check``
    ``(--ref provenance|provenance-site | --dir DIR) [--kind evidence|derived]``
    — validate a tree against the contract: FORMAT, guard-file bytes,
    every blob's shape, receipt paths agreeing with their run ids, bundle
    digests. Exit 1 on the first class of failure, listing them all.
``selftest``
    the offline negative-control suite (``selftest.run``) — what
    ``scripts/provenance.sh --selftest`` and check.sh run.
``config``
    ``--get KEY [--path FILE]`` — print one parsed conf value.

Common options: ``--repo OWNER/NAME`` (default ``$GITHUB_REPOSITORY``),
``--run-id`` / ``--run-attempt`` (default ``$GITHUB_RUN_ID`` /
``$GITHUB_RUN_ATTEMPT``; recorded in intents and ``captured.run_id``),
``--gh-output FILE`` (default ``$GITHUB_OUTPUT``), ``--conf FILE`` (default
``.github/provenance.conf``), ``--repo-dir DIR`` (default ``.``).

Exit codes: 0 ok (including a clean budget stop and "nothing to do"); 1
validation/contract failure or bad input; 2 argparse error; 3 tip-continuity
refusal (foreign tip — the run goes red); 4 guard violation (an add-only rule
would have been broken — nothing pushed); 5 push rejected after retries
(``::warning::``; the cursors redo the work next run).

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
REF_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
PATH_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")
SNAPSHOT_ID_RE = re.compile(r"pr[0-9]{1,7}")
REPO_RE = re.compile(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}")

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_FOREIGN_TIP = 3
EXIT_GUARD = 4
EXIT_PUSH_REJECTED = 5


class InputError(ValueError):
    """A dispatch input failed its pattern (message names the input, never echoes control bytes)."""


@dataclass(frozen=True)
class Inputs:
    """Validated harvest/ingest/refreeze/recover inputs."""

    since: Optional[str] = None
    until: Optional[str] = None
    prs: tuple[int, ...] = ()
    max_requests: Optional[int] = None
    confirm_sha: Optional[str] = None
    snapshot_ref: Optional[str] = None
    snapshot_path: Optional[str] = None
    snapshot_id: Optional[str] = None


def _check(name: str, value: Optional[str], rx: re.Pattern[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or rx.fullmatch(value) is None:
        raise InputError(f"input {name} does not match {rx.pattern}")
    return value


def validate_inputs(*, since: Optional[str] = None, until: Optional[str] = None,
                    pr: Optional[str] = None, max_requests: Optional[str] = None,
                    confirm_sha: Optional[str] = None, snapshot_ref: Optional[str] = None,
                    snapshot_path: Optional[str] = None,
                    snapshot_id: Optional[str] = None) -> Inputs:
    """Regex-validate every dispatch input (implemented by the scaffold; H1 keeps it).

    ``..`` is refused in ``snapshot_ref``/``snapshot_path`` on top of the
    pattern (no path traversal through ``git show <ref>:<path>``).
    """
    s = _check("since", since, DATE_RE)
    u = _check("until", until, DATE_RE)
    p = _check("pr", pr, PR_LIST_RE)
    c = _check("max_requests", max_requests, CAP_RE)
    sha = _check("confirm_sha", confirm_sha, SHA_RE)
    ref = _check("snapshot_ref", snapshot_ref, REF_RE)
    path = _check("snapshot_path", snapshot_path, PATH_RE)
    sid = _check("snapshot_id", snapshot_id, SNAPSHOT_ID_RE)
    for name, val in (("snapshot_ref", ref), ("snapshot_path", path)):
        if val is not None and ".." in val:
            raise InputError(f"input {name} may not contain '..'")
    return Inputs(
        since=s, until=u,
        prs=tuple(sorted({int(x) for x in p.split(",")})) if p else (),
        max_requests=int(c) if c is not None else None,
        confirm_sha=sha, snapshot_ref=ref, snapshot_path=path, snapshot_id=sid,
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

    h = sub.add_parser("harvest", parents=[common], help="receipts + freeze + derive (plan only)")
    h.add_argument("--since", default="")
    h.add_argument("--until", default="")
    h.add_argument("--pr", default="")
    h.add_argument("--receipts-only", action="store_true")
    h.add_argument("--max-requests", default="")
    h.add_argument("--dry-run", action="store_true")
    h.add_argument("--scheduled", action="store_true",
                   help="apply the scheduled cap (scheduled_max_requests) and never sleep")

    i = sub.add_parser("ingest", parents=[common], help="ingest the #843 Actions/status snapshot")
    src = i.add_mutually_exclusive_group(required=True)
    src.add_argument("--snapshot-dir", default="")
    src.add_argument("--ref", default="")
    i.add_argument("--path", default="")
    i.add_argument("--snapshot-id", default="")
    i.add_argument("--dry-run", action="store_true")

    r = sub.add_parser("refreeze", parents=[common], help="capture one PR again as a new revision")
    r.add_argument("--pr", required=True)
    r.add_argument("--dry-run", action="store_true")

    sub.add_parser("publish", parents=[common], help="push what plan.json says")

    rc = sub.add_parser("recover", parents=[common], help="break-glass: reset provenance to a declared intent")
    rc.add_argument("--confirm-sha", required=True)

    g = sub.add_parser("gate", parents=[common], help="should the scheduled harvest run?")
    g.add_argument("--scheduled", action="store_true")
    g.add_argument("--armed-var", default=os.environ.get("PROVENANCE_ENABLED", ""),
                   help="the PROVENANCE_ENABLED repo variable's raw value (schedule's second key)")

    c = sub.add_parser("check", parents=[common], help="validate a data-ref tree against the contract")
    tgt = c.add_mutually_exclusive_group(required=True)
    tgt.add_argument("--ref", choices=("provenance", "provenance-site"))
    tgt.add_argument("--dir")
    c.add_argument("--kind", choices=("evidence", "derived"))

    sub.add_parser("selftest", help="offline negative-control suite")

    cf = sub.add_parser("config", help="print one .github/provenance.conf value")
    cf.add_argument("--get", required=True)
    cf.add_argument("--path", default=".github/provenance.conf")
    return ap


def cmd_harvest(args: argparse.Namespace) -> int:
    """``harvest`` — steps 1–7 of the module docstring. H1."""
    raise NotImplementedError("builder H1: harvest orchestration")


def cmd_ingest(args: argparse.Namespace) -> int:
    """``ingest`` — ``ingest.plan_ingest`` then steps 5–7. H1."""
    raise NotImplementedError("builder H1: ingest orchestration")


def cmd_refreeze(args: argparse.Namespace) -> int:
    """``refreeze`` — ``freeze.refreeze`` then steps 5–7. H1 (wiring) / H6 (freeze.refreeze)."""
    raise NotImplementedError("builder H1: refreeze orchestration")


def cmd_publish(args: argparse.Namespace) -> int:
    """``publish`` — push per ``plan.json``. H1."""
    raise NotImplementedError("builder H1: publish")


def cmd_recover(args: argparse.Namespace) -> int:
    """``recover`` — the break-glass reset. H1."""
    raise NotImplementedError("builder H1: recover")


def cmd_gate(args: argparse.Namespace) -> int:
    """``gate`` — go/no-go for the scheduled harvest. H1."""
    raise NotImplementedError("builder H1: gate")


def cmd_check(args: argparse.Namespace) -> int:
    """``check`` — tree validation via ``contract.validate_tree``. H1 (wiring) / H2 (contract)."""
    raise NotImplementedError("builder H1: check")


def cmd_selftest(args: argparse.Namespace) -> int:
    """``selftest`` — ``selftest.run()``. H6."""
    from . import selftest
    return selftest.run()


def cmd_config(args: argparse.Namespace) -> int:
    """``config --get`` — print one value from ``conf.load``. H6."""
    raise NotImplementedError("builder H6: config --get")


COMMANDS = {
    "harvest": cmd_harvest, "ingest": cmd_ingest, "refreeze": cmd_refreeze, "publish": cmd_publish,
    "recover": cmd_recover, "gate": cmd_gate, "check": cmd_check, "selftest": cmd_selftest,
    "config": cmd_config,
}


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point: parse, dispatch, map :class:`InputError` to exit 1."""
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.cmd](args)
    except InputError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return EXIT_INVALID
