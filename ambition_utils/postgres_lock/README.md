A convenient way to use postgres database row level locking as a lock.

Caveats
-------
 - Only works with postgres database.
 - All code that runs while the lock is acquired is inside a transaction
