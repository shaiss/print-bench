"""CLI for the growth engine.

Subcommands, each a thin shell over one module:

* ``growth config --get <key> [--path <conf>]`` — one policy value, the
  string form the workflow's policy step consumes (the sibling of
  ``backlog-burn config``, over the growth desk's own closed key set).
* ``growth length <text>`` — the weighted tweet length (URLs = 23), so a
  human or an attended session can check copy the way the posting tool will.
* ``growth daycap --author <logins> --cap <n> [--today <YYYY-MM-DD>]`` — the
  per-UTC-day live-post cap: read the desk's marker comments as a JSON list on
  stdin and print ``hold`` iff the number of ``growth-twitter:posted`` markers
  dated today (default: today UTC) authored by one of the trusted ``--author``
  logins (so an outsider's comment can't; matched with ``[bot]``-suffix
  normalization) has reached ``--cap`` — otherwise ``clear``. Lets Lark's Select
  step hold the drain to ≤``max_posts_per_day`` live posts/day.
* ``growth simulate --conf <conf> --snapshot <json> --posts <json>
  --start <iso> --days <n> --out-md <path> [--out-ndjson <path>]`` — the
  accelerated dry run (docs/growth.md): render what would have been posted.
* ``growth board-stage [--snapshot <json>]`` — derive the growth approval
  board's Stage for each queue item (docs/growth.md, docs/roadmap-board.md);
  reads a JSON list of item snapshots (file or stdin) and prints one
  ``<url>\\t<stage>`` line per item that belongs on the board. The
  growth-board-sync workflow's single source for where each post sits.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import board as board_mod
from . import config as config_mod
from . import daycap as daycap_mod
from . import simulate as simulate_mod
from .tweetlen import tweet_weight


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="growth")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_conf = sub.add_parser("config", help="read the committed growth policy")
    p_conf.add_argument("--get", required=True, metavar="KEY")
    p_conf.add_argument("--path", default=config_mod.DEFAULT_PATH)

    p_len = sub.add_parser("length", help="weighted tweet length (URLs = 23)")
    p_len.add_argument("text")

    p_daycap = sub.add_parser("daycap", help="is the day's live-post cap reached?")
    p_daycap.add_argument("--today", default="",
                          help="UTC date YYYY-MM-DD to test (default: today UTC)")
    p_daycap.add_argument("--author", required=True,
                          help="comma-separated GitHub logins the posting tool "
                               "posts as; only a marker from these authors counts "
                               "(so an outsider's comment can't); matched with "
                               "[bot]-suffix normalization")
    p_daycap.add_argument("--cap", type=int, default=1,
                          help="max live posts per UTC day (max_posts_per_day); "
                               "hold once today's count reaches it (default 1)")

    p_sim = sub.add_parser("simulate", help="accelerated dry-run timeline")
    p_sim.add_argument("--conf", default=config_mod.DEFAULT_PATH)
    p_sim.add_argument("--snapshot", required=True,
                       help="JSON file: the queue snapshot (list of issues)")
    p_sim.add_argument("--posts", required=True,
                       help="JSON file: composed posts keyed by issue number")
    p_sim.add_argument("--start", required=True, help="ISO timestamp, UTC")
    p_sim.add_argument("--days", type=int, required=True)
    p_sim.add_argument("--out-md", required=True)
    p_sim.add_argument("--out-ndjson")
    p_sim.add_argument("--note", default="",
                       help="one provenance line rendered under the header")

    p_board = sub.add_parser(
        "board-stage", help="derive the growth approval board's Stage per item")
    p_board.add_argument(
        "--snapshot",
        help="JSON file: a list of queue-item snapshots (default: read stdin)")

    args = parser.parse_args(argv)

    if args.cmd == "config":
        try:
            print(config_mod.get(args.get, args.path))
        except (config_mod.ConfigError, OSError) as e:
            print(f"growth config: {e}", file=sys.stderr)
            return 1
        return 0

    if args.cmd == "length":
        print(tweet_weight(args.text))
        return 0

    if args.cmd == "daycap":
        today = args.today or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        try:
            comments = json.loads(sys.stdin.read() or "[]")
        except json.JSONDecodeError as e:
            print(f"growth daycap: bad comments JSON on stdin: {e}", file=sys.stderr)
            return 1
        if not isinstance(comments, list):
            print("growth daycap: expected a JSON list of comments on stdin", file=sys.stderr)
            return 1
        trusted = {a.strip() for a in args.author.split(",") if a.strip()}
        if not trusted:
            print("growth daycap: --author must name at least one trusted login", file=sys.stderr)
            return 1
        if args.cap < 1:
            print("growth daycap: --cap must be a positive integer", file=sys.stderr)
            return 1
        count = daycap_mod.posts_today(comments, today, trusted)
        # A stderr note aids the workflow log without polluting the stdout
        # decision word the Select step reads.
        print(f"daycap: {count}/{args.cap} live post(s) today ({today})", file=sys.stderr)
        print("hold" if count >= args.cap else "clear")
        return 0

    if args.cmd == "simulate":
        try:
            cfg = config_mod.load(args.conf)
            with open(args.snapshot, encoding="utf-8") as fh:
                snapshot = json.load(fh)
            with open(args.posts, encoding="utf-8") as fh:
                posts = json.load(fh)
            result = simulate_mod.simulate(
                cfg.cadence, cfg.max_posts_per_run, snapshot, posts,
                args.start, args.days, cfg.max_posts_per_day,
            )
        except (config_mod.ConfigError, simulate_mod.SimulationError,
                OSError, json.JSONDecodeError) as e:
            print(f"growth simulate: {e}", file=sys.stderr)
            return 1
        md = simulate_mod.render_markdown(
            result, cfg.cadence, cfg.max_posts_per_run, args.start, args.days,
            generated_note=args.note,
        )
        with open(args.out_md, "w", encoding="utf-8") as fh:
            fh.write(md)
        if args.out_ndjson:
            with open(args.out_ndjson, "w", encoding="utf-8") as fh:
                fh.write(simulate_mod.render_ndjson(result))
        print(f"growth simulate: {len(result['slots'])} slot(s), "
              f"{len(result['unscheduled'])} left queued, "
              f"{len(result['skipped'])} skipped -> {args.out_md}")
        return 0

    if args.cmd == "board-stage":
        try:
            raw = (open(args.snapshot, encoding="utf-8").read()
                   if args.snapshot else sys.stdin.read())
            items = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            print(f"growth board-stage: {e}", file=sys.stderr)
            return 1
        if not isinstance(items, list):
            print("growth board-stage: expected a JSON list of item snapshots",
                  file=sys.stderr)
            return 1
        for item in items:
            stage = board_mod.stage_of(item)
            if stage is None:          # closed-and-never-posted: not a board card
                continue
            url = item.get("url")
            if not url:                # a card needs a URL to add; flag, don't guess
                print(f"growth board-stage: item #{item.get('number')} has no "
                      f"url; skipping", file=sys.stderr)
                continue
            print(f"{url}\t{stage}")
        return 0

    return 2  # pragma: no cover — argparse enforces the subcommand set


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
