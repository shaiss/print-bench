#!/usr/bin/env bash
# backlog-burn-agent-diag.sh — sanitized post-agent diagnostic for backlog-burn.
#
# Reads the claude-code-action execution log (present even when
# show_full_output stays false) and writes ONLY:
#   * denied tool names + deny reasons
#   * a truncated final assistant message (<= 500 chars)
# through the repo's existing redactor (provenance.gitstore.scrub =
# exact known secrets + pattern-based shapes). Never enables
# show_full_output; never prints tokens / raw gh output / headers.
#
# MUST be restored from the pre-agent START_SHA pin into $RUNNER_TEMP
# (see backlog-burn-agent-diag-capture.sh) — never run the worktree copy
# after a ship agent that has Write/Edit. The redactor package is passed
# explicitly via --provenance-src (also restored from START_SHA); this
# script never derives an import path from dirname "$0" (which points into
# RUNNER_TEMP after the restore move) and never imports the PR worktree.
#
# Usage:
#   scripts/backlog-burn-agent-diag.sh --provenance-src <dir> \
#     [--link <n>] [--execution-log <path>] [--secrets-file <path>] \
#     [--out-dir <dir>] [--summary <path>]
#
# Defaults: execution log at $RUNNER_TEMP/claude-execution-output.json,
# out-dir $RUNNER_TEMP/backlog-burn-agent-diag, summary $GITHUB_STEP_SUMMARY.
# A missing/failed provenance import exits non-zero (loud); the capture
# step's continue-on-error keeps the burn walk going.
set -euo pipefail

link=""
execution_log="${RUNNER_TEMP:+$RUNNER_TEMP/claude-execution-output.json}"
out_dir="${RUNNER_TEMP:+$RUNNER_TEMP/backlog-burn-agent-diag}"
summary_path="${GITHUB_STEP_SUMMARY:-}"
provenance_src="${PROVENANCE_SRC:-}"
secrets_file_arg=""

while [ $# -gt 0 ]; do
  case "$1" in
    --link) link="${2:?}"; shift 2 ;;
    --execution-log) execution_log="${2:?}"; shift 2 ;;
    --out-dir) out_dir="${2:?}"; shift 2 ;;
    --summary) summary_path="${2:?}"; shift 2 ;;
    --provenance-src) provenance_src="${2:?}"; shift 2 ;;
    --secrets-file) secrets_file_arg="${2:?}"; shift 2 ;;
    -h|--help)
      sed -n '2,28p' "$0"
      exit 0
      ;;
    *)
      echo "backlog-burn-agent-diag: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$provenance_src" ]; then
  echo "backlog-burn-agent-diag: --provenance-src (or PROVENANCE_SRC) is required" >&2
  echo "  pass the pinned tools/provenance/src restored from START_SHA into \$RUNNER_TEMP" >&2
  exit 2
fi
if [ ! -d "$provenance_src/provenance" ]; then
  echo "backlog-burn-agent-diag: --provenance-src must contain the provenance package: $provenance_src" >&2
  exit 2
fi

out_dir="${out_dir:-/tmp/backlog-burn-agent-diag}"
mkdir -p -- "$out_dir"

# Collect secret values for optional exact redact(). Capture no longer
# passes --secrets-file (exact rematerialization is unsafe); fall back to
# env for local dry-runs. Empty list ⇒ pattern-based scrub only.
secrets_file="$(mktemp)"
cleanup() { rm -f -- "$secrets_file"; }
trap cleanup EXIT
if [ -n "$secrets_file_arg" ]; then
  if [ ! -f "$secrets_file_arg" ]; then
    echo "backlog-burn-agent-diag: --secrets-file not found: $secrets_file_arg" >&2
    exit 2
  fi
  cp -- "$secrets_file_arg" "$secrets_file"
