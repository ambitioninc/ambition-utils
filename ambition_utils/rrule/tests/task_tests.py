import datetime

from dateutil import rrule
from django_dynamic_fixture import G
from django.test import TestCase
from freezegun import freeze_time

from ambition_utils.rrule.handler import OccurrenceHandler
from ambition_utils.rrule.models import RRule
from ambition_utils.rrule.tasks import RecurrenceTask


class HandlerOne(OccurrenceHandler):

    def handle(self):
        return RRule.objects.filter(
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerOne',
            next_occurrence__lte=datetime.datetime.utcnow(),
        ).order_by('id')


class HandlerTwo(OccurrenceHandler):

    def handle(self):
        return RRule.objects.filter(
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerTwo',
            next_occurrence__lte=datetime.datetime.utcnow(),
        ).order_by('id')


class HandlerThree(OccurrenceHandler):

    def handle(self):
        return RRule.objects.filter(
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerThree',
            next_occurrence__lte=datetime.datetime.utcnow(),
        ).order_by('id')


class RecurrenceTaskTest(TestCase):

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
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerOne'
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
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerOne'
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
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerTwo'
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
            occurrence_handler_path='ambition_utils.rrule.tests.task_tests.HandlerThree'
        )

        # Get and verify the classes
        classes = {
            instance.__class__
            for instance in RRule.objects.overdue_handler_class_instances()
        }

        self.assertEqual(classes, {HandlerOne, HandlerTwo})

        # Make the task object
        task = RecurrenceTask()

        # Run the task
        task.run()

        # Check the recurrences. ids 2 and 3 should be updated
        recurrences = list(RRule.objects.order_by('id'))

        self.assertEqual(recurrences[0].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[1].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[2].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[3].next_occurrence, datetime.datetime(2017, 1, 2))

        # For coverage, make handler 3 overdue
        with freeze_time('1-3-2017'):
            task.run()
