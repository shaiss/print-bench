"""trust — exact port of reviewer-posted.sh / coach-lock-check.sh (P1a).

Owner: H2. Each test's docstring is its acceptance criterion (docs/provenance.md,
final plan P0/P1a–e).

The parity tests read the two scripts' ``--selftest`` sources: every ``row``
(reviewer-posted.sh) and every ``expect`` (coach-lock-check.sh) is parsed out
of the script, so a row added there without a Python twin here fails.
reviewer-posted.sh builds its fixtures with Python expressions inside the
shell script; those are rebuilt below (:data:`RP_FIXTURES`, one builder per
``$tmp/<name>`` the script writes, mirroring its ``mkfix`` preamble).
coach-lock-check.sh's fixtures are literal JSON in single quotes and are
parsed straight from the script.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shlex
import shutil
import subprocess

import pytest

from conftest import OWNER_LOGIN, REPO, raw_pr, receipts
from provenance import digest, markers, trust

FOOTER = digest.FOOTER
HEAD = "0123456789abcdef0123456789abcdef01234567"
OLD = "fedcba9876543210fedcba9876543210fedcba98"
RP_SCRIPT = REPO / "scripts" / "reviewer-posted.sh"
CL_SCRIPT = REPO / "scripts" / "coach-lock-check.sh"


def _selftest_body(script) -> str:
    text = script.read_text(encoding="utf-8")
    start = text.index("selftest() {")
    return text[start:]


def _logical_lines(text: str) -> list[str]:
    """Shell logical lines: a trailing backslash continues onto the next line."""
    return text.replace("\\\n", " ").split("\n")


# ---------------------------------------------------------------------------
# reviewer-posted.sh — the fixtures its selftest builds, rebuilt in Python.

jane = f"<!-- JANE_SIGNOFF sha={HEAD} verdict=pass fuse=none -->"
jane_stale = f"<!-- JANE_SIGNOFF sha={OLD} verdict=pass fuse=none -->"
jane_ack = f"<!-- JANE_SIGNOFF sha={HEAD} verdict=pass fuse=acknowledged -->"
drik = f"<!-- DRIK_SIGNOFF sha={HEAD} verdict=block fuse=none -->"
pm_done = f"<!-- PM_TRIAGE_DONE sha={HEAD} -->"
pm_done_stale = f"<!-- PM_TRIAGE_DONE sha={OLD} -->"
pm_full = f"<!-- PM_TRIAGE design=demo sha={HEAD} -->\n\n<!-- PM_TRIAGE_DONE sha={HEAD} -->"
coach_done = f"<!-- COACH_DONE sha={HEAD} -->"
coach_full = f"<!-- COACH_LOCK -->\n\n<!-- COACH_DONE sha={HEAD} -->"
bot = {"login": "github-actions[bot]", "type": "Bot"}


def mcp(body_text, marker, user=None, created="2026-10-05T12:00:01Z"):
    c = {"body": body_text.rstrip() + "\n\n" + marker + "\n\n" + FOOTER, "user": user if user is not None else bot}
    if created is not None:
        c["created_at"] = created
    return c


def _dump(comments) -> str:
    return json.dumps(comments)


#: ``$tmp/<name>`` → the file text reviewer-posted.sh's selftest writes there.
RP_FIXTURES = {
    "posted": lambda: _dump([mcp("Jane here — clean print call.", jane)]),
    "graphql": lambda: _dump([{"body": "Jane here.\n\n" + jane + "\n\n" + FOOTER, "user": {"login": "github-actions"},
                               "created_at": "2026-10-05T12:00:01Z"}]),
    "stale": lambda: _dump([mcp("Jane here.", jane_stale)]),
    "silent": lambda: _dump([{"body": "Jane looked, found nothing to say.\n\n" + FOOTER, "user": bot}]),
    "drik": lambda: _dump([mcp("Drik here.", drik)]),
    "both": lambda: _dump([mcp("Drik.", drik), mcp("Jane.", jane_ack)]),
    "pm": lambda: _dump([mcp("PM triage.", pm_full)]),
    "pm-done-only": lambda: _dump([mcp("PM triage.", pm_done)]),
    "pm-stale": lambda: _dump([mcp("PM triage.", pm_done_stale)]),
    "coach": lambda: _dump([mcp("Coach kickoff.", coach_full)]),
    "coach-done-only": lambda: _dump([mcp("Coach.", coach_done)]),
    "malformed": lambda: _dump([{"body": "x\n\n<!-- JANE_SIGNOFF verdict=pass fuse=none -->\n\n" + FOOTER,
                                 "user": bot}]),
    "impostor": lambda: _dump([{"body": f"unrelated text mentioning JANE_SIGNOFF and sha={HEAD} separately\n\n"
                                + FOOTER, "user": bot}]),
    "planted-human": lambda: _dump([mcp("plant", jane, user={"login": "attacker"})]),
    "planted-cursor": lambda: _dump([mcp("plant", jane, user={"login": "cursor[bot]", "type": "Bot"})]),
    "no-footer": lambda: _dump([{"body": "Jane.\n\n" + jane, "user": bot}]),
    "no-author": lambda: _dump([{"body": "Jane.\n\n" + jane + "\n\n" + FOOTER}]),
    "sibling-plant": lambda: _dump([{"body": "x\n\n" + jane + "\n\n" + drik + "\n\n" + FOOTER, "user": bot}]),
    "casefold": lambda: _dump([{"body": f"x\n\n<!-- jane_signoff sha={HEAD} verdict=pass fuse=none -->\n\n"
                                + FOOTER, "user": bot}]),
    "empty": lambda: "[]\n",
    "planted-pm-human": lambda: _dump([mcp("plant", pm_done, user={"login": "attacker"})]),
    "planted-coach-cursor": lambda: _dump([mcp("plant", coach_done, user={"login": "cursor[bot]", "type": "Bot"})]),
    "plant-then-real": lambda: _dump([mcp("plant", jane, user={"login": "attacker"}), mcp("real", jane)]),
    "no-created": lambda: _dump([mcp("Jane.", jane, created=None)]),
    "pages": lambda: (json.dumps([{"body": "page1", "user": {"login": "github-actions[bot]"}}])
                      + json.dumps([{"body": "Jane.\n\n" + jane + "\n\n" + FOOTER,
                                     "user": {"login": "github-actions[bot]"}}])),
    "slurp": lambda: json.dumps([[{"body": "page1", "user": {"login": "github-actions[bot]"}}],
                                 [{"body": "Jane.\n\n" + jane + "\n\n" + FOOTER,
                                   "user": {"login": "github-actions[bot]"}}]]),
}

#: Every decision row's label → the verdict this port must give (the script's own expectation
#: is parsed too and must agree — a changed expectation there fails here).
RP_ROWS = {
    "Actions-bot MCP-shaped post for this head → served": True,
    "GraphQL github-actions login still serves": True,
    "no marker at all → not served": False,
    "marker names an older head → stale": False,
    "marker without a sha field → unserved": False,
    "sha outside a marker does not count": False,
    "drik marker serves drik": True,
    "jane marker does not serve drik": False,
    "fuse=acknowledged MCP suffix still serves": True,
    "empty thread → not served": False,
    "pm full MCP post (PM_TRIAGE + PM_TRIAGE_DONE) serves pm": True,
    "pm DONE-only suffix also serves pm": True,
    "pm DONE for an older head is stale": False,
    "pm marker does not serve jane": False,
    "jane marker does not serve pm": False,
    "coach full MCP post (COACH_LOCK + COACH_DONE) serves coach": True,
    "coach DONE-only suffix also serves coach": True,
    "coach marker does not serve pm": False,
    "human-planted PM_TRIAGE_DONE is ignored": False,
    "cursor[bot]-planted COACH_DONE is ignored": False,
    "human-planted marker+footer is ignored": False,
    "cursor[bot]-planted marker+footer is ignored": False,
    "Actions-bot marker without MCP footer is ignored": False,
    "marker with no author is ignored": False,
    "sibling Actions-bot plant (Drik suffix, Jane in body) does not serve jane": False,
    "case-folded marker is not an MCP post": False,
    "a human plant does not hide a later genuine MCP post": True,
    "lock created after --since passes": True,
    "lock created at exactly --since passes": True,
    "lock from an earlier run fails under --since": False,
    "lock missing created_at fails under --since": False,
    "concatenated paginated page arrays still find the marker": True,
    "slurped page arrays still find the marker": True,
}

#: Every refusal row → the Python call that must raise ValueError (None: the refusal is about a
#: CLI argument this function does not take — the PR number, the live-mode token).
RP_REFUSALS = {
    "typo'd reviewer refused": lambda c: trust.served(c, reviewer="jan", sha=HEAD),
    "unknown reviewer refused": lambda c: trust.served(c, reviewer="vera", sha=HEAD),
    "short sha refused": lambda c: trust.served(c, reviewer="jane", sha="abc123"),
    "non-numeric pr refused": None,
    "bad --since refused": lambda c: trust.served(c, reviewer="jane", sha=HEAD, since="yesterday"),
}


def _rp_rows():
    rows, refusals = [], []
    for line in _logical_lines(_selftest_body(RP_SCRIPT)):
        stripped = line.strip()
        if stripped.startswith('row "'):
            tokens = shlex.split(stripped)
            label, want, args = tokens[1], tokens[2], tokens[3:]
            assert args[:2] == ["$0", "check"], label
            opts = dict(zip(args[2::2], args[3::2]))
            rows.append((label, want, opts))
        elif stripped.startswith('refuses "'):
            refusals.append(shlex.split(stripped)[1])
    return rows, refusals


def _rp_fixture_names() -> set[str]:
    body = _selftest_body(RP_SCRIPT)
    names = set(re.findall(r'mkfix "\$tmp/([A-Za-z0-9-]+)"', body))
    names |= set(re.findall(r'OUT="\$tmp/([A-Za-z0-9-]+)"', body))
    names |= set(re.findall(r"'\[\]' >\"\$tmp/([A-Za-z0-9-]+)\"", body))
    return names


def test_every_reviewer_posted_selftest_row_agrees():
    """Every `row` of scripts/reviewer-posted.sh --selftest (labels parsed from the script; the expected true/false and fixture rebuilt in Python) gets the same verdict from trust.served; a label added to the script without a Python row fails."""
    rows, refusals = _rp_rows()
    assert len(rows) == 33 and len({label for label, _, _ in rows}) == len(rows)
    assert {label for label, _, _ in rows} == set(RP_ROWS)
    assert _rp_fixture_names() == set(RP_FIXTURES)
    for label, want, opts in rows:
        assert (want == "true") == RP_ROWS[label], f"the script changed its expectation: {label}"
        assert opts["--pr"] == "1"
        sha = {"$head": HEAD, "$old": OLD}[opts["--sha"]]
        name = opts["--comments-file"].removeprefix("$tmp/")
        comments = trust.load_comments(RP_FIXTURES[name]())
        got = trust.served(comments, reviewer=opts["--reviewer"], sha=sha, since=opts.get("--since"))
        assert got is RP_ROWS[label], label
    assert set(refusals) == set(RP_REFUSALS)
    posted = trust.load_comments(RP_FIXTURES["posted"]())
    for label, call in RP_REFUSALS.items():
        if call is not None:
            with pytest.raises(ValueError):
                call(posted)


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash to run the script itself")
def test_rebuilt_fixtures_get_the_scripts_own_verdicts(tmp_path):
    """Fidelity of the Python rebuild: the REAL reviewer-posted.sh, run on each rebuilt fixture file,
    prints the row's expected verdict — so the port is compared against the script's fixtures, not
    against a lookalike."""
    rows, _ = _rp_rows()
    for name, build in RP_FIXTURES.items():
        (tmp_path / name).write_text(build(), encoding="utf-8")
    for label, want, opts in rows:
        argv = ["bash", str(RP_SCRIPT), "check", "--pr", opts["--pr"],
                "--sha", {"$head": HEAD, "$old": OLD}[opts["--sha"]], "--reviewer", opts["--reviewer"],
                "--comments-file", str(tmp_path / opts["--comments-file"].removeprefix("$tmp/"))]
        if "--since" in opts:
            argv += ["--since", opts["--since"]]
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"}
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60, env=env)
        assert proc.returncode == 0, (label, proc.stderr)
        assert proc.stdout.strip() == want, label


#: Bodies chosen to probe where a digest-based rule could part ways with ``body.endswith(...)``.
ADVERSARIAL = {
    "marker glued to the prose": "x" + jane + "\n\n" + FOOTER,
    "marker glued to another marker": "<!-- A -->" + jane + "\n\n" + FOOTER,
    "two markers on one line": "x\n\n<!-- A --> " + jane + "\n\n" + FOOTER,
    "body is only the suffix": jane + "\n\n" + FOOTER,
    "newline after the footer": "x\n\n" + jane + "\n\n" + FOOTER + "\n",
    "CRLF separators": "x\r\n\r\n" + jane + "\r\n\r\n" + FOOTER,
    "single newline before the footer": "x\n\n" + jane + "\n" + FOOTER,
    "three newlines before the footer": "x\n\n" + jane + "\n\n\n" + FOOTER,
    "double space inside the marker": "x\n\n" + jane.replace("fuse=none", " fuse=none") + "\n\n" + FOOTER,
    "no space before -->": "x\n\n" + jane.replace(" -->", "-->") + "\n\n" + FOOTER,
    "an extra attribute": "x\n\n" + jane.replace(" -->", " extra=1 -->") + "\n\n" + FOOTER,
    "attributes reordered": f"x\n\n<!-- JANE_SIGNOFF verdict=pass sha={HEAD} fuse=none -->\n\n" + FOOTER,
    "footer twice": "x\n\n" + jane + "\n\n" + FOOTER + "\n\n" + FOOTER,
    "uppercase sha": "x\n\n" + jane.replace(HEAD, HEAD.upper()) + "\n\n" + FOOTER,
    "four chained markers": "x\n\n<!-- A -->\n\n<!-- B -->\n\n<!-- C -->\n\n" + jane + "\n\n" + FOOTER,
    "emoji prose": "🚢 ✅ 👍\n\n" + jane + "\n\n" + FOOTER,
    "marker inside a code fence": "```\n" + jane + "\n```\n\n" + FOOTER,
}


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash to run the script itself")
def test_suffix_rule_matches_the_script_on_adversarial_bodies(tmp_path):
    """The digest-based served rule and the script's ``endswith(marker + "\\n\\n" + FOOTER)`` agree
    on every body built to tell them apart (both run for real)."""
    for label, body in ADVERSARIAL.items():
        path = tmp_path / "c.json"
        path.write_text(json.dumps([{"body": body, "user": bot}]), encoding="utf-8")
        proc = subprocess.run(["bash", str(RP_SCRIPT), "check", "--pr", "1", "--sha", HEAD, "--reviewer", "jane",
                               "--comments-file", str(path)], capture_output=True, text=True, timeout=60,
                              env={k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"})
        assert proc.returncode == 0, (label, proc.stderr)
        script = proc.stdout.strip() == "true"
        assert trust.served([{"body": body, "user": bot}], reviewer="jane", sha=HEAD) is script, label
    # the probe set exercises both answers
    answers = {label: trust.served([{"body": b, "user": bot}], reviewer="jane", sha=HEAD)
               for label, b in ADVERSARIAL.items()}
    assert answers["marker glued to the prose"] and answers["four chained markers"]
    assert not answers["CRLF separators"] and not answers["footer twice"]


def _coach_core() -> str:
    """The Python source coach-lock-check.sh's ``comments_carry_lock`` runs (between its quotes)."""
    text = CL_SCRIPT.read_text(encoding="utf-8")
    start = text.index('comments_carry_lock() {')
    begin = text.index("-I -c '", start) + len("-I -c '")
    end = text.index("\n'\n}", begin)
    return text[begin:end]


