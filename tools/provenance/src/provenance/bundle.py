"""The site bundle and the ``provenance-site`` tree — the one thing the site reads.

``site/bundle.json`` (contract ``bundle@1``)::

    {"format": "bundle@1", "contract": 1, "extractor": "provenance-extract 1",
     "main_sha": <sha40>, "evidence_sha": <sha40>, "producer_run": <run id>,
     "content_sha256": <hex>,
     "views": {"<design>": <view@1>},
     "views_sha256": {"<design>": sha256(canonical(view))}}

* ``content_sha256`` = ``canonical.content_sha256({"records": {path:
  sha256}, "views_sha256": …, "extractor": …})`` — a digest of everything
  EXCEPT the three provenance-of-the-bundle fields (``main_sha``,
  ``evidence_sha``, ``producer_run``). It is for the site's own integrity
  check; the no-op decision never trusts it (critique item 5). ``records``
  maps EVERY ``records/**`` tree path to the hex SHA-256 of that blob's bytes
  (its canonical JSON), so ``contract.validate_tree`` recomputes it from the
  tree alone.
* **No churn** (critique item 6): nothing in a record or a view depends on
  main's sha — the view has no ``main_sha`` (the bundle's meta does), and a
  committed row's line and URL point at the commit that added it — so a main
  push that touches no ``designs/`` file changes no record, no view and no
  ``content_sha256``, and pushes nothing. ``main_sha`` then reads "the main
  commit these views were last recomputed against".
* :func:`same_content` compares the CURRENT derived tip's actual blobs with
  the new tree: the same path set, every path except ``site/bundle.json``
  byte-identical, and ``site/bundle.json`` equal once the three meta fields
  are removed from both — so a forged tip that copies the real
  ``content_sha256`` but alters a view is not "same content". The push
  decision is ``site_changed = not derived_continuity.accepted or not
  same_content(tip, new)`` (a non-checkpointed tip is overwritten even when
  its content matches).
* No cursors, no pending list, no wall clock: the bundle changes only when
  a view or a record changes.

The derived tree (:func:`derived_tree_files`), one parentless commit pushed
with ``--force-with-lease`` (``gitstore.push_force_with_lease``):

==================================  ==========================================
``vercel.json``,                    the guard bytes (``gitstore.guard_blobs``)
``scripts/vercel-ignore-build.sh``
``FORMAT``                          ``print-bench-provenance-site 1\\n``
``records/pr/<n>.json``             record@1 (canonical JSON, not gzipped)
``records/brief/<n>.json``
``records/commit/<sha40>.json``
``records/release/<tag>.json``
``views/<design>.json``             view@1
``site/bundle.json``                bundle@1
==================================  ==========================================

**Fixture parity** — ``tests/test_bundle.py`` rebuilds
``site/test/fixtures/provenance-bundle.json`` IN MEMORY from the committed
SYNTHETIC records under ``tools/provenance/tests/fixtures/records/``
(hand-authored, contract-valid, covering every record kind and every event
field set: ``<kind>/<key>.json`` record@1 files, ``rows/<design>.json`` the
committed-row events of one design, ``designs.json`` the designs "on main"
including a zero-history one; folded with ``views.build_view``) with fixed meta (``main_sha =
521d092813b78a88bd9a74b1052cfef1f230d86b``, ``evidence_sha = "0"*40``,
``producer_run = 1``) and asserts byte equality with the committed file; it
writes the file only when ``PROVENANCE_UPDATE_FIXTURES=1`` is set (a test
never writes into the repo by default — critique item 27). The test needs
``episodes.episodes_of`` (H3) and so carries ``@needs``; the committed file is
regenerated once at integration. The Node validator
(``site/lib/provenance-contract.mjs``) must accept that file and reject a copy
with one extra field, as the Python validator does.

Owner: H5.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from . import canonical, episodes, extract, serving
from . import views as _views
from .contract import CONTRACT_VERSION
from .protocols import CodeBasis, GitReader, TreeReader

BUNDLE_FORMAT = "bundle@1"
DERIVED_FORMAT_BYTES = b"print-bench-provenance-site 1\n"
EVIDENCE_FORMAT_BYTES = b"print-bench-provenance 1\n"
BUNDLE_PATH = "site/bundle.json"
FORMAT_PATH = "FORMAT"
BLOB_MODE = "100644"

#: The guard paths every derived tree carries and their modes — ``gitstore.GUARD_FILES``'s keys
#: and modes, restated so this pure module never imports the git module (pinned equal by
#: tests/test_bundle.py). The BYTES always come from the caller's ``guard`` (main's current
#: ``.github/data-branch-guard/*`` via ``gitstore.guard_blobs``).
GUARD_MODES = {"vercel.json": "100644", "scripts/vercel-ignore-build.sh": "100755"}

_SHA40 = re.compile(r"[0-9a-f]{40}")
_DESIGN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
#: record kind -> the key pattern its ``records/<kind>/<key>.json`` path accepts (contract record@1).
_RECORD_KEYS = {
    "pr": re.compile(r"[1-9][0-9]*"),
    "brief": re.compile(r"[1-9][0-9]*"),
    "commit": _SHA40,
    "release": re.compile(r"[A-Za-z0-9._-]{1,100}"),
}
#: Evidence paths derive reads. ``raw/pr|brief`` carry revisions (``.r<K>``, K >= 2);
#: a release has one revision. ``raw/snapshot/**`` is consumed at freeze, not here.
_RAW_REV_RE = re.compile(r"raw/(pr|brief)/([1-9][0-9]*)(?:\.r([1-9][0-9]*))?\.json\.gz")
_RAW_RELEASE_RE = re.compile(r"raw/release/([A-Za-z0-9._-]{1,100})\.json\.gz")
_RECEIPT_RE = re.compile(r"receipts/[0-9]{4}/[0-9]{2}/[0-9]{2}/([0-9]+)\.a([1-9][0-9]*)\.json\.gz")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def build_bundle(views: dict[str, dict[str, Any]], *, records: dict[str, bytes], main_sha: str,
                 evidence_sha: str, producer_run: int, extractor: str) -> dict[str, Any]:
    """bundle@1 from views and the serialized records (``{tree path: canonical bytes}``)."""
    for name, sha in (("main_sha", main_sha), ("evidence_sha", evidence_sha)):
        if not isinstance(sha, str) or not _SHA40.fullmatch(sha):
            raise ValueError(f"bundle: {name} must be 40-hex, got {sha!r}")
    if not _is_int(producer_run) or producer_run < 1:
        raise ValueError(f"bundle: producer_run must be a positive int, got {producer_run!r}")
    for path in records:
        if not (path.startswith("records/") and path.endswith(".json")):
            raise ValueError(f"bundle: {path!r} is not a records/ path")
    for design, view in views.items():
        if not _DESIGN.fullmatch(design) or view.get("design") != design:
            raise ValueError(f"bundle: view key {design!r} does not name its view")
    views_sha256 = {design: canonical.content_sha256(view) for design, view in sorted(views.items())}
    content = canonical.content_sha256({
        "records": {path: canonical.sha256_hex(data) for path, data in sorted(records.items())},
        "views_sha256": views_sha256,
        "extractor": extractor,
    })
    return {
        "format": BUNDLE_FORMAT,
        "contract": CONTRACT_VERSION,
        "extractor": extractor,
        "main_sha": main_sha,
        "evidence_sha": evidence_sha,
        "producer_run": producer_run,
        "content_sha256": content,
        "views": dict(sorted(views.items())),
        "views_sha256": views_sha256,
    }


#: The bundle fields that describe the bundle rather than its content.
META_FIELDS = ("main_sha", "evidence_sha", "producer_run")


def _strip_meta(raw: Optional[bytes]) -> Optional[dict[str, Any]]:
    """The bundle object minus :data:`META_FIELDS`, or ``None`` when ``raw`` is not a canonical
    bundle whose meta fields are present and well-typed (fail closed: a tip that cannot be read
    as the harvester writes it is never "the same content")."""
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict) or canonical.dumps_bytes(value) != raw:
            return None
    except (UnicodeDecodeError, ValueError, TypeError):
        return None
    if not all(name in value for name in META_FIELDS):
        return None
    for name in ("main_sha", "evidence_sha"):
        if not isinstance(value[name], str) or not _SHA40.fullmatch(value[name]):
            return None
    if not _is_int(value["producer_run"]) or value["producer_run"] < 1:
        return None
    return {k: v for k, v in value.items() if k not in META_FIELDS}


def same_content(tip: Optional[TreeReader], new_files: dict[str, tuple[str, bytes]]) -> bool:
    """True when the current derived tip (``None`` = absent → False) holds exactly ``new_files``
    up to the bundle's :data:`META_FIELDS` (module docstring). Reads the tip's blobs; never its
    ``content_sha256`` field. Modes are compared too.

    The tip's modes come from its reader's ``mode(path)`` (``gitstore.GitTreeReader`` reads them
    from ``ls-tree``); a reader that cannot report a mode cannot prove sameness, so the answer is
    then False (a push, never a missed forgery). The tip's bundle must be byte-canonical and
    carry well-typed meta fields — a duplicated key, a float or a missing ``main_sha`` is
    "different".
    """
    if tip is None:
        return False
    mode_of = getattr(tip, "mode", None)
    if not callable(mode_of):
        return False
    if set(tip.paths("")) != set(new_files):
        return False
    for path, (mode, data) in new_files.items():
        if mode_of(path) != mode:
            return False
        held = tip.read(path)
        if held is None:
            return False
        if path == BUNDLE_PATH:
            ours, theirs = _strip_meta(data), _strip_meta(held)
            if ours is None or theirs is None or ours != theirs:
                return False
        elif held != data:
            return False
    return True


def record_path(record: dict[str, Any]) -> str:
    """``records/<kind>/<key>.json`` for one record@1."""
    kind, key = record.get("kind"), record.get("key")
    pattern = _RECORD_KEYS.get(kind)
    if pattern is None:
        raise ValueError(f"bundle: unknown record kind {kind!r}")
    if not isinstance(key, str) or not pattern.fullmatch(key) or key in (".", ".."):
        raise ValueError(f"bundle: invalid {kind} record key {key!r}")
    return f"records/{kind}/{key}.json"


def derived_tree_files(records: list[dict[str, Any]], views: dict[str, dict[str, Any]],
                       bundle: dict[str, Any],
                       guard: dict[str, tuple[str, bytes]]) -> dict[str, tuple[str, bytes]]:
    """``{path: (mode, bytes)}`` for the whole provenance-site tree (table above)."""
    if set(guard) != set(GUARD_MODES):
        raise ValueError(f"bundle: guard paths {sorted(guard)} != {sorted(GUARD_MODES)}")
    files: dict[str, tuple[str, bytes]] = {}
    for path, (mode, data) in guard.items():
        if mode != GUARD_MODES[path]:
            raise ValueError(f"bundle: guard {path} mode {mode} != {GUARD_MODES[path]}")
        files[path] = (mode, bytes(data))
    files[FORMAT_PATH] = (BLOB_MODE, DERIVED_FORMAT_BYTES)
    for record in records:
        path = record_path(record)
        if path in files:
            raise ValueError(f"bundle: two records map to {path}")
        files[path] = (BLOB_MODE, canonical.dumps_bytes(record))
    for design, view in views.items():
        if not _DESIGN.fullmatch(design) or view.get("design") != design:
            raise ValueError(f"bundle: view key {design!r} does not name its view")
        files[f"views/{design}.json"] = (BLOB_MODE, canonical.dumps_bytes(view))
    files[BUNDLE_PATH] = (BLOB_MODE, canonical.dumps_bytes(bundle))
    return dict(sorted(files.items()))


@dataclass
class DerivedTree:
    """The result of :func:`derive`: the tree's files, the bundle, and summary counts."""

    files: dict[str, tuple[str, bytes]] = field(default_factory=dict)
    bundle: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def _load(evidence: TreeReader, path: str) -> Any:
    data = evidence.read(path)
    if data is None:
        raise ValueError(f"derive: {path} listed but unreadable")
    return canonical.loads_gz(data)


