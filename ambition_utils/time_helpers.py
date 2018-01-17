from datetime import datetime
from pytz import common_timezones, timezone, exceptions as pytz_exceptions


def get_gmt_offset(tz_name, now):
    try:
        offset = timezone(tz_name).utcoffset(now)
    except pytz_exceptions.AmbiguousTimeError:  # pragma: no cover
        offset = timezone(tz_name).utcoffset(now, is_dst=False)
    except pytz_exceptions.NonExistentTimeError:  # pragma: no cover
        offset = timezone(tz_name).utcoffset(now, is_dst=False)

    offset = int(offset.total_seconds() / 3600)

    return '{0}'.format(offset) if offset < 0 else '+{0}'.format(offset)


def get_time_zones(return_as_tuple=False):
    """
    Gets timezones to display to the front end (and for validation). Orders timezones
    with common US ones first and attaches GMT offset to them.
    """
    us_tzs = [
        ('US/Eastern', 'US/Eastern (EST)'), ('US/Central', 'US/Central (CST)'),
        ('US/Mountain', 'US/Mountain (MST)'), ('US/Pacific', 'US/Pacific (PST)'),
        ('US/Arizona', 'US/Arizona'), ('US/Alaska', 'US/Alaska'), ('US/Hawaii', 'US/Hawaii')
    ]
    other_tzs = set(common_timezones) - set(us_tz[0] for us_tz in us_tzs)
    all_tzs = us_tzs + [(tz, tz) for tz in other_tzs]

    # Attach GMT values to the display names of the tzs
    now = datetime.utcnow()
    all_tzs = [
        (tz[0], '{0} (GMT {1})'.format(tz[1], get_gmt_offset(tz[0], now))) for tz in all_tzs
    ]

    return all_tzs if return_as_tuple else [{
        'id': tz[0],
        'name': tz[1],
    } for tz in all_tzs]
