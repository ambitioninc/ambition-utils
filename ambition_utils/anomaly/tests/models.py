from django.db import models
from ambition_utils.anomaly.models import AnomalyBase
from math import floor


class FloatModel(models.Model):
    value = models.FloatField()


class IncrementalAnomaly(AnomalyBase):
    IS_INCREMENTAL = True
    name = models.CharField(max_length=100)

    def compute_uid(self):
        return self.name


class NonIncrementalAnomaly(AnomalyBase):
    IS_INCREMENTAL = False
    name = models.CharField(max_length=100)

    def compute_uid(self):
        return self.name

    def update(self):
        values = sorted(FloatModel.objects.all().values_list('value', flat=True))

        lower_index = int(floor(.01 * self.percentile_low * len(values)))
        upper_index = int(floor(.01 * self.percentile_high * len(values)))

        self.threshold_low = values[lower_index]
        self.threshold_high = values[upper_index]
        self.num_values_ingested += len(values)

        self.save()
