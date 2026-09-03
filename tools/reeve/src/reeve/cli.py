"""Command-line entry point for Reeve, the platform PM's ops routine.

    reeve report   # snapshot JSON in -> markdown report out
    reeve gather    # read committed files -> snapshot JSON
    reeve run       # gather then report (what the workflow runs)
    reeve config    # read the committed policy file
    reeve armed     # the two-key arming decision, as an output
    reeve greenlight-select  # the draftable parked-decision queue, as numbers
    reeve greenlight-poll    # poll prior greenlights' reactions; push approvals
    reeve greenlight-context  # the drafter's precedent digest (log + owner replies)
    reeve greenlight-append   # records for newly-resolved rounds + the updated log

``report`` is the pure, tested core; ``gather`` is the thin file read; ``run``
composes them. The workflow stays a few lines of glue with no policy of its
own — including the arming decision, which is code here (``config.armed``)
rather than YAML expression soup, so the 2x2 variable-by-conf matrix is
unit-tested.

``gather`` and ``run`` take an optional ``--repo owner/name`` (issue #313):
when set, the GET-only run-health read (``github.gather_run_health``) is
attached to the snapshot as ``runHealth``. Without it the run stays entirely
offline and the two run-health detectors read "not evaluated".

``greenlight-select`` (issue #443) is the greenlight loop's trusted Select
step: it lists the open ``needs-decision`` issues that carry no greenlight
marker yet (``github.gather_greenlight_queue``, GET-only) and prints the
oldest ``greenlight_cap`` of them as space-separated numbers — the bounded
set the workflow hands the drafter as ``$REEVE_SELECTED_ISSUES``, so the
agent never sees an issue it cannot post on.

``greenlight-poll`` (issue #444) is the loop's authority half: GitHub fires
no webhook for reactions, so the NEXT run polls its own prior greenlight
comments' reactions (permission-checked — only write/maintain/admin
counts), and pushes an approved verdict through the decide.yml sequence via
the API (never a posted ``/decide`` command). Its writes live in the
package's one confined seam, ``pushthrough.py``; the ledger commit
authenticates with ``REGEN_TOKEN`` — when that PAT is absent the append is
skipped with a notice (the label still carries the verdict, decide.yml's
documented degradation), never attempted with the workflow token.
``greenlight-context`` and ``greenlight-append`` (issue #445) are the loop's
learning half. The first renders the drafter's precedent digest — the most
recent ``greenlight_precedent_cap`` records of the committed log plus the
inline owner replies on their threads (GET-only gather) — as the prompt
fragment the workflow injects. The second is the observer: it gathers every
greenlighted thread's resolution state, derives the records for rounds that
resolved and are not yet recorded (``greenlights.derive_records``, pure), and
writes the updated log; the push to the ``telemetry`` data branch is trusted
workflow bash, so this package still writes nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

from . import config as config_mod
from . import greenlights
from .detectors import evaluate
from .report import render


def _load_snapshot(path: Optional[str]) -> dict[str, Any]:
    """Load a snapshot from ``path`` (or stdin when ``path`` is None/``-``)."""
    if path and path != "-":
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def _load_config(path: Optional[str]) -> config_mod.Config:
    """The committed policy when ``--conf`` was given, else the defaults."""
    return config_mod.load(path) if path else config_mod.Config()


def _token() -> str:
    """The GitHub token from ``GH_TOKEN``/``GITHUB_TOKEN`` (``""`` if unset)."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _gather(args: argparse.Namespace) -> dict[str, Any]:
    """The snapshot for ``--root``, plus run health when ``--repo`` was given."""
    from .signals import gather_snapshot  # here so the pure commands need no filesystem walk

    snapshot = gather_snapshot(args.root)
    if args.repo:
        # Lazy for the same reason signals is — and stricter: github.py is the
        # one network-capable module, and importing it at module top would put
        # cli.py in breach of the purity test. The offline default never
        # touches it.
        from .github import gather_run_health

        snapshot["runHealth"] = gather_run_health(args.repo, _token())
    return snapshot


