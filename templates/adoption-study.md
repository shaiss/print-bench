<!-- The adoption-study format — a NEUTRAL evaluation of a vendor product.
     This is the shape the .github/ISSUE_TEMPLATE/adoption-study.yml issue form
     collects; the section headings here and that form's field labels must stay
     identical. The study becomes the BODY of an issue labeled `adoption-study`
     and titled "Adoption study: <product>" — the form pre-fills the
     "Adoption study: " prefix and the submitter completes it with the product
     name (an issue form fills a fixed title prefix, not a field value). Filing it is a
     request to EVALUATE a product, not to adopt it — no integration decision is
     implied or made here. Every capability claim carries a link or evidence; a
     claim taken on faith belongs under Assumptions & claims to verify, never
     stated as fact. License reach is first-class: print-bench treats the
     GPL-vs-BSD boundary as a design constraint (docs/licensing.md), so be exact
     about terms. Delete these comments. -->

## Vendor / company

Who makes or maintains the product.

## Product name

The product being studied.

## Product URL

The canonical home page or repository for the product.

## License

The exact license (e.g. BSD-2-Clause, GPL-3.0, MIT, proprietary). Reach
matters here, not just permissiveness: a copyleft license changes what a
design that uses it may ship, so name the exact terms — see
`docs/licensing.md` for the GPL/BSD boundary print-bench enforces.

## Category

What kind of thing this is, so the study routes to the right evaluators. One
of: OpenSCAD library; Slicer / CAM tool; Hardware catalogue (vitamins);
Rendering / preview tool; CI / tooling / observability integration; Printer /
material profile; Other.

## What it does / what it claims

One paragraph: what the product is, the problem it solves, and what its
makers claim it does. State the claims as the vendor makes them — verifying
them is the study's job, not this section's.

## Capabilities offered

One row per capability. Each needs **evidence** — a link, a doc reference, or
a demo — not a bare claim. A capability with nothing in the evidence column is
an assumption; move it to *Assumptions & claims to verify*.

| Capability | What it does | Evidence / link |
|---|---|---|
| | | |

## Integration surface

How it would slot into print-bench: a `lib/` module, a `scripts/` tool, a
`styles/` pack, a single design, or the autonomy loop. Say where it plugs in
and what it would touch — this frames the evaluation, it does not commit to it.

## Links & docs

Repository, API reference, examples, and anything else an evaluator needs to
reach the real thing.

## Licensing & distribution notes

Copyleft reach, attribution obligations, and how distributing print-bench
output would be affected. If the license is copyleft, note whether it would
stay contained to one opted-in design or spread to shared core — the boundary
`docs/licensing.md` draws.

## Maintenance & provenance

Release cadence and recency, versioning scheme, who maintains it, and how
healthy the project looks (last release, open-issue backlog, bus factor).

## Assumptions & claims to verify

Every claim taken on faith, restated in one list so an evaluator can confirm
or refute each without re-reading the whole study.

## Open questions

What must be answered before an adoption decision could be made, and which of
those block it. An empty section is a claim: it says the study is ready to
evaluate as-is.
