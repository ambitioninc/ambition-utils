from celery import Celery
from django.test import TestCase
from mock import patch
from uuid import uuid4

from ambition_utils.activity.tasks import ActivityManagedTaskMixin, track_activity
from ambition_utils.activity.models import Activity, ActivityGroup, ActivityStatus, ActivityGroupStatus

test_application = Celery('task_tests')


class TestTask(ActivityManagedTaskMixin, test_application.Task):

    def run(self):
        self.first()
        self.second()
        self.third()
        self.fourth()
        self.fifth()

    @track_activity
    def first(self):
        pass

    @track_activity
    def second(self):
        pass

    @track_activity
    def third(self):
        pass

    @track_activity
    def fourth(self):
        pass

    def fifth(self):
        pass


class ActivityManagedTaskMixinTest(TestCase):

    def test_activity_tracking(self):
        TestTask(uuid=uuid4()).run()
        self.assertEqual(4, Activity.objects.count())
        successful_activities = Activity.objects.filter(status=ActivityStatus.SUCCESS.value)
        self.assertEqual(4, successful_activities.count())

        # ensure that there is only one activity gruop
        activity_group = ActivityGroup.objects.get()
        # ensure that the group is marked as successful
        self.assertEqual(ActivityGroupStatus.SUCCESS.value, activity_group.status)
        self.assertEqual('TestTask', activity_group.name)

    @patch.object(TestTask, 'second')
    def test_failed_activity(self, mock_second_activity):
        # make the second activity fail
        mock_second_activity.side_effect = Exception('wat')
        mock_second_activity.__name__ = 'foo'
        task = TestTask(uuid=uuid4())
        with self.assertRaises(Exception):
            task.run()
        self.assertEqual(1, Activity.objects.filter(status=ActivityStatus.SUCCESS.value).count())
        self.assertEqual(1, Activity.objects.filter(status=ActivityStatus.FAILURE.value).count())
        self.assertEqual(2, Activity.objects.filter(status=ActivityStatus.PENDING.value).count())

        # ensure that there is only one activity gruop
        activity_group = ActivityGroup.objects.get()
        # ensure that the group is marked as successful
        self.assertEqual(ActivityGroupStatus.FAILURE.value, activity_group.status)
        self.assertEqual('wat', activity_group.error_message)

    def test_activity_group_name(self):
        self.assertEqual(
            ActivityManagedTaskMixin().get_activity_group_name(),
            'ActivityManagedTaskMixin'
        )

        class TestTask(ActivityManagedTaskMixin):
            def get_activity_group_name(self):
                return 'test name'
        mixin = TestTask()
        self.assertEqual(mixin.get_activity_group_name(), 'test name')
