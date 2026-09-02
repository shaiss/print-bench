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

# And this proves the multi-part-deliverable object counter still discriminates:
# two separate part STLs merge to 2 objects, a fused single body to 1, so a
# fused deliverable is detectable as fewer than N (the multi-part-fuse field
# test — plate.sh, ci.plate). The falsifiable half of the plate gate; it needs
# prusa-slicer (the --merge --export-3mf path), so skip with a note when a bare
# environment lacks it — CI installs it (session-start).
if command -v prusa-slicer >/dev/null; then
  echo "-- plate selftest: scripts/plate.sh --selftest"
  if ! ./scripts/plate.sh --selftest; then
    fail=1
  fi
else
  echo "-- plate selftest: skipped (prusa-slicer not on PATH)"
fi

# And this proves the `render` camera opt still works on the installed
# OpenSCAD build (issue #400): --render is value-taking on some builds
# (2021.01, the 2026.08 nightly) and a bare trailing flag makes the parser
# swallow the source path; bool builds reject --render=1 instead. render.sh
# asks the binary which kind it is, and this selftest drives all three opt
# orders through render_previews plus the negative control — so it runs green
# on BOTH the stable and nightly check jobs below, whatever each is running.
echo "-- render selftest: scripts/render.sh --selftest"
if ! ./scripts/render.sh --selftest; then
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

# Adoption-assessor deny-backstop drift check: same reasoning as the chunker's,
# labeler's and scout's, for the adoption-study assessor's own backstop
# (.claude/adoption-assessor-settings.json). It is the WIDEST backstop in the
# family — it must deny every dangerous settings.json allow AND all three sibling
# wrappers (chunk-helper.sh, label-helper.sh, scout-helper.sh; none is the
# assessor's surface) — and must never deny its own assessor-helper.sh wrapper
# (or the scheduled assessor fails closed with no other CI signal). Separate
# script because each routine's wrapper allow/deny roles differ
# (docs/actions-security.md, CR-A; docs/adoption-study-assessor-proposal.md §3).
echo "-- adoption-assessor-perms selftest: scripts/adoption-assessor-perms-check.sh --selftest"
if ! ./scripts/adoption-assessor-perms-check.sh --selftest; then
  fail=1
fi
echo "-- adoption-assessor-perms check: scripts/adoption-assessor-perms-check.sh"
if ! ./scripts/adoption-assessor-perms-check.sh; then
  fail=1
fi

# Scout MCP filing tool: the scout's WRITE surface is the file_design_brief MCP
# tool (.claude/skills/product-scout/scout_mcp.py), which replaced a Bash verb so
# a rich multi-line brief body travels as a JSON argument instead of a shell
# command line the dontAsk matcher rejects. Its --selftest proves the security
# invariants a live run cannot show — the label is hardcoded to design-brief and
# unpassable, the title must carry the 'Design brief:' prefix, and the per-run
# cap fires — the same firing-guard discipline the perms-checks follow.
echo "-- scout MCP selftest: .claude/skills/product-scout/scout_mcp.py --selftest"
if ! python3 .claude/skills/product-scout/scout_mcp.py --selftest; then
  fail=1
fi

# Oracle deny-backstop drift check: same reasoning as the chunker's, labeler's
# and scout's, for the cross-vendor Oracle reviewer's own backstop
# (.claude/oracle-settings.json, issue #333). The Oracle has NO shell wrapper —
# its one write is the MCP posting tool — so unlike the siblings its coverage
# rule has no wrapper exemption: EVERY Bash allow in settings.json must be
# denied, PLUS all three sibling write surfaces (chunk-helper.sh,
# label-helper.sh, scout-helper.sh and the scout MCP server), while never
# denying mcp__oracle__post_oracle_review (or the unattended Oracle fails
# closed with no other CI signal).
echo "-- oracle-perms selftest: scripts/oracle-perms-check.sh --selftest"
if ! ./scripts/oracle-perms-check.sh --selftest; then
  fail=1
fi
echo "-- oracle-perms check: scripts/oracle-perms-check.sh"
if ! ./scripts/oracle-perms-check.sh; then
  fail=1
fi

