import pytz
from django.test import TestCase

from ambition_utils.fields import TimeZoneField
from ambition_utils.tests.models import FakeModel


class TimeZoneFieldTest(TestCase):
    """
    Verifies the time zone field is cast when being assigned
    """

    def test_cast_on_assign(self):
        """

        """
        instance = FakeModel()
        instance.cast_time_zone_field = 'US/Eastern'

        # Verify the timezone was cast
        self.assertEqual(instance.cast_time_zone_field, pytz.timezone('US/Eastern'))

        # Save and verify it is still the same
        instance.save()
        self.assertEqual(instance.cast_time_zone_field, pytz.timezone('US/Eastern'))

        # Load from db and verify again
        instance.refresh_from_db()
        self.assertEqual(instance.cast_time_zone_field, pytz.timezone('US/Eastern'))

    def test_no_cast_on_assign(self):
        """
        Verifies the base time zone field is not cast when being assigned
        """
        instance = FakeModel()
        instance.no_cast_time_zone_field = 'US/Eastern'

        # Verify the timezone is a string
        self.assertEqual(instance.no_cast_time_zone_field, 'US/Eastern')

        # Save and verify it is still a string
        instance.save()
        self.assertEqual(instance.no_cast_time_zone_field, 'US/Eastern')

        # Load from db and verify it is now cast as a time zone
        instance.refresh_from_db()
        self.assertEqual(instance.no_cast_time_zone_field, pytz.timezone('US/Eastern'))

    def test_all_time_zones_choices(self):
        """
        Verifies that all time zones are available in a method for usage in form choices
        """
        # Obtain a timezone that is in pytz.all_timezones, but not in pytz.common_timezones
        timezones = set(pytz.all_timezones) - set(pytz.common_timezones)
        timezone = timezones.pop()

        choices = {
            choice[0]
            for choice in TimeZoneField.get_all_choices()
        }

        self.assertTrue(timezone in choices)

    def test_common_time_zones_choices(self):
        """
        Verifies that all time zones are available in a method for usage in form choices
        """
        # Obtain a timezone that is in pytz.all_timezones, but not in pytz.common_timezones
        timezones = set(pytz.all_timezones) - set(pytz.common_timezones)
        timezone = timezones.pop()

        choices = {
            choice[0]
            for choice in TimeZoneField.get_common_choices()
        }
        self.assertTrue(timezone not in choices)
