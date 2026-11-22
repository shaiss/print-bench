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

# Private out-dir — not under a path later ship links are told to write into.
out_dir="$(mktemp -d "${RUNNER_TEMP}/backlog-burn-diag-out.XXXXXX")"
cleanup_paths+=("$out_dir")
prov_root="$(mktemp -d "${RUNNER_TEMP}/pinned-provenance.XXXXXX")"
cleanup_paths+=("$prov_root")

# Restore pinned diag + provenance from verified *bytes* (CodeRabbit on #953):
# digest the buffers, extract the archive from the same buffer, and run the
# diag script via memfd so a pathname TOCTOU cannot swap the checked bytes.
# Optional EXECUTION_LOG overrides the shared default (per-attempt log).
execution_log_args=()
if [ -n "${EXECUTION_LOG:-}" ]; then
  execution_log_args=(--execution-log "$EXECUTION_LOG")
fi
prov_src="$(
  START_SHA="$START_SHA" DIAG_SHA256="$DIAG_SHA256" \
  PROV_ARCHIVE_SHA256="$PROV_ARCHIVE_SHA256" \
  SECRETS_FILE="$SECRETS_FILE" LINK="$link" OUT_DIR="$out_dir" \
  PROV_ROOT="$prov_root" \
  EXEC_LOG_JSON="$(printf '%s\n' "${execution_log_args[@]+"${execution_log_args[@]}"}" | python3 -I -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))')" \
  python3 -I - <<'PY'
import hashlib
import json
import os
import subprocess
import sys
import tarfile
from io import BytesIO

start_sha = os.environ["START_SHA"]
diag_sha = os.environ["DIAG_SHA256"]
arch_sha = os.environ["PROV_ARCHIVE_SHA256"]
secrets_file = os.environ["SECRETS_FILE"]
link = os.environ["LINK"]
out_dir = os.environ["OUT_DIR"]
prov_root = os.environ["PROV_ROOT"]
extra_args = json.loads(os.environ.get("EXEC_LOG_JSON") or "[]")

git_base = [
    "/usr/bin/git",
    "--no-replace-objects",
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.sshCommand=",
]


def die(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr)
    sys.exit(1)


try:
    diag_data = subprocess.check_output(
        [*git_base, "show", f"{start_sha}:scripts/backlog-burn-agent-diag.sh"]
    )
except subprocess.CalledProcessError:
    die(f"could not restore backlog-burn-agent-diag.sh from {start_sha}")
if hashlib.sha256(diag_data).hexdigest() != diag_sha:
    die("restored backlog-burn-agent-diag.sh sha256 does not match the pre-agent pin")

try:
    arch_data = subprocess.check_output(
        [*git_base, "archive", start_sha, "tools/provenance/src"]
    )
except subprocess.CalledProcessError:
    die(f"could not archive tools/provenance/src from {start_sha}")
if hashlib.sha256(arch_data).hexdigest() != arch_sha:
    die("restored tools/provenance/src archive sha256 does not match the pre-agent pin")

# Extract from the verified buffer — never re-read a pathname.
with tarfile.open(fileobj=BytesIO(arch_data), mode="r:") as tar:
    tar.extractall(path=prov_root)
prov_src = os.path.join(prov_root, "tools", "provenance", "src")
if not os.path.isdir(os.path.join(prov_src, "provenance")):
    die(f"pinned provenance archive missing provenance package at {prov_src}")

# Bind execution to the verified diag bytes via memfd (Linux runners).
if not hasattr(os, "memfd_create"):
    die("memfd_create unavailable — cannot bind diag execution to verified bytes")
