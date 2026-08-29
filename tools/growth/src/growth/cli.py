"""CLI for the growth engine.

Subcommands, each a thin shell over one module:

* ``growth config --get <key> [--path <conf>]`` — one policy value, the
  string form the workflow's policy step consumes (the sibling of
  ``backlog-burn config``, over the growth desk's own closed key set).
* ``growth length <text>`` — the weighted tweet length (URLs = 23), so a
  human or an attended session can check copy the way the posting tool will.
* ``growth simulate --conf <conf> --snapshot <json> --posts <json>
  --start <iso> --days <n> --out-md <path> [--out-ndjson <path>]`` — the
  accelerated dry run (docs/growth.md): render what would have been posted.
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config as config_mod
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

    if args.cmd == "simulate":
        try:
            cfg = config_mod.load(args.conf)
            with open(args.snapshot, encoding="utf-8") as fh:
                snapshot = json.load(fh)
            with open(args.posts, encoding="utf-8") as fh:
                posts = json.load(fh)
            result = simulate_mod.simulate(
                cfg.cadence, cfg.max_posts_per_run, snapshot, posts,
                args.start, args.days,
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

    return 2  # pragma: no cover — argparse enforces the subcommand set


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
