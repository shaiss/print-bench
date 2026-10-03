"""CLI for the andon reconciler.

Subcommands, each a thin shell over :mod:`andon.policy`:

* ``andon decide --repo <owner/name> --cord <raw value> [--now <iso>]
  [--gh-output <file>] [--out-dir <dir>] [--offline]`` — the workflow's
  step: read the open status issue (one GET; skipped with ``--offline``),
  compute the open/close/none decision, append ``KEY=VALUE`` lines to
  ``--gh-output`` (``action``, ``issue_number``, ``pulled``, ``opened_at``)
  and write the rendered text the write step will carry —
  ``<out-dir>/body.md`` for ``open``, ``<out-dir>/comment.md`` for
  ``close``. Exit 0 on any decision; 1 on a configuration error (a bad ISO
  timestamp, a missing ``--repo`` without ``--offline``).
* ``andon render-open [--now <iso>]`` — print the issue body.
* ``andon render-close --since <iso> [--now <iso>]`` — print the closing
  comment for a cord pulled since ``--since``.

The token comes from ``GH_TOKEN`` / ``GITHUB_TOKEN``; empty is allowed and
means an unauthenticated GET (the groomer's convention). Nothing here
writes to GitHub.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import policy
from .policy import OpenIssue


def _now_from(arg: Optional[str]) -> datetime:
    if arg is None or arg == "":
        return datetime.now(timezone.utc)
    return policy.parse_iso(arg)


def _write_gh_output(path: Optional[str], values: dict[str, str]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def _cmd_decide(args: argparse.Namespace) -> int:
    try:
        now = _now_from(args.now)
    except ValueError as exc:
        print(f"error: --now is not an ISO-8601 timestamp: {exc}", file=sys.stderr)
        return 1
    if not args.offline and not args.repo:
        print("error: --repo <owner/name> is required unless --offline", file=sys.stderr)
        return 1

    pulled = policy.is_pulled(args.cord)
    open_issue: Optional[OpenIssue] = None
    if not args.offline:
        from . import github  # the one I/O module, imported only when used

        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        open_issue = github.find_open_status_issue(args.repo, token)

    decision = policy.decide(pulled, open_issue)

    out_dir = Path(args.out_dir)
    if decision.action == "open":
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "body.md").write_text(policy.render_open_body(now, args.repo or None), encoding="utf-8")
    elif decision.action == "close":
        assert open_issue is not None
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "comment.md").write_text(
            policy.render_close_comment(open_issue.created_at, now, args.repo or None),
            encoding="utf-8"
        )

    _write_gh_output(
        args.gh_output,
        {
            "action": decision.action,
            "issue_number": "" if decision.issue_number is None else str(decision.issue_number),
            "pulled": "true" if pulled else "false",
            "opened_at": "" if open_issue is None else policy.iso(open_issue.created_at),
        },
    )
    state = "pulled" if pulled else "released"
    print(f"andon: cord {state}; action={decision.action} — {decision.reason}")
    return 0


def _cmd_render_open(args: argparse.Namespace) -> int:
    try:
        now = _now_from(args.now)
    except ValueError as exc:
        print(f"error: --now is not an ISO-8601 timestamp: {exc}", file=sys.stderr)
        return 1
    sys.stdout.write(policy.render_open_body(now))
    return 0


def _cmd_render_close(args: argparse.Namespace) -> int:
    try:
        now = _now_from(args.now)
        since = policy.parse_iso(args.since)
    except ValueError as exc:
        print(f"error: not an ISO-8601 timestamp: {exc}", file=sys.stderr)
        return 1
    print(policy.render_close_comment(since, now))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="andon")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dec = sub.add_parser("decide", help="reconcile the cord's state against the status issue")
    p_dec.add_argument("--repo", default="", help="owner/name (required unless --offline)")
    p_dec.add_argument("--cord", default="",
                       help=f"the raw value of the {policy.VARIABLE} repo variable "
                            "(empty = unset = released)")
    p_dec.add_argument("--now", default=None, help="ISO timestamp (default: now, UTC)")
    p_dec.add_argument("--gh-output", default=None,
                       help="file to append KEY=VALUE lines to (the step's $GITHUB_OUTPUT)")
    p_dec.add_argument("--out-dir", default=".andon",
                       help="where body.md / comment.md are written (default .andon)")
    p_dec.add_argument("--offline", action="store_true",
                       help="skip the GitHub read; treat the status issue as absent")
    p_dec.set_defaults(func=_cmd_decide)

    p_open = sub.add_parser("render-open", help="print the status issue body")
    p_open.add_argument("--now", default=None)
    p_open.set_defaults(func=_cmd_render_open)

    p_close = sub.add_parser("render-close", help="print the closing comment")
    p_close.add_argument("--since", required=True, help="ISO timestamp the cord was pulled at")
    p_close.add_argument("--now", default=None)
    p_close.set_defaults(func=_cmd_render_close)

    args = parser.parse_args(argv)
    return args.func(args)
