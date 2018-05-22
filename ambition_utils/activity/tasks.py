from django.contrib.contenttypes.models import ContentType
from functools import wraps
from inspect import getmembers
from six import reraise
from sys import exc_info

from ambition_utils.activity.models import Activity, ActivityGroup


def decorate_activity(fn, activity):
    """
    Decorator to wrap function call with activity state management
    """
    @wraps(fn)
    def decorator(*args, **kwargs):
        set_active = getattr(activity, 'active', lambda: None)
        set_active()
        try:
            ret_val = fn(*args, **kwargs)
            activity.success()
            return ret_val
        except Exception as e:
            activity.failure(str(e))
            reraise(*exc_info())
    return decorator


def track_activity(fn):
    """
    decorator to add state to method which indicates that its progress should be tracked through activities
    """
    fn.activity_enabled = True
    return fn


class ActivityManagedTaskMixin(object):
    """
    Mixin for tasks whose progress needs to be tracked through activities

    To make use of this mixin:
    1. include the mixin
    2. name the task methods that you wish track individually with "_activity" suffix
    3. provide a uuid when instantiating the task
    """
    def __init__(self, *args, **kwargs):
        if 'uuid' in kwargs:
            self.uuid = kwargs.pop('uuid', None)
            activity_names = [
                member[0] for member in getmembers(self)
                if hasattr(member[1], 'activity_enabled')
            ]
            context_object = self.get_context_object()
            context_object_id = getattr(context_object, 'id', None)
            context_object_type = None
            if context_object is not None:  # pragma: no cover
                context_object_type = ContentType.objects.get_for_model(context_object)
            self.activity_group, created = ActivityGroup.objects.get_or_create(
                uuid=self.uuid, name=self.get_activity_group_name(), context_object_id=context_object_id,
                context_object_type=context_object_type)

            # decorate the activity methods
            for activity_name in activity_names:
                activity = Activity.objects.create(name=activity_name, group=self.activity_group)
                decorated_method = decorate_activity(getattr(self, activity_name), activity)
                setattr(self, activity_name, decorated_method)

            # decorate the run method
            run_fn = decorate_activity(getattr(self, 'run'), self.activity_group)
            setattr(self, 'run', run_fn)

        super(ActivityManagedTaskMixin, self).__init__(*args, **kwargs)

    def get_activity_group_name(self):
        return self.__class__.__name__

    def get_context_object(self):
        return None
