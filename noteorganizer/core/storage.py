"""Reading and writing the app's data files.

WHAT THIS MODULE IS FOR
-----------------------
Everything that touches ``settings.json``, ``templates.json`` and
``trash.json`` on disk, plus the pre-flight backup of the notes file.

WHERE THE FILES ARE
-------------------
This module does not decide *where* the data lives - :mod:`.paths` does.
It reads the locations as attributes::

    with open(paths.SETTINGS_FILE) as f: ...

That indirection is deliberate. The paths are not known when this module
is imported; they get filled in by ``paths.configure()`` once the app has
worked out which folder to use. Writing ``from .paths import
SETTINGS_FILE`` would copy the value as it stands at import time - which
is ``None`` - and would never see the real one. Going through the module
means the lookup happens when the function actually runs.

This is the same binding rule that made a monkeypatched name stop working
after an earlier extraction; see `docs/CODE_TOUR.md`.

THE PATTERN EVERY LOADER FOLLOWS
--------------------------------
Each ``load_*`` function returns something usable whatever it finds: a
missing file, an unreadable file, or valid JSON of entirely the wrong
shape all produce an empty default rather than an exception. The app is
meant to keep running with an empty notebook, not refuse to start because
one file got damaged.

``save_settings`` is read-modify-write rather than a blind overwrite, so
two features updating different keys cannot clobber each other.

:func:`backup_notes_file` gives destructive operations something to fall
back on, and returns ``None`` on failure so callers can decide whether to
proceed - the migration code, for one, refuses to.
"""

import json
import os
import shutil
from datetime import datetime, timedelta

from . import paths
# normalize_template validates a template's rich-text spans and its
# paragraph formatting, so the storage layer needs both validators.
from .formatting import normalize_formatting, normalize_paragraphs

# Deleted notes live in the trash this many days, then auto-purge on startup.
TRASH_RETENTION_DAYS = 30


# ---- Settings file (read/modify/write, so keys never clobber each other) ----

