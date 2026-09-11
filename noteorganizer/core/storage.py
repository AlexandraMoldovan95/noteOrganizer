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
shape all produce an empty default rather than an exception — after
preserving the unreadable file's bytes aside, so falling back to empty
can never destroy them. The app is meant to keep running with an empty
notebook, not refuse to start because one file got damaged.

``save_setting`` (singular) is read-modify-write rather than a blind
overwrite, so two features updating different keys cannot clobber each
other; every writer funnels through one atomic tmp-then-replace helper.

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

# Deleted notes live in the trash this many days, then auto-purge on
# startup. This is the DEFAULT; the actual window is a setting, read
# through trash_retention_days() below.
TRASH_RETENTION_DAYS = 30


def trash_retention_days():
    """The trash retention window in days: the user's setting, or the
    default. Clamped to a sane range -- a hand-edited settings file
    saying 0 (or "forever", or -3) must not make startup purge
    everything, so anything that isn't a usable number of days reads
    as the default. Read fresh on every call: the setting can change
    while the app runs, and the next purge should honour it."""
    days = get_setting("trash_retention_days")
    if isinstance(days, bool) or not isinstance(days, int):
        return TRASH_RETENTION_DAYS
    return max(1, min(days, 365))


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
        # Reached only when the file exists but held nothing usable —
        # keep its bytes before the next save replaces them.
        _preserve_corrupt(paths.SETTINGS_FILE)
    return {}


def save_settings(settings):
    """Write settings atomically — a failed write leaves the previous file
    intact (see _write_json_atomic), lands in crash_log.txt and reaches
    the registered on_write_failure callback.

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``."""
    return _write_json_atomic(paths.SETTINGS_FILE, settings)




def normalize_template(tpl):
    """Coerce a template dict into a known shape so bad/old data can't crash the
    manager or the 'use template' flow. A template holds a name plus the note
    fields it fills in: title, body, comments, category."""
    if not isinstance(tpl, dict):
        tpl = {}
    # Lazy, like this module's other model imports: model -> categories ->
    # storage at import time, so a top-level import here closes the loop.
    from .model import MAX_CHECKLIST_ITEMS

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
        # Capped like a note's checklist (same constant, same reason): a
        # template is one more door the original widget bomb walked
        # through — normalize_note's cap never sees a template, so an
        # imported/hand-edited templates.json with 20,000 items still
        # froze the app the moment the template was applied.
        "checklist": [
            {"text": it.get("text", "") if isinstance(it.get("text"), str) else "",
             "done": bool(it.get("done"))}
            for it in (tpl.get("checklist") or [])[:MAX_CHECKLIST_ITEMS]
            if isinstance(it, dict)
        ],
    }


