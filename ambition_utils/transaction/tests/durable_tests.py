from django.db import transaction, utils
from django.test.testcases import TestCase
from mock import patch

from ambition_utils.transaction import durable
from ambition_utils.transaction import decorators
from ambition_utils.transaction.utils import DurableResetAtomicForTestingPatcher


class DurableTests(TestCase):
    def setUp(self):
        # Call the parent setup which starts the transaction
        super().setUp()

        # Patch our atomic so we think we have not yet started a transaction
        patcher = DurableResetAtomicForTestingPatcher()
        patcher.start()

        # Add cleanup to stop the patches
        self.addCleanup(patcher.stop)

    def test_nested_atomic_yields_exception(self):
        """
        Verifies that a function wrapped in transaction.durable will yield an exception in a nested transaction
        """

        @transaction.atomic
        def bad_consumer():
            print('Running func')
            test_function()

        self.assertRaises(utils.ProgrammingError, bad_consumer)

    def test_correct_usage(self):
        """
        Verifies that a function wrapped in transaction.durable will not be nested in a transaction
        """
        def test_durable_method():
            # Returns true if the function is in a transaction
            return decorators._is_in_atomic_block()

        self.assertFalse(test_function(test_durable_method))

    @patch('ambition_utils.transaction.decorators.transaction.rollback')
    @patch('ambition_utils.transaction.decorators._db_may_have_uncommitted_work')
    def test_hanging_transaction(self, mock_db_may_have_uncommitted_work, mock_rollback):
        """
        Verify that an exception is raised if we have uncommitted work
        """
        mock_db_may_have_uncommitted_work.return_value = True

        self.assertRaises(utils.ProgrammingError, test_function)
        mock_rollback.assert_called_once_with()


@durable
def test_function(callback=None):
    if callback is not None:
        return callback()
