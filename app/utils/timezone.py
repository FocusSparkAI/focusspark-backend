from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "UTC"


def normalize_timezone(value: str | None) -> str:
    timezone_name = (value or "").strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return DEFAULT_TIMEZONE
    return timezone_name


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def user_zone(user) -> ZoneInfo:
    return ZoneInfo(normalize_timezone(getattr(user, "timezone", None)))


def user_now(user) -> datetime:
    return datetime.now(timezone.utc).astimezone(user_zone(user))


def user_today(user) -> date:
    return user_now(user).date()


def user_local_datetime(value: datetime, user) -> datetime:
    return _as_utc_aware(value).astimezone(user_zone(user))


def user_local_date(value: datetime, user) -> date:
    return user_local_datetime(value, user).date()


def user_local_hour(value: datetime, user) -> int:
    return user_local_datetime(value, user).hour


def user_day_start_utc(day: date, user) -> datetime:
    local_start = datetime.combine(day, time.min, tzinfo=user_zone(user))
    return local_start.astimezone(timezone.utc).replace(tzinfo=None)


def user_day_end_utc(day: date, user) -> datetime:
    local_end = datetime.combine(day, time.max, tzinfo=user_zone(user))
    return local_end.astimezone(timezone.utc).replace(tzinfo=None)
