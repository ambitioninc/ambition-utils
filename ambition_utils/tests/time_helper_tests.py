from django.test import TestCase
from freezegun import freeze_time

from ambition_utils.time_helpers import get_time_zones


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
