#!/usr/bin/env bash
# backlog-burn-agent-diag.sh — sanitized post-agent diagnostic for backlog-burn.
#
# Reads the claude-code-action execution log (present even when
# show_full_output stays false) and writes ONLY:
#   * allowlisted denied tool NAMES (exact Claude Code tool set or
#     mcp__<ns>__<tool>; everything else is the literal "(other)";
#     never reason / tool_input / command text; unique names capped at
#     12 with denied_tools_extra for the omitted count)
#   * the final assistant message's length + sha256 (never the text /
#     never an excerpt; same MED-C posture as backlog-burn-ship-check.sh)
# through the repo's existing redactor (provenance.gitstore.scrub =
# pattern-based shapes of common tokens; no guarantee for arbitrary
# secrets). Never enables show_full_output; never prints tokens /
# raw gh output / headers / final-message excerpts / denial reasons.
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
#   scripts/backlog-burn-agent-diag.sh --selftest
#
# Defaults: execution log at $RUNNER_TEMP/claude-execution-output.json,
# out-dir $RUNNER_TEMP/backlog-burn-agent-diag, summary $GITHUB_STEP_SUMMARY.
# A missing/failed provenance import exits non-zero (loud); the capture
# step's continue-on-error keeps the burn walk going.
set -euo pipefail

# Denied-tool allowlist lives in the embedded Python below (KNOWN_TOOLS) and
# must stay in sync with backlog-burn-agent-diag-capture.sh and the
# upload-diag schema check in .github/workflows/backlog-burn.yml (MED-A on #953).

