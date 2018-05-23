import datetime
import sys

from django.test import TestCase
from django.db import IntegrityError
from freezegun import freeze_time

from ambition_utils.anomaly.tests.models import IncrementalAnomaly, NonIncrementalAnomaly, FloatModel
from ambition_utils.anomaly.models import BadAnomalyType, BadPercentileValue


class NonIncrementalAnomalyTest(TestCase):
    def setUp(self):

        inserts = [FloatModel(value=nn) for nn in range(1, 101)]
        FloatModel.objects.bulk_create(inserts)

        NonIncrementalAnomaly.objects.create(name='non_incremental')

    def test_base_case(self):

        detector = NonIncrementalAnomaly.objects.get(name='non_incremental')
        detector.update()

        values = sorted(FloatModel.objects.all().values_list('value', flat=True))
        outliers = detector.detect(values)

        lows = {t[0] for t in zip(values, outliers) if t[1] == -1}
        highs = {t[0] for t in zip(values, outliers) if t[1] == 1}

        self.assertEqual(lows, {1, 2, 3, 4, 5})
        self.assertEqual(highs, {97, 98, 99, 100})


class IncrementalAnomalyTest(TestCase):
    def setUp(self):

        inserts = [FloatModel(value=nn) for nn in range(1, 101)]
        FloatModel.objects.bulk_create(inserts)

        IncrementalAnomaly.objects.create(name='incremental')

    def test_base_case(self):

        detector = IncrementalAnomaly.objects.get(name='incremental')

        values = FloatModel.objects.all().values_list('value', flat=True)
        detector.update(values)
        detector.save()

        outliers = detector.detect(values)

        lows = {t[0] for t in zip(values, outliers) if t[1] == -1}
        highs = {t[0] for t in zip(values, outliers) if t[1] == 1}

        self.assertEqual(lows, {1, 2, 3, 4, 5})
        self.assertEqual(highs, {96, 97, 98, 99, 100})


class IncrementalLimitedRangeTest(TestCase):
    def setUp(self):

        inserts = [FloatModel(value=nn % 4) for nn in range(1, 101)]
        FloatModel.objects.bulk_create(inserts)

        IncrementalAnomaly.objects.create(name='incremental')

    def test_base_case(self):
        detector = IncrementalAnomaly.objects.get(name='incremental')
        values = [nn % 4 for nn in range(1, 101)]
        detector.update(values)
        detector.save()

        self.assertEqual(detector.detect(list(range(-1, 6))), [-1, 0, 0, 0, 0, 1, 1])


class IncrementalRareEventTest(TestCase):
    def setUp(self):

        inserts = [FloatModel(value=nn % 4) for nn in range(1, 101)]
        # FloatModel.objects.bulk_create(inserts)
        for nn, insert in enumerate(inserts):
            if nn in [10, 11, 12]:
                inserts[nn].value = 5
            inserts[nn].save()

        IncrementalAnomaly.objects.create(name='incremental')
        self.inserts = inserts

    def test_base_case(self):
        detector = IncrementalAnomaly.objects.get(name='incremental')
        values = [m.value for m in self.inserts]
        for v in values:
            detector.update(v, reset_threshold=True)
        # detector.update(values)
        detector.save()
        anomalies = [detector.detect(v) for v in values]
        outliers = [t[0] for t in zip(values, anomalies) if t[1] != 0]
        self.assertEqual(outliers, [5, 5, 5])


class UnprocessedAnomalyTests(TestCase):
    def test_duplicate_uids_not_allowed(self):
        IncrementalAnomaly.objects.create(name='a')
        with self.assertRaises(IntegrityError):
            IncrementalAnomaly.objects.create(name='a')

    def test_get_unprocessed(self):
        names = ['a{}'.format(nn) for nn in range(5)]

        for nn, name in enumerate(names):
            detector = IncrementalAnomaly(name=name)
            if nn > 2:
                with freeze_time(datetime.datetime.utcnow() - datetime.timedelta(days=2)):
                    detector.save()
            else:
                detector.save()

        self.assertEqual({d.uid for d in IncrementalAnomaly.objects.unprocessed()}, {'a3', 'a4'})
        self.assertEqual(
            {
                d.uid for d in IncrementalAnomaly.objects.unprocessed(
                    assume_now=datetime.datetime.utcnow() + datetime.timedelta(days=2)
                )
            },
            {'a0', 'a1', 'a2', 'a3', 'a4'}
        )


class AnomalyUnitTests(TestCase):
    def test_zero_counts(self):
        inc_detector = IncrementalAnomaly.objects.get_or_create(name='non_incremental')[0]
        non_inc_detector = NonIncrementalAnomaly.objects.get_or_create(name='non_incremental')[0]

        self.assertEqual(inc_detector.count, 0)
        self.assertEqual(non_inc_detector.count, 0)

    def test_count_setting(self):
        inc_detector = IncrementalAnomaly.objects.get_or_create(name='non_incremental')[0]
        non_inc_detector = NonIncrementalAnomaly.objects.get_or_create(name='non_incremental')[0]

        non_inc_detector.count = 7
        non_inc_detector.save()
        self.assertEqual(NonIncrementalAnomaly.objects.get(name=non_inc_detector.uid).count, 7)

        with self.assertRaises(ValueError):
            inc_detector.count = 7

    def test_unassigned_percentiles(self):
        detector = NonIncrementalAnomaly(name='non_incremental')
        self.assertEqual(detector.min_num_points_high, sys.maxsize)
        self.assertEqual(detector.min_num_points_low, sys.maxsize)

    def test_bad_update(self):
        detector = IncrementalAnomaly(name='non_incremental')
        detector.IS_INCREMENTAL = False
        with self.assertRaises(BadAnomalyType):
            detector.update(7)

    def test_bad_percentiels(self):
        detector = IncrementalAnomaly(
            name='non_incremental',
            percentile_high=30,
            percentile_low=1
        )
        with self.assertRaises(BadPercentileValue):
            detector.save()

        detector = IncrementalAnomaly(
            name='non_incremental',
            percentile_high=90,
            percentile_low=60
        )
        with self.assertRaises(BadPercentileValue):
            detector.save()