def test_coach_rule_matches_the_script_on_adversarial_bodies():
    """Same for coach-lock-check.sh's SUFFIX_RE, running the script's own embedded Python core."""
    import sys
    lock, done = trust.COACH_LOCK_MARKER, f"<!-- COACH_DONE sha={HEAD} -->"
    bodies = {
        "assembled": f"r\n\n{lock}\n\n{done}\n\n{FOOTER}",
        "lock glued to prose": f"r{lock}\n\n{done}\n\n{FOOTER}",
        "pair reversed": f"r\n\n{done}\n\n{lock}\n\n{FOOTER}",
        "single newline between": f"r\n\n{lock}\n{done}\n\n{FOOTER}",
        "uppercase sha": f"r\n\n{lock}\n\n{done.replace(HEAD, HEAD.upper())}\n\n{FOOTER}",
        "lock without spaces": f"r\n\n<!--COACH_LOCK-->\n\n{done}\n\n{FOOTER}",
        "a fake lock family": f"r\n\n<!-- COACH_LOCK_FAKE -->\n\n{done}\n\n{FOOTER}",
        "trailing newline": f"r\n\n{lock}\n\n{done}\n\n{FOOTER}\n",
        "jane between": f"r\n\n{lock}\n\n{jane}\n\n{done}\n\n{FOOTER}",
        "only the pair": f"{lock}\n\n{done}\n\n{FOOTER}",
    }
    core = _coach_core()
    env = dict(os.environ, MARKER_HTML=lock, COACH_FOOTER=FOOTER)
    env.pop("COACH_LOCK_SINCE", None)
    agreed = {}
    for label, body in bodies.items():
        raw = json.dumps([{"body": body, "user": bot}])
        proc = subprocess.run([sys.executable, "-I", "-c", core], input=raw, capture_output=True, text=True,
                              timeout=60, env=env)
        assert proc.returncode in (0, 1), (label, proc.stderr)
        assert trust.coach_lock_served(trust.load_comments(raw)) is (proc.returncode == 0), label
        agreed[label] = proc.returncode == 0
    assert agreed["assembled"] and agreed["lock glued to prose"] and not agreed["pair reversed"]


