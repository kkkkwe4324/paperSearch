import pytest

from paper_downloader.policy import (
    RATE_LIMIT_COOLDOWNS,
    TRANSIENT_DELAYS,
    classify_failure,
    validate_range,
)


def test_policy_delays_are_conservative():
    assert RATE_LIMIT_COOLDOWNS == (60, 120, 300, 600)
    assert TRANSIENT_DELAYS == (10, 30, 60)


def test_validate_range_accepts_integer_and_float_bounds():
    assert validate_range(0, 10, "delay") is None
    assert validate_range(0.5, 1.5, "delay") is None


def test_validate_range_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        validate_range(-1, 10, "delay")
    with pytest.raises(ValueError):
        validate_range(20, 10, "delay")
    with pytest.raises(ValueError):
        validate_range("0", 10, "delay")


@pytest.mark.parametrize(
    ("status", "text", "expected"),
    [
        (403, "forbidden", "rate_limited"),
        (429, "too many requests", "rate_limited"),
        (None, "CAPTCHA challenge", "rate_limited"),
        (None, "unusual traffic", "rate_limited"),
        (None, "rate limit reached", "rate_limited"),
        (None, "Authentication required", "auth_required"),
        (None, "Sign in to continue", "auth_required"),
        (None, "SSO login", "auth_required"),
        (None, "CAS MFA", "auth_required"),
        (500, "server error", "transient"),
    ],
)
def test_classify_failure(status, text, expected):
    assert classify_failure(status, text) == expected