def load_settings():
    if os.path.exists(paths.SETTINGS_FILE):
        try:
            with open(paths.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return {}


def save_settings(settings):
    settings = mend_surrogates(settings)
    try:
        with open(paths.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except (IOError, OSError):
        pass




def normalize_template(tpl):
    """Coerce a template dict into a known shape so bad/old data can't crash the
    manager or the 'use template' flow. A template holds a name plus the note
    fields it fills in: title, body, comments, category."""
    if not isinstance(tpl, dict):
        tpl = {}

    def _s(key, default=""):
        v = tpl.get(key, default)
        return v if isinstance(v, str) else default

    return {
        "name": _s("name") or "Untitled template",
        "title": _s("title"),
        "body": _s("body"),
        "formatting": normalize_formatting(tpl.get("formatting")),
        "paragraphs": normalize_paragraphs(tpl.get("paragraphs"),
                                           len(_s("body").split("\n"))),
        "comments": _s("comments"),
        "category": _s("category") or "General",
        "checklist": [
            {"text": it.get("text", "") if isinstance(it.get("text"), str) else "",
             "done": bool(it.get("done"))}
            for it in (tpl.get("checklist") or [])
            if isinstance(it, dict)
        ],
    }


def load_templates():
    if os.path.exists(paths.TEMPLATES_FILE):
        try:
            with open(paths.TEMPLATES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [normalize_template(t) for t in data if isinstance(t, dict)]
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return []


def save_templates(templates):
    try:
        with open(paths.TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)
    except (IOError, OSError):
        pass


def load_trash():
    """Read the trashed notes list. Malformed/missing -> empty list, never
    crashes."""
    if os.path.exists(paths.TRASH_FILE):
        try:
            with open(paths.TRASH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return []


def save_trash(trash):
    """Write the trashed notes list, best-effort."""
    try:
        with open(paths.TRASH_FILE, "w", encoding="utf-8") as f:
            json.dump(trash, f, indent=2, ensure_ascii=False)
    except (IOError, OSError):
        pass


def _delete_attachment_files(notes_or_entries):
    """Permanently remove the on-disk files for every attachment referenced by
    the given notes/trash-entries. Each attachment gets a unique timestamped
    filename on disk (see add_attachment), so it's never shared between notes
    — safe to delete outright, no risk of affecting a different note. Only
    call this for PERMANENT deletion (trash purge, delete-forever, empty
    trash) — moving a note to trash must never touch these files, since the
    note might still be restored."""
    for note in notes_or_entries:
        if not isinstance(note, dict):
            continue
        for att in note.get("attachments") or []:
            if not isinstance(att, dict):
                continue
            stored_as = att.get("stored_as")
            if not stored_as:
                continue
            path = os.path.join(paths.ATTACHMENTS_DIR, stored_as)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass  # best-effort — a locked/missing file shouldn't block the delete


def purge_expired_trash(trash):
    """Remove entries older than the retention window. Returns (kept, purged
    count). Entries with a missing/invalid deleted_at are kept (fail-safe: we'd
    rather keep a note too long than delete it early). Attachment files
    belonging to purged notes are permanently deleted too — this is the one
    place purging happens automatically, without an explicit user action, so
    it must not be the one place that silently leaves orphaned files behind."""
    cutoff = datetime.now() - timedelta(days=TRASH_RETENTION_DAYS)
    kept = []
    purged_entries = []
    for entry in trash:
        stamp = entry.get("deleted_at", "") if isinstance(entry, dict) else ""
        try:
            when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            # Unknown timestamp -> keep it, don't risk early deletion.
            kept.append(entry)
            continue
        if when < cutoff:
            purged_entries.append(entry)
        else:
            kept.append(entry)
    _delete_attachment_files(purged_entries)
    return kept, len(purged_entries)


# Duplicate detection moved to noteorganizer/core/duplicates.py.
from noteorganizer.core.duplicates import (
    find_duplicate_groups,
    _strip_copy_suffix,
    _normalize_ws,
    _dup_key,
)


def backup_notes_file():
    """Snapshot the notes file before touching it. Cleanup should never be
    the reason something is lost."""
    if not os.path.exists(paths.DATA_FILE):
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(os.path.dirname(paths.DATA_FILE), f"notes_data_backup_{stamp}.json")
    try:
        shutil.copy2(paths.DATA_FILE, backup_path)
        return backup_path
    except (IOError, OSError):
        return None


# ---- Notes file ----
#
# These moved out of NoteOrganizer, where they had been methods since before
# there was a core layer. Neither drew anything; they were on the UI class
# only because that is where all the code used to live.
#
# Two things changed in the move, both deliberate:
#
# 1. ``load_notes`` used to read the module-global ``VERSION_CHANGE``. A
#    global on the entry module is exactly the value that goes missing when
#    the app runs as ``py note_organizer.py`` -- the running copy is then
#    ``__main__`` and any ``import note_organizer`` gets a *second* module
#    whose ``initialise()`` never ran (see test_entry_module_identity.py,
#    and the About/Statistics bug it was written for). So it is a parameter
#    now: the caller, which does know, passes it in.
#
# 2. ``save_notes`` used to open an error dialog itself. Nothing in core may
#    touch the interface, so it reports the failure and the caller decides
#    how to show it.

def load_notes(version_change=None):
    """Read, normalise and (once) clean the notes file.

    Args:
        version_change: The app's ``VERSION_CHANGE`` tuple, or None. When it
            says the app has been upgraded, the notes file is snapshotted
            *before* this version's code gets a chance to rewrite it.

    Returns:
        ``(notes, report)``. *report* carries what the caller needs to tell
        the user about afterwards:

        * ``version_backup_path`` -- set only if an upgrade backup was taken.
        * ``cleanup_report`` -- ``(stats, backup_path)`` only if the one-time
          cleanup ran on this launch.

        Both are None the rest of the time, which is almost always.
    """
    # Imported here rather than at the top of the file because there is a
    # real cycle: storage -> model -> categories -> storage. At module level
    # it fails with "cannot import name 'load_settings' from partially
    # initialized module". Inside the function the import runs long after
    # every module is built, so it resolves cleanly.
    from .model import normalize_note, clean_notes

    report = {"version_backup_path": None, "cleanup_report": None}
    raw = []
    if os.path.exists(paths.DATA_FILE):
        # A newer app version is about to run against data last saved by
        # an older one — snapshot it now, before this version's own code
        # (which could have new bugs or changed logic) gets any chance
        # to rewrite it. Every future update gets this safety net, not
        # just the very first run (see backup_notes_file's other call,
        # below, for that one-time case). Never auto-deleted — it's the
        # user's call when old backups are no longer needed.
        if version_change and version_change[0] == "up":
            report["version_backup_path"] = backup_notes_file()
        try:
            with open(paths.DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, IOError):
            raw = []
    if not isinstance(raw, list):
        raw = []

    # Every note gets the full set of fields, so no later code has to
    # guess whether an old note has 'comments' or 'attachments'.
    notes = [normalize_note(n) for n in raw if isinstance(n, dict)]

    settings = load_settings()
    if not settings.get("cleanup_done"):
        backup_path = backup_notes_file()
        notes, stats = clean_notes(notes)
        report["cleanup_report"] = (stats, backup_path)

        try:
            with open(paths.DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(notes, f, indent=2, ensure_ascii=False)
        except (IOError, OSError):
            pass

        settings["cleanup_done"] = True
        save_settings(settings)

    return notes, report


def mend_surrogates(value):
    """Recombine UTF-16 surrogate pairs into the characters they spell.

    Tk stores text in UTF-16 and hands astral characters -- every emoji
    past the basic plane -- to Python as two surrogate code points. They
    display, but they cannot be UTF-8 encoded, so the first emoji typed
    into a note killed every save after it. A proper pair becomes the real
    character; a lone surrogate, which spells nothing, becomes U+FFFD
    rather than poisoning the file.
    """
    if isinstance(value, str):
        try:
            value.encode("utf-8")
            return value
        except UnicodeEncodeError:
            return value.encode("utf-16", "surrogatepass").decode(
                "utf-16", "replace")
    if isinstance(value, dict):
        return {mend_surrogates(k): mend_surrogates(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [mend_surrogates(item) for item in value]
    return value


def save_notes(notes):
    """Write notes to disk.

    A failure here used to be invisible — the app looked like it saved but
    nothing hit the disk, which is exactly how notes 'vanished' on other
    PCs. It is surfaced instead, but by the caller: this returns the reason
    rather than opening a dialog, so the same function works whatever is
    drawing the window.

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``.
    """
    try:
        tmp_path = paths.DATA_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(mend_surrogates(notes), f, indent=2,
                      ensure_ascii=False)
        # Atomic replace: a crash mid-write can't corrupt the real file,
        # it either fully updates or stays as it was.
        os.replace(tmp_path, paths.DATA_FILE)
        return True, None
    # ValueError covers UnicodeEncodeError, TypeError the unserializable:
    # the old clause caught only I/O, so an emoji typed into a note flew
    # straight past it, autosave crash-logged sixteen times in a row, and
    # every edit after the first emoji lived only in the running app.
    except (IOError, OSError, ValueError, TypeError) as exc:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False, exc


# ---- Trash operations ----
#
# These were methods on the app class and touch no interface at all. They are
# the data half of "delete" and "restore": the caller still owns telling the
# screen to redraw afterwards.

def move_notes_to_trash(trash, notes_to_trash):
    """Move notes into the trash with a deletion timestamp.

    Nothing is destroyed -- every delete path goes through here so a note is
    never lost without its grace period.

    Args:
        trash: the current trash list, appended to in place.
        notes_to_trash: the notes being removed from the active list.

    Returns:
        The same trash list, for convenience at the call site.
    """
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for note in notes_to_trash:
        entry = dict(note)
        entry["deleted_at"] = stamp
        trash.append(entry)
    save_trash(trash)
    return trash


def days_left_in_trash(deleted_at):
    """How many days until this trashed note auto-purges. None if unknown."""
    try:
        when = datetime.strptime(deleted_at, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    elapsed = (datetime.now() - when).days
    return max(0, TRASH_RETENTION_DAYS - elapsed)


def restore_from_trash(notes, trash, entry):
    """Bring a trashed note back into the active list.

    A note whose category was deleted while it sat in the trash comes back
    filed under "General" rather than orphaned -- but that is
    :func:`~noteorganizer.core.model.normalize_note`'s doing, not this
    function's. The method this replaced re-checked the category itself and
    fell back to the same value, which had no effect; the check is gone
    rather than carried over, and the guarantee is tested where it lives.

    Args:
        notes: the active note list, appended to in place.
        trash: the trash list; ``entry`` is removed from it.
        entry: the trashed note to restore.

    Returns:
        ``(notes, trash)`` -- both lists, saved to disk.
    """
    from .model import normalize_note

    # normalize_note rebuilds the note from a known schema, so it drops
    # "deleted_at" and anything else the trash entry carried. The method this
    # replaced stripped that key by hand first; verified redundant, so it is
    # gone rather than copied across. What it guaranteed is still tested.
    note = normalize_note(entry)
    # A fresh id: the trashed note's own id may have been reused by a note
    # created after it was deleted.
    note["id"] = max([n["id"] for n in notes], default=0) + 1
    notes.append(note)
    trash = [e for e in trash if e is not entry]
    save_trash(trash)
    return notes, trash


# ---- Single settings values ----
#
# Six methods on the app class were the same three lines: load the settings,
# change one key, save them back. That shape is not incidental -- writing the
# whole file for one value is what stops a save from wiping a key it never
# meant to touch, like the one-time cleanup flag. Doing it once here keeps
# the reason attached to the code rather than repeated in six comments.

def get_setting(key, default=None, expect=None):
    """One value out of settings.json.

    Args:
        key: the setting to read.
        default: returned when the key is missing, or when it holds
            something of the wrong type.
        expect: an optional type the value must be. A settings file can be
            hand-edited or written by an older version, so a value that is
            there but wrong should read as absent rather than reach the
            caller and fail somewhere less obvious.
    """
    value = load_settings().get(key, default)
    if expect is not None and not isinstance(value, expect):
        return default
    return value


def save_setting(key, value):
    """Change one value in settings.json, leaving the rest alone.

    Read-modify-write rather than a blind overwrite: several parts of the
    app own different keys in this one file, and a save that rewrote the
    whole thing from one caller's view of it would drop the others.
    """
    settings = load_settings()
    settings[key] = value
    save_settings(settings)
