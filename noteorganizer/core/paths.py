"""Where the app's data lives, and how it gets moved there safely.

WHAT THIS MODULE IS FOR
-----------------------
Deciding which folder holds ``notes_data.json`` and friends, migrating
data forward from older locations, and cleaning up leftovers - carefully.

**Importing this module does nothing.** Every function here has to be
called deliberately. That matters: these are the functions that move and
delete a user's notes, and for a long time they ran as a side effect of
importing the app, which is how a real notebook once got deleted (see
`docs/ISSUES_LOG.md`, "The cleanup that deleted the real notebook").
``note_organizer.py`` no longer calls them at import either: they run from
``note_organizer.initialise()``, which the app and the entry point invoke.
Importing the app is now inert too.

TWO SITUATIONS, HANDLED DIFFERENTLY
-----------------------------------
* **Run as a .py script (development)** - data sits beside the script, so
  ``notes_data.json`` is right there in the project folder.
* **Run as a .exe (distributed)** - data goes to the app's own folder
  under ``%APPDATA%``, which is per-user, always writable, and never
  cleaned up by Windows. A one-file exe unpacks into a temp folder Windows
  later deletes, and places like Program Files may be read-only, so
  writing beside the exe is unreliable.

:func:`resolve_data_dir` picks between them and, importantly, *proves* the
folder is writable by actually writing a probe file. Existence is not
enough - Program Files exists too.

THE IDEA WORTH TAKING AWAY: BACK UP BEFORE YOU DESTROY
------------------------------------------------------
:func:`run_migrations` never overwrites a file it has not copied first.
If the backup fails the migration **aborts** rather than pressing on
hopefully - losing a migration is recoverable, losing the notes is not.

:func:`purge_stale_copies` deletes leftover folders, and is the most
dangerous function in this codebase. Two rules constrain it:

1. It only removes files it recognises as its own
   (:data:`OWNED_FILENAMES`, :data:`OWNED_PREFIXES`) - never a file the
   user happened to put there.
2. The app's folder under ``%APPDATA%`` is **permanently exempt**, however
   redundant it looks. It is the durable store the distributed app reads
   from. Treating it as just another disposable leftover is exactly what
   deleted a real notebook once; the exemption is not an optimisation to
   be tidied away later.

:func:`is_redundant_copy` is the judgement behind that: a folder counts as
redundant only if every note in it is already present locally *and* its
attachments are covered too. Content is compared by signature rather than
by counting files, so "10 notes here, 10 notes there" is never mistaken
for "the same 10 notes".
"""

import filecmp
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime


# ---- Storage location ----
#
# Two very different situations, deliberately handled differently:
#
#   Running as a .py script (development)  -> data sits beside the script, so
#       notes_data.json is right there in the project folder while coding.
#
#   Running as a .exe (distributed)        -> data goes in %APPDATA%\NoteOrganizer,
#       a per-user folder that is ALWAYS writable and NEVER cleaned up by
#       Windows. This is what fixes the "notes vanish on another PC" bug: a
#       --onefile exe unpacks into a temporary folder that Windows deletes on
#       exit, and folders like Downloads or Program Files may be read-only, so
#       writing next to the exe is unreliable. %APPDATA% is neither.

def get_appdata_dir():
    """Per-user application data folder for this app."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "NoteOrganizer")


def bundled_file(*parts):
    """An absolute path to a file that ships WITH the app, not with the
    user's data.

    Two different places depending on how the app is running, which is
    the whole reason this exists: from source it is beside this package,
    and inside a PyInstaller build it is the temporary folder the bundle
    unpacks itself into (``sys._MEIPASS``). The path comes back whether
    or not anything is there -- the caller decides what a missing
    resource means, and for the window icon it means "carry on without
    one".
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def _is_writable(folder):
    """True if we can actually create a file here. Existence isn't enough —
    Program Files exists too, but writing to it silently fails.

    The probe's name is this call's own. It used to be one fixed name, and
    two launches probing the same folder at the same moment -- a second
    double-click on a slow PC -- collided: a sharing violation, or the
    other launch had already deleted it. Measured at nearly half of all
    overlapping probes answering "not writable", which sent a launch off
    to a fallback folder while its twin locked the real one (see _main).
    Removing the probe is tidiness, not proof: creating and writing it
    already answered the question."""
    try:
        os.makedirs(folder, exist_ok=True)
        handle, probe = tempfile.mkstemp(prefix=".write_test_", dir=folder)
    except (IOError, OSError):
        return False
    try:
        with os.fdopen(handle, "w") as f:
            f.write("ok")
        writable = True
    except (IOError, OSError):
        writable = False
    try:
        os.remove(probe)
    except OSError:
        pass
    return writable


