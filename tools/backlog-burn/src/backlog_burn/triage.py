"""Combine ship-step outcomes with provider-triage's class/reason (issue #897).

Provider-triage probes each registry link with a live 1-token request. That
recovers billing / quota / auth / bad-model-id causes the ship steps hide, but
it cannot see an install or agent failure: when Claude Code failed to install
on every link (bubblewrap missing — the 2026-10-20 dead runs), the probe still
printed ``CLASS …: servable`` / ``REASON: served``.

This module is the overlay: feed the ship steps' ``outcome`` values (success /
failure / skipped / cancelled) into triage, and never report servable/served
when no link actually served. When at least one link's outcome is success —
or when settle already classified a #981 deferred/declined/delivered
disposition — keep the provider signal unchanged.
"""

from __future__ import annotations

from typing import Optional, Sequence

# GitHub Actions step outcome that means the ship link ran the agent action
# to completion (continue-on-error still exposes the pre-continue outcome).
_SERVED = "success"

# Settle / ship-check dispositions that mean an agent link really ran and
# produced an explicit outcome (#981 DEFERRED on permission denial, or a
# decline / delivery). Triage must not demote those to infra.
_SETTLED_DISPOSITIONS = frozenset({"deferred", "declined", "delivered"})

# When no link served and the provider probe claimed servable/served, the
# failure was infra (install, runner, action setup) — not a healthy serve.
INFRA_CLASS = "infra"
INFRA_REASON = "no-link-served"


def any_link_served(ship_outcomes: Sequence[str]) -> bool:
    """True when at least one ship link's Actions outcome is ``success``."""
    return any((o or "").strip() == _SERVED for o in ship_outcomes)


def classify_with_ship_outcomes(
    ship_outcomes: Optional[Sequence[str]],
    provider_class: str,
    provider_reason: str,
    *,
    disposition: Optional[str] = None,
) -> tuple[str, str]:
    """Return the triage ``(class, reason)`` after folding in ship outcomes.

    Parameters
    ----------
    ship_outcomes:
        Per-link GitHub Actions ``steps.<id>.outcome`` values, in walk order.
        Typical tokens are ``success``, ``failure``, ``skipped``, ``cancelled``.
        ``None`` means the caller did not feed ship outcomes (identity —
        other provider-triage consumers keep today's provider-only signal).
        An explicit sequence — even all ``skipped`` — is a real walk.
    provider_class / provider_reason:
        The aggregate signal from ``model_registry classify`` (or the
        provider-triage composite that wraps it).
    disposition:
        Optional settle-side outcome. ``deferred`` / ``declined`` /
        ``delivered`` keep the provider signal (#981 permission-denial
        deferred stays deferred — triage must not rebrand it infra).

    Returns
    -------
    (class, reason)
        ``(infra, no-link-served)`` when ship outcomes were provided, no
        link served, and the provider claimed ``servable``/``served``;
        otherwise the provider pair unchanged (including ``needs-human`` /
        ``dead`` / ``transient``, so escalation and registry-defect routing
        stay intact).
    """
    prov_class = (provider_class or "").strip()
    prov_reason = (provider_reason or "").strip()
    disp = (disposition or "").strip().lower()

    if disp in _SETTLED_DISPOSITIONS:
        return prov_class, prov_reason

    # No ship-outcome feed → provider-only triage (labeler, scout, …).
    if ship_outcomes is None:
        return prov_class, prov_reason

    if any_link_served(ship_outcomes):
        return prov_class, prov_reason

    # No link served. Demote only the false-healthy provider signal — the
    # Oct 20 bug. A real provider cause (billing, bad id, outage) still wins.
    if prov_class == "servable" or prov_reason == "served":
        return INFRA_CLASS, INFRA_REASON
    return prov_class, prov_reason


def format_report_lines(
    chain_id: str,
    klass: str,
    reason: str,
    *,
    reset: str = "",
) -> list[str]:
    """Render the same REASON/CLASS (/RESET) lines ``model_registry classify`` prints."""
    lines = [f"REASON {chain_id}: {reason}"]
    if reset:
        # RESET sits between REASON and CLASS in model_registry; keep that
        # order when a quota body named a reset time.
        lines.append(f"RESET {chain_id}: {reset}")
    lines.append(f"CLASS {chain_id}: {klass}")
    return lines
