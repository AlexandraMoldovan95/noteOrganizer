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
* **Run as a .exe (distributed)** - data goes to the app's own folder in
  the person's profile, ``Note Organizer`` beside Documents, which is
  per-user, writable, and left alone by Windows, uninstalling and the
  Microsoft Store's package alike (see :func:`get_user_notebook_dir`).
  Until 2026-10-27 it was ``%APPDATA%\\NoteOrganizer``, still read once
  to bring an older notebook in. Writing beside the exe is unreliable.

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
2. The durable stores -- the app's folder under ``%APPDATA%`` and its
   folder in the profile -- are **permanently exempt**, however redundant
   they look: a built app keeps a real notebook in each. Treating one as
   just another disposable leftover is exactly what
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
import time
from datetime import datetime


#: Every way a JSON file or text can turn out unreadable: not JSON at all,
#: bytes that are not UTF-8 (a notes file saved by another program in
#: Windows' own Romanian encoding, say), and nesting deeper than the parser
#: can follow. The readers caught the first kind only, and the other two
#: escaped them: the app would not start while its notes, settings, Trash or
#: templates file held one, a share code said "Something went wrong", and a
#: backup holding such a file failed whole. Every reader of a file or code
#: that may be damaged catches all three, and treats them as the damage they
#: are.
JSON_UNREADABLE = (json.JSONDecodeError, UnicodeDecodeError, RecursionError)

#: Data files this run must not write: one it could neither read nor keep a
#: copy of. Another program holding the notes file at the start made it read
#: as empty, its copy failed for the same reason, and the first keystroke's
#: autosave replaced fifty notes with one (2026-10-28, the final audit).
WRITES_HELD = set()


def hold_writes(path):
    """Refuse every write to *path* for the rest of this run."""
    WRITES_HELD.add(os.path.normcase(os.path.abspath(path)))


def writes_held(path):
    return os.path.normcase(os.path.abspath(path)) in WRITES_HELD


# ---- Storage location ----
#
# Two very different situations, deliberately handled differently:
#
#   Running as a .py script (development)  -> data sits beside the script, so
#       notes_data.json is right there in the project folder while coding.
#
#   Running as a .exe (distributed)        -> data goes in the profile's
#       "Note Organizer" folder (get_user_notebook_dir), per-user and never
#       cleaned up by Windows, an uninstall or the Store's package. Writing
#       next to the exe is unreliable: a --onefile exe unpacks into a folder
#       Windows deletes on exit, and Downloads or Program Files may be
#       read-only. %APPDATA%\NoteOrganizer held it until 2026-10-27.

