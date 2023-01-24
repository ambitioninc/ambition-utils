from django.db import models
from timezone_field.fields import TimeZoneField as BaseTimeZoneField

from ambition_utils.fields import TimeZoneField


class FakeModel(models.Model):
    name = models.CharField(max_length=50)
    cast_time_zone_field = TimeZoneField(default='utc', null=True)
    no_cast_time_zone_field = BaseTimeZoneField(default='utc', null=True)
