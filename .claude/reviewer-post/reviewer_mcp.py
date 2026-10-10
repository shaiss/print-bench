#!/usr/bin/env python3
"""reviewer_mcp.py — the Jane/Drik/PM-triage shared posting surface, stdio MCP.

WHY THIS SERVER EXISTS (issues #764, #772, coach path #806)
-----------------------------------------------------------
The auto-review reviewer agents (Jane, Drik, then PM triage) ran for their
whole history under
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
    set by the trusted workflow step — never an argument. The marker family
    (JANE_SIGNOFF vs DRIK_SIGNOFF vs PM_TRIAGE) is derived from it server-side,
    so a Jane session cannot forge Drik's sign-off, a PM session cannot post a
    reviewer sign-off, and no input can post an unrecognised marker family;
  * Jane/Drik markers are ASSEMBLED from validated fields (40-hex sha,
    pass|block verdict, none|acknowledged fuse) — the fail-closed
    reviewer-signoff gate's "malformed marker" failure mode is unreachable
    from this path. PM triage markers are assembled as
    ``<!-- PM_TRIAGE design=<name>[,<name>…] sha=<40hex> -->`` (the /pm §8
    family — one ruling per run, every covered design named) plus the
    per-head completion marker ``<!-- PM_TRIAGE_DONE sha=<40hex> -->``
    (issue #770) that the chain walk keys on; coach posts carry
    ``<!-- COACH_LOCK -->`` then ``<!-- COACH_DONE sha=<40hex> -->``;
  * a caller body that contains ``<!-- JANE_SIGNOFF`` / ``<!-- DRIK_SIGNOFF``
    / ``<!-- PM_TRIAGE`` / ``<!-- COACH_LOCK`` / ``<!-- COACH_DONE``
    (case-insensitive) is refused,
    not posted: ``get_marker()`` greps every comment with no author check, so
    a Jane body carrying a Drik pass would otherwise satisfy both identities
    from one post, and a Jane/Drik/PM body carrying ``<!-- COACH_LOCK -->``
    would satisfy the coach completeness pin (those jobs share
    ``github-actions[bot]``). Only the server-assembled marker from trusted
    REVIEWER_ID may appear;
  * the attribution footer is HARDCODED here — every post is disclosed as a
    Claude Code review whatever the body says;
  * a per-run cap of ONE post (counted in a state file every chain link of
    the walk shares, REVIEWER_POST_STATE — the ORACLE_CAP_STATE pattern)
    bounds a hijacked run to a single comment;
  * a size cap bounds the body, so the tool cannot dump a repository into a
    PR thread;
  * the only GitHub call is `POST /issues/{REVIEWER_PR}/comments` on the
    CURRENT repo — no labels, no reviews/approves, no other repo, no pushes.

Jane/Drik ship steps allow `mcp__reviewer__post_review`; pm-triage allows
`mcp__reviewer__post_triage`. Each is the session's only added write; gh/jq/
mktemp stay allowed for reads (the backstop keeps denying everything else).

The design-coach job is the same posting hole (#806) with different
containment: the coach still pushes iterations (Write/Edit + git
checkout/add/commit/push stay allowed — Jane/Drik's read-only
`--allowedTools` must not be copied onto it). Its comments are still
multi-line markdown, so `gh pr comment --body` is denied under dontAsk the
same way; run 37218561622 completed success with `permission_denials_count`
= 3 and posted no COACH-LOCK. `post_coach` is the JSON-argument write for
those comments. The HTML `<!-- COACH_LOCK -->` marker is assembled here;
`scripts/coach-lock-check.sh` is the pin that a denial-only turn cannot
stamp the round complete (claude-code-action still exits 0), and it
counts only an Actions-bot comment that *ends* with the assembled
``<!-- COACH_LOCK -->`` + footer suffix — a planted ``🎓 COACH-LOCK``
substring, or a Jane/Drik/PM body that smuggled the HTML (those jobs
share ``github-actions[bot]``), does not satisfy it. Cap is 8 comments
per unattended walk — a kickoff plus first-round notes — not Jane's
one-review cap.

Jane's and Drik's jobs check out ``pull_request.base.ref`` so this
file is never the PR's copy. The coach cannot: it git-pushes the PR
branch, so auto-review.yml overlays ``.claude/reviewer-post/`` (and
the coach settings/skill) from ``base.sha`` before each agent step.
The completeness pin then extracts ``scripts/coach-lock-check.sh``
from the same base blob AFTER the agent — the workspace copy is
Write-able. The MCP config's command is ``/usr/bin/python3`` (not
PATH ``python3``) with ``-I`` (isolated mode) so a GITHUB_PATH /
GITHUB_ENV write from a failed Bash link cannot become the posting
server via PATH lookup or PYTHONPATH sitecustomize. Do not spawn
this server from a PR-controlled checkout.

Stdlib only; logs go to stderr so stdout carries nothing but JSON-RPC.
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
# The sign-off families this server may emit, keyed by the trusted
# REVIEWER_ID env value. Anything else is refused — a new reviewer joins by
# adding an entry here, not by passing a new string at call time.
REVIEWERS = {"jane": "JANE_SIGNOFF", "drik": "DRIK_SIGNOFF", "pm": "PM_TRIAGE"}
# Which tool an identity may call. The family still comes from REVIEWERS, so a
# new identity is an entry here plus its tool set — never a call-time string.
REVIEW_POSTERS = {"jane", "drik"}
TRIAGE_POSTERS = {"pm"}
FOOTER = "---\n_Generated by [Claude Code](https://claude.ai/code)_"
# One review comment is ~2-6 KB; 64 KiB is generous headroom for a long
# findings list while still refusing a repository dump (GitHub's own comment
# limit is 65536 characters).
MAX_BODY_BYTES = 64 * 1024
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# One review per run. Deliberately not an env knob — "one signed-off review
# per reviewer per round" is the reviewer contract, not a tunable.
MAX_POSTS_PER_RUN = 1
# Coach comments are a thread, not a single sign-off. Bound a hijacked
# unattended walk without refusing the kickoff-plus-round the first job
# actually posts.
MAX_COACH_POSTS_PER_RUN = 8
COACH_LOCK_HTML = "<!-- COACH_LOCK -->"
COACH_LOCK_LINE = "🎓 COACH-LOCK"

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


def _cap_state_record(path, pr, url):
    """Append ONE record — only ever AFTER a successful post, so refused and
    failed attempts never consume the cap (the greenlight wrapper's rule). The
    record doubles as the audit trail of what a link that later died posted."""
    rec = {"pr": pr, "url": url,
           "posted_at": datetime.now(timezone.utc).isoformat()}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


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


def _reviewer():
    """The reviewing identity — trusted workflow input, never an argument.

    Determines the marker family the post may carry; a Jane session can
    never emit a DRIK_SIGNOFF or PM_TRIAGE marker (and vice versa) because
    the prefix is derived here, from the env the step set, not from anything
    the model writes."""
    who = os.environ.get("REVIEWER_ID", "").strip().lower()
    marker = REVIEWERS.get(who)
    if marker is None:
        raise RuntimeError(
            "REVIEWER_ID is not one of " + "/".join(sorted(REVIEWERS))
            + " — the workflow must export it (it selects the sign-off family;"
            + " it is deliberately not a tool argument)")
    return who, marker


def _require_coach():
    """Coach identity — trusted workflow input, never an argument.

    post_coach refuses any other REVIEWER_ID so a Jane/Drik step that
    somehow loaded this tool cannot emit a COACH_LOCK, and a coach step
    cannot satisfy reviewer-signoff via post_review (that tool still keys
    only jane/drik).
    """
    who = os.environ.get("REVIEWER_ID", "").strip().lower()
    if who != "coach":
        raise RuntimeError(
            "REVIEWER_ID is not coach — the workflow must export it for "
            "post_coach (it is deliberately not a tool argument)")
    return who


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


# Reserved HTML-comment syntax the sign-off / coach-lock / completion
# checks grep for. A caller body that already contains any family is
# refused — REVIEWER_ID only chooses which marker *we* append. get_marker()
# has no author check, and Jane/Drik/PM share github-actions[bot] with the
# coach, so a planted COACH_LOCK / COACH_DONE / PM_TRIAGE_DONE in a sibling
# caller body is refused here; coach-lock-check.sh and reviewer-posted.sh
# also require the assembled marker-then-footer suffix.
_INJECTED_MARKER = re.compile(
    r"<!--\s*(?:(?:JANE|DRIK)_SIGNOFF|PM_TRIAGE(?:_DONE)?|COACH_(?:LOCK|DONE))\b",
    re.IGNORECASE,
)


def _marker_line(marker, sha, verdict, fuse):
    """The Jane/Drik sign-off marker, assembled from validated fields —
    byte-identical to the shape scripts/reviewer-signoff.sh parses:
    <!-- <FAMILY>_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
    """
    return f"<!-- {marker} sha={sha} verdict={verdict} fuse={fuse} -->"


def _parse_designs(raw):
    """Every design this ruling covers. Sorted unique names, or an error.

    One post per run (MAX_POSTS_PER_RUN) has to name every design the PR
    touches, so ``design`` accepts a comma- or space-separated list. A
    single name stays the common case and keeps the historical marker
    ``design=<name>``.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None, _tool_error(
            "post_triage: 'design' must name every design this ruling "
            "covers ([A-Za-z0-9][A-Za-z0-9._-]*), comma- or "
            f"space-separated; got {raw!r}")
    names = [t for t in re.split(r"[\s,]+", raw.strip()) if t]
    if not names:
        return None, _tool_error(
            "post_triage: 'design' must name every design this ruling "
            f"covers; got {raw!r}")
    bad = [n for n in names if not _DESIGN_RE.fullmatch(n)]
    if bad:
        return None, _tool_error(
            "post_triage: 'design' must be design directory name(s) "
            "([A-Za-z0-9][A-Za-z0-9._-]*), comma- or space-separated; "
            f"got {bad[0]!r}")
    return sorted(set(names)), None


def _triage_marker_line(designs, sha):
    """The PM triage markers, assembled from validated fields.

    Per-design verdict marker (kept for §8 reads) plus the per-head
    completion marker (issue #770) that reviewer-posted.sh keys the
    chain walk on — DONE is last so the body ends with the completion
    suffix the artifact check matches:
      <!-- PM_TRIAGE design=<name>[,<name>…] sha=<40hex> -->
      <!-- PM_TRIAGE_DONE sha=<40hex> -->
    """
    return (
        f"<!-- PM_TRIAGE design={','.join(designs)} sha={sha} -->\n\n"
        f"<!-- PM_TRIAGE_DONE sha={sha} -->"
    )


def _coach_done_line(sha):
    """Per-head coach completion marker (issue #770)."""
    return f"<!-- COACH_DONE sha={sha} -->"


def _post_comment(body, marker_line):
    """POST one comment to the workflow-selected PR. The marker and footer
    are assembled HERE, never from caller input. REVIEWER_MCP_FAKE
    short-circuits the network for the selftest (it is never set in the
    workflow)."""
    global _last_payload, _last_path
    full = (f"{body.rstrip()}\n\n"
            f"{marker_line}\n\n"
            f"{FOOTER}")
    payload = {"body": full}
    path = f"/repos/{_repo()}/issues/{_pr_number()}/comments"
    _last_payload = payload
    _last_path = path
    if os.environ.get("REVIEWER_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake"}
    return _api("POST", path, payload)


_SHA_CHARS = set("0123456789abcdef")
_DESIGN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _validate_body(tool, body):
    if not isinstance(body, str) or not body.strip():
        return _tool_error(f"{tool}: 'body' is required (non-empty string)")
    if len(body.encode()) > MAX_BODY_BYTES:
        return _tool_error(
            f"{tool}: body is {len(body.encode())} bytes, over the "
            f"{MAX_BODY_BYTES}-byte cap — condense it")
    if _INJECTED_MARKER.search(body):
        return _tool_error(
            f"{tool}: body must not contain a JANE_SIGNOFF, DRIK_SIGNOFF, "
            "PM_TRIAGE, PM_TRIAGE_DONE, COACH_LOCK or COACH_DONE HTML "
            "comment — the marker is assembled server-side from typed "
            "fields and REVIEWER_ID; a caller-supplied marker is refused so "
            "one post cannot satisfy another identity's family")
    return None


def _validate_sha(tool, sha):
    if not isinstance(sha, str) or len(sha) != 40 \
            or not set(sha.lower()) <= _SHA_CHARS:
        return _tool_error(
            f"{tool}: 'sha' must be the PR's current head commit as 40 "
            "lower-case hex characters (read it from `gh pr view`); got "
            f"{sha!r}")
    return None


def _cap_preflight(tool):
    """Return (state_path_or_None, error_or_None)."""
    state = _cap_state_path()
    if state is None:
        return None, None
    if not state:
        return None, _tool_error(
            f"{tool}: {CAP_STATE_ENV} is not set but this is an "
            "unattended run (GITHUB_RUN_ID is set) — the workflow must "
            "give every link step the same state-file path or the "
            "one-post cap cannot span the chain walk; refusing to post")
    try:
        posted = _cap_state_count(state)
    except RuntimeError as e:
        return None, _tool_error(f"{tool}: {e}")
    if posted >= MAX_POSTS_PER_RUN:
        return None, _tool_error(
            "this reviewer posts exactly ONE comment per run and it is "
            f"already posted ({posted} recorded across the chain walk so "
            "far); refusing a second comment")
    try:
        _cap_state_ensure_appendable(state)
    except RuntimeError as e:
        return None, _tool_error(f"{tool}: {e}")
    return state, None


def _cap_record(state, url):
    recorded = False
    try:
        _cap_state_record(state, _pr_number(), url)
        recorded = True
    except OSError as e:
        log(f"WARNING: posted {url} but could not append its "
            f"{CAP_STATE_ENV} JSONL record ({e})")
    try:
        with open(state + ".posted", "w", encoding="utf-8") as fh:
            fh.write("1\n")
            fh.flush()
            os.fsync(fh.fileno())
        recorded = True
    except OSError as e:
        log(f"WARNING: posted {url} but could not write the "
            f"{CAP_STATE_ENV} posted-flag ({e})")
    if not recorded:
        return _tool_error(
            f"posted {url} but could not record the walk cap — refusing "
            "so a later link does not treat this run as unposted")
    return None


def _emit(tool, body, marker_line, noun):
    try:
        _pr_number()
        _repo()
    except RuntimeError as e:
        return _tool_error(f"{tool}: {e}")
    state, err = _cap_preflight(tool)
    if err is not None:
        return err
    try:
        comment = _post_comment(body, marker_line)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} posting {noun}: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to post {noun}: {type(e).__name__}: {e}")
    url = comment.get("html_url", "(unknown url)")
    if state:
        rec_err = _cap_record(state, url)
        if rec_err is not None:
            return rec_err
    log(f"posted {_reviewer()[0]} {noun}: {url}")
    return _tool_text(f"POSTED {url}")