else
  {
    for key in \
      GITHUB_TOKEN GH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN \
      ZAI_KEY OPENAI_API_KEY OPENROUTER_API_KEY REGEN_TOKEN \
      ACTIONS_RUNTIME_TOKEN ACTIONS_ID_TOKEN_REQUEST_TOKEN
    do
      val="${!key-}"
      if [ -n "$val" ]; then
        printf '%s\n' "$val"
      fi
    done
  } >"$secrets_file"
fi

label="backlog-burn agent diag"
[ -n "$link" ] && label="$label (link $link)"

# Fail loud on import — do not fall back to the worktree.
# python3 -I ignores PYTHONPATH, so the pinned path is passed as argv and
# inserted onto sys.path inside the interpreter (never a worktree path).
if ! python3 -I -c '
import sys
from pathlib import Path
p = Path(sys.argv[1])
sys.path.insert(0, str(p))
from provenance.gitstore import scrub, scrub_then_truncate, credential_env
' "$provenance_src"; then
  echo "::error::backlog-burn-agent-diag: cannot import provenance.gitstore from pinned --provenance-src=${provenance_src}" >&2
  exit 1
fi

python3 -I - "$provenance_src" "$execution_log" "$secrets_file" "$out_dir" "$label" "$summary_path" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

provenance_src, log_path, secrets_path, out_dir, label, summary_path = sys.argv[1:7]

# Import path is ONLY the pinned --provenance-src argv (START_SHA archive).
# python3 -I ignores PYTHONPATH; never insert a worktree / dirname-derived root.
sys.path.insert(0, str(Path(provenance_src)))
try:
    from provenance.gitstore import (  # noqa: E402
        credential_env,
        scrub,
        scrub_then_truncate,
    )
except ImportError as exc:
    print(
        f"::error::backlog-burn-agent-diag: provenance.gitstore import failed: {exc}",
        file=sys.stderr,
    )
    sys.exit(1)

raw_secrets = [
    line.strip()
    for line in Path(secrets_path).read_text(encoding="utf-8", errors="replace").splitlines()
    if line.strip()
]
# Match Git.secrets(): redact the token AND its x-access-token base64 header
# form (and the AUTHORIZATION: basic … value). Actions masks the raw token
# but not the base64 form that can appear in git/gh output.
secrets: list[str] = []
for s in raw_secrets:
    secrets.append(s)
    try:
        _cred, b64 = credential_env(s)
        secrets.append(b64)
        secrets.append(_cred.get("GIT_CONFIG_VALUE_0", ""))
    except Exception:  # noqa: BLE001 — never fail closed on expand
        pass


def R(text: str) -> str:
    """Full scrub (exact secrets + patterns). Never truncate inside."""
    return scrub(text or "", secrets)


def RT(text: str, limit: int) -> str:
    """Scrub the FULL text, then truncate — never truncate first."""
    return scrub_then_truncate(text or "", limit, secrets)


denials = []
final_msg = ""
raw = ""
log_note = ""

if log_path and Path(log_path).is_file():
    try:
        raw = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        log_note = f"execution-log unreadable ({e})"
else:
    log_note = f"execution-log not found{(' at ' + log_path) if log_path else ''}"

objs = []
if raw:
    raw_s = raw.strip()
    if raw_s.startswith("["):
        try:
            parsed = json.loads(raw_s)
            if isinstance(parsed, list):
                objs = parsed
        except json.JSONDecodeError:
            objs = []
    elif raw_s.startswith("{"):
        try:
            objs = [json.loads(raw_s)]
        except json.JSONDecodeError:
            objs = []
    if not objs:
        dec = json.JSONDecoder()
        idx = 0
        while idx < len(raw_s):
            while idx < len(raw_s) and raw_s[idx].isspace():
                idx += 1
            if idx >= len(raw_s):
                break
            try:
                obj, end = dec.raw_decode(raw_s, idx)
            except json.JSONDecodeError:
                break
            objs.append(obj)
            idx = end