# Oracle MCP posting tool: the Oracle's ONE write surface is the
# post_oracle_review MCP tool (.claude/skills/oracle-review/oracle_mcp.py) —
# a JSON-argument tool for the same dontAsk-matcher reason as the scout's. Its
# --selftest proves the security invariants a live run cannot show: the target
# PR comes only from the workflow's ORACLE_PR (unredirectable), the marker /
# advisory header / attribution footer are hardcoded onto every post, and the
# one-post-per-run cap fires — the same firing-guard discipline the
# perms-checks follow.
echo "-- oracle MCP selftest: .claude/skills/oracle-review/oracle_mcp.py --selftest"
if ! python3 .claude/skills/oracle-review/oracle_mcp.py --selftest; then
  fail=1
fi

# Adoption-assessor MCP disposition tool: the assessor's WRITE surface is the
# post_adoption_disposition MCP tool (.claude/skills/adoption-assessor/
# assessor_mcp.py), a JSON-argument tool rather than a Bash verb for the same
# reason the scout's is. It validates its TARGET at write time — re-reads the
# issue and refuses unless it is open, still labeled adoption-study, and carries
# no disposition:* label; binds to the run's candidate set; rejects a duplicate;
# caps posts per run. Those write-time guards are what keep a stale or
# prompt-injected run from commenting on a closed or already-ruled study, so
# --selftest proves each one fires offline — the negative-control discipline the
# perms-checks follow, applied to the write tool the deny-backstop cannot cover.
echo "-- adoption-assessor MCP selftest: .claude/skills/adoption-assessor/assessor_mcp.py --selftest"
if ! python3 .claude/skills/adoption-assessor/assessor_mcp.py --selftest; then
  fail=1
fi

# Adoption-assessor vendor-context fetcher (scripts/assessor-context.sh): the
# trusted workflow step that clones each study's named vendor repo into
# .assessor-context/<n>/ so the assessor compares the tool at a code level, not
# just against the vendor's prose. Its --selftest pins the security-critical URL
# parser — only https://github.com/<owner>/<repo> is ever a clone target — with
# negative controls (ssh, non-github host, userinfo spoof, look-alike host,
# reserved owner, bare owner, file://). The clone itself needs network + gh, so
# the selftest exercises the pure parser only; that parser is the guard.
echo "-- assessor-context selftest: scripts/assessor-context.sh --selftest"
if ! ./scripts/assessor-context.sh --selftest; then
  fail=1
fi

# Wright deny-backstop drift check: same reasoning as the chunker's family,
# for BOTH halves of the agent forge (docs/agent-forge.md). One script checks
# two backstops because the halves' allow/deny roles are opposite BY DESIGN:
# the propose half (.claude/wright-settings.json) must deny the sign-off MCP
# server (the proposer can never hold the arming tool) while the sign-off
# half (.claude/reeve-signoff-settings.json) must deny the filing server (the
# judge can never file what it judges) — and each must deny every dangerous
# settings.json allow plus all four sibling wrappers, while never denying the
# shared read wrapper wright-helper.sh or its OWN write tool (or the
# scheduled forge fails closed with no other CI signal).
echo "-- wright-perms selftest: scripts/wright-perms-check.sh --selftest"
if ! ./scripts/wright-perms-check.sh --selftest; then
  fail=1
fi
echo "-- wright-perms check: scripts/wright-perms-check.sh"
if ! ./scripts/wright-perms-check.sh; then
  fail=1
fi

# Wright MCP filing tool: the propose half's WRITE surface is the
# file_agent_brief MCP tool (.claude/skills/wright/wright_mcp.py), a
# JSON-argument tool for the same dontAsk-matcher reason as the scout's. Its
# --selftest proves the invariants a live run cannot show: the label is
# hardcoded to agent-brief and unpassable, the title must carry the 'Agent
# brief:' prefix, and the per-run cap fires.
echo "-- wright MCP selftest: .claude/skills/wright/wright_mcp.py --selftest"
if ! python3 .claude/skills/wright/wright_mcp.py --selftest; then
  fail=1
fi