def resolve_data_dir(script_dir):
    """Pick the data folder, guaranteeing it's writable.

    Args:
        script_dir: Where "beside the app" means — the folder holding the
            entry-point script. It is passed in rather than derived from
            this module's own ``__file__``, which used to be how it worked
            while this code lived in ``note_organizer.py``. Once the code
            moved into a package, ``__file__`` started pointing at
            ``noteorganizer/core/`` and the app quietly chose a data folder
            two levels below the real one. Taking it as an argument means
            the answer can't change again just because this file moves.
            Ignored when running as a frozen ``.exe``, which always uses
            the per-user AppData folder.

    Returns:
        ``(folder, note)`` where *note* is a user-facing warning if we had
        to fall back from the preferred location, else ``None``.
    """
    if getattr(sys, "frozen", False):
        # Distributed app: always per-user AppData.
        appdata = get_appdata_dir()
        if _is_writable(appdata):
            return appdata, None
        # Extremely rare (locked-down AppData). Fall back to the exe's folder,
        # then to the temp dir, so the app still runs instead of dying.
        exe_dir = os.path.dirname(sys.executable)
        if _is_writable(exe_dir):
            return exe_dir, (
                "Your Windows profile folder isn't writable, so notes are being "
                "saved next to the app instead. They'll persist, but move the app "
                "out of Downloads/Program Files if notes ever go missing."
            )
        tmp = os.path.join(tempfile.gettempdir(), "NoteOrganizer")
        return tmp, (
            "Couldn't find a permanent place to save notes on this PC, so a "
            "temporary folder is being used. Export your notes regularly — "
            "temporary files can be cleared by Windows."
        )

    # Development: run as a script -> beside the entry-point .py file.
    script_dir = os.path.abspath(script_dir)
    if _is_writable(script_dir):
        return script_dir, None
    # If even that isn't writable, don't lose the user's data — use AppData.
    return get_appdata_dir(), None


def get_legacy_dirs(app_dir):
    """Other folders this app has historically written to, so old notes can be
    brought forward on first run of a new version."""
    candidates = []
    # The other run-mode's folder (so switching between script and exe, or
    # upgrading from an older build, still finds prior notes).
    candidates.append(get_appdata_dir())
    if getattr(sys, "frozen", False):
        candidates.append(os.path.dirname(sys.executable))
        exe_dir = os.path.dirname(sys.executable)
        if os.path.basename(exe_dir).lower() in ("dist", "noteorganizer"):
            candidates.append(os.path.dirname(exe_dir))
    else:
        candidates.append(os.path.join(app_dir, "dist"))
        candidates.append(os.path.join(app_dir, "dist", "NoteOrganizer"))
    return [d for d in candidates
            if os.path.isdir(d) and os.path.abspath(d) != os.path.abspath(app_dir)]


def count_notes_in(path):
    """How many notes a candidate notes_data.json holds (0 if unreadable)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else 0
    except (json.JSONDecodeError, IOError, OSError):
        return 0


def _copy_attachments(src_dir, dest_dir):
    src_attach = os.path.join(src_dir, "attachments")
    if not os.path.isdir(src_attach):
        return
    os.makedirs(dest_dir, exist_ok=True)
    for filename in os.listdir(src_attach):
        src = os.path.join(src_attach, filename)
        dst = os.path.join(dest_dir, filename)
        if os.path.isfile(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except (IOError, OSError):
                pass


def _timestamped_backup(path, label):
    """Copy a file aside before it gets overwritten. Returns the new path."""
    if not os.path.exists(path):
        return None
    folder = os.path.dirname(path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(folder, f"notes_data_{label}_{stamp}.json")
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except (IOError, OSError):
        return None


def preserve_corrupt_file(path):
    """Copy an unreadable data file aside before anything can overwrite it.

    A file that exists but cannot be parsed still holds the user's bytes —
    and the very next write would replace it with whatever the caller has,
    turning a recoverable corruption into a permanent loss. The copy is
    timestamped, sits beside the original, matches no OWNED_* pattern (so
    no cleanup can ever remove it), and is never auto-deleted.

    Lives here rather than in storage.py because the pre-configure
    migration code below needs it too, and paths cannot import storage
    back. storage re-exports it as its own ``_preserve_corrupt``.

    Returns:
        The copy's path, or None if even the copy failed.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root, ext = os.path.splitext(path)
    backup_path = f"{root}_corrupt_{stamp}{ext or '.json'}"
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except (IOError, OSError):
        return None


