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
#     # does not count, an echo("include <...>") string is not walked, a
#     # commented-out `part ==` selector (entry or included parent) is
#     # refused, an early match in a large file still counts under
#     # pipefail (no strip|grep -Eq SIGPIPE false-negative), a cyclic
#     # include terminates, `counterpart == "x"` is not a `part == "x"`
#     # branch (issue #781). Run by check.sh.
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

# Blank "..." string literals (line-oriented, like the comment strip).
# Used only for include-target extraction: an echo("include <x>") is not
# an include. NOT used for the part== matcher — that selector is itself a
# quoted string. OpenSCAD strings are double-quoted.
closure_blank_strings() {
  awk '
    {
      line = $0; out = ""; i = 1; n = length(line); inq = 0
      while (i <= n) {
        c = substr(line, i, 1)
        if (inq) {
          if (c == "\\" && i < n) { out = out "  "; i += 2; continue }
          if (c == "\"") { inq = 0; out = out " "; i++; continue }
          out = out " "; i++; continue
        }
        if (c == "\"") { inq = 1; out = out " "; i++; continue }
        out = out c; i++
      }
      print out
    }
  '
}

# Live `include <...>` targets only. `use` is a leaf of this walk (see header).
# Comments and string literals are stripped first so a commented include or
# an echo("include <x>") cannot add a file to the traversal.
closure_include_targets() {
  closure_strip_comments "$1" \
    | closure_blank_strings \
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
# merely a quoted string anywhere. Identifier boundary before `part` so
# `counterpart == "…"` (or `numpart`, `subpart`, …) cannot satisfy it —
# the same bound scripts/kinematics-check.sh already uses (issue #781).
# Scan every file in the include closure with comments stripped
# (kinematics-check.sh's kin_strip_comments move), so a `// if (part ==
# "clear")` in a parent header cannot satisfy an empty fitcheck.
# Under `set -o pipefail` (gate.sh / check.sh), piping strip→grep -Eq is a
# false-negative trap: grep exits 0 on the first match and closes the pipe,
# awk then dies with SIGPIPE (141), and pipefail makes the whole pipeline
# non-zero — so a real `part ==` on a large file looks absent. Materialize
# the stripped text first (kinematics-check.sh's comment-stripped matcher
# does the same), then match. Also drain closure_files into an array so an
# early return cannot SIGPIPE the producer's printf.
closure_part_branch() { # <entry.scad> <part>
  local entry="$1" part="$2" f
  local -a files=()
  [[ "$part" =~ ^[A-Za-z0-9_-]+$ ]] || return 1
  [[ -f "$entry" ]] || return 1
  mapfile -t files < <(closure_files "$entry")
  for f in "${files[@]}"; do
    [[ -n "$f" ]] || continue
    if grep -Eq '(^|[^A-Za-z0-9_$])part[[:space:]]*==[[:space:]]*"'"${part}"'"' \
         <<<"$(closure_strip_comments "$f")"; then
      return 0
    fi
  done
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
           "$tmp/designs/cycA" "$tmp/designs/cycB" \
           "$tmp/designs/echoed" "$tmp/designs/commented-branch" \
           "$tmp/designs/lookalike"

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
  # Only spelling is counterpart == "x": the unbounded grep
  # part[[:space:]]*==[[:space:]]*"x" matches this; the identifier bound must not.
  printf '%s\n' \
    'counterpart = "x";' \
    'if (counterpart == "x") cube(1);' \
    >"$tmp/designs/lookalike/lookalike.scad"
  printf 'echo("include <../gp/gp.scad>");\ncube(1);\n' \
    >"$tmp/designs/echoed/echoed.scad"
  printf '// if (part == "fused") cube(1);\ncube(1);\n' \
    >"$tmp/designs/commented-branch/commented-branch.scad"

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

  if closure_part_branch "$tmp/designs/echoed/echoed.scad" fused; then
    bad "an echo() string that looks like include <parent> was walked"
  else
    ok "an echo() string containing include <...> is not walked"
  fi

  if closure_part_branch "$tmp/designs/commented-branch/commented-branch.scad" fused; then
    bad "a commented-out part == selector was accepted as dispatch"
  else
    ok "a commented-out part == selector is refused"
  fi

  # The commented selector in an INCLUDED parent (the surface this proof
  # actually expanded) must also refuse — not only when it sits in the entry.
  printf 'include <../commented-branch/commented-branch.scad>\n' \
    >"$tmp/designs/p/via-commented.scad"
  if closure_part_branch "$tmp/designs/p/via-commented.scad" fused; then
    bad "a commented selector in an included parent was accepted"
  else
    ok "a commented selector in an included parent is refused"
  fi

  # pipefail + early match on a large file: strip|grep -Eq used to SIGPIPE
  # the awk and report the branch missing (the CI failure on
  # over-center-toggle-clamp / nuggs-rim-saddle / pop-fidget-card).
  {
    printf 'if (part == "fused") cube(1);\n'
    # ~400 filler lines after the match — enough that grep -q exits before
    # awk finishes when the two are piped under pipefail.
    for _ in $(seq 1 400); do printf '// filler\n'; done
  } >"$tmp/designs/plain/early-match.scad"
  if closure_part_branch "$tmp/designs/plain/early-match.scad" fused; then
    ok "an early part == match in a large file still counts under pipefail"
  else
    bad "an early part == match in a large file was lost to pipefail/SIGPIPE"
  fi

  # Issue #781: the unbounded `part == "…"` grep treated counterpart as part.
  # Keep the hole loaded (the old pattern still matches this fixture) so a
  # rewritten fixture cannot silently unload the negative control.
  if grep -Eq 'part[[:space:]]*==[[:space:]]*"x"' \
       "$tmp/designs/lookalike/lookalike.scad"; then
    ok "the counterpart fixture still matches the unbounded grep (the hole is loaded)"
  else
    bad "the counterpart fixture no longer spells counterpart == \"x\" — the negative control is unloaded"
  fi
  if closure_part_branch "$tmp/designs/lookalike/lookalike.scad" x; then
    bad "counterpart == \"x\" was accepted as part == \"x\""
  else
    ok "counterpart == \"x\" is not a part == \"x\" dispatch branch"
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
