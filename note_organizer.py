# note_organizer.py
# A simple, colorful, offline Notes Organizer app
# Notes are saved locally to notes_data.json, so they persist between sessions.

import tkinter as tk
from tkinter import ttk, filedialog
import tkinter.font as tkfont
import json
import os
import sys
import shutil
import zipfile
import tempfile
import zlib
import threading
import base64
import calendar as cal_module
import re
import math
from datetime import datetime, date as date_cls, timedelta

try:
    from PIL import Image, ImageTk
except ImportError:
    import tkinter.messagebox as _messagebox
    _root = tk.Tk()
    _root.withdraw()
    _messagebox.showerror(
        "Missing dependency",
        "Note Organizer needs the Pillow library to run (used for image "
        "previews).\n\nInstall it with:\n\n    pip install Pillow\n\n"
        "then start the app again."
    )
    sys.exit(1)


# ---- Version ----
# Single source of truth. Bump this by hand at every release (see
# docs/ROADMAP.md's "Versioning" section for the exact policy and how the
# numbers are calculated — summary: MAJOR stays 0 until a real public
# launch; until then, MINOR/PATCH are cumulative all-time totals of
# Added/Fixed CHANGELOG.md entries, not per-release counts). The running
# app records this into settings, so the next time a newer build opens
# over older data it can tell the user what changed version-wise.
APP_VERSION = "0.32.44"


def parse_version(v):
    """'2.1.0' -> (2, 1, 0). Bad input sorts as (0,0,0) so it never crashes a
    comparison."""
    try:
        parts = [int(x) for x in str(v).strip().split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


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


def _is_writable(folder):
    """True if we can actually create a file here. Existence isn't enough —
    Program Files exists too, but writing to it silently fails."""
    try:
        os.makedirs(folder, exist_ok=True)
        probe = os.path.join(folder, ".write_test")
        with open(probe, "w") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except (IOError, OSError):
        return False


def resolve_data_dir():
    """Pick the data folder, guaranteeing it's writable.

    Returns (folder, note) where note is a user-facing warning if we had to
    fall back from the preferred location, else None."""
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
        import tempfile
        tmp = os.path.join(tempfile.gettempdir(), "NoteOrganizer")
        return tmp, (
            "Couldn't find a permanent place to save notes on this PC, so a "
            "temporary folder is being used. Export your notes regularly — "
            "temporary files can be cleared by Windows."
        )

    # Development: run as a script -> beside the .py file.
    script_dir = os.path.dirname(os.path.abspath(__file__))
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
            try:
                shutil.copy2(appdata_settings, settings_path)
            except (IOError, OSError):
                pass

        _copy_attachments(appdata_dir, attachments_path)

        settings = _settings()
        settings["reclaimed_from_appdata"] = True
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except (IOError, OSError):
            pass

        message = (
            f"Moved your notebook back into the app folder:\n{app_dir}\n\n"
            f"Brought {moved} note(s) back from:\n{appdata_dir}"
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
    if os.path.exists(legacy_settings):
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
    """Identity of a note by its content, ignoring id and timestamps."""
    return {
        (
            str(n.get("title", "")).strip(),
            str(n.get("body", "")).strip(),
            str(n.get("comments", "")).strip(),
            str(n.get("category", "")),
            str(n.get("date", "")),
        )
        for n in notes if isinstance(n, dict)
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
    """Every attached file in the old folder must already exist in the new one."""
    stale_attach = os.path.join(stale_dir, "attachments")
    if not os.path.isdir(stale_attach):
        return True
    local_attach = os.path.join(app_dir, "attachments")
    for filename in os.listdir(stale_attach):
        if os.path.isfile(os.path.join(stale_attach, filename)):
            if not os.path.exists(os.path.join(local_attach, filename)):
                return False
    return True


def purge_stale_copies(app_dir):
    """Delete leftover data in folders the app no longer reads from, so there
    is exactly one notebook on disk.

    Deletion only happens when ALL of these hold:
      - the local notes file exists and is readable
      - every note in the stale copy is already present locally
      - every attachment in the stale folder is already present locally
      - the file being deleted is one this app created
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
            if os.path.isfile(full) and _is_owned_file(filename):
                try:
                    os.remove(full)
                    removed_anything = True
                except OSError:
                    pass

        stale_attach = os.path.join(stale_dir, "attachments")
        if os.path.isdir(stale_attach):
            try:
                shutil.rmtree(stale_attach)
                removed_anything = True
            except OSError:
                pass

        if removed_anything:
            cleared.append(stale_dir)

    return cleared


APP_DIR, STORAGE_WARNING = resolve_data_dir()
MIGRATION_INFO = run_migrations(APP_DIR)
PURGED_DIRS = purge_stale_copies(APP_DIR)

DATA_FILE = os.path.join(APP_DIR, "notes_data.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
ATTACHMENTS_DIR = os.path.join(APP_DIR, "attachments")
TRASH_FILE = os.path.join(APP_DIR, "trash.json")
TEMPLATES_FILE = os.path.join(APP_DIR, "templates.json")

# Deleted notes live in the trash this many days, then auto-purge on startup.
TRASH_RETENTION_DAYS = 30
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)


# ---- Settings file (read/modify/write, so keys never clobber each other) ----

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return {}


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except (IOError, OSError):
        pass


# ---- Rich text formatting (note body only) ----
#
# A note's "body" stays a plain string everywhere (search, duplicate
# detection, share codes, templates, previews) — untouched by this feature.
# Formatting lives in a separate, additive field: a flat list of
# {"start", "end", "style"} spans (plus "value" for the two color styles
# below), character-offset-based into the plain body text. "bold_italic"
# is its own style name (not "bold" + "italic" both present) because
# Tkinter Text tags that both set the widget's font option don't compose —
# only one wins — so bold+italic together has to be one precomputed
# compound font, same as a real font would have a distinct bold-italic
# variant rather than layering two independent effects.
KNOWN_FORMAT_STYLES = {"bold", "italic", "bold_italic", "underline", "strike"}

# text_color/highlight carry a "value" (a hex color) instead of being plain
# on/off styles. Unlike bold/italic, foreground/background are independent
# Tk tag options — they don't fight the font option the way bold and italic
# do, so no compound-tag scheme is needed for these two.
VALUE_FORMAT_STYLES = {"text_color", "highlight"}


def _is_valid_hex_color(value):
    return (isinstance(value, str) and len(value) == 7 and value[0] == "#"
            and all(c in "0123456789abcdefABCDEF" for c in value[1:]))


def normalize_formatting(value):
    """Coerce a note/template's formatting list to valid spans, silently
    dropping anything malformed (bad type, unknown style, out-of-order or
    non-integer offsets, or — for text_color/highlight — a missing/invalid
    hex value) rather than ever letting bad data crash the editor."""
    if not isinstance(value, list):
        return []
    spans = []
    for span in value:
        if not isinstance(span, dict):
            continue
        style = span.get("style")
        start, end = span.get("start"), span.get("end")
        if not (isinstance(start, int) and not isinstance(start, bool)
                and isinstance(end, int) and not isinstance(end, bool)
                and 0 <= start < end):
            continue
        if style in KNOWN_FORMAT_STYLES:
            spans.append({"start": start, "end": end, "style": style})
        elif style in VALUE_FORMAT_STYLES and _is_valid_hex_color(span.get("value")):
            spans.append({"start": start, "end": end, "style": style,
                          "value": span["value"].lower()})
    return spans


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
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [normalize_template(t) for t in data if isinstance(t, dict)]
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return []


def save_templates(templates):
    try:
        with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)
    except (IOError, OSError):
        pass


def detect_version_change():
    """Compare the version recorded in settings against the running app, then
    record the current version. Returns one of:
        None            -> same version, or first run (nothing to announce)
        ('up', old,new) -> app is newer than the data (an update happened)
        ('down',old,new)-> app is OLDER than the data (user ran an old build)
    First run records the version silently — there's no prior version to have
    'updated from', so claiming one would be a lie."""
    settings = load_settings()
    stored = settings.get("app_version")

    result = None
    if stored:
        old, new = parse_version(stored), parse_version(APP_VERSION)
        if new > old:
            result = ("up", stored, APP_VERSION)
        elif new < old:
            # A lower running version than what's on record. Before launch this
            # is just us re-baselining the version number (e.g. an early build
            # briefly recorded a higher number), NOT a real downgrade — so stay
            # silent and quietly adopt the current version. Once the app is
            # public, real downgrades are rare and this stays conservative.
            result = None

    # Always record the current version (unless it's already identical).
    if stored != APP_VERSION:
        settings["app_version"] = APP_VERSION
        save_settings(settings)

    return result


def get_first_launch_date():
    """Returns the date the app was first ever run — stamped once, the
    first time this executes, and never overwritten after. Existing
    installs from before this was added get today's date recorded as their
    starting point; there's no way to know their real first-use date
    retroactively."""
    settings = load_settings()
    stamped = settings.get("first_launch_date")
    if not isinstance(stamped, str) or not stamped:
        stamped = date_cls.today().isoformat()
        settings["first_launch_date"] = stamped
        save_settings(settings)
    return stamped


VERSION_CHANGE = detect_version_change()
FIRST_LAUNCH_DATE = get_first_launch_date()


# ---- Note schema + one-time cleanup ----

NOTE_DEFAULTS = {
    "title": "",
    "body": "",
    "formatting": [],   # list of {"start","end","style"} spans over body
    "comments": "",
    "category": "General",
    "date": "",
    "color": "",
    "attachments": [],
    "updated": "",
    "created": "",      # when the note was first made; backfilled for old notes
    "recurrence": {},   # empty dict = one-off note (see the recurrence engine)
    "exceptions": [],   # dates removed from a series
    "overrides": {},    # date -> partial note, for per-occurrence edits
    "pinned": False,    # pinned notes float to the top of the list
    "checklist": [],    # list of {"text": str, "done": bool} items
}



# Broad-ish emoji ranges — enough to catch common emoji people actually type
# in a note title (faces, symbols, transport, flags, etc.) without pulling in
# a full unicode-data dependency just for this.
_EMOJI_PATTERN = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\U0001F900-\U0001F9FF]",
    flags=re.UNICODE,
)


def _extract_first_emoji(text):
    """Find the first emoji anywhere in a string (title, etc.), or None. Used
    to surface a note's own emoji on its calendar day even when the title is
    long enough that the emoji itself would otherwise get truncated away."""
    if not isinstance(text, str) or not text:
        return None
    m = _EMOJI_PATTERN.search(text)
    return m.group(0) if m else None


def _darken_hex(hex_color, factor=0.85):
    """Return a slightly darker shade of a #rrggbb color, for hover states on
    fixed (non-theme) colored chips."""
    hex_color = hex_color.lstrip("#")
    try:
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hex_color
    r, g, b = (max(0, int(v * factor)) for v in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _truncate(text, limit=60):
    """Shorten a string for display with an ellipsis, collapsing newlines so a
    multi-line title can't blow up the layout. The stored value is never
    changed — this is display-only."""
    if not isinstance(text, str):
        return ""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[:limit].rstrip() + "…"


def _note_str(note, key, default=""):
    """Read a note field as a string, coercing missing/None/non-string values to
    a default. Used in render paths so a single malformed note can never crash
    the list, calendar, or day panels."""
    value = note.get(key) if isinstance(note, dict) else None
    return value if isinstance(value, str) else default


def normalize_note(note):
    """Guarantee every note has every field, with the right type. Older notes
    were saved before 'comments', 'date', 'color' and 'attachments' existed,
    and code that reads note['title'] directly crashes on those."""
    clean = {}
    clean["id"] = note.get("id", 0)
    for key, default in NOTE_DEFAULTS.items():
        value = note.get(key, default)
        if isinstance(default, str) and not isinstance(value, str):
            value = default
        if isinstance(default, list) and not isinstance(value, list):
            value = []
        if isinstance(default, dict) and not isinstance(value, dict):
            value = {}
        clean[key] = value
    if not clean["updated"]:
        # Includes seconds (not just minutes) so two notes saved in the same
        # minute still sort correctly by "Recently updated" instead of tying.
        clean["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Old notes predate the 'created' field — approximate it with 'updated' so
    # they still show a sensible creation date.
    if not clean["created"]:
        clean["created"] = clean["updated"]
    clean["pinned"] = bool(clean.get("pinned"))
    if clean["category"] not in CATEGORY_COLORS:
        clean["category"] = "General"

    clean["recurrence"] = normalize_recurrence(clean["recurrence"])

    # A recurring rule with no anchor date can't be placed on a calendar,
    # so it degrades to a normal note instead of silently disappearing.
    if clean["recurrence"]["freq"] and not parse_date(clean["date"]):
        clean["recurrence"] = normalize_recurrence({})

    clean["exceptions"] = sorted({
        d for d in clean["exceptions"] if isinstance(d, str) and parse_date(d)
    })
    clean["overrides"] = {
        d: {k: v for k, v in patch.items() if k in OVERRIDABLE_FIELDS and isinstance(v, str)}
        for d, patch in clean["overrides"].items()
        if isinstance(d, str) and parse_date(d) and isinstance(patch, dict)
    }


    # Tags were removed as a feature — drop any leftover "tags" key from
    # notes saved before this cleanup, so old data doesn't keep carrying it
    # around indefinitely once re-saved.
    clean.pop("tags", None)

    # Checklist: coerce each item to {"text": str, "done": bool}, dropping junk.
    checklist = []
    for item in clean.get("checklist", []):
        if isinstance(item, dict):
            text = item.get("text", "")
            if not isinstance(text, str):
                text = ""
            checklist.append({"text": text, "done": bool(item.get("done"))})
    clean["checklist"] = checklist

    clean["formatting"] = normalize_formatting(clean.get("formatting"))

    return clean


def note_richness(note):
    """Used to decide which copy of a duplicate to keep: the one carrying the
    most extra data (attachments beat color beat date beat comments)."""
    score = 0
    if note.get("attachments"):
        score += 8
    if note.get("color"):
        score += 4
    if note.get("date"):
        score += 2
    if note.get("comments"):
        score += 1
    return score


def note_is_empty(note):
    """A note with no title, no body, no comments and no attachments is a
    stray '+ New Note' click, not real content."""
    def _s(v):
        return v.strip() if isinstance(v, str) else ""
    return not (
        _s(note.get("title"))
        or _s(note.get("body"))
        or _s(note.get("comments"))
        or note.get("attachments")
    )


def clean_notes(notes):
    """Drop empty notes, collapse exact duplicates, and re-number IDs.
    Returns (cleaned_notes, stats)."""
    stats = {"before": len(notes), "empty_removed": 0, "duplicates_removed": 0}

    kept = [n for n in notes if not note_is_empty(n)]
    stats["empty_removed"] = len(notes) - len(kept)

    # Two notes are "the same" if their actual content matches. 'updated'
    # and 'id' are deliberately excluded — those differ on copies.
    best_by_signature = {}
    order = []
    for note in kept:
        signature = (
            note["title"].strip(),
            note["body"].strip(),
            note["comments"].strip(),
            note["category"],
            note["date"],
        )
        existing = best_by_signature.get(signature)
        if existing is None:
            best_by_signature[signature] = note
            order.append(signature)
        else:
            stats["duplicates_removed"] += 1
            if note_richness(note) > note_richness(existing):
                best_by_signature[signature] = note

    deduped = [best_by_signature[sig] for sig in order]

    for new_id, note in enumerate(deduped, start=1):
        note["id"] = new_id

    stats["after"] = len(deduped)
    return deduped, stats


# ---- Recurrence engine ----
#
# A recurring note is stored ONCE. Its occurrences are computed on demand for
# whatever date range is being displayed, never written to the notes file.
#   - note["date"]        is the series anchor (when it starts)
#   - note["recurrence"]  is the rule
#   - note["exceptions"]  are dates the user deleted individually
#   - note["overrides"]   are per-date content edits, keyed by date string

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

FREQ_LABELS = {
    "": "Does not repeat",
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}

RECURRENCE_DEFAULTS = {
    "freq": "",               # "" means this is a normal one-off note
    "interval": 1,            # every N days / weeks / months / years
    "weekdays": [],           # weekly only: 0=Mon .. 6=Sun
    "month_days": [],         # monthly only: 1..31
    "month_day_policy": "clamp",   # "clamp" -> Feb 28/29, "skip" -> no occurrence
    "end": "",                # "" = never ends
    "count": 0,               # 0 = unlimited; otherwise stop after N occurrences
}

# Fields a per-occurrence override is allowed to replace.
OVERRIDABLE_FIELDS = ["title", "body", "comments", "category", "color"]

# Safety valve: no rule may ever generate more than this in one expansion.
MAX_OCCURRENCES = 5000


def parse_date(value):
    """'2026-07-24' -> date object, or None if it isn't a valid date."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def format_date(d):
    return d.strftime("%Y-%m-%d")


class _CalcError(Exception):
    pass


_CALC_OPEN_BRACKETS = "({["
_CALC_CLOSE_BRACKETS = ")}]"
_CALC_SINGLE_CHAR_TOKENS = "+−×÷√^%" + _CALC_OPEN_BRACKETS + _CALC_CLOSE_BRACKETS


def _tokenize_calc_expression(expr):
    tokens = []
    i, n = 0, len(expr)
    while i < n:
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch in _CALC_SINGLE_CHAR_TOKENS:
            tokens.append(ch)
            i += 1
            continue
        # isdecimal(), not isdigit(): str.isdigit() is True for superscript/
        # other non-ASCII digit-like characters too (they have a defined
        # digit value even though they aren't plain 0-9) — isdecimal() is
        # the one that actually means "a real decimal digit," so pasted
        # text with a lookalike character correctly falls through to the
        # "unexpected character" error instead of silently merging into a
        # nearby number literal.
        if ch.isdecimal() or ch == ".":
            j = i
            seen_dot = False
            while j < n and (expr[j].isdecimal() or (expr[j] == "." and not seen_dot)):
                if expr[j] == ".":
                    seen_dot = True
                j += 1
            tokens.append(float(expr[i:j]))
            i = j
            continue
        raise _CalcError(f"unexpected character {ch!r}")
    return tokens


def evaluate_calculator_expression(expr):
    """Evaluate a calculator expression like '(5+3)×2' or '√{4+5}^2', with
    standard +/−/×/÷ precedence, three interchangeable bracket styles
    (`()`, `{}`, `[]` — purely visual grouping, not distinct types, so
    mismatched pairs like '(5+3]' still evaluate), a prefix square-root
    '√', a power operator '^' (right-associative, e.g. '2^3^2' is
    '2^(3^2)', not '(2^3)^2' — the usual math convention), and a postfix
    percent '%'. Returns the numeric result, or None if the expression is
    empty, malformed (unbalanced brackets, trailing operator, stray
    characters, a square root of a negative number, a power with no real
    result like a fractional power of a negative base...), or divides by
    zero — the caller shows "Error" for None rather than ever letting a
    bad expression crash the app. Input can come from the calculator's
    own buttons OR from directly typing/pasting into the display field —
    both are just plain text by the time they reach here, so both go
    through the exact same validation with nothing assumed about where
    the string came from.

    Deliberately hand-rolled instead of eval(): a parser this small costs
    little and removes the risk entirely, rather than relying on the
    input always staying constrained to safe characters."""
    if not isinstance(expr, str) or not expr.strip():
        return None
    try:
        tokens = _tokenize_calc_expression(expr)
    except _CalcError:
        return None
    if not tokens:
        return None

    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def advance():
        tok = tokens[pos[0]]
        pos[0] += 1
        return tok

    def parse_expression():
        value = parse_term()
        while peek() in ("+", "−"):
            op = advance()
            rhs = parse_term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def parse_term():
        value = parse_percent()
        while peek() in ("×", "÷"):
            op = advance()
            rhs = parse_percent()
            if op == "×":
                value = value * rhs
            else:
                if rhs == 0:
                    raise _CalcError("division by zero")
                value = value / rhs
        return value

    def parse_percent():
        # Postfix — binds to the whole power expression immediately
        # preceding it, e.g. "5^2%" is "(5^2)%" = 0.25, not "5^(2%)".
        value = parse_power()
        while peek() == "%":
            advance()
            value = value / 100
        return value

    def parse_power():
        # Unary +/− live HERE, not in parse_unary below, so a leading sign
        # applies to the whole power expression that follows — "-2^2" is
        # "-(2^2)" = -4 (matching Python's own ** operator and standard
        # convention), not "(-2)^2" = 4. Right-associative: "2^3^2" is
        # "2^(3^2)" = 512, not "(2^3)^2" = 64.
        if peek() == "−":
            advance()
            return -parse_power()
        if peek() == "+":
            advance()
            return parse_power()
        base = parse_unary()
        if peek() == "^":
            advance()
            exponent = parse_power()
            try:
                result = base ** exponent
            except (OverflowError, ZeroDivisionError, ValueError):
                raise _CalcError("invalid power")
            if isinstance(result, complex):
                raise _CalcError("power has no real result")
            return result
        return base

    def parse_unary():
        # Only √, brackets, and plain numbers — unary +/− are handled one
        # level up, in parse_power, so a sign correctly applies to an
        # entire power expression rather than just the base.
        tok = peek()
        if tok == "√":
            advance()
            operand = parse_power()
            if operand < 0:
                raise _CalcError("square root of a negative number")
            return math.sqrt(operand)
        if isinstance(tok, str) and tok in _CALC_OPEN_BRACKETS:
            advance()
            value = parse_expression()
            nxt = peek()
            if not (isinstance(nxt, str) and nxt in _CALC_CLOSE_BRACKETS):
                raise _CalcError("unbalanced brackets")
            advance()
            return value
        if isinstance(tok, float):
            advance()
            return tok
        raise _CalcError("unexpected token")

    try:
        result = parse_expression()
        if pos[0] != len(tokens):
            return None  # leftover tokens, e.g. a stray closing bracket
        return result
    except _CalcError:
        return None


def format_calculator_result(value):
    """1.0 -> '1' (whole numbers display clean); rounds to 10 decimal
    places first to hide float noise like 0.1+0.2 != 0.3 exactly."""
    rounded = round(value, 10)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.10f}".rstrip("0").rstrip(".")


def normalize_recurrence(rec):
    """Coerce a recurrence rule into a known-good shape. Anything unexpected
    degrades to 'does not repeat' rather than crashing the calendar."""
    out = dict(RECURRENCE_DEFAULTS)
    out["weekdays"] = []
    out["month_days"] = []
    if not isinstance(rec, dict):
        return out

    freq = rec.get("freq", "")
    out["freq"] = freq if freq in ("daily", "weekly", "monthly", "yearly") else ""

    try:
        out["interval"] = max(1, int(rec.get("interval", 1)))
    except (TypeError, ValueError):
        out["interval"] = 1

    weekdays = rec.get("weekdays", [])
    if isinstance(weekdays, list):
        out["weekdays"] = sorted({d for d in weekdays if isinstance(d, int) and 0 <= d <= 6})

    month_days = rec.get("month_days", [])
    if isinstance(month_days, list):
        out["month_days"] = sorted({d for d in month_days if isinstance(d, int) and 1 <= d <= 31})

    policy = rec.get("month_day_policy", "clamp")
    out["month_day_policy"] = policy if policy in ("clamp", "skip") else "clamp"

    end = rec.get("end", "")
    out["end"] = end.strip() if isinstance(end, str) and parse_date(end) else ""

    try:
        out["count"] = max(0, int(rec.get("count", 0)))
    except (TypeError, ValueError):
        out["count"] = 0

    return out


def is_recurring(note):
    return bool((note.get("recurrence") or {}).get("freq"))


def _shift_month(year, month, months_to_add):
    total = (year * 12 + (month - 1)) + months_to_add
    return total // 12, (total % 12) + 1


def _day_in_month(year, month, wanted_day, policy):
    """Resolve 'the 31st' inside a month that may not have one."""
    last_day = cal_module.monthrange(year, month)[1]
    if wanted_day <= last_day:
        return date_cls(year, month, wanted_day)
    if policy == "clamp":
        return date_cls(year, month, last_day)
    return None  # "skip"


def expand_occurrences(note, range_start, range_end):
    """Every date this note lands on between range_start and range_end
    (inclusive), as 'YYYY-MM-DD' strings. Exceptions are already removed."""
    anchor = parse_date(note.get("date", ""))
    if anchor is None:
        return []

    rec = normalize_recurrence(note.get("recurrence"))
    exceptions = set(note.get("exceptions") or [])

    if not rec["freq"]:
        one_off = format_date(anchor)
        if range_start <= anchor <= range_end and one_off not in exceptions:
            return [one_off]
        return []

    interval = rec["interval"]
    end_date = parse_date(rec["end"])
    max_count = rec["count"]
    policy = rec["month_day_policy"]

    # Hard stop for the whole expansion: never look past the requested range,
    # and never past the rule's own end date.
    horizon = range_end if end_date is None else min(range_end, end_date)
    if horizon < anchor:
        return []

    results = []
    produced = 0          # counts occurrences from the anchor, for "count"
    limited = max_count > 0

    def take(candidate):
        """Record one occurrence. Returns False when the rule is exhausted."""
        nonlocal produced
        if candidate < anchor:
            return True
        if end_date is not None and candidate > end_date:
            return False
        produced += 1
        if range_start <= candidate <= range_end:
            results.append(candidate)
        if limited and produced >= max_count:
            return False
        return True

    if rec["freq"] == "daily":
        step = timedelta(days=interval)
        current = anchor
        # With no count limit we can jump straight to the visible window
        # instead of walking every day since the anchor.
        if not limited and range_start > anchor:
            skipped = (range_start - anchor).days // interval
            current = anchor + step * skipped
        guard = 0
        while current <= horizon and guard < MAX_OCCURRENCES:
            guard += 1
            if not take(current):
                break
            current += step

    elif rec["freq"] == "weekly":
        weekdays = rec["weekdays"] or [anchor.weekday()]
        anchor_week = anchor - timedelta(days=anchor.weekday())
        week_step = timedelta(weeks=interval)
        week_start = anchor_week
        if not limited and range_start > anchor:
            weeks_ahead = (range_start - anchor_week).days // (7 * interval)
            if weeks_ahead > 0:
                week_start = anchor_week + week_step * weeks_ahead
        guard = 0
        stop = False
        while week_start <= horizon and guard < MAX_OCCURRENCES and not stop:
            guard += 1
            for weekday in weekdays:
                candidate = week_start + timedelta(days=weekday)
                if candidate > horizon:
                    continue
                if not take(candidate):
                    stop = True
                    break
            week_start += week_step

    elif rec["freq"] == "monthly":
        month_days = rec["month_days"] or [anchor.day]
        step_index = 0
        if not limited and range_start > anchor:
            months_ahead = ((range_start.year - anchor.year) * 12
                            + (range_start.month - anchor.month))
            step_index = max(0, months_ahead // interval)
        guard = 0
        stop = False
        while guard < MAX_OCCURRENCES and not stop:
            guard += 1
            year, month = _shift_month(anchor.year, anchor.month, step_index * interval)
            if date_cls(year, month, 1) > horizon:
                break
            for wanted in month_days:
                candidate = _day_in_month(year, month, wanted, policy)
                if candidate is None or candidate > horizon:
                    continue
                if not take(candidate):
                    stop = True
                    break
            step_index += 1

    elif rec["freq"] == "yearly":
        year_index = 0
        if not limited and range_start.year > anchor.year:
            year_index = max(0, (range_start.year - anchor.year) // interval)
        guard = 0
        while guard < MAX_OCCURRENCES:
            guard += 1
            year = anchor.year + year_index * interval
            if year > horizon.year:
                break
            candidate = _day_in_month(year, anchor.month, anchor.day, policy)
            if candidate is not None:
                if candidate > horizon:
                    break
                if not take(candidate):
                    break
            year_index += 1

    return [format_date(d) for d in sorted(results) if format_date(d) not in exceptions]


def effective_note(note, occurrence_date):
    """The note as it should appear on one specific day: the base note, with
    any per-occurrence override applied on top."""
    override = (note.get("overrides") or {}).get(occurrence_date)
    if not isinstance(override, dict):
        return note
    merged = dict(note)
    for field in OVERRIDABLE_FIELDS:
        if field in override:
            merged[field] = override[field]
    return merged


def describe_recurrence(note):
    """Short human-readable summary, e.g. 'Every 2 weeks on Mon, Thu'."""
    rec = normalize_recurrence(note.get("recurrence"))
    freq = rec["freq"]
    if not freq:
        return ""

    interval = rec["interval"]
    unit = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}[freq]
    base = f"Every {unit}" if interval == 1 else f"Every {interval} {unit}s"

    if freq == "weekly" and rec["weekdays"]:
        base += " on " + ", ".join(WEEKDAY_NAMES[d] for d in rec["weekdays"])
    elif freq == "monthly" and rec["month_days"]:
        base += " on day " + ", ".join(str(d) for d in rec["month_days"])

    if rec["count"]:
        base += f", {rec['count']} times"
    elif rec["end"]:
        base += f", until {rec['end']}"

    return base


# ---- Share codes (move notes between devices as copy-paste text) ----
#
# A share code is: a small JSON payload -> zlib-compressed -> Base64 text,
# tagged with a version prefix. It carries note CONTENT (title, body, comments,
# category, date, color, recurrence) but NOT attachments — binary files
# would bloat the code to millions of characters, past what any chat box or
# email will paste. For attachments, the ZIP export is the right tool.

SHARE_CODE_PREFIX = "NOTE1:"

# Safety limits for importing share codes. These stop a malformed or malicious
# code from exhausting memory or flooding the notebook.
MAX_SHARE_CODE_CHARS = 5_000_000      # reject absurdly long pasted text outright
MAX_DECOMPRESSED_BYTES = 20_000_000   # cap zlib output — guards against zip bombs
MAX_SHARED_NOTES = 200                # most notes one code may carry

# Only these fields travel in a share code. Notably absent: id (assigned fresh
# on import), attachments, updated, overrides/exceptions.
SHAREABLE_FIELDS = [
    "title", "body", "formatting", "comments", "category", "date", "color", "recurrence",
]


def _shareable_view(note):
    """The slice of a note that a share code carries."""
    return {k: note.get(k) for k in SHAREABLE_FIELDS if k in note}


def encode_share_code(notes):
    """Turn one or more notes into a copy-paste share code. Accepts a single
    note dict or a list of them."""
    if isinstance(notes, dict):
        notes = [notes]
    payload = {"v": 1, "notes": [_shareable_view(n) for n in notes]}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    b64 = base64.urlsafe_b64encode(compressed).decode("ascii")
    return SHARE_CODE_PREFIX + b64


def _bounded_decompress(compressed, limit):
    """Decompress, but never produce more than `limit` bytes. A tiny 'zip bomb'
    can expand to gigabytes and crash the app; this stops it cold."""
    dobj = zlib.decompressobj()
    out = dobj.decompress(compressed, limit)
    if dobj.unconsumed_tail:
        # There's more than the limit allows — refuse rather than keep going.
        raise ValueError("decompressed data exceeds the safe size limit")
    out += dobj.flush()
    if len(out) > limit:
        raise ValueError("decompressed data exceeds the safe size limit")
    return out


def decode_share_code(code):
    """Parse a share code back into a list of note dicts. Raises ValueError with
    a human-readable message if the code is malformed, oversized, or from a
    newer version."""
    if not isinstance(code, str):
        raise ValueError("That doesn't look like a share code.")
    # Tolerate extra whitespace/newlines from a chat app.
    code = "".join(code.split())
    if not code:
        raise ValueError("No code was pasted.")
    if len(code) > MAX_SHARE_CODE_CHARS:
        raise ValueError(
            "That code is far too large to import safely. Use Import (ZIP) for "
            "very large transfers."
        )
    if not code.startswith(SHARE_CODE_PREFIX):
        raise ValueError(
            "This isn't a Notes Organizer share code. A valid code starts "
            f"with \u201c{SHARE_CODE_PREFIX}\u201d."
        )
    body = code[len(SHARE_CODE_PREFIX):]
    try:
        compressed = base64.urlsafe_b64decode(body)
    except (base64.binascii.Error, ValueError):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again — chat apps sometimes cut long codes short."
        )
    try:
        raw = _bounded_decompress(compressed, MAX_DECOMPRESSED_BYTES)
    except (zlib.error, ValueError):
        raise ValueError(
            "This share code is damaged, or too large to import safely. Ask the "
            "sender to send it again, or use Import (ZIP) for large transfers."
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again."
        )
    if not isinstance(payload, dict) or "notes" not in payload:
        raise ValueError("This share code doesn't contain any notes.")
    if payload.get("v", 1) > 1:
        raise ValueError(
            "This code was made by a newer version of Notes Organizer. "
            "Update the app to import it."
        )
    notes = payload.get("notes")
    if not isinstance(notes, list) or not notes:
        raise ValueError("This share code doesn't contain any notes.")
    if len(notes) > MAX_SHARED_NOTES:
        raise ValueError(
            f"This code contains {len(notes)} notes, which is over the "
            f"{MAX_SHARED_NOTES}-note limit for a single code. Ask the sender to "
            "split it into smaller codes, or to use Export (ZIP) instead."
        )
    return notes


def _safe_extract_zip(zf, dest_dir):
    """Extract a zip safely: block path-traversal ('../' escapes) and refuse
    archives that would expand past a sane size. extractall() does neither, so
    a malicious backup zip could otherwise write files anywhere or fill the disk."""
    MAX_TOTAL = 500_000_000   # 500 MB uncompressed ceiling for a whole backup
    MAX_FILES = 10_000
    dest_root = os.path.abspath(dest_dir)

    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise ValueError("This backup contains too many files to import safely.")

    total = sum(max(i.file_size, 0) for i in infos)
    if total > MAX_TOTAL:
        raise ValueError("This backup is too large to import safely.")

    for info in infos:
        # Reject absolute paths and anything that escapes the destination.
        target = os.path.abspath(os.path.join(dest_root, info.filename))
        if not (target == dest_root or target.startswith(dest_root + os.sep)):
            raise ValueError("This backup contains unsafe file paths and was blocked.")
    zf.extractall(dest_dir)


def load_trash():
    """Read the trashed notes list. Malformed/missing -> empty list, never
    crashes."""
    if os.path.exists(TRASH_FILE):
        try:
            with open(TRASH_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, IOError, OSError):
            pass
    return []


def save_trash(trash):
    """Write the trashed notes list, best-effort."""
    try:
        with open(TRASH_FILE, "w", encoding="utf-8") as f:
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
            path = os.path.join(ATTACHMENTS_DIR, stored_as)
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


def _strip_copy_suffix(title):
    """Remove any number of trailing ' (copy)' markers from a title, so a note
    and its duplicates ('X', 'X (copy)', 'X (copy) (copy)') compare as equal.
    The real title is left untouched — this is only for duplicate matching."""
    t = (title or "").strip()
    while t.lower().endswith("(copy)"):
        t = t[: -len("(copy)")].rstrip()
    return t


def _normalize_ws(text):
    """Collapse whitespace for duplicate comparison: trim ends and squeeze any
    run of spaces/newlines/tabs into a single space. So 'hi  world' and
    ' hi world ' match, but 'hi world' and 'hi werld' still differ."""
    return " ".join((text or "").split())


def _dup_key(note):
    """The (title, body, comments, category) signature used to decide whether
    two notes are 'the same' — case/whitespace-insensitive, ignoring a
    trailing ' (copy)' in the title. Shared by duplicate-group detection and
    by the import flow's duplicate check, so both agree on what counts as a
    match."""
    return (
        _normalize_ws(_strip_copy_suffix(note.get("title") or "")).lower(),
        _normalize_ws(note.get("body") or "").lower(),
        _normalize_ws(note.get("comments") or "").lower(),
        note.get("category") or "",
    )


def find_duplicate_groups(notes):
    """Group notes that are the same in title, body, comments and category.
    Matching ignores case and normalizes whitespace, and a trailing ' (copy)'
    in the title is ignored. Date, attachments, color, recurrence and IDs
    are all IGNORED — only the visible text content (case-insensitively) and
    category define a duplicate. When the user cleans up, the kept copy inherits
    combined attachments so nothing is lost."""
    groups = {}
    for n in notes:
        groups.setdefault(_dup_key(n), []).append(n)
    return [g for g in groups.values() if len(g) > 1]


def backup_notes_file():
    """Snapshot the notes file before touching it. Cleanup should never be
    the reason something is lost."""
    if not os.path.exists(DATA_FILE):
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(APP_DIR, f"notes_data_backup_{stamp}.json")
    try:
        shutil.copy2(DATA_FILE, backup_path)
        return backup_path
    except (IOError, OSError):
        return None

# ---- Themes ----
THEMES = {
    # ---- DARK variants ----
    "dark": {  # Midnight Purple (original)
        "bg": "#1e1e2f",
        "sidebar": "#26263f",
        "accent": "#7c5cff",
        "accent_hover": "#9377ff",
        "card": "#2e2e48",
        "text": "#f2f2f7",
        "subtext": "#a0a0c0",
        "danger": "#ff5c7c",
        "success": "#4cd9a3",
        "calendar_has_notes": "#3d3168",
    },
    "dark_ocean": {  # deep blue
        "bg": "#0f1b2d",
        "sidebar": "#16273f",
        "accent": "#2f9be0",
        "accent_hover": "#54b0ec",
        "card": "#1c3350",
        "text": "#eaf2fb",
        "subtext": "#8fa8c4",
        "danger": "#ff6b6b",
        "success": "#3ecf8e",
        "calendar_has_notes": "#1f4266",
    },
    "dark_forest": {  # deep green
        "bg": "#14231b",
        "sidebar": "#1b3227",
        "accent": "#43c07a",
        "accent_hover": "#5ed494",
        "card": "#213e30",
        "text": "#eafaf0",
        "subtext": "#8fbaa1",
        "danger": "#ff7a7a",
        "success": "#4cd9a3",
        "calendar_has_notes": "#254e39",
    },
    "dark_slate": {  # neutral charcoal, warm accent
        "bg": "#1c1c22",
        "sidebar": "#26262e",
        "accent": "#e0863f",
        "accent_hover": "#ec9d5a",
        "card": "#2d2d38",
        "text": "#f3f2f0",
        "subtext": "#a8a8b0",
        "danger": "#ff6b6b",
        "success": "#4cd9a3",
        "calendar_has_notes": "#3a2f22",
    },
    # ---- LIGHT variants ----
    "light": {  # Soft Lavender (original)
        "bg": "#f5f5fa",
        "sidebar": "#e9e9f5",
        "accent": "#7c5cff",
        "accent_hover": "#6a49e6",
        "card": "#ffffff",
        "text": "#22223a",
        "subtext": "#6b6b85",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#e3dbff",
    },
    "light_sky": {  # airy blue
        "bg": "#f0f6fc",
        "sidebar": "#dcebf8",
        "accent": "#1f88d6",
        "accent_hover": "#1873ba",
        "card": "#ffffff",
        "text": "#173049",
        "subtext": "#5a748c",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#d3e7f8",
    },
    "light_mint": {  # fresh green
        "bg": "#f1f9f4",
        "sidebar": "#dcefe3",
        "accent": "#2aa971",
        "accent_hover": "#238e5f",
        "card": "#ffffff",
        "text": "#183328",
        "subtext": "#5b7d6c",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#d3edde",
    },
    "light_warm": {  # warm cream, orange accent
        "bg": "#faf6f0",
        "sidebar": "#f1e7da",
        "accent": "#d97a2b",
        "accent_hover": "#bd6822",
        "card": "#ffffff",
        "text": "#3a2c1c",
        "subtext": "#8a7660",
        "danger": "#e0405f",
        "success": "#2fae82",
        "calendar_has_notes": "#f3e2cd",
    },
}

# Which variants are dark vs light — used to keep 'light is light, dark is dark'
# behavior and to group them in the theme picker.
DARK_THEMES = ["dark", "dark_ocean", "dark_forest", "dark_slate"]
LIGHT_THEMES = ["light", "light_sky", "light_mint", "light_warm"]

# Friendly display names for the picker.
THEME_LABELS = {
    "dark": "Midnight Purple",
    "dark_ocean": "Ocean Blue",
    "dark_forest": "Forest Green",
    "dark_slate": "Warm Charcoal",
    "light": "Soft Lavender",
    "light_sky": "Sky Blue",
    "light_mint": "Fresh Mint",
    "light_warm": "Warm Cream",
}

DEFAULT_CATEGORY_COLORS = {
    "General": "#7c5cff",
    "Work": "#4cc9f0",
    "Personal": "#f9c74f",
    "Ideas": "#f77f00",
    "Urgent": "#ff5c7c",
}

# A curated palette for the inline color picker (used for categories and
# calendar day markers). Enough variety without overwhelming; one click picks
# a color, no OS dialog.
PALETTE_COLORS = [
    "#7c5cff", "#4cc9f0", "#f9c74f", "#f77f00", "#ff5c7c",
    "#43aa8b", "#90be6d", "#f94144", "#577590", "#9b5de5",
    "#00bbf9", "#00f5d4", "#fee440", "#ff924c", "#ff6392",
    "#8ac926", "#1982c4", "#6a4c93", "#e07a5f", "#b5838d",
]

# "General" is the safety net: it can't be renamed or deleted, so there is
# always a valid home for notes whose category is removed.
PROTECTED_CATEGORY = "General"

# The live category map. Starts from the defaults, then gets overlaid with the
# user's saved categories on startup. Referenced everywhere the old
# CATEGORY_COLORS constant was, so the whole app reads from one place.
CATEGORY_COLORS = dict(DEFAULT_CATEGORY_COLORS)


def load_categories():
    """Read the user's categories from settings, falling back to defaults.
    Guarantees General exists and stays first."""
    saved = load_settings().get("categories")
    result = {}
    if isinstance(saved, dict) and saved:
        # Keep only well-formed name -> #hex entries.
        for name, color in saved.items():
            if (isinstance(name, str) and name.strip()
                    and isinstance(color, str) and color.startswith("#")):
                result[name.strip()] = color
    if not result:
        result = dict(DEFAULT_CATEGORY_COLORS)
    # General is mandatory and always first.
    if PROTECTED_CATEGORY not in result:
        result = {PROTECTED_CATEGORY: DEFAULT_CATEGORY_COLORS[PROTECTED_CATEGORY], **result}
    ordered = {PROTECTED_CATEGORY: result[PROTECTED_CATEGORY]}
    for name, color in result.items():
        if name != PROTECTED_CATEGORY:
            ordered[name] = color
    return ordered


def persist_categories():
    """Write the current category map back to settings."""
    settings = load_settings()
    settings["categories"] = dict(CATEGORY_COLORS)
    save_settings(settings)


# Quick-pick palette offered when choosing a custom note color, and (below)
# for text color. Swatches only, deliberately — no hex-code entry, since
# most users don't think in hex; the palette is sized generously instead so
# picking a swatch stays a real choice, not just the ten "obvious" colors.
PRESET_NOTE_COLORS = [
    "#7c5cff", "#4cc9f0", "#f9c74f", "#f77f00", "#ff5c7c",
    "#4cd9a3", "#ff8fa3", "#a3a3ff", "#ffd166", "#06d6a0",
    "#e63946", "#3a86ff", "#c77dff", "#8ac926", "#6c757d",
]

# Note body TEXT color reuses PRESET_NOTE_COLORS above, for visual
# consistency with the rest of the app. HIGHLIGHT (background) color gets
# its own, separate palette: deliberately soft/pastel, the way a real
# highlighter marker is, so text drawn on top of it stays readable —
# PRESET_NOTE_COLORS' vivid, saturated tones work fine as a small accent
# dot but would be too strong as a block of background behind text.
HIGHLIGHT_COLOR_PALETTE = [
    "#fff3b0",  # soft yellow
    "#c8f4d9",  # soft green
    "#ffd6e8",  # soft pink
    "#cde7ff",  # soft blue
    "#ffe0b3",  # soft peach
    "#e0d4ff",  # soft purple
    "#ffd1d1",  # soft coral
    "#c8f4ec",  # soft teal
    "#e8e8e8",  # soft gray
    "#f0f4c3",  # soft lime
]

SIDEBAR_WIDTH = 280
EDITOR_MIN_WIDTH = 620


class NoteOrganizer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Notes Organizer")
        self.geometry("900x600")
        self.minsize(500, 400)

        self.theme_name = self.load_theme_setting()
        self.colors = THEMES[self.theme_name]
        # Track last-used dark/light for the quick toggle button.
        self._last_dark_theme = self.theme_name if self.theme_name in DARK_THEMES else "dark"
        self._last_light_theme = self.theme_name if self.theme_name in LIGHT_THEMES else "light"

        # Load the user's categories into the live map BEFORE notes load, so
        # normalize_note validates each note's category against the real set.
        CATEGORY_COLORS.clear()
        CATEGORY_COLORS.update(load_categories())

        self._cleanup_report = None  # filled in by load_notes if cleanup ran
        self._version_backup_path = None  # filled in by load_notes on a version upgrade
        self.notes = self.load_notes()
        self.selected_note_id = None

        # User-defined note templates.
        self.templates = load_templates()

        # Load trash and auto-purge anything past the retention window.
        self.trash = load_trash()
        self.trash, purged = purge_expired_trash(self.trash)
        if purged:
            save_trash(self.trash)

        # User-chosen colors for individual calendar days (date -> #hex).
        saved_day_colors = load_settings().get("day_colors")
        self.day_colors = dict(saved_day_colors) if isinstance(saved_day_colors, dict) else {}

        # User-chosen emoji markers for individual calendar days (date -> list
        # of emoji characters), independent of any note. E.g. flag a day with
        # a couple of markers even before you've written a note for it.
        saved_day_emoji = load_settings().get("day_emoji")
        self.day_emoji = {}
        if isinstance(saved_day_emoji, dict):
            for d, v in saved_day_emoji.items():
                if isinstance(v, list):
                    self.day_emoji[d] = [e for e in v if isinstance(e, str) and e]
                elif isinstance(v, str) and v:
                    # Older format stored a single emoji per day — migrate it
                    # into the new list-based format transparently.
                    self.day_emoji[d] = [v]
        self.current_occurrence_date = None  # set when opened from a calendar day
        self.themed_widgets = []

        # Open note tabs: a list of editor-state snapshots, one per open note.
        # self.active_tab_index points at the one currently shown in the editor.
        self.open_tabs = []
        self.active_tab_index = None
        self._tab_counter = 0  # for stable keys on unsaved new notes

        today = datetime.now()
        self.cal_year = today.year
        self.cal_month = today.month

        self.configure(bg=self.colors["bg"])
        self.build_ui()
        self.refresh_note_list()
        self.render_calendar()
        last_open_id = load_settings().get("last_open_note_id")
        if last_open_id is not None:
            last_note = self.find_note(last_open_id)
            if last_note is not None:
                self.open_note_in_tab(last_note)
        self.after(250, self.announce_startup_changes)
        self.after(400, self.maybe_show_reminder)
        self._last_active_dirty = None
        self.after(600, self._poll_active_dirty)

    def _schedule_autosave(self, event=None, skip_word_count=False):
        """Debounced auto-save: (re)start a short timer on every edit. When the
        user pauses even briefly, the note saves itself. Save button still works
        for those who want to save immediately.

        `skip_word_count`: the word/character count recompute reads the whole
        body text on every call — cheap for a single keystroke, but calling it
        on every click while rapid-inserting many emojis in a row adds up to
        noticeable lag. The count still catches up once the debounce timer
        below fires, just not on every single click."""
        if not skip_word_count:
            try:
                self.update_word_count()
            except Exception:
                pass
        if getattr(self, "_autosave_job", None) is not None:
            try:
                self.after_cancel(self._autosave_job)
            except (tk.TclError, ValueError):
                pass
        self._autosave_job = self.after(500, self._autosave_now)

    def _autosave_now(self):
        """Run an auto-save if the current editor content is worth saving and
        actually differs from what's on disk."""
        self._autosave_job = None
        if not self._still_alive():
            return
        # selected_note_id can end up stale — pointing at a note that no
        # longer exists (e.g. it was removed by another action while this
        # timer was pending). save_current_note() would otherwise hit its
        # "Note missing" error dialog here — appropriate for an explicit,
        # user-initiated Save, but not for a silent background autosave the
        # user never directly asked for. Same guard _flush_autosave() already
        # uses for the same reason.
        if self.selected_note_id is not None and self.find_note(self.selected_note_id) is None:
            return
        # Catch the word count up now, in case rapid edits (e.g. inserting
        # several emojis in a row) skipped recomputing it on every click.
        try:
            self.update_word_count()
        except Exception:
            pass
        try:
            st = self.capture_editor_state()
        except Exception:
            return
        # Never auto-save a completely empty note — that would spawn junk notes
        # every time the user clicks "New Note". Attachments and checklist
        # items count as real content too, not just title/body — a note
        # with only an attached file (no typed text at all) is genuinely
        # meaningful and shouldn't be silently dropped.
        if not (st.get("title", "").strip() or st.get("body", "").strip()
                or st.get("attachments") or st.get("checklist")):
            return
        # Only save if something actually changed vs. the saved version.
        try:
            if self.editor_state_matches_saved(st):
                return
        except Exception:
            pass
        # Reuse the normal save path, but mark it as automatic so the status
        # message is gentle rather than a loud "Saved!".
        self.save_current_note(auto=True)

    def _still_alive(self):
        """True if the app window is still around and usable. Checked before
        any code that would otherwise touch a Tkinter widget from a timer
        callback that might fire after the app has closed. winfo_exists()
        itself can raise once the whole Tk application (not just one widget)
        has been torn down, not only when a single widget is gone — so the
        existence check itself needs a guard, not just what comes after it."""
        try:
            return bool(self.winfo_exists())
        except tk.TclError:
            return False

    def _poll_active_dirty(self):
        """Cheaply keep the active tab's dirty dot in sync while the user types,
        without binding every widget. Only redraws when the state flips."""
        try:
            if self.open_tabs and self.active_tab_index is not None and len(self.open_tabs) > 1:
                st = self.capture_editor_state()
                dirty = not self.editor_state_matches_saved(st)
                if dirty != self._last_active_dirty:
                    self._last_active_dirty = dirty
                    self.open_tabs[self.active_tab_index]["state"] = st
                    self.refresh_tab_strip()
        except (tk.TclError, Exception):
            pass
        # Only reschedule if the window is still around — this timer refires
        # forever otherwise, and calling self.after() against an already
        # destroyed root raises its own error (observed in practice, e.g.
        # when a script closes the app while this timer is still pending).
        if self._still_alive():
            self.after(600, self._poll_active_dirty)

    # ---------- Settings (theme) persistence ----------
    def load_theme_setting(self):
        theme = load_settings().get("theme")
        return theme if theme in THEMES else "dark"

    def save_theme_setting(self):
        # Read/modify/write so saving the theme can't wipe other settings
        # (like the cleanup flag) that live in the same file.
        settings = load_settings()
        settings["theme"] = self.theme_name
        save_settings(settings)

    def load_username(self):
        name = load_settings().get("username", "")
        return name if isinstance(name, str) else ""

    def save_username(self, name):
        settings = load_settings()
        settings["username"] = name.strip()
        save_settings(settings)

    def _refresh_greeting(self):
        """Show 'Hi <name>,' if a name is set in Settings, otherwise a gentle
        nudge to set one. Recomputed whenever the name changes."""
        if not hasattr(self, "greeting_lbl"):
            return
        name = self.load_username()
        if name:
            self.greeting_lbl.config(text=f"Hi {name},")
        else:
            self.greeting_lbl.config(text="")

    def _on_toggle_group_by_category(self):
        settings = load_settings()
        settings["group_by_category"] = bool(self.group_by_category.get())
        save_settings(settings)
        self.refresh_note_list()

    def _toggle_group_collapsed(self, category):
        if category in self.collapsed_groups:
            self.collapsed_groups.discard(category)
        else:
            self.collapsed_groups.add(category)
        settings = load_settings()
        settings["collapsed_groups"] = sorted(self.collapsed_groups)
        save_settings(settings)
        self.refresh_note_list()

    def _remember_last_open_note(self, note_id):
        """Persist which note is currently open, so the app reopens directly
        into it next launch instead of always starting on a blank editor."""
        settings = load_settings()
        settings["last_open_note_id"] = note_id
        save_settings(settings)

    # ---------- One-time startup notice ----------
    def announce_startup_changes(self):
        """Shown once: where the notes now live, and what cleanup removed."""
        if not self._still_alive():
            return
        lines = []

        if VERSION_CHANGE:
            direction, old, new = VERSION_CHANGE
            if direction == "up":
                msg = (
                    f"Updated to version {new} (from {old}).\n\n"
                    "Your notes are unchanged — only the app was updated."
                )
                if self._version_backup_path:
                    msg += (
                        "\n\nAs an extra safety net, a backup of your notes "
                        "from just before this update was saved to:\n"
                        f"{self._version_backup_path}"
                    )
                lines.append(msg)
            else:
                lines.append(
                    f"⚠ You're running an older version ({new}) over data last "
                    f"used with {old}. Everything should still work, but if "
                    "anything looks off, use the newer build."
                )

        if STORAGE_WARNING:
            lines.append("⚠ " + STORAGE_WARNING)

        if MIGRATION_INFO:
            lines.append(
                MIGRATION_INFO
                + "\n\nThe script and dist\\NoteOrganizer.exe both read this "
                  "same folder, so they can never drift apart."
            )

        if PURGED_DIRS:
            listed = "\n".join(f"  • {d}" for d in PURGED_DIRS)
            lines.append(
                "Removed leftover copies of your notes from:\n"
                f"{listed}\n\n"
                "Each one was checked first — nothing was deleted unless every "
                "note and attachment in it already existed in the app folder. "
                "There is now exactly one notebook on disk."
            )

        if self._cleanup_report:
            stats, backup_path = self._cleanup_report
            summary = (
                f"Cleanup pass (runs once):\n"
                f"  • Started with {stats['before']} note(s)\n"
                f"  • Removed {stats['empty_removed']} empty note(s)\n"
                f"  • Removed {stats['duplicates_removed']} duplicate(s)\n"
                f"  • {stats['after']} note(s) remain, IDs renumbered 1–{stats['after']}"
            )
            if backup_path:
                summary += f"\n\nA backup of the original was saved to:\n{backup_path}"
            lines.append(summary)

        if lines:
            self.show_info("Notes Organizer — setup complete", "\n\n———\n\n".join(lines))

    # ---------- Data handling ----------
    def load_notes(self):
        raw = []
        if os.path.exists(DATA_FILE):
            # A newer app version is about to run against data last saved by
            # an older one — snapshot it now, before this version's own code
            # (which could have new bugs or changed logic) gets any chance
            # to rewrite it. Every future update gets this safety net, not
            # just the very first run (see backup_notes_file's other call,
            # below, for that one-time case). Never auto-deleted — it's the
            # user's call when old backups are no longer needed.
            if VERSION_CHANGE and VERSION_CHANGE[0] == "up":
                self._version_backup_path = backup_notes_file()
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
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
            self._cleanup_report = (stats, backup_path)

            try:
                with open(DATA_FILE, "w", encoding="utf-8") as f:
                    json.dump(notes, f, indent=2, ensure_ascii=False)
            except (IOError, OSError):
                pass

            settings["cleanup_done"] = True
            save_settings(settings)

        return notes

    def save_notes(self):
        """Write notes to disk. Returns True on success. A failure here used to
        be invisible — the app looked like it saved but nothing hit the disk,
        which is exactly how notes 'vanished' on other PCs. Now it's surfaced."""
        try:
            tmp_path = DATA_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.notes, f, indent=2, ensure_ascii=False)
            # Atomic replace: a crash mid-write can't corrupt the real file,
            # it either fully updates or stays as it was.
            os.replace(tmp_path, DATA_FILE)
            return True
        except (IOError, OSError) as exc:
            self.show_error(
                "Couldn't save your notes",
                "Your notes could not be written to disk, so recent changes may "
                "be lost when you close the app.\n\n"
                f"Location:\n{DATA_FILE}\n\n"
                f"Reason: {exc}\n\n"
                "This usually means the app is in a read-only folder (like "
                "Program Files or a location that needs admin rights). Move the "
                "app to your Documents or Desktop, or use Export to save a copy "
                "somewhere you can write to."
            )
            return False

    # ---------- Export / Import (moving your notebook between devices) ----------
    def export_data(self):
        """Bundle notes_data.json, settings.json, and every attached file
        into one .zip, so moving to another device is copying one file
        instead of hunting down three separate pieces.

        The actual writing runs on a background thread — for a lot of
        attachments this used to visibly freeze the whole app for a few
        seconds. The main thread only ever touches Tkinter widgets from the
        polling callback below; the worker thread does file I/O and updates
        a plain shared dict, which is all it's allowed to touch."""
        default_name = f"NotesBackup_{datetime.now().strftime('%Y-%m-%d')}.zip"
        save_path = filedialog.asksaveasfilename(
            title="Export your notes to a backup file",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("Zip files", "*.zip")]
        )
        if not save_path:
            return

        # Build the file list up front (fast — just enumerating), so the
        # progress bar has a real total to work against, not a guess.
        entries = []  # list of (source_path, arcname)
        if os.path.exists(DATA_FILE):
            entries.append((DATA_FILE, "notes_data.json"))
        if os.path.exists(SETTINGS_FILE):
            entries.append((SETTINGS_FILE, "settings.json"))
        if os.path.isdir(ATTACHMENTS_DIR):
            for filename in os.listdir(ATTACHMENTS_DIR):
                full_path = os.path.join(ATTACHMENTS_DIR, filename)
                if os.path.isfile(full_path):
                    entries.append((full_path, os.path.join("attachments", filename)))

        self._export_state = {"current": 0, "total": len(entries), "done": False,
                              "error": None, "save_path": save_path}
        self.export_progress_bar.configure(maximum=max(len(entries), 1), value=0)
        self.export_progress_lbl.config(text=f"Exporting… 0 / {len(entries)} files")
        self.export_progress_frame.place(relx=0.5, rely=1.0, anchor="s", y=-14)
        self.export_progress_frame.lift()

        def worker():
            state = self._export_state
            try:
                with zipfile.ZipFile(save_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, (src, arcname) in enumerate(entries, start=1):
                        zf.write(src, arcname=arcname)
                        state["current"] = i
            except Exception as e:
                # Deliberately broad: this runs in a background thread, where
                # an uncaught exception of ANY kind kills the thread silently
                # (Python's default thread behavior) without ever reaching
                # state["done"] = True below — leaving the progress bar
                # polling forever against a dict that will never say it's
                # finished, with no error shown. A background worker must
                # never let anything escape uncaught; the specific IOError/
                # OSError message is still preserved when that's the cause,
                # just no longer the only kind of failure that's handled.
                state["error"] = str(e)
            state["done"] = True

        threading.Thread(target=worker, daemon=True).start()
        self._poll_export_progress()

    def _poll_export_progress(self):
        """Runs on the main thread only, on a timer — reads the plain dict the
        background export thread updates, and reflects it in the progress
        bar. This is the ONLY place export touches any Tkinter widget."""
        if not self._still_alive():
            # The app was closed while the background thread was still
            # running — nothing left to update; the thread finishes and
            # writes its file regardless, it just has no UI left to report to.
            return
        state = self._export_state
        if state is None:
            return
        self.export_progress_bar.configure(value=state["current"])
        self.export_progress_lbl.config(
            text=f"Exporting… {state['current']} / {state['total']} files")
        if state["done"]:
            self.export_progress_frame.place_forget()
            self._export_state = None
            if state["error"]:
                self.show_error("Export failed",
                               f"Couldn't create the backup file:\n{state['error']}")
            else:
                self.show_info(
                    "Export complete",
                    f"Your notes, settings, and attachments were saved to:\n"
                    f"{state['save_path']}\n\n"
                    "Copy or email this single file to another device, then use "
                    "'⬇ Import' there to bring everything in."
                )
            return
        self._export_poll_job = self.after(100, self._poll_export_progress)

    # ---------- Share codes ----------
    def _add_paste_menu(self, text_widget, extra_items=None):
        """Give a Text/Entry widget a right-click menu with Cut/Copy/Paste/Select
        All, so users can paste without knowing Ctrl+V.

        extra_items, when given, is a list of (label, command) or (label,
        command, accelerator_text) tuples appended after the emoji entry —
        used only for the note body, to expose the same
        Bold/Italic/Underline/Strikethrough toggles as the formatting
        toolbar (with their keyboard shortcuts shown alongside, display
        only — the actual key bindings live on body_text itself) without
        adding them to every other text field that shares this same
        menu-building function."""
        menu = tk.Menu(text_widget, tearoff=0)
        menu.configure(bg=self.colors["card"], fg=self.colors["text"],
                       activebackground=self.colors["accent"], activeforeground="white",
                       relief="flat", bd=0, font=("Segoe UI", 9))

        def do(action):
            try:
                text_widget.event_generate(action)
            except tk.TclError:
                pass

        menu.add_command(label="Cut", command=lambda: do("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: do("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: do("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label="Select All",
                         # "end" (not "end-1c") is a Text widget's implicit
                         # trailing newline -- including it in the
                         # selection is why the highlight used to visibly
                         # stretch to the full width of the last line,
                         # well past the actual last character, regardless
                         # of how short that line was.
                         command=lambda: (text_widget.tag_add("sel", "1.0", "end-1c")
                                          if isinstance(text_widget, tk.Text)
                                          else text_widget.select_range(0, "end")))
        menu.add_separator()
        menu.add_command(label="Insert emoji…",
                         command=lambda: self._show_emoji_picker(text_widget))

        if extra_items:
            menu.add_separator()
            for item in extra_items:
                label, command = item[0], item[1]
                accelerator = item[2] if len(item) > 2 else ""
                menu.add_command(label=label, command=command, accelerator=accelerator)

        def popup(event):
            try:
                text_widget.focus_set()
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        text_widget.bind("<Button-3>", popup)

    # ---------- Note body rich text formatting ----------
    # Storage: a note's "formatting" field is a flat list of {start, end,
    # style} character-offset spans (see normalize_formatting). The live
    # Tkinter Text widget is the only thing that ever manipulates ranges
    # directly, via its own tags — these two functions are the sole bridge
    # between "tags on a live widget" and "a plain-JSON-serializable list",
    # called once at load time and once at save time. Tkinter itself keeps
    # tag ranges correctly anchored to the surrounding text as the user
    # types/deletes in between, so nothing needs to track offsets while
    # editing is actually happening.
    _FONT_STYLES = ("bold", "italic", "bold_italic")  # mutually exclusive
    _PENDING_STYLE_ANCHOR = "pending_style_anchor"  # see _toggle_body_style

    def _setup_body_formatting_tags(self, text_widget):
        """Define the Tkinter tags the formatting toolbar/menu apply. Font
        objects are kept on self so they aren't garbage-collected (Tkinter
        needs a live Python reference to keep using them)."""
        base = tkfont.Font(font=text_widget["font"])
        family, size = base.actual("family"), base.actual("size")
        self._fmt_bold_font = tkfont.Font(family=family, size=size, weight="bold")
        self._fmt_italic_font = tkfont.Font(family=family, size=size, slant="italic")
        self._fmt_bold_italic_font = tkfont.Font(
            family=family, size=size, weight="bold", slant="italic")
        text_widget.tag_configure("bold", font=self._fmt_bold_font)
        text_widget.tag_configure("italic", font=self._fmt_italic_font)
        text_widget.tag_configure("bold_italic", font=self._fmt_bold_italic_font)
        text_widget.tag_configure("underline", underline=True)
        text_widget.tag_configure("strike", overstrike=True)
        # Tk gives later-configured tags higher display priority, and "sel"
        # is created before any of these -- left alone, a highlight/text
        # color tag always paints over the selection color, making selected
        # highlighted text look unselected even though it really is (see
        # _ensure_color_tag, which re-raises "sel" for the same reason
        # whenever a new color tag is created later).
        text_widget.tag_raise("sel")

    @staticmethod
    def _char_offset(w, index):
        # text.count("1.0", index, "chars") returns None instead of (0,)
        # when the distance is exactly zero (a documented Tkinter quirk) --
        # which happens whenever a tag starts at "1.0" itself, e.g.
        # formatting applied to the very first character(s) of the note.
        # Treat that missing result as a real zero, not a crash.
        result = w.count("1.0", index, "chars")
        return result[0] if result else 0

    _WORD_CHAR_RE = re.compile(r"\w", re.UNICODE)

    @classmethod
    def _char_class(cls, ch):
        # Three classes: contiguous runs of the same class form one
        # double-click "word" -- used by _select_word_at_click so that
        # punctuation like "." always breaks a word (unlike Tk's own
        # default word-boundary detection, which keeps a single "." glued
        # to its surrounding letters, e.g. treating "something.else" as one
        # word regardless of which side of the "." was clicked).
        if not ch:
            return None
        if cls._WORD_CHAR_RE.match(ch):
            return "word"
        if ch.isspace():
            return "space"
        return "other"

    @staticmethod
    def _color_tag_name(style, hex_color):
        # A fixed tag name per style (bold, underline, ...) doesn't work for
        # color, since the tag itself has to carry a specific value — a
        # distinct Tk tag per (style, color) pair, created the first time
        # that exact color is used and reused after that.
        return f"{style}_{hex_color.lstrip('#').lower()}"

    def _ensure_color_tag(self, text_widget, style, hex_color):
        tag = self._color_tag_name(style, hex_color)
        if style == "text_color":
            text_widget.tag_configure(tag, foreground=hex_color)
        else:
            text_widget.tag_configure(tag, background=hex_color)
        # A newly created tag becomes the new highest display priority,
        # which would bury "sel" underneath it -- see the matching
        # tag_raise("sel") in _setup_body_formatting_tags for why that
        # matters.
        text_widget.tag_raise("sel")
        return tag

    @staticmethod
    def _tag_add_no_newline(text_widget, tag, start, end):
        """tag_add over [start, end), but per line and never covering a
        line's newline character.

        Tk paints a BACKGROUND tag across the full remaining width of a
        line whenever the tag covers that line's newline -- so a highlight
        spanning several lines drew a full-width bar on every fully-covered
        line, far past the actual text, instead of hugging the words. Same
        family as the Select-All and triple-click fixes: don't include the
        invisible trailing newline. Only highlight (a background) is
        affected; foreground color and underline/strike don't paint one.
        """
        first = int(str(text_widget.index(start)).split(".")[0])
        last = int(str(text_widget.index(end)).split(".")[0])
        for line in range(first, last + 1):
            seg_start = start if line == first else f"{line}.0"
            seg_end = end if line == last else f"{line}.end"
            if text_widget.compare(seg_start, "<", seg_end):
                text_widget.tag_add(tag, seg_start, seg_end)

    def _extract_formatting(self, text_widget):
        """Read the widget's current tags back out as a plain span list,
        for saving. Character offsets (not Tkinter's own line.col indices)
        so they're stable plain data, independent of line wrapping."""
        spans = []
        for style in KNOWN_FORMAT_STYLES:
            ranges = text_widget.tag_ranges(style)
            for i in range(0, len(ranges), 2):
                start = self._char_offset(text_widget, ranges[i])
                end = self._char_offset(text_widget, ranges[i + 1])
                if end > start:
                    spans.append({"start": start, "end": end, "style": style})
        for tag_name in text_widget.tag_names():
            for style in VALUE_FORMAT_STYLES:
                prefix = style + "_"
                if not tag_name.startswith(prefix):
                    continue
                hex_color = "#" + tag_name[len(prefix):]
                if not _is_valid_hex_color(hex_color):
                    continue
                ranges = text_widget.tag_ranges(tag_name)
                for i in range(0, len(ranges), 2):
                    start = self._char_offset(text_widget, ranges[i])
                    end = self._char_offset(text_widget, ranges[i + 1])
                    if end > start:
                        spans.append({"start": start, "end": end, "style": style,
                                      "value": hex_color})
        return spans

    def _extract_formatting_for_stripped_body(self, text_widget, stripped_body):
        """Like _extract_formatting, but adjusted for save_current_note()'s
        leading/trailing .strip() on the saved body text. Span offsets are
        computed against the widget's raw (unstripped) content — saving them
        as-is against a stripped body would silently shift every span onto
        the wrong characters whenever the note has leading whitespace."""
        raw = text_widget.get("1.0", "end-1c")
        lead = len(raw) - len(raw.lstrip())
        limit = len(stripped_body)
        spans = []
        for span in self._extract_formatting(text_widget):
            start = max(0, span["start"] - lead)
            end = min(limit, span["end"] - lead)
            if end > start:
                shifted = {"start": start, "end": end, "style": span["style"]}
                if "value" in span:
                    shifted["value"] = span["value"]
                spans.append(shifted)
        return spans

    def _apply_formatting(self, text_widget, spans):
        """Re-apply a saved span list as live Tkinter tags, for loading."""
        for span in normalize_formatting(spans):
            try:
                start_idx = text_widget.index(f"1.0+{span['start']}c")
                end_idx = text_widget.index(f"1.0+{span['end']}c")
                if span["style"] in VALUE_FORMAT_STYLES:
                    tag = self._ensure_color_tag(text_widget, span["style"], span["value"])
                else:
                    tag = span["style"]
                if span["style"] == "highlight":
                    # Notes saved before the newline fix can still hold a
                    # single highlight span running across several lines --
                    # re-apply those the corrected way too, so an old note
                    # renders right without needing to be re-highlighted.
                    self._tag_add_no_newline(text_widget, tag, start_idx, end_idx)
                else:
                    text_widget.tag_add(tag, start_idx, end_idx)
            except tk.TclError:
                pass

    def _selection_has_style(self, text_widget, style_set, start, end):
        """True only if EVERY character in [start, end) already carries at
        least one tag from style_set — used to decide whether a toolbar
        toggle should turn a style off (already uniformly applied) or on,
        the same convention most rich text editors use for a mixed
        selection (treated as 'off' until the whole thing is one style)."""
        idx = start
        while text_widget.compare(idx, "<", end):
            if not (set(text_widget.tag_names(idx)) & style_set):
                return False
            idx = text_widget.index(f"{idx}+1c")
        return True

    @staticmethod
    def _font_tag_for(is_bold, is_italic):
        """Which single font tag represents this bold/italic combination (or
        None for neither). Tkinter tags that both set the widget's font
        option don't compose, so bold+italic together needs its own
        precomputed compound tag rather than two independent ones — see
        _FONT_STYLES."""
        if is_bold and is_italic:
            return "bold_italic"
        if is_bold:
            return "bold"
        if is_italic:
            return "italic"
        return None

    @staticmethod
    def _contrasting_fg(hex_color):
        """Black or near-white, whichever reads better against hex_color —
        standard perceived-luminance formula. Used so the Text
        color/Highlight toolbar buttons can show an actual swatch of the
        active color as their own background (not just a subtle tint
        applied against the theme's own sidebar color, which was hard to
        read for some color/theme combinations) while the "A"/"H" letter
        stays legible regardless of which color from the palette, or
        which app theme, is in play."""
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#1a1a1a" if luminance > 0.6 else "#ffffff"

    def _toggle_body_style(self, style):
        """Bold/Italic/Underline/Strikethrough toolbar + right-click handler.

        With an active selection, toggles that style on exactly the
        selected text (existing behavior). With NO selection, toggles a
        "pending" style instead: it has no effect on existing text, but
        every character typed from now on picks it up, until the same
        style is toggled off again the same way — a manual on/off switch,
        not "match whatever formatting is already at the cursor" the way
        some editors infer it. See _apply_pending_style_to_typed_char."""
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
            has_selection = self.body_text.compare(start, "<", end)
        except tk.TclError:
            has_selection = False

        if not has_selection:
            if style in self._pending_styles:
                self._pending_styles.discard(style)
                self.set_status(f"{style.capitalize()} off")
            else:
                self._pending_styles.add(style)
                self.set_status(f"{style.capitalize()} on — applies to what you type next")
            if self._has_any_pending_style():
                # Left gravity: text typed AT this position pushes the
                # cursor forward but leaves the mark itself behind, so it
                # keeps marking "where the pending run started" rather than
                # tracking the cursor like a normal (right-gravity) mark
                # would. See _apply_pending_style_to_typed_char for why
                # this range-based approach (not "just the one most-recent
                # character") is what actually makes fast typing reliable.
                self.body_text.mark_set(self._PENDING_STYLE_ANCHOR, tk.INSERT)
                self.body_text.mark_gravity(self._PENDING_STYLE_ANCHOR, "left")
                self._pending_style_last_length = self._pending_style_text_length()
            self._refresh_format_buttons()
            return

        if style in ("bold", "italic"):
            # Bold and italic both set the Text widget's "font" option, and
            # Tkinter tags that set the same option don't compose — only one
            # wins. So the two can't just be independent on/off tags the way
            # underline/strike are; the pair is tracked as one of exactly
            # four mutually exclusive font tags (none/bold/italic/both).
            is_bold = self._selection_has_style(self.body_text, {"bold", "bold_italic"}, start, end)
            is_italic = self._selection_has_style(self.body_text, {"italic", "bold_italic"}, start, end)
            if style == "bold":
                is_bold = not is_bold
            else:
                is_italic = not is_italic
            for t in self._FONT_STYLES:
                self.body_text.tag_remove(t, start, end)
            tag = self._font_tag_for(is_bold, is_italic)
            if tag:
                self.body_text.tag_add(tag, start, end)
        else:
            already_on = self._selection_has_style(self.body_text, {style}, start, end)
            if already_on:
                self.body_text.tag_remove(style, start, end)
            else:
                self.body_text.tag_add(style, start, end)

        self._refresh_format_buttons()
        self._schedule_autosave()

    def _apply_body_color(self, kind, hex_color):
        """Text-color/highlight-color picker handler. kind is "text_color"
        or "highlight"; hex_color is the chosen color, or None to clear it.

        Unlike Bold/Italic/Underline/Strikethrough, a color isn't a simple
        on/off switch — it's "one of a palette, or nothing" — so this
        isn't quite a toggle: clicking a swatch always sets that color
        (replacing whichever color of the same kind was already on the
        selection, if any), and a separate "Clear" entry in the picker
        popup passes hex_color=None to remove it. With no selection, this
        sets (or clears) the PENDING color instead, sharing the exact same
        anchor-mark-and-length-tracking machinery _toggle_body_style uses
        for the boolean styles — see _has_any_pending_style."""
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
            has_selection = self.body_text.compare(start, "<", end)
        except tk.TclError:
            has_selection = False

        label = "Highlight" if kind == "highlight" else "Text color"

        if not has_selection:
            if kind == "text_color":
                self._pending_text_color = hex_color
            else:
                self._pending_highlight_color = hex_color
            self.set_status(f"{label} on — applies to what you type next" if hex_color
                             else f"{label} off")
            if self._has_any_pending_style():
                self.body_text.mark_set(self._PENDING_STYLE_ANCHOR, tk.INSERT)
                self.body_text.mark_gravity(self._PENDING_STYLE_ANCHOR, "left")
                self._pending_style_last_length = self._pending_style_text_length()
            self._refresh_format_buttons()
            return

        # A span only ever has one text color and one highlight color at a
        # time -- remove whatever tag of this kind is already there before
        # adding (or not adding) the new one, rather than layering a
        # second tag that would just win or lose by tag priority.
        for tag_name in self.body_text.tag_names():
            if tag_name.startswith(kind + "_"):
                self.body_text.tag_remove(tag_name, start, end)
        if hex_color:
            tag = self._ensure_color_tag(self.body_text, kind, hex_color)
            if kind == "highlight":
                self._tag_add_no_newline(self.body_text, tag, start, end)
            else:
                self.body_text.tag_add(tag, start, end)

        self._refresh_format_buttons()
        self._schedule_autosave()

    def _open_color_swatch_popup(self, kind):
        """Text-color/highlight picker popup — a grid of swatches plus a
        Clear option, anchored to the toolbar button that opened it.
        Closely mirrors open_color_picker() (the note's own color), reused
        here with a different palette and a different target (the body
        text's formatting instead of the note's color). Swatches only, no
        hex-code entry -- most users don't think in hex, so the palette is
        the whole picker."""
        self._dismiss_mini_popup()
        palette = PRESET_NOTE_COLORS if kind == "text_color" else HIGHLIGHT_COLOR_PALETTE
        anchor_btn = self.text_color_btn if kind == "text_color" else self.highlight_btn
        label_text = "Pick a text color" if kind == "text_color" else "Pick a highlight color"

        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])
        outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        body = tk.Frame(outer, bg=self.colors["card"])
        body.pack()

        label = tk.Label(body, text=label_text, font=("Segoe UI", 10, "bold"),
                          bg=self.colors["card"], fg=self.colors["text"])
        label.pack(padx=15, pady=(12, 8))

        swatch_grid = tk.Frame(body, bg=self.colors["card"])
        swatch_grid.pack(padx=15)

        def _choose(color):
            self._apply_body_color(kind, color)
            self._dismiss_mini_popup()

        for i, hex_color in enumerate(palette):
            swatch = tk.Button(
                swatch_grid, bg=hex_color, activebackground=hex_color, width=3, height=1,
                relief="flat", cursor="hand2", command=lambda c=hex_color: _choose(c)
            )
            swatch.grid(row=i // 5, column=i % 5, padx=4, pady=4)

        button_row = tk.Frame(body, bg=self.colors["card"])
        button_row.pack(fill="x", padx=15, pady=(8, 14))
        clear_btn = tk.Button(
            button_row, text="Clear", command=lambda: _choose(None), relief="flat",
            bg=self.colors["sidebar"], fg=self.colors["text"], cursor="hand2", font=("Segoe UI", 9)
        )
        clear_btn.pack(fill="x", ipady=5)

        self._place_dropdown_popup(popup, anchor_btn)

    def _pending_style_text_length(self):
        result = self.body_text.count("1.0", "end-1c", "chars")
        return result[0] if result else 0

    def _has_any_pending_style(self):
        """True if there's anything queued for the next typed character —
        a boolean style (bold/italic/underline/strike) or a color. Colors
        aren't members of _pending_styles (a color isn't on/off, it's a
        value, or nothing), so this is the one place that needs to know
        about both kinds together — anywhere that used to just check
        "is _pending_styles non-empty" now goes through this instead."""
        return bool(self._pending_styles) or bool(self._pending_text_color) \
            or bool(self._pending_highlight_color)

    def _apply_pending_style_to_typed_char(self, event=None):
        """Tag whatever's accumulated since _PENDING_STYLE_ANCHOR (set when
        a style was last toggled on with nothing selected, or resynced
        below) up through the current cursor — not just "the one character
        the cursor is now past". Bound to <KeyRelease>.

        The first version of this tagged only a single character —
        "whatever's immediately before the cursor right now" — on the
        reasoning that KeyRelease always fires once per keystroke, right
        after that keystroke's own insertion. True, but under a fast burst
        Tk can process several KeyPress insertions before it gets around
        to dispatching the KeyRelease callbacks for them, so a callback
        can end up running once the cursor has already moved past MORE
        than one new character — "the one character before the cursor" at
        that moment silently skips whichever ones came in between. Tagging
        the whole span from the anchor to the cursor instead means it
        doesn't matter how many characters piled up before a callback got
        its turn — the next one that runs covers all of them in one go,
        since tag_add over an already-tagged sub-range is harmless and
        adjacent same-tag ranges merge automatically.

        Deciding WHETHER to extend the tag is based on whether the note's
        total character count actually grew since the last check — not on
        inspecting event.char/event.state the way an earlier version of
        this did. That first version correctly matched real-world testing
        on Windows, but failed in CI (Linux + Xvfb): a differently-behaving
        Tk build populated (or didn't populate) event.char differently for
        at least one of a fast burst's synthetic key events, which got
        misread as "not a real keystroke" and silently ate a chunk of
        already-typed, correctly-inserted text out of the tag. Character
        count is a fact about the widget's actual content, not something
        that depends on how a given platform's Tk build fills in event
        details — grew means something was typed (of any burst size);
        unchanged or shrank means nothing new to tag, just resync tracking.
        A paste is excluded separately (see the <<Paste>> binding below),
        not by inspecting this event either.

        A version of this whole feature that hooked the Tcl level for
        true per-insert precision was tried and reverted after three
        separate, unpredictable app-launch crashes (Tk's own internal
        Text-widget bookkeeping hits several "normally harmless, silently
        tolerated" Tcl errors that turned into real, escaping Python
        exceptions once a Python proxy sat in the call path). This
        mark-based approach stays entirely within ordinary,
        already-proven-safe Tkinter usage (the same kind of mark tracking
        the calculator's insert-into-note feature already relies on).
        See docs/ISSUES_LOG.md."""
        if not self._has_any_pending_style():
            return
        if self._PENDING_STYLE_ANCHOR not in self.body_text.mark_names():
            return
        current_length = self._pending_style_text_length()
        if current_length <= self._pending_style_last_length:
            # No growth (a shortcut key's release, arrow keys, Home/End) or
            # the text shrank (Backspace/Delete) -- nothing new to tag.
            self._resync_pending_style_anchor()
            return
        start_idx = self.body_text.index(self._PENDING_STYLE_ANCHOR)
        end_idx = self.body_text.index(tk.INSERT)
        if self.body_text.compare(start_idx, "<", end_idx):
            tag = self._font_tag_for("bold" in self._pending_styles, "italic" in self._pending_styles)
            if tag:
                self.body_text.tag_add(tag, start_idx, end_idx)
            if "underline" in self._pending_styles:
                self.body_text.tag_add("underline", start_idx, end_idx)
            if "strike" in self._pending_styles:
                self.body_text.tag_add("strike", start_idx, end_idx)
            if self._pending_text_color:
                color_tag = self._ensure_color_tag(self.body_text, "text_color", self._pending_text_color)
                self.body_text.tag_add(color_tag, start_idx, end_idx)
            if self._pending_highlight_color:
                color_tag = self._ensure_color_tag(self.body_text, "highlight", self._pending_highlight_color)
                # Typing past the end of a line (pressing Enter with a
                # highlight still "stuck" on) would otherwise sweep the
                # newline into the tag and bleed the bar full-width.
                self._tag_add_no_newline(self.body_text, color_tag, start_idx, end_idx)
        self.body_text.mark_set(self._PENDING_STYLE_ANCHOR, end_idx)
        self._pending_style_last_length = current_length

    def _resync_pending_style_anchor(self, event=None):
        """Move the pending-style anchor to the cursor's current position
        with no tagging, and refresh the length baseline it's compared
        against — used whenever the cursor moves without typing
        (navigation keys, a mouse click), and right after a paste (bound
        separately, below), so a later keystroke only ever extends the
        tag over genuinely new typing, never a stretch of older text or a
        pasted block it was never meant to touch."""
        if self._has_any_pending_style() and self._PENDING_STYLE_ANCHOR in self.body_text.mark_names():
            self.body_text.mark_set(self._PENDING_STYLE_ANCHOR, tk.INSERT)
            self._pending_style_last_length = self._pending_style_text_length()

    def _select_word_at_click(self, event):
        """Replaces Tk's default double-click "select word" with a plain
        alnum/underscore definition of "word" (see _char_class), so a
        double-click never crosses a "." or other punctuation -- e.g.
        double-clicking "something" in "something.else" selects only
        "something", and double-clicking "else" selects only "else".

        Also makes double-clicking an EMPTY line select nothing at all,
        rather than Tk's default of grabbing that line's invisible newline
        and painting a full-width selection bar over a row with no words
        in it.

        Works off event.widget, so the same handler serves the note body
        and the comments box rather than being tied to either."""
        w = event.widget
        index = w.index(f"@{event.x},{event.y}")
        line, col = index.split(".")
        line_text = w.get(f"{line}.0", f"{line}.0 lineend")
        col = min(int(col), len(line_text) - 1)
        if col < 0:
            return "break"
        char_cls = self._char_class(line_text[col])
        if char_cls is None:
            return "break"
        start = col
        while start > 0 and self._char_class(line_text[start - 1]) == char_cls:
            start -= 1
        end = col + 1
        while end < len(line_text) and self._char_class(line_text[end]) == char_cls:
            end += 1
        w.tag_remove("sel", "1.0", "end")
        w.tag_add("sel", f"{line}.{start}", f"{line}.{end}")
        w.mark_set("insert", f"{line}.{end}")
        return "break"

    def _select_line_no_newline(self, event):
        """Replaces Tk's default triple-click "select line" behavior. Tk's
        own version selects through the START of the next line, which
        silently includes the invisible trailing newline character in the
        selection -- same overshoot as the Select-All fix above, but harder
        to notice here because it's triggered by mouse clicks (a
        triple-click, or two double-clicks close enough together in time
        that Tk counts them as one), not a menu command. Left as-is, it
        also means copy/paste carries that extra newline along with the
        line's real text.

        Works off event.widget, so the same handler serves the note body
        and the comments box rather than being tied to either."""
        w = event.widget
        index = w.index(f"@{event.x},{event.y}")
        line = index.split(".")[0]
        line_start, line_end = f"{line}.0", f"{line}.0 lineend"
        w.tag_remove("sel", "1.0", "end")
        w.tag_add("sel", line_start, line_end)
        w.mark_set("insert", line_end)
        return "break"

    def _bind_text_selection_fixes(self, text_widget):
        """Apply the double-click (word boundary / empty line) and
        triple-click (no trailing newline) selection fixes to a Text
        widget. Used for every multi-line text field the user types real
        prose into, so selection behaves the same way in all of them."""
        text_widget.bind("<Double-Button-1>", self._select_word_at_click)
        text_widget.bind("<Triple-Button-1>", self._select_line_no_newline)

    def _uniform_color_in_selection(self, kind, start, end):
        """The single hex color of the given kind ("text_color" or
        "highlight") that covers the ENTIRE [start, end) range, or None if
        the range is empty, uncolored, or a mix of more than one color —
        the color-preview equivalent of _selection_has_style."""
        prefix = kind + "_"
        color = None
        idx = start
        while self.body_text.compare(idx, "<", end):
            # Newlines deliberately never carry a highlight tag (see
            # _tag_add_no_newline), so judging them as "uncolored" here
            # would report any multi-line selection as a mix and stop the
            # toolbar button from previewing the color that's really there.
            if self.body_text.get(idx) == "\n":
                idx = self.body_text.index(f"{idx}+1c")
                continue
            names = [n for n in self.body_text.tag_names(idx) if n.startswith(prefix)]
            if not names:
                return None
            this_hex = "#" + names[0][len(prefix):]
            if color is None:
                color = this_hex
            elif color != this_hex:
                return None
            idx = self.body_text.index(f"{idx}+1c")
        return color

    def _refresh_format_buttons(self, event=None):
        """Reflect the current selection's styles — or, with no selection,
        the pending styles queued up for the next typed character — in the
        toolbar buttons' pressed/unpressed look. Called on selection/cursor
        changes and whenever a pending style is toggled."""
        if not hasattr(self, "_fmt_buttons"):
            return
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
            has_selection = self.body_text.compare(start, "<", end)
        except tk.TclError:
            has_selection = False
        for style, btn in self._fmt_buttons.items():
            if has_selection:
                check = {"bold_italic", style} if style in ("bold", "italic") else {style}
                active = self._selection_has_style(self.body_text, check, start, end)
            else:
                active = style in self._pending_styles
            btn.configure(
                relief="sunken" if active else "flat",
                bg=self.colors["accent"] if active else self.colors["sidebar"],
                fg="white" if active else self.colors["text"],
            )

        if hasattr(self, "text_color_btn"):
            if has_selection:
                text_color = self._uniform_color_in_selection("text_color", start, end)
                highlight_color = self._uniform_color_in_selection("highlight", start, end)
            else:
                text_color = self._pending_text_color
                highlight_color = self._pending_highlight_color
            # Both buttons show an actual swatch of the active color as
            # their own background when one is set (matching the note's
            # own color-swatch button elsewhere in the app — a familiar
            # pattern, not a new visual language), falling back to the
            # theme's normal button look when nothing is active. Either
            # way the letter's contrast is computed from whatever
            # background is actually showing, so it stays legible for
            # any palette color against any app theme.
            tc_bg = text_color or self.colors["sidebar"]
            hl_bg = highlight_color or self.colors["sidebar"]
            self.text_color_btn.configure(
                bg=tc_bg, activebackground=tc_bg,
                fg=self._contrasting_fg(tc_bg) if text_color else self.colors["text"],
            )
            self.highlight_btn.configure(
                bg=hl_bg, activebackground=hl_bg,
                fg=self._contrasting_fg(hl_bg) if highlight_color else self.colors["text"],
            )

    # A curated set — common, broadly useful emojis grouped loosely by theme,
    # not an exhaustive unicode picker. Keeps the popup a manageable size.
    # Each group also gets its own chip color: Tk can't render true color
    # emoji glyphs on Windows (a platform rendering limitation, not a font
    # choice), so every glyph shows as a monochrome outline regardless of
    # font. Giving each category its own colored chip background makes them
    # look deliberately styled rather than broken, and doubles as a visual
    # grouping cue.
    EMOJI_GROUPS = [
        ("Faces", ["😀", "😄", "😂", "🙂", "😉", "😍", "🤔", "😅", "😢", "😮",
                  "😴", "🥳", "😎", "🙄", "😬", "🤯"], "#FFD166"),
        ("Gestures", ["👍", "👎", "👏", "🙌", "🤝", "✌️", "🤞", "👌", "💪", "🙏"], "#6EC6CA"),
        ("Hearts & stars", ["❤️", "💜", "💙", "💚", "🧡", "💛", "⭐", "✨", "🌟", "💯"], "#FF8FA3"),
        ("Checks & flags", ["✅", "❌", "☑️", "⚠️", "🚩", "🔴", "🟡", "🟢", "🔵", "⏰"], "#A0C4FF"),
        ("Objects", ["📌", "📎", "📅", "📝", "💡", "🔥", "🎯", "🎉", "🚀", "📦",
                    "🔑", "📞", "💬", "🔗", "🏆"], "#FFB4A2"),
        ("Nature", ["☀️", "🌙", "⛅", "🌧️", "🌈", "🌸", "🍀", "🌳", "☕", "🍕"], "#B9FBC0"),
    ]

    def _show_emoji_picker(self, text_widget):
        """Small themed popup for inserting an emoji at the current cursor
        position of whichever field opened it (title, body, comments, etc.).
        Anchored to that field, not a separate window."""
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        outer = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        outer.pack(padx=1, pady=1)

        head = tk.Frame(outer, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Insert emoji", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")

        wrap = tk.Frame(outer, bg=self.colors["card"], height=220, width=260)
        wrap.pack()
        wrap.pack_propagate(False)
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["card"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw", width=240)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def insert_emoji(emoji):
            try:
                # Skip re-focusing if this field already has focus — avoids
                # redundant OS-level focus-change overhead on rapid clicks.
                if self.focus_get() is not text_widget:
                    text_widget.focus_set()
                if isinstance(text_widget, tk.Text):
                    text_widget.insert(tk.INSERT, emoji)
                else:
                    pos = text_widget.index(tk.INSERT)
                    text_widget.insert(pos, emoji)
                    text_widget.icursor(pos + len(emoji))
                # Best-effort: nudge autosave if this field participates in it.
                # skip_word_count avoids re-reading the whole body on every
                # single click — that's what made rapid emoji-clicking laggy.
                self._schedule_autosave(skip_word_count=True)
            except tk.TclError:
                pass
            # Left open on purpose — inserting a few emojis in a row is common.
            return "break"

        for group_name, emojis, group_color in self.EMOJI_GROUPS:
            tk.Label(inner, text=group_name, bg=self.colors["card"],
                     fg=self.colors["subtext"], font=("Segoe UI", 8, "bold"),
                     anchor="w").pack(fill="x", pady=(4, 2))
            grid = tk.Frame(inner, bg=self.colors["card"])
            grid.pack(fill="x")
            cols = 8
            # Tk can't render true color emoji glyphs on Windows regardless of
            # font — a platform rendering limitation. Giving each category its
            # own colored chip background makes them read as deliberately
            # styled rather than broken, and doubles as a grouping cue.
            chip_bg = group_color
            chip_hover = _darken_hex(group_color)
            for i, em in enumerate(emojis):
                r, c = divmod(i, cols)
                cell = tk.Label(grid, text=em, font=("Segoe UI Emoji", 14),
                                bg=chip_bg, cursor="hand2", bd=0,
                                width=2, height=1)
                cell.grid(row=r, column=c, padx=2, pady=2, ipadx=1, ipady=1)
                cell.bind("<Button-1>", lambda e, em=em: insert_emoji(em))
                cell.bind("<Enter>", lambda e, w=cell, h=chip_hover: w.configure(bg=h))
                cell.bind("<Leave>", lambda e, w=cell, b=chip_bg: w.configure(bg=b))

        # Bind the wheel now that every emoji cell exists — binding earlier
        # only reaches whatever's already in the tree at that moment, missing
        # everything created afterward (which is all of it, since the emoji
        # grid is built right below this).
        self._bind_mousewheel_recursive(inner, canvas)

        self._place_dropdown_popup(pop, text_widget)

    def _build_import_panel(self):
        """The inline import panel: a paste box + Import/close, shown under the
        sidebar button instead of a pop-up window."""
        p = self.import_panel
        tk.Label(p, text="Paste a share code:", font=("Segoe UI", 8, "bold"),
                 anchor="w", bg=self.colors["sidebar"], fg=self.colors["text"]
                 ).pack(fill="x", padx=6, pady=(6, 2))
        self.import_box = tk.Text(p, height=4, wrap="char", font=("Consolas", 8),
                                  relief="flat", bg=self.colors["card"], fg=self.colors["text"],
                                  insertbackground=self.colors["text"], padx=6, pady=6)
        self.track_theme(self.import_box, bg="card", fg="text")
        self.import_box.pack(fill="x", padx=6)
        self._add_paste_menu(self.import_box)
        self.import_status = tk.Label(p, text="", font=("Segoe UI", 7), anchor="w",
                                      wraplength=200, justify="left",
                                      bg=self.colors["sidebar"], fg=self.colors["danger"])
        self.import_status.pack(fill="x", padx=6, pady=(2, 0))
        row = tk.Frame(p, bg=self.colors["sidebar"])
        self.track_theme(row, bg="sidebar")
        row.pack(fill="x", padx=6, pady=6)
        tk.Button(row, text="Import", command=self._do_inline_import,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", fill="x", expand=True, padx=(0, 3), ipady=3)
        tk.Button(row, text="Clear", command=self._clear_import_box,
                  bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                  font=("Segoe UI", 9), cursor="hand2"
                  ).pack(side="left", fill="x", expand=True, padx=3, ipady=3)
        tk.Button(row, text="Close", command=self.toggle_import_panel,
                  bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                  font=("Segoe UI", 9), cursor="hand2"
                  ).pack(side="left", fill="x", expand=True, padx=(3, 0), ipady=3)

    def _clear_import_box(self):
        """Wipe the pasted code and any leftover status message, so a long
        code can be replaced without manually selecting and deleting it."""
        self.import_box.delete("1.0", "end")
        self.import_status.config(text="")
        self.import_box.focus()

    def toggle_import_panel(self):
        if self.import_panel.winfo_ismapped():
            self.import_panel.pack_forget()
        else:
            if self.share_panel.winfo_ismapped():
                self.share_panel.pack_forget()
            self.import_panel.pack(fill="x", padx=8, pady=(0, 8))
            self.import_box.focus()

    def _do_inline_import(self):
        code = self.import_box.get("1.0", "end")
        try:
            shared = decode_share_code(code)
        except ValueError as e:
            self.import_status.config(text=str(e), fg=self.colors["danger"])
            return
        valid = [sn for sn in shared if isinstance(sn, dict)]
        if not valid:
            self.import_status.config(text="No valid notes in that code.",
                                      fg=self.colors["danger"])
            return
        if len(valid) == 1:
            incoming = valid[0]
            existing_keys = {_dup_key(n) for n in self.notes}
            if _dup_key(normalize_note(incoming)) in existing_keys:
                choice = self._themed_dialog(
                    "Possible duplicate",
                    "This note looks identical to one you already have (same "
                    "title, text, comments and category).",
                    kind="question",
                    buttons=[("Cancel", "cancel"), ("Open it anyway", "open")]
                )
                if choice is None or choice == "cancel":
                    return
            self.import_box.delete("1.0", "end")
            self.toggle_import_panel()
            self._open_imported_note_in_editor(incoming)
            return
        next_id = max([n["id"] for n in self.notes], default=0) + 1
        # Check each incoming note against what's already here — same
        # matching rule as "Find duplicates" — before blindly appending
        # everything. Importing the same share code twice (or a code that
        # overlaps with notes you already kept) used to silently create
        # duplicates with no way to tell beforehand.
        existing_keys = {_dup_key(n) for n in self.notes}
        fresh = [sn for sn in valid if _dup_key(normalize_note(sn)) not in existing_keys]
        dupe_count = len(valid) - len(fresh)
        to_import = valid
        if dupe_count > 0:
            if fresh:
                choice = self._themed_dialog(
                    "Possible duplicates",
                    f"{dupe_count} of the {len(valid)} note(s) in this code look "
                    "identical to notes you already have (same title, text, "
                    "comments and category).",
                    kind="question",
                    buttons=[("Cancel", "cancel"),
                             ("Import all anyway", "all"),
                             (f"Skip the {dupe_count} duplicate(s)", "skip")]
                )
            else:
                choice = self._themed_dialog(
                    "All notes already imported",
                    f"All {len(valid)} note(s) in this code look identical to "
                    "notes you already have. Import them anyway as new copies?",
                    kind="question",
                    buttons=[("Cancel", "cancel"), ("Import anyway", "all")]
                )
            if choice is None or choice == "cancel":
                return
            if choice == "skip":
                to_import = fresh
        added = 0
        for sn in to_import:
            note = normalize_note(sn)
            note["id"] = next_id
            next_id += 1
            self.notes.append(note)
            added += 1
        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        self.import_box.delete("1.0", "end")
        skipped_note = f" ({dupe_count} duplicate(s) skipped)" if dupe_count and to_import is not valid else ""
        self.import_status.config(text=f"Added {added} notes ✓{skipped_note}", fg=self.colors["success"])

    def toggle_share_panel(self):
        if self.share_panel.winfo_ismapped():
            self.share_panel.pack_forget()
        else:
            if self.import_panel.winfo_ismapped():
                self.import_panel.pack_forget()
            self._build_share_panel()
            self.share_panel.pack(fill="x", padx=8, pady=(0, 8))

    def _build_share_panel(self):
        """Inline multi-note share: checkboxes to pick notes, then a generated
        code shown right here with a Copy button."""
        for w in self.share_panel.winfo_children():
            w.destroy()
        p = self.share_panel
        if not self.notes:
            tk.Label(p, text="No notes to share yet.", font=("Segoe UI", 8),
                     bg=self.colors["sidebar"], fg=self.colors["subtext"]
                     ).pack(padx=6, pady=6)
            return
        tk.Label(p, text="Pick notes to share:", font=("Segoe UI", 8, "bold"),
                 anchor="w", bg=self.colors["sidebar"], fg=self.colors["text"]
                 ).pack(fill="x", padx=6, pady=(6, 2))

        # Scrollable checklist (a notebook can have many notes). Fixed height so
        # it never grows the whole panel off-screen; the scrollbar handles the
        # overflow.
        list_wrap = tk.Frame(p, bg=self.colors["sidebar"], height=130)
        list_wrap.pack(fill="x", padx=6, pady=(0, 2))
        list_wrap.pack_propagate(False)
        canvas = tk.Canvas(list_wrap, bg=self.colors["sidebar"], highlightthickness=0)
        sb = ttk.Scrollbar(list_wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["sidebar"])
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _fit(e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Make the inner frame span the canvas width so checkboxes fill it.
            canvas.itemconfig(cwin, width=canvas.winfo_width())
        inner.bind("<Configure>", _fit)
        canvas.bind("<Configure>", _fit)
        canvas.configure(yscrollcommand=sb.set)
        # Pack scrollbar FIRST so it always keeps its width, then the canvas.
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._share_checklist_canvas = canvas

        # Direct .configure() calls, not self.track_theme(): this whole panel
        # is destroyed and rebuilt every time "Share notes" is opened, so it
        # always picks up the current theme fresh anyway — the same leak
        # fixed in the note list, calendar, and attachments list. Paginated
        # for the same reason the trash list is: one Checkbutton per note
        # with no cap hits the same slowdown once note counts grow large.
        self._share_vars = getattr(self, "_share_vars", {}) or {}
        SHARE_PAGE_SIZE = 100
        shown = {"n": SHARE_PAGE_SIZE}

        def render_checkboxes():
            for w in inner.winfo_children():
                w.destroy()
            visible_notes = self.notes[:shown["n"]]
            for n in visible_notes:
                if n["id"] not in self._share_vars:
                    self._share_vars[n["id"]] = tk.BooleanVar(value=False)
                var = self._share_vars[n["id"]]
                title = (n["title"].strip() or "(untitled)")[:24]
                extra = " 📎" if n.get("attachments") else ""
                cb = tk.Checkbutton(inner, text=title + extra, variable=var,
                                    bg=self.colors["sidebar"], fg=self.colors["text"],
                                    selectcolor=self.colors["card"],
                                    activebackground=self.colors["sidebar"],
                                    activeforeground=self.colors["text"],
                                    font=("Segoe UI", 8), anchor="w")
                cb.pack(fill="x", anchor="w")
            remaining = len(self.notes) - len(visible_notes)
            if remaining > 0:
                def show_more():
                    shown["n"] += SHARE_PAGE_SIZE
                    render_checkboxes()
                tk.Button(inner, text=f"Show {min(remaining, SHARE_PAGE_SIZE)} more "
                                      f"({remaining} not shown)",
                          command=show_more, relief="flat", cursor="hand2",
                          bg=self.colors["card"], fg=self.colors["text"],
                          font=("Segoe UI", 8)).pack(fill="x", pady=(4, 2))
            # Bind the wheel now that the checkboxes exist, so scrolling works
            # with the cursor anywhere over the list.
            self._bind_mousewheel_recursive(inner, self._share_checklist_canvas)

        render_checkboxes()

        gen_row = tk.Frame(p, bg=self.colors["sidebar"])
        gen_row.pack(fill="x", padx=6, pady=(4, 2))
        tk.Button(gen_row, text="Generate code", command=self._generate_inline_share,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", fill="x", expand=True, padx=(0, 3), ipady=3)
        tk.Button(gen_row, text="Close", command=self.toggle_share_panel,
                  bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                  font=("Segoe UI", 9), cursor="hand2"
                  ).pack(side="left", fill="x", expand=True, padx=(3, 0), ipady=3)

        # The generated code appears here after "Generate code".
        self.share_code_area = tk.Frame(p, bg=self.colors["sidebar"])
        self.share_code_area.pack(fill="x", padx=6, pady=(0, 6))

    def _generate_inline_share(self):
        chosen = [n for n in self.notes if self._share_vars.get(n["id"]) and self._share_vars[n["id"]].get()]
        for w in self.share_code_area.winfo_children():
            w.destroy()
        if not chosen:
            tk.Label(self.share_code_area, text="Pick at least one note.",
                     font=("Segoe UI", 8), bg=self.colors["sidebar"],
                     fg=self.colors["danger"]).pack(anchor="w")
            return
        had_attachments = any(n.get("attachments") for n in chosen)
        code = encode_share_code(chosen)
        self._render_inline_code(self.share_code_area, code, len(chosen), had_attachments)

    def _render_inline_code(self, parent, code, count, had_attachments):
        """Show a generated code inline with a Copy button (used by share)."""
        noun = "note" if count == 1 else "notes"
        tk.Label(parent, text=f"Code for {count} {noun} ({len(code)} chars):",
                 font=("Segoe UI", 8, "bold"), anchor="w",
                 bg=self.colors["sidebar"], fg=self.colors["text"]
                 ).pack(fill="x", pady=(4, 2))
        if had_attachments:
            tk.Label(parent, text="⚠ Attachments not included — use Export for files.",
                     font=("Segoe UI", 7), anchor="w", wraplength=200, justify="left",
                     bg=self.colors["sidebar"], fg=self.colors["danger"]
                     ).pack(fill="x", pady=(0, 2))
        box = tk.Text(parent, height=3, wrap="char", font=("Consolas", 7),
                      relief="flat", bg=self.colors["card"], fg=self.colors["text"],
                      padx=6, pady=6)
        box.insert("1.0", code)
        box.config(state="disabled")
        box.pack(fill="x")
        status = tk.Label(parent, text="", font=("Segoe UI", 7), anchor="w",
                          bg=self.colors["sidebar"], fg=self.colors["success"])
        status.pack(fill="x")

        def copy():
            try:
                self.clipboard_clear()
                self.clipboard_append(code)
                self.update()
                status.config(text="Copied to clipboard ✓", fg=self.colors["success"])
            except tk.TclError:
                status.config(text="Select the code and copy manually.",
                              fg=self.colors["danger"])
        tk.Button(parent, text="📋 Copy code", command=copy, bg=self.colors["accent"],
                  fg="white", relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(fill="x", pady=(4, 0), ipady=3)

    def share_current_note_as_code(self):
        """Generate a share code for the note currently open and show it inline
        in the editor (no pop-up), with a Copy button."""
        st = self.capture_editor_state()
        if not (st["title"].strip() or st["body"].strip()):
            self.set_status("Write something before copying a code.")
            return
        note = {
            "title": st["title"], "body": st["body"], "comments": st["comments"],
            "category": st["category"], "date": st["date"], "color": st["color"],
            "recurrence": st["recurrence"],
        }
        had_attachments = bool(st["attachments"])
        code = encode_share_code(note)
        # Render inline in the editor's code area.
        for w in self.editor_code_area.winfo_children():
            w.destroy()
        if not self.editor_code_area.winfo_ismapped():
            self.editor_code_area.pack(fill="x", padx=30, pady=(0, 20))
        self._render_editor_code(code, had_attachments)

    def _render_editor_code(self, code, had_attachments):
        # Direct .configure() calls, not self.track_theme(): this area is
        # destroyed and rebuilt every time "Copy code" is clicked, so it
        # always picks up the current theme fresh anyway — same leak fixed
        # elsewhere (note list, calendar, attachments, share panel).
        parent = self.editor_code_area
        header = tk.Frame(parent, bg=self.colors["bg"])
        header.pack(fill="x")
        tk.Label(header, text=f"Share code ({len(code)} characters):",
                 font=("Segoe UI", 9, "bold"), anchor="w",
                 bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")
        tk.Button(header, text="✕", command=lambda: self.editor_code_area.pack_forget(),
                  bg=self.colors["bg"], fg=self.colors["subtext"], relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2").pack(side="right")
        if had_attachments:
            tk.Label(parent, text="⚠ Attachments aren't included in a code — use Export for files.",
                     font=("Segoe UI", 8), anchor="w", wraplength=600, justify="left",
                     bg=self.colors["bg"], fg=self.colors["danger"]).pack(fill="x", pady=(2, 2))
        box = tk.Text(parent, height=3, wrap="char", font=("Consolas", 9),
                      relief="flat", bg=self.colors["card"], fg=self.colors["text"],
                      padx=10, pady=8)
        box.insert("1.0", code)
        box.config(state="disabled")
        box.pack(fill="x", pady=(2, 4))
        status = tk.Label(parent, text="", font=("Segoe UI", 8), anchor="w",
                          bg=self.colors["bg"], fg=self.colors["success"])
        status.pack(fill="x")

        def copy():
            try:
                self.clipboard_clear()
                self.clipboard_append(code)
                self.update()
                status.config(text="Copied to clipboard ✓", fg=self.colors["success"])
            except tk.TclError:
                status.config(text="Select the code above and copy it manually (Ctrl+C).",
                              fg=self.colors["danger"])
        tk.Button(parent, text="📋 Copy code", command=copy, bg=self.colors["accent"],
                  fg="white", relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
                  ).pack(fill="x", pady=(2, 0), ipady=5)

    def _open_imported_note_in_editor(self, shared_note):
        """Load an imported single note into a fresh editor tab WITHOUT saving,
        so the user can review or edit it, then hit Save when ready. Crucially
        this stays a NEW note (no selected_note_id) so Save creates a fresh one."""
        note = normalize_note(shared_note)
        self.notebook.select(self.TAB_NOTES)
        self.open_blank_tab()    # gives a clean new-note editor state

        self.title_entry.delete(0, "end")
        title = note.get("title", "")
        if title:
            self.title_entry.insert(0, title)
            self.title_entry.config(fg=self.colors["text"])

        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", note.get("body", ""))
        self._apply_formatting(self.body_text, note.get("formatting", []))
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", note.get("comments", ""))

        self.date_entry.delete(0, "end")
        if note.get("date"):
            self.date_entry.insert(0, note["date"])
            self.date_entry.config(fg=self.colors["text"])
        else:
            self.date_entry.insert(0, "YYYY-MM-DD")
            self.date_entry.config(fg=self.colors["subtext"])

        cat = note.get("category", "General")
        self.category_var.set(cat if cat in CATEGORY_COLORS else "General")

        self.current_note_color = note.get("color", "")
        self._update_color_swatch()

        self.write_recurrence_to_ui(note.get("recurrence"))

        self.update_word_count()
        self.set_status("Imported from code — review, then Save to keep it")

    def import_data(self):
        """Import a previously exported .zip. Notes are MERGED into your
        current list (never overwritten) — safe to use even if this device
        already has notes of its own.

        The slow parts (extracting the zip, copying attachments back) run on
        a background thread, same as export — for a backup with a lot of
        attachments this used to visibly freeze the app while it worked."""
        zip_path = filedialog.askopenfilename(
            title="Choose a notes backup (.zip) to import",
            filetypes=[("Zip files", "*.zip")]
        )
        if not zip_path:
            return

        confirm = self.ask_yes_no(
            "Import notes",
            "This will ADD the notes from that backup to your current list "
            "(your existing notes won't be changed or removed).\n\n"
            "Continue?"
        )
        if not confirm:
            return

        self._import_state = {"phase": "extracting", "current": 0, "total": 1,
                              "done": False, "error": None,
                              "temp_dir": None, "imported_notes": None}
        self.export_progress_bar.configure(maximum=1, value=0)
        self.export_progress_lbl.config(text="Importing… reading backup")
        self.export_progress_frame.place(relx=0.5, rely=1.0, anchor="s", y=-14)
        self.export_progress_frame.lift()

        def worker():
            state = self._import_state
            try:
                temp_dir = tempfile.mkdtemp(prefix="notes_import_")
                state["temp_dir"] = temp_dir
                try:
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        _safe_extract_zip(zf, temp_dir)
                except (zipfile.BadZipFile, IOError, OSError, ValueError) as e:
                    state["error"] = f"That file couldn't be read as a backup:\n{e}"
                    state["done"] = True
                    return

                imported_notes_path = os.path.join(temp_dir, "notes_data.json")
                if not os.path.exists(imported_notes_path):
                    state["error"] = "This .zip doesn't look like a Notes Organizer backup."
                    state["done"] = True
                    return

                try:
                    with open(imported_notes_path, "r", encoding="utf-8") as f:
                        imported_notes = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    state["error"] = f"Couldn't read the notes in that backup:\n{e}"
                    state["done"] = True
                    return
                state["imported_notes"] = imported_notes

                # Copy any attached files from the backup into our attachments
                # folder — the slowest part for a backup with a lot of them.
                imported_attachments_dir = os.path.join(temp_dir, "attachments")
                state["phase"] = "copying"
                if os.path.isdir(imported_attachments_dir):
                    files = os.listdir(imported_attachments_dir)
                    state["total"] = max(len(files), 1)
                    for i, filename in enumerate(files, start=1):
                        dest = os.path.join(ATTACHMENTS_DIR, filename)
                        if not os.path.exists(dest):
                            try:
                                shutil.copy2(os.path.join(imported_attachments_dir, filename), dest)
                            except (IOError, OSError):
                                pass  # non-critical — the note metadata still gets imported
                        state["current"] = i
            except Exception as e:
                # Last-resort catch-all, outside every specific handler above.
                # This runs in a background thread — an uncaught exception of
                # ANY kind kills the thread silently (Python's default thread
                # behavior) without ever reaching state["done"] = True, leaving
                # the progress bar polling forever against a dict that will
                # never say it's finished, with no error shown. The specific
                # handlers above still give a precise message for the cases
                # they know about; this only catches whatever isn't one of them.
                state["error"] = f"Import failed unexpectedly:\n{e}"
            state["done"] = True

        threading.Thread(target=worker, daemon=True).start()
        self._poll_import_progress()

    def _poll_import_progress(self):
        """Runs on the main thread only, on a timer — mirrors
        _poll_export_progress. Reads the plain dict the background import
        thread updates; once the slow I/O is done, hands off to the
        (fast, in-memory) duplicate-check dialog and the actual merge."""
        if not self._still_alive():
            return
        state = self._import_state
        if state is None:
            return
        if state["phase"] == "extracting":
            self.export_progress_lbl.config(text="Importing… reading backup")
        else:
            self.export_progress_bar.configure(maximum=state["total"], value=state["current"])
            self.export_progress_lbl.config(
                text=f"Importing… {state['current']} / {state['total']} attachments")

        if not state["done"]:
            self._export_poll_job = self.after(100, self._poll_import_progress)
            return

        self.export_progress_frame.place_forget()
        self._import_state = None
        temp_dir = state["temp_dir"]

        if state["error"]:
            self.show_error("Import failed", state["error"])
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
            return

        imported_notes = state["imported_notes"]
        # Merge notes in with new local IDs, so they never collide with
        # notes already on this device. Same duplicate check as "Import code":
        # a zip full of notes you already have used to get silently merged in
        # with no warning.
        valid_notes = [n for n in imported_notes if isinstance(n, dict)]
        existing_keys = {_dup_key(n) for n in self.notes}
        fresh = [n for n in valid_notes if _dup_key(normalize_note(n)) not in existing_keys]
        dupe_count = len(valid_notes) - len(fresh)
        to_import = valid_notes
        if dupe_count > 0:
            if fresh:
                choice = self._themed_dialog(
                    "Possible duplicates",
                    f"{dupe_count} of the {len(valid_notes)} note(s) in this backup "
                    "look identical to notes you already have (same title, text, "
                    "comments and category).",
                    kind="question",
                    buttons=[("Cancel", "cancel"),
                             ("Import all anyway", "all"),
                             (f"Skip the {dupe_count} duplicate(s)", "skip")]
                )
            else:
                choice = self._themed_dialog(
                    "All notes already imported",
                    f"All {len(valid_notes)} note(s) in this backup look identical "
                    "to notes you already have. Import them anyway as new copies?",
                    kind="question",
                    buttons=[("Cancel", "cancel"), ("Import anyway", "all")]
                )
            if choice is None or choice == "cancel":
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            if choice == "skip":
                to_import = fresh

        next_id = max([n["id"] for n in self.notes], default=0) + 1
        for note in to_import:
            note = normalize_note(note)
            note["id"] = next_id
            next_id += 1
            self.notes.append(note)

        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        shutil.rmtree(temp_dir, ignore_errors=True)

        skipped_note = f" ({dupe_count} duplicate(s) skipped)" if dupe_count and to_import is not valid_notes else ""
        self.show_info("Import complete", f"Added {len(to_import)} note(s) from the backup.{skipped_note}")

    # ---------- Theme helpers ----------
    def get_note_color(self, note):
        """A note's custom color if it has one, otherwise its category's default.
        Uses .get() throughout so a note with a missing/None category (from older
        or partial data) can't crash the list or calendar render."""
        color = note.get("color")
        if isinstance(color, str) and color:
            return color
        category = note.get("category")
        if not isinstance(category, str):
            category = "General"
        return CATEGORY_COLORS.get(category, self.colors["accent"])

    # ---------- Checklist ----------
    def toggle_checklist_section(self):
        """Show or hide the checklist section under the note body."""
        if self._checklist_open:
            self.checklist_section.pack_forget()
            self._checklist_open = False
            self.checklist_btn.config(text="☑ Checklist")
        else:
            # Pack right after the checklist button. No padx here — the
            # button and section both live inside a column Frame (see
            # build_notes_tab) that already carries the outer margin, now
            # that Checklist and Calculator sit side by side.
            self.checklist_section.pack(fill="x", pady=(0, 8),
                                        after=self.checklist_btn)
            self._checklist_open = True
            self.checklist_btn.config(text="☑ Checklist  ▲")
            self._render_checklist_items()

    def _build_checklist_section(self):
        """Build the (initially hidden) checklist UI: a scrollable list of items
        plus an entry to add new ones and Save/Close buttons."""
        sec = self.checklist_section
        # Header with progress + close.
        head = tk.Frame(sec, bg=self.colors["card"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        self.checklist_progress_lbl = tk.Label(
            head, text="Checklist", bg=self.colors["card"], fg=self.colors["subtext"],
            font=("Segoe UI", 9, "bold"), anchor="w")
        self.checklist_progress_lbl.pack(side="left")
        tk.Button(head, text="✕ Close", command=self.toggle_checklist_section,
                  relief="flat", cursor="hand2", bg=self.colors["card"],
                  fg=self.colors["subtext"], font=("Segoe UI", 8, "bold"), bd=0
                  ).pack(side="right")

        # Scrollable list of items.
        wrap = tk.Frame(sec, bg=self.colors["card"], height=160)
        wrap.pack(fill="x", padx=10, pady=(0, 4))
        wrap.pack_propagate(False)
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        self.checklist_items_frame = tk.Frame(canvas, bg=self.colors["card"])
        self.checklist_items_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=self.checklist_items_frame, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._checklist_canvas = canvas
        self._bind_wheel_tree(self.checklist_items_frame,
                              lambda e: self._panel_or_page_wheel(canvas, e))

        # Add-item row.
        add_row = tk.Frame(sec, bg=self.colors["card"])
        add_row.pack(fill="x", padx=10, pady=(2, 4))
        self.checklist_add_var = tk.StringVar()
        entry = tk.Entry(add_row, textvariable=self.checklist_add_var, relief="flat",
                         font=("Segoe UI", 10), bg=self.colors["sidebar"],
                         fg=self.colors["text"], insertbackground=self.colors["text"])
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.bind("<Return>", lambda e: self._add_checklist_item())
        self._add_paste_menu(entry)
        self.checklist_add_entry = entry
        tk.Button(add_row, text="＋ Add", command=self._add_checklist_item,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", padx=(6, 0), ipadx=8, ipady=2)

    def _get_checklist(self):
        """The working checklist for the note being edited, held in memory until
        the note is saved."""
        if not hasattr(self, "_working_checklist"):
            self._working_checklist = []
        return self._working_checklist

    def _render_checklist_items(self):
        """Redraw the checklist rows from the working list."""
        if not hasattr(self, "checklist_items_frame"):
            return
        for w in self.checklist_items_frame.winfo_children():
            w.destroy()
        items = self._get_checklist()
        if not items:
            tk.Label(self.checklist_items_frame, text="No items yet — add one below.",
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=4, pady=6)
        for idx, item in enumerate(items):
            self._build_checklist_row(idx, item)
        self._update_checklist_progress()

    def _build_checklist_row(self, idx, item):
        row = tk.Frame(self.checklist_items_frame, bg=self.colors["card"])
        row.pack(fill="x", pady=1)
        var = tk.IntVar(value=1 if item.get("done") else 0)

        def on_toggle():
            item["done"] = bool(var.get())
            self._update_checklist_progress()
            self._restyle_checklist_label(lbl, item["done"])
            self._schedule_autosave()

        cb = tk.Checkbutton(row, variable=var, command=on_toggle,
                            bg=self.colors["card"], activebackground=self.colors["card"],
                            selectcolor=self.colors["sidebar"], bd=0,
                            highlightthickness=0)
        cb.pack(side="left")

        lbl = tk.Label(row, text=item.get("text", ""), bg=self.colors["card"],
                       fg=self.colors["text"], font=("Segoe UI", 10), anchor="w",
                       justify="left", wraplength=380)
        lbl.pack(side="left", fill="x", expand=True, padx=(2, 4))
        self._restyle_checklist_label(lbl, item.get("done"))
        # Click the text to toggle too.
        lbl.bind("<Button-1>", lambda e: (var.set(0 if var.get() else 1), on_toggle()))

        def delete():
            try:
                self._get_checklist().remove(item)
            except ValueError:
                pass
            self._render_checklist_items()
            self._schedule_autosave()

        tk.Button(row, text="🗑", command=delete, relief="flat", cursor="hand2",
                  bg=self.colors["card"], fg=self.colors["danger"],
                  font=("Segoe UI", 9), bd=0).pack(side="right")

    def _restyle_checklist_label(self, lbl, done):
        """Dim + strike-through style for completed items (overstrike font)."""
        try:
            f = tkfont.Font(font=lbl.cget("font"))
            f.configure(overstrike=1 if done else 0)
            lbl.configure(font=f, fg=self.colors["subtext"] if done else self.colors["text"])
        except Exception:
            lbl.configure(fg=self.colors["subtext"] if done else self.colors["text"])

    def _add_checklist_item(self):
        text = self.checklist_add_var.get().strip()
        if not text:
            return
        self._get_checklist().append({"text": text, "done": False})
        self.checklist_add_var.set("")
        self._render_checklist_items()
        self._schedule_autosave()
        try:
            self.checklist_add_entry.focus_set()
        except tk.TclError:
            pass

    def _update_checklist_progress(self):
        if not hasattr(self, "checklist_progress_lbl"):
            return
        items = self._get_checklist()
        if not items:
            self.checklist_progress_lbl.config(text="Checklist")
            self.checklist_btn.config(
                text=("☑ Checklist  ▲" if self._checklist_open else "☑ Checklist"))
            return
        done = sum(1 for it in items if it.get("done"))
        self.checklist_progress_lbl.config(text=f"Checklist — {done}/{len(items)} done")
        # Reflect the count on the toggle button too, so it's visible when closed.
        badge = f"☑ Checklist ({done}/{len(items)})"
        self.checklist_btn.config(text=badge + ("  ▲" if self._checklist_open else ""))

    def _sync_checklist_open_state(self):
        """After loading a note, keep the checklist collapsed by default but
        refresh the button badge so the item count shows even when closed."""
        # Collapse on note switch to keep the editor tidy; the badge still shows
        # how many items exist.
        if getattr(self, "_checklist_open", False):
            self.checklist_section.pack_forget()
            self._checklist_open = False
        if hasattr(self, "checklist_btn"):
            self._update_checklist_progress()

    # ---------- In-note calculator ----------
    def toggle_calculator_section(self):
        """Show or hide the in-note calculator panel."""
        if self._calculator_open:
            self.calculator_section.pack_forget()
            self._calculator_open = False
            self.calculator_btn.config(text="🧮 Calculator")
        else:
            # No padx here — this and the button both live inside a column
            # Frame (see build_notes_tab) that already carries the outer
            # margin, now that Checklist and Calculator sit side by side.
            self.calculator_section.pack(fill="x", pady=(0, 8),
                                         after=self.calculator_btn)
            self._calculator_open = True
            self.calculator_btn.config(text="🧮 Calculator  ▲")
            # Ready to paste into immediately, no extra click needed.
            self.calculator_display.focus_set()

    def _build_calculator_section(self):
        """Build the (initially hidden) in-note calculator: an editable
        expression display (buttons, typing, or pasting all feed the same
        field) plus a compact keypad, an optional row of extra functions,
        and a collapsible history of this session's calculations. Purely
        a computation tool — nothing here is persisted on the note (no
        new note field, no share-code/export changes); it starts empty
        every time it's opened. Built once per editor (like the checklist
        section above), not rebuilt on every note switch."""
        sec = self.calculator_section
        head = tk.Frame(sec, bg=self.colors["card"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(head, text="Calculator", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(side="left")
        tk.Button(head, text="✕ Close", command=self.toggle_calculator_section,
                  relief="flat", cursor="hand2", bg=self.colors["card"],
                  fg=self.colors["subtext"], font=("Segoe UI", 8, "bold"), bd=0
                  ).pack(side="right")

        self._calc_display_var = tk.StringVar(value="")
        self._calc_just_evaluated = False
        self._calc_last_full_expr = ""
        self._calc_history = []

        self.calculator_display = tk.Entry(
            sec, textvariable=self._calc_display_var, relief="flat",
            font=("Consolas", 14), justify="right",
            bg=self.colors["sidebar"], fg=self.colors["text"],
            insertbackground=self.colors["text"])
        self.track_theme(self.calculator_display, bg="sidebar", fg="text",
                         insertbackground="text")
        self.calculator_display.pack(fill="x", padx=10, pady=(0, 4), ipady=8)
        # Right-click Cut/Copy/Paste, same as every other text field in the
        # app — plus a normal Ctrl+V/<<Paste>> binding below, so pasting an
        # expression copied from somewhere else just works either way.
        # (No Return-triggers-"=" binding: it would only fire reliably when
        # this exact field has keyboard focus, which isn't guaranteed after
        # a sequence of button clicks — the "=" button already covers this
        # without that fragility.)
        self._add_paste_menu(self.calculator_display)
        self.calculator_display.bind("<KeyRelease>", self._calc_on_direct_edit)
        self.calculator_display.bind("<<Paste>>", self._calc_on_direct_edit)

        grid = tk.Frame(sec, bg=self.colors["card"])
        grid.pack(fill="x", padx=10, pady=(0, 2))
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1)

        rows = [
            ["(", ")", "C", "⌫"],
            ["7", "8", "9", "÷"],
            ["4", "5", "6", "×"],
            ["1", "2", "3", "−"],
            ["0", ".", "=", "+"],
        ]
        for r, row in enumerate(rows):
            for c, label in enumerate(row):
                is_op = label in ("÷", "×", "−", "+", "=")
                btn = tk.Button(
                    grid, text=label, relief="flat", cursor="hand2",
                    font=("Segoe UI", 10, "bold"),
                    command=lambda t=label: self._calc_press(t))
                if is_op:
                    self.track_theme(btn, bg="accent")
                    btn.configure(fg="white")
                else:
                    self.track_theme(btn, bg="sidebar", fg="text")
                btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1, ipady=3)

        # --- Extra functions: extra bracket styles, √, a general power
        # operator '^' (e.g. "3^4" for 3 to the 4th, not just a fixed
        # square), and % — collapsed by default so the everyday keypad
        # above stays the main focus. ---
        self._calc_more_open = False
        self.calculator_more_btn = tk.Button(
            sec, text="More functions  ▾", command=self._toggle_calc_more,
            relief="flat", cursor="hand2", font=("Segoe UI", 8, "bold"))
        self.track_theme(self.calculator_more_btn, bg="card", fg="subtext")
        self.calculator_more_btn.pack(fill="x", padx=10, pady=(0, 2))

        self.calculator_more_frame = tk.Frame(sec, bg=self.colors["card"])
        self.track_theme(self.calculator_more_frame, bg="card")
        # Not packed yet — toggled open by the button above.
        for col in range(4):
            self.calculator_more_frame.grid_columnconfigure(col, weight=1)
        more_rows = [["√", "^", "%", "{"], ["}", "[", "]", ""]]
        for r, row in enumerate(more_rows):
            for c, label in enumerate(row):
                if not label:
                    continue
                btn = tk.Button(
                    self.calculator_more_frame, text=label, relief="flat",
                    cursor="hand2", font=("Segoe UI", 10, "bold"),
                    command=lambda t=label: self._calc_press(t))
                self.track_theme(btn, bg="sidebar", fg="text")
                btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1, ipady=3)

        self.calculator_insert_btn = tk.Button(
            sec, text="⬇ Insert into note", command=self._calc_insert_into_note,
            relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
            state="disabled", disabledforeground=self.colors["subtext"])
        self.track_theme(self.calculator_insert_btn, bg="sidebar", fg="text")
        self.calculator_insert_btn.pack(fill="x", padx=10, pady=(2, 8), ipady=4)

        # --- History: this session's past calculations, newest first.
        # Collapsed by default, like the extra-functions row — a toggle
        # button reveals it rather than it always taking up space. Not
        # persisted anywhere — clears with the rest of the calculator on
        # note switch, same as the expression itself. Each entry is
        # clickable to insert that specific formula into the note (the
        # same "own line, right after the last insertion" placement the
        # main Insert button uses), so an earlier result is still one
        # click away without having to recompute it. ---
        self._calc_history_open = False
        self.calculator_history_head = hist_head = tk.Frame(sec, bg=self.colors["card"])
        hist_head.pack(fill="x", padx=10, pady=(0, 0))
        self.calculator_history_btn = tk.Button(
            hist_head, text="History  ▾", command=self._toggle_calc_history,
            relief="flat", cursor="hand2", font=("Segoe UI", 8, "bold"),
            bg=self.colors["card"], fg=self.colors["subtext"], bd=0, anchor="w")
        self.track_theme(self.calculator_history_btn, bg="card", fg="subtext")
        self.calculator_history_btn.pack(side="left")
        self.calculator_history_clear_btn = tk.Button(
            hist_head, text="Clear", command=self._calc_clear_history,
            relief="flat", cursor="hand2", font=("Segoe UI", 8), bd=0)
        self.track_theme(self.calculator_history_clear_btn, bg="card", fg="subtext")
        self.calculator_history_clear_btn.pack(side="right")

        self.calculator_history_section = tk.Frame(sec, bg=self.colors["card"])
        self.track_theme(self.calculator_history_section, bg="card")
        # Not packed yet — toggled open by the button above.
        hist_wrap = tk.Frame(self.calculator_history_section, bg=self.colors["card"], height=90)
        hist_wrap.pack(fill="x", pady=(2, 8))
        hist_wrap.pack_propagate(False)
        hist_canvas = tk.Canvas(hist_wrap, bg=self.colors["card"], highlightthickness=0)
        hist_sb = ttk.Scrollbar(hist_wrap, orient="vertical", command=hist_canvas.yview)
        self.calculator_history_frame = tk.Frame(hist_canvas, bg=self.colors["card"])
        self.calculator_history_frame.bind(
            "<Configure>", lambda e: hist_canvas.configure(scrollregion=hist_canvas.bbox("all")))
        hist_cwin = hist_canvas.create_window((0, 0), window=self.calculator_history_frame, anchor="nw")
        hist_canvas.bind("<Configure>", self._canvas_width_sync(hist_canvas, hist_cwin))
        hist_canvas.configure(yscrollcommand=hist_sb.set)
        hist_sb.pack(side="right", fill="y")
        hist_canvas.pack(side="left", fill="both", expand=True)
        self._bind_wheel_tree(self.calculator_history_frame,
                              lambda e: self._panel_or_page_wheel(hist_canvas, e))
        self._calc_render_history()

    def _toggle_calc_more(self):
        """Show or hide the extra-functions row (brackets, √, ^, %)."""
        if self._calc_more_open:
            self.calculator_more_frame.pack_forget()
            self._calc_more_open = False
            self.calculator_more_btn.config(text="More functions  ▾")
        else:
            self.calculator_more_frame.pack(fill="x", padx=10, pady=(0, 4),
                                            after=self.calculator_more_btn)
            self._calc_more_open = True
            self.calculator_more_btn.config(text="More functions  ▴")

    def _toggle_calc_history(self):
        """Show or hide the calculation history — collapsed by default so
        it doesn't take up space until actually wanted."""
        if self._calc_history_open:
            self.calculator_history_section.pack_forget()
            self._calc_history_open = False
            self.calculator_history_btn.config(text="History  ▾")
        else:
            self.calculator_history_section.pack(
                fill="x", padx=10, after=self.calculator_history_head)
            self._calc_history_open = True
            self.calculator_history_btn.config(text="History  ▲")

    def _calc_clear_history(self):
        """Wipe this session's calculation history — the current
        expression/result on display is untouched, only the log below it."""
        self._calc_history = []
        self._calc_render_history()

    def _calc_on_direct_edit(self, event=None):
        """Fired when the user types or pastes directly into the display
        instead of using the buttons. Treated like any manual text edit:
        no auto-clearing, and Insert stays unavailable until a fresh "="
        produces a real result from whatever's now in the field."""
        self._calc_just_evaluated = False
        self._calc_refresh_insert_state()

    def _calc_press(self, token):
        """Handle one calculator button press. Reads and writes the same
        editable display field a user could also type or paste into
        directly — see evaluate_calculator_expression() for the actual
        math."""
        current = self._calc_display_var.get()
        if token == "C":
            current = ""
            self._calc_just_evaluated = False
        elif token == "⌫":
            current = "" if self._calc_just_evaluated else current[:-1]
            self._calc_just_evaluated = False
        elif token == "=":
            if current and current != "Error":
                result = evaluate_calculator_expression(current)
                if result is not None:
                    formatted = format_calculator_result(result)
                    self._calc_last_full_expr = current
                    self._calc_history.insert(0, f"{current}={formatted}")
                    self._calc_render_history()
                    current = formatted
                    self._calc_just_evaluated = True
                else:
                    current = "Error"
                    self._calc_just_evaluated = False
        elif token in ("+", "−", "×", "÷", "^", "%"):
            # Binary (+−×÷^) and postfix (%) operators all continue
            # chaining off a just-computed result instead of clearing it.
            if current == "Error":
                current = ""
            self._calc_just_evaluated = False
            current += token
        else:  # a digit, ".", "√", or a bracket — starts a fresh entry
            if self._calc_just_evaluated or current == "Error":
                current = ""
                self._calc_just_evaluated = False
            current += token
        self._calc_display_var.set(current)
        # Button presses set the StringVar programmatically, which doesn't
        # move the Entry's own cursor the way normal typing would — without
        # this, the cursor can end up stuck mid-text instead of following
        # what was just "typed" via the button.
        self.calculator_display.icursor(tk.END)
        self._calc_refresh_insert_state()

    def _calc_refresh_insert_state(self):
        """Insert-into-note is only ever active right after '=' produced
        a real result — never for an in-progress expression or an error,
        so there's nothing meaningful to insert until then."""
        if not hasattr(self, "calculator_insert_btn"):
            return
        current = self._calc_display_var.get()
        enabled = self._calc_just_evaluated and bool(current) and current != "Error"
        self.calculator_insert_btn.config(state=("normal" if enabled else "disabled"))

    def _calc_render_history(self):
        if not hasattr(self, "calculator_history_frame"):
            return
        for w in self.calculator_history_frame.winfo_children():
            w.destroy()
        if not self._calc_history:
            tk.Label(self.calculator_history_frame, text="No calculations yet.",
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=6, pady=4)
            return
        for entry in self._calc_history:
            lbl = tk.Label(self.calculator_history_frame, text=entry,
                           bg=self.colors["card"], fg=self.colors["subtext"],
                           font=("Consolas", 9), anchor="e", justify="right",
                           cursor="hand2")
            lbl.pack(fill="x", padx=6, pady=2)
            lbl.bind("<Button-1>", lambda e, formula=entry: self._calc_insert_formula(formula))

    def _calc_insert_formula(self, formula):
        """Shared insertion logic: type `formula` into the note body,
        landing on a fresh line right after the previous calculator
        insertion (tracked via a Text mark), so repeated use — whether
        from the main Insert button or clicking a history entry — builds
        a clean log downward instead of gluing results onto wherever the
        cursor happens to be sitting."""
        has_prior = "calc_insert_end" in self.body_text.mark_names()
        if self.focus_get() is not self.body_text:
            self.body_text.focus_set()
        if has_prior:
            self.body_text.mark_set(tk.INSERT, "calc_insert_end")
            self.body_text.insert(tk.INSERT, "\n" + formula)
        else:
            self.body_text.insert(tk.INSERT, formula)
        self.body_text.mark_set("calc_insert_end", tk.INSERT)
        self._schedule_autosave(skip_word_count=True)

    def _calc_insert_into_note(self):
        """Insert the full formula just computed ("expr=result") into the
        note body — only reachable right after a successful "=" (the
        button is disabled otherwise)."""
        if not self._calc_just_evaluated:
            return
        result = self._calc_display_var.get()
        if not result or result == "Error" or not self._calc_last_full_expr:
            return
        self._calc_insert_formula(f"{self._calc_last_full_expr}={result}")

    def _sync_calculator_open_state(self):
        """Collapse and fully reset the calculator on note switch — it's a
        transient tool, not part of any note's saved content, so carrying
        a half-finished sum, history, or insertion point over from a
        previous note would be confusing rather than useful."""
        if getattr(self, "_calculator_open", False):
            self.calculator_section.pack_forget()
            self._calculator_open = False
        if getattr(self, "_calc_more_open", False):
            self.calculator_more_frame.pack_forget()
            self._calc_more_open = False
            if hasattr(self, "calculator_more_btn"):
                self.calculator_more_btn.config(text="More functions  ▾")
        if getattr(self, "_calc_history_open", False):
            self.calculator_history_section.pack_forget()
            self._calc_history_open = False
            if hasattr(self, "calculator_history_btn"):
                self.calculator_history_btn.config(text="History  ▾")
        if hasattr(self, "_calc_display_var"):
            self._calc_display_var.set("")
        self._calc_just_evaluated = False
        self._calc_last_full_expr = ""
        self._calc_history = []
        self._calc_render_history()
        if hasattr(self, "calculator_btn"):
            self.calculator_btn.config(text="🧮 Calculator")
        self._calc_refresh_insert_state()
        if "calc_insert_end" in self.body_text.mark_names():
            self.body_text.mark_unset("calc_insert_end")

    def update_word_count(self):
        """Refresh the words · characters readout for the note body."""
        if not hasattr(self, "word_count_lbl"):
            return
        text = self.body_text.get("1.0", "end-1c")
        chars = len(text)
        words = len(text.split())
        if chars == 0:
            self.word_count_lbl.config(text="")
        else:
            w = "word" if words == 1 else "words"
            c = "character" if chars == 1 else "characters"
            self.word_count_lbl.config(text=f"{words} {w} · {chars} {c}")

    def _reset_editor_scroll(self):
        """Called after loading a note into the editor: snap back to the top and
        recompute whether scrolling is even needed, so switching from a long
        note to a short one never leaves the short one scrolled down."""
        if hasattr(self, "_sync_editor_scroll"):
            self.editor_canvas.yview_moveto(0)
            self.after_idle(self._sync_editor_scroll)

    def _canvas_width_sync(self, canvas, item):
        """Return a <Configure> handler that resizes the canvas's inner window to
        the canvas width, but ONLY when the width actually changed. During a
        vertical resize the width stays the same, so this avoids relaying-out all
        the rows on every height change — which was causing the drag flicker."""
        last = {"w": -1}

        def handler(event):
            if event.width != last["w"]:
                last["w"] = event.width
                try:
                    canvas.itemconfig(item, width=event.width)
                except tk.TclError:
                    pass
        return handler

    def _add_text_resize_toggle(self, host, text_widget, compact, expanded,
                                pack_kwargs=None):
        """Add an Expand/Collapse toggle under a Text box. One click switches its
        height (in rows) between compact and expanded — same flicker-free pattern
        as the Settings panels, no dragging. Also disables the box's expand fill
        so the height setting actually takes effect. Not persisted."""
        # Make height changes visible: stop the box from expanding to fill all
        # available space, so the row count controls its size.
        try:
            text_widget.pack_configure(expand=False)
        except tk.TclError:
            pass
        text_widget.configure(height=compact)

        state = {"expanded": False}
        btn = tk.Button(host, relief="flat", font=("Segoe UI", 8, "bold"),
                        cursor="hand2", bd=0)
        self.track_theme(btn, bg="bg", fg="subtext",
                         activebackground="bg", activeforeground="text")

        def apply():
            try:
                text_widget.configure(height=expanded if state["expanded"] else compact)
            except tk.TclError:
                pass
            btn.configure(text=("Restrânge ⌃" if state["expanded"] else "Extinde ⌄"))

        def toggle():
            state["expanded"] = not state["expanded"]
            apply()

        btn.configure(command=toggle)
        apply()
        pk = pack_kwargs or {}
        btn.pack(fill="x", **pk)
        return btn

    def _add_resize_handle(self, target, min_h=80, max_h=1000, host=None):
        """Add an Expand/Collapse toggle below `target`. One click switches the
        panel between its compact height (the default) and an expanded height —
        no dragging, so it's flicker-free and dead simple. `target` must have a
        fixed height with pack_propagate(False). Height not persisted."""
        host = host or target.master
        try:
            compact_h = int(target.cget("height"))
        except tk.TclError:
            compact_h = min_h
        expanded_h = min(max_h, max(compact_h + 260, compact_h * 2))
        state = {"expanded": False}

        btn = tk.Button(host, relief="flat", font=("Segoe UI", 8, "bold"),
                        cursor="hand2", bd=0)
        self.track_theme(btn, bg="sidebar", fg="subtext",
                         activebackground="sidebar", activeforeground="text")

        def apply():
            h = expanded_h if state["expanded"] else compact_h
            try:
                target.configure(height=h)
            except tk.TclError:
                pass
            btn.configure(text=("Restrânge ⌃" if state["expanded"] else "Extinde ⌄"))

        def toggle():
            state["expanded"] = not state["expanded"]
            apply()

        btn.configure(command=toggle)
        apply()
        return btn

    def toggle_settings_panel(self, which):
        """Accordion for Settings: open the requested inline panel and close any
        other. Panels replace the old pop-up dialogs for categories, trash
        and duplicates."""
        panels = {
            "templates": (getattr(self, "settings_templates_panel", None),
                          self._build_settings_templates_panel),
            "categories": (getattr(self, "settings_categories_panel", None),
                           self._build_settings_categories_panel),
            "trash": (getattr(self, "settings_trash_panel", None),
                      self._build_settings_trash_panel),
            "duplicates": (getattr(self, "settings_duplicates_panel", None),
                           self._build_settings_duplicates_panel),
        }
        target, builder = panels.get(which, (None, None))
        if target is None:
            return
        already_open = target.winfo_ismapped()
        # Close every panel first.
        for panel, _ in panels.values():
            if panel is not None and panel.winfo_ismapped():
                panel.pack_forget()
        if already_open:
            return  # it was open → now closed, done (toggle behavior)
        # Build fresh content and show it.
        for w in target.winfo_children():
            w.destroy()
        self._active_panel_canvas = None  # builder sets this if it has a scroll list
        self._resize_handles_pending = []
        builder(target)
        # Create any resize handles the builder requested, now that the canvas
        # exists — the handle overlays the target's bottom edge and is lifted on
        # top so it stays visible and doesn't repack siblings while dragging.
        for tgt, mn, mx in getattr(self, "_resize_handles_pending", []):
            h = self._add_resize_handle(tgt, min_h=mn, max_h=mx, host=target)
            h.pack(fill="x", padx=12, pady=(2, 8))
        self._resize_handles_pending = []
        target.pack(fill="x", padx=16, pady=(0, 12))
        # One wheel rule for the whole panel: if the panel has an inner scroll
        # list with overflow, scroll it; otherwise scroll the Settings page.
        # This works no matter where the cursor is over the panel.
        inner_canvas = getattr(self, "_active_panel_canvas", None)
        self._bind_wheel_tree(target, lambda e: self._panel_or_page_wheel(inner_canvas, e))

    def _panel_or_page_wheel(self, panel_canvas, event):
        """If the panel's list can scroll, scroll it; else scroll the whole
        Settings page. Used for every widget in an inline settings panel."""
        if panel_canvas is not None:
            try:
                first, last = panel_canvas.yview()
                # Small tolerance instead of exact 0.0/1.0: yview() can come
                # back as e.g. 0.0/0.997 rather than a clean 0.0/1.0 depending
                # on how the platform rounds the scroll fraction, which would
                # make an already-fully-visible panel (like an empty trash
                # list) look like it still has more to scroll — trapping the
                # wheel on a tiny, already-fully-shown panel instead of
                # falling through to the page underneath it.
                if not (first <= 0.001 and last >= 0.999):
                    panel_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return "break"
            except (tk.TclError, ValueError):
                pass
        page_canvas = getattr(self, "settings_canvas", None)
        if page_canvas is not None:
            try:
                page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
        return "break"

    def _bind_wheel_tree_if_unbound(self, root, handler):
        """Bind a wheel handler to a widget subtree, but skip widgets that
        already have a MouseWheel binding (their own scroll list keeps priority)."""
        if not root.bind("<MouseWheel>"):
            root.bind("<MouseWheel>", handler)
        for child in root.winfo_children():
            self._bind_wheel_tree_if_unbound(child, handler)

    def _settings_panel_header(self, parent, title, subtitle, which):
        """Common header for an inline settings panel: title + close ✕."""
        head = tk.Frame(parent, bg=self.colors["card"])
        head.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(head, text=title, font=("Segoe UI", 12, "bold"),
                 bg=self.colors["card"], fg=self.colors["text"]).pack(side="left")
        tk.Button(head, text="✕", command=lambda: self.toggle_settings_panel(which),
                  bg=self.colors["card"], fg=self.colors["subtext"], relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2").pack(side="right")
        if subtitle:
            tk.Label(parent, text=subtitle, font=("Segoe UI", 8),
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     justify="left", wraplength=520, anchor="w"
                     ).pack(fill="x", padx=12, pady=(0, 8))

    def _show_inline_rename(self, anchor_widget, current, on_save):
        """Small inline rename box near `anchor_widget`: an entry pre-filled with
        `current`, a Save and an ✕. on_save(new_text) returns True to close or
        False to keep it open. No grab_set() — that can freeze the app."""
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        frame.pack(padx=1, pady=1)

        var = tk.StringVar(value=current)
        entry = tk.Entry(frame, textvariable=var, relief="flat", font=("Segoe UI", 10),
                         bg=self.colors["sidebar"], fg=self.colors["text"],
                         insertbackground=self.colors["text"], width=18)
        entry.pack(side="left", ipady=3, padx=(0, 6))
        entry.select_range(0, "end")
        self._add_paste_menu(entry)

        def save():
            if on_save(var.get()):
                self._dismiss_mini_popup()

        tk.Button(frame, text="Save", command=save, relief="flat", cursor="hand2",
                  bg=self.colors["accent"], fg="white", font=("Segoe UI", 8, "bold")
                  ).pack(side="left", ipadx=6, ipady=2, padx=(0, 3))
        tk.Button(frame, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 8, "bold")).pack(side="left", ipadx=4, ipady=2)

        entry.bind("<Return>", lambda e: save())
        entry.bind("<Escape>", lambda e: self._dismiss_mini_popup())

        self._place_mini_popup(pop, anchor_widget)
        # Focus the entry after placing (safe now — no grab).
        entry.focus_set()
        return pop

    def _show_color_palette(self, anchor_widget, current, on_pick, allow_reset=True,
                            anchor_xy=None, reset_label="Default (theme color)"):
        """Show a small inline color palette near `anchor_widget` (or at
        `anchor_xy` root coordinates, for callers with no persistent widget to
        anchor to — e.g. a calendar day reached via right-click). Clicking a
        swatch calls on_pick(hex) and closes. An ✕ closes without changing.
        Deliberately does NOT use grab_set() — a grabbed borderless window can
        fail to get focus on Windows and freeze the whole app."""
        # Only one of these open at a time.
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        frame.pack(padx=1, pady=1)

        # Header with a close ✕.
        head = tk.Frame(frame, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 4))
        tk.Label(head, text="Pick a color", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")

        def pick(color):
            self._dismiss_mini_popup()
            on_pick(color)

        grid = tk.Frame(frame, bg=self.colors["card"])
        grid.pack()
        per_row = 5
        for i, color in enumerate(PALETTE_COLORS):
            r, c = divmod(i, per_row)
            cell = tk.Canvas(grid, width=26, height=26, highlightthickness=0,
                             bg=self.colors["card"], cursor="hand2")
            self._rounded_rect(cell, 2, 2, 24, 24, 7, fill=color, outline=color)
            if color == current:
                cell.create_text(13, 13, text="✓", fill="white",
                                 font=("Segoe UI", 11, "bold"))
            cell.grid(row=r, column=c, padx=3, pady=3)
            cell.bind("<Button-1>", lambda e, col=color: pick(col))

        if allow_reset:
            tk.Button(frame, text=reset_label,
                      command=lambda: pick(""), relief="flat", cursor="hand2",
                      bg=self.colors["sidebar"], fg=self.colors["text"],
                      font=("Segoe UI", 8)).pack(fill="x", pady=(6, 0), ipady=2)

        self._place_mini_popup(pop, anchor_widget, anchor_xy=anchor_xy)
        return pop

    # ---------- Themed dialogs (replace OS messagebox) ----------
    def _themed_dialog(self, title, message, kind="info", buttons=None):
        """A modal, in-theme replacement for tkinter's messagebox. Renders as an
        overlay INSIDE the app window (not a separate OS window), so it can't be
        dragged off-screen and moves/minimizes with the app. Blocks until the
        user picks a button, then returns that button's value."""
        if buttons is None:
            buttons = [("OK", True)]

        icon = {"info": "ℹ️", "warning": "⚠️", "error": "⛔",
                "question": "❓", "success": "✅"}.get(kind, "ℹ️")
        accent = {"error": self.colors["danger"], "warning": self.colors["danger"],
                  "success": self.colors["success"]}.get(kind, self.colors["accent"])

        result = {"value": None}
        done = tk.IntVar(value=0)

        # A thin transparent-ish "click catcher" that keeps the background
        # VISIBLE but swallows clicks/keys so the app underneath can't be used
        # while the dialog is open. It's a 1x1-anchored full-size frame drawn
        # only where the card isn't — but since tk frames are opaque, we instead
        # place the card directly and block interaction via an event grab on a
        # tiny transparent overlay strip. Simpler and flicker-free: place the
        # card over the window (background stays visible) and intercept clicks
        # through a global binding while the dialog is up.
        border = tk.Frame(self, bg=accent, highlightthickness=0)
        border.place(relx=0.5, rely=0.42, anchor="center")
        card = tk.Frame(border, bg=self.colors["card"])
        card.pack(padx=2, pady=2)

        head = tk.Frame(card, bg=self.colors["card"])
        head.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(head, text=f"{icon}  {title}", bg=self.colors["card"],
                 fg=self.colors["text"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(side="left")

        tk.Label(card, text=message, bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 10), wraplength=380, justify="left", anchor="w"
                 ).pack(fill="x", padx=20, pady=(0, 16))

        btn_row = tk.Frame(card, bg=self.colors["card"])
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        def choose(val):
            result["value"] = val
            done.set(1)

        for i, spec in enumerate(buttons):
            label, value = spec[0], spec[1]
            color_key = spec[2] if len(spec) > 2 else None
            is_primary = (i == len(buttons) - 1)
            if color_key:
                btn_color = self.colors.get(color_key, self.colors["sidebar"])
                fg_color = "white"
            else:
                btn_color = accent if is_primary else self.colors["sidebar"]
                fg_color = "white" if is_primary else self.colors["text"]
            b = tk.Button(
                btn_row, text=label, command=lambda v=value: choose(v),
                relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
                bg=btn_color, fg=fg_color,
                activebackground=btn_color, activeforeground=fg_color)
            b.pack(side="right", padx=(8, 0), ipadx=12, ipady=4)
            if is_primary:
                b.focus_set()

        # Escape = the "safe" (first) value, usually cancel/no.
        safe_val = buttons[0][1] if len(buttons) > 1 else buttons[-1][1]
        esc_bind = self.bind("<Escape>", lambda e: choose(safe_val), add="+")

        # Modal, but the background stays fully visible (we don't cover it). A
        # local grab on the dialog frame routes input to the dialog only; because
        # this is an ordinary in-window Frame (not a borderless Toplevel), the
        # grab is safe and won't freeze the app.
        self.update_idletasks()
        try:
            border.grab_set()
        except tk.TclError:
            pass
        try:
            self.wait_variable(done)
        finally:
            try:
                border.grab_release()
            except tk.TclError:
                pass
            try:
                self.unbind("<Escape>", esc_bind)
            except tk.TclError:
                pass
            try:
                border.destroy()
            except tk.TclError:
                pass
        return result["value"]

    def show_info(self, title, message, **kw):
        return self._themed_dialog(title, message, kind=kw.get("kind", "info"),
                                   buttons=[("OK", True)])

    def show_warning(self, title, message, **kw):
        return self._themed_dialog(title, message, kind="warning",
                                   buttons=[("OK", True)])

    def show_error(self, title, message, **kw):
        return self._themed_dialog(title, message, kind="error",
                                   buttons=[("OK", True)])

    def ask_yes_no(self, title, message, **kw):
        return self._themed_dialog(title, message, kind=kw.get("kind", "question"),
                                   buttons=[("No", False), ("Yes", True)])

    def ask_yes_no_cancel(self, title, message, **kw):
        # Returns True (yes), False (no), or None (cancel) — matches messagebox.
        return self._themed_dialog(title, message, kind=kw.get("kind", "question"),
                                   buttons=[("Cancel", None), ("No", False), ("Yes", True)])

    def _render_statistics(self):
        """Compute and draw a compact, read-only snapshot: total notes; a
        week/month/year/older breakdown of when notes were added and last
        updated; standalone counts of templates, notes with a checklist,
        and notes currently in Trash; the date this install was first
        used; and per-category counts as plain lines (no box, not
        clickable — this is a snapshot, not another way to filter notes).
        Recomputed on every note-list refresh (not just when the Settings
        tab is opened), so category renames/deletes, new notes, and any
        other change stay reflected live while Settings happens to be
        open — not just after leaving and coming back. Deliberately does
        NOT gate on the Settings page's winfo_ismapped() state — that
        looked like the right optimization (skip the work when Settings
        isn't visible), but pack()/pack_forget() don't always update
        ismapped() synchronously, so that check could skip a real update
        and leave stale data on screen. Redrawing every time is cheap
        (this panel is at most a couple dozen small widgets) compared to
        the note-card rebuild refresh_note_list() already does around it,
        so there's no real cost to just always doing it. Every field is
        read defensively — a note with a missing/odd timestamp or
        category just gets skipped from that specific count instead of
        crashing the whole panel."""
        if not hasattr(self, "stats_frame"):
            return
        for w in self.stats_frame.winfo_children():
            w.destroy()

        notes = self.notes
        total = len(notes)

        def _parse_ts(raw):
            if not isinstance(raw, str) or not raw:
                return None
            try:
                return datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
            except ValueError:
                return None

        today = date_cls.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        def _bucket_counts(field):
            # Cumulative from the start of each period (so "this year"
            # already includes "this month"); "older" is the one true
            # complement — notes not touched at all since Jan 1st.
            week = month = year = older = 0
            for n in notes:
                ts = _parse_ts(n.get(field))
                if not ts:
                    continue
                d = ts.date()
                if d >= week_start:
                    week += 1
                if d >= month_start:
                    month += 1
                if d >= year_start:
                    year += 1
                else:
                    older += 1
            return week, month, year, older

        added_week, added_month, added_year, added_older = _bucket_counts("created")
        updated_week, updated_month, updated_year, updated_older = _bucket_counts("updated")

        # --- Summary: total, then a week/month/year/older breakdown for
        # both when notes were added and last updated. Built as a grid —
        # icon, then "Added:"/"Updated:", then each of week/month/year/
        # older in its own column — rather than one big string per row.
        # The icon gets its own column specifically because 🆕 and ✏️
        # aren't the same rendered width, so if the icon and label shared
        # a column, "Added:" and "Updated:" themselves would start at
        # different x positions even though the column as a whole lined
        # up. Splitting it out means every column — icon, label, and each
        # week/month/year/older segment — lines up independently between
        # the two rows, regardless of font/DPI. ---
        tk.Label(
            self.stats_frame, text=f"{total} notes",
            font=("Segoe UI", 9, "bold"), bg=self.colors["card"],
            fg=self.colors["text"], anchor="w"
        ).pack(fill="x", pady=(0, 4))

        breakdown = tk.Frame(self.stats_frame, bg=self.colors["card"])
        breakdown.pack(fill="x", pady=(0, 10))
        stat_font = tkfont.Font(family="Segoe UI", size=9)
        rows_data = [
            ("🆕", "Added:", added_week, added_month, added_year, added_older),
            ("✏️", "Updated:", updated_week, updated_month, updated_year, updated_older),
        ]
        icon_width = max(stat_font.measure(rows_data[0][0]),
                          stat_font.measure(rows_data[1][0])) + 6
        breakdown.grid_columnconfigure(0, minsize=icon_width)
        label_width = max(stat_font.measure(rows_data[0][1]),
                           stat_font.measure(rows_data[1][1])) + 10
        breakdown.grid_columnconfigure(1, minsize=label_width)

        segment_labels = ["this week", "this month", "this year", "older"]
        for seg_idx, seg_label in enumerate(segment_labels):
            col = seg_idx + 2
            texts = [f"{rows_data[0][seg_idx + 2]} {seg_label}",
                     f"{rows_data[1][seg_idx + 2]} {seg_label}"]
            col_width = max(stat_font.measure(t) for t in texts) + 16
            breakdown.grid_columnconfigure(col, minsize=col_width)

        for r, (icon, label_text, week, month, year, older) in enumerate(rows_data):
            tk.Label(breakdown, text=icon, font=("Segoe UI", 9),
                     bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                     ).grid(row=r, column=0, sticky="w")
            tk.Label(breakdown, text=label_text, font=("Segoe UI", 9),
                     bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                     ).grid(row=r, column=1, sticky="w")
            for seg_idx, (value, seg_label) in enumerate(
                    zip((week, month, year, older), segment_labels)):
                tk.Label(breakdown, text=f"{value} {seg_label}",
                         font=("Segoe UI", 9), bg=self.colors["card"],
                         fg=self.colors["text"], anchor="w"
                         ).grid(row=r, column=seg_idx + 2, sticky="w")

        # --- A few standalone counts: templates and checklists are their
        # own things (a template can be reused across many notes; a
        # checklist only ever lives inside the one note it's on), so these
        # count the things themselves, not how many notes reference them.
        # "Deleted" counts what's currently in Trash right now, not an
        # all-time total — it goes back down after Trash is emptied or
        # auto-purges, same as Trash's own count would show. ---
        templates_count = len(self.templates)
        checklists_count = sum(1 for n in notes if n.get("checklist"))
        deleted_count = len(self.trash)
        tk.Label(
            self.stats_frame,
            text=f"🧩 {templates_count} templates   ·   "
                 f"☑ {checklists_count} notes with checklists   ·   "
                 f"🗑 {deleted_count} deleted",
            font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["text"],
            anchor="w"
        ).pack(fill="x")
        tk.Label(
            self.stats_frame, text=f"📅 Using Note Organizer since {FIRST_LAUNCH_DATE}",
            font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["text"],
            anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Per-category counts: known categories first (Manage-categories order),
        # then any leftover/stale category names so nothing is silently dropped.
        counts = {}
        for n in notes:
            cat = n.get("category") if isinstance(n.get("category"), str) else None
            cat = cat or "General"
            counts[cat] = counts.get(cat, 0) + 1
        ordered_cats = [c for c in CATEGORY_COLORS.keys() if c in counts]
        ordered_cats += [c for c in counts.keys() if c not in ordered_cats]

        if not ordered_cats:
            tk.Label(self.stats_frame, text="No notes yet.", font=("Segoe UI", 9),
                     bg=self.colors["card"], fg=self.colors["subtext"]
                     ).pack(anchor="w")
            return

        # --- Per-category counts: plain text, no box — a colored dot plus
        # "Category (count)". Deliberately not clickable; this is just a
        # snapshot, not another way to filter notes. Wraps into rows of 4. ---
        grid = tk.Frame(self.stats_frame, bg=self.colors["card"])
        grid.pack(fill="x")
        cols = 4
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1, uniform="statchip")

        for idx, cat in enumerate(ordered_cats):
            n = counts[cat]
            color = CATEGORY_COLORS.get(cat, self.colors["accent"])
            r, c = divmod(idx, cols)
            row = tk.Frame(grid, bg=self.colors["card"])
            row.grid(row=r, column=c, sticky="ew", padx=3, pady=3)
            tk.Label(row, text="●", font=("Segoe UI", 9), fg=color,
                     bg=self.colors["card"]).pack(side="left", padx=(0, 4))
            tk.Label(row, text=f"{cat} ({n})", font=("Segoe UI", 8),
                     bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                     ).pack(side="left", fill="x", expand=True)

        # Same wheel-forwarding pattern used elsewhere in Settings (theme
        # picker, inline panels) — without it, scrolling with the cursor
        # over the summary text or a category chip does nothing, since
        # those widgets have no scroll behavior of their own to fall back
        # to. Rebound every time this panel rebuilds (it's redrawn on every
        # Settings-page open, to stay fresh).
        def _stats_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        self._bind_wheel_tree(self.stats_frame, _stats_wheel)

    def _refresh_category_button(self):
        """Update the category button's colour dot + label to the current pick."""
        if not hasattr(self, "_cat_dot"):
            return
        cat = self.category_var.get()
        color = CATEGORY_COLORS.get(cat, self.colors["accent"])
        try:
            self._cat_dot.configure(bg=self.colors["sidebar"], fg=color)
        except tk.TclError:
            pass

    def _build_themed_dropdown(self, parent, var, options, on_change,
                               dot_color_fn=None, width_chars=14, nested=False):
        """Build a small themed dropdown button (replaces ttk.Combobox for
        simple single-choice selectors like sort/filter). Returns the button
        Frame; pack it into the caller's layout. `dot_color_fn(value)` — if
        given — returns a hex color to show a bullet next to each option (used
        for the category filter); return None/falsy to skip the bullet for
        that option (e.g. "All").

        `nested=True` — use when this dropdown lives INSIDE another popup
        (e.g. the category picker inside the template editor). The default
        path calls self._dismiss_mini_popup() to close whatever popup was
        open before opening a new, unrelated one — but a dropdown nested
        inside another popup IS that popup's content, not something separate
        to replace; calling the shared dismiss would destroy the very editor
        this dropdown is sitting inside, before its own list even opens.
        Nested mode tracks its own small popup instead, leaving whatever the
        app's main self._mini_popup is completely alone."""
        btn = tk.Frame(parent, bg=self.colors["sidebar"],
                      highlightthickness=1, highlightbackground=self.colors["card"])
        lbl = tk.Label(btn, textvariable=var, bg=self.colors["sidebar"],
                      fg=self.colors["text"], font=("Segoe UI", 8),
                      anchor="w", width=width_chars)
        lbl.pack(side="left", padx=(8, 2), pady=4)
        caret = tk.Label(btn, text="▾", bg=self.colors["sidebar"],
                         fg=self.colors["subtext"], font=("Segoe UI", 7))
        caret.pack(side="left", padx=(0, 6))
        self.track_theme(btn, bg="sidebar")
        self.track_theme(lbl, bg="sidebar", fg="text")
        self.track_theme(caret, bg="sidebar", fg="subtext")

        def open_list():
            if nested:
                # Close only THIS dropdown's own previous popup, if any —
                # never touch self._mini_popup, which belongs to whatever
                # popup this dropdown is living inside.
                existing = getattr(btn, "_nested_popup", None)
                if existing is not None:
                    try:
                        if existing.winfo_exists():
                            existing.destroy()
                    except tk.TclError:
                        pass
                pop = tk.Toplevel(self)
                btn._nested_popup = pop
            else:
                self._dismiss_mini_popup()
                pop = tk.Toplevel(self)
                self._mini_popup = pop
            pop.wm_overrideredirect(True)
            pop.configure(bg=self.colors["accent"])
            frame = tk.Frame(pop, bg=self.colors["card"], padx=4, pady=4)
            frame.pack(padx=1, pady=1)
            current = var.get()
            # `options` may be a static list or a callable returning the
            # current list live, so category renames/adds/deletes show up
            # without needing to rebuild this dropdown.
            live_options = options() if callable(options) else options

            for opt in live_options:
                is_cur = (opt == current)
                row_bg = self.colors["sidebar"] if is_cur else self.colors["card"]
                row = tk.Frame(frame, bg=row_bg, cursor="hand2")
                row.pack(fill="x", pady=1)
                widgets = [row]
                color = dot_color_fn(opt) if dot_color_fn else None
                if color:
                    dot = tk.Label(row, text="●", bg=row_bg, fg=color,
                                   font=("Segoe UI", 11), cursor="hand2")
                    dot.pack(side="left", padx=(10, 6), pady=4)
                    widgets.append(dot)
                lbl2 = tk.Label(row, text=opt, bg=row_bg,
                               fg=self.colors["accent"] if is_cur else self.colors["text"],
                               font=("Segoe UI", 9, "bold" if is_cur else "normal"),
                               anchor="w")
                lbl2.pack(side="left", padx=(10 if not color else 0, 10))
                widgets.append(lbl2)

                def pick(v=opt):
                    var.set(v)
                    if nested:
                        try:
                            pop.destroy()
                        except tk.TclError:
                            pass
                        btn._nested_popup = None
                    else:
                        self._dismiss_mini_popup()
                    on_change(v)

                for w in widgets:
                    w.bind("<Button-1>", lambda e, v=opt: pick(v))
                    if not is_cur:
                        w.bind("<Enter>", lambda e, r=row, ws=widgets:
                               [x.configure(bg=self.colors["sidebar"]) for x in ws])
                        w.bind("<Leave>", lambda e, r=row, ws=widgets:
                               [x.configure(bg=self.colors["card"]) for x in ws])

            if nested:
                # Escape is this dropdown's own way to back out without
                # picking anything, since it can't rely on the shared
                # click-outside-dismiss (that's scoped to self._mini_popup,
                # which nested mode deliberately never touches).
                pop.bind("<Escape>", lambda e: pop.destroy())
            self._place_dropdown_popup(pop, btn)

        for w in (btn, lbl, caret):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda e: open_list())
        return btn

    def _open_category_dropdown(self):
        """Open an in-theme dropdown list of categories, each with its colour
        dot. Replaces the OS-white ttk popup."""
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=4, pady=4)
        frame.pack(padx=1, pady=1)

        current = self.category_var.get()
        for cat in CATEGORY_COLORS.keys():
            color = CATEGORY_COLORS.get(cat, self.colors["accent"])
            is_cur = (cat == current)
            row = tk.Frame(frame, bg=self.colors["sidebar"] if is_cur else self.colors["card"],
                           cursor="hand2")
            row.pack(fill="x", pady=1)
            dot = tk.Label(row, text="●", bg=row.cget("bg"), fg=color,
                          font=("Segoe UI", 11), cursor="hand2")
            dot.pack(side="left", padx=(10, 6), pady=4)
            lbl = tk.Label(row, text=cat, bg=row.cget("bg"),
                           fg=self.colors["accent"] if is_cur else self.colors["text"],
                           font=("Segoe UI", 10, "bold" if is_cur else "normal"),
                           anchor="w", width=13)
            lbl.pack(side="left", padx=(0, 10))

            def pick(c=cat):
                self.category_var.set(c)
                self._refresh_category_button()
                self._update_color_swatch()
                self._schedule_autosave()
                self._dismiss_mini_popup()

            for w in (row, dot, lbl):
                w.bind("<Button-1>", lambda e, c=cat: pick(c))
                w.bind("<Enter>", lambda e, r=row, d=dot, l=lbl:
                       (r.configure(bg=self.colors["sidebar"]),
                        d.configure(bg=self.colors["sidebar"]),
                        l.configure(bg=self.colors["sidebar"])))
                if not is_cur:
                    w.bind("<Leave>", lambda e, r=row, d=dot, l=lbl:
                           (r.configure(bg=self.colors["card"]),
                            d.configure(bg=self.colors["card"]),
                            l.configure(bg=self.colors["card"])))

        self._place_dropdown_popup(pop, self.category_menu)

    def _refresh_category_button_safe(self):
        try:
            self._refresh_category_button()
        except tk.TclError:
            pass

    def _place_dropdown_popup(self, pop, anchor_widget=None, anchor_xy=None,
                              enable_click_outside=True):
        """Position a popup like a dropdown anchored to a button: directly below
        it if there's room, otherwise flipped above so it never runs off-screen.
        Horizontally aligned to the button's left edge (nudged in if needed).

        Pass either `anchor_widget` (a button/label to dock under) or
        `anchor_xy` (an (x, y) root-coordinate pair, e.g. from a right-click
        event) when there's no persistent widget to anchor to — a calendar day
        cell reached via a context menu, for instance.

        Clamped to the APP WINDOW's own bounds, not the system screen. On a
        multi-monitor setup, winfo_screenwidth/height() reports the primary
        display's size even when the app sits on a different monitor, which
        used to yank the dropdown back onto the wrong screen entirely. The
        app window's own root x/y/width/height are always correct for
        whichever monitor it's actually on, so anchoring to those keeps the
        dropdown next to the button regardless of monitor arrangement.

        Also re-anchors LIVE while the popup is open: if the user drags or
        resizes the app window, the popup used to stay put at its original
        screen position — visibly detached from the app. Binding this to the
        app's own <Configure> event keeps it docked the whole time.

        Marked -topmost so it can't get pushed behind the main window when
        focus shifts elsewhere in the app (e.g. inserting an emoji sets focus
        on the text field being edited) — without this, a borderless Toplevel
        with no owner/topmost relationship can silently drop behind its
        parent window on focus changes, which looks exactly like the popup
        having closed even though it's technically still open."""
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass

        def reposition(event=None):
            try:
                pop.update_idletasks()
                self.update_idletasks()
                if anchor_widget is not None:
                    anchor_widget.update_idletasks()
                    ax = anchor_widget.winfo_rootx()
                    ay = anchor_widget.winfo_rooty()
                    ah = anchor_widget.winfo_height()
                else:
                    ax, ay = anchor_xy
                    ah = 0
                pw = pop.winfo_reqwidth()
                ph = pop.winfo_reqheight()

                win_left = self.winfo_rootx()
                win_top = self.winfo_rooty()
                win_right = win_left + self.winfo_width()
                win_bottom = win_top + self.winfo_height()

                # Vertical: below the button, or above if it would overflow the
                # app window's own bottom edge.
                below_y = ay + ah + 2
                if below_y + ph <= win_bottom - 8:
                    y = below_y
                else:
                    above_y = ay - ph - 2
                    # If it also doesn't fit above, clamp within the app window.
                    y = above_y if above_y >= win_top + 8 else max(win_top + 8, win_bottom - ph - 8)

                # Horizontal: align left edges, nudge in if it would run past
                # the app window's own right edge.
                x = ax
                if x + pw > win_right - 8:
                    x = max(win_left + 8, win_right - pw - 8)
                pop.wm_geometry(f"+{int(x)}+{int(y)}")
            except tk.TclError:
                pass

        reposition()

        # Configure fires a LOT — not just window move/resize, but also
        # cascading from things like text insertion changing a Text widget's
        # geometry. Coalescing rapid bursts into one actual reposition (via
        # after_idle) keeps the popup docked without redoing the work on
        # every single event, which was contributing to visible stutter
        # while quickly inserting several emojis in a row.
        pending = {"job": None}

        def throttled_reposition(event=None):
            if pending["job"] is not None:
                return
            def run():
                pending["job"] = None
                reposition()
            pending["job"] = self.after_idle(run)

        # Live-track the app window while this popup is open (move + resize).
        # Cleaned up in _dismiss_mini_popup so it doesn't linger once closed.
        self._mini_popup_configure_bind = self.bind("<Configure>", throttled_reposition, add="+")
        pop.bind("<Escape>", lambda e: self._dismiss_mini_popup())
        if enable_click_outside:
            self._mini_popup_click_bind = self.bind(
                "<Button-1>", self._maybe_dismiss_mini_popup, add="+")
        else:
            self._mini_popup_click_bind = None

    def _place_mini_popup(self, pop, anchor_widget=None, anchor_xy=None):
        """Position a mini popup (inline rename, color palette, etc.) just
        below the anchor, flipping above and clamping within the app window's
        own bounds when needed — same safe logic as _place_dropdown_popup, so
        these popups can't run off a different monitor or off the window edge
        on a multi-monitor setup either."""
        self._place_dropdown_popup(pop, anchor_widget, anchor_xy=anchor_xy)

    def _maybe_dismiss_mini_popup(self, event):
        pop = getattr(self, "_mini_popup", None)
        if pop is None:
            return
        # If the click was inside the popup, keep it open.
        w = event.widget
        while w is not None:
            if w is pop:
                return
            try:
                w = w.master
            except AttributeError:
                break
        self._dismiss_mini_popup()

    def _dismiss_mini_popup(self):
        gif_job = getattr(self, "_gif_anim_job", None)
        if gif_job is not None:
            try:
                self.after_cancel(gif_job)
            except (tk.TclError, ValueError):
                pass
            self._gif_anim_job = None
        pop = getattr(self, "_mini_popup", None)
        if pop is not None:
            try:
                pop.destroy()
                # Force Tk to fully finish processing the destroy (and its
                # own OS-level repaint) right now, synchronously, instead of
                # letting it overlap with whatever runs next. A fixed-length
                # timer alone was a guess at "enough time" that didn't always
                # hold; this actually waits for the pending work to drain.
                self.update_idletasks()
            except tk.TclError:
                pass
            self._mini_popup = None
        bind_id = getattr(self, "_mini_popup_click_bind", None)
        if bind_id is not None:
            try:
                self.unbind("<Button-1>", bind_id)
            except tk.TclError:
                pass
            self._mini_popup_click_bind = None
        configure_bind_id = getattr(self, "_mini_popup_configure_bind", None)
        if configure_bind_id is not None:
            try:
                self.unbind("<Configure>", configure_bind_id)
            except tk.TclError:
                pass
            self._mini_popup_configure_bind = None
        # Run any deferred work now that the popup is actually closing — e.g.
        # a full note-list/calendar rebuild, which is heavy enough to cause a
        # visible flicker if it runs WHILE a popup is open on top of it (this
        # is a list, not a single slot, so several independent features can
        # each defer their own work without overwriting one another).
        #
        # Scheduled via after() — on top of the update_idletasks() above —
        # rather than called immediately: running a heavy rebuild in the very
        # same call stack as destroying the popup Toplevel still caused a
        # visible tear even after settling the destroy first. Giving the
        # event loop one more full cycle before the rebuild starts keeps the
        # two from ever overlapping into a single glitchy frame.
        callbacks = getattr(self, "_mini_popup_on_close", None) or []
        self._mini_popup_on_close = []

        def _run_safely(fn):
            try:
                fn()
            except tk.TclError:
                pass

        for cb in callbacks:
            if callable(cb):
                self.after(150, lambda cb=cb: _run_safely(cb))

    def _rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        """Draw a rounded rectangle on a canvas and return the polygon id."""
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _build_settings_categories_panel(self, parent):
        self._settings_panel_header(
            parent, "Categories",
            "Rename, recolor, or remove your categories. “General” is permanent.",
            "categories")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=220)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        rows_frame = tk.Frame(canvas, bg=self.colors["card"])
        rows_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        def redraw():
            for w in rows_frame.winfo_children():
                w.destroy()
            for name in list(CATEGORY_COLORS.keys()):
                self._build_category_row(rows_frame, name, redraw)
            self._bind_wheel_tree(rows_frame, lambda e: self._panel_or_page_wheel(canvas, e))
        redraw()

        # Add-new row
        add_row = tk.Frame(parent, bg=self.colors["card"])
        add_row.pack(fill="x", padx=12, pady=(6, 10))
        new_name_var = tk.StringVar()
        new_entry = tk.Entry(add_row, textvariable=new_name_var, relief="flat",
                             font=("Segoe UI", 10), bg=self.colors["sidebar"],
                             fg=self.colors["text"], insertbackground=self.colors["text"])
        new_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        self._add_paste_menu(new_entry)

        def add_new():
            name = new_name_var.get().strip()
            if not name:
                return
            if name in CATEGORY_COLORS:
                self.show_warning("Already exists",
                                       f"A category named “{name}” already exists.")
                return
            palette = list(DEFAULT_CATEGORY_COLORS.values())
            CATEGORY_COLORS[name] = palette[len(CATEGORY_COLORS) % len(palette)]
            persist_categories()
            new_name_var.set("")
            redraw()
            self.refresh_category_widgets()

        new_entry.bind("<Return>", lambda e: add_new())
        tk.Button(add_row, text="+ Add", command=add_new, bg=self.colors["accent"],
                  fg="white", relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=10, ipady=4)

    def _build_settings_templates_panel(self, parent):
        self._settings_panel_header(
            parent, "Templates",
            "Reusable starting points for new notes. Create one here or use "
            "“🧩 Save as template” on any note. Pick one with “📎 Use template”. "
            "Editing a template only affects notes you make from it afterwards — "
            "notes already created stay as they are.",
            "templates")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=240)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        rows = tk.Frame(canvas, bg=self.colors["card"])
        rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        def redraw():
            for w in rows.winfo_children():
                w.destroy()
            if not self.templates:
                tk.Label(rows, text="No templates yet. Create one below, or use "
                                    "“Save as template” on a note.",
                         bg=self.colors["card"], fg=self.colors["subtext"],
                         font=("Segoe UI", 9), wraplength=460, justify="left"
                         ).pack(pady=10, padx=6, anchor="w")
            else:
                for tpl in self.templates:
                    self._build_template_row(rows, tpl, redraw)
            self._bind_wheel_tree(rows, lambda e: self._panel_or_page_wheel(canvas, e))
        redraw()
        self._refresh_templates_panel = redraw

        # New-from-scratch row.
        add_row = tk.Frame(parent, bg=self.colors["card"])
        add_row.pack(fill="x", padx=12, pady=(6, 10))
        new_tpl_btn = tk.Button(add_row, text="＋ New template",
                  command=lambda: self._edit_template(None, redraw, new_tpl_btn),
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2")
        new_tpl_btn.pack(fill="x", ipady=4)

    def _build_template_row(self, parent, tpl, redraw):
        name = tpl.get("name", "Untitled template")
        row = tk.Frame(parent, bg=self.colors["sidebar"])
        row.pack(fill="x", pady=4, padx=2)
        tk.Label(row, text=f"🧩  {name}", bg=self.colors["sidebar"],
                 fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w"
                 ).pack(side="left", fill="x", expand=True, padx=10, pady=8)

        def delete():
            if self.ask_yes_no("Delete template",
                                   f"Delete the template “{name}”?", parent=parent):
                self.templates = [t for t in self.templates if t is not tpl]
                save_templates(self.templates)
                redraw()
                self._render_statistics()

        tk.Button(row, text="🗑", command=delete, relief="flat", cursor="hand2",
                  bg=self.colors["sidebar"], fg=self.colors["danger"],
                  font=("Segoe UI", 10)).pack(side="right", padx=(2, 8))
        edit_btn = tk.Button(row, text="✎", relief="flat", cursor="hand2",
                  bg=self.colors["sidebar"], fg=self.colors["text"], font=("Segoe UI", 10))
        edit_btn.configure(command=lambda: self._edit_template(tpl, redraw, edit_btn))
        edit_btn.pack(side="right", padx=2)

    def _edit_template(self, tpl, redraw, anchor_widget=None):
        """Open a small editor (inline window) to create or edit a template's
        name, title, body, comments and category."""
        is_new = tpl is None
        data = normalize_template(tpl or {})

        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=12, pady=12)
        frame.pack(padx=1, pady=1)

        head = tk.Frame(frame, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text=("New template" if is_new else "Edit template"),
                 bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 10, "bold"), bd=0).pack(side="right")

        def field(label, initial, height=1):
            tk.Label(frame, text=label, bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
            if height == 1:
                var = tk.StringVar(value=initial)
                e = tk.Entry(frame, textvariable=var, relief="flat", font=("Segoe UI", 10),
                             bg=self.colors["sidebar"], fg=self.colors["text"],
                             insertbackground=self.colors["text"], width=40)
                e.pack(fill="x", ipady=3)
                self._add_paste_menu(e)
                return var
            else:
                t = tk.Text(frame, height=height, width=40, relief="flat",
                            font=("Segoe UI", 10), bg=self.colors["sidebar"],
                            fg=self.colors["text"], insertbackground=self.colors["text"],
                            wrap="word")
                t.insert("1.0", initial)
                t.pack(fill="x")
                self._add_paste_menu(t)
                return t

        name_var = field("Template name", data["name"])
        title_var = field("Note title (optional)", data["title"])
        body_txt = field("Note body", data["body"], height=4)
        comments_txt = field("Comments (optional)", data["comments"], height=2)

        # Interactive checklist editor (same feel as in a note): type + Enter
        # adds an item with a checkbox; each row can be ticked or deleted.
        tpl_checklist = [
            {"text": it.get("text", ""), "done": bool(it.get("done"))}
            for it in data.get("checklist", []) if isinstance(it, dict)
        ]
        tk.Label(frame, text="Checklist", bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(6, 0))
        tpl_cl_list_frame = tk.Frame(frame, bg=self.colors["sidebar"])
        tpl_cl_list_frame.pack(fill="x", pady=(0, 2))

        def render_tpl_checklist():
            for w in tpl_cl_list_frame.winfo_children():
                w.destroy()
            if not tpl_checklist:
                tk.Label(tpl_cl_list_frame, text="No items yet — type below and press Enter.",
                         bg=self.colors["sidebar"], fg=self.colors["subtext"],
                         font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=6, pady=4)
                return
            for item in tpl_checklist:
                row = tk.Frame(tpl_cl_list_frame, bg=self.colors["sidebar"])
                row.pack(fill="x", padx=4, pady=1)
                v = tk.IntVar(value=1 if item.get("done") else 0)

                def on_tog(it=item, var=v, lb=None):
                    it["done"] = bool(var.get())
                    render_tpl_checklist()

                cb = tk.Checkbutton(row, variable=v, command=on_tog,
                                    bg=self.colors["sidebar"], activebackground=self.colors["sidebar"],
                                    selectcolor=self.colors["card"], bd=0, highlightthickness=0)
                cb.pack(side="left")
                lbl = tk.Label(row, text=item.get("text", ""), bg=self.colors["sidebar"],
                               fg=self.colors["subtext"] if item.get("done") else self.colors["text"],
                               font=("Segoe UI", 9), anchor="w", wraplength=320, justify="left")
                lbl.pack(side="left", fill="x", expand=True, padx=(2, 4))

                def do_del(it=item):
                    try:
                        tpl_checklist.remove(it)
                    except ValueError:
                        pass
                    render_tpl_checklist()

                tk.Button(row, text="🗑", command=do_del, relief="flat", cursor="hand2",
                          bg=self.colors["sidebar"], fg=self.colors["danger"],
                          font=("Segoe UI", 8), bd=0).pack(side="right")

        render_tpl_checklist()

        cl_add_row = tk.Frame(frame, bg=self.colors["card"])
        cl_add_row.pack(fill="x", pady=(0, 6))
        cl_add_var = tk.StringVar()
        cl_entry = tk.Entry(cl_add_row, textvariable=cl_add_var, relief="flat",
                            font=("Segoe UI", 10), bg=self.colors["sidebar"],
                            fg=self.colors["text"], insertbackground=self.colors["text"])
        cl_entry.pack(side="left", fill="x", expand=True, ipady=3)
        self._add_paste_menu(cl_entry)

        def add_tpl_item():
            text = cl_add_var.get().strip()
            if not text:
                return
            tpl_checklist.append({"text": text, "done": False})
            cl_add_var.set("")
            render_tpl_checklist()
            cl_entry.focus_set()

        cl_entry.bind("<Return>", lambda e: add_tpl_item())
        tk.Button(cl_add_row, text="＋ Add", command=add_tpl_item,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", padx=(6, 0), ipadx=8, ipady=2)

        tk.Label(frame, text="Category", bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
        cat_var = tk.StringVar(value=data["category"] if data["category"] in CATEGORY_COLORS else "General")
        cat_menu = self._build_themed_dropdown(
            frame, cat_var, lambda: list(CATEGORY_COLORS.keys()),
            on_change=lambda v: None,
            dot_color_fn=lambda v: CATEGORY_COLORS.get(v), width_chars=16,
            nested=True)
        cat_menu.pack(fill="x", pady=(0, 6))

        def save():
            new_tpl = normalize_template({
                "name": name_var.get(),
                "title": title_var.get(),
                "body": body_txt.get("1.0", "end").rstrip("\n"),
                "comments": comments_txt.get("1.0", "end").rstrip("\n"),
                "category": cat_var.get(),
                "checklist": [dict(it) for it in tpl_checklist],
            })
            if not new_tpl["name"].strip():
                self.show_warning("Name needed", "Give the template a name.", parent=pop)
                return
            if is_new:
                self.templates.append(new_tpl)
            else:
                idx = self.templates.index(tpl) if tpl in self.templates else -1
                if idx >= 0:
                    self.templates[idx] = new_tpl
                else:
                    self.templates.append(new_tpl)
            save_templates(self.templates)
            self._dismiss_mini_popup()
            redraw()
            self._render_statistics()

        btns = tk.Frame(frame, bg=self.colors["card"])
        btns.pack(fill="x", pady=(4, 0))
        tk.Button(btns, text="Save", command=save, relief="flat", cursor="hand2",
                  bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold")
                  ).pack(side="left", ipadx=10, ipady=3)
        tk.Button(btns, text="Cancel", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 9)).pack(side="left", padx=(6, 0), ipadx=10, ipady=3)

        # Anchored to whichever button opened it — same safe, proven
        # mechanism every other popup uses (multi-monitor safe, correct
        # -topmost ordering, live-tracks the app window if it moves). Falls
        # back to centering on the app window if no anchor was given.
        # click-outside-dismiss is turned off here — this editor holds more
        # content than a typical dropdown, so an accidental outside click
        # shouldn't discard it; Save/Cancel are the explicit ways out.
        if anchor_widget is not None and anchor_widget.winfo_exists():
            self._place_dropdown_popup(pop, anchor_widget, enable_click_outside=False)
        else:
            self._place_dropdown_popup(
                pop, None,
                anchor_xy=(self.winfo_rootx() + self.winfo_width() // 2,
                          self.winfo_rooty() + self.winfo_height() // 3),
                enable_click_outside=False)
        pop.bind("<Escape>", lambda e: self._dismiss_mini_popup())

    def _build_settings_trash_panel(self, parent):
        self._settings_panel_header(
            parent, "Recently deleted",
            f"Kept for {TRASH_RETENTION_DAYS} days, then removed automatically.",
            "trash")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=240)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        rows = tk.Frame(canvas, bg=self.colors["card"])
        rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        # Paginated: rendering all 600+ rows (and recursively binding the
        # mousewheel across every one of them) at once was measurably slow —
        # over a second and a half with 600 entries, and this only grows over
        # time since trash accumulates. Showing the most recent batch first,
        # with a button to reveal more, keeps opening the panel fast
        # regardless of how large the trash gets.
        PAGE_SIZE = 50
        shown_count = {"n": PAGE_SIZE}

        def redraw():
            for w in rows.winfo_children():
                w.destroy()
            if not self.trash:
                tk.Label(rows, text="Trash is empty.", bg=self.colors["card"],
                         fg=self.colors["subtext"], font=("Segoe UI", 10)).pack(pady=20)
                self._bind_wheel_tree(rows, lambda e: self._panel_or_page_wheel(canvas, e))
                return
            ordered = sorted(self.trash, key=lambda e: e.get("deleted_at", ""), reverse=True)
            visible = ordered[:shown_count["n"]]
            for entry in visible:
                self._build_trash_row(rows, entry, redraw)
            remaining = len(ordered) - len(visible)
            if remaining > 0:
                def show_more():
                    shown_count["n"] += PAGE_SIZE
                    redraw()
                tk.Button(rows, text=f"Show {min(remaining, PAGE_SIZE)} more "
                                     f"({remaining} not shown)",
                          command=show_more, relief="flat", cursor="hand2",
                          bg=self.colors["sidebar"], fg=self.colors["text"],
                          font=("Segoe UI", 8)).pack(fill="x", pady=(6, 2), ipady=4)
            self._bind_wheel_tree(rows, lambda e: self._panel_or_page_wheel(canvas, e))
        redraw()

        def empty_trash():
            if not self.trash:
                return
            if self.ask_yes_no(
                "Empty trash",
                f"Permanently delete all {len(self.trash)} note(s) in the trash? "
                "This can't be undone.", icon="warning", default="no"
            ):
                _delete_attachment_files(self.trash)
                self.trash = []
                save_trash(self.trash)
                shown_count["n"] = PAGE_SIZE
                redraw()

        tk.Button(parent, text="🗑  Empty trash", command=empty_trash,
                  bg=self.colors["danger"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(fill="x", padx=12, pady=(4, 10), ipady=5)

    def _build_settings_duplicates_panel(self, parent):
        self._settings_panel_header(
            parent, "Duplicate notes",
            "Notes with the same title, text, comments and category (ignoring "
            "case, spacing, date and color). Tick the copies you want to "
            "remove — the rest are kept.", "duplicates")
        groups = find_duplicate_groups(self.notes)
        if not groups:
            tk.Label(parent, text="No duplicates found — every note is unique. 🎉",
                     font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["subtext"],
                     wraplength=520, justify="left").pack(padx=12, pady=(0, 12), anchor="w")
            return

        total_dupes = sum(len(g) - 1 for g in groups)
        tk.Label(parent, text=f"Found {len(groups)} group(s), up to {total_dupes} note(s) "
                              "could be removed.",
                 font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["subtext"],
                 wraplength=520, justify="left").pack(padx=12, pady=(0, 2), anchor="w")
        tk.Label(parent, text="Tick the copies you want to remove. Keep as many as "
                              "you like — anything left unticked stays. Attachments "
                              "from removed copies are merged into a kept one.",
                 font=("Segoe UI", 8, "italic"), bg=self.colors["card"],
                 fg=self.colors["accent"], wraplength=520, justify="left"
                 ).pack(padx=12, pady=(0, 8), anchor="w")

        wrap = tk.Frame(parent, bg=self.colors["card"], height=260)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 120, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["card"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        del_vars = []  # (var, note, group) across all groups
        all_group_vars = []  # list of per-group var lists, for the "clean up everything" button
        for group in groups:
            box = tk.Frame(inner, bg=self.colors["sidebar"])
            box.pack(fill="x", pady=5, padx=2)
            title = (group[0].get("title") or "").strip() or "(untitled)"
            tk.Label(box, text=f"“{title[:36]}” — {len(group)} copies",
                     font=("Segoe UI", 10, "bold"), bg=self.colors["sidebar"],
                     fg=self.colors["text"], anchor="w").pack(fill="x", padx=10, pady=(8, 2))

            hints = []
            if any(n.get("attachments") for n in group) and \
               len({bool(n.get("attachments")) for n in group}) > 1:
                hints.append("attachments")
            if hints:
                tk.Label(box, text=f"↳ differing {' & '.join(hints)} will be merged "
                                   "into a kept copy",
                         font=("Segoe UI", 7, "italic"), bg=self.colors["sidebar"],
                         fg=self.colors["accent"], anchor="w", wraplength=460, justify="left"
                         ).pack(fill="x", padx=14, pady=(0, 2))

            group_vars = []
            for note in group:
                created = note.get("created", "")
                updated = note.get("updated", "")
                meta = f"created {created[:10]}" if created else ""
                if updated and updated != created:
                    meta += f" · updated {updated[:10]}"
                var = tk.IntVar(value=0)
                del_vars.append((var, note, group))
                group_vars.append(var)
                cb = tk.Checkbutton(
                    box, text=f"Delete this copy   ({meta})" if meta else "Delete this copy",
                    variable=var,
                    bg=self.colors["sidebar"], fg=self.colors["text"],
                    selectcolor=self.colors["card"],
                    activebackground=self.colors["sidebar"], activeforeground=self.colors["text"],
                    font=("Segoe UI", 8), anchor="w")
                cb.pack(fill="x", padx=20)
                self._attach_dup_preview(cb, note)

            # Shortcut: tick every copy except the first (old "keep one" behavior).
            def check_all_but_first(gv=group_vars):
                for i, v in enumerate(gv):
                    v.set(0 if i == 0 else 1)

            def clear_group(gv=group_vars):
                for v in gv:
                    v.set(0)

            all_group_vars.append(group_vars)

            btn_row = tk.Frame(box, bg=self.colors["sidebar"])
            btn_row.pack(fill="x", padx=10, pady=(2, 8))
            tk.Button(btn_row, text="Tick all but first", command=check_all_but_first,
                      bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                      font=("Segoe UI", 8), cursor="hand2"
                      ).pack(side="left", ipadx=6, ipady=2)
            tk.Button(btn_row, text="Clear", command=clear_group,
                      bg=self.colors["card"], fg=self.colors["subtext"], relief="flat",
                      font=("Segoe UI", 8), cursor="hand2"
                      ).pack(side="left", padx=(6, 0), ipadx=6, ipady=2)

        self._bind_wheel_tree(inner, lambda e: self._panel_or_page_wheel(canvas, e))

        def do_cleanup():
            self._cleanup_selected_duplicates(
                del_vars, parent,
                refresh=lambda: self._reopen_dup_panel(), announce=True)

        def clean_up_everything():
            # Same "keep first, remove the rest" shortcut as each group's own
            # button, just applied to every group in one click instead of
            # working through them one at a time.
            for gv in all_group_vars:
                for i, v in enumerate(gv):
                    v.set(0 if i == 0 else 1)
            do_cleanup()

        if len(groups) > 1:
            tk.Button(parent, text=f"🧹✨  Clean up ALL {len(groups)} groups (keep first in each)",
                      command=clean_up_everything,
                      bg=self.colors["sidebar"], fg=self.colors["text"], relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2"
                      ).pack(fill="x", padx=12, pady=(4, 4), ipady=5)

        tk.Button(parent, text="🧹  Move ticked duplicates to trash", command=do_cleanup,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2"
                  ).pack(fill="x", padx=12, pady=(4, 10), ipady=6)

    def _reopen_dup_panel(self):
        """Rebuild the duplicates panel in place after a cleanup."""
        panel = getattr(self, "settings_duplicates_panel", None)
        if panel is None:
            return
        for w in panel.winfo_children():
            w.destroy()
        self._build_settings_duplicates_panel(panel)
        if not panel.winfo_ismapped():
            panel.pack(fill="x", padx=16, pady=(0, 12))

    def track_theme(self, widget, **option_map):
        self.themed_widgets.append((widget, option_map))
        widget.configure(**{opt: self.colors[key] for opt, key in option_map.items()})
        return widget

    def _build_theme_picker(self, parent):
        """Show the theme variants for the CURRENT mode (dark or light) as
        larger, nicer preview cards. Switching light/dark swaps which set shows.
        The active theme is highlighted."""
        for w in parent.winfo_children():
            w.destroy()

        in_dark = self.theme_name in DARK_THEMES
        names = DARK_THEMES if in_dark else LIGHT_THEMES

        heading = tk.Label(
            parent, text=("Dark themes" if in_dark else "Light themes"),
            bg=self.colors["card"], fg=self.colors["subtext"],
            font=("Segoe UI", 9, "bold"), anchor="w")
        heading.pack(fill="x", pady=(4, 8))

        grid = tk.Frame(parent, bg=self.colors["card"])
        grid.pack(fill="x")
        for col in range(len(names)):
            grid.grid_columnconfigure(col, weight=1, uniform="themecol")

        for i, name in enumerate(names):
            pal = THEMES[name]
            active = (name == self.theme_name)

            cell = tk.Frame(grid, bg=self.colors["card"], cursor="hand2")
            cell.grid(row=0, column=i, padx=6, pady=2, sticky="nsew")

            # A larger preview card: window chrome with sidebar, an accent
            # button, a couple of text bars — a mini snapshot of the theme.
            W, H = 150, 96
            sw = tk.Canvas(cell, width=W, height=H, highlightthickness=0,
                           bg=self.colors["card"], cursor="hand2")
            # Outer rounded card = bg, with a highlight ring if active.
            ring = pal["accent"] if active else pal["sidebar"]
            self._rounded_rect(sw, 2, 2, W - 2, H - 2, 12, fill=pal["bg"], outline=ring)
            if active:
                self._rounded_rect(sw, 4, 4, W - 4, H - 4, 11, fill=pal["bg"], outline=pal["accent"])
            # Sidebar strip on the left.
            self._rounded_rect(sw, 8, 10, 44, H - 10, 8, fill=pal["sidebar"], outline=pal["sidebar"])
            # A "note card" on the right.
            self._rounded_rect(sw, 52, 12, W - 12, H - 12, 8, fill=pal["card"], outline=pal["card"])
            # Accent button + text lines inside the card.
            self._rounded_rect(sw, 60, 20, 108, 32, 5, fill=pal["accent"], outline=pal["accent"])
            self._rounded_rect(sw, 60, 42, W - 20, 48, 3, fill=pal["text"], outline=pal["text"])
            self._rounded_rect(sw, 60, 54, W - 30, 60, 3, fill=pal["subtext"], outline=pal["subtext"])
            self._rounded_rect(sw, 60, 66, W - 40, 72, 3, fill=pal["subtext"], outline=pal["subtext"])
            # Sidebar dots.
            for dy in (18, 30, 42):
                self._rounded_rect(sw, 14, dy, 38, dy + 6, 3,
                                   fill=pal["accent"] if dy == 18 else pal["card"],
                                   outline=pal["accent"] if dy == 18 else pal["card"])
            if active:
                sw.create_text(W - 16, 16, text="✓", fill=pal["accent"],
                               font=("Segoe UI", 13, "bold"))
            sw.pack()

            lbl = tk.Label(cell, text=THEME_LABELS.get(name, name),
                           bg=self.colors["card"],
                           fg=(self.colors["accent"] if active else self.colors["text"]),
                           font=("Segoe UI", 9, "bold" if active else "normal"))
            lbl.pack(pady=(6, 2))

            for w in (cell, sw, lbl):
                w.bind("<Button-1>", lambda e, n=name: self.set_theme(n))

        # Each preview card's canvas otherwise swallows the mouse wheel
        # itself (a plain Tk quirk: Canvas has a built-in default scroll
        # binding, so it never lets the event reach the Settings page
        # underneath) — forward it to the page's own scroll instead, the
        # same pattern used for every other Settings panel.
        def _theme_picker_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        self._bind_wheel_tree(parent, _theme_picker_wheel)

        self._refresh_theme_picker = lambda: self._build_theme_picker(parent)

    def toggle_theme(self):
        """Quick toggle between the last dark and last light theme. Kept for the
        existing 'Switch to Light/Dark mode' button."""
        if self.theme_name in DARK_THEMES:
            self.set_theme(getattr(self, "_last_light_theme", "light"))
        else:
            self.set_theme(getattr(self, "_last_dark_theme", "dark"))

    def set_theme(self, name):
        """Switch to any named theme variant and persist the choice."""
        if name not in THEMES:
            return
        self.theme_name = name
        self.colors = THEMES[name]
        # Remember the last dark/light pick so the quick toggle feels natural.
        if name in DARK_THEMES:
            self._last_dark_theme = name
        elif name in LIGHT_THEMES:
            self._last_light_theme = name
        self.save_theme_setting()
        self.apply_theme()
        # Refresh the theme picker if it's open.
        refresh = getattr(self, "_refresh_theme_picker", None)
        if callable(refresh):
            try:
                refresh()
            except tk.TclError:
                self._refresh_theme_picker = None

    def apply_theme(self):
        self.configure(bg=self.colors["bg"])
        for widget, option_map in self.themed_widgets:
            try:
                widget.configure(**{opt: self.colors[key] for opt, key in option_map.items()})
            except tk.TclError:
                pass
        # The theme toggle now lives in Settings; update its label if present.
        if hasattr(self, "theme_toggle_btn"):
            self.theme_toggle_btn.config(
                text="☀️  Switch to Light mode" if self.theme_name in DARK_THEMES
                else "🌙  Switch to Dark mode")
        self._refresh_placeholder_colors()
        self.refresh_weekday_buttons()
        self.on_end_mode_changed()
        self.style_notebook()
        self.refresh_note_list()
        self.render_calendar()
        # refresh_note_list() above already refreshes Statistics too.
        # Safety net: catch any widget that slipped through the registered list
        # (e.g. built once and never rebuilt) by swapping known theme colors from
        # the OTHER theme to the current one. This guarantees a clean flip.
        self._recolor_stragglers()

    def _recolor_stragglers(self):
        """Walk the whole widget tree and fix any bg/fg still set to a color from
        a DIFFERENT theme. With several themes, a widget could carry a color from
        any of them, so we remap from every other theme to the current one. This
        keeps each theme clean no matter which one you switch from."""
        cur = self.colors
        remap = {}
        for name, palette in THEMES.items():
            if name == self.theme_name:
                continue
            for key, val in palette.items():
                if key in cur and isinstance(val, str) and val.startswith("#"):
                    # Don't overwrite a color that's also valid in the current
                    # theme (same hex used by both) — only remap true mismatches.
                    if val.lower() != cur[key].lower():
                        remap[val.lower()] = cur[key]
        # Current theme's own colors must never be remapped away.
        for key, val in cur.items():
            if isinstance(val, str) and val.startswith("#"):
                remap.pop(val.lower(), None)

        def walk(w):
            for opt in ("bg", "fg"):
                try:
                    val = str(w.cget(opt)).lower()
                except tk.TclError:
                    continue
                if val in remap:
                    try:
                        w.configure(**{opt: remap[val]})
                    except tk.TclError:
                        pass
            for child in w.winfo_children():
                walk(child)

        try:
            walk(self)
        except tk.TclError:
            pass

    def _refresh_placeholder_colors(self):
        # self._placeholders only ever grows (add_placeholder() appends,
        # nothing ever removes an entry when the widget that owns it is
        # later destroyed) -- harmless for a permanent field, but every
        # hex-code entry inside a temporary color-picker popup (this
        # feature's two new ones, and the note's own pre-existing color
        # picker) registers here too, and gets destroyed the moment its
        # popup closes. The next theme switch after that used to crash on
        # "invalid command name" trying to read a long-gone widget. Prune
        # dead entries here, the first time each one is found stale,
        # rather than letting the list accumulate references that can
        # never be read again.
        alive = []
        for entry, placeholder in getattr(self, "_placeholders", []):
            try:
                if entry.get() == placeholder:
                    entry.config(fg=self.colors["subtext"])
                else:
                    entry.config(fg=self.colors["text"])
                alive.append((entry, placeholder))
            except tk.TclError:
                pass
        self._placeholders = alive

    def style_notebook(self):
        self.style_ttk()

    def style_ttk(self):
        """Theme all ttk widgets (notebook tabs + the sidebar comboboxes) so
        they follow dark/light mode. ttk widgets ignore normal bg/fg, so this
        has to go through ttk.Style and a few option_add calls for the popup
        list, which isn't a real widget we can reach directly."""
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        c = self.colors

        # --- Notebook tabs ---
        style.configure("TNotebook", background=c["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab", background=c["sidebar"], foreground=c["text"],
            padding=(16, 8), font=("Segoe UI", 10, "bold")
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", c["accent"])],
            foreground=[("selected", "white")],
        )

        # --- Subtle sidebar comboboxes (sort + filter) ---
        # Blend between sidebar and card so they read as recessed, not as a
        # hard box shouting for attention. This is the "translucent" look:
        # the control sits just barely above its background.
        blended = self._blend(c["sidebar"], c["card"], 0.5)
        style.configure(
            "Subtle.TCombobox",
            fieldbackground=blended,
            background=blended,
            foreground=c["subtext"],          # muted text = less "in your face"
            arrowcolor=c["subtext"],
            bordercolor=c["sidebar"],
            lightcolor=blended,
            darkcolor=blended,
            borderwidth=0,
            relief="flat",
            padding=(6, 3),
        )
        style.map(
            "Subtle.TCombobox",
            # On hover/focus it "wakes up": accent arrow, brighter text.
            fieldbackground=[("readonly", blended), ("focus", c["card"]),
                             ("active", c["card"])],
            foreground=[("focus", c["text"]), ("active", c["text"])],
            arrowcolor=[("focus", c["accent"]), ("active", c["accent"])],
            bordercolor=[("focus", c["accent"])],
        )

        # --- Scrollbars (every ttk.Scrollbar in the app uses these default
        # style names, so styling them here re-themes all of them at once). ---
        for orient in ("Vertical", "Horizontal"):
            name = f"{orient}.TScrollbar"
            style.configure(
                name,
                background=c["card"],       # the draggable thumb
                troughcolor=c["sidebar"],   # the track behind it
                bordercolor=c["sidebar"],
                arrowcolor=c["subtext"],
                relief="flat",
                borderwidth=0,
                arrowsize=12,
            )
            style.map(
                name,
                background=[("active", c["accent"]), ("pressed", c["accent"])],
                arrowcolor=[("active", "white"), ("pressed", "white")],
            )

        # The dropdown popup list isn't a themeable ttk element — it's a Tk
        # Listbox reached only through the option database.
        # The dropdown popup list isn't a themeable ttk element — it's a Tk
        # Listbox reached only through the option database. Priority 80
        # (interactive) forces these to override the values cached from an
        # earlier theme, so the popup recolors when the user toggles themes.
        self.option_add("*TCombobox*Listbox.background", c["card"], 80)
        self.option_add("*TCombobox*Listbox.foreground", c["text"], 80)
        self.option_add("*TCombobox*Listbox.selectBackground", c["accent"], 80)
        self.option_add("*TCombobox*Listbox.selectForeground", "white", 80)
        self.option_add("*TCombobox*Listbox.font", "{Segoe UI} 9", 80)
        self.option_add("*TCombobox*Listbox.borderWidth", 0, 80)

        # option_add only affects popups created AFTER it runs. A combobox
        # whose popup already exists (because the user opened it once) keeps
        # its old colors, so recolor those existing popup listboxes directly.
        self._recolor_existing_combo_popups()

    def _recolor_existing_combo_popups(self):
        """Find any already-created ttk.Combobox popdown listboxes and recolor
        them to the current theme. The popup lives at .popdown.f.l under the
        combobox in Tk's widget tree."""
        c = self.colors
        for combo in getattr(self, "_styled_combos", []):
            try:
                popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
                listbox = f"{popdown}.f.l"
                combo.tk.call(listbox, "configure", "-background", c["card"])
                combo.tk.call(listbox, "configure", "-foreground", c["text"])
                combo.tk.call(listbox, "configure", "-selectbackground", c["accent"])
                combo.tk.call(listbox, "configure", "-selectforeground", "white")
            except tk.TclError:
                # Popup not created yet (user never opened this combo) — the
                # option_add defaults will handle it on first open.
                pass

    @staticmethod
    def _blend(hex_a, hex_b, t):
        """Mix two #rrggbb colors. t=0 -> hex_a, t=1 -> hex_b."""
        a = tuple(int(hex_a[i:i+2], 16) for i in (1, 3, 5))
        b = tuple(int(hex_b[i:i+2], 16) for i in (1, 3, 5))
        mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
        return "#%02x%02x%02x" % mixed

    # ---------- UI construction ----------
    def build_ui(self):
        self._placeholders = []

        self.style_notebook()

        # --- Outer horizontal-scroll wrapper ---
        self.main_canvas = tk.Canvas(self, highlightthickness=0)
        self.track_theme(self.main_canvas, bg="bg")
        main_hscroll = ttk.Scrollbar(self, orient="horizontal", command=self.main_canvas.xview)

        main_hscroll.pack(side="bottom", fill="x")
        self.main_canvas.pack(side="top", fill="both", expand=True)
        self.main_canvas.configure(xscrollcommand=main_hscroll.set)

        self.main_inner = tk.Frame(self.main_canvas)
        self.track_theme(self.main_inner, bg="bg")
        main_window = self.main_canvas.create_window((0, 0), window=self.main_inner, anchor="nw")

        def _on_inner_configure(event):
            self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

        MIN_TOTAL_WIDTH = SIDEBAR_WIDTH + EDITOR_MIN_WIDTH

        def _on_main_canvas_configure(event):
            target_width = max(event.width, MIN_TOTAL_WIDTH)
            self.main_canvas.itemconfig(main_window, width=target_width, height=event.height)

        self.main_inner.bind("<Configure>", _on_inner_configure)
        self.main_canvas.bind("<Configure>", _on_main_canvas_configure)

        def _on_shift_wheel(event):
            self.main_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        self.main_canvas.bind("<Shift-MouseWheel>", _on_shift_wheel)

        # --- Reminder bar (subtle, dismissable, shown once per day) ---
        # Sits above the tabs. Hidden unless there are notes due today AND it
        # hasn't already been shown/dismissed today.
        self.reminder_bar = tk.Frame(self.main_inner)
        self.track_theme(self.reminder_bar, bg="accent")
        # packed on demand by maybe_show_reminder()

        # --- Autosave toast: a small floating banner, always near the top of
        # the window regardless of scroll position or which tab is active, so
        # "auto-saved" feedback is never missed inside a long note. ---
        self.toast_frame = tk.Frame(self, bg=self.colors["success"])
        self.toast_lbl = tk.Label(
            self.toast_frame, font=("Segoe UI", 9, "bold"),
            bg=self.colors["success"], fg="white", padx=14, pady=6)
        self.toast_lbl.pack()
        self._toast_hide_job = None
        # Not placed yet — shown on demand by _show_toast().

        # --- Export progress bar: floats near the bottom of the window,
        # visible no matter which tab is active — same overlay approach as
        # the toast above, since export can now run while the user keeps
        # working in any tab. Not placed yet; shown on demand. ---
        self.export_progress_frame = tk.Frame(self, bg=self.colors["card"],
                                              highlightthickness=1,
                                              highlightbackground=self.colors["accent"])
        export_inner = tk.Frame(self.export_progress_frame, bg=self.colors["card"])
        export_inner.pack(padx=14, pady=10)
        self.export_progress_lbl = tk.Label(
            export_inner, text="Exporting…", font=("Segoe UI", 9, "bold"),
            bg=self.colors["card"], fg=self.colors["text"])
        self.export_progress_lbl.pack(anchor="w")
        self.export_progress_bar = ttk.Progressbar(
            export_inner, orient="horizontal", length=240, mode="determinate")
        self.export_progress_bar.pack(pady=(6, 0))
        self._export_state = None  # dict shared with the background thread
        self._import_state = None  # same idea, for import
        self._export_poll_job = None

        # --- Notebook: Notes tab / Calendar tab ---
        # Settings is deliberately NOT a third tab here anymore — it lives as
        # a separate page (see show_settings_page/hide_settings_page below),
        # reached via its own button in the sidebar's bottom action zone,
        # alongside New Note / Import / Share. Putting it in the tab strip
        # made it read as "just another tab", and the alternative of pushing
        # it to the top-right corner risked sitting too close to the
        # window's own close button.
        self.notebook = ttk.Notebook(self.main_inner)
        self.notebook.pack(fill="both", expand=True)

        notes_tab = tk.Frame(self.notebook)
        self.track_theme(notes_tab, bg="bg")
        calendar_tab = tk.Frame(self.notebook)
        self.track_theme(calendar_tab, bg="bg")

        self.notebook.add(notes_tab, text="📝 Notes")
        self.notebook.add(calendar_tab, text="📅 Calendar")

        # Looked up from the notebook itself rather than hardcoded — stays
        # correct even if a tab is ever added, removed, or reordered again.
        self.TAB_NOTES = self.notebook.index(notes_tab)
        self.TAB_CALENDAR = self.notebook.index(calendar_tab)

        # Settings page: a sibling of the notebook (not inside it), in the
        # same parent, so showing it is a simple pack-forget/pack swap.
        self.settings_page = tk.Frame(self.main_inner)
        self.track_theme(self.settings_page, bg="bg")
        # Not packed yet — hidden until show_settings_page() is called.

        self.build_notes_tab(notes_tab)
        self.build_calendar_tab(calendar_tab)
        self.build_settings_tab(self.settings_page)

        def _on_tab_changed(event):
            try:
                self.notebook.index(self.notebook.select())
            except tk.TclError:
                return
            self._catch_up_deferred_refresh()
            # Defensive: some platforms move keyboard focus to whatever Entry
            # happens to sit first in the newly-shown tab (e.g. the search box)
            # when the previously-focused widget is hidden by the tab switch.
            # Explicitly park focus on the notebook itself so no field silently
            # starts capturing keystrokes the user didn't click into.
            try:
                focused = self.focus_get()
                if isinstance(focused, (tk.Entry, tk.Text)):
                    self.notebook.focus_set()
            except (tk.TclError, KeyError):
                pass
        self.notebook.bind("<<NotebookTabChanged>>", _on_tab_changed, add="+")

    def show_settings_page(self):
        """Show the Settings page in place of the Notes/Calendar notebook.
        Settings lives outside the tab strip on purpose — see the comment
        where self.settings_page is created."""
        self._catch_up_deferred_refresh()
        self.notebook.pack_forget()
        self.settings_page.pack(fill="both", expand=True)
        self._render_statistics()

    def hide_settings_page(self):
        """Return from Settings to the Notes/Calendar notebook."""
        self.settings_page.pack_forget()
        self.notebook.pack(fill="both", expand=True)

    def toggle_sidebar(self):
        """Hide or show the left sidebar (note list + New Note / Import / Share)
        so the editor can use the full width. The thin toggle strip stays put so
        the sidebar can always be brought back."""
        if self._sidebar_hidden:
            # Show it again — re-pack before the toggle strip to keep the order
            # sidebar → toggle → editor.
            self.sidebar.pack(side="left", fill="y", before=self.sidebar_toggle)
            self.sidebar_toggle_lbl.config(text="‹")
            self._sidebar_hidden = False
        else:
            self.sidebar.pack_forget()
            self.sidebar_toggle_lbl.config(text="›")
            self._sidebar_hidden = True

    def build_notes_tab(self, parent):
        # --- Sidebar (note list) ---
        self.sidebar = tk.Frame(parent, width=SIDEBAR_WIDTH)
        self.track_theme(self.sidebar, bg="sidebar")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        title_lbl = tk.Label(self.sidebar, text="📝 My Notes", font=("Segoe UI", 16, "bold"))
        self.track_theme(title_lbl, bg="sidebar", fg="text")
        title_lbl.pack(pady=(20, 0), padx=15, anchor="w")

        self.greeting_lbl = tk.Label(
            self.sidebar, font=("Segoe UI", 9),
            # Wraps instead of overflowing past the sidebar's fixed width —
            # a safety net independent of the username length cap, in case a
            # name ever ends up longer than expected some other way.
            wraplength=SIDEBAR_WIDTH - 30, justify="left"
        )
        self.track_theme(self.greeting_lbl, bg="sidebar", fg="subtext")
        self.greeting_lbl.pack(pady=(2, 12), padx=15, anchor="w")
        self._refresh_greeting()

        self.search_var = tk.StringVar()
        self._search_debounce_job = None

        def _debounced_search_refresh(*args):
            # Rebuilding the whole note list is not cheap (every card is a
            # handful of widgets) — doing it on every keystroke made typing a
            # search term feel laggy with a large note collection, worse the
            # more notes there are (exactly when search matters most). Wait
            # for a short pause in typing instead, same idea as autosave.
            if self._search_debounce_job is not None:
                try:
                    self.after_cancel(self._search_debounce_job)
                except (tk.TclError, ValueError):
                    pass
            self._search_debounce_job = self.after(180, self.refresh_note_list)

        self.search_var.trace_add("write", _debounced_search_refresh)
        search_entry = tk.Entry(
            self.sidebar, textvariable=self.search_var,
            insertbackground=self.colors["text"], relief="flat", font=("Segoe UI", 11)
        )
        self.track_theme(search_entry, bg="card", fg="text")
        search_entry.pack(fill="x", padx=15, pady=(0, 10), ipady=6)
        self.add_placeholder(search_entry, "Search notes...")

        # Sort + category filter row
        filter_row = tk.Frame(self.sidebar)
        self.track_theme(filter_row, bg="sidebar")
        filter_row.pack(fill="x", padx=15, pady=(0, 8))

        # Human label -> (key function description) handled in refresh_note_list
        self.SORT_OPTIONS = [
            "Recently updated",
            "Oldest updated",
            "Title A–Z",
            "Title Z–A",
            "Category",
            "Date (soonest)",
        ]
        self.sort_var = tk.StringVar(value=self.SORT_OPTIONS[0])
        # width_chars=18: the default (14) renders "Recently updated" at
        # exactly its natural text width with zero margin, which is why the
        # last letter looked cut off. Measured with tkinter.font: the
        # longest option needs 90px, and width=18 gives 114px — comfortable
        # room without wasting space on the shorter options.
        sort_menu = self._build_themed_dropdown(
            filter_row, self.sort_var, self.SORT_OPTIONS,
            on_change=lambda v: self.refresh_note_list(), width_chars=18)
        sort_menu.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.filter_var = tk.StringVar(value="All")
        self.filter_menu = self._build_themed_dropdown(
            filter_row, self.filter_var,
            lambda: ["All"] + list(CATEGORY_COLORS.keys()),
            on_change=lambda v: self.refresh_note_list(),
            dot_color_fn=lambda v: CATEGORY_COLORS.get(v), width_chars=9)
        self.filter_menu.pack(side="left")

        # Group by category — an independent toggle. When on, notes are
        # clustered under collapsible category headers instead of one flat
        # list; sorting still applies within each group.
        self.group_by_category = tk.BooleanVar(
            value=bool(load_settings().get("group_by_category", False)))
        self.collapsed_groups = set(load_settings().get("collapsed_groups", []))
        group_row = tk.Frame(self.sidebar)
        self.track_theme(group_row, bg="sidebar")
        group_row.pack(fill="x", padx=15, pady=(0, 8))
        group_cb = tk.Checkbutton(
            group_row, text="Group by category", variable=self.group_by_category,
            command=self._on_toggle_group_by_category,
            font=("Segoe UI", 8), anchor="w")
        # This checkbox is built ONCE at startup and lives for the whole app
        # session (unlike other checkboxes in the app, which sit inside
        # panels that get fully rebuilt — and so naturally pick up the
        # current theme — every time they're opened). Being long-lived means
        # it needs LIVE theme tracking, or selectcolor stays stuck at
        # whichever theme was active when the app started, regardless of any
        # later theme switch.
        self.track_theme(group_cb, bg="sidebar", fg="subtext", selectcolor="card",
                         activebackground="sidebar")
        group_cb.pack(side="left")

        # Multi-select: pick several notes at once for a bulk action (move to
        # trash, change category), instead of doing each one individually.
        self.selection_mode = False
        self.selected_note_ids = set()
        self.select_toggle_btn = tk.Button(
            group_row, text="☑ Select", command=self._toggle_selection_mode,
            relief="flat", font=("Segoe UI", 8, "bold"), cursor="hand2"
        )
        self.track_theme(self.select_toggle_btn, bg="card", fg="subtext")
        self.select_toggle_btn.pack(side="right", ipadx=6, ipady=2)

        # Bulk-action bar: hidden until selection mode is turned on. Built
        # once, like the rest of this persistent sidebar chrome — its inner
        # label/buttons get live theme tracking for the same reason group_cb
        # above does.
        # Font size 7 (not the sidebar's usual 8) and tighter inter-widget
        # spacing here specifically — measured with tkinter.font: at size 8
        # with the original spacing, these four widgets need 260px total
        # (including the gaps between them), more than the ~230px actually
        # available in the fixed 280px-wide sidebar, which is exactly why
        # "Category"'s last letter looked cramped. At size 7 with tighter
        # spacing they need 209px — comfortable room to spare.
        self.bulk_action_bar = tk.Frame(self.sidebar)
        self.track_theme(self.bulk_action_bar, bg="sidebar")
        self.bulk_selected_lbl = tk.Label(
            self.bulk_action_bar, text="0 selected", font=("Segoe UI", 7, "bold"))
        self.track_theme(self.bulk_selected_lbl, bg="sidebar", fg="text")
        self.bulk_selected_lbl.pack(side="left", padx=(0, 3))
        bulk_select_all_btn = tk.Button(
            self.bulk_action_bar, text="Select all", command=self._bulk_select_all,
            relief="flat", font=("Segoe UI", 7), cursor="hand2")
        self.track_theme(bulk_select_all_btn, bg="card", fg="text")
        bulk_select_all_btn.pack(side="left", padx=(0, 2), ipadx=2, ipady=2)
        bulk_trash_btn = tk.Button(
            self.bulk_action_bar, text="🗑 Trash", command=self._bulk_move_to_trash,
            relief="flat", font=("Segoe UI", 7, "bold"), cursor="hand2")
        self.track_theme(bulk_trash_btn, bg="danger")
        bulk_trash_btn.configure(fg="white")
        bulk_trash_btn.pack(side="left", padx=(0, 2), ipadx=2, ipady=2)
        bulk_category_btn = tk.Button(
            self.bulk_action_bar, text="🗂 Category ▾", command=self._bulk_change_category,
            relief="flat", font=("Segoe UI", 7), cursor="hand2")
        self.track_theme(bulk_category_btn, bg="accent")
        bulk_category_btn.configure(fg="white")
        bulk_category_btn.pack(side="left", ipadx=2, ipady=2)
        self._bulk_category_btn = bulk_category_btn
        # Not packed yet — shown by _toggle_selection_mode() when active.

        # Bottom action zone — pinned to the bottom of the sidebar so New Note /
        # Import / Share and their inline panels always stay on-screen even when
        # the window is short. Packed BEFORE the list so it reserves its space;
        # the note list then fills whatever's left and scrolls on its own.
        bottom_zone = tk.Frame(self.sidebar)
        self.track_theme(bottom_zone, bg="sidebar")
        bottom_zone.pack(side="bottom", fill="x")
        self._sidebar_bottom = bottom_zone

        list_container = tk.Frame(self.sidebar)
        self.track_theme(list_container, bg="sidebar")
        list_container.pack(fill="both", expand=True, padx=10)

        self.canvas = tk.Canvas(list_container, highlightthickness=0)
        self.track_theme(self.canvas, bg="sidebar")
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.list_frame = tk.Frame(self.canvas)
        self.track_theme(self.list_frame, bg="sidebar")

        self.list_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw", width=250)
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Pack the scrollbar FIRST (side="right") so it always reserves its own
        # width before the canvas claims the rest with expand=True — packed in
        # the other order, the canvas could grab all available width and
        # squeeze the scrollbar down to nothing (invisible, unusable).
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self._bind_mousewheel_recursive(self.sidebar, self.canvas)

        new_btn = tk.Button(
            bottom_zone, text="+ New Note", command=self.open_blank_tab,
            fg="white", relief="flat", font=("Segoe UI", 11, "bold"), cursor="hand2"
        )
        self.track_theme(new_btn, bg="accent", activebackground="accent_hover")
        new_btn.pack(fill="x", padx=15, pady=(10, 4), ipady=8)

        import_btn = tk.Button(
            bottom_zone, text="📥 Import code", command=self.toggle_import_panel,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(import_btn, bg="card", fg="text")
        import_btn.pack(fill="x", padx=15, pady=(0, 4), ipady=5)

        # Inline import panel — expands under the button instead of a pop-up.
        self.import_panel = tk.Frame(bottom_zone)
        self.track_theme(self.import_panel, bg="sidebar")
        # not packed until the button is pressed
        self._build_import_panel()

        share_multi_btn = tk.Button(
            bottom_zone, text="🔗 Share notes", command=self.toggle_share_panel,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(share_multi_btn, bg="card", fg="text")
        share_multi_btn.pack(fill="x", padx=15, pady=(0, 12), ipady=5)

        # Inline share panel — pick notes, get a code, all without a pop-up.
        self.share_panel = tk.Frame(bottom_zone)
        self.track_theme(self.share_panel, bg="sidebar")

        settings_btn = tk.Button(
            bottom_zone, text="⚙ Settings", command=self.show_settings_page,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(settings_btn, bg="card", fg="text")
        settings_btn.pack(fill="x", padx=15, pady=(0, 12), ipady=5)

        # --- Sidebar collapse toggle (thin strip on the sidebar's edge) ---
        # Stays visible whether the sidebar is shown or hidden, so the user can
        # always bring the note list back.
        self._sidebar_hidden = False
        self.sidebar_toggle = tk.Frame(parent, width=16, cursor="hand2")
        self.track_theme(self.sidebar_toggle, bg="card")
        self.sidebar_toggle.pack(side="left", fill="y")
        self.sidebar_toggle.pack_propagate(False)
        self.sidebar_toggle_lbl = tk.Label(
            self.sidebar_toggle, text="‹", font=("Segoe UI", 12, "bold"),
            cursor="hand2")
        self.track_theme(self.sidebar_toggle_lbl, bg="card", fg="subtext")
        self.sidebar_toggle_lbl.pack(expand=True)
        for w in (self.sidebar_toggle, self.sidebar_toggle_lbl):
            w.bind("<Button-1>", lambda e: self.toggle_sidebar())

        # --- Right side: open-note tab strip + editor panel ---
        right_side = tk.Frame(parent)
        self.track_theme(right_side, bg="bg")
        right_side.pack(side="left", fill="both", expand=True)

        # The tab strip (one tab per open note). Hidden until >1 note is open,
        # so a single-note workflow looks exactly like before. Sits on its own
        # row, visually distinct from the Notes/Calendar/Settings tabs above.
        self.tab_strip = tk.Frame(right_side, height=34)
        self.track_theme(self.tab_strip, bg="sidebar")
        # packed/unpacked dynamically in refresh_tab_strip()

        self.editor_outer = tk.Frame(right_side)
        self.track_theme(self.editor_outer, bg="bg")
        self.editor_outer.pack(side="top", fill="both", expand=True)

        self.editor_canvas = tk.Canvas(self.editor_outer, highlightthickness=0)
        self.track_theme(self.editor_canvas, bg="bg")
        editor_scrollbar = ttk.Scrollbar(self.editor_outer, orient="vertical", command=self.editor_canvas.yview)
        self.editor = tk.Frame(self.editor_canvas)
        self.track_theme(self.editor, bg="bg")

        editor_window = self.editor_canvas.create_window((0, 0), window=self.editor, anchor="nw")
        self._editor_window = editor_window

        def _sync_editor_scroll():
            """Keep the scrollregion correct and prevent the content from
            drifting away from the top when it's shorter than the visible area.
            Without this, scrolling up on a short note (common when the window
            is maximized) leaves a blank gap above the title."""
            if not self._still_alive():
                return
            self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox("all"))
            bbox = self.editor_canvas.bbox(editor_window)
            if not bbox:
                return
            content_h = bbox[3] - bbox[1]
            canvas_h = self.editor_canvas.winfo_height()
            if content_h <= canvas_h:
                self.editor_canvas.yview_moveto(0)

        self._sync_editor_scroll = _sync_editor_scroll

        def _on_editor_configure(event):
            _sync_editor_scroll()

        def _on_editor_canvas_resize(event):
            # Make the inner window at least as tall as the canvas, so short
            # notes fill the height and there's never dead space above them.
            self.editor_canvas.itemconfig(editor_window, width=event.width)
            _sync_editor_scroll()

        self.editor.bind("<Configure>", _on_editor_configure)
        self.editor_canvas.bind("<Configure>", _on_editor_canvas_resize)
        self.editor_canvas.configure(yscrollcommand=editor_scrollbar.set)

        self.editor_canvas.pack(side="left", fill="both", expand=True)
        editor_scrollbar.pack(side="right", fill="y")

        # Shown only when the current note was started from an empty calendar
        # day — lets you jump straight back to that exact month/day instead of
        # hunting for it again. Not packed yet; shown/hidden as a whole by
        # _update_calendar_return_button() so it leaves no empty gap when off.
        self.calendar_return_btn = tk.Button(
            self.editor, text="← Back to Calendar",
            command=self._return_to_calendar, relief="flat", cursor="hand2",
            font=("Segoe UI", 9, "bold")
        )
        self.track_theme(self.calendar_return_btn, bg="bg", fg="accent")

        top_row = tk.Frame(self.editor)
        self.track_theme(top_row, bg="bg")
        top_row.pack(fill="x", padx=30, pady=(25, 5))
        self.editor_top_row = top_row

        self.title_entry = tk.Entry(
            top_row, insertbackground=self.colors["text"],
            relief="flat", font=("Segoe UI", 20, "bold")
        )
        self.track_theme(self.title_entry, bg="bg", fg="text")
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.add_placeholder(self.title_entry, "Note title...")
        self._add_paste_menu(self.title_entry)
        self.title_entry.bind("<KeyRelease>", self._schedule_autosave)

        self.category_var = tk.StringVar(value="General")
        # Keep the button's dot/label in sync whenever the category changes,
        # however it's set (load, template, restore, etc.).
        self.category_var.trace_add(
            "write", lambda *a: self._refresh_category_button_safe())
        # Custom themed dropdown (replaces ttk.Combobox, which can't be fully
        # themed — its popup list stays OS-white). This button shows the current
        # category with a colored bullet and opens an in-theme list on click.
        # Uses plain Labels only (no Canvas) — simpler and more consistent
        # across platforms/DPI settings than mixing widget types.
        self.category_menu = tk.Frame(top_row, bg=self.colors["sidebar"],
                                      highlightthickness=1,
                                      highlightbackground=self.colors["card"])
        self.category_menu.pack(side="right", padx=(10, 0), ipady=4)
        self._cat_dot = tk.Label(self.category_menu, text="●",
                                 bg=self.colors["sidebar"],
                                 fg=CATEGORY_COLORS.get("General", self.colors["accent"]),
                                 font=("Segoe UI", 11))
        self._cat_dot.pack(side="left", padx=(10, 6))
        self._cat_btn_lbl = tk.Label(self.category_menu, textvariable=self.category_var,
                                     bg=self.colors["sidebar"], fg=self.colors["text"],
                                     font=("Segoe UI", 10), anchor="w")
        self._cat_btn_lbl.pack(side="left")
        self._cat_caret = tk.Label(self.category_menu, text=" ▾", bg=self.colors["sidebar"],
                                   fg=self.colors["subtext"], font=("Segoe UI", 9))
        self._cat_caret.pack(side="left", padx=(4, 10))
        self.track_theme(self.category_menu, bg="sidebar")
        self.track_theme(self._cat_btn_lbl, bg="sidebar", fg="text")
        self.track_theme(self._cat_caret, bg="sidebar", fg="subtext")
        for w in (self.category_menu, self._cat_dot, self._cat_btn_lbl, self._cat_caret):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda e: self._open_category_dropdown())
        self._refresh_category_button()

        # --- Metadata row 1: Date + Note color, side by side ---
        # These are short controls, so pairing them on one line keeps the
        # note's properties compact instead of four sparse stacked rows.
        meta_row = tk.Frame(self.editor)
        self.track_theme(meta_row, bg="bg")
        meta_row.pack(fill="x", padx=30, pady=(0, 8))

        date_label = tk.Label(meta_row, text="📅 Date:", font=("Segoe UI", 9, "bold"))
        self.track_theme(date_label, bg="bg", fg="subtext")
        date_label.pack(side="left")

        self.date_entry = tk.Entry(
            meta_row, insertbackground=self.colors["text"],
            relief="flat", font=("Segoe UI", 10), width=11
        )
        self.track_theme(self.date_entry, bg="card", fg="text")
        self.date_entry.pack(side="left", padx=(6, 4), ipady=3)
        self.add_placeholder(self.date_entry, "YYYY-MM-DD")
        # Typing a date directly (as opposed to using the picker popup, which
        # already autosaves via _pick()) previously had no autosave binding
        # at all, so a typed date change could be silently lost.
        self.date_entry.bind("<KeyRelease>", self._schedule_autosave)

        pick_date_btn = tk.Button(
            meta_row, text="📅", command=self.open_date_picker,
            relief="flat", font=("Segoe UI", 9), cursor="hand2"
        )
        self.track_theme(pick_date_btn, bg="sidebar", fg="text")
        pick_date_btn.pack(side="left", padx=(0, 2), ipadx=2)
        self.pick_date_btn = pick_date_btn

        clear_date_btn = tk.Button(
            meta_row, text="✕", command=self.clear_note_date,
            relief="flat", font=("Segoe UI", 8), cursor="hand2"
        )
        self.track_theme(clear_date_btn, bg="sidebar", fg="subtext")
        clear_date_btn.pack(side="left", padx=(0, 20))

        # Note color, on the same row, pushed a bit right of the date controls.
        color_label = tk.Label(meta_row, text="🎨 Color:", font=("Segoe UI", 9, "bold"))
        self.track_theme(color_label, bg="bg", fg="subtext")
        color_label.pack(side="left")

        self.current_note_color = ""  # "" means "use the category's default color"

        self.color_swatch_btn = tk.Button(
            meta_row, text="", width=3, relief="flat", cursor="hand2",
            command=self.open_color_picker
        )
        self.color_swatch_btn.pack(side="left", padx=(6, 6))

        self.color_hint_lbl = tk.Label(meta_row, text="category color", font=("Segoe UI", 8))
        self.track_theme(self.color_hint_lbl, bg="bg", fg="subtext")
        self.color_hint_lbl.pack(side="left")

        self._update_color_swatch()

        # --- Metadata row 2: Repeat (own line — it expands when active) ---
        self.build_recurrence_section(self.editor)

        body_header = tk.Frame(self.editor)
        self.body_header = body_header
        self.track_theme(body_header, bg="bg")
        body_header.pack(fill="x", padx=30, pady=(5, 2))

        body_label = tk.Label(body_header, text="Note", font=("Segoe UI", 9, "bold"), anchor="w")
        self.track_theme(body_label, bg="bg", fg="subtext")
        body_label.pack(side="left")

        self.word_count_lbl = tk.Label(body_header, text="", font=("Segoe UI", 8), anchor="e")
        self.track_theme(self.word_count_lbl, bg="bg", fg="subtext")
        self.word_count_lbl.pack(side="right")

        # --- Formatting toolbar: Bold/Italic/Underline/Strikethrough toggle
        # buttons, applying to the current selection. Requires an active
        # selection (no sticky format-at-cursor in this first version) —
        # see _toggle_body_style. Each button previews its own style in its
        # own label font. ---
        format_bar = tk.Frame(self.editor)
        self.track_theme(format_bar, bg="bg")
        format_bar.pack(fill="x", padx=30, pady=(0, 4))

        self._fmt_buttons = {}
        self._pending_styles = set()  # styles queued up for the next typed char
        self._pending_text_color = None  # hex, or None
        self._pending_highlight_color = None  # hex, or None
        self._pending_style_last_length = 0  # baseline for detecting growth
        style_lbl = tk.Label(format_bar, text="Style", font=("Segoe UI", 8))
        self.track_theme(style_lbl, bg="bg", fg="subtext")
        style_lbl.pack(side="left", padx=(0, 6))
        for style, label, label_font in (
            ("bold", "B", ("Segoe UI", 10, "bold")),
            ("italic", "I", ("Segoe UI", 10, "italic")),
            ("underline", "U", ("Segoe UI", 10, "underline")),
            ("strike", "S", ("Segoe UI", 10, "overstrike")),
        ):
            btn = tk.Button(
                format_bar, text=label, font=label_font, width=3,
                relief="flat", cursor="hand2",
                command=lambda s=style: self._toggle_body_style(s)
            )
            self.track_theme(btn, bg="sidebar", fg="text")
            btn.pack(side="left", padx=(0, 4), ipady=2)
            self._fmt_buttons[style] = btn

        # A thin divider + short label mark the color pickers as their own
        # group, distinct from the four toggle buttons — they work
        # differently (open a picker rather than applying anything
        # directly) and deserve to read that way at a glance, not blend
        # into the row as two more toggle-looking buttons.
        divider = tk.Frame(format_bar, width=1)
        self.track_theme(divider, bg="card")
        divider.pack(side="left", fill="y", padx=(2, 8), pady=2)
        colors_lbl = tk.Label(format_bar, text="Colors", font=("Segoe UI", 8))
        self.track_theme(colors_lbl, bg="bg", fg="subtext")
        colors_lbl.pack(side="left", padx=(0, 6))

        # Text color / Highlight: unlike the four toggle buttons above,
        # these open a swatch picker rather than applying anything
        # directly (there's no single obvious "the" color to toggle).
        # Each button previews the current state as an actual swatch —
        # its own background set to the chosen color, with the "A"/"H"
        # letter's contrast computed to stay legible against it — falling
        # back to the theme's normal button look when nothing is set. See
        # _refresh_format_buttons / _contrasting_fg.
        self.text_color_btn = tk.Button(
            format_bar, text="A", font=("Segoe UI", 10, "bold"), width=3,
            relief="flat", cursor="hand2",
            command=lambda: self._open_color_swatch_popup("text_color")
        )
        self.text_color_btn.pack(side="left", padx=(0, 4), ipady=2)
        self.highlight_btn = tk.Button(
            format_bar, text="H", font=("Segoe UI", 10, "bold"), width=3,
            relief="flat", cursor="hand2",
            command=lambda: self._open_color_swatch_popup("highlight")
        )
        self.highlight_btn.pack(side="left", padx=(0, 4), ipady=2)

        text_frame = tk.Frame(self.editor)
        self.track_theme(text_frame, bg="card")
        text_frame.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        body_sb = ttk.Scrollbar(text_frame, orient="vertical")
        self.body_text = tk.Text(
            text_frame, insertbackground=self.colors["text"],
            relief="flat", font=("Segoe UI", 12), wrap="word", padx=15, pady=15, height=12,
            yscrollcommand=body_sb.set, undo=True, autoseparators=True, maxundo=-1
        )
        body_sb.config(command=self.body_text.yview)
        self.track_theme(self.body_text, bg="card", fg="text")
        body_sb.pack(side="right", fill="y")
        self.body_text.pack(side="left", fill="both", expand=True)
        self._setup_body_formatting_tags(self.body_text)
        self.body_text.bind("<KeyRelease>", self._schedule_autosave)
        self.body_text.bind("<KeyRelease>", self._apply_pending_style_to_typed_char, add="+")
        self.body_text.bind("<KeyRelease>", self._refresh_format_buttons, add="+")
        self.body_text.bind("<ButtonRelease-1>", self._resync_pending_style_anchor, add="+")
        self.body_text.bind("<ButtonRelease-1>", self._refresh_format_buttons, add="+")
        # Overrides Tk's default double-click "select word" so punctuation
        # like "." always breaks a word (and an empty line selects
        # nothing), and its default triple-click "select line" so it stops
        # at the real end of the line instead of overshooting into the
        # trailing newline. The comments box gets the same treatment.
        self._bind_text_selection_fixes(self.body_text)
        # A paste (Ctrl+V, or the right-click menu's synthetic <<Paste>>)
        # must never pick up a pending style — resyncing here, right after
        # the paste's own text lands, means the length-based growth check
        # in _apply_pending_style_to_typed_char sees no NEW growth by the
        # time that KeyRelease callback runs, so it correctly does nothing.
        self.body_text.bind("<<Paste>>", self._resync_pending_style_anchor, add="+")
        # Keyboard shortcuts for the same four toggles as the toolbar/menu.
        # Bound to body_text specifically, not the whole app, so they only
        # fire while actually editing the note body. Each returns "break"
        # to stop Tk's own default handling of the key combo (relevant on
        # some Tk builds/platforms where Ctrl+letter combos have a default
        # Text-widget behavior of their own) from also running.
        for key, style in (
            ("<Control-b>", "bold"), ("<Control-B>", "bold"),
            ("<Control-i>", "italic"), ("<Control-I>", "italic"),
            ("<Control-u>", "underline"), ("<Control-U>", "underline"),
            ("<Control-d>", "strike"), ("<Control-D>", "strike"),
        ):
            self.body_text.bind(key, lambda e, s=style: (self._toggle_body_style(s), "break")[1])
        # Let the mousewheel scroll the text box's own content when it overflows,
        # instead of bubbling up to the editor's outer scroll.
        self._bind_text_wheel(self.body_text)
        # Plain text labels, no decorative glyph prefixes: the styled
        # characters these used to carry (astral math letters, combining
        # underline/strike marks, an emoji) all render at different widths,
        # so the words after them lined up neither with each other nor with
        # the unprefixed Cut/Copy/Paste entries above.
        self._add_paste_menu(self.body_text, extra_items=[
            ("Bold", lambda: self._toggle_body_style("bold"), "Ctrl+B"),
            ("Italic", lambda: self._toggle_body_style("italic"), "Ctrl+I"),
            ("Underline", lambda: self._toggle_body_style("underline"), "Ctrl+U"),
            ("Strikethrough", lambda: self._toggle_body_style("strike"), "Ctrl+D"),
            ("Text color…", lambda: self._open_color_swatch_popup("text_color")),
            ("Highlight…", lambda: self._open_color_swatch_popup("highlight")),
        ])
        self.update_word_count()

        # --- Checklist and Calculator, side by side — each still its own
        # independent collapsible section, just sharing a row instead of
        # each taking the full editor width stacked one above the other.
        # Uses grid() with a shared uniform group, not pack(expand=True):
        # pack only hands out *leftover* space evenly, so two columns with
        # different natural content widths (the calculator's keypad is
        # naturally wider than the checklist) would still end up visibly
        # unequal sizes. grid's uniform option forces them to genuinely
        # equal widths regardless of what's inside each one. ---
        tools_row = tk.Frame(self.editor)
        self.track_theme(tools_row, bg="bg")
        tools_row.pack(fill="x", padx=30, pady=(4, 2))
        tools_row.grid_columnconfigure(0, weight=1, uniform="tools_col")
        tools_row.grid_columnconfigure(1, weight=1, uniform="tools_col")

        checklist_col = tk.Frame(tools_row)
        self.track_theme(checklist_col, bg="bg")
        checklist_col.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        calculator_col = tk.Frame(tools_row)
        self.track_theme(calculator_col, bg="bg")
        calculator_col.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        self.checklist_btn = tk.Button(
            checklist_col, text="☑ Checklist", command=self.toggle_checklist_section,
            relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2", anchor="w"
        )
        self.track_theme(self.checklist_btn, bg="sidebar", fg="text")
        self.checklist_btn.pack(fill="x", ipady=3)

        self.checklist_section = tk.Frame(checklist_col)
        self.track_theme(self.checklist_section, bg="card")
        # Not packed yet — toggled open by the button.
        self._checklist_open = False
        self._build_checklist_section()

        self.calculator_btn = tk.Button(
            calculator_col, text="🧮 Calculator", command=self.toggle_calculator_section,
            relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2", anchor="w"
        )
        self.track_theme(self.calculator_btn, bg="sidebar", fg="text")
        self.calculator_btn.pack(fill="x", ipady=3)

        self.calculator_section = tk.Frame(calculator_col)
        self.track_theme(self.calculator_section, bg="card")
        # Not packed yet — toggled open by the button.
        self._calculator_open = False
        self._build_calculator_section()

        comments_label = tk.Label(
            self.editor, text="💬 Comments / additional notes",
            font=("Segoe UI", 9, "bold"), anchor="w"
        )
        self.track_theme(comments_label, bg="bg", fg="subtext")
        comments_label.pack(fill="x", padx=30, pady=(5, 2))

        comments_frame = tk.Frame(self.editor)
        self.track_theme(comments_frame, bg="card")
        comments_frame.pack(fill="x", padx=30, pady=(0, 10))

        comments_sb = ttk.Scrollbar(comments_frame, orient="vertical")
        self.comments_text = tk.Text(
            comments_frame, insertbackground=self.colors["text"],
            relief="flat", font=("Segoe UI", 11), wrap="word", padx=15, pady=10, height=4,
            yscrollcommand=comments_sb.set, undo=True, autoseparators=True, maxundo=-1
        )
        comments_sb.config(command=self.comments_text.yview)
        self.track_theme(self.comments_text, bg="card", fg="text")
        comments_sb.pack(side="right", fill="y")
        self.comments_text.pack(side="left", fill="both", expand=True)
        self._bind_text_wheel(self.comments_text)
        self._add_paste_menu(self.comments_text)
        self._bind_text_selection_fixes(self.comments_text)
        self.comments_text.bind("<KeyRelease>", self._schedule_autosave)
        # Expand/Collapse toggle for the comments box (compact 4 rows <-> 12).
        self._add_text_resize_toggle(self.editor, self.comments_text,
                                     compact=4, expanded=12,
                                     pack_kwargs={"padx": 30, "pady": (0, 8)})

        # Reliable undo/redo on both editors (Ctrl+Z / Ctrl+Y and Ctrl+Shift+Z).
        for _tw in (self.body_text, self.comments_text):
            _tw.bind("<Control-z>", lambda e, w=_tw: (w.edit_undo(), "break")[1]
                     if self._can_edit_undo(w) else "break")
            _tw.bind("<Control-y>", lambda e, w=_tw: (w.edit_redo(), "break")[1]
                     if self._can_edit_redo(w) else "break")
            _tw.bind("<Control-Shift-Z>", lambda e, w=_tw: (w.edit_redo(), "break")[1]
                     if self._can_edit_redo(w) else "break")

        # Attachments section
        attach_header = tk.Frame(self.editor)
        self.track_theme(attach_header, bg="bg")
        attach_header.pack(fill="x", padx=30, pady=(5, 2))

        attach_label = tk.Label(attach_header, text="📎 Attachments", font=("Segoe UI", 9, "bold"), anchor="w")
        self.track_theme(attach_label, bg="bg", fg="subtext")
        attach_label.pack(side="left")

        add_attach_btn = tk.Button(
            attach_header, text="+ Add file", command=self.add_attachment,
            relief="flat", font=("Segoe UI", 8, "bold"), cursor="hand2"
        )
        self.track_theme(add_attach_btn, bg="accent")
        add_attach_btn.configure(fg="white")
        add_attach_btn.pack(side="right")

        self.current_attachments = []  # list of {"filename": original name, "stored_as": name on disk}

        self.attachments_frame = tk.Frame(self.editor)
        self.track_theme(self.attachments_frame, bg="bg")
        self.attachments_frame.pack(fill="x", padx=30, pady=(0, 10))
        self.refresh_attachments_list()

        action_row = tk.Frame(self.editor)
        self.track_theme(action_row, bg="bg")
        action_row.pack(fill="x", padx=30, pady=(0, 8))

        save_btn = tk.Button(
            action_row, text="💾 Save", command=self.save_current_note,
            fg="white", relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(save_btn, bg="success")

        delete_btn = tk.Button(
            action_row, text="🗑 Delete", command=self.delete_current_note,
            fg="white", relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(delete_btn, bg="danger")

        share_btn = tk.Button(
            action_row, text="📋 Generate code", command=self.share_current_note_as_code,
            fg="white", relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(share_btn, bg="accent")

        duplicate_btn = tk.Button(
            action_row, text="📄 Duplicate", command=self.duplicate_current_note,
            fg="white", relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(duplicate_btn, bg="sidebar")
        duplicate_btn.configure(fg=self.colors["text"])

        template_btn = tk.Button(
            action_row, text="🧩 Save as template",
            command=self.save_current_as_template,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(template_btn, bg="sidebar", fg="text")

        use_template_btn = tk.Button(
            action_row, text="📎 Use template",
            command=self.show_template_picker,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(use_template_btn, bg="sidebar", fg="text")
        self.use_template_btn = use_template_btn

        # Two rows of three in a neat grid. Columns share equal width and the
        # buttons fill their cell, so the two rows line up cleanly regardless of
        # each button's text length.
        grid_buttons = [save_btn, delete_btn, share_btn,
                        duplicate_btn, template_btn, use_template_btn]
        for col in range(3):
            action_row.grid_columnconfigure(col, weight=1, uniform="editbtn")
        for i, btn in enumerate(grid_buttons):
            r, c = divmod(i, 3)
            btn.configure(anchor="center")
            btn.grid(row=r, column=c, sticky="ew", padx=(0, 8), pady=(0, 6), ipady=5)

        # Appears only when the current note has a recoverable previous version
        # (e.g. after text was accidentally deleted and auto-saved).
        self.restore_prev_btn = tk.Button(
            action_row, text="↩ Restore previous", command=self.restore_previous_version,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(self.restore_prev_btn, bg="card", fg="text")
        # Not packed yet — shown by _update_restore_button() when relevant.

        # Status (Created / Last updated) sits on its OWN row below the buttons,
        # so it can never be overlapped when the window is narrow.
        status_row = tk.Frame(self.editor)
        self.track_theme(status_row, bg="bg")
        status_row.pack(fill="x", padx=30, pady=(0, 25))
        self.status_lbl = tk.Label(status_row, text="", font=("Segoe UI", 9), anchor="w")
        self.track_theme(self.status_lbl, bg="bg", fg="subtext")
        self.status_lbl.pack(side="left", fill="x")

        # Inline area where a generated "Copy code" appears (replaces the pop-up).
        self.editor_code_area = tk.Frame(self.editor)
        self.track_theme(self.editor_code_area, bg="bg")
        # packed on demand by share_current_note_as_code()

        self._bind_mousewheel_recursive(
            self.editor, self.editor_canvas,
            skip={self.body_text, self.comments_text})

    # ---------- Settings tab ----------
    def build_settings_tab(self, parent):
        """A calm, scrollable settings page: appearance, categories, and a
        clearly separated backup section. These are all occasional actions,
        so moving them out of the sidebar keeps the notes list front-and-center."""
        outer = tk.Frame(parent)
        self.track_theme(outer, bg="bg")
        outer.pack(fill="both", expand=True)

        # "Back to Notes" lives in its own fixed row, OUTSIDE the scrollable
        # canvas below — packed first with side="top" so it claims its own
        # space and stays visible no matter how far the page underneath is
        # scrolled, instead of being just another row that scrolls away.
        sticky_bar = tk.Frame(outer)
        self.track_theme(sticky_bar, bg="bg")
        sticky_bar.pack(side="top", fill="x")
        back_row = tk.Frame(sticky_bar)
        self.track_theme(back_row, bg="bg")
        back_row.pack(fill="x", padx=40, pady=(20, 0))
        back_btn = tk.Button(
            back_row, text="← Back to Notes", command=self.hide_settings_page,
            relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        self.track_theme(back_btn, bg="card", fg="text")
        back_btn.pack(side="left", ipadx=8, ipady=4)

        canvas = tk.Canvas(outer, highlightthickness=0, bg=self.colors["bg"])
        self.track_theme(canvas, bg="bg")
        self.settings_canvas = canvas  # panels forward scroll here when they don't scroll
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        page = tk.Frame(canvas)
        self.track_theme(page, bg="bg")
        page.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        page_window = canvas.create_window((0, 0), window=page, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(page_window, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Wheel anywhere over the settings page scrolls the page.
        def _page_wheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        canvas.bind("<MouseWheel>", _page_wheel)
        page.bind("<MouseWheel>", _page_wheel)

        # Clicking a non-interactive part of the Settings page (a section
        # title, card background, blank space) should move keyboard focus
        # away from whatever field currently has it — otherwise a field's
        # cursor stays visibly blinking even after its value has already
        # autosaved. Bound once on the whole app rather than on individual
        # labels/frames (every click bubbles up to the toplevel by default
        # unless something along the way stops it, so this reliably catches
        # all of them) — restricted to only act while Settings is actually
        # showing, and only when focus is genuinely on an Entry/Text that
        # isn't the widget that was just clicked.
        def _clear_settings_field_focus(event):
            if not self.settings_page.winfo_ismapped():
                return
            focused = self.focus_get()
            if isinstance(focused, (tk.Entry, tk.Text)) and event.widget is not focused:
                event.widget.focus_set()
        self.bind("<Button-1>", _clear_settings_field_focus, add="+")

        def section(title, subtitle=None):
            head = tk.Frame(page)
            self.track_theme(head, bg="bg")
            head.pack(fill="x", padx=40, pady=(24, 0))
            tk.Label(head, text=title, font=("Segoe UI", 14, "bold"),
                     bg=self.colors["bg"], fg=self.colors["text"], anchor="w"
                     ).pack(fill="x")
            if subtitle:
                tk.Label(head, text=subtitle, font=("Segoe UI", 9),
                         bg=self.colors["bg"], fg=self.colors["subtext"],
                         anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(2, 0))
            card = tk.Frame(page, bg=self.colors["card"])
            self.track_theme(card, bg="card")
            card.pack(fill="x", padx=40, pady=(10, 0))
            return card

        def big_button(parent_frame, text, command, kind="normal"):
            bg = "accent" if kind == "accent" else "sidebar"
            b = tk.Button(parent_frame, text=text, command=command, relief="flat",
                          font=("Segoe UI", 10, "bold"), cursor="hand2",
                          fg="white" if kind == "accent" else self.colors["text"])
            self.track_theme(b, bg=bg)
            if kind == "accent":
                b.configure(fg="white")
            return b

        tk.Label(page, text="⚙  Settings", font=("Segoe UI", 20, "bold"),
                 bg=self.colors["bg"], fg=self.colors["text"], anchor="w"
                 ).pack(fill="x", padx=40, pady=(24, 0))

        # --- Your name (used for the "Hi <name>," greeting) ---
        name_sec = section(
            "Your name",
            "What should we call you? Shows up as a friendly greeting above "
            "your notes — 30 characters max."
        )
        name_row = tk.Frame(name_sec, bg=self.colors["card"])
        name_row.pack(fill="x", padx=16, pady=16)
        self.username_var = tk.StringVar(value=self.load_username())
        # Cap at 30 characters — an unbounded name could look broken in the
        # sidebar greeting. Only limits new typing; an existing longer name
        # (saved before this cap existed) still loads and displays in full.
        USERNAME_MAX_LEN = 30
        name_len_vcmd = (self.register(lambda p: len(p) <= USERNAME_MAX_LEN), "%P")
        name_entry = tk.Entry(
            name_row, textvariable=self.username_var, relief="flat",
            font=("Segoe UI", 10), bg=self.colors["sidebar"], fg=self.colors["text"],
            insertbackground=self.colors["text"],
            validate="key", validatecommand=name_len_vcmd
        )
        name_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self._add_paste_menu(name_entry)

        def save_name():
            if getattr(self, "_username_save_job", None) is not None:
                try:
                    self.after_cancel(self._username_save_job)
                except (tk.TclError, ValueError):
                    pass
                self._username_save_job = None
            if not self._still_alive():
                return
            # Hard safety net: the key-by-key length check above can miss very
            # fast/held-down typing (a known Tk reliability gap under rapid
            # keystrokes), so enforce the limit again here, at the moment of
            # actually saving, regardless of how the field got too long.
            current = self.username_var.get()
            if len(current) > USERNAME_MAX_LEN:
                current = current[:USERNAME_MAX_LEN]
                self.username_var.set(current)
            self.save_username(current)
            self._refresh_greeting()
            self.set_status("Name saved" if current.strip() else "Name cleared")

        def schedule_name_save(event=None):
            # Real-time correction: the per-keystroke block above can miss
            # very fast/held-down typing, so check again on every key
            # release (a plain event binding, not the special validate hook
            # that has the reliability gap) and snap back immediately if it
            # slipped past 30 — rather than letting it grow freely and only
            # fixing it later when the name is actually saved.
            current = self.username_var.get()
            if len(current) > USERNAME_MAX_LEN:
                self.username_var.set(current[:USERNAME_MAX_LEN])
            # Autosave after a short pause, same convention as note editing —
            # so clearing the field and clicking away still saves the change.
            if getattr(self, "_username_save_job", None) is not None:
                try:
                    self.after_cancel(self._username_save_job)
                except (tk.TclError, ValueError):
                    pass
            self._username_save_job = self.after(600, save_name)

        name_entry.bind("<KeyRelease>", schedule_name_save)
        name_entry.bind("<FocusOut>", lambda e: save_name())
        name_entry.bind("<Return>", lambda e: save_name())
        # No separate Save button — the field already autosaves shortly
        # after typing stops, and immediately on Enter or clicking away.

        # --- Appearance ---
        appearance = section("Appearance", "How the app looks.")
        self.theme_toggle_btn = tk.Button(
            appearance,
            text="☀️  Switch to Light mode" if self.theme_name in DARK_THEMES
            else "🌙  Switch to Dark mode",
            command=self.toggle_theme, relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(self.theme_toggle_btn, bg="sidebar", fg="text")
        self.theme_toggle_btn.pack(fill="x", padx=16, pady=(16, 8), ipady=6)

        # Theme picker — pick any color scheme, grouped Dark / Light.
        self.theme_picker_frame = tk.Frame(appearance, bg=self.colors["card"])
        self.track_theme(self.theme_picker_frame, bg="card")
        self.theme_picker_frame.pack(fill="x", padx=16, pady=(0, 16))
        self._build_theme_picker(self.theme_picker_frame)

        # --- Organization: categories ---
        org = section("Organization",
                      "Categories are folders for your notes.")
        big_button(org, "🗂  Manage categories",
                   lambda: self.toggle_settings_panel("categories")
                   ).pack(fill="x", padx=16, pady=(16, 6), ipady=6)
        self.settings_categories_panel = tk.Frame(org, bg=self.colors["card"])
        self.track_theme(self.settings_categories_panel, bg="card")

        big_button(org, "🧩  Manage templates",
                   lambda: self.toggle_settings_panel("templates")
                   ).pack(fill="x", padx=16, pady=(0, 6), ipady=6)
        # Inline panel for templates.
        self.settings_templates_panel = tk.Frame(org, bg=self.colors["card"])
        self.track_theme(self.settings_templates_panel, bg="card")
        # Reserve trailing space under the last button/panel.
        tk.Frame(org, bg=self.colors["card"], height=10).pack(fill="x")

        # --- Backup (deliberately separate: these act on your data) ---
        backup = section("Backup",
                         "Save all your notes to a file, or bring them in from one. "
                         "Use this to move notes between computers.")
        row = tk.Frame(backup, bg=self.colors["card"])
        self.track_theme(row, bg="card")
        row.pack(fill="x", padx=16, pady=16)
        big_button(row, "⬆  Export notes", self.export_data, kind="accent"
                   ).pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=6)
        big_button(row, "⬇  Import notes", self.import_data
                   ).pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=6)

        # --- Trash (recover recently deleted notes) ---
        trash_sec = section("Recently deleted",
                            f"Deleted notes are kept here for {TRASH_RETENTION_DAYS} "
                            "days, then removed automatically. You can restore them "
                            "until then.")
        self.trash_btn = tk.Button(
            trash_sec, text="🗑  Open Recently Deleted",
            command=lambda: self.toggle_settings_panel("trash"),
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(self.trash_btn, bg="sidebar", fg="text")
        self.trash_btn.pack(fill="x", padx=16, pady=(16, 6), ipady=6)
        self.settings_trash_panel = tk.Frame(trash_sec, bg=self.colors["card"])
        self.track_theme(self.settings_trash_panel, bg="card")
        tk.Frame(trash_sec, bg=self.colors["card"], height=10).pack(fill="x")

        # --- Clean up duplicates ---
        dup_sec = section("Clean up duplicates",
                          "Find notes that are exactly identical (same title, "
                          "text, comments, category and date). Tick the "
                          "copies you want to remove; the rest are kept.")
        tk.Button(dup_sec, text="🧹  Find duplicates",
                  command=lambda: self.toggle_settings_panel("duplicates"),
                  relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2",
                  bg=self.colors["sidebar"], fg=self.colors["text"]
                  ).pack(fill="x", padx=16, pady=(16, 6), ipady=6)
        self.settings_duplicates_panel = tk.Frame(dup_sec, bg=self.colors["card"])
        self.track_theme(self.settings_duplicates_panel, bg="card")
        tk.Frame(dup_sec, bg=self.colors["card"], height=10).pack(fill="x")

        # --- Statistics ---
        stats_sec = section("Statistics", "A quick snapshot of your notes.")
        self.stats_frame = tk.Frame(stats_sec, bg=self.colors["card"])
        self.stats_frame.pack(fill="x", padx=16, pady=16)
        self._render_statistics()

        # --- Storage info ---
        info = section("Where your notes are stored")
        tk.Label(info, text=APP_DIR, font=("Consolas", 9),
                 bg=self.colors["card"], fg=self.colors["subtext"],
                 anchor="w", wraplength=560, justify="left"
                 ).pack(fill="x", padx=16, pady=16)

        # --- About / version ---
        about = section("About")
        about_inner = tk.Frame(about, bg=self.colors["card"])
        self.track_theme(about_inner, bg="card")
        about_inner.pack(fill="x", padx=16, pady=16)
        tk.Label(about_inner, text="Notes Organizer", font=("Segoe UI", 11, "bold"),
                 bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                 ).pack(fill="x")
        tk.Label(about_inner, text=f"Version {APP_VERSION}", font=("Segoe UI", 9),
                 bg=self.colors["card"], fg=self.colors["subtext"], anchor="w"
                 ).pack(fill="x", pady=(2, 0))

        tk.Frame(page, bg=self.colors["bg"], height=30).pack()
        self._bind_mousewheel_recursive(page, canvas)

    # ---------- Calendar tab ----------
    def build_calendar_tab(self, parent):
        header = tk.Frame(parent)
        self.track_theme(header, bg="bg")
        header.pack(fill="x", padx=30, pady=(25, 10))

        def nav_button(text, command, side, width=3, font_size=12):
            btn = tk.Button(
                header, text=text, command=command, relief="flat",
                font=("Segoe UI", font_size, "bold"), cursor="hand2", width=width
            )
            self.track_theme(btn, bg="card", fg="text")
            btn.pack(side=side, padx=2)
            return btn

        # ◀◀ / ▶▶ move a whole year, ◀ / ▶ move a month.
        nav_button("◀◀", lambda: self.shift_calendar(years=-1), "left")
        nav_button("◀", lambda: self.shift_calendar(months=-1), "left")

        nav_button("▶▶", lambda: self.shift_calendar(years=1), "right")
        nav_button("▶", lambda: self.shift_calendar(months=1), "right")
        nav_button("Today", self.go_to_today, "right", width=7, font_size=9)

        # The title doubles as a jump target for anything far away.
        self.cal_month_lbl = tk.Button(
            header, text="", command=self.open_month_jump, relief="flat",
            font=("Segoe UI", 16, "bold"), cursor="hand2", borderwidth=0
        )
        self.track_theme(self.cal_month_lbl, bg="bg", fg="text",
                         activebackground="bg", activeforeground="accent")
        self.cal_month_lbl.pack(side="left", expand=True)

        # Everything below the header lives in a scrollable area, so when the
        # window is short (grid + open day panel taller than the viewport) the
        # user can scroll down to reach the panel instead of it being cut off.
        scroll_host = tk.Frame(parent)
        self.track_theme(scroll_host, bg="bg")
        scroll_host.pack(fill="both", expand=True)

        self.cal_scroll_canvas = tk.Canvas(scroll_host, highlightthickness=0, bg=self.colors["bg"])
        self.track_theme(self.cal_scroll_canvas, bg="bg")
        cal_sb = ttk.Scrollbar(scroll_host, orient="vertical", command=self.cal_scroll_canvas.yview)
        self.cal_scroll_canvas.configure(yscrollcommand=cal_sb.set)
        cal_sb.pack(side="right", fill="y")
        self.cal_scroll_canvas.pack(side="left", fill="both", expand=True)

        self.cal_scroll_inner = tk.Frame(self.cal_scroll_canvas)
        self.track_theme(self.cal_scroll_inner, bg="bg")
        self._cal_scroll_win = self.cal_scroll_canvas.create_window(
            (0, 0), window=self.cal_scroll_inner, anchor="nw")

        def _cal_scroll_config(e):
            self.cal_scroll_canvas.configure(scrollregion=self.cal_scroll_canvas.bbox("all"))
        self.cal_scroll_inner.bind("<Configure>", _cal_scroll_config)
        self.cal_scroll_canvas.bind(
            "<Configure>",
            lambda e: self.cal_scroll_canvas.itemconfig(self._cal_scroll_win, width=e.width))
        self._bind_mousewheel_recursive(self.cal_scroll_inner, self.cal_scroll_canvas)

        # Day panel: appears only when a day is selected, at the bottom of the
        # scrollable area. Fixed height; comfortable, not half the page.
        self.day_panel = tk.Frame(self.cal_scroll_inner, height=240)
        self.track_theme(self.day_panel, bg="sidebar")
        self.day_panel.pack_propagate(False)
        self.selected_day = None          # "YYYY-MM-DD" currently shown
        self._day_panel_mode = "empty"    # empty | list | note

        # Grid gets a comfortable minimum height so cells never shrink to
        # unusable slivers; if the window is smaller, the scrollbar kicks in.
        self.cal_grid_frame = tk.Frame(self.cal_scroll_inner, height=520)
        self.track_theme(self.cal_grid_frame, bg="bg")
        self.cal_grid_frame.pack(side="top", fill="both", expand=True, padx=30, pady=(0, 10))
        self.cal_grid_frame.pack_propagate(False)

        # Re-render the calendar when the window crosses the size threshold, so
        # note previews switch between small/large. Guarded so it only fires on
        # an actual step change (not on every pixel), avoiding needless redraws.
        self._cal_last_font_size = None

        def _on_resize(event):
            if getattr(self, "notebook", None) is None:
                return
            if not self._is_calendar_visible():
                return  # only when the Calendar tab is actually showing
            size = self._cal_note_font_size()
            if size != self._cal_last_font_size:
                self._cal_last_font_size = size
                self.render_calendar()
        self.bind("<Configure>", _on_resize, add="+")

        self.bind_all("<Prior>", lambda e: self._calendar_key(e, months=-1))
        self.bind_all("<Next>", lambda e: self._calendar_key(e, months=1))
        self.bind_all("<Control-Prior>", lambda e: self._calendar_key(e, years=-1))
        self.bind_all("<Control-Next>", lambda e: self._calendar_key(e, years=1))
        self.bind_all("<Home>", lambda e: self._calendar_key(e, today=True))

    def _is_calendar_visible(self):
        """True only if the Calendar tab is both selected AND actually on
        screen. The notebook's own idea of 'which tab is selected' doesn't
        change just because the Settings page is currently covering it (they're
        siblings, and showing one doesn't clear the other's selection) — so
        checking the tab index alone isn't enough on its own, or calendar
        keyboard shortcuts and resize-driven relayout could silently act on a
        calendar the user can't currently see, behind the Settings page."""
        try:
            if not self.notebook.winfo_ismapped():
                return False
            return self.notebook.index(self.notebook.select()) == self.TAB_CALENDAR
        except tk.TclError:
            return False

    def _calendar_key(self, event, months=0, years=0, today=False):
        """Keyboard navigation, but only while the Calendar tab is showing and
        the user isn't typing — otherwise PgUp/Home would hijack the editor."""
        if not self._is_calendar_visible():
            return

        # bind_all delivers the key to whichever widget has focus, so the
        # event's own widget is the reliable signal. focus_get() is only a
        # fallback for synthetic calls.
        typing_widgets = (tk.Text, tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox)
        source = getattr(event, "widget", None)
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if any(isinstance(w, typing_widgets) for w in (source, focused)):
            return

        if today:
            self.go_to_today()
        else:
            self.shift_calendar(months=months, years=years)
        return "break"

    def shift_calendar(self, months=0, years=0):
        total = (self.cal_year * 12 + (self.cal_month - 1)) + years * 12 + months
        year, month = total // 12, (total % 12) + 1
        # datetime can't represent anything outside these bounds, and walking
        # past them would crash the grid rather than just look odd.
        if not 1 <= year <= 9999:
            return
        self.cal_year, self.cal_month = year, month
        self.render_calendar()

    def go_to_today(self):
        today = datetime.now()
        self.cal_year, self.cal_month = today.year, today.month
        self.render_calendar()

    def open_month_jump(self):
        """Pick any month/year directly, for destinations that are years away.
        Renders as an in-app dropdown anchored to the month title, not a
        separate window."""
        self._dismiss_mini_popup()
        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])
        outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        frame = tk.Frame(outer, bg=self.colors["card"])
        frame.pack()

        head = tk.Frame(frame, bg=self.colors["card"])
        head.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(
            head, text="Jump to month and year", font=("Segoe UI", 10, "bold"),
            bg=self.colors["card"], fg=self.colors["text"]
        ).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")

        row = tk.Frame(frame, bg=self.colors["card"])
        row.pack(padx=16)

        month_names = list(cal_module.month_name)[1:]
        month_var = tk.StringVar(value=cal_module.month_name[self.cal_month])
        month_menu = self._build_themed_dropdown(
            row, month_var, month_names, on_change=lambda v: None, width_chars=10,
            nested=True)
        month_menu.pack(side="left", padx=(0, 8))

        year_var = tk.StringVar(value=str(self.cal_year))
        year_entry = tk.Entry(
            row, textvariable=year_var, width=6, relief="flat",
            font=("Segoe UI", 10), justify="center",
            bg=self.colors["sidebar"], fg=self.colors["text"],
            insertbackground=self.colors["text"]
        )
        year_entry.pack(side="left", ipady=3)
        year_entry.select_range(0, "end")
        year_entry.focus()

        error_lbl = tk.Label(
            frame, text="", font=("Segoe UI", 8),
            bg=self.colors["card"], fg=self.colors["danger"]
        )
        error_lbl.pack(pady=(6, 0))

        def _go(event=None):
            raw = year_var.get().strip()
            if not raw.isdigit() or not 1 <= int(raw) <= 9999:
                error_lbl.config(text="Enter a year between 1 and 9999")
                return
            self.cal_year = int(raw)
            self.cal_month = month_names.index(month_var.get()) + 1
            self.render_calendar()
            self._dismiss_mini_popup()

        year_entry.bind("<Return>", _go)

        btn_row = tk.Frame(frame, bg=self.colors["card"])
        btn_row.pack(fill="x", padx=16, pady=(10, 14))

        tk.Button(
            btn_row, text="Go", command=_go, bg=self.colors["accent"], fg="white",
            relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2"
        ).pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=5)

        tk.Button(
            btn_row, text="Cancel", command=self._dismiss_mini_popup, bg=self.colors["sidebar"],
            fg=self.colors["text"], relief="flat", font=("Segoe UI", 9), cursor="hand2"
        ).pack(side="left", fill="x", expand=True, padx=(4, 0), ipady=5)

        self._place_dropdown_popup(popup, self.cal_month_lbl)

    def _cal_note_font_size(self):
        """Two-step sizing: bigger note previews in a wide window, smaller in a
        narrow one. Two fixed steps (not continuous) so there's no flicker."""
        try:
            w = self.winfo_width()
        except tk.TclError:
            w = 900
        return 11 if w >= 1150 else 9

    def _build_day_badge(self, cell, date_str, cell_bg, day_color):
        """Draw (or redraw) the small marker-emoji badge in a day cell's
        corner, capped to a handful so it can't sprawl across the cell. The
        resulting Label is stashed on the cell itself (cell._marker_badge) so
        _refresh_day_badge can find and replace just this one badge later,
        without touching anything else in the calendar."""
        old = getattr(cell, "_marker_badge", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
            cell._marker_badge = None

        markers = self.day_emoji.get(date_str) or []
        if not markers:
            return
        shown_markers = markers[:3]
        badge_text = "".join(shown_markers)
        if len(markers) > 3:
            badge_text += f"+{len(markers) - 3}"
        badge = tk.Label(cell, text=badge_text, font=("Segoe UI Emoji", 10),
                         bg=cell_bg if day_color else self.colors["card"])
        badge.place(relx=1.0, rely=0.0, anchor="ne", x=-3, y=3)
        cell._marker_badge = badge

    def _refresh_day_badge(self, date_str):
        """Update just ONE day's marker badge in place — used after saving
        picks from the Mark-this-day popup. Deliberately avoids a full
        render_calendar() call: destroying/rebuilding all ~35-42 day cells for
        a single small change was visibly heavy enough to cause a brief
        flicker/tear, especially right after a popup closes. This touches
        only the one cell that actually changed."""
        cell = getattr(self, "_cal_cell_widgets", {}).get(date_str)
        if cell is None or not cell.winfo_exists():
            # The visible month changed since the popup opened, or the
            # calendar hasn't been rendered yet — nothing to patch in place,
            # a full render will pick it up naturally next time it's shown.
            return
        day_color = self.day_colors.get(date_str)
        cell_bg = day_color if day_color else self.colors["card"]
        self._build_day_badge(cell, date_str, cell_bg, day_color)

    def render_calendar(self):
        if not hasattr(self, "cal_grid_frame"):
            return
        # Tracks date_str -> cell Frame, so a single day's marker badge can be
        # refreshed later (see _refresh_day_badge) without tearing down and
        # rebuilding all ~35-42 day cells just for one small change.
        self._cal_cell_widgets = {}
        for widget in self.cal_grid_frame.winfo_children():
            widget.destroy()

        month_name = cal_module.month_name[self.cal_month]
        # The caret is the only hint that this opens a jump dialog, so it
        # replaces the instruction text that used to sit under the header.
        self.cal_month_lbl.config(text=f"{month_name} {self.cal_year}  ⌄")

        # Expand every note's occurrences across the visible month only.
        # Recurring notes are stored once; their dates are computed here.
        month_start = date_cls(self.cal_year, self.cal_month, 1)
        month_end = date_cls(
            self.cal_year, self.cal_month,
            cal_module.monthrange(self.cal_year, self.cal_month)[1]
        )
        notes_by_date = {}
        for n in self.notes:
            for occurrence in expand_occurrences(n, month_start, month_end):
                notes_by_date.setdefault(occurrence, []).append(n)

        # Direct .configure() calls throughout this function, not
        # self.track_theme(): every cell and everything in it is destroyed
        # and rebuilt from scratch on every render_calendar() call (a save,
        # switching months, ...), so it always picks up the CURRENT theme
        # fresh anyway. track_theme() appends to a list that's never pruned
        # when its widgets are destroyed — with ~40 cells rebuilt on every
        # save over a long session, that added up to a slow, ever-growing list.
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, wd in enumerate(weekdays):
            lbl = tk.Label(self.cal_grid_frame, text=wd, font=("Segoe UI", 9, "bold"),
                           bg=self.colors["bg"], fg=self.colors["subtext"])
            lbl.grid(row=0, column=col, sticky="nsew", pady=(0, 5))
            self.cal_grid_frame.grid_columnconfigure(col, weight=1, uniform="calday")

        today_str = datetime.now().strftime("%Y-%m-%d")
        month_weeks = cal_module.monthcalendar(self.cal_year, self.cal_month)

        for row_idx, week in enumerate(month_weeks, start=1):
            for col_idx, day in enumerate(week):
                if day == 0:
                    continue
                date_str = f"{self.cal_year:04d}-{self.cal_month:02d}-{day:02d}"
                day_notes = notes_by_date.get(date_str, [])
                has_notes = bool(day_notes)
                is_today = date_str == today_str

                cell = tk.Frame(self.cal_grid_frame, cursor="hand2")
                day_color = self.day_colors.get(date_str)
                if day_color:
                    # User painted this day: tint the whole cell.
                    cell.configure(bg=day_color)
                else:
                    cell.configure(bg=self.colors["card"])
                cell.grid(row=row_idx, column=col_idx, sticky="nsew", padx=3, pady=3, ipady=6)
                self._cal_cell_widgets[date_str] = cell

                # Background used for this cell's inner labels (matches a
                # painted day so text doesn't sit on a mismatched patch).
                cell_bg = day_color if day_color else self.colors["card"]
                lbl_fg = "#ffffff" if day_color else self.colors["text"]

                if is_today:
                    # A thin accent-colored top bar marks "today", separate
                    # from category dots so the two don't get confused.
                    today_bar = tk.Frame(cell, height=3, bg=self.colors["accent"])
                    today_bar.pack(fill="x", side="top")

                day_lbl = tk.Label(cell, text=str(day), font=("Segoe UI", 11, "bold" if is_today else "normal"),
                                   bg=cell_bg, fg=lbl_fg)
                day_lbl.pack(pady=(4, 2))

                # Manually-flagged day markers (via right-click > Mark this
                # day) show as a small badge cluster in the cell's corner —
                # visible whether or not the day has any notes.
                self._build_day_badge(cell, date_str, cell_bg, day_color)

                hover_targets = [cell, day_lbl]

                if has_notes:
                    dots_row = tk.Frame(cell, bg=cell_bg)
                    dots_row.pack(pady=(0, 2))
                    seen_colors = []
                    for n in day_notes:
                        c = self.get_note_color(effective_note(n, date_str))
                        if c not in seen_colors:
                            seen_colors.append(c)
                    for dot_color in seen_colors:
                        dot = tk.Label(dots_row, text="●", fg=dot_color, font=("Segoe UI", 9), bg=cell_bg)
                        dot.pack(side="left", padx=1)
                    hover_targets.append(dots_row)

                    # Title previews — show up to 2 note titles at a readable
                    # size (bigger in a wide window), plus a "+N more" line.
                    # A thin divider between them makes it clear where one
                    # note's title ends and the next begins.
                    note_fs = self._cal_note_font_size()
                    max_shown = 2
                    shown_notes = day_notes[:max_shown]
                    for idx, dn in enumerate(shown_notes):
                        eff = effective_note(dn, date_str)
                        full_title = _note_str(eff, "title") or "(untitled)"
                        t = _truncate(full_title, 16)
                        # If the title has an emoji that truncation would cut
                        # off (e.g. it sits near the end of a long title),
                        # surface it up front so it's still recognizable at a
                        # glance instead of silently disappearing.
                        found_emoji = _extract_first_emoji(full_title)
                        if found_emoji and found_emoji not in t:
                            t = f"{found_emoji} {t}"
                        if is_recurring(dn):
                            t = "🔁 " + t
                        chip = tk.Label(cell, text=t, font=("Segoe UI", note_fs),
                                        wraplength=88, justify="left",
                                        bg=cell_bg,
                                        fg=(lbl_fg if day_color else self.colors["text"]))
                        chip.pack(pady=(0, 1), padx=2, anchor="w", fill="x")
                        # Hovering THIS specific title previews just that one
                        # note, not the whole day's notes crammed together.
                        chip.bind("<Button-1>", lambda e, d=date_str: self.open_day_popup(d))
                        chip.bind("<Button-3>",
                                  lambda e, d=date_str: self.show_day_context_menu(e, d))
                        chip.bind("<Enter>",
                                  lambda e, n=dn, d=date_str: self.show_note_hover_preview(n, d))
                        chip.bind("<Leave>", lambda e: self.hide_day_tooltip())
                        # A faint divider line under each chip except the last,
                        # so multiple notes in one cell read as separate items.
                        if idx < len(shown_notes) - 1:
                            divider = tk.Frame(cell, bg=self.colors["subtext"], height=1)
                            divider.pack(fill="x", padx=10, pady=1)
                    if len(day_notes) > max_shown:
                        more = tk.Label(cell, text=f"+{len(day_notes) - max_shown} more",
                                        font=("Segoe UI", max(note_fs - 1, 8), "italic"),
                                        bg=cell_bg,
                                        fg=(lbl_fg if day_color else self.colors["subtext"]))
                        more.pack(pady=(0, 4), anchor="w", padx=2)
                        hover_targets.append(more)
                    else:
                        tk.Frame(cell, height=2, bg=cell_bg).pack()
                else:
                    # Keep row heights consistent whether or not a day has notes
                    spacer = tk.Label(cell, text=" ", font=("Segoe UI", 4), bg=cell_bg)
                    spacer.pack()

                # These targets (cell background, day number, the dot row, and
                # "+N more") show a compact, TITLES-ONLY summary of the day on
                # hover — never full note bodies, so it can't balloon into a
                # huge box even when a day has many notes.
                for widget in hover_targets:
                    widget.bind("<Button-1>", lambda e, d=date_str: self.open_day_popup(d))
                    widget.bind("<Button-3>", lambda e, d=date_str: self.show_day_context_menu(e, d))
                    if has_notes:
                        widget.bind("<Enter>", lambda e, d=date_str: self.show_day_summary_tooltip(d))
                        widget.bind("<Leave>", lambda e: self.hide_day_tooltip())

            # Uniform row height so every week is the same size regardless of
            # how many notes a day holds. "uniform" ties all rows to one size.
            self.cal_grid_frame.grid_rowconfigure(row_idx, weight=1, uniform="calweek", minsize=90)

        # Cells are recreated on every render, so (re)bind the mousewheel across
        # the whole calendar area — otherwise the wheel only works when the
        # cursor is over the scrollbar, not over the day cells.
        if hasattr(self, "cal_scroll_canvas"):
            self._bind_mousewheel_recursive(self.cal_grid_frame, self.cal_scroll_canvas)

    # ---------- Daily reminder bar ----------
    def maybe_show_reminder(self):
        """Show a subtle 'you have notes today' bar — but only once per calendar
        day, and only if there actually are notes due today."""
        if not self._still_alive():
            return
        today = datetime.now().strftime("%Y-%m-%d")
        settings = load_settings()
        if settings.get("reminder_last_shown") == today:
            return  # already shown (or dismissed) today
        due = self.notes_on_date(today)
        if not due:
            return
        # Mark as shown for today so it won't reappear on the next launch.
        settings["reminder_last_shown"] = today
        save_settings(settings)
        self._render_reminder_bar(len(due), today)

    def _render_reminder_bar(self, count, today):
        for w in self.reminder_bar.winfo_children():
            w.destroy()
        self.reminder_bar.pack(fill="x", side="top", before=self.notebook)

        noun = "note" if count == 1 else "notes"
        try:
            friendly = datetime.strptime(today, "%Y-%m-%d").strftime("%A, %B %d")
        except (ValueError, TypeError):
            friendly = today
        msg = tk.Label(
            self.reminder_bar,
            text=f"🔔  You have {count} {noun} for today ({friendly}).",
            bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold"),
            anchor="w", cursor="hand2"
        )
        msg.pack(side="left", padx=14, pady=6)
        # Clicking the text jumps to today's notes in the calendar.
        msg.bind("<Button-1>", lambda e: self._open_today_from_reminder(today))

        close = tk.Label(self.reminder_bar, text="✕", bg=self.colors["accent"],
                         fg="white", font=("Segoe UI", 10, "bold"), cursor="hand2")
        close.pack(side="right", padx=12)
        close.bind("<Button-1>", lambda e: self.dismiss_reminder())

    def _open_today_from_reminder(self, today):
        self.notebook.select(self.TAB_CALENDAR)
        self.open_day_popup(today)

    def dismiss_reminder(self):
        """Hide the reminder bar for the rest of the session."""
        self.reminder_bar.pack_forget()

    def notes_on_date(self, date_str):
        """Every note that lands on this date, recurring ones included."""
        target = parse_date(date_str)
        if target is None:
            return []
        return [n for n in self.notes if expand_occurrences(n, target, target)]

    def show_day_summary_tooltip(self, date_str):
        """Compact, TITLES-ONLY list for hovering the day cell itself (not a
        specific note's chip). Deliberately shows no note bodies — with many
        notes on one day this would otherwise balloon into a huge box, which
        is exactly what this avoids."""
        self.hide_day_tooltip()
        day_notes = self.notes_on_date(date_str)
        if not day_notes:
            return

        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        x = self.winfo_pointerx() + 16
        y = self.winfo_pointery() + 12
        tip.geometry(f"+{x}+{y}")

        outer = tk.Frame(tip, bg=self.colors["accent"], padx=1, pady=1)
        outer.pack()
        container = tk.Frame(outer, bg=self.colors["card"], padx=10, pady=8)
        container.pack()

        try:
            friendly = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %b %d")
        except (ValueError, TypeError):
            friendly = date_str
        tk.Label(container, text=f"{friendly} — {len(day_notes)} note(s)",
                 bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))

        for base_note in day_notes[:10]:  # a title per line is cheap; cap generously
            note = effective_note(base_note, date_str)
            color = self.get_note_color(note)
            row = tk.Frame(container, bg=self.colors["card"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text="●", fg=color, bg=self.colors["card"],
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 5))
            title_text = _truncate(_note_str(note, "title") or "(untitled)", 34)
            if is_recurring(base_note):
                title_text = "🔁 " + title_text
            tk.Label(row, text=title_text, bg=self.colors["card"], fg=self.colors["text"],
                     font=("Segoe UI", 9), anchor="w").pack(side="left")

        if len(day_notes) > 10:
            tk.Label(container, text=f"+{len(day_notes) - 10} more — click to see all",
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(4, 0))

        self._day_tooltip = tip

    def show_note_hover_preview(self, base_note, date_str):
        """Focused preview for hovering ONE specific note's title chip in a
        calendar cell — just that note, not the whole day crammed together."""
        self.hide_day_tooltip()
        note = effective_note(base_note, date_str)
        color = self.get_note_color(note)

        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        x = self.winfo_pointerx() + 16
        y = self.winfo_pointery() + 12
        tip.geometry(f"+{x}+{y}")

        outer = tk.Frame(tip, bg=self.colors["accent"], padx=1, pady=1)
        outer.pack()
        row = tk.Frame(outer, bg=self.colors["card"])
        row.pack()
        stripe = tk.Frame(row, bg=color, width=3)
        stripe.pack(side="left", fill="y")
        inner = tk.Frame(row, bg=self.colors["card"], padx=10, pady=8)
        inner.pack(side="left")

        title_text = _truncate(_note_str(note, "title") or "(untitled)", 60)
        if is_recurring(base_note):
            title_text = "🔁 " + title_text
        tk.Label(inner, text=title_text, bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w", justify="left",
                 wraplength=260).pack(anchor="w")

        if is_recurring(base_note):
            tk.Label(inner, text=describe_recurrence(base_note), bg=self.colors["card"],
                     fg=self.colors["accent"], font=("Segoe UI", 8, "italic"),
                     anchor="w", justify="left").pack(anchor="w")

        preview = _note_str(note, "body").strip()
        if preview:
            if len(preview) > 150:
                preview = preview[:150].strip() + "…"
            tk.Label(inner, text=preview, bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8), anchor="w", justify="left",
                     wraplength=260).pack(anchor="w", pady=(3, 0))

        icons = []
        if note.get("comments"):
            icons.append("💬")
        if note.get("attachments"):
            icons.append(f"📎×{len(note['attachments'])}")
        checklist = note.get("checklist") or []
        if isinstance(checklist, list) and checklist:
            done = sum(1 for it in checklist if isinstance(it, dict) and it.get("done"))
            icons.append(f"☑ {done}/{len(checklist)}")
        if icons:
            tk.Label(inner, text="   ".join(icons), bg=self.colors["card"],
                     fg=self.colors["subtext"], font=("Segoe UI", 8)
                     ).pack(anchor="w", pady=(4, 0))

        self._day_tooltip = tip

    def hide_day_tooltip(self):
        tip = getattr(self, "_day_tooltip", None)
        if tip is not None:
            try:
                if tip.winfo_exists():
                    tip.destroy()
            except tk.TclError:
                pass
            self._day_tooltip = None

    def open_day_popup(self, date_str):
        """Kept name for existing callers, but now shows the day in the inline
        panel (which appears only when a day is selected)."""
        self.hide_day_tooltip()
        self.selected_day = date_str
        self._show_day_panel()
        self.show_day_list()

    def _show_day_panel(self):
        """Make the panel visible below the grid. Deliberately does NOT
        auto-scroll down to it — clicking a date used to yank the view down
        every time, which was disruptive if you were just glancing at the
        month. Scroll down yourself when you're ready to see it."""
        if not self.day_panel.winfo_ismapped():
            self.day_panel.pack(side="bottom", fill="x", padx=30, pady=(0, 20))

    def close_day_panel(self):
        """Hide the panel and give the calendar its full height back."""
        self.selected_day = None
        self._day_panel_mode = "empty"
        self.day_panel.pack_forget()

    def _clear_day_panel(self):
        for w in self.day_panel.winfo_children():
            w.destroy()

    def _render_day_panel_empty(self):
        self._clear_day_panel()
        self._day_panel_mode = "empty"

    def show_day_list(self):
        """Show the selected day's notes as a scrollable list inside the panel."""
        if not self.selected_day:
            self._render_day_panel_empty()
            return
        self._clear_day_panel()
        self._day_panel_mode = "list"
        date_str = self.selected_day

        try:
            friendly = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        except (ValueError, TypeError):
            friendly = str(date_str)

        header = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        header.pack(fill="x", padx=15, pady=(10, 6))
        tk.Label(header, text=friendly, font=("Segoe UI", 12, "bold"),
                 bg=self.colors["sidebar"], fg=self.colors["text"], anchor="w"
                 ).pack(side="left")
        tk.Button(header, text="✕", command=self.close_day_panel,
                  bg=self.colors["sidebar"], fg=self.colors["subtext"], relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2"
                  ).pack(side="right", padx=(6, 0))
        tk.Button(header, text="+ Add note", command=lambda: self._add_note_for_date(date_str),
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=8, ipady=2)

        # Scrollable list area.
        body = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        body.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        canvas = tk.Canvas(body, bg=self.colors["sidebar"], highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["sidebar"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        day_notes = self.notes_on_date(date_str)
        if not day_notes:
            tk.Label(inner, text="No notes for this day yet.",
                     bg=self.colors["sidebar"], fg=self.colors["subtext"],
                     font=("Segoe UI", 10)).pack(pady=10)
            self._bind_mousewheel_recursive(inner, canvas)
            return

        for base_note in day_notes:
            note = effective_note(base_note, date_str)
            color = self.get_note_color(note)
            row = tk.Frame(inner, bg=self.colors["card"], cursor="hand2")
            row.pack(fill="x", pady=3)
            stripe = tk.Frame(row, bg=color, width=4)
            stripe.pack(side="left", fill="y")

            del_btn = tk.Button(
                row, text="🗑", relief="flat", cursor="hand2", bd=0,
                bg=self.colors["card"], fg=self.colors["subtext"], font=("Segoe UI", 10),
                command=lambda n=base_note, d=date_str: self._delete_note_from_calendar(n, d)
            )
            del_btn.pack(side="right", padx=(0, 8))

            title_text = _note_str(note, "title") or "(untitled)"
            if is_recurring(base_note):
                title_text = "🔁 " + title_text
            icons = ""
            if note.get("comments"):
                icons += "  💬"
            if note.get("attachments"):
                icons += f"  📎×{len(note['attachments'])}"
            lbl = tk.Label(row, text=title_text + icons, bg=self.colors["card"],
                           fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            def _open(e, n=base_note, d=date_str):
                self.show_day_note(n, d)

            def _context(e, n=base_note, d=date_str):
                self.show_note_context_menu(e, n, occurrence_date=d)

            for w in (row, stripe, lbl):
                w.bind("<Button-1>", _open)
                w.bind("<Button-3>", _context)

        # Bind the wheel now that every note row exists.
        self._bind_mousewheel_recursive(inner, canvas)

    def show_day_note(self, base_note, date_str):
        """Open a single note inside the day panel, with a Back button that
        returns to the day's note list."""
        self._clear_day_panel()
        self._day_panel_mode = "note"
        note = effective_note(base_note, date_str)

        top = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        top.pack(fill="x", padx=15, pady=(10, 6))
        tk.Button(top, text="← Back", command=self.show_day_list,
                  bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", ipadx=6, ipady=2)
        tk.Button(top, text="✏ Open in editor",
                  command=lambda: self._open_note_from_calendar(base_note, date_str),
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=6, ipady=2)
        tk.Button(top, text="🗑 Delete",
                  command=lambda: self._delete_note_from_calendar(base_note, date_str),
                  bg=self.colors["danger"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)

        title = _note_str(note, "title").strip() or "(untitled)"
        tk.Label(self.day_panel, text=title, font=("Segoe UI", 12, "bold"),
                 bg=self.colors["sidebar"], fg=self.colors["text"], anchor="w",
                 wraplength=700, justify="left").pack(fill="x", padx=15, pady=(2, 4))

        body = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        body.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        txt_sb = ttk.Scrollbar(body, orient="vertical")
        txt = tk.Text(body, wrap="word", relief="flat", font=("Segoe UI", 10),
                      bg=self.colors["card"], fg=self.colors["text"], padx=10, pady=10,
                      yscrollcommand=txt_sb.set)
        txt_sb.config(command=txt.yview)
        txt_sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        content = _note_str(note, "body") or "(empty note)"
        if note.get("comments"):
            content += f"\n\n— Comments —\n{note['comments']}"
        txt.insert("1.0", content)
        txt.config(state="disabled")

    def _delete_note_from_calendar(self, note, date_str):
        """Delete a note from within the calendar day panel (list or detail
        view). Only refreshes the panel if the note actually stopped
        occurring on this date — if the user cancels the confirmation (or,
        for a recurring note, cancels the occurrence-scope prompt), the
        current view is left exactly as it was, rather than always bouncing
        back to the list regardless of what was chosen."""
        self._context_delete_note(note, date_str)
        still_here = any(n["id"] == note["id"] for n in self.notes_on_date(date_str))
        if not still_here:
            self.refresh_day_panel()

    def refresh_day_panel(self):
        """Re-render whatever the panel is currently showing (after edits/deletes)."""
        if getattr(self, "_day_panel_mode", "empty") == "list":
            self.show_day_list()
        elif self._day_panel_mode == "note":
            # Fall back to the list — the note may have changed or been deleted.
            self.show_day_list()

    def _open_note_from_calendar(self, base_note, date_str):
        """Open an EXISTING note (not a new one) from the calendar day panel.
        Same 'remember where we came from' treatment as creating a note there —
        open_note_in_tab clears any pending return first (it's meant to, for
        the normal case of switching between notes), so we set it again right
        after, once that's done."""
        remembered = {"year": self.cal_year, "month": self.cal_month, "date_str": date_str}
        self.notebook.select(self.TAB_NOTES)
        self.open_note_in_tab(base_note, occurrence_date=date_str)
        self._pending_calendar_return = remembered
        self._update_calendar_return_button()

    def _add_note_for_date(self, date_str):
        """Start a new note pre-filled with this date. Editing still happens on
        the Notes tab (the editor lives there), but we remember where we came
        from in the calendar so saving (or 'Back to Calendar') returns you to
        the exact same month/day — it shouldn't feel like being sent away."""
        self._pending_calendar_return = {
            "year": self.cal_year, "month": self.cal_month, "date_str": date_str,
        }
        self.notebook.select(self.TAB_NOTES)
        self.new_note()
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date_str)
        self.date_entry.config(fg=self.colors["text"])
        self.title_entry.focus()
        self._update_calendar_return_button()

    def _return_to_calendar(self):
        """Jump back to the exact month/day the user was viewing before they
        started creating a note from the calendar."""
        info = getattr(self, "_pending_calendar_return", None)
        self._pending_calendar_return = None
        if hasattr(self, "calendar_return_btn"):
            self.calendar_return_btn.pack_forget()
        if not info:
            self.notebook.select(self.TAB_CALENDAR)
            return
        self.cal_year, self.cal_month = info["year"], info["month"]
        self.notebook.select(self.TAB_CALENDAR)
        self.render_calendar()
        if info.get("date_str"):
            self.open_day_popup(info["date_str"])

    def _update_calendar_return_button(self):
        """Show/hide the small 'Back to Calendar' link in the editor, only
        while there's a pending calendar-originated note to return to."""
        if not hasattr(self, "calendar_return_btn") or not hasattr(self, "editor_top_row"):
            return
        if getattr(self, "_pending_calendar_return", None):
            if not self.calendar_return_btn.winfo_ismapped():
                self.calendar_return_btn.pack(fill="x", padx=30, pady=(14, 0),
                                              anchor="w", before=self.editor_top_row)
        else:
            self.calendar_return_btn.pack_forget()

    def add_attachment(self):
        filepaths = filedialog.askopenfilenames(title="Choose file(s) to attach")
        if not filepaths:
            return
        added_any = False
        for src_path in filepaths:
            original_name = os.path.basename(src_path)
            unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{original_name}"
            dest_path = os.path.join(ATTACHMENTS_DIR, unique_name)
            try:
                shutil.copy2(src_path, dest_path)
            except (IOError, OSError) as e:
                self.show_error("Couldn't attach file", f"Failed to attach '{original_name}':\n{e}")
                continue
            self.current_attachments.append({"filename": original_name, "stored_as": unique_name})
            added_any = True
        self.refresh_attachments_list()
        if added_any:
            self._schedule_autosave()

    def remove_attachment(self, index):
        if 0 <= index < len(self.current_attachments):
            removed = self.current_attachments.pop(index)
            _delete_attachment_files([{"attachments": [removed]}])
            self.refresh_attachments_list()
            self._schedule_autosave()

    # File extensions Windows will execute (or run scripts from) rather than
    # just open in a viewer. Opening one runs code, so we warn first.
    DANGEROUS_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".msi", ".msp",
        ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta",
        ".cpl", ".jar", ".reg", ".ps2", ".msc", ".gadget",
    }

    def open_attachment(self, index):
        if 0 <= index < len(self.current_attachments):
            attachment = self.current_attachments[index]
            path = os.path.join(ATTACHMENTS_DIR, attachment["stored_as"])
            if not os.path.exists(path):
                self.show_warning("File missing", "This attached file can't be found on disk.")
                return

            original_name = attachment.get("filename", attachment["stored_as"])
            ext = os.path.splitext(original_name)[1].lower()

            # Pillow decodes all of these — shown large, right in the app,
            # instead of handing off to whatever image viewer Windows has
            # associated with the file type. Anything else still opens
            # externally below.
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
                self._show_image_preview(path, original_name)
                return

            # Warn before opening anything Windows would execute as a program
            # or script — opening it runs code, not just views a file.
            if ext in self.DANGEROUS_EXTENSIONS:
                proceed = self.ask_yes_no(
                    "⚠ Potentially unsafe file",
                    f"“{original_name}” is a type of file that can run programs "
                    "or commands on your computer.\n\n"
                    "Only open it if you completely trust where it came from. "
                    "Opening an unsafe file can harm your computer.\n\n"
                    "Open it anyway?",
                    icon="warning", default="no"
                )
                if not proceed:
                    return

            try:
                os.startfile(path)  # Windows-only, matches this app's target platform
            except (AttributeError, OSError):
                self.show_info("Can't open automatically", f"File is located at:\n{path}")

    def _show_image_preview(self, path, filename):
        """A large, in-app image preview — most of the window, not a tiny
        thumbnail and not handed off to an external program. Uses Pillow
        (not plain Tk) for two reasons: plain Tk only decodes PNG/GIF, and
        for animated GIFs it only ever shows each frame's own raw pixels at
        that frame's own size — many GIFs only store the part of the frame
        that CHANGED from the previous one, at whatever size that patch
        happens to be, relying on the viewer to composite it onto a fixed
        canvas in the right place. Plain Tk doesn't do that compositing, so
        the image visibly jumped and resized itself every frame. Pillow
        handles this correctly and gives real per-frame timing too, instead
        of a guessed fixed delay."""
        try:
            pil_img = Image.open(path)
        except Exception:
            self.show_warning("Can't preview this file",
                             "This file couldn't be read as an image.")
            return

        self.update_idletasks()
        target_w = max(int(self.winfo_width() * 0.7), 200)
        target_h = max(int(self.winfo_height() * 0.7), 200)

        def _scaled(frame):
            w, h = frame.size
            if w > target_w or h > target_h:
                frame = frame.copy()
                frame.thumbnail((target_w, target_h), Image.LANCZOS)
            elif w > 0 and h > 0 and w < target_w * 0.6 and h < target_h * 0.6:
                # Small image, room to spare — enlarge so it's actually easy
                # to see. Capped so a tiny icon doesn't get blown up absurdly
                # large just because the window happens to be big.
                scale = min(min(target_w / w, target_h / h), 8)
                frame = frame.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                                     Image.LANCZOS)
            return frame

        frames = []
        delays = []
        if getattr(pil_img, "is_animated", False):
            for i in range(pil_img.n_frames):
                pil_img.seek(i)
                # Pillow composites disposal-method-aware frames onto the
                # right canvas internally as you seek — converting to RGBA
                # here is what actually captures that composited result,
                # not just this frame's own raw (possibly partial) pixels.
                frame = _scaled(pil_img.convert("RGBA"))
                frames.append(ImageTk.PhotoImage(frame))
                delays.append(pil_img.info.get("duration", 100) or 100)
        else:
            frame = _scaled(pil_img.convert("RGBA"))
            frames = [ImageTk.PhotoImage(frame)]
            delays = [100]

        self._dismiss_mini_popup()
        overlay = tk.Frame(self, bg=self.colors["bg"], highlightthickness=1,
                           highlightbackground=self.colors["accent"])
        self._image_preview_ref = frames  # keep alive — see refresh_attachments_list
        self._mini_popup = overlay

        header = tk.Frame(overlay, bg=self.colors["bg"])
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(header, text=filename, font=("Segoe UI", 10, "bold"),
                 bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")
        tk.Button(header, text="✕ Close", command=self._dismiss_mini_popup,
                  relief="flat", cursor="hand2", bg=self.colors["card"],
                  fg=self.colors["text"], font=("Segoe UI", 9)
                  ).pack(side="right", ipadx=6, ipady=2)
        tk.Button(header, text="Open externally",
                  command=lambda: (self._dismiss_mini_popup(), self._open_externally(path)),
                  relief="flat", cursor="hand2", bg=self.colors["accent"],
                  fg="white", font=("Segoe UI", 9)
                  ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)

        img_lbl = tk.Label(overlay, image=frames[0], bg=self.colors["bg"])
        img_lbl.pack(padx=16, pady=(4, 16))

        self._gif_anim_job = None  # explicit even for the single-frame case,
        # so this attribute always exists after this function runs, not just
        # when an animation actually starts — any code checking it directly
        # (rather than via getattr with a default) can rely on that.
        if len(frames) > 1:
            state = {"i": 0}

            def _next_frame():
                if not img_lbl.winfo_exists():
                    return
                state["i"] = (state["i"] + 1) % len(frames)
                img_lbl.configure(image=frames[state["i"]])
                self._gif_anim_job = self.after(delays[state["i"]], _next_frame)

            self._gif_anim_job = self.after(delays[0], _next_frame)

        overlay.place(relx=0.5, rely=0.5, anchor="center")
        overlay.lift()
        # Click-outside-to-dismiss, matching every other in-app overlay —
        # bound on a short delay so the click that OPENED this preview isn't
        # also immediately seen as a click "outside" it.
        def _bind_click_outside():
            if not self._still_alive():
                return
            self._mini_popup_click_bind = self.bind(
                "<Button-1>", self._maybe_dismiss_mini_popup, add="+")
        self.after(50, _bind_click_outside)

    def _open_externally(self, path):
        """Hand a file off to whatever program Windows has associated with
        it — the plain, no-preview fallback used for file types this app
        can't show inline itself."""
        try:
            os.startfile(path)
        except (AttributeError, OSError):
            self.show_info("Can't open automatically", f"File is located at:\n{path}")

    def refresh_attachments_list(self):
        # Direct .configure() calls, not self.track_theme(): this list is
        # destroyed and rebuilt on every note switch (load_note runs this
        # every single time you open a different note), so it always picks
        # up the current theme fresh anyway. Same leak as the note list and
        # calendar had — track_theme() never prunes entries for widgets that
        # get destroyed, so this ran up fast given how often switching notes
        # happens in a normal session.
        for widget in self.attachments_frame.winfo_children():
            widget.destroy()

        if not self.current_attachments:
            empty_lbl = tk.Label(self.attachments_frame, text="No files attached.",
                                  font=("Segoe UI", 8), anchor="w",
                                  bg=self.colors["bg"], fg=self.colors["subtext"])
            empty_lbl.pack(fill="x")
            return

        for i, att in enumerate(self.current_attachments):
            ext = os.path.splitext(att["filename"])[1].lower()
            icon = "🖼️" if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp") else "📄"
            can_preview_inline = ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

            row = tk.Frame(self.attachments_frame, bg=self.colors["card"])
            row.pack(fill="x", pady=2)

            top_row = tk.Frame(row, bg=self.colors["card"])
            top_row.pack(fill="x")

            name_lbl = tk.Label(top_row, text=f"{icon} {att['filename']}", font=("Segoe UI", 9),
                                 anchor="w", cursor="hand2",
                                 bg=self.colors["card"], fg=self.colors["text"])
            name_lbl.pack(side="left", fill="x", expand=True, padx=8, pady=4)
            name_lbl.bind("<Button-1>", lambda e, idx=i: self.open_attachment(idx))

            remove_btn = tk.Button(
                top_row, text="✕", command=lambda idx=i: self.remove_attachment(idx),
                relief="flat", font=("Segoe UI", 8), cursor="hand2", width=2,
                bg=self.colors["danger"], fg="white"
            )
            remove_btn.pack(side="right", padx=4, pady=2)

            if not can_preview_inline:
                # Common image formats show large, right in the app (see
                # _show_image_preview) — everything else still opens in
                # whatever program the system has for that file type. Said
                # generically on purpose, since the app can't know for sure
                # which program that'll actually be (varies per computer).
                hint_lbl = tk.Label(row, text="Opens in your default app for this file type",
                                    font=("Segoe UI", 7), anchor="w",
                                    bg=self.colors["card"], fg=self.colors["subtext"])
                hint_lbl.pack(fill="x", padx=(28, 8), pady=(0, 4))

    def _update_color_swatch(self):
        if self.current_note_color:
            self.color_swatch_btn.config(bg=self.current_note_color, activebackground=self.current_note_color)
            self.color_hint_lbl.config(text=self.current_note_color)
        else:
            default_color = CATEGORY_COLORS.get(self.category_var.get(), self.colors["accent"])
            self.color_swatch_btn.config(bg=default_color, activebackground=default_color)
            self.color_hint_lbl.config(text="category color")

    def open_color_picker(self):
        """Pick this note's own color from a curated palette. Renders as an
        in-app dropdown anchored to the color swatch button, not a separate
        window. Swatches only, no hex-code entry -- most users don't think
        in hex, so the palette is the whole picker."""
        self._dismiss_mini_popup()
        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])
        outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        body = tk.Frame(outer, bg=self.colors["card"])
        body.pack()

        label = tk.Label(body, text="Pick a color for this note", font=("Segoe UI", 10, "bold"),
                          bg=self.colors["card"], fg=self.colors["text"])
        label.pack(padx=15, pady=(12, 8))

        swatch_grid = tk.Frame(body, bg=self.colors["card"])
        swatch_grid.pack(padx=15)

        def _choose(color):
            self.current_note_color = color
            self._update_color_swatch()
            self._schedule_autosave()
            self._dismiss_mini_popup()

        for i, hex_color in enumerate(PRESET_NOTE_COLORS):
            swatch = tk.Button(
                swatch_grid, bg=hex_color, activebackground=hex_color, width=3, height=1,
                relief="flat", cursor="hand2", command=lambda c=hex_color: _choose(c)
            )
            swatch.grid(row=i // 5, column=i % 5, padx=4, pady=4)

        button_row = tk.Frame(body, bg=self.colors["card"])
        button_row.pack(fill="x", padx=15, pady=(8, 14))

        reset_btn = tk.Button(
            button_row, text="Reset to category", command=lambda: _choose(""), relief="flat",
            bg=self.colors["sidebar"], fg=self.colors["text"], cursor="hand2", font=("Segoe UI", 9)
        )
        reset_btn.pack(fill="x", ipady=5)

        self._place_dropdown_popup(popup, self.color_swatch_btn)

    def clear_note_date(self):
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, "YYYY-MM-DD")
        self.date_entry.config(fg=self.colors["subtext"])

    def open_date_picker(self, target_entry=None, anchor_widget=None):
        """Small calendar dropdown for picking a date, anchored to whichever
        button opened it — not a separate window. Reusable: pass a different
        target_entry/anchor_widget to use this for any date field (e.g. the
        recurrence 'Ends: On date' field), or call with no args for the main
        note Date field."""
        target_entry = target_entry or self.date_entry
        anchor_widget = anchor_widget or self.pick_date_btn

        current_val = target_entry.get().strip()
        try:
            start_date = datetime.strptime(current_val, "%Y-%m-%d")
        except ValueError:
            start_date = datetime.now()

        self._dismiss_mini_popup()
        picker = tk.Toplevel(self)
        self._mini_popup = picker
        picker.wm_overrideredirect(True)
        picker.configure(bg=self.colors["accent"])
        outer = tk.Frame(picker, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        pop_body = tk.Frame(outer, bg=self.colors["card"])
        pop_body.pack()

        state = {"year": start_date.year, "month": start_date.month}

        header = tk.Frame(pop_body, bg=self.colors["card"])
        header.pack(fill="x", padx=10, pady=(10, 5))

        prev_btn = tk.Button(header, text="◀", relief="flat", font=("Segoe UI", 10, "bold"),
                              bg=self.colors["sidebar"], fg=self.colors["text"], cursor="hand2", width=3)
        prev_btn.pack(side="left")

        month_lbl = tk.Label(header, text="", font=("Segoe UI", 12, "bold"),
                              bg=self.colors["card"], fg=self.colors["text"])
        month_lbl.pack(side="left", expand=True)

        next_btn = tk.Button(header, text="▶", relief="flat", font=("Segoe UI", 10, "bold"),
                              bg=self.colors["sidebar"], fg=self.colors["text"], cursor="hand2", width=3)
        next_btn.pack(side="right")

        grid_frame = tk.Frame(pop_body, bg=self.colors["card"])
        grid_frame.pack(padx=10, pady=(0, 10))

        def _pick(date_str):
            target_entry.delete(0, "end")
            target_entry.insert(0, date_str)
            target_entry.config(fg=self.colors["text"])
            self._schedule_autosave()
            self._dismiss_mini_popup()

        def _render():
            for w in grid_frame.winfo_children():
                w.destroy()
            month_lbl.config(text=f"{cal_module.month_name[state['month']]} {state['year']}")

            for col, wd in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
                lbl = tk.Label(grid_frame, text=wd, font=("Segoe UI", 8, "bold"),
                                bg=self.colors["card"], fg=self.colors["subtext"], width=4)
                lbl.grid(row=0, column=col, pady=(0, 4))

            weeks = cal_module.monthcalendar(state["year"], state["month"])
            for r, week in enumerate(weeks, start=1):
                for c, day in enumerate(week):
                    if day == 0:
                        continue
                    date_str = f"{state['year']:04d}-{state['month']:02d}-{day:02d}"
                    is_selected = date_str == current_val
                    btn = tk.Button(
                        grid_frame, text=str(day), width=4, relief="flat",
                        font=("Segoe UI", 9, "bold" if is_selected else "normal"),
                        bg=(self.colors["accent"] if is_selected else self.colors["sidebar"]),
                        fg=("white" if is_selected else self.colors["text"]),
                        cursor="hand2", command=lambda d=date_str: _pick(d)
                    )
                    btn.grid(row=r, column=c, padx=1, pady=1)

        def _prev():
            state["month"] -= 1
            if state["month"] < 1:
                state["month"] = 12
                state["year"] -= 1
            _render()

        def _next():
            state["month"] += 1
            if state["month"] > 12:
                state["month"] = 1
                state["year"] += 1
            _render()

        prev_btn.config(command=_prev)
        next_btn.config(command=_next)
        _render()
        self._place_dropdown_popup(picker, anchor_widget)

    # ---------- Recurrence editor ----------
    def build_recurrence_section(self, parent):
        """The repeat controls. Sub-rows appear only when they're relevant to
        the chosen frequency, so the panel stays readable."""
        self.rec_weekday_state = [False] * 7

        freq_row = tk.Frame(parent)
        self.track_theme(freq_row, bg="bg")
        freq_row.pack(fill="x", padx=30, pady=(0, 6))

        freq_label = tk.Label(freq_row, text="🔁 Repeat:", font=("Segoe UI", 9, "bold"))
        self.track_theme(freq_label, bg="bg", fg="subtext")
        freq_label.pack(side="left")

        self.rec_freq_var = tk.StringVar(value=FREQ_LABELS[""])
        freq_menu = self._build_themed_dropdown(
            freq_row, self.rec_freq_var,
            [FREQ_LABELS[k] for k in ("", "daily", "weekly", "monthly", "yearly")],
            on_change=lambda v: self.on_recurrence_changed(), width_chars=14)
        freq_menu.pack(side="left", padx=(8, 10))
        self.rec_freq_menu = freq_menu

        self.rec_summary_lbl = tk.Label(freq_row, text="", font=("Segoe UI", 8, "italic"))
        self.track_theme(self.rec_summary_lbl, bg="bg", fg="accent")
        self.rec_summary_lbl.pack(side="left")

        # --- Everything below is hidden unless a frequency is chosen ---
        # The frame is packed once, here, so it always keeps its slot in the
        # editor. Showing/hiding is done by packing its CHILDREN, otherwise
        # re-showing it would drop it at the bottom of the panel.
        # The details frame is packed ONLY when a frequency is chosen (see
        # on_recurrence_changed). Leaving it packed while empty is what used to
        # reserve a blank gap between Repeat and the Note body section.
        self.rec_details = tk.Frame(parent)
        self.track_theme(self.rec_details, bg="bg")

        # Interval
        self.rec_interval_row = tk.Frame(self.rec_details)
        self.track_theme(self.rec_interval_row, bg="bg")
        interval_row = self.rec_interval_row

        every_lbl = tk.Label(interval_row, text="Every", font=("Segoe UI", 9))
        self.track_theme(every_lbl, bg="bg", fg="subtext")
        every_lbl.pack(side="left")

        self.rec_interval_var = tk.StringVar(value="1")
        interval_entry = tk.Entry(
            interval_row, textvariable=self.rec_interval_var, width=4,
            relief="flat", font=("Segoe UI", 9), justify="center",
            insertbackground=self.colors["text"]
        )
        self.track_theme(interval_entry, bg="card", fg="text")
        interval_entry.pack(side="left", padx=6, ipady=2)
        self.rec_interval_var.trace_add("write", lambda *a: self.update_recurrence_summary())

        self.rec_unit_lbl = tk.Label(interval_row, text="day(s)", font=("Segoe UI", 9))
        self.track_theme(self.rec_unit_lbl, bg="bg", fg="subtext")
        self.rec_unit_lbl.pack(side="left")

        # Weekly: which weekdays
        self.rec_weekday_row = tk.Frame(self.rec_details)
        self.track_theme(self.rec_weekday_row, bg="bg")

        on_lbl = tk.Label(self.rec_weekday_row, text="On:", font=("Segoe UI", 9))
        self.track_theme(on_lbl, bg="bg", fg="subtext")
        on_lbl.pack(side="left", padx=(0, 6))

        self.rec_weekday_btns = []
        for index, name in enumerate(WEEKDAY_NAMES):
            btn = tk.Button(
                self.rec_weekday_row, text=name, width=4, relief="flat",
                font=("Segoe UI", 8, "bold"), cursor="hand2",
                command=lambda i=index: self.toggle_weekday(i)
            )
            btn.pack(side="left", padx=1)
            self.rec_weekday_btns.append(btn)

        # Monthly: which days of the month
        self.rec_monthday_row = tk.Frame(self.rec_details)
        self.track_theme(self.rec_monthday_row, bg="bg")

        md_lbl = tk.Label(self.rec_monthday_row, text="On day(s):", font=("Segoe UI", 9))
        self.track_theme(md_lbl, bg="bg", fg="subtext")
        md_lbl.pack(side="left", padx=(0, 6))

        self.rec_monthdays_var = tk.StringVar(value="")
        monthdays_entry = tk.Entry(
            self.rec_monthday_row, textvariable=self.rec_monthdays_var, width=14,
            relief="flat", font=("Segoe UI", 9), insertbackground=self.colors["text"]
        )
        self.track_theme(monthdays_entry, bg="card", fg="text")
        monthdays_entry.pack(side="left", ipady=2)
        self.rec_monthdays_var.trace_add("write", lambda *a: self.update_recurrence_summary())

        md_hint = tk.Label(
            self.rec_monthday_row, text="e.g. 1, 15   (blank = same day as the start date)",
            font=("Segoe UI", 8)
        )
        self.track_theme(md_hint, bg="bg", fg="subtext")
        md_hint.pack(side="left", padx=(8, 0))

        # Short-month policy (monthly + yearly)
        self.rec_policy_row = tk.Frame(self.rec_details)
        self.track_theme(self.rec_policy_row, bg="bg")

        policy_lbl = tk.Label(self.rec_policy_row, text="If the month is too short:", font=("Segoe UI", 9))
        self.track_theme(policy_lbl, bg="bg", fg="subtext")
        policy_lbl.pack(side="left", padx=(0, 6))

        self.rec_policy_var = tk.StringVar(value="Use the last day")
        policy_menu = self._build_themed_dropdown(
            self.rec_policy_row, self.rec_policy_var,
            ["Use the last day", "Skip that month"],
            on_change=lambda v: self.update_recurrence_summary(), width_chars=16)
        policy_menu.pack(side="left")

        # End condition
        self.rec_end_row = tk.Frame(self.rec_details)
        self.track_theme(self.rec_end_row, bg="bg")
        end_row = self.rec_end_row

        ends_lbl = tk.Label(end_row, text="Ends:", font=("Segoe UI", 9))
        self.track_theme(ends_lbl, bg="bg", fg="subtext")
        ends_lbl.pack(side="left", padx=(0, 6))

        self.rec_end_mode_var = tk.StringVar(value="never")

        def _end_radio(value, text):
            rb = tk.Radiobutton(
                end_row, text=text, value=value, variable=self.rec_end_mode_var,
                font=("Segoe UI", 9), relief="flat", cursor="hand2",
                command=self.on_end_mode_changed,
                selectcolor=self.colors["card"]
            )
            self.track_theme(rb, bg="bg", fg="text", activebackground="bg", activeforeground="text")
            rb.pack(side="left", padx=2)
            return rb

        # Each input is packed immediately after the radio it belongs to,
        # so "On date [____]" and "After [__] times" read correctly.
        _end_radio("never", "Never")

        _end_radio("on", "On date")
        self.rec_end_date_var = tk.StringVar(value="")
        self.rec_end_date_entry = tk.Entry(
            end_row, textvariable=self.rec_end_date_var, width=11,
            relief="flat", font=("Segoe UI", 9), insertbackground=self.colors["text"]
        )
        self.track_theme(self.rec_end_date_entry, bg="card", fg="text")
        self.rec_end_date_entry.pack(side="left", padx=(4, 2), ipady=2)
        self.rec_end_date_var.trace_add("write", lambda *a: self.update_recurrence_summary())

        self.rec_end_date_pick_btn = tk.Button(
            end_row, text="📅",
            command=lambda: self.open_date_picker(self.rec_end_date_entry,
                                                  self.rec_end_date_pick_btn),
            relief="flat", font=("Segoe UI", 9), cursor="hand2"
        )
        self.track_theme(self.rec_end_date_pick_btn, bg="sidebar", fg="text")
        self.rec_end_date_pick_btn.pack(side="left", padx=(0, 8), ipadx=2)

        _end_radio("after", "After")
        self.rec_count_var = tk.StringVar(value="10")
        self.rec_count_entry = tk.Entry(
            end_row, textvariable=self.rec_count_var, width=4,
            relief="flat", font=("Segoe UI", 9), justify="center",
            insertbackground=self.colors["text"]
        )
        self.track_theme(self.rec_count_entry, bg="card", fg="text")
        self.rec_count_entry.pack(side="left", padx=(4, 2), ipady=2)
        self.rec_count_var.trace_add("write", lambda *a: self.update_recurrence_summary())

        times_lbl = tk.Label(end_row, text="times", font=("Segoe UI", 9))
        self.track_theme(times_lbl, bg="bg", fg="subtext")
        times_lbl.pack(side="left")

        self.refresh_weekday_buttons()
        self.on_end_mode_changed()
        self.on_recurrence_changed()

    def on_end_mode_changed(self):
        """Grey out the inputs that don't apply, so the panel can't imply an
        end condition that won't actually be saved."""
        mode = self.rec_end_mode_var.get()
        for entry, active in ((self.rec_end_date_entry, mode == "on"),
                              (self.rec_count_entry, mode == "after")):
            if active:
                entry.configure(state="normal", fg=self.colors["text"],
                                bg=self.colors["card"])
            else:
                # Muted, but still clearly a field. Using the panel background
                # here would make the box disappear into the layout.
                entry.configure(state="disabled",
                                disabledbackground=self.colors["sidebar"],
                                disabledforeground=self.colors["subtext"])
        if hasattr(self, "rec_end_date_pick_btn"):
            self.rec_end_date_pick_btn.configure(
                state="normal" if mode == "on" else "disabled")
        self.update_recurrence_summary()

    def toggle_weekday(self, index):
        self.rec_weekday_state[index] = not self.rec_weekday_state[index]
        self.refresh_weekday_buttons()
        self.update_recurrence_summary()

    def refresh_weekday_buttons(self):
        for index, btn in enumerate(getattr(self, "rec_weekday_btns", [])):
            if self.rec_weekday_state[index]:
                btn.configure(bg=self.colors["accent"], fg="white",
                              activebackground=self.colors["accent_hover"])
            else:
                btn.configure(bg=self.colors["card"], fg=self.colors["subtext"],
                              activebackground=self.colors["card"])

    def selected_freq_key(self):
        label = self.rec_freq_var.get()
        for key, text in FREQ_LABELS.items():
            if text == label:
                return key
        return ""

    def on_recurrence_changed(self):
        """Show only the controls that apply to the chosen frequency. All rows
        are re-packed in a fixed order so nothing drifts to the bottom."""
        freq = self.selected_freq_key()

        rows = (self.rec_interval_row, self.rec_weekday_row, self.rec_monthday_row,
                self.rec_policy_row, self.rec_end_row)
        for widget in rows:
            widget.pack_forget()

        if not freq:
            # Collapse the whole details block so the Note body sits right
            # under Repeat with no reserved gap.
            self.rec_details.pack_forget()
            self.rec_summary_lbl.config(text="")
            return

        # Show the details block, positioned just above the Note body section
        # (where the Tags section used to sit, before it was removed).
        if hasattr(self, "body_header") and self.body_header.winfo_manager():
            self.rec_details.pack(fill="x", padx=30, pady=(0, 4),
                                  before=self.body_header)
        else:
            self.rec_details.pack(fill="x", padx=30, pady=(0, 4))

        self.rec_interval_row.pack(fill="x", pady=(0, 6))
        self.rec_unit_lbl.config(
            text={"daily": "day(s)", "weekly": "week(s)",
                  "monthly": "month(s)", "yearly": "year(s)"}[freq]
        )

        if freq == "weekly":
            self.rec_weekday_row.pack(fill="x", pady=(0, 6))
        elif freq == "monthly":
            self.rec_monthday_row.pack(fill="x", pady=(0, 6))
            self.rec_policy_row.pack(fill="x", pady=(0, 6))
        elif freq == "yearly":
            self.rec_policy_row.pack(fill="x", pady=(0, 6))

        self.rec_end_row.pack(fill="x", pady=(0, 12))
        self.update_recurrence_summary()

    def read_recurrence_from_ui(self):
        """Turn the widgets into a rule dict. Invalid entries fall back to
        sane defaults rather than blocking the save."""
        freq = self.selected_freq_key()
        if not freq:
            return normalize_recurrence({})

        try:
            interval = max(1, int(self.rec_interval_var.get().strip()))
        except ValueError:
            interval = 1

        weekdays = [i for i, on in enumerate(self.rec_weekday_state) if on] if freq == "weekly" else []

        month_days = []
        if freq == "monthly":
            for chunk in self.rec_monthdays_var.get().replace(";", ",").split(","):
                chunk = chunk.strip()
                if chunk.isdigit() and 1 <= int(chunk) <= 31:
                    month_days.append(int(chunk))

        policy = "clamp" if self.rec_policy_var.get() == "Use the last day" else "skip"

        end, count = "", 0
        mode = self.rec_end_mode_var.get()
        if mode == "on":
            end = self.rec_end_date_var.get().strip()
        elif mode == "after":
            try:
                count = max(1, int(self.rec_count_var.get().strip()))
            except ValueError:
                count = 1

        return normalize_recurrence({
            "freq": freq, "interval": interval, "weekdays": weekdays,
            "month_days": month_days, "month_day_policy": policy,
            "end": end, "count": count,
        })

    def write_recurrence_to_ui(self, rec):
        rec = normalize_recurrence(rec)
        self.rec_freq_var.set(FREQ_LABELS[rec["freq"]])
        self.rec_interval_var.set(str(rec["interval"]))
        self.rec_weekday_state = [i in rec["weekdays"] for i in range(7)]
        self.rec_monthdays_var.set(", ".join(str(d) for d in rec["month_days"]))
        self.rec_policy_var.set("Use the last day" if rec["month_day_policy"] == "clamp" else "Skip that month")

        if rec["count"]:
            self.rec_end_mode_var.set("after")
            self.rec_count_var.set(str(rec["count"]))
            self.rec_end_date_var.set("")
        elif rec["end"]:
            self.rec_end_mode_var.set("on")
            self.rec_end_date_var.set(rec["end"])
        else:
            self.rec_end_mode_var.set("never")
            self.rec_end_date_var.set("")

        self.refresh_weekday_buttons()
        self.on_end_mode_changed()
        self.on_recurrence_changed()

    def update_recurrence_summary(self):
        rec = self.read_recurrence_from_ui()
        if not rec["freq"]:
            self.rec_summary_lbl.config(text="")
            self._schedule_autosave()
            return
        preview = describe_recurrence({"recurrence": rec})
        anchor = self.date_entry.get().strip()
        if not parse_date(anchor):
            preview += "   ⚠ needs a start date"
        self.rec_summary_lbl.config(text=preview)
        # Recurrence settings (frequency, weekdays, interval, end condition)
        # didn't autosave before — this is the single choke point every one of
        # those changes passes through, so hooking it here covers them all.
        self._schedule_autosave()

    # ---------- Occurrence scope prompt ----------
    def ask_occurrence_scope(self, action_word, occurrence_date):
        """Google-Calendar-style prompt. Returns 'occurrence', 'series' or None.
        Uses the in-app themed dialog overlay (not a separate window)."""
        return self._themed_dialog(
            f"{action_word} repeating note",
            f"This note repeats. What should '{action_word}' apply to?\n"
            f"Currently open occurrence: {occurrence_date}",
            kind="question",
            buttons=[("Cancel", None), ("The entire series", "series"),
                     ("This occurrence only", "occurrence")]
        )

    def _reset_text_undo(self):
        """Clear undo history on both editors — called after loading a note so
        Ctrl+Z can't undo back into a previous note's content."""
        for w in (getattr(self, "body_text", None), getattr(self, "comments_text", None)):
            if w is not None:
                try:
                    w.edit_reset()
                except tk.TclError:
                    pass

    def _can_edit_undo(self, widget):
        try:
            return bool(widget.edit("canundo"))
        except tk.TclError:
            return False

    def _can_edit_redo(self, widget):
        try:
            return bool(widget.edit("canredo"))
        except tk.TclError:
            return False

    def _bind_text_wheel(self, text_widget, fallback_canvas=None):
        """Mousewheel behavior over a text box:
        - if the box has more text than fits, scroll the box's own content;
        - if everything fits, forward the scroll to the editor page instead, so
          the user can still reach the buttons below.
        We must return "break" in BOTH cases, otherwise tkinter's built-in Text
        wheel handling fires too and swallows the event."""
        def _on_wheel(event):
            try:
                first, last = text_widget.yview()
            except (tk.TclError, ValueError):
                return
            fits = first <= 0.0 and last >= 1.0
            if fits:
                # Nothing to scroll inside the box — move the whole editor page.
                target = fallback_canvas or getattr(self, "editor_canvas", None)
                if target is not None:
                    try:
                        target.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    except (tk.TclError, ValueError):
                        pass
                return "break"
            text_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"
        text_widget.bind("<MouseWheel>", _on_wheel)

    def _bind_mousewheel_recursive(self, widget, canvas, skip=None):
        # `skip` is a set of widgets that manage their own wheel scrolling
        # (e.g. the Note/Comments text boxes) — don't override them.
        skip_set = skip if isinstance(skip, (set, list, tuple)) else ()
        if widget in skip_set:
            return

        def _on_wheel(event):
            # Don't scroll if the content already fits — otherwise the wheel
            # can drag short content down and open a gap at the top.
            try:
                first, last = canvas.yview()
                if first <= 0.0 and last >= 1.0:
                    return "break"
            except (tk.TclError, ValueError):
                pass
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        widget.bind("<MouseWheel>", _on_wheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child, canvas, skip=skip)

    def add_placeholder(self, entry, placeholder):
        entry.insert(0, placeholder)
        entry.config(fg=self.colors["subtext"])
        self._placeholders.append((entry, placeholder))

        def clear_if_placeholder():
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.config(fg=self.colors["text"])

        def on_focus_in(e):
            clear_if_placeholder()

        def on_key(e):
            # Clear BEFORE the keystroke lands — <FocusIn> alone can lose this
            # race if the user starts typing immediately after clicking in.
            clear_if_placeholder()

        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg=self.colors["subtext"])

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<KeyPress>", on_key)
        entry.bind("<FocusOut>", on_focus_out)

    # ---------- Note list rendering ----------
    def refresh_note_list(self):
        if not hasattr(self, "list_frame") or not self._still_alive():
            return
        # Called from everywhere note/category data changes (save, delete,
        # category rename/delete, import, ...) — piggyback the Statistics
        # panel's refresh here too, so it stays live while Settings happens
        # to be open, instead of only updating the next time it's opened.
        # Placed before the early-return branches below (e.g. an empty
        # filtered list) so it isn't skipped in those cases.
        self._render_statistics()
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        # Tracks note id -> the card's own widgets, so switching the open
        # note or toggling selection mode can update just the cards that
        # actually changed, instead of a full destroy-and-rebuild (which
        # flickered — every full rebuild here is otherwise a rare enough
        # action, like saving, searching, or sorting, that the flicker was
        # only really noticeable on the frequent actions that started using
        # it too: switching notes, and toggling selection mode).
        self._note_card_widgets = {}

        query = self.search_var.get().lower()
        if query == "search notes...":
            query = ""

        # Search matches title, body, and comments. Coerce every field to a
        # string first — a note with a missing/None field (from older or
        # slightly corrupt data) would otherwise crash the whole list render
        # and show nothing.
        def _txt(value):
            return value.lower() if isinstance(value, str) else ""

        filtered = [
            n for n in self.notes
            if query in _txt(n.get("title"))
            or query in _txt(n.get("body"))
            or query in _txt(n.get("comments"))
        ]

        # Category filter (from the dropdown). "All" shows everything.
        chosen_category = getattr(self, "filter_var", None)
        if chosen_category is not None:
            selected = self.filter_var.get()
            if selected != "All":
                filtered = [n for n in filtered if n.get("category") == selected]

        self._sort_notes(filtered)

        if not filtered:
            # Distinguish "no notes at all" from "nothing matches the filter".
            if self.notes:
                msg = "No notes match your search or filter."
            else:
                msg = "No notes yet.\nClick '+ New Note' to start!"
            empty_lbl = tk.Label(
                self.list_frame, text=msg,
                font=("Segoe UI", 10), justify="left"
            )
            self.track_theme(empty_lbl, bg="sidebar", fg="subtext")
            empty_lbl.pack(pady=20, padx=10, anchor="w")
            return

        if getattr(self, "group_by_category", None) is not None and self.group_by_category.get():
            self._render_grouped_notes(filtered)
        else:
            for note in filtered:
                self.build_note_card(note)

        self._bind_mousewheel_recursive(self.list_frame, self.canvas)

    def _render_grouped_notes(self, filtered):
        """Render notes clustered under collapsible category headers. Group
        order follows Manage-categories order; notes within a group keep the
        sort already applied to `filtered`. A note whose category no longer
        exists (deleted category) falls into its own group by that name, so it
        stays visible rather than disappearing."""
        groups = {}
        for note in filtered:
            cat = note.get("category") or "General"
            groups.setdefault(cat, []).append(note)

        # Known categories first (in their defined order), then any leftover
        # (stale/deleted) category names so nothing gets silently dropped.
        ordered = [c for c in CATEGORY_COLORS.keys() if c in groups]
        ordered += [c for c in groups.keys() if c not in ordered]

        for cat in ordered:
            notes_in_group = groups[cat]
            collapsed = cat in self.collapsed_groups
            color = CATEGORY_COLORS.get(cat, self.colors["accent"])

            header = tk.Frame(self.list_frame, bg=self.colors["sidebar"], cursor="hand2")
            header.pack(fill="x", pady=(6, 2))
            dot = tk.Canvas(header, width=10, height=10, highlightthickness=0,
                            bg=self.colors["sidebar"], cursor="hand2")
            dot.create_oval(1, 1, 9, 9, fill=color, outline=color)
            dot.pack(side="left", padx=(4, 6), pady=6)
            caret = tk.Label(header, text=("▶" if collapsed else "▼"),
                             bg=self.colors["sidebar"], fg=self.colors["subtext"],
                             font=("Segoe UI", 8), cursor="hand2")
            caret.pack(side="left", padx=(0, 4))
            lbl = tk.Label(header, text=f"{cat} ({len(notes_in_group)})",
                           bg=self.colors["sidebar"], fg=self.colors["text"],
                           font=("Segoe UI", 9, "bold"), cursor="hand2")
            lbl.pack(side="left")

            for w in (header, dot, caret, lbl):
                w.bind("<Button-1>", lambda e, c=cat: self._toggle_group_collapsed(c))

            if not collapsed:
                for note in notes_in_group:
                    self.build_note_card(note)

    def _sort_notes(self, notes):
        """Sort the list in place according to the chosen sort option. All keys
        coerce missing/None fields to safe defaults so a single odd note can't
        crash the whole list."""
        choice = getattr(self, "sort_var", None)
        choice = choice.get() if choice is not None else "Recently updated"

        def _s(n, key):
            v = n.get(key, "")
            return v if isinstance(v, str) else ""

        if choice == "Recently updated":
            notes.sort(key=lambda n: _s(n, "updated"), reverse=True)
        elif choice == "Oldest updated":
            notes.sort(key=lambda n: _s(n, "updated"))
        elif choice == "Title A–Z":
            # Untitled notes sink to the bottom rather than clustering at top.
            notes.sort(key=lambda n: (not _s(n, "title").strip(), _s(n, "title").lower()))
        elif choice == "Title Z–A":
            notes.sort(key=lambda n: (not _s(n, "title").strip(), _s(n, "title").lower()),
                       reverse=True)
        elif choice == "Category":
            notes.sort(key=lambda n: (_s(n, "category"), _s(n, "updated")),
                       reverse=False)
        elif choice == "Date (soonest)":
            def date_key(n):
                d = _s(n, "date")
                has = bool(parse_date(d))
                return (not has, d if has else "", )
            notes.sort(key=date_key)

        # Pinned notes always float to the top, keeping their relative order
        # from the chosen sort. Python's sort is stable, so this preserves it.
        notes.sort(key=lambda n: not n.get("pinned", False))

    def build_note_card(self, note):
        # Direct .configure() calls here, not self.track_theme(): every card
        # is destroyed and rebuilt from scratch on every refresh_note_list()
        # call (a save, a search keystroke, switching notes, ...), so it
        # always picks up the CURRENT theme colors fresh anyway — it never
        # needs live tracking for a later theme switch. track_theme() appends
        # to a list that's never pruned when its widgets are destroyed, so
        # with a few hundred notes and a session's worth of saves, that list
        # grew into the thousands, measurably slowing down both this render
        # and every future theme switch.
        color = self.get_note_color(note)
        is_open = note["id"] == self.selected_note_id
        card = tk.Frame(
            self.list_frame, cursor="hand2", bg=self.colors["card"],
            highlightthickness=2 if is_open else 0,
            highlightbackground=self.colors["accent"], highlightcolor=self.colors["accent"]
        )
        card.pack(fill="x", pady=5, padx=2)

        sel_cb = None
        if self.selection_mode:
            sel_var = tk.BooleanVar(value=note["id"] in self.selected_note_ids)
            sel_cb = tk.Checkbutton(
                card, variable=sel_var, bg=self.colors["card"],
                activebackground=self.colors["card"], selectcolor=self.colors["sidebar"],
                bd=0, highlightthickness=0,
                command=lambda n=note, v=sel_var: self._toggle_note_selected(n["id"], v.get())
            )
            sel_cb.pack(side="left", padx=(6, 0))

        stripe = tk.Frame(card, bg=color, width=5)
        stripe.pack(side="left", fill="y")

        content = tk.Frame(card, bg=self.colors["card"])
        content.pack(side="left", fill="both", expand=True, padx=10, pady=8)

        # Coerce possibly-missing/None fields to safe strings so one odd note
        # (e.g. from older data) can never crash the whole list render.
        note_title = note.get("title") if isinstance(note.get("title"), str) else ""
        note_body = note.get("body") if isinstance(note.get("body"), str) else ""
        note_category = note.get("category") if isinstance(note.get("category"), str) else "General"

        title_text = _truncate(note_title, 42) if note_title else "(untitled)"
        if note.get("pinned"):
            title_text = "📌 " + title_text
        if is_recurring(note):
            title_text = "🔁 " + title_text
        title_lbl = tk.Label(content, text=title_text, font=("Segoe UI", 11, "bold"),
                             anchor="w", justify="left",
                             bg=self.colors["card"], fg=self.colors["text"])
        title_lbl.pack(fill="x")

        preview = note_body[:40].replace("\n", " ")
        preview_lbl = tk.Label(
            content, text=preview + ("..." if len(note_body) > 40 else ""),
            font=("Segoe UI", 9), anchor="w",
            bg=self.colors["card"], fg=self.colors["subtext"]
        )
        preview_lbl.pack(fill="x")

        tags_text = note_category
        if is_recurring(note):
            tags_text += f"   🔁 {describe_recurrence(note)}"
            if note.get("exceptions"):
                tags_text += f"   ✕{len(note['exceptions'])}"
            if note.get("overrides"):
                tags_text += f"   ✎{len(note['overrides'])}"
        elif note.get("date"):
            tags_text += f"   📅 {note['date']}"
        if note.get("comments"):
            tags_text += "   💬"
        if note.get("attachments"):
            tags_text += f"   📎×{len(note['attachments'])}"
        checklist = note.get("checklist") or []
        if isinstance(checklist, list) and checklist:
            done = sum(1 for it in checklist
                       if isinstance(it, dict) and it.get("done"))
            tags_text += f"   ☑ {done}/{len(checklist)}"
        cat_lbl = tk.Label(content, text=tags_text, fg=color, font=("Segoe UI", 8, "bold"),
                           anchor="w", bg=self.colors["card"])
        cat_lbl.pack(fill="x", pady=(3, 0))

        widgets = [card, stripe, content, title_lbl, preview_lbl, cat_lbl]
        for widget in widgets:
            if self.selection_mode:
                # In selection mode, clicking anywhere on the card toggles it —
                # opening the note would defeat the point of picking several at
                # once without leaving the list.
                widget.bind("<Button-1>", lambda e, cb=sel_cb: cb.invoke())
            else:
                widget.bind("<Button-1>", lambda e, n=note: self.open_note_in_tab(n))
            # Right-click anywhere on the card opens the context menu.
            widget.bind("<Button-3>", lambda e, n=note: self.show_note_context_menu(e, n))

        self._note_card_widgets[note["id"]] = {
            "card": card, "clickable": widgets, "checkbox": sel_cb, "note": note,
        }

    # ---------- Multi-select for bulk actions ----------
    def _toggle_selection_mode(self):
        """Turn the pick-several-notes mode on or off. Turning it off always
        clears whatever was selected — re-entering starts fresh, rather than
        surprising the user with an old selection still active."""
        self.selection_mode = not self.selection_mode
        self.selected_note_ids = set()
        if self.selection_mode:
            self.select_toggle_btn.config(text="✕ Cancel select")
            self.bulk_action_bar.pack(fill="x", padx=15, pady=(0, 8), after=self._selection_anchor_row())
        else:
            self.select_toggle_btn.config(text="☑ Select")
            self.bulk_action_bar.pack_forget()
        self._update_bulk_selected_label()
        self._apply_selection_mode_to_cards()

    def _exit_selection_mode_after_bulk_action(self):
        """Same UI cleanup as turning selection mode off, but followed by a
        full refresh_note_list() instead of the surgical per-card update —
        used after a bulk action (trash, category change) that actually
        changed which notes exist or what they show. The surgical update
        _toggle_selection_mode() uses elsewhere only adds/removes checkboxes
        on cards that are still valid; after a bulk action, some of those
        cards represent notes that no longer exist (or no longer belong in
        the current view), so nothing short of a real rebuild reflects that
        correctly — the notes were genuinely gone, but their cards stayed
        on screen showing stale data until clicked."""
        self.selection_mode = False
        self.selected_note_ids = set()
        self.select_toggle_btn.config(text="☑ Select")
        self.bulk_action_bar.pack_forget()
        self._update_bulk_selected_label()
        self.refresh_note_list()

    def _apply_selection_mode_to_cards(self):
        """Add or remove just the per-card checkbox, and rebind each card's
        click handler to match the current selection_mode — without
        destroying and rebuilding every card. A full refresh_note_list() here
        worked, but visibly flickered the whole list just to toggle one
        column of checkboxes on or off."""
        for note_id, info in list(self._note_card_widgets.items()):
            card = info["card"]
            try:
                card.winfo_exists()
            except tk.TclError:
                continue
            old_cb = info.get("checkbox")
            if old_cb is not None:
                try:
                    old_cb.destroy()
                except tk.TclError:
                    pass
                info["checkbox"] = None

            if self.selection_mode:
                note = info["note"]
                sel_var = tk.BooleanVar(value=note_id in self.selected_note_ids)
                sel_cb = tk.Checkbutton(
                    card, variable=sel_var, bg=self.colors["card"],
                    activebackground=self.colors["card"], selectcolor=self.colors["sidebar"],
                    bd=0, highlightthickness=0,
                    command=lambda n=note_id, v=sel_var: self._toggle_note_selected(n, v.get())
                )
                # Leftmost, ahead of everything already packed in the card.
                sel_cb.pack(side="left", padx=(6, 0), before=card.winfo_children()[0])
                info["checkbox"] = sel_cb
                for widget in info["clickable"]:
                    widget.bind("<Button-1>", lambda e, cb=sel_cb: cb.invoke())
            else:
                note = info["note"]
                for widget in info["clickable"]:
                    widget.bind("<Button-1>", lambda e, n=note: self.open_note_in_tab(n))

    def _selection_anchor_row(self):
        """The row the bulk-action bar should appear directly under. Looked
        up by walking the sidebar rather than stored separately, so it stays
        correct even if the sidebar layout changes elsewhere."""
        return self.select_toggle_btn.master

    def _toggle_note_selected(self, note_id, now_selected):
        if now_selected:
            self.selected_note_ids.add(note_id)
        else:
            self.selected_note_ids.discard(note_id)
        self._update_bulk_selected_label()
        # No refresh_note_list() here on purpose: rebuilding every card just
        # to reflect one checkbox change caused a visible flicker on every
        # single click. The checkbox already updates its own check-mark
        # natively; nothing else about the card needs to change.

    def _update_bulk_selected_label(self):
        n = len(self.selected_note_ids)
        self.bulk_selected_lbl.config(text=f"{n} selected")

    def _bulk_select_all(self):
        """Selects every note currently visible in the list (respecting
        whatever search/category filter is active) — not necessarily every
        note in the whole app."""
        query = self.search_var.get().lower()
        if query == "search notes...":
            query = ""

        def _txt(value):
            return value.lower() if isinstance(value, str) else ""

        visible = [
            n for n in self.notes
            if query in _txt(n.get("title")) or query in _txt(n.get("body"))
            or query in _txt(n.get("comments"))
        ]
        chosen_category = getattr(self, "filter_var", None)
        if chosen_category is not None and self.filter_var.get() != "All":
            visible = [n for n in visible if n.get("category") == self.filter_var.get()]
        self.selected_note_ids = {n["id"] for n in visible}
        self._update_bulk_selected_label()
        self.refresh_note_list()

    def _bulk_move_to_trash(self):
        if not self.selected_note_ids:
            self.show_info("Nothing selected", "Tick one or more notes first.")
            return
        count = len(self.selected_note_ids)
        to_trash = [n for n in self.notes if n["id"] in self.selected_note_ids]
        attachment_count = sum(len(n.get("attachments") or []) for n in to_trash)
        warning = ""
        if attachment_count:
            plural = "s" if attachment_count != 1 else ""
            warning = f"\n\n{attachment_count} attached file{plural} will go to trash with them."
        if not self.ask_yes_no(
            "Move to trash",
            f"Move {count} selected note(s) to the trash? "
            f"You can restore them within {TRASH_RETENTION_DAYS} days.{warning}",
            icon="question"
        ):
            return
        self._move_notes_to_trash(to_trash)
        self.notes = [n for n in self.notes if n["id"] not in self.selected_note_ids]
        self.save_notes()
        # If the note currently open in the editor was among the ones just
        # trashed, the editor (and any tab pointing at it) is now referring
        # to a note that no longer exists — without this, the very next
        # autosave flush (e.g. triggered by clicking a DIFFERENT, perfectly
        # fine note right after) would fail with "Note missing", since it's
        # still trying to save changes against the now-gone note. Same
        # cleanup delete_current_note() already does for a single delete.
        self.open_tabs = [t for t in self.open_tabs
                          if t["state"]["selected_note_id"] not in self.selected_note_ids]
        if not self.open_tabs:
            self.active_tab_index = None
            self.new_note()
        else:
            self.active_tab_index = None
            self.switch_to_tab(min(0, len(self.open_tabs) - 1))
        self.refresh_tab_strip()
        self._exit_selection_mode_after_bulk_action()
        self.render_calendar()
        self.set_status(f"Moved {count} note(s) to trash")

    def _bulk_change_category(self):
        if not self.selected_note_ids:
            self.show_info("Nothing selected", "Tick one or more notes first.")
            return
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=4, pady=4)
        frame.pack(padx=1, pady=1)
        tk.Label(frame, text=f"Move {len(self.selected_note_ids)} note(s) to:",
                 bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6, pady=(4, 2))

        def apply_category(cat):
            count = len(self.selected_note_ids)
            for n in self.notes:
                if n["id"] in self.selected_note_ids:
                    n["category"] = cat
                    n["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_notes()
            self._dismiss_mini_popup()
            self._exit_selection_mode_after_bulk_action()
            self.set_status(f"Moved {count} note(s) to \u201c{cat}\u201d")

        for cat in CATEGORY_COLORS.keys():
            row = tk.Frame(frame, bg=self.colors["card"], cursor="hand2")
            row.pack(fill="x")
            dot = tk.Canvas(row, width=10, height=10, highlightthickness=0, bg=self.colors["card"])
            dot.create_oval(1, 1, 9, 9, fill=CATEGORY_COLORS[cat], outline=CATEGORY_COLORS[cat])
            dot.pack(side="left", padx=(8, 6), pady=5)
            lbl = tk.Label(row, text=cat, bg=self.colors["card"], fg=self.colors["text"],
                          font=("Segoe UI", 9), anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=(0, 10), pady=5)
            for w in (row, dot, lbl):
                w.bind("<Button-1>", lambda e, c=cat: apply_category(c))

        self._place_dropdown_popup(pop, self._bulk_category_btn)

    # ---------- Note actions ----------
    # ---------- Editor state snapshot (for multi-note tabs) ----------
    def capture_editor_state(self):
        """Snapshot everything the editor currently holds, so a note tab can be
        set aside and restored later exactly as the user left it — including
        unsaved edits. This is the backbone of having several notes open."""
        title = self.title_entry.get()
        if title == "Note title...":
            title = ""
        date_raw = self.date_entry.get().strip()
        if date_raw == "YYYY-MM-DD":
            date_raw = ""
        return {
            "selected_note_id": self.selected_note_id,
            "occurrence_date": self.current_occurrence_date,
            "title": title,
            "body": self.body_text.get("1.0", "end-1c"),
            "formatting": self._extract_formatting(self.body_text),
            "pending_styles": sorted(self._pending_styles),
            "pending_text_color": self._pending_text_color,
            "pending_highlight_color": self._pending_highlight_color,
            "comments": self.comments_text.get("1.0", "end-1c"),
            "category": self.category_var.get(),
            "date": date_raw,
            "color": self.current_note_color,
            "attachments": list(self.current_attachments),
            "recurrence": self.read_recurrence_from_ui(),
            "checklist": [dict(it) for it in self._get_checklist()],
        }

    def restore_editor_state(self, st):
        """Load a previously captured editor state back into the live editor."""
        self.selected_note_id = st["selected_note_id"]
        self.current_occurrence_date = st.get("occurrence_date")

        self.title_entry.delete(0, "end")
        if st["title"]:
            self.title_entry.insert(0, st["title"])
            self.title_entry.config(fg=self.colors["text"])
        else:
            self.title_entry.insert(0, "Note title...")
            self.title_entry.config(fg=self.colors["subtext"])

        # Restore this tab's own pending style (if any) before inserting
        # its body — set after the insert instead, a leftover pending style
        # from whatever tab was open a moment ago could tag this one's text.
        self._pending_styles = set(st.get("pending_styles") or [])
        self._pending_text_color = st.get("pending_text_color")
        self._pending_highlight_color = st.get("pending_highlight_color")
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", st["body"])
        self._apply_formatting(self.body_text, st.get("formatting", []))
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", st["comments"])
        self.category_var.set(st["category"])

        self.date_entry.delete(0, "end")
        if st["date"]:
            self.date_entry.insert(0, st["date"])
            self.date_entry.config(fg=self.colors["text"])
        else:
            self.date_entry.insert(0, "YYYY-MM-DD")
            self.date_entry.config(fg=self.colors["subtext"])

        self.current_note_color = st["color"]
        self._update_color_swatch()
        self.current_attachments = list(st["attachments"])
        self.refresh_attachments_list()
        self._working_checklist = [dict(it) for it in st.get("checklist", [])]
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()
        self._sync_checklist_open_state()
        self._sync_calculator_open_state()

        self.write_recurrence_to_ui(st.get("recurrence") or {})

        self.update_word_count()
        self._refresh_format_buttons()

        self._reset_editor_scroll()
        self._reset_text_undo()
        self._update_restore_button()
    def editor_state_matches_saved(self, st):
        """True if the captured state equals what's on disk for its note — i.e.
        there are no unsaved changes. A brand-new note (no id) counts as unsaved
        the moment it has any content."""
        note_id = st["selected_note_id"]
        if note_id is None:
            # New, never-saved note: "clean" only if completely empty.
            return not (st["title"].strip() or st["body"].strip()
                        or st["comments"].strip()
                        or st["attachments"] or st["date"]
                        or st["recurrence"].get("freq") or st.get("checklist"))
        note = self.find_note(note_id)
        if note is None:
            return False  # underlying note deleted -> treat as dirty/gone

        # Compare against the effective (occurrence-aware) content.
        occ = st.get("occurrence_date")
        shown = effective_note(note, occ) if occ else note
        if (st["title"].strip() != shown["title"].strip()
                or st["body"].strip() != shown["body"].strip()
                or st.get("formatting", []) != note.get("formatting", [])
                or st["comments"].strip() != shown.get("comments", "").strip()
                or st["category"] != shown["category"]
                or st["color"] != shown.get("color", "")
                or st.get("checklist", []) != note.get("checklist", [])):
            return False
        # Date / recurrence belong to the series (compare against base note).
        if st["date"] != note.get("date", ""):
            return False
        if st["recurrence"] != normalize_recurrence(note.get("recurrence")):
            return False
        if st["attachments"] != note.get("attachments", []):
            return False
        return True

    # ---------- Open-note tabs (multiple notes at once) ----------
    def _sync_active_tab(self):
        """Save the live editor back into the active tab's stored state."""
        if self.active_tab_index is not None and 0 <= self.active_tab_index < len(self.open_tabs):
            self.open_tabs[self.active_tab_index]["state"] = self.capture_editor_state()

    def _tab_title(self, tab):
        st = tab.get("state", {})
        raw = st.get("title") if isinstance(st, dict) else ""
        title = _truncate(raw, 16)
        return title or "(untitled)"

    def _catch_up_deferred_refresh(self):
        """If a note-list/calendar rebuild was skipped earlier (see
        save_current_note) because a popup was open during autosave, run it
        now. Called at natural transition points — switching notes, changing
        tabs — where an extra rebuild blends into a change that was already
        happening, rather than standing out as an isolated glitch against an
        otherwise static screen."""
        if getattr(self, "_note_list_needs_refresh", False):
            self._note_list_needs_refresh = False
            self.refresh_note_list()
            self.render_calendar()

    def _update_open_highlight(self):
        """Move the 'currently open' card border directly to whichever card
        needs it, without rebuilding the list. self._note_card_widgets is
        kept up to date by the last full refresh_note_list() — this just
        touches the (at most) two cards that actually changed."""
        prev = getattr(self, "_last_highlighted_note_id", None)
        current = self.selected_note_id
        if prev == current:
            return
        cards = getattr(self, "_note_card_widgets", {})
        if prev is not None and prev in cards:
            try:
                cards[prev]["card"].configure(highlightthickness=0)
            except tk.TclError:
                pass
        if current is not None and current in cards:
            try:
                cards[current]["card"].configure(
                    highlightthickness=2, highlightbackground=self.colors["accent"],
                    highlightcolor=self.colors["accent"])
            except tk.TclError:
                pass
        self._last_highlighted_note_id = current

    def open_note_in_tab(self, note, occurrence_date=None):
        """Open a saved note in the editor. Only one note is open at a time — any
        unsaved work in the current note is auto-saved first, then this note
        loads in its place."""
        # Close any open popup (e.g. an emoji picker) FIRST, before flushing
        # autosave below — otherwise the autosave that follows would see a
        # popup still open and skip refreshing the note list, leaving it
        # stale even after switching notes.
        self._dismiss_mini_popup()
        # Navigating to a different note means we're no longer mid-creation of
        # the calendar-originated one — clear this BEFORE the flush below, so
        # that flush's save can't accidentally trigger an unwanted jump back
        # to the calendar out from under the note the user is trying to open.
        self._pending_calendar_return = None
        self._update_calendar_return_button()
        self._catch_up_deferred_refresh()
        # Save whatever is currently in the editor before switching away.
        self._flush_autosave()
        self.load_note(note, occurrence_date)
        self._remember_last_open_note(note["id"])
        # Keep a single-entry tab list so the save/flush machinery still works.
        self._tab_counter += 1
        self.open_tabs = [{"key": self._tab_counter, "state": self.capture_editor_state()}]
        self.active_tab_index = 0
        self.refresh_tab_strip()
        # Moves the highlighted-card border to this note, without rebuilding
        # the whole list — switching notes happens constantly during normal
        # use, and a full refresh_note_list() here just to move a border was
        # a much more noticeable flicker than the same cost is for genuinely
        # rare actions like saving or searching.
        self._update_open_highlight()

    def open_blank_tab(self):
        """Start a brand-new empty note, replacing whatever was open (after
        auto-saving any unsaved work in it)."""
        self._dismiss_mini_popup()
        self._pending_calendar_return = None
        self._update_calendar_return_button()
        self._catch_up_deferred_refresh()
        self._flush_autosave()
        self.new_note()
        self._tab_counter += 1
        self.open_tabs = [{"key": self._tab_counter, "state": self.capture_editor_state()}]
        self.active_tab_index = 0
        self.refresh_tab_strip()
        # Clears any previously-highlighted card's border — a blank new note
        # isn't "the" open note in the list. Same surgical update as
        # open_note_in_tab, not a full rebuild.
        self._update_open_highlight()

    def _flush_autosave(self):
        """Cancel any pending debounced auto-save and, if the current editor has
        real unsaved changes, save them right now. Called before switching notes
        or closing so a late timer can't fire into the wrong note."""
        if getattr(self, "_autosave_job", None) is not None:
            try:
                self.after_cancel(self._autosave_job)
            except (tk.TclError, ValueError):
                pass
            self._autosave_job = None
        if self.selected_note_id is None and not self.open_tabs:
            return
        # selected_note_id can end up stale — pointing at a note that no
        # longer exists — in the brief window some code paths (e.g.
        # _context_delete_note) temporarily repoint it at a DIFFERENT note
        # than the one genuinely open in the editor, to reuse the normal
        # delete logic. If that happens, there's nothing real to flush
        # against; skip silently rather than falling through to a save
        # attempt that fails with a "Note missing" dialog — an automatic,
        # invisible safety net shouldn't ever surface an interruptive error
        # for something the user didn't directly ask to happen.
        if self.selected_note_id is not None and self.find_note(self.selected_note_id) is None:
            return
        try:
            st = self.capture_editor_state()
        except Exception:
            return
        if not (st.get("title", "").strip() or st.get("body", "").strip()
                or st.get("attachments") or st.get("checklist")):
            return
        try:
            if not self.editor_state_matches_saved(st):
                self.save_current_note(auto=True)
        except Exception:
            pass

    def switch_to_tab(self, index):
        if index == self.active_tab_index:
            return
        if not (0 <= index < len(self.open_tabs)):
            return
        self._flush_autosave()
        self._sync_active_tab()
        self.active_tab_index = index
        self.restore_editor_state(self.open_tabs[index]["state"])
        self.refresh_tab_strip()

    def close_tab(self, index, force=False):
        """Close one open note tab. If it has unsaved changes, ask first."""
        if not (0 <= index < len(self.open_tabs)):
            return
        # Make sure the tab we're checking reflects live edits if it's active.
        if index == self.active_tab_index:
            self._sync_active_tab()

        tab = self.open_tabs[index]
        if not force and not self.editor_state_matches_saved(tab["state"]):
            title = self._tab_title(tab)
            choice = self._ask_close_unsaved(title)
            if choice == "cancel":
                return
            if choice == "save":
                # Switch to it, save, then close.
                self.switch_to_tab(index)
                self.save_current_note()
                self._sync_active_tab()
                # index may have shifted if switch changed nothing; recompute
                index = self.active_tab_index

        del self.open_tabs[index]

        if not self.open_tabs:
            # Nothing open -> blank editor, no active tab.
            self.active_tab_index = None
            self.new_note()
            self.refresh_tab_strip()
            return

        # Pick a sensible neighbor to focus.
        new_index = min(index, len(self.open_tabs) - 1)
        self.active_tab_index = None  # force restore
        self.switch_to_tab(new_index)
        self.refresh_tab_strip()

    def _ask_close_unsaved(self, title):
        """Returns 'save', 'discard', or 'cancel'. Uses the in-app themed
        dialog overlay (not a separate window)."""
        return self._themed_dialog(
            "Unsaved changes",
            f"“{title}” has unsaved changes. Save before closing?",
            kind="warning",
            buttons=[("Cancel", "cancel"),
                     ("Discard", "discard", "danger"),
                     ("Save", "save", "success")]
        )

    def refresh_tab_strip(self):
        """Redraw the open-note tab row. Hidden entirely when 0–1 notes are
        open, so the single-note experience is unchanged."""
        if not hasattr(self, "tab_strip"):
            return
        for w in self.tab_strip.winfo_children():
            w.destroy()

        # Sync dirty markers with live editor before drawing.
        self._sync_active_tab()

        if len(self.open_tabs) <= 1:
            self.tab_strip.pack_forget()
            return

        self.tab_strip.pack(side="top", fill="x", before=self.editor_outer)

        for i, tab in enumerate(self.open_tabs):
            active = (i == self.active_tab_index)
            dirty = not self.editor_state_matches_saved(tab["state"])
            bg = self.colors["bg"] if active else self.colors["sidebar"]
            fg = self.colors["accent"] if active else self.colors["subtext"]

            chip = tk.Frame(self.tab_strip, bg=bg, cursor="hand2")
            chip.pack(side="left", padx=(6, 0), pady=4)

            dot = "● " if dirty else ""
            lbl = tk.Label(chip, text=dot + self._tab_title(tab), bg=bg, fg=fg,
                           font=("Segoe UI", 9, "bold" if active else "normal"),
                           cursor="hand2")
            lbl.pack(side="left", padx=(10, 4), pady=4)
            lbl.bind("<Button-1>", lambda e, idx=i: self.switch_to_tab(idx))

            x = tk.Label(chip, text="✕", bg=bg, fg=fg, font=("Segoe UI", 9),
                         cursor="hand2")
            x.pack(side="left", padx=(0, 8))
            x.bind("<Button-1>", lambda e, idx=i: self.close_tab(idx))
            x.bind("<Enter>", lambda e, w=x: w.configure(fg="#ff5c7c"))
            x.bind("<Leave>", lambda e, w=x, c=fg: w.configure(fg=c))

    def new_note(self):
        self.selected_note_id = None
        self.current_occurrence_date = None
        self.title_entry.delete(0, "end")
        self.title_entry.config(fg=self.colors["text"])
        self.body_text.delete("1.0", "end")
        self.comments_text.delete("1.0", "end")
        self.category_var.set("General")
        self.clear_note_date()
        self.current_note_color = ""
        self._update_color_swatch()
        self.current_attachments = []
        self.refresh_attachments_list()
        self.write_recurrence_to_ui({})
        self._working_checklist = []
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()
        self._sync_checklist_open_state()
        self._sync_calculator_open_state()
        self.title_entry.focus()
        self.set_status("New note — not yet saved")
        self.update_word_count()
        self._pending_styles = set()
        self._pending_text_color = None
        self._pending_highlight_color = None
        self._refresh_format_buttons()
        self._reset_editor_scroll()
        self._reset_text_undo()
        self._update_restore_button()

    def load_note(self, note, occurrence_date=None):
        """Open a note. If occurrence_date is given, the note is being opened
        from one specific day of a repeating series, and any per-occurrence
        override for that day is shown instead of the base content."""
        self.selected_note_id = note["id"]
        self.current_occurrence_date = occurrence_date if is_recurring(note) else None

        shown = effective_note(note, occurrence_date) if occurrence_date else note

        # Clear out any pending style left over from whatever note was open
        # before, BEFORE inserting this note's body — the insert hook that
        # applies pending styles doesn't know or care that this particular
        # insert is "loading a note" rather than "typing", so a stale
        # pending style at this point would silently tag this note's text.
        self._pending_styles = set()
        self._pending_text_color = None
        self._pending_highlight_color = None
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, shown["title"])
        self.title_entry.config(fg=self.colors["text"])
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", shown["body"])
        # Formatting spans are only ever saved for the base note, never a
        # per-occurrence override (see save_current_note) — reapplying them
        # against override text of a different length/content would place
        # bold/italic on the wrong characters. Only apply when what's shown
        # actually IS the base content (no override for this occurrence).
        if shown.get("body") == note.get("body"):
            self._apply_formatting(self.body_text, note.get("formatting", []))
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", shown.get("comments", ""))
        self.category_var.set(shown["category"])

        self.date_entry.delete(0, "end")
        if note.get("date"):
            self.date_entry.insert(0, note["date"])
            self.date_entry.config(fg=self.colors["text"])
        else:
            self.date_entry.insert(0, "YYYY-MM-DD")
            self.date_entry.config(fg=self.colors["subtext"])

        self.current_note_color = shown.get("color", "")
        self._update_color_swatch()
        self.current_attachments = list(note.get("attachments", []))
        self.refresh_attachments_list()
        # Checklist: work on a copy so edits aren't committed until save.
        self._working_checklist = [
            {"text": it.get("text", ""), "done": bool(it.get("done"))}
            for it in note.get("checklist", []) if isinstance(it, dict)
        ]
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()
        self._sync_checklist_open_state()
        self._sync_calculator_open_state()
        self.write_recurrence_to_ui(note.get("recurrence"))

        if self.current_occurrence_date:
            has_override = self.current_occurrence_date in (note.get("overrides") or {})
            suffix = " (edited separately)" if has_override else ""
            self.set_status(f"Occurrence {self.current_occurrence_date}{suffix}")
        else:
            created = note.get("created", "")
            if created:
                self.set_status(f"Created: {created}   ·   Last updated: {note['updated']}")
            else:
                self.set_status(f"Last updated: {note['updated']}")
        self.update_word_count()
        self._refresh_format_buttons()
        self._reset_editor_scroll()
        self._reset_text_undo()
        self._update_restore_button()

    # ---------- Right-click context menu ----------
    def duplicate_note(self, note):
        """Make a full copy of a note as a new, separate note. The copy's title
        gets a '(copy)' suffix so the two are distinguishable in the list. A
        recurring note is copied whole, recurrence included."""
        if note is None:
            return
        import copy as _copy
        clone = _copy.deepcopy(note)
        clone["id"] = max([n["id"] for n in self.notes], default=0) + 1
        base_title = (note.get("title") or "").strip()
        clone["title"] = f"{base_title} (copy)" if base_title else "(copy)"
        clone["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # A duplicate is its own note; don't carry occurrence-specific edits that
        # only made sense relative to the original's timeline.
        clone = normalize_note(clone)
        self.notes.append(clone)
        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        self.set_status(f"Duplicated as “{clone['title']}”")
        return clone

    def show_day_context_menu(self, event, date_str):
        """Right-click menu for a calendar day: add a note, or color the day.
        Left-click still opens the day panel; this is the separate right-click
        action."""
        menu = tk.Menu(self, tearoff=0)
        menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"], activeforeground="white",
            relief="flat", bd=0, font=("Segoe UI", 9)
        )
        menu.add_command(
            label="➕  Add note for this day",
            command=lambda: self._add_note_for_date(date_str)
        )
        # No "View this day" entry here — a plain left-click on the day
        # already opens the same panel via open_day_popup(), so this menu
        # only needs the actions a left-click can't already do.
        menu.add_separator()
        menu.add_command(
            label="🎨  Color this day…",
            command=lambda: self._color_day(date_str, event)
        )
        if self.day_colors.get(date_str):
            menu.add_command(
                label="✖  Clear day color",
                command=lambda: self._clear_day_color(date_str)
            )
        menu.add_command(
            label="🏷  Mark this day…",
            command=lambda: self._mark_day_emoji(date_str, event)
        )
        if self.day_emoji.get(date_str):
            menu.add_command(
                label="✖  Clear day markers",
                command=lambda: (self.day_emoji.pop(date_str, None),
                                 self._persist_day_emoji(), self.render_calendar())
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _color_day(self, date_str, event=None):
        """Color a calendar day using the same curated in-app palette used
        for categories — not the OS color-chooser dialog. Anchored near where
        the right-click happened, since a day cell has no persistent button
        to dock a dropdown to."""
        current = self.day_colors.get(date_str, "")

        def on_pick(color):
            if color:
                self.day_colors[date_str] = color
            else:
                self.day_colors.pop(date_str, None)
            self._persist_day_colors()
            self.render_calendar()

        if event is not None:
            anchor_xy = (event.x_root, event.y_root)
        else:
            anchor_xy = (self.winfo_rootx() + 100, self.winfo_rooty() + 100)
        self._show_color_palette(None, current, on_pick, allow_reset=True,
                                 anchor_xy=anchor_xy, reset_label="No color")

    def _clear_day_color(self, date_str):
        if date_str in self.day_colors:
            del self.day_colors[date_str]
            self._persist_day_colors()
            self.render_calendar()

    def _persist_day_colors(self):
        settings = load_settings()
        settings["day_colors"] = dict(self.day_colors)
        save_settings(settings)

    # A small curated set for flagging a day — not the full emoji picker,
    # just quick, common markers (star, alert, celebration, etc.).
    DAY_MARKER_EMOJIS = [
        ("⭐", "#FFD166"), ("❤️", "#FF6B6B"), ("❗", "#E63946"), ("🎉", "#FF8FA3"),
        ("✅", "#6BCB77"), ("🔴", "#E63946"), ("🟡", "#FFD166"), ("🟢", "#6BCB77"),
        ("💡", "#FFC145"), ("🎂", "#FF8FA3"), ("✈️", "#A0C4FF"), ("📌", "#FFB4A2"),
        ("🔔", "#FFA630"), ("🎁", "#FF8FA3"), ("💰", "#6BCB77"), ("🩺", "#A0C4FF"),
        ("🍽️", "#FFB4A2"), ("🚗", "#A0C4FF"),
    ]

    def _mark_day_emoji(self, date_str, event=None):
        """Small anchored popup for flagging a calendar day with one or more
        emoji markers — independent of whether it has a note. Click any number
        of chips to toggle them; nothing is written to disk or redrawn on the
        calendar until you press Save. ✕ discards whatever you changed here.
        This is deliberate: writing to disk and rebuilding the whole calendar
        on every single click was both slow (visible lag) and confusing (felt
        like nothing had "saved" until you clicked away)."""
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        outer = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        outer.pack(padx=1, pady=1)

        head = tk.Frame(outer, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Mark this day — up to 3", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")

        # Working copy — the real self.day_emoji isn't touched until Save.
        pending = list(self.day_emoji.get(date_str, []))[:3]
        cells = {}
        MAX_DAY_MARKERS = 3

        def refresh_cell(em):
            cell = cells[em]
            selected = em in pending
            cell.configure(highlightthickness=2 if selected else 0,
                           highlightbackground=self.colors["text"],
                           highlightcolor=self.colors["text"])

        def toggle(em):
            if em in pending:
                pending.remove(em)
            elif len(pending) < MAX_DAY_MARKERS:
                pending.append(em)
            # else: already at the 3-marker cap — ignore, keeps the calendar
            # cell readable and avoids piling on emoji that would just show
            # as an anonymous "+N" nobody could identify without reopening
            # this same popup.
            refresh_cell(em)
            # Purely local: just updates this chip's highlight. No disk write,
            # no calendar rebuild — that's what made rapid clicking feel
            # laggy before. Stays snappy no matter how many you pick.
            return "break"

        grid = tk.Frame(outer, bg=self.colors["card"])
        grid.pack()
        cols = 6
        for i, (em, color) in enumerate(self.DAY_MARKER_EMOJIS):
            r, c = divmod(i, cols)
            cell = tk.Label(grid, text=em, font=("Segoe UI Emoji", 14),
                            bg=color, cursor="hand2", width=2, height=1)
            cell.grid(row=r, column=c, padx=2, pady=2)
            cells[em] = cell
            hover_color = _darken_hex(color)
            # "break" stops this click from also reaching the app-wide
            # click-outside-closes-the-popup handler — without it, picking an
            # emoji could immediately close this same popup.
            cell.bind("<Button-1>", lambda e, em=em: toggle(em))
            cell.bind("<Enter>", lambda e, w=cell, h=hover_color: w.configure(bg=h))
            cell.bind("<Leave>", lambda e, w=cell, b=color: w.configure(bg=b))
            refresh_cell(em)

        def clear_pending():
            pending.clear()
            for em in cells:
                refresh_cell(em)

        def save_and_close():
            if pending:
                self.day_emoji[date_str] = list(pending)
            else:
                self.day_emoji.pop(date_str, None)
            self._persist_day_emoji()
            self._mini_popup_on_close = None  # already handled below
            self._dismiss_mini_popup()
            # Only this one day's badge needs to change — a full
            # render_calendar() here was heavy enough (destroying/rebuilding
            # every day cell) to cause a visible flicker right after the
            # popup closes.
            self._refresh_day_badge(date_str)

        btn_row = tk.Frame(outer, bg=self.colors["card"])
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="Clear", command=clear_pending, relief="flat",
                  cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True,
                                             padx=(0, 4), ipady=4)
        tk.Button(btn_row, text="✓ Save", command=save_and_close, relief="flat",
                  cursor="hand2", bg=self.colors["accent"], fg="white",
                  font=("Segoe UI", 8, "bold")).pack(side="left", fill="x", expand=True,
                                                     padx=(4, 0), ipady=4)

        if event is not None:
            anchor_xy = (event.x_root, event.y_root)
            self._place_dropdown_popup(pop, None, anchor_xy=anchor_xy)
        else:
            self._place_dropdown_popup(pop, None,
                                       anchor_xy=(self.winfo_rootx() + 100, self.winfo_rooty() + 100))

    def _persist_day_emoji(self):
        # Drop any None/empty entries (from Clear) rather than persisting them.
        self.day_emoji = {d: e for d, e in self.day_emoji.items() if e}
        settings = load_settings()
        settings["day_emoji"] = dict(self.day_emoji)
        save_settings(settings)

    def show_note_context_menu(self, event, note, occurrence_date=None):
        """Native right-click dropdown for a note. Extensible — add items here
        as new actions appear. When opened from the calendar (occurrence_date
        set), it also offers recurrence-specific actions."""
        if note is None:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"], activeforeground="white",
            relief="flat", bd=0, font=("Segoe UI", 9)
        )

        menu.add_command(
            label="✏  Open / Edit",
            command=lambda: self._ctx_open(note, occurrence_date)
        )
        pin_label = "📌  Unpin from top" if note.get("pinned") else "📌  Pin to top"
        menu.add_command(label=pin_label, command=lambda: self.toggle_pin(note))

        # Recurrence-specific actions, only meaningful from the calendar.
        if occurrence_date is not None:
            if is_recurring(note):
                menu.add_separator()
                menu.add_command(
                    label="✏  Edit only this occurrence",
                    command=lambda: self._ctx_open(note, occurrence_date)
                )
                menu.add_command(
                    label="✏  Edit whole series",
                    command=lambda: self._ctx_open(note, None)
                )
            else:
                # A plain dated note: offer to turn it into a repeating series.
                menu.add_separator()
                menu.add_command(
                    label="🔁  Make this repeat…",
                    command=lambda: self._ctx_make_recurring(note)
                )

        menu.add_separator()
        menu.add_command(
            label="📄  Duplicate",
            command=lambda: (self.duplicate_note(note), self.refresh_day_panel())
        )
        menu.add_command(
            label="🗑  Delete",
            command=(lambda: self._delete_note_from_calendar(note, occurrence_date))
                    if occurrence_date is not None else
                    (lambda: (self._context_delete_note(note, occurrence_date),
                             self.refresh_day_panel()))
        )

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def toggle_pin(self, note):
        """Flip a note's pinned state and re-sort the list."""
        real = self.find_note(note["id"])
        if real is None:
            return
        real["pinned"] = not real.get("pinned", False)
        self.save_notes()
        self.refresh_note_list()
        self.set_status("Pinned to top" if real["pinned"] else "Unpinned")

    def _ctx_open(self, note, occurrence_date):
        """Open a note in the editor tab from the context menu."""
        self.notebook.select(self.TAB_NOTES)
        self.open_note_in_tab(note, occurrence_date=occurrence_date)

    def _ctx_make_recurring(self, note):
        """Open a plain dated note in the editor and focus the Repeat control so
        the user can turn it into a recurring series."""
        self.notebook.select(self.TAB_NOTES)
        self.open_note_in_tab(note)
        # Nudge focus toward the recurrence dropdown so it's obvious what to do.
        try:
            self.rec_freq_menu.focus_set()
        except (AttributeError, tk.TclError):
            pass
        self.set_status("Set a repeat frequency to make this note recurring")

    def _context_delete_note(self, note, occurrence_date=None):
        """Delete triggered from the right-click menu. Routes through the normal
        delete logic so recurring-series scope prompts still apply."""
        # Flush whatever's genuinely open in the editor FIRST, under its real
        # selected_note_id. If the note being deleted here isn't the one
        # actually open, delete_current_note()'s own internal tab-switch
        # (which flushes again, as part of switching to the next tab)
        # would otherwise try to save against the note we're ABOUT to
        # delete below rather than the real one — and since that note is
        # gone by the time the flush runs, it fails with a spurious
        # "Note missing" error dialog, for a delete the user never asked
        # this note to be part of.
        self._flush_autosave()
        # Point the editor's selection at this note so delete_current_note acts
        # on it, then restore afterward isn't needed (delete resets the editor).
        self.selected_note_id = note["id"]
        self.current_occurrence_date = occurrence_date
        self.delete_current_note()

    def show_template_picker(self):
        """Inline picker listing saved templates. Clicking one fills the current
        editor with its contents. Warns before overwriting a note in progress."""
        if not self.templates:
            self.show_info(
                "No templates yet",
                "You don't have any templates. Write a note and use "
                "“🧩 Save as template”, or create one in Settings → Manage templates.")
            return

        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        frame.pack(padx=1, pady=1)

        head = tk.Frame(frame, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Use a template", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")

        for tpl in self.templates:
            name = tpl.get("name", "Untitled template")
            b = tk.Button(frame, text=f"🧩  {name}", anchor="w",
                          command=lambda t=tpl: self._apply_template(t),
                          relief="flat", cursor="hand2", bg=self.colors["sidebar"],
                          fg=self.colors["text"], font=("Segoe UI", 10))
            b.pack(fill="x", pady=2, ipady=3)

        anchor = getattr(self, "use_template_btn", None) or getattr(self, "editor", self)
        self._place_dropdown_popup(pop, anchor)

    def _apply_template(self, tpl):
        """Fill the editor from a template. If the current note has unsaved
        content, ask before replacing it."""
        tpl = normalize_template(tpl)
        try:
            st = self.capture_editor_state()
            has_content = bool((st.get("title") or "").strip() or
                               (st.get("body") or "").strip() or
                               (st.get("comments") or "").strip())
        except Exception:
            has_content = False
        self._dismiss_mini_popup()

        if has_content:
            if not self.ask_yes_no(
                "Replace current note?",
                "This will replace what's currently in the editor with the "
                "template. Any unsaved changes here will be lost. Continue?",
                icon="warning", default="no"):
                return

        # Start a fresh note, then fill it from the template.
        self.new_note()
        self.selected_note_id = None
        if tpl.get("title"):
            self.title_entry.delete(0, "end")
            self.title_entry.insert(0, tpl["title"])
            self.title_entry.config(fg=self.colors["text"])
        if tpl.get("body"):
            self.body_text.delete("1.0", "end")
            self.body_text.insert("1.0", tpl["body"])
            self._apply_formatting(self.body_text, tpl.get("formatting", []))
        if tpl.get("comments"):
            self.comments_text.delete("1.0", "end")
            self.comments_text.insert("1.0", tpl["comments"])
        category = tpl.get("category") or "General"
        if category in CATEGORY_COLORS:
            self.category_var.set(category)
            self._update_color_swatch()
        # Bring the template's checklist along.
        self._working_checklist = [
            {"text": it.get("text", ""), "done": bool(it.get("done"))}
            for it in tpl.get("checklist", []) if isinstance(it, dict)
        ]
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()
        # If the template has checklist items, open the section so they're
        # visible right away instead of hidden behind the button.
        if self._working_checklist and not self._checklist_open:
            self.toggle_checklist_section()
        else:
            self._sync_checklist_open_state()
        self._sync_calculator_open_state()
        self.update_word_count()
        self._refresh_format_buttons()
        self.set_status("New note started from template — edits here won't change the template")
        self._reset_text_undo()

    def save_current_as_template(self):
        """Save the current editor content as a reusable template. Asks for a
        template name inline, then stores title/body/comments/category."""
        try:
            st = self.capture_editor_state()
        except Exception:
            st = {}
        title = (st.get("title") or "").strip()
        body = (st.get("body") or "").strip()
        comments = (st.get("comments") or "").strip()
        if not (title or body or comments):
            self.show_info(
                "Nothing to save",
                "This note is empty, so there's nothing to turn into a template.")
            return

        default_name = title[:30] if title else "My template"

        def do_save(name):
            name = name.strip()
            if not name:
                return False  # keep the box open
            tpl = normalize_template({
                "name": name,
                "title": st.get("title", ""),
                "body": st.get("body", ""),
                "formatting": st.get("formatting", []),
                "comments": st.get("comments", ""),
                "category": st.get("category", "General"),
                "checklist": st.get("checklist", []),
            })
            # If a template with this name exists, overwrite it.
            self.templates = [t for t in self.templates if t.get("name") != name]
            self.templates.append(tpl)
            save_templates(self.templates)
            self.set_status(f"Saved template “{name}”")
            refresh = getattr(self, "_refresh_templates_panel", None)
            if callable(refresh):
                try:
                    refresh()
                except tk.TclError:
                    self._refresh_templates_panel = None
            return True

        anchor = getattr(self, "editor", self)
        self._show_inline_rename(anchor, default_name, do_save)

    def duplicate_current_note(self):
        """Duplicate the note currently open in the editor. Duplicates the SAVED
        version — if there are unsaved edits, offer to save them first so the
        copy reflects what the user sees."""
        if self.selected_note_id is None:
            self.show_info(
                "Save first",
                "This note hasn't been saved yet. Save it, then you can duplicate it."
            )
            return
        note = self.find_note(self.selected_note_id)
        if note is None:
            self.show_info("Nothing to duplicate", "No saved note is open.")
            return

        # If the editor has unsaved changes, the saved version is what gets
        # copied — make that explicit rather than silently copying stale content.
        st = self.capture_editor_state()
        if not self.editor_state_matches_saved(st):
            choice = self.ask_yes_no_cancel(
                "Unsaved changes",
                "This note has unsaved changes. Save them before duplicating?\n\n"
                "Yes = save, then duplicate\n"
                "No = duplicate the last saved version\n"
                "Cancel = do nothing"
            )
            if choice is None:
                return
            if choice:
                self.save_current_note()
                note = self.find_note(self.selected_note_id)

        clone = self.duplicate_note(note)
        # Open the fresh copy so the user can edit it right away.
        if clone is not None:
            self.open_note_in_tab(clone)

    def find_note(self, note_id):
        for n in self.notes:
            if n["id"] == note_id:
                return n
        return None

    # ---------- Category management ----------
    def count_notes_in_category(self, name):
        """How many notes use this category, counting per-occurrence overrides
        too (an override can set a different category for one day)."""
        total = 0
        for n in self.notes:
            if n.get("category") == name:
                total += 1
                continue
            for patch in (n.get("overrides") or {}).values():
                if patch.get("category") == name:
                    total += 1
                    break
        return total

    def rename_category_everywhere(self, old_name, new_name):
        """Rewrite every reference to a category when it's renamed — base notes
        AND per-occurrence overrides — so nothing is left pointing at a name
        that no longer exists."""
        for n in self.notes:
            if n.get("category") == old_name:
                n["category"] = new_name
            for patch in (n.get("overrides") or {}).values():
                if patch.get("category") == old_name:
                    patch["category"] = new_name

    def reassign_category_everywhere(self, old_name, new_name):
        """Move every note from one category to another (used when a category
        is deleted and its notes are kept)."""
        self.rename_category_everywhere(old_name, new_name)

    def refresh_category_widgets(self):
        """Push the current category set into the editor dropdown and the
        sidebar filter, without disrupting a still-valid selection."""
        # The custom category dropdown reads CATEGORY_COLORS live when opened, so
        # it needs no values push here — just keep the selection valid + refresh
        # the button's dot/label.
        if self.category_var.get() not in CATEGORY_COLORS:
            self.category_var.set(PROTECTED_CATEGORY)
        self._refresh_category_button_safe()

        # The category filter dropdown reads CATEGORY_COLORS live when opened,
        # so no values push is needed — just keep the selection valid.
        if hasattr(self, "filter_menu"):
            current = self.filter_var.get()
            if current != "All" and current not in CATEGORY_COLORS:
                self.filter_var.set("All")

    def _build_category_row(self, parent, name, redraw):
        protected = (name == PROTECTED_CATEGORY)
        color = CATEGORY_COLORS[name]

        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", pady=3)

        swatch = tk.Frame(row, bg=color, width=22, height=22, cursor="hand2")
        swatch.pack(side="left", padx=8, pady=8)
        swatch.pack_propagate(False)

        count = self.count_notes_in_category(name)
        name_lbl = tk.Label(
            row, text=f"{name}   ({count})", bg=self.colors["card"],
            fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w"
        )
        name_lbl.pack(side="left", fill="x", expand=True, padx=(2, 6))

        def recolor():
            def apply_color(chosen):
                # Categories always need a color; ignore an empty (reset) pick.
                if not chosen:
                    return
                CATEGORY_COLORS[name] = chosen
                persist_categories()
                redraw()
                self.refresh_note_list()
                self.render_calendar()
                self._update_color_swatch()
            self._show_color_palette(swatch, CATEGORY_COLORS[name], apply_color,
                                     allow_reset=False)

        # Click the swatch itself to recolor (no separate button, no OS dialog).
        swatch.bind("<Button-1>", lambda e: recolor())

        def rename():
            def do_rename(new):
                new = new.strip()
                if not new or new == name:
                    return True
                if new in CATEGORY_COLORS:
                    self.show_warning("Already exists",
                                           f"A category named “{new}” already exists.",
                                           parent=row)
                    return False
                CATEGORY_COLORS[new] = CATEGORY_COLORS.pop(name)
                self.rename_category_everywhere(name, new)
                persist_categories()
                self.save_notes()
                redraw()
                self.refresh_category_widgets()
                self.refresh_note_list()
                self.render_calendar()
                return True
            self._show_inline_rename(name_lbl, name, do_rename)

        if not protected:
            tk.Button(
                row, text="✎", command=rename, relief="flat", cursor="hand2",
                bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10)
            ).pack(side="right", padx=2)

            def delete():
                self._delete_category(name, redraw)

            tk.Button(
                row, text="🗑", command=delete, relief="flat", cursor="hand2",
                bg=self.colors["card"], fg=self.colors["danger"], font=("Segoe UI", 10)
            ).pack(side="right", padx=2)
        else:
            tk.Label(
                row, text="🔒", bg=self.colors["card"], fg=self.colors["subtext"],
                font=("Segoe UI", 10)
            ).pack(side="right", padx=6)

    def _delete_category(self, name, redraw):
        """Delete a category, asking what to do with any notes it holds."""
        count = self.count_notes_in_category(name)

        if count == 0:
            if not self.ask_yes_no("Delete category",
                                       f"Delete “{name}”? It has no notes."):
                return
            CATEGORY_COLORS.pop(name, None)
            persist_categories()
            redraw()
            self.refresh_category_widgets()
            return

        # Notes exist — ask what happens to them.
        choice = self._ask_category_deletion(name, count)
        if choice is None:
            return
        if choice == "move":
            self.reassign_category_everywhere(name, PROTECTED_CATEGORY)
        elif choice == "delete_notes":
            # Move the affected notes to trash rather than destroying them.
            doomed = [n for n in self.notes if n.get("category") == name]
            self._move_notes_to_trash(doomed)
            self.notes = [n for n in self.notes
                          if n.get("category") != name]
            # Also strip overrides that point at the dead category.
            for n in self.notes:
                overrides = n.get("overrides") or {}
                for d in list(overrides):
                    if overrides[d].get("category") == name:
                        del overrides[d]

        CATEGORY_COLORS.pop(name, None)
        persist_categories()
        self.save_notes()
        redraw()
        self.refresh_category_widgets()
        self.refresh_note_list()
        self.render_calendar()
        if self.selected_note_id and not self.find_note(self.selected_note_id):
            self.new_note()

    def _ask_category_deletion(self, name, count):
        """Returns 'move', 'delete_notes', or None (cancel). Uses the in-app
        themed dialog overlay (not a separate window)."""
        return self._themed_dialog(
            "Delete category",
            f"“{name}” has {count} note(s). What should happen to them?",
            kind="warning",
            buttons=[("Cancel", None),
                     ("Delete the notes too (permanent)", "delete_notes", "danger"),
                     (f"Move them to “{PROTECTED_CATEGORY}” (keep the notes)", "move")]
        )

    def _update_restore_button(self):
        """Show the Restore-previous button only when the open note has a
        recoverable previous version. Uses grid (row 2) to match the action row."""
        if not hasattr(self, "restore_prev_btn"):
            return
        note = self.find_note(self.selected_note_id) if self.selected_note_id else None
        has_prev = bool(note and note.get("_prev"))
        if has_prev and not self.restore_prev_btn.winfo_ismapped():
            self.restore_prev_btn.grid(row=2, column=0, columnspan=3, sticky="w",
                                       padx=(0, 8), pady=(0, 6), ipadx=10, ipady=5)
        elif not has_prev and self.restore_prev_btn.winfo_ismapped():
            self.restore_prev_btn.grid_forget()

    def restore_previous_version(self):
        """Bring back the previous non-empty version saved before the last
        drastic shortening (accidental deletion recovery)."""
        note = self.find_note(self.selected_note_id) if self.selected_note_id else None
        if not (note and note.get("_prev")):
            return
        prev = note["_prev"]
        if not self.ask_yes_no(
            "Restore previous version",
            "Bring back the earlier version of this note's text? "
            "The current text will be replaced.",
            icon="question"
        ):
            return
        # Put the previous content back into the editor and save it. Clear
        # any pending style first — the insert hook that applies pending
        # styles doesn't know this insert is a restore rather than typing,
        # so a stale pending style at this point would silently tag it.
        self._pending_styles = set()
        self._pending_text_color = None
        self._pending_highlight_color = None
        self.title_entry.delete(0, "end")
        self.title_entry.insert(0, prev.get("title", ""))
        self.title_entry.config(fg=self.colors["text"])
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", prev.get("body", ""))
        self._apply_formatting(self.body_text, prev.get("formatting", []))
        self._refresh_format_buttons()
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", prev.get("comments", ""))
        # Clear the backup so the button hides after a successful restore.
        note.pop("_prev", None)
        self.save_current_note()
        self._update_restore_button()
        self.set_status("Restored the previous version")

    def save_current_note(self, auto=False):
        title = self.title_entry.get().strip()
        if title == "Note title...":
            title = ""
        body = self.body_text.get("1.0", "end").strip()
        formatting = self._extract_formatting_for_stripped_body(self.body_text, body)
        comments = self.comments_text.get("1.0", "end").strip()
        category = self.category_var.get()

        date_raw = self.date_entry.get().strip()
        date_value = ""
        if date_raw and date_raw != "YYYY-MM-DD":
            if parse_date(date_raw):
                date_value = date_raw
            else:
                # Autosave fires while the user may still be mid-keystroke
                # typing a date (e.g. "2026-1"), which is legitimately
                # incomplete rather than wrong — only the explicit Save
                # button should interrupt with a warning here. Autosave just
                # quietly skips this round and tries again once the field
                # holds a complete, valid date (or is cleared).
                if not auto:
                    self.show_warning(
                        "Invalid date",
                        "Date should be in YYYY-MM-DD format (e.g. 2026-07-20), or left empty."
                    )
                return

        has_attachments = bool(self.current_attachments)
        has_checklist_items = bool(self._get_checklist())
        if not title and not body and not has_attachments and not has_checklist_items:
            self.show_warning("Empty note", "Write something before saving!")
            return

        recurrence = self.read_recurrence_from_ui()
        if recurrence["freq"] and not date_value:
            # Same reasoning as the invalid-date case above: don't interrupt
            # an automatic autosave for a state the user may still be
            # actively editing toward (e.g. clearing the date on a
            # recurring note before typing a new one).
            if not auto:
                self.show_warning(
                    "Repeating note needs a start date",
                    "A repeating note uses its date as the day the series starts.\n\n"
                    "Set a date, or change Repeat back to 'Does not repeat'."
                )
            return

        if recurrence["freq"] == "weekly" and not recurrence["weekdays"]:
            # Empty selection is legal — it means "the same weekday as the
            # start date" — and the summary label already says so.
            pass

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.selected_note_id is None:
            new_id = max([n["id"] for n in self.notes], default=0) + 1
            self.notes.append(normalize_note({
                "id": new_id,
                "title": title,
                "body": body,
                "formatting": formatting,
                "comments": comments,
                "category": category,
                "date": date_value,
                "color": self.current_note_color,
                "attachments": self.current_attachments,
                "recurrence": recurrence,
                "exceptions": [],
                "overrides": {},
                "updated": now,
                "created": now,
                "checklist": [dict(it) for it in self._get_checklist()],
            }))
            self.selected_note_id = new_id
            self._remember_last_open_note(new_id)
            self.set_status(("Auto-saved " if auto else "Saved at ") + now)
            if auto:
                self._show_toast("Note created")
        else:
            note = self.find_note(self.selected_note_id)
            if note is None:
                self.show_error("Note missing", "That note no longer exists.")
                return

            scope = "series"
            if is_recurring(note) and self.current_occurrence_date:
                scope = self.ask_occurrence_scope("Save", self.current_occurrence_date)
                if scope is None:
                    return

            if scope == "occurrence":
                # Only content is overridden. Date, recurrence rule and
                # attachments stay owned by the series. Formatting is
                # deliberately NOT part of an occurrence override (see
                # OVERRIDABLE_FIELDS): overrides only ever hold plain
                # strings, and even setting that aside, this occurrence's
                # body text may now differ in length/content from the base
                # note's, so the base note's formatting spans wouldn't
                # necessarily land on the right characters. An occurrence
                # with its own overridden text shows as plain text.
                note.setdefault("overrides", {})[self.current_occurrence_date] = {
                    "title": title,
                    "body": body,
                    "comments": comments,
                    "category": category,
                    "color": self.current_note_color,
                }
                note["updated"] = now
                self.set_status(("Auto-saved " if auto else "Saved ") + f"{self.current_occurrence_date} only")
                if auto:
                    self._show_toast("Note updated")
            else:
                # Before overwriting, keep a one-step backup of the OLD version
                # if the user just removed a lot of text — either a big fraction
                # (>30%) OR a large absolute amount (200+ chars). This catches
                # "I accidentally deleted a chunk" even in a very long note.
                old_len = len(note.get("body", "")) + len(note.get("title", ""))
                new_len = len(body) + len(title)
                removed = old_len - new_len
                big_fraction = old_len > 0 and new_len < old_len * 0.7
                big_absolute = removed >= 200
                if removed > 40 and (big_fraction or big_absolute):
                    note["_prev"] = {
                        "title": note.get("title", ""),
                        "body": note.get("body", ""),
                        "formatting": note.get("formatting", []),
                        "comments": note.get("comments", ""),
                    }
                note["title"] = title
                note["body"] = body
                note["formatting"] = formatting
                note["comments"] = comments
                note["category"] = category
                note["date"] = date_value
                note["color"] = self.current_note_color
                note["attachments"] = self.current_attachments
                note["recurrence"] = recurrence
                note["checklist"] = [dict(it) for it in self._get_checklist()]
                note["updated"] = now
                if not recurrence["freq"]:
                    # No longer repeating: leftover per-occurrence data would
                    # be invisible clutter, so drop it.
                    note["exceptions"] = []
                    note["overrides"] = {}
                self.set_status(("Auto-saved " if auto else "Saved at ") + now)
                if auto:
                    self._show_toast("Note updated")

        self.save_notes()
        # If this is an autosave AND a popup (e.g. the emoji picker) is open,
        # skip rebuilding the note list/calendar entirely rather than
        # deferring it — the data is safely on disk either way. Several
        # rounds of "just delay it a bit" (even waiting for the popup's own
        # destroy to fully settle first) still produced a visible tear in the
        # sidebar right as the popup closed, which points to the rebuild
        # itself being the problem near a popup's lifetime, not the timing.
        # The list/calendar simply catch up at the next natural refresh —
        # switching notes, a manual Save, or the popup closing for an
        # unrelated reason — which is a fair trade for a note you're not
        # even looking at in the sidebar while actively editing it.
        if auto and getattr(self, "_mini_popup", None) is not None:
            # Remember that the sidebar/calendar are now slightly stale, so
            # the next natural transition (switching notes, changing tabs)
            # can catch them up — see _catch_up_deferred_refresh().
            self._note_list_needs_refresh = True
        else:
            self.refresh_note_list()
            self.render_calendar()
            self._note_list_needs_refresh = False
        # The saved note now matches disk; update this tab's snapshot so its
        # dirty dot clears, and refresh the strip labels/markers.
        self._sync_active_tab()
        self.refresh_tab_strip()
        self._update_restore_button()
        # If the calendar day panel is showing, reflect the edit there too.
        if getattr(self, "_day_panel_mode", "empty") != "empty":
            self.refresh_day_panel()
        # Only an explicit Save click sends you back — autosave alone shouldn't
        # yank the calendar into view mid-typing after just a short pause.
        if not auto and getattr(self, "_pending_calendar_return", None):
            self._return_to_calendar()

    # ---------- Trash / recently deleted ----------
    def _restore_from_trash(self, entry):
        """Bring a trashed note back into the active list. If its category was
        deleted meanwhile, fall back to General so it isn't orphaned."""
        note = {k: v for k, v in entry.items() if k != "deleted_at"}
        note = normalize_note(note)
        # Fresh id to avoid any collision with current notes.
        note["id"] = max([n["id"] for n in self.notes], default=0) + 1
        if note.get("category") not in CATEGORY_COLORS:
            note["category"] = PROTECTED_CATEGORY
        self.notes.append(note)
        self.save_notes()
        # Remove from trash.
        self.trash = [e for e in self.trash if e is not entry]
        save_trash(self.trash)
        self.refresh_note_list()
        self.render_calendar()

    def _attach_dup_preview(self, widget, note):
        """Show a small floating preview of a note's contents while the mouse
        hovers over its row in the duplicates dialog, so the user can tell the
        copies apart before choosing. Vanishes on mouse-leave — no clicking."""
        tip = {"win": None}

        def show(event):
            if tip["win"] is not None:
                return
            win = tk.Toplevel(widget)
            win.wm_overrideredirect(True)  # no title bar / borders
            win.configure(bg=self.colors["accent"])
            frame = tk.Frame(win, bg=self.colors["card"], padx=10, pady=8)
            frame.pack(padx=1, pady=1)

            def line(label, value):
                if not value:
                    return
                row = tk.Frame(frame, bg=self.colors["card"])
                row.pack(fill="x", anchor="w")
                tk.Label(row, text=f"{label}: ", font=("Segoe UI", 8, "bold"),
                         bg=self.colors["card"], fg=self.colors["subtext"]).pack(side="left")
                tk.Label(row, text=value, font=("Segoe UI", 8), bg=self.colors["card"],
                         fg=self.colors["text"], wraplength=260, justify="left"
                         ).pack(side="left")

            title = (note.get("title") or "").strip() or "(untitled)"
            line("Title", title[:60])
            body = (note.get("body") or "").strip()
            if body:
                preview = body[:120] + ("…" if len(body) > 120 else "")
                line("Note", preview)
            comments = (note.get("comments") or "").strip()
            if comments:
                line("Comments", comments[:80] + ("…" if len(comments) > 80 else ""))
            line("Date", note.get("date"))
            if note.get("color"):
                line("Color", note["color"])
            atts = note.get("attachments", [])
            if atts:
                line("Attachments", ", ".join(a.get("filename", "?") for a in atts))
            created = note.get("created", "")
            if created:
                line("Created", created)

            # Position just below-right of the cursor.
            win.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 12}")
            tip["win"] = win

        def hide(event=None):
            if tip["win"] is not None:
                try:
                    tip["win"].destroy()
                except tk.TclError:
                    pass
                tip["win"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)
        # Also hide if the row is destroyed (dialog rebuild).
        widget.bind("<Destroy>", hide)

    def _bind_wheel_tree(self, root, handler):
        """Bind a mousewheel handler to a widget and all its descendants, so the
        wheel works anywhere over a dialog, not just on the scrollbar."""
        root.bind("<MouseWheel>", handler)
        for child in root.winfo_children():
            self._bind_wheel_tree(child, handler)

    def _cleanup_selected_duplicates(self, del_vars, dlg, refresh, announce=False):
        """Move the checkbox-selected duplicates to trash. `del_vars` is a list of
        (delete_var, note, group) — a note is removed when its var is set. Within
        each group, the attachments of removed notes are merged into a
        surviving copy (the first note in that group NOT marked for deletion), so
        nothing unique is lost. If a whole group is checked, all are removed."""
        # Figure out, per group, which notes are being removed and which survive.
        by_group = {}
        for var, note, group in del_vars:
            gid = id(group)
            by_group.setdefault(gid, {"group": group, "remove": []})
            if var.get():
                by_group[gid]["remove"].append(note)

        to_trash = []
        for info in by_group.values():
            group = info["group"]
            remove = info["remove"]
            if not remove:
                continue
            survivors = [n for n in group if n not in remove]
            if survivors:
                # Merge removed notes' attachments into the first survivor.
                kept = survivors[0]
                merged_attach = list(kept.get("attachments", []))
                seen_attach = {a.get("stored_as") for a in merged_attach}
                for note in remove:
                    for a in note.get("attachments", []):
                        if a.get("stored_as") not in seen_attach:
                            merged_attach.append(a)
                            seen_attach.add(a.get("stored_as"))
                kept["attachments"] = merged_attach
            to_trash.extend(remove)

        if not to_trash:
            self.show_info(
                "Nothing selected",
                "Tick the duplicates you want to remove first.", parent=dlg)
            return
        if not self.ask_yes_no(
            "Move duplicates to trash",
            f"Move {len(to_trash)} selected note(s) to the trash? "
            f"You can restore them within {TRASH_RETENTION_DAYS} days.",
            parent=dlg, icon="question"
        ):
            return
        trash_ids = {id(n) for n in to_trash}
        self._move_notes_to_trash(to_trash)
        self.notes = [n for n in self.notes if id(n) not in trash_ids]
        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        if announce:
            self.show_info("Cleaned up",
                                f"Moved {len(to_trash)} duplicate(s) to the trash.")
        refresh()

    def _build_trash_row(self, parent, entry, redraw):
        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", pady=3)

        left = tk.Frame(row, bg=self.colors["card"])
        left.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        title = (entry.get("title") or "").strip() or "(untitled)"
        tk.Label(left, text=title[:42], bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        # Show when it was deleted and how long remains.
        meta = entry.get("deleted_at", "")
        remaining = self._days_left_in_trash(meta)
        sub = f"deleted {meta[:10]}" if meta else "deleted"
        if remaining is not None:
            sub += f" · {remaining} day(s) left"
        tk.Label(left, text=sub, bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8), anchor="w").pack(fill="x")

        def restore():
            self._restore_from_trash(entry)
            redraw()

        def delete_forever():
            if self.ask_yes_no(
                "Delete permanently",
                f"Permanently delete “{title}”? This can't be undone.",
                parent=row, icon="warning", default="no"
            ):
                _delete_attachment_files([entry])
                self.trash = [e for e in self.trash if e is not entry]
                save_trash(self.trash)
                redraw()

        tk.Button(row, text="Delete", command=delete_forever, relief="flat",
                  cursor="hand2", bg=self.colors["danger"], fg="white",
                  font=("Segoe UI", 8, "bold")).pack(side="right", padx=(2, 8), ipadx=4, ipady=1)
        tk.Button(row, text="Restore", command=restore, relief="flat",
                  cursor="hand2", bg=self.colors["accent"], fg="white",
                  font=("Segoe UI", 8, "bold")).pack(side="right", padx=2, ipadx=4, ipady=1)

    def _days_left_in_trash(self, deleted_at):
        """How many days until this trashed note auto-purges. None if unknown."""
        try:
            when = datetime.strptime(deleted_at, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None
        elapsed = (datetime.now() - when).days
        return max(0, TRASH_RETENTION_DAYS - elapsed)

    def _move_notes_to_trash(self, notes_to_trash):
        """Move one or more notes into the trash with a deletion timestamp,
        instead of destroying them. Used by every delete path so nothing is ever
        lost without a 30-day grace period."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for note in notes_to_trash:
            entry = dict(note)
            entry["deleted_at"] = stamp
            self.trash.append(entry)
        save_trash(self.trash)

    def delete_current_note(self):
        if self.selected_note_id is None:
            self.show_info("Nothing to delete", "No note is selected.")
            return

        note = self.find_note(self.selected_note_id)
        if note is None:
            self.show_info("Nothing to delete", "No note is selected.")
            return

        if is_recurring(note) and self.current_occurrence_date:
            scope = self.ask_occurrence_scope("Delete", self.current_occurrence_date)
            if scope is None:
                return
            if scope == "occurrence":
                exceptions = set(note.get("exceptions") or [])
                exceptions.add(self.current_occurrence_date)
                note["exceptions"] = sorted(exceptions)
                note["overrides"].pop(self.current_occurrence_date, None)
                note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_notes()
                self.new_note()
                self.refresh_note_list()
                self.render_calendar()
                self.set_status("Removed that one occurrence")
                return

        attachment_count = len(note.get("attachments") or [])
        warning = ""
        if attachment_count:
            plural = "s" if attachment_count != 1 else ""
            warning = f"\n\n{attachment_count} attached file{plural} will go to trash with it."
        confirm = self.ask_yes_no(
            "Delete note",
            ("Delete this entire repeating series?" if is_recurring(note)
             else "Are you sure you want to delete this note?") + warning
        )
        if confirm:
            deleted_id = self.selected_note_id
            # Move to trash (30-day recovery) rather than destroying it.
            doomed = [n for n in self.notes if n["id"] == deleted_id]
            self._move_notes_to_trash(doomed)
            self.notes = [n for n in self.notes if n["id"] != deleted_id]
            self.save_notes()
            # Close any open tab that pointed at the deleted note (force: its
            # underlying note is gone, so there's nothing to save).
            self.open_tabs = [t for t in self.open_tabs
                              if t["state"]["selected_note_id"] != deleted_id]
            if not self.open_tabs:
                self.active_tab_index = None
                self.new_note()
            else:
                self.active_tab_index = None
                self.switch_to_tab(min(0, len(self.open_tabs) - 1))
            self.refresh_tab_strip()
            self.refresh_note_list()
            self.render_calendar()
            self.set_status("Note moved to Trash (recoverable for 30 days)")

    def report_callback_exception(self, exc_type, exc_value, exc_tb):
        """Overrides Tkinter's default handler for exceptions raised inside
        any bound callback (button click, keyboard shortcut, timer, ...).
        The default implementation only prints to stderr — invisible in this
        app's --windowed build, meaning an unexpected error would otherwise
        fail completely silently: no crash, but no feedback either, leaving
        the user unsure whether their click did anything or their data is
        still safe. This doesn't prevent the failure (whatever the callback
        was doing stops at the point it broke, same as before), but at least
        says so, and leaves a trace to diagnose later — same log file the
        top-level crash handler uses, so both end up in one place."""
        import traceback
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log_path = os.path.join(APP_DIR, "crash_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now().isoformat()} (callback) ---\n{details}\n")
        except (IOError, OSError, NameError):
            pass
        try:
            self._show_toast("Something went wrong with that — your other notes are safe", kind="error")
        except tk.TclError:
            pass

    def on_app_close(self):
        """Before the window closes, offer to save any tabs with unsaved work."""
        self._flush_autosave()
        self._sync_active_tab()
        dirty = [t for t in self.open_tabs
                 if not self.editor_state_matches_saved(t["state"])]
        if dirty:
            names = ", ".join(self._tab_title(t) for t in dirty[:4])
            if len(dirty) > 4:
                names += f", +{len(dirty) - 4} more"
            choice = self.ask_yes_no_cancel(
                "Unsaved notes",
                f"You have {len(dirty)} unsaved note(s):\n{names}\n\n"
                "Save them before quitting?\n\n"
                "Yes = save all · No = discard · Cancel = keep working"
            )
            if choice is None:
                return  # cancel: don't close
            if choice:
                # Save each dirty tab.
                for i in range(len(self.open_tabs)):
                    self.switch_to_tab(i)
                    if not self.editor_state_matches_saved(self.open_tabs[i]["state"]):
                        self.save_current_note()
        self.destroy()

    def set_status(self, text):
        self.status_lbl.config(text=text)

    def _show_toast(self, text, kind="success"):
        """Briefly show a small floating banner near the top of the window —
        visible regardless of scroll position or which tab is active. Used for
        'auto-saved' feedback so it's never missed inside a long note."""
        if not hasattr(self, "toast_frame"):
            return
        color = {"success": self.colors["success"],
                 "info": self.colors["accent"],
                 "error": self.colors["danger"]}.get(kind, self.colors["success"])
        try:
            self.toast_frame.configure(bg=color)
            self.toast_lbl.configure(text=f"✓  {text}", bg=color, fg="white")
            self.toast_frame.place(relx=0.5, rely=0.0, anchor="n", y=4)
            self.toast_frame.lift()
        except tk.TclError:
            return

        if self._toast_hide_job is not None:
            try:
                self.after_cancel(self._toast_hide_job)
            except (tk.TclError, ValueError):
                pass

        def hide():
            try:
                self.toast_frame.place_forget()
            except tk.TclError:
                pass
            self._toast_hide_job = None

        self._toast_hide_job = self.after(1800, hide)


def _main():
    """Launch the app with a top-level guard. In the --windowed .exe there's no
    console, so an unhandled exception would make the app vanish with no trace.
    This shows the error and, where possible, points the user at their data."""
    # Tried declaring the process DPI-aware here, to fix two side-by-side
    # Settings panels rendering at visibly different sizes despite Tk's
    # own layout math treating them as pixel-identical — reverted. It
    # made the whole app's rendering noticeably worse (blurrier) without
    # actually fixing the size mismatch, on the machine that reported the
    # original bug. Left unresolved rather than trading one visible
    # problem for a worse one.
    try:
        app = NoteOrganizer()
        app.protocol("WM_DELETE_WINDOW", app.on_app_close)
        app.mainloop()
    except Exception as exc:  # noqa: BLE001 — last-resort catch-all on purpose
        import traceback
        details = traceback.format_exc()
        # Try to write a crash log next to the data, best-effort.
        try:
            log_path = os.path.join(APP_DIR, "crash_log.txt")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now().isoformat()} ---\n{details}\n")
        except (IOError, OSError, NameError):
            log_path = None
        try:
            root = tk.Tk()
            root.withdraw()
            msg = ("Notes Organizer hit an unexpected error and needs to close.\n\n"
                   f"{type(exc).__name__}: {exc}\n\n"
                   "Your saved notes are safe on disk.")
            if log_path:
                msg += f"\n\nDetails were written to:\n{log_path}"
            # A plain standard-library dialog on purpose, not our own themed
            # one: if we got here, app construction itself may have failed,
            # so nothing that depends on the app's own widgets/theming can be
            # trusted to work either.
            from tkinter import messagebox as _messagebox
            _messagebox.showerror("Notes Organizer", msg)
            root.destroy()
        except Exception:
            # Even the error dialog failed — print as a final fallback.
            print(details)


if __name__ == "__main__":
    _main()