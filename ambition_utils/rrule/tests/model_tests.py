import datetime

import pytz
from dateutil import rrule
from django_dynamic_fixture import G
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


class HandlerOne(OccurrenceHandler):

    def handle(self):
        return RRule.objects.filter(
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne',
            next_occurrence__lte=datetime.datetime.utcnow(),
        ).order_by('id')


class HandlerTwo(OccurrenceHandler):

    def handle(self):
        return RRule.objects.filter(
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerTwo',
            next_occurrence__lte=datetime.datetime.utcnow(),
        ).order_by('id')


class HandlerThree(OccurrenceHandler):

    def handle(self):
        return RRule.objects.filter(
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerThree',
            next_occurrence__lte=datetime.datetime.utcnow(),
        ).order_by('id')


class RRuleManagerTest(TestCase):

    def test_update_next_occurrences(self):
        """
        Make sure that the correct occurrences are selected
        """
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }

        rrule1 = G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne'
        )

        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }

        rrule2 = G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne'
        )

        self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 2))

        # Progress no rules
        with freeze_time('1-3-2017'):
            RRule.objects.update_next_occurrences()

        rrule1.refresh_from_db()
        rrule2.refresh_from_db()

        # Both should be progressed
        self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 2))

        # Progress all rules
        with freeze_time('1-3-2017'):
            RRule.objects.update_next_occurrences([rrule1, rrule2])

        rrule1.refresh_from_db()
        rrule2.refresh_from_db()

        # Both should be progressed
        self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 3))
        self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 3))

        # Progress specific rrules
        with freeze_time('1-4-2017'):
            RRule.objects.update_next_occurrences(rrule_objects=[rrule1])

        rrule1.refresh_from_db()
        rrule2.refresh_from_db()

        # One should be progressed
        self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 4))
        self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 3))

        # Make sure neither are progressed with passing an empty list
        with freeze_time('1-5-2017'):
            RRule.objects.update_next_occurrences(rrule_objects=[])

        rrule1.refresh_from_db()
        rrule2.refresh_from_db()

        # One should be progressed
        self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 4))
        self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 3))

    @freeze_time('1-1-2017')
    def test_run(self):
        """
        Should return the classes that have overdue rrule objects
        """

        # Make a program with HandlerOne that is not overdue
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }

        G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne'
        )

        # Make an overdue program with HandlerOne
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1),
        }

        G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne'
        )

        # Make an overdue program with HandlerTwo
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1),
        }

        G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerTwo'
        )

        # Make a program with HandlerThree that is not overdue
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }

        G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerThree'
        )

        # Get and verify the classes
        classes = {
            instance.__class__
            for instance in RRule.objects.overdue_handler_class_instances()
        }

        self.assertEqual(classes, {HandlerOne, HandlerTwo})

        # Handle overdue rrules
        RRule.objects.handle_overdue()

        # Check the recurrences. ids 2 and 3 should be updated
        recurrences = list(RRule.objects.order_by('id'))

        self.assertEqual(recurrences[0].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[1].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[2].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[3].next_occurrence, datetime.datetime(2017, 1, 2))

        # For coverage, make handler 3 overdue
        with freeze_time('1-3-2017'):
            RRule.objects.handle_overdue()


