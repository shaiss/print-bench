#!/usr/bin/env python3
"""wright_mcp.py — Wright's issue-filing surface, as a stdio MCP tool.

WHY THIS EXISTS (the same command-line dead end the scout hit)
--------------------------------------------------------------
Wright's only write is "file one agent-brief issue", and its body is a full
multi-line markdown brief (headings, an acceptance-criteria list, blank
lines, backticked paths). Under `--permission-mode dontAsk` the Bash matcher
denies any command whose argument reads as shell structure — a table pipe or
an embedded newline is enough, no quoting fixes it (proven on the scout,
scout_mcp.py's header). An MCP tool takes its arguments as JSON over a stdio
pipe — never on a shell command line — so the body can be arbitrary markdown.
Wright's READ verbs stay on wright-helper.sh (trivial args pass the matcher
fine); only the WRITE lives here.

SECURITY (mirrors scout_mcp.py, since this is the write surface)
----------------------------------------------------------------
The Wright run reads UNTRUSTED issue text while holding a GitHub token, so
this server does NOT trust its inputs and cannot be steered into anything but
filing an `agent-brief` issue:
  * the label is HARDCODED to `agent-brief` — the tool applies no other, so a
    prompt-injected run can never mint an `autonomy-ok` / `needs-decision` /
    `wright-declined` issue (arming is Reeve's sign-off, parking is the human
    gate, declining is the judge's — none of them the proposer's);
  * the title MUST start with `Agent brief:` — output is always a
    recognisable Wright proposal a human (and Reeve) can find and cull;
  * a per-run cap (`WRIGHT_MAX_BRIEFS`, default 1) bounds how many issues one
    run can file — a run-scoped in-process counter the agent cannot reach or
    reset, so at worst a hijacked run files a bounded number of proposals,
    noise Reeve declines, never an escalation;
  * its GitHub writes are `POST /issues` on the CURRENT repo plus an
    idempotent ensure-label for `agent-brief` only — it never edits an
    existing issue's labels, never touches another repo, and pushes no code.
The run allow-lists ONLY this tool (`mcp__wright__file_agent_brief`), the
wrapper's read verbs, and the read-only file tools — never `Write`, never a
general `Bash`; the deny backstop (.claude/wright-settings.json) additionally
denies the SIGN-OFF tool's server, so the proposer can never judge its own
briefs. Stdlib only (no pip install in the unattended run); logs go to stderr
so stdout carries nothing but JSON-RPC.
"""

import json
import os
import sys
import urllib.error
import urllib.request

BRIEF_LABEL = "agent-brief"
BRIEF_LABEL_COLOR = "8250DF"
BRIEF_LABEL_DESC = "Well-formed tooling/agent brief awaiting Reeve's sign-off (the agent forge)"
TITLE_PREFIX = "Agent brief:"
GITHUB_API = "https://api.github.com"
SERVER_NAME = "wright"
# Fallback protocol version if the client does not announce one; otherwise we
# echo the client's requested version (the most compatible choice).
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# Per-run cap. GITHUB_RUN_ID is set and stable across one Actions run and this
# process lives for that whole run, so an in-process counter is naturally
# run-scoped. Attended (no run id) the cap is skipped — a human is the trust
# boundary, the same posture the scout takes.
_filed_this_run = 0

# Captured by the selftest so it can assert the exact POST payload (the label
# hardcode) without a network call. `None` in normal operation.
_last_payload = None


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"wright_mcp: {msg}", file=sys.stderr, flush=True)


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
    req.add_header("User-Agent", "print-bench-wright")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


def _ensure_brief_label():
    """Create the agent-brief label if missing — the ONE label this server may
    ever create, from constants. Idempotent: an already-exists 422 is fine."""
    if os.environ.get("WRIGHT_MCP_FAKE"):
        return
    try:
        _api("POST", f"/repos/{_repo()}/labels",
             {"name": BRIEF_LABEL, "color": BRIEF_LABEL_COLOR,
              "description": BRIEF_LABEL_DESC})
    except urllib.error.HTTPError as e:
        if e.code != 422:  # 422 = already exists — the state we want
            raise


def _create_issue(title, body):
    """POST one issue with the HARDCODED agent-brief label. The label is set
    here, from a constant, never from caller input — so no argument can change
    or add a label. WRIGHT_MCP_FAKE short-circuits the network for the
    selftest (it is never set in the workflow)."""
    global _last_payload
    payload = {"title": title, "body": body, "labels": [BRIEF_LABEL]}
    _last_payload = payload
    if os.environ.get("WRIGHT_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake", "number": 0}
    _ensure_brief_label()
    return _api("POST", f"/repos/{_repo()}/issues", payload)


