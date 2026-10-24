#!/usr/bin/env bash
# reviewer-posted: derive a reviewer link's outcome from the artifact (issue
# #762). claude-code-action exits 0 whenever the agent ends its turn without
# an API error — even when it never posted (a provider quota hit mid-run is
# one way this happens). An exit-0 reviewer step therefore reads as 'success'
# to auto-review.yml's chain walk (skipping links 2–6) and to its round stamp
# (marking the commit reviewed) while the PR carries no review at all. This
# script answers the only question those gates may trust, mirroring what
# routine-lock-cleanup.sh (#538) does for the ship routines: did a review
# comment carrying that reviewer's sign-off marker for THIS head sha land?
#
# Trust boundary (the MEDIUM finding on PR #771 / discussion_r4185453576):
# a planted `<!-- JANE_SIGNOFF … -->` / `<!-- DRIK_SIGNOFF … -->` substring
# from any other author must NOT count. The only writer of those markers is
# `.claude/reviewer-post/reviewer_mcp.py`, which posts via the workflow's
# `GITHUB_TOKEN` as `github-actions[bot]` (GraphQL login `github-actions`)
# to `POST /repos/.../issues/{REVIEWER_PR}/comments`, assembling
#   {caller body}\n\n{marker}\n\n{FOOTER}
# server-side. So a served verdict requires ALL of:
#   1. an Actions-bot author (the MCP posting identity — sibling pin:
#      coach-lock-check.sh);
#   2. the body *ends* with the MCP-assembled marker-then-footer suffix for
#      THIS reviewer and THIS head sha (a Jane/Drik/PM sibling that shares
#      github-actions[bot] always ends with its OWN family marker, so a
#      planted cross-family marker in the caller body cannot be the suffix —
#      the same reason coach-lock-check requires the suffix, not a substring);
#   3. when `--since` is set, `created_at >= since` (this run/round — the
#      coach-lock-check pattern), so a lock from an earlier run on the same
#      head cannot short-circuit a fresh chain walk.
#
# The marker shapes are the ones the reviewer MCP emits —
#   <!-- JANE_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
#   <!-- DRIK_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
#   <!-- PM_TRIAGE_DONE sha=<40hex> -->   (issue #770; PM_TRIAGE stays for §8)
#   <!-- COACH_DONE sha=<40hex> -->       (issue #770; COACH_LOCK stays for #806)
# — exact family spelling (the MCP never case-folds), with the hardcoded
# Claude Code footer byte-identical to reviewer_mcp.py's FOOTER.
#
# Usage:
#   scripts/reviewer-posted.sh check --pr <N> --sha <40hex> --reviewer jane|drik|pm|coach
#       [--repo <owner/name>] [--comments-file <path>] [--since <ISO8601>]
#     Prints `true` or `false` (exit 0 either way — a clean negative is a
#     decision, not an error) and, when $GITHUB_OUTPUT is set, appends
#     `served=<value>` to it. --comments-file drives the core over a JSON
#     snapshot of issue comments (the selftest's seam); live mode needs
#     GH_TOKEN and reads ONLY issue comments — the MCP's sole write target.
#     Exit 1 = the artifact read itself failed: a check that cannot read must
#     fail loud, never guess — a silent `false` here would fail the walk open.
#
#   scripts/reviewer-posted.sh diagnose --pr <N> --sha <40hex> --reviewer …
#       [--since <ISO8601>] [--link <n>] [--cap-state <path>]
#       [--execution-log <path>] [--repo <owner/name>] [--comments-file <path>]
#     Advisory (always exit 0 unless the args are unusable): when a link's
#     artifact check reads served=false, print why — whether post_review
#     (etc.) appears in the claude-code-action execution log, which tools
#     were denied, whether a bot comment landed with a *wrong* sha (the
#     PR #559 / run 37530117408 Drik failure: posted 073fd1af… while head
#     was 169898ab…, burning the one-post cap), and whether the walk cap
#     state file already records a post. Does not weaken the check.
#
#   scripts/reviewer-posted.sh --selftest
#     The decision rows (posted / not posted / wrong sha / wrong author /
#     planted suffix / sibling family / stale-since / malformed) plus the
#     refusal rows (typo'd reviewer, bad sha, live mode without GH_TOKEN)
#     and a drift pin against the MCP's FOOTER + the marker literals the
#     two skills document — so this script cannot quietly stop matching
#     what the posting surface emits.
#
# Consumers: auto-review.yml — the per-link artifact checks after each
# Jane/Drik/pm-triage/design-coach ship step (the chain walk's fall-through
# key), and the review stamp's confirmation before a round is called
# complete. Issue #770 closed the exit-code hole for pm-triage and the
# design coach with per-head completion markers (PM_TRIAGE_DONE / COACH_DONE)
# that this script reads the same way it reads JANE/DRIK_SIGNOFF.
set -euo pipefail

# A prior Bash-capable coach/reviewer step can write PYTHONPATH/LD_PRELOAD
# via GITHUB_ENV. Isolated mode ignores those; also drop them in this shell
# so `gh` is not preloaded either (coach-lock-check.sh's belt).
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \
      PYTHONEXECUTABLE LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT \
      DYLD_INSERT_LIBRARIES BASH_ENV ENV || true