def read_evidence(evidence: TreeReader) -> tuple[dict[str, list[Any]], list[dict[str, Any]]]:
    """Step 1: ``({"pr": [raw…], "brief": […], "release": […]}, [receipt…])`` — the highest
    revision per raw key (numeric key / tag order) and the highest attempt per run (run-id
    order). ``raw/snapshot/**`` is skipped (consumed at freeze); any other ``raw/`` or
    ``receipts/`` path that is not in the layout raises (a corrupt evidence tree is never
    derived around silently)."""
    best: dict[tuple[str, str], tuple[int, str]] = {}
    for path in evidence.paths("raw/"):
        if path.startswith("raw/snapshot/"):
            continue
        m = _RAW_REV_RE.fullmatch(path)
        if m:
            key, rev = (m.group(1), m.group(2)), int(m.group(3) or 1)
            if m.group(3) is not None and rev < 2:
                raise ValueError(f"derive: revision 1 is the bare path, not {path}")
        else:
            m = _RAW_RELEASE_RE.fullmatch(path)
            if not m:
                raise ValueError(f"derive: {path} is not an evidence raw/ path")
            key, rev = ("release", m.group(1)), 1
        if key not in best or rev > best[key][0]:
            best[key] = (rev, path)
    raw: dict[str, list[Any]] = {"pr": [], "brief": [], "release": []}
    order = sorted(best, key=lambda k: (k[0], int(k[1]) if k[0] != "release" else 0, k[1]))
    for key in order:
        raw[key[0]].append(_load(evidence, best[key][1]))

    attempts: dict[int, tuple[int, str]] = {}
    for path in evidence.paths("receipts/"):
        m = _RECEIPT_RE.fullmatch(path)
        if not m:
            raise ValueError(f"derive: {path} is not an evidence receipts/ path")
        run, attempt = int(m.group(1)), int(m.group(2))
        if run not in attempts or attempt > attempts[run][0]:
            attempts[run] = (attempt, path)
    receipts = [_load(evidence, attempts[run][1]) for run in sorted(attempts)]
    return raw, receipts