class RRuleTest(TestCase):

    def test_get_time_zone_object_none(self):
        """
        Should return utc when time zone is null
        """
        rrule = RRule()
        rrule.time_zone = None
        self.assertEqual(rrule.get_time_zone_object(), pytz.utc)

    def test_get_time_zone_object_str(self):
        """
        Should return an object when time zone is a string
        """
        rrule = RRule()
        rrule.time_zone = 'UTC'
        self.assertEqual(rrule.get_time_zone_object(), pytz.utc)

    def test_get_time_zone_object(self):
        """
        Should return the object when time zone is an object
        """
        rrule = RRule()
        rrule.time_zone = pytz.utc
        self.assertEqual(rrule.get_time_zone_object(), pytz.utc)

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
        self.assertEqual(rule.get_next_occurrence(), None)
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

    def test_model_different_time_zone_ahead_daily(self):
        """
        Checks a time zone that is ahead of utc
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2018, 6, 19),
            'byhour': 1,
            'until': datetime.datetime(2018, 6, 20),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('Europe/London'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'Europe/London')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2018, 6, 19, 0))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2018, 6, 19, 0))
        self.assertEqual(rule.next_occurrence, None)

        # Check using a past time
        with freeze_time('1-3-2017'):
            # Use the force flag to get the next date
            self.assertEqual(rule.get_next_occurrence(), None)
            self.assertEqual(rule.get_next_occurrence(force=True), datetime.datetime(2018, 7, 19, 0))

        # Check using a future time
        with freeze_time('1-3-2117'):
            # Use the force flag to get the next date
            self.assertEqual(rule.get_next_occurrence(), None)
            self.assertEqual(rule.get_next_occurrence(force=True), datetime.datetime(2018, 7, 19, 0))

    def test_model_different_time_zone_ahead_crossing_day_daily(self):
        """
        Checks a time zone that is ahead of utc
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2018, 6, 19),
            'byhour': 0,
            'until': datetime.datetime(2018, 6, 20),
        }

        rule = RRule.objects.create(
            rrule_params=params,
            time_zone=pytz.timezone('Europe/London'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        self.assertEqual(rule.time_zone.zone, 'Europe/London')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2018, 6, 18, 23))

        # Handle the next occurrence
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2018, 6, 18, 23))
        self.assertEqual(rule.next_occurrence, None)

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

    def test_generate_dates(self):
        """
        Test a monthly first day of month rule to catch case of converting tz back using the generate_dates method
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'bymonthday': -1,
            'until': datetime.datetime(2017, 5, 1, 22),
        }

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )
        next_dates = rule.generate_dates()

        # Check a few dates
        self.assertEqual(len(next_dates), 4)
        self.assertEqual(next_dates[0], datetime.datetime(2017, 2, 1, 3))
        self.assertEqual(next_dates[1], datetime.datetime(2017, 3, 1, 3))
        self.assertEqual(next_dates[2], datetime.datetime(2017, 4, 1, 2))
        self.assertEqual(next_dates[3], datetime.datetime(2017, 5, 1, 2))

        # Run pre save again to make sure it doesn't mess up params
        rule.pre_save_hooks()

        # Get next dates to compare against
        more_next_dates = rule.generate_dates()
        self.assertEqual(next_dates, more_next_dates)

    def test_generate_dates_from_params(self):
        """
        Tests the class method wrapper
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'bymonthday': -1,
            'until': datetime.datetime(2017, 5, 1, 22),
        }

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )
        next_dates = rule.generate_dates(num_dates=3)

        next_dates_from_params = RRule.generate_dates_from_params(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            num_dates=3,
        )

        self.assertEqual(next_dates, next_dates_from_params)

    def test_model_different_time_zone_end_of_month_generate_dates(self):
        """
        Test a monthly first day of month rule to catch case of converting tz back using the generate_dates method
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 1, 22),
            'bymonthday': -1,
        }

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )
        next_dates = rule.generate_dates()
        self.assertEqual(next_dates[0], datetime.datetime(2017, 2, 1, 3))
        self.assertEqual(next_dates[1], datetime.datetime(2017, 3, 1, 3))
        self.assertEqual(next_dates[2], datetime.datetime(2017, 4, 1, 2))
        self.assertEqual(next_dates[3], datetime.datetime(2017, 5, 1, 2))
        self.assertEqual(next_dates[4], datetime.datetime(2017, 6, 1, 2))
        self.assertEqual(next_dates[5], datetime.datetime(2017, 7, 1, 2))
        self.assertEqual(next_dates[6], datetime.datetime(2017, 8, 1, 2))
        self.assertEqual(next_dates[7], datetime.datetime(2017, 9, 1, 2))
        self.assertEqual(next_dates[8], datetime.datetime(2017, 10, 1, 2))
        self.assertEqual(next_dates[9], datetime.datetime(2017, 11, 1, 2))
        self.assertEqual(next_dates[10], datetime.datetime(2017, 12, 1, 3))
        self.assertEqual(next_dates[11], datetime.datetime(2018, 1, 1, 3))
        self.assertEqual(next_dates[12], datetime.datetime(2018, 2, 1, 3))

        self.assertEqual(rule.time_zone.zone, 'US/Eastern')
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 2, 1, 3))

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

    def test_save_existing_update_next_occurrence(self):
        """
        When saving an existing rrule model, make sure that the next occurrence is updated when the
        next occurrence has not yet occurred, and the next occurrence is not updated if the start time
        is before the current date
        """
        params = {
            'freq': rrule.DAILY,
            'dtstart': datetime.datetime(2017, 1, 1),
        }

        with freeze_time('1-1-2018'):
            rule = RRule.objects.create(
                rrule_params=params,
                occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler',
                time_zone=pytz.timezone('US/Eastern'),
            )

            self.assertEqual(rule.last_occurrence, None)
            self.assertEqual(rule.next_occurrence, datetime.datetime(2017, 1, 1, 5))

        # Save the rrule with a current time before the first occurrence
        with freeze_time('1-1-2016'):

            # Change the start date to a future date
            rule.rrule_params['dtstart'] = datetime.datetime(2018, 1, 1)
            rule.refresh_next_occurrence()
            rule.save()
            self.assertEqual(rule.next_occurrence, datetime.datetime(2018, 1, 1, 5))

            # Change the start date to a previous date that is still after the current date
            rule.rrule_params['dtstart'] = datetime.datetime(2016, 2, 1)
            rule.refresh_next_occurrence()
            rule.save()
            self.assertEqual(rule.next_occurrence, datetime.datetime(2016, 2, 1, 5))

            # Try setting the start time to a previous date before the current date and make sure it
            # gets set to the first occurrence after today
            rule.rrule_params['dtstart'] = datetime.datetime(2015, 12, 1)
            rule.refresh_next_occurrence()
            rule.save()
            self.assertEqual(rule.next_occurrence, datetime.datetime(2016, 1, 1, 5))

            # Coverage to test the string dtstart
            rule.rrule_params['dtstart'] = datetime.datetime(2015, 12, 1)
            rule.rrule_params['dtstart'] = rule.rrule_params['dtstart'].strftime('%Y-%m-%d %H:%M:%S')
            rule.save()
            self.assertEqual(rule.next_occurrence, datetime.datetime(2016, 1, 1, 5))

            # Refresh with date in past and make sure it is ignored
            rule.refresh_next_occurrence(current_time=datetime.datetime(2014, 1, 1))
            rule.save()
            self.assertEqual(rule.next_occurrence, datetime.datetime(2016, 1, 1, 5))

    def test_save_with_datetimes(self):
        """
        Verifies that the save method can work with dtstart and until params as datetime objects
        """
        params = {
            'freq': rrule.DAILY,
            'dtstart': datetime.datetime(2019, 5, 1),
            'until': datetime.datetime(2019, 6, 1),
        }
        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler',
            time_zone=pytz.timezone('US/Eastern'),
        )

        self.assertEqual(rule.next_occurrence, datetime.datetime(2019, 5, 1, 4))
        self.assertEqual(rule.rrule_params['dtstart'], '2019-05-01 00:00:00')
        self.assertEqual(rule.rrule_params['until'], '2019-06-01 00:00:00')

    def test_save_with_strings(self):
        """
        Verifies that the save method can work with dtstart and until params as strings
        """
        params = {
            'freq': rrule.DAILY,
            'dtstart': '2019-05-01 00:00:00',
            'until': '2019-06-01 00:00:00',
        }
        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler',
            time_zone=pytz.timezone('US/Eastern'),
        )

        self.assertEqual(rule.next_occurrence, datetime.datetime(2019, 5, 1, 4))
        self.assertEqual(rule.rrule_params['dtstart'], '2019-05-01 00:00:00')
        self.assertEqual(rule.rrule_params['until'], '2019-06-01 00:00:00')
