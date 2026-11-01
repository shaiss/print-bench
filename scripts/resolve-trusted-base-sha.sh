#!/usr/bin/env bash
# resolve-trusted-base-sha: tip of the PR base branch for trust-boundary restores.
#
# auto-review.yml restores scripts/reviewer-posted.sh, reviewer-signoff.sh and
# coach-lock-check.sh before they decide pass/block. Those restores used
# github.event.pull_request.base.sha, which freezes at open/retarget and goes
# stale when main moves — a pre-#947 checker without the `marker` verb then
# exit-2'd and the status treated genuine Actions-bot markers as absent.
#
# Policy (always-tip): resolve refs/heads/<base.ref> from the server NOW, never
# from the event payload's base.sha. A tip restore is what every open PR needs
# once main carries the current checker; using base.sha when it "looks current"
# still races a push to main between open and the status job. Always-tip also
# keeps one code path (no "predates tip" branch that can fail open).
#
# base.ref itself is payload-supplied, so it is checked against the repository
# default_branch from the API; anything else fails closed. The resolved object
# must be 40 lowercase hex and an ancestor-or-equal of the trusted ref tip
# (for always-tip: equal to the tip). Empty/malformed/fetch failure → exit 1.
#
# Usage:
#   scripts/resolve-trusted-base-sha.sh resolve --base-ref <name>
#     Print the 40-hex tip sha. Needs GH_TOKEN + network (or TRUSTED_BASE_RESOLVE_MOCK).
#   scripts/resolve-trusted-base-sha.sh assert-sha <sha>
#     Exit 0 iff <sha> is 40 lowercase hex (LOW-1 guard before every git show).
#   scripts/resolve-trusted-base-sha.sh --selftest
#
# Consumers: auto-review.yml (inline twin of resolve + assert-sha before every
# restore of the three scripts). The workflow inlines the same checks so a
# PR-head rewrite of THIS file cannot supply the sha restored from; this
# script is the tested contract the drift pin in --selftest enforces on the YAML.
set -euo pipefail

unset PYTHONPATH PYTHONHOME PYTHONSTARTUP PYTHONUSERBASE \
      PYTHONEXECUTABLE LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT \
      DYLD_INSERT_LIBRARIES BASH_ENV ENV || true
export PYTHONNOUSERSITE=1

usage() {
  echo "usage: resolve-trusted-base-sha.sh resolve --base-ref <name>" >&2
  echo "       resolve-trusted-base-sha.sh assert-sha <sha>" >&2
  echo "       resolve-trusted-base-sha.sh --selftest" >&2
  exit 2
}