export PYTHONNOUSERSITE=1

cd "$(dirname "$0")/.."

# Prefer the system interpreter; -I ignores PYTHONPATH/PYTHONHOME/user site.
if [[ -x /usr/bin/python3 ]]; then
  PYTHON3=/usr/bin/python3
else
  PYTHON3=python3
fi

# Byte-identical to reviewer_mcp.py FOOTER — the MCP always appends this
# after the server-assembled marker. A planted marker without this exact
# footer is not an MCP post.
REVIEWER_FOOTER=$'---\n_Generated by [Claude Code](https://claude.ai/code)_'
export REVIEWER_FOOTER

usage() {  # [message]
  [ $# -eq 0 ] || echo "reviewer-posted: $*" >&2
  cat >&2 <<'EOF'
usage: scripts/reviewer-posted.sh check --pr <N> --sha <40hex> --reviewer jane|drik|pm|coach
           [--repo <owner/name>] [--comments-file <path>] [--since <ISO8601>]
       scripts/reviewer-posted.sh diagnose --pr <N> --sha <40hex> --reviewer jane|drik|pm|coach
           [--since <ISO8601>] [--link <n>] [--cap-state <path>]
           [--execution-log <path>] [--repo <owner/name>] [--comments-file <path>]
       scripts/reviewer-posted.sh --selftest
EOF
  exit 2
}

# The pure core: does the comments JSON carry an Actions-bot issue comment
# whose body ends with the MCP-assembled marker-then-footer suffix for this
# reviewer + sha (and, when SINCE is set, created_at >= SINCE)?
served_from_comments() {  # stdin = comments JSON; env: REVIEWER_SHA, REVIEWER_FAMILY, REVIEWER_SINCE?, REVIEWER_FOOTER
  "$PYTHON3" -I -c '
import json, os, sys

FOOTER = os.environ["REVIEWER_FOOTER"]
SHA = os.environ["REVIEWER_SHA"]
FAMILY = os.environ["REVIEWER_FAMILY"]
SINCE = os.environ.get("REVIEWER_SINCE", "").strip()
BOT = "github-actions"

# Exact MCP-assembled suffixes for THIS family + sha. Case-sensitive
# family: the MCP emits uppercase. Jane/Drik carry verdict/fuse (the
# closed sets reviewer_mcp.py validates); pm/coach completion markers
# (issue #770) are sha-only. post_* assembles `{body}\n\n{marker}\n\n{FOOTER}`
# (pm/coach may put a sibling marker ahead of the completion one); a
# sibling Actions-bot post always ends with its OWN family marker before
# the same footer, so a planted cross-family marker in the caller body
# cannot be the suffix (coach-lock-check.sh'\''s reason for requiring
# the suffix).
if FAMILY.endswith("_SIGNOFF"):
    SUFFIXES = tuple(
        f"<!-- {FAMILY} sha={SHA} verdict={v} fuse={f} -->\n\n{FOOTER}"
        for v in ("pass", "block")
        for f in ("none", "acknowledged")
    )
else:
    # PM_TRIAGE_DONE / COACH_DONE — one shape, no verdict/fuse.
    SUFFIXES = (f"<!-- {FAMILY} sha={SHA} -->\n\n{FOOTER}",)


def is_actions_bot(comment):
    """REST login is github-actions[bot]; GraphQL is github-actions."""
    user = comment.get("user") or {}
    login = (user.get("login") or "").strip().lower()
    if login.endswith("[bot]"):
        login = login[:-5]
    return login == BOT


def load_comments(raw):
    """Decode `gh api --paginate` output into one comment list.

    One page is a JSON array. Multiple pages are either concatenated arrays
    (default --paginate) or an outer array of page arrays (--slurp). Either
    way every comment must be visible — a marker on page 2 must still count.
    """
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        idx = 0
        out = []
        while idx < len(raw):
            while idx < len(raw) and raw[idx].isspace():
                idx += 1
            if idx >= len(raw):
                break
            obj, end = decoder.raw_decode(raw, idx)
            if isinstance(obj, list):
                out.extend(obj)
            else:
                out.append(obj)
            idx = end
        return out
    if isinstance(data, list):
        if data and all(isinstance(p, list) for p in data):
            return [c for page in data for c in page]
        return data
    return [data]


def ends_with_mcp_suffix(body):
    return any(body.endswith(s) for s in SUFFIXES)


raw = sys.stdin.read()
for c in load_comments(raw):
    if not is_actions_bot(c):
        continue
    body = c.get("body") or ""
    if not ends_with_mcp_suffix(body):
        continue
    if SINCE:
        created = (c.get("created_at") or "").strip()
        if not created or created < SINCE:
            continue
    print("true")
    raise SystemExit(0)
print("false")
'
}

# The live thread read: ONLY issue comments — the MCP's sole write target
# (POST /issues/{n}/comments). Review bodies and line comments are out of
# scope; a planted marker there cannot satisfy the walk/stamp.
gh_comments() {  # $1 = owner/name, $2 = PR number
  gh api --paginate --slurp "/repos/$1/issues/$2/comments?per_page=100"
}

check() {
  local reviewer="" pr="" sha="" repo="${GITHUB_REPOSITORY:-}" comments_file="" since=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --pr) pr="${2:?}"; shift 2 ;;
      --sha) sha="${2:?}"; shift 2 ;;
      --reviewer) reviewer="${2:?}"; shift 2 ;;
      --repo) repo="${2:?}"; shift 2 ;;
      --comments-file) comments_file="${2:?}"; shift 2 ;;
      --since) since="${2:?}"; shift 2 ;;
      *) usage "unknown option: $1" ;;
    esac
  done
  # A typo'd reviewer or a bad sha must fail loud here, not match nothing and
  # read as "not served" — that would burn all six chain links on a typo.
  case "$reviewer" in
    jane|drik|pm|coach) ;;
    *) usage "--reviewer must be jane, drik, pm or coach (got: ${reviewer:-empty})" ;;
  esac
  [[ "$pr" =~ ^[0-9]+$ ]] || usage "--pr must be a number (got: ${pr:-empty})"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || usage "--sha must be 40 hex chars (got: ${sha:-empty})"
  if [[ -n "$since" ]]; then
    # ISO-8601 UTC to the second — lexical compare matches chronological
    # order for this fixed-width form (coach-lock-check.sh's rule).
    [[ "$since" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]] \
      || usage "--since must be UTC ISO8601 to the second (YYYY-MM-DDTHH:MM:SSZ); got ${since}"
  fi

  local comments
  if [[ -n "$comments_file" ]]; then
    comments="$(cat -- "$comments_file")"
  else
    command -v gh >/dev/null 2>&1 || { echo "reviewer-posted: gh is not installed" >&2; exit 1; }
    [[ -n "${GH_TOKEN:-}" ]] || { echo "reviewer-posted: GH_TOKEN is not set (live check needs it)" >&2; exit 1; }
    [[ -n "$repo" ]] || usage "--repo is required in live mode (or set GITHUB_REPOSITORY)"
    if ! comments="$(gh_comments "$repo" "$pr")"; then
      echo "reviewer-posted: could not read PR #$pr's issue comments" >&2
      exit 1
    fi
  fi

  local verdict
  export REVIEWER_SHA="$sha"
  case "$reviewer" in
    jane|drik) export REVIEWER_FAMILY="${reviewer^^}_SIGNOFF" ;;
    pm)        export REVIEWER_FAMILY="PM_TRIAGE_DONE" ;;
    coach)     export REVIEWER_FAMILY="COACH_DONE" ;;
  esac
  if [[ -n "$since" ]]; then
    export REVIEWER_SINCE="$since"
  else
    unset REVIEWER_SINCE || true
  fi
  verdict="$(served_from_comments <<<"$comments")"
  printf '%s\n' "$verdict"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'served=%s\n' "$verdict" >>"$GITHUB_OUTPUT"
  fi
}