def get_appdata_dir():
    """Per-user application data folder for this app: where the built app
    kept its notebook until 2026-10-27, and still a place it reads from."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "NoteOrganizer")


def get_user_notebook_dir():
    """Where the built app keeps the notebook: a folder of its own in the
    person's profile, beside Documents.

    Not AppData: installed from the Microsoft Store, the app runs as an
    MSIX package, and every file it creates in AppData goes to the
    package's private copy, which uninstalling deletes -- and the atomic
    save creates a new file every time. The rest of the profile is the
    person's own and stays. Not Documents: Windows 11 sets it to back up
    to OneDrive without asking, and the notes would leave the device
    unasked. Elsewhere than Windows, the AppData equivalent, as before."""
    if os.name == "nt":
        base = os.environ.get("USERPROFILE") or os.path.expanduser("~")
        return os.path.join(base, "Note Organizer")
    return get_appdata_dir()


def _durable_stores():
    """The folders a built app has kept a real notebook in, compared as
    paths: no cleanup ever removes anything from them, whatever runs it."""
    return {os.path.normcase(os.path.abspath(d))
            for d in (get_appdata_dir(), get_user_notebook_dir())}


def _is_durable(folder):
    """Whether *folder* is one of _durable_stores()."""
    return os.path.normcase(os.path.abspath(folder)) in _durable_stores()


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


# Beside the entry point, a git-ignored file that names another folder for
# the notebook when the app runs from source: the developer's own notebook
# kept out of the working tree, where every lost notebook was lost. A
# scratch copy of the code carries no such file, so tests stay in theirs.
LOCATION_FILE = "notebook_location.txt"


def chosen_notebook_dir(script_dir):
    """The folder ``notebook_location.txt`` beside *script_dir* names, or
    None. Its first line that is not blank or a ``#`` comment is the path;
    environment variables in it are expanded (``%LOCALAPPDATA%\\...``), and
    a relative path is read from *script_dir*. Ignored by the built app."""
    if getattr(sys, "frozen", False):
        return None
    try:
        with open(os.path.join(script_dir, LOCATION_FILE), "r",
                  encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except (IOError, OSError, UnicodeDecodeError):
        return None
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            path = os.path.expanduser(os.path.expandvars(line))
            return os.path.abspath(os.path.join(script_dir, path))
    return None


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
        # Distributed app: its own folder in the profile (see
        # get_user_notebook_dir for why not AppData).
        home = get_user_notebook_dir()
        if _is_writable(home):
            return home, None
        appdata = get_appdata_dir()
        if _is_writable(appdata):
            # Said as it is: a file in the folder's place is not a profile
            # that cannot be written, and renaming it is the whole cure.
            why = (f"A file named \"{os.path.basename(home)}\" is where the notes "
                   f"folder goes:\n{home}\nRename or move that file, then start "
                   "the app again." if os.path.isfile(home)
                   else "Your profile folder couldn't be written to.")
            return appdata, (
                f"{why}\n\nUntil then, notes are being saved here instead:\n"
                f"{appdata}\n\nIf the app came from the Microsoft Store, "
                "uninstalling it can remove that folder: make a backup "
                "(Settings → Backup) before you do."
            )
        # Extremely rare (a locked-down profile). Fall back to the exe's folder,
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

    # Development: run as a script -> beside the entry-point .py file, or in
    # the folder notebook_location.txt there names.
    script_dir = os.path.abspath(script_dir)
    chosen = chosen_notebook_dir(script_dir)
    if chosen is not None:
        if _is_writable(chosen):
            return chosen, None
        if _is_writable(script_dir):
            return script_dir, (
                f"The folder {LOCATION_FILE} names could not be used:\n"
                f"{chosen}\n\nNotes are being saved beside the app instead, "
                "until that folder can be written to."
            )
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
    except (*JSON_UNREADABLE, IOError, OSError):
        return 0


#: What else travels with a notebook brought in, beside its notes, settings
#: and attached files. The Trash and the templates were left behind, so a
#: notebook came in with both empty (2026-10-27).
NOTEBOOK_COMPANIONS = ("trash.json", "templates.json")


def _copy_whole(src, dst, tries=1):
    """Copy *src* to *dst* whole or not at all: beside it first, then
    replaced in one step. Copied in place, a start killed mid-copy left a
    truncated file that every later "copy only if missing" kept for good.
    *tries*: a file another program holds a moment (a scanner, a sync
    tool) gets that many attempts, half a second apart."""
    part = dst + ".part"
    for attempt in range(tries):
        if attempt:
            time.sleep(0.5)
        try:
            shutil.copy2(src, part)
            # On the disk before the rename (the notes file among these is
            # the copy's "done" mark): a power cut could leave it empty.
            with open(part, "ab") as f:
                os.fsync(f.fileno())
            os.replace(part, dst)
            return True
        except (IOError, OSError):
            try:
                os.remove(part)
            except OSError:
                pass
    return False


def _copy_companions(src_dir, dest_dir):
    """The Trash and the templates, copied only where the notebook has none:
    never over a file of its own. Returns the names that could not be."""
    failed = []
    for name in NOTEBOOK_COMPANIONS:
        src = os.path.join(src_dir, name)
        dst = os.path.join(dest_dir, name)
        if (os.path.isfile(src) and not os.path.exists(dst)
                and not _copy_whole(src, dst, tries=3)):
            failed.append(name)
    return failed


def _copy_attachments(src_dir, dest_dir):
    """Every attached file the notebook lacks. Returns the names that could
    not be copied."""
    src_attach = os.path.join(src_dir, "attachments")
    if not os.path.isdir(src_attach):
        return []
    os.makedirs(dest_dir, exist_ok=True)
    failed = []
    for filename in os.listdir(src_attach):
        src = os.path.join(src_attach, filename)
        dst = os.path.join(dest_dir, filename)
        if (os.path.isfile(src) and not os.path.exists(dst)
                and not _copy_whole(src, dst, tries=3)):
            failed.append(filename)
    return failed


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

    The same bytes are kept aside once. A file the app cannot use is read
    again at every launch until something rewrites it -- a Trash nobody
    touches, a templates file -- and each launch kept one more identical
    copy, never deleted.

    Returns:
        The copy's path (an earlier one holding the same bytes, if there is
        one), or None if even the copy failed.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    root, ext = os.path.splitext(path)
    ext = ext or ".json"
    try:
        with open(path, "rb") as fh:
            held = fh.read()
        folder = os.path.dirname(path) or "."
        prefix = os.path.basename(root) + "_corrupt_"
        for name in sorted(os.listdir(folder)):
            if not (name.startswith(prefix) and name.endswith(ext)):
                continue
            kept = os.path.join(folder, name)
            if os.path.getsize(kept) == len(held):
                with open(kept, "rb") as fh:
                    if fh.read() == held:
                        return kept
    except (IOError, OSError):
        pass
    backup_path = f"{root}_corrupt_{stamp}{ext}"
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
    except (*JSON_UNREADABLE, IOError, OSError):
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
        except (*JSON_UNREADABLE, IOError, OSError):
            return {}

    # --- Case 1: reclaim data from %APPDATA% ---
    # A run from source taking over from the installed app. The built app
    # never replaces a notebook it has: it only fills an empty folder
    # (case 2), or an old exe run again would put its notebook in place
    # of the notes written since.
    appdata_dir = get_appdata_dir()
    appdata_notes = os.path.join(appdata_dir, "notes_data.json")
    already_done = _settings().get("reclaimed_from_appdata")

    if (not getattr(sys, "frozen", False)
            and not already_done
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
        _copy_companions(appdata_dir, app_dir)

        settings = _settings()
        settings["reclaimed_from_appdata"] = True
        # The same tmp-then-replace every other data-file write uses: a
        # crash mid-write must not truncate settings.json (this was the
        # one naive writer left after the storage layer learned better).
        tmp_path = settings_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, settings_path)
        except (IOError, OSError):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        # Copied, not moved: the AppData copy stays where it is (the purge
        # never touches that folder). The message used to say "moved", and
        # the entry file added that the two "can never drift apart" -- when
        # from here on they are two notebooks that do exactly that.
        message = (
            f"Copied your notebook into this folder:\n{app_dir}\n\n"
            f"Brought {moved} note(s) from:\n{appdata_dir}\n\n"
            "The notebook there is kept as it was, so changes made here "
            "will not appear in it, or the other way round."
        )
        if displaced:
            message += (
                f"\n\nAn older file was already here; it was backed up to:\n{displaced}"
            )
        return message

    # --- Case 2: nothing here yet, adopt the richest legacy copy ---
    if os.path.exists(notes_path):
        return None

    best_dir, best_count, own_store = None, 0, None
    for d in get_legacy_dirs(app_dir):
        candidate = os.path.join(d, "notes_data.json")
        if os.path.exists(candidate):
            n = count_notes_in(candidate)
            if n > best_count:
                best_dir, best_count = d, n
            elif own_store is None and _is_durable(d):
                own_store = d
    # An empty or unreadable notebook in the old app's own store is still
    # that notebook: its Trash and templates come, and an unreadable file is
    # kept aside and announced by load_notes, as it is anywhere else.
    best_dir = best_dir or own_store
    if not best_dir:
        return None
    durable = _is_durable(best_dir)

    # The notes file goes LAST, whole: it is what tells the next start the
    # copy is done. Written first, a start killed mid-copy left notes whose
    # files never came, and nothing tried again.
    legacy_settings = os.path.join(best_dir, "settings.json")
    # Only a settings file this app wrote. The built app looks in the
    # folder its own folder was unpacked into, and a generic
    # settings.json there -- another program's -- used to be adopted
    # wholesale as this app's preferences.
    ours = os.path.exists(legacy_settings) and _looks_like_our_settings(legacy_settings)
    settings_came = True
    if ours:
        _preserve_settings_if_unreadable(settings_path)
        settings_came = _copy_whole(legacy_settings, settings_path, tries=3)
    elif (durable and os.path.exists(legacy_settings)
          and not os.path.exists(settings_path)):
        # The old app's own settings, unreadable: there the Trash's window
        # is unknown, and nothing leaves it. Copied as it is, it reads the
        # same way here and the start says so; left behind, the default 30
        # days emptied a Trash its owner kept longer (2026-10-28, the audit).
        settings_came = _copy_whole(legacy_settings, settings_path, tries=3)
    # On the same evidence: a Trash or templates file beside another
    # program's notes is not ours to bring in. The old app's own store needs
    # no evidence -- its settings.json may be the file that cannot be read.
    missing = []
    if ours or durable:
        missing += _copy_companions(best_dir, app_dir)

    for d in get_legacy_dirs(app_dir):
        missing += _copy_attachments(d, attachments_path)

    if not (settings_came
            and _copy_whole(os.path.join(best_dir, "notes_data.json"), notes_path,
                            tries=3)):
        # All or nothing for what says what the notebook is: nothing is
        # written here this run, so the next start tries again. ISSUES_LOG:
        # "Round three: one rescue copy, and files another program holds".
        for name in ("notes_data.json",) + NOTEBOOK_COMPANIONS:
            hold_writes(os.path.join(app_dir, name))
        return (f"Your notebook in:\n{best_dir}\ncould not be brought in this "
                "time — another program may be holding its files. Nothing is "
                "saved here until it can be: close Note Organizer and open it "
                "again.")

    message = (
        f"Your notes now live in this folder:\n{app_dir}\n\n"
        + (f"Imported {best_count} note(s) from:\n{best_dir}" if best_count
           else f"Brought in the notebook from:\n{best_dir}")
    )
    if missing:
        # Said, never passed over: the notes file marks the copy done, and
        # no later start looks at the old folder again.
        shown = ", ".join(missing[:5]) + (
            f" and {len(missing) - 5} more" if len(missing) > 5 else "")
        message += (f"\n\nThese files could not be copied, and are only in "
                    f"the folder above: {shown}.")
    if durable:
        message += "\n\nThe notebook there is kept as it was."
    return message


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
    except (*JSON_UNREADABLE, IOError, OSError):
        return False
    if not isinstance(data, list):
        return False
    if not data:
        return True
    try:
        return _content_signatures(data).issubset(_content_signatures(local_notes))
    except Exception:  # noqa: BLE001 -- raw notes nested 990 deep overflowed the
        return False   # recursion and stopped every start: unjudged is kept


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
    except (*JSON_UNREADABLE, IOError, OSError):
        return False
    return isinstance(data, dict) and any(k in data for k in _OUR_SETTINGS_KEYS)


def purge_stale_copies(app_dir):
    """Delete leftover data in folders the app no longer reads from -- an
    old dist copy, say -- so no stale notebook lingers beside the real one.

    Deletion only happens when ALL of these hold:
      - the local notes file exists and is readable
      - every note in the stale copy is already present locally
      - every attachment in the stale folder is already present locally,
        byte for byte, and the attachments folder holds nothing else
      - the file being deleted is one this app created (a settings.json
        must also carry this app's own keys)
      - the folder isn't a durable store (see below)

    The dist\\ folder itself is never removed (it holds the .exe); only the
    orphaned data files inside it are.

    The durable stores -- %APPDATA%\\NoteOrganizer and the profile's
    "Note Organizer" folder (_durable_stores) -- are never touched by this
    function, under any circumstances, even when one looks fully redundant
    against app_dir's own copy. They are where a built app keeps a real
    notebook -- treating the first as just another disposable legacy folder once
    caused it to be silently deleted the moment any throwaway script-mode
    directory (a dev checkout, a CI runner, a test script's own scratch
    copy) imported this module while real notes existed there. See
    docs/ISSUES_LOG.md."""
    local_path = os.path.join(app_dir, "notes_data.json")
    if not os.path.exists(local_path):
        return []
    durable = _durable_stores()
    # Only a leftover folder that still holds a notebook can need clearing
    # (the loop below skips every other one), and on nearly every launch
    # there is none. Reading the whole local notebook first bought
    # nothing: a second full parse of it at every startup, ~95 ms at
    # 5,000 notes (measured).
    stale_dirs = [d for d in get_legacy_dirs(app_dir)
                  if os.path.normcase(os.path.abspath(d)) not in durable
                  and os.path.exists(os.path.join(d, "notes_data.json"))]
    if not stale_dirs:
        return []
    try:
        with open(local_path, "r", encoding="utf-8") as f:
            local_notes = json.load(f)
    except (*JSON_UNREADABLE, IOError, OSError):
        return []
    if not isinstance(local_notes, list):
        return []

    cleared = []

    for stale_dir in stale_dirs:
        if os.path.normcase(os.path.abspath(stale_dir)) in durable:
            # A durable store -- the AppData folder an older .exe read from,
            # the profile folder the built app reads from now -- never a disposable
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
            # A backup is a notebook too: it goes only when every note in it
            # is ours already. They went unread, beside a covered notes file.
            if filename.startswith(OWNED_PREFIXES) and not is_redundant_copy(full, local_notes):
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
