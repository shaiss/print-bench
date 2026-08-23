#!/usr/bin/env python3
"""Turn a gate.sh log into a GitHub-flavored markdown table.

Usage: gate-summary.py gate.log > summary.md

Reads the `== name: printcheck stl ==` / `SCORE:` / `== test-slice ... ==` /
`estimated printing time` lines gate.sh emits and renders one row per gated
STL. Used by CI for both the job summary and the sticky PR comment; safe on
partial logs (a crashed gate run still yields whatever rows completed).

Also reads gate.sh's `<status>  derivative <name>: <kind> <subject> — <detail>`
lines into their own section. A derivative whose override silently failed to
bind renders, slices and scores exactly like a healthy part, so the derivative
check is the only place that failure is visible at all — leaving it out of the
PR comment would make the report itself complicit in the silence.
"""
import re
import sys


def main() -> int:
    """Render the summary table for the gate log named in argv[1].

    Returns a shell exit status: 2 on usage/IO error, 0 otherwise —
    including when the log yielded no rows, since the gate's own exit code,
    not this reporter, decides whether CI fails.
    """
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as e:
        print(f"gate-summary: {e}", file=sys.stderr)
        return 2

    rows = []          # {stl, score, verdict, criticals, warnings, time, slice_fail}
    pre_fails = []     # FAIL lines emitted before printcheck ran (render/missing)
    derivs = []        # {ok, design, kind, subject, detail} from derivative_gate
    fusechecks = []    # {status, design, detail} from the ci.fusecheck gate
    cur = None
    for line in lines:
        m = re.match(r"== .*: printcheck (\S+) ==", line)
        if m:
            cur = {"stl": m.group(1), "score": "?", "verdict": "no report",
                   "criticals": 0, "warnings": 0, "time": "—", "grams": "—",
                   "slice_fail": False}
            rows.append(cur)
            continue
        # Claimed before the pre_fails match below and before the per-row
        # counters: derivative lines belong to a design, not to whichever
        # printcheck row happens to still be open, and matching them first
        # means a reworded gate.sh message can never quietly land in the wrong
        # section instead of failing to parse where someone would notice.
        # `derivative ` is the discriminator, so the pattern cannot swallow an
        # ordinary `FAIL  <design>: render failed`.
        m = re.match(r"(ok|FAIL)\s+derivative (\S+): "
                     r"(override|base-safe|derives\.conf)(?: (\S+))? — (.+)$",
                     line)
        if m:
            status, design, kind, subject, detail = m.groups()
            derivs.append({"ok": status == "ok", "design": design, "kind": kind,
                           "subject": subject or "", "detail": detail.strip()})
            continue
        # Claimed before pre_fails too: a fusecheck control "render failed" line
        # would otherwise be swallowed by the pre_fails matcher below and lose
        # its section. `fusecheck ` is the discriminator, so an ordinary
        # `FAIL  <design>: render failed` still falls through to pre_fails.
        m = re.match(r"(ok|warn|FAIL)\s+fusecheck (\S+): (.+)$", line)
        if m:
            status, design, detail = m.groups()
            fusechecks.append({"status": status, "design": design,
                               "detail": detail.strip()})
            continue
        m = re.match(r"FAIL\s+(.+: (?:render failed|\S+ not found))$", line)
        if m:
            pre_fails.append(m.group(1))
            continue
        if cur is None:
            continue
        m = re.search(r"SCORE: (\d+)/100 — (.+)", line)
        if m:
            cur["score"], cur["verdict"] = m.group(1), m.group(2).strip()
            continue
        if "[CRITICAL]" in line:
            cur["criticals"] += 1
            continue
        if "[WARNING" in line:
            cur["warnings"] += 1
            continue
        m = re.search(r"estimated printing time \(normal mode\) = (.+)", line)
        if m:
            cur["time"] = m.group(1).strip()
            continue
        m = re.search(r"total filament used \[g\] = (.+)", line)
        if m:
            # gate.sh passes --filament-density 1.24 (PLA); a 0.00 here means
            # the density flag was lost — surface it rather than a bare zero
            grams = m.group(1).strip()
            cur["grams"] = f"{grams} ⚠️" if grams == "0.00" else grams
            continue
        if re.search(r"FAIL\s+\S+: slicing failed", line):
            cur["slice_fail"] = True

    print("### printcheck + slice results")
    print()
    if not rows and not pre_fails and not derivs and not fusechecks:
        print("_no gate output captured_")
        return 0
    if rows:
        print("| Part | Score | Verdict | Findings | Est. print time | Filament (g, PLA est.) |")
        print("|---|---|---|---|---|---|")
    for r in rows:
        findings = []
        if r["criticals"]:
            findings.append(f"{r['criticals']} critical")
        if r["warnings"]:
            findings.append(f"{r['warnings']} warning" + ("s" if r["warnings"] > 1 else ""))
        # a row with no SCORE line means printcheck died mid-part — that must
        # never render as a pass
        no_report = r["score"] == "?"
        verdict = r["verdict"] + (" — **slice failed**" if r["slice_fail"] else "")
        if no_report:
            verdict = "**no printcheck score — check the job log**"
        icon = ("❌" if r["criticals"] or r["slice_fail"] or no_report
                else ("⚠️" if r["warnings"] else "✅"))
        print(f"| `{r['stl']}` | {icon} {r['score']}/100 | {verdict} "
              f"| {', '.join(findings) or '—'} | {r['time']} | {r['grams']} |")
    if pre_fails:
        print()
        print("**Failed before printcheck ran:**")
        for p in pre_fails:
            print(f"- ❌ {p}")
    if derivs:
        # Its own section rather than extra rows in the table above: these
        # checks are about a design's relationship to its parent, and the STL
        # they would otherwise hang off is the one that looks perfect.
        print()
        print("### Derivative override checks")
        print()
        print("| Design | Check | Result |")
        print("|---|---|---|")
        for d in derivs:
            check = f"{d['kind']} `{d['subject']}`" if d["subject"] else d["kind"]
            # Escaped the way gallery.sh escapes its pitches: a stray pipe in a
            # gate message would silently add a column and shift every cell
            # after it, turning a failure report into a garbled one.
            detail = d["detail"].replace("|", "\\|")
            print(f"| `{d['design']}` | {check} "
                  f"| {'✅' if d['ok'] else '❌'} {detail} |")
    if fusechecks:
        # Its own section: a fuse warn is not a printcheck finding (the fused
        # part scores a clean 100) and it is not a hard fail either — it is the
        # STRONG WARN the reviewers must sign off on, so it must be impossible to
        # miss in the sticky comment they read as ground truth.
        print()
        print("### Fusecheck (separable bodies)")
        print()
        print("| Design | Result |")
        print("|---|---|")
        icons = {"ok": "✅", "FAIL": "❌", "warn": "⚠️"}
        for u in fusechecks:
            detail = u["detail"].replace("|", "\\|")
            if u["status"] == "warn":
                detail = f"**STRONG WARN — reviewer signoff required.** {detail}"
            print(f"| `{u['design']}` | {icons.get(u['status'], '')} {detail} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