# Advisory diagnosis after a served=false artifact check. Never fails the
# walk — the check already decided; this only makes the log say why.
diagnose() {
  local reviewer="" pr="" sha="" repo="${GITHUB_REPOSITORY:-}" comments_file="" \
        since="" link="" cap_state="${REVIEWER_POST_STATE:-}" \
        execution_log="${RUNNER_TEMP:+$RUNNER_TEMP/claude-execution-output.json}"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --pr) pr="${2:?}"; shift 2 ;;
      --sha) sha="${2:?}"; shift 2 ;;
      --reviewer) reviewer="${2:?}"; shift 2 ;;
      --repo) repo="${2:?}"; shift 2 ;;
      --comments-file) comments_file="${2:?}"; shift 2 ;;
      --since) since="${2:?}"; shift 2 ;;
      --link) link="${2:?}"; shift 2 ;;
      --cap-state) cap_state="${2:?}"; shift 2 ;;
      --execution-log) execution_log="${2:?}"; shift 2 ;;
      *) usage "unknown option: $1" ;;
    esac
  done
  case "$reviewer" in
    jane|drik|pm|coach) ;;
    *) usage "--reviewer must be jane, drik, pm or coach (got: ${reviewer:-empty})" ;;
  esac
  [[ "$pr" =~ ^[0-9]+$ ]] || usage "--pr must be a number (got: ${pr:-empty})"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || usage "--sha must be 40 hex chars (got: ${sha:-empty})"

  local label="reviewer-posted diagnose"
  [[ -n "$link" ]] && label="$label (link $link)"
  echo "::group::$label — why served=false for ${reviewer} @ ${sha:0:12}"

  # 1) Execution log: denials, whether the post tool was invoked, errors.
  if [[ -n "$execution_log" && -f "$execution_log" ]]; then
    local _py
    _py="$(mktemp)"
    cat >"$_py" <<'PY'
import json, os, re

