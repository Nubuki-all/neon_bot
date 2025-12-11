import datetime
import re
from typing import Optional

import dateparser
import pytz
from dateutil.relativedelta import relativedelta


def _parse_duration_to_relativedelta(text: str) -> Optional[relativedelta]:
    token_re = re.compile(
        r"(?P<value>\d+)\s*(?P<unit>years?|yrs?|y|months?|mos?|mo|weeks?|wks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
        flags=re.IGNORECASE,
    )
    matches = list(token_re.finditer(text))
    if not matches:
        return None
    kwargs = {}
    for m in matches:
        val = int(m.group("value"))
        unit = m.group("unit").lower()
        if unit.startswith(("y", "yr")):
            kwargs["years"] = kwargs.get("years", 0) + val
        elif unit.startswith(("mo",)) and not unit.startswith("mon"):
            kwargs["months"] = kwargs.get("months", 0) + val
        elif unit.startswith(("w",)):
            kwargs["weeks"] = kwargs.get("weeks", 0) + val
        elif unit.startswith(("d",)):
            kwargs["days"] = kwargs.get("days", 0) + val
        elif unit.startswith(("h",)):
            kwargs["hours"] = kwargs.get("hours", 0) + val
        elif unit.startswith(("m", "min")):
            kwargs["minutes"] = kwargs.get("minutes", 0) + val
        elif unit.startswith(("s", "sec")):
            kwargs["seconds"] = kwargs.get("seconds", 0) + val
    if not kwargs:
        return None
    return relativedelta(**kwargs)


def _next_weekday_from(
    base: datetime.datetime, target_weekday: int
) -> datetime.datetime:
    """
    Return the datetime for the next target_weekday (0=Monday .. 6=Sunday).
    'Next' means strictly future; if today is the target, it returns next week's day.
    Preserves tzinfo on base.
    """
    days_ahead = (target_weekday - base.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    return base + datetime.timedelta(days=days_ahead)


def parse_reminder_time_hybrid(
    user_phrase: str, to_timezone: str = "Africa/Lagos"
) -> Optional[str]:
    """
    Parse a user phrase into an ISO8601 string anchored to `to_timezone`.
    Returns ISO string (timezone-aware) or None if parsing fails.

    Key points:
    - Uses the timezone `to_timezone` as the parsing timezone and RELATIVE_BASE.
    - When using dateparser, the result is returned directly (no extra conversions).
    - "next <weekday> [at <time>]" is handled by combining YYYY-MM-DD + <time> so words like "noon" attach to that date.
    - Duration-only inputs like "2hrs, 2mins" are supported.
    """
    tz = pytz.timezone(to_timezone)
    # RELATIVE_BASE for dateparser and durations
    now_tz = datetime.datetime.now(tz)
    phrase = user_phrase.strip().lower()

    # Duration-only detection (e.g. "in 2hrs", "2hrs 2mins")
    duration_full_re = re.compile(
        r"^(?:in\s+)?(?:\d+\s*(?:years?|yrs?|y|months?|mo|weeks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)(?:[\s,]*)?)+$",
        flags=re.IGNORECASE,
    )
    if duration_full_re.match(phrase):
        rd = _parse_duration_to_relativedelta(phrase)
        if rd:
            target = now_tz + rd
            # dateparser not involved here so localize/ensure tz, then return
            # iso
            if target.tzinfo is None:
                target = tz.localize(target)
            return target.isoformat()

    # "next <weekday>" with optional "at <time>" or direct time token
    weekday_names = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    m = re.match(r"next\s+(\w+)(?:\s+at\s+(.+)|\s+(.+))?$", phrase)
    if m:
        day = m.group(1)
        time_phrase = (m.group(2) or m.group(3) or "").strip()
        if day in weekday_names:
            target_date = _next_weekday_from(now_tz, weekday_names[day])
            if time_phrase:
                # Force parser to attach the time to this exact date:
                combined = f"{target_date.date().isoformat()} {time_phrase}"
                settings = {
                    "RETURN_AS_TIMEZONE_AWARE": True,
                    "TIMEZONE": to_timezone,
                    "PREFER_DATES_FROM": "future",
                }
                parsed = dateparser.parse(combined, settings=settings)
                if parsed:
                    # dateparser should honor TIMEZONE and return tz-aware; if
                    # not, localize once
                    if parsed.tzinfo is None:
                        parsed = tz.localize(parsed)
                    return parsed.isoformat()
            # no time part -> midnight of that date in tz
            midnight = datetime.datetime.combine(target_date.date(), datetime.time.min)
            midnight = tz.localize(midnight) if midnight.tzinfo is None else midnight
            return midnight.isoformat()

    # Fallback to dateparser using now_tz as RELATIVE_BASE and
    # TIMEZONE=to_timezone
    settings = {
        "RETURN_AS_TIMEZONE_AWARE": True,
        "TIMEZONE": to_timezone,
        "RELATIVE_BASE": now_tz,
        "PREFER_DATES_FROM": "future",
        "DEFAULT_LANGUAGES": ["en"],
    }
    parsed = dateparser.parse(phrase, settings=settings)
    if not parsed:
        return None
    # parsed should already be timezone-aware in `to_timezone`. If it's not,
    # localize to tz once.
    if parsed.tzinfo is None:
        parsed = tz.localize(parsed)
    return parsed.isoformat()
