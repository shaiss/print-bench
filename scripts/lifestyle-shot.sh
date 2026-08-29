#!/usr/bin/env bash
# NOTE (issue #302): the AI lifestyle tier is DISABLED by default behind the
# committed .github/ai-lifestyle.conf (enabled: false). The generation workflows
# (lifestyle-shot.yml / product-still.yml) skip while it is off; this script runs
# only when a human flips the flag or dispatches it deliberately. It is kept for
# that day, and for --mock testing.
#
# Generate an AI-restyled image for a design via the Z.AI GLM-Image API in
# image-to-image mode — the request carries a committed, geometry-true render as
# its seed (image_urls) — size it to the product-shot budget, and embed it in the
# design's README with the canonical disclosure readme-gate requirement 9 demands
# (an "AI-styled scene" alt label and a "geometry is approximate" caption). The
# image is COSMETIC and geometrically approximate: the model repaints scene,
# lighting and materials, and — the reason the tier is disabled — GLM-Image does
# NOT treat the seed as a shape constraint (it follows the prompt), so the output
# is not pinned to the mesh however true the seed is. The disclosure, not the
# seed, is what keeps it honest; the geometry-true tier-1 render and the STL stay
# the source of truth for the real shape. See
# .claude/skills/product-shots/SKILL.md and issues #66 and #302.
#
# One hardened generator, two artifact KINDs (see --kind):
#   lifestyle      (default) tier-2 SCENE — the part staged in a real-world
#                  setting. Reads lifestyle.conf, writes previews/lifestyle-<shot>.png.
#   product-still  tier-1.5 BARE PART — the part alone, no scene, at a chosen
#                  angle. Reads product-still.conf, writes previews/product-still-<shot>.png.
# A product still is itself a legal seed for a lifestyle scene, so the PM can
# chain raytrace -> product still -> lifestyle scene.
#
#   ZAI_KEY=... ./scripts/lifestyle-shot.sh <design>
#   ZAI_KEY=... ./scripts/lifestyle-shot.sh --kind product-still <design>
#   ./scripts/lifestyle-shot.sh <design> --mock   # offline placeholder, no API
#
# Reads designs/<design>/<kind-manifest>. Each line is "<shot> | <prompt>" or
# "<shot> | seed=<ref> | <prompt>": the seed names the committed render
# (previews/<ref>.png) the image-to-image starts from, and defaults to the
# shot's own name (previews/<shot>.png) when omitted. Re-running is safe:
# the README embed is inserted only if it isn't there already. Meant to run in
# CI (lifestyle-shot.yml / product-still.yml) where ZAI_KEY is a repo secret;
# --mock lets the whole pipeline be exercised locally without a key.
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck source=scripts/preview-budget.sh
. scripts/preview-budget.sh          # MAX_SHOT_BYTES

# glm-image is a unified model: the same model and endpoint serve text-to-image
# and image-to-image — supplying image_urls in the body is what selects the
# latter. All three stay env-overridable so a field-name/endpoint change is a
# one-liner, not an edit here.
ZAI_MODEL="${ZAI_MODEL:-glm-image}"
ZAI_ENDPOINT="${ZAI_ENDPOINT:-https://api.z.ai/api/paas/v4/images/generations}"
ZAI_SIZE="${ZAI_SIZE:-1280x1280}"   # a size the GLM-Image docs show in examples
# ZAI_SIZE may arrive from a workflow_dispatch 'size' input, so validate it
# before it reaches the API request or ImageMagick: WxH, each side within a sane
# ceiling. Rejects a fat-finger 99999x99999 that would waste API quota and
# stress the runner (same spirit as shot-spec.sh's MAX_DIM).
if [[ ! "$ZAI_SIZE" =~ ^[0-9]+x[0-9]+$ ]]; then
  echo "invalid ZAI_SIZE '${ZAI_SIZE}' — want WxH (e.g. 1280x1280)" >&2; exit 2
