"""The weighted length rule — the one both composer and poster must obey."""

from growth.tweetlen import MAX_WEIGHT, TARGET_WEIGHT, tweet_weight, over_limit


def test_plain_ascii_counts_one_each():
    assert tweet_weight("hello world") == 11


def test_every_url_counts_as_23_regardless_of_length():
    assert tweet_weight("https://github.com/shaiss/print-bench") == 23
    assert tweet_weight("x https://a.io y") == 2 + 23 + 2  # "x ", url, " y"
    two = "https://github.com/shaiss/print-bench https://example.com/a/very/long/path"
    assert tweet_weight(two) == 23 + 1 + 23


def test_wide_code_points_count_two():
    assert tweet_weight("日本") == 4
    assert tweet_weight("🖨") == 2


def test_narrow_typographic_ranges_count_one():
    # en dash (0x2013) and curly quote (0x2019) sit in the weight-1 ranges.
    assert tweet_weight("–’") == 2


def test_limits():
    assert not over_limit("x" * MAX_WEIGHT)
    assert over_limit("x" * (MAX_WEIGHT + 1))
    assert TARGET_WEIGHT < MAX_WEIGHT, "the compose target must leave headroom"


def test_url_plus_text_boundary():
    # 23 (url) + 1 (space) + 256 chars = 280 exactly — not over.
    text = "https://print-bench.example " + "y" * 256
    assert tweet_weight(text) == 280
    assert not over_limit(text)
    assert over_limit(text + "z")
