# tools/growth — the deterministic engine behind the growth desk

The growth desk ([docs/growth.md](../../docs/growth.md)) is print-bench's
audience loop: **product managers queue messages** (issues labeled
`growth-queue`, filed via the `/growth-queue` skill's MCP tool), and a
**channel-specific growth agent** — Lark, `/growth-twitter`, for Twitter/X —
drains the queue into channel-native posts on its own schedule. The PM owns
*what is worth saying*; the channel agent owns *how that channel says it*.
Queuing is the seam between them.

This package is everything in that loop that must never depend on a model's
judgment:

| Module | What it owns |
|---|---|
| `growth.config` | The strict parser for `.github/growth-twitter.conf` — the committed policy (arming, provider, cadence, per-run post cap, approval requirement). Its own closed key set, like every sibling parser here: unknown keys fail loudly. |
| `growth.tweetlen` | The weighted tweet-length rule (twitter-text v3 ranges; every URL counts 23). One implementation the composer, the posting tool and the simulator all obey — `tests/test_server_parity.py` pins the posting server's self-contained copy to it. |
| `growth.queue` | The drain order: `priority:high` first, then oldest issue number — FIFO with one escape hatch. A pure function of a queue snapshot. |
| `growth.board` | The approval-board Stage policy: `stage_of` maps one queue issue's state + labels + the two hidden markers to a `print-bench growth` board Stage (Queued/Drafted/Approved/Posted/Parked/Attention). A pure function, the single source `growth-board-sync.yml` reflects onto the board (docs/growth.md). Owns the marker strings; a test pins them to the posting tool and pins its stage set to `scripts/gh-project.sh`'s `growth` board spec. |
| `growth.cron` | A minimal 5-field cron matcher (numbers, `*`, steps, lists, ranges) so the simulator can expand a cadence; anything fancier raises rather than simulating the wrong schedule. |
| `growth.daycap` | The per-UTC-day live-post cap: given the desk's marker comments, today's UTC date, the trusted poster login(s), and the cap, how many live posts have gone out today and is the cap met? Counts the `<!-- growth-twitter:posted -->` marker (imported from `growth.board`, one pinned source) **from a trusted author** — one per live post — so an outsider commenting the marker can't mis-tally a day (a DoS), a dry-run never consumes a slot, and Lark holds at ≤`max_posts_per_day` (default 2) live posts/calendar-day whichever (delayed) firings GitHub delivers. Matches the poster across the bot's REST (`github-actions[bot]`) and GraphQL (`github-actions`) login spellings via `[bot]`-suffix normalization — the Select step reads the GraphQL spelling, so without this the guard rejected its own markers. The workflow's Select step calls it (failing closed on a scan error); the decision is here, not in bash. |
| `growth.simulate` | The accelerated dry run: walk N days of firings over a snapshot + composed posts (holding once a day's `max_posts_per_day` cap is met, matching the per-day guard, so the timeline shows the real ~cap/day cadence) and render exactly what would have been posted, when — the committed artifact a human reads before arming anything live. Copy over the weighted 280 fails the simulation loudly. |
| `growth.poster` | The X API v2 seam: OAuth 1.0a (HMAC-SHA1) signing by hand, stdlib-only, inert unless all four `X_*` credentials are present. Mechanics only — the policy (approval label, duplicate markers, caps) lives in the posting MCP tool beside the skill. |

## CLI

```bash
# One policy value, the way the scheduled workflow's policy step reads it
# (PYTHONPATH=tools/growth/src — stdlib-only, no pip step in front):
python3 -m growth config --get enabled --path .github/growth-twitter.conf

# The weighted length the posting tool will meter copy at:
python3 -m growth length 'shipping day https://github.com/shaiss/print-bench'

# Is the day's live-post cap reached? (the per-day guard — the Select step pipes
# the desk's marker comments in and holds the drain on "hold" once today's post
# count reaches --cap; only a marker from a trusted --author counts, so an
# outsider's comment can't mis-tally it; --today defaults to today UTC. The bot's
# GraphQL author spelling "github-actions" matches the trusted "github-actions[bot]"):
echo '[{"body":"<!-- growth-twitter:posted -->","createdAt":"2026-09-01T14:00:00Z","author":"github-actions"}]' \
  | python3 -m growth daycap --today 2026-09-01 --author 'github-actions[bot]' --cap 2

# The accelerated dry run (see docs/growth.md for the artifact convention):
python3 -m growth simulate --conf .github/growth-twitter.conf \
  --snapshot queue.json --posts composed.json \
  --start 2026-08-29T09:00:00Z --days 7 \
  --out-md growth/twitter/dryruns/overnight.md \
  --out-ndjson growth/twitter/dryruns/overnight.ndjson

# The approval-board Stage per queue item — one `<url>\t<stage>` line per card
# the growth-board-sync workflow reflects onto the board (reads a JSON list of
# item snapshots from a file or stdin):
python3 -m growth board-stage --snapshot snapshot.json
```

## Tests

```bash
pip install -e 'tools/growth[test]'
python -m pytest tools/growth/tests -q
```

Stdlib-only on purpose (the tools/lineage rule): the scheduled workflow reads
policy straight from the checkout, and the posting server beside the skill
imports nothing beyond the standard library. A positive case and a negative
control per parser/policy rule; the poster's signing path is exercised
entirely offline through its transport seam.
