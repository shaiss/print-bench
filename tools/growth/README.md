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
| `growth.cron` | A minimal 5-field cron matcher (numbers, `*`, steps, lists, ranges) so the simulator can expand a cadence; anything fancier raises rather than simulating the wrong schedule. |
| `growth.postslot` | Post-time jitter: the cadence is a *window* of candidate hours, and `is_post_slot` picks exactly ONE per UTC date (a hash of the date indexes the sorted candidate hours). The workflow's `pick-slot` job gates the drain on it, so Lark's post time walks day to day while the ≤1-post/day floor stays structural. A single-candidate cadence always resolves to its one hour, so it is inert for every other routine. |
| `growth.simulate` | The accelerated dry run: walk N days of firings over a snapshot + composed posts (filtered through `postslot`, so the timeline shows the real ~1/day cadence at the real varied times) and render exactly what would have been posted, when — the committed artifact a human reads before arming anything live. Copy over the weighted 280 fails the simulation loudly. |
| `growth.poster` | The X API v2 seam: OAuth 1.0a (HMAC-SHA1) signing by hand, stdlib-only, inert unless all four `X_*` credentials are present. Mechanics only — the policy (approval label, duplicate markers, caps) lives in the posting MCP tool beside the skill. |

## CLI

```bash
# One policy value, the way the scheduled workflow's policy step reads it
# (PYTHONPATH=tools/growth/src — stdlib-only, no pip step in front):
python3 -m growth config --get enabled --path .github/growth-twitter.conf

# The weighted length the posting tool will meter copy at:
python3 -m growth length 'shipping day https://github.com/shaiss/print-bench'

# Is now today's chosen post slot? (post-time jitter — the `pick-slot`
# workflow job gates the drain on this; `true` iff this firing's hour is the
# per-date pick among the cadence's candidate hours; --now defaults to UTC now):
python3 -m growth postslot --cadence "$(python3 -m growth config --get cadence --path .github/growth-twitter.conf)"

# The accelerated dry run (see docs/growth.md for the artifact convention):
python3 -m growth simulate --conf .github/growth-twitter.conf \
  --snapshot queue.json --posts composed.json \
  --start 2026-08-29T09:00:00Z --days 7 \
  --out-md growth/twitter/dryruns/overnight.md \
  --out-ndjson growth/twitter/dryruns/overnight.ndjson
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
