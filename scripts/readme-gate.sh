#!/usr/bin/env bash
# Product-page gate: every design directory must ship a README.md that
# works as a product page — the page a stranger reads to decide whether
# to print the design and how. CI runs this on every PR.
#   ./scripts/readme-gate.sh          # gate all designs under designs/
#   ./scripts/readme-gate.sh <name>   # gate one design
#
# A passing README.md must:
#   1. exist in designs/<name>/
#   2. open with an H1 title (# <design name>)
#   3. pitch the design in prose before the first ## section
#      (what it is, who it is for)
#   4. contain non-empty "## Print settings" and "## Parameters" sections
#      (### subheadings belong to their parent ## section; a section needs
#      at least one line of real content — prose, list, or table)
#   5. show at least one committed preview image — a local reference that
#      resolves relative to the design directory (remote http(s) images
#      are allowed but don't satisfy this); every local reference must
#      exist
#   6. if the design ships an animations.conf (GIF previews, rendered by
#      scripts/animate.sh): every manifest entry must have its committed
#      previews/<name>.gif, the README must embed it, and each GIF must
#      stay within the size budget — GIFs live in git history forever
#   7. if the design ships a shots.conf (product shots, rendered by
#      scripts/product-shot.sh): every manifest entry must have its
#      committed previews/<name>.png, the README must embed it, and each
#      shot must stay within the size budget
#   8. if the design ships a derives.conf (it reuses another design's
#      geometry): the page must link every parent's design directory, so a
#      reader who arrives at the derivative can reach what it was built from.
#      Accepted targets, all of them sibling-relative because that is what
#      resolves from designs/<name>/README.md: ../<parent>, ../<parent>/ and
#      ../<parent>/README.md, written as a markdown link — ](...) — or as an
#      HTML <a href="...">, since a page that credits its base with a working
#      anchor has done the thing being asked for. A repo-root-relative
#      designs/<parent>/ does NOT count: from inside designs/<name>/ it
#      resolves to designs/<name>/designs/<parent>/ and 404s, and gating in a
#      dead link is worse than gating in none.
#   9. if the design ships one or more previews/lifestyle-*.png (an
#      AI-restyled lifestyle shot) or previews/lifestyle-*.gif (an AI motion
#      clip, issue #75 — cosmetic, and assumed geometrically approximate, so
#      neither is ever regenerated or geometry-checked): each must be within
#      its size budget (PNG: the product-shot budget; GIF: the animation-GIF
#      budget) and disclosed in CANONICAL form — embedded ONLY as inline
#      markdown images, every embed carrying an "AI-styled scene" alt label
#      and a "geometry is approximate" caption in the paragraph directly
#      below it (alt text is not shown on the rendered page). Canonical, not
#      prose-judged: a fixed phrase an author copies from
#      product-shots/SKILL.md, so a negated caption can't pass and the
#      disclosure can't hide in an <img> tag beside a compliant decoy. Unlike
#      the GIF and product-shot checks there is no manifest — the committed
#      file is the trigger, since an AI restyle cannot be regenerated from
#      source. The trigger is the filename, so an AI image committed under
#      some other name is out of this gate's reach; naming that masquerade is
#      the /jane-review and /drik-review disclosure rules' job, not bash's.
#  10. if the design ships an assembly.conf (assembly instructions, rendered by
#      scripts/assembly.sh, issue #157): the committed previews/exploded.png
#      must exist, be embedded in the README, and stay within the product-shot
#      budget. Presence-only, like shots.conf — CI regenerates the artifact,
#      the gate only checks it is there and visible. No assembly.conf exists
#      in designs/ yet (stage 4 of #98), so this gate is dormant until one
#      ships, and the selftest is the only thing that proves it fires.
#
# Fenced code blocks and HTML comments are ignored throughout: an example
# snippet or commented-out line is not page content, so it neither
# satisfies a requirement nor trips one.
#
# templates/README.md is a skeleton that passes once filled in.
# NOTES.md remains the engineering log; README.md is the product page.
set -euo pipefail

# Absolute path to this script, captured before the cd below so `--selftest`
# can re-invoke the gate against throwaway fixture directories from any CWD.
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"

cd "$(dirname "$0")/.."
# shellcheck source=scripts/preview-budget.sh
# defines MAX_GIF_BYTES (shared with animate.sh) and MAX_SHOT_BYTES (the
# product-shot budget, reused below for lifestyle shots)
. scripts/preview-budget.sh

# The design tree to gate. Overridable so `--selftest` can point the gate at a
# fixture tree without touching the real designs/; defaults to designs/.
ROOT="${READMEGATE_DESIGNS_DIR:-designs}"

