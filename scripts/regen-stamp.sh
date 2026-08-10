#!/usr/bin/env bash
# Input fingerprint for a design's regenerated preview artifacts.
#   ./scripts/regen-stamp.sh <name>    # print the fingerprint (one hex line)
#
# CI's regen job compares this against the committed
# designs/<name>/previews/.regen-stamp and skips re-rendering a design whose
# inputs have not moved — the point being that re-rendering to discover the
# output is byte-identical costs minutes (a Cycles product shot alone is
# ~2 min) and a hash comparison costs milliseconds. After regenerating, the
# job writes the fresh fingerprint back, so the stamp can never be newer than
# the artifacts beside it. A missing or mismatching stamp always regenerates:
# staleness here costs time, never correctness.
#
# The input set is what the preview/GIF/product-shot generators actually read:
#   - the design's own tracked sources — everything under designs/<name>/
#     except prose (*.md), the ARCHIVED marker, and previews/ outputs; the
#     previews/*.conf manifests (cameras.conf) are inputs and stay in.
#   - lib/ in full: OPENSCADPATH means any design may include any library, and
#     resolving the real include graph is not worth the risk of under-hashing
#     (a missed input would silently freeze a stale artifact — the issue #69
#     failure mode this whole mechanism must not reintroduce).
#   - the generator scripts themselves, and this file.
#   - tools/photoshot/ when the design ships a shots.conf; styles/ when it
#     declares a style.conf; scripts/assembly.sh when it ships an assembly.conf.
# NOT hashed, deliberately: the OpenSCAD/Blender versions (they change under
# us and would churn every stamp for pixel wobble the loop guard already
# tolerates) and README/NOTES prose (the gallery and product-page steps run
# regardless of stamps). The regen environment in ci.yml is also invisible to
# this hash — a change there that alters generator output should bump
# STAMP_FORMAT below, which invalidates every committed stamp at once.
set -euo pipefail

cd "$(dirname "$0")/.."

# Part of the hash. Bump to force a full regeneration on the next regen run.
STAMP_FORMAT=1

name="${1:?usage: scripts/regen-stamp.sh <design-name>}"
if [[ ! -f "designs/${name}/${name}.scad" ]]; then
  echo "error: designs/${name}/${name}.scad not found" >&2
  exit 2
fi

# Tracked files only (git ls-files): build outputs and editor droppings can
# never sneak into the fingerprint. Content is hashed from the working tree,
# so uncommitted edits change the stamp the way they change the render.
inputs() {
  # The enumeration is captured FIRST, outside any pipeline, so a git
  # failure aborts loudly instead of hashing a truncated list. Only the
  # grep chain carries `|| true`: grep exits 1 when a filter leaves
  # nothing, which is a real outcome (a design with no non-prose files
  # outside previews/), and under `set -e` that would silently TRUNCATE
  # the input list mid-function — a wrong stamp, not a failed run.
  local design_files
  design_files="$(git ls-files -- "designs/${name}")"
  printf '%s\n' "$design_files" \
    | grep -vE '\.md$' \
    | grep -v -x -F "designs/${name}/ARCHIVED" \
    | grep -v -F "designs/${name}/previews/" \
    || true
  git ls-files -- "designs/${name}/previews/*.conf"
  git ls-files -- lib
  git ls-files -- \
    scripts/render.sh scripts/animate.sh scripts/product-shot.sh \
    scripts/preview-budget.sh scripts/regen-stamp.sh
  if [[ -f "designs/${name}/shots.conf" ]]; then
    git ls-files -- tools/photoshot
  fi
  if [[ -f "designs/${name}/style.conf" ]]; then
    git ls-files -- styles
  fi
  if [[ -f "designs/${name}/assembly.conf" ]]; then
    git ls-files -- scripts/assembly.sh
  fi
}

{
  echo "format=${STAMP_FORMAT}"
  inputs | LC_ALL=C sort -u | while IFS= read -r f; do
    [[ -f "$f" ]] || continue  # listed in the index but deleted on disk
    sha256sum "$f"
  done
} | sha256sum | awk '{print $1}'