# Reeve sign-off MCP tool: the judging half's WRITE surface — the ONE
# escalation-shaped write in the routine family, since an approve applies
# `autonomy-ok`. Its --selftest proves every guard fires offline: write-time
# target re-read (open / agent-brief / unruled / in the candidate set), the
# closed verdict-label taxonomy, label-first fail-closed ordering, marker
# dedup, the per-run cap, the WRIGHT_AUTO_ARM advisory demotion, and above
# all the deterministic sensitive-path guard (an approve whose brief touches
# protection machinery downgrades to needs-decision, with a
# clean-brief negative control so the guard can't rot into always-firing).
echo "-- reeve-signoff MCP selftest: .claude/skills/reeve-signoff/signoff_mcp.py --selftest"
if ! python3 .claude/skills/reeve-signoff/signoff_mcp.py --selftest; then
  fail=1
fi

# Growth deny-backstop drift check: same reasoning as the chunker's family,
# for the Twitter/X growth agent's own backstop
# (.claude/growth-twitter-settings.json — docs/growth.md). Lark is
# oracle-shaped (NO shell wrapper; its one write is the MCP posting tool),
# so like the Oracle's check the coverage rule has no wrapper exemption:
# EVERY Bash allow in settings.json must be denied, PLUS every sibling write
# surface AND the growth desk's own queue-filing server (the poster must
# never refill the queue it drains) — while never denying
# mcp__growth_twitter__post_tweet (or the scheduled agent fails closed with
# no other CI signal, its dry-run comments just silently stopping). The
# stakes are the highest in the family: this is the one write surface that
# can eventually reach OUTSIDE the repo.
echo "-- growth-perms selftest: scripts/growth-perms-check.sh --selftest"
if ! ./scripts/growth-perms-check.sh --selftest; then
  fail=1
fi
echo "-- growth-perms check: scripts/growth-perms-check.sh"
if ! ./scripts/growth-perms-check.sh; then
  fail=1
fi

# Reeve-growth permission drift: the MIRROR of growth-perms — the growth
# desk's generative PM-queueing routine (Reeve, /reeve-growth,
# docs/growth.md) OWNS the queue-filing tool (mcp__growth_queue) and must
# DENY the poster (mcp__growth_twitter), the exact inverse of Lark's
# backstop. Oracle-shaped (no wrapper), so every Bash allow must be denied,
# plus each sibling write surface and the poster, while its own queue tool
# must never be denied (or the scheduled routine fails closed, unable even to
# file a draft). --selftest proves the check can pass AND fail.
echo "-- reeve-growth-perms selftest: scripts/reeve-growth-perms-check.sh --selftest"
if ! ./scripts/reeve-growth-perms-check.sh --selftest; then
  fail=1
fi
echo "-- reeve-growth-perms check: scripts/reeve-growth-perms-check.sh"
if ! ./scripts/reeve-growth-perms-check.sh; then
  fail=1
fi

# Spike-converter permission drift: the scheduled spike-to-brief converter
# (#245 child C, issue #440) — the backstop mirror-image of every sibling:
# it DENIES the scout's wrapper (scout-helper.sh carries a file-brief verb;
# #439's rule is that the converter files via the reused MCP tool only)
# while NEVER denying that same tool (mcp__scout__file_design_brief) or its
# own read wrapper (converter-helper.sh) — the siblings all deny mcp__scout,
# this one depends on it. It also pins the REUSE coupling no sibling needs:
# the scout mcp config + server file the workflow's --mcp-config points at
# still exist and still name the server the tool id is keyed on, so a moved
# or renamed scout filing surface cannot silently arm a routine whose only
# write is denied. --selftest proves the check can pass AND fail.
echo "-- spike-converter-perms selftest: scripts/spike-converter-perms-check.sh --selftest"
if ! ./scripts/spike-converter-perms-check.sh --selftest; then
  fail=1
fi
echo "-- spike-converter-perms check: scripts/spike-converter-perms-check.sh"
if ! ./scripts/spike-converter-perms-check.sh; then
  fail=1
fi

# Reeve-greenlight permission drift: the greenlight loop (issue #296 stage 2,
# #442) reads untrusted issue text while holding a provider secret, so it
# carries the labeler containment pattern, not the v1 reporter exemption. Its
# backstop (.claude/reeve-settings.json) must deny every non-wrapper Bash
# allow inherited from .claude/settings.json (claude-code-action loads it
# additively via settingSources=project) plus every sibling routine's write
# surface (chunk/labeler/scout/assessor/wright wrappers and the sibling MCP
# servers) — while never denying its own greenlight-helper.sh, or the
# scheduled run fails closed. --selftest proves the check can pass AND fail
# (including the dropped-cross-deny case coverage alone can never catch).
echo "-- reeve-perms selftest: scripts/reeve-perms-check.sh --selftest"
if ! ./scripts/reeve-perms-check.sh --selftest; then
  fail=1
