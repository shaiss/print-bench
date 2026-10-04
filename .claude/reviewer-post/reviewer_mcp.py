#!/usr/bin/env python3
"""reviewer_mcp.py — the Jane/Drik reviewers' and PM triage's shared posting surface, stdio MCP.

WHY THIS SERVER EXISTS (issues #764, #772)
------------------------------------------
The auto-review reviewer agents (Jane, Drik) ran for their whole history under
`--permission-mode dontAsk --settings .claude/reviewer-settings.json` with NO
surface that could carry their review: Write/Edit/NotebookEdit are denied
(read-only reviewers), every file-creating Bash form (echo >, heredoc, tee) is
denied, and — the killer — a multi-line `--body` argument is denied by the
dontAsk matcher no matter how it is quoted (the recorded scout/oracle proof:
a table pipe or an embedded newline is enough; see oracle_mcp.py's header). A
review is inherently multi-line markdown, so every post attempt was denied,
the agent ended its turn after 2-5 denials, claude-code-action exited 0 (the
#538 pattern) and NOTHING landed — every JANE/DRIK_SIGNOFF marker ever posted
was authored by the owner's attended local runs, never by the workflow. This
server is the fix: the reviewers' ONE write, as a JSON-argument MCP tool
(the scout/oracle pattern), with the sign-off marker ASSEMBLED HERE from typed
fields so a malformed or forged marker cannot be posted at all.

Issue #772 extended the same server to the `pm-triage` job, which had the
identical disease under the identical posture (its rulings are multi-line
markdown tables) with one twist: it posts ONE verdict comment PER DESIGN, not
one review per run, so its bound is the design set — read from the trusted
`REVIEWER_PM_DESIGNS` env the workflow sets from its own changed-designs
output, never from an argument, making the exact guarantee "one triage
comment per workflow-named design, on the one workflow-selected PR".

SECURITY (this is the write surface of agents that read untrusted PR text)
--------------------------------------------------------------------------
The reviewer sessions read the PR's diff, its thread and the staged design
files — untrusted text — while holding a GitHub token, so this server does NOT
trust its inputs and cannot be steered beyond "post one signed-off review
comment on the ONE PR the workflow selected":

  * the target PR comes ONLY from the REVIEWER_PR environment variable, set by
    the trusted workflow — there is no argument for it, so a prompt-injected
    run can never redirect the comment to another issue or PR;
  * the reviewer IDENTITY comes ONLY from REVIEWER_ID (jane|drik|pm), likewise
    set by the trusted workflow step — never an argument. The marker prefix
    (JANE_SIGNOFF vs DRIK_SIGNOFF vs PM_TRIAGE) is derived from it
    server-side, and each tool accepts only its own identities (post_review
    refuses pm; post_triage refuses jane/drik), so a Jane session cannot
    forge Drik's sign-off, a PM session cannot forge EITHER reviewer's
    sign-off, and no input can post an unrecognised marker family;
  * the sign-off marker is ASSEMBLED from validated fields (40-hex sha,
    pass|block verdict, none|acknowledged fuse) — the fail-closed
    reviewer-signoff gate's "malformed marker" failure mode is unreachable
    from this path; the triage marker likewise from a validated 40-hex sha
    and a design name drawn from the trusted REVIEWER_PM_DESIGNS list;
  * a caller body that contains ``<!-- JANE_SIGNOFF`` / ``<!-- DRIK_SIGNOFF``
    / ``<!-- PM_TRIAGE`` (case-insensitive) is refused, not posted:
    ``get_marker()`` greps every comment with no author check, so a body
    carrying another family's marker would otherwise satisfy that family's
    gate from one post — a PM body carrying a JANE pass is the sharpest case
    (the PM is a third poster on the same thread). Only the server-assembled
    marker from validated fields + trusted REVIEWER_ID may appear;
  * the attribution footer is HARDCODED here — every post is disclosed as a
    Claude Code review whatever the body says;
  * a per-run cap (counted in a state file every chain link of the walk
    shares, REVIEWER_POST_STATE — the ORACLE_CAP_STATE pattern) bounds a
    hijacked run: ONE review post for jane/drik, ONE triage post per
    workflow-named design for pm;
  * a size cap bounds the body, so the tool cannot dump a repository into a
    PR thread;
  * the only GitHub call is `POST /issues/{REVIEWER_PR}/comments` on the
    CURRENT repo — no labels, no reviews/approves, no other repo, no pushes.

Each reviewer job's ship steps run with `--allowedTools
"mcp__reviewer__post_review,Read,Grep,Glob"` (Jane/Drik) or
`"mcp__reviewer__post_triage,Read,Grep,Glob"` (PM triage) on top of the deny
backstop, so the tool is the only added write; gh/jq/mktemp stay allowed for
reads (the backstop keeps denying everything else). Stdlib only; logs go to
stderr so stdout carries nothing but JSON-RPC.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

GITHUB_API = "https://api.github.com"
SERVER_NAME = "reviewer"
# The comment families this server may emit, keyed by the trusted
# REVIEWER_ID env value. Anything else is refused — a new poster joins by
# adding an entry here (and a per-tool identity set below), not by passing a
# new string at call time.
REVIEWERS = {"jane": "JANE_SIGNOFF", "drik": "DRIK_SIGNOFF", "pm": "PM_TRIAGE"}
# Each tool accepts only its own identities: a mis-wired step (or a hijacked
# session of one agent) must fail loudly at the family check, not post the
# other surface's comment. post_review is the sign-off surface (Jane/Drik);
# post_triage is the PM verdict surface (issue #772).
SIGNOFF_IDS = ("jane", "drik")
TRIAGE_IDS = ("pm",)
# The designs pm-triage may rule on — trusted workflow input, read from the
# env the pm-triage steps set from their own changed-designs output, never a
# tool argument. This is what bounds a triage run: one comment per
# workflow-named design, so a hijacked session cannot invent design names to
# multiply posts (the bound jane/drik get from MAX_POSTS_PER_RUN).
PM_DESIGNS_ENV = "REVIEWER_PM_DESIGNS"
FOOTER = "---\n_Generated by [Claude Code](https://claude.ai/code)_"
# One review comment is ~2-6 KB; 64 KiB is generous headroom for a long
# findings list while still refusing a repository dump (GitHub's own comment
# limit is 65536 characters).
MAX_BODY_BYTES = 64 * 1024
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
# A design name as the workflow itself validates them (auto-review.yml's
# staging step uses the same shape): one leading [A-Za-z0-9], then that plus
# `._-`, bounded so a design argument can never smuggle markup.
DESIGN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# One review per run. Deliberately not an env knob — "one signed-off review
# per reviewer per round" is the reviewer contract, not a tunable. The PM's
# counterpart is one triage per design (the designs themselves come from
# PM_DESIGNS_ENV), not a count.
MAX_POSTS_PER_RUN = 1

# The walk-spanning post cap (the #549 class, ORACLE_CAP_STATE's sibling).
# auto-review.yml walks its chain one claude-code-action step per link and each
# step launches this server as a FRESH process, so the count must live where
# every link can see it: a state file the workflow names via
# REVIEWER_POST_STATE, one path shared by every link step of the job. The
# cap-state wiring drift guard (tools/model-registry/tests/
# test_cap_state_wiring.py) reads CAP_STATE_ENV from this file and fails
# pre-merge if a link step that launches this server does not set it.
CAP_STATE_ENV = "REVIEWER_POST_STATE"


def _cap_state_path():
    """The shared state-file path for this run, or None attended.

    Attended (no GITHUB_RUN_ID) the cap is skipped entirely — a human is the
    trust boundary — so no state file is required. Unattended the path comes
    from the env var the workflow sets; an empty value is returned as-is so the
    caller can refuse: posting on without it would silently fall back to
    per-process counting, which is exactly the per-link reset this mechanism
    exists to kill.
    """
    if not os.environ.get("GITHUB_RUN_ID", "").strip():
        return None
    return os.environ.get(CAP_STATE_ENV, "").strip()


def _cap_state_count(path):
    """How many reviews this run has already posted, per the shared state file.

    One JSON record per successful post, so the count is the number of
    non-empty lines; an absent file is a run that has posted nothing yet (the
    first successful post creates it). The ``.posted`` sidecar also counts as
    one, so a post whose JSONL append failed still saturates the cap. Any
    other read failure raises — an unreadable state must refuse, never count
    as zero.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            n = sum(1 for line in fh if line.strip())
    except FileNotFoundError:
        n = 0
    except OSError as e:
        raise RuntimeError(f"cannot read {CAP_STATE_ENV} file {path}: {e}") from e
    if os.path.exists(path + ".posted"):
        n = max(n, 1)
    return n


