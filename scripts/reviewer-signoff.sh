#!/usr/bin/env bash
# reviewer-signoff: decide whether a design PR has both reviewers' sign-off on
# its current design content. The pass/block decision that a REQUIRED commit
# status ("reviewer-signoff") is built from — so Jane and Drik actually run and
# consciously clear a design PR before it can merge (the sweetheart-hamster
# lesson: auto-merge landed a fused hinge because the reviewers never ran and
# nothing required that they had).
#
#   scripts/reviewer-signoff.sh decide \
#       --head <40hex>            PR head sha the status is posted on
#       --designs-changed true|false   does the PR touch designs/ ?
#       --no-auto-review true|false    is the no-auto-review label present?
#       --override true|false          is the signoff-override label present?
#       --fuse-warn true|false         is a fusecheck STRONG WARN live this round?
#       --andon true|false             is the AI andon cord pulled (reviews bypassed)?
#       --jane "<marker or empty>"     the last JANE_SIGNOFF marker line
#       --drik "<marker or empty>"     the last DRIK_SIGNOFF marker line
#       --tree-current <key>           reviewer-signoff.sh key <head>  (currency key)
#       --jane-tree <key|empty>        reviewer-signoff.sh key <jane-sha> (empty if gone)
#       --drik-tree <key|empty>        reviewer-signoff.sh key <drik-sha>
#
#   scripts/reviewer-signoff.sh key <commit>
#       Print the sign-off CURRENCY KEY of <commit> (see CURRENCY below), or
#       nothing and exit 1 when it cannot be resolved. auto-review.yml computes
#       every key the `decide` call compares with this, never with its own
#       rev-parse, so the posting and the checking side cannot drift.
#
#   scripts/reviewer-signoff.sh round --head <sha> --stamp <sha|empty>
#       The regen review guard (issue #470): "SKIP <reason>" (exit 0) when
#       every designs/ change since the last reviewed round (the
#       AUTO_REVIEW_STAMP sha) is a previews-only, all-noise regen commit-back,
#       else "ROUND <reason>" (exit 1). auto-review.yml asks it only after its
#       own diff has already said "designs/ changed", so a SKIP can only turn a
#       round off, and only for that case.
#
# Prints exactly one line — "PASS <reason>" (exit 0) or "BLOCK <reason>" (exit 1)
# — short enough to drop into a GitHub status `description` (<=140 chars). The
# caller does only trivial git plumbing (rev-parse) and API reads; ALL the
# policy lives here, behind --selftest, so the fail-closed decision is proven to
# both pass and fail rather than asserted in YAML.
#
# FAIL-CLOSED by construction: a design PR with a missing, malformed, stale
# (design changed since it was signed), blocking, or fuse-unacknowledged marker
# BLOCKS. The only passes on a design PR are two clean current sign-offs, or a
# deliberate human escape hatch (the no-auto-review / signoff-override labels).
# With the AI andon cord pulled (--andon true, docs/andon-cord.md) no reviewer
# runs, so a design PR lacking two clean current sign-offs BLOCKS with the cord
# named as the reason — while sign-offs that already happened still PASS (a
# review that ran is a fact about the design tree, and the cord stops AI
# consumption, not merging) and the label hatches still PASS.
#
# The marker each reviewer emits as the last line of its PR comment (see
# .claude/skills/{jane,drik}-review/SKILL.md):
#   <!-- JANE_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
#   <!-- DRIK_SIGNOFF sha=<40hex> verdict=pass|block fuse=none|acknowledged -->
# `sha` is the head the reviewer looked at; `verdict` is its call; `fuse` MUST be
# `acknowledged` when a fusecheck STRONG WARN is live that round (the reviewer
# read it in the sticky gate report and addressed it), else `none`.
#
# CURRENCY (why sign-offs survive a non-design push): a sign-off is current when
# its sha IS the head, OR the currency key at its sha equals the key at the
# head — so a later push that touches only docs/CI (which advances the head sha
# but changes no designs/ file) does NOT strand a reviewed PR, matching
# auto-review.yml's own is_new_round dedup. A design change moves the key and
# correctly invalidates the sign-off.
#
# The KEY is the designs/ tree, read back past the regen commit-backs that the
# owner ruled need no new review (issue #470, decision
# regen-commitback-review-retrigger, option C): walk <commit>'s first-parent
# line over the commits that changed designs/, skip every QUALIFYING commit-back,
# and take the designs/ tree of the first commit that is not one. Qualifying
# means all of: one parent; ci.yml's regen subject and bot author (how ci.yml's
# loop guard recognises its own commit); exactly one `Preview-Diff: all-noise`
# trailer (the regen job writes it only when preview-diff rated every staged
# preview noise); and a diff that touches nothing but
# designs/<n>/previews/<file>.png|.gif and designs/<n>/previews/.regen-stamp —
# not a previews/*.conf, not CAMERAS.md, not a README, nothing outside designs/.
# So a sign-off stays current across an all-noise, previews-only commit-back and
# goes stale on a content-class one, a hand edit, or a forged trailer on a
# commit that also touches a source. With no qualifying commit on the line the
# key IS the designs/ tree, today's rule unchanged. Whatever the walk crosses,
# two equal keys mean the two trees differ only in preview images and stamps
# that all-noise commit-backs changed; stopping early (the walk cap) only makes
# a key more conservative.
set -euo pipefail

