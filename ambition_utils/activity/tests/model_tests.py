from django.test import TestCase

from ambition_utils.activity.models import ActivityGroup


class ActivityGroupTest(TestCase):

    def test_str(self):
        self.assertEqual(str(ActivityGroup(name='test name')), 'test name')
