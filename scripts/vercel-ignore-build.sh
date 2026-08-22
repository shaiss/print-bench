#!/usr/bin/env bash
# scripts/vercel-ignore-build.sh — the Vercel "Ignored Build Step" gate.
#
# Wire it in at Vercel: Project Settings -> Git -> Ignored Build Step ->
#   bash scripts/vercel-ignore-build.sh
#
# Vercel runs this command before each deployment and reads its EXIT CODE:
#   exit 1  -> continue the build   (BUILD)
#   exit 0  -> skip the build       (SKIP)
#
# Why it exists: the static site (site/build.mjs) is a pure function of a
# specific slice of the repo — designs/, styles/, people/, site/, the
# architecture and contributor docs (served raw and indexed by /llms.txt),
# telemetry, a couple of root files, and the include
# closure of each design's .scad (which resolves through lib/, so lib/ counts).
# A pull request that touches only CI/tooling/scripts/libs-the-site-doesn't-use
# produces a byte-identical site, so its preview deployment is wasted spend.
# This gate skips exactly those, and nothing else.
#
# Bias is deliberately conservative: we BUILD unless EVERY changed file is
# provably outside the site's input set. An unknown path (a new top-level
# directory), a git error, or an unresolvable base all fall through to a build.
# A needless preview costs one build; a missing or stale one is worse.
#
# The production branch always builds. Only preview (non-production) branches
# are ever skipped.

set -uo pipefail

BUILD=1          # exit code Vercel reads as "continue the build"
SKIP=0           # exit code Vercel reads as "skip the build"
PROD_BRANCH="main"

log() { printf '[vercel-ignore] %s\n' "$*" >&2; }