# The regen commit-back's identity. ci.yml writes it (REGEN_SUBJECT, the bot
# identity it commits as, the Preview-Diff trailer); the selftest's drift pin
# fails if ci.yml stops writing exactly these, because drift here would
# silently turn the guard off (fail-closed: every commit-back opens a round).
REGEN_SUBJECT="CI: regenerate previews and product pages"
REGEN_AUTHOR="41898282+github-actions[bot]@users.noreply.github.com"
REGEN_TRAILER="Preview-Diff"
# How many designs/-changing commits the key walk reads back past at most.
# Commit-backs cannot chain (the loop guard allows one per push), so a real
# line meets one or two; past the cap the key is the raw tree (conservative).
KEY_WALK_MAX=50

# --- field extraction (pure string ops; no git, no network) -----------------
# Echo the value of `<key>=<value>` inside a marker string, or empty. Values are
# [0-9a-z]+ (sha hex, verdict/fuse words), which is all the markers ever carry.
_field() {
  local marker="$1" key="$2"
  [[ "$marker" =~ (^|[[:space:]])"$key"=([0-9a-zA-Z]+) ]] && printf '%s' "${BASH_REMATCH[2]}"
}

# Evaluate one reviewer. Echoes empty on OK, or a short reason on failure.
# Args: <who> <marker> <head> <tree_current> <tree_at_marker> <fuse_warn>
_review_problem() {
  local who="$1" marker="$2" head="$3" tree_cur="$4" tree_mk="$5" fuse_warn="$6"
  if [[ -z "$marker" ]]; then
    printf '%s has not signed off' "$who"; return
  fi
  local sha verdict fuse
  sha="$(_field "$marker" sha)"
  verdict="$(_field "$marker" verdict)"
  fuse="$(_field "$marker" fuse)"
  if [[ -z "$sha" || -z "$verdict" || -z "$fuse" ]]; then
    printf "%s sign-off is malformed" "$who"; return
  fi
  # currency: same head, or same design tree (survives a non-design push)
  if [[ "$sha" != "$head" ]]; then
    if [[ -z "$tree_mk" || "$tree_mk" != "$tree_cur" ]]; then
      printf '%s sign-off is stale (reviewed %s; design changed since)' \
        "$who" "${sha:0:8}"; return
    fi
  fi
  if [[ "$verdict" != "pass" ]]; then
    printf '%s blocked (verdict=%s)' "$who" "$verdict"; return
  fi
  if [[ "$fuse_warn" == "true" && "$fuse" != "acknowledged" ]]; then
    printf '%s has not acknowledged the fusecheck STRONG WARN' "$who"; return
  fi
  printf ''
}

decide() {
  local head="" designs_changed="" no_auto_review="" override="" fuse_warn="" andon=""
  local jane="" drik="" tree_current="" jane_tree="" drik_tree=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --head) head="$2"; shift 2 ;;
      --designs-changed) designs_changed="$2"; shift 2 ;;
      --no-auto-review) no_auto_review="$2"; shift 2 ;;
      --override) override="$2"; shift 2 ;;
      --fuse-warn) fuse_warn="$2"; shift 2 ;;
      --andon) andon="$2"; shift 2 ;;
      --jane) jane="$2"; shift 2 ;;
      --drik) drik="$2"; shift 2 ;;
      --tree-current) tree_current="$2"; shift 2 ;;
      --jane-tree) jane_tree="$2"; shift 2 ;;
      --drik-tree) drik_tree="$2"; shift 2 ;;
      *) echo "reviewer-signoff: unknown arg $1" >&2; return 2 ;;
    esac
  done

  # Human escape hatches and the non-design short-circuit come first: they must
  # let docs/tooling PRs (and a maintainer's deliberate override) through so the
  # required status never strands a PR it was never meant to gate.
  if [[ "$designs_changed" != "true" ]]; then
    echo "PASS no design changes — reviewer sign-off not required"; return 0
  fi
  if [[ "$override" == "true" ]]; then
    echo "PASS overridden by the signoff-override label (a maintainer accepted the risk)"; return 0
  fi
  if [[ "$no_auto_review" == "true" ]]; then
    echo "PASS auto-review suppressed by the no-auto-review label"; return 0
  fi

  local jp dp
  jp="$(_review_problem Jane "$jane" "$head" "$tree_current" "$jane_tree" "$fuse_warn")"
  dp="$(_review_problem Drik "$drik" "$head" "$tree_current" "$drik_tree" "$fuse_warn")"
  if [[ -n "$jp" || -n "$dp" ]]; then
    # The cord explains the gap: no reviewer could have run, so name the cord
    # (and the way out) instead of "has not signed off". Clean current
    # sign-offs never reach here, so they still PASS under the cord.
    if [[ "$andon" == "true" ]]; then
      echo "BLOCK andon cord pulled — reviews bypassed; release the cord or add signoff-override"; return 1
    fi
    local msg="${jp}"
    [[ -n "$jp" && -n "$dp" ]] && msg="${jp}; ${dp}"
    [[ -z "$jp" ]] && msg="$dp"
    echo "BLOCK ${msg}"; return 1
  fi
  if [[ "$fuse_warn" == "true" ]]; then
    echo "PASS Jane and Drik signed off and acknowledged the fuse warn"; return 0
  fi
  echo "PASS Jane and Drik signed off on this design"; return 0
}

