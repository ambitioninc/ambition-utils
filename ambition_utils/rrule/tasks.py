from celery import Task

from ambition_utils.rrule.models import RRule


class RecurrenceTask(Task):
    """
    A task for processing occurrences of a recurrence model
    """

    queue_once = True
    non_overlapping = True

    def run(self, *args, **kwargs):
        """
        Main run method for processing
        :param args:
        :param kwargs:
        :return:
        """

        RRule.objects.handle_overdue()
