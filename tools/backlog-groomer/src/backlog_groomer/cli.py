"""Command-line entry point for the backlog groomer.

    backlog-groomer report    # snapshot JSON in -> markdown report out
    backlog-groomer gather    # live GitHub read -> snapshot JSON
    backlog-groomer run       # gather then report (what the workflow runs)
    backlog-groomer config    # read the committed policy file
    backlog-groomer armed     # the two-key arming decision, as an output
    backlog-groomer narrative # optional fast-model layer: report in, report out (#248)

``report`` is the pure, tested core; ``gather`` is the thin GET-only live
read; ``run`` composes them.  The workflow stays a few lines of glue with
no policy of its own — including the arming decision, which is code here
(``config.armed``) rather than YAML expression soup, so the 2x2
variable-by-conf matrix is unit-tested.

``narrative`` is deliberately a separate verb, not a ``run`` flag: the
deterministic report must render before any model is consulted (the
model's sole input is that rendered body), and the step that calls a
provider key must be visibly skippable in the workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

from . import config as config_mod
from . import narrative
from .detectors import evaluate
from .report import render


def _load_snapshot(path: Optional[str]) -> dict[str, Any]:
    """Load a snapshot from ``path`` (or stdin when ``path`` is None/``-``)."""
    if path and path != "-":
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return json.load(sys.stdin)


def _token() -> str:
    """The GitHub token from ``GH_TOKEN``/``GITHUB_TOKEN`` (``""`` if unset)."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _load_config(path: Optional[str]) -> config_mod.Config:
    """The committed policy when ``--conf`` was given, else the defaults."""
    return config_mod.load(path) if path else config_mod.Config()


def _emit_report(snapshot: dict[str, Any], args: argparse.Namespace) -> int:
    cfg = _load_config(args.conf)
    body = render(evaluate(snapshot, cfg), snapshot, cfg)
    sys.stdout.write(body)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(body)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """`report`: render the grooming report from a snapshot file/stdin."""
    return _emit_report(_load_snapshot(args.input), args)


def cmd_gather(args: argparse.Namespace) -> int:
    """`gather`: print the live snapshot for ``--repo`` as JSON."""
    from .github import gather_snapshot  # here so the pure commands need no network stack

    snapshot = gather_snapshot(args.repo, _token())
    json.dump(snapshot, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """`run`: gather the live snapshot then render the report."""
    from .github import gather_snapshot

    return _emit_report(gather_snapshot(args.repo, _token()), args)


def cmd_config(args: argparse.Namespace) -> int:
    """`config --get <key>`: print one committed policy value."""
    path = args.path or config_mod.DEFAULT_PATH
    sys.stdout.write(config_mod.get(args.get, path=path) + "\n")
    return 0


def cmd_armed(args: argparse.Namespace) -> int:
    """`armed`: print the two-key arming decision and expose it as an output.

    Always exits 0 — the *decision* is the output (``true``/``false``), and
    the workflow gates later steps on it; a non-zero exit would read as the
    groomer failing rather than the groomer deciding not to run.
    """
    verdict = "true" if config_mod.armed(args.variable, args.conf_enabled) else "false"
    sys.stdout.write(verdict + "\n")
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"armed={verdict}\n")
    return 0


