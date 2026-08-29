"""The weighted tweet-length rule — one implementation, everywhere.

X does not count characters; it counts *weights* (the twitter-text v3
config): code points in a handful of "narrow" ranges weigh 1, everything
else (CJK, emoji, most symbols) weighs 2, and **every URL counts as exactly
23** regardless of its real length (the t.co wrapper). A naive ``len()``
passes tweets X refuses, so the composing agent, the posting tool, and the
dry-run simulator all measure with THIS function.

Two deliberate simplifications, both of which only ever *overcount* (a
refused-marginal tweet is an inconvenience; an accepted-too-long tweet is a
failed post at the API, after the approval already happened):

* emoji ZWJ sequences are counted per code point (a family emoji weighs more
  here than X's 2) rather than running the full emoji grammar;
* anything URL-shaped (``http://`` / ``https://`` up to whitespace) is a URL.

``MAX_WEIGHT`` is X's hard 280. The Lark skill composes to ``TARGET_WEIGHT``
(270) so the margin absorbs the overcount.
"""

from __future__ import annotations

import re

MAX_WEIGHT = 280
TARGET_WEIGHT = 270
URL_WEIGHT = 23

_URL_RE = re.compile(r"https?://\S+")

# twitter-text v3: code points inside these inclusive ranges weigh 1; every
# other code point weighs 2.
_WEIGHT_ONE_RANGES = (
    (0x0000, 0x10FF),
    (0x2000, 0x200D),
    (0x2010, 0x201F),
    (0x2032, 0x2037),
)


def _char_weight(cp: int) -> int:
    for lo, hi in _WEIGHT_ONE_RANGES:
        if lo <= cp <= hi:
            return 1
    return 2


def tweet_weight(text: str) -> int:
    """The weighted length X will meter this text at (URLs as 23)."""
    total = 0
    last = 0
    for m in _URL_RE.finditer(text):
        for ch in text[last : m.start()]:
            total += _char_weight(ord(ch))
        total += URL_WEIGHT
        last = m.end()
    for ch in text[last:]:
        total += _char_weight(ord(ch))
    return total


def over_limit(text: str) -> bool:
    return tweet_weight(text) > MAX_WEIGHT
