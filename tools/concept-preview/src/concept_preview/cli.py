"""Command-line interface: build | check | selftest | vocab.

Exit codes are the contract scripts/concept-preview.sh reads:
  0  success
  1  a sheet failed a check (xml / contract / external / bounds / collision),
     or --verify found a committed sheet stale or missing
  2  the spec was refused (the message names file:line), or bad usage

``build`` writes nothing unless all four sheets pass every check — a sheet
set is committed whole or not at all. This module is the package's only
filesystem writer; everything it calls is pure (a test holds that).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import selftest
from .build import build_file
from .check import check_svg
from .spec import SpecError, vocabulary

DEFAULT_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def cmd_build(args) -> int:
    try:
        result = build_file(Path(args.spec))
    except SpecError as e:
        print(f"FAIL  spec: {e}")
        return 2
    except OSError as e:
        print(f"FAIL  spec: cannot read {args.spec}: {e.strerror}")
        return 2
    if result.findings:
        for f in result.findings:
            print(f"FAIL  {f}")
        print(f"concept-preview: {len(result.findings)} finding(s) — nothing written")
        return 1
    out = Path(args.out)
    if args.verify:
        stale = []
        for name, svg in result.sheets.items():
            target = out / name
            if not target.is_file():
                stale.append(f"{target} is missing")
            elif target.read_text(encoding="utf-8") != svg:
                stale.append(f"{target} is stale (does not match its spec)")
        for line in stale:
            print(f"FAIL  {line}")
        if stale:
            print("concept-preview: re-run the generator and commit the result")
            return 1
        print(f"ok    concept-preview: {len(result.sheets)} sheets in {out} match {args.spec}")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for name, svg in result.sheets.items():
        (out / name).write_text(svg, encoding="utf-8")
    print(f"ok    concept-preview: wrote {len(result.sheets)} checked sheets to {out}")
    return 0


def cmd_check(args) -> int:
    bad = 0
    for path in args.svg:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"FAIL  {path}: unreadable ({e})")
            bad += 1
            continue
        findings = check_svg(text, path)
        for f in findings:
            print(f"FAIL  {f}")
        if findings:
            bad += 1
        else:
            print(f"ok    {path}")
    return 1 if bad else 0


def cmd_selftest(args) -> int:
    return selftest.run(Path(args.fixtures))


def cmd_vocab(_args) -> int:
    sys.stdout.write(vocabulary())
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="concept-preview", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="parse a preview-spec.conf, emit + check the four sheets")
    b.add_argument("spec")
    b.add_argument("--out", required=True, help="directory the concept-*.svg sheets go in")
    b.add_argument("--verify", action="store_true",
                   help="write nothing; fail if the committed sheets differ from a fresh build")
    b.set_defaults(func=cmd_build)
    c = sub.add_parser("check", help="re-check existing sheets")
    c.add_argument("svg", nargs="+")
    c.set_defaults(func=cmd_check)
    s = sub.add_parser("selftest", help="valid fixture + negative controls")
    s.add_argument("--fixtures", default=str(DEFAULT_FIXTURES))
    s.set_defaults(func=cmd_selftest)
    v = sub.add_parser("vocab", help="print the spec vocabulary")
    v.set_defaults(func=cmd_vocab)
    args = p.parse_args(argv)
    return args.func(args)
