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
names). ``evidence_sha`` / ``site_sha`` are the sha a ref WILL move to when its
``*_changed`` is true, else empty.

Files under ``--out-dir`` (the plan/publish contract with the workflow; a
plan-mode command first removes every one of them, so a refused run can never
leave an older plan for ``publish``):

* ``plan.json`` — ``{"format": "plan@1", "mode", "dry_run", "foreign_tip",
  "derive_skipped", "derived_from": sha|null, "budget_stopped", "run_id",
  "run_attempt", "refs": {"provenance": {"old", "new", "changed",
  "would_change", "verdict", "checkpoint"}, "provenance-site": {…}}, "counts"}``.
  ``old`` is the tip the plan saw, ``new`` the sha the ref should hold after
  publish (``== old`` when unchanged), ``changed`` what ``publish`` pushes
  (false throughout a dry run), ``would_change`` the same ignoring
  ``--dry-run``, ``checkpoint`` the newest verified checkpoint.
* ``intent-<ref>.json`` (``intent@1``) for every ref that would move (written in
  a dry run too, for inspection; the workflow uploads them only when
  ``*_changed``).
* after ``publish``: ``checkpoints.json`` = ``{"provenance": checkpoint@1|null,
  "provenance-site": …}`` and ``tip-<ref>.json`` (``checkpoint@1``) for each
  verified tip — written even when publish fails part-way, naming only what
  was verified before the failure.
* ``summary.md`` — the job summary (publish appends its line).
* ``etag-cache/`` — the client's conditional-GET cache.

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
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Sequence

from . import HARVESTER, bundle, canonical, codebasis, contract, digest, freeze, github, gitstore, ingest
from . import conf as conf_mod
from . import receipts, state, steps

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
    return datetime.now(timezone.utc).strftime(_TS_FMT)


def make_client(args: argparse.Namespace, conf: object, *, scheduled: bool,
                deadline_epoch: Optional[float]) -> object:
    """The ``protocols.GitHubAPI`` for this run (``github.Client`` with ``$GH_TOKEN``, the
    budget from the conf / ``--max-requests``, the ETag cache under ``--out-dir``). The
    orchestration tests monkeypatch it to return a ``tests.fakes.FakeGitHub``. H1.

    A scheduled run is capped at ``scheduled_max_requests`` (or the smaller
    ``--max-requests``) and never sleeps at the floor; a dispatch is capped only
    by ``--max-requests`` and self-paces."""
    cap_in = getattr(args, "max_requests", "") or ""
    cap = validate_inputs(max_requests=cap_in).max_requests
    if scheduled:
        limit: Optional[int] = conf.scheduled_max_requests
        if cap is not None:
            limit = min(limit, cap)
    else:
        limit = cap
    budget = github.Budget(max_requests=limit, floor=conf.rate_floor, pace=not scheduled,
                           deadline_epoch=deadline_epoch)
    return github.Client(repo=args.repo, token=os.environ.get("GH_TOKEN", ""), budget=budget,
                         cache_dir=os.path.join(args.out_dir, "etag-cache"))


# ---------------------------------------------------------------------------
# plumbing shared by the subcommands

_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
RUN_ID_RE = re.compile(r"[0-9]{1,20}")
PLAN_FORMAT = "plan@1"
PLAN_FILE = "plan.json"
SUMMARY_FILE = "summary.md"
CHECKPOINTS_FILE = "checkpoints.json"
EV, DV = gitstore.EVIDENCE_REF, gitstore.DERIVED_REF
PULL_REFSPEC = gitstore.FETCH_REFSPECS[2]
MAIN_REF = "refs/remotes/origin/main"
#: Output names whose value must be "" or a 40-hex sha (they become artifact names).
SHA_OUTPUTS = frozenset({"evidence_sha", "site_sha", "evidence_tip", "site_tip"})
BOOL_OUTPUTS = frozenset({"dry_run", "foreign_tip", "evidence_changed", "site_changed",
                          "derive_skipped", "budget_stopped", "go"})


