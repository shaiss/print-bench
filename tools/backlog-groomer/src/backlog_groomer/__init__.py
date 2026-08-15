"""backlog-groomer — deterministic backlog-health report (issue #244).

The autonomy routines (backlog burn, design run, chunker, and the coming
product scout) all feed one issue queue; this tool is the thing that tends
it.  It is deliberately **not** an LLM agent: every finding is a
recomputable fact about timestamps, labels, and links, so the report can be
trusted the way a gate is trusted — and it is **advisory-only**: the tool
itself only ever reads (GET), and the workflow's sole write is upserting one
marker-matched report issue.  Humans (or the other routines) act on what it
surfaces; the groomer mutates nothing else.
"""