path = os.environ["REVIEWER_DIAG_LOG"]
who = os.environ["REVIEWER_DIAG_WHO"]
post_tools = {
    "jane": "mcp__reviewer__post_review",
    "drik": "mcp__reviewer__post_review",
    "pm": "mcp__reviewer__post_triage",
    "coach": "mcp__reviewer__post_coach",
}
want = post_tools.get(who, "mcp__reviewer__post_review")
try:
    raw = open(path, encoding="utf-8", errors="replace").read()
except OSError as e:
    print("execution-log: unreadable (%s)" % e)
    raise SystemExit(0)

objs = []
raw_s = raw.strip()
if raw_s.startswith("["):
    try:
        objs = json.loads(raw_s)
    except json.JSONDecodeError:
        objs = []
elif raw_s.startswith("{"):
    try:
        objs = [json.loads(raw_s)]
    except json.JSONDecodeError:
        objs = []
if not objs:
    dec = json.JSONDecoder()
    idx = 0
    while idx < len(raw_s):
        while idx < len(raw_s) and raw_s[idx].isspace():
            idx += 1
        if idx >= len(raw_s):
            break
        try:
            obj, end = dec.raw_decode(raw_s, idx)
        except json.JSONDecodeError:
            break
        objs.append(obj)
        idx = end

text = raw
denials = []
for obj in objs:
    if not isinstance(obj, dict):
        continue
    if obj.get("type") == "result":
        print(
            "execution-log result: is_error=%s num_turns=%s "
            "permission_denials_count=%s cost_usd=%s subtype=%s"
            % (
                obj.get("is_error"),
                obj.get("num_turns"),
                obj.get("permission_denials_count"),
                obj.get("total_cost_usd"),
                obj.get("subtype"),
            )
        )
        res = obj.get("result") or obj.get("errors") or ""
        if isinstance(res, str) and res.strip():
            print("execution-log result text (first 800 chars):")
            print(res.strip()[:800])
        elif isinstance(res, list):
            print("execution-log errors:", res[:5])
        dens = obj.get("permission_denials") or obj.get("permissionDenials") or []
        if dens:
            denials = dens
        mu = obj.get("modelUsage") or obj.get("model_usage") or {}
        if mu:
            print("execution-log models:", ", ".join(mu.keys()))
    for key in ("permission_denials", "permissionDenials"):
        if isinstance(obj.get(key), list):
            denials.extend(obj[key])

posted = want in text
print(
    "execution-log post tool %r: %s"
    % (want, "mentioned in log" if posted else "NOT mentioned in log")
)

names = []
for d in denials:
    if isinstance(d, dict):
        n = d.get("tool_name") or d.get("toolName") or d.get("name") or d.get("tool")
        names.append(str(n) if n else json.dumps(d)[:200])
    else:
        names.append(str(d)[:200])
if not names:
    for m in re.finditer(
        r"(?:denied|permission_denial)[^\n]{0,120}"
        r"(Bash\([^)]*\)|Write|Edit|mcp__\w+|NotebookEdit|Agent)",
        text,
        re.I,
    ):
        names.append(m.group(1))
if names:
    seen = set()
    uniq = []
    for n in names:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    print("execution-log denied tools:", "; ".join(uniq[:20]))
else:
    print(
        "execution-log denied tools: (none listed — enable show_full_output "
        "on the ship step if you need the per-tool list)"
    )

for pat in (
    r"You have reached your specified API usage limits[^\"]*",
    r"credit balance is too low[^\"]*",
    r"invalid_api_key[^\"]*",
    r"HTTP 4\d\d[^\n]{0,200}",
):
    m = re.search(pat, text)
    if m:
        print("execution-log provider error:", m.group(0)[:300])
        break
PY
    REVIEWER_DIAG_LOG="$execution_log" REVIEWER_DIAG_WHO="$reviewer" \
      "$PYTHON3" -I "$_py" || true
    rm -f -- "$_py"
  else
    echo "execution-log: not found${execution_log:+ at $execution_log}"
  fi

  # 2) Cap state — a prior (possibly wrong-sha) post strands later links.
  if [[ -n "$cap_state" ]]; then
    if [[ -f "$cap_state" || -f "${cap_state}.posted" ]]; then
      echo "cap-state: PRESENT at $cap_state (a post already recorded this run;"
      echo "  later links cannot post — if that post used a stale sha, the"
      echo "  artifact check stays served=false for the real head)"
      if [[ -f "$cap_state" ]]; then
        head -n 5 -- "$cap_state" | sed 's/^/cap-state record: /' || true
      fi
      if [[ -f "${cap_state}.posted" ]]; then
        echo "cap-state: .posted sidecar present"
      fi
    else
      echo "cap-state: empty (no successful post recorded this run yet)"
    fi
  else
    echo "cap-state: REVIEWER_POST_STATE unset"
  fi

  # 3) Thread scan — bot comments with this family, any sha, since SINCE.
  local comments family
  case "$reviewer" in
    jane|drik) family="${reviewer^^}_SIGNOFF" ;;
    pm)        family="PM_TRIAGE_DONE" ;;
    coach)     family="COACH_DONE" ;;
  esac
  if [[ -n "$comments_file" ]]; then
    comments="$(cat -- "$comments_file")"
  elif [[ -n "${GH_TOKEN:-}" && -n "$repo" ]] && command -v gh >/dev/null 2>&1; then
    comments="$(gh_comments "$repo" "$pr" 2>/dev/null || true)"
  else
    comments=""
  fi
  if [[ -n "$comments" ]]; then
    local _py2
    _py2="$(mktemp)"
    cat >"$_py2" <<'PY'
