import tempfile
import os
from django.test import TestCase
from ambition_utils.tests.models import FakeModel
from ambition_utils.sql import StringSQL, FileSQL, queryset_to_sql


class TestSQL(TestCase):
    def setUp(self):
        self.simple_query = 'SELECT * FROM tests_fakemodel;'
        self.param_query = 'SELECT * FROM tests_fakemodel WHERE name=%(name)s;'
        self.context_query = 'SELECT * FROM {{table}};'
        self.insert_query = "INSERT INTO tests_fakemodel (id, name) VALUES (DEFAULT, 'newname')"
        for nn in range(1, 4):
            FakeModel(name=f'n_{nn}').save()

    def test_tuples(self):
        sql = StringSQL(self.simple_query)
        tups = sql.to_tuples()
        self.assertEqual({t[1] for t in tups}, {'n_1', 'n_2', 'n_3'})

    def test_dataframe(self):
        sql = StringSQL(self.simple_query)
        sql.using_connection(sql._connection)
        df = sql.to_dataframe()
        self.assertEqual(self.simple_query, sql.raw_sql)
        self.assertEqual(set(df.name), {'n_1', 'n_2', 'n_3'})

    def test_no_return(self):
        sql = StringSQL(self.insert_query)
        df = sql.to_dataframe()
        self.assertTrue(df.empty)

    def test_params_named_tuples(self):
        sql = StringSQL(self.param_query)
        sql.with_params(dict(name='n_1'))
        tups = sql.to_named_tuples()
        self.assertEqual({t.name for t in tups}, {'n_1'})

    def test_context_dicts(self):
        sql = StringSQL(self.context_query)
        sql.with_context(dict(table='tests_fakemodel'))
        tups = sql.to_dicts()
        self.assertEqual({t['name'] for t in tups}, {'n_1', 'n_2', 'n_3'})

    def test_abs_file_sql(self):
        with tempfile.NamedTemporaryFile('w') as query_file:
            query_file.write(self.simple_query)
            query_file.flush()

            sql = FileSQL(query_file.name, path_is_relative=False)
            df = sql.to_dataframe()
            self.assertEqual(set(df.name), {'n_1', 'n_2', 'n_3'})

            # Run query twice to use some cache hits
            df = sql.to_dataframe()
            self.assertEqual(set(df.name), {'n_1', 'n_2', 'n_3'})

    def test_rel_file_sql(self):
        with tempfile.NamedTemporaryFile('w') as query_file:
            query_file.write(self.simple_query)
            query_file.flush()

            rel_path = os.path.relpath(query_file.name, os.path.realpath(__file__))
            sql = FileSQL(rel_path, path_is_relative=True)
            df = sql.to_dataframe()
            self.assertEqual(set(df.name), {'n_1', 'n_2', 'n_3'})

    def test_queryset_to_sql(self):
        # Build a query
        qs = FakeModel.objects.order_by('name').values('name')

        # Get the postgres sql for that query
        query = queryset_to_sql(qs)

        # Run the postgres sql
        sql = StringSQL(query)
        sql_recs = sql.as_dicts()

        # Now run the acutal query
        qs_recs = list(qs)

        # Make sure they are the same
        self.assertEqual(
            [r['name'] for r in sql_recs],
            [r['name'] for r in qs_recs],
        )