class _Exit(Exception):
    """Unwind a subcommand with an exit code after its message was printed."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def _epoch(ts: str) -> int:
    return int(datetime.strptime(ts, _TS_FMT).replace(tzinfo=timezone.utc).timestamp())


def _short(sha: Optional[str]) -> str:
    return sha[:8] if sha else "(absent)"


def _err(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr, flush=True)


def _warn(msg: str) -> None:
    print(f"::warning::{msg}", file=sys.stderr, flush=True)


def _notice(msg: str) -> None:
    print(f"::notice::{msg}", file=sys.stderr, flush=True)


def write_outputs(path: str, values: dict[str, object]) -> None:
    """Append ``key=value`` lines to ``$GITHUB_OUTPUT`` (``path``; nothing when empty). Every sha
    output is validated ``""`` or 40-hex first — the workflow puts them in artifact names."""
    lines = []
    for key, value in values.items():
        if key in BOOL_OUTPUTS:
            value = "true" if value else "false"
        value = "" if value is None else str(value)
        if key in SHA_OUTPUTS and value and not SHA_RE.fullmatch(value):
            raise ValueError(f"output {key} is not a 40-hex sha")
        if "\n" in value or "\r" in value:
            raise ValueError(f"output {key} carries a newline")
        lines.append(f"{key}={value}\n")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.writelines(lines)


def _write_json(path: str, value: object) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(canonical.dumps_bytes(value))


@dataclass
class _Ctx:
    """What every subcommand resolves first: the conf, the repo, the run ids, the clock."""

    args: argparse.Namespace
    conf: object
    owner: str
    name: str
    run_id: int
    run_attempt: int
    now: str
    repo_dir: str
    out_dir: str
    summary: list


def _conf_path(args: argparse.Namespace) -> str:
    return args.conf if os.path.isabs(args.conf) else os.path.join(args.repo_dir, args.conf)


def _context(args: argparse.Namespace, *, plan_mode: bool = False) -> _Ctx:
    if not isinstance(args.repo, str) or REPO_RE.fullmatch(args.repo) is None:
        raise InputError(f"--repo does not match {REPO_RE.pattern} (set GITHUB_REPOSITORY)")
    for opt in ("run_id", "run_attempt"):
        if RUN_ID_RE.fullmatch(str(getattr(args, opt))) is None:
            raise InputError(f"--{opt.replace('_', '-')} does not match {RUN_ID_RE.pattern}")
    try:
        conf = conf_mod.load(_conf_path(args))
    except conf_mod.ConfError as exc:
        _err(f"provenance.conf: {exc}")
        raise _Exit(EXIT_INVALID) from None
    owner, name = args.repo.split("/", 1)
    os.makedirs(args.out_dir, exist_ok=True)
    if plan_mode:
        _clear_plan(args.out_dir)
    return _Ctx(args=args, conf=conf, owner=owner, name=name, run_id=int(args.run_id),
                run_attempt=int(args.run_attempt), now=utcnow(), repo_dir=args.repo_dir,
                out_dir=args.out_dir, summary=[])


def _clear_plan(out_dir: str) -> None:
    """A plan-mode command starts from an empty plan: a refused or failed run must never leave an
    earlier run's plan.json / intents / checkpoints for a later ``publish`` to act on."""
    for name in (PLAN_FILE, SUMMARY_FILE, CHECKPOINTS_FILE, *(f"intent-{r}.json" for r in (EV, DV)),
                 *(f"tip-{r}.json" for r in (EV, DV))):
        try:
            os.remove(os.path.join(out_dir, name))
        except FileNotFoundError:
            pass


def _versions() -> dict[str, object]:
    return {"contract": contract.CONTRACT_VERSION, "digest": digest.DIGEST_VERSION,
            "harvester": HARVESTER, "step_grammar": steps.STEP_GRAMMAR_VERSION}


def _git(ctx: _Ctx, token: str = "") -> gitstore.Git:
    # Commit dates pinned to the run's one clock read: identical inputs → identical commits.
    return gitstore.Git(ctx.repo_dir, env={"GIT_AUTHOR_DATE": ctx.now, "GIT_COMMITTER_DATE": ctx.now},
                        token=token)


class _NoDeadline:
    """The capture deadline bounds CAPTURE; the continuity scan is not capture."""

    def __init__(self, gh: object) -> None:
        self.budget = getattr(gh, "budget", None)
        self.saved = None

    def __enter__(self) -> "_NoDeadline":
        if self.budget is not None:
            self.saved, self.budget.deadline_epoch = self.budget.deadline_epoch, None
        return self

    def __exit__(self, *exc: object) -> None:
        if self.budget is not None:
            self.budget.deadline_epoch = self.saved


def _scan(ctx: _Ctx, gh: object, git: gitstore.Git) -> tuple[gitstore.Continuity, gitstore.Continuity, dict]:
    """Step 2: the artifact scan and both verdicts (local git answers first parents)."""
    with _NoDeadline(gh):
        marks, counts = gitstore.scan_marks(gh, git, now_epoch=_epoch(ctx.now),
                                            horizon_days=ctx.conf.continuity_horizon_days,
                                            main_ref=MAIN_REF)

    def first_parent(sha: str) -> Optional[str]:
        parents = git.parents(sha)
        return parents[0] if parents else None

    ev = gitstore.continuity_verdict(ref=EV, tip=git.rev_parse(f"refs/remotes/origin/{EV}"),
                                     marks=marks, first_parent=first_parent)
    dv = gitstore.continuity_verdict(ref=DV, tip=git.rev_parse(f"refs/remotes/origin/{DV}"),
                                     marks=marks, first_parent=first_parent)
    ctx.summary.append(f"- continuity: evidence **{ev.verdict}** (tip {_short(ev.tip)}, checkpoint "
                       f"{_short(ev.checkpoint)}) · derived **{dv.verdict}** (tip {_short(dv.tip)}, "
                       f"checkpoint {_short(dv.checkpoint)}) · scan {counts}")
    return ev, dv, counts


