#!/usr/bin/env bash
# License-boundary check — enforce print-bench's copyleft/GPL core stance,
# the standing policy decided in issue #160 (full statement: docs/licensing.md,
# LICENSE vendored-code notice, and the CLAUDE.md library list). Run by
# scripts/check.sh (and therefore by /preflight and CI's scad-check jobs).
#
# THE POLICY THIS ENFORCES (issue #160, "quarantine copyleft"):
# The first-party tree is CC-BY-SA-4.0. Vendored BOSL2 is BSD-2-Clause
# (permissive). Vendored NopSCADlib is GPL-3.0 (copyleft, reaches combined
# works). GPL/copyleft may enter the DESIGN layer — a design opts in, discloses
# on its product page, and the lineage system keeps it isolated (issue #155) —
# but it must NOT reach shared first-party CORE, because a shared unit that
# combines with GPL would drag the obligation onto every design that uses it,
# the opposite of design-layer isolation.
#
# WHY A CHECK AND NOT JUST THE DOCS (the silent-failure this closes):
# "core must not combine with GPL" was, until #160, a sentence a human had to
# remember. Nothing failed if a shared lib/*.scad grew an `include
# <NopSCADlib/...>`: OpenSCAD resolves it happily, the mesh renders, every gate
# stays green — and GPL has quietly reached core. Same family as
# nopscadlib-check.sh and printer-conf-check.sh: a mechanical fact about the
# tree that no render measures about itself, written as a check so a regression
# fails loudly instead of being discovered case-by-case.
#
# THE TWO RULES, and why each is scoped the way it is:
#
#   Rule A — shared first-party OpenSCAD code may not `use`/`include` a
#   copyleft-vendored library. Scanned over lib/*.scad (top-level first-party;
#   the single-level glob excludes the vendored lib/BOSL2 and lib/NopSCADlib
#   subtrees) and any *.scad committed under scripts/ or site/. This is THE
#   core rule (issue #160, sub-question 1): an `include`/`use` in a shared .scad
#   is a real combination that ships. designs/ is deliberately NOT scanned —
#   a design MAY opt in (design-layer GPL, #155), so flagging it would be wrong.
#
#   Rule B — core/site code may not bundle the vendored copyleft SOURCE tree.
#   Scanned over committed scripts/ and site/ files for a reference to the
#   vendored source path (lib/<root>, e.g. lib/NopSCADlib), skipping comment
#   lines. This catches a site build that vendors NopSCADlib into the served
#   bytes, or a script that copies the source into a distributed bundle — the
#   "bundling vendored GPL source into distributed first-party code" the #160
#   tooling-line answer names as the forbidden act.
#
# WHAT IS DELIBERATELY NOT FLAGGED (and must not be — the #160 tooling line):
#   - INVOKING GPL tools the repo does not ship (openscad, prusa-slicer,
#     Blender via `import bpy`) — conveying no GPL, so it is fine. This check
#     never looks at tool invocation.
#   - A GENERATOR that EMITS a per-design `include <NopSCADlib/...>` STRING to
#     build a design that has opted in (scripts/assembly.sh does exactly this,
#     issue #156). It is realizing a design's opt-in, scoped to that design —
#     not making core a combined work. Rule A scans only real .scad files, and
#     Rule B is path-based (lib/<root>), so an emitted `<NopSCADlib/...>` string
#     — which carries no `lib/` prefix — trips neither. This is why assembly.sh
#     stays compliant while a lib/*.scad `include` does not.
#   - MCAD (system-installed, LGPL, not vendored in lib/) — out of scope here;
#     it is a tool the repo does not ship, like openscad. See docs/licensing.md.
#
# EXTENDING IT: vendoring another copyleft library means adding its include-root
# to COPYLEFT_ROOTS below AND updating LICENSE + docs/licensing.md in the same
# PR. BOSL2 is NOT listed — it is permissive (BSD-2-Clause), which core may
# combine with freely.
#
# Usage:
#   scripts/license-boundary-check.sh            # check the real tree
#   scripts/license-boundary-check.sh --selftest # prove the check can pass AND fail
set -euo pipefail

cd "$(dirname "$0")/.."

# Include-roots of copyleft-vendored libraries (lib/<root>/). A library is
# listed here iff it is vendored under lib/ AND its license is copyleft
# (GPL/AGPL/…). Permissive vendored libraries (BOSL2, BSD-2-Clause) are NOT
# listed — core may combine with them.
COPYLEFT_ROOTS=(NopSCADlib)

