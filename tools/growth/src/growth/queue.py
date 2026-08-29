"""The queue-drain ordering policy — a pure function of a queue snapshot.

A queue item is one open ``growth-queue`` issue (plus its channel label).
The policy an agent drains the queue in is deterministic and lives HERE, not
in a model's judgment or a workflow's jq: **priority first** (an item whose
labels carry ``priority:high``), **then oldest issue number first** — FIFO
with one escape hatch, which is what a queue is. Items parked for a human
(``needs-decision``) and items already posted are not in a snapshot at all
(the selector excludes the label; the posting tool's marker guard refuses the
duplicate), so this module never re-checks them.

The snapshot shape is a plain list of dicts — ``number`` (int, required),
``title``, ``labels`` (list of label-name strings) — exactly what the trusted
workflow Select step or the dry-run harness hands over.
"""

from __future__ import annotations

PRIORITY_LABEL = "priority:high"
QUEUE_LABEL = "growth-queue"


def _labels(item: dict) -> list[str]:
    out = []
    for lbl in item.get("labels") or []:
        out.append(lbl.get("name", "") if isinstance(lbl, dict) else str(lbl))
    return out


def drain_order(snapshot: list[dict]) -> list[dict]:
    """The snapshot in the order the channel agent drains it: ``priority:high``
    items first, then oldest number first within each class. Items without a
    valid integer ``number`` are dropped (they cannot be posted against)."""
    items = [i for i in snapshot if isinstance(i.get("number"), int) and not isinstance(i.get("number"), bool)]
    return sorted(
        items,
        key=lambda i: (0 if PRIORITY_LABEL in _labels(i) else 1, i["number"]),
    )


def channel_of(item: dict) -> str | None:
    """The item's channel, from its ``channel:<name>`` label. None when the
    item carries no channel label (a hand-filed issue missing it — the posting
    tool refuses those, and the report calls them out instead of guessing)."""
    for name in _labels(item):
        if name.startswith("channel:"):
            return name.split(":", 1)[1] or None
    return None
