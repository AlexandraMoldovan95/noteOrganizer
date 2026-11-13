"""Where the app's data lives, and how it moves there safely: which folder
holds ``notes_data.json``, migrations from older places, the clean-up.
Importing it does nothing -- these functions move and delete notes, and
run only when called (``note_organizer.initialise()``): ISSUES_LOG: "The
cleanup that deleted the real notebook". From source the notebook is beside
the script or where ``notebook_location.txt`` points; built, in the
profile's ``Note Organizer`` folder, proved writable by a probe. Nothing is
overwritten before it is copied; purge_stale_copies removes only files it
owns, judged redundant by content, never in the durable stores.
"""

import filecmp
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime


#: Every way a file or a text can turn out unreadable: not JSON, not UTF-8 (a
#: file saved in a Windows code page), nested past the parser. Readers that
#: caught the first alone let the others stop the app from starting.
JSON_UNREADABLE = (json.JSONDecodeError, UnicodeDecodeError, RecursionError)

#: Data files this run must not write: one it could neither read nor copy.
#: Read as empty while another program held it, a notes file's first autosave
#: replaced fifty notes with one (2026-10-28).
WRITES_HELD = set()


def hold_writes(path):
    """Refuse every write to *path* for the rest of this run."""
    WRITES_HELD.add(os.path.normcase(os.path.abspath(path)))


def writes_held(path):
    return os.path.normcase(os.path.abspath(path)) in WRITES_HELD


# ---- Storage location: from source, beside the script; built, the profile's
# "Note Organizer" folder (get_user_notebook_dir), never beside the exe, which
# may be read-only or deleted on exit. AppData held it until 2026-10-27. ----

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
    person's profile, beside Documents. Not AppData: under the Store's MSIX
    package every file created there goes to the package's copy, which an
    uninstall deletes, and each save creates a new file. Not Documents:
    Windows 11 backs it up to OneDrive unasked. Elsewhere than Windows, the
    AppData equivalent."""
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
    person's data: beside this package from source, in the folder a
    PyInstaller build unpacks to (``sys._MEIPASS``) when built. Returned
    whether anything is there or not: the caller decides what missing
    means (for the window icon, carrying on without one)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
    return os.path.join(base, *parts)


def _is_writable(folder):
    """True if a file can really be created here: Program Files exists too,
    but writing there fails. The probe's name is this call's own: one fixed
    name made two launches probing at once collide, nearly half answering
    "not writable" and one sent to a fallback folder (see _main). Removing
    the probe is tidiness; creating and writing it was the proof."""
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


# A git-ignored file beside the entry point naming the notebook's folder when
# run from source, the developer's own kept out of the working tree; a scratch
# copy of the code carries none, so tests stay in their own folder.
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
            Ignored when running as a frozen ``.exe``, which uses the
            profile's ``Note Organizer`` folder.

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
                "saved next to the app instead. They'll persist there; make a "
                "backup (Settings → Backup) before you move or remove the app."
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
    # The folder an .exe before 2026-10-27 kept its notebook in, so an
    # older build's notes are still found.
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


def _same_bytes(a, b):
    """Whether files *a* and *b* hold the same bytes; False when either cannot
    be read, which then counts as different."""
    try:
        return filecmp.cmp(a, b, shallow=False)
    except OSError:
        return False


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


def unused_path(folder, stem, extension):
    """``<stem><extension>`` in *folder*, or ``<stem>_1<extension>`` and so on
    when that is taken: a copy stamped by the second wrote over one made the
    same second, and removed after, took it with it."""
    candidate = os.path.join(folder, stem + extension)
    number = 0
    while os.path.exists(candidate):
        number += 1
        candidate = os.path.join(folder, "%s_%d%s" % (stem, number, extension))
    return candidate


def _timestamped_backup(path, label):
    """Copy a file aside before it gets overwritten, as
    ``<name>_<label>_<stamp>.json`` beside it. Returns the new path, or None
    when there is no file or the copy failed."""
    if not os.path.exists(path):
        return None
    folder = os.path.dirname(path)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = os.path.splitext(os.path.basename(path))[0]
    backup_path = unused_path(folder, f"{name}_{label}_{stamp}", ".json")
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except (IOError, OSError):
        return None


def preserve_corrupt_file(path):
    """Copy an unreadable data file aside before anything can overwrite it:
    it still holds the person's bytes, and the next write would make the
    damage permanent. Timestamped, beside the original, matching no OWNED_*
    pattern, so no clean-up removes it; the same bytes kept once, not at
    every launch that reads them again. Here, as the migrations below need
    it; storage's _preserve_corrupt wraps it.

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
    backup_path = unused_path(os.path.dirname(path) or ".",
                              f"{os.path.basename(root)}_corrupt_{stamp}", ext)
    try:
        shutil.copy2(path, backup_path)
        return backup_path
    except (IOError, OSError):
        return None


def _preserve_settings_if_unreadable(settings_path):
    """Before migration code overwrites settings.json, keep its bytes if it
    exists but holds no usable dict — the reclaim path used to clobber a
    corrupt settings file with no trace at all. Returns the copy's path, or
    None when nothing was kept aside."""
    if not os.path.exists(settings_path):
        return None
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            if isinstance(json.load(f), dict):
                return None
    except (*JSON_UNREADABLE, IOError, OSError):
        pass
    return preserve_corrupt_file(settings_path)


