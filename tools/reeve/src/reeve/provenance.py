"""Reeve's provenance lens — the ONE module in the package that reads the harvester's data refs.

docs/provenance.md §Registration: Reeve watches the keyless provenance
harvester (``.github/workflows/provenance.yml``, ``tools/provenance``) with two
detectors, and every read they need lives here, so the #646 read lens
(``tools/provenance/tests/test_read_lens.py``) can allow-list exactly this file:

* ``provenance-foreign-tip`` — either data ref's tip under the tip-continuity
  rule. :func:`continuity_verdict` is a PORT of ``tools/provenance``'s
  ``gitstore.continuity_verdict`` (the tools stay independently installable,
  so it is mirrored, not imported), and ``tests/test_provenance.py`` runs it
  over every row of the ONE shared table,
  ``tools/provenance/tests/fixtures/continuity_cases.json`` — the two
  implementations cannot drift apart without one suite going red.
  ``foreign``, ``deleted`` and ``unanchored`` are findings; once armed, so is
  ``bootstrap`` (an absent ref the harvester has never published).
* ``provenance-lag`` — (a) the oldest pending unit in the evidence ref's
  ``state.json`` past its anchor + ``provenance_lag_hours``: the anchor is
  ``due_at``, or ``defer_until`` for a unit LEGITIMATELY deferred (every
  reason one of :data:`DEFER_REASONS` — an in-flight run, a pending
  deployment — which the harvester holds until ``defer_until`` by design); a
  unit that is failing (``capture-failed``, ``contract-invalid``) is measured
  from ``due_at``. (b) The STALL check: one page of
  ``/pulls?state=closed&sort=updated&direction=desc``; a PR closed more than
  ``settle_hours + max_defer_hours + provenance_lag_hours`` ago, last updated
  more than ``provenance_lag_hours`` ago (so the harvester's hourly listing
  has had its chance at an update — a fresh comment on an old PR is not a
  stall) and not before ``backfill_since`` (the harvester never lists those),
  that is in none of frozen (the ``raw/pr`` tree listing), ``pending`` or
  ``skipped`` means the harvester stopped seeing PRs — dropped schedule slots,
  a failing gate, a dead job — even though nothing is pending. Every closed
  PR a harvest pass sees lands in exactly one of the three (tools/provenance's
  ``freeze.plan_freezes``), which is what makes the absence meaningful.

Both read "not evaluated" only while the harvester is DISARMED (the
``PROVENANCE_ENABLED`` variable — whose raw value reeve.yml hands the report
job, the andon pattern — is not ``true`` under GitHub's case-insensitive
compare, or the committed ``.github/provenance.conf`` says ``enabled: false``),
on an offline run, or when the armed gather itself FAILED (a refused read, a
runaway artifact scan, an unreadable conf): the failure is caught, named in
the "not evaluated" reason, and the rest of the daily report still renders —
a provenance read problem never costs Reeve every other detector. Once armed
and gathered, an absent ref is a finding, never a skip.

**The reads** (all GET, through ``github._get`` — the package's one network
seam, so the tests monkeypatch it and nothing leaves the process): the two
tips (``/git/ref/heads/<ref>``); the repo-wide artifact list, newest first,
until each ref has a verified checkpoint or the horizon passes (bounded by
:func:`max_artifact_pages`, derived from the horizon); each candidate mark's
run (``/actions/runs/{id}``: ``path``, ``event``, ``head_branch``,
``head_sha``) and that run's commit on the default branch
(``/compare/{head_sha}...{default}``); the first parents a continuity walk
asks for (``/git/commits/{sha}``); ``state.json`` at the evidence tip
(``/contents``, the ``/git/blobs`` fallback past the contents size limit);
the ``raw/pr`` tree listing (``/git/trees``, three levels); and the one
closed-PR page.

**Which marks count.** A mark counts only when its artifact's
``workflow_run`` names the default branch and its run is ``provenance.yml``
fired by ``schedule`` / ``workflow_dispatch`` with ``head_branch`` the
default branch AND ``head_sha`` in the default branch's history (``compare``
status ``identical`` or ``ahead``). The last check is what refuses a run
dispatched on a TAG named like the default branch — its ``head_branch`` is
the tag's short name, so the name checks alone would pass it, and its YAML is
whatever the tag points at (a contents-write holder could make that upload
forged ``tip-…`` marks, then force-push the forged tip). Residual: this is
reachability, not the harvester's first-parent rule (which needs a clone
Reeve does not hold), so a commit reachable only through a merged PR's
second-parent history passes here; the harvester's own scan refuses such a
mark, its run goes red, and ``routine-dead`` reports it.

The policy values Reeve needs from the harvester (``enabled``,
``settle_hours``, ``max_defer_hours``, ``continuity_horizon_days``,
``backfill_since``) are READ from the committed ``.github/provenance.conf``,
never duplicated; Reeve's own threshold is ``provenance_lag_hours`` in
``.github/reeve.conf``.

Pure at import: the network seam is imported inside :func:`gather` only, so
``detectors.py`` can import the pure half (held by the package's purity scan).
"""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

