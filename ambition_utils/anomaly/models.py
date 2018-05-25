import datetime
import sys
from numbers import Number
from typing import Union, Iterable, List


from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.functional import cached_property
import fleming
from tdigest import TDigest

from manager_utils import ManagerUtilsManager, ManagerUtilsQuerySet


class BadPercentileValue(Exception):
    pass


class BadAnomalyType(Exception):
    pass


class AnomalyBaseQueryset(ManagerUtilsQuerySet):
    def unprocessed(self, assume_now=None):
        if assume_now is None:
            assume_now = datetime.datetime.utcnow()
        today = fleming.floor(assume_now, day=1)

        return self.filter(last_modified__lt=today)


class AnomalyBaseManager(ManagerUtilsManager):
    def get_queryset(self):
        return AnomalyBaseQueryset(self.model)

    def unprocessed(
            self,
            assume_now: Union[datetime.datetime, None] = None
    ) -> AnomalyBaseQueryset:
        return self.get_queryset().unprocessed(assume_now=assume_now)


class AnomalyBase(models.Model):
    """
    Override this class to create an Anomaly Detector.  Think of this as a key-value store
    for anomalies.  You update instances with observed data.  This teaches the detector what
    "normal" is.  You then check values against what it has learned using the .detect(...) method.

    You are free to add whatever fields you want to your detector as long as they don't
    collide with the field names on this base class.

    You must define a get_uid() method on your class to populate the uid field.
    """
    # set whether or not this detector will use the blob to do incremental updates
    # When inheriting from this class, you must specify whether or not this detector will be incremental.
    # Incremental detectors use the tdigest blob.  Non-incremental detectors rely on outside code for updates
    # (for example, direct sql computation)
    IS_INCREMENTAL = True
    PERCENTILE_LOW_DEFAULT = 5
    PERCENTILE_HIGH_DEFAULT = 95

    class Meta:
        abstract = True

    # unique id to identify this anomaly detector
    uid = models.CharField(max_length=256, unique=True)

    # JSON blob to persist the state of the tdigest
    blob = JSONField(default=dict, null=True)

    # User defined percentiles below and above which an anomaly will happen
    percentile_low = models.FloatField(null=True)
    percentile_high = models.FloatField(null=True)

    # These configure the accuracy/space tradeoff for the t-digest state
    delta = models.FloatField(default=.01, null=True)
    K = models.FloatField(default=25, null=True)

    # These are auto-populated and should not be altered by the user
    # I'm indexing these because we will likely want to do a fast search
    # for non-null values.
    threshold_low = models.FloatField(null=True, db_index=True)
    threshold_high = models.FloatField(null=True, db_index=True)

    # This holds the number of ingested values in the database.  Note that this is a duplicate of what
    # is in the digest for incremental detector.  You shouldn't access this field directly.  Use the
    # .count property instead
    num_values_ingested = models.IntegerField(default=0)

    # keeps track of the last time updated
    last_modified = models.DateTimeField(db_index=True)

    objects = AnomalyBaseManager()

    def compute_uid(self) -> str:
        """
        Override this method with code to populate your uid field
        """
        raise NotImplementedError('you must define a .compute_uid() method')

    @property
    def count(self) -> int:
        if self.IS_INCREMENTAL:
            self.num_values_ingested = self.digest.n
        return self.num_values_ingested

    @count.setter
    def count(self, new_count: int) -> None:
        if self.IS_INCREMENTAL:
            raise ValueError('Can\'t set count on an incrmental anomaly detector')
        else:
            self.num_values_ingested = new_count

    @cached_property
    def digest(self) -> TDigest:
        """
        This property pulls from the database to populate a tdigest instance
        """
        dig = TDigest(self.delta, self.K)
        if self.blob:
            dig.update_from_dict(self.blob)
        return dig

    @property
    def min_num_points_high(self) -> float:
        if self.percentile_high is None:
            return sys.maxsize
        return 100. / (100. - self.percentile_high)

    @property
    def min_num_points_low(self) -> float:
        if self.percentile_low is None:
            return sys.maxsize
        return 100. / self.percentile_low

    def update(self, data, reset_threshold=False):
        """
        This method can be overwritten.  It defaults to updating the tdigest.  If you overwrite
        this method, it is your responsibility to update the num_values_ingested field with
        the number of points you are using in the update.
        """
        return self._update_digest(data, reset_threshold)

    def _update_digest(
            self,
            data: Iterable[Union[float, int]],
            reset_thresholds: bool
    ) -> None:
        """
        Call this method with data observations.  These updates are incorporated into internal
        state that will be able to efficiently detect future abnormal values.

        :param data: either a number or an iterable of numbers
        :param reset_thresholds: Setting to True will force the thresholds to update.  This is a
                                pretty big efficiency hit, but you may want to update and check
                                data without hitting the database.  This lets you do that.
        """
        if not self.IS_INCREMENTAL:
            raise BadAnomalyType('update() can only be called for incremental anomaly detector')

        if hasattr(data, '__iter__'):
            self.digest.batch_update(data)
        else:
            self.digest.update(data)

        if reset_thresholds:
            self._set_thresholds_from_tdigest()

    def _detect_point(self, val: Number) -> int:
        """
        compares a single number with thresholds to determine if it is an anomaly
        :param val:  a number.
        :return: -1: low_anomaly,  0: no_anomaly, 1: high_anomaly
        """
        anomaly = 0
        if self.count > self.min_num_points_low and self.threshold_low is not None and val < self.threshold_low:
            anomaly = -1

        if self.count > self.min_num_points_high and self.threshold_high is not None and val > self.threshold_high:
            anomaly = 1
        return anomaly

    def detect(
            self,
            data: Union[Number, Iterable[Number]]
    ) -> Union[int, Iterable[int]]:
        """
        Checks whether data is an anomaly
        :param data: either a number or an iterable of numbers
        :return: either a number or list of numbers depending on input
                 -1 represents low anomaly
                 +1 represents high anomaly
                 0 represents no anomaly
        """
        # These are actually okay typwise, but mypy doesn't like it
        if hasattr(data, '__iter__'):
            data_it: Iterable[Number] = data  # type: ignore
        else:
            data_it: Iterable[Number] = [data]  # type: ignore

        out: List[int] = [self._detect_point(val) for val in data_it]

        if len(out) == 1:
            return out[0]
        else:
            return out

    def _check_percentiles(self) -> None:
        """
        Raises an error if percentile settings look hokey
        """
        # set undefined percentiles to default values
        if self.percentile_low is None:
            self.percentile_low = self.PERCENTILE_LOW_DEFAULT
        if self.percentile_high is None:
            self.percentile_high = self.PERCENTILE_HIGH_DEFAULT

        # make sure percentiles look right
        if not 0. < self.percentile_low < 50.:
            raise BadPercentileValue('(0. < low_percentile < 50) is False')
        if not 50. <= self.percentile_high < 100.:
            raise BadPercentileValue('(50. < high_percentile < 100) is False')

    def _set_thresholds_from_tdigest(self) -> None:
        """
        Automatically sets thresholds based on desired percentiles and values
        already seen.
        """
        # set the high threshold if enough points have been seen
        if self.count > 0:
            self.threshold_high = self.digest.percentile(self.percentile_high)

        # set the low threshold if enough points have been seen
        if self.count > 0:
            self.threshold_low = self.digest.percentile(self.percentile_low)

    def _set_last_modified(self) -> None:
        self.last_modified = datetime.datetime.utcnow()

    def pre_save_hooks(self) -> None:
        """
        Everything here needs to be run to ensure state of the model is properly
        persisted to the database.
        """
        # explicitly implement last_modified logic so that bulk updates/upserts work
        self._set_last_modified()

        # make sure uid is set
        if not self.uid:
            self.uid = self.compute_uid()

        # make sure the percentiles are in range
        self._check_percentiles()

        # if there are enough points, set the thresholds properly for incremental detector
        if self.IS_INCREMENTAL:
            self._set_thresholds_from_tdigest()

        # serialize the digest to the blob
        self.blob = self.digest.to_dict()

        # accessing count property makes sure counts are properly mirrored from digest
        self.count

    def save(self, *args, **kwargs) -> None:
        """
        Make sure the pre-save hooks are called on each save
        """
        self.pre_save_hooks()
        super(AnomalyBase, self).save(*args, **kwargs)