# --- the regen commit-back rule (issue #470): pure, then git -----------------

# _derived_path PATH — 0 when PATH is a regen OUTPUT the guard may skip review
# for: a preview image directly under designs/<n>/previews/ (exactly the files
# preview-diff.sh measures, so an all-noise verdict covers every one of them)
# or the design's .regen-stamp. Inputs that live beside them — cameras.conf
# and the other previews/*.conf manifests, CAMERAS.md — are not outputs.
_derived_path() {
  [[ "$1" =~ ^designs/[^/]+/previews/([^/]+\.(png|gif)|\.regen-stamp)$ ]]
}

# _regen_problem PARENTS SUBJECT AUTHOR TRAILERS PATHS — pure. Echo empty when
# the commit is a qualifying commit-back, else a short reason. TRAILERS is the
# newline-separated Preview-Diff values, PATHS the newline-separated paths the
# commit changes against its parent.
_regen_problem() {
  local parents="$1" subject="$2" author="$3" trailers="$4" paths="$5" p
  if [[ "$parents" != 1 ]]; then
    printf 'not a single-parent commit'; return
  fi
  if [[ "$subject" != "$REGEN_SUBJECT" || "$author" != "$REGEN_AUTHOR" ]]; then
    printf 'not a regen commit-back'; return
  fi
  if [[ "$trailers" != "all-noise" ]]; then
    trailers="${trailers//$'\n'/, }"
    printf 'preview-diff did not rate every changed preview noise (%s: %s)' \
      "$REGEN_TRAILER" "${trailers:-absent}"; return
  fi
  if [[ -z "$paths" ]]; then
    printf 'changes nothing'; return
  fi
  while IFS= read -r p; do
    if ! _derived_path "$p"; then
      printf 'touches %s, which is not a derived preview output' "$p"; return
    fi
  done <<<"$paths"
  printf ''
}

# _round_verdict STAMP TREE_STAMP TREE_HEAD KEY_STAMP KEY_HEAD — pure. Prints
# "SKIP <reason>" (return 0) or "ROUND <reason>" (return 1).
_round_verdict() {
  local stamp="$1" ts="$2" th="$3" ks="$4" kh="$5"
  if [[ -z "$stamp" ]]; then
    echo "ROUND no completed review round on record"; return 1
  fi
  if [[ -z "$ts" || -z "$th" || -z "$ks" || -z "$kh" ]]; then
    echo "ROUND cannot resolve the design tree at the stamp or the head"; return 1
  fi
  if [[ "$ts" == "$th" ]]; then
    # The PR head's designs/ did not move; whatever the caller's merge-ref diff
    # saw came from the base branch, not from a commit-back. Not ours to skip.
    echo "ROUND designs/ is unchanged on the PR head since ${stamp:0:8}; not a regen commit-back"; return 1
  fi
  if [[ "$ks" != "$kh" ]]; then
    echo "ROUND design content changed since the reviewed round ${stamp:0:8}"; return 1
  fi
  echo "SKIP every designs/ change since the reviewed round ${stamp:0:8} is a previews-only regen commit-back that preview-diff rated all-noise (issue #470) — no new round; sign-off currency carries across it"
  return 0
}