def _intent(ctx: _Ctx, ref: str, sha: str, parent: Optional[str]) -> dict:
    return {"format": "intent@1", "parent": parent, "ref": ref, "run_attempt": ctx.run_attempt,
            "run_id": ctx.run_id, "sha": sha}


def _checkpoint(run_id: int, run_attempt: int, ref: str, sha: str) -> dict:
    return {"format": "checkpoint@1", "ref": ref, "run_attempt": run_attempt, "run_id": run_id, "sha": sha}


def _write_summary(ctx: _Ctx, title: str) -> None:
    text = f"## Provenance {title}\n\n" + "\n".join(ctx.summary) + "\n"
    with open(os.path.join(ctx.out_dir, SUMMARY_FILE), "w", encoding="utf-8") as fh:
        fh.write(text)


def _ref_entry(old: Optional[str], new: Optional[str], changed: bool, dry_run: bool,
               verdict: str, checkpoint: Optional[str]) -> dict:
    return {"changed": bool(changed and not dry_run), "checkpoint": checkpoint, "new": new, "old": old,
            "verdict": verdict, "would_change": bool(changed)}


def _emit_plan(ctx: _Ctx, *, mode: str, dry_run: bool, foreign_tip: bool, derive_skipped: bool,
               derived_from: Optional[str], budget_stopped: bool, refs: dict, counts: dict,
               parents: dict) -> None:
    """Step 8: plan.json, the intent files of every ref that would move, summary, outputs."""
    for ref in (EV, DV):
        try:
            os.remove(os.path.join(ctx.out_dir, f"intent-{ref}.json"))
        except FileNotFoundError:
            pass
        r = refs[ref]
        if r["would_change"] and r["new"]:
            _write_json(os.path.join(ctx.out_dir, f"intent-{ref}.json"),
                        _intent(ctx, ref, r["new"], parents.get(ref)))
    plan = {"budget_stopped": budget_stopped, "counts": counts, "derive_skipped": derive_skipped,
            "derived_from": derived_from, "dry_run": dry_run, "foreign_tip": foreign_tip,
            "format": PLAN_FORMAT, "mode": mode, "refs": refs, "run_attempt": ctx.run_attempt,
            "run_id": ctx.run_id}
    _write_json(os.path.join(ctx.out_dir, PLAN_FILE), plan)
    ev, dv = refs[EV], refs[DV]
    ctx.summary.append(f"- evidence: {_short(ev['old'])} → {_short(ev['new'])} "
                       f"({'would change' if ev['would_change'] else 'unchanged'}"
                       f"{', dry run' if dry_run and ev['would_change'] else ''})")
    ctx.summary.append(f"- derived: {_short(dv['old'])} → {_short(dv['new'])} "
                       f"({'would change' if dv['would_change'] else 'unchanged'}"
                       f"{', dry run' if dry_run and dv['would_change'] else ''})")
    _write_summary(ctx, mode)
    write_outputs(ctx.args.gh_output, {
        "mode": mode, "dry_run": dry_run, "foreign_tip": foreign_tip,
        "evidence_changed": ev["changed"], "evidence_sha": ev["new"] if ev["changed"] else "",
        "site_changed": dv["changed"], "site_sha": dv["new"] if dv["changed"] else "",
        "derive_skipped": derive_skipped, "budget_stopped": budget_stopped,
    })


def _noop_plan(ctx: _Ctx, mode: str, dry_run: bool, reason: str) -> int:
    """A plan that moves nothing and checkpoints nothing (budget stopped before continuity)."""
    _notice(reason)
    ctx.summary.append(f"- stopped: {reason}")
    refs = {ref: _ref_entry(None, None, False, dry_run, "unknown", None) for ref in (EV, DV)}
    _emit_plan(ctx, mode=mode, dry_run=dry_run, foreign_tip=False, derive_skipped=True, derived_from=None,
               budget_stopped=True, refs=refs, counts={}, parents={})
    return EXIT_OK


def _apply_freeze(st: dict, fp: "freeze.FreezePlan") -> None:
    """Apply a FreezePlan's state updates through state.py (the cli is state's only writer).

    ``fp.pending`` is read as ``{kind: {key: {closed_at, due_at, defer_until, reasons}}}``
    (kinds ``pr``/``brief``); every ``frozen`` unit leaves ``pending`` (and a PR leaves
    ``skipped``); a skipped PR leaves ``pending``; a freeze cursor is set when the plan
    names a value (``None`` keeps the stored cursor)."""
    for kind, entries in (fp.pending or {}).items():
        if kind not in state.PENDING_KINDS or not isinstance(entries, dict):
            raise ValueError(f"FreezePlan.pending: unexpected kind {kind!r}")
        for key, e in entries.items():
            state.set_pending(st, kind, str(key), closed_at=e.get("closed_at"), due_at=e["due_at"],
                              defer_until=e["defer_until"], reasons=list(e.get("reasons") or []))
    for kind, key, _rev in list(fp.frozen) + list(fp.recaptured):
        if kind in state.PENDING_KINDS:
            state.clear_pending(st, kind, str(key))
        if kind == "pr":
            st["skipped"]["pr"].pop(str(key), None)
    for pr, closed_at in (fp.skipped_prs or {}).items():
        state.set_skipped(st, int(pr), closed_at)
        state.clear_pending(st, "pr", str(pr))
    for key, value in (fp.cursors or {}).items():
        if key in state.FREEZE_CURSORS and value is not None:
            st["cursors"][key] = value


