"""Command-line interface: record | score | check, plus ``--selftest``.

Run from the repo root (the ``--store`` default is repo-relative, the
brief-sources ``--root .`` convention).

Exit codes are the contract callers read:
  0  success — ``record`` wrote the note, or found it already there
     byte-identical (an idempotent no-op is success, not an error)
  1  ``check`` found problems, or ``--selftest`` saw a control fail
  2  the invocation or the event is wrong, or a write was refused
     (a malformed event, a derived field supplied, an overwrite attempt)

Output shapes:
  record    ``created <path>`` or ``unchanged <path>``, then
            ``importance <n> · <depth> · <verified>``
  score     the note ``record`` would write, as its canonical JSON — a dry
            run that touches nothing
  check     ``ok <n> note(s)`` or one ``FAIL <problem>`` line per problem
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import selftest
from .note import NoteError, canonical_bytes, encode
from .store import check, record

DEFAULT_STORE = "tools/agent-memory/store"


def _read_event(spec: str) -> object:
    text = sys.stdin.read() if spec == "-" else Path(spec).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise NoteError(f"the event is not valid JSON: {e}") from None


def cmd_record(args) -> int:
    rec = record(Path(args.store), _read_event(args.event))
    print(f"{'created' if rec.created else 'unchanged'} {rec.path}")
    n = rec.note
    print(f"importance {n['importance']} · {n['depth']} · {n['provenance']['verified']}")
    return 0


def cmd_score(args) -> int:
    print(canonical_bytes(encode(_read_event(args.event))).decode("utf-8"), end="")
    return 0


def cmd_check(args) -> int:
    problems, count = check(Path(args.store))
    for p in problems:
        print(f"FAIL {p}")
    if problems:
        print(f"agent-memory check: {len(problems)} problem(s) in {args.store}")
        return 1
    print(f"ok {count} note(s) in {args.store}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="agent-memory", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--selftest", action="store_true",
                        help="prove every write-path rule still fires (offline, temp dir only)")
    sub = parser.add_subparsers(dest="cmd")

    pr = sub.add_parser("record", help="encode an event and write its note if absent")
    pr.add_argument("--event", required=True, help="event JSON — a path, or - for stdin")
    pr.add_argument("--store", default=DEFAULT_STORE, help=f"store root (default: {DEFAULT_STORE})")
    pr.set_defaults(fn=cmd_record)

    ps = sub.add_parser("score", help="print the note an event encodes to; write nothing")
    ps.add_argument("--event", required=True, help="event JSON — a path, or - for stdin")
    ps.set_defaults(fn=cmd_score)

    pc = sub.add_parser("check", help="validate every committed note in the store")
    pc.add_argument("--store", default=DEFAULT_STORE, help=f"store root (default: {DEFAULT_STORE})")
    pc.set_defaults(fn=cmd_check)

    args = parser.parse_args(argv)
    if args.selftest:
        if args.cmd:
            parser.error("--selftest takes no subcommand")
        return selftest.run()
    if not args.cmd:
        parser.print_usage(sys.stderr)
        print("agent-memory: a subcommand (record | score | check) or --selftest is required",
              file=sys.stderr)
        return 2
    try:
        return args.fn(args)
    except (NoteError, FileNotFoundError, IsADirectoryError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
