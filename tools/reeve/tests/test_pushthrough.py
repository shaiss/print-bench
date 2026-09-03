"""The push-through's own contract (issue #444) — writes recorded, never sent.

``pushthrough.py`` is the package's ONE write seam, so these tests monkeypatch
both halves of its I/O — ``github._get`` (every read, including the ones
``_paged`` makes) and ``pushthrough._write`` (every write) — and assert on the
recorded call sequence: the fail-closed label order, the never-a-/decide-
comment rule, the PAT-only ledger, and the arming bit. The decision semantics
those writes follow live in ``test_greenlight.py``.
"""

from __future__ import annotations

import base64
import re
import urllib.error

from reeve import github, greenlight, pushthrough

REPO = "o/r"
TOKEN = "workflow-token"
PAT = "regen-pat"
ROOT = github.API_ROOT


# The greenlight is posted by the wrapper under the workflow token, so the
# default marker author is the workflow's own bot login — the identity the
# poll trusts without a permission lookup (F3). A human-authored marker in a
# test must appear in the ``permissions`` map with a write-level value.
BOT = greenlight.WORKFLOW_BOT_LOGIN


def comment(cid, body, login=BOT, created="2026-08-20T06:00:00Z"):
    return {"id": cid, "user": {"login": login}, "created_at": created, "body": body}


def greenlight_thread(number=201, verdict="yes", arm=False, extra_comments=()):
    attrs = f"verdict={verdict}" + (" arm=1" if arm else "")
    gl = (f"<!-- reeve-greenlight v1 issue={number} {attrs} -->\n\n"
          f"GREENLIGHT: {verdict.upper()}\nReasoning.")
    return {
        "number": number,
        "body": f"🚦 DECISION NEEDED — `issue-{number}-decision`",
        "comments": [comment(900 + number, gl), *extra_comments],
    }


def react(content, login):
    return {"user": {"login": login}, "content": content}


def install(monkeypatch, *, threads=(), permissions=None, reactions=None,
            ledger="", labels=(), fail=()):
    """Patch both seams: reads answered from maps, writes recorded to a list.

    ``fail`` is a list of ``(url_suffix, method)`` pairs — any write matching
    both raises a 500, the injected mid-sequence failure the Done-when cases
    need — or ``(url_suffix, method, labels)`` triples that additionally
    require the payload's ``labels`` to equal ``labels``, so one label POST
    on an issue (the arming) can fail while another (the verdict) lands.
    Returns the writes list (each entry ``{url, token, method, payload}``,
    in call order — the order IS the fail-closed contract).
    """
    permissions = permissions or {}
    reactions = reactions or {}
    writes: list[dict] = []
    parked_url = f"{ROOT}/repos/{REPO}/issues?state=open&labels=needs-decision&per_page=100"

    def fake_get(url, token):
        if url == parked_url:
            return ([{"number": t["number"], "title": "", "url": "",
                      "body": t.get("body", "")} for t in threads], "")
        m = re.fullmatch(rf"{ROOT}/repos/{REPO}/issues/(\d+)/comments\?per_page=100", url)
        if m:
            return ([c for t in threads if t["number"] == int(m.group(1))
                     for c in t["comments"]], "")
        m = re.fullmatch(rf"{ROOT}/repos/{REPO}/collaborators/([^/]+)/permission", url)
        if m:
            return ({"permission": permissions[m.group(1)]}, "")
        m = re.fullmatch(rf"{ROOT}/repos/{REPO}/issues/comments/(\d+)/reactions\?per_page=100", url)
        if m:
            return (reactions.get(int(m.group(1)), []), "")
        m = re.fullmatch(rf"{ROOT}/repos/{REPO}/labels/(.+)", url)
        if m and m.group(1) in labels:
            return ({"name": m.group(1)}, "")
        if m:
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        if url == f"{ROOT}/repos/{REPO}":
            return ({"default_branch": "main"}, "")
        if url == f"{ROOT}/repos/{REPO}/contents/{pushthrough.LEDGER_PATH}?ref=main":
            return ({"content": base64.b64encode(ledger.encode()).decode(),
                     "sha": "sha-0"}, "")
        raise AssertionError(f"unexpected GET {url}")

    def fake_write(url, token, method, payload):
        for entry in fail:
            suffix, verb = entry[0], entry[1]
            only_labels = entry[2] if len(entry) > 2 else None
            if url.endswith(suffix) and method == verb and (
                only_labels is None or (payload or {}).get("labels") == only_labels
            ):
                raise urllib.error.HTTPError(url, 500, "injected failure", None, None)
        writes.append({"url": url, "token": token, "method": method, "payload": payload})
        return {}

    monkeypatch.setattr(github, "_get", fake_get)
    monkeypatch.setattr(pushthrough, "_write", fake_write)
    return writes


