# Provenance acceptance fixtures

Golden who/how timelines hand-built by the 2026-10-13 audit from every
GitHub source (brief issues and claims, PR branch commits and trailers,
sign-off / triage / coach comments, bot reviews, commit statuses, check
runs, Actions job steps, `registry.conf` at each run's commit, review
threads, deploys, PM.md / NOTES rows). They are the target the provenance
harvester's output must reproduce.

| Path | What |
|---|---|
| `golden/<design>.golden.json.gz` | curated events, episodes (rounds keyed by author-push sha), acceptance assertions, edge-recovery measurements |
| `golden/<design>.full.json.gz` | every normalised event, noise included |
| `golden/timeline-event.schema.json.gz` | the event schema, each field marked deterministic / join / window / not-derivable |
| `golden/summary.json.gz`, `golden/join_stats.json.gz` | volume and join statistics |
| `membership/membership.csv` | every PR × design row (671) with file kinds and the membership verdict |
| `membership/refined_membership.json` | design → member PRs under the refined file-kind rule |
| `membership/design_counts.csv`, `design_story_index.csv`, `issue_design_links.csv`, `orphans.csv` | per-design counts, the story index (60 design keys), issue→design links with the rule used, design-shaped work with no directory |
| `bin/check_acceptance.py` | 21 mechanical checks over the golden files |

```bash
python3 audits/provenance-2026-10/fixtures/bin/check_acceptance.py   # 21 PASS
```

Designs: `nuggs-vent-cap` (brief #592 → PR #636; a GLM design run, an
attended session and a Cursor Agent fixer, 15 rounds), `sbc-case` (#363 →
#371 → #397, attended, 16 rounds), `calibration-cube` (#634 plus the
2026-07-31 seed).

Every free-text field copied from a comment, triage row or finding is
replaced by `<stripped sha256:… len:…>`: the golden files carry structured
fields only, matching the harvester's rule that prose is never stored or
rendered. The membership CSVs keep PR and issue titles, which GitHub shows
publicly and which the owner set at merge. Episode titles and `derivation` / `note` fields are the auditors'
own annotations. Acceptance values are as of 2026-10-13T00:00Z; NVC-12
(noise counts) counted per-SHA check runs and Preview deployments, which a
lean harvester does not read, so re-baseline it against the harvested
sources.
