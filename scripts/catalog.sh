#!/usr/bin/env bash
# catalog.sh — the design-catalog category signal (issue #374).
#
#   ./scripts/catalog.sh check       # every design lands in exactly one group,
#                                    # every declared category is in the closed
#                                    # vocabulary, and the NUGGS cross-check holds
#   ./scripts/catalog.sh order       # emit the GROUPED, lineage-ordered design
#                                    # sequence both catalog surfaces consume
#   ./scripts/catalog.sh groups      # emit "<slug> \t <label> \t <blurb>" per
#                                    # group (the heading + optional promise line)
#   ./scripts/catalog.sh --selftest  # pin the parser + the closed-vocabulary
#                                    # refusal + the NUGGS cross-check with
#                                    # negative controls (run by check.sh)
#
# The one derivation the README gallery (scripts/gallery.sh) and the site index
# (site/lib/catalog.mjs) both consume, so the two surfaces cannot disagree about
# which group a design is in — the same "one authority, cross-checked" shape the
# lineage resolver uses (issue #55). The grouping signal is minimal committed
# source, never a hand-committed grouped table (charter N1):
#
#   - the closed vocabulary + display order live in designs/categories.conf
#     ("<slug> | <label>", order = display order);
#   - NUGGS is DERIVED — any design named "nuggs" or "nuggs-*" is in the nuggs
#     group and carries no catalog.conf; it is cross-checked against the
#     lib/nuggs-coupling.scad include (a non-NUGGS design that includes the
#     coupling is mis-grouped and fails here);
#   - every other design declares `category: <slug>` in designs/<name>/catalog.conf.
#
# `order` re-uses `./scripts/lineage.sh order` for within-group ordering and
# nesting, and buckets by the ROOT ancestor's group so a derivative never lands
# in a different group from the design it nests under (which would split the
# nesting across a group boundary).
set -euo pipefail
cd "$(dirname "$0")/.."

NL=$'\n'
ROOT="."

# --root <dir> lets the selftest run the whole derivation against a throwaway
# tree; every path below is resolved under $ROOT so the real functions — not a
# reimplementation — are what the selftest exercises.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    *) break ;;
  esac
done

DESIGNS_DIR="${ROOT%/}/designs"
VOCAB_FILE="${DESIGNS_DIR}/categories.conf"

err() { echo "catalog: $*" >&2; }

# Pure-Bash set membership over a newline-delimited set (ci-classify.sh idiom).
_set_has() { case "$NL$1$NL" in *"$NL$2$NL"*) return 0 ;; *) return 1 ;; esac; }

# --- vocabulary --------------------------------------------------------------
# Populate VOCAB_ORDER (slugs, in display order), LABEL[slug], and VOCAB_SET
# (the newline-delimited closed set for membership tests).
declare -a VOCAB_ORDER=()
declare -A LABEL=()
declare -A BLURB=()
VOCAB_SET=""

# Trim leading/trailing whitespace from $1.
_trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

