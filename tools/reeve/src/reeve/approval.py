"""Standing approval modes for the greenlight loop (issue #446, #296 item 5).

The approval poll (#444) resolves a parked decision only on an authorized
human's 👍 or ``/decide``. This module adds the owner's **standing, reviewed,
per-category rules** on top — the session-permission-mode analogue #296 named:

* ``auto`` — a **YES** greenlight resolves with no reaction needed, once the
  👎 grace window has passed (the owner's 2026-08-30 ruling: doc-only
  follow-ups);
* ``deny`` — the category is human-only: Reeve drafts no greenlight on it and
  the poll never resolves it, not even on a 👍 (gate machinery);
* ``ask`` — everything else, and the default: #444's behaviour, unchanged.

The rules live in ``.github/reeve.conf`` (``approve_auto:`` / ``approve_deny:``,
comma lists over the closed :data:`CATEGORIES` vocabulary, parsed strictly by
``config.py``). Both default to empty, so an absent key — or a conf the
command was never handed — means every parked decision asks: the fail-safe
direction, since asking is exactly what the loop did before this module.

Classification is deterministic and **asymmetric**, which is the security
property this module exists to hold:

* **Only a trusted signal can loosen.** A category reaches ``auto`` only
  through its label (:data:`CATEGORY_LABELS`), and only when the driver has
  verified that the label's latest applier is a human whose real repository
  permission is write-level — the same bar a 👍 clears
  (:func:`label_actor_trusted`). A label applied by a bot (the workflow
  token's ``github-actions[bot]``, or any ``[bot]`` App) never loosens: an
  agentic routine reading untrusted issue text may hold ``issues: write``, and
  a label it applied must not become standing approval authority.
* **Untrusted text can only tighten.** The issue's title and body are written
  by whoever filed it — often a routine — and can be edited later, so they can
  place an issue in a category (:data:`TEXT_PATTERNS`, today only ``gates``)
  but never vouch for one: a category that only text (or an unverified label)
  names forces ``ask`` even when the conf lists it under ``approve_auto``, and
  can always reach ``deny``.

Most restrictive wins — deny > ask > auto — and an unclassified issue asks.
A parked decision is an *issue*, not a PR, so there are no changed paths to
read: the labels and the text that names paths are the only deterministic
signals there are, and the asymmetry above is what makes the text one safe.

Pure: no I/O, no network, no clock — ``now`` is always handed in. The driver
(``pushthrough.run_poll``, the trusted Select step in ``cli.py``) gathers the
labels, the text and the label events through the GET seam and calls here.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

# --- the closed vocabulary ----------------------------------------------------

DOCS = "docs"
GATES = "gates"

# Every category a conf rule may name. Closed on purpose: a category the code
# cannot classify would be a rule that silently never fires, so config.py
# refuses any name outside this tuple.
CATEGORIES = (DOCS, GATES)

# The trusted signal for each category — one label a human applies. `docs-only`
# is deliberately NOT the generic `documentation` label: that one has been
# applied to issues whose fix shipped a check script (#26 added
# scripts/docs-check.sh), so it means "about docs", not "touches only docs" —
# and standing approval authority needs the narrower assertion.
CATEGORY_LABELS = {
    DOCS: "docs-only",
    GATES: "gate-machinery",
}

# Untrusted-text patterns, matched as substrings of the normalized title+body
# (:func:`normalize`). TIGHTEN-ONLY by construction: a text hit makes its
# category untrusted, which can deny or force ask but can never reach auto.
# There is deliberately no `docs` entry — text naming only docs paths is
# exactly what an attacker would write, and it may never loosen anything.
#
# `gates` is the owner's list (#446, 2026-08-30): scripts/*-check.sh,
# .github/workflows/ci.yml, gate.sh, the .claude/*-settings.json deny
# backstops and the *-perms-check.sh guards — plus the shared
# .claude/settings.json every backstop is defined against. Text cannot tell
# "touches" from "mentions", so an issue that merely names gate.sh as its
# verification step classifies too; that over-reach lands on deny (Reeve
# stays silent, a human rules) — the recoverable direction. `check.sh` alone
# is deliberately NOT a pattern: `./scripts/check.sh green` is near-universal
# Done-when boilerplate, and the owner's list names the *-check.sh family.
GATE_TEXT_PATTERNS = (
    "-check.sh",            # scripts/*-check.sh, *-perms-check.sh included
    "perms-check",          # a perms-check guard named without its .sh
    "gate.sh",              # scripts/gate.sh (readme-gate.sh too)
    "ci.yml",               # .github/workflows/ci.yml
    "-settings.json",       # the .claude/*-settings.json deny backstops
    ".claude/settings.json",  # the shared allow list the backstops counter
)
TEXT_PATTERNS = {GATES: GATE_TEXT_PATTERNS}

# --- modes --------------------------------------------------------------------

MODE_AUTO = "auto"
MODE_ASK = "ask"
MODE_DENY = "deny"

# The ledger/approver identity a standing-rule resolution is recorded under
# (``standing-rule:docs``) — never a human login, so `/decide status`, the
# ledger and the precedent log all say a rule, not a person, resolved it.
STANDING_RULE_PREFIX = "standing-rule:"

# The 👎 window an auto-approve must wait out, measured from the greenlight's
# own post. The poll runs before the drafter in the same job, so a greenlight
# is never polled in the run that posted it — but a manual workflow_dispatch
# minutes later would be, so the window is enforced here rather than left to
# the cadence. Just under the daily cadence on purpose: an on-time next
# scheduled run (~24h later) qualifies and a same-day dispatch never does. A
# heavily delayed scheduled post can make the next run fall short, which only
# waits one more day — the fail-safe direction.
AUTO_APPROVE_GRACE = timedelta(hours=20)


@dataclass(frozen=True)
class Rules:
    """The committed rule set: which categories auto-approve and which deny.

    Validated on construction as well as in ``config.py`` — an unknown
    category or a category in both sets is never a representable state, so
    no caller can hand the poll a rule set the parser would have refused.
    """

    auto: frozenset = frozenset()
    deny: frozenset = frozenset()

    def __post_init__(self) -> None:
        unknown = (set(self.auto) | set(self.deny)) - set(CATEGORIES)
        if unknown:
            raise ValueError(f"unknown approval categories {sorted(unknown)} (known: {list(CATEGORIES)})")
        both = set(self.auto) & set(self.deny)
        if both:
            raise ValueError(f"categories {sorted(both)} are both auto-approve and deny")


@dataclass(frozen=True)
class Classification:
    """Which categories a parked decision falls in, split by signal trust.

    ``trusted`` — categories named by a label whose applier was verified;
    ``untrusted`` — categories named only by text or by an unverified label.
    A category can sit in both (a verified label plus matching text).
    ``evidence`` is the human-readable why, for the poll's log and reply.
    """

    trusted: frozenset
    untrusted: frozenset
    evidence: tuple = ()

    @property
    def categories(self) -> frozenset:
        return self.trusted | self.untrusted


def normalize(text: str) -> str:
    """Fold ``text`` for matching: NFKC, strip format characters, casefold.

    The reeve-signoff sensitive-path guard's normalization: compatibility
    forms fold, zero-width/format characters (category ``Cf``) are removed so
    they cannot split a pattern, and casefold beats ``lower`` on non-ASCII.
    Only tightening rides on this, so a smuggled pattern it still misses costs
    an attacker nothing they could not get by leaving the text out — the
    issue simply asks.
    """
    folded = unicodedata.normalize("NFKC", text or "")
    return "".join(ch for ch in folded if unicodedata.category(ch) != "Cf").casefold()


def _label_key(name: str) -> str:
    """A label name as GitHub compares it: case-insensitively."""
    return (name or "").casefold()


def text_hits(title: str, body: str) -> dict:
    """``{category: (pattern, ...)}`` for every text pattern in title+body."""
    haystack = normalize(f"{title}\n{body}")
    hits = {}
    for category, patterns in TEXT_PATTERNS.items():
        found = tuple(p for p in patterns if p in haystack)
        if found:
            hits[category] = found
    return hits


def classify(
    labels: Iterable[str],
    title: str,
    body: str,
    verified_labels: Iterable[str] = (),
) -> Classification:
    """Classify one parked decision from its labels and its text.

    ``verified_labels`` is the subset of ``labels`` whose latest applier the
    driver verified (:func:`label_applier` + :func:`label_actor_trusted`);
    the Select step passes none, which is right — it only ever acts on
    ``deny``, and nothing may loosen there. A verified label that is not
    actually present counts for nothing.
    """
    # GitHub label names are case-insensitive, so `Docs-Only` is the same
    # label as `docs-only`: compare casefolded, or a differently-cased label
    # would silently loosen nothing and (worse) a differently-cased
    # `gate-machinery` would silently deny nothing.
    present = {_label_key(label) for label in labels or ()}
    verified = present & {_label_key(label) for label in verified_labels or ()}
    trusted: set[str] = set()
    untrusted: set[str] = set()
    evidence: list[str] = []
    for category, label in CATEGORY_LABELS.items():
        if _label_key(label) not in present:
            continue
        if _label_key(label) in verified:
            trusted.add(category)
            evidence.append(f"`{category}`: label `{label}` (applied by a write-permission human)")
        else:
            untrusted.add(category)
            evidence.append(f"`{category}`: label `{label}` (applier not verified — cannot loosen)")
    for category, patterns in text_hits(title, body).items():
        untrusted.add(category)
        named = ", ".join(f"`{p}`" for p in patterns)
        evidence.append(f"`{category}`: the issue text names {named} (untrusted — can only tighten)")
    return Classification(frozenset(trusted), frozenset(untrusted), tuple(evidence))


def mode_for(classification: Classification, rules: Rules) -> tuple[str, frozenset]:
    """The approval mode for a classified decision, and the categories behind it.

    Most restrictive wins:

    1. **deny** when ANY category — trusted or not — is a deny category (text
       may always tighten);
    2. **auto** only when there is at least one category, EVERY category is
       an auto-approve category, and EVERY category is vouched for by a
       trusted signal — so a text-only or unverified-label category, or a
       mix with any non-auto category, falls through to …
    3. **ask**, the default (and the answer for an unclassified decision).

    Returns ``(mode, categories)``: the deny categories that fired, the auto
    categories that resolved it, or every category seen (possibly none) for
    ``ask``.
    """
    cats = classification.categories
    denied = cats & rules.deny
    if denied:
        return MODE_DENY, frozenset(denied)
    if cats and cats <= rules.auto and cats <= classification.trusted:
        return MODE_AUTO, frozenset(cats)
    return MODE_ASK, frozenset(cats)


def standing_rule_login(categories: Iterable[str]) -> str:
    """The approver identity a standing-rule resolution records: ``standing-rule:docs``."""
    return STANDING_RULE_PREFIX + "+".join(sorted(categories))


def loosening_labels(labels: Iterable[str], rules: Rules) -> list[str]:
    """The present labels whose category could loosen — the only ones worth
    the label-events read (a deny or ask category's applier changes nothing)."""
    present = {_label_key(label) for label in labels or ()}
    return sorted(
        label for category, label in CATEGORY_LABELS.items()
        if category in rules.auto and _label_key(label) in present
    )


def label_applier(events: Iterable[dict[str, Any]], label: str) -> str:
    """The login whose ``labeled`` event most recently applied ``label``.

    ``events`` is the issue's label-event history as the GET seam returns it
    (``{"event", "label", "actor", "created_at"}``). The newest ``labeled``
    event for the name wins — the one that put the label there now. No such
    event (a renamed label, a truncated history) is ``""``: an unknown applier,
    which :func:`label_actor_trusted` never trusts.
    """
    newest: Optional[dict[str, Any]] = None
    for event in events or ():
        if event.get("event") != "labeled" or _label_key(event.get("label") or "") != _label_key(label):
            continue
        if newest is None or str(event.get("created_at", "")) >= str(newest.get("created_at", "")):
            newest = event
    return (newest or {}).get("actor", "") or ""


def label_actor_trusted(login: str, authorized: Callable[[str], bool]) -> bool:
    """Whether a label applied by ``login`` may loosen a decision.

    The inverse of ``greenlight.marker_author_trusted`` for bots: the workflow
    token's ``github-actions[bot]`` and every other ``[bot]`` App are refused
    by identity, with no lookup — a marker the loop posted is its own, but a
    label a routine applied is a routine's judgement, never the owner's
    delegation. Any other login must hold a real write-level permission
    (``authorized`` is the driver's memoized ``permission_of`` check — the
    same one a 👍 passes). An empty login is never trusted.
    """
    if not login or login.endswith("[bot]"):
        return False
    return bool(authorized(login))


def _parse_iso(stamp: str) -> Optional[datetime]:
    try:
        parsed = datetime.strptime(stamp or "", "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc)


def grace_elapsed(created_at: str, now: datetime, grace: timedelta = AUTO_APPROVE_GRACE) -> bool:
    """Whether a greenlight posted at ``created_at`` has waited out ``grace``.

    An unparseable or missing stamp has NOT elapsed — the fail-safe answer:
    an auto-approve that cannot prove the owner had their 👎 window waits.
    """
    posted = _parse_iso(created_at)
    if posted is None:
        return False
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)  # a naive clock is read as UTC
    return now - posted >= grace


def grace_ends(created_at: str, grace: timedelta = AUTO_APPROVE_GRACE) -> str:
    """When the grace window closes, as an ISO stamp (``""`` if unknowable)."""
    posted = _parse_iso(created_at)
    return (posted + grace).strftime("%Y-%m-%dT%H:%M:%SZ") if posted else ""