def _preserve_settings_if_unreadable(settings_path):
    """Before migration code overwrites settings.json, keep its bytes if it
    exists but holds no usable dict — the reclaim path used to clobber a
    corrupt settings file with no trace at all."""
    if not os.path.exists(settings_path):
        return
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            if isinstance(json.load(f), dict):
                return
    except (json.JSONDecodeError, IOError, OSError):
        pass
    preserve_corrupt_file(settings_path)


def run_migrations(app_dir):
    """Bring data into app_dir from wherever a previous version left it.

    Two cases, in priority order:
      1. The previous version stored everything in %APPDATA%\\NoteOrganizer.
         That copy is authoritative (it has already been de-duplicated), so it
         wins over whatever stale file is sitting in the project folder — but
         the stale file is backed up first, never silently destroyed.
      2. Fresh install with nothing here yet: pull from the richest legacy
         folder found (e.g. an old dist\\ copy).

    Returns a short description of what happened, or None."""
    notes_path = os.path.join(app_dir, "notes_data.json")
    settings_path = os.path.join(app_dir, "settings.json")
    attachments_path = os.path.join(app_dir, "attachments")

    def _settings():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, IOError, OSError):
            return {}

    # --- Case 1: reclaim data from %APPDATA% ---
    appdata_dir = get_appdata_dir()
    appdata_notes = os.path.join(appdata_dir, "notes_data.json")
    already_done = _settings().get("reclaimed_from_appdata")

    if (not already_done
            and os.path.abspath(appdata_dir) != os.path.abspath(app_dir)
            and os.path.exists(appdata_notes)
            and count_notes_in(appdata_notes) > 0):

        notes_path_existed = os.path.exists(notes_path)
        displaced = _timestamped_backup(notes_path, "replaced")
        if notes_path_existed and not displaced:
            # A local file existed but backing it up failed (disk full,
            # permissions, locked by something else) — don't risk an
            # unprotected overwrite. Leave things as they are and try
            # again next launch instead of proceeding blind.
            return None
        moved = count_notes_in(appdata_notes)
        try:
            shutil.copy2(appdata_notes, notes_path)
        except (IOError, OSError):
            return None

        appdata_settings = os.path.join(appdata_dir, "settings.json")
        if os.path.exists(appdata_settings):
            _preserve_settings_if_unreadable(settings_path)
            try:
                shutil.copy2(appdata_settings, settings_path)
            except (IOError, OSError):
                pass

        _copy_attachments(appdata_dir, attachments_path)

        settings = _settings()
        settings["reclaimed_from_appdata"] = True
        # The same tmp-then-replace every other data-file write uses: a
        # crash mid-write must not truncate settings.json (this was the
        # one naive writer left after the storage layer learned better).
        tmp_path = settings_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
            os.replace(tmp_path, settings_path)
        except (IOError, OSError):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        # Copied, not moved: the AppData copy stays where it is (the purge
        # never touches that folder), and the installed app goes on
        # reading it. The message used to say "moved", and the entry file
        # added that the two "can never drift apart" -- when from here on
        # they are two notebooks that do exactly that.
        message = (
            f"Copied your notebook into the app folder:\n{app_dir}\n\n"
            f"Brought {moved} note(s) from:\n{appdata_dir}\n\n"
            "The installed app keeps its own notebook there, so changes "
            "made here will not appear in it, or the other way round."
        )
        if displaced:
            message += (
                f"\n\nAn older file was already here; it was backed up to:\n{displaced}"
            )
        return message

    # --- Case 2: nothing here yet, adopt the richest legacy copy ---
    if os.path.exists(notes_path):
        return None

    best_dir, best_count = None, 0
    for d in get_legacy_dirs(app_dir):
        candidate = os.path.join(d, "notes_data.json")
        if os.path.exists(candidate):
            n = count_notes_in(candidate)
            if n > best_count:
                best_dir, best_count = d, n

    if not best_dir:
        return None

    try:
        shutil.copy2(os.path.join(best_dir, "notes_data.json"), notes_path)
    except (IOError, OSError):
        return None

    legacy_settings = os.path.join(best_dir, "settings.json")
    # Only a settings file this app wrote. The built app looks in the
    # folder its own folder was unpacked into, and a generic
    # settings.json there -- another program's -- used to be adopted
    # wholesale as this app's preferences.
    if os.path.exists(legacy_settings) and _looks_like_our_settings(legacy_settings):
        _preserve_settings_if_unreadable(settings_path)
        try:
            shutil.copy2(legacy_settings, settings_path)
        except (IOError, OSError):
            pass

    for d in get_legacy_dirs(app_dir):
        _copy_attachments(d, attachments_path)

    return (
        f"Your notes now live in the app folder:\n{app_dir}\n\n"
        f"Imported {best_count} note(s) from:\n{best_dir}"
    )


