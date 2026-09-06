#!/usr/bin/env python3
"""queue_mcp.py — the growth queue's filing surface, as a stdio MCP tool.

WHY AN MCP TOOL (the same dead end the scout hit)
-------------------------------------------------
A queued growth post's body is a full multi-line markdown message brief
(headings, a Facts & sources list, blank lines). Under `--permission-mode
dontAsk` the Bash matcher denies any command whose argument reads as shell
structure — an embedded newline is enough, no quoting fixes it (proven on
the scout's file-brief verb; see scout_mcp.py's header). An MCP tool takes
its arguments as JSON over a stdio pipe, never on a command line. Same
pattern, another consumer.

SECURITY (a queue filer must never become a poster or an approver)
------------------------------------------------------------------
A PM session that queues may be reading untrusted issue text while holding a
GitHub token, so this server does NOT trust its inputs and cannot be steered
into anything but filing a recognisable, un-approved queue item:

  * the labels are HARDCODED to `growth-queue` + `channel:<name>` with the
    channel validated against a closed set — the tool can never apply
    `approved-to-post` (the human live-post gate), `priority:high`, or any
    routing label (`autonomy-ok`, `needs-decision`): queuing grants nothing;
  * the title MUST start with `Growth post:` — every queue item is findable
    and cullable as one;
  * a per-run cap (`GROWTHQ_MAX_POSTS`, default 3) bounds how many items one
    unattended run can file — counted in a state file every link step of the
    chain walk shares (`GROWTHQ_CAP_STATE`, the reeve.yml
    `REEVE_GREENLIGHT_STATE` pattern; issue #567), so the bound spans the
    whole walk and not one server process. The agent can neither set env vars
    nor write files, so it cannot reach or reset the count; at worst a
    hijacked run queues a bounded number of items, noise a human closes,
    never an escalation;
  * the only GitHub call is `POST /issues` on the CURRENT repo — it never
    edits an existing issue, never posts to any channel, pushes no code.

The channel side of the desk is a different tool entirely
(mcp__growth_twitter__post_tweet, growth_mcp.py) held by a different agent:
the poster's deny backstop denies THIS server (pinned by
scripts/growth-perms-check.sh — the poster can never refill the queue it
drains). Two agents mount THIS server: the attended /growth-queue skill (a
human is the trust boundary, so no --settings surface to pin), and the
scheduled /reeve-growth routine, whose own deny backstop
(.claude/reeve-growth-settings.json, pinned by
scripts/reeve-growth-perms-check.sh) is the MIRROR of the poster's — it
allows this queue tool and DENIES the poster, so a queuer can never post.
Every OTHER scheduled sibling's backstop denies both growth servers. Stdlib
only; logs go to stderr so stdout carries nothing but JSON-RPC.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

QUEUE_LABEL = "growth-queue"
TITLE_PREFIX = "Growth post:"
# The channels the desk knows. `youtube` is reserved ahead of its agent so a
# PM can queue for it today; only `twitter` has a draining agent (Lark).
ALLOWED_CHANNELS = ("twitter", "youtube")
GITHUB_API = "https://api.github.com"
SERVER_NAME = "growth_queue"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# --- The walk-spanning queue cap (issue #567) --------------------------------
#
# Every link of a chain walk is its own claude-code-action step, so this server
# process — and anything in-process — restarts at link N+1. An in-process
# counter therefore caps ONE LINK, not the run: a link that queues up to the
# cap and then dies (agent error, step timeout) hands the next link a fresh
# counter with the same prompt, so a 3-link walk could queue up to 3x the cap.
# The count must live where every link can see it: a state file the workflow
# names via GROWTHQ_CAP_STATE, one path shared by every link step of the job
# (the reeve.yml REEVE_GREENLIGHT_STATE precedent). runner.temp is fresh per
# job, so the file is run-scoped and never persists across runs.
#
# SIBLING ADOPTION (#549's remaining splits — wright, reeve-signoff,
# adoption-assessor, growth-twitter): lift the three functions below verbatim
# under your own env-var name. They are deliberately self-contained — stdlib
# only, no growth-queue-specific coupling — so adoption is a copy plus the
# CAP_STATE_ENV constant, not a re-derivation of the mechanism.
CAP_STATE_ENV = "GROWTHQ_CAP_STATE"


def _cap_state_path():
    """The shared state-file path for this run, or None attended.

    Attended (no GITHUB_RUN_ID) the cap is skipped entirely — a human is the
    trust boundary — so no state file is required. Unattended the path comes
    from the env var the workflow sets; an empty value is returned as-is so
    the caller can refuse: filing on without it would silently fall back to
    per-process counting, which is exactly the per-link reset this mechanism
    exists to kill.
    """
    if not os.environ.get("GITHUB_RUN_ID", "").strip():
        return None
    return os.environ.get(CAP_STATE_ENV, "").strip()


def _cap_state_count(path):
    """How many items this run has already queued, per the shared state file.

    One JSON record per successful write, so the count is the number of
    non-empty lines; an absent file is a run that has queued nothing yet (the
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
    record doubles as the audit trail of what a link that later died queued."""
    rec = {"issue": number, "url": url,
           "filed_at": datetime.now(timezone.utc).isoformat()}
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")


def log(msg):
    """Diagnostics go to stderr — stdout is reserved for JSON-RPC frames."""
    print(f"queue_mcp: {msg}", file=sys.stderr, flush=True)


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
    req.add_header("User-Agent", "print-bench-growth-queue")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
    return json.loads(raw) if raw else {}


# Captured by the selftest so it can assert the exact POST payload (the label
# hardcode) without a network call. `None` in normal operation.
_last_payload = None


def _create_issue(title, body, channel):
    """POST one issue with the HARDCODED queue + channel labels. The labels
    are set here, from constants, never from caller input — so no argument
    can add an approval, priority, or routing label. GROWTHQ_MCP_FAKE
    short-circuits the network for the selftest (never set in a workflow)."""
    global _last_payload
    payload = {
        "title": title,
        "body": body,
        "labels": [QUEUE_LABEL, f"channel:{channel}"],
    }
    _last_payload = payload
    if os.environ.get("GROWTHQ_MCP_FAKE"):
        return {"html_url": "https://example.invalid/fake", "number": 0}
    return _api("POST", f"/repos/{_repo()}/issues", payload)


def _queue_growth_post(arguments):
    """Create ONE growth-queue issue. The queue filer's entire write taxonomy."""
    args = arguments or {}
    channel = args.get("channel")
    title = args.get("title")
    body = args.get("body")
    if not isinstance(channel, str) or channel.strip().lower() not in ALLOWED_CHANNELS:
        return _tool_error(
            f"queue_growth_post: 'channel' must be one of {', '.join(ALLOWED_CHANNELS)}"
        )
    channel = channel.strip().lower()
    if not isinstance(title, str) or not title.strip():
        return _tool_error("queue_growth_post: 'title' is required (non-empty string)")
    if not isinstance(body, str) or not body.strip():
        return _tool_error("queue_growth_post: 'body' is required (non-empty string)")
    title = title.strip()
    if not title.startswith(TITLE_PREFIX):
        return _tool_error(
            f"queue_growth_post: title must start with '{TITLE_PREFIX}' (got {title!r})"
        )

    # Per-run cap — enforced only inside an Actions run (the unattended case
    # the cap exists to bound); attended, a human is the trust boundary. The
    # count is read from the shared state file so it spans the whole chain
    # walk, not this one server process (#567).
    state = _cap_state_path()
    if state is not None:
        if not state:
            return _tool_error(
                f"queue_growth_post: {CAP_STATE_ENV} is not set but this is an "
                "unattended run (GITHUB_RUN_ID is set) — the workflow must give "
                "every link step the same state-file path (the reeve.yml "
                "REEVE_GREENLIGHT_STATE pattern) or the queue cap cannot span "
                "the chain walk; refusing to file"
            )
        try:
            cap = int(os.environ.get("GROWTHQ_MAX_POSTS", "3"))
        except ValueError:
            cap = 3
        try:
            filed = _cap_state_count(state)
        except RuntimeError as e:
            return _tool_error(f"queue_growth_post: {e}")
        if filed >= cap:
            return _tool_error(
                f"per-run queue cap reached ({filed}/{cap} filed across the "
                "chain walk so far); refusing to file more"
            )

    try:
        issue = _create_issue(title, body, channel)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} queuing post: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to queue post: {type(e).__name__}: {e}")

    url = issue.get("html_url", "(unknown url)")
    number = issue.get("number", "?")
    if state:
        try:
            _cap_state_record(state, number, url)
        except OSError as e:
            log(f"WARNING: queued #{number} but could not append its "
                f"{CAP_STATE_ENV} record ({e}) — this filing will not count "
                f"toward the walk cap")
    log(f"queued #{number} for {channel} {url}")
    return _tool_text(f"QUEUED #{number} for {channel} {url}")


