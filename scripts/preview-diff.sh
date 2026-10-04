#!/usr/bin/env bash
# preview-diff.sh — the regen-faithfulness check (issue #470): classify every
# regenerated preview against the committed bytes it is about to replace.
#
# Issue #69 closed the STALENESS half of the preview problem: CI's regen job
# re-renders and commits the previews in the same run that gates the source,
# so a committed image can never be older than the source beside it. Nothing
# measured the FAITHFULNESS half — whether the regenerated image depicts the
# same thing the committed one did. Every gate on a derived artifact is
# presence-only, and the regen commit step asserted without measuring that the
# diff on a default-branch push, or on the loop guard's second pass, "is
# rendering noise". #408's Jane re-verified 27 regenerated previews by hand
# because nothing else would; PR #619's fixer reverted a bot regen commit by
# hand on the same unmeasured judgement.
#
# This measures it. For each staged designs/*/previews/*.png|*.gif it takes the
# base bytes (<base>:<path>) and the staged bytes (:<path>) as raw blobs,
# flattens each to one strip (a GIF's frames coalesced onto the full canvas and
# stacked top to bottom; a PNG is its own strip), and counts the differing
# pixels with ImageMagick's `compare -metric AE -fuzz <pct>`. One class a file:
#
#   noise         same size; the differing pixels are within the band (default
#                 1% of the image — tools/photoshot/README.md measures Cycles'
#                 cross-runner SSE4.2/AVX2 kernel wobble at 0.3-0.6% of pixels)
#   content       same size; more pixels differ than the band allows
#   resized       the dimensions differ — for a GIF that includes the frame
#                 count, since the strip height is frames x canvas height
#   new           added; there is nothing to compare it against
#   removed       deleted
#   not-compared  ImageMagick is absent, or could not decode one side as the
#                 format its extension names. Listed, never dropped: every
#                 staged preview gets exactly one line.
#
# Cross-check (--source-base <ref>): a content or resized diff on a design
# whose OWN sources did not change since <ref> raises a ::warning:: — it is an
# intended lib/generator change or a generator regression, and either way a
# human should look. A design whose sources DID change but whose every
# compared preview reads as noise gets a ::notice:: (do the frozen cameras
# cover the edit?). "Own sources" is regen-stamp.sh's definition: everything
# under designs/<name>/ except *.md prose, the ARCHIVED marker and previews/
# outputs — the previews/*.conf manifests are inputs and do count. Without
# --source-base the cross-check is skipped, and the output says so.
#
# ADVISORY by construction, the fusecheck/cogcheck WARN tier: a verdict always
# exits 0, whatever it says. Exit 2 is a usage error or a git failure that
# leaves no verdict to give. It JUDGES output and generates none, so it is not
# a regen-stamp.sh input and not in ci-classify.sh's regen_all list — editing
# it re-renders nothing (ci-classify's selftest pins that).
#
#   ./scripts/preview-diff.sh [--base <ref>] [--source-base <ref>]
#                             [--band <pct>] [--fuzz <pct>] [--summary <file>]
#   ./scripts/preview-diff.sh --selftest
#
# --base defaults to HEAD, so what is staged is compared against the last
# commit — exactly the commit CI's regen step is about to make
# (.github/workflows/ci.yml stages what its commit step will, then calls this
# in a step of its own that holds no token). Stage first; the script only
# reads, it never touches the index or the working tree.
# --repo <dir> reads another repository (the selftest's throwaway one).
#
# Output: one machine line per staged preview on stdout,
#   PREVIEW-DIFF <class> <changed-pixels-%|-> <path>
# then the annotations, a tally, and one verdict line over the whole set,
#   PREVIEW-DIFF-VERDICT all-noise|content
# — all-noise only when no staged preview is anything but noise (none staged
# counts: a stamp-only commit-back changes no image), content the moment one
# is content, resized, new, removed or not-compared. CI's regen job carries it
# on its commit-back as a `Preview-Diff:` trailer, and auto-review.yml opens no
# new review round for a previews-only all-noise one (reviewer-signoff.sh's
# `round`, the owner's ruling on decision regen-commitback-review-retrigger).
# It is printed only once every row is in, so a run that dies early has none.
# --summary appends a markdown table to <file> (CI passes $GITHUB_STEP_SUMMARY).
#
# The ImageMagick binaries are read from PREVIEW_DIFF_CONVERT and
# PREVIEW_DIFF_COMPARE (default `convert` and `compare`); the selftest points
# one at a missing name to drive the not-compared path for real.
set -euo pipefail

