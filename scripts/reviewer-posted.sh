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
# The marker is the one the reviewer skills emit as the last line of their PR
# comment (.claude/skills/{jane,drik}-review/SKILL.md) and the
# `reviewer-signoff` status already keys on —
#   <!-- JANE_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
#   <!-- DRIK_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
# — read here with the SAME case-insensitive marker-then-sha two-step the
# signoff-status job uses, so the two readers can never disagree about what
# counts as posted. A marker for an older head sha does not count: rounds are
# per-push, so a marker naming this sha is the only evidence a review of this
# commit exists.
#
# Usage:
#   scripts/reviewer-posted.sh check --pr <N> --sha <40hex> --reviewer jane|drik
#       [--repo <owner/name>] [--bodies-file <path>]
#     Prints `true` or `false` (exit 0 either way — a clean negative is a
#     decision, not an error) and, when $GITHUB_OUTPUT is set, appends
#     `served=<value>` to it. --bodies-file drives the core over a snapshot
#     of the PR's comment/review bodies instead of the live thread (the
#     selftest's seam); live mode needs GH_TOKEN and reads all three places a
#     marker can land (issue comments, PR review bodies, review line comments
#     — the signoff-status job's own three sources).
#     Exit 1 = the artifact read itself failed: a check that cannot read must
#     fail loud, never guess — a silent `false` here would fail the walk open.
#
#   scripts/reviewer-posted.sh --selftest
#     The decision rows (posted / not posted / wrong sha / malformed /
#     case-folded marker / marker in a review body) plus the refusal rows
#     (typo'd reviewer, bad sha, live mode without GH_TOKEN) and a drift pin
#     against the marker literals the two skills actually document — so this
#     script cannot quietly stop matching the format the reviewers emit.
#
# Consumers: auto-review.yml — the per-link artifact checks after each
# Jane/Drik ship step (the chain walk's fall-through key), and the review
# stamp's confirmation before a round is called complete. pm-triage and the
# design coach keep their exit-code walks: no per-head completion marker is
# defined for either (the PM's PM_TRIAGE markers are per-design verdicts, the
# coach's COACH-LOCK is a dedupe lock, not a completion signal).
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {  # [message]
  [ $# -eq 0 ] || echo "reviewer-posted: $*" >&2
  cat >&2 <<'EOF'
usage: scripts/reviewer-posted.sh check --pr <N> --sha <40hex> --reviewer jane|drik
           [--repo <owner/name>] [--bodies-file <path>]
       scripts/reviewer-posted.sh --selftest
EOF
  exit 2
}

# The pure core: does the bodies text carry this reviewer's sign-off marker
# naming this sha? Marker first (case-insensitive, `[^>]*-->` so the match is
# the whole marker — the signoff-status job's own expression), then the sha
# inside what that matched. One line per marker (the skills put it on its own
# line), which is what makes the two greps compose.
served_from_bodies() {  # $1 = bodies text, $2 = sha, $3 = reviewer
  local prefix="${3^^}_SIGNOFF"
  if grep -oiE "<!-- ${prefix} [^>]*-->" <<<"$1" | grep -qiF "sha=$2"; then
    printf 'true'
  else
    printf 'false'
  fi
}

# The live thread read: the three sources a marker can land in, in the order
# the signoff-status job reads them. Any gh failure aborts the function, and
# the caller turns that into exit 1 — an unreadable thread is never a `false`.
gh_bodies() {  # $1 = owner/name, $2 = PR number
  gh api --paginate "/repos/$1/issues/$2/comments" --jq '.[].body'
  gh api --paginate "/repos/$1/pulls/$2/reviews"   --jq '.[].body'
  gh api --paginate "/repos/$1/pulls/$2/comments"  --jq '.[].body'
}

check() {
  local reviewer="" pr="" sha="" repo="${GITHUB_REPOSITORY:-}" bodies_file=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --pr) pr="${2:?}"; shift 2 ;;
      --sha) sha="${2:?}"; shift 2 ;;
      --reviewer) reviewer="${2:?}"; shift 2 ;;
      --repo) repo="${2:?}"; shift 2 ;;
      --bodies-file) bodies_file="${2:?}"; shift 2 ;;
      *) usage "unknown option: $1" ;;
    esac
  done
  # A typo'd reviewer or a bad sha must fail loud here, not match nothing and
  # read as "not served" — that would burn all six chain links on a typo.
  [[ "$reviewer" == "jane" || "$reviewer" == "drik" ]] \
    || usage "--reviewer must be jane or drik (got: ${reviewer:-empty})"
  [[ "$pr" =~ ^[0-9]+$ ]] || usage "--pr must be a number (got: ${pr:-empty})"
  [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || usage "--sha must be 40 hex chars (got: ${sha:-empty})"

  local bodies
  if [[ -n "$bodies_file" ]]; then
    bodies="$(cat -- "$bodies_file")"
  else
    command -v gh >/dev/null 2>&1 || { echo "reviewer-posted: gh is not installed" >&2; exit 1; }
    [[ -n "${GH_TOKEN:-}" ]] || { echo "reviewer-posted: GH_TOKEN is not set (live check needs it)" >&2; exit 1; }
    [[ -n "$repo" ]] || usage "--repo is required in live mode (or set GITHUB_REPOSITORY)"
    if ! bodies="$(gh_bodies "$repo" "$pr")"; then
      echo "reviewer-posted: could not read PR #$pr's comments/reviews" >&2
      exit 1
    fi
  fi

  local verdict
  verdict="$(served_from_bodies "$bodies" "$sha" "$reviewer")"
  printf '%s\n' "$verdict"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'served=%s\n' "$verdict" >>"$GITHUB_OUTPUT"
  fi
}