def run_migrations(app_dir):
    """Bring data into app_dir from wherever a previous version left it, in
    order: from source, once, the notebook an .exe before 2026-10-27 kept in
    %APPDATA%\\NoteOrganizer, over the source folder's files (copied aside
    first); else, with nothing here yet, the richest legacy folder found.
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

    # --- Case 1: a run from source takes over an older .exe's notebook. The
    # built app never replaces one it has: it only fills an empty folder
    # (case 2), or an old exe run again would undo the notes written since.
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
            # A local file whose copy failed (a full disk, a lock): no
            # overwrite without one. Left as it is; the next launch tries again.
            return None
        moved = count_notes_in(appdata_notes)
        if not _copy_whole(appdata_notes, notes_path):
            return None

        # This folder's own settings are copied aside too, readable or not;
        # if that copy fails they stay, and only the notes come in.
        appdata_settings = os.path.join(appdata_dir, "settings.json")
        if os.path.exists(appdata_settings) and (
                not os.path.exists(settings_path)
                or _preserve_settings_if_unreadable(settings_path)
                or _timestamped_backup(settings_path, "replaced")):
            _copy_whole(appdata_settings, settings_path)

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

        # Copied, not moved: the AppData copy stays (the purge never touches
        # it), and from here on the two are separate notebooks, said so.
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
    # Only a settings file this app wrote: the built app looks where it was
    # unpacked, and another program's settings.json there was once adopted.
    ours = os.path.exists(legacy_settings) and _looks_like_our_settings(legacy_settings)
    settings_came = True
    settings_stayed = False
    if ours:
        # This folder's settings copied aside first, readable or not, as case
        # 1's are; that copy failing, they stay. Already the old notebook's own
        # bytes (a start that went no further), neither: each left a copy.
        if os.path.exists(settings_path) and _same_bytes(settings_path, legacy_settings):
            pass
        elif (not os.path.exists(settings_path)
                or _preserve_settings_if_unreadable(settings_path)
                or _timestamped_backup(settings_path, "replaced")):
            settings_came = _copy_whole(legacy_settings, settings_path, tries=3)
        else:
            settings_stayed = True
    elif (durable and os.path.exists(legacy_settings)
          and not os.path.exists(settings_path)):
        # The old app's own settings, unreadable: copied as they are, the start
        # says so, and the Trash's unknown window keeps everything; left behind,
        # the default 30 days emptied a Trash kept longer (2026-10-28).
        settings_came = _copy_whole(legacy_settings, settings_path, tries=3)
    # On the same evidence: a Trash or templates file beside another
    # program's notes is not ours to bring in. The old app's own store needs
    # no evidence -- its settings.json may be the file that cannot be read.
    missing = []
    if settings_stayed:
        # Under this folder's settings the old Trash would be emptied by this
        # folder's window: left where it is, and said, as a file not copied.
        missing += [name for name in NOTEBOOK_COMPANIONS
                    if os.path.exists(os.path.join(best_dir, name))]
    elif ours or durable:
        missing += _copy_companions(best_dir, app_dir)

    for d in get_legacy_dirs(app_dir):
        missing += _copy_attachments(d, attachments_path)

    if not (settings_came
            and _copy_whole(os.path.join(best_dir, "notes_data.json"), notes_path,
                            tries=3)):
        # All or nothing, the settings too (written at once, they made this a
        # first run): nothing written here this run, the next start tries again.
        # ISSUES_LOG: "Round three: one rescue copy, and files another program holds".
        for name in ("notes_data.json", "settings.json") + NOTEBOOK_COMPANIONS:
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
    """Identity of a note by its content, ignoring id and timestamps:
    model.content_signature, the ONE definition, as this set gates an
    irreversible delete of a leftover notebook folder -- a field list of its
    own here once fell behind (no checklist), and a folder differing only in
    its checklists was judged covered and deleted."""
    # Imported here: model -> categories -> storage -> paths at import time,
    # so a module-level import of model would close that loop.
    from .model import content_signature
    # An irreversible delete: ANY content difference keeps the folder (styles,
    # layout, a day's edits, the pin, the colour) -- content_signature's only answer.
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
    """Every attached file in the old folder already exists in the new one --
    the same bytes, not merely the same name: names alone, top level only,
    once let the purge destroy a file in a subfolder (never copied) or a
    different one sharing a name. The app writes files flat, so a subfolder
    means the folder is not wholly ours, and it is left alone."""
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


# Keys only this app writes into its settings.json: a folder looked at may be
# somebody else's (the built app's parent is wherever the zip was unpacked),
# and a settings.json carrying none of them is neither adopted nor deleted.
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
    """Delete leftover data in folders the app no longer reads from, only when
    ALL hold: the local notes file reads, every stale note and attached file
    (same bytes, nothing else there) is already local, the file is one this
    app made (a settings.json with its keys), and the folder is no durable
    store -- those hold a real notebook and are never touched. ISSUES_LOG:
    "The cleanup that deleted the real notebook"."""
    local_path = os.path.join(app_dir, "notes_data.json")
    if not os.path.exists(local_path):
        return []
    durable = _durable_stores()
    # On nearly every launch no leftover holds a notebook: the local one is
    # read only when one does (a second full parse, ~95 ms at 5,000 notes).
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
            # A durable store is never a disposable copy, however redundant it
            # looks: else a throwaway checkout running this copied the real
            # notes out and deleted them here (the docstring's story).
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

        # File by file, each proved identical to its copy as it goes, never the
        # folder wholesale (rmtree took whatever else was there); the folder
        # goes only if that left it empty.
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


# ---- The data files, None until configure(): read as ATTRIBUTES
# (``paths.SETTINGS_FILE``), since ``from ... import`` copies the None of
# import time and never sees the value (docs/CODE_TOUR.md). ----
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
