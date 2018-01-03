from abc import ABCMeta, abstractmethod


class OccurrenceHandler(object):
    """
    Recurrence handler class that is meant to be extended that will handle when a recurrence
    occurs for an rrule model
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def handle(self):
        """
        Handle a recurrence
        :return:
        """
        raise NotImplementedError
