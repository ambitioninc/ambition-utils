from django.db import models


class Program(models.Model):
    name = models.TextField()
    start_called = models.IntegerField(default=0)
    end_called = models.IntegerField(default=0)

    start_recurrence = models.ForeignKey('rrule.RRule', on_delete=models.SET_NULL, null=True)
    end_recurrence = models.ForeignKey('rrule.RRule', on_delete=models.SET_NULL, null=True)

    def handle_start_recurrence(self, rrule):
        self.start_called += 1
        self.save()
        return rrule

    def handle_end_recurrence(self, rrule):
        self.end_called += 1
        self.save()
        return rrule
