from __future__ import annotations
from datetime import datetime, timedelta
from dateutil import parser
from dateutil.rrule import rrule
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from django.utils.module_loading import import_string
from fleming import fleming
from manager_utils import bulk_update
from timezone_field import TimeZoneField
import copy
import pytz


class RRuleManager(models.Manager):
    """
    Custom manager for rrule objects
    """
    def update_next_occurrences(self, rrule_objects=None):
        if rrule_objects is None:
            return
        for rrule_object in rrule_objects:
            rrule_object.update_next_occurrence(save=False)

        bulk_update(self, rrule_objects, ['last_occurrence', 'next_occurrence'])

        return rrule_objects

    @transaction.atomic
    def handle_overdue(self, **kwargs):
        """
        Handles any overdue rrules
        :param kwargs: the old optional kwarg filters for specifying additional occurrence handler filters
        """
        self.process_occurrence_handler_paths(**kwargs)
        self.process_related_model_handlers()

    def process_occurrence_handler_paths(self, **kwargs):
        """
        This is the old style of processing overdue rrules
        """
        # Get instances of all overdue recurrence handler classes
        instances = self.overdue_handler_class_instances(**kwargs)

        # Build a list of rrules that get returned from the handler
        rrules = []
        for instance in instances:
            rrules.extend(instance.handle())

        # Bulk update the next occurrences
        RRule.objects.update_next_occurrences(rrule_objects=rrules)

    def process_related_model_handlers(self):
        # Get the rrule objects that are overdue and need to be handled
        rrule_objects = self.get_queryset().filter(
            next_occurrence__lte=datetime.utcnow(),
            related_object_handler_name__isnull=False,
            related_object_id__isnull=False,
        ).prefetch_related('related_object')

        rrules_to_advance = []
        for rrule_object in rrule_objects:
            if hasattr(rrule_object.related_object, rrule_object.related_object_handler_name):
                rrules_to_advance.append(
                    getattr(rrule_object.related_object, rrule_object.related_object_handler_name)(rrule_object)
                )

        rrules_to_advance = [rrule_to_advance for rrule_to_advance in rrules_to_advance if rrule_to_advance]

        # Bulk update the next occurrences
        rrules_to_advance = RRule.objects.update_next_occurrences(rrule_objects=rrules_to_advance)

        return rrules_to_advance

    def overdue_handler_class_instances(self, **kwargs):
        """
        Returns a set of instances for any handler with an old next_occurrence
        """

        # Get the rrule objects that are overdue and need to be handled
        rrule_objects = self.get_queryset().filter(
            next_occurrence__lte=datetime.utcnow(),
            **kwargs
        ).distinct(
            'occurrence_handler_path'
        )

        # Return instances of the handler classes
        handler_classes = [
            rrule_object.get_occurrence_handler_class_instance()
            for rrule_object in rrule_objects
        ]
        handler_classes = [handler_class for handler_class in handler_classes if handler_class]
        return handler_classes


