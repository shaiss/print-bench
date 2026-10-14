"""digest: what replaces prose (scaffold-implemented; H2 owns and extends).

The real-data checks below were computed over the scaffold's raw capture and
are pinned through the committed (digested) fixtures, so they run in CI
without any body.
"""

from __future__ import annotations

import pathlib
import re

from conftest import REPO, raw_brief, raw_pr
from provenance import digest

FOOTER = digest.FOOTER


def test_footer_is_byte_identical_to_the_reviewer_mcp_and_both_scripts():
    mcp = (REPO / ".claude" / "reviewer-post" / "reviewer_mcp.py").read_text(encoding="utf-8")
    m = re.search(r'^FOOTER = "(.*)"$', mcp, re.M)
    assert m and m.group(1).encode().decode("unicode_escape") == FOOTER
    for script, var in (("reviewer-posted.sh", "REVIEWER_FOOTER"), ("coach-lock-check.sh", "COACH_FOOTER")):
        text = (REPO / "scripts" / script).read_text(encoding="utf-8")
        m = re.search(rf"^{var}=\$'(.*)'$", text, re.M)
        assert m and m.group(1).replace("\\n", "\n") == FOOTER, script


def test_regen_subject_matches_reviewer_signoff():
    text = (REPO / "scripts" / "reviewer-signoff.sh").read_text(encoding="utf-8")
    assert f'REGEN_SUBJECT="{digest.REGEN_SUBJECT}"' in text


def test_mcp_suffix_and_planted_markers():
    sha = "0" * 40
    jane = f"<!-- JANE_SIGNOFF sha={sha} verdict=pass fuse=none -->"
    drik = f"<!-- DRIK_SIGNOFF sha={sha} verdict=block fuse=none -->"
    ok = digest.body_digest(f"Jane here.\n\n{jane}\n\n{FOOTER}")
    assert ok["suffix_ok"] and ok["suffix_markers"] == [jane] and ok["footer_ok"]
    # marker AFTER the footer (the M3 gh-posted era) is not an MCP suffix
    late = digest.body_digest(f"Jane here.\n\n{FOOTER}\n\n{jane}\n")
    assert not late["suffix_ok"] and late["marker_lines"] == [jane]
    # sibling plant: the suffix is Drik's, never Jane's
    sib = digest.body_digest(f"x\n\n{jane}\n\n{drik}\n\n{FOOTER}")
    assert sib["suffix_markers"] == [jane, drik] and sib["suffix_ok"]
    # case-folded family is not a marker shape the MCP emits
    assert not digest.body_digest(f"x\n\n{jane.lower()}\n\n{FOOTER}")["suffix_ok"]
    # an inline-quoted marker is not a full-line marker
    assert digest.body_digest("sticky `<!-- printcheck-gate-report -->` for x")["marker_lines"] == []


def test_coach_pair_suffix():
    sha = "a" * 40
    d = digest.body_digest(f"round 1\n\n<!-- COACH_LOCK -->\n\n<!-- COACH_DONE sha={sha} -->\n\n{FOOTER}")
    assert d["suffix_markers"] == ["<!-- COACH_LOCK -->", f"<!-- COACH_DONE sha={sha} -->"]


def test_table_verdict_tokens():
    body = ("| Finding | Verdict | Why |\n|---|---|---|\n| a | **act-now** | x |\n"
            "| b | **decline** the claim, **act-now** the kernel | y |\n| c | no action — credit | z |\n"
            "| d | **queue** | w |\n| e | ? | v |\n\nprose | not a row\n")
    assert digest.table_verdicts(body) == ["act-now", "act-now+decline", "no-action", "queue", "unknown"]


def test_lead_classes_and_fields():
    assert digest.classify_lead("🚢 SHIP-LOCK — running\n\n**Design name:** `sbc-case`\n") == \
        ("ship_lock", {"design_name": "sbc-case"})
    assert digest.classify_lead("🚢 SHIP-LOCK WITHDRAWN — x")[0] == "ship_lock_withdrawn"
    assert digest.classify_lead("✅ **SHIPPED — gated draft PR: #636** (url)") == \
        ("shipped", {"shipped_pr": 636, "design_name": None})
    assert digest.classify_lead("📦 **Draft PR opened: #371** — x")[1]["shipped_pr"] == 371
    assert digest.classify_lead("Round 2b — **one push, `abc`**")[1] == {"round": 2, "round_sub": "b"}
    assert digest.classify_lead("<!-- M -->\n<h3>Bugbot couldn't run - usage limit reached</h3>")[0] == "bugbot_limit"
    assert digest.classify_lead("Hi! Jane here 👋") == (None, {})


def test_refs_closes_drops_issue_zero():
    """``#0`` names no issue (contract body-digest@1.refs_closes is ``min 1``): it is dropped, while
    every positive number — leading zeros included, the pre-integration behaviour — is kept."""
    assert digest.refs_closes("Closes #0\nfixes #901\nResolves: #00") == [901]
    assert digest.refs_closes("Closes #0123") == [123]
    assert digest.body_digest("Closes #0")["refs_closes"] == []
    # Negative control: without the filter the same body would carry the invalid 0.
    assert sorted({int(n) for n in digest._CLOSES_RE.findall("Closes #0")}) == [0]


def test_message_digest_trailers():
    msg = ("Fix x\n\nbody\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_01WCMY5F5seUgxYPnyibzYs1\nPreview-Diff: maybe\n")
    d = digest.message_digest(msg)
    assert [t["key"] for t in d["trailers"]] == ["Co-Authored-By", "Claude-Session"]
    assert digest.message_digest("Add design: x (#636)")["subject_pr"] == 636
    assert digest.message_digest(digest.REGEN_SUBJECT + "\n\nPreview-Diff: all-noise")["subject_regen"]


def test_real_fixture_counts_survive_digesting():
    # NVC-5/NVC-12/NVC-13/SBC-6 inputs, recomputed from digests only.
    def bot(c):
        login = (c["user"] or {}).get("login", "").lower()
        return login.removesuffix("[bot]") == "github-actions"
    c636 = raw_pr(636)["issue_comments"]
    verified = [c for c in c636 if bot(c) and c["body"]["suffix_ok"]
                and c["body"]["suffix_markers"][-1].split()[1] in ("JANE_SIGNOFF", "DRIK_SIGNOFF")]
    assert len(verified) == 12
    assert sum(c["body"]["lead"] == "bugbot_limit" for c in c636) == 21
    assert sum(c["body"]["lead"] == "qodo_paused" for c in c636) == 1
    last_fix = "2026-10-11T21:53:02Z"
    act_now = sum(1 for c in c636 if c["created_at"] > last_fix
                  and any(m.startswith("<!-- PM_TRIAGE ") for m in c["body"]["marker_lines"])
                  for v in c["body"]["table_verdicts"] if "act-now" in v)
    assert act_now == 21
    assert sum(c["body"]["lead"] == "coach_round" for c in raw_pr(397)["issue_comments"]) == 13
    assert [c["body"]["lead_fields"].get("design_name") for c in raw_brief(592)["comments"]][:1] == ["nuggs-vent-cap"]