def _date_floor(conf: object, since: Optional[str], until: Optional[str]) -> None:
    lo = f"{conf.backfill_since}T00:00:00Z"
    s = receipts.normalize_bound(since, end=False) if since else None
    u = receipts.normalize_bound(until, end=True) if until else None
    if s is not None and s < lo:
        raise InputError(f"input since is earlier than backfill_since ({conf.backfill_since})")
    if s is not None and u is not None and s > u:
        raise InputError("input since is after until")


def _run_plan(ctx: _Ctx, *, mode: str, inputs: Inputs, bootstrap: bool = False,
              receipts_only: bool = False, dry_run: bool = False, scheduled: bool = False,
              snapshot_dir: str = "") -> int:
    """harvest / refreeze: steps 1–8 of the module docstring (nothing is pushed here)."""
    conf = ctx.conf
    git = _git(ctx)
    start = _epoch(ctx.now)
    deadline = None if scheduled else float(start + (conf.dispatch_max_minutes - conf.derive_reserve_minutes) * 60)
    gh = make_client(ctx.args, conf, scheduled=scheduled, deadline_epoch=deadline)
    ctx.summary.append(f"- mode **{mode}**{' (dry run)' if dry_run else ''}{' (scheduled)' if scheduled else ''}"
                       f" · now {ctx.now} · run {ctx.run_id}.{ctx.run_attempt}")

    # 1. fetch — token-less, once.
    fetched = git.fetch_all()
    derive_skipped = not fetched[PULL_REFSPEC]
    reasons: list[str] = []
    if derive_skipped:
        reasons.append("the bulk PR-head fetch failed")
        _err("the token-less PR-head fetch failed: evidence is still planned, no derived push this run")
    main_sha = git.rev_parse(MAIN_REF) or git.rev_parse("HEAD")

    # 2. continuity.
    try:
        ev, dv, scan_counts = _scan(ctx, gh, git)
    except github.BudgetExhausted as exc:
        return _noop_plan(ctx, mode, dry_run, f"budget stopped before tip continuity could be judged ({exc})")
    if bootstrap and ev.verdict != "bootstrap":
        _err(f"--bootstrap refused: the evidence verdict is {ev.verdict} ({ev.reason}); a root is created "
             "only when the ref is absent and no checkpoint exists in the horizon")
        _write_summary(ctx, mode)
        return EXIT_INVALID
    if ev.verdict == "bootstrap" and not bootstrap:
        _err("refs/heads/provenance is absent and no checkpoint exists in the horizon: dispatch "
             "harvest with bootstrap=true to create the evidence root (never automatic)")
        ctx.summary.append("- refused: bootstrap needs the flag")
        _write_summary(ctx, mode)
        return EXIT_FOREIGN_TIP
    foreign_tip = ev.verdict in ("foreign", "deleted", "unanchored")
    if foreign_tip and mode == "refreeze":
        _err(f"refreeze refused: the evidence tip failed continuity ({ev.verdict}: {ev.reason})")
        _write_summary(ctx, mode)
        return EXIT_FOREIGN_TIP
    if foreign_tip:
        _err(f"evidence tip {_short(ev.tip)} failed continuity ({ev.verdict}: {ev.reason}); no evidence is "
             f"written this run and the derived ref is rebuilt from checkpoint {_short(ev.checkpoint)}")
    base = ev.tip if ev.verdict == "ok" else None
    bootstrapping = ev.verdict == "bootstrap"

    guard = gitstore.guard_blobs(ctx.repo_dir)
    counts: dict[str, object] = {"requests": 0, "not_modified": 0}
    budget_stopped = False
    ev_new: Optional[str] = ev.tip
    ev_changed = False

    if not foreign_tip:
        tree = gitstore.GitTreeReader(git, base)
        existing_paths = set(tree.paths())
        st = state.load_state(tree.read(state.STATE_PATH), _versions())
        planned: dict[str, bytes] = {}

        def read(path: str) -> Optional[bytes]:
            return planned[path] if path in planned else tree.read(path)

        def exists(path: str) -> bool:
            return path in planned or path in existing_paths

        # 3. ingest (harvest only; ≈ 0 requests).
        if mode == "harvest" and ingest.needs_ingest(st, conf.snapshot_id):
            sdir = snapshot_dir or os.path.join(ctx.repo_dir, conf.snapshot_dir)
            data = ingest.read_snapshot(sdir, conf.snapshot_id, conf.snapshot_manifest_sha256)
            ip = ingest.plan_ingest(data, watched=conf.watched_workflows, commit=conf.snapshot_commit,
                                    cursors=st["cursors"]["receipts"], existing=read)
            planned.update(ip.files)
            st["cursors"]["receipts"].update(ip.cursors)
            st["ingested"][conf.snapshot_id] = ip.state_entry
            counts["ingest"] = {"conflicts": ip.conflicts, "existing": ip.receipts_existing,
                                "full": ip.receipts_full, "missing_jobs": ip.missing_jobs,
                                "planned": len(ip.files), "statuses": ip.statuses, "stub": ip.receipts_stub}
            ctx.summary.append(f"- ingest {conf.snapshot_id}: {len(ip.files)} files planned "
                               f"({ip.receipts_full} full / {ip.receipts_stub} stub receipts, {ip.statuses} "
                               f"status files), {ip.receipts_existing} identical, {ip.conflicts} conflicts, "
                               f"{ip.missing_jobs} without jobs, snapshot end {data.snapshot_end}")

        # 4. receipts.
        if mode == "harvest":
            rp = receipts.harvest_receipts(
                gh, workflows=conf.watched_workflows, cursors=st["cursors"]["receipts"], since=inputs.since,
                until=inputs.until, now=ctx.now, lookback_hours=conf.receipt_lookback_hours,
                default_cursor=f"{conf.backfill_since}T00:00:00Z", exists=exists)
            planned.update(rp.files)
            st["cursors"]["receipts"].update(rp.cursors)
            budget_stopped = budget_stopped or rp.budget_stopped
            counts["receipts"] = {"full": rp.full, "gone": rp.gone, "in_progress": rp.in_progress,
                                  "listed": rp.listed, "skipped": rp.skipped_runs, "stub": rp.stub,
                                  "windows": rp.windows}
            ctx.summary.append(f"- receipts: {rp.full} full / {rp.stub} stub from {rp.listed} listed runs in "
                               f"{rp.windows} windows ({rp.skipped_runs} skipped, {rp.in_progress} in progress)")
            for step_name, n in sorted(rp.suspicious.items()):
                ctx.summary.append(f"- unknown.step ×{n}: `{step_name}`")

        # 5. freeze / refreeze.
        if not budget_stopped and ((mode == "harvest" and not receipts_only) or mode == "refreeze"):
            frozen = state.frozen_from_paths(existing_paths | set(planned))
            try:
                plans = []
                if mode == "harvest":
                    plans.append(freeze.plan_freezes(gh, state=st, frozen=frozen, conf=conf, now=ctx.now,
                                                     read=read, only_prs=inputs.prs))
                else:
                    for n in inputs.prs:
                        plans.append(freeze.refreeze(gh, n, state=st, frozen=frozen, conf=conf, read=read))
                        frozen = state.frozen_from_paths(existing_paths | set(planned) | set(plans[-1].files))
            except github.BudgetExhausted:
                budget_stopped = True
            for fp in plans:
                _apply_freeze(st, fp)
                planned.update(fp.files)
                budget_stopped = budget_stopped or fp.budget_stopped
            pending_n = sum(len(v) for v in st["pending"].values())
            counts["freeze"] = {"frozen": sum(len(p.frozen) for p in plans), "pending": pending_n,
                                "recaptured": sum(len(p.recaptured) for p in plans),
                                "skipped": sum(len(p.skipped_prs) for p in plans)}
            ctx.summary.append(f"- freeze: {counts['freeze']}")
        if budget_stopped:
            _notice(f"capture stopped cleanly ({getattr(getattr(gh, 'budget', None), 'stopped', None) or 'budget'}); "
                    "the cursors in state.json resume it on the next run")

        # 6. evidence commit (add-only; guard files only at bootstrap).
        tb = gitstore.TreeBuilder(git, base)
        if bootstrapping:
            for path, (fmode, data) in sorted(guard.items()):
                tb.add(path, data, fmode)
            tb.add("README.md", gitstore.EVIDENCE_README)
            tb.add("FORMAT", bundle.EVIDENCE_FORMAT_BYTES)
        for path in sorted(planned):
            tb.add(path, planned[path])
        tb.replace(state.STATE_PATH, state.dump_state(st))
        new_tree = tb.write_tree()
        if base is not None and new_tree == gitstore.tree_of(git, base):
            ev_new = base
        else:
            msg = (f"provenance: evidence from run {ctx.run_id}.{ctx.run_attempt} ({mode})\n\n"
                   f"{len(planned)} new file(s); generated by .github/workflows/provenance.yml.\n")
            candidate = gitstore.commit_tree(git, new_tree, base, msg)
            changes = gitstore.guard_diff(git, base, candidate)
            ev_new = candidate if changes else base
            counts["evidence_changes"] = len(changes)
        ev_changed = ev_new != base
        if base is not None:
            for path in gitstore.guard_drift(gitstore.GitTreeReader(git, base), guard):
                _warn(f"guard drift: {path} on the evidence ref differs from main's "
                      f"{gitstore.GUARD_FILES[path][1]} (kept: the evidence ref keeps its bootstrap bytes)")
                ctx.summary.append(f"- guard drift: `{path}` (warning)")

    # 7. derive — from this run's evidence commit, or the newest checkpoint when foreign.
    derived_from = ev.checkpoint if foreign_tip else ev_new
    dv_new: Optional[str] = dv.tip
    site_changed = False
    if not derive_skipped:
        if derived_from is None:
            derive_skipped = True
            reasons.append("no evidence commit to derive from (no checkpoint in the horizon)")
        elif not git.has_commit(derived_from):
            derive_skipped = True
            reasons.append(f"evidence commit {_short(derived_from)} is not local")
        elif main_sha is None:
            derive_skipped = True
            reasons.append("main is not local")
    if not derive_skipped:
        try:
            dt = bundle.derive(
                gitstore.GitTreeReader(git, derived_from), git=git,
                codebasis=codebasis.GitCodeBasis(git, ambiguity_window_seconds=conf.ambiguity_window_minutes * 60),
                main_sha=main_sha, owner=ctx.owner, repo=ctx.name, owner_login=ctx.owner,
                evidence_sha=derived_from, producer_run=ctx.run_id,
                edit_grace_seconds=conf.edit_grace_seconds, guard=guard)
        except Exception as exc:  # a derive bug must not block evidence capture (receipts expire)
            derive_skipped = True
            reasons.append(f"derive failed ({type(exc).__name__})")
            counts["derive_error"] = type(exc).__name__
            _err(f"derive failed ({type(exc).__name__}: {str(exc)[:200]}); no derived push this run")
        else:
            dtb = gitstore.DerivedTreeBuilder(git)
            for path, (fmode, data) in sorted(dt.files.items()):
                dtb.set(path, data, fmode)
            dtree = dtb.write_tree()
            current = gitstore.GitTreeReader(git, dv.tip) if dv.tip and git.has_commit(dv.tip) else None
            same = bundle.same_content(current, dt.files)
            site_changed = (not dv.accepted) or (not same)
            if site_changed:
                dv_new = gitstore.commit_tree(git, dtree, None,
                                              f"provenance-site: derived from evidence {derived_from} "
                                              f"and main {main_sha}\n")
                if dv.verdict in ("foreign", "deleted"):
                    _err(f"derived tip {_short(dv.tip)} failed continuity ({dv.verdict}: {dv.reason}); "
                         "it is overwritten with the verified tree")
                elif dv.verdict in ("bootstrap", "unanchored"):
                    _notice(f"derived ref {dv.verdict}: it is (re)created from the verified tree")
            counts["derived"] = dict(sorted((dt.counts or {}).items()))
            ctx.summary.append(f"- derived counts: {counts['derived']}")
    if derive_skipped:
        ctx.summary.append(f"- derive skipped: {'; '.join(reasons) or 'n/a'}")
        if dv.verdict in ("foreign", "deleted"):
            _err(f"derived tip {_short(dv.tip)} is {dv.verdict} ({dv.reason}) and could not be rebuilt this run")
        elif not dv.accepted:
            _notice(f"derived ref is {dv.verdict}; it is (re)created once a derive succeeds")
    counts["requests"] = getattr(getattr(gh, "budget", None), "used", len(getattr(gh, "calls", [])))
    counts["not_modified"] = getattr(getattr(gh, "budget", None), "not_modified", 0)
    counts["scan"] = scan_counts
    ctx.summary.append(f"- requests: {counts['requests']} (304s: {counts['not_modified']})"
                       f"{' · budget stopped' if budget_stopped else ''}")
    for ref, sha in ((EV, ev_new), (DV, dv_new)):
        files, size = git.tree_size(sha)
        ctx.summary.append(f"- {ref} tree: {files} files, {size} bytes")
    refs = {
        EV: _ref_entry(ev.tip, ev_new, ev_changed, dry_run, ev.verdict, ev.checkpoint),
        DV: _ref_entry(dv.tip, dv_new, site_changed, dry_run, dv.verdict, dv.checkpoint),
    }
    _emit_plan(ctx, mode=mode, dry_run=dry_run, foreign_tip=foreign_tip, derive_skipped=derive_skipped,
               derived_from=derived_from if not derive_skipped else None, budget_stopped=budget_stopped,
               refs=refs, counts=counts, parents={EV: base, DV: None})
    return EXIT_OK


