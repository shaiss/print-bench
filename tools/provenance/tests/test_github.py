"""github.Client — GET-only, ETag, cap, floor, pacing, pagination (docs/provenance.md §API budget).

Owner: H1. Each placeholder's docstring is its acceptance criterion
(docs/provenance.md, final plan P0/P1a–e); replace the skip with the test.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="builder: implement")
def test_get_sends_if_none_match_and_304_is_free():
    """A cached ETag is sent as If-None-Match; a 304 returns the cached body, increments budget.not_modified and NOT budget.used."""


@pytest.mark.skip(reason="builder: implement")
def test_request_cap_raises_before_sending():
    """With max_requests=5 the 6th request raises BudgetExhausted before the transport is called (P1e: 'a request cap of 5 stops cleanly')."""


@pytest.mark.skip(reason="builder: implement")
def test_scheduled_floor_stops_and_dispatch_floor_sleeps():
    """Remaining < rate_floor: pace=False raises BudgetExhausted; pace=True calls sleep(reset - now + 5) and continues; a sleep that would pass deadline_epoch raises instead."""


@pytest.mark.skip(reason="builder: implement")
def test_link_next_is_followed_on_api_host_only():
    """rel=next on api.github.com is followed (including a /repositories/<id>/ link rewritten to /repos/<owner>/<repo>/); a next link to any other host is refused."""


@pytest.mark.skip(reason="builder: implement")
def test_truncation_raises():
    """More pages than max_pages raises Truncated, never a short list."""


@pytest.mark.skip(reason="builder: implement")
def test_retries_5xx_and_secondary_limits_not_404():
    """5xx / 403+Retry-After retried 3x with backoff; 404/410 return GONE; 401/422 raise APIError."""


@pytest.mark.skip(reason="builder: implement")
def test_graphql_unavailable_on_403():
    """A 403 or an errors payload from the GraphQL endpoint raises GraphQLUnavailable; the normaliser maps reviewThreads nodes to {first_comment_id, resolved, outdated}."""


@pytest.mark.skip(reason="builder: implement")
def test_token_never_logged():
    """APIError messages carry status and path, never the Authorization header value."""
