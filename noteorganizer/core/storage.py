"""Reading and writing the app's data files.

Everything that touches settings.json, templates.json and trash.json, and
the copy of the notes file made before it is rewritten. The locations are
read from :mod:`.paths` when a function runs, never copied at import time,
when they are not yet known. Every loader returns something usable
whatever it finds -- a missing, unreadable or wrongly shaped file gives an
empty default, after the unreadable bytes are kept aside -- and every
writer goes through one atomic helper. docs/CODE_TOUR.md walks through it.
"""

import json
import os
import shutil
import time
from datetime import datetime

from . import diagnostics, paths
# normalize_template validates a template's rich-text spans and its
# paragraph formatting, so the storage layer needs both validators.
from .formatting import (normalize_formatting, normalize_paragraphs,
                         clamp_spans_per_line)

# Deleted notes live in the trash this many days, then auto-purge on
# startup. This is the DEFAULT; the actual window is a setting, read
# through trash_retention_days() below.
TRASH_RETENTION_DAYS = 30

# Set by load_settings on an unreadable settings.json, kept by every
# writer until choose_trash_window; True, then "told" once the startup
# notice has said so. ISSUES_LOG: "The Trash that forgot its window".
TRASH_WINDOW_UNKNOWN = "desktop_trash_window_unknown"


def trash_retention_days():
    """The trash retention window in days, or None when it is not known --
    settings.json unreadable (TRASH_WINDOW_UNKNOWN), or a stored value that
    is not a whole number from 1 to 365 -- and then nothing leaves the
    Trash by itself. Never chosen, it is the default. Read fresh each call:
    the setting can change mid-run."""
    settings = load_settings()
    if settings.get(TRASH_WINDOW_UNKNOWN):
        return None
    if "trash_retention_days" not in settings:
        return TRASH_RETENTION_DAYS
    days = settings["trash_retention_days"]
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 365:
        return None
    return days


def trash_window_words(lead):
    """" within 30 days" -- *lead* and the window in force, for a promise a
    delete makes about the Trash -- or "" while the window is not known,
    when no number of days would be true."""
    days = trash_retention_days()
    return "" if days is None else f" {lead} {days} days"


def choose_trash_window(days):
    """Save the window the person chose, and with it forget that the one
    before could not be read: one write, so no start can see either half
    alone. Returns what save_settings returns."""
    settings = load_settings()
    settings["trash_retention_days"] = days
    settings.pop(TRASH_WINDOW_UNKNOWN, None)
    return save_settings(settings)


# ---- Settings file (read/modify/write, so keys never clobber each other) ----

