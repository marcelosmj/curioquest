"""Values in the formats the Flash client parses."""
from datetime import datetime, timezone

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def as3_date(moment=None):
    """A UTC date string Flash's Date.parse() accepts, e.g. 'Mon Sep 15 13:04:05 GMT+0000 2026'.

    `moment` may be a datetime or a Unix timestamp; defaults to now."""
    if moment is None:
        moment = datetime.now(timezone.utc)
    elif isinstance(moment, (int, float)):
        moment = datetime.fromtimestamp(moment, timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return f"{_DAYS[moment.weekday()]} {_MONTHS[moment.month - 1]} {moment.day} {moment:%H:%M:%S} GMT+0000 {moment.year}"
