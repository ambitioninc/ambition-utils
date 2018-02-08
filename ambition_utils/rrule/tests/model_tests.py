import datetime

import pytz
from dateutil import rrule
from django.test import TestCase
from freezegun import freeze_time

from ambition_utils.rrule.handler import OccurrenceHandler

from ambition_utils.rrule.models import RRule


class MockHandler(OccurrenceHandler):
    """
    Mack handler for handling an occurrence during testing
    """
    def handle(self, rrule):
        return True


class RRuleTest(TestCase):

    def test_get_next_occurrence_first_is_occurrence(self):
        """
        First occurrence should be the dtstart
        """

        # Setup the params for creating the rule
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1),
            'count': 3,
            'bymonthday': 1,
            'byhour': 10,
        }

        # Create the rule
        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        # Assert initial values
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 1, 10))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 2, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 2, 1, 10))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 3, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 3, 1, 10))
        self.assertEqual(rule.next_occurrence, None)

        # For coverage run the handler
        with freeze_time('1-3-2017'):
            handler = MockHandler()

            self.assertTrue(handler.handle(None))

    def test_get_next_occurrence_first_is_not_occurrence(self):
        """
        First occurrence should be later than the dtstart
        """

        # Create the params to create the rule
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
            'count': 3,
            'bymonthday': 1,
            'byhour': 10,
        }

        # Create the rule
        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        # Assert the initial values
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 2, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 2, 1, 10))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 3, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 3, 1, 10))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 4, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 4, 1, 10))
        self.assertEqual(rule.next_occurrence, None)

    def test_get_next_occurrence_force(self):
        """
        If there is no next occurrence but we want to know what it would have been
        """

        # Create the params to create the rule
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
            'count': 1,
            'bymonthday': 1,
            'byhour': 10,
        }

        # Create the rule
        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        # Assert the initial values
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 2, 1, 10))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 2, 1, 10))
        self.assertEqual(rule.next_occurrence, None)
        self.assertEqual(rule.get_next_occurrence(force=True), datetime.datetime(2017, 3, 1, 10))

        # Coverage for returning early
        self.assertEqual(rule.update_next_occurrence(), None)

    def test_model_default_time_zone(self):
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'UTC')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 1))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2))

    def test_model_different_time_zone_daily(self):
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'US/Eastern')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 2, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 3, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 3, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 4, 3))

    def test_model_different_time_zone_monthly(self):
        """
        Test a monthly first day of month rule to catch case of converting tz back
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'bymonthday': 1,
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'US/Eastern')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 2, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 2, 2, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 2, 2, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 3, 2, 3))

        # Cross dst
        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 3, 2, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 4, 2, 2))

    def test_model_different_time_zone_end_of_month(self):
        """
        Test a monthly first day of month rule to catch case of converting tz back
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'bymonthday': -1,
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'US/Eastern')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 2, 1, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 2, 1, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 3, 1, 3))

        # Test crossing dst
        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 3, 1, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 4, 1, 2))

    def test_model_different_time_zone_daily_with_ending_early(self):
        """
        Makes sure the time_zone is respected and ends before the ending time
        """
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'until': datetime.datetime(2017, 1, 3, 21),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'US/Eastern')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 2, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 3, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 3, 3))
        self.assertEqual(rule.next_occurrence, None)

        # Save again to hit all conditions (resaving when dtstart and until are already strings)
        rule.save()

        self.assertEqual(rule.rrule_params['dtstart'], '2017-01-01 22:00:00')
        self.assertEqual(rule.rrule_params['until'], '2017-01-03 21:00:00')

    def test_model_different_time_zone_daily_with_ending_on_interval(self):
        """
        Makes sure the time_zone is respected and ends before the ending time
        """
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'until': datetime.datetime(2017, 1, 3, 22),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'US/Eastern')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 2, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 3, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 3, 3))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 4, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 4, 3))
        self.assertEqual(rule.next_occurrence, None)

    def test_get_next_occurrence_count(self):
        """
        Makes sure the count ending is respected
        """
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1),
            'count': 3,
        }

        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 1))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 3))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 3))
        self.assertEqual(rule.next_occurrence, None)

    @freeze_time('1-1-2016')
    def test_update_next_occurrence_ignore(self):
        """
        Make sure the next occurrence does not advance if the current time is beyond the next occurrence
        """
        params = {
            'freq': rrule.DAILY,
            'dtstart': datetime.datetime(2017, 1, 1),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1))

    @freeze_time('1-1-2018')
    def test_update_next_occurrence(self):
        """
        Make sure the next occurrence does not advance if the current time is beyond the next occurrence
        """
        params = {
            'freq': rrule.DAILY,
            'dtstart': datetime.datetime(2017, 1, 1),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2017, 1, 1))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 2))
