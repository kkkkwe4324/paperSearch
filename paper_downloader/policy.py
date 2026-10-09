RATE_LIMIT_COOLDOWNS = (60, 120, 300, 600)
TRANSIENT_DELAYS = (10, 30, 60)


def validate_range(minimum, maximum, name):
    if (
        not isinstance(minimum, (int, float))
        or isinstance(minimum, bool)
        or not isinstance(maximum, (int, float))
        or isinstance(maximum, bool)
        or minimum < 0
        or maximum < minimum
    ):
        raise ValueError(f"{name} must be non-negative and ordered")


def classify_failure(status, text):
    lowered = text.lower()
    if status in (403, 429) or any(
        marker in lowered for marker in ("captcha", "unusual traffic", "rate limit")
    ):
        return "rate_limited"
    if any(
        marker in lowered
        for marker in ("login", "sign in", "authentication", "sso", "cas", "mfa")
    ):
        return "auth_required"
    return "transient"
