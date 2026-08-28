#!/usr/bin/env python3
"""signoff_mcp.py — Reeve's sign-off surface for agent briefs, a stdio MCP tool.

WHY THIS EXISTS
---------------
The sign-off's only write is "post ONE verdict on a pending agent-brief issue
and apply that verdict's label" — and an *approve* verdict applies
`autonomy-ok`, the label that arms the backlog burn. That makes this the one
escalation-shaped write in the routine family, so it is the most guarded: the
verdict body is rich markdown (the dontAsk Bash matcher would deny it on a
command line — scout_mcp.py's documented dead end), and more importantly a
JSON tool lets every guarantee below live in committed code rather than in
model behavior.

SECURITY (the run reads UNTRUSTED issue text while holding a token)
-------------------------------------------------------------------
This server does NOT trust its inputs, and validates the TARGET at write time
rather than trusting anything the model supplies:
  * it RE-READS the target issue immediately before writing and requires it to
    be OPEN, an issue (not a PR), still carry the `agent-brief` label, and
    carry NO verdict label yet (`autonomy-ok` / `needs-decision` /
    `wright-declined`) — a stale or prompt-injected run can never re-arm,
    re-park or re-judge a ruled brief;
  * when the trusted workflow Select step exports `SIGNOFF_SELECTED_ISSUES`,
    the tool refuses any number NOT in that run's candidate set;
  * the VERDICT TAXONOMY is closed — `approve` / `decline` / `needs-human` —
    and each verdict's labels are constants: approve → `autonomy-ok` +
    `points-<n>` (n in 1/2/3, required), decline → `wright-declined`,
    needs-human → `needs-decision`. No argument can name a label;
  * the SENSITIVE-PATH GUARD is deterministic and runs on the SERVER-FETCHED
    title+body (never the model's paraphrase): an `approve` whose brief
    mentions the bench's protection machinery — existing deny backstops,
    perms-checks, the decision gate, arming variables, secret names, the
    forge's own workflow — is DOWNGRADED to needs-human, so the forge can
    never arm a brief that would modify its own fence. Erring safe is the
    point: a false positive parks a brief for a human, it never blocks one;
  * `WRIGHT_AUTO_ARM` != 'true' demotes the whole tool to advisory: approve
    then applies `needs-decision` (+ points) instead of `autonomy-ok`, so the
    human arms via the #161 decision gate;
  * labels are applied FIRST, the comment second (decide.yml's label-first
    fail-closed ordering): a half-failed write leaves the brief RULED (the
    label is the operative verdict) rather than eternally re-selected;
  * it refuses a DUPLICATE (a hidden marker on a prior sign-off comment,
    scanned across every comment page), caps verdicts per run, and its only
    GitHub writes are label-add + comment on the CURRENT repo. It never
    removes a label, never closes an issue, never touches code.
The run allow-lists ONLY this tool (`mcp__reeve_signoff__post_reeve_signoff`),
the read wrapper's verbs, and the read-only file tools; the deny backstop
(.claude/reeve-signoff-settings.json) additionally denies Wright's FILING
tool, so the judge can never file briefs. Stdlib only; logs to stderr.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BRIEF_LABEL = "agent-brief"
VERDICT_LABELS = ("autonomy-ok", "needs-decision", "wright-declined")
DECLINED_LABEL = "wright-declined"
DECLINED_LABEL_COLOR = "D93F0B"
DECLINED_LABEL_DESC = "Agent brief declined by Reeve's sign-off (the agent forge)"
VALID_POINTS = (1, 2, 3)
# Hidden marker the tool stamps on every sign-off comment. The duplicate
# guard looks for it, so one brief gets at most one sign-off comment.
MARKER = "<!-- reeve-signoff:v1 -->"
ADVISORY = (
    "> **Reeve sign-off (auto)** — the agent forge's sign-off half "
    "(`/reeve-signoff`) judged this agent brief against the platform charter "
    "(`PM.md`). The verdict label it applied is one click for a human to "
    "undo, an armed brief only ever becomes a **draft PR** through the "
    "backlog burn's gated pipeline, and every merge stays the human lead's "
    "(charter N3). See `docs/agent-forge.md`."
)
GITHUB_API = "https://api.github.com"
SERVER_NAME = "reeve_signoff"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# The deterministic sensitive-path guard: case-insensitive substrings that,
# found in the SERVER-FETCHED title+body, downgrade an `approve` to
# needs-human. These name the bench's EXISTING protection machinery — the
# things an unattended run must never arm a modification of. A brief for a
# NEW routine names its own conf/backstop/perms-check generically and never
# needs these literals (templates/agent-brief.md says so), so a hit is either
# a brief genuinely touching the fence (a human's call by definition) or
# sloppy phrasing worth a human glance. Either way: park, never arm.
SENSITIVE_PATTERNS = (
    # existing deny backstops + the shared settings file
    ".claude/settings.json",
    "chunker-settings.json",
    "labeler-settings.json",
    "scout-settings.json",
    "oracle-settings.json",
    "adoption-assessor-settings.json",
    "wright-settings.json",
    "reeve-signoff-settings.json",
    # the perms-check family
    "chunker-perms-check",
    "labeler-perms-check",
    "scout-perms-check",
    "oracle-perms-check",
    "adoption-assessor-perms-check",
    "wright-perms-check",
    # the decision gate + privileged workflows + the forge itself
    "decide.yml",
    "ci-gate-approve",
    "workflows/wright.yml",
    "wright_mcp",
    "signoff_mcp",
    # the sibling wrappers (each is another routine's write surface)
    "chunk-helper.sh",
    "label-helper.sh",
    "scout-helper.sh",
    "assessor-helper.sh",
    "wright-helper.sh",
    # secrets
    "regen_token",
    "anthropic_api_key",
    "zai_key",
    # arming variables (the live kill switches)
    "wright_enabled",
    "labeler_enabled",
    "chunker_enabled",
    "design_run_enabled",
    "backlog_burn_enabled",
    "product_scout_enabled",
    "backlog_groomer_enabled",
    "reeve_enabled",
    "adoption_assessor_enabled",
    # branch protection / the required design sign-off status
    "branch protection",
    "branch-protection",
    "reviewer-signoff",
)

# Per-run cap — GITHUB_RUN_ID is set and stable across one Actions run and
# this process lives for that whole run, so an in-process counter is naturally
# run-scoped. Attended (no run id) the cap is skipped — a human is the trust
# boundary, the same posture every sibling tool takes.
_posted_this_run = 0

# Captured by the selftest so it can assert exact writes (labels applied, in
# what order, and the comment body) without a network call.
_write_log = []

# Fake state for the offline selftest (SIGNOFF_MCP_FAKE): issue metadata and
# comments the network helpers read instead of GitHub.
_FAKE_ISSUES = {}
_FAKE_COMMENTS = {}


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"signoff_mcp: {msg}", file=sys.stderr, flush=True)


def _repo():
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo:
        raise RuntimeError("GITHUB_REPOSITORY is not set")
    return repo


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
    req.add_header("User-Agent", "print-bench-reeve-signoff")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def _get_issue(number):
    if os.environ.get("SIGNOFF_MCP_FAKE"):
        return _FAKE_ISSUES.get(number)
    return _api("GET", f"/repos/{_repo()}/issues/{number}")


def _get_comments(number):
    if os.environ.get("SIGNOFF_MCP_FAKE"):
        return list(_FAKE_COMMENTS.get(number, []))
    # Walk EVERY page — the duplicate guard scans for the marker, and on a
    # long thread an earlier sign-off can fall past the first 100.
    out = []
    page = 1
    while True:
        batch = _api(
            "GET",
            f"/repos/{_repo()}/issues/{number}/comments?per_page=100&page={page}",
        )
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
        if page > 50:  # bound the walk; a brief thread is never this long
            break
    return out


def _ensure_declined_label():
    """Create the wright-declined label if missing — the ONE label this server
    may ever create, from constants. Idempotent (422 = exists)."""
    if os.environ.get("SIGNOFF_MCP_FAKE"):
        return
    try:
        _api("POST", f"/repos/{_repo()}/labels",
             {"name": DECLINED_LABEL, "color": DECLINED_LABEL_COLOR,
              "description": DECLINED_LABEL_DESC})
    except urllib.error.HTTPError as e:
        if e.code != 422:
            raise


def _add_labels(number, labels):
    """ADD (never remove) labels to one issue on the CURRENT repo."""
    _write_log.append(("labels", number, tuple(labels)))
    if os.environ.get("SIGNOFF_MCP_FAKE"):
        issue = _FAKE_ISSUES.get(number)
        if issue is not None:
            issue.setdefault("labels", [])
            issue["labels"].extend({"name": l} for l in labels)
        return {}
    return _api("POST", f"/repos/{_repo()}/issues/{number}/labels",
                {"labels": list(labels)})


def _post_comment(number, body):
    """POST one issue comment on the CURRENT repo."""
    _write_log.append(("comment", number, body))
    if os.environ.get("SIGNOFF_MCP_FAKE"):
        _FAKE_COMMENTS.setdefault(number, []).append({"body": body})
        return {"html_url": f"https://example.invalid/{number}", "id": 0}
    return _api("POST", f"/repos/{_repo()}/issues/{number}/comments", {"body": body})


def _selected_issues():
    """The trusted workflow Select step exports SIGNOFF_SELECTED_ISSUES
    (space- or comma-separated digits) — the run's candidate set. Returns a
    set, or None when unset (attended: a human is the trust boundary)."""
    raw = os.environ.get("SIGNOFF_SELECTED_ISSUES", "").strip()
    if not raw:
        return None
    nums = set()
    for tok in raw.replace(",", " ").split():
        if tok.isdigit():
            nums.add(int(tok))
    return nums


def _label_names(issue):
    out = []
    for lbl in (issue.get("labels") or []):
        out.append(lbl.get("name", "") if isinstance(lbl, dict) else str(lbl))
    return out


def _sensitive_hits(title, body):
    """The deterministic guard, run on SERVER-FETCHED text only."""
    haystack = f"{title}\n{body}".lower()
    return sorted({p for p in SENSITIVE_PATTERNS if p in haystack})


def _auto_arm():
    return os.environ.get("WRIGHT_AUTO_ARM", "").strip() == "true"


def _post_reeve_signoff(arguments):
    """Post ONE verdict (comment + label) on a pending agent-brief issue,
    after validating the target at write time. The sign-off's entire write
    taxonomy — labels come from constants, never from arguments."""
    global _posted_this_run
    args = arguments or {}
    number = args.get("number")
    verdict = args.get("verdict")
    points = args.get("points")
    body = args.get("body")

    # --- input shape -------------------------------------------------------
    if isinstance(number, bool):
        return _tool_error("post_reeve_signoff: 'number' must be an integer issue number")
    if isinstance(number, str):
        if not number.strip().isdigit():
            return _tool_error(
                f"post_reeve_signoff: 'number' must be a positive integer (got {number!r})")
        number = int(number.strip())
    if not isinstance(number, int) or number <= 0:
        return _tool_error("post_reeve_signoff: 'number' is required (positive integer)")
    if verdict not in ("approve", "decline", "needs-human"):
        return _tool_error(
            f"post_reeve_signoff: 'verdict' must be approve/decline/needs-human (got {verdict!r})")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("post_reeve_signoff: 'body' is required (non-empty string)")
    if verdict == "approve":
        if isinstance(points, bool) or points not in VALID_POINTS:
            return _tool_error(
                f"post_reeve_signoff: an approve requires 'points' in {list(VALID_POINTS)} "
                f"(got {points!r}) — the roadmap board reads the size")

    # --- candidate-set binding (trusted Select step) -----------------------
    selected = _selected_issues()
    if selected is not None and number not in selected:
        return _tool_error(
            f"issue #{number} is not in this run's candidate set {sorted(selected)}; refusing")

    # --- per-run cap (unattended only) -------------------------------------
    if os.environ.get("GITHUB_RUN_ID", "").strip():
        try:
            cap = int(os.environ.get("SIGNOFF_MAX_VERDICTS", "3"))
        except ValueError:
            cap = 3
        if _posted_this_run >= cap:
            return _tool_error(
                f"per-run verdict cap reached ({_posted_this_run}/{cap}); refusing to post more")

    # --- re-read the target and enforce state at WRITE time ----------------
    try:
        issue = _get_issue(number)
    except urllib.error.HTTPError as e:
        return _tool_error(f"GitHub API error {e.code} reading issue #{number}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to read issue #{number}: {type(e).__name__}: {e}")
    if not issue:
        return _tool_error(f"issue #{number} not found")
    if "pull_request" in issue:
        return _tool_error(f"#{number} is a pull request, not an agent-brief issue; refusing")
    if issue.get("state") != "open":
        return _tool_error(f"issue #{number} is not open (state={issue.get('state')!r}); refusing")
    labels = _label_names(issue)
    if BRIEF_LABEL not in labels:
        return _tool_error(
            f"issue #{number} does not carry the '{BRIEF_LABEL}' label; refusing")
    ruled = [lbl for lbl in labels if lbl in VERDICT_LABELS]
    if ruled:
        return _tool_error(
            f"issue #{number} already carries a verdict label ({', '.join(ruled)}); "
            "refusing to re-judge")

    # --- duplicate guard — one sign-off comment per brief ------------------
    try:
        comments = _get_comments(number)
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to read comments on #{number}: {type(e).__name__}: {e}")
    if any(MARKER in (c.get("body") or "") for c in comments):
        return _tool_error(
            f"issue #{number} already carries a Reeve sign-off; refusing to duplicate")

    # --- the deterministic sensitive-path guard (server-fetched text) ------
    guard_note = ""
    effective = verdict
    hits = _sensitive_hits(issue.get("title", ""), issue.get("body", ""))
    if verdict == "approve" and hits:
        effective = "needs-human"
        guard_note = (
            "\n\n> ⚠️ **Sensitive-path guard**: the brief's own text mentions "
            "protection machinery (" + ", ".join(f"`{h}`" for h in hits) + "), "
            "so this approve was **downgraded to needs-human** — arming a "
            "change that touches the bench's fence is a human's call by "
            "construction. Resolve with the decision gate "
            "(`docs/decision-gate.md`) or arm by hand after review."
        )

    # --- advisory mode (WRIGHT_AUTO_ARM off) -------------------------------
    if effective == "approve" and not _auto_arm():
        effective = "needs-human"
        guard_note += (
            "\n\n> ℹ️ **Advisory mode** (`WRIGHT_AUTO_ARM` is off): approved "
            "on the merits, but parked with `needs-decision` instead of armed "
            "— a human arms it (apply `autonomy-ok`, or use the decision gate)."
        )

    # --- decide the labels (constants only) --------------------------------
    if effective == "approve":
        to_apply = ["autonomy-ok", f"points-{points}"]
    elif effective == "needs-human":
        to_apply = ["needs-decision"]
        if verdict == "approve" and points in VALID_POINTS:
            to_apply.append(f"points-{points}")
    else:  # decline
        to_apply = [DECLINED_LABEL]

    # --- write: labels FIRST (fail-closed), then the comment ---------------
    try:
        if DECLINED_LABEL in to_apply:
            _ensure_declined_label()
        _add_labels(number, to_apply)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} labeling #{number}: {detail}")
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to label #{number}: {type(e).__name__}: {e}")

    verdict_line = f"**Verdict: {verdict}**"
    if effective != verdict:
        verdict_line += f" → recorded as **{effective}**"
    verdict_line += f" · labels applied: {', '.join(f'`{l}`' for l in to_apply)}"
    full = f"{MARKER}\n{ADVISORY}\n\n{verdict_line}\n\n{body.strip()}{guard_note}\n"
    try:
        posted = _post_comment(number, full)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        # The label already landed — the verdict stands; the next run's select
        # excludes this brief by label, so a retry cannot double-rule it.
        return _tool_error(
            f"labels applied but the comment failed (GitHub {e.code}: {detail}) — "
            f"the verdict label on #{number} is the operative record")
    except Exception as e:  # noqa: BLE001
        return _tool_error(
            f"labels applied but the comment failed ({type(e).__name__}: {e}) — "
            f"the verdict label on #{number} is the operative record")

    _posted_this_run += 1
    url = posted.get("html_url", "(unknown url)")
    log(f"signed off #{number} as {effective} {url} ({_posted_this_run} this run)")
    return _tool_text(f"SIGNED-OFF #{number} verdict={verdict} recorded={effective} "
                      f"labels={','.join(to_apply)} {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "post_reeve_signoff",
        "description": (
            "Post Reeve's ONE sign-off verdict on a pending agent-brief issue: "
            "a comment plus the verdict's label, applied label-first. verdict "
            "'approve' arms the brief (autonomy-ok + points-<n>; a "
            "deterministic guard downgrades approves that touch protection "
            "machinery to needs-human), 'decline' labels wright-declined, "
            "'needs-human' labels needs-decision. The tool re-reads the target "
            "and refuses unless it is open, agent-brief-labeled, unruled, and "
            "in this run's candidate set; one verdict per brief, capped per "
            "run. The body is the judged reasoning — full markdown is fine."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "number": {
                    "type": "integer",
                    "description": "The agent-brief issue number to sign off.",
                },
                "verdict": {
                    "type": "string",
                    "enum": ["approve", "decline", "needs-human"],
                    "description": "Reeve's ruling on the brief.",
                },
                "points": {
                    "type": "integer",
                    "enum": [1, 2, 3],
                    "description": (
                        "Size for the roadmap board — required with verdict "
                        "'approve' (use the brief's own Size section unless "
                        "it is dishonest, then say so in the body)."
                    ),
                },
                "body": {
                    "type": "string",
                    "description": (
                        "The verdict's reasoning against the platform charter "
                        "(PM.md): which non-negotiables it touches, whether "
                        "the acceptance criteria are falsifiable, why this "
                        "size. Any markdown is fine."
                    ),
                },
            },
            "required": ["number", "verdict", "body"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"post_reeve_signoff": _post_reeve_signoff}


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


def _fresh_brief(n, title="Agent brief: t", body="a plain brief body"):
    return {"number": n, "state": "open", "title": title, "body": body,
            "labels": [{"name": BRIEF_LABEL}]}


def selftest():
    """Prove every write-surface invariant fires, offline — the negative-
    control discipline the perms-checks follow, applied to the one
    escalation-shaped write in the routine family."""
    global _posted_this_run, _FAKE_ISSUES, _FAKE_COMMENTS, _write_log
    os.environ["SIGNOFF_MCP_FAKE"] = "1"
    os.environ.pop("SIGNOFF_SELECTED_ISSUES", None)
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ["WRIGHT_AUTO_ARM"] = "true"
    fails = []

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    def err(res):
        return res.get("isError") is True

    def reset():
        global _FAKE_ISSUES, _FAKE_COMMENTS, _write_log, _posted_this_run
        _FAKE_ISSUES = {}
        _FAKE_COMMENTS = {}
        _write_log = []
        _posted_this_run = 0

    # Input guards.
    reset()
    _FAKE_ISSUES[1] = _fresh_brief(1)
    check("missing number is rejected",
          err(_post_reeve_signoff({"verdict": "decline", "body": "x"})))
    check("a boolean number is rejected",
          err(_post_reeve_signoff({"number": True, "verdict": "decline", "body": "x"})))
    check("an unknown verdict is rejected",
          err(_post_reeve_signoff({"number": 1, "verdict": "arm", "body": "x"})))
    check("missing body is rejected",
          err(_post_reeve_signoff({"number": 1, "verdict": "decline"})))
    check("an approve without points is rejected",
          err(_post_reeve_signoff({"number": 1, "verdict": "approve", "body": "x"})))
    check("an approve with points=5 is rejected",
          err(_post_reeve_signoff({"number": 1, "verdict": "approve", "points": 5,
                                   "body": "x"})))

    # State guards — the target is re-read and must be an open, unruled brief.
    reset()
    _FAKE_ISSUES[2] = {**_fresh_brief(2), "state": "closed"}
    _FAKE_ISSUES[3] = {"number": 3, "state": "open", "title": "t", "body": "b",
                       "labels": [{"name": "bug"}]}
    _FAKE_ISSUES[4] = {**_fresh_brief(4)}
    _FAKE_ISSUES[4]["labels"].append({"name": "autonomy-ok"})
    _FAKE_ISSUES[5] = {**_fresh_brief(5), "pull_request": {"url": "x"}}
    _FAKE_ISSUES[6] = _fresh_brief(6)
    _FAKE_COMMENTS[6] = [{"body": f"{MARKER}\nan earlier sign-off"}]
    check("a closed issue is rejected",
          err(_post_reeve_signoff({"number": 2, "verdict": "decline", "body": "x"})))
    check("a missing agent-brief label is rejected",
          err(_post_reeve_signoff({"number": 3, "verdict": "decline", "body": "x"})))
    check("an already-ruled brief (autonomy-ok) is rejected",
          err(_post_reeve_signoff({"number": 4, "verdict": "decline", "body": "x"})))
    check("a pull request is rejected",
          err(_post_reeve_signoff({"number": 5, "verdict": "decline", "body": "x"})))
    check("a duplicate (marker already present) is rejected",
          err(_post_reeve_signoff({"number": 6, "verdict": "decline", "body": "x"})))

    # Candidate-set binding (the trusted Select step).
    reset()
    _FAKE_ISSUES[7] = _fresh_brief(7)
    _FAKE_ISSUES[8] = _fresh_brief(8)
    os.environ["SIGNOFF_SELECTED_ISSUES"] = "7"
    check("a number outside the run's candidate set is rejected",
          err(_post_reeve_signoff({"number": 8, "verdict": "decline", "body": "x"})))
    check("a number inside the candidate set is allowed",
          _post_reeve_signoff({"number": 7, "verdict": "decline",
                               "body": "x"}).get("isError") is False)
    os.environ.pop("SIGNOFF_SELECTED_ISSUES", None)

    # Approve arms with the hardcoded labels, label-first, marker + framing.
    reset()
    _FAKE_ISSUES[10] = _fresh_brief(10)
    ok = _post_reeve_signoff({"number": 10, "verdict": "approve", "points": 2,
                              "body": "sound brief"})
    check("a clean approve succeeds", ok.get("isError") is False)
    check("approve applies exactly autonomy-ok + points-2",
          ("labels", 10, ("autonomy-ok", "points-2")) in _write_log)
    check("labels are applied BEFORE the comment (fail-closed ordering)",
          [w[0] for w in _write_log] == ["labels", "comment"])
    comment = next(w[2] for w in _write_log if w[0] == "comment")
    check("the comment carries the marker", MARKER in comment)
    check("the comment carries the advisory framing", "Reeve sign-off (auto)" in comment)

    # Decline and needs-human apply their labels.
    reset()
    _FAKE_ISSUES[11] = _fresh_brief(11)
    _FAKE_ISSUES[12] = _fresh_brief(12)
    _post_reeve_signoff({"number": 11, "verdict": "decline", "body": "weak gap"})
    _post_reeve_signoff({"number": 12, "verdict": "needs-human", "body": "charter call"})
    check("decline applies wright-declined",
          ("labels", 11, (DECLINED_LABEL,)) in _write_log)
    check("needs-human applies needs-decision",
          ("labels", 12, ("needs-decision",)) in _write_log)

    # THE GUARD: an approve on a brief whose SERVER-FETCHED body touches
    # protection machinery is downgraded — it must NOT arm.
    reset()
    _FAKE_ISSUES[13] = _fresh_brief(
        13, body="Great idea: relax .claude/labeler-settings.json so the labeler can push")
    r = _post_reeve_signoff({"number": 13, "verdict": "approve", "points": 1,
                             "body": "looks fine"})
    check("a sensitive approve still posts (as a downgrade)", r.get("isError") is False)
    labels13 = next(w[2] for w in _write_log if w[0] == "labels")
    check("the sensitive approve applied needs-decision, NOT autonomy-ok",
          "needs-decision" in labels13 and "autonomy-ok" not in labels13)
    comment13 = next(w[2] for w in _write_log if w[0] == "comment")
    check("the downgrade names the guard in the comment",
          "Sensitive-path guard" in comment13)
    # Negative control for the guard itself: a clean body must NOT trip it.
    check("the guard does not fire on a clean brief (no false downgrade)",
          not _sensitive_hits("Agent brief: clean", "adds a detector to tools/reeve"))
    # And it DOES fire on secrets and arming variables, case-insensitively.
    check("the guard fires on a secret name",
          _sensitive_hits("t", "wire up ZAI_KEY differently") == ["zai_key"])
    check("the guard fires on an arming variable",
          "labeler_enabled" in _sensitive_hits("t", "flip LABELER_ENABLED off"))

    # Advisory mode (WRIGHT_AUTO_ARM off): approve parks instead of arming.
    reset()
    os.environ["WRIGHT_AUTO_ARM"] = "false"
    _FAKE_ISSUES[14] = _fresh_brief(14)
    _post_reeve_signoff({"number": 14, "verdict": "approve", "points": 3,
                         "body": "sound brief"})
    labels14 = next(w[2] for w in _write_log if w[0] == "labels")
    check("advisory mode: approve applies needs-decision + points, never autonomy-ok",
          "needs-decision" in labels14 and "points-3" in labels14
          and "autonomy-ok" not in labels14)
    os.environ["WRIGHT_AUTO_ARM"] = "true"

    # Per-run cap (unattended: GITHUB_RUN_ID set).
    reset()
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    os.environ["SIGNOFF_MAX_VERDICTS"] = "1"
    _FAKE_ISSUES[15] = _fresh_brief(15)
    _FAKE_ISSUES[16] = _fresh_brief(16)
    r1 = _post_reeve_signoff({"number": 15, "verdict": "decline", "body": "x"})
    r2 = _post_reeve_signoff({"number": 16, "verdict": "decline", "body": "x"})
    check("the cap lets through up to SIGNOFF_MAX_VERDICTS", r1.get("isError") is False)
    check("the cap refuses past SIGNOFF_MAX_VERDICTS",
          err(r2) and "cap reached" in r2["content"][0]["text"])
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop("SIGNOFF_MAX_VERDICTS", None)

    # The JSON-RPC surface exposes exactly the one tool.
    check("tools/list exposes exactly post_reeve_signoff",
          [t["name"] for t in TOOLS] == ["post_reeve_signoff"])

    if fails:
        print(f"\nsignoff_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nsignoff_mcp selftest passed")
    return 0


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    log(f"starting (repo={os.environ.get('GITHUB_REPOSITORY', '?')}, "
        f"run={os.environ.get('GITHUB_RUN_ID', 'attended')}, "
        f"auto_arm={_auto_arm()})")
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