BAND_PCT="1"       # % of an image's pixels that may differ and still be noise
FUZZ_PCT="1"       # per-pixel colour distance compare treats as equal
BASE="HEAD"
SRC_BASE=""
SUMMARY=""
REPO=""
MODE="run"
IM_CONVERT="${PREVIEW_DIFF_CONVERT:-convert}"
IM_COMPARE="${PREVIEW_DIFF_COMPARE:-compare}"

usage() {
  echo "usage: $0 [--base <ref>] [--source-base <ref>] [--band <pct>] [--fuzz <pct>] [--summary <file>] | --selftest" >&2
  exit 2
}

# --- the pure decision --------------------------------------------------------

# classify W0 H0 W1 H1 DIFFPX BAND_PPM — no I/O. Prints noise | content |
# resized | not-compared. BAND_PPM is the band in parts per million of the
# image, so the comparison stays in integer arithmetic (Bash has no floats).
# Returns 2 on a malformed argument: a caller bug, never a verdict.
classify() {
  [ "$#" -eq 6 ] || return 2
  local a
  for a in "$@"; do
    case "$a" in ''|*[!0-9]*) return 2 ;; esac
  done
  # 10# so a leading zero reads as decimal, not octal.
  local w0=$((10#$1)) h0=$((10#$2)) w1=$((10#$3)) h1=$((10#$4))
  local diff=$((10#$5)) band=$((10#$6))
  if [ "$w0" -ne "$w1" ] || [ "$h0" -ne "$h1" ]; then
    echo resized; return 0
  fi
  local area=$((w0 * h0))
  if [ "$area" -eq 0 ]; then
    echo not-compared; return 0
  fi
  # diff/area <= band/1e6, cross-multiplied.
  if [ $((diff * 1000000)) -le $((band * area)) ]; then
    echo noise
  else
    echo content
  fi
}

# verdict_of CLASS... — no I/O. all-noise when every class given is noise (or
# none is given), content otherwise: an unmeasured preview is never noise.
verdict_of() {
  local c
  for c in "$@"; do
    [ "$c" = noise ] || { echo content; return 0; }
  done
  echo all-noise
}

# pct_to_ppm PCT — "1" -> 10000, "0.25" -> 2500. Refuses (returns 2) anything
# that is not a plain non-negative decimal no greater than 100.
pct_to_ppm() {
  case "$1" in ''|.*|*.|*[!0-9.]*|*.*.*) return 2 ;; esac
  awk -v p="$1" 'BEGIN { if (p + 0 > 100) exit 2; printf "%d\n", p * 10000 + 0.5 }'
}

# --- measurement --------------------------------------------------------------

have_im() {
  command -v "$IM_CONVERT" >/dev/null 2>&1 && command -v "$IM_COMPARE" >/dev/null 2>&1
}

# coder_of FILE — the ImageMagick coder for a preview's extension: png | gif,
# anything else refused (returns 1).
coder_of() {
  case "${1##*.}" in
    png) echo png ;;
    gif) echo gif ;;
    *) return 1 ;;
  esac
}

# measure OLD NEW SCRATCH — prints "W0 H0 W1 H1 DIFFPX", or returns 1 when
# ImageMagick cannot decode either side. Different strip sizes skip compare
# (IM6 would run a sub-image search rather than refuse) and report DIFFPX 0;
# classify() calls that resized before it looks at the count.
#
# Every read names its coder (`png:FILE`, `gif:FILE`). Unprefixed, ImageMagick
# picks a decoder by sniffing the bytes before it looks at the name, so a
# branch-committed "x.png" that is really SVG, MVG or MSL — the ImageTragick
# shape — would reach a far richer decoder than PNG's. Pinned, the PNG or GIF
# reader refuses anything else as undecodable, and the row says not-compared.
measure() {
  local old="$1" new="$2" s="$3" co cn
  co="$(coder_of "$old")" && cn="$(coder_of "$new")" || return 1
  "$IM_CONVERT" "$co:$old" -coalesce -append +repage "png:$s/old.png" 2>/dev/null || return 1
  "$IM_CONVERT" "$cn:$new" -coalesce -append +repage "png:$s/new.png" 2>/dev/null || return 1
  local d0 d1
  d0="$("$IM_CONVERT" "png:$s/old.png" -format '%w %h' info: 2>/dev/null)" || return 1
  d1="$("$IM_CONVERT" "png:$s/new.png" -format '%w %h' info: 2>/dev/null)" || return 1
  if [ "$d0" != "$d1" ]; then
    echo "$d0 $d1 0"; return 0
  fi
  # compare exits 0 (alike), 1 (different) or 2 (error) and writes the metric
  # to stderr. -precision 16: IM6 otherwise prints a large count as 1.234e+06.
  local out rc=0 px
  out="$("$IM_COMPARE" -precision 16 -metric AE -fuzz "${FUZZ_PCT}%" \
           "png:$s/old.png" "png:$s/new.png" null: 2>&1)" || rc=$?
  [ "$rc" -le 1 ] || return 1
  px="$(printf '%s\n' "$out" | awk 'NF { printf "%.0f\n", $1; exit }')"
  case "$px" in ''|*[!0-9]*) return 1 ;; esac
  echo "$d0 $d1 $px"
}