# --- MCP tool registry ------------------------------------------------------

TOOLS = [
    {
        "name": "queue_growth_post",
        "description": (
            "Queue ONE growth post on this repository: file a growth-queue "
            "issue the matching channel agent (Lark for twitter) drains on its "
            "schedule. The body is passed as a JSON argument (not a shell "
            "command line), so it may be the full multi-line markdown message "
            "matching templates/growth-post.md. The 'growth-queue' and "
            "'channel:<name>' labels are applied automatically and are the only "
            "labels this tool can set — it can never approve, prioritize, or "
            "route; the title must start with 'Growth post:'. Returns "
            "'QUEUED #<n> for <channel> <url>'. One call queues one item, up to "
            "the per-run cap."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "description": "The target channel: 'twitter' or 'youtube'.",
                },
                "title": {
                    "type": "string",
                    "description": "Issue title, must start with 'Growth post:'.",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Full markdown body matching templates/growth-post.md, "
                        "section for section (Channel, Message, Link, Facts & "
                        "sources, Timing & priority)."
                    ),
                },
            },
            "required": ["channel", "title", "body"],
            "additionalProperties": False,
        },
    }
]

_DISPATCH = {"queue_growth_post": _queue_growth_post}


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
    (the repo's standing rule), so these are the cases a live run cannot
    show."""
    global _last_payload
    os.environ["GROWTHQ_MCP_FAKE"] = "1"
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
    check("missing channel is rejected",
          _queue_growth_post({"title": "Growth post: x", "body": "b"}).get("isError") is True)
    check("an unknown channel is rejected",
          _queue_growth_post({"channel": "tiktok", "title": "Growth post: x",
                              "body": "b"}).get("isError") is True)
    check("missing title is rejected",
          _queue_growth_post({"channel": "twitter", "body": "b"}).get("isError") is True)
    check("missing body is rejected",
          _queue_growth_post({"channel": "twitter",
                              "title": "Growth post: x"}).get("isError") is True)
    check("title without the 'Growth post:' prefix is rejected",
          _queue_growth_post({"channel": "twitter", "title": "sneak in",
                              "body": "b"}).get("isError") is True)

    # A valid call files with the hardcoded queue + channel labels — there is
    # no label argument to pass, so no approval/priority/routing label can
    # ever ride along. Attended here (no run id): the cap is skipped and no
    # state file is required.
    ok = _queue_growth_post({"channel": "Twitter", "title": "Growth post: good",
                             "body": "## Message\n| a | b |\nyes"})
    check("a well-formed queue item files", ok.get("isError") is False)
    check("the filed labels are hardcoded to growth-queue + channel:twitter",
          _last_payload == {"title": "Growth post: good",
                            "body": "## Message\n| a | b |\nyes",
                            "labels": [QUEUE_LABEL, "channel:twitter"]})

    # The reserved channel queues too (its agent arrives later).
    ok2 = _queue_growth_post({"channel": "youtube", "title": "Growth post: later",
                              "body": "b"})
    check("the reserved youtube channel queues",
          ok2.get("isError") is False
          and _last_payload["labels"] == [QUEUE_LABEL, "channel:youtube"])

    # The walk-spanning cap (issue #567), inside an Actions run.
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    os.environ["GROWTHQ_MAX_POSTS"] = "2"

    # Unwired: run id set but no state path. Fail closed — per-process
    # counting is exactly the per-link reset the state file replaces.
    r = _queue_growth_post({"channel": "twitter", "title": "Growth post: unwired",
                            "body": "b"})
    check("an unattended run without GROWTHQ_CAP_STATE refuses (fail closed)",
          r.get("isError") is True and CAP_STATE_ENV in r["content"][0]["text"])

    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.join(tmp, "growthq-posts")
        os.environ[CAP_STATE_ENV] = state

        # In-process: up to the cap files, the next is refused, and the count
        # the refusals read comes from the state file.
        r1 = _queue_growth_post({"channel": "twitter", "title": "Growth post: one", "body": "b"})
        r2 = _queue_growth_post({"channel": "twitter", "title": "Growth post: two", "body": "b"})
        r3 = _queue_growth_post({"channel": "twitter", "title": "Growth post: three", "body": "b"})
        check("cap lets through up to GROWTHQ_MAX_POSTS",
              r1.get("isError") is False and r2.get("isError") is False)
        check("cap refuses the item past GROWTHQ_MAX_POSTS",
              r3.get("isError") is True and "cap reached" in r3["content"][0]["text"])
        check("each successful filing appended one state record",
              _cap_state_count(state) == 2)

        # THE cross-process property (#567): link N queues its fill and then
        # dies; link N+1 is a FRESH process whose only memory of the run is
        # the state file. A real subprocess against the pre-populated file is
        # the exact situation an in-process counter got wrong.
        probe = [sys.executable, os.path.abspath(__file__), "--selftest-cap-child"]

        proc = subprocess.run(probe + [state], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process counting from a state file at the cap refuses "
              "(the cross-process property)",
              proc.returncode == 0 and proc.stdout.startswith("REFUSED"))

        # One below the cap → the fresh process queues, and the shared file
        # advances — so the link after IT sees the incremented count too.
        state2 = os.path.join(tmp, "growthq-posts-2")
        _cap_state_record(state2, 41, "https://example.invalid/41")
        proc = subprocess.run(probe + [state2], env=dict(os.environ),
                              capture_output=True, text=True)
        check("a fresh process one below the cap files (cross-process)",
              proc.returncode == 0 and proc.stdout.startswith("FILED"))
        check("the fresh process's filing advanced the shared state file",
              _cap_state_count(state2) == 2)

    # An unreadable state path refuses rather than counting zero — a silent
    # zero would silently uncap the walk.
    os.environ[CAP_STATE_ENV] = "/tmp"
    r = _queue_growth_post({"channel": "twitter", "title": "Growth post: unreadable",
                            "body": "b"})
    check("an unreadable state file refuses (never counts as zero)",
          r.get("isError") is True and "cannot read" in r["content"][0]["text"])

    # Attended behavior is unchanged: no GITHUB_RUN_ID means the cap is
    # skipped — no state file needed, filing not bounded by GROWTHQ_MAX_POSTS.
    os.environ.pop(CAP_STATE_ENV, None)
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ["GROWTHQ_MAX_POSTS"] = "1"
    a1 = _queue_growth_post({"channel": "twitter", "title": "Growth post: attended one",
                             "body": "b"})
    a2 = _queue_growth_post({"channel": "twitter", "title": "Growth post: attended two",
                             "body": "b"})
    check("attended (no GITHUB_RUN_ID) skips the cap — no state file required",
          a1.get("isError") is False and a2.get("isError") is False)
    os.environ.pop("GROWTHQ_MAX_POSTS", None)

    # The JSON-RPC surface only exposes the one tool.
    check("tools/list exposes exactly queue_growth_post",
          [t["name"] for t in TOOLS] == ["queue_growth_post"])

    if fails:
        print(f"\nqueue_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nqueue_mcp selftest passed")
    return 0


def selftest_cap_child(state_path):
    """One queueing attempt in THIS fresh process — the parent selftest's
    cross-process case. The parent's module state died with its process; the
    only thing this process knows about the run's filings is the state file it
    is handed, which is exactly link N+1's view after link N queued and died
    (issue #567). Prints FILED/REFUSED for the parent to assert on."""
    os.environ["GROWTHQ_MCP_FAKE"] = "1"
    os.environ["GITHUB_RUN_ID"] = "selftest-link-n+1"
    os.environ[CAP_STATE_ENV] = state_path
    r = _queue_growth_post({"channel": "twitter",
                            "title": "Growth post: cross-process probe", "body": "b"})
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