fd = os.memfd_create("backlog-burn-agent-diag", 0)
try:
    os.write(fd, diag_data)
    os.lseek(fd, 0, os.SEEK_SET)
    # Re-hash the open fd contents before launch.
    got = hashlib.sha256(os.read(fd, len(diag_data) + 1)).hexdigest()
    if got != diag_sha:
        die("memfd diag bytes drifted from the pre-agent pin before launch")
    os.lseek(fd, 0, os.SEEK_SET)
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "GITHUB_TOKEN",
            "GH_TOKEN",
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ZAI_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "REGEN_TOKEN",
            "ACTIONS_RUNTIME_TOKEN",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
        }
    }
    # Address the open memfd via this process's pid — a child bash's
    # /proc/self/fd would not see the parent's descriptor.
    script_path = f"/proc/{os.getpid()}/fd/{fd}"
    cmd = [
        "/usr/bin/bash",
        script_path,
        "--link",
        link,
        "--secrets-file",
        secrets_file,
        "--provenance-src",
        prov_src,
        "--out-dir",
        out_dir,
        *extra_args,
    ]
    proc = subprocess.run(cmd, env=env, check=False)
finally:
    os.close(fd)

if proc.returncode != 0:
    sys.exit(proc.returncode)
print(prov_src)
PY
)"
prov_src="${prov_src:?pinned provenance restore failed}"

raw_diag="${out_dir}/diag.json"
if [ ! -f "$raw_diag" ] || [ -L "$raw_diag" ]; then
  echo "::error::diag did not write a regular diag.json" >&2
  exit 1
fi

# Validate schema + re-scrub denied-tool fields with pinned provenance
# (SECRETS_FILE values + credential_env forms + pattern shapes). Refuse
# anything that is not our payload shape (blocks planting the execution
# log). Final assistant message text is never in the payload — only
# length + sha256 (MED-1 / MED-C).
validated="$(mktemp "${RUNNER_TEMP}/backlog-burn-diag-validated.XXXXXX")"
cleanup_paths+=("$validated")
python3 -I - "$prov_src" "$raw_diag" "$validated" "$SECRETS_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path

prov_src, raw_path, out_path, secrets_path = sys.argv[1:5]
sys.path.insert(0, prov_src)
from provenance.gitstore import credential_env, scrub  # noqa: E402

ALLOWED = {
    "label",
    "log_note",
    "denied_tools",
    "denied_tools_extra",
    "final_assistant_message_len",
    "final_assistant_message_sha256",
}
MAX_BYTES = 64 * 1024
MAX_DENIALS = 12
# MED-A (#953): keep in sync with backlog-burn-agent-diag.sh and the
# upload-diag schema check in .github/workflows/backlog-burn.yml.
KNOWN_TOOLS = frozenset(
    {
        "Bash",
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "Glob",
        "Grep",
        "LS",
        "WebFetch",
        "WebSearch",
        "Task",
        "TodoWrite",
        "NotebookEdit",
        "NotebookRead",
        "BashOutput",
        "KillBash",
        "KillShell",
        "ExitPlanMode",
        "SlashCommand",
        "Agent",
        "Skill",
    }
)
_MCP_TOOL = re.compile(r"^mcp__[A-Za-z0-9_-]{1,64}__[A-Za-z0-9_-]{1,64}$")
_OTHER = "(other)"
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def tool_allowed(name: str) -> bool:
    return name == _OTHER or name in KNOWN_TOOLS or _MCP_TOOL.fullmatch(name) is not None

raw_secrets = [
    line.strip()
    for line in Path(secrets_path).read_text(encoding="utf-8", errors="replace").splitlines()
    if line.strip()
]
secrets: list[str] = []
for s in raw_secrets:
    secrets.append(s)
    try:
        _cred, b64 = credential_env(s)
        secrets.append(b64)
        secrets.append(_cred.get("GIT_CONFIG_VALUE_0", ""))
    except Exception:  # noqa: BLE001
        pass


def S(text: str) -> str:
    return scrub(text or "", secrets)


# Bound the read before allocating the whole file (CodeRabbit on #953).
with Path(raw_path).open("rb") as fh:
    raw = fh.read(MAX_BYTES + 1)
