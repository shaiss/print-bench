# growth/ — the growth desk's committed artifacts

The growth desk ([docs/growth.md](../docs/growth.md)) is the bench's
audience loop: product managers queue messages (`growth-queue` issues, via
`/growth-queue` or the issue form) and channel-specific growth agents drain
them — Lark (`/growth-twitter`) for Twitter/X first. This directory holds
the desk's **reviewable output**, committed so the feed can be read before
it exists anywhere else:

* `twitter/dryruns/` — accelerated-timeline dry runs (`python3 -m growth
  simulate`): what would have been posted, when, in drain order, over a
  simulated window. One markdown report + ndjson sidecar per run, named by
  date. These are the artifacts the arming checklist says to read before
  ever setting a live key.

Live posting leaves its record on each queue issue's own thread (the posting
tool's marker comments), not here — the issue thread is the per-item audit
trail, this directory is the before-the-fact preview. The engine behind both
is [tools/growth](../tools/growth/README.md).
