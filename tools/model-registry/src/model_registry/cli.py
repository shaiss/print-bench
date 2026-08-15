"""Command-line entry point for the model registry.

    model-registry check                 # validate the registry, fail loud
    model-registry resolve <chain>       # ordered links -> $GITHUB_OUTPUT + JSON
    model-registry chain <chain>         # the ordered model ids, one per line
    model-registry show                  # human summary of providers/models/chains

``resolve`` is what a workflow calls: it appends ``link<N>_model`` /
``link<N>_provider`` / ``link<N>_secret`` / ``link<N>_base_url`` and ``link_count``
lines to ``$GITHUB_OUTPUT`` (the same plain key=value shape ``backlog-burn`` uses),
so a job reads the chain's model ids into its ship steps without a JSON parse or a
matrix.  The full resolution is also dumped as JSON to stdout for pipes/humans.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Optional

from . import registry as reg_mod
from .registry import Registry


def _load(args: argparse.Namespace) -> Registry:
    path = args.path or reg_mod.DEFAULT_PATH
    return Registry.load(path)


def cmd_check(args: argparse.Namespace) -> int:
    """`check`: load the registry; a clean load is a valid registry."""
    reg = _load(args)
    print(
        f"ok: {len(reg.providers)} providers, {len(reg.models)} models, "
        f"{len(reg.chains)} chains"
    )
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """`resolve <chain>`: emit the ordered links to $GITHUB_OUTPUT + stdout JSON."""
    reg = _load(args)
    links = reg.resolve(args.chain)

    # JSON to stdout — pipeable, human-readable, the full record.
    json.dump({"chain": args.chain, "links": [asdict(l) for l in links]},
              sys.stdout, indent=2)
    sys.stdout.write("\n")

    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"link_count={len(links)}\n")
            for link in links:
                fh.write(f"link{link.position}_model={link.model}\n")
                fh.write(f"link{link.position}_provider={link.provider}\n")
                fh.write(f"link{link.position}_secret={link.secret}\n")
                fh.write(f"link{link.position}_base_url={link.base_url}\n")
    return 0


def cmd_chain(args: argparse.Namespace) -> int:
    """`chain <chain>`: the ordered model ids, one per line (drift-guard/humans)."""
    reg = _load(args)
    for link in reg.resolve(args.chain):
        sys.stdout.write(link.model + "\n")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """`show`: a human summary of the whole registry."""
    reg = _load(args)
    for pid, p in sorted(reg.providers.items()):
        endpoint = p.base_url or "(native endpoint)"
        sys.stdout.write(f"provider {pid}: secret={p.secret} url={endpoint}\n")
    for mid, m in sorted(reg.models.items()):
        sys.stdout.write(f"model {mid}: provider={m.provider}\n")
    for cid, c in sorted(reg.chains.items()):
        sys.stdout.write(f"chain {cid}: {' -> '.join(c.models)}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="model-registry", description=__doc__)
    parser.add_argument("--path", default=None,
                        help=f"registry file (default: {reg_mod.DEFAULT_PATH})")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="validate the registry, fail loud")
    p_check.set_defaults(func=cmd_check)

    p_resolve = sub.add_parser("resolve", help="ordered links -> $GITHUB_OUTPUT + JSON")
    p_resolve.add_argument("chain", help="the chain id to resolve")
    p_resolve.add_argument("--gh-output",
                           help="path to append link lines (defaults to $GITHUB_OUTPUT)")
    p_resolve.set_defaults(func=cmd_resolve)

    p_chain = sub.add_parser("chain", help="the ordered model ids, one per line")
    p_chain.add_argument("chain", help="the chain id")
    p_chain.set_defaults(func=cmd_chain)

    p_show = sub.add_parser("show", help="human summary of the registry")
    p_show.set_defaults(func=cmd_show)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point; returns the process exit code.

    A malformed registry (ValueError) or an unknown chain (KeyError) prints a
    one-line ``error:`` to stderr and returns 1 — never a traceback, so a
    workflow step's log stays legible.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, KeyError, FileNotFoundError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
