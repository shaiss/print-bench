"""Command-line entry point for the model registry.

    model-registry check                 # validate the registry, fail loud
    model-registry resolve <chain>       # ordered links -> $GITHUB_OUTPUT + JSON
    model-registry chain <chain>         # the ordered model ids, one per line
    model-registry show                  # human summary of providers/models/chains
    model-registry smoke <chain>         # live 1-token ping of each configured link
    model-registry classify <chain>      # diagnose an exhausted chain -> one class
    model-registry shape <chain> --head <provider> --layout p1,p2,…
                                         # does the chain fit a workflow's walk?

``resolve`` is what a workflow calls: it appends ``link_count`` plus
``link<N>_model`` / ``link<N>_provider`` lines to ``$GITHUB_OUTPUT`` (the same
plain key=value shape ``backlog-burn`` uses), so a job reads the chain's model ids
and providers into its ship steps without a JSON parse or a matrix.  The secret
*name* and ``base_url`` are deliberately NOT emitted to ``$GITHUB_OUTPUT`` — a
workflow cannot dereference a secret by a runtime name (each provider keeps a
literal-secret ship step), and echoing a secret name to a step-output sink trips
secret-logging scanners.  The resolution is also dumped as JSON to stdout for
pipes/humans, carrying position/model/provider/base_url but never the secret name.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
from dataclasses import asdict
from typing import Optional

from . import registry as reg_mod
from . import smoke as smoke_mod
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

    # JSON to stdout — pipeable, human-readable. The provider's secret *name*
    # (e.g. ZAI_KEY) is deliberately excluded from every output sink: it is a
    # public identifier, not a value, but echoing a `secret`-named field to
    # stdout trips secret-logging scanners for no benefit, and nothing consumes
    # it (secrets are referenced literally in the workflow, never resolved here).
    def _public(link):
        d = asdict(link)
        d.pop("secret", None)
        return d
    json.dump({"chain": args.chain, "links": [_public(l) for l in links]},
              sys.stdout, indent=2)
    sys.stdout.write("\n")

    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        # Only the model id and provider go to $GITHUB_OUTPUT — those are what a
        # workflow branches on. The provider's secret name and base_url stay out
        # of the step output on purpose: a workflow cannot dereference a secret by
        # a runtime name (secrets must be referenced literally, which is exactly
        # why each provider keeps an explicit literal-secret ship step), so
        # emitting them here would be unusable, and echoing a secret *name* to a
        # step-output sink trips secret-logging scanners for no benefit. The JSON
        # on stdout above carries position/model/provider/base_url (the secret
        # name is stripped there too) for a human or a pipe.
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"link_count={len(links)}\n")
            for link in links:
                fh.write(f"link{link.position}_model={link.model}\n")
                fh.write(f"link{link.position}_provider={link.provider}\n")
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
        # The secret name is intentionally not printed (see cmd_resolve) — it's in
        # the committed registry.conf if a human needs it.
        sys.stdout.write(f"provider {pid}: url={endpoint}\n")
    for mid, m in sorted(reg.models.items()):
        sys.stdout.write(f"model {mid}: provider={m.provider}\n")
    for cid, c in sorted(reg.chains.items()):
        sys.stdout.write(f"chain {cid}: {' -> '.join(c.models)}\n")
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    """`smoke <chain>`: prove each configured link is callable with a live request.

    Static checks cannot prove a model id is servable by a key (issue #298 —
    the review chain's claude-opus-4-8 backstop passed every check and was dead
    on its first live call).  This walks the chain and makes a real 1-token
    request per link whose provider secret is set in the environment.  Exit 1
    only on positive evidence of a registry defect — a link proven UNSERVABLE
    (404/permission/invalid-model) — or when no link could be attempted at all
    (no secret set), so it can never report a green nothing.  A run whose every
    attempt was inconclusive (rate limit / account funding / auth / network)
    exits 0 with a loud WARN: nothing proven, but nothing proved unservable.
    """
    reg = _load(args)
    lines, code = smoke_mod.smoke_chain(reg, args.chain, os.environ)
    for line in lines:
        print(line)
    return code


def cmd_classify(args: argparse.Namespace) -> int:
    """`classify <chain>`: diagnose an exhausted chain into a class AND a reason.

    Where `smoke` answers "is any id a registry defect?" (its exit code), this
    answers "what should be done about a chain that just failed on every link?"
    (issue #347). It emits two signals: the aggregate **class** — the action
    bucket `servable` / `dead` / `needs-human` / `transient` the HITL escalation
    branches on — and the finer **reason** behind it, `billing` / `quota` / `auth`
    / `no-key` / `rate-limit` / `outage` / `bad-model-id` / `served`, so a workflow
    can tell *out of credit* from *out of tokens* from *bad key* and route the
    right remediation. It probes each configured link with the same live 1-token
    request, prints the per-link report plus the REASON/CLASS lines to stdout, and
    — when a sink is available — appends `class=<token>` and `reason=<token>` to
    $GITHUB_OUTPUT (the same key=value shape `resolve` uses) so a workflow step
    reads both without a JSON parse. Exit 0 regardless: the class/reason ARE the
    signal, not the exit code (a malformed registry or unknown chain still errors
    via main()).
    """
    reg = _load(args)
    lines, klass, reason = smoke_mod.diagnose_chain(reg, args.chain, os.environ)
    for line in lines:
        print(line)
    gh_output = args.gh_output or os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as fh:
            fh.write(f"class={klass}\n")
            fh.write(f"reason={reason}\n")
    return 0


def cmd_shape(args: argparse.Namespace) -> int:
    """`shape <chain> --head <p> --layout p1,p2,…`: does the chain fit the walk?

    The runtime half of the cross-provider walk contract (issue #544). A
    routine workflow's walk is a fixed sequence of literal ship steps — its
    LAYOUT, one provider per step in file order — and the conf's `provider:`
    names the HEAD. This applies `walk_shape_errors` (the same pure rule the
    drift guard pins pre-merge, so the two cannot drift) to the resolved chain
    and prints one `::error::` per violation, naming the registry file, the
    conf and the offending link, exiting 1 — so a mismatch fails the run
    BEFORE any key is spent rather than mid-walk against the wrong endpoint.
    """
    reg = _load(args)
    links = reg.resolve(args.chain)
    layout = [p.strip() for p in args.layout.split(",") if p.strip()]
    undeclared = sorted({p for p in layout if p not in reg.providers})
    errors = ([f"the walk layout names provider(s) {undeclared} the registry "
               f"does not declare (known: {sorted(reg.providers)})"]
              if undeclared else [])
    errors += reg_mod.walk_shape_errors(links, args.head, layout)
    registry_path = args.path or reg_mod.DEFAULT_PATH
    conf_label = f" / {args.conf}" if args.conf else ""
    for err in errors:
        print(f"::error::{registry_path} [chain:{args.chain}]{conf_label}: {err}. "
              "Edit the chain in the registry and the workflow's ship steps "
              "(and its conf's provider:) together.")
    if errors:
        return 1
    print(f"ok: chain {args.chain} walks layout {','.join(layout)} from head "
          f"provider {args.head}")
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

    p_smoke = sub.add_parser(
        "smoke", help="live 1-token ping of each chain link whose secret is set")
    p_smoke.add_argument("chain", help="the chain id to smoke-test")
    p_smoke.set_defaults(func=cmd_smoke)

    p_classify = sub.add_parser(
        "classify",
        help="diagnose an exhausted chain -> class (action) + reason (cause)")
    p_classify.add_argument("chain", help="the chain id to classify")
    p_classify.add_argument(
        "--gh-output",
        help="path to append `class=<token>` and `reason=<token>` (defaults to $GITHUB_OUTPUT)")
    p_classify.set_defaults(func=cmd_classify)

    p_shape = sub.add_parser(
        "shape",
        help="check a chain fits a workflow's literal ship-step walk (issue #544)")
    p_shape.add_argument("chain", help="the chain id to check")
    p_shape.add_argument(
        "--head", required=True,
        help="the provider the routine's conf names — link 1 must sit on it")
    p_shape.add_argument(
        "--layout", required=True,
        help="the workflow's ship-step providers in file order, comma-separated "
             "(one per step, e.g. zai,zai,zai,anthropic,anthropic)")
    p_shape.add_argument(
        "--conf", default=None,
        help="the conf file the head provider was read from (named in errors)")
    p_shape.set_defaults(func=cmd_shape)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point; returns the process exit code.

    A malformed registry (ValueError) or an unknown chain (KeyError) prints a
    one-line ``error:`` to stderr and returns 1 — never a traceback, so a
    workflow step's log stays legible. ``configparser.Error`` is caught too as a
    last line of defense: ``Registry.load`` disables interpolation and wraps the
    read, but a future parser change must still degrade to the legible ``error:``
    rather than a traceback in the auto-review resolve step.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, KeyError, FileNotFoundError, configparser.Error) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
