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
#       --tree-current <treesha>       git rev-parse HEAD:designs (current design tree)
#       --jane-tree <treesha|empty>    git rev-parse <jane-sha>:designs (empty if gone)
#       --drik-tree <treesha|empty>    git rev-parse <drik-sha>:designs
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
# its sha IS the head, OR the design tree at its sha equals the current design
# tree — so a later push that touches only docs/CI (which advances the head sha
# but changes no designs/ file) does NOT strand a reviewed PR, matching
# auto-review.yml's own is_new_round dedup. A design change moves the tree and
# correctly invalidates the sign-off.
set -euo pipefail

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

  if [[ "$pass" == 1 ]]; then
    echo "ok    reviewer-signoff --selftest: the sign-off gate passes clean and fails closed"
    return 0
  fi
  echo "FAIL  reviewer-signoff --selftest: a decision-table row was wrong"
  return 1
}

case "${1:-}" in
  --selftest) selftest ;;
  decide) shift; decide "$@" ;;
  *) echo "usage: reviewer-signoff.sh decide <args> | --selftest" >&2; exit 2 ;;
esac
