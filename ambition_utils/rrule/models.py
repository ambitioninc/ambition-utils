from __future__ import annotations
from datetime import datetime, timedelta
from dateutil import parser
from dateutil.rrule import rrule, rruleset
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models, transaction
from django.utils.module_loading import import_string
from fleming import fleming
from manager_utils import bulk_update
from ambition_utils.fields import TimeZoneField
from typing import List
import copy
import pytz
import logging

LOG = logging.getLogger(__name__)


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
    rrule_params = models.JSONField()

    # Optional params used to generate the rrule exclusion
    rrule_exclusion_params = models.JSONField(default=None, blank=True, null=True)

    # Any meta data associated with the object that created this rule
    meta_data = models.JSONField(default=dict)

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
        """
        Returns the time zone object from pytz
        """
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

    def get_rrule_set(self):
        """
        Returns the rrule set that will combine the rrule and optional exclusion rrule
        """
        rrule_set = rruleset()
        rrule_set.rrule(self.get_rrule())
        rrule_exclusion = self.get_rrule_exclusion()
        if rrule_exclusion:
            rrule_set.exrule(rrule_exclusion)
        return rrule_set

    def get_rrule(self):
        """
        Builds the rrule object by restoring all the params.
        """
        return self.get_rrule_from_params(self.rrule_params)

    def get_rrule_exclusion(self):
        """
        Builds the rrule exclusion object by restoring all the params.
        :rtype: rrule
        """
        return self.get_rrule_from_params(self.rrule_exclusion_params)

    def get_rrule_from_params(self, params):
        """
        Creates an rrule object from a dict of rrule params. Returns None if no params exists.
        The dtstart param will be converted to local time if it is set.
        :rtype: rrule
        """
        # Check for none or empty
        if not params:
            return None

        # Create a deep copy because we will manipulate
        params = copy.deepcopy(params)

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

        # Get the rule set
        rule_set = self.get_rrule_set()

        # Convert to local time zone for getting next occurrence, otherwise time zones ahead of utc will return the same
        last_occurrence = fleming.convert_to_tz(last_occurrence, self.get_time_zone_object(), return_naive=True)

        # Generate the next occurrence
        next_occurrence = rule_set.after(last_occurrence)

        # If next occurrence is none and force is true, force the rrule to generate another date
        if next_occurrence is None and force:
            # Keep a reference to the original rrule_params
            original_rrule_params = {}
            original_rrule_params.update(self.rrule_params)

            # Remove any limiting params
            self.rrule_params.pop('count', None)
            self.rrule_params.pop('until', None)

            # Refetch the rule set
            rule_set = self.get_rrule_set()

            # Generate the next occurrence
            next_occurrence = rule_set.after(last_occurrence)

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
        """
        Ensure that all the date keys are properly set on all rrule params
        """

        # Convert the rrule and exclusion rrule params to properly set date keys
        is_new = self.pk is None
        self.set_date_objects_for_params(self.rrule_params, is_new=is_new)
        self.set_date_objects_for_params(self.rrule_exclusion_params, is_new=is_new)

        # Check if this is a new rrule object
        if is_new:
            # Get the first scheduled time according to the rrule (this converts from utc back to local time)
            self.next_occurrence = self.get_rrule_set()[0]

            # Convert back to utc before saving
            self.next_occurrence = self.convert_to_utc(self.next_occurrence)

    def set_date_objects_for_params(self, params, is_new=False):
        """
        Give an rrule params object, ensure that the date keys are properly set and properly converted to strings
        """
        # Check for no params
        if not params:
            return params

        # Check if this is a new rrule object
        if is_new:
            # Convert next scheduled from utc back to time zone
            if params.get('dtstart') and not hasattr(params.get('dtstart'), 'date'):
                params['dtstart'] = parser.parse(params['dtstart'])

            # Convert until date from utc back to time zone
            if params.get('until') and not hasattr(params.get('until'), 'date'):
                params['until'] = parser.parse(params['until'])

        # Serialize the datetime objects if they exist
        if params.get('dtstart') and hasattr(params.get('dtstart'), 'date'):
            params['dtstart'] = params['dtstart'].strftime('%Y-%m-%d %H:%M:%S')

        if params.get('until') and hasattr(params.get('until'), 'date'):
            params['until'] = params['until'].strftime('%Y-%m-%d %H:%M:%S')

    def save(self, *args, **kwargs):
        """
        Saves the rrule model to the database. If this is a new object, the first next_scheduled time is
        determined and set. The `dtstart` and `until` objects will be safely encoded as strings if they are
        datetime objects.
        """

        # Run any pre save hooks
        self.pre_save_hooks()

        # Call the parent save method
        super().save(*args, **kwargs)

    def get_dates(self, num_dates=20, start_date=None) -> List[datetime]:
        """
        Return a list of datetime objects the recurrence will generate, after the start date (if defined).
        :param num_dates: The maximum number of dates to calculate. Will stop at passed start_date
        :param start_date: The optional start date to begin generating dates after
        :return: A list of datetime objects
        """

        # Assert that we have dates
        assert num_dates > 0

        # Ensure that pre save hooks have been run
        self.pre_save_hooks()

        # Generate the dates
        dates = []
        try:
            # Capture the rule's first date for use in RRule.after() in the loop.
            rule_set = self.get_rrule_set()

            # Evaluate if the first date should be retained.
            d = self.convert_to_utc(rule_set[0])
            if not start_date or d > start_date:
                dates.append(d)

            # Continue evaluating and appending dates to satisfy desired number,
            # retaining date for evaluation in the next iteration.
            while len(dates) < num_dates:
                d = self.get_next_occurrence(last_occurrence=d)
                if d:
                    if not start_date or d > start_date:
                        dates.append(d)
                else:
                    break
        except Exception:  # pragma: no cover
            pass

        # Return the generated dates
        return dates

    def generate_dates(self, num_dates=20):
        """
        DEPRECATED. Replaced by get_dates.
        Return a list of the next num_dates datetimes of the recurrence.
        """
        LOG.warning('generate_dates has been replaced by get_dates and will be removed in version 3.x.')
        return self.get_dates(num_dates)

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
        Creates a clone of a passed RRule object offset by a specified number of days
        :param day_offset: The number of days to offset the clone's start date. Can be negative.
        """

        # Create a clone of itself
        clone = self.clone()

        # Manually update the rrule.dtstart & next_occurrence with the offset.
        clone.rrule_params['dtstart'] = parser.parse(clone.rrule_params['dtstart']) + timedelta(days=day_offset)
        clone.next_occurrence = clone.next_occurrence + timedelta(days=day_offset)

        # Update until param by offsetting if it exists
        if 'until' in clone.rrule_params:
            clone.rrule_params['until'] = parser.parse(clone.rrule_params['until']) + timedelta(days=day_offset)

        def offset_day(day: int) -> int:
            """
            Calculates the representation of a given day of the week plus the provided offset
            For example, Tuesday (1) - 3 days yields Saturday (5).
            :param int day: 0-6 that corresponds to RRule's weekday constants, MO-SU.
            """
            return (7 + (day + day_offset)) % 7

        # Update byweekday param by offsetting. byweekday can be an array or integer.
        if 'byweekday' in clone.rrule_params:
            if isinstance(clone.rrule_params['byweekday'], list):
                clone.rrule_params['byweekday'] = [
                    offset_day(day) for day in clone.rrule_params['byweekday']
                ]
            else:
                clone.rrule_params['byweekday'] = offset_day(clone.rrule_params['byweekday'])

        # Lock it.
        clone.save()

        return clone

    @classmethod
    def get_dates_from_params(cls, rrule_params, time_zone=None, num_dates=20, start_date=None):
        time_zone = time_zone or pytz.utc
        rule = cls(rrule_params=rrule_params, time_zone=time_zone)

        return rule.get_dates(num_dates=num_dates, start_date=start_date)

    @classmethod
    def generate_dates_from_params(cls, rrule_params, time_zone=None, num_dates=20):
        """
        DEPRECATED. Replaced by get_dates_from_params.
        """
        LOG.warning(
            'generate_dates_from_params has been replaced by get_dates_from_params and will be removed in version 3.x.'
        )
        return cls.get_dates_from_params(rrule_params, time_zone, num_dates)