assert_sha() {
  local sha="${1:-}"
  if ! [[ "$sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "TRUSTED_SHA empty or malformed (want 40 lowercase hex, got: ${sha:-empty})" >&2
    return 1
  fi
  return 0
}

# Optional mock seam for --selftest: TRUSTED_BASE_RESOLVE_MOCK is a dir of
# files named default_branch and ref-<branch> (contents = sha or empty).
_api_default_branch() {
  if [[ -n "${TRUSTED_BASE_RESOLVE_MOCK:-}" ]]; then
    cat "${TRUSTED_BASE_RESOLVE_MOCK}/default_branch"
    return 0
  fi
  # gh api --jq takes the filter as the next arg; do NOT pass -r
  # (that makes the filter `-r` and leaves the value empty).
  gh api "repos/${GITHUB_REPOSITORY}" --jq .default_branch
}

_api_ref_sha() {
  local ref="$1"
  if [[ -n "${TRUSTED_BASE_RESOLVE_MOCK:-}" ]]; then
    local f="${TRUSTED_BASE_RESOLVE_MOCK}/ref-${ref}"
    if [[ -f "$f" ]]; then
      cat "$f"
      return 0
    fi
    echo "" 
    return 0
  fi
  gh api "repos/${GITHUB_REPOSITORY}/git/ref/heads/${ref}" --jq .object.sha
}

# persist-credentials: false — GH_TOKEN authenticates gh, not bare git.
# Same masked, command-scoped extraheader pattern as auto-review.yml.
_git_authed() {
  local fetch_auth
  fetch_auth="$(printf 'x-access-token:%s' "${GH_TOKEN:?}" | base64 | tr -d '\n')"
  # Mask when running under Actions; harmless locally.
  if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
    echo "::add-mask::${fetch_auth}"
  fi
  git -c "http.https://github.com/.extraheader=Authorization: Basic ${fetch_auth}" "$@"
}

resolve() {
  local base_ref="" tip ref_tip
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --base-ref) base_ref="${2:-}"; shift 2 ;;
      *) usage ;;
    esac
  done
  [[ -n "$base_ref" ]] || usage

  local default_branch
  default_branch="$(_api_default_branch)"
  default_branch="${default_branch//$'\r'/}"
  default_branch="${default_branch//$'\n'/}"
  if [[ -z "$default_branch" || "$base_ref" != "$default_branch" ]]; then
    echo "base.ref '${base_ref}' is not the repository default branch '${default_branch}' — fail closed" >&2
    return 1
  fi

  tip="$(_api_ref_sha "$base_ref")"
  tip="${tip//$'\r'/}"
  tip="${tip//$'\n'/}"
  tip="${tip##* }"  # ls-remote style "sha\tref" → sha
  if ! assert_sha "$tip"; then
    echo "trusted tip sha empty or malformed for refs/heads/${base_ref}" >&2
    return 1
  fi

  # Fetch when needed so ancestor checks and git show can read the object.
  if [[ -z "${TRUSTED_BASE_RESOLVE_MOCK:-}" ]]; then
    if ! git cat-file -e "${tip}^{commit}" 2>/dev/null; then
      _git_authed fetch --no-tags origin "$tip" || {
        echo "could not fetch trusted tip ${tip}" >&2
        return 1
      }
    fi
    # Cross-check against a second server view (ls-remote) so a single
    # confused API response cannot pin an attacker-chosen ancestor.
    ref_tip="$(_git_authed ls-remote origin "refs/heads/${base_ref}" | awk '{print $1; exit}')"
    if ! assert_sha "$ref_tip"; then
      echo "ls-remote tip for refs/heads/${base_ref} empty or malformed" >&2
      return 1
    fi
    if [[ "$tip" != "$ref_tip" ]]; then
      echo "API tip ${tip} diverges from ls-remote tip ${ref_tip} — fail closed" >&2
      return 1
    fi
    if ! git merge-base --is-ancestor "$tip" "$ref_tip"; then
      echo "trusted sha ${tip} is not an ancestor of the trusted ref tip" >&2
      return 1
    fi
  fi

  printf '%s\n' "$tip"
}