fail=0

err() {
  echo "FAIL  $1: $2"
  fail=1
}

# Strip fenced code blocks and HTML comments so example snippets are not
# mistaken for real content (an image inside a ``` fence or <!-- --> comment
# neither renders on the page nor satisfies the gate).
strip_noise() {
  awk '
    BEGIN { fence = 0; incomment = 0 }
    {
      line = $0
      if (fence) {
        if (line ~ /^(```|~~~)/) fence = 0
        next
      }
      if (!incomment && line ~ /^(```|~~~)/) { fence = 1; next }
      out = ""
      rest = line
      while (length(rest) > 0) {
        if (incomment) {
          p = index(rest, "-->")
          if (p == 0) { rest = ""; break }
          rest = substr(rest, p + 3)
          incomment = 0
        } else {
          p = index(rest, "<!--")
          if (p == 0) { out = out rest; rest = ""; break }
          out = out substr(rest, 1, p - 1)
          rest = substr(rest, p + 4)
          incomment = 1
        }
      }
      print out
    }
  ' "$1"
}

# Does the (noise-stripped) README have a "## <section>" heading
# (case-insensitive) with at least one non-blank line of content before the
# next same-or-higher-level heading? Nested ### subheadings count as content.
section_has_content() {
  local section="$1"
  awk -v want="$(tr '[:upper:]' '[:lower:]' <<<"$section")" '
    tolower($0) ~ ("^##[ \t]+" want "([ \t]|$)") { insec = 1; next }
    insec && /^##?[ \t]/                         { exit }
    insec && !/^[ \t]*$/                         { found = 1; exit }
    END                                          { exit !found }
  '
}

# Decide whether one committed lifestyle PNG is disclosed the way the gate
# requires. Reads the (noise-stripped) README on stdin; prints one verdict.
#
# This is a MECHANICAL, canonical-form check, not a judge of prose. The repo's
# own gate philosophy (see scripts/docs-check.sh) is that a check which tries
# to decide whether free text "means" a warning is flaky and gameable — a
# negated caption ("geometry is exact, not approximate") passes a token match,
# a synonym ("generative AI") fails one. So the gate demands a fixed, visible
# marker and leaves the judgment (is the note honest, is the shot masquerading
# as a photo of the print) to /jane-review and /drik-review. The verdicts:
#   OK             every inline embed of the PNG carries the "AI-styled scene"
#                  alt label and a caption containing the canonical phrase
#                  "geometry is approximate" in the paragraph directly below it
#   MISSING_EMBED  the committed PNG is never embedded
#   EXTRA_REF      the PNG path appears somewhere that is NOT a compliant inline
#                  markdown image — an <img> tag, a reference-style link, a bare
#                  link — where the disclosure scan can't see it. Lifestyle
#                  shots must be embedded ONLY as inline `![...](path)` so an
#                  undisclosed hero can't hide beside a disclosed decoy.
#   MISSING_LABEL  some inline embed's alt lacks the "AI-styled scene" label
#   MISSING_NOTE   some inline embed has no "geometry is approximate" caption
#                  directly below it (alt text isn't shown on the rendered page)
# The canonical caption phrase is fixed on purpose: an author copies it from
# product-shots/SKILL.md, so synonyms don't fool it and negations don't pass it.
lifestyle_disclosure() {
  local png="$1"
  awk -v png="$png" '
    BEGIN {
      pat = png
      gsub(/[][(){}.^$*+?|\\]/, "\\\\&", pat)   # escape regex metacharacters
      # ![alt](path) with the path terminated by ")", or by whitespace (the
      # space before an optional "title") — nothing else counts as an embed.
      embed = "!\\[[^]]*\\]\\(" pat "[) \t]"
    }
    {
      lines[NR] = $0
      s = $0                                     # count EVERY occurrence of the
      while ((q = index(s, png)) > 0) {          # path, to compare against the
        total++                                  # number of compliant embeds
        s = substr(s, q + length(png))
      }
    }
    END {
      inline = 0; miss_label = 0; miss_note = 0
      for (i = 1; i <= NR; i++) {
        if (lines[i] !~ embed) continue
        inline++
        a = index(lines[i], "![")
        rest = substr(lines[i], a + 2)
        rb = index(rest, "]")
        alt = tolower(substr(rest, 1, rb - 1))
        if (alt !~ /ai[- ]styled scene/) miss_label = 1
        para = ""; j = i + 1
        while (j <= NR && lines[j] ~ /^[ \t]*$/) j++    # skip blanks
        for (; j <= NR; j++) {
          if (lines[j] ~ /^[ \t]*$/) break              # end of paragraph
          if (lines[j] ~ /^[ \t]*#/) break              # a heading ends it
          if (lines[j] ~ /!\[/) break                   # next image ends it
          if (lines[j] ~ /^[ \t]*</) break              # an HTML block ends it
          para = para " " lines[j]
        }
        if (tolower(para) !~ /geometry is approximate/) miss_note = 1
      }
      if (inline == 0 && total == 0) { print "MISSING_EMBED"; exit }
      if (total > inline)            { print "EXTRA_REF"; exit }
      if (miss_label)                { print "MISSING_LABEL"; exit }
      if (miss_note)                 { print "MISSING_NOTE"; exit }
      print "OK"
    }
  '
}

check_one() {
  local name="$1"
  local dir="${ROOT}/${name}"
  local readme="${dir}/README.md"
  local ok=1

  if [[ ! -d "$dir" ]]; then
    echo "error: $dir not found" >&2
    fail=1
    return 0
  fi

  if [[ ! -f "$readme" ]]; then
    err "$name" "missing README.md — every design ships a product page (start from templates/README.md)"
    return 0
  fi

  # All content checks run on the noise-stripped text: fenced code blocks
  # and HTML comments don't render as page content, so they neither satisfy
  # a requirement nor trip one.
  local cleaned
  cleaned="$(strip_noise "$readme")"

  # Checks below are numbered to match the requirement list in the header
  # comment (requirement 1 — the README exists — is the early return above).

  # 2. Title: the first non-blank line must be an H1 with actual text
  #    ("# Name" — markdown requires the space, and a bare "#" is no title).
  local first
  first="$(grep -m1 -v '^[[:space:]]*$' <<<"$cleaned" || true)"
  if [[ ! "$first" =~ ^#[[:space:]]+[^[:space:]] ]]; then
    err "$name" "README.md must open with an H1 title (# <design name>)"
    ok=0
  fi

  # 3. Intro pitch: at least one line of prose (not a heading, image,
  #    or table row) before the first ## section.
  if ! awk '
      /^## /                                        { exit }
      !/^#/ && !/^!\[/ && !/^\|/ && !/^[ \t]*$/     { found = 1; exit }
      END                                           { exit !found }
    ' <<<"$cleaned"; then
    err "$name" "README.md needs an intro paragraph before the first ## section — pitch the design (what it is, who it is for)"
    ok=0
  fi

  # 4. Required sections, each non-empty.
  local section
  for section in "Print settings" "Parameters"; do
    if ! grep -qiE "^##[[:space:]]+${section}([[:space:]]|$)" <<<"$cleaned"; then
      err "$name" "README.md is missing a \"## ${section}\" section"
      ok=0
    elif ! section_has_content "$section" <<<"$cleaned"; then
      err "$name" "README.md \"## ${section}\" section is empty"
      ok=0
    fi
  done

  # 5. Images: at least one committed local preview, and every local
  #    reference must resolve. Remote http(s) images are allowed but don't
  #    satisfy the requirement — a dead URL is not a product page.
  local images has_local=0
  images="$(grep -oE '!\[[^]]*\]\([^)]+\)' <<<"$cleaned" \
            | sed -E 's/^!\[[^]]*\]\(([^) ]+).*$/\1/' || true)"
  if [[ -n "$images" ]]; then
    local img
    while IFS= read -r img; do
      [[ "$img" =~ ^https?:// ]] && continue
      has_local=1
      if [[ ! -f "${dir}/${img}" ]]; then
        err "$name" "README.md references a missing image: ${img}"
        ok=0
      fi
    done <<<"$images"
  fi
  if [[ "$has_local" == 0 ]]; then
    err "$name" "README.md needs at least one committed preview image (![...](previews/...)); remote URLs don't count"
    ok=0
  fi

  # 6. Animated previews: every animations.conf entry needs its committed
  #    GIF, embedded in the README, within the size budget (MAX_GIF_BYTES,
  #    shared with scripts/animate.sh via scripts/preview-budget.sh).
  local conf="${dir}/animations.conf"
  if [[ -f "$conf" ]]; then
    local anim gif bytes
    # `|| [[ -n ... ]]`: a final line without a trailing newline still makes
    # read populate the variable while returning nonzero — without the guard
    # that entry would silently escape the gate (false pass).
    while IFS= read -r anim || [[ -n "$anim" ]]; do
      anim="${anim%%#*}"
      anim="${anim%%|*}"
      anim="$(tr -d '[:space:]' <<<"$anim")"
      [[ -n "$anim" ]] || continue
      gif="previews/${anim}.gif"
      if [[ ! -f "${dir}/${gif}" ]]; then
        err "$name" "animations.conf lists \"${anim}\" but ${gif} is missing — run ./scripts/animate.sh ${name}"
        ok=0
        continue
      fi
      bytes="$(stat -c %s "${dir}/${gif}")"
      if (( bytes > MAX_GIF_BYTES )); then
        err "$name" "${gif} is $(( (bytes + 1023) / 1024 )) KiB, over the $((MAX_GIF_BYTES / 1024 / 1024)) MiB budget — fewer frames or a smaller size"
        ok=0
      fi
      if ! grep -qF "](${gif})" <<<"$cleaned"; then
        err "$name" "README.md doesn't embed ${gif} — an animation nobody sees isn't a product-page feature"
        ok=0
      fi
    done <"$conf"
  fi

  # 7. Product shots: every shots.conf entry needs its committed PNG,
  #    embedded in the README, within the size budget (MAX_SHOT_BYTES,
  #    shared with scripts/product-shot.sh via scripts/preview-budget.sh).
  local shotsconf="${dir}/shots.conf"
  if [[ -f "$shotsconf" ]]; then
    local shot png sbytes
    # same no-trailing-newline guard as the animations loop above
    while IFS= read -r shot || [[ -n "$shot" ]]; do
      shot="${shot%%#*}"
      shot="${shot%%|*}"
      shot="$(tr -d '[:space:]' <<<"$shot")"
      [[ -n "$shot" ]] || continue
      png="previews/${shot}.png"
      if [[ ! -f "${dir}/${png}" ]]; then
        err "$name" "shots.conf lists \"${shot}\" but ${png} is missing — run ./scripts/product-shot.sh ${name}"
        ok=0
        continue
      fi
      sbytes="$(stat -c %s "${dir}/${png}")"
      if (( sbytes > MAX_SHOT_BYTES )); then
        err "$name" "${png} is $(( (sbytes + 1023) / 1024 )) KiB, over the $((MAX_SHOT_BYTES / 1024 / 1024)) MiB budget — use a smaller size"
        ok=0
      fi
      if ! grep -qF "](${png})" <<<"$cleaned"; then
        err "$name" "README.md doesn't embed ${png} — a product shot nobody sees isn't a product page"
        ok=0
      fi
    done <"$shotsconf"
  fi

  # 10. Assembly instructions: if the design ships an assembly.conf
  #     (exploded view + BOM, rendered by scripts/assembly.sh), the committed
  #     previews/exploded.png must exist, be embedded in the README, and stay
  #     within the product-shot budget. assembly.conf produces exactly one PNG,
  #     so there is no per-entry loop like animations.conf/shots.conf.
  #     Presence-only — CI regenerates the artifact, the gate checks it is
  #     committed and visible (#69 lesson: a gate that judges content is
  #     fragile; one that checks presence is safe because CI owns the artifact).
  local asmconf="${dir}/assembly.conf"
  if [[ -f "$asmconf" ]]; then
    local apng="previews/exploded.png" abytes
    if [[ ! -f "${dir}/${apng}" ]]; then
      err "$name" "assembly.conf is present but ${apng} is missing — run ./scripts/assembly.sh ${name}"
      ok=0
    else
      abytes="$(stat -c %s "${dir}/${apng}")"
      if (( abytes > MAX_SHOT_BYTES )); then
        err "$name" "${apng} is $(( (abytes + 1023) / 1024 )) KiB, over the $((MAX_SHOT_BYTES / 1024 / 1024)) MiB budget — use a smaller render"
        ok=0
      fi
      if ! grep -qF "](${apng})" <<<"$cleaned"; then
        err "$name" "README.md doesn't embed ${apng} — an exploded view nobody sees isn't a product page"
        ok=0
      fi
    fi
  fi

  # 8. Lineage credit. A derivative's product page documents the delta and
  #    links its base — that link is the only durable form the lineage takes.
  #    The Thingiverse-remix failure this answers is not that people refuse to
  #    credit: it is that the credit lives in a creation-time gesture nobody
  #    can repair afterwards, so a page that ships without it never gets one.
  #    Here the parent list comes from derives.conf, which the design has to
  #    keep accurate anyway (the render gate re-gates every derivative when a
  #    parent changes), so the page and the machinery cannot disagree.
  #    Whether derives.conf is itself well-formed is not asked here — a
  #    retired key or a parent that does not exist is `lineage check`'s
  #    finding, and reporting it twice in two voices helps nobody. This gate
  #    asks one question: does the page link the parents the resolver reports?
  local derives="${dir}/derives.conf"
  if [[ -f "$derives" ]]; then
    local parents parent parent_re
    if ! parents="$(./scripts/lineage.sh parents "$name")"; then
      err "$name" "could not read the lineage of a design that ships a derives.conf — run ./scripts/lineage.sh check"
      ok=0
      parents=""
    fi
    while IFS= read -r parent; do
      [[ -n "$parent" ]] || continue
      # Escape dots so a name containing one can't match a neighbour's path.
      # The terminator class is what keeps the match honest: without it a page
      # linking ../sushi-battleship-tall/ would satisfy a claim to derive from
      # sushi-battleship, crediting the wrong design.
      parent_re="${parent//./\\.}"
      if ! grep -qE "(\]\(|href=\"|href=')\.\./${parent_re}(/|/README\.md)?[\"')# ]" <<<"$cleaned"; then
        err "$name" "README.md never links its base — add a link to ../${parent}/ (derives.conf says this design reuses ${parent}'s geometry; a page that doesn't send the reader there is a remix with the lineage left out)"
        ok=0
      fi
    done <<<"$parents"
  fi

  # 9. Lifestyle (AI-styled) shots and motion clips. Manifest-less on purpose:
  #    the presence of a committed previews/lifestyle-*.png (still) or
  #    previews/lifestyle-*.gif (motion clip, issue #75) IS the trigger,
  #    because an AI restyle cannot be regenerated from source. Both are
  #    cosmetic and assumed geometrically approximate, so the gate never
  #    checks geometry — it checks the DISCLOSURE, in canonical form, that
  #    keeps a cosmetic image off the page passing as a photo (or a working
  #    demo) of the real print: in budget (per format — a still against the
  #    product-shot budget, a clip against the animation-GIF budget), embedded
  #    ONLY as inline markdown images, each carrying an "AI-styled scene" alt
  #    label and a "geometry is approximate" caption directly below it. See
  #    product-shots/SKILL.md, tier 2.
  #
  #    Scope limit, stated honestly: the trigger is the FILENAME. An AI image
  #    committed under any other name (hero.png, scene.png) is invisible to
  #    this gate — a mechanical check cannot tell an AI render from a photo by
  #    its pixels. That masquerade is exactly what the /jane-review and
  #    /drik-review disclosure rules exist to catch; the gate closes the
  #    honest-author failure modes, the reviewers close the adversarial one.
  local lf lrel lbytes budget verdict
  # -iname: case-insensitive, so a stray .PNG can't slip the lowercase glob.
  while IFS= read -r lf; do
    [[ -n "$lf" ]] || continue
    lrel="previews/$(basename "$lf")"
    lbytes="$(stat -c %s "$lf")"
    # Budget per format: a motion clip is judged against the animation-GIF
    # budget (same ceiling as the deterministic turntables it sits beside),
    # a still against the product-shot budget. Lowercased so the .GIF the
    # -iname above admits gets the GIF budget, not the PNG one.
    case "$(basename "$lf" | tr '[:upper:]' '[:lower:]')" in
      *.gif) budget="$MAX_GIF_BYTES" ;;
      *)     budget="$MAX_SHOT_BYTES" ;;
    esac
    if (( lbytes > budget )); then
      err "$name" "${lrel} is $(( (lbytes + 1023) / 1024 )) KiB, over the $((budget / 1024 / 1024)) MiB budget — use a smaller image or clip"
      ok=0
    fi
    verdict="$(lifestyle_disclosure "$lrel" <<<"$cleaned")"
    case "$verdict" in
      OK) ;;
      MISSING_EMBED)
        err "$name" "commits ${lrel} but the README never shows it — embed it as an inline markdown image with the \"AI-styled scene\" label and a \"geometry is approximate\" caption, or drop the file"
        ok=0 ;;
      EXTRA_REF)
        err "$name" "${lrel} is referenced outside an inline markdown image (an <img> tag, a reference-style link, or a bare link) — a lifestyle shot or clip must appear ONLY as \`![AI-styled scene ...](${lrel})\` so an undisclosed copy can't hide beside a disclosed one"
        ok=0 ;;
      MISSING_LABEL)
        err "$name" "an embed of ${lrel} is missing the \"AI-styled scene\" alt label — every inline embed of a lifestyle shot or clip must carry it, so no copy reads as a photo or demo of the print"
        ok=0 ;;
      MISSING_NOTE)
        err "$name" "an embed of ${lrel} has no \"geometry is approximate\" caption directly below it — alt text isn't shown on the rendered page, so add the canonical disclosure line (see product-shots/SKILL.md)"
        ok=0 ;;
    esac
  done < <(find "${dir}/previews" -maxdepth 1 -type f \
             \( -iname 'lifestyle-*.png' -o -iname 'lifestyle-*.gif' \) 2>/dev/null | sort)

  if [[ "$ok" == 1 ]]; then
    echo "ok    ${name}"
  fi
}