def _file_agent_brief(arguments):
    """Create ONE agent-brief issue. Wright's entire write taxonomy."""
    global _filed_this_run
    title = (arguments or {}).get("title")
    body = (arguments or {}).get("body")
    if not isinstance(title, str) or not title.strip():
        return _tool_error("file_agent_brief: 'title' is required (non-empty string)")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("file_agent_brief: 'body' is required (non-empty string)")
    title = title.strip()
    if not title.startswith(TITLE_PREFIX):
        return _tool_error(
            f"file_agent_brief: title must start with '{TITLE_PREFIX}' (got {title!r})"
        )

    # Per-run cap — enforced only inside an Actions run (the unattended case
    # the cap exists to bound); attended, a human is the trust boundary.
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if run_id:
        try:
            cap = int(os.environ.get("WRIGHT_MAX_BRIEFS", "1"))
        except ValueError:
            cap = 1
        if _filed_this_run >= cap:
            return _tool_error(
                f"per-run brief cap reached ({_filed_this_run}/{cap}); refusing to file more"
            )

    try:
        issue = _create_issue(title, body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} filing brief: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to file brief: {type(e).__name__}: {e}")

    _filed_this_run += 1
    url = issue.get("html_url", "(unknown url)")
    number = issue.get("number", "?")
    log(f"filed #{number} {url} ({_filed_this_run} this run)")
    return _tool_text(f"FILED #{number} {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "file_agent_brief",
        "description": (
            "File ONE agent-brief issue on this repository — a proposal for a "
            "new probabilistic agent, deterministic tool, or hybrid, awaiting "
            "Reeve's sign-off. The body is passed as a JSON argument (not a "
            "shell command line), so it may be a full multi-line markdown "
            "brief. The 'agent-brief' label is applied automatically and is "
            "the only label this tool can set; the title must start with "
            "'Agent brief:'. Returns 'FILED #<n> <url>'. One call files one "
            "issue; call it once per proposal, up to the per-run cap."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Issue title, must start with 'Agent brief:'.",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Full markdown body matching templates/agent-brief.md, "
                        "section for section. Any markdown is fine here — "
                        "tables, pipes, backticks, newlines, apostrophes."
                    ),
                },
            },
            "required": ["title", "body"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"file_agent_brief": _file_agent_brief}


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
    """Prove the write surface's security invariants fire, offline. A guard
    that is never exercised can be weakened and every other check stays green
    (the repo's standing rule), so these are the cases a live run cannot show."""
    global _filed_this_run, _last_payload
    os.environ["WRIGHT_MCP_FAKE"] = "1"
    os.environ.pop("GITHUB_RUN_ID", None)
    fails = []

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    # Input guards reject and file nothing.
    check("missing title is rejected",
          _file_agent_brief({"body": "x"}).get("isError") is True)
    check("missing body is rejected",
          _file_agent_brief({"title": "Agent brief: x"}).get("isError") is True)
    check("title without the 'Agent brief:' prefix is rejected",
          _file_agent_brief({"title": "sneak in", "body": "x"}).get("isError") is True)
    check("a 'Design brief:' title is rejected (Wright cannot pose as the scout)",
          _file_agent_brief({"title": "Design brief: x", "body": "x"}).get("isError") is True)

    # A valid call files and stamps the hardcoded label — no caller input can
    # change it (there is no label argument to pass).
    _filed_this_run = 0
    ok = _file_agent_brief({"title": "Agent brief: good one",
                            "body": "## Gap\n| a | b |\nyes"})
    check("a well-formed brief files", ok.get("isError") is False)
    check("the filed label is hardcoded to agent-brief",
          _last_payload == {"title": "Agent brief: good one",
                            "body": "## Gap\n| a | b |\nyes",
                            "labels": [BRIEF_LABEL]})

    # The per-run cap fires inside an Actions run (GITHUB_RUN_ID set).
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    os.environ["WRIGHT_MAX_BRIEFS"] = "1"
    _filed_this_run = 0
    r1 = _file_agent_brief({"title": "Agent brief: one", "body": "b"})
    r2 = _file_agent_brief({"title": "Agent brief: two", "body": "b"})
    check("cap lets through up to WRIGHT_MAX_BRIEFS", r1.get("isError") is False)
    check("cap refuses the brief past WRIGHT_MAX_BRIEFS",
          r2.get("isError") is True and "cap reached" in r2["content"][0]["text"])
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop("WRIGHT_MAX_BRIEFS", None)

    # The JSON-RPC surface exposes exactly the one tool.
    check("tools/list exposes exactly file_agent_brief",
          [t["name"] for t in TOOLS] == ["file_agent_brief"])

    if fails:
        print(f"\nwright_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nwright_mcp selftest passed")
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
