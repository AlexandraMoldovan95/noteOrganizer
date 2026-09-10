"""One notebook, one app — an advisory lock on the data directory.

WHY THIS EXISTS
---------------
The whole notebook is read into memory once at startup and written back
whole on every save. That is a perfectly good design for one process and
a data-shredder for two: open the app twice (a taskbar pin, the Start
menu while the window is minimised, a second double-click of the ``.exe``
— all one careless moment) and both windows hold their own copy of the
same file. Whichever autosaves last wins, and everything the other window
wrote that session is gone, silently, with both windows still cheerfully
showing it on screen.

There was no guard of any kind before: no lock, no mtime check, no reload.
A product reviewer reproduced the loss with two real windows in under a
minute.

WHY A FILE LOCK RATHER THAN A PID FILE
--------------------------------------
A PID file has to answer "is that process still alive?", which is a
different, worse question on every platform — and it goes stale the
moment the app is killed rather than closed, leaving the user locked out
of their own notes. An OS file lock is released by the kernel when the
process dies, however it dies, so a crash cannot strand anybody.

``msvcrt`` on Windows and ``fcntl`` elsewhere; both are standard library,
which keeps the app's one-dependency promise.

THE DELIBERATE FAILURE MODE
---------------------------
If the lock cannot be created at all — a read-only folder, an exotic
filesystem — this reports success. Refusing to start because a *lock*
failed would turn a cosmetic problem into "the app won't open", which is
worse than the risk it guards against. The lock is advisory: it stops the
ordinary accident, not a determined user.
"""

import os

from . import paths

LOCK_FILENAME = ".notebook.lock"

_held = None


def _lock_path():
    return os.path.join(paths.APP_DIR or ".", LOCK_FILENAME)


def acquire(path=None):
    """Take the notebook lock. True if this process owns it.

    Already owning it counts as success, so a second window inside the
    SAME process (the qa scripts build several) is never blocked — the
    guard is about two processes, which is the case that loses data.
    """
    global _held
    if _held is not None:
        return True
    target = path or _lock_path()
    try:
        handle = open(target, "a+")
    except (IOError, OSError):
        return True  # see "the deliberate failure mode" above
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        try:
            handle.close()
        except (IOError, OSError):
            pass
        return False
    _held = handle
    return True


def release():
    """Give the lock up early. The OS does this on exit anyway; this is
    for tests and for a clean handover."""
    global _held
    if _held is None:
        return
    handle, _held = _held, None
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError):
        pass
    try:
        handle.close()
    except (IOError, OSError):
        pass


def held():
    """Whether this process currently holds the lock."""
    return _held is not None