# _commit_problem SHA — gather one commit's facts with git and judge them.
_commit_problem() {
  local c="$1" line parents subject author trailers paths
  line="$(git rev-list --parents -n 1 "$c" 2>/dev/null)" || { printf 'unresolvable commit'; return; }
  read -ra parents <<<"$line"
  subject="$(git log -1 --format=%s "$c")" || { printf 'unreadable commit'; return; }
  author="$(git log -1 --format=%ae "$c")" || { printf 'unreadable commit'; return; }
  trailers="$(git log -1 --format="%(trailers:key=${REGEN_TRAILER},valueonly)" "$c")" \
    || { printf 'unreadable commit'; return; }
  paths=""
  if [[ "${#parents[@]}" == 2 ]]; then
    paths="$(git diff-tree --no-commit-id --name-only -r --no-renames "$c")" \
      || { printf 'unreadable commit'; return; }
  fi
  _regen_problem "$(( ${#parents[@]} - 1 ))" "$subject" "$author" "$trailers" "$paths"
}

# key COMMIT — the sign-off currency key (see CURRENCY at the top).
key() {
  local c="${1:-}" list x
  git rev-parse --verify --quiet "${c}^{commit}" >/dev/null || return 1
  # --first-parent with a pathspec compares each commit to its FIRST parent
  # only, so a merge that brought designs/ changes in is listed (and, having two
  # parents, is an anchor) while one that brought none is not.
  list="$(git rev-list --first-parent --max-count="$KEY_WALK_MAX" "$c" -- designs)" || return 1
  while IFS= read -r x; do
    [[ -n "$x" ]] || continue
    if [[ -n "$(_commit_problem "$x")" ]]; then
      git rev-parse --verify --quiet "${x}:designs"; return
    fi
  done <<<"$list"
  # Nothing but qualifying commit-backs within the cap: no anchor found, so
  # fall back to the raw tree — the conservative side.
  git rev-parse --verify --quiet "${c}:designs"
}

# round --head SHA --stamp SHA — the regen review guard (see the usage above).
round() {
  local head="" stamp=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --head) head="${2:-}"; shift 2 ;;
      --stamp) stamp="${2:-}"; shift 2 ;;
      *) echo "reviewer-signoff: unknown arg $1" >&2; return 2 ;;
    esac
  done
  [[ -n "$head" ]] || { echo "reviewer-signoff: round needs --head" >&2; return 2; }
  local ts="" th="" ks="" kh="" out rc=0
  if [[ -n "$stamp" ]]; then
    ts="$(git rev-parse --verify --quiet "${stamp}:designs" 2>/dev/null)" || ts=""
    ks="$(key "$stamp" 2>/dev/null)" || ks=""
  fi
  th="$(git rev-parse --verify --quiet "${head}:designs" 2>/dev/null)" || th=""
  kh="$(key "$head" 2>/dev/null)" || kh=""
  out="$(_round_verdict "$stamp" "$ts" "$th" "$ks" "$kh")" || rc=$?
  if [[ "$rc" != 0 && "$out" == "ROUND design content changed"* ]]; then
    # Say which side of the rule the head fell on, so a commit-back that did
    # not qualify (a content verdict, a source in the diff) is legible.
    local hp; hp="$(_commit_problem "$head")"
    out="${out} (head ${head:0:8}: ${hp:-a qualifying commit-back})"
  fi
  echo "$out"; return "$rc"
}

