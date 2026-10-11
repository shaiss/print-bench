"""Drift guard: no workflow input may be silently cut short by an unquoted ` #`.

Inside a plain (unquoted) YAML scalar, whitespace followed by `#` starts a
comment. So the line

    context: the backlog-burn routine (issue #${{ steps.select.outputs.issue }})

hands the provider-triage action `the backlog-burn routine (issue` — no parse
error, no warning, actionlint clean. That is how escalation issue #637 came to
read "the backlog-burn routine (issue — registry chain `backlog-burn`": the
issue number the context existed to carry never left the workflow file, so a
human could not tell which issue's run had exhausted the chain. backlog-burn,
design-run and chunker all carried the same line.

Two pins, each with its negative controls:

* every provider-triage invocation's `context:` reaches the action whole — the
  YAML-parsed value equals the raw source value (its quotes removed, nothing
  else), with balanced brackets;
* a generic scan of every `with:` and `env:` entry in every workflow refuses a
  plain value whose trailing "comment" is really eaten content: a `#` glued to
  the text after it (`#${{`, `#637`), an expression inside the comment, or
  brackets the cut left unbalanced. A deliberate `# note` after a value stays
  legal — ci.yml's `fetch-depth: 0  # need the merge base` is one.

Stdlib-only like the rest of this suite (its CI job installs pytest alone), so
the YAML rule is applied by a deliberately tiny single-line scalar reader, not
a YAML library. When PyYAML happens to be importable (a dev box), one more
test holds that reader to PyYAML's own parse of every live entry, so the
reader cannot quietly drift from the language it imitates.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import pytest

from test_workflow_drift import REPO_ROOT, _workflow_paths

# The mappings whose values are a step's or job's inputs. `with:` is what the
# truncated provider-triage context lived in; `env:` is the same failure one
# mapping over (a value cut short before it reaches a script).
INPUT_BLOCKS = ("with", "env")

_TRIAGE_ACTION = "./.github/actions/provider-triage"

# Every provider-triage invocation as written — the count the step reader must
# match, so a step it failed to find cannot slip past the context pin.
_TRIAGE_USES_RE = re.compile(
    r"^[ ]*(?:-[ ]+)?uses:[ \t]*([\"']?)" + re.escape(_TRIAGE_ACTION)
    + r"\1[ \t]*(?:#.*)?$", re.MULTILINE)

# A block-mapping line: optional sequence dash, a bare key, then the rest of
# the line as written (absent for a key that opens a nested block).
_KEY_LINE = re.compile(
    r"^(?P<indent>[ ]*)(?P<dash>-[ ]+)?(?P<key>[A-Za-z0-9_.-]+):(?:[ \t]+(?P<rest>.*))?$")

# YAML double-quoted escapes a workflow label could plausibly carry.
_DQ_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", " ": " "}


class Line(NamedTuple):
    lineno: int        # 1-based, as an editor shows it
    indent: int        # leading spaces
    keycol: int        # column of the key (indent + any `- `)
    match: re.Match | None


class Entry(NamedTuple):
    lineno: int
    block: str         # the enclosing mapping: "with" or "env"
    key: str
    rest: str          # the raw text after `key:`, as written


class Scalar(NamedTuple):
    value: str         # what YAML hands the step
    eaten: str         # source text after the scalar YAML dropped as a comment
    style: str         # "plain", '"' or "'"


# ── The reader: YAML's rule for a one-line scalar ────────────────────────────

def _read_scalar(rest: str) -> Scalar | None:
    """YAML's reading of a single-line scalar value — or None for a form a
    trailing ` #` cannot truncate (a block scalar, a quoted scalar continuing
    onto the next line), which this guard has nothing to say about."""
    s = rest.strip()
    if not s:
        return Scalar("", "", "plain")
    if s[0] == "#":
        return Scalar("", s, "plain")
    if s[0] in "|>":
        return None
    if s[0] == '"':
        m = re.match(r'"((?:[^"\\]|\\.)*)"', s)
        if m is None:
            return None
        value = re.sub(r"\\(.)", lambda e: _DQ_ESCAPES.get(e.group(1), e.group(1)), m.group(1))
        return Scalar(value, s[m.end():].strip(), '"')
    if s[0] == "'":
        m = re.match(r"'((?:[^']|'')*)'", s)
        if m is None:
            return None
        return Scalar(m.group(1).replace("''", "'"), s[m.end():].strip(), "'")
    # Plain: the first whitespace-then-`#` ends the value and starts a comment.
    cut = re.search(r"[ \t]#", s)
    if cut is None:
        return Scalar(s, "", "plain")
    return Scalar(s[:cut.start()].rstrip(), s[cut.start():].strip(), "plain")


def _raw_source(rest: str) -> str:
    """The value as a human reads it in the file: the text after `key:`, with
    one wrapping pair of quotes removed and nothing else."""
    s = rest.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


_CLOSERS = {")": "(", "]": "[", "}": "{"}


def _balanced(value: str) -> bool:
    stack: list[str] = []
    for ch in value:
        if ch in "([{":
            stack.append(ch)
        elif ch in _CLOSERS and (not stack or stack.pop() != _CLOSERS[ch]):
            return False
    return not stack


def _truncation(sc: Scalar) -> str | None:
    """Why a plain value's trailing "comment" is really content YAML ate —
    or None when it reads as a deliberate note (or there is none)."""
    if sc.style != "plain" or not sc.eaten:
        return None   # a quoted value's trailing comment never cut the value
    if re.match(r"#[^\s#]", sc.eaten):
        return "a `#` glued to the text after it — an issue ref or expression, not a note"
    if "${{" in sc.eaten:
        return "an expression inside the comment"
    if not _balanced(sc.value):
        return "the cut left the value's brackets unbalanced"
    return None


# ── The structure reader: just enough block YAML to find the inputs ─────────

def _code_lines(text: str) -> list[Line]:
    """Every line YAML reads as structure. Blank lines, whole-line comments and
    block-scalar bodies (a `run: |` script, a folded `if: >-`) are dropped — a
    heredoc in a script that happens to say `with:` is shell, not an input."""
    out: list[Line] = []
    body_above: int | None = None   # a block scalar's body sits deeper than this
    for lineno, line in enumerate(text.split("\n"), 1):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if body_above is not None:
            if not stripped or indent > body_above:
                continue
            body_above = None
        if not stripped or stripped.startswith("#"):
            continue
        m = _KEY_LINE.match(line)
        keycol = indent + (len(m.group("dash")) if m and m.group("dash") else 0)
        out.append(Line(lineno, indent, keycol, m))
        if m and (m.group("rest") or "")[:1] in ("|", ">"):
            body_above = keycol
    return out


def _input_entries(text: str) -> list[Entry]:
    """Every `key: value` entry directly inside a `with:` or `env:` block, at
    any depth (step, job or workflow level)."""
    code = _code_lines(text)
    entries: list[Entry] = []
    for i, opener in enumerate(code):
        m = opener.match
        if m is None or m.group("key") not in INPUT_BLOCKS:
            continue
        rest = m.group("rest") or ""
        if rest and not rest.startswith("#"):
            continue   # an inline value (`env: ${{ fromJSON(...) }}`), not a block
        child_col: int | None = None
        for line in code[i + 1:]:
            if line.indent <= opener.keycol:
                break
            if child_col is None:
                child_col = line.indent
            if line.indent != child_col or line.match is None or line.match.group("dash"):
                continue   # a deeper continuation line, or not a mapping entry
            entries.append(Entry(line.lineno, m.group("key"), line.match.group("key"),
                                 line.match.group("rest") or ""))
    return entries


def _opens_step(line: Line, col: int) -> bool:
    """The `- key: …` line that starts the sequence item whose keys sit at col."""
    return bool(line.match and line.match.group("dash")) and line.keycol == col


def _triage_steps(text: str) -> list[tuple[int, dict[str, Entry]]]:
    """Each provider-triage step as (its `uses:` line, its `with:` inputs)."""
    code = _code_lines(text)
    inputs = [e for e in _input_entries(text) if e.block == "with"]
    steps: list[tuple[int, dict[str, Entry]]] = []
    for i, uses in enumerate(code):
        m = uses.match
        sc = _read_scalar(m.group("rest") or "") if m and m.group("key") == "uses" else None
        if sc is None or sc.value != _TRIAGE_ACTION:
            continue
        # The step runs from its `- ` line (at or above `uses:`) to the first
        # line indented left of its keys — the next step's dash, or the job's end.
        col = uses.keycol
        start = i
        while start > 0 and not _opens_step(code[start], col) and code[start - 1].keycol >= col:
            start -= 1
        end = i + 1
        while end < len(code) and code[end].indent >= col:
            end += 1
        first, last = code[start].lineno, code[end - 1].lineno
        steps.append((uses.lineno, {e.key: e for e in inputs if first <= e.lineno <= last}))
    return steps


# ── The two pins, factored so the negative controls run the same rule ───────

def _assert_triage_contexts_whole(texts: dict[str, str]) -> int:
    """Every provider-triage `context:` reaches the action exactly as written.
    Returns how many invocations were checked."""
    problems: list[str] = []
    checked = 0
    for name, text in sorted(texts.items()):
        steps = _triage_steps(text)
        written = len(_TRIAGE_USES_RE.findall(text))
        if len(steps) != written:
            problems.append(
                f"{name}: {written} provider-triage `uses:` line(s) but the step "
                f"reader found {len(steps)} — a step it cannot see escapes this pin")
        for uses_line, inputs in steps:
            checked += 1
            entry = inputs.get("context")
            if entry is None:
                problems.append(
                    f"{name}:{uses_line}: provider-triage step passes no `context:` "
                    "— the escalation would carry no label for what failed")
                continue
            sc = _read_scalar(entry.rest)
            if sc is None:
                continue   # a block scalar: no ` #` can cut it
            raw = _raw_source(entry.rest)
            if sc.value != raw:
                cause = (f"YAML read {sc.eaten!r} as a comment and dropped it (the "
                         "#637 truncation). Quote the whole label — context: \"...\" "
                         "— and keep any note on its own line" if sc.eaten else
                         "the quoting rewrote it (an escape?) — write the label so "
                         "the file shows exactly what the escalation will say")
                problems.append(
                    f"{name}:{entry.lineno}: provider-triage receives context "
                    f"{sc.value!r}, but the file says {raw!r} — {cause}")
            elif not _balanced(sc.value):
                problems.append(
                    f"{name}:{entry.lineno}: provider-triage context {sc.value!r} "
                    "has unbalanced brackets — part of the label is missing")
    assert not problems, "\n".join(problems)
    return checked


def _assert_no_truncated_inputs(texts: dict[str, str]) -> dict[str, int]:
    """No `with:`/`env:` value lost content to an unquoted ` #`. Returns how
    many single-line entries each block contributed to the scan."""
    problems: list[str] = []
    scanned = {block: 0 for block in INPUT_BLOCKS}
    for name, text in sorted(texts.items()):
        for entry in _input_entries(text):
            sc = _read_scalar(entry.rest)
            if sc is None:
                continue
            scanned[entry.block] += 1
            why = _truncation(sc)
            if why:
                problems.append(
                    f"{name}:{entry.lineno}: `{entry.block}:` input `{entry.key}` "
                    f"reaches its step as {sc.value!r} — YAML read {sc.eaten!r} "
                    f"as a comment ({why}). Quote the value, or move a real note "
                    "onto its own line.")
    assert not problems, "\n".join(problems)
    return scanned


def _live_texts() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8")
            for p in _workflow_paths(REPO_ROOT / ".github" / "workflows")}


# ── The reader itself ────────────────────────────────────────────────────────

@pytest.mark.parametrize("rest, expected", [
    ("the labeler routine", Scalar("the labeler routine", "", "plain")),
    ("the routine (issue #${{ x }})",                       # the #637 form
     Scalar("the routine (issue", "#${{ x }})", "plain")),
    ("0  # need the merge base", Scalar("0", "# need the merge base", "plain")),
    ("a#b", Scalar("a#b", "", "plain")),                   # no whitespace: not a comment
    ('"the routine (issue #${{ x }})"', Scalar("the routine (issue #${{ x }})", "", '"')),
    ('"say \\"hi\\""  # note', Scalar('say "hi"', "# note", '"')),
    ("'the forge''s routine'", Scalar("the forge's routine", "", "'")),
    ("", Scalar("", "", "plain")),
    ("# just a comment", Scalar("", "# just a comment", "plain")),
    (">-", None),
    ("|", None),
    ('"opens here and continues', None),
])
def test_reader_applies_yamls_one_line_scalar_rule(rest, expected):
    assert _read_scalar(rest) == expected


# ── Pin 1: the provider-triage context reaches the action whole ──────────────

def test_every_provider_triage_context_reaches_the_action_whole():
    texts = _live_texts()
    checked = _assert_triage_contexts_whole(texts)
    written = sum(len(_TRIAGE_USES_RE.findall(t)) for t in texts.values())
    assert written > 0, "no workflow invokes provider-triage — the pin is vacuous"
    assert checked == written


_UNQUOTED_FIXTURE = """\
jobs:
  burn:
    runs-on: ubuntu-latest
    steps:
      - name: Diagnose the exhausted chain
        id: triage
        uses: ./.github/actions/provider-triage
        with:
          chain: backlog-burn
          github-token: ${{ github.token }}
          context: the backlog-burn routine (issue #${{ steps.select.outputs.issue }})
          escalate: "true"
"""


def test_triage_context_guard_rejects_the_unquoted_form():
    # NEGATIVE CONTROL: the exact line #637 shipped must fail the pin…
    with pytest.raises(AssertionError, match=r"fixture\.yml:11: .*dropped it"):
        _assert_triage_contexts_whole({"fixture.yml": _UNQUOTED_FIXTURE})
    # …and the fix — the same line quoted — must pass it (positive control).
    quoted = _UNQUOTED_FIXTURE.replace(
        "context: the backlog-burn routine (issue #${{ steps.select.outputs.issue }})",
        'context: "the backlog-burn routine (issue #${{ steps.select.outputs.issue }})"')
    assert quoted != _UNQUOTED_FIXTURE
    assert _assert_triage_contexts_whole({"fixture.yml": quoted}) == 1


def _unquote_live_context(name: str) -> str:
    """The live workflow with its provider-triage context's quotes stripped —
    derived from the committed file, never a hand-copied literal."""
    text = (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    tampered, n = re.subn(r'^([ ]*context:[ ]*)"([^"\n]*#[^"\n]*)"[ ]*$', r"\1\2",
                          text, count=1, flags=re.MULTILINE)
    assert n == 1, f"{name}: no quoted `#`-bearing context to unquote — the fixture is stale"
    return tampered


@pytest.mark.parametrize("workflow", ["backlog-burn.yml", "design-run.yml", "chunker.yml"])
def test_both_pins_reject_a_live_context_unquoted_again(workflow):
    # NEGATIVE CONTROL against the real files: re-introducing the bug in any
    # of the three workflows that carried it must fail both pins.
    tampered = {workflow: _unquote_live_context(workflow)}
    with pytest.raises(AssertionError, match=re.escape(workflow) + r":\d+: .*#637"):
        _assert_triage_contexts_whole(tampered)
    with pytest.raises(AssertionError, match=re.escape(workflow) + r":\d+: `with:` input `context`"):
        _assert_no_truncated_inputs(tampered)


def test_triage_context_guard_rejects_a_step_with_no_context():
    # NEGATIVE CONTROL: the step reader must see the step it is pinning — a
    # triage step whose context line is gone is named, not silently skipped.
    text = (REPO_ROOT / ".github" / "workflows" / "labeler.yml").read_text(encoding="utf-8")
    tampered, n = re.subn(r"^[ ]*context:.*\n", "", text, count=1, flags=re.MULTILINE)
    assert n == 1, "tamper target not found — the fixture is stale"
    with pytest.raises(AssertionError, match=r"labeler\.yml:\d+: provider-triage step passes no `context:`"):
        _assert_triage_contexts_whole({"labeler.yml": tampered})


_NEIGHBOURS_FIXTURE = """\
jobs:
  a:
    steps:
      - name: A neighbour that happens to take a context input
        uses: actions/github-script@v8
        with:
          context: a neighbour's whole label
      - name: Triage, inputs written before uses
        with:
          chain: labeler
          context: the labeler routine (issue #${{ inputs.n }})
        uses: ./.github/actions/provider-triage
      - name: Triage with no context of its own
        uses: ./.github/actions/provider-triage
        with:
          chain: labeler
"""


def test_step_reader_binds_each_context_to_its_own_step():
    # NEGATIVE CONTROL for the step reader: a context written above `uses:`
    # is still this step's (and its cut is caught), and a triage step with no
    # context is named rather than credited with a neighbour's.
    with pytest.raises(AssertionError) as caught:
        _assert_triage_contexts_whole({"fixture.yml": _NEIGHBOURS_FIXTURE})
    message = str(caught.value)
    assert re.search(r"fixture\.yml:11: .*dropped it", message), message
    assert re.search(r"fixture\.yml:14: provider-triage step passes no `context:`", message), message


# ── Pin 2: no `with:` / `env:` value anywhere lost content to ` #` ───────────

def test_no_workflow_input_is_truncated_by_an_unquoted_hash():
    scanned = _assert_no_truncated_inputs(_live_texts())
    # Not vacuous: the scan must actually be reading both kinds of block.
    assert all(scanned[block] > 0 for block in INPUT_BLOCKS), scanned


def test_scan_reads_every_provider_triage_context():
    # The generic scan is a superset of pin 1: every triage context it is
    # meant to cover must be among the entries it reads.
    for name, text in _live_texts().items():
        contexts = {e.lineno for e in _input_entries(text) if e.key == "context"}
        for _, inputs in _triage_steps(text):
            assert inputs["context"].lineno in contexts, name


_EATEN_FIXTURES = {
    "glued issue ref": """\
jobs:
  a:
    steps:
      - uses: actions/github-script@v8
        with:
          title: fix for issue #12
""",
    "env expression": """\
jobs:
  a:
    env:
      LABEL: the routine (issue #${{ inputs.n }})
    steps:
      - run: echo "$LABEL"
""",
    "spaced hash, unbalanced": """\
jobs:
  a:
    steps:
      - uses: ./.github/actions/provider-triage
        with:
          context: the routine (issue # 5)
""",
    "expression in the comment": """\
jobs:
  a:
    steps:
      - uses: actions/github-script@v8
        with:
          body: see ${{ github.sha }}  # ${{ inputs.extra }}
""",
    "reusable-workflow with": """\
jobs:
  call:
    uses: ./.github/workflows/release.yml
    with:
      title: release #${{ inputs.version }}
""",
    "workflow-level env": """\
env:
  TAG: build #${{ github.run_number }}
jobs:
  a:
    steps:
      - run: echo "$TAG"
""",
}


@pytest.mark.parametrize("case", sorted(_EATEN_FIXTURES))
def test_truncation_scan_rejects_an_eaten_input(case):
    # NEGATIVE CONTROL: each shape of the bug — glued ref, expression, an
    # unbalanced cut, at step / job / workflow level — must fail the scan.
    with pytest.raises(AssertionError, match=r"fixture\.yml:\d+: `(with|env):` input"):
        _assert_no_truncated_inputs({"fixture.yml": _EATEN_FIXTURES[case]})


_CLEAN_FIXTURE = """\
env:
  NOTE: "issue #12 stays whole when quoted"
  PLAIN: a value  # a deliberate note
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0  # need the merge base (PR) / previous commit (push)
          ref: 'refs/pull/#${{ github.event.number }}'
          path: a#b
      - name: Script
        env:
          BODY: >-
            a folded value (issue #12
            continues here)
        run: |
          cat <<'YAML'
          with:
            title: fix for issue #12
          YAML
"""


def test_truncation_scan_accepts_deliberate_comments_and_quoted_hashes():
    # POSITIVE CONTROL: a real `# note`, a quoted `#`, a `#` with no space
    # before it, a folded block and a heredoc that merely says `with:` are all
    # fine — the scan must not regress into refusing every `#`.
    scanned = _assert_no_truncated_inputs({"fixture.yml": _CLEAN_FIXTURE})
    assert scanned == {"with": 3, "env": 2}, scanned


# ── The reader against a real YAML parser, where one is available ───────────

def test_reader_agrees_with_pyyaml_on_every_live_input():
    yaml = pytest.importorskip("yaml")
    cases = [(name, e) for name, text in _live_texts().items() for e in _input_entries(text)]
    cases += [("fixture.yml", e)
              for text in (*_EATEN_FIXTURES.values(), _CLEAN_FIXTURE, _UNQUOTED_FIXTURE,
                           _NEIGHBOURS_FIXTURE)
              for e in _input_entries(text)]
    compared = 0
    for name, entry in cases:
        sc = _read_scalar(entry.rest)
        if sc is None:
            continue
        # BaseLoader keeps every scalar a string, as the Actions runner sees it.
        parsed = yaml.load(f"k: {entry.rest}\n", Loader=yaml.BaseLoader)["k"]
        assert sc.value == parsed, f"{name}:{entry.lineno}: reader {sc.value!r} != PyYAML {parsed!r}"
        compared += 1
    assert compared > 0


def test_structure_reader_finds_every_input_pyyaml_does():
    # The scan only judges entries it finds; PyYAML's node tree is the truth
    # for which `with:`/`env:` entries a workflow actually has.
    yaml = pytest.importorskip("yaml")
    for name, text in _live_texts().items():
        found = {(e.lineno, e.block, e.key) for e in _input_entries(text)}
        truth: set[tuple[int, str, str]] = set()
        stack = [(yaml.compose(text), None)]
        while stack:
            node, parent = stack.pop()
            if isinstance(node, yaml.MappingNode):
                for key, value in node.value:
                    if parent in INPUT_BLOCKS:
                        truth.add((key.start_mark.line + 1, parent, key.value))
                    stack.append((value, key.value))
            elif isinstance(node, yaml.SequenceNode):
                stack.extend((item, parent) for item in node.value)
        assert found == truth, (
            f"{name}: missed {sorted(truth - found)[:5]}, invented {sorted(found - truth)[:5]}")
