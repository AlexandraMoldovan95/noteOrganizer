"""What the app may say about itself, when something goes wrong or someone
writes in.

Two readers share one definition, so they always agree: crash_log.txt, and
the feedback page that Settings → About opens in the browser. The app itself
connects to nothing -- the browser opens a page, and the person decides
whether to send it.

What is said: the version, the Windows it runs on, how it draws on this
screen, and how big the notebook is. Never what the notes say, and never a
path: a folder's path holds the person's name.
"""

import os
import platform
import sys
from datetime import datetime
from urllib.parse import urlencode

from . import paths

# The page the feedback button opens. Its form sends to the owner through the
# site's host; no address of hers appears in the app or on the page.
FEEDBACK_URL = "https://note-organizer-8f7772.netlify.app/feedback.html"

# The Microsoft Store's review page, once the app is published there. While
# it is None, the button that would open it is not shown.
STORE_REVIEW_URL = None

# Every detail there is, in the order both readers give them. The feedback
# link carries these and nothing else, and site/build.py requires the
# feedback page to have a field for each: one list, so the two cannot drift.
DETAIL_KEYS = ("version", "scale", "sharp", "theme", "notes", "files", "mb",
               "windows", "build")

# Set by the entry file as it loads, so even a crash at start-up says which
# version crashed.
version = None

# Registered by the app once its window exists, as storage.on_write_failure
# is: returns the (key, value) pairs only a running app knows. Before that --
# a crash during start-up -- the log still gets what is known without it.
app_details = None


def environment():
    """The Windows the app runs on, and whether it runs as the built .exe.

    Asked of sys.getwindowsversion, not platform: platform asks Windows'
    WMI service, 60 ms the first time (measured), and a broken WMI can stall
    -- in a crash handler, of all places. Windows 11 is build 22000 on."""
    try:
        w = sys.getwindowsversion()
        name = "11" if (w.major, w.build) >= (10, 22000) else str(w.major)
        windows = "%s (%d.%d.%d)" % (name, w.major, w.minor, w.build)
    except AttributeError:   # not Windows: the CI's Linux, a developer's machine
        windows = "not Windows: %s %s" % (platform.system(), platform.release())
    except Exception:  # noqa: BLE001 -- a report must not fail on its own facts
        windows = "unknown"
    return [("windows", windows),
            ("build", "exe" if getattr(sys, "frozen", False) else "source")]


def notebook(notes):
    """How big the notebook is: its notes, their attached files, and the
    size of the notes file in MB."""
    notes = [n for n in notes if isinstance(n, dict)]
    files = sum(len(n.get("attachments") or []) for n in notes)
    try:
        mb = round(os.path.getsize(paths.DATA_FILE) / 1e6, 1)
    except (OSError, TypeError):
        mb = None
    return [("notes", len(notes)), ("files", files), ("mb", mb)]


def details():
    """Every (key, value) pair the two readers may carry, in one order:
    the version, the running app's own details when it has registered them,
    then the environment. A key is given once, only DETAIL_KEYS names pass,
    and None means unknown."""
    out = [("version", version)]
    provider = app_details
    if provider is not None:
        try:
            out.extend(pair for pair in provider() if pair[0] != "version")
        except Exception:  # noqa: BLE001 -- see environment()
            pass
    seen = {key for key, _ in out}
    out.extend(pair for pair in environment() if pair[0] not in seen)
    return [(key, value) for key, value in out if key in DETAIL_KEYS]


def feedback_url(pairs=None):
    """The feedback page, carrying the details for the form to show and send
    -- only those DETAIL_KEYS names, whatever else *pairs* holds."""
    pairs = details() if pairs is None else pairs
    return FEEDBACK_URL + "?" + urlencode(
        [(key, value) for key, value in pairs
         if key in DETAIL_KEYS and value is not None])


def append_crash_log(kind, text, folder=None):
    """Add one entry to crash_log.txt: when, what kind of failure, the
    details above on one line, then *text*. *folder* is where the log goes;
    the data folder when not given.

    Never raises -- it runs where something has already gone wrong, and a
    start-up crash before the folder is known simply goes unlogged rather
    than taking the crash window with it.

    Returns:
        The log's path, or None when nothing could be written.
    """
    try:
        path = os.path.join(folder or paths.APP_DIR, "crash_log.txt")
        head = "--- %s%s ---" % (datetime.now().isoformat(),
                                 " (%s)" % kind if kind else "")
        facts = "  ".join("%s: %s" % (key, value)
                          for key, value in details() if value is not None)
        # errors="replace": a traceback quoting a note can carry lone
        # surrogates, and the writer must never raise over its own payload.
        with open(path, "a", encoding="utf-8", errors="replace") as f:
            f.write("\n%s\n%s\n%s\n" % (head, facts, text))
        return path
    except Exception:  # noqa: BLE001 -- see the docstring
        return None