# --- selftest: the decision table, each row with its negative control --------
selftest() {
  local pass=1 H="abc1230000000000000000000000000000000000"
  local T="tree1111111111111111111111111111111111111"
  local JOK="<!-- JANE_SIGNOFF sha=${H} verdict=pass fuse=none -->"
  local DOK="<!-- DRIK_SIGNOFF sha=${H} verdict=pass fuse=none -->"

  _expect() {  # _expect <label> <want:PASS|BLOCK> -- <decide args...>
    local label="$1" want="$2"; shift 3   # drop the literal --
    local out rc=0
    out="$(decide "$@")" || rc=$?
    local got="BLOCK"; [[ "$rc" == 0 ]] && got="PASS"
    if [[ "$got" != "$want" ]]; then
      echo "SELFTEST FAIL  ${label}: wanted ${want}, got ${got} — ${out}"
      pass=0; return
    fi
    echo "selftest ok    ${label} (${got}: ${out#* })"
  }

  # non-design PR passes with no markers at all (the always-report case)
  _expect non-design PASS -- --head "$H" --designs-changed false \
    --no-auto-review false --override false --fuse-warn false \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # design PR, both clean current sign-offs -> PASS
  _expect both-signed PASS -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "$JOK" --drik "$DOK" --tree-current "$T" --jane-tree "" --drik-tree ""

  # NEGATIVE CONTROLS — each must BLOCK, proving the gate can fail:

  # no markers at all (reviewers never ran / no key) -> fail-closed BLOCK
  _expect no-signoff BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # only Jane signed -> BLOCK
  _expect drik-missing BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "$JOK" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # Jane blocks -> BLOCK
  _expect jane-blocks BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "<!-- JANE_SIGNOFF sha=${H} verdict=block fuse=none -->" --drik "$DOK" \
    --tree-current "$T" --jane-tree "" --drik-tree ""

  # stale sign-off: marker sha != head AND its design tree differs -> BLOCK
  _expect stale BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "<!-- JANE_SIGNOFF sha=old0000000000000000000000000000000000000 verdict=pass fuse=none -->" \
    --drik "$DOK" --tree-current "$T" \
    --jane-tree "different2222222222222222222222222222222" --drik-tree ""

  # stale sha BUT the design tree is unchanged (a non-design push) -> PASS.
  # This is the currency carry-forward — the pair to the stale control above.
  _expect tree-carry-forward PASS -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "<!-- JANE_SIGNOFF sha=old0000000000000000000000000000000000000 verdict=pass fuse=none -->" \
    --drik "<!-- DRIK_SIGNOFF sha=old0000000000000000000000000000000000000 verdict=pass fuse=none -->" \
    --tree-current "$T" --jane-tree "$T" --drik-tree "$T"

  # malformed marker (missing verdict) -> BLOCK
  _expect malformed BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false \
    --jane "<!-- JANE_SIGNOFF sha=${H} fuse=none -->" --drik "$DOK" \
    --tree-current "$T" --jane-tree "" --drik-tree ""

  # fuse warn live, Jane didn't acknowledge (fuse=none) -> BLOCK
  _expect fuse-unacked BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn true \
    --jane "$JOK" --drik "<!-- DRIK_SIGNOFF sha=${H} verdict=pass fuse=acknowledged -->" \
    --tree-current "$T" --jane-tree "" --drik-tree ""

  # fuse warn live, BOTH acknowledged -> PASS (the pair to fuse-unacked)
  _expect fuse-acked PASS -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn true \
    --jane "<!-- JANE_SIGNOFF sha=${H} verdict=pass fuse=acknowledged -->" \
    --drik "<!-- DRIK_SIGNOFF sha=${H} verdict=pass fuse=acknowledged -->" \
    --tree-current "$T" --jane-tree "" --drik-tree ""

  # override label passes even a design PR with no sign-offs (human escape hatch)
  _expect override PASS -- --head "$H" --designs-changed true \
    --no-auto-review false --override true --fuse-warn false \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # no-auto-review label passes a design PR with no sign-offs (human escape hatch)
  _expect no-auto-review-label PASS -- --head "$H" --designs-changed true \
    --no-auto-review true --override false --fuse-warn false \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # AI ANDON CORD (docs/andon-cord.md) — with the cord pulled no reviewer ran:

  # design PR, no sign-offs, cord pulled -> BLOCK, naming the cord
  _expect andon-no-signoff BLOCK -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false --andon true \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # the description is the status text a human reads on the PR — pin it exactly
  local out want
  want="BLOCK andon cord pulled — reviews bypassed; release the cord or add signoff-override"
  out="$(decide --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false --andon true \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree "")" || true
  if [[ "$out" == "$want" ]]; then
    echo "selftest ok    andon-description"
  else
    echo "SELFTEST FAIL  andon-description: wanted '${want}', got '${out}'"; pass=0
  fi

  # NEGATIVE CONTROL: with the cord released the same PR must NOT blame the cord
  out="$(decide --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false --andon false \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree "")" || true
  if [[ "$out" != *"andon cord"* ]]; then
    echo "selftest ok    andon-off-no-leak (${out#* })"
  else
    echo "SELFTEST FAIL  andon-off-no-leak: cord released but the text blames it — ${out}"; pass=0
  fi

  # two clean current sign-offs still PASS under the cord (a review that ran is
  # a fact about the design tree; the cord stops AI consumption, not merging)
  _expect andon-both-signed PASS -- --head "$H" --designs-changed true \
    --no-auto-review false --override false --fuse-warn false --andon true \
    --jane "$JOK" --drik "$DOK" --tree-current "$T" --jane-tree "" --drik-tree ""

  # the short-circuits outrank the cord: non-design PR, override, no-auto-review
  _expect andon-non-design PASS -- --head "$H" --designs-changed false \
    --no-auto-review false --override false --fuse-warn false --andon true \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""
  _expect andon-override PASS -- --head "$H" --designs-changed true \
    --no-auto-review false --override true --fuse-warn false --andon true \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""
  _expect andon-no-auto-review PASS -- --head "$H" --designs-changed true \
    --no-auto-review true --override false --fuse-warn false --andon true \
    --jane "" --drik "" --tree-current "$T" --jane-tree "" --drik-tree ""

  # THE REGEN COMMIT-BACK RULE (issue #470) — pure tables, then real git.
  selftest_regen

  if [[ "$pass" == 1 ]]; then
    echo "ok    reviewer-signoff --selftest: the sign-off gate passes clean and fails closed"
    return 0
  fi
  echo "FAIL  reviewer-signoff --selftest: a decision-table row was wrong"
  return 1
}

