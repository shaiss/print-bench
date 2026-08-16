#!/usr/bin/env bash
# Fast validation of every .scad file in the repo (no STL output).
#   1. Syntax/eval check of all designs, lib, template and style files
#      (echo export — seconds). Fails on ERROR and on a failing assert as
#      well as on a wrong-geometry WARNING: under --export-format echo
#      OpenSCAD reports both in the export file and still exits 0.
#   2. Full CGAL render of the lib demo to catch geometry regressions
#   3. Guard check (scripts/guard-check.sh): every lib guard still fires
#   4. Lineage check (scripts/lineage.sh check): every derives.conf must
#      describe the graph its entry .scad actually includes
#   5. Docs-drift check (scripts/docs-check.sh): docs must match the tree
#   6. readme-gate selftest (scripts/readme-gate.sh --selftest): the
#      lifestyle disclosure guards still refuse an undisclosed AI shot or clip
#   7. shot-spec selftest (scripts/shot-spec.sh --selftest): the shot-manifest
#      freeze guard and field validators still refuse a bad line
# Run before committing. For full STL+PNG output use scripts/render.sh.
set -euo pipefail

cd "$(dirname "$0")/.."
# lib/ resolves `use <printability.scad>`; the repo root resolves
# `include <styles/<name>/style.scad>` (see scripts/style-lift.sh).
export OPENSCADPATH="$PWD/lib:$PWD"

# OPENSCAD_BIN selects the binary (e.g. openscad-nightly); OPENSCAD_ARGS
# passes extra flags (e.g. --backend=manifold — nightly-only, 2021.01 has
# no --backend). Both default to the stable invocation.
OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
read -ra OSC_ARGS <<<"${OPENSCAD_ARGS:-}"

fail=0

# WARNINGs that mean the file silently produced the WRONG SHAPE rather than
# something cosmetic: OpenSCAD skips the call, exits 0, and hands you a
# watertight, sliceable, gate-passing STL with the feature missing. These fail
# the check; every other WARNING stays advisory.
#
# Note the echo pass below does not instantiate geometry, so it never sees an
# unresolved `use <lib.scad>` — that is what the link check further down is
# for. This pattern covers the top-level cases the echo pass does reach.
FATAL_WARN="Ignoring unknown module|Ignoring unknown function|Can't open include file"

# A failing assert is not a warning and it is not an exit code either. Under
# `--export-format echo` OpenSCAD writes
#   ERROR: Assertion '(bore_d >= min_bore_mm)' failed ...
# into the export file and **exits 0**, so before this pattern existed the
# success branch below printed `ok` for a design whose welfare asserts were
# firing. gate.sh caught it on the real render, but the fast pre-commit check
# — the one a developer actually runs — reported the design valid. Designs in
# this repo use asserts as the enforcement mechanism for non-negotiables
# (see designs/nuggs/PM.md), so an unenforced assert is the whole safety net.
FATAL_ERR="ERROR|Assertion.*failed"

# Under `--export-format echo` OpenSCAD writes its diagnostics into the export
# file, not to stderr — so the old `-o /dev/null` threw every WARNING away and
# the FATAL_WARN test below could never fire. Export to a real file and read
# the warnings back out of it (plus whatever stderr does carry).
mkdir -p build
ECHO_OUT="build/.check-echo.txt"
trap 'rm -f "$ECHO_OUT"' EXIT

check() {
  local f="$1" rc=0 err
  : >"$ECHO_OUT"
  err=$(xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    -o "$ECHO_OUT" --export-format echo "$f" 2>&1) || rc=$?
  out=$(printf '%s\n%s' "$err" "$(cat "$ECHO_OUT")")
  if (( rc == 0 )); then
    # Exit 0 does not mean the file evaluated cleanly — check for ERROR first.
    if grep -qE "$FATAL_ERR" <<<"$out"; then
      echo "FAIL  $f  (ERROR/failed assert — OpenSCAD still exited 0)"
      grep -E "$FATAL_ERR" <<<"$out" | sed 's/^/      /'
      fail=1
    # Surface WARNINGs even on success
    elif grep -q "WARNING" <<<"$out"; then
      if grep -qE "$FATAL_WARN" <<<"$out"; then
        echo "FAIL  $f  (unresolved module/include — wrong geometry, not a nit)"
        fail=1
      else
        echo "WARN  $f"
      fi
      grep "WARNING" <<<"$out" | sed 's/^/      /'
    else
      echo "ok    $f"
    fi
  else
    echo "FAIL  $f"
    sed 's/^/      /' <<<"$out" | tail -20
    fail=1
  fi
}

