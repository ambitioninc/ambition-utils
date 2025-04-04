import datetime

import fleming
import pytz
from dateutil import parser, rrule
from django.test import TestCase
from django_dynamic_fixture import G
from freezegun import freeze_time

from ambition_utils.rrule.constants import RecurrenceEnds
from ambition_utils.rrule.forms import RecurrenceForm
from ambition_utils.rrule.handler import OccurrenceHandler
from ambition_utils.rrule.models import RRule
from ambition_utils.rrule.tests.models import Program


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


class HandlerNoOp(OccurrenceHandler):

    def handle(self):
        return None


class RRuleManagerTest(TestCase):
    def add_test_rules(self):
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

        # Add the test rules
        self.add_test_rules()

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

    @freeze_time('1-1-2017')
    def test_run_with_limit(self):
        """
        Test running with a limit
        """

        # Add the test rules
        self.add_test_rules()

        # Get and verify the classes
        classes = {
            instance.__class__
            for instance in RRule.objects.overdue_handler_class_instances(limit=1)
        }

        self.assertEqual(classes, {HandlerOne})

        # Handle overdue rrules
        RRule.objects.handle_overdue(occurrence_handler_limit=1)

        # Check the recurrences, only handler one should be updated
        recurrences = list(RRule.objects.order_by('id'))
        self.assertEqual(recurrences[0].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[1].next_occurrence, datetime.datetime(2017, 1, 2))
        self.assertEqual(recurrences[2].next_occurrence, datetime.datetime(2017, 1, 1))
        self.assertEqual(recurrences[3].next_occurrence, datetime.datetime(2017, 1, 2))

        # Setup our expected classes, each handler needs to occur twice
        # except for handler two which should occur three times
        expected_classes = [
            {HandlerTwo},
            {HandlerThree},
            {HandlerOne},
            {HandlerTwo},
            {HandlerOne},
            {HandlerThree},
            {HandlerTwo},
            set(),
        ]
        for expected_class in expected_classes:
            with freeze_time('1-3-2017'):
                classes = {
                    instance.__class__
                    for instance in RRule.objects.overdue_handler_class_instances(limit=1)
                }
                self.assertEqual(classes, expected_class)
                RRule.objects.handle_overdue(occurrence_handler_limit=1)

        # Assert that the recurrences are updated
        recurrences = list(RRule.objects.order_by('id'))
        self.assertEqual(recurrences[0].next_occurrence, datetime.datetime(2017, 1, 4))
        self.assertEqual(recurrences[1].next_occurrence, datetime.datetime(2017, 1, 4))
        self.assertEqual(recurrences[2].next_occurrence, datetime.datetime(2017, 1, 4))
        self.assertEqual(recurrences[3].next_occurrence, datetime.datetime(2017, 1, 4))

    def test_run_with_no_op(self):
        """
        Test running with a no-op handler
        """
        rrule_params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }
        no_op_rrule1 = G(
            RRule,
            rrule_params=rrule_params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerNoOp'
        )
        no_op_rrule2 = G(
            RRule,
            rrule_params=rrule_params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerNoOp'
        )
        rrule1 = G(
            RRule,
            rrule_params=rrule_params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne'
        )

        # Process with a limit of 1, we should handle the no-op rrules
        with freeze_time(datetime.datetime(2017, 1, 2)):
            RRule.objects.handle_overdue(occurrence_handler_limit=1)

        no_op_rrule1.refresh_from_db()
        no_op_rrule2.refresh_from_db()
        rrule1.refresh_from_db()
        self.assertEqual(no_op_rrule1.time_last_handled, datetime.datetime(2017, 1, 2))
        self.assertEqual(no_op_rrule2.time_last_handled, datetime.datetime(2017, 1, 2))
        self.assertEqual(rrule1.time_last_handled, None)

        # Process with a limit of 1, we should handle handler one
        with freeze_time(datetime.datetime(2017, 1, 3)):
            RRule.objects.handle_overdue(occurrence_handler_limit=1)

        no_op_rrule1.refresh_from_db()
        no_op_rrule2.refresh_from_db()
        rrule1.refresh_from_db()
        self.assertEqual(no_op_rrule1.time_last_handled, datetime.datetime(2017, 1, 2))
        self.assertEqual(no_op_rrule2.time_last_handled, datetime.datetime(2017, 1, 2))
        self.assertEqual(rrule1.time_last_handled, datetime.datetime(2017, 1, 3))

        # Process again and we should go back to the no op handler
        with freeze_time(datetime.datetime(2017, 1, 4)):
            RRule.objects.handle_overdue(occurrence_handler_limit=1)

        no_op_rrule1.refresh_from_db()
        no_op_rrule2.refresh_from_db()
        rrule1.refresh_from_db()
        self.assertEqual(no_op_rrule1.time_last_handled, datetime.datetime(2017, 1, 4))
        self.assertEqual(no_op_rrule2.time_last_handled, datetime.datetime(2017, 1, 4))
        self.assertEqual(rrule1.time_last_handled, datetime.datetime(2017, 1, 3))


