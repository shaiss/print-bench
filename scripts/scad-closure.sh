#!/usr/bin/env bash
# Include-closure walk for textual part-dispatch proofs (issue #766).
#
#   source scripts/scad-closure.sh
#     closure_part_branch <entry.scad> <part>
#       # 0 iff some file in the entry's include closure carries
#       # `part == "<part>"` (the matcher gate.sh / fusecheck-check.sh used
#       # on the entry file alone).
#     closure_files <entry.scad>
#       # one resolved path per line: the entry, then every first-party file
#       # it transitively `include`s (not `use`s).
#   ./scripts/scad-closure.sh --selftest
#     # throwaway trees: a branch in an included parent counts, two include
#     # hops count, a branch nowhere in the closure is refused, a `use` of a
#     # file that carries the branch does not count, a commented include
#     # does not count, a cyclic include terminates. Run by check.sh.
#
# WHY NOT catalog.sh's walker: catalog.sh's includes_coupling (issue #517)
# walks include AND use, because a NUGGS module can `use <nuggs-coupling.scad>`
# two parents up. A `part == "..."` dispatcher is top-level executable
# geometry; OpenSCAD's `use` imports modules/functions and does not inject
# that dispatcher, so a variable-only derivative's live path is `include
# <../parent/parent.scad>`. Following `use` here would count a branch that
# is not live. Resolve-and-first-party / cycle-safe shape is the same move
# (dirname, then lib/, then repo root; vendored lib/<vendor>/ is a leaf).
#
# CLOSURE_ROOT (default $PWD) is the repo root the OPENSCADPATH candidates
# are relative to. gate.sh / fusecheck-check.sh source this after they cd
# to the repo root; the selftest points it at a throwaway tree.

closure_root() {
  echo "${CLOSURE_ROOT:-$PWD}"
}

# Same line-preserving strip catalog.sh::strip_scad_comments uses, so a
# commented-out include is never walked. Copied rather than sourced: catalog.sh
# is an executed CLI whose functions are not a sourced library, and extracting
# them would be a catalog.sh behavior-risk the #766 contract forbids.
closure_strip_comments() {
  awk '
    {
      line = $0; out = ""; i = 1; n = length(line)
      while (i <= n) {
        two = substr(line, i, 2)
        if (inblock) {
          if (two == "*/") { inblock = 0; i = i + 2 } else { i = i + 1 }
          continue
        }
        if (two == "//") { break }
        if (two == "/*") { inblock = 1; i = i + 2; continue }
        out = out substr(line, i, 1); i = i + 1
      }
      print out
    }
  ' "$1"
}

# Live `include <...>` targets only. `use` is a leaf of this walk (see header).
closure_include_targets() {
  closure_strip_comments "$1" \
    | grep -oE 'include[[:space:]]*<[^>]+>' \
    | sed -E 's/^include[[:space:]]*<//; s/>$//' \
    || true
}

# Resolve one include target against the file that carries it, the way the
# scripts set OPENSCADPATH: the including file's directory first (the
# `../<parent>/<parent>.scad` derivative form), then lib/, then the repo root.
# Echoes the resolved path, or nothing for a target no candidate holds.
closure_resolve() { # <target> <including-file>
  local p="$1" from="$2" cand root
  root="$(closure_root)"
  for cand in "$(dirname "$from")/$p" "${root%/}/lib/$p" "${root%/}/$p"; do
    [[ -f "$cand" ]] && { realpath -s "$cand"; return 0; }
  done
  return 0
}

# Recurse into a resolved file? First-party under CLOSURE_ROOT, minus vendored
# trees (lib/<vendor>/...). An include of a sibling fixture, a parent design,
# or a top-level lib/*.scad is in; BOSL2 / NopSCADlib are leaves.
closure_enter() {
  local resolved="$1" root
  root="$(realpath -s "$(closure_root)")"
  case "$resolved" in
    "${root%/}/"*) ;;
    *) return 1 ;;
  esac
  case "$resolved" in
    "${root%/}/lib/"*"/"*) return 1 ;;
  esac
  return 0
}

