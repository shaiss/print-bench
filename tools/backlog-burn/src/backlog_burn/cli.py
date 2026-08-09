"""Command-line entry point for the scheduled backlog burn.

    backlog-burn select   # snapshot JSON on stdin -> selection record
    backlog-burn gather    # live GitHub read -> snapshot JSON
    backlog-burn run       # gather then select (what the workflow runs)

``select`` is the pure, tested core; ``gather`` is the thin live read; ``run``
composes them. Any command can write GitHub Actions outputs (``--gh-output``)
and a job-summary block (``--summary``) so the workflow stays a few lines of
glue with no policy of its own.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from .select import DEFAULT_REQUIRED_LABEL, render_summary, select_issue


def _emit(record: dict[str, Any], args: argparse.Namespace) -> None:
    """Write the record to stdout and, when present, GitHub Actions outputs."""
    # The record itself, always, to stdout, so `run`/`select` are pipeable.
    json.dump(record, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")

    # GitHub Actions step outputs: `issue` is the empty string when nothing
    # was selected, which an `if: steps.x.outputs.issue != ''` gate reads
    # correctly as "skip the ship step".
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        selected = record["selected"]
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"issue={selected if selected is not None else ''}\n")

    summary_path = args.summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        # The heading is caller-supplied so the three routines that share this
        # selector (backlog burn, design run, chunker) each get a correctly
        # titled summary block instead of every one reading "## Backlog burn".
        title = getattr(args, "summary_title", None) or "Backlog burn"
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write(f"## {title}\n\n")
            fh.write(render_summary(record))
            fh.write("\n")


def _load_snapshot(path: Optional[str]) -> dict[str, Any]:
    """Load a snapshot from ``path`` (or stdin when ``path`` is None/``-``)."""
    if path and path != "-":
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def _token() -> str:
    """The GitHub token from ``GH_TOKEN``/``GITHUB_TOKEN`` (``""`` if unset)."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def cmd_select(args: argparse.Namespace) -> int:
    """`select`: apply the policy to a snapshot read from stdin/file."""
    snapshot = _load_snapshot(args.input)
    record = select_issue(snapshot, required_label=args.label,
                          now=datetime.now(timezone.utc))
    _emit(record, args)
    return 0


def cmd_gather(args: argparse.Namespace) -> int:
    """`gather`: print the live snapshot for ``--repo`` as JSON."""
    from .github import gather_snapshot  # imported here so `select` needs no network stack

    snapshot = gather_snapshot(args.repo, _token())
    json.dump(snapshot, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """`run`: gather the live snapshot then apply the policy."""
    from .github import gather_snapshot

    snapshot = gather_snapshot(args.repo, _token())
    record = select_issue(snapshot, required_label=args.label,
                          now=datetime.now(timezone.utc))
    _emit(record, args)
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """`config`: read or write a value in the committed policy file.

    Sub-commands:
      ``--get <key>``          print one value (existing behaviour)
      ``set <key> <value>``    update a key and print the resolved cron (for cadence)

    The workflow reads `enabled`, `label`, and `provider` from
    `.github/backlog-burn.conf` this way, so the policy lives in git rather
    than in the YAML.  The ``set`` sub-command is what the
    ``backlog-burn-config`` workflow invokes to apply a ``/backlog-burn set``
    command to the branch's config file without a full checkout.
    """
    from . import config as config_mod

    path = args.path or config_mod.DEFAULT_PATH

    if hasattr(args, "set_key"):  # `config set <key> <value>`
        workflow_path = args.workflow_path or config_mod.WORKFLOW_PATH
        cron = config_mod.set_value(args.set_key, args.set_value, path=path)
        if cron:
            # cadence change: also patch the workflow's cron literal
            config_mod.patch_workflow_cron(cron, path=workflow_path)
            sys.stdout.write(f"cadence={args.set_value}\ncron={cron}\n")
        else:
            sys.stdout.write(f"{args.set_key}={args.set_value}\n")
        return 0

    # --get (existing behaviour)
    if not args.get:
        import argparse as _ap
        sys.stderr.write("error: one of --get KEY or sub-command 'set' is required\n")
        return 2
    sys.stdout.write(config_mod.get(args.get, path=path) + "\n")
    return 0


def _add_output_flags(p: argparse.ArgumentParser) -> None:
    """Attach the shared ``--gh-output`` / ``--summary`` / ``--label`` flags."""
    p.add_argument("--gh-output", help="path to append `issue=` (defaults to $GITHUB_OUTPUT)")
    p.add_argument("--summary", help="path to append a markdown summary (defaults to $GITHUB_STEP_SUMMARY)")
    p.add_argument("--summary-title", default="Backlog burn",
                   help="heading for the job-summary block (default: Backlog burn); "
                        "pass e.g. 'Chunker' or 'Design run' from the sibling routines")
    p.add_argument("--label", default=DEFAULT_REQUIRED_LABEL,
                   help=f"required opt-in label (default: {DEFAULT_REQUIRED_LABEL})")


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the three subcommands."""
    parser = argparse.ArgumentParser(prog="backlog-burn", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_select = sub.add_parser("select", help="apply the policy to a snapshot on stdin")
    p_select.add_argument("--input", help="snapshot JSON file (default: stdin)")
    _add_output_flags(p_select)
    p_select.set_defaults(func=cmd_select)

    p_gather = sub.add_parser("gather", help="read the live snapshot from GitHub")
    p_gather.add_argument("--repo", required=True, help="owner/name")
    p_gather.set_defaults(func=cmd_gather)

    p_run = sub.add_parser("run", help="gather then select")
    p_run.add_argument("--repo", required=True, help="owner/name")
    _add_output_flags(p_run)
    p_run.set_defaults(func=cmd_run)

    p_config = sub.add_parser("config", help="read or write the committed policy file")
    p_config.add_argument("--get", choices=["enabled", "label", "provider", "cadence"],
                          help="which config value to print")
    p_config.add_argument("--path", default=None,
                          help="config file (default: .github/backlog-burn.conf)")
    p_config.set_defaults(func=cmd_config)

    # `config set <key> <value>` — the sub-subcommand the /backlog-burn set
    # workflow uses.  Kept as positional args so the workflow step is a clean
    # one-liner: `backlog-burn config set enabled false`.
    config_sub = p_config.add_subparsers(dest="config_sub")
    p_config_set = config_sub.add_parser("set", help="update a config key")
    p_config_set.add_argument("set_key", choices=["enabled", "label", "provider", "cadence"],
                              metavar="key", help="key to update")
    p_config_set.add_argument("set_value", metavar="value", help="new value")
    p_config_set.add_argument("--path", default=None,
                              help="config file (default: .github/backlog-burn.conf)")
    p_config_set.add_argument("--workflow-path", default=None,
                              help="workflow file to patch for cadence changes "
                                   "(default: .github/workflows/backlog-burn.yml)")
    p_config_set.set_defaults(func=cmd_config)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point; returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