class RRuleTest(TestCase):

    def test_related_object_handlers(self):
        """
        Verifies the behavior of rrule related object handlers
        """
        program = Program.objects.create(name='Program 1')
        start_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=program,
            related_object_handler_name='handle_start_recurrence',
        )
        end_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 17),
                'byhour': 17,
            },
            related_object=program,
            related_object_handler_name='handle_end_recurrence',
        )
        program.start_recurrence = start_rrule
        program.end_recurrence = end_rrule
        program.save()

        # Make sure handlers are not called before date
        with freeze_time(datetime.datetime(2022, 5, 31)):
            RRule.objects.handle_overdue()
            program = Program.objects.get(id=program.id)
            self.assertEqual(program.start_called, 0)
            self.assertEqual(program.end_called, 0)
            self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 9))
            self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))

        # Make sure only start handler is called
        with freeze_time(datetime.datetime(2022, 6, 1, 9)):
            RRule.objects.handle_overdue()
            program = Program.objects.get(id=program.id)
            self.assertEqual(program.start_called, 1)
            self.assertEqual(program.end_called, 0)
            self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))

        # Make sure only end handler is called
        with freeze_time(datetime.datetime(2022, 6, 1, 17)):
            RRule.objects.handle_overdue()
            program = Program.objects.get(id=program.id)
            self.assertEqual(program.start_called, 1)
            self.assertEqual(program.end_called, 1)
            self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 17))

    def test_related_object_handlers_with_limit(self):
        """
        Handle overdue related object handlers with a limit
        """
        program = Program.objects.create(name='Program 1')
        start_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=program,
            related_object_handler_name='handle_start_recurrence',
        )
        end_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 17),
                'byhour': 17,
            },
            related_object=program,
            related_object_handler_name='handle_end_recurrence',
        )
        program.start_recurrence = start_rrule
        program.end_recurrence = end_rrule
        program.save()

        program2 = Program.objects.create(name='Program 2')
        start_rrule2 = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=program2,
            related_object_handler_name='handle_start_recurrence',
        )
        end_rrule2 = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 17),
                'byhour': 17,
            },
            related_object=program2,
            related_object_handler_name='handle_end_recurrence',
        )
        program2.start_recurrence = start_rrule2
        program2.end_recurrence = end_rrule2
        program2.save()

        # Make sure only start handler is called for program 1
        with freeze_time(datetime.datetime(2022, 6, 1, 9)):
            RRule.objects.handle_overdue(related_model_handler_limit=1)
            program.refresh_from_db()
            program2.refresh_from_db()
            self.assertEqual(program.start_called, 1)
            self.assertEqual(program.end_called, 0)
            self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))
            self.assertEqual(program2.start_called, 0)
            self.assertEqual(program2.end_called, 0)
            self.assertEqual(program2.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 9))
            self.assertEqual(program2.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))

        # Make sure only start handler is called for program 2
        with freeze_time(datetime.datetime(2022, 6, 1, 9)):
            RRule.objects.handle_overdue(related_model_handler_limit=2)
            program.refresh_from_db()
            program2.refresh_from_db()
            self.assertEqual(program.start_called, 1)
            self.assertEqual(program.end_called, 0)
            self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))
            self.assertEqual(program2.start_called, 1)
            self.assertEqual(program2.end_called, 0)
            self.assertEqual(program2.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program2.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))

        # # Make sure only end handlers are called
        with freeze_time(datetime.datetime(2022, 6, 1, 17)):
            RRule.objects.handle_overdue(related_model_handler_limit=2)
            program = Program.objects.get(id=program.id)
            program2 = Program.objects.get(id=program2.id)
            self.assertEqual(program.start_called, 1)
            self.assertEqual(program.end_called, 1)
            self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 17))
            self.assertEqual(program2.start_called, 1)
            self.assertEqual(program2.end_called, 1)
            self.assertEqual(program2.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 9))
            self.assertEqual(program2.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 2, 17))

    def test_related_object_handlers_no_op(self):
        """
        Test a scenario where the handler of the object is no-op and does not progress the rule
        """

        no_op_program1 = Program.objects.create(name='Program 1')
        rrule1 = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=no_op_program1,
            related_object_handler_name='handle_no_op',
        )
        no_op_program1.start_recurrence = rrule1
        no_op_program1.save()

        no_op_program2 = Program.objects.create(name='Program 1')
        rrule2 = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=no_op_program1,
            related_object_handler_name='handle_no_op',
        )
        no_op_program2.start_recurrence = rrule2
        no_op_program2.save()

        program = Program.objects.create(name='Program 1')
        rrule3 = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=program,
            related_object_handler_name='handle_start_recurrence',
        )
        program.start_recurrence = rrule3
        program.save()

        # Run with a limit of 1, we should handle the no-op program
        with freeze_time(datetime.datetime(2022, 6, 1, 9)):
            RRule.objects.handle_overdue(related_model_handler_limit=1)

        # Make sure only the no-op program is handled
        no_op_program1.refresh_from_db()
        no_op_program2.refresh_from_db()
        program.refresh_from_db()
        self.assertEqual(no_op_program1.start_recurrence.time_last_handled, datetime.datetime(2022, 6, 1, 9))
        self.assertEqual(no_op_program2.start_recurrence.time_last_handled, None)
        self.assertEqual(program.start_recurrence.time_last_handled, None)

        # Run with a limit of 1 again , we should handle the no-op program2
        with freeze_time(datetime.datetime(2022, 6, 1, 9)):
            RRule.objects.handle_overdue(related_model_handler_limit=1)

        # Make sure only the no-op program is handled
        no_op_program1.refresh_from_db()
        no_op_program2.refresh_from_db()
        program.refresh_from_db()
        self.assertEqual(no_op_program1.start_recurrence.time_last_handled, datetime.datetime(2022, 6, 1, 9))
        self.assertEqual(no_op_program2.start_recurrence.time_last_handled, datetime.datetime(2022, 6, 1, 9))
        self.assertEqual(program.start_recurrence.time_last_handled, None)

        # Run with a limit of 1 again , we should handle the program
        with freeze_time(datetime.datetime(2022, 6, 1, 9)):
            RRule.objects.handle_overdue(related_model_handler_limit=1)

        # Make sure only the program is handled
        no_op_program1.refresh_from_db()
        no_op_program2.refresh_from_db()
        program.refresh_from_db()
        self.assertEqual(no_op_program1.start_recurrence.time_last_handled, datetime.datetime(2022, 6, 1, 9))
        self.assertEqual(no_op_program2.start_recurrence.time_last_handled, datetime.datetime(2022, 6, 1, 9))
        self.assertEqual(program.start_recurrence.time_last_handled, datetime.datetime(2022, 6, 1, 9))

    def test_related_object_handlers_invalid_handler(self):
        """
        Hits the else block when the handler path is not valid
        """
        program = Program.objects.create(name='Program 1')
        start_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 9),
                'byhour': 9,
            },
            related_object=program,
            related_object_handler_name='handle_start_recurrence_fake',
        )
        end_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2022, 6, 1, 17),
                'byhour': 17,
            },
            related_object=program,
            related_object_handler_name='handle_end_recurrence_fake',
        )
        program.start_recurrence = start_rrule
        program.end_recurrence = end_rrule
        program.save()

        # Make sure handlers are not called before date
        with freeze_time(datetime.datetime(2022, 7, 31)):
            RRule.objects.handle_overdue()

        # Occurrences should not be progressed
        program = Program.objects.get(id=program.id)
        self.assertEqual(program.start_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 9))
        self.assertEqual(program.end_recurrence.next_occurrence, datetime.datetime(2022, 6, 1, 17))

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

    def test_get_next_occurrence_dst(self):
        """
        What happens across DST changes?
        """

        # Create the params to create the rule
        params = {
            'freq': rrule.DAILY,
            'interval': 1,
            'dtstart': datetime.datetime(2022, 10, 29),
            'until': datetime.datetime(2022, 11, 1),
            'byhour': 10,
        }

        timezone = pytz.timezone('Europe/Kiev')
        format = '%Y-%m-%d %H:%M'

        # Create the rule
        rule = RRule.objects.create(
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler',
            time_zone=timezone,
        )

        # Assert the initial values
        # Europe/Kiev is UTC + 3 prior to 10/30/22. (10 Europe/Kiev meeting is 7 UTC.)
        self.assertEqual(rule.last_occurrence, None)
        self.assertEqual(rule.next_occurrence, datetime.datetime(2022, 10, 29, 7))
        self.assertEqual(
            fleming.convert_to_tz(rule.next_occurrence, timezone).strftime(format),
            '2022-10-29 10:00'
        )

        # Notice next occurrence jumps to UTC + 2 to reflect change from DST on early hours of 10/30.
        # Notice the converted date is still the expected 10am.
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2022, 10, 29, 7))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2022, 10, 30, 8))
        self.assertEqual(
            fleming.convert_to_tz(rule.next_occurrence, timezone).strftime(format),
            '2022-10-30 10:00'
        )

        # Notice UTC + 2 is here to stay.
        # Notice the converted date is still the expected 10am.
        rule.update_next_occurrence()
        self.assertEqual(rule.last_occurrence, datetime.datetime(2022, 10, 30, 8))
        self.assertEqual(rule.next_occurrence, datetime.datetime(2022, 10, 31, 8))
        self.assertEqual(
            fleming.convert_to_tz(rule.next_occurrence, timezone).strftime(format),
            '2022-10-31 10:00'
        )

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
        Assert generate_dates returns the same values as get_dates.
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

        self.assertEqual(
            rule.get_dates(),
            rule.generate_dates()
        )

    def test_get_dates(self):
        """
        Test a monthly 1st day of month rule to catch case of converting tz back using the get_dates method
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2016, 12, 31),
            'bymonthday': 1,
            'until': datetime.datetime(2017, 4, 30),
        }

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )
        next_dates = rule.get_dates()

        # Check a few dates
        self.assertEqual(len(next_dates), 4)

        self.assertEqual(next_dates[0], datetime.datetime(2017, 1, 1, 5))
        self.assertEqual(next_dates[1], datetime.datetime(2017, 2, 1, 5))
        self.assertEqual(next_dates[2], datetime.datetime(2017, 3, 1, 5))
        self.assertEqual(next_dates[3], datetime.datetime(2017, 4, 1, 4))  # DST change for US/Eastern

        # Run pre save again to make sure it doesn't mess up params
        rule.pre_save_hooks()

        # Get next dates to compare against
        more_next_dates = rule.get_dates()
        self.assertEqual(next_dates, more_next_dates)

    def test_get_dates_with_start_date(self):
        """
        Test a date generation with a start date.
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2016, 12, 31),
            'bymonthday': 1,
        }

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )
        next_dates = rule.get_dates(num_dates=10, start_date=datetime.datetime(2018, 1, 1))

        # Check a few dates
        self.assertEqual(len(next_dates), 10)
        self.assertEqual(next_dates[0], datetime.datetime(2018, 1, 1, 5))
        self.assertEqual(next_dates[1], datetime.datetime(2018, 2, 1, 5))
        self.assertEqual(next_dates[2], datetime.datetime(2018, 3, 1, 5))
        self.assertEqual(next_dates[3], datetime.datetime(2018, 4, 1, 4))  # DST change for US/Eastern
        self.assertEqual(next_dates[-1], datetime.datetime(2018, 10, 1, 4))

    def test_get_dates_num_dates_greater(self):
        """
        Test a date generation with a start date and end date that will yield fewer dates than num_dates.
        Daily from 1/1 to 1/10 is 10. Request default of 20 but only after 1/5 which should yield 6 dates, inclusive.
        """
        rule = RRule(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2017, 1, 1),
                'until': datetime.datetime(2017, 1, 10),
            },
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )
        next_dates = rule.get_dates(
            num_dates=20,
            start_date=datetime.datetime(2017, 1, 5)
        )

        self.assertEqual(len(next_dates), 6)
        self.assertEqual(next_dates[0], datetime.datetime(2017, 1, 5, 5))
        self.assertEqual(next_dates[1], datetime.datetime(2017, 1, 6, 5))
        self.assertEqual(next_dates[2], datetime.datetime(2017, 1, 7, 5))
        self.assertEqual(next_dates[3], datetime.datetime(2017, 1, 8, 5))
        self.assertEqual(next_dates[4], datetime.datetime(2017, 1, 9, 5))
        self.assertEqual(next_dates[5], datetime.datetime(2017, 1, 10, 5))

    def test_generate_dates_from_params(self):
        """
        Assert generate_dates_from_params returns the same values as get_dates_from_params.
        """
        params = {
            'rrule_params': {
                'freq': rrule.MONTHLY,
                'interval': 1,
                'dtstart': datetime.datetime(2017, 1, 1, 22),
                'bymonthday': -1,
                'until': datetime.datetime(2017, 5, 1, 22),
            },
            'time_zone': pytz.timezone('US/Eastern'),
            'num_dates': 3,
        }

        self.assertEqual(
            RRule.get_dates_from_params(**params),
            RRule.generate_dates_from_params(**params)
        )

    def test_get_dates_from_params(self):
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
        next_dates = rule.get_dates(
            num_dates=3,
            start_date=datetime.datetime(2017, 2, 2, 22)
        )

        next_dates_from_params = RRule.get_dates_from_params(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            num_dates=3,
            start_date=datetime.datetime(2017, 2, 2, 22)
        )

        self.assertEqual(next_dates, next_dates_from_params)

    def test_model_different_time_zone_end_of_month_get_dates(self):
        """
        Test a monthly first day of month rule to catch case of converting tz back using the get_dates method
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
        next_dates = rule.get_dates()
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

    def test_refresh_next_occurrence(self):
        """
        Checks that the next occurrence is set relative to the passed occurrence (or last occurrence if null)
        Also verifies that a null next occurrence does not raise an exception, but sets the next to null
        """
        params = {
            'freq': rrule.DAILY,
            'dtstart': datetime.datetime(2022, 2, 15),
            'until': datetime.datetime(2022, 2, 17),
        }

        with freeze_time('2-14-2022'):
            rule = RRule.objects.create(
                rrule_params=params,
                occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
            )
            self.assertEqual(rule.last_occurrence, None)
            self.assertEqual(rule.next_occurrence, datetime.datetime(2022, 2, 15))

        with freeze_time('2-15-2022'):
            rule.refresh_next_occurrence()
            self.assertEqual(rule.last_occurrence, None)
            self.assertEqual(rule.next_occurrence, datetime.datetime(2022, 2, 16))

        with freeze_time('2-16-2022'):
            rule.refresh_next_occurrence()
            self.assertEqual(rule.last_occurrence, None)
            self.assertEqual(rule.next_occurrence, datetime.datetime(2022, 2, 17))

        with freeze_time('2-17-2022'):
            rule.refresh_next_occurrence()
            self.assertEqual(rule.last_occurrence, None)
            self.assertEqual(rule.next_occurrence, None)

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

    @freeze_time('6-15-2022')
    def test_clone(self):
        # New object that starts next Wednesday
        # Weekly on MWF
        rule = RRule.objects.create(
            rrule_params={
                'freq': rrule.WEEKLY,
                'dtstart': datetime.datetime(2022, 6, 22),
                'byweekday': [0, 2, 4],
            },
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        # Create a clone of the object.
        clone = RRule.clone(rule)

        # Assert that the clone's next occurrence is the same.
        format = '%Y-%m-%d'
        self.assertEqual(rule.next_occurrence.strftime(format), clone.next_occurrence.strftime(format))

        # Assert that the clone's params are the same
        self.assertEqual(rule.rrule_params, clone.rrule_params)

        # Assert the generated dates are equal.
        self.assertEqual(rule.get_dates(num_dates=4), clone.get_dates(num_dates=4))

    @freeze_time('6-15-2022')
    def test_weekly_clone_with_offset(self):
        # New object that starts next Wednesday
        # Weekly on MWF
        rule = RRule.objects.create(
            rrule_params={
                'freq': rrule.WEEKLY,
                'dtstart': datetime.datetime(2022, 6, 21),  # Tuesday
                'byweekday': [0, 2, 4],
            },
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler'
        )

        # Create a clones of the object with a start date of 2 days into the future and 2 days into the past.
        future_clone = rule.clone_with_day_offset(2)
        past_clone = rule.clone_with_day_offset(-2)

        # Assert that the rule created here is unchanged but the clones reflect their offsets.
        format = '%Y-%m-%d'
        self.assertEqual(rule.next_occurrence.strftime(format), '2022-06-22')
        self.assertEqual(future_clone.next_occurrence.strftime(format), '2022-06-24')
        self.assertEqual(past_clone.next_occurrence.strftime(format), '2022-06-20')

        # Assert that the rule and clones all reflect MWF
        self.assertEqual(rule.rrule_params['byweekday'], [0, 2, 4])
        self.assertEqual(future_clone.rrule_params['byweekday'], [0, 2, 4])
        self.assertEqual(past_clone.rrule_params['byweekday'], [0, 2, 4])

        # Assert the generated dates are as expected.
        self.assertEqual(
            rule.get_dates(num_dates=4),
            [
                datetime.datetime(2022, 6, 22),  # Wednesday
                datetime.datetime(2022, 6, 24),  # Friday
                datetime.datetime(2022, 6, 27),  # Monday
                datetime.datetime(2022, 6, 29),  # Wednesday
            ]
        )

        # Two days after each date in the regular series.
        self.assertEqual(
            future_clone.get_dates(num_dates=4),
            [
                datetime.datetime(2022, 6, 24),  # Friday
                datetime.datetime(2022, 6, 26),  # Sunday
                datetime.datetime(2022, 6, 29),  # Wednesday
                datetime.datetime(2022, 7, 1),   # Friday
            ]
        )

        # Two days before each date in the regular series.
        self.assertEqual(
            past_clone.get_dates(num_dates=4),
            [
                datetime.datetime(2022, 6, 20),  # Monday
                datetime.datetime(2022, 6, 22),  # Wednesday
                datetime.datetime(2022, 6, 25),  # Saturday
                datetime.datetime(2022, 6, 27),  # Monday
            ]
        )

    @freeze_time('6-1-2022')
    def test_monthly_clone_with_offset(self):
        """
        Assert than an object with bynweekday data can be cloned with an offset.
        """

        # Second Monday from end of month every other month
        # Starts today, 6/1. First occurrence is 6/20. (Last Monday is 27th.)
        data = {
            'freq': rrule.MONTHLY,
            'interval': 2,
            'dtstart': '6/1/2022',
            'byhour': '0',
            'time_zone': 'UTC',
            'ends': RecurrenceEnds.NEVER,
            'repeat_by': 'DAY_OF_THE_WEEK_END',
            'bynweekday': '[[0, -2]]'
        }

        # Form is used to flex the bynweeday to byweekday + bysetpos conversion that occurs in its save().
        form = RecurrenceForm(data=data)
        self.assertTrue(form.is_valid())
        rule = form.save()

        # Create a clones of the object with a start date of 2 days into the future and 2 days into the past.
        future_clone = rule.clone_with_day_offset(2)
        past_clone = rule.clone_with_day_offset(-2)

        # Assert that the rule created here is unchanged but the clones reflect their offsets.
        format = '%Y-%m-%d'
        self.assertEqual(rule.next_occurrence.strftime(format), '2022-06-20')
        self.assertEqual(future_clone.next_occurrence.strftime(format), '2022-06-22')
        self.assertEqual(past_clone.next_occurrence.strftime(format), '2022-06-18')

    @freeze_time('6-15-2022')
    def test_clone_with_day_offset_with_finish_date(self):
        """
        Assert that the 'until' param is offset correctly
        """

        rule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'dtstart': datetime.datetime(2022, 10, 15),
                'until': datetime.datetime(2022, 10, 17)
            }
        )

        future_clone = rule.clone_with_day_offset(1)
        past_clone = rule.clone_with_day_offset(-1)

        # Assert the cloned until values are the same
        self.assertEqual(
            parser.parse(rule.rrule_params['until']),
            parser.parse(future_clone.rrule_params['until'])
        )
        self.assertEqual(
            parser.parse(rule.rrule_params['until']),
            parser.parse(past_clone.rrule_params['until'])
        )

        # Assert the generated dates are as expected for the original.
        self.assertEqual(
            rule.get_dates(),
            [
                datetime.datetime(2022, 10, 15),
                datetime.datetime(2022, 10, 16),
                datetime.datetime(2022, 10, 17)
            ]
        )

        # One day after each date in the regular series.
        self.assertEqual(
            future_clone.get_dates(),
            [
                datetime.datetime(2022, 10, 16),
                datetime.datetime(2022, 10, 17),
                datetime.datetime(2022, 10, 18)
            ]
        )

        # One day before each date in the regular series.
        self.assertEqual(
            past_clone.get_dates(),
            [
                datetime.datetime(2022, 10, 14),
                datetime.datetime(2022, 10, 15),
                datetime.datetime(2022, 10, 16)
            ]
        )

    @freeze_time('10-31-2022')
    def test_clone_with_future_days_across_dst(self):
        """
        Assert that the resulting recurrence next occurrence reflects *its* timezone offset.
        Fall Back.
        """

        rule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'dtstart': datetime.datetime(2022, 10, 29, 10),
                'until': datetime.datetime(2022, 11, 1, 10),
            },
            time_zone=pytz.timezone('Europe/Kiev')
        )

        # Europe/Kiev goes from UTC+3 to UTC+2 in the early hours of 10/30.
        self.assertEqual(
            rule.get_dates(),
            [
                datetime.datetime(2022, 10, 29, 7),
                datetime.datetime(2022, 10, 30, 8),
                datetime.datetime(2022, 10, 31, 8),
                datetime.datetime(2022, 11, 1, 8),
            ]
        )

        # Europe/Kiev goes to standard time (UTC+2) in the early hours of 1/30.
        # This offset should result in a datetime (UTC+3).
        past_clone = rule.clone_with_day_offset(-1)

        # One day before each date in the regular series.
        self.assertEqual(
            past_clone.get_dates(),
            [
                datetime.datetime(2022, 10, 28, 7),
                datetime.datetime(2022, 10, 29, 7),
                datetime.datetime(2022, 10, 30, 8),
                datetime.datetime(2022, 10, 31, 8),
            ]
        )

    @freeze_time('10-31-2022')
    def test_clone_with_offset_from_dst(self):
        """
        Assert that a clone, with a negative offset results in dates that respect a DST transition.
        Europe/Kiev goes from UTC+3 to UTC+2 in the early hours of 10/30.
        Fall back.
        """

        # Starting in standard time
        rule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'dtstart': datetime.datetime(2022, 10, 31, 10),
                'until': datetime.datetime(2022, 11, 3, 10),
            },
            time_zone=pytz.timezone('Europe/Kiev'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne',
        )

        # Times are UTC+2 because it is after the 10/30 transition.
        self.assertEqual(
            rule.generate_dates(),
            [
                datetime.datetime(2022, 10, 31, 8),
                datetime.datetime(2022, 11, 1, 8),
                datetime.datetime(2022, 11, 2, 8),
                datetime.datetime(2022, 11, 3, 8),
            ]
        )

        # Clone prior to the DST switch and ensure the times transition between 10/30 & 10/31.
        past_clone = rule.clone_with_day_offset(-3)
        expected_clone_dates = [
            datetime.datetime(2022, 10, 28, 7),
            datetime.datetime(2022, 10, 29, 7),
            datetime.datetime(2022, 10, 30, 8),
            datetime.datetime(2022, 10, 31, 8),
        ]
        self.assertEqual(past_clone.generate_dates(), expected_clone_dates)

        # Progress through dates and assert generated next_occurrence matches get_dates()
        for x, expected_date in enumerate(expected_clone_dates):
            with freeze_time(expected_date):
                RRule.objects.handle_overdue()
                past_clone.refresh_from_db()
                if x < len(expected_clone_dates) - 1:
                    self.assertEqual(
                        past_clone.next_occurrence,
                        expected_clone_dates[x + 1],
                    )

    @freeze_time('10-31-2022')
    def test_clone_with_offset_to_dst(self):
        """
        Assert that a clone, with a negative offset results in dates that respect a DST transition.
        Europe/Kiev goes from UTC+2 to UTC+3 in the early hours of 3/27.
        Spring forward.
        """

        # Starting in standard time
        rule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'dtstart': datetime.datetime(2022, 3, 28, 10),
                'until': datetime.datetime(2022, 3, 31, 10),
            },
            time_zone=pytz.timezone('Europe/Kiev'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne',
        )

        # Times are UTC+2 because it is after the 3/27 transition.
        self.assertEqual(
            rule.generate_dates(),
            [
                datetime.datetime(2022, 3, 28, 7),
                datetime.datetime(2022, 3, 29, 7),
                datetime.datetime(2022, 3, 30, 7),
                datetime.datetime(2022, 3, 31, 7),
            ]
        )

        # Clone prior to the DST switch and ensure the times transition between 3/26 & 3/27.
        past_clone = rule.clone_with_day_offset(-3)
        expected_clone_dates = [
            datetime.datetime(2022, 3, 25, 8),
            datetime.datetime(2022, 3, 26, 8),
            datetime.datetime(2022, 3, 27, 7),
            datetime.datetime(2022, 3, 28, 7),
        ]
        self.assertEqual(past_clone.generate_dates(), expected_clone_dates)

        # Progress through dates and assert generated next_occurrence matches get_dates()
        for x, expected_date in enumerate(expected_clone_dates):
            with freeze_time(expected_date):
                RRule.objects.handle_overdue()
                past_clone.refresh_from_db()
                if x < len(expected_clone_dates) - 1:
                    self.assertEqual(
                        past_clone.next_occurrence,
                        expected_clone_dates[x + 1],
                    )

    def test_offset(self):
        """
        Assert the offset method adjusts a given date by the given number of days
        """
        self.assertEqual(
            RRule(day_offset=1).offset(datetime.datetime(2023, 1, 1)),
            datetime.datetime(2023, 1, 2)
        )

        self.assertEqual(
            RRule(day_offset=-1).offset(datetime.datetime(2023, 1, 1)),
            datetime.datetime(2022, 12, 31)
        )

        self.assertEqual(
            RRule().offset(datetime.datetime(2023, 1, 1)),
            datetime.datetime(2023, 1, 1)
        )

    def test_day_offset(self):
        """
        Assert that the field, day_offset, adjusts all generated dates.
        """
        params = {
            'freq': rrule.MONTHLY,
            'interval': 1,
            'dtstart': datetime.datetime(2016, 12, 31),
            'bymonthday': 1,
            'until': datetime.datetime(2017, 4, 30),
        }

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler',
            day_offset=1,
        )
        next_dates = rule.get_dates()

        # Check a few dates
        self.assertEqual(len(next_dates), 4)

        self.assertEqual(next_dates[0], datetime.datetime(2017, 1, 2, 5))
        self.assertEqual(next_dates[1], datetime.datetime(2017, 2, 2, 5))
        self.assertEqual(next_dates[2], datetime.datetime(2017, 3, 2, 5))
        self.assertEqual(next_dates[3], datetime.datetime(2017, 4, 2, 4))  # DST change for US/Eastern

        # Run pre save again to make sure it doesn't mess up params
        rule.pre_save_hooks()

        # Get next dates to compare against
        more_next_dates = rule.get_dates()
        self.assertEqual(next_dates, more_next_dates)

        rule = RRule(
            rrule_params=params,
            time_zone=pytz.timezone('US/Eastern'),
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.MockHandler',
            day_offset=-1,
        )

        next_dates = rule.get_dates()

        # Check a few dates
        self.assertEqual(len(next_dates), 4)

        self.assertEqual(next_dates[0], datetime.datetime(2016, 12, 31, 5))
        self.assertEqual(next_dates[1], datetime.datetime(2017, 1, 31, 5))
        self.assertEqual(next_dates[2], datetime.datetime(2017, 2, 28, 5))
        self.assertEqual(next_dates[3], datetime.datetime(2017, 3, 31, 4))  # DST change for US/Eastern

        # Run pre save again to make sure it doesn't mess up params
        rule.pre_save_hooks()

        # Get next dates to compare against
        more_next_dates = rule.get_dates()
        self.assertEqual(next_dates, more_next_dates)

    def test_next_occurrences_day_offset(self):
        """
        Make sure that the correct occurrences are selected when a day offset is configured.
        """
        params = {
            'freq': rrule.WEEKLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }

        rrule1 = G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne',
            day_offset=1
        )

        params = {
            'freq': rrule.WEEKLY,
            'interval': 1,
            'dtstart': datetime.datetime(2017, 1, 2),
        }

        rrule2 = G(
            RRule,
            rrule_params=params,
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerTwo',
            day_offset=-1
        )

        self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 3))
        self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 1))

        with freeze_time('1-3-2017'):
            RRule.objects.handle_overdue()

            rrule1.refresh_from_db()
            rrule2.refresh_from_db()

            # Both should be progressed
            self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 10))
            self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 8))

        with freeze_time('1-8-2017'):
            RRule.objects.handle_overdue()

            rrule1.refresh_from_db()
            rrule2.refresh_from_db()

            # Both should be progressed
            self.assertEqual(rrule1.next_occurrence, datetime.datetime(2017, 1, 10))
            self.assertEqual(rrule2.next_occurrence, datetime.datetime(2017, 1, 15))

    def test_next_occurrence_clone_with_offset(self):
        """
        Cloning an established object with an offset should yield a next_occurrence of the object's with the offset.
        """
        # A daily recurrence with a multi-day offset to highlight differences clearly.
        rrule1 = G(
            RRule,
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2023, 1, 1),
            },
            occurrence_handler_path='ambition_utils.rrule.tests.model_tests.HandlerOne',
        )

        # Many days into the future
        with freeze_time('1-10-2023'):
            # Catch the recurrence object up.
            while rrule1.next_occurrence <= datetime.datetime.now():
                RRule.objects.handle_overdue()
                rrule1.refresh_from_db()
            self.assertEqual(rrule1.next_occurrence, datetime.datetime(2023, 1, 11))

            # Create a clone with an offset and assert that the clone's next occurrence is 1/11 -5 = 1/6.
            rrule2 = rrule1.clone_with_day_offset(day_offset=-5)
            self.assertEqual(rrule2.next_occurrence, datetime.datetime(2023, 1, 6))

            # First object is unchanged
            rrule1.refresh_from_db()
            self.assertEqual(rrule1.next_occurrence, datetime.datetime(2023, 1, 11))


class RRuleWithExclusionTest(TestCase):
    def test_exclusion(self):
        weekly_program = Program.objects.create(name='Weekly Program')
        weekly_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.DAILY,
                'interval': 1,
                'dtstart': datetime.datetime(2023, 6, 1),
                'byweekday': 0,
            },
            rrule_exclusion_params={
                'freq': rrule.MONTHLY,
                'interval': 1,
                'dtstart': datetime.datetime(2023, 6, 1),
                'bysetpos': 2,
                'byweekday': 0
            },
            related_object=weekly_program,
            related_object_handler_name='handle_start_recurrence',
        )
        monthly_program = Program.objects.create(name='Monthly Program')
        monthly_rrule = RRule.objects.create(
            rrule_params={
                'freq': rrule.MONTHLY,
                'interval': 1,
                'dtstart': datetime.datetime(2023, 6, 1),
                'bysetpos': 2,
                'byweekday': 0
            },
            related_object=monthly_program,
            related_object_handler_name='handle_start_recurrence',
        )

        weekly_dates = weekly_rrule.get_dates(num_dates=10)
        monthly_dates = monthly_rrule.get_dates(num_dates=10)
        self.assertEqual(
            weekly_dates,
            [datetime.datetime(2023, 6, 5, 0, 0), datetime.datetime(2023, 6, 19, 0, 0),
             datetime.datetime(2023, 6, 26, 0, 0), datetime.datetime(2023, 7, 3, 0, 0),
             datetime.datetime(2023, 7, 17, 0, 0), datetime.datetime(2023, 7, 24, 0, 0),
             datetime.datetime(2023, 7, 31, 0, 0), datetime.datetime(2023, 8, 7, 0, 0),
             datetime.datetime(2023, 8, 21, 0, 0), datetime.datetime(2023, 8, 28, 0, 0)]
        )
        self.assertEqual(
            monthly_dates,
            [datetime.datetime(2023, 6, 12, 0, 0), datetime.datetime(2023, 7, 10, 0, 0),
             datetime.datetime(2023, 8, 14, 0, 0), datetime.datetime(2023, 9, 11, 0, 0),
             datetime.datetime(2023, 10, 9, 0, 0), datetime.datetime(2023, 11, 13, 0, 0),
             datetime.datetime(2023, 12, 11, 0, 0), datetime.datetime(2024, 1, 8, 0, 0),
             datetime.datetime(2024, 2, 12, 0, 0), datetime.datetime(2024, 3, 11, 0, 0)]
        )
