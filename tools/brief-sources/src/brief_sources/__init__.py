"""brief-sources — the deterministic half of the spike-to-brief converter (#245 A).

The #245 thesis is that the *substance* of a new design brief is human-vetted
research already committed under `docs/`, and a model should only reshape it.
This package makes the **which recommendation** half of that reshaping pure and
provable: an in-band marker convention records decisions a research doc already
made, `extract` reads those markers into candidates, and `select` applies the
guard rails #245 locks — committed sources only, dedup against what is already
open or already built, one candidate per firing at most, provenance per number
— so they are enforced by code with tests, not by a prompt.

The mold is `tools/backlog-groomer` / `tools/reeve`: pure functions of
committed files, its own pytest suite, and — stronger than either sibling,
because there is not even an advisory GitHub write — **zero HTTP and zero
write verbs anywhere in the package** (tests scan for both). It reads
`<root>/docs/*.md` and lists `<root>/designs/`; it modifies nothing.
"""

from .markers import Candidate, MarkerError, extract
from .select import select

__all__ = ["Candidate", "MarkerError", "extract", "select"]
