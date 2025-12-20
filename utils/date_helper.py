from datetime import datetime

try:
    # optional dependency for robust parsing
    from dateutil import parser as _dateutil_parser
except Exception:
    _dateutil_parser = None


def _parse_to_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    # try dateutil if available
    if _dateutil_parser:
        try:
            return _dateutil_parser.parse(s)
        except Exception:
            pass
    # try isoformat
    try:
        if 'T' in s:
            # fromisoformat supports offset like +00:00
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        pass
    # try common formats
    for fmt in [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%d/%m/%Y %H:%M',
        '%m/%d/%Y %H:%M',
        '%d-%m-%Y %H:%M',
        '%m-%d-%Y %H:%M',
    ]:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    # final fallback: try float timestamp
    try:
        ts = float(s)
        return datetime.fromtimestamp(ts)
    except Exception:
        return None


def format_datetime(value, day_first=False):
    """Format a date/time value into M/D/YYYY H:MM (no leading zeros for month/day).

    - value: datetime, ISO string, or timestamp.
    - day_first: if True, format as D/M/YYYY H:MM instead.

    Returns empty string for invalid values.
    """
    dt = _parse_to_datetime(value)
    if not dt:
        return ""
    # normalize to local naive datetime (do not change timezone)
    month = dt.month
    day = dt.day
    year = dt.year
    hour = dt.hour
    minute = dt.minute
    if day_first:
        return f"{day}/{month}/{year} {hour}:{minute:02d}"
    return f"{month}/{day}/{year} {hour}:{minute:02d}"


# helper to register as jinja filter
def register_jinja_filters(app):
    app.add_template_filter(lambda v, day_first=False: format_datetime(v, day_first=day_first), 'format_datetime')