# Files this app is responsible for. Nothing outside this list is ever
# deleted from a folder we're cleaning up.
OWNED_FILENAMES = ("notes_data.json", "settings.json")
OWNED_PREFIXES = ("notes_data_backup_", "notes_data_replaced_")


def _content_signatures(notes):
    """Identity of a note by its content, ignoring id and timestamps.

    Delegates to model.content_signature — the ONE definition — because
    this set gates an irreversible os.remove/rmtree of a leftover
    notebook folder. A private field tuple here once fell behind the
    dedup's (no checklist, no recurrence), so a legacy folder whose notes
    differed from the local ones only by their checklists was judged
    "fully covered" and deleted outright."""
    # Imported here, not at the top: model -> categories -> storage ->
    # paths at import time, so a module-level import of model from here
    # closes that loop and crashes the whole package. The function-level
    # import runs long after every module is initialised.
    from .model import content_signature
    # This set gates an irreversible delete, so ANY content difference
    # must keep the folder -- styling, layout, per-day edits, skipped
    # dates, the pin and the colour included. content_signature has only
    # that strict answer now; see its docstring for the looser one it
    # used to offer, and what it cost.
    return {
        content_signature(n) for n in notes if isinstance(n, dict)
    }


def _is_owned_file(filename):
    return filename in OWNED_FILENAMES or filename.startswith(OWNED_PREFIXES)