import json, os, re

def is_actions_bot(comment):
    user = comment.get("user") or {}
    login = (user.get("login") or "").strip().lower()
    if login.endswith("[bot]"):
        login = login[:-5]
    return login == "github-actions"


def load_comments(raw):
    raw = raw.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        idx = 0
        out = []
        while idx < len(raw):
            while idx < len(raw) and raw[idx].isspace():
                idx += 1
            if idx >= len(raw):
                break
            obj, end = dec.raw_decode(raw, idx)
            if isinstance(obj, list):
                out.extend(obj)
            else:
                out.append(obj)
            idx = end
        return out
    if isinstance(data, list):
        if data and all(isinstance(p, list) for p in data):
            return [c for page in data for c in page]
        return data
    return [data]


family = os.environ["REVIEWER_DIAG_FAMILY"]
want = os.environ["REVIEWER_DIAG_SHA"].lower()
since = os.environ.get("REVIEWER_DIAG_SINCE", "").strip()
footer = os.environ["REVIEWER_DIAG_FOOTER"]
pat = re.compile(r"<!-- " + re.escape(family) + r" sha=([0-9a-fA-F]{40})[^>]*-->")
found = []
for c in load_comments(os.environ["REVIEWER_DIAG_COMMENTS"]):
    if not is_actions_bot(c):
        continue
    body = c.get("body") or ""
    created = (c.get("created_at") or "").strip()
    if since and (not created or created < since):
        continue
    for m in pat.finditer(body):
        sha = m.group(1).lower()
        ends = body.rstrip().endswith(footer.rstrip()) or body.endswith(footer)
        found.append((sha, created, ends, sha == want))

if not found:
    when = since if since else "(any time)"
    print("thread: no Actions-bot %s marker since %s" % (family, when))
else:
    any_ok = False
    any_bad = False
    for sha, created, ends, ok in found:
        any_ok = any_ok or ok
        any_bad = any_bad or (not ok)
        match = "YES" if ok else "NO — STALE/WRONG SHA"
        footer_s = "yes" if ends else "no"
        print(
            "thread: %s sha=%s created=%s footer_suffix=%s matches_head=%s"
            % (family, sha, created, footer_s, match)
        )
    if any_bad and not any_ok:
        print(
            "thread: a review DID post, but with the wrong sha — that burns "
            "the one-post cap while served=false for the real head. "
            "REVIEWER_HEAD_SHA pinning refuses this before the write."
        )
PY
    REVIEWER_DIAG_COMMENTS="$comments" REVIEWER_DIAG_FAMILY="$family" \
      REVIEWER_DIAG_SHA="$sha" REVIEWER_DIAG_SINCE="$since" \
      REVIEWER_DIAG_FOOTER="$REVIEWER_FOOTER" \
      "$PYTHON3" -I "$_py2" || true
    rm -f -- "$_py2"
  else
    echo "thread: could not read issue comments (no GH_TOKEN/repo or empty)"
  fi

  echo "::endgroup::"
  return 0
}