# Is a single changed path outside everything site/build.mjs reads?
#   return 0 -> site-irrelevant (safe to skip if every file is)
#   return 1 -> site-relevant   (forces a build)
# Unknown paths are site-relevant on purpose: a new top-level dir builds until
# this gate is taught it is safe to skip.
path_is_irrelevant() {
  case "$1" in
    # Site inputs that live inside otherwise-skippable trees — guard first.
    docs/architecture/*)       return 1 ;;  # source of the How-it-works page; served raw for llms.txt
    docs/contributing/*)       return 1 ;;  # served raw + indexed by /llms.txt (site/lib/llms.mjs)
    .github/ai-lifestyle.conf) return 1 ;;  # site/lib/media.mjs reads this flag
    # Trees the served site never reads.
    .github/*)    return 0 ;;
    tools/*)      return 0 ;;
    scripts/*)    return 0 ;;
    templates/*)  return 0 ;;
    audits/*)     return 0 ;;
    docs/*)       return 0 ;;
    CLAUDE.md)       return 0 ;;
    CONTRIBUTING.md) return 0 ;;  # nothing under site/ reads it
    .gitignore)      return 0 ;;
    # Everything else is site-relevant: designs/ styles/ people/ lib/ site/
    # PM.md README.md telemetry/ vercel.json — and any path not named above.
    # printer.conf lands here on purpose: lib/printer-conf.scad does
    # `include <printer.conf>`, and site/lib/model.mjs embeds a design's whole
    # include closure, so a design that opts into the print-feedback profile
    # would serve its bytes. It is a rare-changing stub, so building on it costs
    # nothing and closes a latent stale-preview hole.
    *)            return 1 ;;
  esac
}

# Decide from a newline-delimited changed-file list on stdin.
#   return 0 -> SKIP   return 1 -> BUILD
# An empty list means "identical to base" -> SKIP.
decide_from_list() {
  local any=0 f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    any=1
    if ! path_is_irrelevant "$f"; then
      log "site-relevant change: $f -> build"
      return "$BUILD"
    fi
  done
  if [ "$any" -eq 0 ]; then
    log "no changed files vs $PROD_BRANCH -> skip"
    return "$SKIP"
  fi
  log "all changed files are site-irrelevant -> skip"
  return "$SKIP"
}

main() {
  local ref="${VERCEL_GIT_COMMIT_REF:-}"

  # Production (and any unknown ref) always builds.
  if [ -z "$ref" ] || [ "$ref" = "$PROD_BRANCH" ]; then
    log "branch '${ref:-<unknown>}' -> build (production or unknown ref)"
    exit "$BUILD"
  fi

  # Resolve the production branch to diff against. Vercel's checkout can be
  # shallow and may lack the ref, so fetch it if it isn't already present.
  local base=""
  if git rev-parse --verify --quiet "origin/${PROD_BRANCH}^{commit}" >/dev/null 2>&1; then
    base="origin/${PROD_BRANCH}"
  elif git fetch --no-tags --depth=100 origin "$PROD_BRANCH" >/dev/null 2>&1; then
    base="FETCH_HEAD"
  fi
  if [ -z "$base" ]; then
    log "cannot resolve base '$PROD_BRANCH' -> build (fail-safe)"
    exit "$BUILD"
  fi

  local mb
  mb="$(git merge-base "$base" HEAD 2>/dev/null || true)"
  if [ -z "$mb" ]; then
    log "no merge-base with $base -> build (fail-safe)"
    exit "$BUILD"
  fi

  local changed
  if ! changed="$(git diff --name-only "$mb" HEAD 2>/dev/null)"; then
    log "git diff failed -> build (fail-safe)"
    exit "$BUILD"
  fi

  decide_from_list <<<"$changed"
  exit $?
}

# --selftest: exercise the pure classifier with no git or Vercel env, the way
# check.sh proves a gate still fires. A positive case per skip-safe tree and a
# negative control per guarded/relevant path — the half a live run can't show.
selftest() {
  local fails=0 rc
  check() { # <expected 0|1> <label> <changed paths...>
    local expected="$1" label="$2"; shift 2
    decide_from_list <<<"$(printf '%s\n' "$@")" >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne "$expected" ]; then
      printf 'FAIL %-22s expected=%s got=%s\n' "$label" "$expected" "$rc" >&2
      fails=1
    fi
  }

  # SKIP (0): every changed file is site-irrelevant.
  check 0 tooling-only        ".github/workflows/ci.yml" "tools/reeve/src/reeve/cli.py" "scripts/check.sh"
  check 0 docs-nonarch        "docs/metamaterials-4d.md"
  check 0 templates-audits    "templates/design.scad" "audits/pr3/before.png"
  check 0 root-noise          "CLAUDE.md" ".gitignore" "CONTRIBUTING.md"
  check 0 empty-diff          # no paths -> identical to base

  # BUILD (1): at least one site-relevant file, incl. the guarded exceptions.
  check 1 design-scad         "designs/foo/foo.scad"
  check 1 design-readme       "designs/foo/README.md"
  check 1 lib-include-closure "lib/threads-fdm.scad"
  check 1 style               "styles/tactile/style.scad"
  check 1 people              "people/reeve.md"
  check 1 site                "site/build.mjs"
  check 1 docs-architecture   "docs/architecture/ci-platform.md"
  check 1 docs-contributing   "docs/contributing/ci-and-gates.md"
  check 1 ai-lifestyle-conf   ".github/ai-lifestyle.conf"
  check 1 root-pm             "PM.md"
  check 1 vercel-json         "vercel.json"
  check 1 printer-conf        "printer.conf"  # enters the include closure via printer-conf.scad
  check 1 unknown-topdir      "newthing/x.txt"
  check 1 mixed               "scripts/check.sh" "designs/foo/README.md"

  if [ "$fails" -ne 0 ]; then
    echo "vercel-ignore-build selftest: FAIL" >&2
    exit 1
  fi
  echo "vercel-ignore-build selftest: OK"
}

case "${1:-}" in
  --selftest) selftest ;;
  *)          main ;;
esac