def _post_review(arguments):
    """Post ONE signed-off Jane/Drik review comment."""
    args = arguments or {}
    body = args.get("body")
    sha = args.get("sha")
    verdict = args.get("verdict")
    fuse = args.get("fuse")
    err = _validate_body("post_review", body)
    if err is not None:
        return err
    err = _validate_sha("post_review", sha)
    if err is not None:
        return err
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

    try:
        who, marker = _reviewer()
    except RuntimeError as e:
        return _tool_error(f"post_review: {e}")
    if who not in REVIEW_POSTERS:
        return _tool_error(
            "post_review: REVIEWER_ID is "
            f"{who!r} — this tool posts a Jane/Drik sign-off; a pm session "
            "must use post_triage so it cannot emit JANE_SIGNOFF/DRIK_SIGNOFF")
    return _emit("post_review", body, _marker_line(marker, sha, verdict, fuse),
                 "review")


def _post_triage(arguments):
    """Post ONE PM triage ruling. The pm-triage job's entire write taxonomy
    besides the HITL `needs-decision` label via chunk-helper."""
    args = arguments or {}
    body = args.get("body")
    sha = args.get("sha")
    design = args.get("design")
    err = _validate_body("post_triage", body)
    if err is not None:
        return err
    err = _validate_sha("post_triage", sha)
    if err is not None:
        return err
    designs, err = _parse_designs(design)
    if err is not None:
        return err

    try:
        who, marker = _reviewer()
    except RuntimeError as e:
        return _tool_error(f"post_triage: {e}")
    if who not in TRIAGE_POSTERS:
        return _tool_error(
            "post_triage: REVIEWER_ID is "
            f"{who!r} — this tool posts a PM_TRIAGE ruling; a jane/drik "
            "session must use post_review so it cannot emit the PM family")
    if marker != "PM_TRIAGE":
        return _tool_error(
            "post_triage: REVIEWER_ID did not select the PM_TRIAGE family")
    return _emit("post_triage", body, _triage_marker_line(designs, sha),
                 "triage")


