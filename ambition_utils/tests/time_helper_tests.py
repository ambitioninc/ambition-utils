import pytz
from django.test import TestCase, SimpleTestCase
from freezegun import freeze_time

from ambition_utils.time_helpers import get_time_zones, Weekday


class TimeHelperTestCase(TestCase):

    @freeze_time('1-1-2017')
    def test_get_time_zones(self):
        """
        Makes sure the time zones are returned as dicts and that eastern is first
        """

        time_zones = get_time_zones()

        self.assertEqual(time_zones[0]['id'], 'US/Eastern')
        self.assertEqual(time_zones[0]['name'], 'US/Eastern (EST) (GMT -5)')
        self.assertTrue(len(time_zones) > 400)

    @freeze_time('1-1-2017')
    def test_get_time_zones_as_tuple(self):
        """
        Makes sure the time zones are returned as tuples and that eastern is first
        """

        time_zones = get_time_zones(return_as_tuple=True)

        self.assertEqual(time_zones[0][0], 'US/Eastern')
        self.assertEqual(time_zones[0][1], 'US/Eastern (EST) (GMT -5)')

    def test_get_timezones_contains_all_timezones(self):
        """
        Ensures that the get_timezones method returns pytz.all_timezones rather than pytz.common_timezones
        """
        # get a set of all_timezones from pytz
        timezones_all_pytz = set(pytz.all_timezones)

        # get the actual timezones we are returning
        timezones_actual = get_time_zones(return_as_tuple=False)
        timezones_actual_set = set()

        # grab the appropriate timezone format for comparison
        [timezones_actual_set.add(item['id']) for item in timezones_actual]

        # grab the timezones that exist in pytz.all_timezones but don't exist in the actual timezones set
        timezones_difference = timezones_all_pytz.difference(timezones_actual_set)

        self.assertEqual(len(timezones_difference), 0)


class TestWeekday(SimpleTestCase):
    def test_bad_convention(self):
        with self.assertRaises(ValueError):
            Weekday(0, convention='bad')

    def test_bad_day(self):
        with self.assertRaises(ValueError):
            Weekday(9)

    def test_mondays(self):

        mondays = {
            'python': 0,
            'django': 2,
            'postgres': 1,
            'iso': 1,
        }

        sundays = {
            'python': 6,
            'django': 1,
            'postgres': 0,
            'iso': 7,
        }

        # Test that mondays look right
        python_day = 0
        weekday = Weekday(python_day)
        for convention in mondays.keys():
            # Test forward
            convention_day1 = weekday[convention]
            convention_day2 = getattr(weekday, convention)
            self.assertEqual(convention_day1, convention_day2)
            self.assertEqual(convention_day1, mondays[convention])

            # Test backward
            weekday_back = Weekday(convention_day1, convention)
            self.assertEqual(weekday_back.python, python_day)

        # Test that sundays look right
        python_day = 6
        weekday = Weekday(python_day)
        for convention in mondays.keys():
            convention_day1 = weekday[convention]
            convention_day2 = getattr(weekday, convention)
            self.assertEqual(convention_day1, convention_day2)
            self.assertEqual(convention_day1, sundays[convention])

            # Test backward
            weekday_back = Weekday(convention_day1, convention)
            self.assertEqual(weekday_back.python, python_day)
