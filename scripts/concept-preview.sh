#!/usr/bin/env bash
# concept-preview.sh — blueprint-style SVG concept sheets for a design
# (issue #472): the mechanics behind the /concept-preview skill.
#
# A design's concept is drawn from designs/<name>/preview-spec.conf — a small
# spec of explicit placements (format: tools/concept-preview/README.md, or
# `--vocab`) — into four standalone sheets in one house drafting style:
#
#   designs/<name>/previews/concept-exterior.svg   sheet 1 — exterior elevation
#   designs/<name>/previews/concept-cutaway.svg    sheet 2 — cutaway / half-section
#   designs/<name>/previews/concept-section.svg    sheet 3 — top section
#   designs/<name>/previews/concept-exploded.svg   sheet 4 — exploded + bill of parts
#
# The spec says what and where; tools/concept-preview owns the look (palette,
# grid, title block, dimension and leader conventions — defined once, embedded
# identically in every sheet). Every sheet is checked before anything is
# written: it parses as XML, carries no external reference, every element lies
# inside its viewBox, and no two labels overlap. A sheet set is written whole
# or not at all.
#
#   ./scripts/concept-preview.sh <name>           write the four sheets
#   ./scripts/concept-preview.sh --check <name>   write nothing; fail if the
#                                                 committed sheets are stale,
#                                                 missing, or fail a check
#   ./scripts/concept-preview.sh --vocab          print the spec vocabulary
#   ./scripts/concept-preview.sh --selftest       the fixture under
#                                                 tools/concept-preview/fixtures:
#                                                 four valid sheets, then three
#                                                 negative controls that must each
#                                                 FAIL — a malformed spec, an
#                                                 out-of-bounds element, two
#                                                 overlapping labels (issue #37:
#                                                 a check that cannot fail is
#                                                 worthless)
#
# Exit codes: 0 pass; 1 a check failed (or --check found the sheets stale);
# 2 the spec was refused (the message names file:line) or bad usage.
set -euo pipefail

cd "$(dirname "$0")/.."

usage() {
  echo "usage: concept-preview.sh <name> | --check <name> | --vocab | --selftest" >&2
  exit 2
}

# The lineage.sh / cog-check.sh pattern: run the package from its src/ tree
# rather than requiring a pip install — stdlib-only by design
# (tools/concept-preview/pyproject.toml).
run_tool() {
  env PYTHONPATH="$PWD/tools/concept-preview/src${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m concept_preview "$@"
}

design_spec() {  # <name> — validates the name, prints the spec path
  local name="$1"
  if [[ ! "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "concept-preview.sh: '$name' is not a design name (kebab-case)" >&2
    exit 2
  fi
  if [[ ! -f "designs/$name/$name.scad" ]]; then
    echo "concept-preview.sh: no design '$name' (designs/$name/$name.scad not found)" >&2
    exit 2
  fi
  if [[ ! -f "designs/$name/preview-spec.conf" ]]; then
    echo "concept-preview.sh: designs/$name/preview-spec.conf not found — compose one first (see /concept-preview)" >&2
    exit 2
  fi
  printf '%s\n' "designs/$name/preview-spec.conf"
}

case "${1:-}" in
  --selftest)
    [[ $# -eq 1 ]] || usage
    run_tool selftest --fixtures tools/concept-preview/fixtures ;;
  --vocab)
    [[ $# -eq 1 ]] || usage
    run_tool vocab ;;
  --check)
    [[ $# -eq 2 ]] || usage
    spec="$(design_spec "$2")"
    run_tool build "$spec" --out "designs/$2/previews" --verify ;;
  ""|-*)
    usage ;;
  *)
    [[ $# -eq 1 ]] || usage
    spec="$(design_spec "$1")"
    run_tool build "$spec" --out "designs/$1/previews" ;;
esac