def cmd_narrative(args: argparse.Namespace) -> int:
    """`narrative`: splice the model-written summary into a rendered report.

    Reads the deterministic report, calls the configured provider's model
    over that body (and nothing else), and rewrites the file with the
    narrative block spliced in.  Fail-soft by design (#248): a missing
    key, an API error, or a bad answer leaves the file untouched and the
    exit code 0, printing one `::notice::` line — the deterministic report
    is the committed behavior and must always survive the layer.

    ``--mock`` runs the whole pipeline offline (a fixed stand-in paragraph
    in place of the model call) so the placement, markers, and disclosure
    can be exercised end-to-end with no provider key — the dry-run path
    the workflow's `workflow_dispatch` uses.
    """
    with open(args.report, encoding="utf-8") as fh:
        body = fh.read()
    if args.mock:
        block = narrative.render_narrative_block(
            "Mock narrative — the deterministic findings stand below; this "
            "paragraph stands in for the model-written summary so the "
            "layer's placement, markers, and disclosure can be exercised "
            "with no provider key.",
            "mock",
        )
        status = "mock"
    else:
        cfg = _load_config(args.conf)
        if not cfg.narrative:
            print("::notice::narrative: false in the committed conf — skipping the narrative layer")
            return 0
        model, base_url, secret = narrative.model_from_registry(
            args.registry, args.chain,
        )
        api_key = os.environ.get(args.api_key_env or secret, "")
        if not api_key:
            print(
                "::notice::narrative: true but the provider's key "
                f"({secret}) is not set — posting the deterministic report "
                "unchanged"
            )
            return 0
        block = narrative.generate(
            body, base_url=base_url, api_key=api_key, model=model,
        )
        status = "written" if block else "skipped"
    if block is None:
        print(
            "::notice::narrative step produced no block (missing key, API "
            "error, or out-of-bounds output) — posting the deterministic "
            "report unchanged"
        )
        return 0
    with open(args.report, "w", encoding="utf-8") as fh:
        fh.write(narrative.insert(body, block))
    print(f"::notice::narrative {status}: spliced into {args.report}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="backlog-groomer", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_report = sub.add_parser("report", help="render the report from a snapshot")
    p_report.add_argument("--input", help="snapshot JSON file (default: stdin)")
    p_report.add_argument("--conf", help="policy file (default: built-in defaults)")
    p_report.add_argument("--out", help="also write the report to this file")
    p_report.set_defaults(func=cmd_report)

    p_gather = sub.add_parser("gather", help="read the live snapshot from GitHub")
    p_gather.add_argument("--repo", required=True, help="owner/name")
    p_gather.set_defaults(func=cmd_gather)

    p_run = sub.add_parser("run", help="gather then report")
    p_run.add_argument("--repo", required=True, help="owner/name")
    p_run.add_argument("--conf", help="policy file (default: built-in defaults)")
    p_run.add_argument("--out", help="also write the report to this file")
    p_run.set_defaults(func=cmd_run)

    p_config = sub.add_parser("config", help="read the committed policy file")
    p_config.add_argument("--get", required=True, choices=list(config_mod._KNOWN_KEYS),
                          help="which config value to print")
    p_config.add_argument("--path", default=None,
                          help=f"config file (default: {config_mod.DEFAULT_PATH})")
    p_config.set_defaults(func=cmd_config)

    p_narrative = sub.add_parser(
        "narrative", help="splice the optional model-written summary into a report (#248)"
    )
    p_narrative.add_argument("--report", required=True,
                             help="the rendered report file, rewritten in place")
    p_narrative.add_argument("--conf", help="policy file (default: built-in defaults)")
    p_narrative.add_argument("--registry", default=".github/models/registry.conf",
                             help="the #206 model registry to resolve the model from")
    p_narrative.add_argument("--chain", default="groomer-narrative",
                             help="the registry chain the narrative model comes from")
    p_narrative.add_argument("--api-key-env", default=None,
                             help="environment variable holding the provider key "
                                  "(default: the provider's registry secret name)")
    p_narrative.add_argument("--mock", action="store_true",
                             help="offline mode: a fixed stand-in paragraph, no API call")
    p_narrative.set_defaults(func=cmd_narrative)

    p_armed = sub.add_parser("armed", help="the two-key arming decision")
    p_armed.add_argument("--variable", default=None,
                         help="the BACKLOG_GROOMER_ENABLED repo variable's value")
    p_armed.add_argument("--conf-enabled", default=None,
                         help="the committed conf's `enabled`, as a string")
    p_armed.add_argument("--gh-output",
                         help="path to append `armed=` (defaults to $GITHUB_OUTPUT)")
    p_armed.set_defaults(func=cmd_armed)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point; returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