def _post_coach_comment(body, sha):
    """POST one coach comment. COACH_LOCK, COACH_DONE and the footer are
    assembled HERE so a denial-only turn that never called this tool cannot
    satisfy scripts/coach-lock-check.sh / reviewer-posted.sh with a forged
    Jane comment. DONE is last (issue #770) so the artifact check's
    endswith match keys on the per-head completion marker; COACH_LOCK
    stays ahead of it for the lock-check's "contains lock + ends with
    DONE+footer" rule."""
    global _last_payload, _last_path
    text = body.rstrip()
    full = (f"{text}\n\n"
            f"{COACH_LOCK_HTML}\n\n"
            f"{_coach_done_line(sha)}\n\n"
            f"{FOOTER}")
    payload = {"body": full}
    path = f"/repos/{_repo()}/issues/{_pr_number()}/comments"
    _last_payload = payload
    _last_path = path
    if os.environ.get("REVIEWER_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake"}
    return _api("POST", path, payload)


def _cap_gate(label, max_posts):
    """Return None if posting may proceed, or a tool-error result."""
    state = _cap_state_path()
    if state is None:
        return None, None
    if not state:
        return _tool_error(
            f"{label}: {CAP_STATE_ENV} is not set but this is an "
            "unattended run (GITHUB_RUN_ID is set) — the workflow must "
            "give every link step the same state-file path or the "
            "cap cannot span the chain walk; refusing to post"
        ), None
    try:
        posted = _cap_state_count(state)
    except RuntimeError as e:
        return _tool_error(f"{label}: {e}"), None
    if posted >= max_posts:
        return _tool_error(
            f"{label}: this run's comment cap is {max_posts} and "
            f"{posted} are already recorded across the chain walk; "
            "refusing another comment"
        ), None
    try:
        _cap_state_ensure_appendable(state)
    except RuntimeError as e:
        return _tool_error(f"{label}: {e}"), None
    return None, state


