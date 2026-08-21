#!/usr/bin/env python3
"""assessor_mcp.py — the adoption-study assessor's write surface, a stdio MCP tool.

WHY THIS EXISTS (the comment-body command-line dead end)
-------------------------------------------------------
The assessor's only write is "post ONE advisory split-verdict COMMENT on a filed
`adoption-study` issue", and that verdict is a full multi-line markdown body
(headings, a redundant / additive / where-integration structure, tables with `|`
pipes, blank lines). A Bash `gh issue comment --body '...'` with table pipes and
newlines is DENIED on a command line under `--permission-mode dontAsk` no matter
how it is quoted — the same Actions permission-matcher bug scout_mcp.py documents
(a rich multi-line argument reads as shell structure the matcher cannot verify).
An MCP tool takes its arguments as JSON over a stdio pipe — never on a shell
command line — so the body can be arbitrary markdown. The assessor's READ verbs
stay on assessor-helper.sh (their args are trivial and pass fine).

SECURITY (this is the write surface; the run reads UNTRUSTED issue text)
-----------------------------------------------------------------------
The assessor run reads untrusted issue/comment text while holding a provider key
and a GitHub token, so this server does NOT trust its inputs. It validates the
TARGET at write time rather than trusting the issue number the model supplies:
  * it RE-READS the target issue immediately before posting and requires it to be
    OPEN, still carry the `adoption-study` label, and carry NO `disposition:*`
    label — so a stale or prompt-injected run can never comment on a closed or
    already-ruled study (the read wrapper's `list-awaiting` is a convenience,
    never the enforcement boundary, since the model supplies the number later);
  * when the trusted workflow Select step exports `ASSESSOR_SELECTED_ISSUES`, the
    tool refuses any number NOT in that run's candidate set;
  * it refuses a DUPLICATE — if the issue already carries an assessor comment
    (detected by a hidden marker the tool prepends), it will not post again;
  * every posted body is prepended with the ADVISORY framing and the marker, so
    the comment is always a recognisable auto-draft a human still dispositions;
  * it applies NO label (the disposition stays the human's call), its only
    GitHub write is `POST /issues/{n}/comments` on the CURRENT repo, and a per-run
    cap bounds how many comments one run can post.
The run allow-lists ONLY this tool (`mcp__assessor__post_adoption_disposition`),
the wrapper's read verbs, and the read-only file tools — never `Write`, never a
general `Bash`. Stdlib only (no pip install in the unattended run); logs go to
stderr so stdout carries nothing but JSON-RPC.
"""

import json
import os
import sys
import urllib.error
import urllib.request

ADOPTION_STUDY_LABEL = "adoption-study"
DISPOSITION_PREFIX = "disposition:"
# Hidden marker the tool stamps on every comment it posts. The duplicate guard
# looks for it, so one study gets at most one assessor comment.
MARKER = "<!-- adoption-assessor:v1 -->"
ADVISORY = (
    "> **Auto-drafted advisory verdict** — the adoption-study assessor "
    "(`/adoption-assessor`) drafted this reading of the study against the bench's "
    "deterministic baseline. It is *advisory*: a human still applies the "
    "`disposition:*` label and decides. See `docs/adoption-studies.md`."
)
GITHUB_API = "https://api.github.com"
SERVER_NAME = "assessor"
# Fallback protocol version if the client does not announce one; otherwise we
# echo the client's requested version (the most compatible choice).
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# Per-run cap — GITHUB_RUN_ID is set and stable across one Actions run and this
# process lives for that whole run, so an in-process counter is naturally
# run-scoped. Attended (no run id) the cap is skipped — a human is the trust
# boundary, the same posture the scout and wrapper take.
_posted_this_run = 0

# Captured by the selftest so it can assert the exact comment body (the advisory
# framing + marker) without a network call. `None` in normal operation.
_last_comment = None

# Fake state for the offline selftest (ASSESSOR_MCP_FAKE): issue metadata and
# comments the network helpers read instead of GitHub.
_FAKE_ISSUES = {}
_FAKE_COMMENTS = {}


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"assessor_mcp: {msg}", file=sys.stderr, flush=True)


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
    req.add_header("User-Agent", "print-bench-adoption-assessor")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def _get_issue(number):
    if os.environ.get("ASSESSOR_MCP_FAKE"):
        return _FAKE_ISSUES.get(number)
    return _api("GET", f"/repos/{_repo()}/issues/{number}")


def _get_comments(number):
    if os.environ.get("ASSESSOR_MCP_FAKE"):
        return list(_FAKE_COMMENTS.get(number, []))
    # Walk EVERY page. The duplicate guard scans the returned comments for the
    # assessor's MARKER, and on a long study thread an earlier assessor comment
    # can fall past the first 100 — a single page would miss it and post twice.
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
        if page > 50:  # bound the walk; a study thread is never this long
            break
    return out


