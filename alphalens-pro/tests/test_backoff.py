from __future__ import annotations

import pytest

from backend.data.backoff import with_backoff


def test_backoff_succeeds_after_retries() -> None:
    calls = {"n": 0}
    delays: list[float] = []

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("boom")
        return "ok"

    assert with_backoff(flaky, retries=4, sleep=delays.append) == "ok"
    assert calls["n"] == 3
    assert len(delays) == 2
    assert delays[1] > delays[0] - 1  # exponentiell wachsend (Jitter toleriert)


def test_backoff_raises_after_max_retries() -> None:
    def always_fails() -> None:
        raise TimeoutError("dauerhaft down")

    with pytest.raises(TimeoutError):
        with_backoff(always_fails, retries=2, sleep=lambda _: None)