# Files exempt from Rule B because their job is to NAME the boundary, not cross
# it, matched by exact path:
#   - this check, which spells out the roots and source paths it scans for;
#   - nopscadlib-check.sh, whose diagnostics quote "lib/NopSCADlib/ missing …"
#     to report a broken vendor — it exists to prove the tree resolves, and
#     writes only a throwaway build/ fixture, never a distributed bundle.
# assembly.sh is intentionally NOT here: it references the include *name*
# (<NopSCADlib/...>) as generated string output, never the vendored source
# *path* (lib/NopSCADlib), so the path-based Rule B does not reach it and no
# exemption is needed. Keeping the list minimal keeps the gate honest.
ALLOW_BUNDLE=(
  scripts/license-boundary-check.sh
  scripts/nopscadlib-check.sh
)

# Pipe-joined alternation of the roots, e.g. "NopSCADlib" or "NopSCADlib|Foo".
roots_alt() { local IFS='|'; printf '%s' "${COPYLEFT_ROOTS[*]}"; }

# Membership test for the Rule B allowlist. A plain loop, not a `declare -A`
# associative array: the repo holds every locally-run script to the stock-macOS
# Bash 3.2 floor (scripts/check.sh runs this one — see scripts/ci-classify.sh),
# and 3.2 has no associative arrays.
_in_allow_bundle() {
  local x="$1" a
  for a in "${ALLOW_BUNDLE[@]}"; do
    [[ "$x" == "$a" ]] && return 0
  done
  return 1
}

# Rule A: a first-party .scad that `use`/`include`s a copyleft root at statement
# position. Prints every violation; returns 1 if any, 0 if clean.
scan_scad() {
  local alt f n line hits=0
  alt="$(roots_alt)"
  for f in "$@"; do
    [[ -f "$f" ]] || continue
    while IFS=: read -r n line; do
      echo "FAIL  license-boundary: ${f}:${n} — shared first-party OpenSCAD code combines with a copyleft library"
      echo "        ${line#"${line%%[![:space:]]*}"}"
      echo "      → a shared .scad that includes GPL makes every design using it a combined work; move the GPL use into an opt-in design (docs/licensing.md)."
      hits=1
    done < <(grep -nE "^[[:space:]]*(use|include)[[:space:]]*<[[:space:]]*(${alt})/" "$f" || true)
  done
  return "$hits"
}

# Rule B: a core/site source file that references the vendored copyleft SOURCE
# path (lib/<root>) outside a comment. Prints every violation; returns 1 if any.
scan_core_source() {
  local alt f n line stripped hits=0
  alt="$(roots_alt)"
  for f in "$@"; do
    [[ -f "$f" ]] || continue
    while IFS=: read -r n line; do
      # Skip line comments (shell/python `#`, js `//`) — prose may name the
      # vendored path when documenting the boundary; only code references bundle.
      stripped="${line#"${line%%[![:space:]]*}"}"
      case "$stripped" in
        '#'* | '//'*) continue ;;
      esac
      echo "FAIL  license-boundary: ${f}:${n} — core/site code bundles the vendored copyleft source tree"
      echo "        ${stripped}"
      echo "      → do not copy or ship lib/${COPYLEFT_ROOTS[0]}/ from core/site; it stays vendored aggregation only (docs/licensing.md)."
      hits=1
      # Leading boundary [^A-Za-z0-9_-] deliberately ALLOWS `/` and `.` so a
      # path-prefixed reference (./lib/<root>, ../lib/<root>, sub/lib/<root>) is
      # still caught; excluding them let those slip past. It still rejects a
      # longer dir name (zlib/<root>). Trailing group anchors on `/`, a
      # non-word char, or end-of-line (the bare `$` — bash turns "\$" into the
      # anchor `$`, verified against an EOL fixture in --selftest).
    done < <(grep -nE "(^|[^A-Za-z0-9_-])lib/(${alt})(/|[^A-Za-z0-9_-]|\$)" "$f" || true)
  done
  return "$hits"
}