# selftest_regen — sets the caller's `pass` to 0 on any wrong row.
selftest_regen() {
  local P="designs/d/previews"
  local label parents subj auth trl paths want got stamp
  # (a) _regen_problem: the qualifying commit-back, then a negative control per
  #     condition. Fields: label|parents|subject|author|trailers|paths, with
  #     S/B standing for the real subject/author, "~" for an empty field, ","
  #     separating paths and ";" separating trailer values.
  while IFS='|' read -r label parents subj auth trl paths want; do
    [[ -n "$label" ]] || continue
    [[ "$subj" == S ]] && subj="$REGEN_SUBJECT"
    [[ "$auth" == B ]] && auth="$REGEN_AUTHOR"
    [[ "$trl" == "~" ]] && trl=""
    [[ "$paths" == "~" ]] && paths=""
    got="$(_regen_problem "$parents" "$subj" "$auth" "${trl//;/$'\n'}" "${paths//,/$'\n'}")"
    if [[ ( "$want" == ok && -z "$got" ) || ( "$want" == no && -n "$got" ) ]]; then
      echo "selftest ok    regen ${label} (${got:-qualifies})"
    else
      echo "SELFTEST FAIL  regen ${label}: wanted ${want}, got '${got:-qualifies}'"; pass=0
    fi
  done <<ROWS
previews-and-stamp|1|S|B|all-noise|$P/a.png,$P/.regen-stamp|ok
stamp-only|1|S|B|all-noise|$P/.regen-stamp|ok
gif|1|S|B|all-noise|$P/spin.gif|ok
NEGCTL-merge|2|S|B|all-noise|$P/a.png|no
NEGCTL-subject|1|Update design: d|B|all-noise|$P/a.png|no
NEGCTL-author|1|S|someone@example.invalid|all-noise|$P/a.png|no
NEGCTL-no-trailer|1|S|B|~|$P/a.png|no
NEGCTL-content-trailer|1|S|B|content|$P/a.png|no
NEGCTL-two-trailers|1|S|B|all-noise;all-noise|$P/a.png|no
NEGCTL-empty-diff|1|S|B|all-noise|~|no
NEGCTL-scad-beside-previews|1|S|B|all-noise|$P/a.png,designs/d/d.scad|no
NEGCTL-cameras-conf|1|S|B|all-noise|$P/cameras.conf|no
NEGCTL-CAMERAS-md|1|S|B|all-noise|$P/CAMERAS.md|no
NEGCTL-design-readme|1|S|B|all-noise|$P/a.png,designs/d/README.md|no
NEGCTL-root-readme|1|S|B|all-noise|$P/a.png,README.md|no
NEGCTL-nested-preview|1|S|B|all-noise|$P/sub/a.png|no
NEGCTL-uppercase-ext|1|S|B|all-noise|$P/A.PNG|no
ROWS

  # (b) _round_verdict: SKIP, then a negative control per condition.
  local ts th ks kh
  while IFS='|' read -r label stamp ts th ks kh want; do
    [[ -n "$label" ]] || continue
    [[ "$stamp" == "~" ]] && stamp=""
    [[ "$kh" == "~" ]] && kh=""
    got="$(_round_verdict "$stamp" "$ts" "$th" "$ks" "$kh")" || true
    if [[ "${got%% *}" == "$want" ]]; then
      echo "selftest ok    round ${label} (${got})"
    else
      echo "SELFTEST FAIL  round ${label}: wanted ${want}, got '${got}'"; pass=0
    fi
  done <<'ROWS'
noise-commit-back|s0|t1|t2|k1|k1|SKIP
NEGCTL-no-stamp|~|t1|t2|k1|k1|ROUND
NEGCTL-unresolvable-key|s0|t1|t2|k1|~|ROUND
NEGCTL-head-tree-unchanged|s0|t1|t1|k1|k1|ROUND
NEGCTL-key-moved|s0|t1|t2|k1|k2|ROUND
ROWS

  selftest_regen_git
  selftest_regen_drift
}

# selftest_regen_git — the rule against real commits in a throwaway repo, fed
# through `key`, `round` and `decide` exactly as auto-review.yml does.
selftest_regen_git() {
  local r
  r="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand $r now: it is local to this function
  trap "rm -rf '$r'; trap - RETURN" RETURN
  local d="designs/d" p="designs/d/previews"
  (
    cd "$r" || exit 1
    g() { git "$@"; }
    g init -q
    g config user.name selftest
    g config user.email selftest@example.invalid
    g config commit.gpgsign false
    as_bot() {
      GIT_AUTHOR_NAME="github-actions[bot]" GIT_AUTHOR_EMAIL="$REGEN_AUTHOR" "$@"
    }
    mkdir -p "$p" docs
    echo "cube(10);" > "$d/d.scad"
    echo "iso | 0,0,0,55,0,25,140" > "$p/cameras.conf"
    echo "# iso" > "$p/CAMERAS.md"
    echo "png-0" > "$p/a.png"
    echo "stamp-0" > "$p/.regen-stamp"
    echo "docs" > docs/x.md
    echo "readme" > README.md
    g add -A && g commit -qm base && g tag base
    # A — the author's design change, the round the sign-offs are on.
    echo "cube(12);" > "$d/d.scad"; g commit -qam A && g tag A
    # R — the all-noise, previews-only commit-back.
    echo "png-1" > "$p/a.png"; echo "stamp-1" > "$p/.regen-stamp"
    as_bot g commit -qam "$REGEN_SUBJECT" -m "$REGEN_TRAILER: all-noise" && g tag R
    # D — a docs-only push after it; E — a design push after that.
    echo "more docs" >> docs/x.md; g commit -qam D && g tag D
    echo "cube(14);" > "$d/d.scad"; g commit -qam E && g tag E
    # The negatives, each one commit off A.
    variant() {  # variant <tag> <bot|human> <trailer|-> <file>...
      local tag="$1" who="$2" trl="$3"; shift 3
      g checkout -q -B "v-$tag" A
      local f; for f in "$@"; do echo "$tag" >> "$f"; done
      local msg=(-m "$REGEN_SUBJECT"); [[ "$trl" != - ]] && msg+=(-m "$REGEN_TRAILER: $trl")
      if [[ "$who" == bot ]]; then as_bot g commit -qa "${msg[@]}"; else g commit -qa "${msg[@]}"; fi
      g tag "$tag"
    }
    variant Rcontent bot content "$p/a.png" "$p/.regen-stamp"
    variant Rforged bot all-noise "$p/a.png" "$d/d.scad"
    variant Rconf bot all-noise "$p/a.png" "$p/cameras.conf"
    variant Rhuman human all-noise "$p/a.png"
    variant Rbare bot - "$p/a.png"
    variant Hconf human - "$p/cameras.conf"
    variant Rstamp bot all-noise "$p/.regen-stamp"
    variant Rreadme bot all-noise "$p/a.png" README.md
    # A merge of the base branch into R: one that brings a designs/ change and
    # one that brings only docs.
    g checkout -q -B main base
    echo "docs on main" > docs/y.md; g add -A; g commit -qm "main docs" && g tag Mdocs
    g checkout -q -B v-mdocs R; g merge -q --no-edit Mdocs && g tag Rmdocs
    g checkout -q main; mkdir -p designs/e; echo "e" > designs/e/e.scad; g add -A
    g commit -qm "main design" && g tag Mdesign
    g checkout -q -B v-mdesign R; g merge -q --no-edit Mdesign && g tag Rmdesign
  ) >/dev/null 2>&1 || { echo "SELFTEST FAIL  regen-git: could not build the fixture repo"; pass=0; return; }

  local kA got want label tag stamp
  kA="$(git -C "$r" rev-parse "A:designs")"
  _k() { (cd "$r" && key "$(git rev-parse "$1")"); }
  # key: current (== key(A)) or stale, per head.
  while IFS='|' read -r label tag want; do
    [[ -n "$label" ]] || continue
    got=stale; [[ "$(_k "$tag")" == "$kA" ]] && got=current
    if [[ "$got" == "$want" ]]; then
      echo "selftest ok    key ${label} (${got})"
    else
      echo "SELFTEST FAIL  key ${label}: wanted ${want}, got ${got}"; pass=0
    fi
  done <<'ROWS'
signed-commit-itself|A|current
all-noise-previews-only-commit-back|R|current
docs-push-after-the-commit-back|D|current
stamp-only-commit-back|Rstamp|current
docs-only-merge-after-the-commit-back|Rmdocs|current
NEGCTL-design-push-after-the-commit-back|E|stale
NEGCTL-content-commit-back|Rcontent|stale
NEGCTL-forged-trailer-also-touching-the-scad|Rforged|stale
NEGCTL-commit-back-touching-cameras-conf|Rconf|stale
NEGCTL-human-authored-all-noise-trailer|Rhuman|stale
NEGCTL-commit-back-without-a-trailer|Rbare|stale
NEGCTL-hand-edit-to-a-preview-conf|Hconf|stale
NEGCTL-commit-back-touching-the-root-readme|Rreadme|stale
NEGCTL-merge-bringing-a-design-change|Rmdesign|stale
NEGCTL-the-base-before-the-signed-commit|base|stale
ROWS
  local kbad
  kbad="$( (cd "$r" && key no-such-ref) 2>/dev/null)" && kbad="resolved:$kbad" || kbad=""
  if [[ -z "$kbad" ]]; then
    echo "selftest ok    key NEGCTL-unresolvable-commit (empty, exit 1)"
  else
    echo "SELFTEST FAIL  key NEGCTL-unresolvable-commit: ${kbad}"; pass=0
  fi

  # round: the guard auto-review.yml asks, with the stamp on A.
  while IFS='|' read -r label tag stamp want; do
    [[ -n "$label" ]] || continue
    local hs ss=""
    hs="$(git -C "$r" rev-parse "$tag")"
    [[ "$stamp" != "~" ]] && ss="$(git -C "$r" rev-parse "$stamp")"
    got="$( (cd "$r" && round --head "$hs" --stamp "$ss") )" || true
    if [[ "${got%% *}" == "$want" ]]; then
      echo "selftest ok    round-git ${label} (${got%% *})"
    else
      echo "SELFTEST FAIL  round-git ${label}: wanted ${want}, got '${got}'"; pass=0
    fi
  done <<'ROWS'
all-noise-commit-back|R|A|SKIP
docs-push-after-a-skipped-commit-back|D|A|SKIP
NEGCTL-content-commit-back|Rcontent|A|ROUND
NEGCTL-forged-trailer-also-touching-the-scad|Rforged|A|ROUND
NEGCTL-no-stamp|R|~|ROUND
NEGCTL-stamp-before-the-design-change|R|base|ROUND
NEGCTL-head-designs-unchanged-since-the-stamp|A|A|ROUND
ROWS

  # decide, fed the keys the way auto-review.yml feeds them: Jane and Drik
  # signed A; the head has moved on to <tag>.
  local H JA DA
  JA="<!-- JANE_SIGNOFF sha=$(git -C "$r" rev-parse A) verdict=pass fuse=none -->"
  DA="<!-- DRIK_SIGNOFF sha=$(git -C "$r" rev-parse A) verdict=pass fuse=none -->"
  while IFS='|' read -r label tag want; do
    [[ -n "$label" ]] || continue
    H="$(git -C "$r" rev-parse "$tag")"
    _expect "regen ${label}" "$want" -- --head "$H" --designs-changed true \
      --no-auto-review false --override false --fuse-warn false \
      --jane "$JA" --drik "$DA" --tree-current "$(_k "$tag")" \
      --jane-tree "$kA" --drik-tree "$kA"
  done <<'ROWS'
signoff-carries-across-an-all-noise-commit-back|R|PASS
NEGCTL-content-commit-back-stales-the-signoff|Rcontent|BLOCK
NEGCTL-hand-edit-to-a-preview-conf-stales-the-signoff|Hconf|BLOCK
NEGCTL-forged-trailer-on-a-scad-commit-stales-the-signoff|Rforged|BLOCK
ROWS
}

# selftest_regen_drift — ci.yml must still write the commit-back this script
# recognises. A drift would not fail open (no commit would qualify, so every
# commit-back reopens review), but it would switch the owner's ruling off
# silently. The negative control runs the same pin on a copy with the trailer
# line removed, and must fail.
_regen_pin() {  # _regen_pin <ci.yml> — prints the first missing literal
  local f="$1" lit
  for lit in \
    "REGEN_SUBJECT: \"${REGEN_SUBJECT}\"" \
    "git config user.email \"${REGEN_AUTHOR}\"" \
    "-m \"${REGEN_TRAILER}: \${PREVIEW_VERDICT}\"" \
    "PREVIEW-DIFF-VERDICT"; do
    grep -qF -- "$lit" "$f" || { printf '%s' "$lit"; return 1; }
  done
}
selftest_regen_drift() {
  local ci miss tmp
  ci="$(dirname "$0")/../.github/workflows/ci.yml"
  if [[ ! -f "$ci" ]]; then
    echo "SELFTEST FAIL  regen-drift: $ci not found"; pass=0; return
  fi
  if miss="$(_regen_pin "$ci")"; then
    echo "selftest ok    regen-drift ci.yml writes the commit-back this script recognises"
  else
    echo "SELFTEST FAIL  regen-drift: ci.yml no longer contains: ${miss}"; pass=0
  fi
  tmp="$(mktemp)"
  grep -vF -- "-m \"${REGEN_TRAILER}: \${PREVIEW_VERDICT}\"" "$ci" > "$tmp" || true
  if _regen_pin "$tmp" >/dev/null; then
    echo "SELFTEST FAIL  regen-drift NEGCTL: the pin passed a ci.yml with no trailer line"; pass=0
  else
    echo "selftest ok    regen-drift NEGCTL a ci.yml that stopped writing the trailer fails the pin"
  fi
  rm -f "$tmp"
}

case "${1:-}" in
  --selftest) selftest ;;
  decide) shift; decide "$@" ;;
  key) shift; key "$@" ;;
  round) shift; round "$@" ;;
  *) echo "usage: reviewer-signoff.sh decide <args> | key <commit> | round --head <sha> --stamp <sha> | --selftest" >&2; exit 2 ;;
esac
