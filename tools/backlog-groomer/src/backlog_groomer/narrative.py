"""The optional fast-model narrative layer (issue #248).

A 3-5 sentence "this week's focus" paragraph, **phrased by a model over
the deterministic report — never a source of findings**.  The division of
labor is the one #244 locked: every finding stays a recomputable fact from
``detectors.py``; the narrative may only summarize and prioritize what the
report already says.  A narrative claim with no corresponding finding is a
bug, and this module is built so the bug has nowhere to come from:

* the model call's **sole input** is the rendered report body (plus a
  system prompt that forbids new facts), never the snapshot, the repo
  tree, or a live issue read;
* the paragraph is emitted between its own markers, and
  :func:`strip_narrative` removes exactly that span — so the deterministic
  sections render byte-identically with and without a narrative, which
  ``tests/test_narrative.py`` proves rather than trusts;
* generation fails soft: a missing key, a transport error, or a model that
  ignores the length cap degrades to no narrative, and the deterministic
  report posts exactly as it did before this layer existed (#248's "no
  key → today's behavior" contract).

The network call is ``_post_message`` — the single seam, monkeypatched in
tests.  It is a POST (the Anthropic Messages API is not cacheable-GET),
so it lives here and not in the GET-only ``github.py``: the groomer's
"advisory-only, GET-only" property is asserted by a test that forbids
write verbs **in the rest of the package** and by an explicit carve-out
that ``narrative.py``'s one POST is this seam and nothing else.  The
workflow still performs the only GitHub write (the sticky-issue upsert);
this module talks to a model API, not to GitHub.

Stdlib-only like the rest of the tool (``urllib.request``), so the
scheduled job needs no pip resolve in front of the reporting step.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

# The narrative is emitted between these HTML comments so it can be
# located and stripped deterministically. The opener is what the workflow
# and `strip_narrative` key on; the closer keeps the span bounded even if
# a future renderer appends content below it.
NARRATIVE_OPEN = "<!-- backlog-groomer-narrative -->"
NARRATIVE_CLOSE = "<!-- /backlog-groomer-narrative -->"

# Model output longer than this is refused (fail soft to no narrative):
# a "3-5 sentence" paragraph that runs to a page is the model ignoring
# the brief, and shipping it would let the summary outweigh the findings.
_MAX_CHARS = 1200

# The system prompt: the phrasing-only contract, stated to the model.  The
# sole user content is the rendered report; the model is never given the
# snapshot, credentials, or any way to reach the repo.
_SYSTEM_PROMPT = (
    "You write the opening summary of a backlog-grooming report. "
    "The report's findings are deterministic facts computed by a tool; "
    "your job is only to phrase and prioritize them for a maintainer "
    "skimming the queue this week. "
    "Rules: use ONLY the findings in the report you are given; do not "
    "invent, estimate, or extrapolate any issue number, count, age, "
    "label, or title that is not literally there; do not advise actions "
    "beyond what the report's sections imply; no headings, no lists, no "
    "markdown formatting — plain sentences only. "
    "Write 3 to 5 sentences naming this week's focus: which sections "
    "carry findings, roughly how many, and which one deserves attention "
    "first and why. If the report has no findings at all, say so plainly."
)

# API shape: Anthropic Messages-compatible (Anthropic native, and Z.AI's
# /api/anthropic endpoint behind the same contract). One request, no
# streaming, no tools. An empty registry base_url means the provider's
# native endpoint — Anthropic's.
ANTHROPIC_BASE = "https://api.anthropic.com"
_TIMEOUT_S = 60


def _post_message(
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
) -> str:
    """One Messages-API call; returns the model's text.  The single seam.

    Raises on any transport or API error — the caller decides that a
    failed narrative means "no narrative", never "no report".
    """
    body = json.dumps(
        {
            "model": model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        payload = json.load(response)
    return "".join(
        block.get("text", "")
        for block in payload.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    )


def _clean(text: str) -> str:
    """One paragraph, no markdown structure, length already validated."""
    flat = re.sub(r"\s+", " ", text).strip()
    # The prompt forbids these; belt-and-braces in case it produces them
    # anyway — a narrative that renders as structure would blur the line
    # the markers exist to draw.
    return flat.replace("```", "")


def render_narrative_block(paragraph: str, model_id: str) -> str:
    """The full narrative section: markers, disclosure heading, paragraph."""
    return "\n".join(
        [
            NARRATIVE_OPEN,
            "## This week's focus",
            "",
            "_Model-written summary of the findings below ("
            f"{model_id}, via the #206 registry) — the narrative adds no "
            "information; every finding is a deterministic fact from the "
            "sections that follow._",
            "",
            paragraph,
            "",
            NARRATIVE_CLOSE,
        ]
    )


def strip_narrative(body: str) -> str:
    """Remove the narrative span from ``body``; a no-op when absent.

    This is the byte-identity guarantee made executable: whatever a model
    wrote, the deterministic report is recoverable by stripping the span,
    and the tests hold renderer output and ``strip(render + narrative)``
    equal.
    """
    pattern = re.compile(
        re.escape(NARRATIVE_OPEN) + r".*?" + re.escape(NARRATIVE_CLOSE) + r"\n\n?",
        re.DOTALL,
    )
    return pattern.sub("", body)


def generate(
    report_body: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
    max_tokens: int = 1024,
    seam: Optional[Callable[..., str]] = None,
) -> Optional[str]:
    """Return the narrative **block** for ``report_body``, or ``None``.

    ``None`` is the fail-soft answer for every way generation can go
    wrong: empty key, transport/API error, empty or over-long or
    structure-bearing output.  The caller posts the report either way.
    """
    if not api_key:
        return None
    base_url = base_url or ANTHROPIC_BASE
    post = seam or _post_message
    try:
        text = post(base_url, api_key, model, _SYSTEM_PROMPT, report_body, max_tokens)
    except (urllib.error.URLError, OSError, ValueError, KeyError):
        return None
    paragraph = _clean(text)
    if not paragraph or len(paragraph) > _MAX_CHARS:
        return None
    return render_narrative_block(paragraph, model)


def insert(report_body: str, block: Optional[str]) -> str:
    """Splice a narrative ``block`` into a rendered report.

    Placement is the contract from #248: below the report's marker line
    (the workflow's upsert keys on ``body.startswith(MARKER)``) and above
    the ``## Summary`` table — purely additive, never inside a
    deterministic section.  ``block=None`` returns ``report_body``
    unchanged, byte for byte.
    """
    if block is None:
        return report_body
    lines = report_body.split("\n")
    # Line 0 is the marker; the narrative goes immediately after it,
    # before the first deterministic heading, separated by a blank line.
    # `strip_narrative` removes the block plus exactly the one separator
    # blank that follows it, so the round trip is byte-exact.
    return "\n".join([lines[0], block, *lines[1:]])


def model_from_registry(registry_path: str, chain: str) -> tuple[str, str, str]:
    """Resolve ``(model_id, base_url, secret_name)`` from the #206 registry.

    Reads the registry with the stdlib parser ``tools/model-registry``
    ships, straight from the checkout — the groomer stays stdlib-only, so
    this imports the sibling's module by path rather than depending on
    its package being installed.  ``registry_path`` may be relative to
    the CWD (the workflow runs from the checkout root) or omitted; a
    missing file falls back to the checkout's committed registry, located
    the same way the sibling module above is.

    The first link of ``chain`` is the model: the narrative is the
    cheap-to-be-wrong tier (#248's own reasoning), so it takes the
    chain's first (cheapest-capable) link and does not walk the
    fallbacks — a failed call degrades to no narrative, which is already
    the designed behavior.

    Raises (fail loud, before any report is built) when the registry is
    malformed or the chain is unknown — a broken registry should never
    silently read as "no narrative configured".
    """
    import importlib.util
    import pathlib
    import sys

    # repo-root/tools/backlog-groomer/src/backlog_groomer/narrative.py —
    # parents[4] is the repo root regardless of where the tool was invoked
    # from (an editable install keeps __file__ pointing at the checkout).
    repo_root = pathlib.Path(__file__).resolve().parents[4]
    registry_py = (
        repo_root / "tools" / "model-registry" / "src" / "model_registry" / "registry.py"
    )
    if not registry_py.exists():
        raise FileNotFoundError(
            f"the #206 model registry tool is not at {registry_py} — the "
            "narrative layer needs it to resolve its model; cannot continue"
        )
    # A relative/missing registry path falls back to the checkout's
    # committed copy, so the verb works from any CWD the same way the
    # sibling tools' find_root does.
    path = pathlib.Path(registry_path)
    if not path.is_absolute() and not path.exists():
        path = repo_root / registry_path
    spec = importlib.util.spec_from_file_location("_groomer_model_registry", registry_py)
    if spec is None or spec.loader is None:  # pragma: no cover - path is committed
        raise RuntimeError(f"cannot import the model registry at {registry_py}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)

    registry = module.Registry.load(str(path))
    links = registry.resolve(chain)
    if not links:
        raise ValueError(f"registry chain {chain!r} resolved to zero links")
    link = links[0]
    return link.model, link.base_url or "", link.secret