def load_settings():
    if os.path.exists(paths.SETTINGS_FILE):
        try:
            with open(paths.SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (*paths.JSON_UNREADABLE, IOError, OSError):
            pass
        # Reached only when the file exists but held nothing usable —
        # keep its bytes before the next save replaces them.
        _preserve_corrupt(paths.SETTINGS_FILE)
        # And say that the Trash's window went with them, or the next
        # write turns "unknown" into "never chosen" (TRASH_WINDOW_UNKNOWN).
        return {TRASH_WINDOW_UNKNOWN: True}
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
        # Capped per line like a note's, and for the same reason the
        # checklist above is capped here: normalize_note never sees a
        # template, so this is its own door into the editor.
        "formatting": clamp_spans_per_line(
            _s("body"), normalize_formatting(tpl.get("formatting"))),
        "paragraphs": normalize_paragraphs(tpl.get("paragraphs"),
                                           len(_s("body").split("\n"))),
        "comments": _s("comments"),
        "category": _s("category") or "General",
        # Capped like a note's checklist, since normalize_note never sees a
        # template: 20,000 items in templates.json froze the app the moment
        # the template was applied.
        "checklist": [
            {"text": it.get("text", "") if isinstance(it.get("text"), str) else "",
             "done": bool(it.get("done"))}
            # isinstance first: the cap's slice raises on a dict-shaped
            # value, and templates.json is hand-editable -- what used to
            # degrade to an empty checklist would have crashed startup.
            for it in (tpl.get("checklist")
                       if isinstance(tpl.get("checklist"), list)
                       else [])[:MAX_CHECKLIST_ITEMS]
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
        except (*paths.JSON_UNREADABLE, IOError, OSError):
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
    """Read the trashed notes list: missing or malformed gives [], after the
    file is preserved aside. Only dict entries come in, kept as the file held
    them: a string or null beside them kept Recently deleted from opening,
    and the real notes could not be restored."""
    if os.path.exists(paths.TRASH_FILE):
        try:
            with open(paths.TRASH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                kept = [e for e in data if isinstance(e, dict)]
                if len(kept) != len(data):
                    _preserve_corrupt(paths.TRASH_FILE)
                return kept
        except (*paths.JSON_UNREADABLE, IOError, OSError):
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
        # Refused outright: realpath does not always raise on a NUL, but a
        # later remove or startfile raises ValueError, which the sinks'
        # "except OSError" would not catch.
        return None
    try:
        base = os.path.realpath(paths.ATTACHMENTS_DIR)
        named = os.path.normpath(os.path.join(base, stored_as))
        candidate = os.path.realpath(named)
        if candidate == base:
            return None  # the folder itself, not a file in it
        if os.path.commonpath([base, candidate]) != base:
            return None  # escaped the attachments folder
        # The file reached must be the file named: NTFS aliases (a short
        # name, "::$DATA") passed every name check upstream and reached
        # another file. ISSUES_LOG: "A file with two names".
        if os.path.normcase(candidate) != os.path.normcase(named):
            return None
    except (ValueError, OSError):
        # commonpath raises across drives and UNC roots, realpath on a NUL:
        # "cannot resolve safely" means refuse, never crash the delete loop,
        # which runs unguarded in the startup purge.
        return None
    return candidate


def copy_attachment_file(stored_as):
    """Copy an attachment to a fresh unique name and return it, or None if
    the source is missing or the copy fails (the caller keeps the old name).
    A duplicated note needs files of its own: sharing them, a permanent
    delete of either note removed the other's. ISSUES_LOG: "The duplicate
    that wasn't a copy"."""
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


def attachments_of(note):
    """The attachments of a note or Trash entry that name a file: dicts with
    a non-empty string stored_as. Trash entries come in as the file held
    them, and a 7, a true or a list there stopped the app at every start."""
    atts = note.get("attachments") if isinstance(note, dict) else None
    if not isinstance(atts, list):
        return []
    return [a for a in atts if isinstance(a, dict)
            and isinstance(a.get("stored_as"), str) and a["stored_as"]]


def attachment_names_in(notes_or_entries):
    """The stored file name of every attachment these notes (or trash
    entries) use."""
    return {att["stored_as"] for note in notes_or_entries
            for att in attachments_of(note)}


def _delete_attachment_files(notes_or_entries, spare=()):
    """Remove the files of every attachment these notes or trash entries use
    -- only for PERMANENT deletion (purge, delete forever, empty trash): a
    note moved to the Trash may still come back. *spare* names files that
    must survive, those the notes in the app still use, in case a stale row
    acts. ISSUES_LOG: "The Trash that gave notes back one at a time"."""
    for note in notes_or_entries:
        for att in attachments_of(note):
            stored_as = att["stored_as"]
            if stored_as in spare:
                continue
            path = _attachment_path_within(stored_as)
            if path is None:
                # Outside the attachments folder (a "../../file" from a
                # crafted share code): refused, as the zip import refuses it.
                continue
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass  # best-effort — a locked/missing file shouldn't block the delete


def _trash_cutoff(days=None):
    """The moment (real seconds) an entry has to predate to have expired.

    `days=None` means the window currently in force, and gives None while
    that window is not known: then nothing has expired. A number being
    PREVIEWED is clamped to 1-365, so no preview can name more than a
    window the dropdown offers would remove.
    """
    if days is None:
        window = trash_retention_days()
        if window is None:
            return None
    elif isinstance(days, bool) or not isinstance(days, int):
        window = TRASH_RETENTION_DAYS
    else:
        window = max(1, min(days, 365))
    return _now_epoch() - window * 86400


def _now_epoch():
    """Now, in real seconds. One name, so a test can stand the clock still."""
    return time.time()


def _local_epoch(when):
    """A local wall-clock moment, in real seconds: mktime places it with the
    offset in force on THAT day, not today's."""
    return time.mktime(when.timetuple())


def _deleted_epoch(stamp):
    """When a Trash entry was deleted, in real seconds; None if its stamp is
    unreadable. The stamp is wall-clock time, and an age measured on the
    wall clock is an hour off across a change to or from summer time -- in
    spring the purge took notes an hour before the window was up. Counted
    in real time, as the Android app counts (2026-10-26)."""
    try:
        when = datetime.strptime(stamp or "", "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    try:
        return _local_epoch(when)
    except (OverflowError, OSError, ValueError):
        # Before 1970 (Windows' mktime refuses it) or past its reach: a
        # hand-edited stamp, outside every window. Read as UTC, so it is
        # past or not as it always was, never kept for good as unreadable.
        return (when - datetime(1970, 1, 1)).total_seconds()


def _trash_entry_is_past(entry, cutoff):
    """THE single answer to "has this entry outlived the window?", asked by
    the startup purge and by trash_entries_past_window, so a dialog names
    what a shorter window will destroy by the very rule the purge uses. An
    unreadable deleted_at is never past, and nothing is past a window not
    known (cutoff None): better kept too long than early."""
    if cutoff is None or not isinstance(entry, dict):
        return False
    when = _deleted_epoch(entry.get("deleted_at", ""))
    return when is not None and when < cutoff


def trash_entries_past_window(trash, days=None):
    """The entries a retention window of `days` has already outlived.

    Nothing is deleted and no file is touched -- this is the question on
    its own, so a confirmation can name what it is about to cost. With
    `days=None` it describes the window in force, which is exactly what
    the next startup's purge will remove.
    """
    cutoff = _trash_cutoff(days)
    return [entry for entry in (trash or [])
            if _trash_entry_is_past(entry, cutoff)]


def purge_expired_trash(trash, notes):
    """Remove entries older than the retention window. Returns (kept, purged
    count). An entry with a missing/invalid deleted_at is kept: better too
    long than early. The purged notes' attached files go too -- the one
    deletion nobody asks for must not leave orphans -- except a file *notes*
    or a kept entry still uses, as Delete and Empty trash spare it
    (ISSUES_LOG: "The Trash that forgot its window")."""
    cutoff = _trash_cutoff()
    kept = []
    purged_entries = []
    for entry in (trash or []):
        if _trash_entry_is_past(entry, cutoff):
            purged_entries.append(entry)
        else:
            kept.append(entry)
    _delete_attachment_files(
        purged_entries, spare=attachment_names_in(list(notes or []) + kept))
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
# The version change is a parameter, not the entry module's global, which a
# second import never sets: ISSUES_LOG, "The module that existed twice".

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
        * ``categories_adopted`` -- the category names the notes were
          filed under that settings.json had lost, now back in the map
          with default colours. The caller says so: the colours changed,
          and the user should know why.
        * ``fresh_notebook`` -- True only if there was no notes file at all:
          a first install, the one notebook the welcome note is for. An
          unreadable or emptied notebook still had its file, so is not.

        All are None/False/empty the rest of the time, which is almost
        always.
    """
    # Imported here: storage -> model -> categories -> storage is a real
    # cycle, and at module level the import fails half-initialised.
    from .model import normalize_note, clean_notes, repair_note_ids
    from .categories import adopt_categories_of, persist_categories

    report = {"version_backup_path": None, "cleanup_report": None,
              "notes_file_corrupt": False, "corrupt_backup_path": None,
              "categories_adopted": [],
              "fresh_notebook": not os.path.exists(paths.DATA_FILE)}
    raw = []
    if os.path.exists(paths.DATA_FILE):
        # After an upgrade, a snapshot before this version's code can rewrite
        # the file -- on every update, not only the first run. Never deleted
        # automatically: old backups are the user's to throw away.
        if version_change and version_change[0] == "up":
            report["version_backup_path"] = backup_notes_file()
        try:
            with open(paths.DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (*paths.JSON_UNREADABLE, IOError, OSError):
            raw = None
        if not isinstance(raw, list):
            # There, but nothing usable: its bytes are kept before an empty
            # list can be saved over them (once the moment a corrupt notebook
            # was lost for good), and the caller is told to TELL the user.
            report["notes_file_corrupt"] = True
            report["corrupt_backup_path"] = _preserve_corrupt(paths.DATA_FILE)
            raw = []
    if not isinstance(raw, list):
        raw = []

    # The notes' own categories join the map BEFORE normalising, which files
    # an unknown category under General; saved at once, before the cleanup
    # below reads the settings, so its own write carries them too.
    report["categories_adopted"] = adopt_categories_of(raw)
    if report["categories_adopted"]:
        persist_categories()

    # Every note gets the full set of fields, so no later code has to
    # guess whether an old note has 'comments' or 'attachments'.
    notes = [normalize_note(n) for n in raw if isinstance(n, dict)]
    ids_repaired = repair_note_ids(notes)
    # Identities minted in memory differ every launch unless written down
    # (ISSUES_LOG: "The identity that only lasted until you closed the
    # app"), so a read that minted any writes them, once, after the cleanup.
    minted_any = any(
        isinstance(n, dict) and not str(n.get("uid") or "").strip()
        for n in raw)
    if raw and not notes and not report["notes_file_corrupt"]:
        # A list of nothing but junk is the same loss in another costume:
        # preserved and announced like a file that cannot be read.
        report["notes_file_corrupt"] = True
        report["corrupt_backup_path"] = _preserve_corrupt(paths.DATA_FILE)

    settings = load_settings()
    # The one-time cleanup rewrites the file, so it waits out a launch that
    # just declared the file unreadable: the startup notice is promising
    # those bytes are still on disk (and an empty list has nothing to clean).
    if not settings.get("cleanup_done") and not report["notes_file_corrupt"]:
        backup_path = backup_notes_file()
        # The cleanup renumbers every id from 1, so the remembered open note
        # is re-pointed by identity, or forgotten if the cleanup removed it.
        # ISSUES_LOG, smaller lessons: load_notes.
        remembered = settings.get("last_open_note_id")
        was_open = None
        if remembered is not None:
            was_open = next(
                (n for n in notes if n.get("id") == remembered), None)
        notes, stats = clean_notes(notes)
        if remembered is not None:
            settings["last_open_note_id"] = (
                was_open["id"]
                if was_open is not None and any(n is was_open for n in notes)
                else None)
        report["cleanup_report"] = (stats, backup_path)

        _write_json_atomic(paths.DATA_FILE, notes)

        settings["cleanup_done"] = True
        save_settings(settings)
        # That write already carries the new identities, and numbers
        # every note afresh besides.
        minted_any = False
        ids_repaired = False

    if (minted_any or ids_repaired) and not report["notes_file_corrupt"]:
        # Guarded like the cleanup: never over a file just declared
        # unreadable. A failure needs no dialog, as the next save writes them
        # anyway; repaired ids ride along, or a read-only session repeats it.
        try:
            _write_json_atomic(paths.DATA_FILE, notes)
        except (IOError, OSError):
            pass

    return notes, report


def mend_surrogates(value):
    """Recombine UTF-16 surrogate pairs into the characters they spell.

    Tk hands astral characters (most emoji) to Python as two surrogates,
    which cannot be UTF-8 encoded: the first emoji typed killed every save
    after it. A lone surrogate becomes U+FFFD. ISSUES_LOG: "The mend that
    only ran on the way to disk"."""
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


# The UI registers a callback here at startup: core never imports tkinter, so
# this is its one way to say "that write FAILED". Every failed write is also
# appended to crash_log.txt, so a route nobody checks still leaves a trace.
on_write_failure = None


def _report_write_failure(path, exc):
    # The file's name and the error's kind, never its folder: the path holds
    # the person's name, and an OSError's own text repeats the path.
    diagnostics.append_crash_log("write failure", "%s: %s (errno %s, %s)" % (
        os.path.basename(path), type(exc).__name__, getattr(exc, "errno", None),
        getattr(exc, "strerror", None)))
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
    sibling ``.tmp``, then atomically replace the real file, so a crash
    mid-write leaves the old file whole and an unencodable value fails
    cleanly. Every data file the app owns saves through here. ISSUES_LOG:
    "The mend that only ran on the way to disk".

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``.
    """
    tmp_path = path + ".tmp"
    try:
        # Mended only when needed: mend_surrogates rebuilds the notebook (a
        # quarter of an autosave at 5,000 notes), while asking the dumped text
        # whether it encodes is one C pass, and the bytes come out the same.
        text = json.dumps(value, indent=2, ensure_ascii=False)
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            text = json.dumps(mend_surrogates(value), indent=2,
                              ensure_ascii=False)
        with open(tmp_path, "w", encoding="utf-8") as f:
            # One string, one write: json.dump streams the same bytes in
            # thousands of pieces, twice the time at 1,000 notes (36 ms to 18).
            f.write(text)
            # On the disk before the rename: a power cut just after a replace
            # could otherwise leave an empty file where the notes were.
            f.flush()
            os.fsync(f.fileno())
        # Atomic replace: a crash mid-write can't corrupt the real file,
        # it either fully updates or stays as it was.
        os.replace(tmp_path, path)
        return True, None
    # ValueError covers UnicodeEncodeError, TypeError the unserializable:
    # catching I/O alone let an emoji through, and every edit after it lived
    # only in the running app.
    except (IOError, OSError, ValueError, TypeError) as exc:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        _report_write_failure(path, exc)
        return False, exc


def save_notes(notes):
    """Write notes to disk, returning why a write failed rather than showing
    it: a failure nobody saw is how notes once 'vanished' on other PCs, and
    the caller, which owns the window, decides how to say so.

    Returns:
        ``(True, None)`` on success, or ``(False, exception)``.
    """
    return _write_json_atomic(paths.DATA_FILE, notes)


# ---- Trash operations ----
# The data half of "delete" and "restore"; the caller redraws the screen.

def move_notes_to_trash(trash, notes_to_trash):
    """Move notes into the trash with a deletion timestamp.

    Nothing is destroyed -- every delete path goes through here so a note is
    never lost without its grace period.

    Args:
        trash: the current trash list, appended to in place.
        notes_to_trash: the notes being removed from the active list.

    Returns:
        ``(True, None)`` once trash.json holds them, or ``(False, exception)``
        with *trash* as it was: the caller must then keep the notes, or they
        are in neither file (ISSUES_LOG: "A delete that trusted the Trash").
    """
    before = len(trash)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for note in notes_to_trash:
        entry = dict(note)
        entry["deleted_at"] = stamp
        trash.append(entry)
    ok, exc = save_trash(trash)
    if not ok:
        del trash[before:]
    return ok, exc


def days_left_in_trash(deleted_at):
    """How many days until this trashed note auto-purges. None if unknown --
    the stamp unreadable, or the window (then it never purges by itself)."""
    when = _deleted_epoch(deleted_at)
    if when is None:
        return None
    window = trash_retention_days()
    if window is None:
        return None
    # Real days, by the purge's own clock, so the row and the purge agree;
    # a stamp in the future (a clock put right since) is "just deleted".
    elapsed = max(0, int((_now_epoch() - when) // 86400))
    return max(0, window - elapsed)


def restore_from_trash(notes, trash, entry):
    """Bring one trashed note back into the active list; see
    :func:`restore_many_from_trash`, which this is one case of.

    Returns:
        ``(notes, trash)`` -- both lists. Nothing is written to disk.
    """
    notes, trash, _restored = restore_many_from_trash(notes, trash, [entry])
    return notes, trash


def restore_many_from_trash(notes, trash, entries):
    """Bring trashed notes back into the active list, in one pass.

    Nothing is written: the caller saves the notes FIRST and the trash after,
    so a failed write leaves a duplicate at worst, never a note in neither
    file. ISSUES_LOG: "The Trash that gave notes back one at a time"; smaller
    lessons: restore_many_from_trash, on why no category is checked here.

    Args:
        notes: the active note list, appended to in place.
        trash: the trash list; ``entries`` are removed from it.
        entries: the trashed notes to restore (objects from ``trash``).

    Returns:
        ``(notes, trash, restored)`` -- the two lists, and the notes that
        were appended, in order.
    """
    from .model import new_note_uid, normalize_note

    leaving = {id(e) for e in entries}
    next_id = max([n["id"] for n in notes], default=0) + 1
    worn = {n.get("uid") for n in notes if isinstance(n, dict)}
    restored = []
    for entry in entries:
        # normalize_note rebuilds the note from a known schema, so it drops
        # "deleted_at" and anything else the trash entry carried.
        note = normalize_note(entry)
        # A fresh id: the trashed note's own id may have been reused by a
        # note created after it was deleted.
        note["id"] = next_id
        next_id += 1
        # A new identity only if a copy arrived by share code while this one
        # sat in the trash (two notes, one identity); otherwise it is kept,
        # so a code made before the delete still finds the note.
        if note.get("uid") in worn:
            note["uid"] = new_note_uid()
        worn.add(note["uid"])
        notes.append(note)
        restored.append(note)
    trash = [e for e in trash if id(e) not in leaving]
    return notes, trash, restored


# ---- Single settings values ----
# Read-modify-write of the whole file for one value, so a save never wipes a
# key it did not mean to touch (the one-time cleanup flag, say).

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
