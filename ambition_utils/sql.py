import os
import inspect
from collections import namedtuple
from django.template import Template, Context
from django.db.utils import ProgrammingError
from typing import Dict, List, Tuple, Any


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
            self.run()
        return self._raw_results

    @property
    def _columns(self):
        if self._raw_columns is None:
            self.run()
        return self._raw_columns

    def run(self):
        with self._connection.cursor() as cursor:
            cursor.execute(self.raw_sql, self._params)
            try:
                self._raw_results = list(cursor.fetchall())
                self._raw_columns = [col[0] for col in cursor.description]
            except ProgrammingError as e:
                if str(e) == 'no results to fetch':
                    self._raw_results = []
                    self._raw_columns = []
                else:  # pragma: no cover  No expected to hit this, but raise just in case
                    raise

    def using_connection(self, connection):
        self._raw_connection = connection
        return self

    def with_context(self, context: Dict[str, Any]) -> 'SQLBase':
        """
        specify a dict of django-context for rendering sql
        """
        self._django_context = context
        return self

    def with_params(self, params: Dict[str, Any]) -> 'SQLBase':
        """
        specify a list or dict of sql params
        """
        self._params = params
        return self

    def as_tuples(self) -> List[Tuple]:
        """
        :return: Results as a list of tuples
        """
        return self._results

    def as_dicts(self) -> List[Dict[str, Any]]:
        """
        :return: Results as a list of dicts
        """
        return [dict(zip(self._columns, row)) for row in self._results]

    def as_named_tuples(self, named_tuple_name='Result') -> List[Any]:
        """
        :return: Results as a list of named tuples
        """
        # Ignore typing in here because of unconventional namedtuple usage
        nt_result = namedtuple(named_tuple_name, self._columns)  # type: ignore
        return [nt_result(*row) for row in self._results]  # type: ignore

    def as_dataframe(self) -> Any:
        """
        :return: Results as a pandas dataframe
        """
        try:
            import pandas as pd
        except ImportError:  # pragma: no cover.  Not going to uninstall pandas to test this
            raise ImportError('\n\nNope! This method requires that pandas be installed.  You know what to do.')

        return pd.DataFrame(self._results, columns=self._columns)

    def to_tuples(self) -> List[Tuple]:
        """
        alias
        """
        return self.as_tuples()

    def to_dicts(self) -> List[Dict[str, Any]]:
        """
        alias
        """
        return self.as_dicts()

    def to_named_tuples(self) -> List[Any]:
        """
        alias
        """
        return self.as_named_tuples()

    def to_dataframe(self) -> Any:
        """
        alias
        """
        return self.as_dataframe()


class FileSQL(SQLBase):
    def __init__(
            self,
            path_to_sql_file: str,
            path_is_relative: bool = True
    ) -> None:
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
    def __init__(
            self,
            sql_query_string: str
    ) -> None:
        """
        Simple wrapper to execute a sql query against django models
        and provide the results as different object types.
        """
        super(StringSQL, self).__init__()
        self._raw_sql = sql_query_string