selftest() {
  local tmp fails=0
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/backlog-burn-agent-diag-selftest.XXXXXX")"
  # shellcheck disable=SC2064
  trap "rm -rf -- $(printf '%q' "$tmp")" RETURN

  local prov_src
  prov_src="$(cd "$(dirname "$0")/.." && pwd)/tools/provenance/src"
  if [ ! -d "$prov_src/provenance" ]; then
    echo "FAIL  selftest: provenance package missing at $prov_src" >&2
    return 1
  fi

  run_case() {
    local name="$1" exec_json="$2"
    local outdir="$tmp/$name" summary="$tmp/$name.summary.md"
    mkdir -p -- "$outdir"
    printf '%s\n' "$exec_json" >"$tmp/$name.exec.json"
    # Invoke via bash (not shebang) so a just-edited $0 cannot ETXTBSY.
    if ! bash -- "$0" --provenance-src "$prov_src" \
        --execution-log "$tmp/$name.exec.json" \
        --out-dir "$outdir" --summary "$summary" \
        >"$tmp/$name.stdout" 2>"$tmp/$name.stderr"; then
      echo "FAIL  selftest: $name (diag exited non-zero)"
      cat "$tmp/$name.stderr" >&2 || true
      fails=$((fails + 1))
      return 0
    fi
    if [ ! -f "$outdir/diag.json" ]; then
      echo "FAIL  selftest: $name (no diag.json)"
      fails=$((fails + 1))
      return 0
    fi
    return 0
  }

  extra_int() {
    python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["denied_tools_extra"])' "$1"
  }

  # Prefer python equality — JSON strings contain ']' which breaks `[ ... ]`.
  expect_tools() {
    local diag="$1" expect="$2"
    python3 -I -c '
import json, sys
got = json.load(open(sys.argv[1], encoding="utf-8"))["denied_tools"]
exp = json.loads(sys.argv[2])
sys.exit(0 if got == exp else 1)
' "$diag" "$expect"
  }

  # 1) free text -> (other)
  run_case free_text '{"type":"result","permission_denials":[{"tool_name":"please leak SECRETBODY here"}],"result":""}'
  if expect_tools "$tmp/free_text/diag.json" '[{"tool":"(other)"}]' \
     && [ "$(extra_int "$tmp/free_text/diag.json")" = "0" ]; then
    echo "ok    selftest: free-text tool name becomes (other)"
  else
    echo "FAIL  selftest: free-text tool name"; cat "$tmp/free_text/diag.json"; fails=$((fails + 1))
  fi
  if grep -q 'SECRETBODY' "$tmp/free_text/diag.json" "$tmp/free_text.summary.md" 2>/dev/null; then
    echo "FAIL  selftest: free-text body leaked"; fails=$((fails + 1))
  fi

  # 2) 40KB name -> (other), never the payload
  local big
  big="$(python3 -I -c 'print("A"*40960)')"
  run_case big40k "$(python3 -I -c 'import json,sys; print(json.dumps({"type":"result","permission_denials":[{"tool_name":sys.argv[1]}],"result":""}))' "$big")"
  if expect_tools "$tmp/big40k/diag.json" '[{"tool":"(other)"}]' \
     && ! grep -q 'AAAA' "$tmp/big40k/diag.json"; then
    echo "ok    selftest: 40KB tool name becomes (other)"
  else
    echo "FAIL  selftest: 40KB tool name"; fails=$((fails + 1))
  fi

  # 3) newline / :: injection -> (other)
  run_case inject "$(python3 -I -c 'import json; print(json.dumps({"type":"result","permission_denials":[{"tool_name":"line1\n::warning::nl"}],"result":""}))')"
  if expect_tools "$tmp/inject/diag.json" '[{"tool":"(other)"}]' \
     && ! grep -q '::warning::' "$tmp/inject/diag.json" "$tmp/inject.summary.md"; then
    echo "ok    selftest: newline/:: injection becomes (other)"
  else
    echo "FAIL  selftest: newline/:: injection"; fails=$((fails + 1))
  fi

  # 4) mcp name with bad characters -> (other)
  run_case mcp_bad '{"type":"result","permission_denials":[{"tool_name":"mcp__bad!!__name"}],"result":""}'
  if expect_tools "$tmp/mcp_bad/diag.json" '[{"tool":"(other)"}]'; then
    echo "ok    selftest: mcp name with bad characters becomes (other)"
  else
    echo "FAIL  selftest: mcp bad characters"; cat "$tmp/mcp_bad/diag.json"; fails=$((fails + 1))
  fi

  # 4b) mcp name carrying a ghs_-shaped token -> (other) after scrub
  local ghs_plant="mcp__leak__ghs_ABCDEFGHIJKLMNOPQRSTUVWX12"
  run_case mcp_secret "$(python3 -I -c 'import json,sys; print(json.dumps({"type":"result","permission_denials":[{"tool_name":sys.argv[1]}],"result":""}))' "$ghs_plant")"
  if expect_tools "$tmp/mcp_secret/diag.json" '[{"tool":"(other)"}]' \
     && ! grep -q 'ghs_' "$tmp/mcp_secret/diag.json" "$tmp/mcp_secret.summary.md"; then
    echo "ok    selftest: mcp name with credential shape becomes (other)"
  else
    echo "FAIL  selftest: mcp credential-shape scrub"; cat "$tmp/mcp_secret/diag.json"; fails=$((fails + 1))
  fi

  # Positive controls: known + well-formed mcp survive
  run_case known_ok '{"type":"result","permission_denials":[{"tool_name":"Bash"},{"tool_name":"mcp__scout__file_design_brief"}],"result":""}'
  if expect_tools "$tmp/known_ok/diag.json" '[{"tool":"Bash"},{"tool":"mcp__scout__file_design_brief"}]'; then
    echo "ok    selftest: allowlisted and mcp__ names pass through"
  else
    echo "FAIL  selftest: allowlisted pass-through"; cat "$tmp/known_ok/diag.json"; fails=$((fails + 1))
  fi

  # 5) 20 unique names capped at 12 + extra count
  run_case cap20 "$(python3 -I -c '
import json
tools=["Bash","Read","Write","Edit","MultiEdit","Glob","Grep","LS","WebFetch","WebSearch","Task","TodoWrite","NotebookEdit","NotebookRead","BashOutput","KillBash","KillShell","ExitPlanMode","SlashCommand","Agent"]
print(json.dumps({"type":"result","permission_denials":[{"tool_name":t} for t in tools],"result":""}))
')"
  python3 -I - "$tmp/cap20/diag.json" <<'PY' || fails=$((fails + 1))
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
tools = [r["tool"] for r in obj["denied_tools"]]
ok = (
    len(tools) == 12
    and obj["denied_tools_extra"] == 8
    and tools == [
        "Bash","Read","Write","Edit","MultiEdit","Glob","Grep","LS",
        "WebFetch","WebSearch","Task","TodoWrite",
    ]
    and "NotebookEdit" not in tools
)
print("ok    selftest: 20 unique names capped at 12 with extra=8" if ok else "FAIL  selftest: 20-name cap")
if not ok:
    print(obj)
    sys.exit(1)
