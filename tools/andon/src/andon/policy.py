"""The pure core: constants, the pulled test, the decision, the rendered text.

No I/O here — nothing in this module imports ``os``, ``urllib`` or anything
network-capable (tests/test_purity.py holds it). Every byte the workflow
writes to GitHub is rendered here, so the whole surface is unit-testable
offline and the workflow step only carries text it was handed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

# The HTML marker the status issue's body starts with — how the reconciler
# recognises its own issue (belt-and-braces with the label, the groomer's
# sticky-report pattern). The workflow's github-script step carries the same
# literals; tests/test_workflow.py pins the two sets equal.
MARKER = "<!-- andon-cord -->"
LABEL = "andon-cord"
NOTICE_LABEL = "notice"
TITLE = "🛑 AI andon cord pulled — AI usage bypassed"
VARIABLE = "AI_ANDON_CORD"
DOC = "docs/andon-cord.md"

ACTIONS = ("open", "close", "none")

_ISO_Z = "%Y-%m-%dT%H:%M:%SZ"


def is_pulled(raw: Optional[str]) -> bool:
    """Is the cord pulled, given the variable's raw value?

    Mirrors GitHub's expression ``vars.AI_ANDON_CORD == 'pulled'`` EXACTLY:
    the comparison is case-insensitive, so ``Pulled`` and ``PULLED`` pull it
    too — and nothing else is forgiven. GitHub does **not** trim whitespace,
    so neither does this: ``' pulled '`` and ``'pulled '`` read as released
    here precisely because every workflow gate reads them as released. A
    tolerant reading would split the brain — the AI jobs keep running while
    the status issue opens and Reeve banners a bypass that isn't happening.
    An unset variable (``None`` / empty), ``released``, ``false`` or any
    other word means released — the cord's off state is the default.
    """
    return raw is not None and raw.casefold() == "pulled"


@dataclass(frozen=True)
class OpenIssue:
    """The open status issue the gather layer found (or ``None``)."""

    number: int
    created_at: datetime


@dataclass(frozen=True)
class Decision:
    """What the workflow's one write step should do this run."""

    action: str  # one of ACTIONS
    issue_number: Optional[int]
    reason: str

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"unknown action {self.action!r}; expected one of {ACTIONS}")


def decide(pulled: bool, open_issue: Optional[OpenIssue]) -> Decision:
    """The four-branch reconcile: open once on pull, close once on release.

    * pulled, no open issue    → ``open`` (the first observation of a pull)
    * pulled, open issue       → ``none`` (still pulled; the issue stands)
    * released, open issue     → ``close`` (the first observation of release)
    * released, no open issue  → ``none`` (steady state; nothing to do)
    """
    if pulled and open_issue is None:
        return Decision("open", None, "cord pulled and no open status issue — opening one")
    if pulled and open_issue is not None:
        return Decision(
            "none",
            open_issue.number,
            f"still pulled since {iso(open_issue.created_at)} (#{open_issue.number} stays open)",
        )
    if not pulled and open_issue is not None:
        return Decision(
            "close",
            open_issue.number,
            f"cord released — closing #{open_issue.number} (open since {iso(open_issue.created_at)})",
        )
    return Decision("none", None, "cord released and nothing open — nothing to do")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def parse_iso(s: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerant of a trailing ``Z``; always UTC-aware."""
    text = s.strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    """Render a datetime as ``YYYY-MM-DDTHH:MM:SSZ`` (UTC, second precision)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(_ISO_Z)


def format_duration(delta: timedelta) -> str:
    """Humanise a span at the reconciler's own (hourly) granularity.

    ``under an hour`` below 60 minutes; otherwise whole hours, with whole
    days split out above 24 (``about 3 days 4 hours``, ``about 2 hours``,
    ``about 1 day``). Never negative: a clock skew between the issue's
    ``created_at`` and the run's ``now`` clamps to zero, so the closing
    comment can never claim a negative episode.
    """
    total_s = max(0, int(delta.total_seconds()))
    hours, _ = divmod(total_s, 3600)
    if hours < 1:
        return "under an hour"
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days} day" + ("" if days == 1 else "s"))
    if hours:
        parts.append(f"{hours} hour" + ("" if hours == 1 else "s"))
    return "about " + " ".join(parts)