def _cap_state_record(path, pr, url, design=None):
    """Append ONE record — only ever AFTER a successful post, so refused and
    failed attempts never consume the cap (the greenlight wrapper's rule). The
    record doubles as the audit trail of what a link that later died posted.
    A triage record also names its design: the per-design dedup reads it back
    across the chain walk's fresh processes."""
    rec = {"pr": pr, "url": url,
           "posted_at": datetime.now(timezone.utc).isoformat()}
    if design is not None:
        rec["design"] = design
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def _cap_state_designs(path):
    """The designs a triage run has already ruled on, per the shared state
    file — the per-design sibling of ``_cap_state_count``. Every record this
    server writes in a pm-triage run carries a design, so an unparseable line
    or a designless record means the file no longer proves what was posted:
    refuse (raise) rather than under-count. The ``.posted`` sidecar holds the
    design of the LAST successful post (``"1"`` for review posts), because it
    is the one record that survives a failed JSONL append — its design must
    still count as posted."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = [ln for ln in fh if ln.strip()]
    except FileNotFoundError:
        lines = []
    except OSError as e:
        raise RuntimeError(f"cannot read {CAP_STATE_ENV} file {path}: {e}") from e
    designs = set()
    for ln in lines:
        try:
            rec = json.loads(ln)
        except ValueError as e:
            raise RuntimeError(
                f"cannot parse {CAP_STATE_ENV} file {path}: {e}") from e
        d = rec.get("design")
        if not (isinstance(d, str) and d):
            raise RuntimeError(
                f"{CAP_STATE_ENV} file {path} holds a record with no design — "
                "it cannot prove which designs this run already triaged; "
                "refusing rather than risk a duplicate verdict")
        designs.add(d)
    try:
        with open(path + ".posted", encoding="utf-8") as fh:
            sidecar = fh.read().strip()
    except FileNotFoundError:
        sidecar = ""
    except OSError as e:
        raise RuntimeError(
            f"cannot read {CAP_STATE_ENV} posted-flag {path}.posted: {e}") from e
    if sidecar and sidecar != "1":
        # A post whose JSONL append failed left only the sidecar — its design
        # is as posted as any recorded one.
        designs.add(sidecar)
    return designs


def _cap_state_ensure_appendable(path):
    """Fail-closed preflight: the state path must be appendable BEFORE a
    GitHub write. Create the file if absent (zero posted so far); refuse if
    the path is readable-but-not-appendable or its directory is missing —
    otherwise a successful post that can't be recorded lets a later link post
    a second review."""
    try:
        with open(path, "a", encoding="utf-8"):
            pass
    except OSError as e:
        raise RuntimeError(
            f"cannot append to {CAP_STATE_ENV} file {path}: {e}"
        ) from e


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"reviewer_mcp: {msg}", file=sys.stderr, flush=True)


def _repo():
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    return repo


def _pr_number():
    """The one PR this run may post to — trusted workflow input, never an
    argument the model controls."""
    raw = os.environ.get("REVIEWER_PR", "").strip()
    if not raw.isdigit():
        raise RuntimeError(
            "REVIEWER_PR is not set to a PR number — the workflow must export it")
    return int(raw)


def _reviewer(ids=None):
    """The reviewing identity — trusted workflow input, never an argument.

    Determines the comment family the post may carry; a Jane session can
    never emit a DRIK_SIGNOFF marker (and vice versa) because the prefix is
    derived here, from the env the step set, not from anything the model
    writes. ``ids`` narrows the registry to one tool's identities — a
    post_review step set up as pm (or a post_triage step as jane) is a wiring
    defect this refuses loudly, before any comment exists to walk back."""
    who = os.environ.get("REVIEWER_ID", "").strip().lower()
    allowed = tuple(REVIEWERS) if ids is None else ids
    marker = REVIEWERS.get(who)
    if marker is None or who not in allowed:
        raise RuntimeError(
            "REVIEWER_ID is not one of " + "/".join(sorted(allowed))
            + " — the workflow must export it (it selects the comment family;"
            + " it is deliberately not a tool argument)")
    return who, marker


def _token():
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        tok = os.environ.get(var, "").strip()
        if tok:
            return tok
    raise RuntimeError("no GitHub token (set GITHUB_TOKEN)")


def _api(method, path, payload=None):
    """One authenticated GitHub REST call. Returns the decoded JSON body."""
    url = f"{GITHUB_API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "print-bench-reviewer-post")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


# Captured by the selftest so it can assert the exact POST payload (marker,
# footer, target) without a network call. `None` in normal operation.
_last_payload = None
_last_path = None


# Reserved HTML-comment syntax the sign-off status (and, for PM_TRIAGE, the
# triage readers) grep for. A caller body that already contains any family's
# marker is refused — REVIEWER_ID only chooses which marker *we* append, and
# get_marker() has no author check, so a body carrying another family's
# marker would satisfy that family's gate from this one post. The PM is the
# sharpest case: it is a third poster on the same thread as both sign-offs.
_MARKER_IN_BODY = re.compile(
    r"<!--\s*(?:(?:JANE|DRIK)_SIGNOFF|PM_TRIAGE)\b",
    re.IGNORECASE,
)


def _marker_line(marker, sha, verdict, fuse):
    """The sign-off marker, assembled from validated fields — byte-identical
    to the shape scripts/reviewer-signoff.sh parses:
    <!-- <FAMILY>_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
    """
    return f"<!-- {marker} sha={sha} verdict={verdict} fuse={fuse} -->"


def _triage_marker_line(design, sha):
    """The PM triage marker, assembled from validated fields — byte-identical
    to the shape the /pm skill's §8 verdict comment specifies:
    <!-- PM_TRIAGE design=<name> sha=<40hex> -->
    """
    return f"<!-- PM_TRIAGE design={design} sha={sha} -->"


def _post_triage_comment(body, design, sha):
    """POST one PM verdict comment to the workflow-selected PR. Same assembly
    rule as a review: the marker and footer come from constants and validated
    fields, never caller input. REVIEWER_MCP_FAKE short-circuits the network
    for the selftest (it is never set in the workflow)."""
    global _last_payload, _last_path
    full = (f"{body.rstrip()}\n\n"
            f"{_triage_marker_line(design, sha)}\n\n"
            f"{FOOTER}")
    payload = {"body": full}
    path = f"/repos/{_repo()}/issues/{_pr_number()}/comments"
    _last_payload = payload
    _last_path = path
    if os.environ.get("REVIEWER_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake"}
    return _api("POST", path, payload)


def _post_comment(body, sha, verdict, fuse):
    """POST one review comment to the workflow-selected PR. The marker and
    footer are assembled HERE, from constants and validated fields, never from
    caller input — so every post is a disclosed, correctly-signed reviewer
    comment whatever the body says. REVIEWER_MCP_FAKE short-circuits the
    network for the selftest (it is never set in the workflow)."""
    global _last_payload, _last_path
    _, marker = _reviewer()
    full = (f"{body.rstrip()}\n\n"
            f"{_marker_line(marker, sha, verdict, fuse)}\n\n"
            f"{FOOTER}")
    payload = {"body": full}
    path = f"/repos/{_repo()}/issues/{_pr_number()}/comments"
    _last_payload = payload
    _last_path = path
    if os.environ.get("REVIEWER_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake"}
    return _api("POST", path, payload)


_SHA_CHARS = set("0123456789abcdef")


def _cap_state_commit(path, pr, url, design=None):
    """Record one successful post so later links of the walk see it: append
    its JSONL record, then write the sidecar — which CARRIES THE DESIGN for a
    triage post, because the sidecar is the one record that survives a failed
    append and an unrecorded design must still count as posted. Returns True
    if either landed; the sidecar alone counts, exactly as for the review
    cap (``_cap_state_count`` reads it back)."""
    recorded = False
    try:
        _cap_state_record(path, pr, url, design=design)
        recorded = True
    except OSError as e:
        log(f"WARNING: posted {url} but could not append its "
            f"{CAP_STATE_ENV} JSONL record ({e})")
    try:
        with open(path + ".posted", "w", encoding="utf-8") as fh:
            fh.write((design or "1") + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        recorded = True
    except OSError as e:
        log(f"WARNING: posted {url} but could not write the "
            f"{CAP_STATE_ENV} posted-flag ({e})")
    return recorded


def _post_review(arguments):
    """Post ONE signed-off review comment. The reviewer agents' entire write
    taxonomy."""
    args = arguments or {}
    body = args.get("body")
    sha = args.get("sha")
    verdict = args.get("verdict")
    fuse = args.get("fuse")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("post_review: 'body' is required (non-empty string)")
    if len(body.encode()) > MAX_BODY_BYTES:
        return _tool_error(
            f"post_review: body is {len(body.encode())} bytes, over the "
            f"{MAX_BODY_BYTES}-byte cap — a review is a verdict with findings, "
            f"not a data dump; condense it")
    if _MARKER_IN_BODY.search(body):
        return _tool_error(
            "post_review: body must not contain a JANE_SIGNOFF, DRIK_SIGNOFF "
            "or PM_TRIAGE HTML comment — the marker is assembled server-side "
            "from sha/verdict/fuse and REVIEWER_ID; a caller-supplied marker "
            "is refused so one post cannot satisfy another poster's gate")
    # sha/verdict/fuse are validated here so the marker the gate parses can
    # never be malformed from this path (a malformed marker blocks the merge
    # fail-closed — better to refuse the post than to ship a blocker).
    if not isinstance(sha, str) or len(sha) != 40 \
            or not set(sha.lower()) <= _SHA_CHARS:
        return _tool_error(
            "post_review: 'sha' must be the PR's current head commit as 40 "
            "lower-case hex characters (read it from `gh pr view`); got "
            f"{sha!r}")
    if verdict not in ("pass", "block"):
        return _tool_error(
            "post_review: 'verdict' must be \"pass\" (default — findings are "
            "feedback the PM triages) or \"block\" (a genuine defect you "
            f"would stake the sign-off on); got {verdict!r}")
    if fuse not in ("none", "acknowledged"):
        return _tool_error(
            "post_review: 'fuse' must be \"none\", or \"acknowledged\" when "
            "the printcheck sticky shows a fusecheck STRONG WARN you address "
            f"in a finding; got {fuse!r}")

    # Identity and target are read (and validated) before anything else can
    # run, so a mis-wired step fails loudly rather than posting as the wrong
    # reviewer or to the wrong PR. Sign-off identities only: a pm step wired
    # to post_review is a wiring defect, and pm's verdicts have their own
    # tool (post_triage, issue #772).
    try:
        _reviewer(SIGNOFF_IDS)
        _pr_number()
        _repo()
    except RuntimeError as e:
        return _tool_error(f"post_review: {e}")

    # Per-run cap — enforced only inside an Actions run (the unattended case
    # it exists to bound); attended, a human is the trust boundary. The count
    # is read from the shared state file so it spans the whole chain walk,
    # not this one server process.
    state = _cap_state_path()
    if state is not None:
        if not state:
            return _tool_error(
                f"post_review: {CAP_STATE_ENV} is not set but this is an "
                "unattended run (GITHUB_RUN_ID is set) — the workflow must "
                "give every link step the same state-file path or the "
                "one-review cap cannot span the chain walk; refusing to post")
        try:
            posted = _cap_state_count(state)
        except RuntimeError as e:
            return _tool_error(f"post_review: {e}")
        if posted >= MAX_POSTS_PER_RUN:
            return _tool_error(
                "this reviewer posts exactly ONE review per run and it is "
                f"already posted ({posted} recorded across the chain walk so "
                "far); refusing a second comment")
        try:
            _cap_state_ensure_appendable(state)
        except RuntimeError as e:
            return _tool_error(f"post_review: {e}")

    try:
        comment = _post_comment(body, sha, verdict, fuse)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} posting review: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to post review: {type(e).__name__}: {e}")

    url = comment.get("html_url", "(unknown url)")
    if state:
        if not _cap_state_commit(state, _pr_number(), url):
            return _tool_error(
                f"posted {url} but could not record the walk cap — refusing "
                "so a later link does not treat this run as unposted")
    log(f"posted {_reviewer(SIGNOFF_IDS)[0]} review: {url}")
    return _tool_text(f"POSTED {url}")


def _triage_designs():
    """The designs this run may rule on — trusted workflow input, or None
    attended (a human is the trust boundary, the cap's own attended rule)."""
    if not os.environ.get("GITHUB_RUN_ID", "").strip():
        return None
    raw = os.environ.get(PM_DESIGNS_ENV, "").strip()
    if not raw:
        raise RuntimeError(
            f"{PM_DESIGNS_ENV} is not set but this is an unattended run — "
            "the workflow must give every pm-triage link step the designs it "
            "may rule on (its own changed-designs output), or the one-triage-"
            "per-design bound cannot hold; refusing to post")
    return set(raw.split())


def _post_triage(arguments):
    """Post ONE PM triage verdict comment for ONE design. The PM gate's
    entire write taxonomy (issue #772 — the pm-triage job's rulings never
    landed before this: multi-line markdown cannot pass the dontAsk matcher
    as a gh --body argument, and the job exits 0 anyway, the #538 pattern)."""
    args = arguments or {}
    body = args.get("body")
    design = args.get("design")
    sha = args.get("sha")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("post_triage: 'body' is required (non-empty string)")
    if len(body.encode()) > MAX_BODY_BYTES:
        return _tool_error(
            f"post_triage: body is {len(body.encode())} bytes, over the "
            f"{MAX_BODY_BYTES}-byte cap — a triage is a verdict table per "
            "finding, not a data dump; condense it")
    if _MARKER_IN_BODY.search(body):
        return _tool_error(
            "post_triage: body must not contain a PM_TRIAGE, JANE_SIGNOFF or "
            "DRIK_SIGNOFF HTML comment — the marker is assembled server-side "
            "from design/sha and REVIEWER_ID; a caller-supplied marker is "
            "refused so a triage post can never satisfy a reviewer's "
            "sign-off gate or forge a second triage marker")
    if not isinstance(design, str) or not DESIGN_NAME_RE.match(design):
        return _tool_error(
            "post_triage: 'design' must be the design name this verdict "
            "rules on — one leading letter/digit, then letters/digits/._- , "
            f"max 64 chars; got {design!r}")
    if not isinstance(sha, str) or len(sha) != 40 \
            or not set(sha.lower()) <= _SHA_CHARS:
        return _tool_error(
            "post_triage: 'sha' must be the PR's current head commit as 40 "
            "lower-case hex characters (read it from `gh pr view`); got "
            f"{sha!r}")

    # Identity and target are read (and validated) before anything else can
    # run, so a mis-wired step fails loudly rather than posting as the wrong
    # poster or to the wrong PR. The triage identities are pm's alone — a
    # jane/drik step wired to post_triage is a wiring defect.
    try:
        _reviewer(TRIAGE_IDS)
        _pr_number()
        _repo()
    except RuntimeError as e:
        return _tool_error(f"post_triage: {e}")

    # The design set — trusted workflow input, checked before the cap reads
    # so an unwired step fails before any state is touched. Unattended it is
    # required (fail closed, the CAP_STATE_ENV rule); attended there is no
    # list to check (a human is the trust boundary).
    try:
        allowed = _triage_designs()
    except RuntimeError as e:
        return _tool_error(f"post_triage: {e}")
    if allowed is not None and design not in allowed:
        return _tool_error(
            f"post_triage: design {design!r} is not one this run may rule on "
            f"({PM_DESIGNS_ENV} names {sorted(allowed)}) — the workflow hands "
            "the triage its design set, so an off-list verdict is a mistake "
            "or an injection, never a real design")

    # Per-run cap: one verdict per design, counted across the whole chain
    # walk from the shared state file (each link is a fresh process).
    state = _cap_state_path()
    if state is not None:
        if not state:
            return _tool_error(
                f"post_triage: {CAP_STATE_ENV} is not set but this is an "
                "unattended run (GITHUB_RUN_ID is set) — the workflow must "
                "give every link step the same state-file path or the "
                "one-triage-per-design cap cannot span the chain walk; "
                "refusing to post")
        try:
            posted = _cap_state_designs(state)
        except RuntimeError as e:
            return _tool_error(f"post_triage: {e}")
        if design in posted:
            return _tool_error(
                f"this run posts exactly ONE verdict per design and {design}'s"
                f" is already posted ({len(posted)} design(s) ruled on across "
                "the chain walk so far); refusing a duplicate")
        try:
            _cap_state_ensure_appendable(state)
        except RuntimeError as e:
            return _tool_error(f"post_triage: {e}")

    try:
        comment = _post_triage_comment(body, design, sha)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} posting triage: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to post triage: {type(e).__name__}: {e}")

    url = comment.get("html_url", "(unknown url)")
    if state:
        if not _cap_state_commit(state, _pr_number(), url, design=design):
            return _tool_error(
                f"posted {url} but could not record the walk cap — refusing "
                "so a later link does not treat this run as unposted")
    log(f"posted pm triage for {design}: {url}")
    return _tool_text(f"POSTED {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "post_review",
        "description": (
            "Post your ONE review comment on the PR this run was launched "
            "for (the workflow fixes the PR number and your reviewer "
            "identity — neither is an argument). This is your ONLY write: "
            "posting any other way (gh pr comment, gh pr review, writing "
            "files) is denied by the permission backstop and will silently "
            "fail. The body is a JSON argument, so it may be full "
            "multi-line markdown with tables, pipes and backticks. Your "
            "sign-off marker and the attribution footer are added "
            "automatically from the sha/verdict/fuse fields — never type the "
            "marker yourself. One post per run; a second call is refused."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": (
                        "The review body in markdown: the TL;DR verdict "
                        "first, then every finding. Multi-line markdown, "
                        "tables and code spans are all fine here."
                    ),
                },
                "sha": {
                    "type": "string",
                    "description": (
                        "The PR's current head commit, 40 lower-case hex "
                        "characters — read it from `gh pr view <n>` first. "
                        "A marker for a superseded head is treated as stale "
                        "by the merge gate."
                    ),
                },
                "verdict": {
                    "type": "string",
                    "enum": ["pass", "block"],
                    "description": (
                        "\"pass\" is the default — findings are feedback the "
                        "PM triages. \"block\" only for a genuine defect you "
                        "would stake the sign-off on."
                    ),
                },
                "fuse": {
                    "type": "string",
                    "enum": ["none", "acknowledged"],
                    "description": (
                        "\"none\", or \"acknowledged\" when the printcheck "
                        "sticky shows a fusecheck STRONG WARN (and your body "
                        "addresses it in a finding)."
                    ),
                },
            },
            "required": ["body", "sha", "verdict", "fuse"],
            "additionalProperties": False,
        },
    },
    {
        "name": "post_triage",
        "description": (
            "Post your PM triage verdict comment for ONE design on the PR "
            "this run was launched for (the workflow fixes the PR number, "
            "your identity and the design set — none are arguments). This is "
            "your ONLY write: posting any other way (gh pr comment, gh pr "
            "review, writing files) is denied by the permission backstop "
            "and will silently fail. Call it once per design you were handed, "
            "with that design's verdict body. The body is a JSON argument, "
            "so it may be full multi-line markdown with tables, pipes and "
            "backticks. The PM_TRIAGE marker and the attribution footer are "
            "added automatically from the design/sha fields — never type the "
            "marker yourself. One post per design per run; a repeat design "
            "is refused."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": (
                        "The verdict body in markdown per /pm §8: the "
                        "findings table (Finding / Verdict / Why), then the "
                        "This-round, Non-negotiables and Charter-follow-up "
                        "lines. Multi-line markdown, tables and code spans "
                        "are all fine here."
                    ),
                },
                "design": {
                    "type": "string",
                    "description": (
                        "The design name this verdict rules on — one of the "
                        "designs this run was handed (a name from "
                        "designs/<name>/)."
                    ),
                },
                "sha": {
                    "type": "string",
                    "description": (
                        "The PR's current head commit, 40 lower-case hex "
                        "characters — read it from `gh pr view <n>` first. "
                        "The marker records it so a verdict on a superseded "
                        "head is detectable."
                    ),
                },
            },
            "required": ["body", "design", "sha"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"post_review": _post_review, "post_triage": _post_triage}