EVIDENCE_REF = "provenance"
DERIVED_REF = "provenance-site"
REFS = (EVIDENCE_REF, DERIVED_REF)
WORKFLOW_PATH = ".github/workflows/provenance.yml"
MARK_EVENTS = frozenset({"schedule", "workflow_dispatch"})
MARK_KINDS = {"intent": "intent-", "tip": "tip-"}
VERDICTS = ("ok", "foreign", "deleted", "unanchored", "bootstrap")
CONF_PATH = os.path.join(".github", "provenance.conf")
#: The harvester's conf keys Reeve reads: ``enabled``, three integers, and ``backfill_since``.
CONF_KEYS = ("enabled", "settle_hours", "max_defer_hours", "continuity_horizon_days",
             "backfill_since")
_INT_KEYS = ("settle_hours", "max_defer_hours", "continuity_horizon_days")
#: Artifact-list pages (100 artifacts each) the scan may read per day of the continuity
#: horizon: ~70 artifacts a day were measured on 2026-10-14 (6,519 in all), so 3 pages a day
#: is ~4x headroom before :func:`max_artifact_pages` refuses a scan that has not reached
#: the horizon.
PAGES_PER_HORIZON_DAY = 3
MIN_ARTIFACT_PAGES = 10
#: Pending reasons that mean "deferred until ``defer_until`` by design" — tools/provenance's
#: ``freeze.REASON_IN_FLIGHT`` / ``REASON_DEPLOYMENT``, mirrored (the tools stay independently
#: installable) and pinned to them by a test in each suite. Any other reason is a failure.
DEFER_REASONS = frozenset({"in-flight-run", "deployment-pending"})
#: Compare statuses that put a run's head sha in the default branch's history.
ON_BRANCH_STATUSES = frozenset({"identical", "ahead"})
#: Unseen PR numbers a stall finding names (the count is always exact).
STALL_SHOWN = 10
#: Length cap of a gather-failure reason (the report's "not evaluated" line).
ERROR_SHOWN = 200

_SHA40_RE = re.compile(r"[0-9a-f]{40}")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_RAW_PR_RE = re.compile(r"([1-9][0-9]{0,6})(?:\.r[0-9]{1,4})?\.json\.gz")
_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


# --- pure: marks and the continuity port --------------------------------------

def _is_sha(s: Any) -> bool:
    return isinstance(s, str) and _SHA40_RE.fullmatch(s) is not None


def parse_mark_name(name: str) -> Optional[tuple[str, str, str]]:
    """``(kind, ref, sha)`` of an ``intent-<ref>-<sha40>`` / ``tip-<ref>-<sha40>`` artifact name."""
    for kind, prefix in MARK_KINDS.items():
        if not isinstance(name, str) or not name.startswith(prefix):
            continue
        rest = name[len(prefix):]
        for ref in (DERIVED_REF, EVIDENCE_REF):  # longest first
            if rest.startswith(f"{ref}-") and _is_sha(rest[len(ref) + 1:]):
                return kind, ref, rest[len(ref) + 1:]
    return None