def _guarded(fn, *a, **kw) -> int:
    """Map the package's exceptions to the documented exit codes."""
    try:
        return fn(*a, **kw)
    except _Exit as exc:
        return exc.code
    except gitstore.GuardViolation as exc:
        _err(f"guard: {exc} — nothing is pushed")
        return EXIT_GUARD
    except gitstore.ForeignTip as exc:
        _err(f"tip continuity: {exc}")
        return EXIT_FOREIGN_TIP
    except (gitstore.GitError, ingest.IngestError, github.APIError, github.Truncated,
            github.GraphQLUnavailable) as exc:
        _err(f"{type(exc).__name__}: {exc}")
        return EXIT_INVALID


def cmd_harvest(args: argparse.Namespace) -> int:
    """``harvest`` — steps 1–8 of the module docstring. H1."""
    def body() -> int:
        inputs = validate_inputs(since=args.since, until=args.until, pr=args.pr, max_requests=args.max_requests)
        ctx = _context(args, plan_mode=True)
        _date_floor(ctx.conf, inputs.since, inputs.until)
        return _run_plan(ctx, mode="harvest", inputs=inputs, bootstrap=args.bootstrap,
                         receipts_only=args.receipts_only, dry_run=args.dry_run, scheduled=args.scheduled,
                         snapshot_dir=args.snapshot_dir)
    return _guarded(body)


