#!/usr/bin/env bash
# backlog-burn-agent-diag.sh — sanitized post-agent diagnostic for backlog-burn.
#
# Reads the claude-code-action execution log (present even when
# show_full_output stays false) and writes ONLY:
#   * denied tool names + deny reasons
#   * a truncated final assistant message (<= 500 chars)
# through the repo's existing redactor (provenance.gitstore.redact). Never
# enables show_full_output; never prints tokens / raw gh output / headers.
#
# Usage:
#   scripts/backlog-burn-agent-diag.sh [--link <n>] [--execution-log <path>]
#                                     [--out-dir <dir>] [--summary <path>]
#
# Defaults: execution log at $RUNNER_TEMP/claude-execution-output.json,
# out-dir $RUNNER_TEMP/backlog-burn-agent-diag, summary $GITHUB_STEP_SUMMARY.
set -euo pipefail

link=""
execution_log="${RUNNER_TEMP:+$RUNNER_TEMP/claude-execution-output.json}"
out_dir="${RUNNER_TEMP:+$RUNNER_TEMP/backlog-burn-agent-diag}"
summary_path="${GITHUB_STEP_SUMMARY:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --link) link="${2:?}"; shift 2 ;;
    --execution-log) execution_log="${2:?}"; shift 2 ;;
    --out-dir) out_dir="${2:?}"; shift 2 ;;
    --summary) summary_path="${2:?}"; shift 2 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "backlog-burn-agent-diag: unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
out_dir="${out_dir:-/tmp/backlog-burn-agent-diag}"
mkdir -p -- "$out_dir"

# Collect secret values to feed the existing redactor. Never print them.
# Empty entries are ignored by redact().
secrets_file="$(mktemp)"
cleanup() { rm -f -- "$secrets_file"; }
trap cleanup EXIT
{
  for key in \
    GITHUB_TOKEN GH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN \
    ZAI_KEY OPENAI_API_KEY OPENROUTER_API_KEY REGEN_TOKEN \
    ACTIONS_RUNTIME_TOKEN ACTIONS_ID_TOKEN_REQUEST_TOKEN
  do
    # ${!key} is bash nameref expansion; skip unset / empty.
    val="${!key-}"
    if [ -n "$val" ]; then
      printf '%s\n' "$val"
    fi
  done
} >"$secrets_file"

label="backlog-burn agent diag"
[ -n "$link" ] && label="$label (link $link)"

python3 -I - "$execution_log" "$secrets_file" "$out_dir" "$label" "$summary_path" "$repo_root" <<'PY'
import json
import os
import re
import sys
from pathlib import Path

log_path, secrets_path, out_dir, label, summary_path, repo_root = sys.argv[1:7]

sys.path.insert(0, str(Path(repo_root) / "tools" / "provenance" / "src"))
from provenance.gitstore import redact  # noqa: E402  — existing redactor

secrets = [
    line.strip()
    for line in Path(secrets_path).read_text(encoding="utf-8", errors="replace").splitlines()
    if line.strip()
]

def R(text: str) -> str:
    return redact(text or "", secrets)

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
        structured.append({
            "tool": R(str(name)) if name else R(json.dumps(d)[:200]),
            "reason": R(str(reason))[:300] if reason else "",
        })
    else:
        structured.append({"tool": R(str(d)[:200]), "reason": ""})

if not structured and raw:
    for m in re.finditer(
        r"(?:denied|permission_denial|PermissionDenied)[^\n]{0,160}"
        r"(Bash\([^)]*\)|Write|Edit|mcp__\w+|NotebookEdit|Agent|Skill|Read|Glob|Grep)",
        raw,
        re.I,
    ):
        structured.append({"tool": R(m.group(1)), "reason": R(m.group(0)[:200])})

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

final_trunc = R(final_msg)[:500]

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
if summary_path:
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write(block)
        fh.write("\n")
print(f"::notice::{label}: wrote {out_path} ({len(uniq)} denied tool(s))")
PY
