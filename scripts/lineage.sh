#!/usr/bin/env bash
# Lineage CLI for derivative designs, plus the shell helpers scripts/gate.sh
# uses to PROVE a derivative's override actually took.
#
#   ./scripts/lineage.sh check|blast-radius|parents|children|ancestors|...
#                                  # delegated to tools/lineage
#   ./scripts/lineage.sh selftest  # handled here: renders the fixtures under
#                                  # tools/lineage/selftest/ and asserts the
#                                  # gate's comparison still distinguishes a
#                                  # working override from a typo'd one
#
# Why PYTHONPATH instead of requiring `pip install -e tools/lineage`: the
# package is deliberately stdlib-only so CI's classifier job — which runs
# before anything is installed, because its whole job is deciding what to
# install and gate — can call the resolver with no install step. Pointing
# PYTHONPATH at the source tree keeps that true locally as well, so a
# contributor can never gate against a stale installed copy of the resolver
# while editing the one in the tree. `pip install -e tools/lineage` still
# works and puts the same code behind a `lineage` console script.
#
# gate.sh SOURCES this file for the three helpers below. They live here rather
# than in gate.sh so that `selftest` exercises the very functions the gate
# runs: a selftest that reimplements the mesh comparison proves only that the
# reimplementation works, which is worth nothing on the day OpenSCAD changes
# its export behaviour. Sourcing is safe — everything below the guard at the
# bottom is a definition, and gate.sh already runs under these same shell
# options.
set -euo pipefail

# Both this script and gate.sh derive these from the same two environment
# variables, so it makes no difference which of them assigns first when gate.sh
# sources us. OPENSCAD_BIN selects the binary (e.g. openscad-nightly);
# OPENSCAD_ARGS passes extra flags (e.g. --backend=manifold — nightly-only).
OPENSCAD_BIN="${OPENSCAD_BIN:-openscad}"
read -ra OSC_ARGS <<<"${OPENSCAD_ARGS:-}"

# Render <src> to <out> as an explicit binary STL; any further arguments are
# passed to OpenSCAD (that is how the caller supplies -D part="...").
#
# --export-format binstl rather than trusting the .stl extension: the override
# check compares the two exports, and that means nothing unless both sides came
# out of the same exporter. binstl also parses to triangles cheaply, which
# lineage_mesh_hash needs — it cannot compare the raw bytes, because OpenSCAD
# does not write them in a stable order (see there).
#
# Returns 0 and leaves NO file behind when the source's top level is empty.
# OpenSCAD treats that as an error — it prints "Current top level object is
# empty", exits 1 and writes nothing — but for us it is not one: it is the
# exact signal the base-safety proof is hunting for. A real render failure
# (parse error, unreadable input, CGAL error) still returns 1, with the tail
# of OpenSCAD's output indented under the caller's own failure line.
#
# The ERROR test is not belt-and-braces. OpenSCAD prints "Current top level
# object is empty" after a failed assert too, on top of the ERROR line and the
# same exit 1 — so keying on the empty message alone would report a design that
# blew up mid-render as one that cleanly emitted no geometry, and the
# base-safety proof would pass on a design nobody can even render. Demanding
# the absence of ERROR is what keeps "empty" meaning empty.
#
# LINEAGE_RENDER_LOG=<path>, when set, additionally saves OpenSCAD's full
# output there on every path (an optional out-parameter: unset by default,
# so no existing caller changes). scripts/kinematics-check.sh sets it to fail
# a check on a wrong-geometry WARNING that the empty path returns success on.
lineage_render_binstl() {
  local src="$1" out="$2"
  shift 2
  # A leftover STL from an earlier run would make a geometry-free source look
  # like it had emitted geometry — the base-safety proof would then fail on
  # exactly the design that passes it. Clear the target first.
  rm -f "$out"
  local log rc=0
  log=$(xvfb-run -a "$OPENSCAD_BIN" ${OSC_ARGS[@]+"${OSC_ARGS[@]}"} \
    --export-format binstl -o "$out" "$@" "$src" 2>&1) || rc=$?
  # Optional out-parameter, unset by every caller but the kinematics gate: a
  # path in LINEAGE_RENDER_LOG receives OpenSCAD's full output on every path
  # below — the cleanly-empty one included, where a wrong-geometry WARNING
  # ("Ignoring unknown module": the call skipped, the top level empty) is the
  # success this function returns and nothing is printed. A caller that must
  # fail on that reads the file back. Unset, nothing here changes.
  if [[ -n "${LINEAGE_RENDER_LOG:-}" ]]; then
    printf '%s\n' "$log" > "$LINEAGE_RENDER_LOG"
  fi
  if (( rc != 0 )); then
    if grep -qF "Current top level object is empty" <<<"$log" \
       && ! grep -qF "ERROR" <<<"$log"; then
      return 0
    fi
    sed 's/^/      /' <<<"$log" | tail -20
    return 1
  fi
  # An "Ignoring unknown module" here is the sibling of the bug this whole
  # gate exists for, and it never reaches a nonzero exit — surface it.
  grep "WARNING" <<<"$log" | sed 's/^/      /' || true
}