def _emit_report(snapshot: dict[str, Any], args: argparse.Namespace) -> int:
    cfg = _load_config(args.conf)
    body = render(evaluate(snapshot, cfg), snapshot, cfg)
    sys.stdout.write(body)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """`report`: render the bench-health report from a snapshot file/stdin."""
    return _emit_report(_load_snapshot(args.input), args)


def cmd_gather(args: argparse.Namespace) -> int:
    """`gather`: print the snapshot for ``--root`` (and ``--repo``) as JSON."""
    json.dump(_gather(args), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """`run`: gather the committed pulse then render the report."""
    return _emit_report(_gather(args), args)


def cmd_config(args: argparse.Namespace) -> int:
    """`config --get <key>`: print one committed policy value."""
    path = args.path or config_mod.DEFAULT_PATH
    sys.stdout.write(config_mod.get(args.get, path=path) + "\n")
    return 0


def cmd_armed(args: argparse.Namespace) -> int:
    """`armed`: print the two-key arming decision and expose it as an output.

    Always exits 0 — the *decision* is the output (``true``/``false``), and
    the workflow gates later steps on it; a non-zero exit would read as Reeve
    failing rather than Reeve deciding not to run.
    """
    verdict = "true" if config_mod.armed(args.variable, args.conf_enabled) else "false"
    sys.stdout.write(verdict + "\n")
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"armed={verdict}\n")
    return 0


def cmd_greenlight_select(args: argparse.Namespace) -> int:
    """`greenlight-select`: print the draftable parked-decision queue.

    One line of space-separated issue numbers — the open ``needs-decision``
    issues with no greenlight marker yet (and not a provider-triage
    escalation, which the gather skips), oldest first, bounded by the conf's
    ``greenlight_cap`` (so every issue the drafter is handed is postable
    within the same run's cap). The same string is appended to
    ``$GITHUB_OUTPUT`` as ``issues=`` (the ``armed`` precedent), so the
    workflow needs no stdout scraping. An empty queue prints an empty line
    and writes ``issues=`` — a legitimate state, not a failure.
    """
    # Lazy for the same reason as in _gather: github.py is the one
    # network-capable module, and cli.py stays on the purity test's list.
    from .github import gather_greenlight_queue

    cfg = _load_config(args.conf)
    queue = gather_greenlight_queue(args.repo, _token())["queue"]
    nums = " ".join(str(issue["number"]) for issue in queue[: cfg.greenlight_cap])
    sys.stdout.write(nums + "\n")
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"issues={nums}\n")
    return 0


