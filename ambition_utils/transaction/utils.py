from contextlib import contextmanager
from django.db import transaction

from ambition_utils.transaction import decorators


@contextmanager
def durable_reset_atomic_for_testing():  # pragma: no cover
    """
    A context manager for resetting the durable state for easier testing of a durable
    function inside of a transaction test case.
    This is only meant to be used for testing and never inside of production code.

    Any code wrapped in this will be tricked into thinking its not in a current
    transaction and will only keep track of new transactions created moving forward.
    This will allow us to bypass the initial transaction created by the test case and
    only care about those created from the actual code block
    """

    # Keep track of the original methods
    original_atomic_enter = transaction.Atomic.__enter__
    original_atomic_exit = transaction.Atomic.__exit__
    original_is_in_atomic_block = decorators._is_in_atomic_block
    original_db_may_have_uncommitted_work = decorators._db_may_have_uncommitted_work
    transactions = []

    # Create patch methods
    def patch_atomic_enter(*args, **kwargs):
        transactions.append((args, kwargs))
        return original_atomic_enter(*args, **kwargs)

    def patch_atomic_exit(*args, **kwargs):
        if len(transactions):
            transactions.pop()
        return original_atomic_exit(*args, **kwargs)

    def patch_is_in_atomic_block():
        if len(transactions):
            return original_is_in_atomic_block()
        return False

    def patch_db_may_have_uncommitted_work():
        return patch_is_in_atomic_block()

    # Patch the methods
    transaction.Atomic.__enter__ = patch_atomic_enter
    transaction.Atomic.__exit__ = patch_atomic_exit
    decorators._is_in_atomic_block = patch_is_in_atomic_block
    decorators._db_may_have_uncommitted_work = patch_db_may_have_uncommitted_work

    # Run the wrapped method
    yield True

    # Restore the patched methods
    transaction.Atomic.__enter__ = original_atomic_enter
    transaction.Atomic.__exit__ = original_atomic_exit
    decorators._is_in_atomic_block = original_is_in_atomic_block
    decorators._db_may_have_uncommitted_work = original_db_may_have_uncommitted_work


class DurableResetAtomicForTestingPatcher:  # pragma: no cover
    """
    A patcher for testing durable atomic blocks in a transaction test case
    """

    def __init__(self):
        self.patcher = None

    def start(self):
        self.patcher = durable_reset_atomic_for_testing()
        self.patcher.__enter__()

    def stop(self):
        if self.patcher:
            self.patcher.__exit__(None, None, None)