def cmd_refreeze(args: argparse.Namespace) -> int:
    """``refreeze`` — ``freeze.refreeze`` then steps 6–8. H1 (wiring) / H6 (freeze.refreeze)."""
    def body() -> int:
        inputs = validate_inputs(pr=args.pr)
        if not inputs.prs:
            raise InputError("refreeze needs --pr")
        ctx = _context(args, plan_mode=True)
        return _run_plan(ctx, mode="refreeze", inputs=inputs, dry_run=args.dry_run)
    return _guarded(body)


def _read_plan(out_dir: str) -> dict:
    with open(os.path.join(out_dir, PLAN_FILE), encoding="utf-8") as fh:
        plan = json.load(fh)
    if plan.get("format") != PLAN_FORMAT or plan.get("mode") not in ("harvest", "refreeze", "recover"):
        raise ValueError("plan.json is not a plan@1 document")
    for ref in (EV, DV):
        r = plan["refs"][ref]
        for key in ("old", "new"):
            if r.get(key) is not None and not SHA_RE.fullmatch(str(r[key])):
                raise ValueError(f"plan.json refs.{ref}.{key} is not a 40-hex sha")
    return plan


def cmd_publish(args: argparse.Namespace) -> int:
    """``publish`` — ordered pushes per ``plan.json``, then checkpoints.json. H1."""
    out_dir = args.out_dir
    try:
        plan = _read_plan(out_dir)
    except (OSError, ValueError, KeyError) as exc:
        _err(f"publish: cannot read {PLAN_FILE} ({type(exc).__name__}: {exc})")
        return EXIT_INVALID
    run_id, run_attempt = int(plan["run_id"]), int(plan["run_attempt"])
    ev, dv = plan["refs"][EV], plan["refs"][DV]
    tips: dict[str, str] = {EV: "", DV: ""}
    code = EXIT_OK

    def finish() -> int:
        ckpts = {}
        for ref in (EV, DV):
            path = os.path.join(out_dir, f"tip-{ref}.json")
            if tips[ref]:
                ckpts[ref] = _checkpoint(run_id, run_attempt, ref, tips[ref])
                _write_json(path, ckpts[ref])
            else:
                ckpts[ref] = None
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
        _write_json(os.path.join(out_dir, CHECKPOINTS_FILE), ckpts)
        try:
            with open(os.path.join(out_dir, SUMMARY_FILE), "a", encoding="utf-8") as fh:
                fh.write(f"- publish (exit {code}): checkpoint evidence {_short(tips[EV] or None)} · "
                         f"derived {_short(tips[DV] or None)}"
                         f"{' · foreign evidence tip: the verdict step fails the job' if plan['foreign_tip'] else ''}\n")
        except OSError:
            pass
        write_outputs(args.gh_output, {"evidence_tip": tips[EV], "site_tip": tips[DV],
                                       "foreign_tip": bool(plan["foreign_tip"])})
        return code

    if plan["dry_run"]:
        _notice("publish: the plan is a dry run — nothing is pushed and nothing is checkpointed")
        return finish()
    git = gitstore.Git(args.repo_dir, token=os.environ.get("GH_TOKEN", ""))
    try:
        heads = git.remote_heads((EV, DV))
        if not plan["foreign_tip"] and heads.get(EV) != ev["old"]:
            raise gitstore.ForeignTip(f"{EV} moved since the plan: {_short(heads.get(EV))} is not the planned "
                                      f"{_short(ev['old'])}")
        if heads.get(DV) != dv["old"]:
            raise gitstore.ForeignTip(f"{DV} moved since the plan: {_short(heads.get(DV))} is not the planned "
                                      f"{_short(dv['old'])}")
        # (1) evidence: fast-forward only (recover: the one force-with-lease of the evidence ref).
        if plan["mode"] == "recover":
            gitstore.push_force_with_lease(git, EV, ev["new"], ev["old"])
            tips[EV] = ev["new"]
        elif ev["changed"]:
            gitstore.push_fast_forward(git, EV, ev["new"], ev["old"])
            tips[EV] = ev["new"]
        elif not plan["foreign_tip"] and ev["verdict"] == "ok" and ev["old"]:
            tips[EV] = ev["old"]
        # (2) derived: only after (1) pushed, was unchanged, or the plan derived from C.
        if dv["changed"]:
            gitstore.push_force_with_lease(git, DV, dv["new"], dv["old"])
            tips[DV] = dv["new"]
        elif dv["verdict"] == "ok" and dv["old"]:
            tips[DV] = dv["old"]
    except gitstore.ForeignTip as exc:
        _err(f"publish refused: {exc} — nothing further is pushed")
        code = EXIT_FOREIGN_TIP
    except gitstore.GitError as exc:
        _err(f"publish: push transport failure: {exc}")
        code = EXIT_INVALID
    finally:
        git.close()
    return finish()