load_vocab() {
  VOCAB_ORDER=(); LABEL=(); BLURB=(); VOCAB_SET=""
  if [[ ! -f "$VOCAB_FILE" ]]; then
    err "vocabulary file ${VOCAB_FILE} is missing"
    return 1
  fi
  # Each line is "<slug> | <label>" or "<slug> | <label> | <blurb>": the blurb
  # is an optional promise line shown under the group's heading. Split on the
  # FIRST two pipes explicitly — a naive "everything after the first |" would
  # glue the blurb onto the label.
  local line slug rest label blurb
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"                       # drop trailing/whole-line comments
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" != *"|"* ]]; then
      err "${VOCAB_FILE}: line '${line}' is not '<slug> | <label>[ | <blurb>]'"
      return 1
    fi
    slug="$(printf '%s' "${line%%|*}" | tr -d '[:space:]')"
    rest="${line#*|}"                        # everything after the first |
    if [[ "$rest" == *"|"* ]]; then
      label="$(_trim "${rest%%|*}")"; blurb="$(_trim "${rest#*|}")"
    else
      label="$(_trim "$rest")"; blurb=""
    fi
    if [[ -z "$slug" || -z "$label" ]]; then
      err "${VOCAB_FILE}: line '${line}' has an empty slug or label"
      return 1
    fi
    if _set_has "$VOCAB_SET" "$slug"; then
      err "${VOCAB_FILE}: duplicate category slug '${slug}'"
      return 1
    fi
    VOCAB_ORDER+=("$slug")
    LABEL["$slug"]="$label"
    BLURB["$slug"]="$blurb"
    VOCAB_SET="${VOCAB_SET:+$VOCAB_SET$NL}$slug"
  done <"$VOCAB_FILE"
  if (( ${#VOCAB_ORDER[@]} == 0 )); then
    err "${VOCAB_FILE}: no categories defined"
    return 1
  fi
}

# Emit one line per group in display order: "<slug> \t <label> \t <blurb>"
# (blurb may be empty). Both surfaces read this for the group headings.
catalog_groups() {
  load_vocab || return 1
  local slug
  for slug in "${VOCAB_ORDER[@]}"; do
    printf '%s\t%s\t%s\n' "$slug" "${LABEL[$slug]}" "${BLURB[$slug]:-}"
  done
}

# --- per-design signals ------------------------------------------------------
is_nuggs() { case "$1" in nuggs|nuggs-*) return 0 ;; *) return 1 ;; esac; }

# The `category:` value from designs/<name>/catalog.conf, or empty. Comments and
# blanks ignored, first colon splits key/value (site/lib team.mjs idiom).
read_category() {
  local conf="${DESIGNS_DIR}/$1/catalog.conf"
  [[ -f "$conf" ]] || return 0
  grep -vE '^[[:space:]]*(#|$)' "$conf" \
    | grep -E '^[[:space:]]*category:' \
    | head -1 \
    | sed -E 's/^[[:space:]]*category:[[:space:]]*//; s/[[:space:]]*$//' \
    || true
}

# Does the design's entry .scad pull in the NUGGS coupling standard?
includes_coupling() {
  local entry="${DESIGNS_DIR}/$1/$1.scad"
  [[ -f "$entry" ]] || return 1
  grep -qE '(include|use)[[:space:]]*<[^>]*nuggs-coupling\.scad>' "$entry"
}

# Resolve every design's group into the GROUP map. Returns non-zero and prints
# one line per problem — the refusals that make the signal a gate, not a comment.
declare -A GROUP=()
resolve_groups() {
  GROUP=()
  local fails=0 d name cat
  for d in "${DESIGNS_DIR}"/*/; do
    [[ -d "$d" ]] || continue
    name="$(basename "$d")"
    [[ -f "${DESIGNS_DIR}/${name}/${name}.scad" ]] || continue

    if is_nuggs "$name"; then
      # NUGGS is derived; a catalog.conf here would be a second, drifting source
      # of truth for a group the name already decides.
      cat="$(read_category "$name")"
      if [[ -n "$cat" ]]; then
        err "designs/${name}: NUGGS designs are grouped by name, not by catalog.conf — remove the category key"
        fails=$((fails + 1))
      fi
      GROUP["$name"]="nuggs"
      continue
    fi

    # A non-NUGGS design that includes the coupling is mis-grouped: it belongs
    # in the NUGGS collection but is not named for it. (#374 cross-check.)
    if includes_coupling "$name"; then
      err "designs/${name}: includes lib/nuggs-coupling.scad but is not named nuggs-* — a NUGGS module must carry the nuggs- prefix"
      fails=$((fails + 1))
    fi

    cat="$(read_category "$name")"
    if [[ -z "$cat" ]]; then
      err "designs/${name}: no 'category:' in designs/${name}/catalog.conf (see ${VOCAB_FILE})"
      fails=$((fails + 1))
      continue
    fi
    if [[ "$cat" == "nuggs" ]]; then
      err "designs/${name}: 'nuggs' is a derived group; a design cannot declare category: nuggs"
      fails=$((fails + 1))
      continue
    fi
    if ! _set_has "$VOCAB_SET" "$cat"; then
      err "designs/${name}: category '${cat}' is not in the closed vocabulary (${VOCAB_FILE}: ${VOCAB_ORDER[*]})"
      fails=$((fails + 1))
      continue
    fi
    GROUP["$name"]="$cat"
  done
  return "$fails"
}

# `./scripts/lineage.sh order`, optionally scoped to $ROOT for the selftest.
lineage_order() {
  if [[ "$ROOT" == "." ]]; then
    ./scripts/lineage.sh order
  else
    ./scripts/lineage.sh order --root "$ROOT"
  fi
}

# Walk lineage order and, per design, its bucket = the group of its ROOT
# ancestor (depth 0). Asserts a derivative's own group matches its root's, so a
# group boundary can never split a parent from its nested child. Emits (or, in
# check mode, only validates) `slug \t label \t depth \t name \t parent`.
declare -a ORDER_LINES=()
build_order() {
  ORDER_LINES=()
  local order
  if ! order="$(lineage_order)"; then
    err "./scripts/lineage.sh order failed — refusing to group a catalog with the lineage missing"
    return 1
  fi

  # Census cross-check: the designs lineage knows about must be exactly the
  # designs on disk (the gallery.sh guard, kept here at the authority).
  local from_order from_glob d
  from_order="$(awk -F'\t' 'NF { print $2 }' <<<"$order" | sort)"
  from_glob="$(for d in "${DESIGNS_DIR}"/*/; do
      d="$(basename "$d")"
      [[ -f "${DESIGNS_DIR}/${d}/${d}.scad" ]] || continue
      echo "$d"
    done | sort)"
  if [[ "$from_order" != "$from_glob" ]]; then
    err "lineage order and ${DESIGNS_DIR}/*/ disagree about which designs exist"
    diff <(printf '%s\n' "$from_glob") <(printf '%s\n' "$from_order") >&2 || true
    return 1
  fi

  local fails=0 depth name parent root_group g
  declare -A BUCKET=()
  root_group=""
  while IFS=$'\t' read -r depth name parent; do
    [[ -n "$name" ]] || continue
    g="${GROUP[$name]:-}"
    if [[ -z "$g" ]]; then
      err "designs/${name}: no resolved group (should have failed check)"
      fails=$((fails + 1)); continue
    fi
    if (( depth == 0 )); then
      root_group="$g"
    elif [[ "$g" != "$root_group" ]]; then
      err "designs/${name}: category '${g}' differs from its lineage root's group '${root_group}' — a derivative must share its parent's group"
      fails=$((fails + 1))
    fi
    BUCKET["$root_group"]="${BUCKET[$root_group]:-}${depth}"$'\t'"${name}"$'\t'"${parent}"$'\n'
  done <<<"$order"
  (( fails == 0 )) || return "$fails"

  # Emit groups in vocabulary (display) order; within each, lineage order.
  local slug line
  for slug in "${VOCAB_ORDER[@]}"; do
    [[ -n "${BUCKET[$slug]:-}" ]] || continue
    while IFS= read -r line; do
      [[ -n "$line" ]] || continue
      ORDER_LINES+=("${slug}"$'\t'"${LABEL[$slug]}"$'\t'"${line}")
    done <<<"${BUCKET[$slug]}"
  done
}

catalog_check() {
  load_vocab || return 1
  local rc=0
  resolve_groups || rc=$?
  # build_order re-validates the derivative-vs-root-group invariant and the
  # census; run it so `check` covers everything `order` relies on.
  build_order || rc=$?
  if (( rc != 0 )); then
    err "catalog check failed"
    return 1
  fi
  echo "catalog: ${#GROUP[@]} designs, all in the closed vocabulary (${VOCAB_ORDER[*]})"
}

catalog_order() {
  load_vocab || return 1
  resolve_groups || { err "catalog order: category validation failed — run ./scripts/catalog.sh check"; return 1; }
  build_order || { err "catalog order: grouping failed"; return 1; }
  local line
  for line in "${ORDER_LINES[@]}"; do
    printf '%s\n' "$line"
  done
}

# --- selftest ----------------------------------------------------------------
# A throwaway tree exercised through the very functions the gate runs. Negative
# controls are the point: a gate that has never refused a bad category looks
# exactly like one that cannot.
catalog_selftest() {
  local tmp fails=0
  tmp="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap "rm -rf '$tmp'" RETURN

  mkdir -p "$tmp/designs"
  cp "$VOCAB_FILE" "$tmp/designs/categories.conf"

  _mk() {  # <name> [category]
    local n="$1" cat="${2:-}"
    mkdir -p "$tmp/designs/$n"
    printf '// %s fixture\n' "$n" >"$tmp/designs/$n/$n.scad"
    printf '# %s\n\nThe %s design.\n' "$n" "$n" >"$tmp/designs/$n/README.md"
    [[ -n "$cat" ]] && printf 'category: %s\n' "$cat" >"$tmp/designs/$n/catalog.conf"
  }
  _run() { ./scripts/catalog.sh --root "$tmp" "$@"; }

  # ---- positive: a clean tree checks and orders correctly -------------------
  rm -rf "$tmp/designs"/*/ 2>/dev/null || true
  _mk zeta everyday-functional
  _mk alpha compliant-mechanisms
  _mk nuggs-thing            # NUGGS by prefix, no catalog.conf
  if _run check >/dev/null 2>&1; then
    echo "ok    selftest: a clean tree passes check"
  else
    echo "FAIL  selftest: a clean tree was rejected by check"; fails=$((fails + 1))
  fi
  # order groups by vocabulary order (nuggs first), not alphabetically.
  local ord
  if ord="$(_run order 2>/dev/null)"; then
    local names; names="$(awk -F'\t' '{print $4}' <<<"$ord" | tr '\n' ' ')"
    if [[ "$names" == "nuggs-thing alpha zeta "* ]]; then
      echo "ok    selftest: order groups by category (nuggs, compliant, everyday), not name"
    else
      echo "FAIL  selftest: order sequence was '${names}' (expected nuggs-thing, alpha, zeta)"; fails=$((fails + 1))
    fi
  else
    echo "FAIL  selftest: order failed on a clean tree"; fails=$((fails + 1))
  fi

  # groups emits the optional promise blurb for the promise headings and nothing
  # for the navigational ones — and, the parser-trap Vera flagged, the label
  # must NOT have absorbed the blurb (a naive "after the first |" would).
  local grps
  if grps="$(_run groups 2>/dev/null)"; then
    local sf_blurb nuggs_blurb sf_label
    sf_blurb="$(awk -F'\t' '$1=="support-free"{print $3}' <<<"$grps")"
    nuggs_blurb="$(awk -F'\t' '$1=="nuggs"{print $3}' <<<"$grps")"
    sf_label="$(awk -F'\t' '$1=="support-free"{print $2}' <<<"$grps")"
    if [[ -n "$sf_blurb" && -z "$nuggs_blurb" && "$sf_label" != *"|"* && "$sf_label" != *"support"*"—"* ]]; then
      echo "ok    selftest: groups splits label|blurb (support-free blurb present, label clean, nuggs blurb-less)"
    else
      echo "FAIL  selftest: groups label/blurb parse wrong (label='${sf_label}', sf_blurb='${sf_blurb}', nuggs_blurb='${nuggs_blurb}')"; fails=$((fails + 1))
    fi
  else
    echo "FAIL  selftest: groups failed on a clean tree"; fails=$((fails + 1))
  fi

  # ---- negative: a typo'd / free-text category is refused -------------------
  rm -rf "$tmp/designs"/*/ 2>/dev/null || true
  _mk typo compliant-mechanismz     # deliberate typo
  if _run check >/dev/null 2>&1; then
    echo "FAIL  selftest: a typo'd category was accepted"; fails=$((fails + 1))
  else
    echo "ok    selftest: a typo'd / free-text category is refused"
  fi

  # ---- negative: a non-NUGGS design with no category is refused -------------
  rm -rf "$tmp/designs"/*/ 2>/dev/null || true
  _mk orphan                        # no catalog.conf
  if _run check >/dev/null 2>&1; then
    echo "FAIL  selftest: a design with no category was accepted"; fails=$((fails + 1))
  else
    echo "ok    selftest: a design with no category is refused"
  fi

  # ---- negative: a NUGGS design carrying a category key is refused ----------
  rm -rf "$tmp/designs"/*/ 2>/dev/null || true
  _mk nuggs-dupe compliant-mechanisms   # nuggs-* must NOT declare a category
  if _run check >/dev/null 2>&1; then
    echo "FAIL  selftest: a NUGGS design with a catalog.conf category was accepted"; fails=$((fails + 1))
  else
    echo "ok    selftest: a NUGGS design cannot also declare a category"
  fi

  # ---- negative: a non-NUGGS design that includes the coupling is refused ---
  rm -rf "$tmp/designs"/*/ 2>/dev/null || true
  _mk sneaky everyday-functional
  printf 'include <nuggs-coupling.scad>\n' >>"$tmp/designs/sneaky/sneaky.scad"
  if _run check >/dev/null 2>&1; then
    echo "FAIL  selftest: a non-NUGGS design that includes nuggs-coupling was accepted"; fails=$((fails + 1))
  else
    echo "ok    selftest: a coupling include outside the nuggs- prefix is refused"
  fi

  return "$fails"
}

catalog_main() {
  case "${1:-}" in
    --selftest) local rc=0; catalog_selftest || rc=$?; return "$rc" ;;
    check)      catalog_check ;;
    order)      catalog_order ;;
    groups)     catalog_groups ;;
    *) echo "usage: $0 [--root DIR] check|order|groups|--selftest" >&2; exit 2 ;;
  esac
}

catalog_main "$@"
