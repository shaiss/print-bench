#!/usr/bin/env bash
# docs-standards-check.sh — the standards gate for the architecture docs and the
# "How it works" product-site page (and its diagrams).
#
# Same discipline as docs-check.sh: every assertion here is a MECHANICAL fact —
# a file exists, a symbol is wired, a link is present — verified with test/grep.
# Nothing judges prose. What it protects is that the doc set and the page stay
# whole and wired together: the three architecture docs exist and cross-link,
# the page is exported and reachable in the nav, its four diagrams are authored
# inline and used, and the page still traces back to the docs it presents.
#
# Deliberately NOT run by check.sh and NOT dependent on OpenSCAD: a docs change
# must not spin up the render toolchain. It runs as its own light CI job that
# ci-classify.sh selects (the `docs_standards` output) only when the docs, the
# page, or this script itself change — smart CI, not an unconditional gate.
#
#   ./scripts/docs-standards-check.sh            # gate the repo
#   ./scripts/docs-standards-check.sh --selftest # prove the gate still fires
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"

# The architecture docs the page is built from.
ARCH_DOCS=(
  docs/architecture/README.md
  docs/architecture/ci-platform.md
  docs/architecture/design-workflow.md
)
# The four inline SVG diagrams the page must embed.
DIAGRAMS=(journeyMap infographicNonTechnical infographicTechnical regenLoop)

# run_checks <root> — every check is relative to <root>, so the selftest can
# point it at a mutated fixture tree and watch it fail.
run_checks() {
  local root="$1" fail=0
  err() { echo "FAIL  docs-standards: $1"; fail=1; }
  have() { [ -f "$root/$1" ] || err "missing $1"; }
  # contains <relpath> <fixed-string> <message>
  contains() {
    local f="$root/$1"
    if [ ! -f "$f" ]; then err "missing $1"; return; fi
    grep -qF -- "$2" "$f" || err "$3"
  }

  # A. The architecture doc set: present, titled, and cross-linked from the index.
  local d
  for d in "${ARCH_DOCS[@]}"; do
    have "$d"
    [ -f "$root/$d" ] && { head -1 "$root/$d" | grep -q '^# ' || err "$d has no H1 title"; }
  done
  contains docs/architecture/README.md "ci-platform.md" \
    "docs/architecture/README.md must link ci-platform.md"
  contains docs/architecture/README.md "design-workflow.md" \
    "docs/architecture/README.md must link design-workflow.md"

  # B. The How-it-works page: exported, emitted, in the nav, drawn from the docs.
  contains site/lib/templates.mjs "export function howItWorksPage(" \
    "site/lib/templates.mjs must export howItWorksPage"
  contains site/lib/templates.mjs "/how-it-works/" \
    "the shared site nav must link /how-it-works/"
  contains site/lib/templates.mjs "docs/architecture/" \
    "the page must link the architecture docs it is drawn from"
  contains site/build.mjs "how-it-works/index.html" \
    "site/build.mjs must emit the /how-it-works/ page"
  contains site/README.md "/how-it-works/" \
    "site/README.md must list the /how-it-works/ route it publishes"
  have site/test/how-it-works.test.mjs

  # C. The diagrams: authored inline in diagrams.mjs and used by the page.
  have site/lib/diagrams.mjs
  local sym
  for sym in "${DIAGRAMS[@]}"; do
    contains site/lib/diagrams.mjs "export function $sym(" \
      "site/lib/diagrams.mjs must export the $sym diagram"
    contains site/lib/templates.mjs "$sym" \
      "site/lib/templates.mjs must embed the $sym diagram"
  done
  have site/test/diagrams.test.mjs

  return "$fail"
}

# The files run_checks reads — copied verbatim into the selftest fixture, where
# the real (valid) arrangement must pass and each mutation must fail.
FIXTURE_FILES=(
  "${ARCH_DOCS[@]}"
  site/lib/templates.mjs
  site/lib/diagrams.mjs
  site/build.mjs
  site/README.md
  site/test/how-it-works.test.mjs
  site/test/diagrams.test.mjs
)

selftest() {
  local fails=0 tmp f
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand tmp now, not at trap time
  trap "rm -rf '$tmp'" RETURN

  fresh() { # re-lay the valid fixture
    rm -rf "${tmp:?}/docs" "${tmp:?}/site"
    for f in "${FIXTURE_FILES[@]}"; do
      mkdir -p "$tmp/$(dirname "$f")"
      cp "$REPO/$f" "$tmp/$f"
    done
  }
  expect() { # label expected-rc
    local label="$1" want="$2" got=0
    run_checks "$tmp" >/dev/null 2>&1 || got=$?
    if [ "$got" -eq "$want" ]; then
      echo "ok   [$label]"
    else
      echo "FAIL [$label]: expected exit $want, got $got" >&2
      fails=$((fails + 1))
    fi
  }

  # Positive control: the real files, as committed, pass.
  fresh
  expect "positive: real files pass" 0

  # Negative controls: each must make the gate fire (exit 1).
  fresh; rm -f "$tmp/docs/architecture/ci-platform.md"
  expect "missing an architecture doc fails" 1

  fresh; rm -f "$tmp/site/lib/diagrams.mjs"
  expect "missing the diagrams module fails" 1

  fresh; sed -i 's/export function howItWorksPage/function howItWorksPage_DISABLED/' "$tmp/site/lib/templates.mjs"
  expect "howItWorksPage not exported fails" 1

  fresh; sed -i 's#/how-it-works/#/gone/#g' "$tmp/site/lib/templates.mjs"
  expect "page dropped from the nav fails" 1

  fresh; sed -i 's/export function journeyMap/export function journeyMap_GONE/' "$tmp/site/lib/diagrams.mjs"
  expect "a diagram removed fails" 1

  fresh; : > "$tmp/docs/architecture/README.md"
  expect "index without cross-links fails" 1

  # One control per remaining assertion, so none can be silently weakened.
  fresh; sed -i 's#how-it-works/index.html#gone.html#' "$tmp/site/build.mjs"
  expect "page not emitted by build.mjs fails" 1

  fresh; sed -i 's#/how-it-works/#/gone/#g' "$tmp/site/README.md"
  expect "route missing from site/README.md fails" 1

  fresh; sed -i 's#docs/architecture/#docs/gone/#g' "$tmp/site/lib/templates.mjs"
  expect "page no longer links the architecture docs fails" 1

  fresh; rm -f "$tmp/site/test/how-it-works.test.mjs"
  expect "missing the page test fails" 1

  fresh; rm -f "$tmp/site/test/diagrams.test.mjs"
  expect "missing the diagrams test fails" 1

  fresh; sed -i 's/regenLoop//g' "$tmp/site/lib/templates.mjs"
  expect "a diagram not embedded by the page fails" 1

  if [ "$fails" -ne 0 ]; then
    echo "docs-standards selftest: $fails case(s) failed" >&2
    return 1
  fi
  echo "docs-standards selftest: all cases passed"
}

main() {
  case "${1:-}" in
    --selftest) selftest ;;
    "")
      if run_checks "$REPO"; then
        echo "ok    docs-standards: architecture docs and the How-it-works page are whole and wired"
      else
        echo "docs-standards: fix the items above — the docs/page standards are not met" >&2
        exit 1
      fi
      ;;
    *) echo "usage: $0 [--selftest]" >&2; exit 2 ;;
  esac
}

main "$@"
