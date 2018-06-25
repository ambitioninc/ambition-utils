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


class Weekday:
    """
    Python, Postgres and Django each have different conventions for assigning numbers to weekdays.
    This class provides a general utility for translating between the conventions when you need to.

    See the following for references to the different conventions:
        - Python datetime.weekday() and datetime.isoweekday(): https://docs.python.org/3.6/library/datetime.html
        - Django: https://docs.djangoproject.com/en/dev/ref/models/querysets/#week-day
        - Postgres DOW() function: https://www.postgresql.org/docs/8.2/static/functions-datetime.html

    The translations are implemented using a lookup table.  There is probably some fancy modulo math
    that could be used, but lookups are fairly quick, and easy to understand.

    Here are some examples:


    # Convert Python Monday to a Postgres Monday
    postgres_monday = Weekday(0, convention='python').postgres
    postgres_monday = Weekday(0, convention='python')['postgres']

    # Convert a Postgres Monday to a Python Monday
    python_monday = Weekday(1, convention='postgres').python

    """
    # This lookup has keys of the python convention and values of each of the other types of conventions
    LOOKUP = {
        ('python', 'python'): {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6},
        ('python', 'django'): {0: 2, 1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 1},
        ('python', 'postgres'): {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0},
        ('python', 'iso'): {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7}
    }

    # Compute reverse relations
    LOOKUP[('django', 'python')] = {v: k for (k, v) in LOOKUP[('python', 'django')].items()}
    LOOKUP[('postgres', 'python')] = {v: k for (k, v) in LOOKUP[('python', 'postgres')].items()}
    LOOKUP[('iso', 'python')] = {v: k for (k, v) in LOOKUP[('python', 'iso')].items()}

    _CONVENTIONS = {t[1] for t in LOOKUP.keys()}

    @classmethod
    def _check_convention(cls, convention):
        """
        Make sure only valid conventions are specified
        """
        if convention not in cls._CONVENTIONS:
            raise ValueError(f'Allowed conventions: {cls._CONVENTIONS}')

    def __init__(self, input_day, convention='python'):
        """
        :param input_day: An integer representing the day
        :param convention:  The convention assumed for the input day
        """
        # Make sure the convention is valid
        self._check_convention(convention)

        # Get the lookup from the input convention into Python
        to_python = self.LOOKUP[(convention, 'python')]

        # Make sure the input day is valid
        if input_day not in to_python:
            raise ValueError(f'Valid input days for {convention} are {list(to_python.keys())}')

        # Convert the input into a python weekday
        python_day = self.LOOKUP[(convention, 'python')][input_day]

        # Populate the appropriate values for all the conventions
        for conv in self._CONVENTIONS:
            setattr(self, conv, self.LOOKUP[('python', conv)][python_day])

    def __getitem__(self, convention):
        """
        Allow for dictionary-like access to convention attributes
        """
        self._check_convention(convention)
        return getattr(self, convention)