# --- selftest: every rule with its negative control ----------------------------
selftest() {
  local tmp; tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  local fail=0
  ok()  { echo "selftest ok    $1"; }
  bad() { echo "selftest FAIL  $1"; fail=1; }
  # row <label> <expected> <script-args...>: run the real CLI over a bodies
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

  printf 'Jane here — clean print call.\n<!-- JANE_SIGNOFF sha=%s verdict=pass fuse=none -->\n' "$head" >"$tmp/posted"
  printf 'Jane here — clean print call.\n<!-- JANE_SIGNOFF sha=%s verdict=pass fuse=none -->\n' "$old" >"$tmp/stale"
  printf 'Jane looked, found nothing to say.\n' >"$tmp/silent"
  printf 'review body\n<!-- DRIK_SIGNOFF sha=%s verdict=block fuse=none -->\nline comment\n<!-- JANE_SIGNOFF sha=%s verdict=pass fuse=acknowledged -->\n' "$head" "$head" >"$tmp/review"
  printf '<!-- jane_signoff SHA=%s verdict=pass fuse=none -->\n' "$head" >"$tmp/folded"
  printf '<!-- JANE_SIGNOFF verdict=pass fuse=none -->\n' >"$tmp/malformed"
  printf 'unrelated text mentioning JANE_SIGNOFF and sha=%s separately\n' "$head" >"$tmp/impostor"

  # The served rows — the workflow's four outcomes, through the real CLI.
  row "posted for this head → served"          true  "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/posted"
  row "no marker at all → not served"          false "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/silent"
  row "marker names an older head → stale"     false "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/stale"
  row "marker in a review/line-comment body"   true  "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/review"
  row "case-folded marker still matches"       true  "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/folded"
  row "marker without a sha field → unserved"  false "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/malformed"
  row "sha outside a marker does not count"    false "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/impostor"
  row "drik marker serves drik"                true  "$0" check --pr 1 --sha "$head" --reviewer drik  --bodies-file "$tmp/review"
  row "jane marker does not serve drik"        false "$0" check --pr 1 --sha "$head" --reviewer drik  --bodies-file "$tmp/posted"

  # $GITHUB_OUTPUT wiring: the same verdict lands as served=<value>.
  GITHUB_OUTPUT="$tmp/gh-output" \
    "$0" check --pr 1 --sha "$head" --reviewer jane --bodies-file "$tmp/posted" >/dev/null
  if grep -qx 'served=true' "$tmp/gh-output" 2>/dev/null; then ok "GITHUB_OUTPUT gets served=<verdict>"
  else bad "GITHUB_OUTPUT gets served=<verdict> (got: $(cat "$tmp/gh-output" 2>/dev/null))"; fi

  # The refusal rows — a typo or a bad sha must fail loud, never read as a
  # clean "not served" (that would burn the whole chain walk on a typo).
  refuses "typo'd reviewer refused" "$0" check --pr 1 --sha "$head" --reviewer jan --bodies-file "$tmp/posted"
  refuses "short sha refused"       "$0" check --pr 1 --sha abc123 --reviewer jane --bodies-file "$tmp/posted"
  refuses "non-numeric pr refused"  "$0" check --pr abc --sha "$head" --reviewer jane --bodies-file "$tmp/posted"
  # Live mode without a token must fail loud (fail-closed read, not a guess).
  rc=0
  GH_TOKEN="" "$0" check --pr 1 --sha "$head" --reviewer jane >"$tmp/stdout" 2>"$tmp/stderr" || rc=$?
  if [[ "$rc" -ne 0 ]] && [[ -s "$tmp/stderr" ]]; then ok "live check without GH_TOKEN refuses"
  else bad "live check without GH_TOKEN refuses (rc=$rc)"; fi

  # Drift pin: the marker literals this script matches are the ones the two
  # reviewer skills tell their agents to emit. If a skill rewords its marker,
  # this fails — the artifact check would silently stop seeing real reviews.
  local skill marker_lit
  for skill in jane drik; do
    marker_lit="$(grep -oE "<!-- ${skill^^}_SIGNOFF sha=<[^>]*>" ".claude/skills/${skill}-review/SKILL.md" | head -1)"
    if [[ -n "$marker_lit" ]]; then ok "skills/$skill-review documents ${skill^^}_SIGNOFF"
    else bad "skills/$skill-review no longer documents the ${skill^^}_SIGNOFF marker"; fi
  done

  if [[ "$fail" -eq 0 ]]; then
    echo "ok    reviewer-posted --selftest: the artifact check passes a posted marker and refuses everything else"
  else
    echo "FAIL  reviewer-posted --selftest: a decision row was wrong"
  fi
  exit "$fail"
}

case "${1:-}" in
  check) shift; check "$@" ;;
  --selftest) selftest "$0" ;;
  *) usage "unknown mode: ${1:-none}" ;;
esac