def is_redundant_copy(candidate_path, local_notes):
    """True only when every note in the candidate file already exists locally.
    This is the safety gate for deletion — if even one note is unique to the
    old copy, it stays put."""
    try:
        with open(candidate_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return False
    if not isinstance(data, list):
        return False
    if not data:
        return True
    return _content_signatures(data).issubset(_content_signatures(local_notes))


def _attachments_are_covered(stale_dir, app_dir):
    """Every attached file in the old folder must already exist in the new
    one -- the same bytes, not merely the same name.

    It used to compare names alone, and only of the files at the top
    level. The purge then deleted the whole folder, so a file in a
    subfolder (never copied: the migration copies the top level only) or
    a different file that happened to share a name was destroyed, while
    the startup message said every attachment had been checked. The app
    itself only ever writes files flat, so a subfolder means the folder
    is not wholly ours, and it is left alone."""
    stale_attach = os.path.join(stale_dir, "attachments")
    if not os.path.isdir(stale_attach):
        return True
    local_attach = os.path.join(app_dir, "attachments")
    try:
        entries = os.listdir(stale_attach)
    except OSError:
        return False
    for filename in entries:
        stale_file = os.path.join(stale_attach, filename)
        if not os.path.isfile(stale_file):
            return False
        local_file = os.path.join(local_attach, filename)
        try:
            if not (os.path.isfile(local_file)
                    and filecmp.cmp(stale_file, local_file, shallow=False)):
                return False
        except OSError:
            return False
    return True


# Keys only this app writes into its settings.json. A folder the purge or
# the adoption looks at can be somebody else's -- in the built app, the
# folder ABOVE the app's own is one of them, and that is wherever the zip
# was unpacked: Downloads, the Desktop. A settings.json there that carries
# none of these is not ours, and is neither adopted nor deleted.
_OUR_SETTINGS_KEYS = ("app_version", "cleanup_done", "categories",
                      "first_launch_date", "reclaimed_from_appdata")


def _looks_like_our_settings(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError, OSError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and any(k in data for k in _OUR_SETTINGS_KEYS)


def purge_stale_copies(app_dir):
    """Delete leftover data in folders the app no longer reads from, so there
    is exactly one notebook on disk.

    Deletion only happens when ALL of these hold:
      - the local notes file exists and is readable
      - every note in the stale copy is already present locally
      - every attachment in the stale folder is already present locally,
        byte for byte, and the attachments folder holds nothing else
      - the file being deleted is one this app created (a settings.json
        must also carry this app's own keys)
      - the folder isn't the real per-user AppData folder (see below)

    The dist\\ folder itself is never removed (it holds the .exe); only the
    orphaned data files inside it are.

    %APPDATA%\\NoteOrganizer is never touched by this function, under any
    circumstances, even when it looks fully redundant against app_dir's own
    copy. It's the durable, cross-run store the distributed .exe actually
    reads from — treating it as just another disposable legacy folder once
    caused it to be silently deleted the moment any throwaway script-mode
    directory (a dev checkout, a CI runner, a test script's own scratch
    copy) imported this module while real notes existed there. See
    docs/ISSUES_LOG.md."""
    local_path = os.path.join(app_dir, "notes_data.json")
    if not os.path.exists(local_path):
        return []
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            local_notes = json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        return []
    if not isinstance(local_notes, list):
        return []

    appdata_dir = os.path.abspath(get_appdata_dir())
    cleared = []

    for stale_dir in get_legacy_dirs(app_dir):
        if os.path.abspath(stale_dir) == appdata_dir:
            # The per-user AppData folder is the durable, cross-run store the
            # distributed .exe actually reads from — never a disposable
            # leftover copy, no matter how "redundant" it looks against
            # whatever directory happens to be running this code right now.
            # Without this guard, simply importing this module from any
            # throwaway script-mode directory (a dev checkout, a CI runner,
            # even a test script's own scratch copy) that hasn't reclaimed
            # yet would copy the real notes out and then delete the
            # originals here, since they'd look fully redundant right after
            # being copied. See docs/ISSUES_LOG.md.
            continue
        stale_notes = os.path.join(stale_dir, "notes_data.json")
        if not os.path.exists(stale_notes):
            continue
        if not is_redundant_copy(stale_notes, local_notes):
            continue
        if not _attachments_are_covered(stale_dir, app_dir):
            continue

        removed_anything = False

        try:
            entries = os.listdir(stale_dir)
        except OSError:
            continue

        for filename in entries:
            full = os.path.join(stale_dir, filename)
            if not (os.path.isfile(full) and _is_owned_file(filename)):
                continue
            if filename == "settings.json" and not _looks_like_our_settings(full):
                continue
            try:
                os.remove(full)
                removed_anything = True
            except OSError:
                pass

        # File by file, each one proved identical to its copy in the app
        # folder at the moment it goes -- never the folder wholesale.
        # shutil.rmtree took whatever else was in it too, subfolders
        # included. The folder itself goes only if that left it empty.
        stale_attach = os.path.join(stale_dir, "attachments")
        local_attach = os.path.join(app_dir, "attachments")
        if os.path.isdir(stale_attach):
            for filename in os.listdir(stale_attach):
                stale_file = os.path.join(stale_attach, filename)
                local_file = os.path.join(local_attach, filename)
                try:
                    if (os.path.isfile(stale_file) and os.path.isfile(local_file)
                            and filecmp.cmp(stale_file, local_file, shallow=False)):
                        os.remove(stale_file)
                        removed_anything = True
                except OSError:
                    pass
            try:
                os.rmdir(stale_attach)
            except OSError:
                pass

        if removed_anything:
            cleared.append(stale_dir)

    return cleared


# ---- The resolved data-file locations ----
#
# These start as None and are filled in by configure() once the app knows
# which folder it is using. Other modules must read them as ATTRIBUTES of
# this module (``paths.SETTINGS_FILE``) rather than importing the names
# directly: ``from ... import SETTINGS_FILE`` copies whatever the value is
# at import time, which is None, and would never see the configured value.
# The same binding rule is why patching a re-exported name doesn't work
# (see docs/CODE_TOUR.md).
APP_DIR = None
DATA_FILE = None
SETTINGS_FILE = None
ATTACHMENTS_DIR = None
TRASH_FILE = None
TEMPLATES_FILE = None


def configure(app_dir):
    """Point the storage layer at ``app_dir`` and make sure it is usable.

    Called once at startup, after :func:`resolve_data_dir` has decided
    where the data lives. Creates the attachments folder as a side effect,
    which is why this is an explicit call rather than something that
    happens on import.

    Args:
        app_dir: The folder holding this app's data files.

    Returns:
        The same ``app_dir``, for convenience at the call site.
    """
    global APP_DIR, DATA_FILE, SETTINGS_FILE, ATTACHMENTS_DIR, TRASH_FILE, TEMPLATES_FILE
    APP_DIR = app_dir
    DATA_FILE = os.path.join(app_dir, "notes_data.json")
    SETTINGS_FILE = os.path.join(app_dir, "settings.json")
    ATTACHMENTS_DIR = os.path.join(app_dir, "attachments")
    TRASH_FILE = os.path.join(app_dir, "trash.json")
    TEMPLATES_FILE = os.path.join(app_dir, "templates.json")
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    return app_dir
