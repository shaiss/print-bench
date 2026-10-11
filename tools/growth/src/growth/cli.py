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
* ``growth dedup-context (--repo <owner/name> | --snapshot <json>) --out-dir
  <dir> [--now <iso>] [--window-days <n>]`` — the queuer's dedup context
  (:mod:`growth.dedup`): every open, or recently-closed, ``channel:*`` issue,
  split into "queued" and "already covered or declined", written as
  ``<dir>/dedup.md`` (for the agent) and ``<dir>/dedup.json`` (for the queue
  tool's near-duplicate backstop). ``--repo`` reads GitHub live, GET-only
  (:mod:`growth.github`); ``--snapshot`` reads a JSON list of issues. FAIL
  CLOSED: when assembly fails it still writes both files, marked
  unavailable, and exits 1 — so the queue tool refuses rather than trusting
  an empty list; and the previous pair is removed before anything is
  written, so a write that itself fails leaves no context, never a stale one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from . import board as board_mod
from . import config as config_mod
from . import daycap as daycap_mod
from . import dedup as dedup_mod
from . import github as github_mod
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

    p_dd = sub.add_parser(
        "dedup-context",
        help="write the queuer's dedup context (queued + already covered/declined)")
    p_dd_src = p_dd.add_mutually_exclusive_group(required=True)
    p_dd_src.add_argument(
        "--repo", help="owner/name: list the live channel:* issues (GET-only; "
                       "token from GITHUB_TOKEN or GH_TOKEN)")
    p_dd_src.add_argument(
        "--snapshot", help="JSON file: a list of issue objects (offline)")
    p_dd.add_argument("--out-dir", required=True,
                      help=f"directory for {dedup_mod.MD_NAME} and {dedup_mod.JSON_NAME}")
    p_dd.add_argument("--now", default="",
                      help="ISO timestamp the window is measured from (default: now UTC)")
    p_dd.add_argument("--window-days", type=int, default=dedup_mod.DEFAULT_WINDOW_DAYS,
                      help="keep closed items closed within this many days "
                           f"(default {dedup_mod.DEFAULT_WINDOW_DAYS})")

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

    if args.cmd == "dedup-context":
        return _dedup_context(args)

    return 2  # pragma: no cover — argparse enforces the subcommand set


def _write_atomic(path: str, text: str) -> None:
    """Write ``text`` to ``path`` via a sibling temp file + ``os.replace``, so
    a reader sees the whole new file or none of it — never a truncated one."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               prefix=f".{os.path.basename(path)}.", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_context(out_dir: str, ctx: dict) -> None:
    """Replace the context pair, invalidating the previous one FIRST.

    The workflow refreshes the context in place before each tail link, so the
    out-dir can already hold an earlier link's COMPLETE ``dedup.json``. If
    this write then failed part-way, that stale file would survive and the
    queue tool would accept it, blind to whatever the earlier link queued. So
    both old files are removed before anything is written, the markdown lands
    first and the JSON last, each atomically: a failure at any point leaves
    no JSON at all, which the queue tool refuses — never a stale or
    half-written one."""
    os.makedirs(out_dir, exist_ok=True)
    for name in (dedup_mod.JSON_NAME, dedup_mod.MD_NAME):
        try:
            os.unlink(os.path.join(out_dir, name))
        except FileNotFoundError:
            pass
    _write_atomic(os.path.join(out_dir, dedup_mod.MD_NAME), dedup_mod.render_markdown(ctx))
    _write_atomic(os.path.join(out_dir, dedup_mod.JSON_NAME), dedup_mod.render_json(ctx))


def _dedup_context(args) -> int:
    """Assemble and write the dedup context; on ANY failure write the
    unavailable form instead and exit 1 (fail closed — see the module doc)."""
    try:
        now = (datetime.fromisoformat(args.now.replace("Z", "+00:00"))
               if args.now else datetime.now(timezone.utc))
        if now.tzinfo is None:
            raise ValueError(f"--now must carry a UTC offset (got {args.now!r})")
        if args.window_days < 1:
            raise ValueError(f"--window-days must be a positive integer (got {args.window_days})")
        if args.snapshot:
            with open(args.snapshot, encoding="utf-8") as fh:
                snapshot = json.load(fh)
            if not isinstance(snapshot, list):
                raise ValueError("--snapshot must hold a JSON list of issues")
        else:
            token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
            cutoff = now - timedelta(days=args.window_days)
            snapshot = github_mod.channel_issues(args.repo, token, cutoff)
        ctx = dedup_mod.build(snapshot, now, args.window_days)
    except Exception as e:  # noqa: BLE001 — every failure takes the fail-closed path
        error = f"{type(e).__name__}: {e}"
        print(f"growth dedup-context: {error}", file=sys.stderr)
        try:
            _write_context(args.out_dir,
                           dedup_mod.unavailable(error, datetime.now(timezone.utc)))
        except OSError as w:
            print(f"growth dedup-context: could not write the unavailable "
                  f"context either: {w}", file=sys.stderr)
        return 1
    try:
        _write_context(args.out_dir, ctx)
    except OSError as e:
        print(f"growth dedup-context: {e}", file=sys.stderr)
        return 1
    print(f"growth dedup-context: {len(ctx[dedup_mod.SECTION_QUEUED])} queued, "
          f"{len(ctx[dedup_mod.SECTION_COVERED])} already covered or declined "
          f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
