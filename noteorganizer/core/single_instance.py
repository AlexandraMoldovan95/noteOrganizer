"""One notebook, one app — an advisory lock on the data directory.

The notebook is read whole at start and written whole at every save, so two
windows on one folder lose whatever the first saved. A file lock, not a PID
file: the kernel releases it however the process dies, so a crash strands
nobody (``msvcrt`` / ``fcntl``, standard library). The deliberate failure
mode: a lock that cannot be *taken* for any reason but "another process
holds it" -- a read-only folder, a filesystem with no byte-range locks --
reports success, as refusing to start would be worse than the risk. The
story: ISSUES_LOG: "Two windows, one file, and the last one to autosave wins".
"""

import errno
import os
import time

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
    for attempt in range(3):
        try:
            handle = open(target, "a+")
            break
        except (IOError, OSError) as exc:
            # A sharing violation (open() says EACCES, the C runtime's errno)
            # is another program holding the file a moment: tried again, as
            # the data files are, failing open let a second window in.
            if (getattr(exc, "winerror", None) != 32
                    and getattr(exc, "errno", None) != errno.EACCES) or attempt == 2:
                return True  # see "the deliberate failure mode" above
            time.sleep(0.5)
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError) as exc:
        try:
            handle.close()
        except (IOError, OSError):
            pass
        # Only "another process holds this byte" refuses: msvcrt's EACCES or
        # EDEADLK, fcntl's EAGAIN/EWOULDBLOCK. Any other errno is a filesystem
        # that cannot lock at all, which fails open (the module docstring).
        if getattr(exc, "errno", None) in (errno.EACCES, errno.EAGAIN,
                                           errno.EWOULDBLOCK, errno.EDEADLK):
            return False
        return True
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