# An archived design (designs/<n>/ARCHIVED) is frozen at v0.1 and retired from
# full-catalog CI. The syntax/link pass skips it for the same reason gate.sh,
# regen and geo-diff do: a shared-code change (a lib/ or scripts/ edit reaches
# this pass over the whole tree) must not be held hostage by a design nobody is
# maintaining. Only checks a designs/<n>/<file> path; lib/, templates/ and
# styles/ files are never archived and always fall through to be checked.
scad_is_archived() {
  case "$1" in
    designs/*/*) local d=${1#designs/}; d=${d%%/*}; [[ -f "designs/$d/ARCHIVED" ]] ;;
    *) return 1 ;;
  esac
}

shopt -s nullglob
for f in designs/*/*.scad lib/*.scad templates/*.scad styles/*/*.scad; do
  scad_is_archived "$f" && continue
  check "$f"
done

# Library-link check. OpenSCAD treats an unresolvable `use <x.scad>` as a
# non-event: no error, no warning during the echo pass, exit 0 — and at render
# time only "Ignoring unknown module", after which you get a watertight,
# sliceable STL with the feature simply absent. Rendering the capsule without
# OPENSCADPATH gives you a threadless neck that passes every downstream gate.
# So resolve the links statically instead of hoping a render complains.
echo "-- library-link check"
# Search path mirrors what the scripts export: lib/ for shared modules, the
# repo root for `include <styles/<name>/style.scad>`. A style's swatch is a
# .scad like any other and gets link-checked too — a swatch that silently
# loses its tokens would render an unstyled shape and still pass the gate.
lib_search=("$PWD/lib" "$PWD" /usr/share/openscad/libraries)
for f in designs/*/*.scad lib/*.scad templates/*.scad styles/*/*.scad; do
  scad_is_archived "$f" && continue
  while read -r ref; do
    [[ -f "$(dirname "$f")/$ref" ]] && continue     # sibling file
    found=0
    for d in "${lib_search[@]}"; do
      [[ -f "$d/$ref" ]] && { found=1; break; }
    done
    (( found )) || { echo "FAIL  $f: use/include <$ref> resolves nowhere"; fail=1; }
  done < <(grep -oE '^[[:space:]]*(use|include)[[:space:]]*<[^>]+>' "$f" \
             | sed -E 's/.*<([^>]+)>.*/\1/')
done
(( fail )) || echo "ok    every use/include resolves"

# Every lib/*-demo.scad is a full CGAL render, not just an echo check: that is
# what catches a geometry regression in a shared module before a design does.
# Globbed rather than named so a new library's demo is covered the day it
# lands (the echo pass above already covers every lib/*.scad for syntax).
for demo in lib/*-demo.scad; do
  [[ -f "$demo" ]] || continue
  echo "-- geometry check: ${demo}"
  if xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
      -o /dev/null --export-format binstl "$demo" 2>&1 \
      | grep -E "ERROR|WARNING"; then
    echo "FAIL  ${demo} rendered with errors/warnings above"
    fail=1
  else
    echo "ok    ${demo} renders clean"
  fi
done

# The demos above prove the libraries still BUILD. This proves their guards
# still REFUSE — the one thing a demo cannot cover, since a firing assert
# would abort the render it lives in.
echo "-- guard check: scripts/guard-check.sh"
if ! ./scripts/guard-check.sh; then
  fail=1
fi

# And this proves their fits still FIT. The mirror of the guard check: a demo
# renders a mating pair side by side and looks right at any clearance, because
# nothing in the render measures whether the two parts actually go together.
# Issue #37 is the cautionary tale — the demo "verified" its flank clearance by
# echoing the identity that defines the constant, and printed the promised
# number for as long as the geometry delivered 6.9% less.
echo "-- mate check: scripts/mate-check.sh"
if ! ./scripts/mate-check.sh; then
  fail=1
fi

# And this proves the printer.conf mechanism still resolves the default when
# nothing is measured and the profile's value when one is — reaching the
# exported geometry, not just an echo. Same family as the two checks above: a
# thing a demo render cannot measure about itself (lib/printer-conf.scad, #101).
echo "-- printer-conf check: scripts/printer-conf-check.sh"
if ! ./scripts/printer-conf-check.sh; then
  fail=1
fi

# And this proves the vendored NopSCADlib tree still resolves through
# OPENSCADPATH and builds a real vitamin. No committed file includes it (no
# design is wired — stage 4 of #98 — and core first-party tooling is forbidden
# from including it by the GPL boundary), so nothing else in this check would
# notice if lib/NopSCADlib/ went missing: an unresolved `include` only WARNs and
# exits 0, the silent wrong-geometry mode CLAUDE.md documents. This is the one
# thing that closes it for a vendored tree nothing exercises yet (issue #155).
echo "-- nopscadlib resolve check: scripts/nopscadlib-check.sh"
if ! ./scripts/nopscadlib-check.sh; then
  fail=1
fi

# And this proves the copyleft/GPL boundary decided in issue #160 still holds:
# no shared first-party lib/*.scad `include`s a copyleft-vendored library (which
# would make the shared unit a combined work and spread GPL to every design
# using it), and no core/site code bundles the vendored copyleft source tree.
# Same silent-failure family as the nopscadlib check above — an `include
# <NopSCADlib/...>` in a shared lib resolves and renders green while quietly
# pulling GPL into core — so the boundary is a check, not a remembered rule
# (docs/licensing.md, LICENSE). The --selftest proves both rules still fire on
# a planted violation; no committed file trips them, so it is the only thing
# exercising the positive path.
echo "-- license-boundary selftest: scripts/license-boundary-check.sh --selftest"
if ! ./scripts/license-boundary-check.sh --selftest; then
  fail=1
fi
echo "-- license-boundary check: scripts/license-boundary-check.sh"
if ! ./scripts/license-boundary-check.sh; then
  fail=1
fi

# And this proves the chunker's deny backstop still neutralizes every dangerous
# tool allow it would otherwise inherit from .claude/settings.json (which
# claude-code-action loads via settingSources=project). Same family again: the
# thing being protected is the ABSENCE of a capability, so a demo cannot cover
# it and a new settings.json allow would silently re-arm the chunker without a
# check that fails on the drift (docs/actions-security.md, CR-A).
echo "-- chunker-perms selftest: scripts/chunker-perms-check.sh --selftest"
if ! ./scripts/chunker-perms-check.sh --selftest; then
  fail=1
fi
echo "-- chunker-perms check: scripts/chunker-perms-check.sh"
if ! ./scripts/chunker-perms-check.sh; then
  fail=1
fi

# Labeler deny-backstop drift check: same reasoning as the chunker's, for the
# labeler's own backstop (.claude/labeler-settings.json). It must deny every
# dangerous settings.json allow — INCLUDING the chunker's chunk-helper.sh wrapper,
# which the chunker's backstop deliberately leaves usable — and must never deny
# the label-helper.sh wrapper (or the scheduled labeler fails closed with no other
# CI signal). Separate script because the two wrappers' allow/deny roles are
# opposite (docs/actions-security.md, CR-A).
echo "-- labeler-perms selftest: scripts/labeler-perms-check.sh --selftest"
if ! ./scripts/labeler-perms-check.sh --selftest; then
  fail=1
fi
echo "-- labeler-perms check: scripts/labeler-perms-check.sh"
if ! ./scripts/labeler-perms-check.sh; then
  fail=1
fi

# Scout deny-backstop drift check: same reasoning as the chunker's and labeler's,
# for the product scout's own backstop (.claude/scout-settings.json). It must deny
# every dangerous settings.json allow — INCLUDING BOTH the chunker's
# chunk-helper.sh AND the labeler's label-helper.sh (neither is the scout's
# surface) — and must never deny the scout-helper.sh wrapper (or the scheduled
# scout fails closed with no other CI signal). Separate script because each
# routine's wrapper allow/deny roles differ (docs/actions-security.md, CR-A).
echo "-- scout-perms selftest: scripts/scout-perms-check.sh --selftest"
if ! ./scripts/scout-perms-check.sh --selftest; then
  fail=1
fi
echo "-- scout-perms check: scripts/scout-perms-check.sh"
if ! ./scripts/scout-perms-check.sh; then
  fail=1
fi

# Lineage check: derives.conf parses, its parents exist, the declared parent
# order still matches the entry .scad's include order, and every diamond is
# explicitly asserted. All static, all milliseconds, so it runs unconditionally
# rather than only when a derives.conf exists — a tree with no derivatives
# answers in one line, and the day someone adds the first one the check is
# already wired in rather than waiting to be remembered.
#
# Ahead of docs-check because docs-check regenerates the gallery, and the
# gallery is now ordered by the same resolver: a broken derives.conf changes
# the nesting, so without this step first the only thing the run says is
# "README gallery is stale" — which points at the wrong file, and at a fix
# (rerun gallery.sh) that would bake the broken lineage into the README.
echo "-- lineage check: scripts/lineage.sh check"
if ! ./scripts/lineage.sh check; then
  fail=1
fi

echo "-- docs-drift check: scripts/docs-check.sh"
if ! ./scripts/docs-check.sh; then
  fail=1
fi

# readme-gate carries a negative-test suite for its lifestyle disclosure
# guards (requirement 9: AI stills and AI motion clips). No lifestyle-*.png or
# lifestyle-*.gif exists in the tree yet, so those guards are dormant on the
# real designs — the selftest is the only thing that proves they still fire.
# Fast (no render), so it runs here alongside the other negative-test suites
# even though the product-page gate itself is a CI job.
echo "-- readme-gate selftest: scripts/readme-gate.sh --selftest"
if ! ./scripts/readme-gate.sh --selftest; then
  fail=1
fi

# shot-spec.sh authors the product-shot manifests and validates them; its
# --selftest proves the freeze guard and every field validator still refuse a
# bad line. Same rationale as the suites above — a weakened validator would
# leave every other check green — and it is fast (no render), so it runs here.
echo "-- shot-spec selftest: scripts/shot-spec.sh --selftest"
if ! ./scripts/shot-spec.sh --selftest; then
  fail=1
fi

# field-test.sh is the tested core of the "Log a print result" Action
# (issue #101): its --selftest proves the FIELD-TEST entry formatting, the
# section-creation, and the design-name/required-field refusals still hold.
# Fast (no render), so it runs here with the other negative-test suites.
echo "-- field-test selftest: scripts/field-test.sh --selftest"
if ! ./scripts/field-test.sh --selftest; then
  fail=1
fi

# telemetry.sh is the capture/report entry for the repo's self-measurement
# (issue #93): its --selftest proves the shell glue — the budgets sourced
# from preview-budget.sh reach the record, capture refuses a missing gate
# log, report refuses a corrupt one. The parsing itself has its own pytest
# suite in tools/telemetry. Fast (no render), so it runs here.
echo "-- telemetry selftest: scripts/telemetry.sh --selftest"
if ! ./scripts/telemetry.sh --selftest; then
  fail=1
fi

# ci-classify.sh is the extracted CI classifier — the one implementation
# ci.yml's `changes` job and /preflight both run, so the local mirror can't
# drift from the workflow. Its --selftest pins the classification with negative
# controls (docs-only gates nothing, geo-infra gates ALL, a non-existent design
# entry is dropped, an archived design pulled in only by a shared style is not
# gated), because nothing else here would notice if a case silently stopped
# classifying. Fast (no render), so it runs here with the other suites.
echo "-- ci-classify selftest: scripts/ci-classify.sh --selftest"
if ! ./scripts/ci-classify.sh --selftest; then
  fail=1
fi

# release-bundle.sh is the build half of the versioned-download UX (issue
# #102): its --selftest proves the shell glue — the manifest names every part,
# each recorded SHA-256 recomputes over the bundled STL, the README's print
# settings reach the manifest, the zip is produced, and an archived design is
# skipped. No release bundle exists in the tree, so the selftest is the only
# thing that proves the builder still works. It renders nothing (fixture STLs
# are pre-seeded), so it is fast and runs here with the other suites.
echo "-- release-bundle selftest: scripts/release-bundle.sh --selftest"
if ! ./scripts/release-bundle.sh --selftest; then
  fail=1
fi

# gh-project.sh emits the idempotent `gh` recipe that provisions the autonomy
# roadmap board (issue #148). Its --selftest proves the emitted recipe is valid,
# idempotent bash and that the board spec (title, owner, Stage options, Story
# points) reaches it — the board itself lives in GitHub, so this is the only
# thing that proves the provisioning recipe still works. Renders/creates nothing
# (pure string emit), so it is fast and runs here with the other suites.
echo "-- gh-project selftest: scripts/gh-project.sh --selftest"
if ! ./scripts/gh-project.sh --selftest; then
  fail=1
fi

# assembly.sh is the generator half of the assembly-instructions feature (#98,
# stage 2 — issue #156). Its --selftest proves the manifest parser captures
# every declared part/vitamin/step in the right order, comments are stripped,
# the title defaults to the design name when absent, and a design with no
# assembly.conf errors cleanly — all without a render, so it is fast and runs
# here with the other suites. No design ships an assembly.conf yet (stage 4),
# so this is the only thing that exercises the parser.
echo "-- assembly selftest: scripts/assembly.sh --selftest"
if ! ./scripts/assembly.sh --selftest; then
  fail=1
fi

exit "$fail"
