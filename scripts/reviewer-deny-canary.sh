#!/usr/bin/env bash
# Runtime deny canary for reviewer/coach backstop rule syntax (issue #776).
#
# scripts/reviewer-perms-check.sh checks the committed deny lists against a
# Python MODEL of Claude Code's matcher. This canary exercises the REAL
# matcher from the Claude Code build that auto-review.yml's pinned
# claude-code-action SHA actually installs. If that build drops mid-string
# `*`, `:*` word-boundary prefix, or `Edit(./.git/**)`, the rules in
# .claude/reviewer-settings.json / .claude/design-coach-settings.json silently
# stop blocking while the model — and every gate reading it — stays green.
#
# The action SHA does not bundle the CLI. It installs a version-pinned CLI
# at run time (`curl https://claude.ai/install.sh | bash -s -- 2.1.287`,
# hardcoded in the action's src/entrypoints/run.ts). That is not a moving
# latest, so the SHA pin DOES pin the matcher as long as install.sh honors
# the version argument. This canary re-proves that pin on the installed
# binary: extract the matcher, run one probe per syntax family, fail loudly
# if a denied probe is not refused.
#
# Usage:
#   scripts/reviewer-deny-canary.sh            # live: need claude 2.1.287
#   scripts/reviewer-deny-canary.sh --selftest # harness pass + fail, no CLI
#
# The live path is what .github/workflows/reviewer-deny-canary.yml runs
# (dispatchable; not a required / ci-ok check). check.sh runs --selftest.
set -euo pipefail

cd "$(dirname "$0")/.."

# The SHA auto-review.yml pins today (dependabot #765, v1.0.239). The issue
# text named an older SHA (9171db3e…); record a bump here if that pin moves.
PINNED_ACTION_SHA="97c53473391bff1901034d4b454b5bac7ab7a029"
PINNED_CLI_VERSION="2.1.287"

REVIEWER=".claude/reviewer-settings.json"
COACH=".claude/design-coach-settings.json"
AUTO_REVIEW=".github/workflows/auto-review.yml"

python3 - "$PINNED_ACTION_SHA" "$PINNED_CLI_VERSION" "${1:-}" <<'PY'
import json, os, re, subprocess, sys, textwrap
from pathlib import Path

PINNED_SHA, PINNED_CLI, mode = sys.argv[1], sys.argv[2], sys.argv[3]
SELFTEST = mode == "--selftest"
ROOT = Path(".").resolve()
REVIEWER = ROOT / ".claude/reviewer-settings.json"
COACH = ROOT / ".claude/design-coach-settings.json"
AUTO_REVIEW = ROOT / ".github/workflows/auto-review.yml"

# Byte markers of the 2.1.287 matcher module (contiguous ASCII in the native
# CLI). Absence = this build no longer carries the three syntax families.
EXTRACT_START = b'var Hg=new RegExp("\\x00ESCAPED_STAR\\x00","g")'
EXTRACT_END = b"function Okn("
KWE_NEEDLE = b"function kwe(e){return e.match(/^(.+):\\*$/)"
V8R_NEEDLE = b"function V8r(e){if(e.endsWith(\":*\"))"
DOLLAR8_NEEDLE = b"function $8(e,n,s=!1,r=!1)"
ZQE_NEEDLE = b"function ZQe(e){let n=kwe(e);"

# One probe per syntax family the backstops spell. (rule, probe, family,
# which committed file must contain the rule).
PROBES = [
    # :* word-boundary prefix (reviewer denies all git)
    ("Bash(git:*)", "git status", "colon-star-boundary", "reviewer"),
    # mid-string * (coach: global git options however ordered)
    ("Bash(git -*)", "git -C /tmp status", "mid-string-star", "coach"),
    ("Bash(git --git-dir*)", "git --git-dir=/path log", "mid-string-star", "coach"),
    # Edit path glob (coach; reviewer denies Edit outright)
    ("Edit(./.git/**)", "./.git/config", "edit-git-glob", "coach"),
]
# Boundary negative: :* must NOT match a longer token (the family is a
# word-boundary prefix, not a fnmatch prefix).
BOUNDARY_NEG = ("Bash(git:*)", "gitk", "colon-star-boundary")


class MatcherMissing(RuntimeError):
    pass


def die(msg, code=1):
    sys.stderr.write(f"reviewer-deny-canary: {msg}\n")
    sys.stderr.flush()
    sys.exit(code)


def deny_list(path: Path) -> list[str]:
    data = json.loads(path.read_text())
    return list(data.get("permissions", {}).get("deny", []))


