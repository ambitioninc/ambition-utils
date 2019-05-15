import copy
from datetime import datetime

import pytz
from dateutil.rrule import rrule
from dateutil import parser
from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from django.utils.module_loading import import_string
from fleming import fleming
from manager_utils import bulk_update
from timezone_field import TimeZoneField


class RRuleManager(models.Manager):
    """
    Custom manager for rrule objects
    """
    def update_next_occurrences(self, rrule_objects=None):
        rrule_objects = rrule_objects or self.get_queryset()
        for rrule_object in rrule_objects:
            rrule_object.update_next_occurrence(save=False)

        bulk_update(self, rrule_objects, ['last_occurrence', 'next_occurrence'])

    @transaction.atomic
    def handle_overdue(self, **filters):
        """
        Handles any overdue rrules
        """

        # Get instances of all overdue recurrence handler classes
        instances = self.overdue_handler_class_instances(**filters)

        # Build a list of rrules that get returned from the handler
        rrules = []
        for instance in instances:
            rrules.extend(instance.handle())

        # Bulk update the next occurrences
        RRule.objects.update_next_occurrences(rrule_objects=rrules)

    def overdue_handler_class_instances(self, **filters):
        """
        Returns a set of instances for any handler with an old next_occurrence
        """

        # Get the rrule objects that are overdue and need to be handled
        rrule_objects = self.get_queryset().filter(
            next_occurrence__lte=datetime.utcnow(),
            **filters
        ).distinct(
            'occurrence_handler_path'
        )

        # Return instances of the handler classes
        return [
            rrule_object.get_occurrence_handler_class_instance()
            for rrule_object in rrule_objects
        ]


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

    # Custom object manager
    objects = RRuleManager()

    def get_occurrence_handler_class_instance(self):
        """
        Gets an instance of the occurrence handler class associated with this rrule
        :rtype: ambition_utils.rrule.handler.OccurrenceHandler
        :return: The instance
        """
        return import_string(self.occurrence_handler_path)()

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
        last_occurrence = fleming.convert_to_tz(last_occurrence, self.time_zone, return_naive=True)

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
        dt = fleming.attach_tz_if_none(dt, self.time_zone)

        # Convert to utc
        dt = fleming.convert_to_tz(dt, pytz.utc, return_naive=True)

        return dt

    def save(self, *args, **kwargs):
        """
        Saves the rrule model to the database. If this is a new object, the first next_scheduled time is
        determined and set. The `dtstart` and `until` objects will be safely encoded as strings if they are
        datetime objects.
        """

        # Check if this is a new rrule object
        if self.pk is None:
            # Convert the scheduled time to utc so getting the rrule
            self.next_occurrence = self.convert_to_utc(self.rrule_params['dtstart'])

            # Get the first scheduled time according to the rrule (this converts from utc back to local time)
            self.next_occurrence = self.get_rrule()[0]

            # Convert back to utc before saving
            self.next_occurrence = self.convert_to_utc(self.next_occurrence)
        else:
            # This is an existing rrule object so check if the start time is different but still greater than now
            next_occurrence = self.get_rrule()[0]

            # Convert back to utc before saving
            next_occurrence = self.convert_to_utc(next_occurrence)
            now = datetime.utcnow()
            if next_occurrence != self.next_occurrence and next_occurrence > now:
                self.next_occurrence = next_occurrence

        # Serialize the datetime objects if they exist
        if self.rrule_params.get('dtstart') and hasattr(self.rrule_params.get('dtstart'), 'date'):
            self.rrule_params['dtstart'] = self.rrule_params['dtstart'].strftime('%Y-%m-%d %H:%M:%S')

        if self.rrule_params.get('until') and hasattr(self.rrule_params.get('until'), 'date'):
            self.rrule_params['until'] = self.rrule_params['until'].strftime('%Y-%m-%d %H:%M:%S')

        # Call the parent save method
        super().save(*args, **kwargs)
