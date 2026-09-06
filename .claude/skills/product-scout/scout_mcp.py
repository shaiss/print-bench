#!/usr/bin/env python3
"""scout_mcp.py — the product scout's issue-filing surface, as a stdio MCP tool.

WHY THIS EXISTS (issue: the file-brief command-line dead end)
-------------------------------------------------------------
The scout's only write is "file one design-brief issue", and its body is a full
multi-line markdown brief (headings, a Must-fit TABLE with `|` pipes, blank
lines). We first routed that through a Bash wrapper (`scout-helper.sh
file-brief`) under `--permission-mode dontAsk`. The wrapper is allow-listed, yet
every file-brief call was DENIED while the read verbs passed — because the
Actions permission matcher inspects the *command string* and a rich multi-line
argument (table pipes and/or embedded newlines) reads as shell structure it
cannot verify, no matter how the body is quoted. Proven from the run's verbatim
`permission_denials`: bare `scout-helper.sh list-briefs` allowed,
`scout-helper.sh file-brief --title '...' --body '## What it is\n\n| ... |'`
denied.

An MCP tool takes its arguments as JSON over a stdio pipe — never on a shell
command line — so the body can be arbitrary markdown and the whole class of
matcher bug disappears. The scout's READ verbs stay on the wrapper (their args
are trivial and pass fine); only the WRITE moves here.

SECURITY (mirrors the wrapper's guarantees, since this is now the write surface)
--------------------------------------------------------------------------------
The scout run reads UNTRUSTED issue text while holding a GitHub token, so this
server does NOT trust its inputs and cannot be steered into anything but filing a
`design-brief` issue:
  * the label is HARDCODED to `design-brief` — the tool applies no other, so a
    prompt-injected run can never mint an `autonomy-ok` / `declined-too-big` /
    `needs-decision` issue (arming, chunking, parking are decisions the scout
    does not get to make);
  * the title MUST start with `Design brief:` — output is always a recognisable
    scout proposal a human can find and cull;
  * a per-run cap (`SCOUT_MAX_BRIEFS`, default 3) bounds how many issues one run
    can file — counted in a state file every link step of the chain walk shares
    (`SCOUT_CAP_STATE`, the reeve.yml `REEVE_GREENLIGHT_STATE` pattern; issue
    #565), so the bound spans the whole walk and not one server process. The
    agent can neither set env vars nor write files, so it cannot reach or reset
    the count; at worst a hijacked run files a bounded number of proposals,
    noise a human closes, never an escalation;
  * the only GitHub call is `POST /issues` on the CURRENT repo — it never edits
    an existing issue's labels, never removes a label, never touches another
    repo, and pushes no code.
The run allow-lists ONLY this tool (`mcp__scout__file_design_brief`), the
wrapper's read verbs, and the read-only file tools — never `Write`, never a
general `Bash`. Stdlib only (no pip install in the unattended run); logs go to
stderr so stdout carries nothing but JSON-RPC.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

BRIEF_LABEL = "design-brief"
TITLE_PREFIX = "Design brief:"
GITHUB_API = "https://api.github.com"
SERVER_NAME = "scout"
# Fallback protocol version if the client does not announce one. We otherwise
# echo the client's requested version, which is the most compatible choice.
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# --- The walk-spanning brief cap (issue #565) --------------------------------
#
# Every link of a chain walk is its own claude-code-action step, so this server
# process — and anything in-process — restarts at link N+1. An in-process
# counter therefore caps ONE LINK, not the run: a link that files up to the cap
# and then dies (agent error, step timeout) hands the next link a fresh counter
# with the same prompt, so a 3-link walk could file up to 3x the cap. The count
# must live where every link can see it: a state file the workflow names via
# SCOUT_CAP_STATE, one path shared by every link step of the job (the reeve.yml
# REEVE_GREENLIGHT_STATE precedent). runner.temp is fresh per job, so the file
# is run-scoped and never persists across runs.
#
# SIBLING ADOPTION (#549's splits — wright, growth-queue, reeve-signoff,
# adoption-assessor, growth-twitter): lift the three functions below verbatim
# under your own env-var name. They are deliberately self-contained — stdlib
# only, no scout-specific coupling — so adoption is a copy plus the CAP_STATE_ENV
# constant, not a re-derivation of the mechanism.
CAP_STATE_ENV = "SCOUT_CAP_STATE"


def _cap_state_path():
    """The shared state-file path for this run, or None attended.

    Attended (no GITHUB_RUN_ID) the cap is skipped entirely — a human is the
    trust boundary — so no state file is required. Unattended the path comes
    from the env var the workflow sets; an empty value is returned as-is so the
    caller can refuse: filing on without it would silently fall back to
    per-process counting, which is exactly the per-link reset this mechanism
    exists to kill.
    """
    if not os.environ.get("GITHUB_RUN_ID", "").strip():
        return None
    return os.environ.get(CAP_STATE_ENV, "").strip()


def _cap_state_count(path):
    """How many briefs this run has already filed, per the shared state file.

    One JSON record per successful write, so the count is the number of
    non-empty lines; an absent file is a run that has filed nothing yet (the
    first successful write creates it). Any other read failure raises — an
    unreadable state must refuse, never count as zero.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except FileNotFoundError:
        return 0
    except OSError as e:
        raise RuntimeError(f"cannot read {CAP_STATE_ENV} file {path}: {e}") from e


