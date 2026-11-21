"""The pacer decides how long a run takes, so its arithmetic is tested.

Nothing here touches the network. The pacer is driven directly with the
numbers a provider would have returned in its headers.
"""

from __future__ import annotations

import time

from src.llm import _TokenPacer


def test_it_waits_before_the_first_call_because_it_cannot_know_the_window():
    """A fresh process has no idea what the last one already spent.

    Starting full would burst past the real allowance and earn a 429 carrying
    a multi-minute retry-after, which costs more than the wait it saved.
    """
    pacer = _TokenPacer(tokens_per_minute=8000)
    waited = pacer.acquire(estimated=800)
    assert waited > 0


def test_a_reported_allowance_is_adopted_rather_than_only_lowered():
    """The regression that cost seven minutes on an eighty ticket run.

    Taking a minimum here made the estimate monotonically pessimistic: once
    the bucket read low it could never be told it had refilled, so every later
    call was metered out at the refill rate against an allowance that was
    actually untouched.
    """
    pacer = _TokenPacer(tokens_per_minute=8000)
    pacer.acquire(estimated=800)        # drains the local bucket
    pacer.observe(remaining_tokens=7900)  # the server says there is room

    started = time.monotonic()
    waited = pacer.acquire(estimated=800)
    assert waited == 0
    assert time.monotonic() - started < 0.1


def test_a_drained_allowance_is_still_respected():
    """Trusting the server has to cut both ways or it is just optimism."""
    pacer = _TokenPacer(tokens_per_minute=8000)
    pacer.observe(remaining_tokens=7900)
    pacer.observe(remaining_tokens=10)
    assert pacer.acquire(estimated=800) > 0


def test_it_never_demands_more_than_one_window_holds():
    """An estimate above capacity must not wedge the run forever."""
    pacer = _TokenPacer(tokens_per_minute=100)
    pacer.observe(remaining_tokens=100)
    assert pacer.acquire(estimated=10_000) == 0