def _tool_text(text):
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _tool_error(text):
    log(text)
    return {"content": [{"type": "text", "text": f"Error: {text}"}], "isError": True}


# --- JSON-RPC over stdio (newline-delimited) --------------------------------

def _result(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def handle(msg):
    """Map one JSON-RPC request to a response dict, or None for notifications."""
    method = msg.get("method")
    msg_id = msg.get("id")

    if msg_id is None and "id" not in msg:
        # Notifications get no response; ignore other id-less messages quietly.
        return None

    if method == "initialize":
        params = msg.get("params") or {}
        version = params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION
        return _result(
            msg_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"},
            },
        )

    if method == "ping":
        return _result(msg_id, {})

    if method == "tools/list":
        return _result(msg_id, {"tools": TOOLS})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        fn = _DISPATCH.get(name)
        if fn is None:
            return _result(msg_id, _tool_error(f"unknown tool: {name!r}"))
        return _result(msg_id, fn(params.get("arguments") or {}))

    return _error(msg_id, -32601, f"method not found: {method}")


def selftest():
    """Prove the write surface's security invariants fire, offline. A guard
    that is never exercised can be weakened and every other check stays green
    (the repo's standing rule), so these are the cases a live run cannot
    show."""
    global _last_payload
    os.environ["REVIEWER_MCP_FAKE"] = "1"
    os.environ["GITHUB_REPOSITORY"] = "example/selftest"
    os.environ["REVIEWER_PR"] = "123"
    os.environ["REVIEWER_ID"] = "jane"
    fails = []
    H40 = "a" * 40

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    def refused(r, needle):
        return r.get("isError") is True and needle in r["content"][0]["text"]

    def posted_body():
        return _last_payload["body"] if _last_payload else None

    # Pin the environment: each case below decides attended/unattended itself,
    # so an ambient Actions GITHUB_RUN_ID / REVIEWER_POST_STATE (this selftest
    # runs inside CI) must not leak into the attended cases.
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop(PM_DESIGNS_ENV, None)

    # Input guards reject and post nothing.
    _last_payload = None
    check("missing body is rejected",
          _post_review({"sha": H40, "verdict": "pass", "fuse": "none"})
          .get("isError") is True and _last_payload is None)
    _last_payload = None
    check("oversized body is rejected",
          _post_review({"body": "x" * (MAX_BODY_BYTES + 1), "sha": H40,
                        "verdict": "pass", "fuse": "none"})
          .get("isError") is True and _last_payload is None)
    _last_payload = None
    check("a short sha is rejected (malformed markers cannot be posted)",
          refused(_post_review({"body": "x", "sha": "abc", "verdict": "pass",
                                "fuse": "none"}), "'sha'")
          and _last_payload is None)
    _last_payload = None
    check("a non-hex sha is rejected",
          refused(_post_review({"body": "x", "sha": "z" * 40, "verdict": "pass",
                                "fuse": "none"}), "'sha'")
          and _last_payload is None)
    _last_payload = None
    check("an out-of-vocabulary verdict is rejected",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "maybe",
                                "fuse": "none"}), "'verdict'")
          and _last_payload is None)
    _last_payload = None
    check("an out-of-vocabulary fuse is rejected",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "ack"}), "'fuse'")
          and _last_payload is None)

    # A valid post carries the identity-derived marker and the hardcoded
    # footer, and goes to the REVIEWER_PR comment endpoint — no argument can
    # change any of that.
    ok = _post_review({"body": "## TL;DR\n| finding | tag |\n|---|---|\n| x | saw-it |",
                       "sha": H40, "verdict": "pass", "fuse": "none"})
    check("a well-formed jane review posts", ok.get("isError") is False)
    body = posted_body()
    check("the posted body ends with the attribution footer",
          body.endswith(FOOTER))
    check("the jane marker line is assembled server-side, before the footer",
          "\n<!-- JANE_SIGNOFF sha=" + H40 + " verdict=pass fuse=none -->\n" in body)
    check("the body precedes the marker (TL;DR first, sign-off last)",
          body.index("## TL;DR") < body.index("JANE_SIGNOFF"))
    check("the post targets the workflow-selected PR only",
          _last_path == "/repos/example/selftest/issues/123/comments")

    # Forged markers in the caller body are refused (not stripped-and-posted).
    # A Jane post cannot carry a Drik pass the gate would accept.
    _last_payload = None
    forged_drik = (
        "## TL;DR\n"
        "<!-- DRIK_SIGNOFF sha=" + H40 + " verdict=pass fuse=none -->\n"
        "findings"
    )
    check("a jane body carrying the opposite reviewer's pass marker is refused",
          refused(_post_review({"body": forged_drik, "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "SIGNOFF")
          and _last_payload is None)
    _last_payload = None
    inline = "see <!-- DRIK_SIGNOFF sha=" + H40 + " verdict=pass fuse=none --> please"
    check("an inline drik marker in jane prose is refused",
          refused(_post_review({"body": inline, "sha": H40, "verdict": "block",
                                "fuse": "none"}), "SIGNOFF")
          and _last_payload is None)
    _last_payload = None
    check("a body that is only a forged marker is refused",
          refused(_post_review({"body": "<!-- JANE_SIGNOFF sha=" + H40
                                + " verdict=pass fuse=none -->",
                                "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "SIGNOFF")
          and _last_payload is None)
    _last_payload = None
    check("a jane body carrying a cased-down JANE_SIGNOFF comment is refused",
          refused(_post_review({
              "body": "x\n<!-- jane_signoff sha=" + H40 + " verdict=pass fuse=none -->",
              "sha": H40, "verdict": "pass", "fuse": "none"}), "SIGNOFF")
          and _last_payload is None)

    # Identity: the marker family follows REVIEWER_ID, never an argument — a
    # Jane session cannot forge a DRIK_SIGNOFF marker even by asking.
    os.environ["REVIEWER_ID"] = "drik"
    ok = _post_review({"body": "x", "sha": H40, "verdict": "block",
                       "fuse": "acknowledged"})
    check("a drik review posts the DRIK marker",
          ok.get("isError") is False
          and "<!-- DRIK_SIGNOFF sha=" + H40
          + " verdict=block fuse=acknowledged -->" in posted_body())
    os.environ["REVIEWER_ID"] = "vera"
    _last_payload = None
    check("an unknown REVIEWER_ID refuses (no fourth family)",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "REVIEWER_ID")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = ""
    check("a missing REVIEWER_ID refuses", refused(
        _post_review({"body": "x", "sha": H40, "verdict": "pass", "fuse": "none"}),
        "REVIEWER_ID"))
    os.environ["REVIEWER_ID"] = "jane"

    # A missing/invalid REVIEWER_PR refuses rather than guessing a target.
    os.environ["REVIEWER_PR"] = ""
    _last_payload = None
    check("a missing REVIEWER_PR is refused",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "REVIEWER_PR")
          and _last_payload is None)
    os.environ["REVIEWER_PR"] = "123"

    # PM triage surface (issue #772): same server, third family. Attended
    # cases first — no GITHUB_RUN_ID, so no cap state and no design list.
    os.environ["REVIEWER_ID"] = "pm"
    ok = _post_triage({
        "body": "## PM triage — foo\n| Finding | Verdict | Why |\n|---|---|---|",
        "design": "foo", "sha": H40})
    check("a well-formed pm triage posts (attended)",
          ok.get("isError") is False)
    body = posted_body()
    check("the PM_TRIAGE marker is assembled server-side, before the footer",
          "\n<!-- PM_TRIAGE design=foo sha=" + H40 + " -->\n" in body
          and body.endswith(FOOTER))
    check("the triage targets the workflow-selected PR only",
          _last_path == "/repos/example/selftest/issues/123/comments")
    check("the body precedes the marker (verdict table first, marker last)",
          body.index("PM triage") < body.index("PM_TRIAGE"))
    ok = _post_triage({"body": "y", "design": "bar", "sha": H40})
    check("attended allows one post per design with no list to check",
          ok.get("isError") is False)
    _last_payload = None
    check("a triage body carrying a forged PM_TRIAGE marker is refused",
          refused(_post_triage({
              "body": "x\n<!-- PM_TRIAGE design=foo sha=" + H40 + " -->",
              "design": "foo", "sha": H40}), "PM_TRIAGE")
          and _last_payload is None)
    _last_payload = None
    check("a pm body carrying a reviewer's pass marker is refused (the gate "
          "forgery — get_marker() has no author check)",
          refused(_post_triage({
              "body": "<!-- JANE_SIGNOFF sha=" + H40
                      + " verdict=pass fuse=none -->",
              "design": "foo", "sha": H40}), "SIGNOFF")
          and _last_payload is None)
    _last_payload = None
    check("a malformed design name is refused",
          refused(_post_triage({"body": "x", "design": "../evil", "sha": H40}),
                  "'design'")
          and _last_payload is None)
    _last_payload = None
    check("a triage with a short sha is refused",
          refused(_post_triage({"body": "x", "design": "foo", "sha": "abc"}),
                  "'sha'")
          and _last_payload is None)
    # Cross-tool identity: each surface refuses the other's identities — a
    # mis-wired step must fail loudly, not post the wrong family.
    os.environ["REVIEWER_ID"] = "jane"
    _last_payload = None
    check("post_triage under a jane identity refuses",
          refused(_post_triage({"body": "x", "design": "foo", "sha": H40}),
                  "REVIEWER_ID")
          and _last_payload is None)
    _last_payload = None
    check("a jane body carrying a PM_TRIAGE marker is refused",
          refused(_post_review({
              "body": "x\n<!-- pm_triage design=foo sha=" + H40 + " -->",
              "sha": H40, "verdict": "pass", "fuse": "none"}), "PM_TRIAGE")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = "pm"
    _last_payload = None
    check("post_review under a pm identity refuses (sign-offs are not the "
          "PM's to give)",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "REVIEWER_ID")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = "jane"

    # Attended behavior: no GITHUB_RUN_ID means the cap is skipped — no state
    # file needed, and a human driving a local review may post again.
    a1 = _post_review({"body": "attended one", "sha": H40, "verdict": "pass",
                       "fuse": "none"})
    a2 = _post_review({"body": "attended two", "sha": H40, "verdict": "pass",
                       "fuse": "none"})
    check("attended (no GITHUB_RUN_ID) skips the cap — no state file required",
          a1.get("isError") is False and a2.get("isError") is False)

    # The walk-spanning one-review cap, inside an Actions run.
    os.environ["GITHUB_RUN_ID"] = "selftest-run"

    # Unwired: run id set but no state path. Fail closed — per-process
    # counting is exactly the per-link reset the state file replaces.
    _last_payload = None
    r = _post_review({"body": "unwired", "sha": H40, "verdict": "pass",
                      "fuse": "none"})
    check("an unattended run without REVIEWER_POST_STATE refuses (fail closed)",
          refused(r, f"{CAP_STATE_ENV} is not set") and _last_payload is None)

    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "reviewer-posts")
        os.environ[CAP_STATE_ENV] = state

        # A post that FAILS does not consume the cap — the record is appended
        # only after a successful write.
        os.environ["REVIEWER_PR"] = ""
        r = _post_review({"body": "will fail", "sha": H40, "verdict": "pass",
                          "fuse": "none"})
        os.environ["REVIEWER_PR"] = "123"
        check("a failed post does not consume the cap",
              r.get("isError") is True and _cap_state_count(state) == 0)

        # In-process: the first post goes through and is recorded; the second
        # is refused from the count the state file holds.
        r1 = _post_review({"body": "first", "sha": H40, "verdict": "pass",
                           "fuse": "none"})
        check("the first post of a run goes through and appends one record",
              r1.get("isError") is False and _cap_state_count(state) == 1)
        try:
            with open(state, encoding="utf-8") as fh:
                recs = [json.loads(ln) for ln in fh if ln.strip()]
        except (OSError, ValueError):
            recs = []
        check("the state record names the workflow-selected PR",
              len(recs) == 1 and recs[0].get("pr") == 123)
        _last_payload = None
        r2 = _post_review({"body": "second", "sha": H40, "verdict": "pass",
                           "fuse": "none"})
        check("a second post in the same run is refused",
              refused(r2, "ONE review") and _last_payload is None
              and _cap_state_count(state) == 1)

        # THE cross-process property: link N posts and then dies; link N+1 is
        # a FRESH process whose only memory of the run is the state file. A
        # real subprocess against the populated file is the exact situation
        # the old in-process counter got wrong.
        probe = [sys.executable, os.path.abspath(__file__), "--selftest-cap-child"]
        proc = subprocess.run(probe + [state], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process counting from a state file at the cap refuses "
              "(the cross-process property)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))

        # Below the cap (link 1 died before posting) → the fresh process posts,
        # and the shared file advances — so the link after IT refuses too.
        state2 = os.path.join(tmp, "reviewer-posts-2")
        proc = subprocess.run(probe + [state2], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process below the cap posts (cross-process)",
              proc.returncode == 0 and proc.stdout.startswith("POSTED"))
        check("the fresh process's post advanced the shared state file",
              _cap_state_count(state2) == 1)
        proc = subprocess.run(probe + [state2], env=dict(os.environ),
                              capture_output=True, text=True)
        check("the next fresh process sees that post and refuses",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))

        # Post-then-record hole: JSONL append failed after the GitHub POST, so
        # the state file is empty, but the sidecar flag was written. A later
        # link must still refuse.
        state3 = os.path.join(tmp, "reviewer-posts-sidecar")
        with open(state3, "w", encoding="utf-8"):
            pass
        with open(state3 + ".posted", "w", encoding="utf-8") as fh:
            fh.write("1\n")
        check("an empty JSONL plus the posted sidecar counts as already posted",
              _cap_state_count(state3) == 1)
        proc = subprocess.run(probe + [state3], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process seeing only the posted sidecar refuses "
              "(post-then-record reconcile)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))

        # An unreadable state path (a directory) refuses rather than counting
        # zero — a silent zero would silently uncap the walk.
        os.environ[CAP_STATE_ENV] = tmp
        _last_payload = None
        r = _post_review({"body": "unreadable", "sha": H40, "verdict": "pass",
                          "fuse": "none"})
        check("an unreadable state file refuses (never counts as zero)",
              refused(r, "cannot read") and _last_payload is None)

        # A state path that cannot be appended (its directory is missing)
        # refuses BEFORE posting — a post it could not record would let a
        # later link post again.
        os.environ[CAP_STATE_ENV] = os.path.join(tmp, "missing-dir", "reviewer-posts")
        _last_payload = None
        r = _post_review({"body": "unappendable", "sha": H40, "verdict": "pass",
                          "fuse": "none"})
        check("an unappendable state path refuses before posting",
              refused(r, "cannot append") and _last_payload is None)

    # The PM triage cap (issue #772): ONE verdict per workflow-selected design,
    # counted from the shared state file so it spans the chain walk's fresh
    # processes. The design set itself comes from trusted env and is required
    # unattended — a missing list fails closed before any state is touched.
    with tempfile.TemporaryDirectory() as ttmp:
        state = os.path.join(ttmp, "reviewer-posts")
        os.environ[CAP_STATE_ENV] = state
        os.environ["REVIEWER_ID"] = "pm"
        os.environ.pop(PM_DESIGNS_ENV, None)
        _last_payload = None
        r = _post_triage({"body": "no list", "design": "foo", "sha": H40})
        check("an unattended pm triage without REVIEWER_PM_DESIGNS refuses "
              "(fail closed)",
              refused(r, PM_DESIGNS_ENV) and _last_payload is None)
        os.environ[PM_DESIGNS_ENV] = "foo bar"
        r = _post_triage({"body": "triage foo", "design": "foo", "sha": H40})
        check("the first verdict for a design posts and is recorded with "
              "its design",
              r.get("isError") is False
              and _cap_state_designs(state) == {"foo"})
        _last_payload = None
        r = _post_triage({"body": "triage foo again", "design": "foo",
                          "sha": H40})
        check("a second verdict for the same design is refused",
              refused(r, "ONE verdict per design") and _last_payload is None)

        # Cross-process, the triage twin of the review cap's probe: link N
        # triaged foo and died; link N+1 knows only the state file.
        tprobe = [sys.executable, os.path.abspath(__file__),
                  "--selftest-triage-child"]
        proc = subprocess.run(tprobe + [state, "foo"], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process refuses a design a dead link triaged "
              "(cross-process per-design cap)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))
        proc = subprocess.run(tprobe + [state, "bar"], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process posts the design not yet triaged "
              "(cross-process)",
              proc.returncode == 0 and proc.stdout.startswith("POSTED"))
        _last_payload = None
        r = _post_triage({"body": "triage bar again", "design": "bar",
                          "sha": H40})
        check("the fresh process's post advanced the shared state (the next "
              "link refuses)",
              refused(r, "ONE verdict per design") and _last_payload is None)
        _last_payload = None
        r = _post_triage({"body": "triage baz", "design": "baz", "sha": H40})
        check("a design outside REVIEWER_PM_DESIGNS is refused",
              refused(r, "may rule on") and _last_payload is None)

        # Post-then-record hole, triage shape: empty JSONL, sidecar carrying
        # the design — that design still counts as posted, another does not.
        state4 = os.path.join(ttmp, "reviewer-triage-sidecar")
        with open(state4, "w", encoding="utf-8"):
            pass
        with open(state4 + ".posted", "w", encoding="utf-8") as fh:
            fh.write("foo\n")
        proc = subprocess.run(tprobe + [state4, "foo"], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a sidecar carrying design foo refuses foo (post-then-record "
              "reconcile)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))
        proc = subprocess.run(tprobe + [state4, "bar"], env=dict(os.environ),
                              capture_output=True, text=True)
        check("the same sidecar does not refuse a different design",
              proc.returncode == 0 and proc.stdout.startswith("POSTED"))

        # A record with no design proves nothing about what was triaged —
        # refuse rather than under-count (a review record could never sit in
        # a pm-triage run's state, but a truncated write could).
        state5 = os.path.join(ttmp, "reviewer-triage-designless")
        with open(state5, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"pr": 123, "url": "x",
                                 "posted_at": "now"}) + "\n")
        os.environ[CAP_STATE_ENV] = state5
        _last_payload = None
        r = _post_triage({"body": "designless", "design": "foo", "sha": H40})
        check("a state record with no design refuses (never under-counts)",
              refused(r, "no design") and _last_payload is None)
        os.environ["REVIEWER_ID"] = "jane"

    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop(PM_DESIGNS_ENV, None)

    # The JSON-RPC surface exposes exactly the two posting tools.
    check("tools/list exposes exactly post_review and post_triage",
          [t["name"] for t in TOOLS] == ["post_review", "post_triage"])

    if fails:
        print(f"\nreviewer_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nreviewer_mcp selftest passed")
    return 0


def selftest_cap_child(state_path):
    """One posting attempt in THIS fresh process — the parent selftest's
    cross-process case. The parent's module state died with its process; the
    only thing this process knows about the run's posts is the state file it
    is handed, which is exactly link N+1's view after link N posted and died.
    Prints POSTED/REFUSED for the parent to assert on."""
    os.environ["REVIEWER_MCP_FAKE"] = "1"
    os.environ["GITHUB_REPOSITORY"] = "example/selftest"
    os.environ["REVIEWER_PR"] = "123"
    os.environ["REVIEWER_ID"] = "jane"
    os.environ["GITHUB_RUN_ID"] = "selftest-link-n+1"
    os.environ[CAP_STATE_ENV] = state_path
    r = _post_review({"body": "cross-process probe", "sha": "b" * 40,
                      "verdict": "pass", "fuse": "none"})
    outcome = "REFUSED" if r.get("isError") else "POSTED"
    print(f"{outcome}: {r['content'][0]['text']}")
    return 0


def selftest_triage_child(state_path, design):
    """The triage twin of ``selftest_cap_child``: one post_triage attempt in
    THIS fresh process, for one design. Prints POSTED/REFUSED for the parent
    to assert on. The design list is inherited from the parent's env — it
    travels with the walk exactly as the workflow's step env does."""
    os.environ["REVIEWER_MCP_FAKE"] = "1"
    os.environ["GITHUB_REPOSITORY"] = "example/selftest"
    os.environ["REVIEWER_PR"] = "123"
    os.environ["REVIEWER_ID"] = "pm"
    os.environ["GITHUB_RUN_ID"] = "selftest-triage-link-n+1"
    os.environ[CAP_STATE_ENV] = state_path
    r = _post_triage({"body": "cross-process triage probe", "design": design,
                      "sha": "b" * 40})
    outcome = "REFUSED" if r.get("isError") else "POSTED"
    print(f"{outcome}: {r['content'][0]['text']}")
    return 0


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--selftest-cap-child" in sys.argv:
        i = sys.argv.index("--selftest-cap-child")
        if i + 1 >= len(sys.argv):
            log("--selftest-cap-child needs the state-file path argument")
            raise SystemExit(2)
        raise SystemExit(selftest_cap_child(sys.argv[i + 1]))
    if "--selftest-triage-child" in sys.argv:
        i = sys.argv.index("--selftest-triage-child")
        if i + 2 >= len(sys.argv):
            log("--selftest-triage-child needs the state-file path and "
                "design arguments")
            raise SystemExit(2)
        raise SystemExit(selftest_triage_child(sys.argv[i + 1],
                                               sys.argv[i + 2]))
    log(f"starting (repo={os.environ.get('GITHUB_REPOSITORY', '?')}, "
        f"pr={os.environ.get('REVIEWER_PR', '?')}, "
        f"reviewer={os.environ.get('REVIEWER_ID', '?')}, "
        f"run={os.environ.get('GITHUB_RUN_ID', 'attended')})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"skipping unparseable line: {e}")
            continue
        try:
            response = handle(msg)
        except Exception as e:  # noqa: BLE001 — never let one message kill the loop
            log(f"handler error: {type(e).__name__}: {e}")
            response = _error(msg.get("id"), -32603, f"internal error: {e}")
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    log("stdin closed, exiting")


if __name__ == "__main__":
    main()