def parse_rule(rule: str) -> tuple[str, str | None]:
    m = re.fullmatch(r"([A-Za-z][A-Za-z0-9_]*)\((.*)\)", rule)
    if not m:
        return rule, None
    return m.group(1), m.group(2)


# --- transcription of the 2.1.287 matcher (kwe / V8r / $8 / ZQe / prefix).
# Live runs ALSO eval the bytes extracted from the installed CLI via node and
# require agreement; this copy is the harness when node is absent (selftest).

def kwe(spec: str) -> str | None:
    m = re.match(r"^(.+):\*$", spec)
    return m.group(1) if m else None


def v8r(spec: str) -> bool:
    if spec.endswith(":*"):
        return False
    for n, ch in enumerate(spec):
        if ch != "*":
            continue
        s = 0
        r = n - 1
        while r >= 0 and spec[r] == "\\":
            s += 1
            r -= 1
        if s % 2 == 0:
            return True
    return False


def dollar8(pattern: str, command: str, case_insensitive=False, collapse_ws=False) -> bool:
    if "\x00" in pattern:
        return False
    i = pattern.strip()
    d = re.sub(r"[ \t]+", " ", i) if collapse_ws else i
    c = re.sub(r"[ \t]+", " ", command) if collapse_ws else command
    p_parts = []
    g = 0
    while g < len(d):
        P = d[g]
        if P == "\\" and g + 1 < len(d):
            j = d[g + 1]
            if j == "*":
                p_parts.append("\x00ESCAPED_STAR\x00")
                g += 2
                continue
            if j == "\\":
                p_parts.append("\x00ESCAPED_BACKSLASH\x00")
                g += 2
                continue
        p_parts.append(P)
        g += 1
    p = "".join(p_parts)
    escaped = re.sub(r"""[.+?^${}()|[\]\\'"]""", lambda m: "\\" + m.group(0), p)
    escaped = re.sub(r"/(?:\*\*/)+", "\x00GLOBSTAR\x00", escaped)
    escaped = escaped.replace("*", ".*")
    escaped = escaped.replace("\x00GLOBSTAR\x00", "/(?:.*/)?")
    escaped = escaped.replace("\x00ESCAPED_STAR\x00", r"\*")
    escaped = escaped.replace("\x00ESCAPED_BACKSLASH\x00", r"\\")
    star_count = p.count("*")
    if escaped.endswith(" .*") and star_count == 1:
        escaped = escaped[:-3] + "( .*)?"
    flags = re.DOTALL | (re.IGNORECASE if case_insensitive else 0)
    try:
        return re.match(r"^" + escaped + r"$", c, flags) is not None
    except re.error:
        return False


def zqe(spec: str) -> tuple[str, str]:
    prefix = kwe(spec)
    if prefix is not None:
        return "prefix", prefix
    if v8r(spec):
        return "wildcard", spec
    return "exact", spec


def bash_denied(spec: str, command: str) -> bool:
    kind, val = zqe(spec)
    cmd = command
    if kind == "exact":
        return val.lower() == cmd.lower()
    if kind == "prefix":
        cl, pl = cmd.lower(), val.lower()
        return cl == pl or cl.startswith(pl + " ")
    return dollar8(val, cmd, case_insensitive=True, collapse_ws=True)


def edit_denied(spec: str, path: str) -> bool:
    # File-pattern rules use the same $8 glob engine the Bash wildcard
    # family uses. Probe with the path spelling the rule names (./.git/…).
    return dollar8(spec, path, case_insensitive=True, collapse_ws=False)


def rule_refuses(rule: str, probe: str) -> bool:
    tool, spec = parse_rule(rule)
    if spec is None:
        return False
    if tool == "Bash":
        return bash_denied(spec, probe)
    if tool == "Edit":
        return edit_denied(spec, probe)
    return False


def check_pin():
    text = AUTO_REVIEW.read_text()
    uses = re.findall(
        r"uses:\s+anthropics/claude-code-action@([0-9a-f]{40})", text
    )
    if not uses:
        die(f"{AUTO_REVIEW} has no claude-code-action SHA pin")
    bad = sorted({s for s in uses if s != PINNED_SHA})
    if bad:
        die(
            f"{AUTO_REVIEW} pins claude-code-action SHA(s) {bad} — canary "
            f"expects {PINNED_SHA} (the CLI version {PINNED_CLI} that SHA "
            f"installs). Re-verify the matcher on the new build, then update "
            f"PINNED_ACTION_SHA / PINNED_CLI_VERSION here and "
            f"docs/actions-security.md."
        )
    if PINNED_SHA not in uses:
        die(f"{AUTO_REVIEW} does not pin {PINNED_SHA}")