# ---------------------------------------------------------------------------
# Rendered text — every byte the workflow writes
# ---------------------------------------------------------------------------


def doc_link(repo: Optional[str] = None) -> str:
    """A markdown link to the design doc.

    An issue body is not rendered repo-relative, so when the repo is known
    the link is absolute (to the default branch's blob); otherwise the bare
    path, which is what the docs and the offline demos show.
    """
    if repo:
        return f"[`{DOC}`](https://github.com/{repo}/blob/main/{DOC})"
    return f"[`{DOC}`]({DOC})"


def render_open_body(now: datetime, repo: Optional[str] = None) -> str:
    """The status issue's body. MARKER is the first line, always."""
    stamp = iso(now)
    link = doc_link(repo)
    return f"""{MARKER}
**The AI andon cord is pulled.** First observed at **{stamp}** by the hourly reconciler.

The repo variable `{VARIABLE}` is set to `pulled`, so **every AI-consuming workflow job in this repository is bypassed** — grey/skipped, never red, no provider API call, no `needs-decision` escalation — with one `::notice::` line per run explaining why. This issue is the visible, timestamped record of that state; it closes itself when the cord is released.

## What is bypassed while the cord is pulled

- The twelve scheduled agent routines: the backlog burn, the design run, the chunker, the labeler, the product scout, the spike converter, the adoption assessor, the Twitter/X growth agent, Reeve's growth queueing, both halves of the agent forge (Wright's proposals and Reeve's sign-off) and Reeve's greenlight drafter.
- The backlog groomer's narrative layer (the one model call in its otherwise deterministic report).
- The Jane / Drik / PM-triage / design-coach reviewers and the Oracle on pull requests.
- CI's product-page drafting (`product-page.sh`, the Claude API step of the `regen` job).
- The Z.AI lifestyle-shot, product-still and lifestyle-clip generators.
- The model-chain smoke (`model-smoke.yml`).

## What continues unchanged

Every deterministic job: the CI gates (render, printcheck, test-slice, readme-gate, the check suites), `regen`'s preview rendering and commit-back, Reeve's bench-health report, the groomer's deterministic report, telemetry, and the `/decide` command.

## Consequence for design PRs

A design PR needs two clean, current reviewer sign-offs to merge, and the reviewers do not run while the cord is pulled — so `reviewer-signoff` **blocks** design PRs until the cord is released (then push, or close and reopen the PR, to re-fire a review round — nothing re-fires on its own) or a maintainer applies the `signoff-override` label.

## How to release

Delete the `{VARIABLE}` repo variable, or set it to anything but `pulled` (Settings → Secrets and variables → Actions → Variables). The AI jobs resume on their next run, and **this issue closes itself within about an hour** — the reconciler runs hourly and on `workflow_dispatch` (dispatch `Andon cord status (AI bypass)` to close it immediately).

> Timestamps here are *observation* times at the reconciler's hourly granularity, not the moment the variable changed.

See {link} for the full design.
"""


def render_close_comment(
    opened_at: datetime, now: datetime, repo: Optional[str] = None
) -> str:
    """The closing comment: names both timestamps and the humanised span."""
    return (
        f"🟢 AI andon cord released — first observed {iso(now)}. "
        f"The cord was pulled for {format_duration(now - opened_at)} "
        f"(from {iso(opened_at)}; observation granularity is the reconciler's "
        f"hourly cadence). AI-consuming workflow jobs resume on their next run — "
        f"see {doc_link(repo)}."
    )
