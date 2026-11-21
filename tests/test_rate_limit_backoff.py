"""How the client reacts to a rate limit, which decides how long a run takes.

There was a token pacer here that tried to predict the provider's remaining
allowance from a local bucket and wait before each call. It was removed. A
local model cannot know what the server's window actually holds, so it waited
when there was headroom and still earned a 429 when it guessed high -- having
already paid for the wait. Reading the provider's own reset hint off the 429
is better information and usually asks for milliseconds.

Nothing here touches the network.
"""

from __future__ import annotations

from src.llm import _reset_hint_seconds


def test_it_reads_a_plain_seconds_value():
    assert _reset_hint_seconds({"retry-after": "2"}) == 2.0


def test_it_reads_the_millisecond_form_groq_sends():
    """The common case, and the reason reacting beats predicting."""
    assert _reset_hint_seconds({"x-ratelimit-reset-tokens": "547ms"}) == 0.547


def test_it_reads_the_minutes_and_seconds_form():
    assert _reset_hint_seconds({"x-ratelimit-reset-requests": "1m26.4s"}) == 86.4


def test_retry_after_is_preferred_over_the_reset_hints():
    headers = {"retry-after": "30", "x-ratelimit-reset-tokens": "105ms"}
    assert _reset_hint_seconds(headers) == 30.0


def test_no_hint_returns_zero_so_the_caller_uses_its_own_backoff():
    assert _reset_hint_seconds({}) == 0.0
    assert _reset_hint_seconds(None) == 0.0


def test_an_unreadable_value_does_not_become_a_zero_wait_by_accident():
    """Falling through to the caller's backoff is right; returning 0 silently is not."""
    assert _reset_hint_seconds({"retry-after": "soon"}) == 0.0