def _cap_record_after(state, url, label):
    recorded = False
    try:
        _cap_state_record(state, _pr_number(), url)
        recorded = True
    except OSError as e:
        log(f"WARNING: posted {url} but could not append its "
            f"{CAP_STATE_ENV} JSONL record ({e})")
    try:
        with open(state + ".posted", "w", encoding="utf-8") as fh:
            fh.write("1\n")
            fh.flush()
            os.fsync(fh.fileno())
        recorded = True
    except OSError as e:
        log(f"WARNING: posted {url} but could not write the "
            f"{CAP_STATE_ENV} posted-flag ({e})")
    if not recorded:
        return _tool_error(
            f"posted {url} but could not record the walk cap — refusing "
            "so a later link does not treat this run as unposted")
    log(f"posted {label}: {url}")
    return None


def _post_coach(arguments):
    """Post one coach comment on the workflow-selected PR."""
    args = arguments or {}
    body = args.get("body")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("post_coach: 'body' is required (non-empty string)")
    if len(body.encode()) > MAX_BODY_BYTES:
        return _tool_error(
            f"post_coach: body is {len(body.encode())} bytes, over the "
            f"{MAX_BODY_BYTES}-byte cap")
    if _INJECTED_MARKER.search(body):
        return _tool_error(
            "post_coach: body must not contain a JANE_SIGNOFF, DRIK_SIGNOFF, "
            "PM_TRIAGE, PM_TRIAGE_DONE, COACH_LOCK or COACH_DONE HTML "
            "comment — those markers are assembled server-side")
    sha = args.get("sha")
    err = _validate_sha("post_coach", sha)
    if err is not None:
        return err
    # Canonicalise to lower-case hex (the artifact check is case-sensitive).
    sha = sha.lower()

    try:
        _require_coach()
        _pr_number()
        _repo()
    except RuntimeError as e:
        return _tool_error(f"post_coach: {e}")

    err, state = _cap_gate("post_coach", MAX_COACH_POSTS_PER_RUN)
    if err is not None:
        return err

    try:
        comment = _post_coach_comment(body, sha)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} posting coach comment: {detail}")
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to post coach comment: {type(e).__name__}: {e}")

    url = comment.get("html_url", "(unknown url)")
    if state:
        rec_err = _cap_record_after(state, url, "coach")
        if rec_err is not None:
            return rec_err
    else:
        log(f"posted coach comment: {url}")
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
            "Post your ONE PM triage ruling on the PR this run was launched "
            "for (the workflow fixes the PR number and REVIEWER_ID=pm — "
            "neither is an argument). This is your ONLY write for the "
            "verdict comment: posting any other way (gh pr comment, writing "
            "files) is denied by the permission backstop and will silently "
            "fail. The body is a JSON argument, so it may be full "
            "multi-line markdown with tables, pipes and backticks. The "
            "PM_TRIAGE + PM_TRIAGE_DONE markers and the attribution footer "
            "are added automatically from the design/sha fields — never "
            "type either marker yourself. One post per run covering every "
            "named design (a section each in the body); a second call is "
            "refused."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": (
                        "The triage body in markdown: the §8 table first. "
                        "Multi-line markdown, tables and code spans are all "
                        "fine here."
                    ),
                },
                "design": {
                    "type": "string",
                    "description": (
                        "Every design directory this ruling covers "
                        "(designs/<name>/), comma- or space-separated. "
                        "A single name is fine. Assembled into the "
                        "PM_TRIAGE marker server-side so the comment "
                        "identifies every design it rules on."
                    ),
                },
                "sha": {
                    "type": "string",
                    "description": (
                        "The PR's current head commit, 40 lower-case hex "
                        "characters — read it from `gh pr view <n>` first. "
                        "Also assembled into the PM_TRIAGE_DONE "
                        "completion marker (issue #770)."
                    ),
                },
            },
            "required": ["body", "design", "sha"],
            "additionalProperties": False,
        },
    },
    {
        "name": "post_coach",
        "description": (
            "Post a comment on the design PR this run was launched for "
            "(the workflow fixes the PR number — it is not an argument). "
            "Use this for the kickoff (start the body with "
            "'🎓 COACH-LOCK') and later round notes. This is the coach's "
            "comment write: a multi-line `gh pr comment --body` is denied "
            "under dontAsk. Git checkout/add/commit/push stay available "
            "separately for iterations. The COACH_LOCK HTML marker, the "
            "per-head COACH_DONE completion marker (issue #770) and the "
            "attribution footer are added automatically — pass `sha`."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "body": {
                    "type": "string",
                    "description": (
                        "The comment body in markdown. Kickoff comments "
                        "must start with '🎓 COACH-LOCK'. Multi-line "
                        "markdown, tables and code spans are fine here."
                    ),
                },
                "sha": {
                    "type": "string",
                    "description": (
                        "The PR's current head commit, 40 lower-case hex "
                        "characters — read it from `gh pr view <n>` first. "
                        "Assembled into the COACH_DONE completion marker."
                    ),
                },
            },
            "required": ["body", "sha"],
            "additionalProperties": False,
        },
    },
]

