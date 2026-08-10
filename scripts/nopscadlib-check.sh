#!/usr/bin/env bash
# Proves the vendored NopSCADlib tree (lib/NopSCADlib/, issue #155) still
# resolves through OPENSCADPATH and actually builds, run by scripts/check.sh.
#
# Why a dedicated check, and not the echo/link pass already in check.sh:
# check.sh link-checks every use/include it can grep, but NO committed file in
# this repo includes NopSCADlib yet — no design is wired (stage 4 of #98), and
# core first-party tooling is forbidden from including it by the GPL boundary
# in LICENSE. So nothing in the regular pass would notice if lib/NopSCADlib/
# went missing, was half-copied, or stopped resolving after a path change: the
# CLAUDE.md silent-failure mode is that an unresolved `include` only WARNs and
# OpenSCAD still exits 0, shipping a part with the feature simply absent. This
# check is the single thing that closes that hole for a vendored tree nothing
# else exercises — same family as printer-conf-check.sh, which exists because a
# render cannot measure whether a mechanism still works.
#
# What it proves, in order of tightness:
#   1. the include resolves at all  (a missing/unreadable core.scad is a hard
#      OpenSCAD error, not a WARN-and-exit-0 — so this alone catches the most
#      likely failure, a botched vendor or a path rename)
#   2. the include produced real geometry (echo alone could pass while the
#      included file bound nothing; a successful STL export means a NopSCADlib
#      module instantiated an actual mesh)
# It does NOT exercise the BOM/exploded-view tooling #98 will use — that lands
# with the generator in #156. This only answers the question #155 asks: "is the
# vendored tree present and resolvable".
set -euo pipefail

cd "$(dirname "$0")/.."
export OPENSCADPATH="$PWD/lib:$PWD"

OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
read -ra OSC_ARGS <<<"${OPENSCAD_ARGS:-}"

fail=0
note() { echo "FAIL  nopscadlib: $1"; fail=1; }

# The check fixture must not live in lib/ (docs-check.sh asserts every lib/*.scad
# is a first-party library with a demo), and not in designs/ (no design ships an
# assembly.conf yet — stage 4). build/ is gitignored, so it is the right home.
mkdir -p build
fixture="build/.nopscadlib-check.scad"
# Capture $? first so the EXIT trap cleans up without clobbering the exit code
# the script chose — the script bails early on failure via `exit 1`, and without
# this the trap's final `rm` (which succeeds) would mask it as 0.
trap 'rc=$?; rm -f "$fixture" build/.nopscadlib-check.echo build/.nopscadlib-check.stl; exit "$rc"' EXIT

# include core.scad (the documented minimum entry point — pulls in utils/core
# plus screws/nuts/washers via screws.scad, which itself `use`s screw.scad for
# the module), then instantiate a real vitamin so the include has to bind
# geometry, not just parse. M2p5_pan_screw is one of the smallest parts in the
# catalogue (defined in screws.scad); $bom=0 suppresses the BOM side effects so
# the render is pure geometry.
cat > "$fixture" <<'EOF'
include <NopSCADlib/core.scad>
$bom = 0;
// M2.5 pan screw from screws.scad — small, fast, exercises the full include chain.
screw(M2p5_pan_screw, 10);
EOF

echo "-- nopscadlib resolve check: include <NopSCADlib/core.scad>"

# Pass 1 — does the include resolve at all? An unresolved include is the silent
# failure mode: under --export-format echo OpenSCAD writes "Can't open include
# file" into the export and STILL exits 0, which is exactly the wrong-geometry
# WARNING check.sh's FATAL_WARN set exists to catch — re-checked here because no
# committed file exercises this include.
echo_log="build/.nopscadlib-check.echo"
rc=0
err="$(xvfb-run -a "$OPENSCAD_BIN" \
  ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
  -o "$echo_log" --export-format echo "$fixture" 2>&1)" || rc=$?
combined="$(printf '%s\n%s' "$err" "$(cat "$echo_log" 2>/dev/null)")"
if (( rc != 0 )); then
  note "echo render of the include failed (exit $rc)"
  sed 's/^/      /' <<<"$combined" | tail -20
  exit "$fail"
fi
if grep -qE "Can't open include file|Ignoring unknown module|Ignoring unknown function" <<<"$combined"; then
  note "include <NopSCADlib/core.scad> did not resolve — lib/NopSCADlib/ missing, half-copied, or path moved"
  grep -E "Can't open include file|Ignoring unknown module|Ignoring unknown function" <<<"$combined" | sed 's/^/      /'
  exit "$fail"
fi
echo "ok    include <NopSCADlib/core.scad> resolves through OPENSCADPATH"

# Pass 2 — did the include bind real geometry? An echo can parse clean while the
# instantiated module binds nothing (the silent-shape failure). A successful STL
# export means a NopSCADlib module produced an actual mesh, which is the
# strongest evidence the vendored tree is functional, not just present.
stl="build/.nopscadlib-check.stl"
rc=0
err="$(xvfb-run -a "$OPENSCAD_BIN" \
  ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
  -o "$stl" --export-format binstl "$fixture" 2>&1)" || rc=$?
if (( rc != 0 )); then
  note "STL render failed — the include resolved but a NopSCADlib module did not build"
  sed 's/^/      /' <<<"$err" | tail -20
  exit "$fail"
fi
# A non-empty STL means geometry was produced. (We do not assert a facet count —
# that would couple this check to OpenSCAD's tessellation across versions, and
# the question #155 asks is "does it resolve and build", not "is the mesh
# identical to some reference".)
if [[ ! -s "$stl" ]]; then
  note "STL export produced an empty file — the include resolved but no geometry was emitted"
  exit "$fail"
fi
echo "ok    NopSCADlib screw(M2p5_pan_screw, 10) built a non-empty mesh (vendored tree is functional)"

exit "$fail"
