# Architecture

Two layers, kept apart on purpose.

1. **[CI & automation platform](ci-platform.md)** — a generic pattern for
   gating a repository, regenerating its derived files, and running agentic
   workflows against it. Nothing in it knows what the repo builds. This is the
   part that becomes a template.
2. **[Design workflow](design-workflow.md)** — the OpenSCAD / FDM 3D-print
   domain: the geometry, the printability gates, the co-design loop. This is
   the part you replace.

The point of the split is reuse. Everything in layer 1 talks about *files,
gates, derived artifacts, and workflows* — never about millimeters or STLs.
Everything domain-specific lives in layer 2 and plugs into layer 1 at three
named seams. Swap layer 2 and you have the same machine building something
else.

## The seams

The platform never calls a domain tool directly. It reaches the domain through
three interfaces, each a plain file or script contract:

| Seam | Platform side | Domain side |
|---|---|---|
| **Classification** | `changes` CI job asks "what runs for this diff?" | `scripts/ci-classify.sh` maps changed paths → gate set |
| **Regeneration** | `regen` CI job commits derived artifacts back | `render.sh`, `animate.sh`, `product-shot.sh`, `gallery.sh` produce them |
| **Gating** | `render-gate` job runs whatever the classifier selected | `gate.sh`, `check.sh`, `readme-gate.sh`, `style-check.sh` are the gates |

To retarget the template: rewrite the domain scripts behind these three seams,
keep the CI jobs, the auth model, and the autonomy engine as they are.

## Reading order

- New to the repo → [design-workflow.md](design-workflow.md) first (what it
  builds), then [ci-platform.md](ci-platform.md) (how it ships).
- Extracting the template → [ci-platform.md](ci-platform.md), then this table.

## The rest of `docs/`

These two files are the map. The deep dives stay in their existing single-topic
docs and are linked from both: `licensing.md`, `derivative-designs.md`,
`decision-gate.md`, `print-feedback.md`, `roadmap-board.md`,
`actions-security.md`, `vercel-hosted-tooling.md`.