# --selftest: prove every lifestyle-disclosure failure still fires. Builds a
# throwaway design tree, points the gate at it via READMEGATE_DESIGNS_DIR, and
# asserts the verdict on a good fixture and one fixture per failure mode. This
# is the half the per-design gate on the real tree cannot cover: no
# lifestyle-*.png or lifestyle-*.gif exists in designs/ yet, so without these
# fixtures the whole check could be weakened or deleted and every gate in the
# repo stays green. Mirrors scripts/lineage.sh selftest and
# scripts/guard-check.sh.
run_selftest() {
  local tmp
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064  # expand $tmp now, when the trap is installed
  trap "rm -rf '$tmp'" RETURN

  # Write a README that passes every OTHER requirement, so the only thing a
  # fixture can trip is the lifestyle check being probed. Echoes the dir path.
  _fixture() {
    local n="$1" d="$tmp/$1"
    mkdir -p "$d/previews"
    : >"$d/previews/contact.png"          # a normal committed preview (req 5)
    {
      printf '# %s\n\n' "$n"
      printf 'A throwaway fixture for the readme-gate selftest.\n\n'
      printf '![contact sheet](previews/contact.png)\n\n'
      printf '## Print settings\n\n- layer height: 0.2 mm\n\n'
      printf '## Parameters\n\n- `wall` — wall thickness (mm)\n'
    } >"$d/README.md"
    printf '%s' "$d"
  }

  local pass=1
  _check() {   # _check <name> <expected-rc> <needle>
    local n="$1" want_rc="$2" needle="$3" out rc=0
    out="$(READMEGATE_DESIGNS_DIR="$tmp" bash "$SELF" "$n" 2>&1)" || rc=$?
    if [[ "$rc" != "$want_rc" ]]; then
      echo "SELFTEST FAIL  ${n}: expected exit ${want_rc}, got ${rc}"
      sed 's/^/    /' <<<"$out"
      pass=0
      return
    fi
    if [[ -n "$needle" ]] && ! grep -qF "$needle" <<<"$out"; then
      echo "SELFTEST FAIL  ${n}: output missing \"${needle}\""
      sed 's/^/    /' <<<"$out"
      pass=0
      return
    fi
    echo "selftest ok    ${n} (${needle:-passes clean})"
  }

  local d
  # The canonical disclosure block a good fixture appends: inline embed with
  # the label, then the "geometry is approximate" caption directly below.
  _disclosed() {   # _disclosed <dir> [png-path]
    local dd="$1" p="${2:-previews/lifestyle-hero.png}"
    {
      printf '\n![AI-styled scene: the fixture on a desk](%s)\n\n' "$p"
      printf '*AI-generated impression for general illustration only — geometry is approximate and may not exactly match the printed part.*\n'
    } >>"$dd/README.md"
  }

  # good: embedded, labeled, canonical caption directly below -> passes
  d="$(_fixture good)"; : >"$d/previews/lifestyle-hero.png"; _disclosed "$d"
  _check good 0 ""

  # good with a markdown title attribute on the embed -> still passes (the
  # title must not hide the embed from the scanner). Regression: fb-title-attr.
  d="$(_fixture good-title)"; : >"$d/previews/lifestyle-hero.png"
  {
    printf '\n![AI-styled scene: on a desk](previews/lifestyle-hero.png "Studio look")\n\n'
    printf '*AI-generated impression — geometry is approximate and may not match the print.*\n'
  } >>"$d/README.md"
  _check good-title 0 ""

  # missing-embed: committed PNG, never referenced -> MISSING_EMBED
  d="$(_fixture missing-embed)"; : >"$d/previews/lifestyle-hero.png"
  _check missing-embed 1 "never shows it"

  # over-budget: proper disclosure, but the PNG exceeds MAX_SHOT_BYTES
  d="$(_fixture over-budget)"
  truncate -s "$((MAX_SHOT_BYTES + 1))" "$d/previews/lifestyle-hero.png"; _disclosed "$d"
  _check over-budget 1 "over the"

  # missing-label: canonical caption present, but no "AI-styled scene" label
  d="$(_fixture missing-label)"; : >"$d/previews/lifestyle-hero.png"
  {
    printf '\n![The fixture on a desk](previews/lifestyle-hero.png)\n\n'
    printf '*AI-generated — geometry is approximate and may not match the print.*\n'
  } >>"$d/README.md"
  _check missing-label 1 "AI-styled scene"

  # missing-note: labeled embed, but the caption below lacks the canonical phrase
  d="$(_fixture missing-note)"; : >"$d/previews/lifestyle-hero.png"
  {
    printf '\n![AI-styled scene: on a desk](previews/lifestyle-hero.png)\n\n'
    printf 'Just some ordinary prose that discloses nothing.\n'
  } >>"$d/README.md"
  _check missing-note 1 "geometry is approximate"

  # negated-note: caption carries the tokens but negates them ("geometry is
  # exact, not approximate") -> the canonical phrase is absent -> MISSING_NOTE.
  # Regression for the semantic-gaming bypass (fo-negated-note).
  d="$(_fixture negated-note)"; : >"$d/previews/lifestyle-hero.png"
  {
    printf '\n![AI-styled scene: on a desk](previews/lifestyle-hero.png)\n\n'
    printf 'A genuine studio photograph, not an AI-generated render, and the geometry is exact, not approximate.\n'
  } >>"$d/README.md"
  _check negated-note 1 "geometry is approximate"

  # decoy: one disclosed embed and one undisclosed embed of the SAME png ->
  # every embed must be disclosed -> MISSING_LABEL. Regression: fo-dup-decoy /
  # disclosure-buried-on-second-embed (the "any embed OK" bypass).
  d="$(_fixture decoy)"; : >"$d/previews/lifestyle-hero.png"
  {
    printf '\n![Studio hero shot](previews/lifestyle-hero.png)\n\n'
    printf 'Straight off the print farm — exactly what you get.\n\n'
    printf '## Reference\n\n![AI-styled scene: on a shelf](previews/lifestyle-hero.png)\n\n'
    printf '*AI-generated — geometry is approximate and may not match the print.*\n'
  } >>"$d/README.md"
  _check decoy 1 "AI-styled scene"

  # html-hero: an <img> hero (undisclosed) beside a compliant markdown decoy ->
  # the path appears outside an inline embed -> EXTRA_REF. Regression:
  # fo-html-hero-md-decoy (HTML embeds are invisible to the disclosure scan).
  d="$(_fixture html-hero)"; : >"$d/previews/lifestyle-hero.png"
  {
    printf '\n<img src="previews/lifestyle-hero.png" width="900" alt="on a desk">\n\n'
    printf 'The finished part, ready to mount.\n\n'
    printf '## Details\n\n![AI-styled scene: on a bench](previews/lifestyle-hero.png)\n\n'
    printf '*AI-generated — geometry is approximate and may not match the print.*\n'
  } >>"$d/README.md"
  _check html-hero 1 "referenced outside an inline markdown image"

  # uppercase-ext: an undisclosed .PNG must still be caught (case-insensitive
  # trigger). Regression: fo-uppercase-ext.
  d="$(_fixture uppercase-ext)"; : >"$d/previews/lifestyle-hero.PNG"
  {
    printf '\n![The fixture in a camper van](previews/lifestyle-hero.PNG)\n\n'
    printf 'Ready to install straight off the bed.\n'
  } >>"$d/README.md"
  _check uppercase-ext 1 "AI-styled scene"

  # --- Motion clips (previews/lifestyle-*.gif, issue #75). Same disclosure
  # machinery, so one fixture per failure mode proves the .gif trigger and the
  # per-format budget dispatch — without these the whole motion extension
  # could be reverted and every gate in the repo would stay green.

  # motion-good: a disclosed clip -> passes
  d="$(_fixture motion-good)"; : >"$d/previews/lifestyle-turntable.gif"
  _disclosed "$d" previews/lifestyle-turntable.gif
  _check motion-good 0 ""

  # motion-missing-embed: committed clip, never referenced -> MISSING_EMBED
  d="$(_fixture motion-missing-embed)"; : >"$d/previews/lifestyle-turntable.gif"
  _check motion-missing-embed 1 "never shows it"

  # motion-over-budget: disclosed, but the clip exceeds MAX_GIF_BYTES
  d="$(_fixture motion-over-budget)"
  truncate -s "$((MAX_GIF_BYTES + 1))" "$d/previews/lifestyle-turntable.gif"
  _disclosed "$d" previews/lifestyle-turntable.gif
  _check motion-over-budget 1 "over the"

  # motion-gif-budget-not-png: a clip sized over the PNG budget but under the
  # GIF budget must PASS — the one fixture that pins the per-format budget
  # dispatch (a regression to a single MAX_SHOT_BYTES check fails here).
  d="$(_fixture motion-gif-budget-not-png)"
  truncate -s "$((MAX_SHOT_BYTES + 1))" "$d/previews/lifestyle-turntable.gif"
  _disclosed "$d" previews/lifestyle-turntable.gif
  _check motion-gif-budget-not-png 0 ""

  # motion-missing-label: caption present, no "AI-styled scene" label
  d="$(_fixture motion-missing-label)"; : >"$d/previews/lifestyle-turntable.gif"
  {
    printf '\n![The shutter in motion](previews/lifestyle-turntable.gif)\n\n'
    printf '*AI-generated — geometry is approximate and may not match the print.*\n'
  } >>"$d/README.md"
  _check motion-missing-label 1 "AI-styled scene"

  # motion-missing-note: labeled clip, caption lacks the canonical phrase
  d="$(_fixture motion-missing-note)"; : >"$d/previews/lifestyle-turntable.gif"
  {
    printf '\n![AI-styled scene: the part in motion](previews/lifestyle-turntable.gif)\n\n'
    printf 'Watch it glide.\n'
  } >>"$d/README.md"
  _check motion-missing-note 1 "geometry is approximate"

  # motion-html-hero: an <img> clip beside a compliant markdown decoy -> EXTRA_REF
  d="$(_fixture motion-html-hero)"; : >"$d/previews/lifestyle-turntable.gif"
  {
    printf '\n<img src="previews/lifestyle-turntable.gif" width="900" alt="in motion">\n\n'
    printf 'See it work.\n\n'
    printf '## Details\n\n![AI-styled scene: in motion](previews/lifestyle-turntable.gif)\n\n'
    printf '*AI-generated — geometry is approximate and may not match the print.*\n'
  } >>"$d/README.md"
  _check motion-html-hero 1 "referenced outside an inline markdown image"

  # motion-uppercase-ext: an undisclosed .GIF must still be caught
  d="$(_fixture motion-uppercase-ext)"; : >"$d/previews/lifestyle-turntable.GIF"
  {
    printf '\n![The part in motion](previews/lifestyle-turntable.GIF)\n\n'
    printf 'Straight off the printer.\n'
  } >>"$d/README.md"
  _check motion-uppercase-ext 1 "AI-styled scene"

  # motion-uppercase-gif-budget: a disclosed .GIF over the PNG budget but
  # under the GIF budget must PASS — pins the lowercasing that routes an
  # uppercase extension to the GIF budget (dropping it would judge this
  # file against MAX_SHOT_BYTES and fail it).
  d="$(_fixture motion-uppercase-gif-budget)"
  truncate -s "$((MAX_SHOT_BYTES + 1))" "$d/previews/lifestyle-turntable.GIF"
  _disclosed "$d" previews/lifestyle-turntable.GIF
  _check motion-uppercase-gif-budget 0 ""

  # --- Assembly (previews/exploded.png, issue #157). A design with an
  # assembly.conf must commit the exploded view, embed it, and stay in budget.
  # No assembly.conf exists in designs/ yet (stage 4), so without these
  # fixtures the gate could be weakened and every other check stays green.

  # asm-good: assembly.conf present, exploded.png embedded in budget -> passes
  d="$(_fixture asm-good)"; : >"$d/previews/exploded.png"
  : >"$d/assembly.conf"
  printf '\n![Exploded view](previews/exploded.png)\n' >>"$d/README.md"
  _check asm-good 0 ""

  # asm-missing-png: assembly.conf present, exploded.png absent -> fails
  d="$(_fixture asm-missing-png)"; : >"$d/assembly.conf"
  _check asm-missing-png 1 "is missing"

  # asm-over-budget: embedded, but exploded.png exceeds MAX_SHOT_BYTES
  d="$(_fixture asm-over-budget)"; : >"$d/assembly.conf"
  truncate -s "$((MAX_SHOT_BYTES + 1))" "$d/previews/exploded.png"
  printf '\n![Exploded view](previews/exploded.png)\n' >>"$d/README.md"
  _check asm-over-budget 1 "over the"

  # asm-unembedded: PNG present and in budget, but not in the README -> fails
  d="$(_fixture asm-unembedded)"
  : >"$d/previews/exploded.png"; : >"$d/assembly.conf"
  _check asm-unembedded 1 "doesn't embed"

  if [[ "$pass" == 1 ]]; then
    echo "ok    readme-gate --selftest: every lifestyle-disclosure and assembly guard fires"
    return 0
  fi
  echo "FAIL  readme-gate --selftest: a guard did not fire"
  return 1
}

if [[ "${1:-}" == "--selftest" ]]; then
  run_selftest || fail=1
elif [[ $# -ge 1 ]]; then
  check_one "$1"
else
  found=0
  for dir in "${ROOT}"/*/; do
    [[ -d "$dir" ]] || continue
    found=1
    check_one "$(basename "$dir")"
  done
  if [[ "$found" -eq 0 ]]; then
    echo "no designs found under ${ROOT}/"
  fi
fi

exit "$fail"
