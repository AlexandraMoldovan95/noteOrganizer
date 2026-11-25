"""What the app may say about itself when something goes wrong, the pages
it opens in the browser, and the licenses file it ships with.

crash_log.txt says it, on this computer only. Under each entry's dated head,
one line gives the version, the Windows it runs on, how it draws on this
screen, and how big the notebook is: never what the notes say, and never a
path, since a folder's path holds the person's name. The trace below it is
Python's own, and can hold both. The app connects to nothing: the Store's
reviews and the privacy policy on Google Sites open in the browser.
"""

import os
import platform
import sys
from datetime import datetime

from . import paths

# The privacy policy, opened from Settings → About and given to both stores.
# docs/PRIVACY.md is its text; the owner copies it to this page by hand.
PRIVACY_URL = "https://sites.google.com/view/noteorganizer-privacy"

# Said under the version in Settings → About: the MIT license's "as is",
# where people who install from a store, and never see LICENSE, read it.
ABOUT_TERMS = ("Free software under the MIT license, provided as is. "
               "Keep a backup of your notes.")

# The licenses of everything the built app carries, opened from About.
# tools/make_third_party_notices.py writes it; NoteOrganizer.spec ships it.
NOTICES = "THIRD_PARTY_NOTICES.txt"

# The app's review page in the Microsoft Store (docs/STORE_LISTING.md), which
# About's Feedback card opens. A copy built with None has no Feedback card:
# reviews are the only way in.
STORE_REVIEW_URL = "ms-windows-store://review/?ProductId=9NBS2548QTXF"

# Every detail a crash log entry carries, in its order.
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
    """Every (key, value) pair a crash log entry may carry, in one order:
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


def append_crash_log(kind, text, folder=None):
    """Add one entry to crash_log.txt: when, what kind of failure, the
    details above on one line, then *text*. *folder* is where the log goes;
    the data folder when not given. Never raises -- it runs where something
    has already gone wrong, and a start-up crash before the folder is known
    goes unlogged rather than taking the crash window with it.

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
