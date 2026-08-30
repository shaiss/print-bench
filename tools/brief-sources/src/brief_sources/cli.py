"""Command-line interface: extract | select.

Exit codes are the contract callers read:
  0  the command succeeded — for `select` that includes the ``NONE`` verdict,
     which is an answer ("nothing to file"), not an error
  2  the invocation, a marker, or an open-brief list is wrong

Output shapes:
  extract  one ``slug | title | source | status…`` line per candidate,
           oldest-undone-first; ``--json`` for a machine-readable list
  select   exactly ONE candidate with its provenance as ``key: value`` lines,
           or the single word ``NONE``; ``--json`` emits the object or ``null``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .markers import MarkerError, extract
from .select import parse_briefs, select


def _design_names(root: Path) -> list[str]:
    designs = root / "designs"
    if not designs.is_dir():
        return []
    return sorted(p.name for p in designs.iterdir() if p.is_dir())


def _read_briefs(spec: str) -> list[tuple[int, str]]:
    if spec == "-":
        return parse_briefs(sys.stdin.read())
    return parse_briefs(Path(spec).read_text(encoding="utf-8"))


def cmd_extract(args) -> int:
    root = Path(args.root).resolve()
    candidates = extract(root)
    if args.json:
        print(json.dumps([c.as_dict() for c in candidates], indent=2))
    else:
        for c in candidates:
            status = f"status={c.status}" + (f" ref={c.ref}" if c.ref is not None else "")
            print(f"{c.slug} | {c.title} | {c.source} | {status}")
    return 0


def cmd_select(args) -> int:
    root = Path(args.root).resolve()
    candidates = extract(root)
    briefs = _read_briefs(args.open_briefs)
    chosen = select(candidates, briefs, _design_names(root))
    if args.json:
        print(json.dumps(chosen.as_dict() if chosen else None, indent=2))
    elif chosen is None:
        print("NONE")
    else:
        print(f"slug: {chosen.slug}")
        print(f"title: {chosen.title}")
        print(f"source: {chosen.source}")
        print(f"status: {chosen.status}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="brief-sources", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="list every brief-candidate marker under <root>/docs")
    pe.add_argument("--root", default=".", help="repo root holding docs/ (default: cwd)")
    pe.add_argument("--json", action="store_true", help="emit a JSON list")
    pe.set_defaults(fn=cmd_extract)

    ps = sub.add_parser("select", help="apply the guard rails; print ONE candidate or NONE")
    ps.add_argument("--root", default=".", help="repo root holding docs/ and designs/ (default: cwd)")
    # Required on purpose: dedup is the guard rail this tool exists for, and a
    # select run that silently assumed "nothing open" would re-file every
    # already-briefed subject it was meant to skip. Pass an empty file (or
    # `printf '' |`) to select against a genuinely empty backlog.
    ps.add_argument(
        "--open-briefs",
        required=True,
        help="open-brief list, '<number> <title>' per line — a path, or - for stdin",
    )
    ps.add_argument("--json", action="store_true", help="emit the chosen candidate as JSON (or null)")
    ps.set_defaults(fn=cmd_select)

    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except (MarkerError, ValueError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