fi
if (( ${ZAI_SIZE%x*} < 256 || ${ZAI_SIZE#*x} < 256 || ${ZAI_SIZE%x*} > 4096 || ${ZAI_SIZE#*x} > 4096 )); then
  echo "ZAI_SIZE '${ZAI_SIZE}' out of range — each side must be 256..4096 px" >&2; exit 2
fi

# Flags in any order around the one positional <design>, so both
# "lifestyle-shot.sh <design> --mock" and "lifestyle-shot.sh --kind product-still
# <design>" (the form product-still.yml uses) parse identically.
design=""
mock=0
kind="lifestyle"     # 'lifestyle' (tier-2 scene) or 'product-still' (tier-1.5 bare part)
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mock)   mock=1; shift ;;
    --kind)   [[ $# -ge 2 ]] || { echo "--kind requires a value ('lifestyle' or 'product-still')" >&2; exit 2; }; kind="$2"; shift 2 ;;
    --kind=*) kind="${1#--kind=}"; shift ;;
    --)       shift; break ;;
    -*)       echo "unknown flag '$1'" >&2; exit 2 ;;
    *)        if [[ -z "$design" ]]; then design="$1"; shift; else echo "unexpected extra argument '$1'" >&2; exit 2; fi ;;
  esac
done
if [[ -z "$design" ]]; then
  echo "usage: ZAI_KEY=... $0 [--kind lifestyle|product-still] <design> [--mock]" >&2
  exit 2
fi
# The design name is interpolated into paths (designs/<design>/...); pin it to
# the repo's kebab-case convention so a stray "../" or a space can't write or
# edit outside the design directory. Strict kebab-case (no leading/trailing
# or doubled hyphens) — the SAME pattern lifestyle-shot.yml's dispatch path
# validates against, so the workflow and the generator accept and reject
# identical names (CodeRabbit review on #90).
if [[ ! "$design" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "invalid design name '${design}' — must be lowercase kebab-case (e.g. sushi-battleship)" >&2
  exit 2
fi

# Two artifact kinds share this one hardened generator — the identical
# GLM-Image image-to-image call, SSRF/download hardening and budget fit — and
# differ only in the manifest read, the output prefix, the README alt text and
# which seeds they accept:
#   lifestyle      tier-2 SCENE:        previews/lifestyle-<shot>.png     (lifestyle.conf)
#   product-still  tier-1.5 BARE PART:  previews/product-still-<shot>.png (product-still.conf)
case "$kind" in
  lifestyle)     conf_name="lifestyle.conf";     out_prefix="lifestyle";     kind_label="lifestyle scene" ;;
  product-still) conf_name="product-still.conf"; out_prefix="product-still"; kind_label="product still" ;;
  *) echo "invalid --kind '${kind}' — must be 'lifestyle' or 'product-still'" >&2; exit 2 ;;
esac

conf="designs/${design}/${conf_name}"
if [[ ! -f "$conf" ]]; then
  echo "no ${conf} — nothing to generate" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# trim leading/trailing whitespace without touching interior spaces
trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }

# Log-safe form of a download URL: scheme + host + path ONLY. The query string
# routinely carries a signed, expiring access token, and userinfo is
# credential-shaped by definition; everything printed here lands in public CI
# logs — so no log line in this script may include either, the issue-#128
# download diagnostics included.
sanitize_url() {
  local u="${1%%[?#]*}" scheme rest authority path=""
  scheme="${u%%://*}"; rest="${u#*://}"
  [[ "$rest" == "$u" ]] && { printf '%s' "$u"; return; }  # no scheme separator
  authority="${rest%%/*}"
  [[ "$rest" == */* ]] && path="/${rest#*/}"
  printf '%s' "${scheme}://${authority##*@}${path}"       # drop any userinfo
}

# Log-safe one-line summary of an error-response body. Structured-first: a
# JSON body — the shape the Z.AI CDN actually returns on the issue-#128
# failure, e.g. {"RetCode":-148654, "ErrMsg":"file not exist"} — yields ONLY
# a whitelist of non-sensitive fields, so no unexpected key (an echoed signed
# URL, an S3-style SignatureProvided) can carry a credential into a public
# log. Anything else falls back to a 300-byte snippet with non-printables
# dotted, query strings inside the body stripped (an echoed request URL is
# the classic leak), and token-length runs masked.
body_summary() {
  local f="$1" out
  if out="$(python3 - "$f" <<'PY' 2>/dev/null
import json, sys
obj = json.load(open(sys.argv[1], "rb"))
if not isinstance(obj, dict): raise SystemExit(1)
parts = []
for k in ("RetCode", "ErrMsg", "code", "message", "msg", "error", "status"):
    v = obj.get(k)
    if isinstance(v, (str, int, float, bool)):
        parts.append("%s=%s" % (k, str(v)[:120]))
    elif isinstance(v, dict):
        for k2 in ("code", "message", "msg"):
            v2 = v.get(k2)
            if isinstance(v2, (str, int, float, bool)):
                parts.append("%s.%s=%s" % (k, k2, str(v2)[:120]))
if not parts: raise SystemExit(1)
print("; ".join(parts))
PY
)"; then
    printf '%s' "$out"
    return
  fi
  head -c 300 "$f" | tr -c '[:print:]' '.' \
    | sed -E -e 's|\?[^[:space:]"<>]*|?[query-stripped]|g' \
             -e 's|[A-Za-z0-9+/=_-]{40,}|[masked]|g'
}