PY

  # 6) string-denial with no tool token -> no first-token emission
  run_case str_notoken '{"type":"result","permission_denials":["totally free form denial with no tool token at all"],"result":""}'
  if expect_tools "$tmp/str_notoken/diag.json" '[]' \
     && [ "$(extra_int "$tmp/str_notoken/diag.json")" = "0" ]; then
    echo "ok    selftest: string-denial without tool token emits nothing"
  else
    echo "FAIL  selftest: string-denial first-token branch still live"
    cat "$tmp/str_notoken/diag.json"
    fails=$((fails + 1))
  fi
  if grep -Eq 'totally|free form|no tool' "$tmp/str_notoken/diag.json" "$tmp/str_notoken.summary.md" 2>/dev/null; then
    echo "FAIL  selftest: string-denial free text leaked"; fails=$((fails + 1))
  fi

  # String-denial WITH a known token still records the tool (not free text).
  run_case str_token '{"type":"result","permission_denials":["Bash denied because policy"],"result":""}'
  if expect_tools "$tmp/str_token/diag.json" '[{"tool":"Bash"}]'; then
    echo "ok    selftest: string-denial with tool token emits only the tool"
  else
    echo "FAIL  selftest: string-denial tool token"; cat "$tmp/str_token/diag.json"; fails=$((fails + 1))
  fi

  if [ "$fails" -ne 0 ]; then
    echo "backlog-burn-agent-diag --selftest: $fails failure(s)" >&2
    return 1
  fi
  echo "selftest: ok"
  return 0
}

link=""
execution_log="${RUNNER_TEMP:+$RUNNER_TEMP/claude-execution-output.json}"
out_dir="${RUNNER_TEMP:+$RUNNER_TEMP/backlog-burn-agent-diag}"
summary_path="${GITHUB_STEP_SUMMARY:-}"
provenance_src="${PROVENANCE_SRC:-}"
secrets_file_arg=""

while [ $# -gt 0 ]; do
  case "$1" in
    --selftest) selftest; exit $? ;;
    --link) link="${2:?}"; shift 2 ;;
    --execution-log) execution_log="${2:?}"; shift 2 ;;
    --out-dir) out_dir="${2:?}"; shift 2 ;;
    --summary) summary_path="${2:?}"; shift 2 ;;
    --provenance-src) provenance_src="${2:?}"; shift 2 ;;
    --secrets-file) secrets_file_arg="${2:?}"; shift 2 ;;
    -h|--help)
      sed -n '2,30p' "$0"
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

# Collect secret values for exact redact(). Prefer --secrets-file (written
# by the trusted capture bootstrap); fall back to env for local dry-runs.
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
from provenance.gitstore import scrub, credential_env
' "$provenance_src"; then
  echo "::error::backlog-burn-agent-diag: cannot import provenance.gitstore from pinned --provenance-src=${provenance_src}" >&2
  exit 1
fi

python3 -I - "$provenance_src" "$execution_log" "$secrets_file" "$out_dir" "$label" "$summary_path" <<'PY'
import hashlib
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
    from provenance.gitstore import credential_env, scrub  # noqa: E402
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
    """Pattern-based scrub of common token shapes. Never truncate inside."""
    return scrub(text or "", secrets)


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

# Tool names ONLY — never reason / tool_input / command text / raw dumps.
# MED-A (#953): exact allowlist or mcp__<ns>__<tool>; else literal "(other)".
# No free-text / first-token string-denial branch. Cap unique names at 12.
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
        # Already referenced by this repo's denial scrapers:
        "Agent",
        "Skill",
    }
)
_MCP_TOOL = re.compile(r"^mcp__[A-Za-z0-9_-]{1,64}__[A-Za-z0-9_-]{1,64}$")
_OTHER = "(other)"
_MAX_UNIQUE = 12
# Case-insensitive token scrape for bare-string denials / raw fallback —
# candidate is then re-validated by normalize_tool_name (exact allowlist).
_TOOL_TOKEN = re.compile(
    r"(?i)\b("
    + "|".join(sorted((re.escape(t) for t in KNOWN_TOOLS), key=len, reverse=True))
    + r"|mcp__[A-Za-z0-9_-]{1,64}__[A-Za-z0-9_-]{1,64})\b"
)