def continuity_verdict(*, ref: str, tip: Optional[str], marks: Iterable[dict[str, Any]],
                       first_parent: Callable[[str], Optional[str]],
                       max_chain: int = 24) -> dict[str, Any]:
    """The tip-continuity rule — a port of tools/provenance's ``gitstore.continuity_verdict``.

    ``marks`` are VERIFIED marks (``{seq, kind, ref, sha, run_id}``) within the horizon;
    ``first_parent(sha)`` answers the evidence chain walk. Returns ``{ref, verdict, tip,
    checkpoint, chain, reason}``; ``verdict`` is one of :data:`VERDICTS`.
    """
    if ref not in REFS:
        raise ValueError(f"unknown ref {ref!r}")

    def out(verdict: str, checkpoint: Optional[str], chain: Iterable[str], reason: str) -> dict:
        return {"ref": ref, "verdict": verdict, "tip": tip, "checkpoint": checkpoint,
                "chain": list(chain), "reason": reason}

    mine = [m for m in marks if m.get("ref") == ref]
    tips = sorted((m for m in mine if m.get("kind") == "tip"), key=lambda m: m["seq"], reverse=True)
    if not tips:
        if tip is None:
            return out("bootstrap", None, (), "ref absent, no checkpoint in the horizon")
        return out("unanchored", None, (), "no checkpoint in the horizon")
    c = tips[0]
    if tip is None:
        return out("deleted", c["sha"], (), f"ref absent; newest checkpoint {c['sha'][:8]}")
    if tip == c["sha"]:
        return out("ok", c["sha"], (), "tip is the newest checkpoint")
    newer = {m["sha"] for m in mine if m.get("kind") == "intent" and m["seq"] > c["seq"]}
    if ref == DERIVED_REF:
        if tip in newer:
            return out("ok", c["sha"], (tip,), "declared after the newest checkpoint")
        return out("foreign", c["sha"], (),
                   f"{tip[:8]} is neither checkpoint {c['sha'][:8]} nor declared after it")
    chain: list[str] = []
    sha: Optional[str] = tip
    for _ in range(max_chain):
        if sha not in newer:
            return out("foreign", c["sha"], chain,
                       f"{sha[:8]} is not an intent declared after checkpoint {c['sha'][:8]}")
        chain.append(sha)
        parent = first_parent(sha)
        if parent == c["sha"]:
            return out("ok", c["sha"], chain,
                       f"{len(chain)} declared commit(s) on checkpoint {c['sha'][:8]}")
        if parent is None:
            break
        sha = parent
    return out("foreign", c["sha"], chain,
               f"no declared chain from {tip[:8]} to checkpoint {c['sha'][:8]}")


def armed(conf_enabled: bool, variable: Optional[str]) -> bool:
    """The harvester's two-key arming as its schedule sees it: the conf's ``enabled`` AND the
    ``PROVENANCE_ENABLED`` value casefolding to ``true`` — GitHub's ``==`` is case-insensitive
    and never trims, so ``' true'`` is disarmed (tools/provenance ``conf.armed``)."""
    return conf_enabled is True and isinstance(variable, str) and variable.casefold() == "true"


def max_artifact_pages(horizon_days: int) -> int:
    """The artifact-scan page bound for a ``horizon_days`` horizon (:data:`PAGES_PER_HORIZON_DAY`
    a day, never under :data:`MIN_ARTIFACT_PAGES`) — derived, so a longer horizon or a busier
    repo moves it with the conf instead of tripping a fixed count."""
    return max(MIN_ARTIFACT_PAGES, int(horizon_days) * PAGES_PER_HORIZON_DAY)


