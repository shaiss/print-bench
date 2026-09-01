"""The accelerated dry run: what WOULD the growth agent have posted, when?

Given the committed policy (cadence + per-run cap), a queue snapshot, and the
channel-agent's composed posts, walk N days of scheduled firings and assign
each queue item its posting slot in drain order. The output is the artifact a
human reads before ever arming the routine live: a timeline of concrete
posts with their would-have-been timestamps, plus an ndjson sidecar.

Everything here is deterministic — the *composing* (turning a queued message
into channel copy) is the agent's job and arrives as input; this module only
schedules, measures, and renders. An item with no composed post is reported
as skipped, never invented; a composed post over the weighted 280 limit fails
the simulation loudly (the same rule the posting tool enforces at write
time), because a dry run that renders an unpostable tweet is a lie.
"""

from __future__ import annotations

import json
from datetime import datetime

from . import queue as queue_policy
from .cron import Cron
from .tweetlen import MAX_WEIGHT, tweet_weight


class SimulationError(ValueError):
    pass


def _parse_start(raw: str) -> datetime:
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as e:
        raise SimulationError(f"bad --start timestamp {raw!r}: {e}") from e
    return t.replace(tzinfo=None)


def simulate(
    cadence: str,
    max_posts_per_run: int,
    snapshot: list[dict],
    posts: dict[str, dict],
    start: str,
    days: int,
) -> dict:
    """Assign composed posts to firing slots. ``posts`` maps the queue issue
    number (as a string — JSON object keys) to ``{"text": ..., "thread":
    [...]}``. Returns ``{"slots": [...], "unscheduled": [...], "skipped":
    [...]}`` where each slot is ``{"at": iso, "number": n, "title": ...,
    "text": ..., "thread": [...], "weight": n}``."""
    # Lark posts at most ONCE per UTC calendar day (the per-day live-post guard,
    # daycap): the multi-slot cadence fires several times a day for delivery
    # redundancy, but the drain acts on one firing per day and then holds.
    # Collapsing the firings to one-per-date keeps the dry-run timeline honest —
    # it shows the real ~1/day cadence, not a post at every firing. NOTE the
    # collapsed time is the day's FIRST nominal slot (a deterministic stand-in,
    # e.g. 13:19 for the current cadence); the simulator cannot model GitHub's
    # real delivery jitter (it has no delivery times), so the LIVE post time
    # varies while this projection does not. A single-candidate cadence already
    # fires once a day, so it is unaffected.
    firings, _seen_days = [], set()
    for f in Cron(cadence).firings(_parse_start(start), days):
        if f.date() not in _seen_days:
            _seen_days.add(f.date())
            firings.append(f)
    ordered = queue_policy.drain_order(snapshot)

    composed, skipped = [], []
    for item in ordered:
        post = posts.get(str(item["number"]))
        if not post or not (post.get("text") or "").strip():
            skipped.append({"number": item["number"], "title": item.get("title", ""),
                            "reason": "no composed post"})
            continue
        for part in [post["text"], *(post.get("thread") or [])]:
            w = tweet_weight(part)
            if w > MAX_WEIGHT:
                raise SimulationError(
                    f"composed post for #{item['number']} is over the weighted "
                    f"{MAX_WEIGHT} limit ({w}): {part[:60]!r}…"
                )
        composed.append((item, post))

    slots, i = [], 0
    for at in firings:
        for _ in range(max_posts_per_run):
            if i >= len(composed):
                break
            item, post = composed[i]
            slots.append({
                "at": at.isoformat() + "Z",
                "number": item["number"],
                "title": item.get("title", ""),
                "text": post["text"],
                "thread": list(post.get("thread") or []),
                "weight": tweet_weight(post["text"]),
            })
            i += 1
    unscheduled = [{"number": item["number"], "title": item.get("title", "")}
                   for item, _ in composed[i:]]
    return {"slots": slots, "unscheduled": unscheduled, "skipped": skipped}


def render_markdown(result: dict, cadence: str, max_posts_per_run: int,
                    start: str, days: int, generated_note: str = "") -> str:
    """The human-readable timeline. Committed under growth/<channel>/dryruns/
    so the would-have-been feed is reviewable in a PR."""
    lines = [
        "# Growth dry run — Twitter/X, accelerated timeline",
        "",
        f"Simulated window: **{days} days** from **{start}**, cadence "
        f"`{cadence}`, at most **{max_posts_per_run}** post(s) per firing.",
        "Nothing here was posted anywhere — this is the committed preview of "
        "what the growth agent would have published, in order, had it been "
        "armed live over this window. Weighted lengths use the same rule the "
        "posting tool enforces (URLs = 23, wide code points = 2, cap 280).",
        "",
    ]
    if generated_note:
        lines += [generated_note, ""]
    if not result["slots"]:
        lines += ["_No posts would have gone out (empty queue or empty compose set)._", ""]
    for n, slot in enumerate(result["slots"], start=1):
        lines += [
            f"## {n}. {slot['at']} — queue item #{slot['number']}",
            "",
            f"_{slot['title']}_" if slot.get("title") else "",
            "",
            "> " + slot["text"].replace("\n", "\n> "),
            "",
            f"({slot['weight']}/{MAX_WEIGHT} weighted)",
            "",
        ]
        for j, part in enumerate(slot["thread"], start=2):
            lines += [
                f"**{j}/** (thread)",
                "",
                "> " + part.replace("\n", "\n> "),
                "",
                f"({tweet_weight(part)}/{MAX_WEIGHT} weighted)",
                "",
            ]
    if result["unscheduled"]:
        lines += ["## Still queued after the window", ""]
        lines += [f"- #{u['number']} {u['title']}" for u in result["unscheduled"]]
        lines += [""]
    if result["skipped"]:
        lines += ["## Skipped (no composed post — reported, never invented)", ""]
        lines += [f"- #{s['number']} {s['title']} — {s['reason']}" for s in result["skipped"]]
        lines += [""]
    return "\n".join(line for line in lines if line is not None) + "\n"


def render_ndjson(result: dict) -> str:
    out = []
    for slot in result["slots"]:
        out.append(json.dumps({"mode": "dry-run", **slot}, ensure_ascii=False))
    return "\n".join(out) + ("\n" if out else "")
