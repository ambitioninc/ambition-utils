from django.db import models
from ambition_utils.models import AnomalyBase
from math import floor


class FakeModel(models.Model):
    name = models.CharField(max_length=50)