def cmd_recover(args: argparse.Namespace) -> int:
    """``recover`` — plan the break-glass restore to the newest checkpoint. H1."""
    def body() -> int:
        inputs = validate_inputs(confirm_sha=args.confirm_sha)
        if inputs.confirm_sha is None:
            raise InputError("recover needs --confirm-sha")
        ctx = _context(args, plan_mode=True)
        git = _git(ctx)
        gh = make_client(args, ctx.conf, scheduled=False, deadline_epoch=None)
        ctx.summary.append(f"- mode **recover** · now {ctx.now} · run {ctx.run_id}.{ctx.run_attempt}")
        git.fetch_data_refs()
        ev, dv, _ = _scan(ctx, gh, git)
        if ev.verdict not in ("foreign", "deleted"):
            _err(f"recover refused: the evidence verdict is {ev.verdict} ({ev.reason}); recover runs only "
                 "while the evidence tip fails continuity (foreign or deleted)")
            _write_summary(ctx, "recover")
            return EXIT_FOREIGN_TIP
        if inputs.confirm_sha != ev.checkpoint:
            _err(f"recover refused: confirm_sha {_short(inputs.confirm_sha)} is not the newest evidence "
                 f"checkpoint {_short(ev.checkpoint)}")
            _write_summary(ctx, "recover")
            return EXIT_FOREIGN_TIP
        c = ev.checkpoint
        if not git.has_commit(c):
            git.fetch(c)
        if not git.has_commit(c):
            _err(f"recover: checkpoint {c} is not fetchable from origin; push exactly that sha from any "
                 "clone that holds it (tip == checkpoint is ok)")
            _write_summary(ctx, "recover")
            return EXIT_FOREIGN_TIP
        parents = git.parents(c)
        refs = {EV: _ref_entry(ev.tip, c, True, False, ev.verdict, ev.checkpoint),
                DV: _ref_entry(dv.tip, dv.tip, False, False, dv.verdict, dv.checkpoint)}
        ctx.summary.append(f"- recover: force-with-lease {_short(c)} over {_short(ev.tip)}")
        _emit_plan(ctx, mode="recover", dry_run=False, foreign_tip=False, derive_skipped=True, derived_from=None,
                   budget_stopped=False, refs=refs, counts={}, parents={EV: parents[0] if parents else None})
        return EXIT_OK
    return _guarded(body)