# --- selftest: every rule with its negative control ----------------------------
selftest() {
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  local fail=0
  ok()  { echo "selftest ok    $1"; }
  bad() { echo "selftest FAIL  $1"; fail=1; }
  # row <label> <expected> <script-args...>: run the real CLI over a comments
  # snapshot and compare the printed verdict.
  row() {
    local label="$1" want="$2" got rc=0
    shift 2
    got="$("$@" 2>"$tmp/stderr")" || rc=$?
    if [[ "$rc" -eq 0 && "$got" == "$want" ]]; then ok "$label ($got)"
    else bad "$label (want $want, got ${got:-<empty>} rc=$rc: $(cat "$tmp/stderr" 2>/dev/null))"; fi
  }
  # refuses <label> : the real CLI must exit non-zero with a message.
  refuses() {
    local label="$1" rc=0
    shift
    "$@" >"$tmp/stdout" 2>"$tmp/stderr" || rc=$?
    if [[ "$rc" -ne 0 ]] && [[ -s "$tmp/stderr" ]]; then ok "$label (refused, rc=$rc)"
    else bad "$label (should refuse; rc=$rc)"; fi
  }

  local head="0123456789abcdef0123456789abcdef01234567"
  local old="fedcba9876543210fedcba9876543210fedcba98"
  local footer=$'---\n_Generated by [Claude Code](https://claude.ai/code)_'

  # Build comment fixtures via Python so the MCP footer newlines stay valid JSON.
  mkfix() {  # $1 = path, remaining = python expr producing the comments list
    local path="$1"; shift
    REVIEWER_FOOTER="$footer" HEAD_SHA="$head" OLD_SHA="$old" \
      "$PYTHON3" -I -c "
import json, os, sys
FOOTER = os.environ['REVIEWER_FOOTER']
HEAD = os.environ['HEAD_SHA']
OLD = os.environ['OLD_SHA']
jane = f'<!-- JANE_SIGNOFF sha={HEAD} verdict=pass fuse=none -->'
jane_stale = f'<!-- JANE_SIGNOFF sha={OLD} verdict=pass fuse=none -->'
jane_ack = f'<!-- JANE_SIGNOFF sha={HEAD} verdict=pass fuse=acknowledged -->'
drik = f'<!-- DRIK_SIGNOFF sha={HEAD} verdict=block fuse=none -->'
pm_done = f'<!-- PM_TRIAGE_DONE sha={HEAD} -->'
pm_done_stale = f'<!-- PM_TRIAGE_DONE sha={OLD} -->'
# Full MCP PM post: per-design marker then completion marker (DONE last).
pm_full = (
    f'<!-- PM_TRIAGE design=demo sha={HEAD} -->\\n\\n'
    f'<!-- PM_TRIAGE_DONE sha={HEAD} -->'
)
coach_done = f'<!-- COACH_DONE sha={HEAD} -->'
coach_full = (
    f'<!-- COACH_LOCK -->\\n\\n'
    f'<!-- COACH_DONE sha={HEAD} -->'
)
bot = {'login': 'github-actions[bot]', 'type': 'Bot'}
def mcp(body_text, marker, user=None, created='2026-10-05T12:00:01Z'):
    c = {'body': body_text.rstrip() + '\\n\\n' + marker + '\\n\\n' + FOOTER,
         'user': user if user is not None else bot}
    if created is not None:
        c['created_at'] = created
    return c
comments = $*
with open(sys.argv[1], 'w', encoding='utf-8') as fh:
    if isinstance(comments, str):
        fh.write(comments)
    else:
        json.dump(comments, fh)
" "$path"
  }

  mkfix "$tmp/posted" "[mcp('Jane here — clean print call.', jane)]"
  mkfix "$tmp/graphql" \
    "[{'body': 'Jane here.\\n\\n' + jane + '\\n\\n' + FOOTER, 'user': {'login': 'github-actions'}, 'created_at': '2026-10-05T12:00:01Z'}]"
  mkfix "$tmp/stale" "[mcp('Jane here.', jane_stale)]"
  mkfix "$tmp/silent" \
    "[{'body': 'Jane looked, found nothing to say.\\n\\n' + FOOTER, 'user': bot}]"
  mkfix "$tmp/drik" "[mcp('Drik here.', drik)]"
  mkfix "$tmp/both" "[mcp('Drik.', drik), mcp('Jane.', jane_ack)]"
  mkfix "$tmp/pm" "[mcp('PM triage.', pm_full)]"
  mkfix "$tmp/pm-done-only" "[mcp('PM triage.', pm_done)]"
  mkfix "$tmp/pm-stale" "[mcp('PM triage.', pm_done_stale)]"
  mkfix "$tmp/coach" "[mcp('Coach kickoff.', coach_full)]"
  mkfix "$tmp/coach-done-only" "[mcp('Coach.', coach_done)]"
  mkfix "$tmp/malformed" \
    "[{'body': 'x\n\n<!-- JANE_SIGNOFF verdict=pass fuse=none -->\n\n' + FOOTER, 'user': bot}]"
  mkfix "$tmp/impostor" \
    "[{'body': f'unrelated text mentioning JANE_SIGNOFF and sha={HEAD} separately\n\n' + FOOTER, 'user': bot}]"
  # THE SECURITY ROWS: planted markers from other authors / wrong shape.
  mkfix "$tmp/planted-human" "[mcp('plant', jane, user={'login': 'attacker'})]"
  mkfix "$tmp/planted-cursor" \
    "[mcp('plant', jane, user={'login': 'cursor[bot]', 'type': 'Bot'})]"
  mkfix "$tmp/no-footer" \
    "[{'body': 'Jane.\n\n' + jane, 'user': bot}]"
  mkfix "$tmp/no-author" \
    "[{'body': 'Jane.\n\n' + jane + '\n\n' + FOOTER}]"
  # Sibling Actions-bot post that planted JANE_SIGNOFF before its own Drik
  # marker — body ends with DRIK suffix, so it must NOT serve jane.
  mkfix "$tmp/sibling-plant" \
    "[{'body': 'x\n\n' + jane + '\n\n' + drik + '\n\n' + FOOTER, 'user': bot}]"
  mkfix "$tmp/casefold" \
    "[{'body': f'x\n\n<!-- jane_signoff sha={HEAD} verdict=pass fuse=none -->\n\n' + FOOTER, 'user': bot}]"
  printf '%s\n' '[]' >"$tmp/empty"

  # The served rows — through the real CLI.
  row "Actions-bot MCP-shaped post for this head → served" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/posted"
  row "GraphQL github-actions login still serves" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/graphql"
  row "no marker at all → not served" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/silent"
  row "marker names an older head → stale" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/stale"
  row "marker without a sha field → unserved" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/malformed"
  row "sha outside a marker does not count" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/impostor"
  row "drik marker serves drik" \
    true  "$0" check --pr 1 --sha "$head" --reviewer drik --comments-file "$tmp/drik"
  row "jane marker does not serve drik" \
    false "$0" check --pr 1 --sha "$head" --reviewer drik --comments-file "$tmp/posted"
  row "fuse=acknowledged MCP suffix still serves" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/both"
  row "empty thread → not served" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/empty"
  # Issue #770: pm / coach completion markers.
  row "pm full MCP post (PM_TRIAGE + PM_TRIAGE_DONE) serves pm" \
    true  "$0" check --pr 1 --sha "$head" --reviewer pm --comments-file "$tmp/pm"
  row "pm DONE-only suffix also serves pm" \
    true  "$0" check --pr 1 --sha "$head" --reviewer pm --comments-file "$tmp/pm-done-only"
  row "pm DONE for an older head is stale" \
    false "$0" check --pr 1 --sha "$head" --reviewer pm --comments-file "$tmp/pm-stale"
  row "pm marker does not serve jane" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/pm"
  row "jane marker does not serve pm" \
    false "$0" check --pr 1 --sha "$head" --reviewer pm --comments-file "$tmp/posted"
  row "coach full MCP post (COACH_LOCK + COACH_DONE) serves coach" \
    true  "$0" check --pr 1 --sha "$head" --reviewer coach --comments-file "$tmp/coach"
  row "coach DONE-only suffix also serves coach" \
    true  "$0" check --pr 1 --sha "$head" --reviewer coach --comments-file "$tmp/coach-done-only"
  row "coach marker does not serve pm" \
    false "$0" check --pr 1 --sha "$head" --reviewer pm --comments-file "$tmp/coach"
  mkfix "$tmp/planted-pm-human" "[mcp('plant', pm_done, user={'login': 'attacker'})]"
  row "human-planted PM_TRIAGE_DONE is ignored" \
    false "$0" check --pr 1 --sha "$head" --reviewer pm --comments-file "$tmp/planted-pm-human"
  mkfix "$tmp/planted-coach-cursor" \
    "[mcp('plant', coach_done, user={'login': 'cursor[bot]', 'type': 'Bot'})]"
  row "cursor[bot]-planted COACH_DONE is ignored" \
    false "$0" check --pr 1 --sha "$head" --reviewer coach --comments-file "$tmp/planted-coach-cursor"

  # Security: planted markers from other authors / non-MCP shapes.
  row "human-planted marker+footer is ignored" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/planted-human"
  row "cursor[bot]-planted marker+footer is ignored" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/planted-cursor"
  row "Actions-bot marker without MCP footer is ignored" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/no-footer"
  row "marker with no author is ignored" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/no-author"
  row "sibling Actions-bot plant (Drik suffix, Jane in body) does not serve jane" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/sibling-plant"
  row "case-folded marker is not an MCP post" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/casefold"
  # A human plant must not hide a later genuine MCP post.
  mkfix "$tmp/plant-then-real" \
    "[mcp('plant', jane, user={'login': 'attacker'}), mcp('real', jane)]"
  row "a human plant does not hide a later genuine MCP post" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/plant-then-real"

  # --since (this-run scope), coach-lock-check pattern.
  row "lock created after --since passes" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/posted" \
    --since 2026-10-05T12:00:00Z
  row "lock created at exactly --since passes" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/posted" \
    --since 2026-10-05T12:00:01Z
  row "lock from an earlier run fails under --since" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/posted" \
    --since 2026-10-05T12:00:02Z
  mkfix "$tmp/no-created" "[mcp('Jane.', jane, created=None)]"
  row "lock missing created_at fails under --since" \
    false "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/no-created" \
    --since 2026-10-05T12:00:00Z

  # Pagination shapes (coach-lock-check belt).
  OUT="$tmp/pages" REVIEWER_FOOTER="$footer" HEAD_SHA="$head" "$PYTHON3" -I -c '
import json, os
FOOTER = os.environ["REVIEWER_FOOTER"]
HEAD = os.environ["HEAD_SHA"]
jane = f"<!-- JANE_SIGNOFF sha={HEAD} verdict=pass fuse=none -->"
bot = {"login": "github-actions[bot]"}
page1 = [{"body": "page1", "user": bot}]
page2 = [{"body": "Jane.\n\n" + jane + "\n\n" + FOOTER, "user": bot}]
open(os.environ["OUT"], "w", encoding="utf-8").write(
    json.dumps(page1) + json.dumps(page2))
'
  row "concatenated paginated page arrays still find the marker" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/pages"
  OUT="$tmp/slurp" REVIEWER_FOOTER="$footer" HEAD_SHA="$head" "$PYTHON3" -I -c '
import json, os
FOOTER = os.environ["REVIEWER_FOOTER"]
HEAD = os.environ["HEAD_SHA"]
jane = f"<!-- JANE_SIGNOFF sha={HEAD} verdict=pass fuse=none -->"
bot = {"login": "github-actions[bot]"}
pages = [[{"body": "page1", "user": bot}],
         [{"body": "Jane.\n\n" + jane + "\n\n" + FOOTER, "user": bot}]]
json.dump(pages, open(os.environ["OUT"], "w", encoding="utf-8"))
'
  row "slurped page arrays still find the marker" \
    true  "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/slurp"

  # $GITHUB_OUTPUT wiring: the same verdict lands as served=<value>.
  GITHUB_OUTPUT="$tmp/gh-output" \
    "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/posted" >/dev/null
  if grep -qx 'served=true' "$tmp/gh-output" 2>/dev/null; then ok "GITHUB_OUTPUT gets served=<verdict>"
  else bad "GITHUB_OUTPUT gets served=<verdict> (got: $(cat "$tmp/gh-output" 2>/dev/null))"; fi

  # The refusal rows — a typo or a bad sha must fail loud, never read as a
  # clean "not served" (that would burn the whole chain walk on a typo).
  refuses "typo'd reviewer refused" "$0" check --pr 1 --sha "$head" --reviewer jan --comments-file "$tmp/posted"
  refuses "unknown reviewer refused" "$0" check --pr 1 --sha "$head" --reviewer vera --comments-file "$tmp/posted"
  refuses "short sha refused"       "$0" check --pr 1 --sha abc123 --reviewer jane --comments-file "$tmp/posted"
  refuses "non-numeric pr refused"  "$0" check --pr abc --sha "$head" --reviewer jane --comments-file "$tmp/posted"
  refuses "bad --since refused"     "$0" check --pr 1 --sha "$head" --reviewer jane --comments-file "$tmp/posted" --since yesterday
  # Live mode without a token must fail loud (fail-closed read, not a guess).
  rc=0
  GH_TOKEN="" "$0" check --pr 1 --sha "$head" --reviewer jane >"$tmp/stdout" 2>"$tmp/stderr" || rc=$?
  if [[ "$rc" -ne 0 ]] && [[ -s "$tmp/stderr" ]]; then ok "live check without GH_TOKEN refuses"
  else bad "live check without GH_TOKEN refuses (rc=$rc)"; fi

  # Drift pin: the footer this script requires is the one the MCP appends.
  local mcp_footer
  mcp_footer="$("$PYTHON3" -I -c '
import ast, pathlib
src = pathlib.Path(".claude/reviewer-post/reviewer_mcp.py").read_text(encoding="utf-8")
mod = ast.parse(src)
for node in mod.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "FOOTER":
                print(ast.literal_eval(node.value))
                raise SystemExit(0)
raise SystemExit("FOOTER not found")
')"
  if [[ "$mcp_footer" == "$footer" ]]; then ok "FOOTER matches reviewer_mcp.py"
  else bad "FOOTER drifted from reviewer_mcp.py (script=$footer mcp=$mcp_footer)"; fi

  # Drift pin: the marker literals this script matches are the ones the two
  # reviewer skills tell their agents to emit.
  local skill marker_lit
  for skill in jane drik; do
    marker_lit="$(grep -oE "<!-- ${skill^^}_SIGNOFF sha=<[^>]*>" ".claude/skills/${skill}-review/SKILL.md" | head -1)"
    if [[ -n "$marker_lit" ]]; then ok "skills/$skill-review documents ${skill^^}_SIGNOFF"
    else bad "skills/$skill-review no longer documents the ${skill^^}_SIGNOFF marker"; fi
  done

  # diagnose is advisory and must not fail the walk; pin a stale-sha
  # report so a future edit that drops the thread scan is caught.
  cat >"$tmp/diag-comments.json" <<JSON
[{"user":{"login":"github-actions[bot]"},"created_at":"2026-10-10T13:03:36Z","body":"## Drik\n\n<!-- DRIK_SIGNOFF sha=073fd1af8d7087d25869571d225fb8f8a4e004d9 verdict=pass fuse=none -->\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_"}]
JSON
  diag_out="$tmp/diag-out.txt"
  if ./scripts/reviewer-posted.sh diagnose \
        --pr 559 --sha 169898ab5a64b42697738e803fc583aeff938445 \
        --reviewer drik --since 2026-10-10T12:44:10Z --link 1 \
        --comments-file "$tmp/diag-comments.json" \
        >"$diag_out" 2>&1; then
    if grep -q 'STALE/WRONG SHA' "$diag_out"; then
      ok "diagnose flags a bot post with the wrong sha"
    else
      bad "diagnose missed the stale-sha thread finding ($(cat "$diag_out"))"
    fi
  else
    bad "diagnose exited non-zero (must stay advisory): $(cat "$diag_out")"
  fi

  if [[ "$fail" -eq 0 ]]; then
    echo "ok    reviewer-posted --selftest: the artifact check passes a trusted MCP post and refuses planted/wrong-author markers"
  else
    echo "FAIL  reviewer-posted --selftest: a decision row was wrong"
  fi
  exit "$fail"
}

case "${1:-}" in
  check) shift; check "$@" ;;
  diagnose) shift; diagnose "$@" ;;
  --selftest) selftest "$0" ;;
  *) usage "unknown mode: ${1:-none}" ;;
esac