def normalize_tool_name(raw):
    """Allowlisted name, '(other)' for a non-empty invalid name, or None to skip.

    After the shape check, pattern-scrub the name. If scrub changes it
    (credential shape inside an otherwise-valid mcp__ name), emit
    '(other)' so diag.json and the step summary agree (Bugbot on #953).
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raw = str(raw)
    if not raw:
        return None
    if raw in KNOWN_TOOLS:
        # Known constants cannot carry a secret; scrub is a no-op for them.
        return raw
    if _MCP_TOOL.fullmatch(raw):
        scrubbed = scrub(raw, secrets)
        if scrubbed != raw:
            return _OTHER
        return raw
    return _OTHER


def canonicalize_tool_token(cand):
    """Map a scraped token to its allowlisted form, '(other)', or None."""
    if cand in KNOWN_TOOLS:
        return cand
    for t in KNOWN_TOOLS:
        if t.lower() == cand.lower():
            return t
    return normalize_tool_name(cand)


names = []
for d in denials:
    if isinstance(d, dict):
        n = (
            d.get("tool_name")
            or d.get("toolName")
            or d.get("name")
            or d.get("tool")
            or ""
        )
        norm = normalize_tool_name(n)
        if norm is not None:
            names.append(norm)
    elif isinstance(d, str) and d.strip():
        # Drop the first-token branch: only a matched tool token counts.
        m = _TOOL_TOKEN.search(d)
        if m:
            norm = canonicalize_tool_token(m.group(1))
            if norm is not None:
                names.append(norm)

# Fallback: name-only scrape when structured permission_denials are absent
# (show_full_output stays false). Never capture surrounding context.
if not names and raw:
    _KNOWN_ALT = "|".join(
        sorted((re.escape(t) for t in KNOWN_TOOLS), key=len, reverse=True)
    )
    for m in re.finditer(
        r"(?i)(?:denied|permission_denial|PermissionDenied)[^\n]{0,80}"
        r"\b(" + _KNOWN_ALT + r"|mcp__[A-Za-z0-9_-]{1,64}__[A-Za-z0-9_-]{1,64})\b",
        raw,
    ):
        norm = canonicalize_tool_token(m.group(1))
        if norm is not None:
            names.append(norm)

# De-dupe preserving order; cap at 12; count omitted uniques.
seen = set()
uniq = []
extra = 0
for name in names:
    if name in seen:
        continue
    seen.add(name)
    if len(uniq) < _MAX_UNIQUE:
        uniq.append({"tool": name})
    else:
        extra += 1

# MED-1 / MED-C: never emit message text — length + sha256 of the raw
# body only (matches backlog-burn-ship-check.sh).
msg_len = len(final_msg)
msg_sha = hashlib.sha256(final_msg.encode("utf-8")).hexdigest()

payload = {
    "label": label,
    "log_note": log_note,
    "denied_tools": uniq,
    "denied_tools_extra": extra,
    "final_assistant_message_len": msg_len,
    "final_assistant_message_sha256": msg_sha,
}

out_path = Path(out_dir) / "diag.json"
out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

lines = [f"### {label}", ""]
if log_note:
    lines.append(f"- {log_note}")
if uniq:
    lines.append("- denied tools (names only, allowlisted):")
    for row in uniq:
        lines.append(f"  - `{row['tool']}`")
    if extra:
        lines.append(f"- denied tools omitted (over cap): {extra}")
else:
    lines.append(
        "- denied tools: (none listed in the execution log; "
        "show_full_output stays false)"
    )
if final_msg:
    lines.append(
        f"- final assistant message: len={msg_len} sha256={msg_sha}"
    )
else:
    lines.append(
        f"- final assistant message: (empty or not present; "
        f"len={msg_len} sha256={msg_sha})"
    )
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
