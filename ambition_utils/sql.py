import os
import inspect
from collections import namedtuple
from django.template import Template, Context


class SQLBase(object):

    def __init__(self):
        self._raw_sql = None
        self._params = []
        self._raw_results = None
        self._raw_columns = None
        self._raw_connection = None
        self._django_context = None
        self._raw_sql = None
        self._rendered_sql = None

    @property
    def raw_sql(self):
        if self._rendered_sql is None:
            if self._django_context is not None:
                template = Template(self._raw_sql)
                self._rendered_sql = template.render(context=Context(self._django_context))
            else:
                self._rendered_sql = self._raw_sql
        return self._rendered_sql

    @property
    def _connection(self):
        if self._raw_connection is None:
            from django.db import connection
            self._raw_connection = connection
        return self._raw_connection

    @property
    def _results(self):
        if self._raw_results is None:
            self._run()
        return self._raw_results

    @property
    def _columns(self):
        if self._raw_columns is None:
            self._run()
        return self._raw_columns

    def _run(self):
        with self._connection.cursor() as cursor:
            print '~'*80
            print self.raw_sql
            print '~'*80
            cursor.execute(self.raw_sql, self._params)
            self._raw_results = list(cursor.fetchall())
            self._raw_columns = [col[0] for col in cursor.description]

    def using_connection(self, connection):
        self._raw_connection = connection
        return self

    def with_context(self, context):
        """
        specify a dict of django-context for rendering sql
        """
        self._django_context = context

    def with_params(self, params):
        """
        specify a list or dict of sql params
        """
        self._params = params
        return self

    def as_tuples(self):
        """
        :return: Results as a list of tuples
        """
        return self._results

    def as_dicts(self):
        """
        :return: Results as a list of dicts
        """
        return [dict(zip(self._columns, row)) for row in self._results]

    def as_named_tuples(self):
        """
        :return: Results as a list of named tuples
        """
        nt_result = namedtuple('Result', self._columns)
        return [nt_result(*row) for row in self._results]

    def as_dataframe(self):
        """
        :return: Results as a pandas dataframe
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError('\n\nNope! This method requires that pandas be installed.  You know what to do.')

        return pd.DataFrame(self._results, columns=self._columns)


class FileSQL(SQLBase):
    def __init__(self, path_to_sql_file, path_is_relative=True):
        """

        :param path_to_sql_file: the relative path from the file you call this in to the sql file you
                                 want to execute.
        :param params: The params that will get passed into the sql template you right.
                       See: https://www.python.org/dev/peps/pep-0249/#paramstyle

        Here is an example:
            Lets say you have directory structure
            my_app
              |
              +-- my_python_code
                     |
                     +-- my_script.py
              +-- my_sql_code
                     |
                     +-- query.sql

            Then in my_app/my_python_code/my_script.py

            # These can be optionally passed to the SimpleSql object
            connection = get_my_connection_function()
            params = get_my_params_list_or_dict()

            # run simple query with no params and return the results as dicts
            SQL('../my_sql_code.sql').as_dicts()

            # run sql with a custom connection and parameters retrieving results as dataframe
            # note that the abolute path to sql file is now specified
            sql = SQL('/Users/billybob/my_sql_code.sql', path_is_relative=False)
            sql.using(connection)
            sql.with_params(params)
            df = sql.as_dataframe()

            # exact same command as above, but chained as a one-liner
            results = SQL('../my_sql_code.sql').using(connection).with_params(params).as_dataframe()

            # print the raw sql template
            print(sql.raw_sql)
        """
        super(FileSQL, self).__init__()
        # get the path of the file that is calling this constructor
        frame = inspect.stack()[1]
        calling_module = inspect.getmodule(frame[0])
        calling_module_path = os.path.abspath(os.path.dirname(calling_module.__file__))

        # read the sql template from the file
        if path_is_relative:
            path_to_sql_file = os.path.join(calling_module_path, path_to_sql_file)

        self._path_to_sql_file = path_to_sql_file

        with open(os.path.realpath(path_to_sql_file)) as sql_file:
            self._raw_sql = sql_file.read()


class StringSQL(SQLBase):
    def __init__(self, sql_query_string):
        """
        Simple wrapper to execute a sql query against django models
        and provide the results as different object types.
        """
        super(StringSQL, self).__init__()
        self._raw_sql = sql_query_string