def _issue_writes(writes, number):
    return [w for w in writes if f"/issues/{number}/labels" in w["url"]]


def _posted_comments(writes):
    return [w["payload"]["body"] for w in writes
            if w["method"] == "POST" and w["url"].endswith("/comments")]


def _no_decide_command_anywhere(writes):
    # Done-when (e): the routine never posts a /decide. Since #540 decide.yml
    # honours a bot command carrying the tooling's footer, so a posted one
    # would now be a SECOND write path racing the API push-through — the
    # opposite failure from the stage-1 silently-neutral no-op, and still
    # forbidden.
    for body in _posted_comments(writes):
        for line in body.splitlines():
            assert greenlight.DECIDE_COMMAND_RE.match(line.strip()) is None, (
                f"a /decide command was posted: {line.strip()!r}"
            )


# ---------------------------------------------------------------------------
# Done-when (a): a 👍 from a write-permission user resolves the gate.
# ---------------------------------------------------------------------------

def test_write_permission_upside_resolves(monkeypatch):
    thread = greenlight_thread(201, verdict="yes")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},
                     reactions={1101: [react("+1", "owner")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved"
    # The verdict label is the FIRST write on the issue — fail-closed order.
    issue_writes = _issue_writes(writes, 201)
    assert issue_writes[0] == {
        "url": f"{ROOT}/repos/{REPO}/issues/201/labels", "token": TOKEN,
        "method": "POST", "payload": {"labels": ["decision-approved"]},
    }
    removed = [w["url"].rsplit("/", 1)[-1] for w in issue_writes
               if w["method"] == "DELETE"]
    assert "needs-decision" in removed and "decision-rejected" in removed
    # The ledger went through the PAT, not the workflow token.
    puts = [w for w in writes if w["method"] == "PUT"]
    assert len(puts) == 1 and puts[0]["token"] == PAT
    row = greenlight.parse_ledger(
        base64.b64decode(puts[0]["payload"]["content"]).decode()
    )
    assert row == [{"id": "issue-201-decision", "verdict": "approved",
                    "issue": "#201", "login": "owner",
                    "when": row[0]["when"]}]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", row[0]["when"])
    # The reply is a resolution marker, not a command.
    comments = _posted_comments(writes)
    assert len(comments) == 1
    assert comments[0].startswith(
        "<!-- reeve-greenlight v1 issue=201 resolution=approved id=issue-201-decision -->"
    )
    assert "never a posted command" in comments[0]
    _no_decide_command_anywhere(writes)
    # Not armed: the marker carried no arm=1, so autonomy-ok never appears.
    assert not any(w["payload"]["labels"] == ["autonomy-ok"]
                   for w in issue_writes if w["method"] == "POST")


def test_armed_greenlight_applies_autonomy_ok(monkeypatch):
    thread = greenlight_thread(202, verdict="yes", arm=True)
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "admin"},
                     reactions={1102: [react("+1", "owner")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved" and results[0]["armed"] is True
    added = [w["payload"]["labels"] for w in _issue_writes(writes, 202)
             if w["method"] == "POST"]
    assert ["autonomy-ok"] in added


def test_overrule_parks_with_one_reply_and_no_writes_of_state(monkeypatch):
    thread = greenlight_thread(203, verdict="yes")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"a": "write", "b": "maintain"},
                     reactions={1103: [react("+1", "a"), react("-1", "b")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    # Contested fails closed to overrule; the gate stays parked.
    assert results[0]["outcome"] == "overruled"
    assert writes and all(w["method"] == "POST" and w["url"].endswith("/comments")
                          for w in writes)
    body = _posted_comments(writes)[0]
    assert body.startswith(
        "<!-- reeve-greenlight v1 issue=203 resolution=overruled id=issue-203-decision -->"
    )
    assert "needs-decision" in body and "/decide yes issue-203-decision" in body
    _no_decide_command_anywhere(writes)  # the /decide mention is prose, not a command line


# ---------------------------------------------------------------------------
# Done-when (b): a 👍 from a read-only user changes nothing.
# ---------------------------------------------------------------------------

def test_read_only_reaction_changes_nothing(monkeypatch):
    thread = greenlight_thread(204, verdict="yes")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"reader": "read", "first-timer": "none"},
                     reactions={1104: [react("+1", "reader"), react("-1", "first-timer")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "wait"
    assert writes == []  # not even a comment — nothing happened at all


# ---------------------------------------------------------------------------
# Done-when (c): an explicit /decide comment outranks a conflicting reaction.
# ---------------------------------------------------------------------------

def test_decide_comment_outranks_the_reaction(monkeypatch):
    # A human typed /decide no while an owner 👍'd the YES greenlight: the
    # command wins, this loop writes nothing, decide.yml owns the thread.
    thread = greenlight_thread(205, verdict="yes",
                               extra_comments=[comment(905, "/decide no issue-205-decision",
                                                       login="owner")])
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write", "someone": "write"},
                     reactions={1105: [react("+1", "someone")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "yield"
    assert "outranks" in results[0]["reason"]
    assert writes == []


def test_decide_command_from_a_read_only_author_outranks_nothing(monkeypatch):
    # decide.yml itself would refuse it; this loop must not parse it twice.
    thread = greenlight_thread(206, verdict="yes",
                               extra_comments=[comment(906, "/decide no issue-206-decision",
                                                       login="reader")])
    writes = install(monkeypatch, threads=[thread],
                     permissions={"reader": "read", "owner": "write"},
                     reactions={1106: [react("+1", "owner")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved"  # the authorized 👍 stands
    assert writes  # …and the push happened


# ---------------------------------------------------------------------------
# Done-when (d): the label order is fail-closed — an injected mid-sequence
# failure leaves decision-approved set and needs-decision in place, never the
# reverse.
# ---------------------------------------------------------------------------

def test_failure_mid_sequence_keeps_the_park_on(monkeypatch):
    # Inject: the needs-decision DELETE 500s. The verdict label IS applied,
    # the pause survives, and the reply reports it — the recoverable half-state.
    thread = greenlight_thread(207, verdict="yes")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},
                     reactions={1107: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"),
                     fail=[("/issues/207/labels/needs-decision", "DELETE")])
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved"
    added = [w["payload"]["labels"] for w in _issue_writes(writes, 207)
             if w["method"] == "POST"]
    assert ["decision-approved"] in added
    deleted = [w["url"].rsplit("/", 1)[-1] for w in _issue_writes(writes, 207)
               if w["method"] == "DELETE"]
    assert "needs-decision" not in deleted  # the removal failed — the park stays
    assert any("needs-decision" in note for note in results[0]["notes"])
    # F5: the reply reports the TRUE state — it never claims the pause was
    # lifted when the removal failed.
    reply = _posted_comments(writes)[0]
    assert "`needs-decision` could NOT be lifted" in reply
    assert "`needs-decision` lifted" not in reply


def test_arming_failure_is_reported_as_requested_but_not_applied(monkeypatch):
    # Inject: only the autonomy-ok POST 500s (the verdict POST on the same
    # URL lands). The verdict stands, and the reply must say arming was
    # REQUESTED and did not complete — never "the greenlight did not
    # recommend arming", which would send the human away from the one label
    # they now have to apply by hand (F5).
    thread = greenlight_thread(214, verdict="yes", arm=True)
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "admin"},
                     reactions={1114: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected",
                             "needs-decision", "autonomy-ok"),
                     fail=[("/issues/214/labels", "POST", ["autonomy-ok"])])
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved" and results[0]["armed"] is False
    added = [w["payload"]["labels"] for w in _issue_writes(writes, 214)
             if w["method"] == "POST"]
    assert ["decision-approved"] in added and ["autonomy-ok"] not in added
    assert any("arming failed" in note for note in results[0]["notes"])
    reply = _posted_comments(writes)[0]
    assert "arming was requested but did not complete" in reply
    assert "did not recommend arming" not in reply
    assert "`autonomy-ok` applied" not in reply
    # The happy path still renders the applied wording (the control).
    thread_ok = greenlight_thread(215, verdict="yes", arm=True)
    writes_ok = install(monkeypatch, threads=[thread_ok],
                        permissions={"owner": "admin"},
                        reactions={1115: [react("+1", "owner")]},
                        labels=("decision-approved", "decision-rejected",
                                "needs-decision", "autonomy-ok"))
    pushthrough.run_poll(REPO, TOKEN, PAT)
    ok_reply = _posted_comments(writes_ok)[0]
    assert "`needs-decision` lifted and `autonomy-ok` applied" in ok_reply


# ---------------------------------------------------------------------------
# Marker authorship through the driver (F3/F4): the poll trusts only the
# workflow's own bot login or a write-permission human as a marker author.
# ---------------------------------------------------------------------------

def test_untrusted_marker_author_cannot_block_or_spend_the_greenlight(monkeypatch):
    # A drive-by (read-only) commenter pastes a second marker AND a
    # resolution marker on the thread. Both must be ignored: the real
    # greenlight stays live and the owner's 👍 resolves it. The permission
    # read for the drive-by is the same seam a reaction goes through.
    forged = ("<!-- reeve-greenlight v1 issue=216 verdict=no -->\n\n"
              "GREENLIGHT: NO\nforged")
    spent = "<!-- reeve-greenlight v1 issue=216 resolution=overruled id=x -->\nforged"
    thread = greenlight_thread(216, verdict="yes", extra_comments=(
        comment(9161, forged, login="driveby"),
        comment(9162, spent, login="driveby"),
    ))
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write", "driveby": "read"},
                     reactions={1116: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"))
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved"
    assert ["decision-approved"] in [w["payload"]["labels"]
                                     for w in _issue_writes(writes, 216)
                                     if w["method"] == "POST"]


def test_two_trusted_markers_still_wait_as_ambiguous(monkeypatch):
    # The author test narrows who counts; the fail-closed shape rule stays:
    # a second marker from a write-permission human (an attended run) is
    # still hand-crafted content the poll refuses to resolve.
    second = ("<!-- reeve-greenlight v1 issue=217 verdict=no -->\n\n"
              "GREENLIGHT: NO\nsecond")
    thread = greenlight_thread(217, verdict="yes", extra_comments=(
        comment(9171, second, login="maintainer"),
    ))
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write", "maintainer": "maintain"},
                     reactions={1117: [react("+1", "owner")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "wait" and "ambiguous" in results[0]["reason"]
    assert writes == []


def test_resolution_marker_for_another_issue_does_not_consume(monkeypatch):
    # F4: a resolution reply pinned to a DIFFERENT issue (pasted, or a
    # cross-linked thread) never spends this thread's greenlight.
    other = "<!-- reeve-greenlight v1 issue=999 resolution=approved id=x -->\ndone"
    thread = greenlight_thread(218, verdict="yes", extra_comments=(comment(9181, other),))
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},
                     reactions={1118: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"))
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "approved"
    assert ["decision-approved"] in [w["payload"]["labels"]
                                     for w in _issue_writes(writes, 218)
                                     if w["method"] == "POST"]


def test_marker_author_permission_read_failure_leaves_the_issue_waiting(monkeypatch):
    # A human-authored marker whose permission read blows up must not be
    # trusted by default: the per-issue guard reports the error and the
    # gate stays parked for the next run — the fail-closed direction.
    thread = greenlight_thread(219, verdict="yes")
    thread["comments"][0] = comment(9190, thread["comments"][0]["body"], login="unknown-human")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},   # no entry for unknown-human → KeyError
                     reactions={9190: [react("+1", "owner")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "error"
    assert writes == []


def test_failure_on_the_verdict_label_writes_nothing_else(monkeypatch):
    # Inject: adding decision-approved 500s. Nothing else may happen — no
    # removal of needs-decision, no ledger row, no reply — the exact reverse
    # ordering (un-parked with no verdict) is what must be impossible.
    thread = greenlight_thread(208, verdict="yes")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},
                     reactions={1108: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"),
                     fail=[("/issues/208/labels", "POST")])
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "error"
    assert "could not apply decision-approved" in results[0]["reason"]
    assert _issue_writes(writes, 208) == []          # no label write landed
    assert not [w for w in writes if w["method"] == "PUT"]   # no ledger row
    assert _posted_comments(writes) == []            # no reply claiming success
    _no_decide_command_anywhere(writes)


# ---------------------------------------------------------------------------
# The REGEN_TOKEN contract: the ledger is PAT-only, never the workflow token.
# ---------------------------------------------------------------------------

def test_absent_pat_skips_the_ledger_and_says_so(monkeypatch):
    thread = greenlight_thread(209, verdict="no")
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},
                     reactions={1109: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"))
    results = pushthrough.run_poll(REPO, TOKEN, "")

    assert results[0]["outcome"] == "approved" and results[0]["ledger"] is False
    assert not [w for w in writes if w["method"] == "PUT"]
    assert any("REGEN_TOKEN" in note for note in results[0]["notes"])
    # The verdict still landed — decide.yml's documented degradation: the
    # label is authoritative, the ledger is the audit trail.
    assert ["decision-rejected"] in [w["payload"]["labels"]
                                     for w in _issue_writes(writes, 209)
                                     if w["method"] == "POST"]


def test_ledger_appends_into_the_existing_rows(monkeypatch):
    existing = ("# Decision ledger\n"
                "older | approved | #5 | someone | 2026-01-01T00:00:00.000Z\n")
    thread = greenlight_thread(210, verdict="yes")
    writes = install(monkeypatch, threads=[thread], ledger=existing,
                     permissions={"owner": "write"},
                     reactions={1110: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"))
    pushthrough.run_poll(REPO, TOKEN, PAT)

    put = next(w for w in writes if w["method"] == "PUT")
    assert put["payload"]["branch"] == "main" and put["payload"]["sha"] == "sha-0"
    rows = greenlight.parse_ledger(base64.b64decode(put["payload"]["content"]).decode())
    assert [r["id"] for r in rows] == ["older", "issue-210-decision"]


# ---------------------------------------------------------------------------
# Driver discipline: consumed greenlights, per-issue isolation.
# ---------------------------------------------------------------------------

def test_consumed_greenlight_is_never_re_polled(monkeypatch):
    thread = greenlight_thread(211, verdict="yes")
    thread["comments"].append(comment(
        911, "<!-- reeve-greenlight v1 issue=211 resolution=approved id=x -->\ndone"))
    writes = install(monkeypatch, threads=[thread],
                     permissions={"owner": "write"},
                     reactions={1111: [react("+1", "owner")]})
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    assert results[0]["outcome"] == "wait"
    assert "consumed" in results[0]["reason"]
    assert writes == []  # a stale 👍 on a spent greenlight resolves nothing


def test_one_issue_failing_does_not_stop_the_rest(monkeypatch):
    bad = greenlight_thread(212, verdict="yes")
    good = greenlight_thread(213, verdict="yes")
    writes = install(monkeypatch, threads=[bad, good],
                     permissions={"owner": "write"},
                     reactions={1112: [react("+1", "owner")],
                                1113: [react("+1", "owner")]},
                     labels=("decision-approved", "decision-rejected", "needs-decision"),
                     fail=[("/issues/212/labels", "POST")])
    results = pushthrough.run_poll(REPO, TOKEN, PAT)

    by_number = {r["number"]: r for r in results}
    assert by_number[212]["outcome"] == "error"
    assert by_number[213]["outcome"] == "approved"
    assert ["decision-approved"] in [w["payload"]["labels"]
                                     for w in _issue_writes(writes, 213)
                                     if w["method"] == "POST"]