_DISPATCH = {
    "post_review": _post_review,
    "post_triage": _post_triage,
    "post_coach": _post_coach,
}


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
    _last_payload = None
    check("a jane body carrying COACH_LOCK is refused (cannot stamp the coach pin)",
          refused(_post_review({
              "body": "x\n" + COACH_LOCK_HTML, "sha": H40, "verdict": "pass",
              "fuse": "none"}), "COACH_LOCK")
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
    os.environ["REVIEWER_ID"] = "oracle"
    _last_payload = None
    check("an unknown REVIEWER_ID refuses (closed set)",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "REVIEWER_ID")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = ""
    check("a missing REVIEWER_ID refuses", refused(
        _post_review({"body": "x", "sha": H40, "verdict": "pass", "fuse": "none"}),
        "REVIEWER_ID"))
    os.environ["REVIEWER_ID"] = "jane"

    # PM identity: post_triage assembles PM_TRIAGE; post_review refuses so a
    # pm session cannot emit a Jane/Drik sign-off. The reverse: jane/drik
    # cannot emit PM_TRIAGE via post_triage.
    os.environ["REVIEWER_ID"] = "pm"
    ok = _post_triage({"body": "## 🧭 PM triage — demo\n| f | v |\n|---|---|\n| x | act-now |",
                       "design": "demo-part", "sha": H40})
    check("a well-formed pm triage posts", ok.get("isError") is False)
    body = posted_body()
    check("the posted triage ends with the attribution footer",
          body.endswith(FOOTER))
    check("the pm marker line is assembled server-side from design+sha",
          "\n<!-- PM_TRIAGE design=demo-part sha=" + H40 + " -->\n" in body)
    check("the pm completion marker (PM_TRIAGE_DONE) is assembled last",
          "\n<!-- PM_TRIAGE_DONE sha=" + H40 + " -->\n" in body
          and (body or "").endswith(
              "<!-- PM_TRIAGE_DONE sha=" + H40 + " -->\n\n" + FOOTER))
    check("the triage body precedes the marker",
          body.index("PM triage") < body.index("PM_TRIAGE design="))
    check("the triage post targets the workflow-selected PR only",
          _last_path == "/repos/example/selftest/issues/123/comments")
    _last_payload = None
    check("pm calling post_review is refused (cannot emit a Jane/Drik family)",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "post_triage")
          and _last_payload is None)
    _last_payload = None
    check("a pm body carrying a Jane sign-off marker is refused",
          refused(_post_triage({
              "body": "x\n<!-- JANE_SIGNOFF sha=" + H40 + " verdict=pass fuse=none -->",
              "design": "demo-part", "sha": H40}), "SIGNOFF")
          and _last_payload is None)
    _last_payload = None
    check("a pm body carrying a PM_TRIAGE marker is refused",
          refused(_post_triage({
              "body": "x\n<!-- PM_TRIAGE design=other sha=" + H40 + " -->",
              "design": "demo-part", "sha": H40}), "PM_TRIAGE")
          and _last_payload is None)
    _last_payload = None
    check("a pm body carrying COACH_LOCK is refused (cannot stamp the coach pin)",
          refused(_post_triage({
              "body": "x\n" + COACH_LOCK_HTML, "design": "demo-part",
              "sha": H40}), "COACH_LOCK")
          and _last_payload is None)
    _last_payload = None
    check("an invalid design name is refused",
          refused(_post_triage({"body": "x", "design": "../etc", "sha": H40}),
                  "'design'")
          and _last_payload is None)
    ok = _post_triage({"body": "## 🧭 PM triage — alpha\n## 🧭 PM triage — beta",
                       "design": "beta alpha", "sha": H40})
    check("a combined ruling names every design in the marker, sorted",
          ok.get("isError") is False
          and "\n<!-- PM_TRIAGE design=alpha,beta sha=" + H40 + " -->\n"
          in posted_body()
          and "\n<!-- PM_TRIAGE_DONE sha=" + H40 + " -->\n" in posted_body())
    ok = _post_triage({"body": "comma list", "design": "alpha, beta",
                       "sha": H40})
    check("comma-separated design names assemble the same marker",
          ok.get("isError") is False
          and "PM_TRIAGE design=alpha,beta sha=" + H40 in posted_body()
          and "PM_TRIAGE_DONE sha=" + H40 in posted_body())
    _last_payload = None
    check("a mixed list with one invalid name is refused",
          refused(_post_triage({"body": "x", "design": "alpha,../etc",
                                "sha": H40}), "'design'")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = "jane"
    _last_payload = None
    check("jane calling post_triage is refused (cannot emit the PM family)",
          refused(_post_triage({"body": "x", "design": "demo-part", "sha": H40}),
                  "post_review")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = "drik"
    _last_payload = None
    check("drik calling post_triage is refused (cross-family negative)",
          refused(_post_triage({"body": "x", "design": "demo-part", "sha": H40}),
                  "post_review")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = "jane"

    # A missing/invalid REVIEWER_PR refuses rather than guessing a target.
    os.environ["REVIEWER_PR"] = ""
    _last_payload = None
    check("a missing REVIEWER_PR is refused",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "REVIEWER_PR")
          and _last_payload is None)
    os.environ["REVIEWER_PR"] = "123"

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
              refused(r2, "ONE comment") and _last_payload is None
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

    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop("GITHUB_RUN_ID", None)

    # Coach family (#806): a separate tool, not a third REVIEWERS sign-off.
    os.environ["REVIEWER_ID"] = "coach"
    os.environ["REVIEWER_PR"] = "123"
    _last_payload = None
    check("post_review under coach is refused (not a sign-off family)",
          refused(_post_review({"body": "x", "sha": H40, "verdict": "pass",
                                "fuse": "none"}), "REVIEWER_ID")
          and _last_payload is None)
    ok = _post_coach({"body": COACH_LOCK_LINE + "\n\nkickoff", "sha": H40})
    check("a well-formed coach post succeeds", ok.get("isError") is False)
    body = posted_body()
    check("the coach post carries the HTML COACH_LOCK marker",
          COACH_LOCK_HTML in (body or ""))
    check("the coach post carries the per-head COACH_DONE marker",
          "<!-- COACH_DONE sha=" + H40 + " -->" in (body or ""))
    check("the coach post ends with the assembled DONE-then-footer suffix",
          (body or "").endswith(
              "<!-- COACH_DONE sha=" + H40 + " -->\n\n" + FOOTER))
    check("COACH_LOCK sits immediately before COACH_DONE",
          (body or "").index(COACH_LOCK_HTML)
          < (body or "").index("<!-- COACH_DONE sha=" + H40 + " -->"))
    check("the coach post targets the workflow-selected PR",
          _last_path == "/repos/example/selftest/issues/123/comments")
    _last_payload = None
    os.environ["REVIEWER_ID"] = "jane"
    check("post_coach under jane is refused",
          refused(_post_coach({"body": "x", "sha": H40}), "coach")
          and _last_payload is None)
    os.environ["REVIEWER_ID"] = "coach"
    _last_payload = None
    check("post_coach missing body is refused",
          _post_coach({"sha": H40}).get("isError") is True
          and _last_payload is None)
    _last_payload = None
    check("post_coach missing sha is refused",
          _post_coach({"body": "x"}).get("isError") is True
          and _last_payload is None)
    _last_payload = None
    check("a coach body carrying a JANE_SIGNOFF marker is refused",
          refused(_post_coach({
              "body": "<!-- JANE_SIGNOFF sha=" + H40
              + " verdict=pass fuse=none -->", "sha": H40}), "SIGNOFF")
          and _last_payload is None)
    _last_payload = None
    check("a coach body carrying a caller-supplied COACH_LOCK is refused",
          refused(_post_coach({"body": "x\n" + COACH_LOCK_HTML, "sha": H40}),
                  "COACH_LOCK")
          and _last_payload is None)
    _last_payload = None
    check("a coach body carrying a caller-supplied COACH_DONE is refused",
          refused(_post_coach({
              "body": "x\n<!-- COACH_DONE sha=" + H40 + " -->",
              "sha": H40}), "COACH_DONE")
          and _last_payload is None)

    os.environ["GITHUB_RUN_ID"] = "selftest-coach-cap"
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "coach-posts")
        os.environ[CAP_STATE_ENV] = state
        for i in range(MAX_COACH_POSTS_PER_RUN):
            r = _post_coach({"body": f"note {i}", "sha": H40})
            check(f"coach post {i + 1} under the cap succeeds",
                  r.get("isError") is False)
        _last_payload = None
        r = _post_coach({"body": "one too many", "sha": H40})
        check("coach post past the cap is refused",
              r.get("isError") is True and _last_payload is None)
    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ["REVIEWER_ID"] = "jane"

    check("tools/list exposes post_review, post_triage and post_coach",
          [t["name"] for t in TOOLS] == [
              "post_review", "post_triage", "post_coach"])

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


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    if "--selftest-cap-child" in sys.argv:
        i = sys.argv.index("--selftest-cap-child")
        if i + 1 >= len(sys.argv):
            log("--selftest-cap-child needs the state-file path argument")
            raise SystemExit(2)
        raise SystemExit(selftest_cap_child(sys.argv[i + 1]))
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