fi
echo "-- reeve-perms check: scripts/reeve-perms-check.sh"
if ! ./scripts/reeve-perms-check.sh; then
  fail=1
fi

	echo "-- reviewer-perms selftest: scripts/reviewer-perms-check.sh --selftest"
	if ! ./scripts/reviewer-perms-check.sh --selftest; then
	  fail=1
	fi
	echo "-- reviewer-perms check: scripts/reviewer-perms-check.sh"
	if ! ./scripts/reviewer-perms-check.sh; then
	  fail=1
	fi

# Greenlight wrapper selftest (.claude/skills/reeve-greenlight/
# greenlight-helper.sh --selftest, the growth-queue MCP precedent): the
# wrapper is the greenlight loop's ONE shell surface, and its --selftest is
# the only thing proving offline what a live run must never show — a post
# without a valid verdict, off the workflow-selected set, past the
# greenlight_cap conf key, or onto an issue that already carries a greenlight
# is refused and publishes nothing; a forged marker line in --body cannot
# survive (the wrapper writes the marker from --verdict); and a refusal
# consumes no cap. Offline against a recording gh stub — no network, no real
# repository.
echo "-- greenlight-helper selftest: .claude/skills/reeve-greenlight/greenlight-helper.sh --selftest"
if ! .claude/skills/reeve-greenlight/greenlight-helper.sh --selftest; then
  fail=1
fi

# Growth queue MCP filing tool: the PM-side half of the growth desk's
# queuing seam (docs/growth.md) — the /growth-queue skill's ONE write, a
# JSON-argument tool for the same dontAsk-matcher reason as the scout's. Its
# --selftest proves the invariants a live run cannot show: the labels are
# hardcoded to growth-queue + channel:<name> and unpassable (queuing can
# never approve, prioritize, or route), the channel set is closed, the title
# must carry the 'Growth post:' prefix, and the per-run cap fires.
echo "-- growth-queue MCP selftest: .claude/skills/growth-queue/queue_mcp.py --selftest"
if ! python3 .claude/skills/growth-queue/queue_mcp.py --selftest; then
  fail=1
fi

# Growth posting MCP tool: Lark's ONE write and the most-guarded surface in
# the family — the only one that can eventually publish OUTSIDE the repo.
# Its --selftest proves offline what a live run must never show: dry-run is
# the default (live needs the human GROWTH_TWITTER_LIVE key AND all four X
# credentials AND, per policy, the human-applied approved-to-post label),
# the weighted-length rule refuses over-280 copy (URLs = 23), write-time
# target re-read (open / growth-queue / channel:twitter / not parked), the
# one-post-per-item marker guards in both modes, candidate-set binding, the
# per-run cap, and that a live post closes its drained queue item while a
# dry run never does.
echo "-- growth MCP selftest: .claude/skills/growth-twitter/growth_mcp.py --selftest"
if ! python3 .claude/skills/growth-twitter/growth_mcp.py --selftest; then
  fail=1
fi

# Cadence-parity check (issue #276): every scheduled autonomy routine stores
# its cadence TWICE — the `cadence:` key in .github/<routine>.conf and the
# `cron:` literal in .github/workflows/<routine>.yml (Actions can't read a
# file for on.schedule) — and before this check nothing held them together,
# so a one-sided edit shipped a routine firing on a schedule nobody
# reviewed. The check resolves presets (backlog-burn stores `hourly`, the
# workflow carries `17 * * * *`) through backlog-burn's own parser so the
# mapping has one source, and compares. PARITY only, not correctness: it
# does not check a cron against the prose schedule the comments describe
# (see the script header). Selftest first — it is the only thing proving
# the failure direction still fires — then the real files.
echo "-- cadence-sync selftest: scripts/cadence-sync-check.sh --selftest"
if ! ./scripts/cadence-sync-check.sh --selftest; then
  fail=1
fi
echo "-- cadence-sync check: scripts/cadence-sync-check.sh"
if ! ./scripts/cadence-sync-check.sh; then
  fail=1