def read_conf(text: str, where: str = CONF_PATH) -> dict[str, Any]:
    """The five values Reeve needs from the committed harvester conf (``key: value``, ``#``
    comments; the file's other keys are the harvester's own and are not read). A missing or
    malformed value raises ``ValueError`` naming ``where`` — never a silent default."""
    found: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip() in CONF_KEYS:
            found[key.strip()] = value.strip()
    missing = [k for k in CONF_KEYS if k not in found]
    if missing:
        raise ValueError(f"{where}: missing {', '.join(missing)}")
    if found["enabled"].lower() not in ("true", "false"):
        raise ValueError(f"{where}: 'enabled' must be true or false")
    out: dict[str, Any] = {"enabled": found["enabled"].lower() == "true"}
    for key in _INT_KEYS:
        if not re.fullmatch(r"[0-9]{1,6}", found[key]):
            raise ValueError(f"{where}: {key!r} must be a non-negative integer")
        out[key] = int(found[key])
    if not _DATE_RE.fullmatch(found["backfill_since"]) or _ts(found["backfill_since"]) is None:
        raise ValueError(f"{where}: 'backfill_since' must be a YYYY-MM-DD date")
    out["backfill_since"] = found["backfill_since"]
    return out


# --- pure: the two detectors ------------------------------------------------------

def _ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def foreign_tip(block: dict[str, Any]) -> list[dict[str, Any]]:
    """``provenance-foreign-tip`` findings: every ref whose verdict is not ``ok``."""
    parents = block.get("parents") or {}
    marks = block.get("marks") or []
    findings = []
    for ref in REFS:
        v = continuity_verdict(ref=ref, tip=(block.get("tips") or {}).get(ref), marks=marks,
                               first_parent=parents.get)
        if v["verdict"] == "ok":
            continue
        findings.append({"ref": ref, "verdict": v["verdict"],
                         "tip": (v["tip"] or "")[:8] or None,
                         "checkpoint": (v["checkpoint"] or "")[:8] or None,
                         "reason": v["reason"]})
    return findings


def lag(block: dict[str, Any], now: str, lag_hours: int) -> list[dict[str, Any]]:
    """``provenance-lag`` findings: an absent evidence ref, the oldest overdue pending unit,
    and the stall check (module docstring)."""
    t = _ts(now)
    if not (block.get("tips") or {}).get(EVIDENCE_REF):
        return [{"kind": "no-evidence",
                 "detail": "the provenance evidence ref is absent — nothing has been harvested"}]
    findings: list[dict[str, Any]] = []
    state = block.get("state") or {}
    overdue = []
    for kind in ("pr", "brief"):
        for key, entry in sorted(((state.get("pending") or {}).get(kind) or {}).items()):
            entry = entry or {}
            due = _ts(entry.get("due_at", ""))
            if due is None or t is None:
                continue
            # A unit deferred by design (every reason a DEFER_REASONS one) is pending until
            # defer_until; a failing one (capture-failed, contract-invalid) from due_at.
            anchor_key, anchor = "due_at", due
            reasons = set(entry.get("reasons") or ())
            until = _ts(entry.get("defer_until", ""))
            if reasons and reasons <= DEFER_REASONS and until is not None and until > due:
                anchor_key, anchor = "defer_until", until
            past = (t - (anchor + timedelta(hours=lag_hours))).total_seconds() / 3600.0
            if past > 0:
                overdue.append((past, kind, key, anchor_key, entry[anchor_key]))
    if overdue:
        overdue.sort(key=lambda o: (-o[0], o[1], int(o[2]) if o[2].isdigit() else 0))
        past, kind, key, anchor_key, since = overdue[0]
        findings.append({"kind": "overdue", "unit": f"{kind} #{key}", "anchor": anchor_key,
                         "since": since, "hours_past": round(past, 1), "count": len(overdue)})
    conf = block.get("conf") or {}
    window = int(conf.get("settle_hours", 0)) + int(conf.get("max_defer_hours", 0)) + int(lag_hours)
    floor = _ts(conf.get("backfill_since") or "")
    known = ({int(n) for n in block.get("frozen_prs") or []}
             | {int(k) for k in ((state.get("pending") or {}).get("pr") or {})}
             | {int(k) for k in ((state.get("skipped") or {}).get("pr") or {})})
    unseen = []
    for pr in block.get("closed_prs") or []:
        closed = _ts(pr.get("closed_at") or "")
        if closed is None or t is None or pr.get("number") in known:
            continue
        # updated_at ≥ closed_at on GitHub; an older snapshot without it reads closed_at.
        updated = _ts(pr.get("updated_at") or "") or closed
        if floor is not None and updated < floor:
            continue  # never in the harvester's listing (its cursor floor is backfill_since)
        if (t - updated).total_seconds() / 3600.0 <= lag_hours:
            continue  # touched since the harvester's last chances to list it: not yet a stall
        if (t - closed).total_seconds() / 3600.0 > window:
            unseen.append(int(pr["number"]))
    if unseen:
        unseen.sort()
        findings.append({"kind": "stall", "prs": unseen[:STALL_SHOWN], "count": len(unseen),
                         "window_hours": window})
    return findings


