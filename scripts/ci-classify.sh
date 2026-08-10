#!/usr/bin/env bash
# ci-classify.sh — the single source of truth for "given a PR's changed files,
# what does CI run, and over which designs?".
#
# This is the extracted body of ci.yml's `changes` job. It exists so the
# classification lives in ONE place: ci.yml's `changes` job pipes the diff to
# it, and /preflight runs it (`--local`) to mirror CI exactly. Before this
# split, preflight re-described these rules in English prose and drifted every
# time the classifier moved. Now the workflow and the local mirror share this
# implementation — they cannot disagree.
#
#   Emits, one `key=value` per line on STDOUT (the 12 outputs ci.yml's
#   `changes` job declares — the shape is what `>> "$GITHUB_OUTPUT"` consumes):
#     scad, printcheck_tests, stylelift_tests, lineage_tests,
#     backlog_burn_tests, telemetry_tests, ci_gates_tests, styles, gate,
#     gate_designs, regen, regen_designs
#   All diagnostics go to STDERR so STDOUT stays a clean key=value stream.
#
# Usage:
#   ./scripts/ci-classify.sh < changed-files        # one path per line on stdin
#   ./scripts/ci-classify.sh --local [--base <ref>] # compute the diff itself
#   ./scripts/ci-classify.sh --selftest             # pin the classification
#
# Event mode: a non-empty CI_CLASSIFY_EVENT that is not "pull_request" means a
# default-branch push (or any non-PR trigger) — CI runs and gates EVERYTHING,
# and the changed-file list is ignored. Empty/unset (the local default) and
# "pull_request" both mean diff mode: classify the supplied paths. This is the
# exact `[ "$GITHUB_EVENT_NAME" != "pull_request" ]` test ci.yml used, with the
# one difference that an unset event means "local, diff mode" rather than ALL.
set -euo pipefail

DEFAULT_BRANCH="${CI_CLASSIFY_BASE:-main}"

# The repo holds every locally-run script to the stock-macOS Bash 3.2 floor
# (scripts/check.sh runs this one, and shot-spec.sh documents the same rule), so
# no Bash 4 associative arrays. The three "sets" this classifier needs (design
# names, directly-touched names, touched styles) are newline-delimited strings
# of kebab-case names that never contain a space or newline, with a pure-Bash
# membership test and a deterministic (sorted) space-join for the output list.
NL=$'\n'
_set_has() { case "$NL$1$NL" in *"$NL$2$NL"*) return 0 ;; *) return 1 ;; esac; }
_join() { printf '%s' "$1" | sed '/^$/d' | sort | tr "$NL" ' ' | sed 's/ *$//'; }

