import datetime

from dateutil import rrule
from django.test import TestCase

from ambition_utils.rrule.constants import RecurrenceEnds
from ambition_utils.rrule.forms import RecurrenceForm


class NestedRecurrenceFormTest(TestCase):
    def test_daily_never_ends(self):
        data = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': '6/1/2017',
            'byhour': '3',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
        }
        form = RecurrenceForm(data=data)
        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule[0].replace(tzinfo=None), datetime.datetime(2017, 6, 1, 3))
        self.assertEqual(rule[1].replace(tzinfo=None), datetime.datetime(2017, 6, 2, 3))
        self.assertEqual(rule[365].replace(tzinfo=None), datetime.datetime(2018, 6, 1, 3))

    def test_daily_never_ends_different_time_zone(self):
        data = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': '6/1/2017',
            'byhour': '22',
            'time_zone': 'US/Eastern',
            'ends': RecurrenceEnds.NEVER,
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rrule_model.next_occurrence, datetime.datetime(2017, 6, 2, 2))

        self.assertEqual(rule[0].replace(tzinfo=None), datetime.datetime(2017, 6, 1, 22))
        self.assertEqual(rule[1].replace(tzinfo=None), datetime.datetime(2017, 6, 2, 22))
        self.assertEqual(rule[365].replace(tzinfo=None), datetime.datetime(2018, 6, 1, 22))

        # Advance the occurrence
        rrule_model.update_next_occurrence()

        self.assertEqual(rrule_model.next_occurrence, datetime.datetime(2017, 6, 3, 2))

    def test_daily_every_4_days_3_times(self):
        data = {
            'freq': rrule.DAILY,
            'interval': 4,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.AFTER,
            'count': 3,
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule.count(), 3)

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 1))
        self.assertEqual(rule[1], datetime.datetime(2017, 6, 5))
        self.assertEqual(rule[2], datetime.datetime(2017, 6, 9))

    def test_return_if_errors(self):
        """
        Returns from the clean method if there are already errors
        """
        data = {}
        form = RecurrenceForm(data=data)

        self.assertFalse(form.is_valid())

        self.assertEqual(form.clean(), {
            'bynweekday': [],
            'byweekday': [],
            'count': None,
            'repeat_by': '',
            'until': None,
        })

    def test_missing_after_occurrences_count(self):
        data = {
            'freq': rrule.DAILY,
            'interval': 4,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.AFTER,
        }
        form = RecurrenceForm(data=data)

        self.assertFalse(form.is_valid())

    def test_daily_with_end_date(self):
        data = {
            'freq': rrule.DAILY,
            'interval': 6,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.ON,
            'until': '6/10/2017',
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule.count(), 2)

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 1))
        self.assertEqual(rule[1], datetime.datetime(2017, 6, 7))

    def test_missing_ends_on(self):
        """
        Checks that there is an end date if the recurrence is set to end on a date
        """
        data = {
            'freq': rrule.DAILY,
            'interval': 6,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.ON,
        }
        form = RecurrenceForm(data=data)

        self.assertFalse(form.is_valid())

    def test_clear_ends_on_if_not_selected(self):
        """
        This handles a case with the date picker (and won't happen after date picker is fixed, but should still
        be handled) where the date field is not cleared when another ends choice is selected.
        """
        data = {
            'freq': rrule.DAILY,
            'interval': 6,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
            'until': '6/1/2017',
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['until'], '')

    def test_end_date_after_start_date(self):
        """
        Makes sure the end date is after the start date
        """
        data = {
            'freq': rrule.DAILY,
            'interval': 6,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.ON,
            'until': '5/31/2017',
        }
        form = RecurrenceForm(data=data)
        self.assertFalse(form.is_valid())

        data['until'] = '6/1/2017'
        form = RecurrenceForm(data=data)
        self.assertFalse(form.is_valid())

        data['until'] = '6/2/2017'
        form = RecurrenceForm(data=data)
        self.assertTrue(form.is_valid())

    def test_weekly_mwf_every_2_weeks_with_end(self):
        data = {
            'freq': rrule.WEEKLY,
            'interval': 2,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.ON,
            'until': '7/10/2017',
            'byweekday': '[0, 2, 4]',
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule.count(), 8)

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 2))
        self.assertEqual(rule[1], datetime.datetime(2017, 6, 12))
        self.assertEqual(rule[2], datetime.datetime(2017, 6, 14))
        self.assertEqual(rule[3], datetime.datetime(2017, 6, 16))
        self.assertEqual(rule[4], datetime.datetime(2017, 6, 26))
        self.assertEqual(rule[5], datetime.datetime(2017, 6, 28))
        self.assertEqual(rule[6], datetime.datetime(2017, 6, 30))
        self.assertEqual(rule[7], datetime.datetime(2017, 7, 10))

    def test_weekly_missing_repeat_on(self):
        data = {
            'freq': rrule.WEEKLY,
            'interval': 2,
            'dtstart': '6/1/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.ON,
            'until': '7/10/2017',
            'byweekday': '',
        }
        form = RecurrenceForm(data=data)

        self.assertFalse(form.is_valid())

    def test_monthly_every_month_day_of_month(self):
        data = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': '6/4/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
            'repeat_by': 'DAY_OF_THE_MONTH',
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 4))
        self.assertEqual(rule[1], datetime.datetime(2017, 7, 4))
        self.assertEqual(rule[2], datetime.datetime(2017, 8, 4))

    def test_monthly_every_month_day_of_week_from_start_of_month(self):
        """
        Second Monday of each month
        """
        data = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': '6/11/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
            'repeat_by': 'DAY_OF_THE_WEEK_START',
            'bynweekday': '[[0, 2]]',
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 12))
        self.assertEqual(rule[1], datetime.datetime(2017, 7, 10))
        self.assertEqual(rule[2], datetime.datetime(2017, 8, 14))

    def test_monthly_every_month_day_of_week_from_end_of_month(self):
        """
        Second Monday from end of month every other month
        """
        data = {
            'freq': rrule.MONTHLY,
            'interval': 2,
            'dtstart': '6/11/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
            'repeat_by': 'DAY_OF_THE_WEEK_END',
            'bynweekday': '[[0, -2]]'
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 19))
        self.assertEqual(rule[1], datetime.datetime(2017, 8, 21))
        self.assertEqual(rule[2], datetime.datetime(2017, 10, 23))

    def test_yearly(self):
        data = {
            'freq': rrule.YEARLY,
            'interval': 1,
            'dtstart': '6/4/2017',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
        }
        form = RecurrenceForm(data=data)

        self.assertTrue(form.is_valid())

        rrule_model = form.save()
        rule = rrule_model.get_rrule()

        self.assertEqual(rule[0], datetime.datetime(2017, 6, 4))
        self.assertEqual(rule[1], datetime.datetime(2018, 6, 4))
        self.assertEqual(rule[2], datetime.datetime(2019, 6, 4))