fi

# ci-ok wiring guard (scripts/ci-ok-guard.sh): every gating job in ci.yml is
# in ci-ok's hand-maintained `needs:` list, or is job-level advisory
# (continue-on-error). Closes the hole ci.yml documents in its own comment — a
# new gating job left out of needs can fail RED while ci-ok stays green.
# Selftest first (the only thing proving the failure direction fires), then the
# real ci.yml.
echo "-- ci-ok-guard selftest: scripts/ci-ok-guard.sh --selftest"
if ! ./scripts/ci-ok-guard.sh --selftest; then
  fail=1
fi
echo "-- ci-ok-guard check: scripts/ci-ok-guard.sh"
if ! ./scripts/ci-ok-guard.sh; then
  fail=1
fi

# reviewer-signoff decision helper (scripts/reviewer-signoff.sh): the pass/block
# logic behind the `reviewer-signoff` required status (auto-review.yml, W2). The
# gate is fail-closed — a design PR without two clean, current sign-offs blocks —
# so the selftest is the only thing that proves it both passes clean AND fails
# closed (missing/malformed/stale/blocking/fuse-unacked markers each block).
echo "-- reviewer-signoff selftest: scripts/reviewer-signoff.sh --selftest"
if ! ./scripts/reviewer-signoff.sh --selftest; then
  fail=1
fi

# vercel-ignore-build selftest (scripts/vercel-ignore-build.sh --selftest): the
# Vercel "Ignored Build Step" gate decides whether a preview deployment is worth
# building from the changed-file list alone. The classifier is a pure function
# of paths, so the selftest is the only thing that proves it still skips a
# tooling/CI/docs-only diff and still builds on any site input (a design, a lib
# in the include closure, an architecture doc, an unknown top-level dir).
echo "-- vercel-ignore-build selftest: scripts/vercel-ignore-build.sh --selftest"
if ! ./scripts/vercel-ignore-build.sh --selftest; then
  fail=1
fi

# lifestyle-shot.sh selftest (issue #418): drives the LIVE parse branch — the
# resp_kind assignment that once reused the 'kind' global, clobbering it so
# product-still embeds got lifestyle alt text and the per-kind seed guard
# stopped firing after the first shot — by running a sandboxed copy of the
# real script against a localhost HTTP stub (no ZAI_KEY, no network beyond
# 127.0.0.1), asserting the produced alt text, the second-shot seed-guard
# refusal, and that malformed responses fail loudly. A sabotaged copy with
# the rename reverted is the negative control proving the selftest still
# fails when the clobber returns.
echo "-- lifestyle-shot selftest: scripts/lifestyle-shot.sh --selftest"
if ! ./scripts/lifestyle-shot.sh --selftest; then
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

# catalog.sh is the design-category signal (issue #374): its --selftest pins the
# closed-vocabulary refusal and the NUGGS cross-check with negative controls
# (the only thing proving a typo'd or free-text category still fails), then the
# real `check` validates every design's category and the grouping the README
# gallery + site index consume. Ahead of docs-check for the lineage reason: it
# calls the same resolver, and a bad category should read as a category error,
# not as "README gallery is stale".
echo "-- catalog selftest: scripts/catalog.sh --selftest"
if ! ./scripts/catalog.sh --selftest; then
  fail=1
fi
echo "-- catalog check: scripts/catalog.sh check"
if ! ./scripts/catalog.sh check; then
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

# routine-lock-cleanup.sh withdraws the 🚢 SHIP-LOCK a dead scheduled
# design-run/backlog-burn firing leaves behind (issue #312) — the orphaned
# claim otherwise excludes the issue from every later selection, so ghost
# locks read as green no-ops. Its --selftest pins the selector-compatibility
# contract against select.py (first-non-blank-line classification, the
# closing-keyword #9-vs-#95 boundary, the branch near-miss, the escalation
# threshold, the withdrawal line the selector must read as released), each
# with a negative control, fully offline — nothing else would notice if the
# withdrawal wording drifted off what the selector reads. Fast (no network),
# so it runs here with the other suites.
echo "-- routine-lock-cleanup selftest: scripts/routine-lock-cleanup.sh --selftest"
if ! ./scripts/routine-lock-cleanup.sh --selftest; then
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