def _cl_rows():
    rows, since = [], None
    for line in _logical_lines(_selftest_body(CL_SCRIPT)):
        stripped = line.strip()
        if stripped.startswith("export COACH_LOCK_SINCE="):
            since = stripped.split("=", 1)[1]
        elif stripped.startswith("unset COACH_LOCK_SINCE"):
            since = None
        elif stripped.startswith('expect "'):
            _, name, raw, want = shlex.split(stripped)
            rows.append((name, raw, want, since))
    return rows


def test_every_coach_lock_selftest_row_agrees():
    """Same for scripts/coach-lock-check.sh --selftest rows via trust.coach_lock_served."""
    rows = _cl_rows()
    body = _selftest_body(CL_SCRIPT)
    # every expect line is parsed (a parser that silently skipped rows would lose coverage)
    assert len(rows) == body.count('expect "') and len(rows) >= 26
    assert {want for _, _, want, _ in rows} == {"pass", "fail"}
    assert sum(1 for *_, since in rows if since) == 5
    for name, raw, want, since in rows:
        got = trust.coach_lock_served(trust.load_comments(raw), since=since)
        assert got is (want == "pass"), name


def test_served_refusals_and_shapes():
    posted = trust.load_comments(RP_FIXTURES["posted"]())
    assert trust.served(posted, reviewer="jane", sha=HEAD)
    with pytest.raises(ValueError):
        trust.served(posted, reviewer="jane", sha=HEAD.upper())
    with pytest.raises(ValueError):
        trust.served(posted, reviewer="jane", sha=HEAD, since="2026-10-05T12:00:00")
    with pytest.raises(ValueError):
        trust.coach_lock_served([], since="")
    # a page list is read as its pages (the --slurp shape), as the scripts do
    assert trust.served([posted], reviewer="jane", sha=HEAD)
    assert trust.load_comments("") == [] and trust.load_comments('{"body": "x"}') == [{"body": "x"}]
    assert not trust.served([{"body": None, "user": None}, "junk"], reviewer="jane", sha=HEAD)