# pct DIFFPX AREA — "0.4000%".
pct() { awk -v d="$1" -v a="$2" 'BEGIN { printf "%.4f%%\n", 100 * d / a }'; }

# design_of PATH — designs/<n>/previews/x.png -> <n>
design_of() { local n="${1#designs/}"; echo "${n%%/*}"; }

# sources_changed NAME — 0 when designs/<NAME>/'s own sources (regen-stamp.sh's
# set) differ between --source-base and the index. A git failure here reads as
# "unchanged", so it errs toward the warning, never toward silence.
sources_changed() {
  local n="$1" f changed
  changed="$(git diff --cached --no-renames --name-only "$SRC_BASE" -- "designs/$n")" || changed=""
  while IFS= read -r f; do
    case "$f" in
      designs/"$n"/previews/*.conf) return 0 ;;
      designs/"$n"/previews/*) ;;
      designs/"$n"/ARCHIVED|*.md) ;;
      '') ;;
      *) return 0 ;;
    esac
  done <<<"$changed"
  return 1
}

# --- the run ------------------------------------------------------------------

run() {
  local band_ppm
  band_ppm="$(pct_to_ppm "$BAND_PCT")" || { echo "preview-diff: --band must be a percentage 0-100, got '$BAND_PCT'" >&2; exit 2; }
  pct_to_ppm "$FUZZ_PCT" >/dev/null || { echo "preview-diff: --fuzz must be a percentage 0-100, got '$FUZZ_PCT'" >&2; exit 2; }
  git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null \
    || { echo "preview-diff: --base '$BASE' is not a commit" >&2; exit 2; }
  if [ -n "$SRC_BASE" ]; then
    git rev-parse --verify --quiet "${SRC_BASE}^{commit}" >/dev/null \
      || { echo "preview-diff: --source-base '$SRC_BASE' is not a commit" >&2; exit 2; }
  fi

  local t
  t="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand $t now: it is local to this function
  trap "rm -rf '$t'" EXIT

  # NUL-separated status/path pairs, captured to a file FIRST so a git failure
  # aborts loudly instead of reading as "nothing staged" (fail open).
  git diff --cached --no-renames --name-status -z "$BASE" -- \
    'designs/*/previews/*.png' 'designs/*/previews/*.gif' > "$t/list" \
    || { echo "preview-diff: git diff against '$BASE' failed" >&2; exit 2; }

  local im=false
  have_im && im=true

  # rows: "<class>\t<pct|->\t<path>\t<detail>", one per staged preview.
  : > "$t/rows"
  local st path cls frac detail ext m w0 h0 w1 h1 px
  while IFS= read -r -d '' st && IFS= read -r -d '' path; do
    frac="-"; detail=""
    case "$st" in
      A) cls=new; detail="no committed bytes to compare against" ;;
      D) cls=removed; detail="deleted" ;;
      *)
        if [ "$im" != true ]; then
          cls=not-compared; detail="ImageMagick ($IM_CONVERT/$IM_COMPARE) not on PATH"
        else
          ext="${path##*.}"
          rm -f "$t/old.$ext" "$t/new.$ext"
          # cat-file, the plumbing: raw blob bytes, never a textconv'd view.
          if git cat-file blob "${BASE}:${path}" > "$t/old.$ext" 2>/dev/null \
             && git cat-file blob ":${path}" > "$t/new.$ext" 2>/dev/null \
             && m="$(measure "$t/old.$ext" "$t/new.$ext" "$t")"; then
            read -r w0 h0 w1 h1 px <<<"$m"
            cls="$(classify "$w0" "$h0" "$w1" "$h1" "$px" "$band_ppm")"
            case "$cls" in
              noise|content)
                frac="$(pct "$px" $((w0 * h0)))"
                detail="$px of $((w0 * h0)) px" ;;
              resized) detail="${w0}x${h0} -> ${w1}x${h1}" ;;
              *) detail="empty image" ;;
            esac
          else
            cls=not-compared; detail="ImageMagick could not decode one side as .$ext"
          fi
        fi ;;
    esac
    printf '%s\t%s\t%s\t%s\n' "$cls" "$frac" "$path" "$detail" >> "$t/rows"
    echo "PREVIEW-DIFF $cls $frac $path"
  done < "$t/list"

  # Cross-check, per design that has a compared row.
  local n cross
  : > "$t/notes"
  if [ -z "$SRC_BASE" ]; then
    cross="not run (no --source-base given)"
  else
    cross="against \`$(git rev-parse --short "$SRC_BASE")\`"
    for n in $(cut -f3 "$t/rows" | while IFS= read -r p; do design_of "$p"; done | sort -u); do
      local mine has_change=false has_noise=false
      mine="$(awk -F'\t' -v d="designs/$n/" 'index($3, d) == 1 { print $1 }' "$t/rows")"
      grep -qxE 'content|resized' <<<"$mine" && has_change=true
      grep -qx noise <<<"$mine" && has_noise=true
      if [ "$has_change" = true ]; then
        if ! sources_changed "$n"; then
          echo "::warning::preview-diff: designs/$n/ previews changed beyond the noise band, but designs/$n/'s own sources did not change — an intended lib/generator change, or a generator regression; look before merging (issue #470)" >> "$t/notes"
        fi
      elif [ "$has_noise" = true ] && sources_changed "$n"; then
        echo "::notice::preview-diff: designs/$n/'s sources changed, but every regenerated preview of it reads as noise — check the frozen cameras actually show the edit (issue #470)" >> "$t/notes"
      fi
    done
  fi
  cat "$t/notes"

  local total tally c
  total="$(wc -l < "$t/rows" | tr -d ' ')"
  tally=""
  for c in noise content resized new removed not-compared; do
    tally="$tally $c=$(cut -f1 "$t/rows" | grep -cx -- "$c" || true)"
  done
  echo "preview-diff: $total staged preview(s) vs $BASE —$tally (band ${BAND_PCT}% at fuzz ${FUZZ_PCT}%; cross-check $cross)"
  local verdict
  # shellcheck disable=SC2046  # one class per word is the point
  verdict="$(verdict_of $(cut -f1 "$t/rows"))"
  echo "PREVIEW-DIFF-VERDICT $verdict"

  if [ -n "$SUMMARY" ]; then
    {
      echo "### Preview faithfulness (\`preview-diff.sh\`, issue #470)"
      echo
      if [ "$total" -eq 0 ]; then
        echo "No staged preview differs from \`$BASE\` — nothing to measure."
      else
        echo "$total staged preview(s) compared against \`$BASE\`. **noise** = at most ${BAND_PCT}% of pixels differ"
        echo "(\`compare -metric AE -fuzz ${FUZZ_PCT}%\`), **content** = more. Advisory: this never fails the job."
        echo
        echo "| Class | Pixels changed | Preview | Detail |"
        echo "|---|---|---|---|"
        while IFS="$(printf '\t')" read -r cls frac path detail; do
          echo "| \`$cls\` | $frac | \`$path\` | $detail |"
        done < "$t/rows"
      fi
      echo
      echo "Commit-back verdict: \`$verdict\`."
      echo
      echo "Source cross-check: $cross."
      if [ -s "$t/notes" ]; then
        echo
        sed -E 's/^::(warning|notice)::preview-diff: /- **\1:** /' "$t/notes"
      fi
      echo
    } >> "$SUMMARY"
  fi
  exit 0
}

# --- --selftest -----------------------------------------------------------------

selftest() {
  local fails=0
  ok() { echo "ok   [$1]"; }
  bad() { echo "FAIL [$1]: $2" >&2; fails=$((fails + 1)); }

  # (a) The pure classifier — unconditional, no ImageMagick, no git. The image
  #     is 200x150 = 30000 px, so the default 1% band is 300 px.
  local row label args want got
  while IFS='|' read -r label args want; do
    [ -n "$label" ] || continue
    # shellcheck disable=SC2086  # args is a space-separated argument list
    got="$(classify $args)" || got="rc=$?"
    if [ "$got" = "$want" ]; then ok "classify $label -> $want"; else bad "classify $label" "expected $want, got $got"; fi
  done <<'ROWS'
identical|200 150 200 150 0 10000|noise
sparse-0.4%|200 150 200 150 120 10000|noise
exactly-at-band|200 150 200 150 300 10000|noise
band-plus-1px|200 150 200 150 301 10000|content
size-change|200 150 220 150 0 10000|resized
gif-extra-frame|200 300 200 450 0 10000|resized
empty-image|0 0 0 0 0 10000|not-compared
leading-zero-is-decimal|200 150 200 150 0099 10000|noise
NEGCTL-band-0-flips-the-0.4%-row|200 150 200 150 120 0|content
NEGCTL-5%-shifted-shape-is-never-noise|200 150 200 150 1500 10000|content
NEGCTL-5%-shape-at-a-generous-4.99%-band|200 150 200 150 1500 49900|content
malformed-arg|200 150 200 x 0 10000|rc=2
too-few-args|200 150 200 150 0|rc=2
ROWS
  # The commit-back verdict (the Preview-Diff trailer): all-noise only when no
  # class is anything but noise; a negative control per other class.
  while IFS='|' read -r label args want; do
    [ -n "$label" ] || continue
    # shellcheck disable=SC2086  # args is a space-separated class list
    got="$(verdict_of $args)"
    if [ "$got" = "$want" ]; then ok "verdict $label -> $want"; else bad "verdict $label" "expected $want, got $got"; fi
  done <<'ROWS'
all-noise|noise noise noise|all-noise
none-staged|  |all-noise
NEGCTL-one-content|noise content noise|content
NEGCTL-resized|noise resized|content
NEGCTL-new|new|content
NEGCTL-removed|noise removed|content
NEGCTL-not-compared|not-compared|content
ROWS
  for row in "1|10000" "0.25|2500" "0|0" "100|1000000" "abc|rc=2" "101|rc=2" ".5|rc=2" "1.2.3|rc=2" "|rc=2"; do
    args="${row%%|*}"; want="${row#*|}"
    got="$(pct_to_ppm "$args")" || got="rc=$?"
    if [ "$got" = "$want" ]; then ok "band '$args' -> $want"; else bad "band '$args'" "expected $want, got $got"; fi
  done

  # (b) End to end in a throwaway git repo with ImageMagick-made fixtures. CI's
  #     scad-check jobs cannot carry ImageMagick (cached apt restores its
  #     alternatives symlinks dangling — ci.yml, issue #85), so this half skips
  #     with a notice there and the classifier rows above still run.
  if ! have_im; then
    echo "::notice::preview-diff selftest: ImageMagick ($IM_CONVERT/$IM_COMPARE) not on PATH — end-to-end half skipped, classifier rows ran"
  else
    # Its own ok/bad add to `fails` above (dynamic scope); a non-zero return
    # only means it stopped early, after counting why.
    selftest_e2e || true
  fi

  if [ "$fails" -ne 0 ]; then
    echo "preview-diff selftest: $fails case(s) failed" >&2
    return 1
  fi
  echo "preview-diff selftest: all cases passed"
}

selftest_e2e() {
  local self t r
  self="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  t="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand $t now: it is local to this function
  # The trap clears itself: a RETURN trap set in a function outlives it and
  # would fire again when the caller returns.
  trap "rm -rf '$t'; trap - RETURN" RETURN
  r="$t/repo"
  mkdir -p "$r"
  ok() { echo "ok   [e2e $1]"; }
  bad() { echo "FAIL [e2e $1]: $2" >&2; fails=$((fails + 1)); }

  # Fixtures: a 200x150 white frame with a 60x50 black block (3000 px).
  local f="$t/fx" i pts=""
  mkdir -p "$f"
  "$IM_CONVERT" -size 200x150 xc:white -fill black -draw 'rectangle 40,30 99,79' "$f/base.png"
  # ~0.4%: 120 sparse red pixels in the white margin — the wobble shape.
  for i in $(seq 0 119); do pts="$pts point $((110 + (i % 40) * 2)),$((100 + (i / 40) * 4))"; done
  "$IM_CONVERT" "$f/base.png" -fill red -draw "$pts" "$f/noise.png"
  # 5%: the block shifted 15 px right — two 15x50 slivers differ, 1500 px.
  "$IM_CONVERT" -size 200x150 xc:white -fill black -draw 'rectangle 55,30 114,79' "$f/shift.png"
  "$IM_CONVERT" -size 220x150 xc:white -fill black -draw 'rectangle 40,30 99,79' "$f/wide.png"
  # Byte-different, pixel-identical: the same image at another zlib level (the
  # photoshot tEXt-chunk rewrite is this shape).
  "$IM_CONVERT" "$f/base.png" -define png:compression-level=1 "$f/reencoded.png"
  # 10%, but faint: a 60x50 #FAFAFA block on white, 1.96% colour distance —
  # different at the default 1% fuzz, equal at 3%. Pins that --fuzz reaches
  # compare in both directions.
  "$IM_CONVERT" "$f/base.png" -fill '#FAFAFA' -draw 'rectangle 120,90 179,139' "$f/faint.png"
  cmp -s "$f/base.png" "$f/reencoded.png" && { bad fixture "re-encoded PNG is byte-identical; the row would never be staged"; return 1; }
  "$IM_CONVERT" -delay 10 "$f/base.png" "$f/shift.png" "$f/two.gif"
  "$IM_CONVERT" -delay 10 "$f/base.png" "$f/shift.png" "$f/base.png" "$f/three.gif"
  # The same two frames with the 120-px wobble on frame 1: 0.2% of the strip.
  "$IM_CONVERT" -delay 10 "$f/noise.png" "$f/shift.png" "$f/two-wobble.gif"
  # The base image's exact pixels, GIF-encoded, under a .png name — staged
  # (h.png) and committed (i.png), since both sides come from the branch. A
  # byte-sniffing read decodes it and calls it noise 0.0000%; the pinned PNG
  # coder must refuse it (the stand-in for SVG/MVG bytes in a .png).
  "$IM_CONVERT" "$f/base.png" "gif:$f/base-as-gif.bin"

  # S0: three designs, sources + committed previews.
  (
    cd "$r"
    git init -q
    git config user.email selftest@example.invalid
    git config user.name selftest
    git config commit.gpgsign false
    for n in still edited moved; do
      mkdir -p "designs/$n/previews"
      echo "cube(10);" > "designs/$n/$n.scad"
      echo "# $n" > "designs/$n/NOTES.md"
      echo "stamp-0" > "designs/$n/previews/.regen-stamp"
      echo "iso | 0,0,0,55,0,25,140" > "designs/$n/previews/cameras.conf"
      cp "$f/base.png" "designs/$n/previews/a.png"
    done
    for x in b c d f g h; do cp "$f/base.png" "designs/still/previews/$x.png"; done
    cp "$f/two.gif" designs/still/previews/anim.gif
    cp "$f/two.gif" designs/still/previews/wobble.gif
    cp "$f/base-as-gif.bin" designs/still/previews/i.png
    cp "$f/base.png" designs/moved/photo.png
    echo "readme" > README.md
    git add -A && git commit -qm S0
    # S1 — the "PR": still changes only prose and its stamp (neither is a
    # source), edited changes only its cameras.conf (a source), moved changes
    # its .scad. HEAD now carries the old previews, as before a regen.
    echo "more prose" >> designs/still/NOTES.md
    echo "stamp-1" > designs/still/previews/.regen-stamp
    echo "top | 0,0,0,0,0,0,140" >> designs/edited/previews/cameras.conf
    echo "cube(12);" > designs/moved/moved.scad
    git add -A && git commit -qm S1
    # The regen: stage what the generators would write.
    cp "$f/noise.png" designs/still/previews/a.png
    cp "$f/shift.png" designs/still/previews/b.png
    cp "$f/wide.png" designs/still/previews/c.png
    git rm -q designs/still/previews/d.png
    cp "$f/base.png" designs/still/previews/e.png
    cp "$f/reencoded.png" designs/still/previews/f.png
    cp "$f/faint.png" designs/still/previews/g.png
    cp "$f/base-as-gif.bin" designs/still/previews/h.png
    cp "$f/base.png" designs/still/previews/i.png
    cp "$f/three.gif" designs/still/previews/anim.gif
    cp "$f/two-wobble.gif" designs/still/previews/wobble.gif
    cp "$f/shift.png" designs/edited/previews/a.png
    cp "$f/noise.png" designs/moved/previews/a.png
    # Out of scope: a stamp, the README and a PNG outside previews/ (which is
    # a design SOURCE by regen-stamp.sh's definition — so it lives in moved,
    # whose sources changed anyway, and cannot mask still's warning).
    echo "stamp-2" > designs/still/previews/.regen-stamp
    echo "gallery" >> README.md
    cp "$f/shift.png" designs/moved/photo.png
    git add -A
  ) || { bad setup "could not build the fixture repo"; return 1; }

  local out rc sum="$t/summary.md" s0
  s0="$(git -C "$r" rev-parse HEAD~1)"
  rc=0
  out="$(bash "$self" --repo "$r" --base HEAD --source-base "$s0" --summary "$sum" 2>&1)" || rc=$?
  [ "$rc" -eq 0 ] && ok "exit 0 on a verdict" || bad "exit" "expected 0, got $rc"

  local line want
  while IFS='|' read -r want line; do
    [ -n "$want" ] || continue
    if grep -qE "^PREVIEW-DIFF $want [^ ]+ $line\$" <<<"$out"; then
      ok "$line -> $want"
    else
      bad "$line" "expected class $want"; printf '%s\n' "$out" | sed 's/^/    /' >&2
    fi
  done <<'WANT'
noise|designs/still/previews/a.png
content|designs/still/previews/b.png
resized|designs/still/previews/c.png
removed|designs/still/previews/d.png
new|designs/still/previews/e.png
noise|designs/still/previews/f.png
content|designs/still/previews/g.png
resized|designs/still/previews/anim.gif
noise|designs/still/previews/wobble.gif
content|designs/edited/previews/a.png
noise|designs/moved/previews/a.png
WANT
  # Exactly thirteen rows (the eleven above plus h.png and i.png): nothing
  # dropped, and nothing outside previews/*.png|gif (the stamp, the README,
  # designs/moved/photo.png) admitted.
  local nrows
  nrows="$(grep -c '^PREVIEW-DIFF ' <<<"$out" || true)"
  [ "$nrows" -eq 13 ] && ok "exactly one row per staged preview" || bad "row count" "expected 13 PREVIEW-DIFF lines, got $nrows"
  grep -q 'PREVIEW-DIFF .* designs/still/previews/f.png$' <<<"$out" \
    && grep -q '^PREVIEW-DIFF noise 0.0000% designs/still/previews/f.png$' <<<"$out" \
    && ok "byte-different, pixel-identical re-encode measures 0.0000%" \
    || bad "re-encode" "expected 'noise 0.0000%'"
  # NEGATIVE CONTROL: h.png (staged side) and i.png (committed side) hold the
  # base image's own pixels, GIF-encoded. A read that sniffs the bytes decodes
  # them and calls each noise 0.0000%; the pinned PNG coder must refuse them,
  # so both list as not-compared.
  for x in h i; do
    grep -q "^PREVIEW-DIFF not-compared - designs/still/previews/$x.png\$" <<<"$out" \
      && ok "NEGCTL a GIF as .png ($x.png) is refused by the PNG coder, not sniffed" \
      || bad "NEGCTL coder pin $x.png" "expected $x.png 'not-compared -'"
  done
  nrows="$(grep -c '^| `' "$sum" || true)"
  [ "$nrows" -eq 13 ] && ok "summary table carries all thirteen rows" || bad "summary" "expected 13 table rows, got $nrows"
  # NEGATIVE CONTROL: a set with any non-noise row is never all-noise, and the
  # verdict is the last machine line, printed once.
  [ "$(grep -c '^PREVIEW-DIFF-VERDICT ' <<<"$out" || true)" -eq 1 ] \
    && grep -q '^PREVIEW-DIFF-VERDICT content$' <<<"$out" \
    && grep -q '^Commit-back verdict: `content`\.$' "$sum" \
    && ok "NEGCTL a mixed set's verdict is content (stdout and summary)" \
    || bad "verdict mixed" "expected exactly one 'PREVIEW-DIFF-VERDICT content'"

  # Cross-check: still (prose + stamp only — not sources) warns; edited
  # (cameras.conf moved — a source) must NOT warn; moved (.scad moved, noise
  # only) gets the notice, and still (it has content) must not.
  grep -q '^::warning::preview-diff: designs/still/ ' <<<"$out" \
    && ok "content with no source change warns (prose and stamp are not sources)" \
    || bad "cross-check still" "expected a ::warning:: for designs/still/"
  grep -q '^::warning::preview-diff: designs/edited/' <<<"$out" \
    && bad "NEGCTL cross-check edited" "warned although cameras.conf (a source) changed" \
    || ok "NEGCTL content with a source change (cameras.conf) does not warn"
  grep -q '^::notice::preview-diff: designs/moved/' <<<"$out" \
    && ok "source change with noise-only previews gets the notice" \
    || bad "cross-check moved" "expected a ::notice:: for designs/moved/"
  grep -q '^::notice::preview-diff: designs/still/' <<<"$out" \
    && bad "NEGCTL notice still" "noticed a design that has a content row" \
    || ok "NEGCTL a design with content gets no noise notice"

  # NEGATIVE CONTROL: band 0 turns the real 0.4% wobble into content — the
  # band is what keeps it noise — while the 0-px re-encode stays noise.
  out="$(bash "$self" --repo "$r" --base HEAD --band 0 2>&1)" || true
  grep -q '^PREVIEW-DIFF content [^ ]* designs/still/previews/a.png$' <<<"$out" \
    && grep -q '^PREVIEW-DIFF noise [^ ]* designs/still/previews/f.png$' <<<"$out" \
    && ok "NEGCTL --band 0 flips the wobble row to content, the re-encode stays noise" \
    || bad "NEGCTL band 0" "expected a.png content and f.png noise"
  grep -q 'cross-check not run (no --source-base given)' <<<"$out" \
    && ok "no --source-base: the cross-check is disclosed as not run" \
    || bad "cross-check disclosure" "expected 'cross-check not run'"

  # NEGATIVE CONTROL: the faint 10% block is content at the default fuzz (row
  # above) and noise at --fuzz 3 — so a fuzz that never reaches compare, or a
  # hardcoded one, fails one direction or the other.
  out="$(bash "$self" --repo "$r" --base HEAD --fuzz 3 2>&1)" || true
  grep -q '^PREVIEW-DIFF noise 0.0000% designs/still/previews/g.png$' <<<"$out" \
    && ok "NEGCTL --fuzz 3 absorbs the faint block the default fuzz reports" \
    || bad "NEGCTL fuzz 3" "expected g.png 'noise 0.0000%'"

  # ImageMagick absent: every modified preview is listed not-compared — none
  # dropped, none guessed — added/removed still classify, and it exits 0.
  rc=0
  out="$(PREVIEW_DIFF_COMPARE=__preview_diff_absent__ bash "$self" --repo "$r" --base HEAD --source-base "$s0" 2>&1)" || rc=$?
  nrows="$(grep -c '^PREVIEW-DIFF not-compared ' <<<"$out" || true)"
  if [ "$rc" -eq 0 ] && [ "$nrows" -eq 11 ] \
     && grep -q '^PREVIEW-DIFF new - designs/still/previews/e.png$' <<<"$out" \
     && grep -q '^PREVIEW-DIFF removed - designs/still/previews/d.png$' <<<"$out" \
     && ! grep -q '^::warning::' <<<"$out"; then
    ok "ImageMagick absent: 11 not-compared, new/removed kept, no guessed warning, exit 0"
  else
    bad "ImageMagick absent" "rc=$rc, not-compared=$nrows"; printf '%s\n' "$out" | sed 's/^/    /' >&2
  fi
  # NEGATIVE CONTROL: an unmeasured preview can never vouch for noise.
  grep -q '^PREVIEW-DIFF-VERDICT content$' <<<"$out" \
    && ok "NEGCTL ImageMagick absent: the verdict is content, not all-noise" \
    || bad "verdict unmeasured" "expected 'PREVIEW-DIFF-VERDICT content'"

  # Usage errors are exit 2, never a verdict.
  for args in "--band abc" "--fuzz 101" "--base no-such-ref" "--source-base no-such-ref" "--bogus"; do
    rc=0
    # shellcheck disable=SC2086  # args is a space-separated argument list
    bash "$self" --repo "$r" $args >/dev/null 2>&1 || rc=$?
    [ "$rc" -eq 2 ] && ok "usage error '$args' -> exit 2" || bad "usage '$args'" "expected exit 2, got $rc"
  done

  # LAST, because it rewrites the index the runs above share: stage only the
  # noise rows (the wobble PNG, the pixel-identical re-encode, the wobble GIF)
  # plus a stamp, and the verdict must be all-noise.
  (
    cd "$r" && git reset -q \
      && git add designs/still/previews/a.png designs/still/previews/f.png \
           designs/still/previews/wobble.gif designs/still/previews/.regen-stamp
  ) || { bad "verdict all-noise" "could not restage the fixture repo"; return 1; }
  out="$(bash "$self" --repo "$r" --base HEAD 2>&1)" || true
  grep -q '^PREVIEW-DIFF-VERDICT all-noise$' <<<"$out" \
    && [ "$(grep -c '^PREVIEW-DIFF noise ' <<<"$out" || true)" -eq 3 ] \
    && ok "a noise-only set (plus its stamp) is all-noise" \
    || { bad "verdict all-noise" "expected 3 noise rows and 'PREVIEW-DIFF-VERDICT all-noise'"; printf '%s\n' "$out" | sed 's/^/    /' >&2; }
}

# --- CLI --------------------------------------------------------------------------

while [ $# -gt 0 ]; do
  case "$1" in
    --selftest) MODE=selftest ;;
    --base) [ $# -ge 2 ] || usage; BASE="$2"; shift ;;
    --source-base) [ $# -ge 2 ] || usage; SRC_BASE="$2"; shift ;;
    --band) [ $# -ge 2 ] || usage; BAND_PCT="$2"; shift ;;
    --fuzz) [ $# -ge 2 ] || usage; FUZZ_PCT="$2"; shift ;;
    --summary) [ $# -ge 2 ] || usage; SUMMARY="$2"; shift ;;
    # The repository to read; defaults to the one this script lives in. The
    # selftest points it at a throwaway repo.
    --repo) [ $# -ge 2 ] || usage; REPO="$2"; shift ;;
    -h|--help) awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 0 ;;
    *) usage ;;
  esac
  shift
done

if [ "$MODE" = selftest ]; then
  selftest
  exit $?
fi

# A relative --summary is resolved before the cd below moves the cwd.
case "$SUMMARY" in ''|/*) ;; *) SUMMARY="$PWD/$SUMMARY" ;; esac
cd "${REPO:-$(dirname "$0")/..}"
run
