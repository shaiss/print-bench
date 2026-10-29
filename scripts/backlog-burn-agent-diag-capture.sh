#!/usr/bin/env bash
# backlog-burn-agent-diag-capture.sh — trusted post-agent bootstrap for backlog-burn.
#
# The workflow restores THIS script from the pre-agent START_SHA pin into a
# mktemp path (never a predictable name, never the worktree) and verifies
# CAPTURE_SHA256 before exec. This bootstrap then:
#   1. restores scripts/backlog-burn-agent-diag.sh from the same pin (mktemp)
#   2. archives tools/provenance/src from the same pin (the redactor)
#   3. runs the pinned diag with secrets only via SECRETS_FILE (no token env)
#   4. validates the diag.json schema, re-scrubs with patterns, writes DIAG_OUT
#
# The workflow step then copies DIAG_OUT into GITHUB_OUTPUT (immutable to
# later ship links). Never rely on a shared RUNNER_TEMP path surviving until
# a final upload — later dontAsk links can overwrite those bytes.
#
# Usage (env-driven, called from backlog-burn.yml capture steps):
#   START_SHA=… DIAG_SHA256=… PROV_ARCHIVE_SHA256=… RUNNER_TEMP=…
#   SECRETS_FILE=… DIAG_OUT=…
#     /tmp/XXXX-capture.sh <link>
set -euo pipefail

link="${1:?usage: backlog-burn-agent-diag-capture.sh <link>}"

: "${START_SHA:?START_SHA required}"
: "${DIAG_SHA256:?DIAG_SHA256 required}"
: "${PROV_ARCHIVE_SHA256:?PROV_ARCHIVE_SHA256 required}"
: "${RUNNER_TEMP:?RUNNER_TEMP required}"
: "${DIAG_OUT:?DIAG_OUT required (path for validated diag.json)}"
: "${SECRETS_FILE:?SECRETS_FILE required}"

if [ ! -f "$SECRETS_FILE" ] || [ -L "$SECRETS_FILE" ]; then
  echo "::error::SECRETS_FILE must be a regular file" >&2
  exit 1
fi

git_show() {
  /usr/bin/git --no-replace-objects \
    -c core.hooksPath=/dev/null \
    -c core.fsmonitor=false \
    -c core.sshCommand= \
    show "$1"
}

git_archive() {
  /usr/bin/git --no-replace-objects \
    -c core.hooksPath=/dev/null \
    -c core.fsmonitor=false \
    -c core.sshCommand= \
    archive "$1" "$2"
}

cleanup_paths=()
cleanup() {
  local p
  for p in "${cleanup_paths[@]+"${cleanup_paths[@]}"}"; do
    rm -rf -- "$p" 2>/dev/null || true
  done
}
trap cleanup EXIT

# --- restore pinned diag script into mktemp (no predictable path) -----------
diag_blob="$(mktemp "${RUNNER_TEMP}/backlog-burn-agent-diag.XXXXXX")"
cleanup_paths+=("$diag_blob")
if ! git_show "${START_SHA}:scripts/backlog-burn-agent-diag.sh" > "$diag_blob"; then
  echo "::error::could not restore backlog-burn-agent-diag.sh from ${START_SHA}" >&2
  exit 1
fi
got="$(sha256sum "$diag_blob" | awk '{print $1}')"
if [ "$got" != "$DIAG_SHA256" ]; then
  echo "::error::restored backlog-burn-agent-diag.sh sha256 does not match the pre-agent pin" >&2
  exit 1
fi
chmod +x "$diag_blob"

# --- restore pinned provenance redactor -------------------------------------
arch="$(mktemp "${RUNNER_TEMP}/provenance-src.tar.XXXXXX")"
cleanup_paths+=("$arch")
if ! git_archive "$START_SHA" tools/provenance/src > "$arch"; then
  echo "::error::could not archive tools/provenance/src from ${START_SHA}" >&2
  exit 1
fi
got_arch="$(sha256sum "$arch" | awk '{print $1}')"
if [ "$got_arch" != "$PROV_ARCHIVE_SHA256" ]; then
  echo "::error::restored tools/provenance/src archive sha256 does not match the pre-agent pin" >&2
  exit 1
fi
prov_root="$(mktemp -d "${RUNNER_TEMP}/pinned-provenance.XXXXXX")"
cleanup_paths+=("$prov_root")
tar -x -f "$arch" -C "$prov_root"
rm -f -- "$arch"
prov_src="${prov_root}/tools/provenance/src"
if [ ! -d "$prov_src/provenance" ]; then
  echo "::error::pinned provenance archive missing provenance package at ${prov_src}" >&2
  exit 1