def test_actions_bot_spellings():
    assert trust.is_actions_bot("github-actions[bot]") and trust.is_actions_bot("github-actions")
    assert trust.is_actions_bot(" GitHub-Actions[BOT] ")
    for login in ("github-actions[bot][bot]", "github-actions-bot", "cursor[bot]", "shaiss", "", None, 7):
        assert not trust.is_actions_bot(login), login


def _mcp_footer() -> str:
    tree = ast.parse((REPO / ".claude" / "reviewer-post" / "reviewer_mcp.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FOOTER" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("reviewer_mcp.py has no FOOTER")


def _script_footer(script, var) -> str:
    m = re.search(rf"^{var}=\$'(.*)'$", script.read_text(encoding="utf-8"), re.M)
    assert m, f"{script.name}: no {var}"
    return m.group(1).replace("\\n", "\n")


def test_footer_drift_pin():
    """A 1-byte FOOTER change (in digest.FOOTER vs reviewer_mcp.FOOTER) fails this test."""
    mcp_footer = _mcp_footer()
    assert digest.FOOTER == mcp_footer
    assert _script_footer(RP_SCRIPT, "REVIEWER_FOOTER") == mcp_footer
    assert _script_footer(CL_SCRIPT, "COACH_FOOTER") == mcp_footer

    def agrees(candidate: str) -> bool:
        return candidate == mcp_footer

    # negative controls: every 1-byte edit is caught by the pin …
    for edited in (mcp_footer[:-1], mcp_footer + " ", mcp_footer.replace("---", "--_"), "x" + mcp_footer[1:]):
        assert not agrees(edited)
    # … and the served rule itself depends on the exact bytes: an MCP post assembled with a
    # 1-byte-different footer is not served.
    body = f"Jane.\n\n{jane}\n\n" + mcp_footer[:-1] + "*"
    assert not trust.served([{"body": body, "user": bot}], reviewer="jane", sha=HEAD)
    assert trust.served([{"body": f"Jane.\n\n{jane}\n\n{mcp_footer}", "user": bot}], reviewer="jane", sha=HEAD)


# ---------------------------------------------------------------------------
# Tiers over the committed fixtures.

SIGNOFFS = ("JANE_SIGNOFF", "DRIK_SIGNOFF")


def _family(marker_line: str) -> str:
    return markers.parse_marker(marker_line).family


def signoff_marker(d: dict) -> str | None:
    """The extractor's choice (extract.py): ``suffix_markers[-1]`` when it is a sign-off, else
    the LAST sign-off line of ``marker_lines``."""
    suffix = d["suffix_markers"]
    if suffix and _family(suffix[-1]) in SIGNOFFS:
        return suffix[-1]
    lines = [m for m in d["marker_lines"] if _family(m) in SIGNOFFS]
    return lines[-1] if lines else None


def signoff_tiers(n: int):
    out = []
    for c in raw_pr(n)["issue_comments"]:
        marker = signoff_marker(c["body"])
        if marker is None:
            continue
        parsed = markers.parse_signoff(markers.parse_marker(marker))
        login = (c["user"] or {}).get("login")
        tier = trust.comment_tier(kind="review.signoff", login=login, owner_login=OWNER_LOGIN, digest=c["body"],
                                  created_at=c["created_at"], updated_at=c["updated_at"], edit_grace_seconds=60,
                                  marker_sha=parsed["sha"])
        out.append((parsed["family"], login, parsed["sha"], tier))
    return out


def test_owner_token_signoffs_are_claimed():
    """NVC-6: the 13 DRIK_SIGNOFF comments authored by shaiss on #636 are claimed (basis marker:owner-token), none verified."""
    own = [t for t in signoff_tiers(636) if t[1] == OWNER_LOGIN]
    assert len(own) == 13
    assert {family for family, *_ in own} == {"DRIK_SIGNOFF"}
    assert {tier for *_, tier in own} == {("claimed", "marker:owner-token")}
    # some of them carry a perfect MCP suffix — the author alone demotes them
    suffixed = [c for c in raw_pr(636)["issue_comments"]
                if (c["user"] or {}).get("login") == OWNER_LOGIN and c["body"]["suffix_ok"]]
    assert suffixed
    # NVC-7's input: the distinct (family, sha) pairs among them
    assert len({(family, sha) for family, _, sha, _ in own}) == 9


def test_owner_token_drik_on_calibration_cube():
    """CC-6's input: the 11 owner-token DRIK_SIGNOFF comments on #634 are claimed, none verified."""
    own = [t for t in signoff_tiers(634) if t[1] == OWNER_LOGIN]
    assert len(own) == 11 and {f for f, *_ in own} == {"DRIK_SIGNOFF"}
    assert {tier for *_, tier in own} == {("claimed", "marker:owner-token")}


def test_verified_count_for_nuggs_vent_cap():
    """P1a: exactly 12 sign-offs on #636 are verified (6 Jane + 6 Drik)."""
    tiers = signoff_tiers(636)
    verified = [t for t in tiers if t[3] == ("verified", "actions-bot+suffix")]
    assert len(verified) == 12
    assert sorted(f for f, *_ in verified) == ["DRIK_SIGNOFF"] * 6 + ["JANE_SIGNOFF"] * 6
    assert {login for _, login, _, _ in verified} == {"github-actions[bot]"}
    assert len(tiers) == 25  # every sign-off comment is either one of the 12 or one of the 13


def _tier(kind, body, *, login="github-actions[bot]", created="2026-10-05T12:00:00Z",
          updated="2026-10-05T12:00:00Z", marker_sha=HEAD, grace=60):
    return trust.comment_tier(kind=kind, login=login, owner_login="shaiss", digest=digest.body_digest(body),
                              created_at=created, updated_at=updated, edit_grace_seconds=grace,
                              marker_sha=marker_sha)


def test_edited_comment_drops_to_claimed():
    """updated_at - created_at >= edit_grace_seconds demotes a verified suffix to claimed (marker:edited)."""
    body = f"Jane.\n\n{jane}\n\n{FOOTER}"
    assert _tier("review.signoff", body, updated="2026-10-05T12:00:59Z") == ("verified", "actions-bot+suffix")
    assert _tier("review.signoff", body, updated="2026-10-05T12:01:00Z") == ("claimed", "marker:edited")
    assert _tier("review.signoff", body, updated=None) == ("verified", "actions-bot+suffix")
    assert _tier("review.signoff", body, updated="2026-10-05T12:00:30Z", grace=30) == ("claimed", "marker:edited")
    assert trust.is_edited("2026-10-05T12:00:00Z", "2026-10-06T12:00:00Z", 60)
    with pytest.raises(ValueError):
        trust.is_edited("2026-10-05", "2026-10-06T12:00:00Z", 60)
    with pytest.raises(ValueError):
        trust.is_edited("2026-10-05T12:00:00Z", None, -1)


def test_comment_tier_rules_per_kind():
    signoff = f"Jane.\n\n{jane}\n\n{FOOTER}"
    assert _tier("review.signoff", signoff) == ("verified", "actions-bot+suffix")
    assert _tier("review.signoff", signoff, marker_sha=OLD) == ("claimed", "marker:no-suffix")
    assert _tier("review.signoff", f"Jane.\n\n{FOOTER}\n\n{jane}\n") == ("claimed", "marker:no-suffix")  # M3
    assert _tier("review.signoff", signoff, login="shaiss") == ("claimed", "marker:owner-token")
    assert _tier("review.signoff", signoff, login="ShaIss") == ("claimed", "marker:owner-token")
    assert _tier("review.signoff", signoff, login="cursor[bot]") == ("claimed", "marker:other-author")
    assert _tier("review.signoff", signoff, login=None) == ("claimed", "marker:other-author")
    fail = f"<!-- JANE_SIGNOFF sha={HEAD} verdict=fail fuse=none -->"
    assert _tier("review.signoff", f"x\n\n{fail}\n\n{FOOTER}") == ("claimed", "marker:no-suffix")
    # triage: PM_TRIAGE_DONE for the triage marker's own sha
    triage = f"t\n\n{pm_full}\n\n{FOOTER}"
    assert _tier("triage.verdict", triage) == ("verified", "actions-bot+suffix")
    assert _tier("triage.verdict", triage, marker_sha=OLD) == ("claimed", "marker:no-suffix")
    assert _tier("triage.verdict", triage, marker_sha=None) == ("claimed", "marker:no-suffix")
    assert _tier("triage.verdict", f"t\n\n<!-- PM_TRIAGE design=demo sha={HEAD} -->\n") == ("claimed", "marker:no-suffix")
    # coach lock: the ordered pair
    lock = f"r\n\n{coach_full}\n\n{FOOTER}"
    assert _tier("coach.lock", lock) == ("verified", "actions-bot+suffix")
    assert _tier("coach.lock", lock, marker_sha=None) == ("verified", "actions-bot+suffix")
    assert _tier("coach.lock", lock, marker_sha=OLD) == ("claimed", "marker:no-suffix")
    assert _tier("coach.lock", f"r\n\n{coach_done}\n\n{FOOTER}") == ("claimed", "marker:no-suffix")
    assert _tier("coach.lock", "🎓 COACH-LOCK\n\nkickoff") == ("claimed", "marker:no-suffix")
    # oracle: the head marker and the footer
    oracle = f"{trust.ORACLE_MARKER}\n\n## Oracle\n\n{FOOTER}"
    assert _tier("oracle.review", oracle) == ("verified", "actions-bot+head-marker")
    assert _tier("oracle.review", f"{trust.ORACLE_MARKER}\n\n## Oracle") == ("claimed", "marker:no-suffix")
    assert _tier("oracle.review", f"## Oracle\n\n{trust.ORACLE_MARKER}\n\n{FOOTER}") == ("claimed", "marker:no-suffix")
    # a kind with no marker rule: only the login is known
    assert _tier("coach.round", "Round 2 — x") == ("login", "login")
    assert _tier("brief.claimed", "🚢 SHIP-LOCK", login=None) == ("none", "none")


def test_triage_tiers_on_nuggs_vent_cap():
    """The six M5 triage comments on #636 (PM_TRIAGE then PM_TRIAGE_DONE) are verified for their own sha."""
    got = []
    for c in raw_pr(636)["issue_comments"]:
        lines = [m for m in c["body"]["marker_lines"] if m.startswith("<!-- PM_TRIAGE ")]
        if not lines:
            continue
        sha = markers.parse_pm_triage(markers.parse_marker(lines[-1]))["sha"]
        got.append(trust.comment_tier(kind="triage.verdict", login=c["user"]["login"], owner_login=OWNER_LOGIN,
                                      digest=c["body"], created_at=c["created_at"], updated_at=c["updated_at"],
                                      edit_grace_seconds=60, marker_sha=sha))
    assert got == [("verified", "actions-bot+suffix")] * 6


def _auto_review_runs() -> set[int]:
    return {r["run"]["id"] for r in receipts() if r["workflow"] == "auto-review.yml"}


def test_status_trust_needs_actions_creator_and_receipt():
    """A reviewer-signoff status by github-actions[bot] whose target run is an auto-review receipt is verified; created by the owner it is claimed."""
    ids = _auto_review_runs()
    statuses = [s for sts in raw_pr(636)["statuses"].values() for s in sts if s["context"] == "reviewer-signoff"]
    assert len(statuses) == 22
    assert {trust.status_tier(s, ids) for s in statuses} == {("verified", "actions-status+receipt")}
    one = statuses[0]
    assert trust.status_tier(dict(one, creator="shaiss"), ids, owner_login="shaiss") == ("claimed", "marker:owner-token")
    assert trust.status_tier(dict(one, creator="shaiss"), ids) == ("claimed", "marker:other-author")
    assert trust.status_tier(dict(one, creator="cursor[bot]"), ids) == ("claimed", "marker:other-author")
    assert trust.status_tier(one, set()) == ("login", "login")  # no receipt vouches for the run
    assert trust.status_tier(dict(one, target_url=None), ids) == ("login", "login")
    assert trust.status_tier(dict(one, target_url="https://vercel.com/x/actions/runs/1"), ids) == ("login", "login")
    assert trust.status_tier(dict(one, creator=None), ids) == ("none", "none")
    rid = trust.run_id_of(one["target_url"])
    assert rid in ids and trust.run_id_of(one["target_url"] + "/job/5") == rid
    assert trust.run_id_of(f"https://github.com/o/r/actions/runs/{rid}x") is None


def test_selftest_cases_hold():
    cases = trust.selftest_cases()
    assert len(cases) >= 12
    for label, case in cases:
        assert label.startswith("trust: ")
        assert case() is True, label
