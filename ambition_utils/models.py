import datetime


from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils.functional import cached_property
import fleming
from tdigest import TDigest

from manager_utils import ManagerUtilsManager, ManagerUtilsQuerySet

ROLLING_DAYS_DEFAULT = 90

# from entity.models import Entity
# from ambition.bridges.entity_bridge.constants import ACCOUNT_KIND_NAME

class BadPercentileValue(Exception):
    pass


class BadAnomalyType(Exception):
    pass


class AnomalyBaseQueryset(ManagerUtilsQuerySet):
    def unprocessed(self, assume_now=None):
        if assume_now is None:
            assume_now = datetime.datetime.utcnow()
        today = fleming.floor(assume_now, day=1)

        return self.filter(last_updated__lt=today)


class AnomalyBaseManager(ManagerUtilsManager):
    def get_queryset(self):
        return AnomalyBaseQueryset(self.model)


class AnomalyBase(models.Model):
    """
    Override this class to create an Anomaly Detector.  Think of this as a key-value store
    for anomalies.  You update instances with observed data.  This teaches the detector what
    "normal" is.  You then check values against what it has learned using the .check method.

    You are free to add whatever fields you want to your detector as long as they don't
    collide with the field names on this base class.

    You must define a get_uid() method on your class to populate the uid field.
    """
    class Meta:
        abstract = True

    # unique id to identify this anomaly detector
    uid = models.CharField(max_length=256, unique=True)

    # set whether or not this detector will use the blob to do incremental updates
    is_incremental = models.BooleanField(default=True)

    # JSON blob to persist the state of the tdigest
    blob = JSONField(default=dict)

    # User defined percentiles below and above which an anomaly will happen
    percentile_low = models.FloatField(default=5)
    percentile_high = models.FloatField(default=95)

    # These configure the accuracy/space tradeoff for the t-digest state
    delta = models.FloatField(default=5)
    K = models.FloatField(default=25)

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

    objects = ManagerUtilsManager()

    def compute_uid(self):
        """
        Override this method with code to populate your uid field
        """
        raise NotImplementedError('you must define a .compute_uid() method')

    @property
    def count(self):
        if self.is_incremental:
            self.num_values_ingested = self.digest.N
        return self.num_values_ingested

    @count.setter
    def count(self, new_count):
        if self.is_incremental:
            raise ValueError('Can\'t set count on an incrmental anomaly detector')
        else:
            self.num_values_ingested = new_count


    @cached_property
    def digest(self):
        """
        This property pulls from the database to populate a tdigest instance
        """
        dig = TDigest(self.delta, self.K)
        dig.update_from_dict(self.blob)
        return dig

    def set_thresholds(self, lower, uppper):
        """
        Method to manually set lower and upper thresholds.  This should only be used for
        non-incremental detectors.

        :param lower: value below which anomalies will be detected
        :param uppper:  upper value abo e which anomalies will be detected
        :return:
        """
        if self.is_incremental:
            raise BadAnomalyType('set_thresholds() can not be called on incremental detector')

    def update(self, data, reset_thesholds=False):
        """
        Call this method with data observations.  These updates are incorporated into internal
        state that will be able to efficiently detect future abnormal values.

        :param data: either a number or an iterable of numbers
        :param reset_thesholds: Setting to True will force the thresholds to update.  This is a
                                pretty big efficiency hit, but you may want to update and check
                                data without hitting the database.  This lets you do that.
        """
        if not self.is_incremental:
            raise BadAnomalyType('update() can only be called for incremental anomoly detector')

        if hasattr(data, '__iter__'):
            self.digest.batch_update(data)
        else:
            self.digest.update(data)

        if reset_thesholds:
            self._set_thesholds()

    def _check_point(self, val):
        """
        compares a single number with thresholds to determine if it is an anomaly
        :param val:  a number.
        :return: -1: low_anomaly,  0: no_anomaly, 1: high_anomaly
        """
        anomaly = 0
        if self.threshold_low is not None and val < self.threshold_low:
            anomaly = -1
        elif self.threshold_high is not None and val > self.threshold_high:
            anomaly = 1
        return anomaly

    def check(self, data):
        """
        Checks whether data is an anomaly
        :param data: either a number or an iterable of numbers
        :return: either a number or list of numbers depending on input
                 -1 represents low anomaly
                 +1 represents high anomaly
                 0 represents no anomaly
        """
        if not hasattr(data, '__iter__'):
            data = [data]

        out = [self._check_point(val) for val in data]

        if len(out) == 1:
            return out[0]
        else:
            return out

    def _check_percentiles(self):
        """
        Raises an error if percentile settings look hokey
        """
        if not 0. < self.percentile_low < 50.:
            raise BadPercentileValue('(0. < low_percentile < 50) is False')
        if not 50. <= self.percentile_low < 100.:
            raise BadPercentileValue('(50. < high_percentile < 100) is False')

    def _set_thresholds(self):
        """
        Automatically sets thresholds based on desired percentiles and values
        already seen.
        """
        # calculate the number of points that must have been seen in order to
        # generate anomalies.
        min_num_points_high = 100. / (100. - self.percentile_high)
        min_num_points_low = 100. / self.percentile_low

        # set the high threshold if enough points have been seen
        if self.digest.n > min_num_points_high:
            self.threshold_high = self.digest.percentile(self.percentile_high)
        else:
            self.threshold_high = None

        # set the low threshold if enough points have been seen
        if self.digest.n > min_num_points_low:
            self.threshold_low = self.digest.percentile(self.percentile_low)
        else:
            self.threshold_low = None

    def _set_last_modified(self):
        self.last_modified = datetime.datetime.utcnow()

    def pre_save_hooks(self):
        """
        Everything here needs to be run to ensure state of the model is properly
        persisted to the database.
        """
        # explicitly implement last_modified logic so that bulk updates/upserts work
        self._set_last_modified()

        # make sure uid is set
        if self.uid is None:
            self.uid = self.compute_uid()

        # make sure the percentiles are in range
        self._check_percentiles()

        # if there are enough points, set the thresholds properly
        self._set_thresholds()

        # serialize the digest to the blob
        self.blob = self.digest.to_dict()

        # accessing count property makes sure counts are properly mirrored from digest
        self.count

    def save(self, *args, **kwargs):
        """
        Make sure the pre-save hooks are called on each save
        """
        self.pre_save_hooks()
        super(AnomalyBase, self).save(*args, **kwargs)


class MetricAnomaly(AnomalyBase):
    entity = models.ForeignKey('entity.models.Entity')
    metric_config = models.ForeignKey('animal.models.MetricConfig')
    rolling_days = models.IntegerField(null=True)

    def compute_uid(self):
        return '{}_{}_{}'.format(self.entity_id, self.metric_config_id, self.rolling_days)

    def _set_rolling_days(self):
        if self.rolling_days is None:
            self.rolling_days = ROLLING_DAYS_DEFAULT

    def pre_save_hooks(self):
        self._set_rolling_days()
        super(MetricAnomaly, self).pre_save_hooks()

    def update(self):
        """
        Write sql here to update thresholds
        :return:
        """
