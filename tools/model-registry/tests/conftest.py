"""Make the package importable from a bare checkout without installing it.

Mirrors tools/ci-gates' conftest: put src/ on sys.path so ``python -m pytest
tools/model-registry/tests`` runs from a fresh clone (the tool is stdlib-only and
never needs a build step).
"""

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
