import os
import inspect
from collections import namedtuple


class SimpleSQL(object):

    def __init__(self, relative_path_to_sql_file):
        """

        :param relative_path_to_sql_file: the relative path from the file you call this in to the sql file you
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

            connection = get_connection_function()
            params = get_params_list_or_dict()

            results = SQL('../my_sql_code').using(connection).with_params(params).as_dicts()
        """
        # get the path of the file that is calling this constructor
        frame = inspect.stack()[1]
        calling_module = inspect.getmodule(frame[0])
        calling_module_path = os.path.abspath(os.path.dirname(calling_module.__file__))

        # read the sql template from the file
        with open(os.path.join(calling_module_path, relative_path_to_sql_file)) as sql_file:
            self.template = sql_file.read()

        self._params = []
        self._raw_results = None
        self._raw_columns = None
        self._raw_connection = None

    def _run(self):
        with self._connection.cursor() as cursor:
            cursor.execute(self.template, self.kwargs)
            self._raw_results = list(cursor.fetchall())
            self._raw_columns = [col[0] for col in cursor.description]

    @property
    def connection(self):
        if self._raw_connection is None:
            from django.db import connection
            self._raw_connection = connection

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

    def using(self, connection):
        self._raw_connection = connection
        return self

    def with_params(self, params):
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

# class SQL(object):
#
#     def __init__(self, relative_path_to_sql_file, **params):
#         """
#
#         :param relative_path_to_sql_file: the relative path from the file you call this in to the sql file you
#                                           want to execute.
#         :param params: The params that will get passed into the sql template you right.
#                        See: https://www.python.org/dev/peps/pep-0249/#paramstyle
#
#         Here is an example:
#             Lets say you have directory structure
#             my_app
#               |
#               +-- my_python_code
#                      |
#                      +-- my_script.py
#               +-- my_sql_code
#                      |
#                      +-- query.sql
#
#             Then in my_app/my_python_code/my_script.py
#
#             results = SQL('../my_sql_code')[:]
#         """
#         # get the path of the file that is calling this constructor
#         frame = inspect.stack()[1]
#         calling_module = inspect.getmodule(frame[0])
#         calling_module_path = os.path.abspath(os.path.dirname(calling_module.__file__))
#
#         # read the sql template from the file
#         with open(os.path.join(calling_module_path, relative_path_to_sql_file)) as sql_file:
#             self.template = sql_file.read()
#
#         # save the params
#         self.kwargs = params
#
#         self._raw_results = None
#
#         self._raw_columns = None
#
#     def _run(self):
#         with connection.cursor() as cursor:
#             cursor.execute(self.template, self.kwargs)
#             self._raw_results = list(cursor.fetchall())
#             self._raw_columns = [col[0] for col in cursor.description]
#
#     @property
#     def _results(self):
#         if self._raw_results is None:
#             self._run()
#         return self._raw_results
#
#     @property
#     def _columns(self):
#         if self._raw_columns is None:
#             self._run()
#         return self._raw_columns
#
#     def as_tuples(self):
#         """
#         :return: Results as a list of tuples
#         """
#         return self._results
#
#     def as_dicts(self):
#         """
#         :return: Results as a list of dicts
#         """
#         return [dict(zip(self._columns, row)) for row in self._results]
#
#     def as_named_tuples(self):
#         """
#         :return: Results as a list of named tuples
#         """
#         nt_result = namedtuple('Result', self._columns)
#         return [nt_result(*row) for row in self._results]
#
#     def as_dataframe(self):
#         """
#         :return: Results as a pandas dataframe
#         """
#         try:
#             import pandas as pd
#         except ImportError:
#             raise ImportError('\n\nNope! This method requires that pandas be installed.  You know what to do.')
#
#         return pd.DataFrame(self._results, columns=self._columns)







# class SQL(object):
#     """
#     A class to run sql queries defined in files in your code
#     """
#     def __init__(self, relative_path_to_sql_file, **params):
#         """
#
#         :param relative_path_to_sql_file: the relative path from the file you call this in to the sql file you
#                                           want to execute.
#         :param params: The params that will get passed into the sql template you right.
#                        See: https://www.python.org/dev/peps/pep-0249/#paramstyle
#
#         Here is an example:
#             Lets say you have directory structure
#             my_app
#               |
#               +-- my_python_code
#                      |
#                      +-- my_script.py
#               +-- my_sql_code
#                      |
#                      +-- query.sql
#
#             Then in my_app/my_python_code/my_script.py
#
#             results = SQL('../my_sql_code').run()
#         """
#         # get the path of the file that is calling this constructor
#         frame = inspect.stack()[1]
#         calling_module = inspect.getmodule(frame[0])
#         calling_module_path = os.path.abspath(os.path.dirname(calling_module.__file__))
#
#         # read the sql template from the file
#         with open(os.path.join(calling_module_path, relative_path_to_sql_file)) as sql_file:
#             self.template = sql_file.read()
#
#         # save the params
#         self.kwargs = params
#
#     def run(self):
#         # execute the query with the params
#         with connection.cursor() as cursor:
#             cursor.execute(self.template, self.kwargs)
#             results = list(cursor.fetchall())
#         # return the results
#         return results
