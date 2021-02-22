from unittest import TestCase

from django.db import transaction, utils
from mock import patch

from ambition_utils.transaction import durable


class DurableTests(TestCase):

    def test_nested_atomic_yields_exception(self):
        """
        Verifies that a function wrapped in transaction.durable will yield an exception in a nested transaction
        """
        @transaction.atomic
        def bad_consumer():
            test_function()

        self.assertRaises(utils.ProgrammingError, bad_consumer)

    def test_correct_usage(self):
        """
        Verifies that a function wrapped in transaction.durable will not be nested in a transaction
        """
        def test_durable_method():
            # Returns true if the function is in a transaction
            return not transaction.get_autocommit()

        self.assertFalse(test_function(test_durable_method))

    @patch('ambition_utils.transaction.decorators.transaction')
    def test_hanging_transaction(self, mock_transaction):
        """
        Verify that an exception is raised if we have uncommitted work
        """
        mock_transaction.get_autocommit.side_effect = [
            True,
            False,
        ]

        self.assertRaises(utils.ProgrammingError, test_function)
        mock_transaction.rollback.assert_called_once_with()


@durable
def test_function(callback=None):
    if callback is not None:
        return callback()