fi

# Private out-dir — not under a path later ship links are told to write into.
out_dir="$(mktemp -d "${RUNNER_TEMP}/backlog-burn-diag-out.XXXXXX")"
cleanup_paths+=("$out_dir")

# Strip credential env from the diag child: secrets reach it only via the
# SECRETS_FILE the trusted workflow step prepared.
env -u GITHUB_TOKEN -u GH_TOKEN \
    -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
    -u ZAI_KEY -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u REGEN_TOKEN \
    -u ACTIONS_RUNTIME_TOKEN -u ACTIONS_ID_TOKEN_REQUEST_TOKEN \
  "$diag_blob" --link "$link" \
    --secrets-file "$SECRETS_FILE" \
    --provenance-src "$prov_src" \
    --out-dir "$out_dir"

raw_diag="${out_dir}/diag.json"
if [ ! -f "$raw_diag" ] || [ -L "$raw_diag" ]; then
  echo "::error::diag did not write a regular diag.json" >&2
  exit 1
fi

# Validate schema + re-scrub with pinned provenance (pattern pass). Refuse
# anything that is not our payload shape (blocks planting the execution log).
validated="$(mktemp "${RUNNER_TEMP}/backlog-burn-diag-validated.XXXXXX")"
cleanup_paths+=("$validated")
python3 -I - "$prov_src" "$raw_diag" "$validated" <<'PY'
import json
import sys
from pathlib import Path

prov_src, raw_path, out_path = sys.argv[1:4]
sys.path.insert(0, prov_src)
from provenance.gitstore import scrub  # noqa: E402

ALLOWED = {
    "label",
    "log_note",
    "denied_tools",
    "final_assistant_message_truncated",
}
MAX_BYTES = 64 * 1024
MAX_FINAL = 500
MAX_DENIALS = 40

raw = Path(raw_path).read_bytes()
if len(raw) > MAX_BYTES:
    print(f"::error::diag.json too large ({len(raw)} > {MAX_BYTES})", file=sys.stderr)
    sys.exit(1)
try:
    text = raw.decode("utf-8")
    obj = json.loads(text)
except (UnicodeDecodeError, json.JSONDecodeError) as exc:
    print(f"::error::diag.json is not UTF-8 JSON: {exc}", file=sys.stderr)
    sys.exit(1)
if not isinstance(obj, dict) or set(obj.keys()) != ALLOWED:
    print(
        f"::error::diag.json keys {sorted(obj.keys()) if isinstance(obj, dict) else type(obj)} "
        f"!= {sorted(ALLOWED)}",
        file=sys.stderr,
    )
    sys.exit(1)
if not isinstance(obj["label"], str) or not isinstance(obj["log_note"], str):
    print("::error::diag.json label/log_note must be strings", file=sys.stderr)
    sys.exit(1)
if not isinstance(obj["final_assistant_message_truncated"], str):
    print("::error::diag.json final_assistant_message_truncated must be a string", file=sys.stderr)
    sys.exit(1)
if len(obj["final_assistant_message_truncated"]) > MAX_FINAL:
    print("::error::diag.json final message exceeds truncate bound", file=sys.stderr)
    sys.exit(1)
if not isinstance(obj["denied_tools"], list) or len(obj["denied_tools"]) > MAX_DENIALS:
    print("::error::diag.json denied_tools invalid", file=sys.stderr)
    sys.exit(1)
clean_denials = []
for row in obj["denied_tools"]:
    if not isinstance(row, dict) or set(row.keys()) - {"tool", "reason"}:
        print("::error::diag.json denial row shape invalid", file=sys.stderr)
        sys.exit(1)
    tool = scrub(str(row.get("tool") or ""))
    reason = scrub(str(row.get("reason") or ""))
    clean_denials.append({"tool": tool[:200], "reason": reason[:300]})

payload = {
    "label": scrub(obj["label"])[:200],
    "log_note": scrub(obj["log_note"])[:300],
    "denied_tools": clean_denials,
    "final_assistant_message_truncated": scrub(
        obj["final_assistant_message_truncated"]
    )[:MAX_FINAL],
}
Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

# Atomic publish to DIAG_OUT (caller-owned path; typically a mktemp file).
# Do not leave the validated bytes under a well-known RUNNER_TEMP tree.
cp -f -- "$validated" "$DIAG_OUT"
chmod 600 -- "$DIAG_OUT" 2>/dev/null || true