def cmd_greenlight_poll(args: argparse.Namespace) -> int:
    """`greenlight-poll`: poll prior greenlights, push what is approved.

    The authority half of the loop (issue #444): for every open parked
    decision with a live greenlight, read the greenlight's reactions
    (GET-only), keep only reactions from write/maintain/admin accounts, let
    an explicit authorized `/decide` comment outrank them, and apply an
    approval through decide.yml's own sequence — label-first fail-closed,
    then `autonomy-ok` where the marker carried `arm=1`, then the PAT-backed
    ledger append, then the resolution reply. Per-issue failures are
    reported, never fatal to the rest: the fail-closed order leaves a
    half-applied push parked for the next run to retry. Prints one line per
    issue and appends `resolved=`/`overruled=`/`failed=` to
    ``$GITHUB_OUTPUT`` (the workflow's summary reads them).
    """
    # Lazy like the other live commands: pushthrough.py is the package's one
    # write-bearing seam, and importing it here would defeat the point of
    # keeping it out of the offline commands entirely.
    from .pushthrough import run_poll

    pat = os.environ.get("REGEN_TOKEN") or ""
    results = run_poll(args.repo, _token(), pat)

    resolved = [str(r["number"]) for r in results if r.get("outcome") == "approved"]
    overruled = [str(r["number"]) for r in results if r.get("outcome") == "overruled"]
    failed = [str(r["number"]) for r in results if r.get("outcome") == "error"]
    for result in results:
        number = result["number"]
        outcome = result.get("outcome", "?")
        reason = result.get("reason", "")
        detail = f" ({reason})" if reason else ""
        notes = "".join(f" [{note}]" for note in result.get("notes", []))
        print(f"#{number}: {outcome}{detail}{notes}")
    if not pat:
        print("notice: REGEN_TOKEN is not set — ledger appends skipped; the labels carry the verdicts")
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"resolved={' '.join(resolved)}\n")
            fh.write(f"overruled={' '.join(overruled)}\n")
            fh.write(f"failed={' '.join(failed)}\n")
    return 0


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def cmd_greenlight_context(args: argparse.Namespace) -> int:
    """`greenlight-context`: print the drafter's precedent digest.

    The load half of the learning loop (issue #445): the most recent
    ``greenlight_precedent_cap`` records of ``--log``, plus the inline owner
    replies on their threads (a GET-only gather, skipped when the log is
    empty — no records, nothing to read). The digest is printed and appended
    to ``$GITHUB_OUTPUT`` as the multiline ``digest`` (heredoc form), which
    the workflow splices into the drafter's prompt — trusted workflow code
    assembles the context, never the agent.
    """
    # Lazy for the same reason as greenlight-select: the purity test.
    from . import greenlights
    from .github import gather_greenlight_rounds

    cfg = _load_config(args.conf)
    records = greenlights.parse_log(_read_text(args.log or greenlights.LOG_PATH))
    replies: dict[int, list[dict[str, Any]]] = {}
    if records and args.repo:
        by_number = {
            t["number"]: t for t in gather_greenlight_rounds(args.repo, _token())["threads"]
        }
        recent_issues = sorted(
            records, key=lambda r: (r["recorded_at"], r["issue"]), reverse=True
        )[: cfg.greenlight_precedent_cap]
        replies = {
            r["issue"]: by_number[r["issue"]].get("owner_replies", [])
            for r in recent_issues
            if r["issue"] in by_number
        }
    digest = greenlights.context_digest(records, replies, cfg.greenlight_precedent_cap)
    sys.stdout.write(digest + "\n")
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write("digest<<REEVE_GL_DIGEST_EOF\n" + digest + "\nREEVE_GL_DIGEST_EOF\n")
    return 0


