from django.db import models


class PostgresLock(models.Model):
    """
    A model that will represent a postgres lock. A postgres lock is just a unique row
    on a model that we will insert or update a row to indicate that the row is locked.
    Postgres automatically locks the row and prevents others from writing until the transaction
    is complete. This allows us to treat this exactly like a locking system
    """

    # The name of the lock
    name = models.CharField(
        max_length=512,
        unique=True,
        primary_key=True,
    )

    # The last time the lock was updated
    time = models.DateTimeField(default=None)

    # An optional value to store with the lock
    value = models.TextField(default=None, null=True)

    # The previous value the last time the lock was acquired
    previous_value = models.TextField(default=None, null=True)