selftest() {
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN
  local ok=1

  # --- Rule A -------------------------------------------------------------
  # POSITIVE: a shared lib that includes a copyleft root must be caught.
  cat > "$tmp/bad-lib.scad" <<'EOF'
// a shared first-party module
include <NopSCADlib/core.scad>
module widget() { screw(M3_cap_screw, 10); }
EOF
  if scan_scad "$tmp/bad-lib.scad" >/dev/null 2>&1; then
    echo "FAIL  selftest: a copyleft include in a shared lib was NOT caught"; ok=0
  else
    echo "ok    selftest: a copyleft include in a shared lib fails Rule A"
  fi

  # NEGATIVE: a permissive (BOSL2) include, and a plain module, must pass.
  cat > "$tmp/good-lib.scad" <<'EOF'
include <BOSL2/std.scad>
use <printability.scad>
module widget() { cuboid([10,10,10], rounding=1); }
EOF
  if scan_scad "$tmp/good-lib.scad" >/dev/null 2>&1; then
    echo "ok    selftest: a permissive (BOSL2) include passes Rule A"
  else
    echo "FAIL  selftest: a permissive include was wrongly flagged"; ok=0
  fi

  # --- Rule B -------------------------------------------------------------
  # POSITIVE: core/site code that copies the vendored source tree must be caught.
  cat > "$tmp/bad-build.mjs" <<'EOF'
import fs from 'node:fs';
fs.cpSync('lib/NopSCADlib', 'build/site/vendor/NopSCADlib', {recursive: true});
EOF
  if scan_core_source "$tmp/bad-build.mjs" >/dev/null 2>&1; then
    echo "FAIL  selftest: bundling the vendored source tree was NOT caught"; ok=0
  else
    echo "ok    selftest: bundling the vendored source tree fails Rule B"
  fi

  # POSITIVE: path-prefixed refs (./, ../, sub/dir) and an END-OF-LINE ref must
  # ALSO be caught — the leading boundary must allow `/` and `.`, and the
  # trailing `$` must anchor EOL. Regression: an earlier leading class excluded
  # `/`+`.` and silently missed ./lib and ../lib entirely, and no fixture
  # covered an EOL-terminated reference.
  cat > "$tmp/bad-paths.sh" <<'EOF'
cp -r ./lib/NopSCADlib "$dest"
VENDOR=../lib/NopSCADlib
tar cf x.tar src/lib/NopSCADlib
EOF
  if scan_core_source "$tmp/bad-paths.sh" >/dev/null 2>&1; then
    echo "FAIL  selftest: path-prefixed (./ ../ sub/) or EOL vendored refs were NOT caught"; ok=0
  else
    echo "ok    selftest: path-prefixed (./ ../ sub/) and EOL vendored refs fail Rule B"
  fi

  # NEGATIVE 0: a different directory whose name merely ends in "lib", or a
  # longer library name under lib/, is not the vendored lib/<root> — no match.
  cat > "$tmp/lookalike.sh" <<'EOF'
cp zlib/NopSCADlib d
use lib/NopSCADlibExtra/foo
EOF
  if scan_core_source "$tmp/lookalike.sh" >/dev/null 2>&1; then
    echo "ok    selftest: zlib/ and NopSCADlibExtra look-alikes do not match Rule B"
  else
    echo "FAIL  selftest: a look-alike path wrongly matched Rule B"; ok=0
  fi

  # NEGATIVE 1: a COMMENT naming the vendored path is documentation, not a bundle.
  cat > "$tmp/comment.sh" <<'EOF'
# nothing here includes lib/NopSCADlib/ — see docs/licensing.md
echo "building site"
EOF
  # NEGATIVE 2: a GENERATOR emitting a per-design include STRING (the assembly.sh
  # pattern) references the include NAME, not the lib/ source path — must pass.
  cat > "$tmp/generator.sh" <<'EOF'
echo 'include <NopSCADlib/core.scad>' > "$out"
EOF
  if scan_core_source "$tmp/comment.sh" "$tmp/generator.sh" >/dev/null 2>&1; then
    echo "ok    selftest: a comment and a per-design include-string generator pass Rule B"
  else
    echo "FAIL  selftest: a comment or include-string generator was wrongly flagged"; ok=0
  fi

  [[ "$ok" == 1 ]] || return 1
}

if [[ "${1:-}" == "--selftest" ]]; then
  selftest
  echo "ok    license-boundary-check selftest passed"
  exit 0
fi

fail=0

# nullglob (Bash 3.0+) so an empty lib/*.scad vanishes; globstar (Bash 4) is
# deliberately NOT used — see the ci-classify.sh Bash 3.2 note.
shopt -s nullglob

# Rule A file set: first-party lib/*.scad (top-level only — the single-level
# glob excludes the vendored lib/BOSL2 and lib/NopSCADlib subtrees), plus any
# .scad committed under scripts/ or site/ (none today; future-proofed). The
# latter come from `git ls-files`, not a `**` globstar glob, to stay on the
# stock-macOS Bash 3.2 floor. Rule B file set is built in the same pass:
# committed scripts/ and site/ files, minus the .scad routed to Rule A and
# minus the boundary-naming allowlist.
scad_files=(lib/*.scad)
core_src=()
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  if [[ "$f" == *.scad ]]; then
    scad_files+=("$f")
    continue
  fi
  _in_allow_bundle "$f" && continue
  core_src+=("$f")
done < <(git ls-files -- scripts/ site/)

echo "-- license-boundary: Rule A (shared .scad must not include a copyleft library)"
if ((${#scad_files[@]})) && ! scan_scad "${scad_files[@]}"; then
  fail=1
fi

echo "-- license-boundary: Rule B (core/site must not bundle the vendored copyleft source)"
if ((${#core_src[@]})) && ! scan_core_source "${core_src[@]}"; then
  fail=1
fi

if [[ "$fail" == 0 ]]; then
  echo "ok    copyleft stays out of shared core — GPL/copyleft is design-layer only (issue #160, docs/licensing.md)"
fi
exit "$fail"