def cmd_gate(args: argparse.Namespace) -> int:
    """``gate`` — go/no-go for this run's harvest job. H1."""
    def body() -> int:
        ctx = _context(args)
        conf = ctx.conf
        go = bool(conf.enabled)
        why = "conf enabled" if go else "conf enabled is false"
        if go and args.scheduled:
            if not conf_mod.armed(conf.enabled, args.armed_var):
                go, why = False, "schedule disarmed (PROVENANCE_ENABLED is not 'true')"
            else:
                gh = make_client(args, conf, scheduled=True, deadline_epoch=None)
                try:
                    page = gh.get("/actions/workflows/provenance.yml/runs", {"per_page": "100"})
                except github.BudgetExhausted as exc:
                    go, why = False, f"budget: {exc}"
                else:
                    runs = page.get("workflow_runs", []) if isinstance(page, dict) else []
                    waiting = [r.get("id") for r in runs
                               if r.get("id") != ctx.run_id and r.get("status") in WAITING_STATUSES]
                    if waiting:
                        go, why = False, f"another provenance.yml run is waiting or running ({waiting[0]})"
        _notice(f"gate: go={'true' if go else 'false'} — {why}")
        write_outputs(args.gh_output, {"go": go})
        return EXIT_OK
    return _guarded(body)


def cmd_check(args: argparse.Namespace) -> int:
    """``check`` — tree validation via ``contract.validate_tree``. H1 (wiring) / H2 (contract)."""
    def body() -> int:
        if not os.path.isdir(args.dir):
            raise InputError("--dir is not a directory")
        reader = gitstore.DirTreeReader(args.dir)
        errors = contract.validate_tree(reader, args.kind)
        try:
            guard = gitstore.guard_blobs(args.repo_dir)
        except gitstore.GuardViolation as exc:
            _warn(f"check: {exc}")
        else:
            for path in gitstore.guard_drift(reader, guard):
                _warn(f"guard drift: {path} differs from main's {gitstore.GUARD_FILES[path][1]}")
        for e in errors:
            _err(e)
        print(f"check {args.kind}: {len(reader.paths())} files, {len(errors)} error(s)")
        return EXIT_INVALID if errors else EXIT_OK
    return _guarded(body)


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
