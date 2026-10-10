"""Spec → checked sheets, as one pure step: parse, emit all four sheets,
run every check on every sheet. Nothing here touches the filesystem beyond
reading the spec; writing is the CLI's job, and it writes only a result that
came back clean."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .check import check_svg
from .emit import render_all
from .spec import Spec, load, parse


@dataclass
class Result:
    spec: Spec
    sheets: dict                                    # filename -> svg text
    findings: list = field(default_factory=list)    # [Finding], empty = pass


def build_text(text: str, path: str = "<spec>") -> Result:
    """Raises SpecError for a spec the tool refuses; otherwise returns the
    sheets plus every check finding (an empty list is a pass)."""
    return _checked(parse(text, path))


def build_file(path: Path) -> Result:
    return _checked(load(path))


def _checked(spec: Spec) -> Result:
    sheets = render_all(spec)
    findings = []
    for name, svg in sheets.items():
        findings.extend(check_svg(svg, name))
    return Result(spec, sheets, findings)
