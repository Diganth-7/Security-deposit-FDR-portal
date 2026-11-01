"""Time helpers shared by models, services and routers.

* ``utc_now()``  - naive UTC timestamp (the DB columns are naive UTC DateTimes).
                    Replaces the deprecated ``datetime.utcnow()``.
* ``today()``    - the calendar date used for maturity logic. When APP_TIMEZONE is
                    set (e.g. "Asia/Kolkata") it is that zone's date, otherwise
                    the server's local date. FDR maturity is a calendar-date
                    concept, so this must not silently depend on the server zone
                    in production: set APP_TIMEZONE there.
* ``add_months()`` - calendar month arithmetic that clamps to month end.
"""
import calendar
import logging
from datetime import date, datetime, timezone

from backend.app.config import settings

logger = logging.getLogger("aicte_fdr.clock")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today() -> date:
    tz_name = (settings.APP_TIMEZONE or "").strip()
    if not tz_name:
        return date.today()
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:  # unknown zone or missing tzdata: fall back, but say so once
        logger.warning("APP_TIMEZONE=%r is not usable; falling back to server local date", tz_name)
        return date.today()


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