def _cap_state_record(path, number, url):
    """Append ONE record — only ever AFTER a successful filing, so refused and
    failed attempts never consume the cap (the greenlight wrapper's rule). The
    record doubles as the audit trail of what a link that later died filed."""
    rec = {"issue": number, "url": url,
           "filed_at": datetime.now(timezone.utc).isoformat()}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"scout_mcp: {msg}", file=sys.stderr, flush=True)


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
    req.add_header("User-Agent", "print-bench-product-scout")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


# Captured by the selftest so it can assert the exact POST payload (the label
# hardcode) without a network call. `None` in normal operation.
_last_payload = None


def _create_issue(title, body):
    """POST one issue with the HARDCODED design-brief label. The label is set
    here, from a constant, never from caller input — so no argument can change
    or add a label. SCOUT_MCP_FAKE short-circuits the network for the selftest
    (it is never set in the workflow)."""
    global _last_payload
    payload = {"title": title, "body": body, "labels": [BRIEF_LABEL]}
    _last_payload = payload
    if os.environ.get("SCOUT_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake", "number": 0}
    return _api("POST", f"/repos/{_repo()}/issues", payload)


def _file_design_brief(arguments):
    """Create ONE design-brief issue. The scout's entire write taxonomy."""
    title = (arguments or {}).get("title")
    body = (arguments or {}).get("body")
    if not isinstance(title, str) or not title.strip():
        return _tool_error("file_design_brief: 'title' is required (non-empty string)")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("file_design_brief: 'body' is required (non-empty string)")
    title = title.strip()
    if not title.startswith(TITLE_PREFIX):
        return _tool_error(
            f"file_design_brief: title must start with '{TITLE_PREFIX}' (got {title!r})"
        )

    # Per-run cap — enforced only inside an Actions run (the unattended case
    # the cap exists to bound); attended, a human is the trust boundary. The
    # count is read from the shared state file so it spans the whole chain
    # walk, not this one server process (#565).
    state = _cap_state_path()
    if state is not None:
        if not state:
            return _tool_error(
                f"file_design_brief: {CAP_STATE_ENV} is not set but this is an "
                "unattended run (GITHUB_RUN_ID is set) — the workflow must give "
                "every link step the same state-file path (the reeve.yml "
                "REEVE_GREENLIGHT_STATE pattern) or the brief cap cannot span "
                "the chain walk; refusing to file"
            )
        try:
            cap = int(os.environ.get("SCOUT_MAX_BRIEFS", "3"))
        except ValueError:
            cap = 3
        try:
            filed = _cap_state_count(state)
        except RuntimeError as e:
            return _tool_error(f"file_design_brief: {e}")
        if filed >= cap:
            return _tool_error(
                f"per-run brief cap reached ({filed}/{cap} filed across the "
                "chain walk so far); refusing to file more"
            )

    try:
        issue = _create_issue(title, body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} filing brief: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to file brief: {type(e).__name__}: {e}")

    url = issue.get("html_url", "(unknown url)")
    number = issue.get("number", "?")
    if state:
        try:
            _cap_state_record(state, number, url)
        except OSError as e:
            log(f"WARNING: filed #{number} but could not append its "
                f"{CAP_STATE_ENV} record ({e}) — this filing will not count "
                f"toward the walk cap")
    log(f"filed #{number} {url}")
    return _tool_text(f"FILED #{number} {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "file_design_brief",
        "description": (
            "File ONE design-brief issue on this repository. The body is passed as "
            "a JSON argument (not a shell command line), so it may be a full "
            "multi-line markdown brief with tables. The 'design-brief' label is "
            "applied automatically and is the only label this tool can set; the "
            "title must start with 'Design brief:'. Returns 'FILED #<n> <url>'. "
            "One call files one issue; call it once per proposal, up to the "
            "per-run cap."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Issue title, must start with 'Design brief:'.",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Full markdown body matching templates/design-brief.md, "
                        "section for section. Any markdown is fine here — tables, "
                        "pipes, backticks, newlines, apostrophes."
                    ),
                },
            },
            "required": ["title", "body"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"file_design_brief": _file_design_brief}


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

    # Notifications (no id) get no response.
    if msg_id is None and method != "" and method is not None and "id" not in msg:
        if method and method.startswith("notifications/"):
            return None
        # Some clients send other id-less messages; ignore quietly.
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
    os.environ["SCOUT_MCP_FAKE"] = "1"
    fails = []

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

    # Pin the environment: each case below decides attended/unattended itself,
    # so an ambient Actions GITHUB_RUN_ID (this selftest runs inside CI) must
    # not leak into the attended cases.
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop(CAP_STATE_ENV, None)

    # Input guards reject and file nothing.
    check("missing title is rejected",
          _file_design_brief({"body": "x"}).get("isError") is True)
    check("missing body is rejected",
          _file_design_brief({"title": "Design brief: x"}).get("isError") is True)
    check("title without the 'Design brief:' prefix is rejected",
          _file_design_brief({"title": "sneak in", "body": "x"}).get("isError") is True)

    # A valid call files and stamps the hardcoded label — no caller input can
    # change it (there is no label argument to pass). Attended here (no run
    # id): the cap is skipped and no state file is required.
    ok = _file_design_brief({"title": "Design brief: good one", "body": "## What\n| a | b |\nyes"})
    check("a well-formed brief files", ok.get("isError") is False)
    check("the filed label is hardcoded to design-brief",
          _last_payload == {"title": "Design brief: good one",
                            "body": "## What\n| a | b |\nyes", "labels": [BRIEF_LABEL]})

    # The walk-spanning cap (issue #565), inside an Actions run.
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    os.environ["SCOUT_MAX_BRIEFS"] = "2"

    # Unwired: run id set but no state path. Fail closed — per-process
    # counting is exactly the per-link reset the state file replaces.
    r = _file_design_brief({"title": "Design brief: unwired", "body": "b"})
    check("an unattended run without SCOUT_CAP_STATE refuses (fail closed)",
          r.get("isError") is True and CAP_STATE_ENV in r["content"][0]["text"])

    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "scout-briefs")
        os.environ[CAP_STATE_ENV] = state

        # In-process: up to the cap files, the next is refused, and the count
        # the refusals read comes from the state file.
        r1 = _file_design_brief({"title": "Design brief: one", "body": "b"})
        r2 = _file_design_brief({"title": "Design brief: two", "body": "b"})
        r3 = _file_design_brief({"title": "Design brief: three", "body": "b"})
        check("cap lets through up to SCOUT_MAX_BRIEFS",
              r1.get("isError") is False and r2.get("isError") is False)
        check("cap refuses the brief past SCOUT_MAX_BRIEFS",
              r3.get("isError") is True and "cap reached" in r3["content"][0]["text"])
        check("each successful filing appended one state record",
              _cap_state_count(state) == 2)

        # THE cross-process property (#565): link N files its fill and then
        # dies; link N+1 is a FRESH process whose only memory of the run is the
        # state file. A real subprocess against the pre-populated file is the
        # exact situation an in-process counter got wrong.
        probe = [sys.executable, os.path.abspath(__file__), "--selftest-cap-child"]

        proc = subprocess.run(probe + [state], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process counting from a state file at the cap refuses "
              "(the cross-process property)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))

        # One below the cap → the fresh process files, and the shared file
        # advances — so the link after IT sees the incremented count too.
        state2 = os.path.join(tmp, "scout-briefs-2")
        _cap_state_record(state2, 41, "https://example.invalid/41")
        proc = subprocess.run(probe + [state2], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process one below the cap files (cross-process)",
              proc.returncode == 0 and proc.stdout.startswith("FILED"))
        check("the fresh process's filing advanced the shared state file",
              _cap_state_count(state2) == 2)

    # Attended behavior is unchanged: no GITHUB_RUN_ID means the cap is
    # skipped — no state file needed, filing not bounded by SCOUT_MAX_BRIEFS.
    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ["SCOUT_MAX_BRIEFS"] = "1"
    a1 = _file_design_brief({"title": "Design brief: attended one", "body": "b"})
    a2 = _file_design_brief({"title": "Design brief: attended two", "body": "b"})
    check("attended (no GITHUB_RUN_ID) skips the cap — no state file required",
          a1.get("isError") is False and a2.get("isError") is False)

    # The JSON-RPC surface only exposes the one tool.
    check("tools/list exposes exactly file_design_brief",
          [t["name"] for t in TOOLS] == ["file_design_brief"])

    if fails:
        print(f"\nscout_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nscout_mcp selftest passed")
    return 0


def selftest_cap_child(state_path):
    """One filing attempt in THIS fresh process — the parent selftest's
    cross-process case. The parent's module state died with its process; the
    only thing this process knows about the run's filings is the state file it
    is handed, which is exactly link N+1's view after link N filed and died
    (issue #565). Prints FILED/REFUSED for the parent to assert on."""
    os.environ["SCOUT_MCP_FAKE"] = "1"
    os.environ["GITHUB_RUN_ID"] = "selftest-link-n+1"
    os.environ[CAP_STATE_ENV] = state_path
    r = _file_design_brief({"title": "Design brief: cross-process probe", "body": "b"})
    outcome = "REFUSED" if r.get("isError") else "FILED"
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