# Every file in the include closure of <entry>, entry first. Cycle-safe.
closure_files() {
  local entry="$1"
  [[ -f "$entry" ]] || return 0
  local f p resolved
  entry="$(realpath -s "$entry")"
  local -a queue=("$entry")
  local -A seen=()
  while (( ${#queue[@]} > 0 )); do
    f="${queue[0]}"
    queue=("${queue[@]:1}")
    [[ -n "${seen[$f]:-}" ]] && continue
    seen["$f"]=1
    printf '%s\n' "$f"
    while IFS= read -r p; do
      [[ -n "$p" ]] || continue
      resolved="$(closure_resolve "$p" "$f")"
      [[ -n "$resolved" ]] || continue
      if closure_enter "$resolved" && [[ -z "${seen[$resolved]:-}" ]]; then
        queue+=("$resolved")
      fi
    done < <(closure_include_targets "$f")
  done
}

# The matcher gate.sh used on the entry file: a real DISPATCH selector, not
# merely a quoted string anywhere. Scan every file in the include closure.
closure_part_branch() { # <entry.scad> <part>
  local entry="$1" part="$2" f
  [[ "$part" =~ ^[A-Za-z0-9_-]+$ ]] || return 1
  [[ -f "$entry" ]] || return 1
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    if grep -Eq "part[[:space:]]*==[[:space:]]*\"${part}\"" "$f"; then
      return 0
    fi
  done < <(closure_files "$entry")
  return 1
}

closure_selftest() {
  local tmp fails=0
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/scad-closure.XXXXXX")"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN
  CLOSURE_ROOT="$tmp"
  mkdir -p "$tmp/designs/gp" "$tmp/designs/p" "$tmp/designs/c" \
           "$tmp/designs/plain" "$tmp/designs/useonly" "$tmp/designs/commented" \
           "$tmp/designs/cycA" "$tmp/designs/cycB"

  printf '%s\n' \
    'part = "assembled";' \
    'if (part == "fused") cube(1);' \
    'else if (part == "fitcheck") cube(2);' \
    >"$tmp/designs/gp/gp.scad"
  printf 'include <../gp/gp.scad>\n' >"$tmp/designs/p/p.scad"
  printf 'include <../p/p.scad>\n' >"$tmp/designs/c/c.scad"
  printf 'cube(1);\n' >"$tmp/designs/plain/plain.scad"
  printf 'use <../gp/gp.scad>\n' >"$tmp/designs/useonly/useonly.scad"
  printf '// include <../gp/gp.scad>\ncube(1);\n' \
    >"$tmp/designs/commented/commented.scad"
  printf 'include <../cycB/cycB.scad>\n' >"$tmp/designs/cycA/cycA.scad"
  printf 'include <../cycA/cycA.scad>\nif (part == "fused") cube(1);\n' \
    >"$tmp/designs/cycB/cycB.scad"

  ok() { echo "ok    scad-closure selftest: $1"; }
  bad() {
    echo "FAIL  scad-closure selftest: $1"
    fails=$((fails + 1))
  }

  if closure_part_branch "$tmp/designs/p/p.scad" fused; then
    ok "a branch in an included parent counts (variable-only derivative)"
  else
    bad "included-parent branch was not found"
  fi

  if closure_part_branch "$tmp/designs/c/c.scad" fitcheck; then
    ok "a branch two include hops up counts (transitive closure)"
  else
    bad "grandparent branch was not found"
  fi

  if closure_part_branch "$tmp/designs/gp/gp.scad" fused; then
    ok "a branch in the entry file still counts"
  else
    bad "entry-file branch was not found"
  fi

  if closure_part_branch "$tmp/designs/plain/plain.scad" fused; then
    bad "a branch nowhere in the closure was accepted"
  else
    ok "a branch nowhere in the closure is refused"
  fi

  if closure_part_branch "$tmp/designs/p/p.scad" nope; then
    bad "a missing part name on a live parent was accepted"
  else
    ok "a part name the closure does not dispatch is refused"
  fi

  if closure_part_branch "$tmp/designs/useonly/useonly.scad" fused; then
    bad "a use-only (not include) parent branch was counted — that dispatcher is not live"
  else
    ok "a use of a file that carries the branch does not count"
  fi

  if closure_part_branch "$tmp/designs/commented/commented.scad" fused; then
    bad "a commented-out include was walked"
  else
    ok "a commented include is not walked"
  fi

  if closure_part_branch "$tmp/designs/cycA/cycA.scad" fused; then
    ok "a cyclic include terminates and still finds the branch"
  else
    bad "a cyclic include hung or missed the branch"
  fi

  # Wiring pin: the two proofs this helper exists to serve still call it.
  if grep -q 'closure_part_branch' scripts/gate.sh \
     && grep -q 'closure_part_branch' scripts/fusecheck-check.sh; then
    ok "gate.sh and fusecheck-check.sh call closure_part_branch"
  else
    bad "gate.sh / fusecheck-check.sh no longer call closure_part_branch"
  fi

  unset CLOSURE_ROOT
  # Live #675 shape: a file that only includes pip-ratchet must see that
  # parent's fitcheck/fused dispatch (the six-FAILs-on-green-poses case).
  if [[ -f designs/pip-ratchet/pip-ratchet.scad ]]; then
    printf 'include <designs/pip-ratchet/pip-ratchet.scad>\n' >"$tmp/der.scad"
    if closure_part_branch "$tmp/der.scad" fitcheck \
       && closure_part_branch "$tmp/der.scad" fused; then
      ok "pip-ratchet dispatch is visible through a child include (the #675 shape)"
    else
      bad "pip-ratchet's fitcheck/fused branches were not found through include"
    fi
    if closure_part_branch "$tmp/der.scad" not-a-part; then
      bad "a name pip-ratchet does not dispatch was accepted through include"
    else
      ok "a name pip-ratchet does not dispatch is still refused through include"
    fi
  fi
  if [[ "$fails" -ne 0 ]]; then
    echo "FAIL  scad-closure selftest: ${fails} check(s) missed"
    return 1
  fi
  echo "ok    scad-closure selftest: include-closure branch proof still discriminates"
  return 0
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  set -euo pipefail
  cd "$(dirname "$0")/.."
  case "${1:-}" in
    --selftest) closure_selftest ;;
    -h|--help)
      echo "usage: scripts/scad-closure.sh --selftest" >&2
      echo "       source scripts/scad-closure.sh  # closure_part_branch / closure_files" >&2
      ;;
    *)
      echo "usage: scripts/scad-closure.sh --selftest" >&2
      exit 2
      ;;
  esac
fi