def _merged(raw_pr: dict[str, Any]) -> bool:
    return bool(raw_pr["pull"].get("merged")) or raw_pr["pull"].get("merged_at") is not None


def derive(evidence: TreeReader, *, git: GitReader, codebasis: CodeBasis, main_sha: str,
           owner: str, repo: str, owner_login: str, evidence_sha: str, producer_run: int,
           edit_grace_seconds: int, guard: dict[str, tuple[str, bytes]]) -> DerivedTree:
    """The whole derivation, evidence tree → provenance-site tree (pure given its readers).

    ``evidence`` is the evidence commit the bundle will name — this run's new
    commit, the unchanged tip, or the newest checkpoint when the tip is foreign
    (cli step 2). The order is fixed (critique item 14):

    1. read every ``raw/**`` (highest revision per key) and ``receipts/**``
       (highest attempt per run);
    2. ``extract.extract_pr`` / ``extract_brief`` / ``extract_release`` per raw
       doc (``ExtractContext.brief_numbers`` from the ``raw/brief/`` paths),
       ``extract.extract_direct_commits`` from main;
    3. ``serving.ReceiptIndex(receipts)``; ``claims = serving.run_claims(brief
       records, …)``; ``serving.annotate_record(…, claims=claims)`` per record;
       ``serving.receipt_events`` appended to each PR record (unplaced);
    4. ``episodes.place`` per record — after this every event has an episode;
    5. ``views.build_views`` (rows via ``episodes.decision_rows``, rounds via
       ``episodes.rounds_from_record``);
    6. :func:`build_bundle` and :func:`derived_tree_files`.

    No fetch happens here: ``git`` reads only what the job-start fetch made
    local (a missing commit is basis ``none``). The orchestrator compares the
    result with the current derived tip via :func:`same_content`.

    The context every extractor sees is built from the raw documents alone
    (never from another extractor's output): ``merge_shas`` = ``{pull.
    merge_commit_sha: pr}`` of the MERGED raw PRs, ``brief_numbers`` = the
    ``raw/brief/`` keys, ``design_names`` = ``views.design_names`` at main;
    the direct-commit rule's frozen PR commits and the rows' ``commit_to_pr``
    come from the raw PRs' ``commits`` (a commit in several PRs maps to the
    lowest-numbered MERGED one, else the lowest-numbered). Each phase runs
    over every record before the next starts. A record that still carries an
    unplaced event after step 4 raises ``ValueError`` — nothing unplaced is
    ever stored.
    """
    raw, receipts = read_evidence(evidence)
    raw_prs, raw_briefs, raw_releases = raw["pr"], raw["brief"], raw["release"]

    merge_shas = {doc["pull"]["merge_commit_sha"]: doc["pr"] for doc in raw_prs
                  if _merged(doc) and doc["pull"].get("merge_commit_sha")}
    ctx = extract.ExtractContext(
        owner=owner, repo=repo, owner_login=owner_login, git=git, main_sha=main_sha,
        design_names=frozenset(_views.design_names(git, main_sha)), merge_shas=merge_shas,
        brief_numbers=frozenset(doc["number"] for doc in raw_briefs),
        edit_grace_seconds=edit_grace_seconds)
    commit_to_pr: dict[str, int] = {}
    for doc in sorted(raw_prs, key=lambda d: (not _merged(d), d["pr"])):
        for commit in doc.get("commits", []):
            commit_to_pr.setdefault(commit["sha"], doc["pr"])

    # 2. extraction (raw document → record, events placed from the document itself)
    pr_records = [extract.extract_pr(doc, ctx) for doc in raw_prs]
    brief_records = [extract.extract_brief(doc, ctx) for doc in raw_briefs]
    release_records = [extract.extract_release(doc, ctx) for doc in raw_releases]
    commit_records = extract.extract_direct_commits(ctx, set(commit_to_pr))

    # 3. the serving join, then the receipt events (unplaced)
    index = serving.ReceiptIndex(receipts)
    claims = serving.run_claims(brief_records, index, owner_login=owner_login)
    records = [serving.annotate_record(r, index, codebasis, owner_login=owner_login, claims=claims)
               for r in pr_records + brief_records + release_records + commit_records]
    joined = []
    for record in records:
        if record["kind"] == "pr":
            extra = serving.receipt_events(record, index, codebasis, owner=owner, repo=repo)
            record = dict(record, events=list(record["events"]) + list(extra))
        joined.append(record)

    # 4. placement — every stored event has an episode
    placed = sorted((episodes.place(r) for r in joined), key=record_path)
    for record in placed:
        unplaced = [e.get("id") for e in record["events"] if e.get("episode") is None]
        if unplaced:
            raise ValueError(f"derive: {record_path(record)} has unplaced events {unplaced[:5]}")

    # 5–6. views, bundle, tree
    views = _views.build_views(placed, git=git, main_sha=main_sha, owner=owner, repo=repo,
                               commit_to_pr=commit_to_pr)
    record_bytes = {record_path(r): canonical.dumps_bytes(r) for r in placed}
    bundle = build_bundle(views, records=record_bytes, main_sha=main_sha, evidence_sha=evidence_sha,
                          producer_run=producer_run, extractor=extract.EXTRACTOR_VERSION)
    files = derived_tree_files(placed, views, bundle, guard)
    counts = {
        "records": len(placed),
        "pr": sum(1 for r in placed if r["kind"] == "pr"),
        "brief": sum(1 for r in placed if r["kind"] == "brief"),
        "commit": sum(1 for r in placed if r["kind"] == "commit"),
        "release": sum(1 for r in placed if r["kind"] == "release"),
        "events": sum(len(r["events"]) for r in placed),
        "receipts": len(receipts),
        "views": len(views),
        "files": len(files),
    }
    return DerivedTree(files=files, bundle=bundle, records=placed, counts=counts)
