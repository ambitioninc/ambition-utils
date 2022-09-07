import json

from datetime import datetime
from dateutil import rrule
from django import forms
from django.core.exceptions import ValidationError

from ambition_utils.rrule.constants import RecurrenceEnds
from ambition_utils.rrule.models import RRule

from ambition_utils.time_helpers import get_time_zones

FREQ_CHOICES = (
    (rrule.DAILY, 'Daily'),
    (rrule.WEEKLY, 'Weekly'),
    (rrule.MONTHLY, 'Monthly'),
    (rrule.YEARLY, 'Yearly'),
)


ENDS_CHOICES = (
    (RecurrenceEnds.NEVER, 'Never'),
    (RecurrenceEnds.AFTER, 'After'),
    (RecurrenceEnds.ON, 'On'),
)


REPEAT_BY_CHOICES = (
    ('DAY_OF_THE_MONTH', 'Day of the month'),
    ('DAY_OF_THE_WEEK_START', 'Day of the week counting from the beginning of the month'),
    ('DAY_OF_THE_WEEK_END', 'Day of the week counting backwards from the end of the month'),
    # ('FIRST_DAY_OF_MONTH', 'First day of Month'),
    ('DAY_OF_THE_MONTH_END', 'Last day of Month'),
)


class RecurrenceForm(forms.Form):
    """
    Handles submission of data for populating rrule objects. The field names are based on the rrule
    params defined here http://dateutil.readthedocs.io/en/stable/rrule.html
    """
    rrule = forms.ModelChoiceField(queryset=RRule.objects.all(), required=False)

    # Date from which the recurrence will be started from. This might not always be the first recurrence in the series
    dtstart = forms.DateField(
        error_messages={'required': 'Starts on is required'},
    )

    # The hour for each recurrence (0-23)
    byhour = forms.IntegerField(
        error_messages={'required': 'Hour is required'},
    )

    # The minute for each recurrence (0-59)
    byminute = forms.IntegerField(required=False)

    # The time zone which the submitted time is treated as. The submitted time is converted to utc
    time_zone = forms.ChoiceField(
        choices=get_time_zones(return_as_tuple=True),
        error_messages={'required': 'Time Zone is required'},
    )

    # Type of interval - daily, weekly, etc
    freq = forms.ChoiceField(
        choices=FREQ_CHOICES,
        error_messages={'required': 'Frequency is required'},
    )

    # How often does the event repeat? This is related to the repeats value.
    interval = forms.IntegerField()

    # Day checkboxes, required if frequency is weekly. json encoded list of day numbers ex: [0,2,4]
    byweekday = forms.CharField(required=False)

    # Required if frequency is monthly and day of week. json encoded list of nth day data ex: [[1,-2]]
    bynweekday = forms.CharField(required=False)

    # Only required to monthly frequency
    repeat_by = forms.ChoiceField(choices=REPEAT_BY_CHOICES, required=False)

    # Choice of how the recurrence can be ended
    ends = forms.ChoiceField(choices=ENDS_CHOICES)

    # Number of times the recurrence will occur. Only required if ends is set to AFTER
    count = forms.IntegerField(required=False)

    # Date when the recurrence will end. Only required if ends is set to ON. The 'until' date might not be the last
    # recurrence date
    until = forms.DateField(required=False)

    def __init__(self, *args, **kwargs):
        # Remove the instance param if it exists. Model forms will try to pass this, but it isn't used here and will
        # cause the base form init to fail
        kwargs.pop('instance', None)

        super(RecurrenceForm, self).__init__(*args, **kwargs)

    def clean_freq(self):
        """
        Make sure the frequency is an integer
        """
        return int(self.data.get('freq', -1))

    def clean(self):
        """
        Perform additional form validation based on submitted params
        """
        cleaned_data = super(RecurrenceForm, self).clean()

        if self.errors:
            return cleaned_data

        # Check if count is required
        if self.cleaned_data['ends'] == RecurrenceEnds.AFTER and not self.cleaned_data['count']:
            raise ValidationError('Number of occurrences is required')

        # Check if until is required
        if self.cleaned_data['ends'] == RecurrenceEnds.ON and not self.cleaned_data['until']:
            raise ValidationError('Ending date is required')

        # Unset until date if end ON is not selected
        if self.cleaned_data.get('ends') != RecurrenceEnds.ON:
            self.cleaned_data['until'] = ''

        # Check end date is after start date
        if self.cleaned_data.get('until') and self.cleaned_data.get('until') <= self.cleaned_data.get('dtstart'):
            raise ValidationError('End date must be after the start date')

        # Check if byweekday is required
        if self.cleaned_data['freq'] == rrule.WEEKLY and not self.cleaned_data['byweekday']:
            raise ValidationError('At least one day choice is required')

        # Check if repeat_by is required
        if self.cleaned_data['freq'] == rrule.MONTHLY and not self.cleaned_data.get('repeat_by'):
            raise ValidationError('Repeat by is required')

        return cleaned_data

    def clean_byminute(self):
        """
        Set optional byminute value to 0 if not defined
        """

        if 'byminute' not in self.data:
            return 0
        else:
            return self.cleaned_data['byminute']

    def clean_byweekday(self):
        """
        Decode the byweekday option
        """
        value = []

        try:
            value = json.loads(self.data.get('byweekday', '[]'))
        except ValueError:
            pass

        return value

    def clean_bynweekday(self):
        """
        Decode the bynweekday option
        """
        value = []

        try:
            value = json.loads(self.data.get('bynweekday', '[]'))
        except ValueError:
            pass

        return value

    def save(self, **kwargs):
        """
        Saves the RRule model and returns it
        """
        rrule_freq = self.cleaned_data['freq']
        start_date = self.cleaned_data['dtstart']

        # Convert date to datetime
        start_datetime = datetime.combine(start_date, datetime.min.time())

        # Build params for rrule object
        params = {
            'freq': rrule_freq,
            'dtstart': start_datetime,
            'byhour': self.cleaned_data.get('byhour'),
            'byminute': self.cleaned_data.get('byminute'),
            'interval': self.cleaned_data.get('interval', 1),
        }

        if self.cleaned_data.get('count'):
            params['count'] = self.cleaned_data.get('count')

        if self.cleaned_data.get('until'):
            # Convert date to datetime
            until = datetime.combine(self.cleaned_data.get('until'), datetime.min.time())

            # Add hour to until datetime if it exists
            until = until.replace(hour=params['byhour'], minute=params['byminute'])
            params['until'] = until

        # Add day choices
        if self.cleaned_data.get('freq') == rrule.WEEKLY:
            params['byweekday'] = self.cleaned_data.get('byweekday')

        # Add repeat by choices
        if self.cleaned_data.get('freq') == rrule.MONTHLY:
            if self.cleaned_data.get('repeat_by') == 'DAY_OF_THE_MONTH':
                params['bymonthday'] = start_datetime.day
            elif self.cleaned_data.get('repeat_by') == 'DAY_OF_THE_MONTH_END':
                params['bymonthday'] = -1
            else:
                params['byweekday'] = self.cleaned_data['bynweekday'][0][0]
                params['bysetpos'] = self.cleaned_data['bynweekday'][0][1]

        # Keep track if this is an existing rrule that needs occurrence updated
        need_to_refresh_next_recurrence = False

        # Get the rrule model from the cleaned data
        rrule_model = self.cleaned_data.get('rrule')
        if rrule_model:
            need_to_refresh_next_recurrence = True
        else:
            # Use the recurrence passed into save kwargs
            rrule_model = kwargs.get('recurrence') or RRule()

        # Create or update the rule
        rrule_model.rrule_params = params
        rrule_model.time_zone = self.cleaned_data.get('time_zone')
        for key, value in kwargs.items():
            if hasattr(rrule_model, key):
                # This try except is because some field names might be reverse foreign key relationships
                try:
                    setattr(rrule_model, key, value)
                except TypeError:  # pragma: no cover
                    pass

        # Check if this was an existing model that needs to have its next occurrence updated
        if need_to_refresh_next_recurrence:
            rrule_model.refresh_next_occurrence()

        rrule_model.save()

        # Return the rule
        return rrule_model
