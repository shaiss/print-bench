"""Behavioral tests for ship-outcome triage overlay (issue #897).

Each case runs :func:`classify_with_ship_outcomes` on synthetic step
outcomes — not greps over workflow YAML. Covers:

* all links failed install → infra / no-link-served (never servable/served)
* one link served → provider servable/served kept
* mixed denial/deferred (#981) → disposition keeps provider signal
* provider needs-human / dead / transient with no link served → kept
"""

from __future__ import annotations

from backlog_burn.triage import (
    INFRA_CLASS,
    INFRA_REASON,
    any_link_served,
    classify_with_ship_outcomes,
    format_report_lines,
)

# Five-link walk shape matching backlog-burn.yml (3 GLM + 2 Anthropic).
_ALL_FAILED = ("failure", "failure", "failure", "failure", "failure")
_ONE_SERVED = ("failure", "failure", "success", "skipped", "skipped")
_ALL_SKIPPED = ("skipped", "skipped", "skipped", "skipped", "skipped")
# #981: a link exited 0 (outcome=success) after a permission denial; settle
# records deferred. Later links are skipped because an earlier link "succeeded".
_DEFERRED_WALK = ("success", "skipped", "skipped", "skipped", "skipped")


def test_all_links_failed_install_demotes_servable_to_infra():
    """The Oct 20 dead-run shape: every ship link failed, provider still healthy."""
    klass, reason = classify_with_ship_outcomes(
        _ALL_FAILED, "servable", "served",
    )
    assert (klass, reason) == (INFRA_CLASS, INFRA_REASON)
    assert klass != "servable"
    assert reason != "served"


def test_all_links_failed_report_lines_print_infra():
    klass, reason = classify_with_ship_outcomes(
        _ALL_FAILED, "servable", "served",
    )
    lines = format_report_lines("backlog-burn", klass, reason)
    assert lines == [
        "REASON backlog-burn: no-link-served",
        "CLASS backlog-burn: infra",
    ]


def test_one_link_served_keeps_provider_servable():
    """At least one link's outcome is success → today's provider signal stands."""
    assert any_link_served(_ONE_SERVED)
    klass, reason = classify_with_ship_outcomes(
        _ONE_SERVED, "servable", "served",
    )
    assert (klass, reason) == ("servable", "served")


def test_one_link_served_keeps_provider_needs_human():
    """A served walk that still exhausted for billing keeps needs-human."""
    klass, reason = classify_with_ship_outcomes(
        _ONE_SERVED, "needs-human", "billing",
    )
    assert (klass, reason) == ("needs-human", "billing")


def test_deferred_disposition_keeps_provider_signal_as_981():
    """#981 DEFERRED: agent ran (outcome=success), settle declined — not infra.

    Triage is skipped when settle.declined is true; if the classifier is still
    handed the deferred disposition, it must not demote servable → infra.
    """
    klass, reason = classify_with_ship_outcomes(
        _DEFERRED_WALK, "servable", "served", disposition="deferred",
    )
    assert (klass, reason) == ("servable", "served")


def test_declined_disposition_keeps_provider_signal():
    klass, reason = classify_with_ship_outcomes(
        _DEFERRED_WALK, "servable", "served", disposition="declined",
    )
    assert (klass, reason) == ("servable", "served")


def test_delivered_disposition_keeps_provider_signal():
    klass, reason = classify_with_ship_outcomes(
        ("success", "skipped", "skipped", "skipped", "skipped"),
        "servable", "served", disposition="delivered",
    )
    assert (klass, reason) == ("servable", "served")


def test_mixed_failure_then_deferred_success_without_disposition_keeps_servable():
    """A success outcome means a link served at the Actions layer — keep today.

    The #981 stop marker is settle's job; the overlay only demotes when *no*
    link's outcome is success (install-failure walks).
    """
    mixed = ("failure", "failure", "success", "skipped", "skipped")
    klass, reason = classify_with_ship_outcomes(mixed, "servable", "served")
    assert (klass, reason) == ("servable", "served")


def test_no_link_served_keeps_needs_human_for_escalation():
    """Install failed *and* the probe found billing — escalate, don't hide it."""
    klass, reason = classify_with_ship_outcomes(
        _ALL_FAILED, "needs-human", "billing",
    )
    assert (klass, reason) == ("needs-human", "billing")


def test_no_link_served_keeps_dead_registry_defect():
    klass, reason = classify_with_ship_outcomes(
        _ALL_FAILED, "dead", "bad-model-id",
    )
    assert (klass, reason) == ("dead", "bad-model-id")


def test_no_link_served_keeps_transient():
    klass, reason = classify_with_ship_outcomes(
        _ALL_FAILED, "transient", "rate-limit",
    )
    assert (klass, reason) == ("transient", "rate-limit")


def test_all_skipped_demotes_servable():
    """not-run walk: no link served either."""
    assert not any_link_served(_ALL_SKIPPED)
    klass, reason = classify_with_ship_outcomes(
        _ALL_SKIPPED, "servable", "served",
    )
    assert (klass, reason) == (INFRA_CLASS, INFRA_REASON)


def test_none_outcomes_is_identity_for_provider_only_callers():
    """Other routines invoke provider-triage with no ship-outcomes feed."""
    klass, reason = classify_with_ship_outcomes(None, "servable", "served")
    assert (klass, reason) == ("servable", "served")


def test_explicit_empty_sequence_demotes_servable():
    """An explicit empty walk list still means no link served."""
    klass, reason = classify_with_ship_outcomes([], "servable", "served")
    assert (klass, reason) == (INFRA_CLASS, INFRA_REASON)


def test_format_report_lines_with_reset():
    lines = format_report_lines(
        "backlog-burn", "needs-human", "quota", reset="2026-11-06T00:00:00Z",
    )
    assert lines == [
        "REASON backlog-burn: quota",
        "RESET backlog-burn: 2026-11-06T00:00:00Z",
        "CLASS backlog-burn: needs-human",
    ]
