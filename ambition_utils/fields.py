import pytz
from timezone_field.fields import TimeZoneField as BaseTimeZoneField


class CastOnAssignDescriptor:
    """
    A property descriptor which ensures that `field.to_python()` is called on _every_ assignment to the field.
    This used to be provided by the `django.db.models.subclassing.Creator` class, which in turn
    was used by the deprecated-in-Django-1.10 `SubfieldBase` class, hence the reimplementation here.
    Copied from https://stackoverflow.com/questions/
    39392343/how-do-i-make-a-custom-model-field-call-to-python-when-the-field-is-accessed-imm
    """

    def __init__(self, field):
        self.field = field

    def __get__(self, obj, type=None):
        if obj is None:  # pragma: no cover
            return self
        return obj.__dict__[self.field.name]

    def __set__(self, obj, value):
        obj.__dict__[self.field.name] = self.field.to_python(value)


class CastOnAssignFieldMixin:
    """
    Makes use of CastOnAssignDescriptor which will cast the field to its expected data type upon each assignment
    rather than only being cast when fetched from the db. This is the old behavior in django and is meant to be
    used for backwards compatibility for application that still expect this behavior.
    """

    def contribute_to_class(self, cls, name, virtual_only=False):
        """
        Cast to the correct value every
        """
        super().contribute_to_class(cls, name, virtual_only)
        setattr(cls, name, CastOnAssignDescriptor(self))


class TimeZoneField(CastOnAssignFieldMixin, BaseTimeZoneField):

    @classmethod
    def get_all_choices(cls):
        """
        Gets all timezones to use in a forms.ChoiceField for form validation
        """
        return [
            (tz, tz)
            for tz in pytz.all_timezones
        ]

    @classmethod
    def get_common_choices(cls):
        """
        Gets common timezones to use in a forms.ChoiceField for form validation
        """
        return [
            (tz, tz)
            for tz in pytz.common_timezones
        ]
