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
    unattended run can file — noise a human closes, never an escalation;
  * the only GitHub call is `POST /issues` on the CURRENT repo — it never
    edits an existing issue, never posts to any channel, pushes no code.

The channel side of the desk is a different tool entirely
(mcp__growth_twitter__post_tweet, growth_mcp.py) held by a different agent:
the poster's deny backstop denies THIS server (pinned by
scripts/growth-perms-check.sh — the poster can never refill the queue it
drains), and the reverse holds structurally rather than by a backstop — this
skill is attended-only (no scheduled run, so no --settings surface to pin),
a /growth-queue session never mounts the posting server's mcp-config, and
every scheduled sibling's backstop denies both growth servers. Stdlib only;
logs go to stderr so stdout carries nothing but JSON-RPC.
"""

import json
import os
import sys
import urllib.error
import urllib.request

QUEUE_LABEL = "growth-queue"
TITLE_PREFIX = "Growth post:"
# The channels the desk knows. `youtube` is reserved ahead of its agent so a
# PM can queue for it today; only `twitter` has a draining agent (Lark).
ALLOWED_CHANNELS = ("twitter", "youtube")
GITHUB_API = "https://api.github.com"
SERVER_NAME = "growth_queue"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

# Per-run cap. GITHUB_RUN_ID is set and stable across one Actions run and
# this process lives for that whole run, so an in-process counter is
# naturally run-scoped. Attended (no run id) the cap is skipped — a human is
# the trust boundary, the same posture scout_mcp.py takes.
_filed_this_run = 0


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
    global _filed_this_run
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
    # the cap exists to bound); attended, a human is the trust boundary.
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if run_id:
        try:
            cap = int(os.environ.get("GROWTHQ_MAX_POSTS", "3"))
        except ValueError:
            cap = 3
        if _filed_this_run >= cap:
            return _tool_error(
                f"per-run queue cap reached ({_filed_this_run}/{cap}); refusing to file more"
            )

    try:
        issue = _create_issue(title, body, channel)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500] if hasattr(e, "read") else ""
        return _tool_error(f"GitHub API error {e.code} queuing post: {detail}")
    except Exception as e:  # noqa: BLE001 — surface any failure to the agent
        return _tool_error(f"failed to queue post: {type(e).__name__}: {e}")

    _filed_this_run += 1
    url = issue.get("html_url", "(unknown url)")
    number = issue.get("number", "?")
    log(f"queued #{number} for {channel} {url} ({_filed_this_run} this run)")
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
    global _filed_this_run, _last_payload
    os.environ["GROWTHQ_MCP_FAKE"] = "1"
    os.environ.pop("GITHUB_RUN_ID", None)
    fails = []

    def check(name, cond):
        print(f"{'ok  ' if cond else 'FAIL'}  {name}")
        if not cond:
            fails.append(name)

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
    # ever ride along.
    _filed_this_run = 0
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

    # The per-run cap fires inside an Actions run (GITHUB_RUN_ID set).
    os.environ["GITHUB_RUN_ID"] = "selftest-run"
    os.environ["GROWTHQ_MAX_POSTS"] = "2"
    _filed_this_run = 0
    r1 = _queue_growth_post({"channel": "twitter", "title": "Growth post: one", "body": "b"})
    r2 = _queue_growth_post({"channel": "twitter", "title": "Growth post: two", "body": "b"})
    r3 = _queue_growth_post({"channel": "twitter", "title": "Growth post: three", "body": "b"})
    check("cap lets through up to GROWTHQ_MAX_POSTS",
          r1.get("isError") is False and r2.get("isError") is False)
    check("cap refuses the item past GROWTHQ_MAX_POSTS",
          r3.get("isError") is True and "cap reached" in r3["content"][0]["text"])
    os.environ.pop("GITHUB_RUN_ID", None)
    os.environ.pop("GROWTHQ_MAX_POSTS", None)

    # The JSON-RPC surface only exposes the one tool.
    check("tools/list exposes exactly queue_growth_post",
          [t["name"] for t in TOOLS] == ["queue_growth_post"])

    if fails:
        print(f"\nqueue_mcp selftest FAILED: {', '.join(fails)}")
        return 1
    print("\nqueue_mcp selftest passed")
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