def not_evaluated_reason(block: Optional[dict[str, Any]]) -> Optional[str]:
    """Why the two detectors cannot run on this block (``None`` = evaluate)."""
    if block is None:
        return "no provenance block gathered (offline run — pass --repo to enable)"
    if not block.get("armed"):
        return block.get("reason") or "the provenance harvester is disarmed"
    if block.get("error"):
        return f"the provenance gather failed: {block['error']}"
    return None


def _one_line(text: str) -> str:
    """A gather failure as one markdown-defused line of at most :data:`ERROR_SHOWN` characters
    (the report's not-evaluated line carries it; an exception text is not ours to trust)."""
    flat = re.sub(r"\s+", " ", str(text)).strip()
    escaped = re.sub(r"([\\`*_\[\]|~<>])", r"\\\1", flat)
    return escaped[:ERROR_SHOWN] + "…" if len(escaped) > ERROR_SHOWN else escaped


# --- the GET-only gather -----------------------------------------------------------

def _api(repo: str, path: str) -> str:
    from .github import API_ROOT

    return f"{API_ROOT}/repos/{repo}{path}"


def _call(url: str, token: str) -> tuple[Any, str]:
    from . import github  # the network seam, resolved at call time (tests patch github._get)

    return github._get(url, token)


def _get_or_none(url: str, token: str) -> Any:
    """One GET; ``None`` on a 404 (an absent ref or path), any other error propagates."""
    try:
        body, _ = _call(url, token)
    except Exception as exc:  # urllib's HTTPError carries .code; never swallow anything else
        if getattr(exc, "code", None) == 404:
            return None
        raise
    return body


def _tip(repo: str, token: str, ref: str) -> Optional[str]:
    body = _get_or_none(_api(repo, f"/git/ref/heads/{ref}"), token)
    sha = ((body or {}).get("object") or {}).get("sha") if isinstance(body, dict) else None
    return sha if _is_sha(sha) else None


def _on_default_branch(repo: str, token: str, sha: str, default_branch: str,
                       memo: dict[str, bool]) -> bool:
    """Is ``sha`` in the default branch's history? ``GET /compare/{sha}...{default}``: status
    ``identical`` (it is the tip) or ``ahead`` (the branch moved on from it); ``behind`` /
    ``diverged`` — a tag's or another branch's commit — and an unknown sha (404) are not."""
    if sha not in memo:
        body = _get_or_none(_api(repo, f"/compare/{sha}...{default_branch}?per_page=1"), token)
        memo[sha] = isinstance(body, dict) and body.get("status") in ON_BRANCH_STATUSES
    return memo[sha]