# Shrink an image (any format) to a stripped PNG that fits MAX_SHOT_BYTES,
# stepping the width down until it does. Photoreal 1280-wide PNGs can blow the
# 3 MiB budget, so this is not optional. The ">" on -resize means "only shrink,
# never enlarge", so a small source is never upscaled. Fails (rather than
# silently shipping an over-budget file) if it can't be met.
fit_budget() {
  local src="$1" out="$2" w=1280
  convert "$src" -resize "${w}x>" -strip "$out"
  while (( $(stat -c %s "$out") > MAX_SHOT_BYTES )) && (( w > 480 )); do
    w=$(( w * 85 / 100 ))
    convert "$src" -resize "${w}x>" -strip "$out"
  done
  if (( $(stat -c %s "$out") > MAX_SHOT_BYTES )); then
    echo "could not fit ${out} under $((MAX_SHOT_BYTES / 1024 / 1024)) MiB (down to ${w}px wide)" >&2
    return 1
  fi
}

generated=()
generated_seed=()   # parallel to generated[]: the seed each shot derived from
while IFS= read -r line || [[ -n "$line" ]]; do
  # Full-line comments and blank lines only — a '#' inside a prompt is content
  # (a scene may legitimately say "buoy #3"), so do not strip inline.
  trimmed="$(trim "$line")"
  [[ -z "$trimmed" || "$trimmed" == '#'* ]] && continue
  shot="$(trim "${line%%|*}")"
  rest="${line#*|}"
  if [[ -z "$shot" || "$line" != *"|"* ]]; then
    echo "malformed lifestyle.conf line (want '<shot> | <prompt>' or '<shot> | seed=<ref> | <prompt>'): $line" >&2
    exit 1
  fi
  # Optional middle field "seed=<ref>" names the geometry-true render this shot
  # seeds image-to-image from (a committed previews/<ref>.png — a hero shot, a
  # frozen cameras.conf view, or a custom-angle render). Omitted, the seed
  # defaults to the shot's own name (previews/<shot>.png), same-name seeding
  # like motion.conf. Only a middle field that literally begins with "seed="
  # is treated as one, so a prompt that happens to contain "|" parses exactly
  # as it did before this field existed.
  seed=""
  rest_trim="$(trim "$rest")"
  if [[ "$rest_trim" == seed=* && "$rest" == *"|"* ]]; then
    seed="$(trim "${rest%%|*}")"; seed="${seed#seed=}"; seed="$(trim "$seed")"
    prompt="$(trim "${rest#*|}")"
    # An empty value ("seed= | prompt") is malformed: a blank Seed column that
    # reached the manifest as a bare "seed=" must not silently fall back to the
    # shot name — reject it so a paid API call isn't spent on a mis-seeded shot.
    if [[ -z "$seed" ]]; then
      echo "malformed ${conf} line (empty 'seed=' — give a ref or drop the field): $line" >&2
      exit 1
    fi
  elif [[ "$rest_trim" == seed=* ]]; then
    # "shot | seed=ref" with no trailing "| prompt": the branch above needs a
    # second '|', so without this guard the literal "seed=ref" becomes the
    # prompt and a paid call is spent on nonsense. Reject it.
    echo "malformed ${conf} line ('seed=' without a following '| <prompt>'): $line" >&2
    exit 1
  else
    prompt="$rest_trim"
  fi
  if [[ -z "$seed" ]]; then
    # Implicit default: same-name seeding (previews/<shot>.png). When that
    # render is absent, fall back to the first shots.conf shot — a shot name and
    # its tier-1 render legitimately differ (a `scene` lifestyle shot anchored on
    # the `hero` render), and without this the documented re-roll of every such
    # design is a hard error. Mirrors lifestyle-clip.sh's seed_url_for fallback,
    # and applies ONLY to the implicit seed: an explicit seed=<ref> (which leaves
    # $seed non-empty here) names a specific render and must still error below if
    # it is missing, never silently animate a different image.
    seed="$shot"
    if [[ ! -f "designs/${design}/previews/${seed}.png" && -f "designs/${design}/shots.conf" ]]; then
      first_shot=""
      while IFS= read -r sline || [[ -n "$sline" ]]; do
        strimmed="$(trim "$sline")"
        [[ -z "$strimmed" || "$strimmed" == '#'* ]] && continue
        first_shot="$(trim "${sline%%|*}")"
        break
      done <"designs/${design}/shots.conf"
      if [[ -n "$first_shot" ]]; then
        seed="$first_shot"
        # Announce the substitution (issue #415): the image is correctly seeded
        # either way, but a PM re-rolling after renaming the tier-1 shot would
        # otherwise have no trace of WHICH render seeded the shot they are
        # looking at — requested shot and substituted seed, one line.
        echo "seed: ${shot} → ${seed} (fallback — no previews/${shot}.png, seeded from the first shots.conf shot)"
      fi
    fi
  fi
  if [[ -z "$prompt" ]]; then
    echo "malformed ${conf} line (empty prompt): $line" >&2
    exit 1
  fi
  # <shot> becomes the filename stem (lifestyle-<shot>.png) and part of the
  # README embed URL — pin it to kebab-case so it can't escape previews/ or
  # produce a broken markdown link.
  if [[ ! "$shot" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "invalid shot name '${shot}' in ${conf} — must be kebab-case ([a-z0-9-])" >&2
    exit 1
  fi
  # The seed resolves to a committed render in the SAME design's previews/:
  # kebab-case only (so it can't escape the directory), never another
  # lifestyle-* image (seeding from an AI repaint defeats the geometry pinning),
  # and it must already exist — that render is precisely what makes the shot
  # geometry-accurate.
  if [[ ! "$seed" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "invalid seed name '${seed}' in ${conf} — must be kebab-case ([a-z0-9-])" >&2
    exit 1
  fi
  # Seed integrity, bounded per kind. A lifestyle SCENE may seed from a
  # geometry-true tier-1 render OR a tier-1.5 product still, but never another
  # lifestyle-* scene — seeding a repaint from a repaint drifts even further from
  # the real shape. A PRODUCT STILL may seed ONLY from a geometry-true render —
  # never any AI image (neither a lifestyle-* scene nor another product-still-*).
  # These rules keep the seed as close to the true mesh as the pipeline allows;
  # they do NOT make the output faithful — GLM-Image follows the prompt, not the
  # seed's geometry (issue #302), which is why the whole tier ships disabled. The
  # break of the old "a seed is always geometry-true" invariant is deliberate and
  # made explicit here rather than silently.
  if [[ "$seed" == lifestyle-* ]]; then
    echo "invalid seed '${seed}' in ${conf} — a ${kind_label} must not seed from a lifestyle-* scene (an AI repaint); seed from a geometry-true tier-1 render (or, for a lifestyle scene, a product-still-* render)" >&2
    exit 1
  fi
  if [[ "$kind" == "product-still" && "$seed" == product-still-* ]]; then
    echo "invalid seed '${seed}' in ${conf} — a product still must seed from a geometry-true tier-1 render, not another AI product still" >&2
    exit 1
  fi
  seed_path="designs/${design}/previews/${seed}.png"
  if [[ ! -f "$seed_path" ]]; then
    echo "seed render ${seed_path} not found — a ${kind_label} seeds image-to-image from a committed geometry-true render; add the tier-1 shots.conf/cameras.conf entry that produces it (or point seed= at an existing one)" >&2
    exit 1
  fi

  outdir="designs/${design}/previews"
  mkdir -p "$outdir"
  out="${outdir}/${out_prefix}-${shot}.png"

  if (( mock )); then
    # Offline placeholder so the fit-to-budget, README-embed and gate steps are
    # testable without the API or a key. Never commit a --mock image.
    convert -size "$ZAI_SIZE" gradient:'#2b3a4a'-'#c98f5a' \
      -gravity center -pointsize 42 -fill white \
      -annotate 0 "MOCK ${kind_label}\n${design} / ${shot}\nseed: ${seed}\n(placeholder, not for commit)" \
      "$tmp/gen.png"
  else
    if [[ -z "${ZAI_KEY:-}" ]]; then
      echo "ZAI_KEY is not set — export it (CI: repo secret) or pass --mock" >&2
      exit 1
    fi
    # Build the request body in a temp file. It carries the base64-encoded seed
    # render (the geometry-true tier-1 image) in image_urls, which switches
    # glm-image into image-to-image mode — though the model follows the prompt
    # rather than constraining shape to the seed (issue #302). The base64 payload
    # is far too large to pass as a shell argument (ARG_MAX). Python reads the
    # seed straight off disk and writes the JSON; nothing large ever transits
    # argv or a shell variable.
    ZAI_MODEL="$ZAI_MODEL" PROMPT="$prompt" ZAI_SIZE="$ZAI_SIZE" SEED_PATH="$seed_path" \
      python3 - "$tmp/req.json" <<'PY'
import base64, json, os, sys
with open(os.environ["SEED_PATH"], "rb") as fh:
    b64 = base64.b64encode(fh.read()).decode("ascii")
body = {
    "model": os.environ["ZAI_MODEL"],
    "prompt": os.environ["PROMPT"],
    "size": os.environ["ZAI_SIZE"],
    "image_urls": ["data:image/png;base64," + b64],
}
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(body, out)
PY
    # Capture body AND status (no -f): a 4xx body carries the real reason — a
    # rejected size, an invalid key, a content-filter block — which we must
    # surface, not swallow, on the first live run. The Authorization header goes
    # in via -K - (stdin config) so the key never lands in curl's argv (readable
    # from /proc); the printf is a bash builtin, so it doesn't fork either. The
    # body goes in via --data-binary @file (not -d) for the same ARG_MAX reason.
    # --connect-timeout/--max-time bound a stalled third-party call; hd-quality
    # image-to-image is slower than text-to-image, hence the larger max-time.
    http="$(printf 'header = "Authorization: Bearer %s"\n' "$ZAI_KEY" \
      | curl -sS -K - --connect-timeout 15 --max-time 180 -w $'\n%{http_code}' \
        -X POST "$ZAI_ENDPOINT" \
        -H "Content-Type: application/json" \
        --data-binary @"$tmp/req.json")" || { echo "GLM-Image request failed (curl transport error)" >&2; exit 1; }
    code="${http##*$'\n'}"
    resp="${http%$'\n'*}"
    if [[ "$code" != 2?? ]]; then
      echo "GLM-Image HTTP ${code}: ${resp:0:800}" >&2
      exit 1
    fi
    # Parse ONCE from the captured body. Accept a hosted url or inline base64;
    # surface an error/refusal object or an unexpected shape (async task,
    # content filter) with the raw body instead of a bare traceback.
    parsed="$(printf '%s' "$resp" | python3 -c '
import json, sys
raw = sys.stdin.read()
try:
    obj = json.loads(raw)
except Exception:
    sys.stderr.write("non-JSON GLM-Image response: %s\n" % raw[:800]); raise
if isinstance(obj, dict) and obj.get("error"):
    sys.stderr.write("GLM-Image error: %s\n" % json.dumps(obj["error"])[:500]); sys.exit(3)
try:
    item = obj["data"][0]
    if item.get("url"):
        print("url\t" + item["url"])
    elif item.get("b64_json"):
        print("b64\t" + item["b64_json"])
    else:
        raise KeyError("data[0] has neither url nor b64_json")
except Exception:
    sys.stderr.write("unexpected GLM-Image response shape: %s\n" % raw[:800]); raise')"
    # NB: 'resp_kind', NOT 'kind' — 'kind' is the artifact-kind global
    # (lifestyle|product-still) set from --kind and read again by the README
    # embed loop and the per-kind seed guard. Reusing 'kind' here clobbered it on
    # the live path, so product-still embeds got lifestyle alt text and the
    # product-still seed guard stopped firing after the first shot.
    resp_kind="${parsed%%$'\t'*}"
    value="${parsed#*$'\t'}"
    if [[ "$resp_kind" == "url" ]]; then
      # SSRF guard: require https, extract the host correctly (dropping any
      # userinfo so https://x@169.254.169.254/ can't spoof it), then RESOLVE it
      # and refuse if any resolved address is non-public. Resolving — rather
      # than string-matching — is what catches decimal/hex IP literals and
      # hostnames that point at internal targets (cloud metadata, etc.), even
      # if the API response or ZAI_ENDPOINT is tampered with.
      if [[ "$value" != https://* ]]; then
        echo "refusing non-https image URL from API: ${value:0:80}" >&2
        exit 1
      fi
      authority="${value#https://}"
      authority="${authority%%[/?#]*}"   # drop path / query / fragment
      authority="${authority##*@}"       # drop userinfo (segment after last @)
      if [[ "$authority" == \[* ]]; then
        host="${authority%%\]*}]"        # bracketed IPv6 literal, keep [ ... ]
        rest="${authority#*\]}"; port="${rest#:}"; [[ "$port" == "$rest" ]] && port=443
      else
        host="${authority%%:*}"
        port="${authority##*:}"; [[ "$port" == "$authority" ]] && port=443
      fi
      # Download with a bounded retry (issue #128): two CI runs failed here
      # identically — the generation POST returned 2xx with a data[0].url, and
      # the immediate GET of that URL 404'd, with no diagnostics (the old
      # curl -f discarded the error body). Two hypotheses fit that shape, and
      # the retry covers both: (a) eventual consistency — the object isn't
      # visible at the CDN yet when the API hands out the URL, so waiting and
      # re-fetching finds it; (b) pinned-IP skew — the --resolve pin below held
      # the first vetted address for the whole fetch, and a FRESH getaddrinfo
      # on the next attempt can rotate to a CDN edge that has the object. So
      # every attempt re-runs resolve-and-vet from scratch, which also keeps
      # the TOCTOU property: each connection is pinned to an address vetted in
      # that same attempt, never a stale one.
      #
      # Policy: 404/408/425/429/5xx and transient curl transport errors retry
      # — 5 attempts with 3/6/12/24s sleeps between them, under a 900-second
      # elapsed-time deadline that also clamps the final attempt's --max-time.
      # The sleeps alone are trivial, but five attempts against a CDN that
      # dribbles bytes for the full per-attempt --max-time would outlive the
      # workflow's 20-minute timeout and die with no final diagnostic — the
      # deadline guarantees the loop always fails inside the job with its
      # per-attempt lines printed. A 3xx is refused immediately and
      # permanently — following or retrying a redirect is the SSRF hole
      # --max-redirs 0 exists to close. Any other 4xx (401/403 — a bad or
      # expired credential) fails immediately with diagnostics, because
      # retrying an auth failure only burns the clock; deterministic curl
      # errors (unsupported scheme, TLS verification, --max-filesize) fail
      # immediately for the same reason.
      dl_deadline=$(( SECONDS + 900 ))
      dl_ok=0
      for dl_attempt in 1 2 3 4 5; do
        if (( dl_attempt > 1 )); then
          sleep $(( 3 * (1 << (dl_attempt - 2)) ))   # 3, 6, 12, 24
        fi
        dl_left=$(( dl_deadline - SECONDS ))
        if (( dl_left <= 0 )); then
          echo "image download attempt ${dl_attempt}/5: skipped — 900s retry time budget exhausted" >&2
          break
        fi
        # Resolve + validate FRESH each attempt and capture the vetted IP, so
        # curl connects to that exact address via --resolve rather than doing
        # its own second DNS lookup — which a short-TTL rebind could swing to
        # an internal host between the check and the fetch (TOCTOU). A literal
        # IP host has no DNS lookup to rebind, so it's fetched directly once
        # vetted. A vet refusal (unresolvable host, non-public address) is a
        # security stop, not a transient: it exits and is never retried.
        vet="$(python3 - "$host" <<'PY'
import sys, socket, ipaddress
host = sys.argv[1].strip("[]")
try:
    ipaddress.ip_address(host); literal = True
except ValueError:
    literal = False
try:
    addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
except Exception as e:
    sys.stderr.write("refusing image URL: cannot resolve host %r (%s)\n" % (host, e)); sys.exit(1)
vetted = ""
for a in addrs:
    ip = ipaddress.ip_address(a)
    if (not ip.is_global) or ip.is_private or ip.is_loopback or ip.is_link_local \
       or ip.is_reserved or ip.is_multicast:
        sys.stderr.write("refusing image URL: host %r resolves to non-public %s\n" % (host, a)); sys.exit(1)
    vetted = vetted or a
if not vetted:
    sys.stderr.write("refusing image URL: host %r has no addresses\n" % host); sys.exit(1)
print("literal" if literal else "name")
print(vetted)
PY
)" || exit 1
        vetted_ip="${vet##*$'\n'}"
        # Download hardening: --proto '=https' pins the scheme, --max-redirs 0
        # plus no -L means a redirect can't send curl to a fresh, unvetted
        # host (a 3xx is refused below too), --connect-timeout/--max-time
        # bound a stall, and --max-filesize caps an API-controlled payload
        # before it hits ImageMagick. No Authorization header here, ever: the
        # signed URL is the credential, and the API key must not be handed to
        # a third-party CDN.
        dl_flags=(--proto '=https' --max-redirs 0 --connect-timeout 15 --max-time "$(( dl_left < 300 ? dl_left : 300 ))" --max-filesize 20000000)
        resolve_args=()
        if [[ "${vet%%$'\n'*}" == "name" ]]; then
          resolve_host="${host#[}"; resolve_host="${resolve_host%]}"
          resolve_args=(--resolve "${resolve_host}:${port}:${vetted_ip}")
        fi
        # No -f: -f discards the response body on an HTTP error, and that body
        # is the diagnosis — a CDN names the real cause there (NoSuchKey vs
        # AccessDenied vs an expired signature), exactly what the issue-#128
        # logs were missing. Capture the body to the output file and branch on
        # the status ourselves; the || keeps a failing curl from tripping
        # set -e before it can be logged.
        curl_rc=0
        dl_meta="$(curl -sS "${dl_flags[@]}" "${resolve_args[@]}" \
          -o "$tmp/gen.img" -w '%{http_code}\t%{content_type}' "$value")" || curl_rc=$?
        if (( curl_rc != 0 )); then
          echo "image download attempt ${dl_attempt}/5: curl transport error ${curl_rc} for $(sanitize_url "$value")" >&2
          case "$curl_rc" in
            # Deterministic, not transient: an unsupported/refused scheme (1),
            # a TLS certificate that does not verify (60 — a security stop,
            # not a blip), or a payload over --max-filesize (63) fails
            # identically on every attempt. Retrying only burns the clock.
            1|60|63) echo "image download failed (curl error ${curl_rc} is not retryable)" >&2; exit 1 ;;
          esac
          continue
        fi
        dl_code="${dl_meta%%$'\t'*}"
        dl_ctype="${dl_meta#*$'\t'}"
        if [[ "$dl_code" == 2?? && -s "$tmp/gen.img" ]]; then
          dl_ok=1
          break
        fi
        # Failed attempt: log the status, the sanitized URL (scheme + host +
        # path — never the query string), the Content-Type, and a log-safe
        # structured summary of the body (see body_summary above) — enough for
        # the CI log to name the cause without echoing credential-shaped bytes.
        echo "image download attempt ${dl_attempt}/5: HTTP ${dl_code} from $(sanitize_url "$value") (Content-Type: ${dl_ctype:-unknown})" >&2
        echo "  response body: $(body_summary "$tmp/gen.img")" >&2
        if [[ "$dl_code" == 3?? ]]; then
          echo "refusing image URL: it returned a redirect (HTTP ${dl_code}); not following it (SSRF guard, never retried)" >&2
          exit 1
        fi
        case "$dl_code" in
          404|408|425|429|5??) continue ;;   # retryable — see the policy above
          2??) continue ;;                   # 2xx but an EMPTY body: transient truncation, retry
          *) echo "image download failed (HTTP ${dl_code} is not retryable)" >&2; exit 1 ;;
        esac
      done
      if (( ! dl_ok )); then
        echo "image download failed (${dl_attempt} attempt(s) made) — the per-attempt lines above carry the diagnosis (issue #128)" >&2
        exit 1
      fi
    else
      printf '%s' "$value" | base64 -d >"$tmp/gen.img"
    fi
    # These bytes are API-controlled. Pin ImageMagick to the detected type so it
    # can't pick a delegate (PS/SVG/MSL/...) from sniffed content, and reject
    # anything that isn't a plain raster image.
    mime="$(file -b --mime-type "$tmp/gen.img")"
    case "$mime" in
      image/png)  coder=png ;;
      image/jpeg) coder=jpeg ;;
      image/webp) coder=webp ;;
      *) echo "refusing unexpected image type from API: ${mime}" >&2; exit 1 ;;
    esac
    convert "${coder}:$tmp/gen.img" "$tmp/gen.png"
  fi

  fit_budget "$tmp/gen.png" "$out"
  echo "wrote ${out} ($(( ($(stat -c %s "$out") + 1023) / 1024 )) KiB)"
  generated+=("$shot")
  generated_seed+=("$seed")