def cmd_greenlight_append(args: argparse.Namespace) -> int:
    """`greenlight-append`: derive and write records for resolved rounds.

    The observing half (issue #445): gather every greenlighted thread's
    resolution state (GET-only), read the decide.yml ledger and the committed
    log, derive the records for rounds that resolved and are not yet
    recorded, and write the updated log to ``--out`` (in place by default —
    the workflow overlays the live log from the data branch first). The
    count is appended to ``$GITHUB_OUTPUT`` as ``appended=`` so the workflow
    pushes the data branch only when something actually landed; the push
    itself is trusted workflow bash, not this package.
    """
    # Lazy for the same reason as greenlight-select: the purity test.
    from datetime import datetime, timezone

    from . import greenlights
    from .github import gather_greenlight_rounds

    cfg = _load_config(args.conf)
    log_text = _read_text(args.log or greenlights.LOG_PATH)
    records = greenlights.parse_log(log_text)
    ledger_rows = greenlights.parse_ledger(_read_text(args.ledger or greenlights.LEDGER_PATH))
    threads = gather_greenlight_rounds(args.repo, _token())["threads"]
    for thread in threads:
        thread["ledger_reaction"] = greenlights.ledger_reaction(
            ledger_rows, thread["number"]
        )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = greenlights.derive_records(
        threads, [r["issue"] for r in records], now
    )
    for record in fresh:
        sys.stdout.write(greenlights.render_line(record) + "\n")
    if fresh:
        updated = greenlights.append_records(log_text, fresh)
        if args.out == "-":
            sys.stdout.write("\n" + updated)
        else:
            out = args.out or (args.log or greenlights.LOG_PATH)
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(updated)
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"appended={len(fresh)}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reeve", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="render the report from a snapshot")
    p_report.add_argument("--input", help="snapshot JSON file (default: stdin)")
    p_report.add_argument("--conf", help="policy file (default: built-in defaults)")
    p_report.add_argument("--out", help="also write the report to this file")
    p_report.set_defaults(func=cmd_report)

    p_gather = sub.add_parser("gather", help="read the snapshot from committed files")
    p_gather.add_argument("--root", default=".", help="repo root (default: .)")
    p_gather.add_argument("--repo", default=None,
                          help="owner/name — also gather GitHub run health (GET-only)")
    p_gather.set_defaults(func=cmd_gather)

    p_run = sub.add_parser("run", help="gather then report")
    p_run.add_argument("--root", default=".", help="repo root (default: .)")
    p_run.add_argument("--repo", default=None,
                       help="owner/name — also gather GitHub run health (GET-only)")
    p_run.add_argument("--conf", help="policy file (default: built-in defaults)")
    p_run.add_argument("--out", help="also write the report to this file")
    p_run.set_defaults(func=cmd_run)

    p_config = sub.add_parser("config", help="read the committed policy file")
    p_config.add_argument("--get", required=True, choices=list(config_mod._KNOWN_KEYS),
                          help="which config value to print")
    p_config.add_argument("--path", default=None,
                          help=f"config file (default: {config_mod.DEFAULT_PATH})")
    p_config.set_defaults(func=cmd_config)

    p_armed = sub.add_parser("armed", help="the two-key arming decision")
    p_armed.add_argument("--variable", default=None,
                         help="the REEVE_ENABLED repo variable's value")
    p_armed.add_argument("--conf-enabled", default=None,
                         help="the committed conf's `enabled`, as a string")
    p_armed.add_argument("--gh-output",
                         help="path to append `armed=` (defaults to $GITHUB_OUTPUT)")
    p_armed.set_defaults(func=cmd_armed)

    p_gl = sub.add_parser("greenlight-select",
                          help="the draftable parked-decision queue (GET-only)")
    p_gl.add_argument("--repo", required=True,
                      help="owner/name — the repo to list parked issues from")
    p_gl.add_argument("--conf", help="policy file for greenlight_cap (default: built-in)")
    p_gl.add_argument("--gh-output",
                      help="path to append `issues=` (defaults to $GITHUB_OUTPUT)")
    p_gl.set_defaults(func=cmd_greenlight_select)

    p_poll = sub.add_parser("greenlight-poll",
                            help="poll prior greenlights' reactions; push approvals")
    p_poll.add_argument("--repo", required=True,
                        help="owner/name — the repo to poll parked decisions on")
    p_poll.add_argument("--gh-output",
                        help="path to append resolved=/overruled=/failed= (defaults to $GITHUB_OUTPUT)")
    p_poll.set_defaults(func=cmd_greenlight_poll)
    p_ctx = sub.add_parser("greenlight-context",
                           help="the drafter's precedent digest (log + owner replies)")
    p_ctx.add_argument("--repo", required=True,
                       help="owner/name — the repo to read owner replies from")
    p_ctx.add_argument("--conf",
                       help="policy file for greenlight_precedent_cap (default: built-in)")
    p_ctx.add_argument("--log", default=None,
                       help=f"precedent log (default: {greenlights.LOG_PATH})")
    p_ctx.add_argument("--gh-output",
                       help="path to append the multiline `digest` (defaults to $GITHUB_OUTPUT)")
    p_ctx.set_defaults(func=cmd_greenlight_context)

    p_app = sub.add_parser("greenlight-append",
                           help="records for newly-resolved rounds + the updated log")
    p_app.add_argument("--repo", required=True,
                       help="owner/name — the repo to read greenlighted threads from")
    p_app.add_argument("--conf", help="policy file (default: built-in defaults)")
    p_app.add_argument("--log", default=None,
                       help=f"precedent log (default: {greenlights.LOG_PATH})")
    p_app.add_argument("--ledger", default=None,
                       help=f"decide.yml ledger (default: {greenlights.LEDGER_PATH})")
    p_app.add_argument("--out", default=None,
                       help="where to write the updated log (default: in place; `-` prints it)")
    p_app.add_argument("--gh-output",
                       help="path to append `appended=` (defaults to $GITHUB_OUTPUT)")
    p_app.set_defaults(func=cmd_greenlight_append)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point; returns the process exit code.

    A malformed conf (ValueError), an unknown config key (KeyError), or a
    missing/unreadable snapshot or conf (OSError, incl. FileNotFoundError, and
    json.JSONDecodeError — a ValueError subclass) prints a one-line ``error:``
    to stderr and returns 1 — never a traceback, so a scheduled workflow step's
    log stays legible. argparse's own usage errors (exit 2) pass through.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, KeyError, FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