def check_rules_present():
    files = {"reviewer": deny_list(REVIEWER), "coach": deny_list(COACH)}
    missing = []
    for rule, _probe, family, which in PROBES:
        if rule not in files[which]:
            missing.append(f"{family}: {rule} not in {which} backstop")
    if missing:
        die("committed backstop drifted from the canary's probes:\n  " +
            "\n  ".join(missing))


def extract_matcher(blob: bytes) -> str:
    start = blob.find(EXTRACT_START)
    end = blob.find(EXTRACT_END, start if start >= 0 else 0)
    if start < 0 or end < 0 or end <= start:
        raise MatcherMissing(
            f"Claude Code {PINNED_CLI} binary does not contain the matcher "
            f"module (kwe/V8r/$8/ZQe). The pinned build lacks one or more "
            f"syntax families — bump the action pin to a build that has them "
            f"and record it in docs/actions-security.md."
        )
    for needle, name in (
        (KWE_NEEDLE, ":* prefix (kwe)"),
        (V8R_NEEDLE, "mid-string * classifier (V8r)"),
        (DOLLAR8_NEEDLE, "glob engine ($8)"),
        (ZQE_NEEDLE, "rule classifier (ZQe)"),
    ):
        if needle not in blob[start:end]:
            raise MatcherMissing(
                f"extracted matcher is missing {name}. Pin bump required; "
                f"see docs/actions-security.md CR-A canary."
            )
    return blob[start:end].decode("ascii")