selftest() {
  local pass=1 tmp tip out rc wf
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  # --- assert-sha (LOW-1) ---
  if assert_sha "0123456789abcdef0123456789abcdef01234567"; then
    echo "selftest ok    assert-sha accepts 40 lowercase hex"
  else
    echo "SELFTEST FAIL  assert-sha rejected a valid sha"; pass=0
  fi
  for bad in "" "abc" "0123456789ABCDEF0123456789ABCDEF01234567" \
             "0123456789abcdef0123456789abcdef0123456" \
             "0123456789abcdef0123456789abcdef012345678"; do
    if assert_sha "$bad" 2>/dev/null; then
      echo "SELFTEST FAIL  assert-sha accepted malformed '${bad}'"; pass=0
    else
      echo "selftest ok    assert-sha rejects '${bad:-empty}'"
    fi
  done

  # --- resolve: default branch tip (stale event base.sha must be ignored) ---
  mkdir -p "$tmp/mock-ok"
  tip="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  printf '%s\n' "main" >"$tmp/mock-ok/default_branch"
  printf '%s\n' "$tip" >"$tmp/mock-ok/ref-main"
  # A stale event sha in the environment must not win over the tip.
  export TRUSTED_BASE_RESOLVE_MOCK="$tmp/mock-ok"
  export GITHUB_REPOSITORY="owner/repo"
  out="$(env BASE_SHA="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" \
    "$0" resolve --base-ref main)" || { echo "SELFTEST FAIL  resolve main failed"; pass=0; out=""; }
  if [[ "$out" == "$tip" ]]; then
    echo "selftest ok    resolve returns server tip (ignores stale BASE_SHA)"
  else
    echo "SELFTEST FAIL  resolve wanted tip ${tip}, got '${out}'"; pass=0
  fi

  # --- resolve: forged / non-default base.ref fails closed ---
  if out="$( "$0" resolve --base-ref attacker-branch 2>"$tmp/err" )"; then
    echo "SELFTEST FAIL  forged base.ref resolved to '${out}'"; pass=0
  else
    if grep -q "not the repository default branch" "$tmp/err"; then
      echo "selftest ok    forged base.ref fails closed"
    else
      echo "SELFTEST FAIL  forged base.ref error missing: $(cat "$tmp/err")"; pass=0
    fi
  fi

  # --- resolve: empty tip fails closed ---
  mkdir -p "$tmp/mock-empty"
  printf '%s\n' "main" >"$tmp/mock-empty/default_branch"
  : >"$tmp/mock-empty/ref-main"
  export TRUSTED_BASE_RESOLVE_MOCK="$tmp/mock-empty"
  if out="$( "$0" resolve --base-ref main 2>"$tmp/err" )"; then
    echo "SELFTEST FAIL  empty tip resolved to '${out}'"; pass=0
  else
    echo "selftest ok    empty trusted tip fails closed"
  fi

  # --- resolve: malformed tip fails closed ---
  mkdir -p "$tmp/mock-bad"
  printf '%s\n' "main" >"$tmp/mock-bad/default_branch"
  printf '%s\n' "not-a-sha" >"$tmp/mock-bad/ref-main"
  export TRUSTED_BASE_RESOLVE_MOCK="$tmp/mock-bad"
  if out="$( "$0" resolve --base-ref main 2>"$tmp/err" )"; then
    echo "SELFTEST FAIL  malformed tip resolved to '${out}'"; pass=0
  else
    echo "selftest ok    malformed trusted tip fails closed"
  fi

  unset TRUSTED_BASE_RESOLVE_MOCK

  # --- marker trust fixtures (stale base + bot vs user) ---
  # The restore policy is "always tip"; once tip carries marker, a stale
  # event base.sha cannot demote a genuine Actions-bot MCP suffix. The
  # marker verb itself is proven in reviewer-posted.sh; here we pin that a
  # tip-current checker serves bot markers and refuses user plants.
  local posted head footer jane PYTHON3
  posted="$(dirname "$0")/reviewer-posted.sh"
  head="0123456789abcdef0123456789abcdef01234567"
  footer=$'---\n_Generated by [Claude Code](https://claude.ai/code)_'
  jane="<!-- JANE_SIGNOFF sha=${head} verdict=pass fuse=none -->"
  if [[ -x /usr/bin/python3 ]]; then PYTHON3=/usr/bin/python3; else PYTHON3=python3; fi
  HEAD="$head" FOOTER="$footer" JANE="$jane" \
    BOT_PATH="$tmp/bot.json" USER_PATH="$tmp/user.json" \
    "$PYTHON3" -I -c '
import json, os
head, footer, jane = os.environ["HEAD"], os.environ["FOOTER"], os.environ["JANE"]
bot = [{"body": f"ok\n\n{jane}\n\n{footer}",
        "user": {"login": "github-actions[bot]", "type": "Bot"}}]
user = [{"body": f"plant\n\n{jane}\n\n{footer}",
         "user": {"login": "attacker", "type": "User"}}]
open(os.environ["BOT_PATH"], "w", encoding="utf-8").write(json.dumps(bot))
open(os.environ["USER_PATH"], "w", encoding="utf-8").write(json.dumps(user))
'
  rc=0
  out="$("$posted" marker --pr 1 --sha "$head" \
    --reviewer jane --comments-file "$tmp/bot.json" --currency)" || rc=$?
  out="${out%$'\n'}"
  if [[ "$rc" -eq 0 && "$out" == "$jane" ]]; then
    echo "selftest ok    stale-base scenario: tip checker + Actions-bot marker → served"
  else
    echo "SELFTEST FAIL  bot marker not served (rc=${rc}, out='${out}')"; pass=0
  fi
  out="$("$posted" marker --pr 1 --sha "$head" \
    --reviewer jane --comments-file "$tmp/user.json" --currency || true)"
  out="${out%$'\n'}"
  if [[ -z "$out" ]]; then
    echo "selftest ok    stale-base scenario: tip checker + user-planted marker → absent"
  else
    echo "SELFTEST FAIL  user plant served as '${out}'"; pass=0
  fi

  # --- behavioral: gh api --jq must take the filter next (not -r) ---
  # A fake `gh` on PATH records argv and refuses `--jq -r`; exercising the
  # real `_api_*` helpers (no TRUSTED_BASE_RESOLVE_MOCK) catches the CI
  # failure mode where default_branch came back empty.
  mkdir -p "$tmp/fakebin"
  cat >"$tmp/fakebin/gh" <<'FAKEGH'
#!/usr/bin/env bash
set -euo pipefail
args=("$@")
for i in "${!args[@]}"; do
  if [[ "${args[$i]}" == "--jq" ]]; then
    next="${args[$((i+1))]:-}"
    if [[ "$next" == "-r" ]]; then
      echo "accepts 1 arg(s), received 2" >&2
      exit 1
    fi
  fi
done
# Emit canned values for the two queries resolve() issues.
joined="${args[*]}"
if [[ "$joined" == *"/git/ref/heads/"* ]]; then
  printf '%s\n' "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  exit 0
fi
if [[ "$joined" == *"repos/"* ]]; then
  printf '%s\n' "main"
  exit 0
fi
echo "fake gh: unexpected argv: $joined" >&2
exit 1
FAKEGH
  chmod +x "$tmp/fakebin/gh"
  # Also fake git so resolve()'s fetch/ls-remote path is exercised without network.
  cat >"$tmp/fakebin/git" <<'FAKEGIT'
#!/usr/bin/env bash
set -euo pipefail
# Require the authed extraheader on fetch/ls-remote (private-repo path).
joined="$*"
if [[ "$joined" == *"ls-remote"* || "$joined" == *"fetch"* ]]; then
  if [[ "$joined" != *"extraheader=Authorization: Basic"* ]]; then
    echo "fake git: missing auth extraheader for: $joined" >&2
    exit 1
  fi
fi
if [[ "$joined" == *"cat-file"* ]]; then
  exit 0  # tip already "local"
fi
if [[ "$joined" == *"ls-remote"* ]]; then
  printf '%s\t%s\n' "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" "refs/heads/main"
  exit 0
fi
if [[ "$joined" == *"merge-base"* ]]; then
  exit 0
fi
if [[ "$joined" == *"fetch"* ]]; then
  exit 0
fi
# Fall through to real git for anything unexpected? refuse.
echo "fake git: unexpected: $joined" >&2
exit 1
FAKEGIT
  chmod +x "$tmp/fakebin/git"
  (
    export PATH="$tmp/fakebin:/usr/bin:/bin"
    export GITHUB_REPOSITORY="shaiss/print-bench"
    export GH_TOKEN="test-token-not-real"
    unset TRUSTED_BASE_RESOLVE_MOCK
    tip_out="$(resolve --base-ref main)" || tip_out=""
    if [[ "$tip_out" == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" ]]; then
      echo "selftest ok    behavioral: gh api --jq filter (not -r) + authed git resolve"
    else
      echo "SELFTEST FAIL  behavioral resolve got '${tip_out}'"; pass=0
    fi
    # NEGCTL: the broken --jq -r form must fail under the same fake gh.
    if ! gh api "repos/${GITHUB_REPOSITORY}" --jq -r .default_branch >/dev/null 2>"$tmp/jq-r.err"; then
      if grep -q 'accepts 1 arg' "$tmp/jq-r.err"; then
        echo "selftest ok    NEGCTL: gh api --jq -r fails closed (behavioral)"
      else
        echo "SELFTEST FAIL  NEGCTL --jq -r failed differently: $(cat "$tmp/jq-r.err")"; pass=0
      fi
    else
      echo "SELFTEST FAIL  NEGCTL --jq -r unexpectedly succeeded"; pass=0
    fi
  )

  # --- workflow drift pin (always-tip + LOW-1 + LOW-2 + no silent #947 exit-2) ---
  wf="$(dirname "$0")/../.github/workflows/auto-review.yml"
  if [[ ! -f "$wf" ]]; then
    echo "SELFTEST FAIL  drift: $wf missing"; pass=0
  else
    local miss=""
    if ! grep -qF 'TRUSTED_SHA' "$wf"; then
      miss="TRUSTED_SHA not used"
    elif ! grep -qE 'default_branch' "$wf"; then
      miss="default_branch validation missing"
    elif ! grep -qE 'git/ref/heads/|ls-remote.*refs/heads/' "$wf"; then
      miss="server-side tip resolve missing"
    elif ! grep -qF 'merge-base --is-ancestor' "$wf"; then
      miss="ancestor assertion missing"
    elif grep -qE 'git show "\$\{BASE_SHA\}:scripts/(reviewer-posted|reviewer-signoff|coach-lock-check)\.sh"' "$wf"; then
      miss="still restores a trust script from BASE_SHA (event payload)"
    elif ! grep -qE 'git show "\$\{TRUSTED_SHA\}:scripts/reviewer-posted\.sh"' "$wf"; then
      miss="reviewer-posted.sh not restored from TRUSTED_SHA"
    elif ! grep -qE 'git show "\$\{TRUSTED_SHA\}:scripts/reviewer-signoff\.sh"' "$wf"; then
      miss="reviewer-signoff.sh not restored from TRUSTED_SHA"
    elif ! grep -qE 'git show "\$\{TRUSTED_SHA\}:scripts/coach-lock-check\.sh"' "$wf"; then
      miss="coach-lock-check.sh not restored from TRUSTED_SHA"
    elif grep -qF 'predates #947 marker verb — treating' "$wf"; then
      miss="silent predates #947 exit-2 branch still present"
    elif ! grep -qF 'user.login // "") == "github-actions[bot]"' "$wf"; then
      miss="printcheck sticky not filtered to github-actions[bot]"
    elif ! grep -qF 'user.type // "") == "Bot"' "$wf"; then
      miss="printcheck sticky not filtered to type Bot"
    elif grep -qE -- '--jq -r' "$wf"; then
      miss="gh api still uses broken --jq -r"
    elif ! grep -qF 'trusted_sha=${TRUSTED_SHA}' "$wf"; then
      miss="coach ready step does not publish trusted_sha via GITHUB_OUTPUT"
    elif grep -qE 'TRUSTED_SHA=.*GITHUB_ENV' "$wf"; then
      miss="TRUSTED_SHA still exported via GITHUB_ENV (coach-overwriteable)"
    elif ! grep -qF 'TRUSTED_SHA: ${{ steps.ready.outputs.trusted_sha }}' "$wf"; then
      miss="consumers do not bind TRUSTED_SHA from ready step output"
    elif grep -qE 'git checkout "\$BASE_SHA" --' "$wf"; then
      miss="coach overlay still checks out from BASE_SHA"
    elif ! grep -qE 'git checkout "\$TRUSTED_SHA" --' "$wf"; then
      miss="coach overlay does not checkout from TRUSTED_SHA"
    elif ! grep -qF 'extraheader=Authorization: Basic ${fetch_auth}' "$wf"; then
      miss="resolve_trusted_sha missing authenticated git fetch/ls-remote"
    fi
    if [[ -z "$miss" ]]; then
      echo "selftest ok    auto-review.yml always-tip restore + LOW-1/LOW-2 pins"
    else
      echo "SELFTEST FAIL  drift: ${miss}"; pass=0
    fi
    # NEGCTL: a YAML that restored from BASE_SHA again must fail the pin shape
    if grep -qE 'git show "\$\{BASE_SHA\}:scripts/reviewer-posted\.sh"' "$wf"; then
      echo "SELFTEST FAIL  NEGCTL precondition: live YAML still has BASE_SHA restore"; pass=0
    else
      echo "selftest ok    NEGCTL live YAML no longer restores reviewer-posted from BASE_SHA"
    fi
  fi

  if [[ "$pass" -eq 1 ]]; then
    echo "resolve-trusted-base-sha.sh --selftest: OK"
    return 0
  fi
  echo "resolve-trusted-base-sha.sh --selftest: FAILED" >&2
  return 1
}

case "${1:-}" in
  resolve) shift; resolve "$@" ;;
  assert-sha) shift; assert_sha "${1:-}" ;;
  --selftest) selftest ;;
  *) usage ;;
esac
