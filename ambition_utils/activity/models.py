from datetime import datetime
from enum import Enum
from uuid import uuid4

from django.db import models


def get_sorted_enum_types(enum_class):
    """
    Returns a sorted tuple list of the enum's values sutable for a CharField's
    ``choices`` argument
    :param enum_class: A class that inherits Enum
    :return: A tuple of tuples ((element.value, element.name), ...)
    """
    choices = [(element.value, element.name) for element in list(enum_class)]
    choices.sort()
    return tuple(choices)


class ActivityGroupStatus(Enum):
    """
    Enum for the possible status states of an activity group
    """
    ACTIVE = 'ACTIVE'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'


class ActivityStatus(Enum):
    """
    Enum for the possible status states of an activity
    """
    PENDING = 'PENDING'
    ACTIVE = 'ACTIVE'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'


class ActivityGroup(models.Model):
    """
    General-purpose model to track state of a process
    """
    uuid = models.UUIDField(db_index=True, default=uuid4, editable=False, null=True)
    name = models.CharField(max_length=255, blank=False, null=False)
    time_created = models.DateTimeField(auto_now_add=True, db_index=True)
    time_finished = models.DateTimeField(null=True, db_index=True)
    status = models.CharField(
        max_length=255,
        choices=get_sorted_enum_types(ActivityGroupStatus),
        default=ActivityGroupStatus.ACTIVE.value,
        db_index=True
    )
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    def finish(self, status=ActivityGroupStatus.SUCCESS.value):
        self.status = status
        self.time_finished = datetime.utcnow()
        self.save()
        return self

    def success(self):
        return self.finish(status=ActivityGroupStatus.SUCCESS.value)

    def failure(self, message):
        self.error_message = message
        return self.finish(status=ActivityGroupStatus.FAILURE.value)


class Activity(models.Model):
    """
    Model to track the state of a single activity belonging to a process
    """
    name = models.CharField(max_length=255, blank=False, null=False)
    description = models.TextField(blank=False, null=False)
    time_created = models.DateTimeField(auto_now_add=True, db_index=True)
    time_updated = models.DateTimeField(auto_now=True, db_index=True)
    time_finished = models.DateTimeField(null=True, db_index=True)
    group = models.ForeignKey(ActivityGroup, null=True, related_name='activities', on_delete=models.CASCADE)
    status = models.CharField(
        max_length=255,
        default=ActivityStatus.PENDING.value,
        choices=get_sorted_enum_types(ActivityStatus),
        db_index=True
    )
    error_message = models.TextField(blank=True, null=True)

    def finish(self, status=ActivityStatus.SUCCESS.value):
        self.status = status
        self.time_finished = datetime.utcnow()
        self.save()
        return self

    def active(self):
        self.status = ActivityStatus.ACTIVE.value
        self.save()
        return self

    def success(self):
        return self.finish(status=ActivityStatus.SUCCESS.value)

    def failure(self, error_message):
        return self.finish(status=ActivityStatus.FAILURE.value)