for obj in objs:
    if not isinstance(obj, dict):
        continue
    for key in ("permission_denials", "permissionDenials"):
        dens = obj.get(key)
        if isinstance(dens, list):
            denials.extend(dens)
    # Final assistant text: prefer the result envelope, else last assistant msg.
    if obj.get("type") == "result":
        res = obj.get("result") or ""
        if isinstance(res, str) and res.strip():
            final_msg = res.strip()
    if not final_msg and obj.get("type") == "assistant":
        msg = obj.get("message") or obj.get("content") or ""
        if isinstance(msg, list):
            bits = []
            for part in msg:
                if isinstance(part, dict) and part.get("type") == "text":
                    bits.append(str(part.get("text") or ""))
                elif isinstance(part, str):
                    bits.append(part)
            cand = "".join(bits).strip()
            if cand:
                final_msg = cand
        elif isinstance(msg, str) and msg.strip():
            final_msg = msg.strip()
        elif isinstance(msg, dict):
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                final_msg = content.strip()
            elif isinstance(content, list):
                bits = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        bits.append(str(part.get("text") or ""))
                cand = "".join(bits).strip()
                if cand:
                    final_msg = cand

# Fallback: scrape denial mentions from the raw text when structured
# permission_denials are absent (show_full_output stays false).
structured = []
for d in denials:
    if isinstance(d, dict):
        name = (
            d.get("tool_name")
            or d.get("toolName")
            or d.get("name")
            or d.get("tool")
            or ""
        )
        reason = (
            d.get("reason")
            or d.get("message")
            or d.get("error")
            or d.get("rule")
            or ""
        )
        # Scrub FULL strings, then truncate — never [:N] before scrub.
        if name:
            tool = RT(str(name), 200)
        else:
            tool = RT(json.dumps(d), 200)
        structured.append({
            "tool": tool,
            "reason": RT(str(reason), 300) if reason else "",
        })
    else:
        structured.append({"tool": RT(str(d), 200), "reason": ""})

if not structured and raw:
    for m in re.finditer(
        r"(?:denied|permission_denial|PermissionDenied)[^\n]{0,160}"
        r"(Bash\([^)]*\)|Write|Edit|mcp__\w+|NotebookEdit|Agent|Skill|Read|Glob|Grep)",
        raw,
        re.I,
    ):
        structured.append({
            "tool": RT(m.group(1), 200),
            "reason": RT(m.group(0), 200),
        })

# De-dupe by tool name, keep first reason.
seen = set()
uniq = []
for row in structured:
    key = row["tool"]
    if key in seen:
        continue
    seen.add(key)
    uniq.append(row)
    if len(uniq) >= 40:
        break

final_trunc = RT(final_msg, 500)

payload = {
    "label": label,
    "log_note": log_note,
    "denied_tools": uniq,
    "final_assistant_message_truncated": final_trunc,
}

out_path = Path(out_dir) / "diag.json"
out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

lines = [f"### {label}", ""]
if log_note:
    lines.append(f"- {log_note}")
if uniq:
    lines.append("- denied tools:")
    for row in uniq:
        if row["reason"]:
            lines.append(f"  - `{row['tool']}` — {row['reason']}")
        else:
            lines.append(f"  - `{row['tool']}`")
else:
    lines.append(
        "- denied tools: (none listed in the execution log; "
        "show_full_output stays false)"
    )
lines.append("- final assistant message (<=500 chars, redacted):")
if final_trunc:
    lines.append("")
    lines.append("```")
    lines.append(final_trunc)
    lines.append("```")
else:
    lines.append("  (empty)")
lines.append("")
block = "\n".join(lines)

# Step summary (optional) + always echo a short notice for the log.
# Scrub the summary block too (belt and braces — fields already scrubbed).
block = R(block)
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(block)
        fh.write("\n")
print(f"::notice::{label}: wrote {out_path} ({len(uniq)} denied tool(s))")
PY
