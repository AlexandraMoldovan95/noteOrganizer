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
# normalize_template validates a template's rich-text spans, so the
# storage layer needs the span validator.
from .formatting import normalize_formatting

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
