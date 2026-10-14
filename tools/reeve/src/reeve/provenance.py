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
  ``state.json`` past ``due_at + provenance_lag_hours``, and (b) the STALL
  check: one page of ``/pulls?state=closed&sort=updated&direction=desc``; a
  PR closed more than ``settle_hours + max_defer_hours +
  provenance_lag_hours`` ago that is in none of frozen (the ``raw/pr`` tree
  listing), ``pending`` or ``skipped`` means the harvester stopped seeing PRs
  — dropped schedule slots, a failing gate, a dead job — even though nothing
  is pending. Every closed PR a harvest pass sees lands in exactly one of the
  three (tools/provenance's ``freeze.plan_freezes``), which is what makes the
  absence meaningful.

Both read "not evaluated" only while the harvester is DISARMED (the
``PROVENANCE_ENABLED`` variable — whose raw value reeve.yml hands the report
job, the andon pattern — is not ``true`` under GitHub's case-insensitive
compare, or the committed ``.github/provenance.conf`` says ``enabled: false``)
or on an offline run. Once armed, an absent ref is a finding, never a skip.

**The reads** (all GET, through ``github._get`` — the package's one network
seam, so the tests monkeypatch it and nothing leaves the process): the two
tips (``/git/ref/heads/<ref>``); the repo-wide artifact list, newest first,
until each ref has a verified checkpoint or the horizon passes; each candidate
mark's run (``/actions/runs/{id}``: ``path``, ``event``, ``head_branch``);
the first parents a continuity walk asks for (``/git/commits/{sha}``);
``state.json`` at the evidence tip (``/contents``, the ``/git/blobs``
fallback past the contents size limit); the ``raw/pr`` tree listing
(``/git/trees``, three levels); and the one closed-PR page. A mark counts
only when its artifact's ``workflow_run`` is on the default branch and the run
is ``provenance.yml`` fired by ``schedule`` / ``workflow_dispatch`` — the
harvester's own rule minus its first-parent pre-filter, which needs a clone
Reeve does not hold (a residual only a rewritten default branch could reach).

The policy values Reeve needs from the harvester (``enabled``,
``settle_hours``, ``max_defer_hours``, ``continuity_horizon_days``) are READ
from the committed ``.github/provenance.conf``, never duplicated; Reeve's own
threshold is ``provenance_lag_hours`` in ``.github/reeve.conf``.

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
#: The harvester's conf keys Reeve reads (and the ints they must be).
CONF_KEYS = ("enabled", "settle_hours", "max_defer_hours", "continuity_horizon_days")
#: Artifact-list pages read at most (100 artifacts each; ~1.4 days a page measured on
#: 2026-10-14, so 70 pages comfortably cover the 90-day horizon). Hitting it raises.
MAX_ARTIFACT_PAGES = 70
#: Unseen PR numbers a stall finding names (the count is always exact).
STALL_SHOWN = 10

_SHA40_RE = re.compile(r"[0-9a-f]{40}")
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


def read_conf(text: str, where: str = CONF_PATH) -> dict[str, Any]:
    """The four values Reeve needs from the committed harvester conf (``key: value``, ``#``
    comments; the file's other keys are the harvester's own and are not read). A missing or
    non-integer value raises ``ValueError`` naming ``where`` — never a silent default."""
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
    for key in CONF_KEYS[1:]:
        if not re.fullmatch(r"[0-9]{1,6}", found[key]):
            raise ValueError(f"{where}: {key!r} must be a non-negative integer")
        out[key] = int(found[key])
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
            due = _ts((entry or {}).get("due_at", ""))
            if due is None or t is None:
                continue
            past = (t - (due + timedelta(hours=lag_hours))).total_seconds() / 3600.0
            if past > 0:
                overdue.append((past, kind, key, entry["due_at"]))
    if overdue:
        overdue.sort(key=lambda o: (-o[0], o[1], int(o[2]) if o[2].isdigit() else 0))
        past, kind, key, due_at = overdue[0]
        findings.append({"kind": "overdue", "unit": f"{kind} #{key}", "due_at": due_at,
                         "hours_past": round(past, 1), "count": len(overdue)})
    conf = block.get("conf") or {}
    window = int(conf.get("settle_hours", 0)) + int(conf.get("max_defer_hours", 0)) + int(lag_hours)
    known = ({int(n) for n in block.get("frozen_prs") or []}
             | {int(k) for k in ((state.get("pending") or {}).get("pr") or {})}
             | {int(k) for k in ((state.get("skipped") or {}).get("pr") or {})})
    unseen = []
    for pr in block.get("closed_prs") or []:
        closed = _ts(pr.get("closed_at") or "")
        if closed is None or t is None or pr.get("number") in known:
            continue
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
    return None


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


def _scan_marks(repo: str, token: str, *, now: datetime, horizon_days: int,
                default_branch: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    horizon = now - timedelta(days=horizon_days)
    marks: list[dict[str, Any]] = []
    runs: dict[int, bool] = {}
    counts = {"pages": 0, "runs_verified": 0, "marks_rejected": 0}
    url: Optional[str] = _api(repo, "/actions/artifacts?per_page=100")
    while url:
        counts["pages"] += 1
        if counts["pages"] > MAX_ARTIFACT_PAGES:
            raise RuntimeError(f"more than {MAX_ARTIFACT_PAGES} artifact pages — refusing a "
                               "silently-truncated provenance continuity scan")
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
                runs[run_id] = (run.get("path") == WORKFLOW_PATH
                                and run.get("event") in MARK_EVENTS
                                and run.get("head_branch") == default_branch)
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
    pending / skipped, the frozen PR numbers and one closed-PR page."""
    if not (isinstance(variable, str) and variable.casefold() == "true"):
        return {"armed": False,
                "reason": "PROVENANCE_ENABLED is not 'true' — the harvester's schedule is "
                          "disarmed (arming is phase P2, docs/provenance.md)"}
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
    closed = [{"number": p["number"], "closed_at": p.get("closed_at")}
              for p in page if isinstance(p, dict) and isinstance(p.get("number"), int)]
    return {"armed": True,
            "conf": {"settle_hours": conf["settle_hours"],
                     "max_defer_hours": conf["max_defer_hours"]},
            "tips": tips, "marks": marks, "parents": parents, "scan": counts,
            "state": state, "frozen_prs": frozen, "closed_prs": closed}
