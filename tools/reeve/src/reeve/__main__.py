"""``python -m reeve`` — the same CLI as the installed ``reeve`` script.

ci.yml's telemetry roll-up runs ``greenlights-merge`` without installing the
package (``PYTHONPATH=tools/reeve/src python3 -m reeve ...``), the way the
classifier calls tools/lineage uninstalled.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