def node_eval(extracted_js: str, rule: str, probe: str) -> bool:
    """Run one probe through the extracted 2.1.287 functions via node."""
    tool, spec = parse_rule(rule)
    js = extracted_js + textwrap.dedent(f"""
    const tool = {json.dumps(tool)};
    const spec = {json.dumps(spec)};
    const probe = {json.dumps(probe)};
    function prefixMatch(prefix, command) {{
      const cl = command.toLowerCase(), pl = prefix.toLowerCase();
      return cl === pl || cl.startsWith(pl + " ");
    }}
    function denies() {{
      const C = ZQe(spec);
      if (tool === "Bash") {{
        if (C.type === "exact") return C.command.toLowerCase() === probe.toLowerCase();
        if (C.type === "prefix") return prefixMatch(C.prefix, probe);
        return $8(C.pattern, probe, true, true);
      }}
      if (tool === "Edit") return $8(spec, probe, true, false);
      return false;
    }}
    process.stdout.write(denies() ? "1" : "0");
    """)
    try:
        r = subprocess.run(
            ["node", "-e", js],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        die("node is required to eval the extracted matcher")
    except subprocess.CalledProcessError as e:
        die(f"node eval of extracted matcher failed: {e.stderr or e}")
    return r.stdout.strip() == "1"


def run_probes(extracted_js: str | None, label: str) -> None:
    failed = []
    for rule, probe, family, _which in PROBES:
        py = rule_refuses(rule, probe)
        if extracted_js is not None:
            js = node_eval(extracted_js, rule, probe)
            if js != py:
                failed.append(
                    f"{family}: python/node disagree on {rule} vs {probe!r} "
                    f"(py={py} node={js})"
                )
                continue
            ok = js
        else:
            ok = py
        if not ok:
            failed.append(
                f"{family}: denied probe was NOT refused: {rule} vs {probe!r} "
                f"({label})"
            )
        else:
            print(f"ok    {family}: {rule} refuses {probe!r}")
    # Boundary: git:* must not swallow gitk
    if rule_refuses(*BOUNDARY_NEG[:2]):
        failed.append(
            f"{BOUNDARY_NEG[2]}: {BOUNDARY_NEG[0]} incorrectly refuses "
            f"{BOUNDARY_NEG[1]!r} (not a word-boundary prefix)"
        )
    else:
        print(f"ok    {BOUNDARY_NEG[2]}: {BOUNDARY_NEG[0]} does not refuse "
              f"{BOUNDARY_NEG[1]!r}")
    if failed:
        die("canary failed:\n  " + "\n  ".join(failed))


def fake_binary(js: str) -> bytes:
    return b"PAD" * 50 + js.encode("ascii") + b"function Okn(e,n){return 1}"


def selftest() -> None:
    n = 0
    check_pin()
    n += 1
    print("ok    selftest: auto-review.yml pin matches PINNED_ACTION_SHA")
    check_rules_present()
    n += 1
    print("ok    selftest: committed backstops still carry the three families")

    # Minimal original matcher with the same export names the extractor looks
    # for, so the extract path is proven without vendoring the CLI.
    stub = (
        'var Hg=new RegExp("\\x00ESCAPED_STAR\\x00","g"),'
        'Kg=new RegExp("\\x00ESCAPED_BACKSLASH\\x00","g"),'
        r"jg=/\/(?:\*\*\/)+/g,"
        'Fg=new RegExp("\\x00GLOBSTAR\\x00","g");'
        "function kwe(e){return e.match(/^(.+):\\*$/)?.[1]??null}"
        'function V8r(e){if(e.endsWith(":*"))return!1;'
        'for(let n=0;n<e.length;n++)if(e[n]==="*"){let s=0,r=n-1;'
        'while(r>=0&&e[r]==="\\\\")s++,r--;if(s%2===0)return!0}return!1}'
        "function enr(e){return!1}"
        "function $8(e,n,s=!1,r=!1){"
        "if(e.includes('\\x00'))return!1;"
        "let i=e.trim(),d=r?i.replace(/[ \\t]+/g,' '):i,"
        "c=r?n.replace(/[ \\t]+/g,' '):n;"
        "let S=d.replace(/[.+?^${}()|[\\]\\\\'\"]/g,'\\\\$&')"
        ".replaceAll('*','.*');"
        "let v='s'+(s?'i':'');"
        "return new RegExp('^'+S+'$',v).test(c)}"
        "function ZQe(e){let n=kwe(e);if(n!==null)"
        'return{type:"prefix",prefix:n};if(V8r(e))'
        'return{type:"wildcard",pattern:e};'
        'return{type:"exact",command:e}}'
    )
    extracted = extract_matcher(fake_binary(stub))
    n += 1
    print("ok    selftest: extractor finds kwe/V8r/$8/ZQe in a fixture binary")

    try:
        extract_matcher(b"XXXX" + b"function nope(){}" + b"function Okn(")
    except MatcherMissing:
        n += 1
        print("ok    selftest: missing matcher module fails loudly")
    else:
        die("selftest: extractor did not fail on a binary with no matcher")

    run_probes(None, "python transcription")
    n += 1
    print("ok    selftest: python transcription refuses every family probe")

    # Negatives the live canary must keep: :* is a word-boundary prefix, so
    # combined spellings and longer tokens are NOT refused by a :* rule —
    # that is why the backstops also spell mid-string *.
    if rule_refuses("Bash(git:*)", "gitk"):
        die("selftest: :* boundary incorrectly matched gitk")
    n += 1
    print("ok    selftest: :* boundary does not match gitk")
    if bash_denied("git -c:*", "git -cx=y"):
        die("selftest: :* covered git -cx=y (mid-string * must)")
    n += 1
    print("ok    selftest: :* does not cover git -cx=y")
    if rule_refuses("Bash(git --git-dir:*)", "git --git-dir=/path log"):
        die("selftest: :* incorrectly covered git --git-dir=/path")
    n += 1
    print("ok    selftest: :* does not cover git --git-dir=/path (mid-string * must)")

    print(f"reviewer-deny-canary selftest: {n} checks ok")


def find_cli_binary() -> Path:
    import shutil
    env_path = str(Path.home() / ".local/bin") + os.pathsep + os.environ.get("PATH", "")
    path = shutil.which("claude", path=env_path)
    if not path:
        die(
            f"claude {PINNED_CLI} is not on PATH. Install with: "
            f"curl -fsSL https://claude.ai/install.sh | bash -s -- {PINNED_CLI}",
            code=2,
        )
    ver = subprocess.run(
        [path, "--version"], capture_output=True, text=True, timeout=30
    )
    out = (ver.stdout or "") + (ver.stderr or "")
    if PINNED_CLI not in out:
        die(
            f"{path} reports {out.strip()!r}, expected {PINNED_CLI}. "
            f"The SHA pin is only as good as this CLI; install that version."
        )
    resolved = Path(path).resolve()
    return resolved


def live() -> None:
    check_pin()
    print(f"ok    auto-review.yml pins claude-code-action@{PINNED_SHA}")
    check_rules_present()
    print("ok    committed backstops still name one rule per syntax family")
    binary = find_cli_binary()
    print(f"ok    Claude Code CLI {PINNED_CLI} at {binary}")
    blob = binary.read_bytes()
    try:
        extracted = extract_matcher(blob)
    except MatcherMissing as e:
        die(str(e))
    print(f"ok    extracted matcher ({len(extracted)} bytes) from {binary}")
    run_probes(extracted, "extracted 2.1.287 matcher")
    print(
        f"reviewer-deny-canary: {PINNED_CLI} matcher refuses every family "
        f"probe under the committed reviewer/coach backstops"
    )


if SELFTEST:
    selftest()
else:
    live()
PY