done <"$conf"

# Insert the canonical disclosure embed into the README for each shot (only if
# it isn't already embedded), directly after the geometry-true render it was
# seeded from, so the AI image sits beside the real shape it derives from.
readme="designs/${design}/README.md"
(( ${#generated[@]} )) || { echo "no shots generated (empty ${conf}?)" >&2; exit 1; }
for i in "${!generated[@]}"; do
  shot="${generated[$i]}"
  seed="${generated_seed[$i]}"
  DESIGN="$design" SHOT="$shot" SEED="$seed" README="$readme" \
    OUT_PREFIX="$out_prefix" KIND="$kind" python3 - <<'PY'
import os
design, shot, readme = os.environ["DESIGN"], os.environ["SHOT"], os.environ["README"]
seed, out_prefix, kind = os.environ["SEED"], os.environ["OUT_PREFIX"], os.environ["KIND"]
rel = f"previews/{out_prefix}-{shot}.png"
hero = f"previews/{seed}.png"
# Alt text differs by kind for the reader, but BOTH kinds carry the canonical
# "AI-styled scene" token (readme-gate requirement 9 keys on it) and the
# identical "geometry is approximate" caption — one disclosure vocabulary,
# reused verbatim, because a product still is still an AI repaint.
if kind == "product-still":
    alt = f"AI-styled scene: {design} bare-part product still"
else:
    alt = f"AI-styled scene: {design} staged in a real-world setting"
block = (
    f"\n![{alt}]({rel})\n\n"
    "*AI-generated impression for general illustration only — geometry is "
    "approximate and may not exactly match the printed part; see the studio "
    "render above and the STL for the true shape.*\n"
)
text = open(readme, encoding="utf-8").read()
if f"]({rel})" in text:
    print(f"README already embeds {rel}")
    raise SystemExit(0)
lines = text.splitlines(keepends=True)
# insert after the paragraph containing the tier-1 hero embed, else after the
# first image embed, else append.
anchor = next((i for i, l in enumerate(lines) if f"]({hero})" in l), None)
if anchor is None:
    anchor = next((i for i, l in enumerate(lines) if l.lstrip().startswith("![")), None)
if anchor is None:
    out = text + block
else:
    # Advance past the hero image's paragraph, then — if the next paragraph is
    # the hero's caption (a blank-separated emphasis line, not another image or
    # a heading) — past that too, so the lifestyle block lands after the whole
    # hero unit instead of wedged between the hero image and its caption.
    def end_of_para(i):
        while i < len(lines) and lines[i].strip():
            i += 1
        return i
    end = end_of_para(anchor + 1)
    nxt = end
    while nxt < len(lines) and not lines[nxt].strip():
        nxt += 1
    if nxt < len(lines):
        s = lines[nxt].lstrip()
        if s[:1] in ("*", "_") and not s.startswith("!["):
            end = end_of_para(nxt)
    out = "".join(lines[:end]) + block + "".join(lines[end:])
open(readme, "w", encoding="utf-8").write(out)
print(f"embedded {rel} in {readme}")
PY
done
