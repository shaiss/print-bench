# The agent forge — Wright, Reeve's sign-off, and the self-growing tooling loop

The agent forge is the bench growing and healing its **own tooling** through
the same gated pipeline its designs already use. It is one scheduled routine
(`.github/workflows/wright.yml`, 4×/day) with two independent halves and a
hard wall between them:

- **Wright** (`/wright`, the *toolwright* — a registered agent,
  `people/wright.md`) is the generative half: it reads the bench's own pulse
  and files `agent-brief` issues proposing new **LLM-based probabilistic
  agents**, **deterministic tools**, or **hybrids**. Where Remy
  (`/product-scout`) proposes designs, Wright proposes tooling.
- **Reeve's sign-off** (`/reeve-signoff`) is the judging half: Reeve — the
  platform PM and Wright's keeper (`PM.md`) — rules on each pending brief
  against the charter and posts one verdict: **approve** (arms it),
  **decline**, or **needs-human** (parks it at the decision gate, #161).

Everything downstream already exists. The forge builds nothing itself:

```
      pulse (reports, run health, telemetry, issues)
        │
        ▼
   /wright ──files──▶  agent-brief issue          (≤1/firing, backpressure-capped)
        │                    │
        │              /reeve-signoff  ──rules──▶  approve │ decline │ needs-human
        │                    │                        │         │          │
        ▼                    ▼                  autonomy-ok  wright-   needs-decision
   (next firing:        verdict comment         + points-n   declined  (human /decide)
    dedup first)        (marker, advisory)          │
                                                    ▼
                                    hourly backlog burn → /ship-issue → DRAFT PR
                                    (too big → declined-too-big → chunker → pieces)
                                                    │
                                          Oracle cross-vendor review
                                                    │
                                                    ▼
                                        A HUMAN MERGES (charter N3)
```

The bet is the same one `/design-run` made: **composition over invention**.
The forge adds exactly two model calls (propose, judge) and reuses the burn,
the chunker, `/ship-issue`'s frozen-contract discipline, the Oracle, the
decision gate, and the human merge for everything else.

## Why a sign-off, and why it may arm

Every other generative routine here is advisory-only: the scout files, the
assessor comments, the labeler adds routing labels *conservatively*. The
forge's whole point — the operator's ask — is **autopilot**: while nobody is
watching, a real gap becomes a built draft PR. That requires *something*
unattended to apply `autonomy-ok`, which is the one escalation-shaped write
in the family. The design spends its entire safety budget there:

1. **Separation of proposer and judge.** Two agent invocations, two deny
   backstops: `.claude/wright-settings.json` denies the sign-off MCP server,
   `.claude/reeve-signoff-settings.json` denies the filing server. The
   proposer can never approve its own brief in-process; the judge can never
   file what it then approves. `scripts/wright-perms-check.sh` pins both
   directions with negative controls.
2. **Cross-model judgment.** The propose chain (`wright`, cheap tier) and
   the sign-off chain (`wright-signoff`, frontier head + walking tail) are
   separate registry chains — a different model rules than proposed. (A
   cross-*vendor* split, the Oracle's stronger property, is blocked today by
   the unfunded Anthropic account — see Future work.)
3. **The deterministic sensitive-path guard.** `signoff_mcp.py` scans the
   *server-fetched* brief text (never the model's paraphrase, normalized
   against invisible-character smuggling) and downgrades any approve that
   mentions the bench's protection machinery — existing deny backstops,
   perms-checks, `decide.yml`, arming variables, the routine policy confs,
   secret names, the forge's own workflow — to `needs-decision`. It is a
   best-effort backstop behind the judge's own never-arm-the-fence
   instruction (generic wording can always describe a fence change), but
   what it costs a bypasser is a human's eyes, never an arm — and false
   positives park a brief; they never arm one.
4. **Write-time target validation.** The sign-off tool re-reads the issue at
   write time: open, an issue (not a PR), `agent-brief`-labeled, no verdict
   label yet, inside the trusted Select step's candidate set. Labels apply
   from a closed constant taxonomy, label-first (decide.yml's fail-closed
   ordering), one verdict per brief (marker dedup), capped per run.
5. **Bounded volume.** Propose is capped at `WRIGHT_MAX_BRIEFS` (1) per
   firing and skipped entirely while ≥ `WRIGHT_MAX_PENDING` (3) briefs are
   pending or armed-unbuilt — backpressure computed in trusted workflow
   bash, so the forge can never flood the queue it feeds.
6. **Everything is reversible before it is real.** A wrong label is one
   click to undo; an armed brief only ever becomes a *draft* PR; the Oracle
   reviews it; the human merges. `WRIGHT_AUTO_ARM: 'false'` in wright.yml
   demotes every approve to `needs-decision` (advisory mode) in a one-line
   PR; unsetting the `WRIGHT_ENABLED` repo variable kills the routine in
   seconds. **Shipped disarmed** — two-key arming, the variable unset.

What the forge **never** does, by construction: push code, open or merge a
PR, close an issue, remove a label, apply any label outside
{`agent-brief`} ∪ {`autonomy-ok`, `points-n`, `needs-decision`,
`wright-declined`}, or touch another repo.

## The pieces

| Piece | Path | Pattern parent |
|---|---|---|
| Policy conf (two-key, closed key set) | `.github/wright.conf` | product-scout.conf |
| Scheduled workflow (2 agent jobs + disarmed notice) | `.github/workflows/wright.yml` | adoption-assessor.yml + labeler.yml's walk |
| Propose skill | `.claude/skills/wright/SKILL.md` | product-scout |
| Sign-off skill | `.claude/skills/reeve-signoff/SKILL.md` | adoption-assessor |
| Shared read wrapper (`list-briefs`/`read-thread`/`pulse`/`run-health`) | `.claude/skills/wright/wright-helper.sh` | assessor-helper.sh |
| Filing MCP tool (`file_agent_brief`) | `.claude/skills/wright/wright_mcp.py` | scout_mcp.py |
| Sign-off MCP tool (`post_reeve_signoff`) | `.claude/skills/reeve-signoff/signoff_mcp.py` | assessor_mcp.py, hardened |
| Deny backstops (one per half, cross-denying) | `.claude/wright-settings.json`, `.claude/reeve-signoff-settings.json` | scout/assessor settings |
| Perms drift check (both backstops, run by check.sh) | `scripts/wright-perms-check.sh` | adoption-assessor-perms-check.sh |
| Brief format + issue form | `templates/agent-brief.md`, `.github/ISSUE_TEMPLATE/agent-brief.yml` | design-brief pair |
| Model chains | `[chain:wright]`, `[chain:wright-signoff]` in `.github/models/registry.conf` | scout / labeler chains |
| Drift-guard coverage | `tools/model-registry/tests/test_workflow_drift.py` (Wright section) | the Oracle section |
| Cadence parity | `wright` in `scripts/cadence-sync-check.sh` | the eight prior routines |

Label taxonomy added: **`agent-brief`** (the queue identity — excluded from
the labeler's untriaged sweep so the labeler can never arm or park a brief
around the sign-off) and **`wright-declined`** (Reeve said no; keeps a
declined brief out of every future Select without closing it — closing stays
a human's write).

## The signals Wright reads

All committed or first-party live, the scout's honest-inputs rule (#229):
Reeve's bench-health report and the groomer report (the sticky issues, via
the wrapper's `pulse`), the scheduled routines' recent run conclusions
(`run-health` — a red streak nobody filed is the strongest signal; the
worked example is the auto-review run where Jane and Drik exhausted every
provider link and the PR just went red, run 32917536406),
`telemetry/REPORT.md` + `log.ndjson`, the routine confs and workflows (the
pattern census: what every sibling has that one lacks), and open issues (for
dedup, and for `needs-decision` threads whose answer is a small tool).

## Failure modes and what handles each

| Failure | Handled by |
|---|---|
| Prompt injection in an issue Wright reads | dontAsk over {read wrapper, filing tool, file reads}; deny backstop; worst case = 1 bounded `agent-brief`/firing that Reeve then judges |
| Prompt injection in a brief the sign-off reads | the same surface split; a steered approve still passes the write-time re-read, the closed label taxonomy, and the sensitive-path guard; worst case = arming one in-taxonomy brief whose build is still a gated draft PR |
| A brief targeting the fence (backstops, decide.yml, secrets, arming vars) | the deterministic sensitive-path guard: approve → `needs-decision`, never armed |
| Brief flood | `WRIGHT_MAX_BRIEFS` (tool-enforced) + `WRIGHT_MAX_PENDING` backpressure (trusted bash) |
| Duplicate verdicts / re-judging | verdict-label re-read + marker dedup, both at write time |
| Verdict label applied but comment lost | label-first ordering — the label is the operative record; the next Select excludes the brief, so no re-rule |
| Sign-off model chain head dies | the `wright-signoff` chain walks (3 GLM links, labeler-style); total exhaustion fails the job red in the Actions run list. Reeve's `routine-dead` detector does **not** watch wright.yml yet (`ROUTINE_WORKFLOWS` covers the four #326 routines) — extending it is a named first agent-brief (see Future work) |
| Propose model dies | single-link by design (scout precedent) — the firing fails, retries ≤6h later, sign-off is unaffected (separate job) |
| A build run dies mid-flight after arming | the burn's existing `routine-lock-cleanup.sh` (SHIP-LOCK withdrawal + red-on-death) — the forge adds no new lock machinery |
| An armed brief is actually too big | `/ship-issue` declines → `declined-too-big` → the chunker splits → the burn ships the pieces (the existing loop) |
| The forge proposing forge changes | Wright's mandate forbids it; the sensitive-path guard backstops it deterministically (`wright.yml`, `wright.conf`, `wright_mcp`, `signoff_mcp` are sensitive patterns) |
| Runaway routine | two-key arming (`WRIGHT_ENABLED` unset kills in seconds); `WRIGHT_AUTO_ARM: 'false'` demotes to advisory; conf `enabled: false` pauses in git |

## Arming it (the morning-after checklist)

Shipped fully disarmed. To turn the autopilot on:

1. Merge the PR (human, as ever).
2. Create the queue's label — the issue form silently drops a label that
   does not exist yet, and an unlabeled brief is invisible to every guard
   keyed on it (the armed workflow also ensures it, but a hand-filed brief
   can arrive before the first armed firing):
   `gh label create agent-brief --color 8250DF --description "Well-formed tooling/agent brief awaiting Reeve's sign-off (the agent forge)"`
3. `gh variable set WRIGHT_ENABLED --body true` — key 2 of 2
   (`.github/wright.conf` already says `enabled: true`).
4. Optionally dispatch `Wright (scheduled agent forge)` with `dry_run: true`
   first — it selects and logs without invoking either model.
5. To run *proposals-only* for a probation period: leave `WRIGHT_AUTO_ARM:
   'true'` alone but expect the first approves to be fence-adjacent and
   parked; or flip it to `'false'` so every approve lands as
   `needs-decision` for `/decide`.

## Relationship to earlier decisions

- **#245 (spike→brief converter, declined-too-big)**: Wright subsumes the
  generative half for tooling; a research-doc-to-brief converter is a
  natural early agent-brief.
- **#296 (Reeve stage 2, declined-too-big)**: the sign-off is a bounded
  slice of "Reeve's hands" — one delegated write, behind the labeler-family
  backstop pattern the charter's leash table demanded, without the general
  file/label-from-pulse machinery.
- **Charter N6**: the forge's own existence traces to the pulse (dead runs,
  exhausted chains, "not evaluated" detectors sat unfixed for days), and its
  sign-off is explicitly instructed to decline on N6 — the machinery that
  guards against machinery-for-its-own-sake is the machinery's own judge.

## Future work (deliberately not in v1)

- **Cross-vendor sign-off** (judge on the vendor the proposer didn't use —
  the Oracle's independence property) once the Anthropic account is funded;
  today both chains sit on the servable frontier provider, split by model.
- Reeve watching the forge: `tools/reeve`'s `ROUTINE_WORKFLOWS` predates
  wright.yml, so a forge death-streak is red in Actions but absent from the
  bench-health report — adding it (plus a pending/parked agent-brief
  detector) is a natural first agent-brief.
- Per-agent memory for Wright (issue #426's pilot order applies) so a
  declined-gap class stops being re-derived from scratch each firing.