# Identity of the mesh in a binary STL, ignoring the order its facets happen
# to have been written in.
#
# NOT `sha256sum` over the file, which is what this was first written as. That
# is wrong in the direction that matters: OpenSCAD 2021.01 re-orders facets
# between renders of the SAME unchanged source, so parent and derivative differ
# every time and the override check passes unconditionally — a gate that always
# says yes, guarding the one failure that already looks like success. Measured
# on sushi-battleship part=top, rendered twice with no edit: identical facet
# count (24256), identical file size, 3248 differing bytes, and sorted triangle
# lists that match exactly. Small models reproduce byte for byte, which is why
# a byte hash looks sound right up until it is used on a real design.
#
# tools/lineage does the canonicalising (sort the triangles, then hash), where
# it is unit-tested against a deliberately shuffled mesh.
lineage_mesh_hash() {
  ./scripts/lineage.sh mesh-hash "$1"
}

# Facet count of a binary STL. Absent file means OpenSCAD had no geometry to
# write (see lineage_render_binstl) and counts as zero — precisely what a
# base-safe design renders to.
lineage_facet_count() {
  ./scripts/lineage.sh facet-count "$1"
}

# Prove the gate can still fire. A gate that has never fired looks exactly like
# a gate that cannot, and this one rests entirely on undocumented OpenSCAD
# behaviour: that a redefinition binding nothing is reported nowhere, and that
# the mesh it leaves behind is the base's. Those are the two facts the
# derivative check is built on, so they get re-proven on whatever OpenSCAD is
# actually installed rather than assumed from the version that was measured.
# Run it after any OpenSCAD upgrade.
#
# "the base's mesh" and not "the base's bytes": facet order is not stable
# between renders, which is why lineage_mesh_hash canonicalises before hashing.
# The fixtures here are small enough to reproduce byte for byte even so — which
# is precisely why they cannot be the only evidence, and why the ordering
# itself is pinned by a unit test in tools/lineage/tests that shuffles a mesh.
lineage_selftest() {
  local src="tools/lineage/selftest"
  local out="build/.lineage/selftest"
  mkdir -p "$out"

  local f rc=0
  for f in base derivative-ok derivative-typo base-safe; do
    if [[ ! -f "${src}/${f}.scad" ]]; then
      echo "FAIL  selftest: fixture ${src}/${f}.scad is missing"
      return 1
    fi
    if ! lineage_render_binstl "${src}/${f}.scad" "${out}/${f}.stl"; then
      echo "FAIL  selftest: ${src}/${f}.scad did not render"
      return 1
    fi
  done

  # Tested, not assigned bare: `x=$(cmd)` adopts cmd's status and errexit
  # would abort the selftest mid-way, reporting nothing about the assertions
  # it had not reached yet — a selftest has to say which property broke.
  local h_base h_ok h_typo
  for f in base derivative-ok derivative-typo; do
    if ! lineage_mesh_hash "${out}/${f}.stl" >/dev/null; then
      echo "FAIL  selftest: ${out}/${f}.stl did not parse as a binary STL"
      return 1
    fi
  done
  h_base=$(lineage_mesh_hash "${out}/base.stl")
  h_ok=$(lineage_mesh_hash "${out}/derivative-ok.stl")
  h_typo=$(lineage_mesh_hash "${out}/derivative-typo.stl")

  if [[ "$h_ok" != "$h_base" ]]; then
    echo "ok    selftest: a real override changes the mesh — the gate can recognise success"
  else
    echo "FAIL  selftest: derivative-ok.scad rendered the base's mesh"
    echo "      Its redefinition of lid() should have rerouted the base's own call"
    echo "      site. Either this OpenSCAD no longer honours that, or the export no"
    echo "      longer shows it — either way the gate would reject correct work."
    rc=1
  fi

  if [[ "$h_typo" == "$h_base" ]]; then
    echo "ok    selftest: a typo'd override reproduces the base mesh exactly — the gate fires"
  else
    echo "FAIL  selftest: derivative-typo.scad did not reproduce the base mesh"
    echo "      The gate's whole failure signature is 'identical to the parent'. If a"
    echo "      no-op override no longer renders identically, the gate cannot see one"
    echo "      and needs a new signal before it is trusted again."
    rc=1
  fi

  local n_base n_safe
  if ! n_base=$(lineage_facet_count "${out}/base.stl"); then
    n_base=unreadable
  fi
  if ! n_safe=$(lineage_facet_count "${out}/base-safe.stl"); then
    n_safe=unreadable
  fi

  if [[ "$n_safe" == 0 && "$n_base" != 0 && "$n_base" != unreadable ]]; then
    echo "ok    selftest: base-safe.scad emits 0 facets, base.scad emits ${n_base} — the base-safety proof separates them"
  else
    echo "FAIL  selftest: facet counts do not separate a base-safe file from an ordinary one"
    echo "      base-safe.scad: ${n_safe} facets (expected 0), base.scad: ${n_base} facets (expected non-zero)."
    rc=1
  fi

  return "$rc"
}

lineage_main() {
  # selftest is answered here rather than passed through: it renders geometry,
  # which the stdlib-only Python package deliberately cannot do.
  if [[ "${1:-}" == "selftest" ]]; then
    if [[ $# -gt 1 ]]; then
      echo "error: selftest takes no arguments" >&2
      exit 2
    fi
    # Explicitly, rather than letting errexit turn a failed assertion into an
    # exit: this status is the script's, and it should be obvious why.
    local rc=0
    lineage_selftest || rc=$?
    return "$rc"
  fi
  exec env PYTHONPATH="$PWD/tools/lineage/src${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m lineage.cli "$@"
}

# Run only when executed. When gate.sh sources this file it has already cd'd to
# the repo root, and a cd here would move it out from under the caller.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  cd "$(dirname "$0")/.."
  lineage_main "$@"
fi
