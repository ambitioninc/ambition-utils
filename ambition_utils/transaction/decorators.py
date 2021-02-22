import functools

from django.conf import settings
from django.db import transaction, utils


def durable(func):
    """
    https://seddonym.me/2020/11/19/trouble-atomic/
    Decorator to ensure that a function is not being called within an atomic block.
    Usage:
        @durable
        def some_function(...):
            with transaction.atomic():
               ...
    Code decorated like this is guaranteed to be *durable* - that is, not at risk of being rolled
    back due to an exception that happens after this function has completed.
    This is achieved by enforcing that:
    1. The function does not begin in the context of a currently open transaction.
    2. The function does not leave work uncommitted.
    Warning: This may not work with SQLite (which requires workarounds for bugs in the stdlib
    sqlite3 module).
    Disabling this behaviour in tests
    ---------------------------------
    This behaviour doesn't play well with tests that are wrapped in transactions.
    It can be disabled by setting DISABLE_DURABILITY_CHECKING to True in your Django settings.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        durability_checking_enabled = not getattr(
            settings, "DISABLE_DURABILITY_CHECKING", False
        )
        if durability_checking_enabled and _is_in_atomic_block():
            raise utils.ProgrammingError(
                "A durable function must not be called within a database transaction."
            )

        return_value = func(*args, **kwargs)

        if durability_checking_enabled and _db_may_have_uncommitted_work():
            # Clean up first, otherwise we may see errors later that will mask this one.
            transaction.rollback()
            raise utils.ProgrammingError(
                "A durable function must not leave work uncommitted."
            )

        return return_value

    return wrapper


def _is_in_atomic_block():
    return not transaction.get_autocommit()


def _db_may_have_uncommitted_work():
    # Django doesn't seem to provide an API to tell this, but practically speaking there shouldn't
    # be any uncommitted work if we're not in an atomic block, and autocommit is turned on.
    return not transaction.get_autocommit()