def _scan_marks(repo: str, token: str, *, now: datetime, horizon_days: int,
                default_branch: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    horizon = now - timedelta(days=horizon_days)
    max_pages = max_artifact_pages(horizon_days)
    marks: list[dict[str, Any]] = []
    runs: dict[int, bool] = {}
    reach: dict[str, bool] = {}
    counts = {"pages": 0, "runs_verified": 0, "marks_rejected": 0}
    url: Optional[str] = _api(repo, "/actions/artifacts?per_page=100")
    while url:
        counts["pages"] += 1
        if counts["pages"] > max_pages:
            raise RuntimeError(f"more than {max_pages} artifact pages before the "
                               f"{horizon_days}-day horizon — refusing a silently-truncated "
                               "provenance continuity scan")
        body, link = _call(url, token)
        items = (body or {}).get("artifacts") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise RuntimeError("unexpected artifacts payload (no artifacts list)")
        past_horizon = False
        for art in items:
            created = _ts(art.get("created_at") or "")
            if created is not None and created < horizon:
                past_horizon = True
                continue
            parsed = parse_mark_name(art.get("name") or "")
            if parsed is None:
                continue
            wr = art.get("workflow_run") or {}
            run_id = wr.get("id")
            if wr.get("head_branch") != default_branch or not isinstance(run_id, int):
                counts["marks_rejected"] += 1
                continue
            if run_id not in runs:
                run = _get_or_none(_api(repo, f"/actions/runs/{run_id}"), token) or {}
                head = run.get("head_sha")
                # head_branch is a TAG's short name for a run dispatched on refs/tags/<default>;
                # only the head sha being in the default branch's history refuses that run.
                runs[run_id] = (run.get("path") == WORKFLOW_PATH
                                and run.get("event") in MARK_EVENTS
                                and run.get("head_branch") == default_branch
                                and _is_sha(head)
                                and _on_default_branch(repo, token, head, default_branch, reach))
                counts["runs_verified"] += runs[run_id]
            if not runs[run_id]:
                counts["marks_rejected"] += 1
                continue
            kind, ref, sha = parsed
            marks.append({"seq": int(art["id"]), "kind": kind, "ref": ref, "sha": sha,
                          "run_id": run_id})
        have = {m["ref"] for m in marks if m["kind"] == "tip"}
        if past_horizon or have >= set(REFS):
            break
        m = _LINK_NEXT_RE.search(link or "")
        url = m.group(1) if m else None
        if url is not None and not url.startswith(_api(repo, "/")):
            # The token rides on every request: never follow a next link off this repo's API.
            raise RuntimeError("artifact-list next link points off api.github.com/repos/"
                               f"{repo} — refusing to follow it")
    marks.sort(key=lambda m: m["seq"], reverse=True)
    return marks, counts


def _commit(repo: str, token: str, sha: str, memo: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if sha not in memo:
        memo[sha] = _get_or_none(_api(repo, f"/git/commits/{sha}"), token) or {}
    return memo[sha]


def _first_parent(repo: str, token: str, sha: str, memo: dict[str, dict[str, Any]]) -> Optional[str]:
    parents = _commit(repo, token, sha, memo).get("parents") or []
    first = (parents[0] or {}).get("sha") if parents else None
    return first if _is_sha(first) else None


def _tree(repo: str, token: str, sha: str) -> list[dict[str, Any]]:
    body = _get_or_none(_api(repo, f"/git/trees/{sha}"), token) or {}
    if body.get("truncated"):
        raise RuntimeError(f"git tree {sha[:8]} listing truncated — refusing a partial frozen set")
    return [e for e in body.get("tree") or [] if isinstance(e, dict)]


def _frozen_prs(repo: str, token: str, tip: str, memo: dict[str, dict[str, Any]]) -> list[int]:
    tree = ((_commit(repo, token, tip, memo).get("tree")) or {}).get("sha")
    for name in ("raw", "pr"):
        if not _is_sha(tree):
            return []
        entry = next((e for e in _tree(repo, token, tree)
                      if e.get("path") == name and e.get("type") == "tree"), None)
        tree = (entry or {}).get("sha")
    if not _is_sha(tree):
        return []
    nums = {int(m.group(1)) for e in _tree(repo, token, tree)
            if (m := _RAW_PR_RE.fullmatch(e.get("path") or ""))}
    return sorted(nums)


def _state(repo: str, token: str, tip: str) -> dict[str, Any]:
    body = _get_or_none(_api(repo, f"/contents/state.json?ref={tip}"), token)
    if not isinstance(body, dict):
        return {}
    content = body.get("content") or ""
    if body.get("encoding") != "base64" or not content:
        blob = _get_or_none(_api(repo, f"/git/blobs/{body.get('sha')}"), token) or {}
        content = blob.get("content") or ""
    try:
        doc = json.loads(base64.b64decode(content).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("provenance state.json is not valid JSON") from None
    return {"pending": doc.get("pending") or {}, "skipped": doc.get("skipped") or {}}


def gather(repo: str, token: str, *, root: str = ".", variable: Optional[str] = None,
           now: Optional[datetime] = None, default_branch: str = "main") -> dict[str, Any]:
    """The ``runHealth.provenance`` block :func:`foreign_tip` / :func:`lag` consume.

    Disarmed → ``{"armed": false, "reason": …}`` with NO request sent and the conf read
    only when the variable arms it. Armed → the tips, the verified marks (newest first),
    the first parents the continuity walk asked for, the scan counts, ``state.json``'s
    pending / skipped, the frozen PR numbers and one closed-PR page. Any failure once the
    variable arms it → ``{"armed": true, "error": <one defused line>}``: both detectors then
    read "not evaluated" with that reason and every other detector still reports."""
    if not (isinstance(variable, str) and variable.casefold() == "true"):
        return {"armed": False,
                "reason": "PROVENANCE_ENABLED is not 'true' — the harvester's schedule is "
                          "disarmed (arming is phase P2, docs/provenance.md)"}
    try:
        return _gather_armed(repo, token, root=root, variable=variable, now=now,
                             default_branch=default_branch)
    except Exception as exc:  # any read or parse failure: report it, never lose the report
        return {"armed": True, "error": _one_line(f"{type(exc).__name__}: {exc}")}


def _gather_armed(repo: str, token: str, *, root: str, variable: str, now: Optional[datetime],
                  default_branch: str) -> dict[str, Any]:
    with open(os.path.join(root, CONF_PATH), encoding="utf-8") as fh:
        conf = read_conf(fh.read())
    if not armed(conf["enabled"], variable):
        return {"armed": False,
                "reason": ".github/provenance.conf says 'enabled: false' — the harvester is "
                          "paused in git"}
    at = now or datetime.now(timezone.utc)
    tips = {ref: _tip(repo, token, ref) for ref in REFS}
    marks, counts = _scan_marks(repo, token, now=at, horizon_days=conf["continuity_horizon_days"],
                                default_branch=default_branch)
    memo: dict[str, dict[str, Any]] = {}
    parents: dict[str, Optional[str]] = {}

    def walk(sha: str) -> Optional[str]:
        parents[sha] = _first_parent(repo, token, sha, memo)
        return parents[sha]

    continuity_verdict(ref=EVIDENCE_REF, tip=tips[EVIDENCE_REF], marks=marks, first_parent=walk)
    evidence = tips[EVIDENCE_REF]
    state = _state(repo, token, evidence) if evidence else {}
    frozen = _frozen_prs(repo, token, evidence, memo) if evidence else []
    page, _ = _call(_api(repo, "/pulls?state=closed&sort=updated&direction=desc&per_page=100"), token)
    if not isinstance(page, list):
        raise RuntimeError("unexpected closed-pulls payload (not a list)")
    closed = [{"number": p["number"], "closed_at": p.get("closed_at"),
               "updated_at": p.get("updated_at")}
              for p in page if isinstance(p, dict) and isinstance(p.get("number"), int)]
    return {"armed": True,
            "conf": {"settle_hours": conf["settle_hours"],
                     "max_defer_hours": conf["max_defer_hours"],
                     "backfill_since": conf["backfill_since"]},
            "tips": tips, "marks": marks, "parents": parents, "scan": counts,
            "state": state, "frozen_prs": frozen, "closed_prs": closed}