def _post_comment(number, body):
    """POST one issue comment on the CURRENT repo. No label is touched.
    ASSESSOR_MCP_FAKE short-circuits the network for the selftest."""
    global _last_comment
    _last_comment = {"number": number, "body": body}
    if os.environ.get("ASSESSOR_MCP_FAKE"):
        _FAKE_COMMENTS.setdefault(number, []).append({"body": body})
        return {"html_url": f"https://example.invalid/{number}", "id": 0}
    return _api("POST", f"/repos/{_repo()}/issues/{number}/comments", {"body": body})


def _selected_issues():
    """The trusted workflow Select step exports ASSESSOR_SELECTED_ISSUES (space-
    or comma-separated digits) — the run's candidate set. Returns a set, or None
    when unset (attended: a human is the trust boundary, no binding)."""
    raw = os.environ.get("ASSESSOR_SELECTED_ISSUES", "").strip()
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


def _post_adoption_disposition(arguments):
    """Post ONE advisory split-verdict comment on a filed adoption-study issue,
    after validating the target at write time. The assessor's entire write
    taxonomy — it applies no label and touches no other repo."""
    global _posted_this_run
    args = arguments or {}
    number = args.get("number")
    body = args.get("body")

    # --- input shape -------------------------------------------------------
    if isinstance(number, bool):
        return _tool_error("post_adoption_disposition: 'number' must be an integer issue number")
    if isinstance(number, str):
        if not number.strip().isdigit():
            return _tool_error(
                f"post_adoption_disposition: 'number' must be a positive integer (got {number!r})"
            )
        number = int(number.strip())
    if not isinstance(number, int) or number <= 0:
        return _tool_error("post_adoption_disposition: 'number' is required (positive integer)")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("post_adoption_disposition: 'body' is required (non-empty string)")

    # --- candidate-set binding (trusted Select step) -----------------------
    selected = _selected_issues()
    if selected is not None and number not in selected:
        return _tool_error(
            f"issue #{number} is not in this run's candidate set {sorted(selected)}; refusing"
        )

    # --- per-run cap (unattended only) -------------------------------------
    if os.environ.get("GITHUB_RUN_ID", "").strip():
        try:
            cap = int(os.environ.get("ASSESSOR_MAX_DISPOSITIONS", "5"))
        except ValueError:
            cap = 5
        if _posted_this_run >= cap:
            return _tool_error(
                f"per-run disposition cap reached ({_posted_this_run}/{cap}); refusing to post more"
            )

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
        return _tool_error(f"#{number} is a pull request, not an adoption-study issue; refusing")
    if issue.get("state") != "open":
        return _tool_error(f"issue #{number} is not open (state={issue.get('state')!r}); refusing")
    labels = _label_names(issue)
    if ADOPTION_STUDY_LABEL not in labels:
        return _tool_error(
            f"issue #{number} does not carry the '{ADOPTION_STUDY_LABEL}' label; refusing"
        )
    disp = [lbl for lbl in labels if lbl.startswith(DISPOSITION_PREFIX)]
    if disp:
        return _tool_error(
            f"issue #{number} already has a disposition ({', '.join(disp)}); a human already ruled it"
        )

    # --- duplicate guard — one assessor comment per study ------------------
    try:
        comments = _get_comments(number)
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to read comments on #{number}: {type(e).__name__}: {e}")
    if any(MARKER in (c.get("body") or "") for c in comments):
        return _tool_error(
            f"issue #{number} already carries an assessor disposition; refusing to duplicate"
        )

    # --- post — advisory framing + marker prepended ------------------------
    full = f"{MARKER}\n{ADVISORY}\n\n{body.strip()}\n"
    try:
        posted = _post_comment(number, full)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} commenting on #{number}: {detail}")
    except Exception as e:  # noqa: BLE001
        return _tool_error(f"failed to comment on #{number}: {type(e).__name__}: {e}")

    _posted_this_run += 1
    url = posted.get("html_url", "(unknown url)")
    log(f"posted disposition on #{number} {url} ({_posted_this_run} this run)")
    return _tool_text(f"POSTED disposition on #{number} {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "post_adoption_disposition",
        "description": (
            "Post ONE advisory split-verdict COMMENT on a filed adoption-study "
            "issue on this repository. The body is passed as a JSON argument (not a "
            "shell command line), so it may be a full multi-line markdown verdict "
            "with tables. The tool re-reads the target and refuses unless it is "
            "open, carries the 'adoption-study' label, and has no 'disposition:*' "
            "label; it applies NO label and posts at most one comment per study. "
            "Returns 'POSTED disposition on #<n> <url>'. A human still applies the "
            "disposition label and decides — this comment is advisory."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "number": {
                    "type": "integer",
                    "description": "The adoption-study issue number to comment on.",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "The split-verdict markdown: Redundant / Additive / Where "
                        "integration makes sense, plus qualifying questions, in the "
                        "shape of issue #332. Any markdown is fine — tables, pipes, "
                        "backticks, newlines."
                    ),
                },
            },
            "required": ["number", "body"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"post_adoption_disposition": _post_adoption_disposition}


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
        # Notifications (no id) get no response.
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
    """Prove the write surface's security invariants fire, offline. A guard that
    is never exercised can be weakened and every other check stays green (the
    repo's standing rule), so these are the cases a live run cannot show."""
    global _posted_this_run, _FAKE_ISSUES, _FAKE_COMMENTS
    os.environ["ASSESSOR_MCP_FAKE"] = "1"
    os.environ.pop("ASSESSOR_SELECTED_ISSUES", None)
    os.environ.pop("GITHUB_RUN_ID", None)
    fails = []

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    def err(res):
        return res.get("isError") is True

    _FAKE_ISSUES = {
        1: {"number": 1, "state": "open", "labels": [{"name": "adoption-study"}]},
        2: {"number": 2, "state": "closed", "labels": [{"name": "adoption-study"}]},
        3: {"number": 3, "state": "open", "labels": [{"name": "bug"}]},
        4: {"number": 4, "state": "open",
            "labels": [{"name": "adoption-study"}, {"name": "disposition:worth-raising"}]},
        5: {"number": 5, "state": "open", "labels": [{"name": "adoption-study"}]},
        6: {"number": 6, "state": "open", "labels": [{"name": "adoption-study"}]},
        7: {"number": 7, "state": "open", "labels": [{"name": "adoption-study"}]},
        8: {"number": 8, "state": "open", "labels": [{"name": "adoption-study"}],
            "pull_request": {"url": "x"}},
    }
    _FAKE_COMMENTS = {5: [{"body": f"{MARKER}\nan earlier assessor comment"}]}

    # Input guards.
    check("missing number is rejected", err(_post_adoption_disposition({"body": "x"})))
    check("non-numeric number is rejected",
          err(_post_adoption_disposition({"number": "abc", "body": "x"})))
    check("missing body is rejected", err(_post_adoption_disposition({"number": 1})))
    check("a boolean number is rejected (bool is an int subclass in Python)",
          err(_post_adoption_disposition({"number": True, "body": "x"})))
    check("a non-positive number is rejected",
          err(_post_adoption_disposition({"number": 0, "body": "x"})))

    # A valid post succeeds and stamps the advisory framing + marker.
    _posted_this_run = 0
    ok = _post_adoption_disposition({"number": 1, "body": "## Redundant\n| a | b |\n..."})
    check("a well-formed disposition posts", ok.get("isError") is False)
    check("the posted body carries the marker",
          _last_comment and MARKER in _last_comment["body"])
    check("the posted body carries the advisory framing",
          _last_comment and "advisory" in _last_comment["body"].lower())

    # State guards — the target is re-read and must be an open, undecided study.
    check("a closed issue is rejected", err(_post_adoption_disposition({"number": 2, "body": "x"})))
    check("a missing adoption-study label is rejected",
          err(_post_adoption_disposition({"number": 3, "body": "x"})))
    check("an already-dispositioned issue is rejected",
          err(_post_adoption_disposition({"number": 4, "body": "x"})))
    check("a duplicate (marker already present) is rejected",
          err(_post_adoption_disposition({"number": 5, "body": "x"})))
    check("a pull request is rejected", err(_post_adoption_disposition({"number": 8, "body": "x"})))

    # Candidate-set binding (the trusted Select step).
    os.environ["ASSESSOR_SELECTED_ISSUES"] = "6"
    check("a number outside the run's candidate set is rejected",
          err(_post_adoption_disposition({"number": 7, "body": "x"})))
    check("a number inside the candidate set is allowed",
          _post_adoption_disposition({"number": 6, "body": "x"}).get("isError") is False)
    os.environ.pop("ASSESSOR_SELECTED_ISSUES", None)

    # Per-run cap (unattended: GITHUB_RUN_ID set).
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    os.environ["ASSESSOR_MAX_DISPOSITIONS"] = "1"
    _posted_this_run = 0
    _FAKE_ISSUES[10] = {"number": 10, "state": "open", "labels": [{"name": "adoption-study"}]}
    _FAKE_ISSUES[11] = {"number": 11, "state": "open", "labels": [{"name": "adoption-study"}]}
    r1 = _post_adoption_disposition({"number": 10, "body": "x"})
    r2 = _post_adoption_disposition({"number": 11, "body": "x"})
    check("the cap lets through up to ASSESSOR_MAX_DISPOSITIONS", r1.get("isError") is False)
    check("the cap refuses past ASSESSOR_MAX_DISPOSITIONS",
          err(r2) and "cap reached" in r2["content"][0]["text"])
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop("ASSESSOR_MAX_DISPOSITIONS", None)

    # The JSON-RPC surface exposes exactly the one tool.
    check("tools/list exposes exactly post_adoption_disposition",
          [t["name"] for t in TOOLS] == ["post_adoption_disposition"])

    if fails:
        print(f"\nassessor_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nassessor_mcp selftest passed")
    return 0


def main():
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    log(f"starting (repo={os.environ.get('GITHUB_REPOSITORY', '?')}, "
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
