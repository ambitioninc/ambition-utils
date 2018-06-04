import multiprocessing

import time

from datetime import datetime
from django.test import TransactionTestCase
from django import db

from ambition_utils.postgres_lock.lock import PostgresLockContext, PostgresLockException


def acquire_postgres_lock(queue, process_name, lock_name, lock_timeout, sleep=0):  # pragma: no cover
    try:
        with PostgresLockContext(lock_name, timeout=lock_timeout):
            # Create the start time
            start_time = datetime.utcnow()

            # Sleep for the passed amount of time
            time.sleep(sleep)

            # Get the end time
            queue.put({
                process_name: {
                    'start_time': start_time,
                    'end_time': datetime.utcnow(),
                    'exception': None
                }
            })
    except PostgresLockException as e:
        # Put the exception in the queue
        queue.put({
            process_name: {
                'start_time': None,
                'end_time': None,
                'exception': e
            }
        })


class PostgresLockTests(TransactionTestCase):
    """
    Test the postgres lock
    """

    def test_lock_context(self):
        # Create a queue for responses
        queue = multiprocessing.Queue()

        # Create the processes
        process_one = multiprocessing.Process(
            target=acquire_postgres_lock,
            kwargs={
                'queue': queue,
                'process_name': 'one',
                'lock_name': 'test',
                'lock_timeout': 60,
                'sleep': 5
            }
        )
        process_two = multiprocessing.Process(
            target=acquire_postgres_lock,
            kwargs={
                'queue': queue,
                'process_name': 'two',
                'lock_name': 'test',
                'lock_timeout': 60,
                'sleep': 5
            }
        )

        # close django's database connections to avoid multiprocess issue
        db.connections.close_all()

        # Start the processes
        process_one.start()
        time.sleep(1)
        process_two.start()

        # Wait for the processes to complete
        process_one.join()
        process_two.join()

        # Read the responses
        response = {}
        while not queue.empty():
            response.update(queue.get())

        # Assert that we acquired the lock in the correct order
        self.assertTrue(
            (response['two']['start_time'] - response['one']['start_time']).total_seconds() >= 5
        )

    def test_lock_context_session_timeout(self):
        # Create a queue for responses
        queue = multiprocessing.Queue()

        # Create the processes
        process_one = multiprocessing.Process(
            target=acquire_postgres_lock,
            kwargs={
                'queue': queue,
                'process_name': 'one',
                'lock_name': 'test',
                'lock_timeout': 1,
                'sleep': 5
            }
        )
        process_two = multiprocessing.Process(
            target=acquire_postgres_lock,
            kwargs={
                'queue': queue,
                'process_name': 'two',
                'lock_name': 'test',
                'lock_timeout': 1,
                'sleep': 5
            }
        )

        # close django's database connections to avoid multiprocess issue
        db.connections.close_all()

        # Start the processes
        process_one.start()
        time.sleep(1)
        process_two.start()

        # Wait for the processes to complete
        process_one.join()
        process_two.join()

        # Read the responses
        response = {}
        while not queue.empty():
            response.update(queue.get())

        # Assert that process two raised a proper timeout exception
        self.assertTrue(
            isinstance(response['two']['exception'], PostgresLockException)
        )