class RRule(models.Model):
    """
    Model that will hold rrule details and generate recurrences to be handled by the supplied handler
    """

    # Params used to generate the rrule
    rrule_params = JSONField()

    # Any meta data associated with the object that created this rule
    meta_data = JSONField(default=dict)

    # The timezone all dates should be converted to
    time_zone = TimeZoneField(default='UTC')

    # The last occurrence date that was handled
    last_occurrence = models.DateTimeField(null=True, default=None)

    # The next occurrence date that should be handled
    next_occurrence = models.DateTimeField(null=True, default=None)

    # A python path to the handler class used to handle when a recurrence occurs for this rrule
    # The configuration class must extend ambition_utils.rrule.handler.OccurrenceHandler
    occurrence_handler_path = models.CharField(max_length=500, blank=False, null=False)

    # Generic relation back to object to explicitly call expiration methods
    related_object_id = models.IntegerField(null=True, db_index=True)
    related_object_content_type = models.ForeignKey(ContentType, null=True, on_delete=models.PROTECT)
    related_object = GenericForeignKey('related_object_content_type', 'related_object_id')

    # The name of the method to call on the related_object when the recurrence has expired
    related_object_handler_name = models.TextField(default=None, null=True, blank=True)

    # Custom object manager
    objects = RRuleManager()

    def get_time_zone_object(self):
        if self.time_zone is None:
            return pytz.utc

        # There is a test for this but it still doesn't hit this block
        if isinstance(self.time_zone, str):  # pragma: no cover
            return pytz.timezone(self.time_zone)

        return self.time_zone

    def get_occurrence_handler_class_instance(self):
        """
        Gets an instance of the occurrence handler class associated with this rrule
        :rtype: ambition_utils.rrule.handler.OccurrenceHandler
        :return: The instance
        """
        try:
            handler_class = import_string(self.occurrence_handler_path)()
            return handler_class
        except:
            return None

    def get_rrule(self):
        """
        Builds the rrule object by restoring all the params.
        The dtstart param will be converted to local time if it is set.
        :rtype: rrule
        """
        params = copy.deepcopy(self.rrule_params)

        # Convert next scheduled from utc back to time zone
        if params.get('dtstart') and not hasattr(params.get('dtstart'), 'date'):
            params['dtstart'] = parser.parse(params['dtstart'])

        # Convert until date from utc back to time zone
        if params.get('until') and not hasattr(params.get('until'), 'date'):
            params['until'] = parser.parse(params['until'])

        # Always cache
        params['cache'] = True

        # Return the rrule
        return rrule(**params)

    def get_next_occurrence(self, last_occurrence=None, force=False):
        """
        Builds the rrule and returns the next date in the series or None of it is the end of the series
        :param last_occurrence: The last occurrence that was generated
        :param force: If the next occurrence is none, force the rrule to generate another
        :rtype: rrule or None
        """
        # Get the last occurrence
        last_occurrence = last_occurrence or self.last_occurrence or datetime.utcnow()

        # Get the rule
        rule = self.get_rrule()

        # Convert to local time zone for getting next occurrence, otherwise time zones ahead of utc will return the same
        last_occurrence = fleming.convert_to_tz(last_occurrence, self.get_time_zone_object(), return_naive=True)

        # Generate the next occurrence
        next_occurrence = rule.after(last_occurrence)

        # If next occurrence is none and force is true, force the rrule to generate another date
        if next_occurrence is None and force:
            # Keep a reference to the original rrule_params
            original_rrule_params = {}
            original_rrule_params.update(self.rrule_params)

            # Remove any limiting params
            self.rrule_params.pop('count', None)
            self.rrule_params.pop('until', None)

            # Refetch the rule
            rule = self.get_rrule()

            # Generate the next occurrence
            next_occurrence = rule.after(last_occurrence)

            # Restore the rrule params
            self.rrule_params = original_rrule_params

        # If there is a next occurrence, convert to utc
        if next_occurrence:
            next_occurrence = self.convert_to_utc(next_occurrence)

        # Return the next occurrence
        return next_occurrence

    def update_next_occurrence(self, save=True):
        """
        Sets the next_occurrence property to the next time in the series and sets the last_occurrence property
        to the previous value of next_occurrence. If the save option is True, the model will be saved. The
        save flag is typically set to False when wanting to bulk update records after updating the values
        of many models.
        :param save: Flag to save the model after updating the schedule.
        :type save: bool
        """
        if not self.next_occurrence:
            return None

        # Only handle if the current date is >= next occurrence
        if datetime.utcnow() < self.next_occurrence:
            return False

        self.last_occurrence = self.next_occurrence
        self.next_occurrence = self.get_next_occurrence(self.last_occurrence)

        # Only save if the flag is true
        if save:
            self.save(update_fields=['last_occurrence', 'next_occurrence'])

    def convert_to_utc(self, dt):
        """
        Treats the datetime object as being in the timezone of self.timezone and then converts it to utc timezone.
        :type dt: datetime
        """
        # Add timezone info
        dt = fleming.attach_tz_if_none(dt, self.get_time_zone_object())

        # Convert to utc
        dt = fleming.convert_to_tz(dt, pytz.utc, return_naive=True)

        return dt

    def refresh_next_occurrence(self, current_time=None):
        """
        Sets the next occurrence date based on the current rrule param definition. The date will be after the
        specified current_time or utcnow.
        :param current_time: Optional datetime object to compute the next time from
        """
        # Get the current time or go off the specified current time
        current_time = current_time or datetime.utcnow()

        # Next occurrence is in utc here
        next_occurrence = self.get_next_occurrence(last_occurrence=current_time)

        if next_occurrence:
            # Only set if the new time is still greater than now
            if next_occurrence > datetime.utcnow():
                self.next_occurrence = next_occurrence
        else:
            self.next_occurrence = next_occurrence

    def pre_save_hooks(self):
        self.set_date_objects()

    def set_date_objects(self):
        # Check if this is a new rrule object
        if self.pk is None:
            # Convert next scheduled from utc back to time zone
            if self.rrule_params.get('dtstart') and not hasattr(self.rrule_params.get('dtstart'), 'date'):
                self.rrule_params['dtstart'] = parser.parse(self.rrule_params['dtstart'])

            # Convert until date from utc back to time zone
            if self.rrule_params.get('until') and not hasattr(self.rrule_params.get('until'), 'date'):
                self.rrule_params['until'] = parser.parse(self.rrule_params['until'])

            # Get the first scheduled time according to the rrule (this converts from utc back to local time)
            self.next_occurrence = self.get_rrule()[0]

            # Convert back to utc before saving
            self.next_occurrence = self.convert_to_utc(self.next_occurrence)

        # Serialize the datetime objects if they exist
        if self.rrule_params.get('dtstart') and hasattr(self.rrule_params.get('dtstart'), 'date'):
            self.rrule_params['dtstart'] = self.rrule_params['dtstart'].strftime('%Y-%m-%d %H:%M:%S')

        if self.rrule_params.get('until') and hasattr(self.rrule_params.get('until'), 'date'):
            self.rrule_params['until'] = self.rrule_params['until'].strftime('%Y-%m-%d %H:%M:%S')

    def save(self, *args, **kwargs):
        """
        Saves the rrule model to the database. If this is a new object, the first next_scheduled time is
        determined and set. The `dtstart` and `until` objects will be safely encoded as strings if they are
        datetime objects.
        """
        self.pre_save_hooks()

        # Call the parent save method
        super().save(*args, **kwargs)

    def generate_dates(self, num_dates=20):
        """
        Generate the first num_dates dates of the recurrence and return a list of datetimes
        """
        assert num_dates > 0

        self.pre_save_hooks()

        dates = []

        rule = self.get_rrule()

        try:
            d = rule[0]
            # Convert to time zone
            date_with_tz = fleming.attach_tz_if_none(d, self.time_zone)
            date_in_utc = fleming.convert_to_tz(date_with_tz, pytz.utc, True)
            dates.append(date_in_utc)

            for x in range(0, num_dates):
                d = rule.after(d)
                if not d:
                    break
                # Convert to time zone
                date_with_tz = fleming.attach_tz_if_none(d, self.time_zone)
                date_in_utc = fleming.convert_to_tz(date_with_tz, pytz.utc, True)
                dates.append(date_in_utc)
        except Exception:  # pragma: no cover
            pass

        return dates

    def clone(self) -> RRule:
        """
        Creates a clone of itself.
        """

        # Clear id to force a new object.
        clone = copy.deepcopy(self)
        clone.id = None

        clone.save()

        return clone

    def clone_with_day_offset(self, day_offset: int) -> RRule:
        """
        Creates a clone of a passed RRule object offset by a specified number of days.
        Days can be negative.
        """

        # Create a clone of itself
        clone = self.clone()

        # Manually update the rrule.dtstart & next_occurrence with the offset.
        clone.rrule_params['dtstart'] = parser.parse(clone.rrule_params['dtstart']) + timedelta(days=day_offset)
        clone.next_occurrence = clone.next_occurrence + timedelta(days=day_offset)

        def offset_day(day, day_offset):
            """
            Calculates a day offset by a number of days.
            """
            return (7 + (day + day_offset)) % 7

        # Update byweekday param by offsetting. byweekday can be an array or integer.
        if 'byweekday' in clone.rrule_params:
            if isinstance(clone.rrule_params['byweekday'], list):
                clone.rrule_params['byweekday'] = [
                    offset_day(day, day_offset) for day in clone.rrule_params['byweekday']
                ]
            else:
                clone.rrule_params['byweekday'] = offset_day(clone.rrule_params['byweekday'], day_offset)

        # Lock it.
        clone.save()

        return clone

    @classmethod
    def generate_dates_from_params(cls, rrule_params, time_zone=None, num_dates=20):
        time_zone = time_zone or pytz.utc
        rule = cls(rrule_params=rrule_params, time_zone=time_zone)

        return rule.generate_dates(num_dates=num_dates)