def load_templates():
    if os.path.exists(paths.TEMPLATES_FILE):
        try:
            with open(paths.TEMPLATES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                kept = [normalize_template(t) for t in data if isinstance(t, dict)]
                if data and not kept:
                    # List-shaped but all junk: same as unreadable —
                    # keep the bytes before a save replaces them.
                    _preserve_corrupt(paths.TEMPLATES_FILE)
                return kept
        except (json.JSONDecodeError, IOError, OSError):
            pass
        # Reached only when the file exists but held nothing usable —
        # keep its bytes before the next save replaces them.
        _preserve_corrupt(paths.TEMPLATES_FILE)
    return []


def save_templates(templates):
    """Write the templates list atomically — a failed write leaves the
    previous file intact (see _write_json_atomic), lands in crash_log.txt
    and reaches the registered on_write_failure callback.

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``."""
    return _write_json_atomic(paths.TEMPLATES_FILE, templates)


def load_trash():
    """Read the trashed notes list. Malformed/missing -> empty list, never
    crashes; a malformed file is preserved aside first."""
    if os.path.exists(paths.TRASH_FILE):
        try:
            with open(paths.TRASH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, IOError, OSError):
            pass
        # Reached only when the file exists but held nothing usable —
        # keep its bytes before the next save replaces them.
        _preserve_corrupt(paths.TRASH_FILE)
    return []


def save_trash(trash):
    """Write the trashed notes list atomically — a failed write leaves the
    previous file intact (see _write_json_atomic), lands in crash_log.txt
    and reaches the registered on_write_failure callback.

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``."""
    return _write_json_atomic(paths.TRASH_FILE, trash)


def _attachment_path_within(stored_as):
    """Resolve *stored_as* to a path INSIDE the attachments folder, or
    None if it would escape it. `stored_as` is meant to be a bare
    timestamped filename (see add_attachment); a value carrying path
    separators or ``..`` — only possible from hand-crafted/imported
    data — must never resolve a delete to a file elsewhere on disk."""
    if not isinstance(stored_as, str) or not stored_as:
        return None
    if "\x00" in stored_as:
        # A NUL doesn't always make realpath raise (platform-dependent),
        # but a later os.remove/os.startfile on it raises ValueError,
        # which the sinks' `except OSError` would NOT catch — reject it
        # outright rather than let that escape.
        return None
    try:
        base = os.path.realpath(paths.ATTACHMENTS_DIR)
        candidate = os.path.realpath(os.path.join(base, stored_as))
        if candidate == base:
            return None  # the folder itself, not a file in it
        if os.path.commonpath([base, candidate]) != base:
            return None  # escaped the attachments folder
    except (ValueError, OSError):
        # commonpath raises ValueError across drives / UNC roots, and
        # realpath raises on an embedded NUL — all only reachable from a
        # crafted stored_as. "Can't resolve safely" means refuse, never
        # let the exception escape and crash the delete loop (which runs
        # unguarded at startup purge).
        return None
    return candidate


def copy_attachment_file(stored_as):
    """Copy an existing attachment to a fresh, unique on-disk name and
    return that name — so a duplicated note gets its OWN physical files
    instead of sharing the original's. A plain deep-copy of a note keeps
    the same stored_as values, i.e. the same files; permanently deleting
    either note then removed the file the other still referenced —
    silent attachment loss (audit finding). Returns None if the source
    is missing or the copy fails, and the caller keeps the old reference
    (no worse than before)."""
    src = _attachment_path_within(stored_as)
    if src is None or not os.path.isfile(src):
        return None
    base = os.path.basename(str(stored_as).replace("\\", "/"))
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    new_name = f"{stamp}_{base}"
    dest = os.path.join(paths.ATTACHMENTS_DIR, new_name)
    n = 1
    while os.path.exists(dest):
        new_name = f"{stamp}_{n}_{base}"
        dest = os.path.join(paths.ATTACHMENTS_DIR, new_name)
        n += 1
    try:
        shutil.copy2(src, dest)
        return new_name
    except (IOError, OSError):
        return None


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
            path = _attachment_path_within(stored_as)
            if path is None:
                # stored_as escaped the attachments folder (e.g. a
                # "../../file" smuggled in via a crafted share code) —
                # refuse to delete anything outside it. The same
                # path-traversal guard the zip import already applies,
                # now on the delete side too.
                continue
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
    cutoff = datetime.now() - timedelta(days=trash_retention_days())
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


# One implementation, shared with the pre-configure migration code in
# paths.py (which cannot import this module back without a cycle).
_preserve_corrupt = paths.preserve_corrupt_file


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
        * ``notes_file_corrupt`` -- True only if the notes file existed but
          held nothing usable. The caller must tell the user: starting
          with an empty list must never look like the notes vanished on
          their own.
        * ``corrupt_backup_path`` -- where the unreadable original was
          copied aside, or None if even that copy failed (the boolean
          above still says the file was unreadable).

        All are None/False the rest of the time, which is almost always.
    """
    # Imported here rather than at the top of the file because there is a
    # real cycle: storage -> model -> categories -> storage. At module level
    # it fails with "cannot import name 'load_settings' from partially
    # initialized module". Inside the function the import runs long after
    # every module is built, so it resolves cleanly.
    from .model import normalize_note, clean_notes

    report = {"version_backup_path": None, "cleanup_report": None,
              "notes_file_corrupt": False, "corrupt_backup_path": None}
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
        except (json.JSONDecodeError, IOError, OSError):
            raw = None
        if not isinstance(raw, list):
            # The file exists but held nothing usable — unparsable, or a
            # JSON value of the wrong shape. Keep its bytes before the
            # empty list below can be saved over them (that overwrite
            # used to be the moment a corrupt notebook became a
            # permanent loss), and flag it so the caller TELLS the user.
            report["notes_file_corrupt"] = True
            report["corrupt_backup_path"] = _preserve_corrupt(paths.DATA_FILE)
            raw = []
    if not isinstance(raw, list):
        raw = []

    # Every note gets the full set of fields, so no later code has to
    # guess whether an old note has 'comments' or 'attachments'.
    notes = [normalize_note(n) for n in raw if isinstance(n, dict)]
    if raw and not notes and not report["notes_file_corrupt"]:
        # A list-shaped file whose entries are all junk is the same loss
        # in a different costume — every note gone, nothing usable kept.
        # It must not slip past the preserve-and-announce net just
        # because the outermost bracket happened to be the right one.
        report["notes_file_corrupt"] = True
        report["corrupt_backup_path"] = _preserve_corrupt(paths.DATA_FILE)

    settings = load_settings()
    # The one-time cleanup would rewrite the notes file — on a launch
    # that just declared the file unreadable, that rewrite could destroy
    # the corrupt bytes at the very moment the startup notice tells the
    # user they are still on disk. There is nothing to clean in an empty
    # list anyway; the cleanup simply waits for the next healthy launch.
    if not settings.get("cleanup_done") and not report["notes_file_corrupt"]:
        backup_path = backup_notes_file()
        notes, stats = clean_notes(notes)
        report["cleanup_report"] = (stats, backup_path)

        _write_json_atomic(paths.DATA_FILE, notes)

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


# The UI registers a callback here at startup — core never imports
# tkinter, so this attribute is the one channel core has to say "that
# write FAILED" to whatever is drawing the window. Independently of the
# callback, every failed data-file write is appended to crash_log.txt
# (the same file the crash handlers use), so a failure on a route nobody
# checks still leaves a trace to diagnose.
on_write_failure = None


def _report_write_failure(path, exc):
    try:
        with open(os.path.join(paths.APP_DIR, "crash_log.txt"), "a",
                  encoding="utf-8") as f:
            f.write("\n--- %s (write failure) ---\n%s\n%r\n"
                    % (datetime.now().isoformat(), path, exc))
    except (IOError, OSError):
        pass
    cb = on_write_failure
    if cb is not None:
        try:
            cb(path, exc)
        except Exception:
            # The reporter must never take down the save path it reports
            # on — a broken callback would turn "write failed" into a
            # crash loop. The failure itself is already in the log above.
            pass


def _write_json_atomic(path, value):
    """Write a JSON data file the one safe way: mend surrogates, dump to a
    sibling ``.tmp``, then atomically replace the real file. A crash
    mid-write leaves the old file whole, and an unencodable value fails
    cleanly instead of leaving a truncated file behind. Every data file
    the app owns saves through here — notes_data.json learned each of
    these guards from a real loss, and its siblings (trash, templates,
    settings) once lacked all of them, so an emoji in a deleted note
    could corrupt trash.json outright.

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``.
    """
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(mend_surrogates(value), f, indent=2,
                      ensure_ascii=False)
        # Atomic replace: a crash mid-write can't corrupt the real file,
        # it either fully updates or stays as it was.
        os.replace(tmp_path, path)
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
        _report_write_failure(path, exc)
        return False, exc


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
    return _write_json_atomic(paths.DATA_FILE, notes)


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
    return max(0, trash_retention_days() - elapsed)


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