if len(raw) > MAX_BYTES:
    print(f"::error::diag.json too large (>{MAX_BYTES} bytes)", file=sys.stderr)
    sys.exit(1)
try:
    text = raw.decode("utf-8")
    obj = json.loads(text)
except (UnicodeDecodeError, json.JSONDecodeError):
    # Do not echo the rejected payload or exception text that may carry it.
    print("::error::diag.json failed UTF-8 JSON schema rule", file=sys.stderr)
    sys.exit(1)
if not isinstance(obj, dict) or set(obj.keys()) != ALLOWED:
    # Report the rule, never the rejected keys/values (CodeRabbit on #953).
    print("::error::diag.json failed allowlisted-keys schema rule", file=sys.stderr)
    sys.exit(1)
if not isinstance(obj["label"], str) or not isinstance(obj["log_note"], str):
    print("::error::diag.json failed label/log_note type schema rule", file=sys.stderr)
    sys.exit(1)
if "final_assistant_message_truncated" in obj:
    print(
        "::error::diag.json failed no-message-text schema rule",
        file=sys.stderr,
    )
    sys.exit(1)
msg_len = obj["final_assistant_message_len"]
if type(msg_len) is not int or isinstance(msg_len, bool) or msg_len < 0:
    print("::error::diag.json failed message-len schema rule", file=sys.stderr)
    sys.exit(1)
msg_sha = obj["final_assistant_message_sha256"]
if not isinstance(msg_sha, str) or not _SHA256_HEX.fullmatch(msg_sha):
    print("::error::diag.json failed message-sha256 schema rule", file=sys.stderr)
    sys.exit(1)
if not isinstance(obj["denied_tools"], list) or len(obj["denied_tools"]) > MAX_DENIALS:
    print("::error::diag.json failed denied_tools schema rule", file=sys.stderr)
    sys.exit(1)
extra = obj["denied_tools_extra"]
if type(extra) is not int or isinstance(extra, bool) or extra < 0:
    print("::error::diag.json failed denied_tools_extra schema rule", file=sys.stderr)
    sys.exit(1)
clean_denials = []
seen_tools = set()
for row in obj["denied_tools"]:
    # Tool name only — refuse a reason/input field (Agentic Security on #953).
    if not isinstance(row, dict) or set(row.keys()) != {"tool"}:
        print("::error::diag.json failed denial-row schema rule", file=sys.stderr)
        sys.exit(1)
    tool = str(row.get("tool") or "")
    # MED-A: refuse planted free text — allowlist / mcp pattern / "(other)" only.
    # Do not scrub-then-accept into the allowlist: scrub cannot turn arbitrary
    # text into a known tool name. But DO scrub an already-shaped mcp__ name
    # and collapse to "(other)" if a credential pattern fires (Bugbot on #953).
    if not tool_allowed(tool):
        print(
            "::error::diag.json failed denial-tool allowlist schema rule",
            file=sys.stderr,
        )
        sys.exit(1)
    if tool != _OTHER and tool not in KNOWN_TOOLS:
        scrubbed = S(tool)
        if scrubbed != tool:
            tool = _OTHER
    if tool in seen_tools:
        # Dedup after scrub collapse (two secret-shaped mcp names → one other).
        continue
    seen_tools.add(tool)
    clean_denials.append({"tool": tool})

payload = {
    "label": S(obj["label"])[:200],
    "log_note": S(obj["log_note"])[:300],
    "denied_tools": clean_denials,
    "denied_tools_extra": extra,
    "final_assistant_message_len": msg_len,
    "final_assistant_message_sha256": msg_sha,
}
Path(out_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY

# Atomic publish to DIAG_OUT (caller-owned path; typically a mktemp file).
# Do not leave the validated bytes under a well-known RUNNER_TEMP tree.
cp -f -- "$validated" "$DIAG_OUT"
chmod 600 -- "$DIAG_OUT" 2>/dev/null || true
