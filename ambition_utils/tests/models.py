from django.db import models


class FakeModel(models.Model):
    name = models.CharField(max_length=50)