# --- classify: the shared decision -------------------------------------------
# Reads the changed-file list from stdin (one path per line), reads the working
# tree for existence/ARCHIVED/style.conf facts, and prints the 12 outputs.
classify() {
  local event="${CI_CLASSIFY_EVENT:-}"
  local scad=false ptests=false stests=false ltests=false styles=false
  local bbtests=false tmtests=false cgtests=false
  local gate=false designs=""
  local regen=false regen_designs=""

  if [ -n "$event" ] && [ "$event" != "pull_request" ]; then
    # Default-branch push (or any non-PR trigger): run everything, gate and
    # regenerate every design.
    scad=true; ptests=true; stests=true; ltests=true; styles=true
    bbtests=true; tmtests=true; cgtests=true
    gate=true; designs=ALL
    regen=true; regen_designs=ALL
  else
    local files=()
    local line
    # `|| [ -n "$line" ]` so a final path with no trailing newline is not
    # silently dropped (that would fail open — a changed design left ungated).
    while IFS= read -r line || [ -n "$line" ]; do
      [ -n "$line" ] && files+=("$line")
    done
    echo "changed files:" >&2
    # Guard the empty-array expansion: "${files[@]}" on an empty array aborts
    # under `set -u` on Bash < 4.4 (the 3.2 floor included). A clean tree at the
    # merge base reaches this on a `--local` run.
    if [ "${#files[@]}" -gt 0 ]; then
      printf '  %s\n' "${files[@]}" >&2
    else
      echo "  (none)" >&2
    fi

    # Two infra tiers, where there used to be one. The old single `infra`
    # treated every file under scripts/ as able to move any design's geometry,
    # so a gallery.sh or readme-gate.sh edit re-gated, re-rendered and re-shot
    # the entire catalog. What a change can actually reach:
    #
    #   geo_infra — can change an exported STL or a gate verdict, so every
    #   design re-gates (designs=ALL): the shared libraries, the two scripts
    #   the render gate executes (gate.sh, and lineage.sh, which it sources),
    #   THIS script (ci-classify.sh — it decides the gate scope itself, so a
    #   bug here can under-scope verification; it must re-gate everything,
    #   exactly as editing the inline classifier in ci.yml used to before the
    #   logic was extracted here), printcheck (the analyzer that judges every
    #   STL), tools/lineage (the resolver that decides which designs a change
    #   reaches at all — edit it and every blast radius can move, including the
    #   one this step computes), this workflow, and .github/actions (the
    #   composite action selecting the OpenSCAD build five jobs render with).
    #
    #   soft_infra — everything else under scripts/, plus site/ and
    #   vercel.json, tools/photoshot, tools/backlog-burn, printer.conf,
    #   telemetry/ and tools/telemetry, people/ (the team registry, #123 —
    #   read only by the site build, it can never move a mesh or a gate
    #   verdict), and the non-ci.yml workflows: cannot
    #   move geometry, but three of the five required contexts are geometry
    #   jobs and a job skipped via `if:` does NOT satisfy a required context
    #   (PR #50) — so the jobs must RUN. gate=true with an EMPTY design list is
    #   render-gate's "run but gate nothing" mode.
    #
    # regen scope (regen_all) is decoupled from gate scope for the same reason:
    # gate.sh and printcheck change verdicts, not pixels; the preview/GIF/
    # product-shot generators change pixels, not verdicts.
    local geo_infra=false soft_infra=false regen_all=false
    local names="" touched="" touched_styles=""
    local f n s
    # The empty-array guard again — see the printf above.
    if [ "${#files[@]}" -gt 0 ]; then
    for f in "${files[@]}"; do
      case "$f" in
        lib/*|scripts/gate.sh|scripts/lineage.sh|scripts/ci-classify.sh|\
        tools/printcheck/*|tools/lineage/*|\
        .github/workflows/ci.yml|.github/actions/*)
          # This alternation is matched before the scripts/* soft-infra case
          # below, so ci-classify.sh lands here (gate ALL), not there.
          geo_infra=true ;;
        scripts/*|site/*|vercel.json|tools/photoshot/*|\
        tools/backlog-burn/*|.github/backlog-burn.conf|\
        .github/workflows/*|printer.conf|\
        telemetry/*|tools/telemetry/*|people/*)
          soft_infra=true ;;
      esac
      case "$f" in
        # Everything a committed preview, GIF, product shot or the gallery is
        # derived from, beyond the design's own directory. gate.sh and
        # printcheck are deliberately absent: they judge STLs, not pixels.
        lib/*|tools/lineage/*|tools/photoshot/*|\
        .github/workflows/ci.yml|.github/actions/*|\
        scripts/render.sh|scripts/animate.sh|\
        scripts/product-shot.sh|scripts/gallery.sh|\
        scripts/product-page.sh|scripts/preview-budget.sh|\
        scripts/regen-stamp.sh|scripts/lineage.sh|\
        scripts/assembly.sh)
          regen_all=true ;;
      esac
      case "$f" in
        styles/*|tools/stylelift/*|lib/*|scripts/style-*.sh|\
        designs/*/style.conf|.github/workflows/ci.yml)
          styles=true ;;
      esac
      case "$f" in
        # A style's tokens compile into every design that declares it, so
        # editing style.json/style.scad moves that design's geometry. Remember
        # which styles moved and map them back to designs after the loop.
        styles/*)
          s=${f#styles/}; s=${s%%/*}
          _set_has "$touched_styles" "$s" || touched_styles="${touched_styles:+$touched_styles$NL}$s" ;;
      esac
      case "$f" in
        designs/*/*)
          n=${f#designs/}; n=${n%%/*}
          # skip names whose entry point no longer exists. `touched` records
          # designs the PR edited DIRECTLY (their own files), as distinct from
          # ones pulled in later by blast radius or a shared style — the
          # archived filter below needs that split.
          if [ -f "designs/$n/$n.scad" ]; then
            _set_has "$names" "$n"   || names="${names:+$names$NL}$n"
            _set_has "$touched" "$n" || touched="${touched:+$touched$NL}$n"
          fi ;;
      esac
      case "$f" in
        tools/printcheck/*|.github/workflows/ci.yml) ptests=true ;;
      esac
      case "$f" in
        tools/stylelift/*|.github/workflows/ci.yml) stests=true ;;
      esac
      case "$f" in
        tools/lineage/*|.github/workflows/ci.yml) ltests=true ;;
      esac
      case "$f" in
        tools/backlog-burn/*|.github/backlog-burn.conf|\
        .github/workflows/ci.yml) bbtests=true ;;
      esac
      case "$f" in
        tools/telemetry/*|.github/workflows/ci.yml) tmtests=true ;;
      esac
      case "$f" in
        # The smart-ci selector's own unit tests. The registry is data the
        # selector reads, so a registry edit re-runs them too.
        tools/ci-gates/*|.github/ci-gates/*|\
        .github/workflows/ci.yml) cgtests=true ;;
      esac
      case "$f" in
        # tools/lineage is here and tools/printcheck is not: check.sh RUNS the
        # lineage resolver and fails on what it reports, while printcheck only
        # reads exported STLs after the fact. site/, vercel.json and
        # tools/photoshot are here for the required-context reason (this job
        # must RUN for such a PR to be mergeable), not because they move
        # geometry.
        designs/*|lib/*|templates/*|scripts/*|styles/*|site/*|\
        vercel.json|printer.conf|tools/lineage/*|tools/photoshot/*|\
        tools/backlog-burn/*|.github/backlog-burn.conf|\
        telemetry/*|tools/telemetry/*|people/*|\
        .github/workflows/*|.github/actions/*)
          scad=true ;;
      esac
    done
    fi  # end empty-files guard

    # The other direction: a design that declares a style the PR touched gets
    # gated as if the design itself had changed.
    for conf in designs/*/style.conf; do
      [ -f "$conf" ] || continue
      n=${conf#designs/}; n=${n%%/*}
      [ -f "designs/$n/$n.scad" ] || continue
      s="$(grep -vE '^[[:space:]]*(#|$)' "$conf" | head -1 \
           | tr -d '[:space:]' || true)"
      if [ -n "$s" ] && _set_has "$touched_styles" "$s"; then
        _set_has "$names" "$n" || names="${names:+$names$NL}$n"
      fi
    done

    # Blast radius. A derivative includes its parent's .scad and redefines part
    # of it, so a change under designs/<parent>/ moves the derivative's
    # geometry with no file inside the derivative's own directory in the diff.
    # Ask the resolver for the descendants.
    #
    # Unguarded, deliberately (matching ci.yml): the resolver exits non-zero on
    # a cycle or an unparsable derives.conf; under `set -euo pipefail` that
    # fails the step, which is the point. A `|| true` here would fail open.
    # $geo_infra already means designs=ALL, and an empty names would expand to
    # zero arguments the resolver rejects — so both are skipped.
    if ! $geo_infra && [ -n "$names" ]; then
      local radius
      # Unquoted expansion is intentional: the names are space-free kebab-case,
      # so word-splitting hands the resolver one argument per design.
      # shellcheck disable=SC2046
      radius="$(./scripts/lineage.sh blast-radius $(_join "$names"))"
      while IFS= read -r n; do
        if [ -n "$n" ] && [ -f "designs/$n/$n.scad" ]; then
          _set_has "$names" "$n" || names="${names:+$names$NL}$n"
        fi
      done <<<"$radius"
    fi

    # A changed design that claims a style has to be re-checked against it.
    while IFS= read -r n; do
      [ -n "$n" ] || continue
      if [ -f "designs/$n/style.conf" ]; then styles=true; fi
    done <<<"$names"

    # Archived designs (designs/<n>/ARCHIVED) are frozen at v0.1. Gate them
    # ONLY when the PR edits their own files (a revival), never when pulled in
    # indirectly by blast radius or a shared style. Mirrors the ALL skip in
    # gate.sh, regen and geo-diff. Rebuild the set from a snapshot (also
    # dedupes) rather than removing in place.
    local kept=""
    while IFS= read -r n; do
      [ -n "$n" ] || continue
      if [ -f "designs/$n/ARCHIVED" ] && ! _set_has "$touched" "$n"; then
        continue
      fi
      _set_has "$kept" "$n" || kept="${kept:+$kept$NL}$n"
    done <<<"$names"
    names="$kept"

    if $geo_infra; then
      gate=true; designs=ALL
      # A geo-infra change gates every design THROUGH printcheck, so the
      # analyzer is on the critical path and its own tests belong in the run.
      ptests=true
    elif [ -n "$names" ]; then
      gate=true; designs="$(_join "$names")"
    fi
    # Required contexts must actually RUN (PR #50): a scripts/- or site/-only
    # PR must still report gate and printcheck tests, so soft_infra widens both
    # to "run" without narrowing any design list already set above.
    if $soft_infra; then
      gate=true; ptests=true
    fi
    # regen scope, decoupled from gate scope.
    if $regen_all; then
      regen=true; regen_designs=ALL
    elif [ -n "$names" ]; then
      regen=true; regen_designs="$(_join "$names")"
    fi
  fi

  echo "scad=$scad"
  echo "printcheck_tests=$ptests"
  echo "stylelift_tests=$stests"
  echo "lineage_tests=$ltests"
  echo "backlog_burn_tests=$bbtests"
  echo "telemetry_tests=$tmtests"
  echo "ci_gates_tests=$cgtests"
  echo "styles=$styles"
  echo "gate=$gate"
  echo "gate_designs=$designs"
  echo "regen=$regen"
  echo "regen_designs=$regen_designs"
}

# --- --local: compute the changed-file list the way /preflight scopes --------
# Merge-base diff against the default branch, plus untracked work, deduped. This
# is the diff /preflight's §1 describes; classify() then makes it identical to
# CI's decision.
local_changed_files() {
  local base merge
  base="origin/${DEFAULT_BRANCH}"
  if ! git rev-parse --verify --quiet "$base" >/dev/null; then
    base="$DEFAULT_BRANCH"
  fi
  # Fail loud rather than open: a missing merge base (default branch not
  # fetched, or no common ancestor) with `|| true` would leave $merge empty,
  # skip the diff below, and emit only untracked files — silently dropping
  # every tracked change and under-scoping the local mirror. Erroring tells the
  # caller to fetch instead.
  if ! merge="$(git merge-base "$base" HEAD 2>/dev/null)"; then
    echo "ci-classify: no merge base between $base and HEAD — fetch the default branch (e.g. 'git fetch origin ${DEFAULT_BRANCH}') and retry, or pass --base <ref>" >&2
    return 1
  fi
  # `git diff <merge>` compares the merge base to the WORKING TREE, so it
  # already covers committed-since-base, staged and unstaged tracked changes in
  # one pass — only untracked files need a second command. Both emit one clean
  # path per line, so there is no `git status --porcelain` text to parse (its
  # rename records — `R old -> new` — and quoted paths would mis-scope).
  # --no-renames lists a rename's old and new path separately; over-listing the
  # vanished old path is harmless (classify drops any name whose entry .scad no
  # longer exists), whereas missing the new one would under-scope.
  {
    git diff --name-only --no-renames "$merge"
    git ls-files --others --exclude-standard
  } | sort -u | sed '/^$/d'
}

# --- --selftest: negative controls that pin the classification ---------------
selftest() {
  local fails=0
  # Run classify on an explicit file list in diff mode, regardless of the
  # caller's environment.
  run() {
    printf '%s\n' "$@" | env -u CI_CLASSIFY_EVENT bash "$0" 2>/dev/null
  }
  check() { # label | out | expected-lines...
    local label="$1" out="$2"; shift 2
    local e
    for e in "$@"; do
      if ! grep -qxF "$e" <<<"$out"; then
        echo "FAIL [$label]: expected '$e' in output" >&2
        printf '%s\n' "$out" | sed 's/^/    /' >&2
        fails=$((fails + 1))
        return
      fi
    done
    echo "ok   [$label]"
  }

  local out
  # 1. Docs/skills only — matches no case, so nothing runs or gates.
  out="$(run "docs/derivative-designs.md" ".claude/skills/preflight/SKILL.md")"
  check "docs-only" "$out" \
    "scad=false" "gate=false" "gate_designs=" "regen=false" "styles=false" \
    "printcheck_tests=false"

  # 2. printcheck is geo-infra (it judges every STL), so a printcheck change
  #    gates ALL designs and forces its own tests — but moves no pixels
  #    (regen=false) and no source check.sh reads (scad=false).
  out="$(run "tools/printcheck/src/printcheck/foo.py")"
  check "printcheck-only" "$out" \
    "printcheck_tests=true" "gate=true" "gate_designs=ALL" "scad=false" \
    "regen=false" "stylelift_tests=false"

  # 3. geo-infra (a lib change) — gates ALL, forces printcheck tests, is
  #    regen-ALL and a style-gate trigger.
  out="$(run "lib/printability.scad")"
  check "geo-infra" "$out" \
    "gate=true" "gate_designs=ALL" "printcheck_tests=true" "scad=true" \
    "styles=true" "regen=true" "regen_designs=ALL"

  # 4. soft-infra (a non-geo script) — "run but gate nothing" and forces
  #    printcheck tests, without a design list.
  out="$(run "scripts/readme-gate.sh")"
  check "soft-infra" "$out" \
    "gate=true" "gate_designs=" "printcheck_tests=true" "scad=true"

  # 4a. people/ (the team registry, #123) is soft-infra for the same reason as
  #     telemetry/: only the site build reads it, but a people-only PR must
  #     still RUN the required contexts to be mergeable (the ci.yml CAUTION).
  out="$(run "people/vera.md")"
  check "people-only" "$out" \
    "gate=true" "gate_designs=" "printcheck_tests=true" "scad=true" \
    "regen=false"

  # 4b. This script IS the scope decider, so editing it must gate ALL (geo-infra),
  #     not fall through to the scripts/* soft-infra "gate nothing" — otherwise a
  #     mis-scoping change to the classifier could ship unverified. Regression
  #     guard for the ci.yml→ci-classify.sh extraction.
  out="$(run "scripts/ci-classify.sh")"
  check "self-is-geo-infra" "$out" \
    "gate=true" "gate_designs=ALL" "printcheck_tests=true" "scad=true"

  # 4c. assembly.sh is a generator producing committed artifacts (exploded
  #     views + ASSEMBLY.md), so editing it must regen ALL — a stale exploded
  #     view is the #69 failure mode the stamp exists to prevent.
  out="$(run "scripts/assembly.sh")"
  check "assembly-script" "$out" "regen=true" "regen_designs=ALL"

  # 5. A design path whose entry point does not exist is dropped — the guard
  #    against gating a deleted/renamed design under the wrong name.
  out="$(run "designs/__nonexistent__/__nonexistent__.scad")"
  check "missing-entry" "$out" \
    "gate=false" "gate_designs=" "regen=false"

  # 6. A real, non-archived design is gated by name (blast radius included).
  local real=""
  local d
  for d in designs/*/; do
    n=${d#designs/}; n=${n%/}
    if [ -f "designs/$n/$n.scad" ] && [ ! -f "designs/$n/ARCHIVED" ]; then
      real="$n"; break
    fi
  done
  if [ -n "$real" ]; then
    out="$(run "designs/$real/$real.scad")"
    if grep -qxF "gate=true" <<<"$out" \
       && grep -qE "^gate_designs=([^=]* )?${real}( |\$)" <<<"$out"; then
      echo "ok   [real-design=$real]"
    else
      echo "FAIL [real-design=$real]: expected gate=true and $real in gate_designs" >&2
      printf '%s\n' "$out" | sed 's/^/    /' >&2
      fails=$((fails + 1))
    fi
  else
    echo "ok   [real-design] (skipped — no non-archived design in catalog)"
  fi

  # 7. An archived design pulled in only by a style it declares is NOT gated.
  #    Synthesized against the live catalog: find an archived design whose
  #    style.conf names a style, touch that style, and assert the design is
  #    absent from gate_designs (touched=empty → archived filter drops it).
  local arch_style_design="" arch_style=""
  for d in designs/*/; do
    n=${d#designs/}; n=${n%/}
    [ -f "designs/$n/ARCHIVED" ] || continue
    [ -f "designs/$n/style.conf" ] || continue
    s="$(grep -vE '^[[:space:]]*(#|$)' "designs/$n/style.conf" | head -1 \
         | tr -d '[:space:]' || true)"
    [ -n "$s" ] || continue
    arch_style_design="$n"; arch_style="$s"; break
  done
  if [ -n "$arch_style_design" ]; then
    out="$(run "styles/$arch_style/style.json")"
    if grep -qE "^gate_designs=([^=]* )?${arch_style_design}( |\$)" <<<"$out"; then
      echo "FAIL [archived-via-style=$arch_style_design]: archived design was gated indirectly" >&2
      printf '%s\n' "$out" | sed 's/^/    /' >&2
      fails=$((fails + 1))
    else
      echo "ok   [archived-via-style=$arch_style_design]"
    fi
  else
    echo "ok   [archived-via-style] (skipped — no archived design declares a style)"
  fi

  if [ "$fails" -ne 0 ]; then
    echo "ci-classify selftest: $fails case(s) failed" >&2
    return 1
  fi
  echo "ci-classify selftest: all cases passed"
}

# Compute the local file list FIRST and bail on failure, so a merge-base error
# (local_changed_files → non-zero) never reaches classify and emits a
# misleading all-false classification on stdout.
classify_local() {
  local changed
  changed="$(local_changed_files)" || return 1
  printf '%s\n' "$changed" | classify
}

main() {
  case "${1:-}" in
    --selftest) selftest ;;
    --local)
      shift
      if [ "${1:-}" = "--base" ]; then DEFAULT_BRANCH="${2:?--base needs a ref}"; fi
      classify_local ;;
    --base)
      DEFAULT_BRANCH="${2:?--base needs a ref}"
      classify_local ;;
    "" ) classify ;;
    * ) echo "usage: $0 [--local [--base <ref>]] | --selftest   (default: read paths on stdin)" >&2; exit 2 ;;
  esac
}

main "$@"
