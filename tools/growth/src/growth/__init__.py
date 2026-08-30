"""growth — the deterministic engine behind print-bench's growth desk.

The growth desk (docs/growth.md) splits audience work in two: product
managers *queue* messages (``growth-queue``-labeled issues, filed via the
``/growth-queue`` skill's MCP tool), and a channel-specific *growth agent*
(Lark, ``/growth-twitter``) drains the queue into channel-native posts.

This package is the deterministic half of that loop — everything that must
never depend on a model's judgment:

* :mod:`growth.config` — the strict parser for ``.github/growth-twitter.conf``
  (the committed policy: arming, provider, cadence, per-run post cap, the
  approval requirement).
* :mod:`growth.tweetlen` — the weighted tweet-length rule (URLs count as 23,
  wide code points as 2) the composing agent and the posting tool both obey.
* :mod:`growth.queue` — the queue-drain ordering policy (priority first,
  then oldest), a pure function of a queue snapshot.
* :mod:`growth.cron` — a minimal 5-field cron matcher so the simulator can
  expand a routine's cadence into concrete firing times.
* :mod:`growth.postslot` — post-time jitter: the cadence is a window of
  candidate hours, and this picks exactly one per UTC date so Lark's post
  time varies day to day while staying ≤1 post/day.
* :mod:`growth.simulate` — the accelerated dry-run: walk N days of cadence
  over a queue snapshot and render exactly what would have been posted, when.
* :mod:`growth.poster` — the X API v2 seam (OAuth 1.0a signing, stdlib-only);
  inert unless every credential is present.

Stdlib-only, like tools/lineage and tools/reeve: the scheduled workflow reads
policy straight from the checkout with no pip step in front of it.
"""

__all__ = [
    "config",
    "cron",
    "postslot",
    "poster",
    "queue",
    "simulate",
    "tweetlen",
]
