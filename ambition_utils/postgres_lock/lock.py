import logging

import sys
from django.db import connection, transaction
from django.db.utils import OperationalError

from ambition_utils.postgres_lock.models import PostgresLock


LOG = logging.getLogger(__name__)


class PostgresLockException(Exception):
    """
    An exception that is raised if there is an error trying to acquire the lock
    """
    pass


class PostgresLockContext(object):
    """
    Context manager for a postgres lock
    """

    def __init__(self, name, timeout=60 * 15):
        # Save the name
        self._name = name

        # Create an empty transaction
        self._transaction = None

        # Set the timeout
        self._timeout = '{0}s'.format(timeout)

        # Call the parent
        super(PostgresLockContext, self).__init__()

    def __enter__(self):
        # Log that we are trying to acquire the lock
        LOG.info('Waiting to acquire lock: {0}'.format(self._name))

        # Create the transaction
        self._transaction = transaction.atomic()

        # Build the query
        query = """
        INSERT INTO {table}(
                name,
                time
            )
            VALUES (
                %(name)s,
                now()
            )
            ON CONFLICT (name) DO UPDATE
            SET
                time = now();
        """.format(
            table=PostgresLock._meta.db_table
        )

        # Start the transaction
        self._transaction.__enter__()

        # Keep a reference to the exception
        exception = None

        # Create the connection
        with connection.cursor() as cursor:
            # Get the default timeout
            cursor.execute('SHOW statement_timeout')
            default_timeout = cursor.fetchone()[0]

            # Set the timeout
            cursor.execute('SET statement_timeout = %(timeout)s', {
                'timeout': self._timeout
            })

            # Acquire the lock
            try:
                cursor.execute(
                    query,
                    {
                        'name': self._name
                    }
                )
            except OperationalError:
                exception = PostgresLockException('Timed out waiting for lock')

            # Reset the timeout
            if exception is None:
                cursor.execute('SET statement_timeout = %(timeout)s', {
                    'timeout': default_timeout
                })

        # If we have an exception, raise it
        if exception is not None:
            self.__exit__(*sys.exc_info())
            raise exception

        # At this point we have the lock
        LOG.info('Successfully acquired lock: {0}'.format(self._name))

        # Return the transaction
        return transaction

    def __exit__(self, *args, **kwargs):
        # Complete the transaction
        if self._transaction:
            self._transaction.__exit__(*args, **kwargs)
        else:  # pragma: no cover
            pass
