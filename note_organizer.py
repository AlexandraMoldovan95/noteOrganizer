# note_organizer.py
# A simple, colorful, offline Note Organizer app
# Notes are saved locally to notes_data.json, so they persist between sessions.

import tkinter as tk
from tkinter import ttk, filedialog
import tkinter.font as tkfont
import copy
import json
import os
import sys
import shutil
import zipfile
import tempfile
import zlib
import threading
import time
import base64
from html import escape
import calendar as cal_module
import re
import math
import functools
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
APP_VERSION = "0.82.233"


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
# Picking the data folder, migrating from older locations and cleaning up
# leftovers now live in noteorganizer/core/paths.py. That module has NO
# import-time side effects - the calls below are still what actually runs
# them, unchanged for now. Re-exported so callers and the QA scripts are
# unaffected.
from noteorganizer.core import paths as _core_paths
from noteorganizer.core import single_instance
from noteorganizer.core.paths import (
    bundled_file,
    get_appdata_dir,
    _is_writable,
    resolve_data_dir,
    get_legacy_dirs,
    count_notes_in,
    _copy_attachments,
    _timestamped_backup,
    run_migrations,
    OWNED_FILENAMES,
    OWNED_PREFIXES,
    _content_signatures,
    _is_owned_file,
    is_redundant_copy,
    _attachments_are_covered,
    purge_stale_copies,
)


# ---- Startup state, filled in by initialise() ----
#
# These stay None until initialise() runs. NOTHING here happens at import
# time any more, and that is the entire point: importing this module used
# to resolve a data folder, migrate notes into it, DELETE files it judged
# stale, and write settings.json — so merely importing the app could
# destroy a notebook. It did, once (see docs/ISSUES_LOG.md, "The cleanup
# that deleted the real notebook"), and it is why every test in this
# project has to be run from a throwaway directory.
#
# Now an import is inert and the work happens when someone asks for it.
APP_DIR = None
STORAGE_WARNING = None
MIGRATION_INFO = None
PURGED_DIRS = None
DATA_FILE = None
SETTINGS_FILE = None
ATTACHMENTS_DIR = None
TRASH_FILE = None
TEMPLATES_FILE = None
VERSION_CHANGE = None
FIRST_LAUNCH_DATE = None

_initialised = False


def initialise(app_dir=None, resolved=None):
    """Work out where the data lives, bring it up to date, and open it.

    Does, in order: resolve the data folder, migrate anything left in an
    older location, purge genuinely stale copies, point core.paths at the
    result, then record the app version and first-launch date.

    Called by NoteOrganizer.__init__ and by _main(), so ordinary use needs
    no change. Anything that wants the data layer WITHOUT building a
    window — test_data_safety.py, say — must call this explicitly.

    Idempotent: calling it again is a no-op, so it does not matter whether
    the app or the entry point gets there first.

    Args:
        app_dir: Override the data folder. Only for tests; normally the
            folder is derived from this file's location.
        resolved: A ``(folder, warning)`` pair resolve_data_dir already
            answered. _main passes the one it took the notebook lock in,
            so the folder locked and the folder opened are the same by
            construction rather than by two answers agreeing.

    Returns:
        The resolved data folder.
    """
    global APP_DIR, STORAGE_WARNING, MIGRATION_INFO, PURGED_DIRS
    global DATA_FILE, SETTINGS_FILE, ATTACHMENTS_DIR, TRASH_FILE, TEMPLATES_FILE
    global VERSION_CHANGE, FIRST_LAUNCH_DATE, _initialised
    if _initialised:
        return APP_DIR

    if resolved is not None:
        APP_DIR, STORAGE_WARNING = resolved
    else:
        # The data folder is resolved relative to THIS file, the entry
        # point. resolve_data_dir() takes it as an argument rather than
        # deriving it from its own location: once that code moved into
        # noteorganizer/core/, its __file__ pointed there instead, and the
        # app silently picked a data folder two levels below the right one.
        base = app_dir or os.path.dirname(os.path.abspath(__file__))
        APP_DIR, STORAGE_WARNING = resolve_data_dir(base)
    MIGRATION_INFO = run_migrations(APP_DIR)
    PURGED_DIRS = purge_stale_copies(APP_DIR)

    # Hand the resolved folder to core.paths, which works out the individual
    # file locations and creates the attachments folder. Everything in
    # core.storage reads them from there, so this has to happen before any
    # load/save call. Mirrored onto this module so existing callers and the
    # QA scripts still find note_organizer.DATA_FILE and friends.
    _core_paths.configure(APP_DIR)
    DATA_FILE = _core_paths.DATA_FILE
    SETTINGS_FILE = _core_paths.SETTINGS_FILE
    ATTACHMENTS_DIR = _core_paths.ATTACHMENTS_DIR
    TRASH_FILE = _core_paths.TRASH_FILE
    TEMPLATES_FILE = _core_paths.TEMPLATES_FILE

    # These write to settings.json, so they belong after configure() and
    # are just as much a side effect as the migration above.
    VERSION_CHANGE = detect_version_change()
    FIRST_LAUNCH_DATE = get_first_launch_date()

    _initialised = True
    return APP_DIR


# Reading/writing settings, templates and trash, plus the pre-flight
# notes backup, now live in noteorganizer/core/storage.py. They read the
# file locations from core.paths, which configure() filled in above.
# Duplicate detection lives in noteorganizer/core/duplicates.py.
from noteorganizer.core.duplicates import (
    find_duplicate_groups,
    _strip_copy_suffix,
    _normalize_ws,
    _dup_key,
)

# Rich-text span storage lives in noteorganizer/core/formatting.py.
from noteorganizer.core import clipboard
from noteorganizer.core import tables as core_tables
from noteorganizer.core.tables import is_table_row, with_caret_line
from noteorganizer.core.richtext import (html_to_note, note_to_html,
                                        html_document, reflow_wrapped)
from noteorganizer.core.formatting import (
    normalize_paragraphs,
    parse_list_marker,
    strip_list_markers,
    marker_for,
    bullet_level_of,
    renumber,
    shift_spans,
    merge_spans,
    split_toolbar_rows,
    MAX_INDENT,
    MAX_FORMATTING_SPANS,
    parse_font_tag,
    is_format_tag,
    resolve_font_runs,
    clamp_spans_per_line,
    MAX_SPANS_PER_LINE,
    COLOR_FORMAT_STYLES,
    FONT_VALUE_STYLES,
    FONT_FAMILIES,
    FONT_SIZES,
    MONOSPACE_FAMILIES,
    char_class as core_char_class,
    color_tag_name as core_color_tag_name,
    font_tag_for as core_font_tag_for,
    KNOWN_FORMAT_STYLES,
    VALUE_FORMAT_STYLES,
    _is_valid_hex_color,
    normalize_formatting,
)

from noteorganizer.core.storage import (
    TRASH_RETENTION_DAYS,
    trash_retention_days,
    load_settings,
    save_settings,
    mend_surrogates,
    normalize_template,
    load_templates,
    save_templates,
    load_trash,
    save_trash,
    _delete_attachment_files,
    attachment_names_in,
    copy_attachment_file,
    purge_expired_trash,
    # The same question the purge acts on, asked without acting: what a
    # retention window has already outlived. Re-exported here because the
    # qa suite reaches everything through `import note_organizer as NO`.
    trash_entries_past_window,
    backup_notes_file,
    # Aliased because the methods that call them are also called load_notes
    # and save_notes; without the alias the method name would shadow the
    # function inside the class body.
    load_notes as core_load_notes,
    save_notes as core_save_notes,
    get_setting,
    save_setting,
    move_notes_to_trash as core_move_to_trash,
    days_left_in_trash as core_days_left_in_trash,
    restore_from_trash as core_restore_from_trash,
    restore_many_from_trash as core_restore_many_from_trash,
)


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


# VERSION_CHANGE / FIRST_LAUNCH_DATE are set by initialise().


# ---- UI, split into mixins (see noteorganizer/ui/__init__.py) ----
# Each mixin holds one area's methods; Python recombines them into a
# single class below, so every method still uses self exactly as before.
from noteorganizer.ui.calculator_panel import CalculatorPanelMixin
from noteorganizer.ui.attachments import AttachmentsMixin
from noteorganizer.ui.calendar_view import CalendarViewMixin
from noteorganizer.ui.dialogs import DialogsMixin
from noteorganizer.ui.settings_page import SettingsPageMixin


# ---- Note schema + one-time cleanup ----
# The note model moved to noteorganizer/core/model.py; the live category
# map and its load/save moved to noteorganizer/core/categories.py.
# Re-exported so existing callers and the QA scripts are unaffected.
from noteorganizer.core.categories import (
    CATEGORY_COLORS,
    load_categories,
    persist_categories,
    category_name_refusal,
    MAX_CATEGORIES,
    MAX_CATEGORY_NAME,
)
from noteorganizer.core.model import (
    NOTE_DEFAULTS,
    find_note as core_find_note,
    notes_on_date as core_notes_on_date,
    count_notes_in_category as core_count_in_category,
    rename_category_everywhere as core_rename_category,
    _extract_first_emoji,
    _darken_hex,
    _truncate,
    _note_str,
    normalize_note,
    find_by_uid,
    split_by_identity,
    apply_shared_update,
    shared_update_changes,
    UPDATABLE_FROM_SHARED,
    UPDATABLE_FROM_BACKUP,
    PREV_TEXT_FIELDS,
    note_richness,
    note_is_empty,
    reading_time,
    clean_notes,
    content_signature,
    sanitize_color,
    MAX_CHECKLIST_ITEMS,
    MAX_ATTACHMENTS,
)


# ---- Recurrence engine ----
#
# Moved to noteorganizer/core/recurrence.py — a recurring note is stored
# ONCE and its occurrences are computed on demand; see that module (and
# docs/CODE_TOUR.md) for how and why. Re-exported here so existing
# callers and the QA scripts keep working unchanged.
from noteorganizer.core.recurrence import (
    WEEKDAY_NAMES,
    FREQ_LABELS,
    RECURRENCE_DEFAULTS,
    OVERRIDABLE_FIELDS,
    MAX_OCCURRENCES,
    parse_date,
    format_date,
    normalize_recurrence,
    is_recurring,
    expand_occurrences,
    next_occurrence_on_or_after,
    effective_note,
    describe_recurrence,
)


# The calculator's expression parser now lives in its own module — see
# noteorganizer/core/calculator.py. Re-exported here so existing callers
# (and the QA scripts, which reach for `note_organizer.<name>`) keep
# working unchanged; _CalcError keeps its old private name for the same
# reason.
from noteorganizer.core.calculator import (
    CalcError as _CalcError,
    evaluate_calculator_expression,
    format_calculator_result,
)




# ---- Share codes (move notes between devices as copy-paste text) ----
# Moved to noteorganizer/core/sharing.py, together with the ZIP-import
# path guard. Re-exported so existing callers are unaffected.
from noteorganizer.core.sharing import (
    SHARE_CODE_PREFIX,
    MAX_SHARE_CODE_CHARS,
    MAX_DECOMPRESSED_BYTES,
    MAX_SHARED_NOTES,
    SHAREABLE_FIELDS,
    encode_share_code,
    decode_share_code,
    _safe_extract_zip,
)



# ---- Themes ----
# Palettes, theme names/labels, the default categories and the swatch
# lists all moved to noteorganizer/core/themes.py — pure data, no logic.
# Re-exported so existing callers and the QA scripts are unaffected.
from noteorganizer.core.themes import (
    blend as core_blend,
    contrasting_fg as core_contrasting_fg,
    inset_surface,
    hairline,
    THEMES,
    DARK_THEMES,
    LIGHT_THEMES,
    THEME_LABELS,
    DEFAULT_CATEGORY_COLORS,
    PALETTE_COLORS,
    PROTECTED_CATEGORY,
    PRESET_NOTE_COLORS,
    HIGHLIGHT_COLOR_PALETTE,
    SIDEBAR_WIDTH,
    EDITOR_MIN_WIDTH,
)


def _undo_atom(method):
    """One table operation = ONE undo unit.

    A commit, a resize, a fill are each a burst of small inserts and
    deletes, and Tk's autoseparators made every one its own Ctrl+Z step:
    undoing a cell edit could stop halfway -- the old value gone, the
    padding collapsed. The wrapper opens a unit, runs the operation,
    closes the unit; nested wrapped calls keep the outermost unit.
    """
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        self._undo_atom_begin()
        try:
            return method(self, *args, **kwargs)
        finally:
            self._undo_atom_end()
    return wrapped


def _undo_hidden(method):
    """The method's edits never reach the undo stack.

    Rebuilding the drawn grids deletes and re-creates embedded window
    characters; recorded, they turned every second Ctrl+Z into "undo the
    redraw" instead of "undo my edit", stepping through phantom windows.
    The pipe text is the truth and stays recorded; the drawing is not an
    edit. Tk keeps the existing stack across the undo=False window --
    verified against a live Text widget, not assumed.
    """
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        depth = getattr(self, "_undo_hidden_depth", 0)
        self._undo_hidden_depth = depth + 1
        prev = None
        if depth == 0 and hasattr(self, "body_text"):
            try:
                prev = self.body_text.cget("undo")
                self.body_text.configure(undo=False)
            except tk.TclError:
                prev = None
        try:
            return method(self, *args, **kwargs)
        finally:
            self._undo_hidden_depth = depth
            if depth == 0 and prev is not None:
                try:
                    self.body_text.configure(undo=prev)
                except tk.TclError:
                    pass
    return wrapped


def _checklist_rows_current(drawn, items, theme):
    """True when the checklist rows on screen were drawn from exactly this
    list -- the same item objects, in this order, still saying what each
    item says -- and in this theme.

    Only then may a change touch one row instead of redrawing them all:
    every row's tick box and bin close over its own item, so a row left
    standing beside a DIFFERENT item would tick or remove the wrong one.
    *drawn* is the record _render_checklist_items keeps, or None.
    """
    return (drawn is not None and drawn["items"] is items
            and drawn["theme"] == theme
            and len(drawn["rows"]) == len(items)
            and all(rec[0] is item
                    and rec[2] == (item.get("text", ""), bool(item.get("done")))
                    for rec, item in zip(drawn["rows"], items)))



class NoteOrganizer(AttachmentsMixin, CalculatorPanelMixin, CalendarViewMixin,
                    DialogsMixin, SettingsPageMixin, tk.Tk):
    def __init__(self):
        # Make sure the data layer is open before anything reads it. Safe to
        # call repeatedly; _main() calls it too.
        initialise()
        super().__init__()
        self.title("Note Organizer")
        # Armed from day one, for EVERY popup path -- and for every WINDOW:
        # typing in a popup makes the popup the active window, so its
        # deactivation lands on the popup's own toplevel and a binding on
        # the root alone never hears it.
        #
        # On the two window classes rather than with bind_all. Tk sends
        # Activate and Deactivate to every widget INSIDE a window, not only
        # to the window, so bind_all ran these handlers once per widget on
        # every Alt+Tab -- 2,132 calls for a list of 300 notes, counted by
        # delivering the event the way Tk does, each returning at its first
        # line because the widget was not a window. Only windows carry these
        # class tags, so the question the handlers ask first is now answered
        # before Python is ever called.
        for window_class in (self.winfo_class(), "Toplevel"):
            self.bind_class(window_class, "<Deactivate>",
                            self._on_app_deactivated, add="+")
            self.bind_class(window_class, "<Activate>",
                            self._on_app_activated, add="+")
        self._deactivate_bound = True
        # ...and the heartbeat, because a popup holding the activation
        # receives neither event when the user switches away.
        self.after(300, self._popup_foreground_watch)
        # Let core say "that write FAILED" to the screen: trash, templates
        # and settings save through routes nobody checks the return of, and
        # a failed write used to be completely invisible. core also logs
        # every failure to crash_log.txt, callback or not.
        from noteorganizer.core import storage as _core_storage
        _core_storage.on_write_failure = self._on_data_write_failure
        self.geometry("900x600")
        # The smallest window that still looks like the app, measured and
        # photographed rather than guessed. The sidebar's fixed parts -- the
        # heading, search, sort and select row above the list, New Note,
        # Import, Share and Settings below it -- take about 496 pixels of
        # height, so at the old 500x400 the list had NO room at all: an app
        # with no notes in it, which is what a person who drags the window
        # small or snaps it to a corner saw. At 600 the list holds a whole
        # card. The width stays small enough for a half-screen snap on a
        # 1280-wide (150%-scaled) laptop; below 900 the page scrolls
        # sideways, which is the design choice the main canvas already makes.
        self.minsize(640, 600)
        # On <Map>, not on after_idle. Measured: before the window is
        # mapped, wm_frame() names a DIFFERENT window from the one it
        # names afterwards -- and the compositor accepts a paint on that
        # first handle, reports success, and then Windows throws the
        # window away. That is why a fresh launch kept the system colours
        # until a theme was switched: the switch was simply the first
        # paint that happened after mapping.
        #
        # Bound to the window ITSELF, not with self.bind. A binding on the
        # main window is also a binding on every widget inside it (each one
        # carries its window's tag), so this used to repaint the title bar
        # once per widget whenever a page was shown -- 1,939 paints for a
        # rebuild of 300 notes, and as many again for every switch back to
        # the list. One paint costs next to nothing; two thousand of them
        # did not. See _bind_window_only.
        self._bind_window_only("<Map>", lambda _e: self._paint_title_bar())
        # On <Map> for the same reason: before the window is mapped,
        # wm_frame() names a different window. See _stop_whole_repaints.
        self._bind_window_only("<Map>", lambda _e: self._stop_whole_repaints())

        self.theme_name = self.load_theme_setting()
        self.colors = THEMES[self.theme_name]
        # Not before this line: the icon is chosen by the theme's accent,
        # so asking for it in the constructor's first breath raised on a
        # self.colors that did not exist yet. The raise was swallowed --
        # correctly, an icon is never worth failing to open over -- and
        # the window simply wore the toolkit's feather. It only looked
        # fine in testing because switching a theme re-runs this, which
        # is exactly how the title bar's own startup bug hid too.
        self._set_window_icon()
        # Read before the editor is built, so the body text is created in the
        # right font rather than being restyled a moment after it appears.
        self._load_editor_font()
        # Track last-used dark/light for the quick toggle button.
        self._last_dark_theme = self.theme_name if self.theme_name in DARK_THEMES else "dark"
        self._last_light_theme = self.theme_name if self.theme_name in LIGHT_THEMES else "light"

        # Load the user's categories into the live map BEFORE notes load, so
        # normalize_note validates each note's category against the real set.
        CATEGORY_COLORS.clear()
        CATEGORY_COLORS.update(load_categories())

        self._cleanup_report = None  # filled in by load_notes if cleanup ran
        self._categories_adopted = []  # names load_notes brought back from the notes
        self._version_backup_path = None  # filled in by load_notes on a version upgrade
        self._corrupt_notes_report = None  # (flag, preserved-copy path) if the notes file was unreadable
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
        # Each value passes sanitize_color: settings.json is hand-editable
        # and rides inside backups, and one garbage value here reached
        # render_calendar's configure() on every launch — the make-the-app-
        # unopenable class, through the calendar's door.
        saved_day_colors = load_settings().get("day_colors")
        self.day_colors = {}
        if isinstance(saved_day_colors, dict):
            for d, c in saved_day_colors.items():
                c = sanitize_color(c)
                if isinstance(d, str) and c:
                    self.day_colors[d] = c

        # User-chosen emoji markers for individual calendar days (date -> list
        # of emoji characters), independent of any note. E.g. flag a day with
        # a couple of markers even before you've written a note for it.
        # Capped at 3 per day on the way in — the same cap the picker
        # enforces — so a hand-edited file can't stack hundreds of markers
        # into every day cell's redraw.
        saved_day_emoji = load_settings().get("day_emoji")
        self.day_emoji = {}
        if isinstance(saved_day_emoji, dict):
            for d, v in saved_day_emoji.items():
                if isinstance(v, list):
                    kept = [e for e in v if isinstance(e, str) and e][:3]
                    if kept:
                        self.day_emoji[d] = kept
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
        self._bind_global_shortcuts()
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

    # The desktop compositor's attribute numbers, from the DWM docs. Only
    # these four matter here: the caption's fill, its text, the window's
    # border, and whether Windows draws its own minimise/maximise/close
    # glyphs light or dark. That last one is not optional -- a dark
    # caption with the light-theme glyphs leaves a close button nobody
    # can see.
    _DWMWA_USE_IMMERSIVE_DARK_MODE = 20
    _DWMWA_BORDER_COLOR = 34
    _DWMWA_CAPTION_COLOR = 35
    _DWMWA_TEXT_COLOR = 36

    # A bind tag only the main window carries. See _bind_window_only.
    _WINDOW_ONLY_TAG = "NoteOrganizerWindowOnly"

    def _bind_window_only(self, sequence, func):
        """Bind `func` to `sequence` on the main window itself -- never on
        the widgets inside it.

        `self.bind` cannot say that. Every widget carries its window's tag
        among its own, which is what lets a key pressed anywhere reach a
        window-level shortcut -- and it means a <Map> or <Configure> bound
        on the window also runs for every widget that is mapped or laid
        out. A list rebuild of 300 notes repainted the title bar 1,939
        times that way, for a handler that only ever cared about the
        window. (The calendar's width step was the other one; it listens to
        its own grid now, which is the event it really wanted.)

        So the window gets a tag of its own, placed right after its own
        name, and window-level handlers live on that. Nothing else
        carries it.

        Before moving a handler here, ask what the storm was doing for it:
        the calendar's step had been riding on its descendants' events to
        notice a resize made while it was hidden, and a window-only
        binding silently took that away.
        """
        tags = self.bindtags()
        if self._WINDOW_ONLY_TAG not in tags:
            self.bindtags((tags[0], self._WINDOW_ONLY_TAG) + tuple(tags[1:]))
        return self.bind_class(self._WINDOW_ONLY_TAG, sequence, func, add="+")

    # The two window classes Tk registers on Windows, and the class styles
    # that make Windows repaint a window WHOLE whenever its size changes.
    _TK_WINDOW_CLASSES = ("TkTopLevel", "TkChild")
    _CS_WHOLE_REPAINT = 0x0001 | 0x0002         # CS_VREDRAW | CS_HREDRAW

    def _stop_whole_repaints(self):
        """Stop Windows repainting every window whole on each size change.

        Tk registers its window classes with CS_HREDRAW and CS_VREDRAW, so
        every change of size -- each step of a drag of the window's edge --
        invalidated the main window whole, and everything on screen was
        painted again: measured, 72 ms a step on the Calendar with its
        content not even being laid out. Tk does not need it. Its widgets
        redraw themselves when their own size changes (every one handles
        ConfigureNotify), so the class styles only paid for the same paint
        twice. Taken off both classes, a held step measured 10 ms, a step
        laid out live 120 instead of 264, the editor 65 instead of 145 --
        and the window photographed before and after, mid-drag and at a new
        size, was the same to the pixel.

        On <Map>, because before the window is mapped wm_frame() names a
        different window (see _paint_title_bar). Only Tk's own two classes
        are touched, asked by name. Windows only; anywhere else, or if the
        question fails, nothing changes and the window paints as it did.
        """
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            get_style = user32.GetClassLongPtrW
            set_style = user32.SetClassLongPtrW
            get_style.restype = set_style.restype = ctypes.c_size_t
            get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
            set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t]
            gcl_style = -26
            name = ctypes.create_unicode_buffer(64)
            windows = [int(self.wm_frame(), 16), self.winfo_id()]
            if getattr(self, "main_canvas", None) is not None:
                windows.append(self.main_canvas.winfo_id())   # measured: TkChild
            for hwnd in windows:
                user32.GetClassNameW(ctypes.c_void_p(hwnd), name, 64)
                if name.value not in self._TK_WINDOW_CLASSES:
                    continue
                style = get_style(hwnd, gcl_style)
                if style & self._CS_WHOLE_REPAINT:
                    set_style(hwnd, gcl_style, style & ~self._CS_WHOLE_REPAINT)
        except Exception:                             # noqa: BLE001
            self._log_swallowed("window class repaint styles")

    def _paint_title_bar(self):
        """Ask Windows to draw the title bar in the current theme.

        The alternative was a hand-drawn borderless caption, and it costs
        far more than it looks: snapping to screen edges, dragging,
        double-click to maximise, the system menu, Alt+Space, Aero shake,
        the taskbar's own behaviours and every accessibility affordance
        are all things Windows does for a real caption and nothing does
        for a `Frame` with a label in it. This keeps the native title bar
        and only changes its colours, which is the whole of what was
        wrong with it.

        Windows 11 (build 22000+) only, and silently nothing anywhere
        else -- including the Linux CI, where there is no compositor to
        ask. A title bar is decoration: no failure here is a reason for
        the app not to open.
        """
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            def colorref(hex_colour):
                # Windows wants 0x00BBGGRR -- a CSS hex, byte-reversed.
                r = int(hex_colour[1:3], 16)
                g = int(hex_colour[3:5], 16)
                b = int(hex_colour[5:7], 16)
                return (b << 16) | (g << 8) | r

            # winfo_id() is Tk's child window; the caption belongs to the
            # frame above it, which is what wm_frame names.
            handle = int(self.wm_frame(), 16)
            dwm = ctypes.windll.dwmapi
            dark = self.theme_name.startswith("dark")
            for attribute, value in (
                    (self._DWMWA_USE_IMMERSIVE_DARK_MODE, int(dark)),
                    (self._DWMWA_CAPTION_COLOR, colorref(self.colors["bg"])),
                    (self._DWMWA_TEXT_COLOR, colorref(self.colors["text"])),
                    (self._DWMWA_BORDER_COLOR,
                     colorref(self.colors["accent"]))):
                payload = ctypes.c_int(value)
                # c_void_p, not wintypes.HWND: `import ctypes` does not
                # bring ctypes.wintypes with it, and a handle is a
                # pointer either way.
                dwm.DwmSetWindowAttribute(
                    ctypes.c_void_p(handle), ctypes.c_uint(attribute),
                    ctypes.byref(payload), ctypes.sizeof(payload))
        except Exception:                             # noqa: BLE001
            self._log_swallowed("title bar colours")

    def _icon_files(self):
        """The icon files for the current theme, best first.

        Named after the accent colour rather than after the theme --
        `icon_7c5cff.ico` -- which is why there is no table here mapping
        one to the other. A table would be a second place to keep in
        step, and a theme added later would quietly get the wrong icon.
        The colour is already in hand, so the filename is computed from
        it, and the plain `icon.ico` is the fallback when a colour has no
        drawing of its own yet.
        """
        # getattr, not self.colors: this is called from the constructor
        # and from the theme switch, and the constructor once called it
        # before the colours existed. Degrading to the default icon is a
        # better answer than degrading to none.
        colors = getattr(self, "colors", None) or {}
        accent = (colors.get("accent") or "").lstrip("#").lower()
        stems = ([("icon_%s.ico" % accent, "icon_%s.png" % accent)]
                 if accent else [])
        stems.append(("icon.ico", "icon_256.png"))
        return stems

    def _set_window_icon(self):
        """Put the app's icon on the window, in the theme's colour.

        Wrapped end to end because an icon is decoration: a missing file,
        an X server that will not take an .ico, an odd Tk build -- none
        of those is a reason for the app not to open. The failure goes to
        the crash log, not to the user.

        Two formats on purpose. Windows takes the .ico and picks the size
        it needs from inside it -- 16px for the title bar, larger ones for
        the task switcher. X11 has no notion of .ico at all and wants a
        PhotoImage, so the PNG is a real second path rather than an
        afterthought.

        Set twice on Windows, which is not belt and braces: `default=`
        governs windows made LATER, and the plain form repaints the one
        already on screen. Only doing the first leaves the open window
        wearing the previous theme's colour until it is reopened.
        """
        try:
            for ico_name, png_name in self._icon_files():
                ico = bundled_file("assets", ico_name)
                if os.path.exists(ico):
                    try:
                        self.iconbitmap(ico)
                        self.iconbitmap(default=ico)
                        return
                    except tk.TclError:
                        pass      # not Windows, or a Tk built without it
                png = bundled_file("assets", png_name)
                if os.path.exists(png):
                    # Held on self: Tk keeps no reference of its own, and
                    # a collected PhotoImage silently blanks the icon.
                    self._window_icon = tk.PhotoImage(file=png)
                    self.iconphoto(True, self._window_icon)
                    return
        except Exception:                             # noqa: BLE001
            self._log_swallowed("window icon")

    # A title longer than this cannot be typed or pasted in. The limit is
    # not about storage or layout -- the note list already truncates to 60
    # characters for display -- but about tk.Entry, which slows roughly with
    # the square of what it holds: measured, one keystroke costs 0.5ms at 30
    # characters, 38ms at 10,000, and 3.5 seconds at 100,000. Someone who
    # pastes a document into the title by accident would find the field
    # frozen and no way to edit it back. 200 is far past any real title and
    # far short of where the widget struggles.
    TITLE_MAX_LEN = 200

    def _title_within_limit(self, proposed):
        """Validator for the title field: reject an edit past the cap."""
        if getattr(self, "_setting_title", False):
            return True                      # a stored title being loaded
        if len(proposed) <= self.TITLE_MAX_LEN:
            return True
        # Deferred: Tk turns validation off if the validate command touches
        # a widget while it runs, and the status bar is a widget.
        self.after_idle(
            lambda: self.set_status(
                f"A note title can be up to {self.TITLE_MAX_LEN} characters"))
        return False

    # How close to the cap the counter starts showing. Far enough out to be
    # a warning rather than a surprise, close enough that an ordinary title
    # never sees it.
    TITLE_COUNT_FROM = 40

    # The sidebar search box's hint, and the single place it is written down.
    # It used to be spelled out three times -- once where the box is built
    # and twice, lowercased, in the two functions that read the query
    # (`if query == "search notes...": query = ""`). Nothing connected them,
    # so changing the wording would have left the app quietly filtering every
    # list by its own hint text. Adding a fourth reader (the ✕ that appears
    # only for a real query) is what made that worth closing.
    SEARCH_PLACEHOLDER = "Search notes..."

    def _search_query(self):
        """What the user is actually searching for, lowercased.

        Empty when the box is only showing its hint, which is not a query
        even though it is the box's contents: the entry is wired to
        `search_var`, so `add_placeholder` writing the hint in makes it
        readable as one.
        """
        query = self.search_var.get().lower()
        return "" if query == self.SEARCH_PLACEHOLDER.lower() else query

    def _refresh_search_clear(self):
        """Show the ✕ only while the box holds a real query.

        A clear button that is always there invites clearing an empty box,
        and one sitting beside the hint text suggests the hint is something
        you could remove.
        """
        btn = getattr(self, "search_clear_btn", None)
        if btn is None:
            return                      # called while the row is being built
        if self._search_query():
            if not self._is_placed(btn):
                btn.pack(side="right", padx=(0, 6))
        elif self._is_placed(btn):
            btn.pack_forget()

    def _clear_search(self):
        """Empty the search box and put the full list back, at once.

        The hint is NOT written back here. The box takes the focus instead,
        which is the state add_placeholder already gives a box someone has
        clicked into, and its own <FocusOut> puts the hint back when they
        look elsewhere — one mechanism for the hint rather than two.
        """
        self.search_var.set("")
        try:
            self.search_entry.focus_set()
        except tk.TclError:
            pass
        # The var write above queued a rebuild 180ms out. Clearing a search
        # should feel like the list snapping back, so the wait is dropped and
        # the rebuild happens now -- the debounce is there to make TYPING
        # cheap, and this is one event, not a stream of them.
        if self._search_debounce_job is not None:
            try:
                self.after_cancel(self._search_debounce_job)
            except (tk.TclError, ValueError):
                pass
            self._search_debounce_job = None
        self.refresh_note_list()

    # One sentence for one fact. A share code carries a note's text and not
    # its files, and the two places that say so said it differently -- the
    # sidebar "Attachments not included", the editor "Attachments aren't
    # included in a code". The editor's wording is the one kept, because it
    # names WHICH mechanism leaves them out, which is the part a reader needs
    # to know that Export does include them.
    SHARE_ATTACHMENT_WARNING = (
        "⚠ Attachments aren't included in a code — use Export for files.")

    def _refresh_title_count(self, event=None):
        """Show how much title is left, once there is little enough of it.

        Also called after a note is loaded, so opening one that is already
        near the cap says so straight away rather than waiting for a
        keystroke to reveal it.
        """
        if not hasattr(self, "title_count_lbl"):
            return
        used = len(self.title_entry.get())
        if self._title_is_placeholder():
            used = 0
        if used < self.TITLE_MAX_LEN - self.TITLE_COUNT_FROM:
            if self._is_placed(self.title_count_lbl):
                self.title_count_lbl.pack_forget()
            return
        self.title_count_lbl.config(
            text=f"{used}/{self.TITLE_MAX_LEN}",
            fg=self.colors["danger"] if used >= self.TITLE_MAX_LEN
            else self.colors["subtext"],
        )
        if not self._is_placed(self.title_count_lbl):
            # Before the category button, which is packed to the right first,
            # so the counter sits between the title and it rather than past
            # the edge of the row.
            self.title_count_lbl.pack(side="left", padx=(8, 0))

    def _title_is_placeholder(self):
        """True while the field is showing its grey 'Note title...' prompt."""
        return self.title_entry.get() == "Note title..."

    def _insert_title(self, text):
        """Put a stored title into the field, cap or no cap.

        Validation fires on programmatic inserts as well as on typing. A
        note whose title predates the cap -- or one hand-edited in the JSON
        -- would otherwise have the widget silently drop the overflow, and
        the next autosave would write that shortened title back over the
        real one. Loading a note must never edit it.
        """
        self._setting_title = True
        try:
            self.title_entry.insert(0, text)
        finally:
            self._setting_title = False
        self._refresh_title_count()

    def _on_title_paste(self, event=None):
        """Paste into the title, trimmed to fit rather than refused.

        A validator can only accept or reject a change whole, so pasting
        something long past the cap would otherwise leave the field empty --
        which looks like the paste failed rather than like it was shortened.
        """
        try:
            pasted = self.clipboard_get()
        except tk.TclError:
            return "break"
        try:
            self.title_entry.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        room = self.TITLE_MAX_LEN - len(self.title_entry.get())
        if room <= 0:
            self.set_status(
                f"A note title can be up to {self.TITLE_MAX_LEN} characters")
            return "break"
        clipped = " ".join(pasted.split())[:room]
        self.title_entry.insert("insert", clipped)
        self._refresh_title_count()
        if len(pasted) > len(clipped):
            self.set_status(
                f"Pasted title shortened to {self.TITLE_MAX_LEN} characters")
        return "break"

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
                self._log_swallowed("autosave: schedule-time word count")
        self._cancel_pending_autosave()
        self._autosave_job = self.after(500, self._autosave_now)

    def _cancel_pending_autosave(self):
        """Drop a scheduled autosave, if one is waiting."""
        if getattr(self, "_autosave_job", None) is not None:
            try:
                self.after_cancel(self._autosave_job)
            except (tk.TclError, ValueError):
                pass
            self._autosave_job = None

    def _log_swallowed(self, where):
        """A guarded spot chose to carry on — leave the trace the bare
        `pass` never did (audit Z02-F04: a persistent bug in the autosave
        spine could stop saving in complete silence). Same file as every
        other crash record; deliberately no toast — a background path can
        hit its guard on every keystroke. Logged ONCE per spot per
        session for the same reason: a persistent bug would otherwise
        append a traceback per keystroke, growing the log without bound
        and putting file I/O on the typing path."""
        seen = getattr(self, "_swallowed_seen", None)
        if seen is None:
            seen = self._swallowed_seen = set()
        if where in seen:
            return
        seen.add(where)
        try:
            import traceback
            # errors="replace": a traceback quoting editor text can carry
            # lone surrogates (a known-real class here), and the trace
            # writer must never raise over its own payload.
            with open(os.path.join(APP_DIR, "crash_log.txt"), "a",
                      encoding="utf-8", errors="replace") as f:
                f.write(f"\n--- {datetime.now().isoformat()} "
                        f"(swallowed: {where}) ---\n"
                        f"{traceback.format_exc()}\n")
        except (IOError, OSError, NameError):
            pass

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
            self._log_swallowed("autosave: catch-up word count")
        # An occurrence view can't be saved without asking "this occurrence
        # or the whole series?", and a silent background timer must never
        # open a dialog — every pause in typing used to raise the question,
        # and one such prompt stacked on a manual save's own produced a
        # frozen "ghost" save (see ISSUES_LOG). Leave the edits in the
        # editor; the next explicit gesture — Save, a note switch, closing —
        # asks exactly once and saves then.
        if self.selected_note_id is not None and self.current_occurrence_date:
            note = self.find_note(self.selected_note_id)
            if note is not None and is_recurring(note):
                return
        try:
            st = self.capture_editor_state()
        except Exception:
            self._log_swallowed("autosave: capture_editor_state")
            return
        # Never auto-save a completely empty NEVER-SAVED note — that would
        # spawn junk notes every time the user clicks "New Note". A note
        # that already exists on disk is the opposite case: an empty editor
        # there is a deliberate emptying, and this very gate silently
        # throwing it away was T0-5's actual mechanism — the fix in
        # save_current_note was unreachable because this early-return ran
        # first on the autosave route.
        if not self._editor_state_has_content(st) and not self._editing_saved_note():
            return
        # Only save if something actually changed vs. the saved version.
        try:
            if self.editor_state_matches_saved(st):
                return
        except Exception:
            self._log_swallowed("autosave: editor_state_matches_saved")
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

    def _is_placed(self, widget):
        """Whether a widget has its place in the layout -- packed, gridded
        or placed -- which is what every "show it" / "hide it" decision
        means to ask.

        Not winfo_ismapped(). That asks whether the widget is on the SCREEN,
        and Tk answers no for a widget that has its place in two ordinary
        moments: until Tk first draws it after it was packed, and for as
        long as the page holding it is hidden -- Tk unmaps every child of a
        hidden container and maps them again when it comes back. So "hide
        it if it shows" skipped a widget that was only asleep, and it woke
        up with its page: Restore previous stayed on a note with nothing to
        restore, opened from the Calendar. And "show it if it does not" packed
        again a widget that already had a place, which moves it to the end
        of its container. tools/check_one_definition.py keeps
        winfo_ismapped() out of these decisions."""
        try:
            return bool(widget.winfo_manager())
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
                    self._sync_editor_snapshot()
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
        """The saved theme, or the default if it names one that no longer exists."""
        theme = get_setting("theme")
        return theme if theme in THEMES else "dark"

    def save_theme_setting(self):
        save_setting("theme", self.theme_name)

    def load_username(self):
        return get_setting("username", "", expect=str)

    def save_username(self, name):
        save_setting("username", name.strip())

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

    def _sync_list_scroll(self, _event=None):
        """Keep the note list honest about where its top is: content
        that fits the viewport sits AT the top, and the origin never
        rests above the first card (which showed as unexplained space
        between the top bar and the first title). The editor page has
        carried this exact guard for its own canvas since 0.32.x; the
        list showed the same family of symptoms without it."""
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        try:
            # While a rebuild's restore is still in force, every Configure
            # re-applies it. A rebuilt list's geometry settles over SEVERAL
            # event-loop passes (measured: one collapse reported heights
            # 106 -> 276 -> 820 as separate Configure events), and each
            # intermediate scrollregion re-clamps the canvas -- a single
            # idle-time restore loses that race to whichever stage lands
            # after it.
            pending = getattr(self, "_list_restore_px", None)
            if pending is not None:
                if time.monotonic() <= getattr(self, "_list_restore_until", 0):
                    self._apply_list_scroll_px(pending)
                    return
                self._list_restore_px = None
            # Keep the scrollregion honest before judging the origin:
            # yview_moveto() below works in region fractions, and setting
            # the region to the truth makes Tk clamp an origin sitting past
            # a new, shorter end (a blank viewport otherwise) by itself.
            # The extent comes from the rows, not from Tk (_list_extent).
            region = self._list_extent()
            canvas.configure(scrollregion=region)
            content_h = region[3] - region[1]
            if (content_h <= canvas.winfo_height()
                    or canvas.canvasy(0) < 0):
                canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def _apply_list_scroll_px(self, pixels):
        """Scroll the list to `pixels` from the top, clamped into the
        content as it is RIGHT NOW; content that fits pins to the top.
        Sets the scrollregion from the list's own extent first: the
        content may just have shrunk under a canvas scrolled past its new
        end, and a stale region would leave the view parked in blank
        space. (When the cards lived in a frame, that frame could end up
        above the viewport, stop being resized and never report it.)"""
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return
        try:
            region = self._list_extent()
            canvas.configure(scrollregion=region)
            content_h = max(1, region[3] - region[1])
            view_h = canvas.winfo_height()
            if content_h <= view_h:
                canvas.yview_moveto(0)
                return
            pixels = max(0, min(pixels, content_h - view_h))
            canvas.yview_moveto(pixels / content_h)
        except tk.TclError:
            pass

    def _restore_list_scroll(self, pixels):
        """Put the note list back where it was before a full rebuild --
        in PIXELS from the top, because a rebuild can change the content
        height (collapsing a group, say) and a remembered fraction would
        land somewhere else. The restore stays in force for a short
        window rather than firing once, re-applied from two directions:
        _sync_list_scroll on every Configure (a rebuilt list's geometry
        settles over several event-loop passes, each re-clamping the
        canvas), and the timers below (a rebuild that only SHRINKS
        content scrolled out of view fires no Configure at all, and at
        this idle moment bbox may still report the old geometry)."""
        self._list_restore_px = pixels
        self._list_restore_until = time.monotonic() + 0.4
        self._apply_list_scroll_px(pixels)
        for delay in (60, 160, 360):
            self.after(delay, self._reapply_list_restore)

    def _reapply_list_restore(self):
        """One timed beat of a still-in-force rebuild restore."""
        pending = getattr(self, "_list_restore_px", None)
        if pending is None or not self._still_alive():
            return
        if time.monotonic() > getattr(self, "_list_restore_until", 0):
            self._list_restore_px = None
            return
        self._apply_list_scroll_px(pending)

    def _list_scrollbar_moved(self, *args):
        """The list scrollbar's command: a deliberate drag beats a
        rebuild's still-pending restore, then scrolls as normal."""
        self._list_restore_px = None
        try:
            self.canvas.yview(*args)
        except tk.TclError:
            pass

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
        save_setting("last_open_note_id", note_id)

    # ---------- One-time startup notice ----------
    def announce_startup_changes(self):
        """Shown once: where the notes now live, and what cleanup removed."""
        if not self._still_alive():
            return
        lines = []

        if self._corrupt_notes_report is not None:
            msg = (
                "⚠ Your notes file could not be read this time, so the app "
                "started with an empty list. Your notes did NOT delete "
                "themselves — the file on disk was unreadable (a bad "
                "shutdown or disk problem can do this)."
            )
            if self._corrupt_notes_report:
                msg += (
                    "\n\nThe unreadable file was preserved, untouched, at:\n"
                    f"{self._corrupt_notes_report}\n\n"
                    "It may be repairable — keep it safe and restore from "
                    "your most recent backup (Settings → Backup), or ask "
                    "for help with the preserved file."
                )
            else:
                msg += (
                    "\n\nPreserving a copy of it also failed, so do not "
                    "save over it: close the app and back up "
                    "notes_data.json from the data folder first."
                )
            lines.append(msg)

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
            # Said by the migration itself, per case, and only what is
            # true. A fixed tail used to follow it here -- "the script and
            # dist\NoteOrganizer.exe both read this same folder, so they
            # can never drift apart" -- which was false in source mode
            # after a reclaim, and developer jargon in the built app.
            lines.append(MIGRATION_INFO)

        if self._categories_adopted:
            # The notes were right and settings.json had lost track: say
            # which categories came back, because their colours are now
            # the default palette's, and a change nobody explains looks
            # like the app forgetting things.
            count = len(self._categories_adopted)
            shown = self._categories_adopted[:8]
            listed = "\n".join(f"  • {name}" for name in shown)
            if count > len(shown):
                listed += f"\n  • …and {count - len(shown)} more"
            lines.append(
                f"{count} categor{'y' if count == 1 else 'ies'} your notes "
                "are filed under had gone missing from the settings, so "
                f"{'it was' if count == 1 else 'they were'} added back, "
                "with default colours:\n"
                f"{listed}\n\n"
                "Your notes stayed where you filed them. Settings → "
                "Categories changes the colours.")

        if PURGED_DIRS:
            listed = "\n".join(f"  • {d}" for d in PURGED_DIRS)
            lines.append(
                "Removed leftover copies of your notes from:\n"
                f"{listed}\n\n"
                "Each one was checked first — nothing was deleted unless every "
                "note and attachment in it already existed in the app folder. "
                "There is now exactly one notebook on disk."
            )

        # Only speak if the pass actually DID something. On a fresh
        # install it runs against an empty notebook and used to announce
        # itself anyway — the literal first screen of the product was a
        # blocking modal reading "0 note(s) remain, IDs renumbered 1–0".
        if self._cleanup_report and (
                self._cleanup_report[0].get("empty_removed")
                or self._cleanup_report[0].get("duplicates_removed")):
            stats, backup_path = self._cleanup_report
            # Plain words, in the user's vocabulary: this dialog removes
            # notes PERMANENTLY, and its first draft described that as a
            # "Cleanup pass" with "IDs renumbered" under a "setup
            # complete" title — internal maintenance language wrapped
            # around a deletion (the product review's T2-1, second half).
            removed_bits = []
            if stats["empty_removed"]:
                removed_bits.append(f"{stats['empty_removed']} empty note(s)")
            if stats["duplicates_removed"]:
                removed_bits.append(
                    f"{stats['duplicates_removed']} exact duplicate(s)")
            summary = (
                f"While tidying up, {' and '.join(removed_bits)} "
                f"were removed.\n"
                f"{stats['after']} of your {stats['before']} note(s) remain."
            )
            if backup_path:
                summary += (f"\n\nEverything as it was before is saved in:\n"
                            f"{backup_path}")
            lines.append(summary)

        if lines:
            self.show_info("Note Organizer — your notes", "\n\n———\n\n".join(lines))

    # ---------- Data handling ----------
    def load_notes(self):
        """Read the notes file, and remember anything the user should be told.

        The work happens in core/storage.py; this keeps the two pieces of
        news it produces -- an upgrade backup, and the one-time cleanup
        report -- on the app, where the code that shows them looks for them.

        VERSION_CHANGE is passed in rather than read inside core on purpose:
        it is a global on this module, and this module has two identities
        when the app is launched as a script. See core/storage.load_notes.
        """
        notes, report = core_load_notes(VERSION_CHANGE)
        if report["version_backup_path"]:
            self._version_backup_path = report["version_backup_path"]
        if report["cleanup_report"]:
            self._cleanup_report = report["cleanup_report"]
        self._categories_adopted = report.get("categories_adopted") or []
        if report.get("notes_file_corrupt"):
            self._corrupt_notes_report = report.get("corrupt_backup_path")
            # Sentinel distinct from "nothing happened": the file WAS
            # unreadable even if copying it aside also failed.
            if self._corrupt_notes_report is None:
                self._corrupt_notes_report = ""
        return notes

    def save_notes(self):
        """Write notes to disk, and say so plainly if it fails.

        A failure here used to be invisible - the app looked like it saved
        but nothing hit the disk, which is exactly how notes "vanished" on
        other PCs. core/storage.py does the writing and reports the reason;
        turning that into a dialog is this layer's job.
        """
        ok, exc = core_save_notes(self.notes)
        if ok:
            return True
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
    def _start_io_worker(self, target):
        """Start a background file-I/O worker and remember it, so closing
        the app can wait for it instead of killing a write mid-file (a
        daemon thread dies with the process, whatever it was writing)."""
        t = threading.Thread(target=target, daemon=True)
        self._io_workers = [w for w in getattr(self, "_io_workers", [])
                            if w.is_alive()]
        self._io_workers.append(t)
        t.start()
        return t

    def _wait_for_io_workers(self, cap_s=30.0):
        """Let an in-flight export/import worker finish before the process
        goes away. Hard-capped: a genuinely hung worker must not make the
        app refuse to close — the threads stay daemon for that reason, and
        the export's tmp-then-replace protocol means even the capped-out
        case can no longer destroy an existing backup."""
        workers = [t for t in getattr(self, "_io_workers", [])
                   if t.is_alive()]
        if not workers:
            return
        try:
            self.set_status("Finishing the file operation in progress…")
            self.update_idletasks()
        except tk.TclError:
            pass
        deadline = time.time() + cap_s
        for t in workers:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            t.join(timeout=remaining)

    def export_data(self):
        """Bundle notes_data.json, settings.json, and every attached file
        into one .zip, so moving to another device is copying one file
        instead of hunting down three separate pieces.

        The actual writing runs on a background thread — for a lot of
        attachments this used to visibly freeze the whole app for a few
        seconds. The main thread only ever touches Tkinter widgets from the
        polling callback below; the worker thread does file I/O and updates
        a plain shared dict, which is all it's allowed to touch."""
        # One file operation at a time (audit Z05-F05): a second click on
        # Export mid-run used to start a second worker onto the SAME .tmp,
        # interleaving the two, and overwrote _export_state so the first
        # worker's outcome was never reported.
        if self._export_state is not None or self._import_state is not None:
            self.set_status("An export or import is already running — "
                            "let it finish first.")
            return
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
        # A backup is only a backup if it carries the WHOLE notebook:
        # templates and the trash used to be silently left out, and moving
        # to another device lost them.
        if os.path.exists(TEMPLATES_FILE):
            entries.append((TEMPLATES_FILE, "templates.json"))
        if os.path.exists(TRASH_FILE):
            entries.append((TRASH_FILE, "trash.json"))
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
            # Write beside the target and move into place only when whole —
            # the zip used to be opened ON the target, so a failure (or the
            # app dying) mid-write destroyed the very backup being replaced.
            # Same one-safe-way rule as _write_json_atomic.
            tmp_path = save_path + ".tmp"
            try:
                with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, (src, arcname) in enumerate(entries, start=1):
                        zf.write(src, arcname=arcname)
                        state["current"] = i
                os.replace(tmp_path, save_path)
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
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            state["done"] = True

        self._start_io_worker(worker)
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
                self._remember_finished_export()
                self.show_info(
                    "Export complete",
                    f"Your notes, settings, and attachments were saved to:\n"
                    f"{state['save_path']}\n\n"
                    "Copy or email this single file to another device, then use "
                    "'⬇ Import' there to bring everything in."
                )
            return
        self._export_poll_job = self.after(100, self._poll_export_progress)

    def _remember_finished_export(self):
        """Record the moment a backup export succeeded -- the Backup panel
        shows it, since an export is the only copy of the notes outside
        the app's own folder."""
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_setting("last_export_at", stamp)
        lbl = getattr(self, "last_export_lbl", None)
        if lbl is not None:
            try:
                lbl.config(text=f"Last exported: {stamp}")
            except tk.TclError:
                pass

    def _settle_background_work_at_close(self):
        """Finish what the main thread does once a backup's worker is done
        -- at close, where the timer that would have done it never runs.

        An export that finished is recorded as the last one. An import
        whose worker finished, but whose notes were never merged, is dropped
        whole: the unpacked backup leaves the temp folder, and the files it
        copied into attachments -- which no note points at yet -- leave that
        folder. The close used to wait for the worker and quit, leaving both
        behind (forty orphaned files in one run) and the export unrecorded.
        Merging instead would mean asking the import's questions in a window
        that is closing.
        """
        state = self._export_state
        if state is not None and state.get("done") and not state.get("error"):
            self._remember_finished_export()
            self._export_state = None
        state = self._import_state
        if state is None or not state.get("done"):
            # Still running past the wait's cap: leave it alone.
            return
        self._import_state = None
        if state.get("temp_dir"):
            shutil.rmtree(state["temp_dir"], ignore_errors=True)
        in_use = attachment_names_in(self.notes + self.trash)
        for name in state.get("copied") or []:
            if name in in_use or os.path.basename(name) != name:
                continue
            try:
                os.remove(os.path.join(ATTACHMENTS_DIR, name))
            except OSError:
                pass

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
        # Hover colour resolved at POST time, not build time: these menus
        # hang off both long-lived fields (body, title, search…) and
        # transient ones, so track_theme would leak entries for the
        # transient ones while a build-time capture froze the long-lived
        # ones on the old accent. postcommand runs on every open — live
        # palette, zero tracking.
        menu.configure(postcommand=lambda m=menu: m.configure(
            activebackground=self.colors["accent"], activeforeground="white"))
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
        # Only the note body knows what to do with formatting; everywhere
        # else this widget appears -- the import box, a rename field -- takes
        # plain text anyway, so offering the choice there would be noise.
        if text_widget is getattr(self, "body_text", None):
            menu.add_command(label="Paste without formatting",
                             accelerator="Ctrl+Shift+V",
                             command=self._paste_plain)
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

    # ---------- Bullet and numbered lists ----------
    def _setup_list_tags(self, text_widget):
        """Tags for the paragraph properties: hanging indent and alignment.

        lmargin1 indents the first line, lmargin2 the wrapped continuation --
        which is what keeps a long item lined up under its own text instead
        of back under the marker.

        Alignment gets its own tags rather than being folded into the list
        ones. They set different Tk options (justify vs lmargin), so the two
        compose: a centred bullet keeps its hanging indent.
        """
        self._paragraph_tags = {}
        text_widget.tag_configure("align_center", justify="center")
        text_widget.tag_configure("align_right", justify="right")

    # Pixels per indent step, and the room a marker needs in front of its
    # text so a wrapped line hangs under the text rather than the marker.
    # Shown in both font dropdowns for "no span at all", which is what lets
    # a note follow the Settings default instead of being pinned to whatever
    # that happened to be the day it was written.
    DEFAULT_FONT_LABEL = "Default"

    INDENT_STEP = 24
    # Widths measured at _MARKER_ROOM_AT point. A marker set larger is
    # wider, so these are scaled rather than used raw -- see _marker_room.
    # The reference is a fixed number, not the current base size: that moves
    # with the setting, and comparing it against itself scales by one.
    _MARKER_ROOM = {"bullet": 24, "number": 28}
    _MARKER_ROOM_AT = 12

    def _load_editor_font(self):
        """Read the editor's baseline font from settings.

        Falls back to the app's own defaults rather than to whatever the
        widget happens to be set to, so a settings file with a font that is
        no longer offered degrades to something known instead of sticking.
        """
        family = get_setting("editor_font_family", FONT_FAMILIES[0], str)
        if family not in FONT_FAMILIES:
            family = FONT_FAMILIES[0]
        size = get_setting("editor_font_size", 12, int)
        if size not in FONT_SIZES:
            size = 12
        self.editor_font_family, self.editor_font_size = family, size

    def _set_editor_font(self, family=None, size=None):
        """Change the baseline font every note is written in.

        Rebuilds the tags derived from it as well as the widget's own font:
        bold and italic are separate Font objects built from the base
        family and size, and the list margins are in pixels scaled by that
        size, so neither follows automatically.
        """
        if family is not None:
            self.editor_font_family = family
            save_setting("editor_font_family", family)
        if size is not None:
            self.editor_font_size = size
            save_setting("editor_font_size", size)

        spec = (self.editor_font_family, self.editor_font_size)
        for widget in (self.body_text, getattr(self, "comments_text", None)):
            if widget is not None:
                widget.configure(font=spec)
        self._setup_body_formatting_tags(self.body_text)
        # Rebuilt at the new base size: a tag's margin was computed from the
        # old one, and nothing else recomputes it.
        for name in list(self._paragraph_tags):
            self._configure_paragraph_tag(self.body_text, name)
        # The table face follows the base size too, or a table would stay at
        # whatever size it was built at while the text around it moved.
        self._configure_table_tag(self.body_text)
        # Grids carry their own fonts and cell widths, so they are rebuilt
        # at the new size rather than left at the old one.
        self._render_table_grids()
        self._refresh_format_buttons()

    def _marker_room(self, kind):
        """How much room a list marker needs before its text.

        Scaled by the editor's font size, because the margin is in pixels
        and the marker is not: "• " measures 11px at 12pt and 22px at 24pt,
        so a fixed 42px lmargin2 that hangs correctly at the default size
        leaves a large-font item's second line 11px out of true.
        """
        room = self._MARKER_ROOM[kind]
        current = self._editor_font_size()
        if current and current != self._MARKER_ROOM_AT:
            room = int(round(room * current / self._MARKER_ROOM_AT))
        return room

    def _editor_font_size(self):
        """The size the body text is actually set in right now."""
        try:
            return tkfont.Font(font=self.body_text["font"]).actual("size")
        except (tk.TclError, AttributeError):
            return getattr(self, "_body_base_size", 0)

    def _paragraph_tag(self, text_widget, kind, indent):
        """The margin tag for this combination of properties, made on demand.

        There is one tag per combination rather than one per property,
        because they all set the same two Tk options -- lmargin1 and
        lmargin2 -- and a widget applies only the winning tag's value for an
        option. Building them lazily is the same pattern the colour tags
        use: the app cannot know which combinations a note will want.
        """
        name = f"para_{kind or 'plain'}_{indent}"
        if name not in self._paragraph_tags:
            self._paragraph_tags[name] = (kind, indent)
            self._configure_paragraph_tag(text_widget, name)
        return name

    TABLE_TAG = "table_row"

    def _table_block_at(self, line_no):
        """The first and last line of the table *line_no* belongs to, 1-based.

        None if that line is not a table row. Read from the widget rather
        than from anything remembered, because the text is what decides.
        """
        if not is_table_row(self.body_text.get(f"{line_no}.0", f"{line_no}.end")):
            return None
        first = last = line_no
        end = int(self.body_text.index("end-1c").split(".")[0])
        while first > 1 and is_table_row(
                self.body_text.get(f"{first - 1}.0", f"{first - 1}.end")):
            first -= 1
        while last < end and is_table_row(
                self.body_text.get(f"{last + 1}.0", f"{last + 1}.end")):
            last += 1
        return first, last

    @_undo_atom
    def _align_table_block(self, line_no):
        """Line the columns of one table up again.

        Only the spaces are touched, never the whole line: Tk carries a tag
        along with the text around it, so a space inserted beside a cell
        leaves the bold inside it where it was, while rewriting the line
        would take its tags with it.

        The caret is not put back by index. Tk already moves the insert mark
        along with the text around it, which keeps it beside the character it
        was beside; setting it back to the index it had before would drag it
        to a column that now holds something else -- measured, with the caret
        just after "Z" in a widened row, it landed nineteen characters early.

        What it does need is gravity. Padding is added at the end of a cell's
        text, which is exactly where a caret sits after typing there, and a
        mark's default gravity puts it to the *right* of text inserted at it
        -- so the caret drifted past the new spaces to the far side of the
        cell. Left gravity keeps it against the word it was against.
        """
        block = self._table_block_at(line_no)
        if not block:
            return False
        first, last = block
        lines = [self.body_text.get(f"{n}.0", f"{n}.end")
                 for n in range(first, last + 1)]
        aligns = [core_tables.cell_alignments(line) for line in lines]
        widths = core_tables.layout_widths(
            [core_tables.split_row(line) for line in lines], aligns)
        changed = False
        try:
            was_gravity = self.body_text.mark_gravity("insert")
            self.body_text.mark_gravity("insert", "left")
        except tk.TclError:
            was_gravity = None
        for offset, line in enumerate(lines):
            row = first + offset
            # A rendered grid's window occupies column 0 of its first line,
            # so edits on that line land one Tk column further right than
            # the offsets computed from get(), which skips windows.
            base = self._col_base(row)
            for at, delta in core_tables.pad_ops(
                    line, widths,
                    aligns[offset] if offset < len(aligns) else None):
                changed = True
                # Ops come right-to-left, so the prefix each one converts
                # against is still the snapshot the offsets were computed
                # from. The deltas themselves are spaces -- one unit each.
                t_at = base + self._tk_col(line, at)
                if delta > 0:
                    self.body_text.insert(f"{row}.{t_at}", " " * delta)
                else:
                    self.body_text.delete(f"{row}.{t_at}",
                                          f"{row}.{t_at + (-delta)}")
        if was_gravity:
            try:
                self.body_text.mark_gravity("insert", was_gravity)
            except tk.TclError:
                pass
        if changed:
            self._resync_list_tags()
        return changed

    def _align_table_on_leaving(self, event=None):
        """Re-pad a table once the caret is no longer inside it.

        Not on every keystroke: the columns would jump about under the
        hands of whoever is typing, and every keystroke would rewrite
        characters. Waiting until the row is left means one rewrite, at a
        moment nobody is mid-word.
        """
        try:
            now = int(self.body_text.index("insert").split(".")[0])
        except tk.TclError:
            return
        was = getattr(self, "_last_caret_line", None)
        self._last_caret_line = now
        if was is None or was == now:
            return
        # The line just left, not the one just arrived at: a table is tidied
        # when it is finished with, and a caret moving between two rows of
        # the same table is not finished with it.
        leaving = self._table_block_at(was)
        if leaving and leaving != self._table_block_at(now):
            self._align_table_block(was)
            # A table that has just been left is finished with, which is the
            # moment it turns from typed pipes into a drawn grid.
            self._render_table_grids()

    # ---------- Tables drawn as real grids ----------
    #
    # The pipe text stays the stored form and the single source of truth;
    # the grid is only how a table is shown and edited. Search, share codes,
    # export, word counts and save never know the grid exists, because the
    # text they read is the text the grid writes back into. The spike that
    # cleared this approach also measured the one hazard: _char_offset counts
    # with "chars", which skips embedded windows, so formatting offsets are
    # safe -- but Tk *index* columns on the window's own line shift by one,
    # which is what _col_base is for.

    TABLE_HIDE_TAG = "table_hidden"

    def _grid_first_line(self, info):
        """The 1-based line a grid currently starts on, or None if gone.

        Read from a mark rather than remembered as a number: text edited
        above the table moves it, and a mark moves with it.

        Liveness first: a full-range delete (New note, typing over a
        Ctrl+A selection) destroys the embedded windows WITHOUT a
        teardown, and Tk marks survive that delete — collapsed to 1.0.
        Answering for such a dead grid made _caret_out_of_hidden walk the
        caret of a fresh note to its end on the next keystroke, and
        shifted line-1 column math by a phantom window character.
        """
        try:
            if not info["frame"].winfo_exists():
                return None
            return int(self.body_text.index(info["mark"]).split(".")[0])
        except (tk.TclError, KeyError, ValueError):
            return None

    def _grid_at_line(self, line_no):
        for info in getattr(self, "_table_grids", []):
            if self._grid_first_line(info) == line_no:
                return info
        return None

    def _col_base(self, line_no):
        """1 when a grid window occupies column 0 of this line, else 0."""
        return 1 if self._grid_at_line(line_no) is not None else 0

    @_undo_hidden
    def _teardown_table_grids(self):
        for info in getattr(self, "_table_grids", []):
            # Deleting the window's character is what actually removes it
            # from the text. Destroying the widget alone leaves the slot
            # behind as a phantom index that still shifts every column on
            # its line -- one more per re-render, which is how "a/b" once
            # became " |a/be" as the edits landed a column further left
            # each time.
            try:
                self.body_text.delete(self.body_text.index(info["frame"]))
            except tk.TclError:
                try:
                    info["frame"].destroy()
                except tk.TclError:
                    pass
            try:
                self.body_text.mark_unset(info["mark"])
            except tk.TclError:
                pass
        self._table_grids = []
        self._grid_sel = None
        self._grid_pressed = None
        self._grid_resizing = None
        try:
            self.body_text.tag_remove(self.TABLE_HIDE_TAG, "1.0", "end")
        except tk.TclError:
            pass

    @_undo_hidden
    def _render_table_grids(self):
        """Draw every table in the note as a grid of real cells.

        Torn down and rebuilt whole: a grid is cheap to make, and tracking
        which of them an arbitrary edit invalidated is not. Never called
        while focus is in a cell -- rebuilding would destroy the widget
        being typed into -- which the call sites guarantee: they all run
        with focus in the text or on a toolbar control.
        """
        if not hasattr(self, "body_text"):
            return
        # Tearing the grids down shrinks the editor page for a moment, and
        # the page's own keep-short-content-at-top handler read that as a
        # short note and snapped the scroll to the top -- on every insert,
        # and on every commit that re-rendered. The handlers run from the
        # event queue, so the view is restored after them, not merely after
        # this function.
        # A menu operation tears the grids down BEFORE this runs, and
        # deleting the window characters shifts body_text's scroll on the
        # spot -- capturing here was too late, and the restore faithfully
        # pinned the already-jumped view. The op context captures first and
        # leaves its snapshot for this render to honour.
        saved = getattr(self, "_grid_saved_view", None)
        self._grid_saved_view = None
        explicit_capture = saved is not None
        if saved is not None:
            restore_view, restore_body, restore_x = saved
        else:
            restore_view, restore_body, restore_x = self._capture_grid_views()
        self._teardown_table_grids()
        # Anything a plain destroy left behind -- a dead window dumps with an
        # empty name -- is swept out bottom-up, so the deletions do not move
        # the indices still to be visited.
        for _kind, name, index in reversed(
                self.body_text.dump("1.0", "end", window=True)):
            if not name:
                try:
                    self.body_text.delete(index)
                except tk.TclError:
                    pass
        self.body_text.tag_configure(self.TABLE_HIDE_TAG, elide=True)
        text = self.body_text.get("1.0", "end-1c")
        blocks = core_tables.find_blocks(text)
        for first0, last0 in blocks:
            self._build_table_grid(first0 + 1, last0 + 1)
        # There is always a line under the last table, or the caret guard
        # would have nowhere to put the caret and writing could never
        # continue past it.
        if blocks:
            total = int(self.body_text.index("end-1c").split(".")[0])
            if blocks[-1][1] + 1 >= total:
                self.body_text.insert("end", "\n")
        for info in getattr(self, "_table_grids", []):
            line = self._grid_first_line(info)
            if line in restore_x:
                try:
                    info["canvas"].xview_moveto(restore_x[line])
                except tk.TclError:
                    pass
        # Both restores wait for the queue: the fresh windows are not yet
        # mapped here, the Text estimates their heights wrong, and a
        # fraction restored against those estimates lands somewhere else
        # once geometry settles -- measured drifting 0.316 to 0.164.
        if restore_body is not None or restore_view is not None:
            self.after_idle(lambda page=restore_view, body=restore_body,
                            expl=explicit_capture:
                            self._restore_views_idle(page, body, expl))

    def _grid_fonts(self):
        key = (self.editor_font_family, self.editor_font_size)
        cache = getattr(self, "_grid_font_cache", None)
        if cache is None:
            cache = self._grid_font_cache = {}
        if key not in cache:
            cache[key] = (
                tkfont.Font(family=key[0], size=key[1], weight="bold"),
                tkfont.Font(family=key[0], size=key[1]),
            )
        return cache[key]

    def _measuring_font(self, font):
        """A font that can measure -- the emoji cells pass a plain tuple,
        which draws fine but cannot answer measure()."""
        if hasattr(font, "measure"):
            return font
        cache = getattr(self, "_measure_font_cache", None)
        if cache is None:
            cache = self._measure_font_cache = {}
        if font not in cache:
            cache[font] = tkfont.Font(family=font[0], size=font[1])
        return cache[font]

    def _measure_text(self, font, text):
        """``_measuring_font(font).measure(text)``, remembered per font and
        text. Opening a 60-row table asked Tk for 1,563 widths -- a third
        of the open -- over a few hundred distinct strings. The grid's
        fonts are never reconfigured in place (a new size or family makes
        new Font objects, see _grid_fonts), so a remembered width cannot
        go stale; the store is dropped whole if it ever grows large."""
        font = self._measuring_font(font)
        cache = getattr(self, "_measure_text_cache", None)
        if cache is None or len(cache) > 50000:
            cache = self._measure_text_cache = {}
        key = (str(font), text)
        width = cache.get(key)
        if width is None:
            width = cache[key] = font.measure(text)
        return width

    def _ellipsize(self, value, font, max_px):
        """The drawing clips, the text never does: a value wider than its
        column is drawn shortened with an ellipsis, while the note's own
        text keeps every character."""
        if max_px <= 0 or self._measure_text(font, value) <= max_px:
            return value
        ellipsis = "\u2026"
        lo, hi = 0, len(value)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self._measure_text(font, value[:mid] + ellipsis) <= max_px:
                lo = mid
            else:
                hi = mid - 1
        return value[:lo] + ellipsis

    @staticmethod
    def _char_is_emoji(ch):
        return ord(ch) >= 0x1F000 or 0x2600 <= ord(ch) <= 0x27BF or ord(ch) > 0xFFFF

    def _cell_value_styles(self, line_no, line, c):
        """Per-character style of one cell's raw value, read straight off
        the body tags: one dict per character. The drawing folds equal
        neighbours into runs, so a single coloured letter -- or a single
        coloured checkmark -- shows exactly as itself instead of painting
        the whole cell."""
        bounds = core_tables.cell_bounds(line)
        if c >= len(bounds):
            return []
        start, end = bounds[c]
        if start >= end:
            return []
        # The column walks along with the characters -- counting each one's
        # UTF-16 width from the line's start again made this quadratic.
        col = self._col_base(line_no) + self._tk_col(line, start)
        out = []
        for ch in line[start:end]:
            try:
                tags = set(self.body_text.tag_names(f"{line_no}.{col}"))
            except tk.TclError:
                tags = set()
            col += 2 if ord(ch) > 0xFFFF else 1
            st = {"bold": bool(tags & {"bold", "bold_italic"}),
                  "italic": bool(tags & {"italic", "bold_italic"}),
                  "underline": "underline" in tags,
                  "strike": "strike" in tags, "fg": None, "bg": None}
            for t in tags:
                if t.startswith("text_color_"):
                    st["fg"] = "#" + t[len("text_color_"):]
                elif t.startswith("highlight_"):
                    st["bg"] = "#" + t[len("highlight_"):]
            out.append(st)
        return out

    _PLAIN_STYLE = {"bold": False, "italic": False, "underline": False,
                    "strike": False, "fg": None, "bg": None}

    def _grid_run_font(self, key, header):
        """The face one run is drawn with. key is (bold, italic,
        underline, strike, fg, emoji)."""
        bold, italic, underline, strike, _fg, emoji = key
        if emoji:
            return ("Segoe UI Emoji", self.editor_font_size)
        header_font, cell_font = self._grid_fonts()
        base = header_font if header else cell_font
        mods = [m for m, on in (("bold", bold or header),
                                ("italic", italic),
                                ("underline", underline),
                                ("overstrike", strike)) if on]
        family, size = base.cget("family"), base.cget("size")
        return (family, size, " ".join(mods)) if mods else (family, size)

    def _grid_draw_cell_text(self, canvas, cell, value, styles, align,
                             header, pad_x, row_h):
        """One cell's text as runs of equal style, one row of runs per
        display line, vertically centred in the cell. Returns the canvas
        item ids -- the caller keeps them to delete on redraw."""
        state = core_tables.checkbox_state(value)
        if state is not None:
            # The cell IS a checkbox: drawn as a real box, not as text.
            # The colour it was given rides as a text_color span on the
            # marker characters, so it survives every save unchanged.
            ink = next((st["fg"] for st in styles if st.get("fg")), None) \
                or self.colors["text"]
            side = max(12, min(18, row_h - 14))
            cx = cell["x"] + cell["w"] / 2
            cy = cell["y"] + cell["h"] / 2
            items = [canvas.create_rectangle(
                cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2,
                outline=ink, width=2)]
            if state:
                items.append(canvas.create_text(
                    cx, cy, text="✓", fill=ink,
                    font=("Segoe UI", max(9, int(side * 0.7)), "bold")))
            return items
        items = []
        lines = core_tables.cell_display_lines(value)
        top = cell["y"] + (cell["h"] - len(lines) * row_h) / 2
        raw_i = 0
        for li, seg in enumerate(lines):
            seg_styles = styles[raw_i:raw_i + len(seg)]
            raw_i += len(seg) + len(core_tables.LINE_BREAK)
            runs = []
            for j, ch in enumerate(seg):
                st = seg_styles[j] if j < len(seg_styles) else self._PLAIN_STYLE
                key = (st["bold"], st["italic"], st["underline"],
                       st["strike"], st["fg"], self._char_is_emoji(ch))
                if runs and runs[-1][0] == key:
                    runs[-1][1] += ch
                else:
                    runs.append([key, ch])
            budget = cell["w"] - 2 * pad_x
            laid, used = [], 0
            for key, txt in runs:
                font = self._grid_run_font(key, header)
                width = self._measure_text(font, txt)
                if used + width <= budget:
                    laid.append((txt, font, key[4]))
                    used += width
                else:
                    shown = self._ellipsize(txt, font, budget - used)
                    if shown:
                        laid.append((shown, font, key[4]))
                        used += self._measure_text(font, shown)
                    break
            if align == core_tables.ALIGN_CENTER:
                x = cell["x"] + (cell["w"] - used) / 2
            elif align == core_tables.ALIGN_RIGHT:
                x = cell["x"] + cell["w"] - pad_x - used
            else:
                x = cell["x"] + pad_x
            y_mid = top + li * row_h + row_h / 2
            for txt, font, fg in laid:
                items.append(canvas.create_text(
                    x, y_mid, anchor="w", font=font,
                    fill=fg or self.colors["text"], text=txt))
                x += self._measure_text(font, txt)
        return items

    def _grid_redraw_cell_text(self, info, r, c):
        """Replace one drawn cell's text items with a fresh run layout --
        after a commit, a restyle, or anything that changed the value or
        the tags underneath it."""
        cell = info["cells"].get((r, c))
        if cell is None or c in info.get("hidden_cols", ()):
            return
        canvas = info["canvas"]
        for item in cell.get("texts", ()):
            try:
                canvas.delete(item)
            except tk.TclError:
                pass
        line_no = self._grid_line_of_row(info, r)
        if line_no is None:
            cell["texts"] = []
            return
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        aligns = core_tables.cell_alignments(line)
        align = aligns[c] if c < len(aligns) else core_tables.ALIGN_LEFT
        styles = self._cell_value_styles(line_no, line, c)
        cell["texts"] = self._grid_draw_cell_text(
            info["canvas"], cell, cell["value"], styles, align,
            r == 0, 10, info["row_h"])

    def _editor_configure_style_tags(self, t, header):
        """The cell editor's own copies of the styles it can show live:
        the same names the body uses, so sampling back out is one code
        path."""
        header_font, cell_font = self._grid_fonts()
        base = header_font if header else cell_font
        family, size = base.cget("family"), base.cget("size")
        t.tag_configure("bold", font=(family, size, "bold"))
        t.tag_configure("italic", font=(
            family, size, "bold italic" if header else "italic"))
        t.tag_configure("bold_italic", font=(family, size, "bold italic"))
        t.tag_configure("underline", underline=True)
        t.tag_configure("strike", overstrike=True)
        t.tag_configure("emojif",
                        font=("Segoe UI Emoji", self.editor_font_size))
        t.tag_raise("sel")

    def _editor_apply_display_styles(self, t, raw_value, raw_styles):
        """Lay the cell's saved styles over the editor's display text, so
        the user edits the coloured text they see -- not a plain black
        stand-in that recolours only after commit."""
        li, colu, i = 1, 0, 0
        marker = core_tables.LINE_BREAK
        while i < len(raw_value):
            if raw_value.startswith(marker, i):
                i += len(marker)
                li += 1
                colu = 0
                continue
            ch = raw_value[i]
            st = raw_styles[i] if i < len(raw_styles) else self._PLAIN_STYLE
            units = self._tk_units(ch)
            s_idx = f"{li}.{colu}"
            e_idx = f"{li}.{colu + units}"
            try:
                if st["bold"] and st["italic"]:
                    t.tag_add("bold_italic", s_idx, e_idx)
                elif st["bold"]:
                    t.tag_add("bold", s_idx, e_idx)
                elif st["italic"]:
                    t.tag_add("italic", s_idx, e_idx)
                if st["underline"]:
                    t.tag_add("underline", s_idx, e_idx)
                if st["strike"]:
                    t.tag_add("strike", s_idx, e_idx)
                if st["fg"]:
                    t.tag_add(self._ensure_color_tag(
                        t, "text_color", st["fg"]), s_idx, e_idx)
                if st["bg"]:
                    t.tag_add(self._ensure_color_tag(
                        t, "highlight", st["bg"]), s_idx, e_idx)
            except tk.TclError:
                pass
            colu += units
            i += 1

    def _editor_retag_emoji(self, t):
        """Emoji get their face per character, live -- the old Entry
        switched the WHOLE box to the emoji font at the first emoji."""
        try:
            t.tag_remove("emojif", "1.0", "end")
            content = t.get("1.0", "end-1c")
        except tk.TclError:
            return
        li, colu = 1, 0
        for ch in content:
            if ch == "\n":
                li += 1
                colu = 0
                continue
            units = self._tk_units(ch)
            if self._char_is_emoji(ch):
                try:
                    t.tag_add("emojif", f"{li}.{colu}",
                              f"{li}.{colu + units}")
                except tk.TclError:
                    pass
            colu += units

    def _editor_sample_styles(self, t, content):
        """Read the editor's live tags back as per-character styles, in
        the same shape _cell_value_styles returns; newlines read plain."""
        out = []
        li, colu = 1, 0
        for ch in content:
            if ch == "\n":
                out.append(dict(self._PLAIN_STYLE))
                li += 1
                colu = 0
                continue
            try:
                tags = set(t.tag_names(f"{li}.{colu}"))
            except tk.TclError:
                tags = set()
            st = {"bold": bool(tags & {"bold", "bold_italic"}),
                  "italic": bool(tags & {"italic", "bold_italic"}),
                  "underline": "underline" in tags,
                  "strike": "strike" in tags, "fg": None, "bg": None}
            for tag in tags:
                if tag.startswith("text_color_"):
                    st["fg"] = "#" + tag[len("text_color_"):]
                elif tag.startswith("highlight_"):
                    st["bg"] = "#" + tag[len("highlight_"):]
            out.append(st)
            colu += self._tk_units(ch)
        return out

    def _styles_display_to_raw(self, display_value, display_styles):
        """The editor's display text (real newlines) as the stored raw
        value (<br> markers), with the style list stretched to match --
        the marker's characters carry no style of their own."""
        raw, out = [], []
        for i, ch in enumerate(display_value):
            st = (display_styles[i] if i < len(display_styles)
                  else dict(self._PLAIN_STYLE))
            if ch == "\n":
                raw.append(core_tables.LINE_BREAK)
                out.extend(dict(self._PLAIN_STYLE)
                           for _ in core_tables.LINE_BREAK)
            else:
                raw.append(ch)
                out.append(st)
        return "".join(raw), out

    def _apply_styles_to_cell(self, info, r, c, value, raw_styles):
        """One cell's per-character styles, written back to the body tags
        -- the inverse of _cell_value_styles. Only the styles the editor
        models are cleared and re-laid; a font size or family tag already
        on the cell is left exactly where it was."""
        line_no = self._grid_line_of_row(info, r)
        if line_no is None:
            return
        b = self.body_text
        line = b.get(f"{line_no}.0", f"{line_no}.end")
        bounds = core_tables.cell_bounds(line)
        if c >= len(bounds):
            return
        start, end = bounds[c]
        if line[start:end] != value:
            # The text on the line is not what these styles were sampled
            # against -- write nothing rather than style the wrong chars.
            return
        base = self._col_base(line_no)

        def idx(off):
            return f"{line_no}.{base + self._tk_col(line, off)}"

        s_idx, e_idx = idx(start), idx(end)
        if b.compare(s_idx, ">=", e_idx):
            return
        for tag in ("bold", "italic", "bold_italic", "underline", "strike"):
            b.tag_remove(tag, s_idx, e_idx)
        for tag in b.tag_names():
            if (tag.startswith("text_color_")
                    or tag.startswith("highlight_")):
                b.tag_remove(tag, s_idx, e_idx)
        i = 0
        while i < len(raw_styles):
            st = raw_styles[i]
            j = i
            while j < len(raw_styles) and raw_styles[j] == st:
                j += 1
            cs, ce = idx(start + i), idx(start + j)
            if st["bold"] and st["italic"]:
                b.tag_add("bold_italic", cs, ce)
            elif st["bold"]:
                b.tag_add("bold", cs, ce)
            elif st["italic"]:
                b.tag_add("italic", cs, ce)
            if st["underline"]:
                b.tag_add("underline", cs, ce)
            if st["strike"]:
                b.tag_add("strike", cs, ce)
            if st["fg"]:
                b.tag_add(self._ensure_color_tag(b, "text_color", st["fg"]),
                          cs, ce)
            if st["bg"]:
                b.tag_add(self._ensure_color_tag(b, "highlight", st["bg"]),
                          cs, ce)
            i = j
        self._grid_reassert_cell_highlight(info, r, c)

    def _grid_reassert_cell_highlight(self, info, r, c):
        """A CELL-level highlight lives pipe-to-pipe; keep it whole.

        The style re-lay above clears the value range and re-applies what
        the editor sampled -- which, for text typed into an empty
        highlighted cell, is nothing. The pads still carry the cell's
        highlight; re-dress the full region so the new text sits inside
        it instead of punching a hole that surfaces at the next rebuild
        ("type in a coloured cell, drag the column, colour gone")."""
        span = self._grid_cell_text_range(info, r, c, pad_ok=True, full=True)
        if not span:
            return
        b = self.body_text
        for tag in b.tag_names():
            if (tag.startswith("highlight_")
                    and b.tag_nextrange(tag, span[0], span[1])):
                b.tag_add(tag, span[0], span[1])
                return

    def _editor_apply_style(self, kind, value=None):
        """A toolbar action while the cell editor is open styles the
        SELECTION inside the editor -- one letter, one emoji, one word --
        or the whole cell when nothing is selected. Visible immediately,
        in the editor itself; the commit carries it to the body."""
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return
        t = editor["entry"]
        try:
            s, e = t.index("sel.first"), t.index("sel.last")
            has_sel = t.compare(s, "<", e)
        except tk.TclError:
            has_sel = False
        if not has_sel and kind in ("text_color", "highlight"):
            # No selection: the colour becomes the PENDING one -- shown
            # as a swatch on the toolbar button, worn by whatever is
            # typed next, in the cell and in the body alike.
            label = "Highlight" if kind == "highlight" else "Text color"
            if kind == "text_color":
                self._pending_text_color = value
            else:
                self._pending_highlight_color = value
            self.set_status(f"{label} on — applies to what you type next"
                            if value else f"{label} off")
            self._refresh_format_buttons()
            return
        if not has_sel:
            s, e = "1.0", "end-1c"
        if t.compare(s, ">=", e):
            return

        def chars():
            idx = s
            while t.compare(idx, "<", e):
                nxt = t.index(f"{idx}+1c")
                if t.get(idx, nxt) != "\n":
                    yield idx, nxt
                idx = nxt

        if kind in ("bold", "italic"):
            family = {"bold": {"bold", "bold_italic"},
                      "italic": {"italic", "bold_italic"}}[kind]
            have = all(set(t.tag_names(i)) & family for i, _ in chars())
            turn_on = not have
            for i, n in chars():
                tags = set(t.tag_names(i))
                b_now = bool(tags & {"bold", "bold_italic"})
                i_now = bool(tags & {"italic", "bold_italic"})
                if kind == "bold":
                    b_now = turn_on
                else:
                    i_now = turn_on
                for tag in ("bold", "italic", "bold_italic"):
                    t.tag_remove(tag, i, n)
                if b_now and i_now:
                    t.tag_add("bold_italic", i, n)
                elif b_now:
                    t.tag_add("bold", i, n)
                elif i_now:
                    t.tag_add("italic", i, n)
        elif kind in ("underline", "strike"):
            have = all(kind in t.tag_names(i) for i, _ in chars())
            for i, n in chars():
                if have:
                    t.tag_remove(kind, i, n)
                else:
                    t.tag_add(kind, i, n)
        elif kind in ("text_color", "highlight"):
            prefix = kind + "_"
            for tag in list(t.tag_names()):
                if tag.startswith(prefix):
                    t.tag_remove(tag, s, e)
            if value:
                t.tag_add(self._ensure_color_tag(t, kind, value), s, e)
        self._refresh_format_buttons()

    def _editor_typing_style(self, t):
        """What the NEXT typed character in the cell should wear: the
        pending colours first, otherwise the style of the character the
        caret sits after (or of the selection about to be replaced, or of
        the character ahead at the very start) -- typing in the middle of
        a blue word stays blue instead of falling back to plain ink."""
        ref = None
        try:
            if t.compare("sel.first", "<", "sel.last"):
                ref = t.index("sel.first")
        except tk.TclError:
            pass
        if ref is None:
            ins = t.index("insert")
            if (t.compare(ins, ">", "1.0")
                    and t.get(f"{ins} -1c", ins) != "\n"):
                ref = t.index(f"{ins} -1c")
            elif t.get(ins, f"{ins} +1c") not in ("", "\n"):
                ref = ins
        st = dict(self._PLAIN_STYLE)
        if ref is not None:
            tags = set(t.tag_names(ref))
            st = {"bold": bool(tags & {"bold", "bold_italic"}),
                  "italic": bool(tags & {"italic", "bold_italic"}),
                  "underline": "underline" in tags,
                  "strike": "strike" in tags, "fg": None, "bg": None}
            for tag in tags:
                if tag.startswith("text_color_"):
                    st["fg"] = "#" + tag[len("text_color_"):]
                elif tag.startswith("highlight_"):
                    st["bg"] = "#" + tag[len("highlight_"):]
        if self._pending_text_color:
            st["fg"] = self._pending_text_color
        if self._pending_highlight_color:
            st["bg"] = self._pending_highlight_color
        return st

    def _editor_paint_range(self, t, s, e, st):
        """One uniform style over [s, e) in the editor -- the modeled
        tags are cleared first, so the range wears exactly *st*."""
        for tag in ("bold", "italic", "bold_italic", "underline", "strike"):
            t.tag_remove(tag, s, e)
        for tag in list(t.tag_names()):
            if (tag.startswith("text_color_")
                    or tag.startswith("highlight_")):
                t.tag_remove(tag, s, e)
        if st["bold"] and st["italic"]:
            t.tag_add("bold_italic", s, e)
        elif st["bold"]:
            t.tag_add("bold", s, e)
        elif st["italic"]:
            t.tag_add("italic", s, e)
        if st["underline"]:
            t.tag_add("underline", s, e)
        if st["strike"]:
            t.tag_add("strike", s, e)
        if st["fg"]:
            t.tag_add(self._ensure_color_tag(t, "text_color", st["fg"]),
                      s, e)
        if st["bg"]:
            t.tag_add(self._ensure_color_tag(t, "highlight", st["bg"]),
                      s, e)

    _EDITOR_PASSTHROUGH_KEYS = {
        "Return", "KP_Enter", "Tab", "Escape", "BackSpace", "Delete",
        "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next",
    }

    def _editor_flush_type_paint(self):
        """Dress whatever the last recorded keystroke typed, if it has
        not been dressed yet. Called from BOTH ends of the key pair --
        fast typing interleaves the events (press, press, release,
        release), and a paint that waited for its own release skipped
        every character whose bookkeeping the next press overwrote."""
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return
        st = editor.pop("type_style", None)
        if st is None:
            return
        t = editor["entry"]
        try:
            s, e = t.index("typestart"), t.index("insert")
            if t.compare(s, "<", e):
                self._editor_paint_range(t, s, e, st)
                self._editor_retag_emoji(t)
        except tk.TclError:
            pass

    def _editor_key_press(self, event=None):
        """BEFORE the class binding inserts the typed character: paint
        anything the previous keystroke left undressed, then remember
        where this one will land and what it should wear. Tk only
        inherits a tag when both neighbours carry it, so a character
        typed at the END of a coloured run -- or over a replaced
        selection -- arrived plain and the cell read as 'reset to
        black'."""
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return
        self._editor_flush_type_paint()
        char = getattr(event, "char", "") or ""
        keysym = getattr(event, "keysym", "")
        if (len(char) != 1 or ord(char) < 32
                or keysym in self._EDITOR_PASSTHROUGH_KEYS):
            return
        t = editor["entry"]
        try:
            editor["type_style"] = self._editor_typing_style(t)
            try:
                start = (t.index("sel.first")
                         if t.compare("sel.first", "<", "sel.last")
                         else t.index("insert"))
            except tk.TclError:
                start = t.index("insert")
            t.mark_set("typestart", start)
            t.mark_gravity("typestart", "left")
        except tk.TclError:
            editor.pop("type_style", None)

    def _editor_key_release(self, event=None):
        """AFTER the character landed: dress it."""
        self._editor_flush_type_paint()

    def _grid_line_of_row(self, info, r):
        """The text line a data row lives on -- the separator makes the
        mapping non-trivial, and every write must go through it."""
        first = self._grid_first_line(info)
        if first is None:
            return None
        offsets = info.get("row_off")
        if offsets and r < len(offsets):
            return first + offsets[r]
        return first + r

    def _grid_boundary_at(self, info, x):
        """Which column's right edge sits within grabbing distance of x."""
        for c in range(1, len(info["col_x"])):
            if abs(x - info["col_x"][c]) <= 4:
                return c - 1
        return None

    def _grid_row_boundary_at(self, info, y):
        """Which row's bottom edge sits within grabbing distance of y --
        the vertical twin of the column rule, for dragging rows taller
        or shorter."""
        row_y = info.get("row_y") or []
        for r in range(1, len(row_y)):
            if abs(y - row_y[r]) <= 4:
                return r - 1
        return None

    @_undo_atom
    def _grid_set_row_lines(self, info, r, lines):
        """One row's height, as its line count. Growing pads the row's
        tallest cell with empty <br> lines; shrinking trims trailing
        empty lines from every cell -- never below anyone's real
        content, so the table's text is never cut by a drag."""
        cells_in_row = [(c, cell) for (rr, c), cell in info["cells"].items()
                        if rr == r and cell.get("rs", 1) == 1]
        if not cells_in_row:
            return
        first = self._grid_first_line(info)
        if first is None:
            return

        def core_of(value):
            segs = core_tables.cell_display_lines(value)
            while len(segs) > 1 and not segs[-1].strip():
                segs.pop()
            return segs

        floor = max(len(core_of(cell["value"])) for _c, cell in cells_in_row)
        target = max(max(1, lines), floor)
        anchor_c = max(cells_in_row,
                       key=lambda item: len(core_tables.cell_display_lines(
                           item[1]["value"])))[0]
        changed = False
        for c, cell in cells_in_row:
            core = core_of(cell["value"])
            want = target if c == anchor_c else len(core)
            new_value = core_tables.LINE_BREAK.join(
                core + [""] * (want - len(core)))
            if new_value != cell["value"]:
                self._write_cell(info, r, c, new_value)
                cell["value"] = new_value
                changed = True
        if changed:
            self._grid_after_op(first)

    def _grid_cell_at_xy(self, info, x, y):
        """Which cell a canvas point falls in. Covered positions have no
        cell of their own, so a click inside a merge finds its anchor."""
        for (r, c), cell in info["cells"].items():
            if (cell["x"] <= x < cell["x"] + cell["w"]
                    and cell["y"] <= y < cell["y"] + cell["h"]):
                return r, c
        return None

    def _open_cell_editor(self, info, r, c, select=True):
        """One floating Entry over one cell -- the only live widget a table
        ever has. Everything else is drawn, which is what lets a table of
        hundreds of rows scroll without dragging the editor down."""
        # Committing the previous editor can rebuild the grids (a widened
        # column goes stale at close), which destroys the very canvas the
        # caller's info points at. Anchor the table by line first and pick
        # up the fresh grid after -- the same dance _editor_step does.
        anchor_line = self._grid_first_line(info)
        self._commit_cell_editor()
        if anchor_line is not None:
            fresh = self._grid_at_line(anchor_line)
            if fresh is not None:
                info = fresh
        cell = info["cells"].get((r, c))
        if cell is None:
            return
        canvas = info["canvas"]
        if not int(canvas.winfo_exists()):
            return
        header_font, cell_font = self._grid_fonts()
        base_font = header_font if r == 0 else cell_font
        # A Text, not an Entry: a cell can hold line breaks now (stored
        # as markdown's own <br>), and a Text can also SHOW the cell's
        # colours and styles while it is being edited -- the Entry went
        # plain black until commit.
        # The editor wears the cell's own background, the same blend the
        # drawing uses. Left at the theme surface, an empty highlighted
        # cell went bare the moment typing started, and a filled one
        # kept its colour only where text lines carried highlight tags
        # -- the editor's empty area below them showed the theme
        # through, "half the cell's colour gone" in the field report.
        paint = self._grid_cell_paint(info, r, c)
        surface = (inset_surface(self.colors) if r == 0
                   else self.colors["card"])
        editor_bg = (self._blend_hex(paint["bg"], surface, 0.45)
                     if paint["bg"] else surface)
        entry = tk.Text(canvas, relief="flat", bd=0, wrap="none",
                        font=(base_font.cget("family"),
                              base_font.cget("size"),
                              "bold" if r == 0 else "normal"),
                        bg=editor_bg, fg=self.colors["text"],
                        insertbackground=self.colors["text"],
                        highlightthickness=0, padx=2, pady=2, undo=True)
        entry.insert("1.0", cell["value"].replace(
            core_tables.LINE_BREAK, "\n"))
        self._editor_configure_style_tags(entry, r == 0)
        raw_styles = []
        row_line = self._grid_line_of_row(info, r)
        if row_line is not None:
            line = self.body_text.get(f"{row_line}.0", f"{row_line}.end")
            raw_styles = self._cell_value_styles(row_line, line, c)
            self._editor_apply_display_styles(entry, cell["value"],
                                              raw_styles)
            row_aligns = core_tables.cell_alignments(line)
            if c < len(row_aligns):
                entry.tag_configure("cellalign", justify={
                    core_tables.ALIGN_CENTER: "center",
                    core_tables.ALIGN_RIGHT: "right",
                }.get(row_aligns[c], "left"))
                entry.tag_add("cellalign", "1.0", "end")
        self._editor_retag_emoji(entry)
        if select:
            entry.tag_add("sel", "1.0", "end-1c")
        entry.mark_set("insert", "end-1c")
        win = canvas.create_window(cell["x"] + 1, cell["y"] + 1, anchor="nw",
                                   width=cell["w"] - 2, height=cell["h"] - 2,
                                   window=entry)
        self._cell_editor = {"entry": entry, "win": win, "info": info,
                             "r": r, "c": c,
                             "styles_in": [dict(s) for s in raw_styles]}
        entry.focus_set()
        self._refresh_list_buttons()
        # Destroying the previous editor hands focus to the root a moment
        # later, clobbering the focus_set above. Re-asserting after the
        # queue settles keeps the keyboard where the user is looking --
        # and synthetic key events, which follow focus, reach the entry.
        self.after_idle(lambda e=entry: e.focus_set()
                        if e.winfo_exists() else None)
        # The record dies with the widget, on every route that can kill it.
        # Opening another note tears the grids down and this Text with them,
        # and nothing cleared the record -- so the toolbar kept aiming at a
        # dead widget: Bold, Italic and the colours did nothing on the next
        # note except raise "Something went wrong". A <Destroy> binding
        # cannot be missed by a route nobody thought to list; the identity
        # test keeps an old editor's death from clearing a new one's record.
        entry.bind("<Destroy>",
                   lambda _e, this=entry: self._forget_dead_cell_editor(this),
                   add="+")
        entry.bind("<Tab>", lambda _e: self._editor_step(+1))
        entry.bind("<Shift-Tab>", lambda _e: self._editor_step(-1))
        # X11 reports Shift+Tab as its own keysym rather than a modified
        # Tab -- the body text learned this long ago; the cell editor
        # walked into the same wall on the CI. Unknown keysyms are an
        # error on Windows, so the binding is allowed to fail there.
        try:
            entry.bind("<ISO_Left_Tab>",
                       lambda _e: self._editor_step(-1))
        except tk.TclError:
            pass
        entry.bind("<Return>", lambda _e: self._editor_newline())
        entry.bind("<Shift-Return>", lambda _e: self._editor_newline())
        # Escape LEAVES the cell and keeps what was typed, exactly as Tab
        # and a click elsewhere do -- what the User Guide promises. It
        # used to close the editor without a commit, and the keystrokes
        # only ever reach the text through one, so a quick Escape threw
        # the cell's typing away.
        entry.bind("<Escape>",
                   lambda _e: (self._commit_cell_editor(), "break")[1])
        entry.bind("<FocusOut>",
                   lambda _e, this=entry: self.after_idle(
                       lambda: self._maybe_close_cell_editor(this)))
        entry.bind("<KeyPress>", self._editor_key_press, add="+")
        entry.bind("<KeyRelease>", self._editor_key_release, add="+")
        entry.bind("<KeyRelease>",
                   lambda _e, w=win, cv=canvas: self._grow_cell_editor(w, cv),
                   add="+")
        entry.bind("<MouseWheel>", self._forward_grid_wheel)
        # The floating editor sits exactly over its cell, so a right-click
        # lands on it, not the canvas -- commit and show the same menu.
        entry.bind("<Button-3>",
                   lambda e, i=info: self._editor_context_menu(i, e))
        # Ctrl+V with a copied block of cells spreads it from this cell;
        # plain text falls through to the Entry's own paste.
        entry.bind("<Control-v>",
                   lambda e, i=info: self._editor_paste(i))
        entry.bind("<Control-V>",
                   lambda e, i=info: self._editor_paste(i))
        # Ctrl+A selects the whole cell -- Tk's Text default for it is
        # an emacs-style line-start jump nobody here is looking for.
        def _select_all_cell(_e, t=entry):
            try:
                t.tag_add("sel", "1.0", "end-1c")
                t.mark_set("insert", "end-1c")
            except tk.TclError:
                pass
            return "break"
        entry.bind("<Control-a>", _select_all_cell)
        entry.bind("<Control-A>", _select_all_cell)
        # Keep the edited cell inside the scrolled viewport.
        try:
            shown = int(float(canvas.cget("width")))
            left = canvas.canvasx(0)
            if cell["x"] < left or cell["x"] + cell["w"] > left + shown:
                canvas.xview_moveto(
                    max(0.0, cell["x"] / max(1, info["natural"])))
        except tk.TclError:
            pass

    def _close_cell_editor(self):
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return
        self._cell_editor = None
        try:
            editor["info"]["canvas"].delete(editor["win"])
        except tk.TclError:
            pass
        try:
            editor["entry"].destroy()
        except tk.TclError:
            pass
        # A commit that widened a column left the drawing behind the text;
        # the rebuild waits for this moment so it never happens under an
        # editor still open on the grid.
        if editor["info"].pop("stale", False):
            # The commit promises the view stays where the user was --
            # capture explicitly so the restore holds in force through
            # the late window-mapping (the double-click jump's root).
            self._grid_saved_view = self._capture_grid_views()
            self._render_table_grids()

    def _forget_dead_cell_editor(self, entry):
        """A destroyed cell editor stops being the open one (see where
        _open_cell_editor binds this)."""
        editor = getattr(self, "_cell_editor", None)
        if editor is not None and editor.get("entry") is entry:
            self._cell_editor = None

    def _maybe_close_cell_editor(self, source=None):
        """FocusOut closes the editor -- except while the emoji picker is
        up, which holds the click without holding the focus, and the chosen
        emoji still needs somewhere to land.

        *source* is the entry whose FocusOut scheduled this. A destroyed
        editor fires FocusOut too, and by the time the callback runs a NEW
        editor may be open -- the stale callback must not close it, which
        it did: stepping through cells worked once and then died.
        """
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return
        if source is not None and source is not editor["entry"]:
            return
        try:
            focus = self.focus_get()
        except (tk.TclError, KeyError):
            focus = None
        if focus is editor["entry"]:
            return
        if focus is None or focus is self:
            # Mid-transfer. Destroying the old editor hands focus to the
            # root window before the new editor's focus_set settles, so at
            # this moment focus reads as the app itself -- and closing here
            # is what killed the second cell of every step-through. A real
            # click elsewhere always names a specific widget, never the
            # root.
            return
        popup = getattr(self, "_mini_popup", None)
        try:
            if popup is not None and popup.winfo_exists():
                return
        except tk.TclError:
            pass
        self._commit_cell_editor()

    @_undo_atom
    def _commit_cell_editor(self, close=True):
        """The editor's value reaches the hidden text, then the drawing.

        The text is written while the grid's mark is still alive -- writing
        after a teardown would find no line to write to, and the keystrokes
        still sitting in the box would be lost.
        """
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return False
        # A commit can arrive between a keystroke's press and release --
        # the typed character gets its dress before it is sampled.
        self._editor_flush_type_paint()
        info, r, c = editor["info"], editor["r"], editor["c"]
        try:
            content = editor["entry"].get("1.0", "end-1c")
            display_styles = self._editor_sample_styles(
                editor["entry"], content)
        except tk.TclError:
            content, display_styles = None, None
        wrote = False
        cell = info["cells"].get((r, c))
        if content is not None and cell is not None:
            # Spaces and tabs trim off the ends; NEWLINES stay -- an
            # empty last line the user just made with Enter is the room
            # they are about to type into, not stray whitespace.
            lead = len(content) - len(content.lstrip(" \t"))
            trimmed = content.strip(" \t").replace(core_tables.CELL, "/")
            display_styles = (display_styles or [])[lead:lead + len(trimmed)]
            while len(display_styles) < len(trimmed):
                display_styles.append(dict(self._PLAIN_STYLE))
            trimmed = mend_surrogates(trimmed)
            display_styles = display_styles[:len(trimmed)]
            value, raw_styles = self._styles_display_to_raw(
                trimmed, display_styles)
            changed_text = value != cell["value"]
            styles_changed = raw_styles != editor.get("styles_in")
            if changed_text:
                old_lines = len(core_tables.cell_display_lines(
                    cell["value"]))
                self._write_cell(info, r, c, value)
                cell["value"] = value
                if len(core_tables.cell_display_lines(value)) != old_lines:
                    # The row must grow or shrink to the new line count;
                    # the rebuild waits for the editor to close.
                    info["stale"] = True
                first = self._grid_first_line(info)
                if first is not None:
                    data = [self.body_text.get(f"{n}.0", f"{n}.end")
                            for n in (self._grid_line_of_row(info, i)
                                      for i in range(info["data_rows"]))
                            if n is not None]
                    widths = core_tables.column_widths(
                        [core_tables.split_row(line) for line in data])
                    if widths != info["widths_chars"]:
                        info["stale"] = True
            if changed_text or styles_changed:
                # The editor's styles ARE the cell's styles now: what was
                # bolded or coloured while typing reaches the body tags,
                # then the drawing -- redrawn as runs, so the face, the
                # colours, and the line breaks all follow immediately.
                self._apply_styles_to_cell(info, r, c, value, raw_styles)
                self._grid_redraw_cell_text(info, r, c)
                editor["styles_in"] = [dict(s) for s in raw_styles]
                wrote = True
        if close:
            self._close_cell_editor()
        if wrote:
            self._schedule_autosave()
        return wrote

    def _write_cell(self, info, r, c, value):
        b = self.body_text
        first = self._grid_first_line(info)
        if first is None:
            return
        line_no = self._grid_line_of_row(info, r)
        if line_no is None:
            return
        base = 1 if line_no == first else 0
        line = b.get(f"{line_no}.0", f"{line_no}.end")
        bounds = core_tables.cell_bounds(line)
        if c >= len(bounds):
            return
        start, end = bounds[c]
        old = line[start:end]
        if old != value:
            # Edit only the differing middle. A whole-range delete took
            # every tag on the cell with it -- a styled cell being padded
            # with trailing <br>s by a row-height drag came back plain.
            # The untouched prefix/suffix keep their tags; the markers a
            # pad appends arrive unstyled, which is what they should be.
            p = 0
            while p < len(old) and p < len(value) and old[p] == value[p]:
                p += 1
            sfx = 0
            while (sfx < len(old) - p and sfx < len(value) - p
                   and old[len(old) - 1 - sfx] == value[len(value) - 1 - sfx]):
                sfx += 1
            t_a = base + self._tk_col(line, start + p)
            t_b = base + self._tk_col(line, end - sfx)
            if t_b > t_a:
                b.delete(f"{line_no}.{t_a}", f"{line_no}.{t_b}")
            mid = value[p:len(value) - sfx]
            if mid:
                b.insert(f"{line_no}.{t_a}", mid)
            self._align_table_block(first)

    def _editor_step(self, delta):
        """Tab and Shift+Tab between cells; Tab at the very last one adds
        a row, which is what lets a whole table be typed without the
        mouse. Backwards out of the first cell stays put."""
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return "break"
        info, r, c = editor["info"], editor["r"], editor["c"]
        anchor_line = self._grid_first_line(info)
        self._commit_cell_editor()
        fresh = (self._grid_at_line(anchor_line)
                 if anchor_line is not None else None)
        if fresh is None:
            return "break"
        order = sorted(fresh["cells"])
        try:
            index = order.index((r, c)) + delta
        except ValueError:
            index = 0
        if index >= len(order):
            self._grid_add_row(fresh)
            return "break"
        if index < 0:
            index = 0
        self._open_cell_editor(fresh, *order[index])
        return "break"

    def _editor_newline(self):
        """Enter (and Shift+Enter) start a new line INSIDE the cell --
        stored as markdown's own <br>. The ROW grows right now, not at
        the eventual commit: the taller floating overlay used to hang
        over the row below and hide it. Commit, rebuild, and reopen the
        editor inside the properly sized cell, caret where it was.
        Leaving the cell stays what it always was elsewhere: Tab,
        Escape, or a click anywhere else."""
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return "break"
        entry = editor["entry"]
        self._editor_flush_type_paint()
        try:
            entry.insert("insert", "\n")
            entry.tag_add("cellalign", "1.0", "end")
            caret = entry.index("insert")
        except tk.TclError:
            return "break"
        info, r, c = editor["info"], editor["r"], editor["c"]
        anchor_line = self._grid_first_line(info)
        self._commit_cell_editor()
        fresh = (self._grid_at_line(anchor_line)
                 if anchor_line is not None else None)
        if fresh is not None and (r, c) in fresh["cells"]:
            self._open_cell_editor(fresh, r, c, select=False)
            reopened = getattr(self, "_cell_editor", None)
            if reopened is not None:
                try:
                    reopened["entry"].mark_set("insert", caret)
                except tk.TclError:
                    pass
        return "break"

    def _editor_fit_window(self):
        """Grow the floating editor's window to its line count -- the
        drawn row itself grows on commit, when the grids may rebuild."""
        editor = getattr(self, "_cell_editor", None)
        if not editor:
            return
        info, cell = editor["info"], editor["info"]["cells"].get(
            (editor["r"], editor["c"]))
        if cell is None:
            return
        try:
            lines = int(editor["entry"].index("end-1c").split(".")[0])
            need = max(cell["h"] - 2, lines * info["row_h"])
            if need > int(float(info["canvas"].itemcget(
                    editor["win"], "height"))):
                info["canvas"].itemconfigure(editor["win"], height=need)
        except (tk.TclError, ValueError):
            pass

    def _insert_emoji_from_toolbar(self):
        """The toolbar emoji button lands in whatever is being written --
        the open table cell if there is one, the note body otherwise."""
        editor = getattr(self, "_cell_editor", None)
        target = editor["entry"] if editor else self.body_text
        self._show_emoji_picker(target, anchor=self.emoji_btn)

    def _grid_available_width(self):
        """How wide a table may draw before it has to scroll instead."""
        try:
            width = self.body_text.winfo_width()
        except tk.TclError:
            width = 0
        # Before the editor is mapped the widget reports 1; better to let a
        # table draw at its natural width than to squeeze it into nothing.
        return width - 50 if width > 120 else 10_000

    def _fit_grid(self, info):
        """Size one grid's viewport, showing a scrollbar only when needed."""
        canvas = info.get("canvas")
        if canvas is None:
            return
        avail = max(160, self._grid_available_width())
        shown = min(info["natural"] + 1, avail)
        try:
            if int(float(canvas.cget("width"))) != shown:
                canvas.configure(width=shown)
        except tk.TclError:
            return
        needs_bar = info["natural"] + 1 > avail
        hbar = info.get("hbar")
        if needs_bar and hbar is None:
            hbar = ttk.Scrollbar(info["frame"], orient="horizontal",
                                 command=canvas.xview)
            canvas.configure(xscrollcommand=hbar.set)
            info["hbar"] = hbar
        if hbar is not None:
            if needs_bar:
                hbar.pack(side="top", fill="x")
            else:
                hbar.pack_forget()

    def _on_body_resize_grids(self, _event=None):
        for info in getattr(self, "_table_grids", []):
            self._fit_grid(info)

    def _wheel_pixels(self, delta):
        """One notch of the wheel, in pixels. A unit is a text LINE, and
        a drawn table is one line as tall as the whole grid -- so unit
        scrolling leapt from table to table instead of gliding."""
        if not delta:
            return 0
        notches = -delta / 120.0
        step = int(notches * 60)
        if step == 0:
            step = -1 if delta > 0 else 1
        return step

    def _text_wheel_scroll(self, text_widget, event, fallback_canvas=None):
        """One wheel step over a text box, in PIXELS. THE handler for
        every real wheel event over the body -- the box's own binding and
        the grids' forwarding both land here, so there is exactly one
        place deciding how a note scrolls. (A first pixel version lived
        on a direct body binding that _bind_text_wheel then silently
        REPLACED -- bind() without add overwrites -- so real wheels kept
        leaping table to table while the tests, calling the method
        directly, stayed green.) If the box's content fits, the page
        scrolls instead, so the buttons below stay reachable."""
        # A deliberate wheel move beats a grid rebuild's pending
        # view restore -- the user outranks the machinery here just
        # as on the note list.
        self._grid_view_restore = None
        try:
            first, last = text_widget.yview()
        except (tk.TclError, ValueError):
            return
        fits = first <= 0.0 and last >= 1.0
        if fits:
            target = fallback_canvas or getattr(self, "editor_canvas", None)
            if target is not None:
                try:
                    target.yview_scroll(int(-1 * (event.delta / 120)),
                                        "units")
                except (tk.TclError, ValueError):
                    pass
            return "break"
        try:
            text_widget.yview_scroll(self._wheel_pixels(event.delta),
                                     "pixels")
        except tk.TclError:
            pass
        return "break"

    def _forward_grid_wheel(self, event):
        """The wheel over a table scrolls the note, as it does over text."""
        return self._text_wheel_scroll(self.body_text, event)

    def _grid_wheel_x(self, canvas, event):
        """Shift+wheel pans a wide table sideways."""
        try:
            canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        except tk.TclError:
            pass
        return "break"

    def _build_table_grid(self, first, last):
        b = self.body_text
        block = [b.get(f"{n}.0", f"{n}.end") for n in range(first, last + 1)]
        sep_at = core_tables.separator_index(block)
        sep_cols = (core_tables.parse_separator(block[sep_at])
                    if sep_at is not None else None)
        # Data rows and the separator part ways here: the separator is
        # mechanics and is never drawn, so every grid row index maps back
        # to its text line through row_off.
        row_off = [i for i in range(len(block)) if i != sep_at]
        rows = [core_tables.split_row(block[i]) for i in row_off]
        widths = core_tables.column_widths(rows)
        if not widths:
            return
        merges, covered = core_tables.merge_map(rows)
        aligns_matrix = [core_tables.cell_alignments(block[i])
                         for i in row_off]
        header_font, cell_font = self._grid_fonts()
        pad_x, pad_y = 10, 7
        row_h = max(header_font.metrics("linespace"),
                    cell_font.metrics("linespace")) + 2 * pad_y
        char_px = cell_font.measure("0")
        floor = char_px * core_tables.MIN_COLUMN
        col_w = [floor] * len(widths)
        hidden_cols = set()
        for c in range(len(widths)):
            column = sep_cols[c] if sep_cols and c < len(sep_cols) else None
            if column and column.get("hidden"):
                # A hidden column is a sliver, not an absence: wide enough
                # to right-click for Unhide, too thin to read.
                hidden_cols.add(c)
                col_w[c] = 14
                continue
            if column and column.get("width"):
                # The dash count is the display width, exactly -- narrower
                # than the content clips to an ellipsis, deliberately (a
                # hand-narrowed column). Pasted markdown's conventional
                # "---" never reaches here: parse_separator reads a
                # minimum-width separator as "no width opinion".
                col_w[c] = char_px * column["width"] + 2 * pad_x
                continue
            for r, row in enumerate(rows):
                span = merges.get((r, c))
                if (r, c) in covered or (span and span[1] > 1):
                    continue
                font = header_font if r == 0 else cell_font
                value = row[c] if c < len(row) else ""
                # A multi-line cell is as wide as its WIDEST line, not as
                # wide as its raw text with the break markers in it.
                col_w[c] = max(col_w[c], max(
                    (self._measure_text(font, seg)
                     for seg in core_tables.cell_display_lines(value)),
                    default=0) + 2 * pad_x)
        col_x = [0]
        for width in col_w:
            col_x.append(col_x[-1] + width)
        natural = col_x[-1]
        # A row is as tall as its tallest cell's line count.
        row_lines = []
        for r, row in enumerate(rows):
            n = 1
            for c in range(len(widths)):
                if (r, c) in covered or c in hidden_cols:
                    continue
                value = row[c] if c < len(row) else ""
                n = max(n, len(core_tables.cell_display_lines(value)))
            row_lines.append(n)
        row_y = [0]
        for n in row_lines:
            row_y.append(row_y[-1] + n * row_h)
        height = row_y[-1]

        host = tk.Frame(b, bg=self.colors["card"], cursor="arrow")
        canvas = tk.Canvas(host, highlightthickness=0, bd=0, cursor="arrow",
                           bg=self.colors["card"], height=height + 1,
                           scrollregion=(0, 0, natural + 1, height + 1))
        canvas.pack(side="top", anchor="w")
        cells = {}
        rule = hairline(self.colors)

        def wash(line_no, line, c, styles):
            """The highlight a cell's rectangle is washed with -- the tag on
            its first character, or on its padding when it is empty: the
            same question _grid_cell_paint asks of a grid already built."""
            if styles:
                return styles[0]["bg"]
            pipes = core_tables.pipe_positions(line)
            if c + 1 >= len(pipes) or pipes[c] + 1 >= pipes[c + 1]:
                return None
            try:
                tags = self.body_text.tag_names(
                    f"{line_no}.{self._tk_col(line, pipes[c] + 1)}")
            except tk.TclError:
                return None
            bg = None
            for t in tags:
                if t.startswith("highlight_"):
                    bg = "#" + t[len("highlight_"):]
            return bg

        # Each cell is drawn ONCE, with its own styles. The build used to
        # draw every cell plain and then _grid_restyle drew every one
        # again, reading all its tags a second time -- half of opening a
        # big table. The rectangles go down first and the text after
        # them, the stacking that second pass left behind.
        texts = []
        for r, row in enumerate(rows):
            for c in range(len(widths)):
                if (r, c) in covered:
                    continue
                row_span, col_span = merges.get((r, c), (1, 1))
                x, y = col_x[c], row_y[r]
                w = col_x[min(c + col_span, len(col_w))] - x
                h = row_y[min(r + row_span, len(rows))] - y
                value = row[c] if c < len(row) else ""
                surface = (inset_surface(self.colors) if r == 0
                           else self.colors["card"])
                if c in hidden_cols:
                    canvas.create_rectangle(x, y, x + w, y + h,
                                            fill=surface, outline=rule)
                    continue
                line_no = first + row_off[r]
                line = block[row_off[r]]
                styles = self._cell_value_styles(line_no, line, c)
                bg = wash(line_no, line, c, styles)
                # The saved colour stays pure; only the DRAWING blends it
                # toward the cell's surface (see _grid_restyle).
                rect = canvas.create_rectangle(
                    x, y, x + w, y + h,
                    fill=(self._blend_hex(bg, surface, 0.45) if bg
                          else surface),
                    outline=rule)
                align = (aligns_matrix[r][c]
                         if r < len(aligns_matrix)
                         and c < len(aligns_matrix[r])
                         else core_tables.ALIGN_LEFT)
                cell = {"value": value, "rect": rect, "texts": [],
                        "x": x, "y": y, "w": w, "h": h,
                        "rs": row_span, "cs": col_span}
                cells[(r, c)] = cell
                texts.append((cell, value, styles, align, r == 0))
        for cell, value, styles, align, header in texts:
            cell["texts"] = self._grid_draw_cell_text(
                canvas, cell, value, styles, align, header, pad_x, row_h)
        mark = f"table_grid_{id(host)}"
        b.mark_set(mark, f"{first}.0")
        b.mark_gravity(mark, "left")
        info = {"frame": host, "canvas": canvas, "hbar": None,
                "natural": natural, "cells": cells, "mark": mark,
                "nrows": len(block), "data_rows": len(rows),
                "row_off": row_off, "sep_cols": sep_cols,
                "hidden_cols": hidden_cols,
                "ncols": len(widths), "row_h": row_h, "col_x": col_x,
                "row_y": row_y, "widths_chars": list(widths)}
        self._fit_grid(info)
        canvas.bind("<Button-1>", lambda e, i=info: self._grid_press(i, e))
        canvas.bind("<B1-Motion>", lambda e, i=info: self._grid_drag(i, e))
        canvas.bind("<ButtonRelease-1>",
                    lambda e, i=info: self._grid_release(i, e))
        canvas.bind("<Button-3>", lambda e, i=info: self._grid_menu(i, e))
        canvas.bind("<Motion>", lambda e, i=info: self._grid_motion(i, e))
        canvas.bind("<Double-Button-1>",
                    lambda e, i=info: self._grid_double(i, e))
        # Saved formatting is already on the text as tags by the time a
        # grid is built (load applies formatting first), so the one pass
        # above painted it from the first frame.
        for widget in (host, canvas):
            widget.bind("<MouseWheel>", self._forward_grid_wheel)
            widget.bind("<Shift-MouseWheel>",
                        lambda ev, cv=canvas: self._grid_wheel_x(cv, ev))
        b.window_create(f"{first}.0", window=host, padx=1, pady=6,
                        align="bottom")
        b.tag_add(self.TABLE_HIDE_TAG, f"{first}.1", f"{last}.end")
        # Tk justifies a display line by its FIRST character's tags, and
        # the window character just landed untagged at column 0 -- a
        # centred table snapped back left on every rebuild until the
        # window itself carried the position.
        table_align = self._grid_table_align_of(first)
        if table_align in ("center", "right"):
            b.tag_add(f"align_{table_align}", f"{first}.0", f"{first}.1")
        self._table_grids = getattr(self, "_table_grids", [])
        self._table_grids.append(info)

    def _grid_clear_selection(self):
        sel = getattr(self, "_grid_sel", None)
        self._grid_sel = None
        if not sel:
            return
        info = sel["info"]
        rule = hairline(self.colors)
        for key in sel["cells"]:
            cell = info["cells"].get(key)
            if cell is None:
                continue
            try:
                info["canvas"].itemconfigure(cell["rect"],
                                             outline=rule, width=1)
            except tk.TclError:
                pass

    def _grid_select_range(self, info, a, b):
        """Highlight the rectangle spanned by two cells.

        Grown until it swallows every merge it touches -- half a merged
        cell is not a thing a selection can hold.
        """
        r0, r1 = sorted((a[0], b[0]))
        c0, c1 = sorted((a[1], b[1]))
        grew = True
        while grew:
            grew = False
            for (r, c), cell in info["cells"].items():
                if r + cell["rs"] - 1 < r0 or r > r1:
                    continue
                if c + cell["cs"] - 1 < c0 or c > c1:
                    continue
                lo_r, hi_r = min(r0, r), max(r1, r + cell["rs"] - 1)
                lo_c, hi_c = min(c0, c), max(c1, c + cell["cs"] - 1)
                if (lo_r, hi_r, lo_c, hi_c) != (r0, r1, c0, c1):
                    r0, r1, c0, c1 = lo_r, hi_r, lo_c, hi_c
                    grew = True
        self._grid_clear_selection()
        chosen = [key for key, cell in info["cells"].items()
                  if r0 <= key[0] <= r1 and c0 <= key[1] <= c1]
        for key in chosen:
            try:
                info["canvas"].itemconfigure(info["cells"][key]["rect"],
                                             outline=self.colors["accent"],
                                             width=2)
            except tk.TclError:
                pass
        self._grid_sel = {"info": info, "cells": chosen,
                          "box": (r0, c0, r1, c1)}

    def _grid_press(self, info, event):
        # Canvas coordinates are read while the canvas is certainly alive:
        # the commit below can destroy it, and a scrolled table would
        # otherwise aim the click at the wrong cell.
        self._grid_autoscroll_stop()
        press_x = info["canvas"].canvasx(event.x)
        press_y = info["canvas"].canvasy(event.y)
        if getattr(self, "_cell_editor", None) is not None:
            # The press takes the keyboard back from the open editor --
            # otherwise Ctrl+C/V keep talking to the entry (whose text
            # opens selected) while the user is looking at the cells they
            # just selected: copying two cells pasted the entry's word
            # into the entry's own cell instead.
            anchor_line = self._grid_first_line(info)
            self._commit_cell_editor()
            self.body_text.focus_set()
            if not int(info["canvas"].winfo_exists()):
                # The commit's rebuild took this canvas with it, and the
                # implicit grab means no drag or release will follow. The
                # cell the user aimed at is known from the geometry they
                # were LOOKING at, so the click still lands: the editor
                # opens there on the fresh grid, at press time.
                self._grid_pressed = None
                hit = self._grid_cell_at_xy(info, press_x, press_y)
                fresh = (self._grid_at_line(anchor_line)
                         if anchor_line is not None else None)
                if fresh is not None and hit is not None:
                    self._open_cell_editor(fresh, *hit)
                return "break"
        canvas = info["canvas"]
        x = press_x
        boundary = self._grid_boundary_at(info, x)
        if boundary is not None:
            # Grabbing a rule resizes its column instead of selecting.
            self._grid_resizing = {"info": info, "col": boundary, "x": x}
            self._grid_pressed = None
            return "break"
        row_boundary = self._grid_row_boundary_at(info, press_y)
        if row_boundary is not None:
            # The horizontal rule resizes its row, the vertical twin of
            # dragging a column wider.
            self._grid_row_resizing = {"info": info, "row": row_boundary,
                                       "y": press_y}
            self._grid_pressed = None
            return "break"
        hit = self._grid_cell_at_xy(info, x, press_y)
        self._grid_clear_selection()
        self._grid_pressed = (info, hit, x, press_y) if hit else None
        return "break"

    def _grid_drag_autoscroll(self, info):
        self._grid_view_restore = None
        """While a cell drag runs, the view follows the pointer: the
        grid pans sideways past its own viewport, and the NOTE scrolls
        when the pointer crosses the editor's top or bottom edge -- so a
        selection can reach cells that were not on screen when the drag
        began, the way any spreadsheet allows. The selection is then
        re-stretched to whatever sits under the pointer now."""
        canvas = info.get("canvas")
        try:
            if canvas is None or not int(canvas.winfo_exists()):
                return
            px, py = self.winfo_pointerxy()
            wx = px - canvas.winfo_rootx()
            wy = py - canvas.winfo_rooty()
            try:
                shown = int(float(canvas.cget("width")))
            except (tk.TclError, ValueError):
                shown = canvas.winfo_width()
            natural = max(1, info.get("natural", 1))
            if wx > shown - 24 and canvas.xview()[1] < 1.0:
                canvas.xview_moveto(min(1.0, canvas.xview()[0]
                                        + 24.0 / natural))
            elif wx < 24 and canvas.xview()[0] > 0.0:
                canvas.xview_moveto(max(0.0, canvas.xview()[0]
                                        - 24.0 / natural))
            body = self.body_text
            top = body.winfo_rooty()
            bottom = top + body.winfo_height()
            if py > bottom - 16:
                body.yview_scroll(24, "pixels")
            elif py < top + 16:
                body.yview_scroll(-24, "pixels")
            pressed = getattr(self, "_grid_pressed", None)
            if pressed and pressed[0] is info:
                hit = self._grid_cell_at_xy(info, canvas.canvasx(wx),
                                            canvas.canvasy(wy))
                if hit and hit != pressed[1]:
                    self._grid_select_range(info, pressed[1], hit)
        except tk.TclError:
            pass

    def _grid_autoscroll_tick(self):
        self._grid_autoscroll_job = None
        info = getattr(self, "_grid_drag_hold", None)
        if info is None:
            return
        self._grid_drag_autoscroll(info)
        self._grid_autoscroll_job = self.after(
            60, self._grid_autoscroll_tick)

    def _grid_autoscroll_stop(self):
        self._grid_drag_hold = None
        job = getattr(self, "_grid_autoscroll_job", None)
        self._grid_autoscroll_job = None
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass

    def _grid_drag(self, info, event):
        if (getattr(self, "_grid_resizing", None)
                or getattr(self, "_grid_row_resizing", None)):
            return "break"
        pressed = getattr(self, "_grid_pressed", None)
        if not pressed or pressed[0] is not info:
            return "break"
        # A held pointer at an edge produces no more motion events; the
        # timer keeps the view (and the selection) moving until release.
        self._grid_drag_hold = info
        if getattr(self, "_grid_autoscroll_job", None) is None:
            self._grid_autoscroll_job = self.after(
                60, self._grid_autoscroll_tick)
        canvas = info["canvas"]
        hit = self._grid_cell_at_xy(info, canvas.canvasx(event.x),
                                    canvas.canvasy(event.y))
        if hit and hit != pressed[1]:
            self._grid_select_range(info, pressed[1], hit)
        return "break"

    def _grid_release(self, info, event):
        """A plain click opens the editor; a drag leaves its selection."""
        self._grid_autoscroll_stop()
        self.after_idle(self._refresh_list_buttons)
        resizing = getattr(self, "_grid_resizing", None)
        self._grid_resizing = None
        if resizing is not None and resizing["info"] is info:
            canvas = info["canvas"]
            # A press beside a rule that never moved is a click, not a
            # drag -- applying it would nudge the width by a rounding
            # error every time someone clicks near a boundary.
            if abs(canvas.canvasx(event.x) - resizing["x"]) < 3:
                return "break"
            col = resizing["col"]
            left = info["col_x"][col]
            new_px = canvas.canvasx(event.x) - left
            _hf, cell_font = self._grid_fonts()
            char_px = max(1, cell_font.measure("0"))
            self._grid_set_col_width(
                info, col, max(2, round((new_px - 20) / char_px)))
            return "break"
        row_resizing = getattr(self, "_grid_row_resizing", None)
        self._grid_row_resizing = None
        if row_resizing is not None and row_resizing["info"] is info:
            canvas = info["canvas"]
            if abs(canvas.canvasy(event.y) - row_resizing["y"]) < 3:
                return "break"
            row = row_resizing["row"]
            top = info.get("row_y", [0])[row] if row < len(
                info.get("row_y", [])) else 0
            new_px = canvas.canvasy(event.y) - top
            self._grid_set_row_lines(
                info, row, max(1, round(new_px / info["row_h"])))
            return "break"
        pressed = getattr(self, "_grid_pressed", None)
        self._grid_pressed = None
        if pressed is None or pressed[0] is not info:
            return "break"
        if getattr(self, "_grid_sel", None) is None and pressed[1]:
            # A real drag that never left its cell selects THAT cell
            # whole -- there was no way to select a single cell before
            # (the drag had to reach a neighbour), so grabbing one cell
            # meant grabbing two. A short click still opens the editor.
            canvas = info["canvas"]
            moved = max(abs(canvas.canvasx(event.x) - pressed[2]),
                        abs(canvas.canvasy(event.y) - pressed[3]))
            if moved >= 10:
                self._grid_select_range(info, pressed[1], pressed[1])
                self.body_text.focus_set()
            elif not self._grid_toggle_checkbox(info, *pressed[1]):
                # A checkbox cell toggles on click; every other cell
                # opens for typing, as always. Editing a checkbox AS
                # TEXT stays available from its right-click menu.
                self._open_cell_editor(info, *pressed[1])
        else:
            # A finished drag leaves a selection; the keyboard belongs to
            # it now, so Delete and Ctrl+C/V land on the cells no matter
            # where focus wandered before the drag.
            self.body_text.focus_set()
        return "break"

    @staticmethod
    def _tk_units(text):
        """How many index steps *text* is wide in a Tk Entry.

        Tk counts UTF-16 units, so an astral character -- every emoji past
        the basic plane -- is two steps, and advancing by Python's len()
        parks the caret inside the character just inserted. Counted by
        the codec rather than character by character (the same answer,
        a lone surrogate half counting one): opening a 60-row table
        walked 131,000 characters through a generator here.
        """
        return len(text.encode("utf-16-le", "surrogatepass")) // 2

    @classmethod
    def _tk_col(cls, line, char_col):
        """A Python character offset into *line*, as a Tk Text column.

        Tk counts UTF-16 units, so every astral character before the offset
        widens it by one. Addressing the text with raw character offsets cut
        into the wrong place the moment a cell held an emoji -- and every
        flush re-cut at the drifted position, multiplying the damage.
        """
        return cls._tk_units(line[:char_col])

    @staticmethod
    def _py_col(line, tk_col):
        """A Tk Text column into *line*, as a Python character offset —
        the inverse of _tk_col. A unit index landing inside an astral
        pair resolves past that character (never mid-character), and
        anything beyond the line clamps to its length. Without this, a
        Tk column read from an index was used to slice Python strings
        directly, drifting one place per emoji to its left."""
        u = 0
        for i, ch in enumerate(line):
            if u >= tk_col:
                return i
            u += 2 if ord(ch) > 0xFFFF else 1
        return len(line)

    @staticmethod
    def _astral_span_at(s, iu, before):
        """The character whose UTF-16 span contains unit index *iu*
        (``before=False``), or ends at / straddles it (``before=True``).

        Returns ``(start_unit, unit_width)``, or ``(None, None)`` past
        either end of the string.
        """
        u = 0
        for ch in s:
            w = 2 if ord(ch) > 0xFFFF else 1
            if (before and u < iu <= u + w) or (not before and u <= iu < u + w):
                return u, w
            u += w
        return None, None

    def _entry_backspace_astral(self, event):
        """BackSpace in a tk.Entry deletes exactly one UTF-16 unit — half
        an astral emoji. The torn remnant renders as a box, and the save's
        surrogate mend then faithfully turns its bytes into replacement
        characters (field report: emoji in the title -> box -> question
        marks after a restart). Delete the whole character instead; stand
        down (return None) everywhere else so stock behavior is untouched.
        The body is a tk.Text, which deletes whole characters on its own —
        only the Entry family needs this."""
        w = event.widget
        try:
            if w.select_present():
                return None  # Tk deletes the whole selection; no tearing
            s = w.get()
            iu = w.index("insert")
        except tk.TclError:
            return None
        start, width = self._astral_span_at(s, iu, before=True)
        if width == 2:
            w.delete(start, start + width)
            return "break"
        return None

    def _entry_delete_astral(self, event):
        """The Delete-key twin of _entry_backspace_astral."""
        w = event.widget
        try:
            if w.select_present():
                return None
            s = w.get()
            iu = w.index("insert")
        except tk.TclError:
            return None
        start, width = self._astral_span_at(s, iu, before=False)
        if width == 2:
            w.delete(start, start + width)
            return "break"
        return None

    def _guard_entry_astral(self, entry):
        """Arm a free-text tk.Entry against tearing astral characters —
        bound on every Entry that accepts arbitrary text (title, searches,
        checklist items, category and template names, the username)."""
        entry.bind("<BackSpace>", self._entry_backspace_astral)
        entry.bind("<Delete>", self._entry_delete_astral)

    def _restore_editor_view(self, at):
        try:
            self.editor_canvas.yview_moveto(at)
        except tk.TclError:
            pass

    def _restore_views_idle(self, page, body, explicit=False):
        # After a paste the right view is wherever the caret ended up --
        # the end of what was just pasted -- not the fraction captured
        # before the note grew. A plain see() from the paste handler ran
        # BEFORE this restore and was silently undone by it, which is why
        # the flag is honoured here, at the moment the restore happens.
        follow = getattr(self, "_body_follow_caret", False)
        self._body_follow_caret = False
        if follow:
            self._grid_view_restore = None
            try:
                self.body_text.see("insert")
            except tk.TclError:
                pass
        elif body is not None or page is not None:
            if body is not None:
                try:
                    self.body_text.yview_moveto(body)
                except tk.TclError:
                    pass
            if page is not None:
                self._restore_editor_view(page)
            # One idle-time application is not enough for the ops that
            # PROMISE the view stays put (the op-context family and the
            # editor's commit -- the ones that capture the view
            # explicitly before tearing grids down): the fresh grid
            # windows can map AFTER this runs, the Text's estimates
            # settle late, and the fraction lands at the top of the
            # table once they do -- "double-click near the table and
            # the scroll jumps to its start". Same cure as the note
            # list: the target stays in force briefly, on timers.
            # AMBIENT renders (a push-down, an inserted table) keep the
            # single application: their content legitimately moves, and
            # re-pinning a stale fraction is exactly the yank the
            # push-down fix removed.
            if explicit:
                self._grid_view_restore = {
                    "page": page, "body": body,
                    "until": time.monotonic() + 0.5}
                for delay in (60, 160, 360):
                    self.after(delay, self._reapply_grid_view_restore)
            else:
                self._grid_view_restore = None
        if page is None and body is None and not follow:
            self._grid_view_restore = None

    def _editor_scrollbar_moved(self, *args):
        self._grid_view_restore = None
        try:
            self.editor_canvas.yview(*args)
        except tk.TclError:
            pass

    def _body_scrollbar_moved(self, *args):
        self._grid_view_restore = None
        try:
            self.body_text.yview(*args)
        except tk.TclError:
            pass

    def _reapply_grid_view_restore(self):
        """One timed beat of a still-in-force grid-rebuild restore."""
        pend = getattr(self, "_grid_view_restore", None)
        if not pend or not self._still_alive():
            return
        if time.monotonic() > pend["until"]:
            self._grid_view_restore = None
            return
        if pend["body"] is not None:
            try:
                self.body_text.yview_moveto(pend["body"])
            except tk.TclError:
                pass
        if pend["page"] is not None:
            self._restore_editor_view(pend["page"])

    def _grid_click(self, info, event):
        canvas = info["canvas"]
        hit = self._grid_cell_at_xy(info, canvas.canvasx(event.x),
                                    canvas.canvasy(event.y))
        if hit is not None:
            self._open_cell_editor(info, *hit)
        return "break"

    def _flush_table_grids(self):
        """Anything still sitting in the open cell editor reaches the text.

        Every other value is in the text already -- each commit wrote it --
        so capture, autosave and the dirty poll only need the one editor
        flushed, without closing it under the user's typing.

        With no cell open there is nothing to flush, and the commit's undo
        unit -- which notes the note's formatting (_undo_atom_begin) -- is
        not worth opening on every autosave and every dirty poll. The one
        thing it always left behind stays: an undo boundary, which is what
        makes Ctrl+Z take typing back one pause at a time.
        """
        if not getattr(self, "_cell_editor", None):
            try:
                self.body_text.edit_separator()
            except (tk.TclError, AttributeError):
                pass
            return False
        return self._commit_cell_editor(close=False)

    @_undo_atom
    def _grid_add_row(self, info):
        """Tab at the last cell: make somewhere to go, as the text path does."""
        first = self._grid_first_line(info)
        if first is None:
            return "break"
        self._commit_cell_editor()
        again = self._grid_at_line(first)
        if again is not None:
            info = again
        last = first + info["nrows"] - 1
        self.body_text.insert(
            f"{last}.end",
            "\n" + core_tables.blank_table(1, info["ncols"])[0])
        self._align_table_block(first)
        self._resync_list_tags()
        self._render_table_grids()
        fresh = self._grid_at_line(first)
        if fresh is not None:
            bottom = fresh["nrows"] - 1
            for c in range(fresh["ncols"]):
                if (bottom, c) in fresh["cells"]:
                    self._open_cell_editor(fresh, bottom, c)
                    break
        self._schedule_autosave()
        return "break"

    def _extend_word_styles_on_typing(self, event=None):
        """Letters glued onto a styled word wear the word's styles.

        Tk extends a tag over an inserted character only when BOTH its
        neighbours carry it -- so typing at the END of a coloured word
        produced bare letters ("the new letters don't get the colour").
        The rule follows the word boundary the field report asked for:
        a non-space character typed directly after a styled non-space
        character inherits that character's colour, highlight and font
        styles; type a space first and the styles stay behind.
        """
        b = self.body_text
        try:
            typed = b.index("insert-1c")
            prev = b.index("insert-2c")
            if b.compare(prev, ">=", typed):
                return
            # The characters come from the BUFFER, not the event: a
            # synthetic KeyRelease carries no char at all, and reading
            # what actually sits left of the caret is true for real
            # typing, IME input and tests alike.
            typed_ch = b.get(typed)
            if not typed_ch.strip():
                return
            prev_ch = b.get(prev)
            if not prev_ch.strip():
                return
            carry = [t for t in b.tag_names(prev)
                     if t in ("bold", "italic", "bold_italic",
                              "underline", "strike")
                     or t.startswith("text_color_")
                     or t.startswith("highlight_")]
            for tag in carry:
                if tag not in b.tag_names(typed):
                    b.tag_add(tag, typed, "insert")
        except tk.TclError:
            pass

    def _reassert_line_alignment(self, _event=None):
        """Keep the caret's line wearing its own alignment while it is
        typed into.

        Tk justifies a line by the tag on its FIRST character, and a
        typed character lands untagged -- so typing at the start of a
        centred line yanked the whole line left, and the first
        character typed into an EMPTY centred line lost the centring
        outright. The line's newline keeps the tag through all of it
        (which is why deleting the text snapped the cursor back to the
        middle -- the report that exposed this). Re-dress the whole
        line in whatever alignment its surviving characters remember.
        """
        b = self.body_text
        try:
            ln = int(b.index("insert").split(".")[0])
            for align in ("center", "right"):
                tag = f"align_{align}"
                # Anywhere on the line counts, the newline included --
                # typing at the START leaves the tag alive only on the
                # middle of the line, and an empty centred line keeps
                # it only on its newline.
                if b.tag_nextrange(tag, f"{ln}.0", f"{ln}.end+1c"):
                    b.tag_add(tag, f"{ln}.0", f"{ln}.end")
                    break
        except (tk.TclError, ValueError):
            pass

    def _caret_out_of_hidden(self, _event=None):
        """Keep the caret off a rendered table's lines entirely.

        The hidden pipe text, and the window line's visible edges left and
        right of the drawn table, are all places where typing would either
        edit characters nobody can see or land text floating beside the
        grid. The caret is walked to the line under the table instead, so
        writing always continues from the start of a real row.

        On a key press it also holds the table's edges against Tk's own
        line-joining keys, which reach no handler of their own: Ctrl+H
        deletes backwards as BackSpace does, and Ctrl+K at the end of a
        line deletes its line break -- at a drawn table's edge either one
        pulled a table row onto the prose beside it. Delete and BackSpace
        ask the same question in their own handlers.
        """
        b = self.body_text
        try:
            line_no = int(b.index("insert").split(".")[0])
        except (tk.TclError, ValueError):
            return None
        for info in getattr(self, "_table_grids", []):
            first = self._grid_first_line(info)
            if first is not None and first <= line_no < first + info["nrows"]:
                try:
                    b.mark_set("insert", f"{first + info['nrows']}.0")
                except tk.TclError:
                    pass
                break
        if (getattr(_event, "type", None) == tk.EventType.KeyPress
                and getattr(_event, "state", 0) & 0x4):
            keysym = getattr(_event, "keysym", "")
            try:
                at_line_end = b.compare("insert", "==", "insert lineend")
            except tk.TclError:
                at_line_end = False
            if ((keysym == "h"
                 and self._deletion_joins_table(False, selection_wins=False))
                    or (keysym == "k" and at_line_end
                        and self._deletion_joins_table(
                            True, selection_wins=False))):
                return "break"
        return None

    def _deletion_joins_table(self, forward, selection_wins=True):
        """Would a one-character deletion at the caret break a drawn table?

        True when the character it takes is the line break just above a
        drawn table, the one just below it, or anything in between. Tk's
        own Delete and BackSpace glued the neighbouring line onto the
        table's first or last row -- the row then read as prose, fell out
        of the grid and was saved that way. The same boundary the caret
        guard keeps: the table is one block, and the keys stop at its
        edge. *selection_wins* mirrors Tk's rule for Delete and
        BackSpace: with the caret inside a selection they delete the
        selection instead, which is not a question about the edge.
        """
        b = self.body_text
        try:
            if (selection_wins and b.tag_ranges("sel")
                    and b.compare("sel.first", "<=", "insert")
                    and b.compare("insert", "<=", "sel.last")):
                return False
            if not forward and b.compare("insert", "==", "1.0"):
                return False
            at = b.index("insert" if forward else "insert-1c")
            for info in getattr(self, "_table_grids", []):
                first = self._grid_first_line(info)
                if first is None:
                    continue
                last = first + info["nrows"] - 1
                start = f"{first - 1}.end" if first > 1 else "1.0"
                if (b.compare(start, "<=", at)
                        and b.compare(at, "<=", f"{last}.end")):
                    return True
        except tk.TclError:
            return False
        return False

    # ---------- The table's own right-click menu ----------

    def _capture_grid_views(self):
        """The page scroll, the body's own scroll, and each wide table's
        sideways position -- everything a rebuild has to put back."""
        try:
            page = self.editor_canvas.yview()[0]
        except (tk.TclError, AttributeError, IndexError):
            page = None
        try:
            body = self.body_text.yview()[0]
        except (tk.TclError, IndexError):
            body = None
        sideways = {}
        for info in getattr(self, "_table_grids", []):
            line = self._grid_first_line(info)
            if line is not None and info.get("canvas") is not None:
                try:
                    sideways[line] = info["canvas"].xview()[0]
                except (tk.TclError, IndexError):
                    pass
        return page, body, sideways

    def _grid_op_context(self, info):
        """(first, nrows, ncols) with the editor committed and grids down.

        Structural edits move real characters around the window's own
        column; the simplest correct order is grids down, text edited
        plain, grids back up.
        """
        first = self._grid_first_line(info)
        if first is None:
            return None
        self._commit_cell_editor()
        again = self._grid_at_line(first)
        if again is not None:
            info = again
            first = self._grid_first_line(info) or first
        shape = (first, info["nrows"], info["ncols"])
        self._grid_saved_view = self._capture_grid_views()
        self._teardown_table_grids()
        return shape

    def _grid_after_op(self, first):
        self._align_table_block(first)
        self._resync_list_tags()
        self._render_table_grids()
        self._schedule_autosave()
        self._refresh_list_buttons()

    def _grid_block_parts(self, first, text_rows):
        """(data_rows, data_aligns, sep_cols, sep_at) for one block.

        Every structural operation transforms the data and carries the
        separator's columns alongside, so a hand-dragged width or a hidden
        column survives inserts, deletes, merges and fills.
        """
        block = [self.body_text.get(f"{n}.0", f"{n}.end")
                 for n in range(first, first + text_rows)]
        sep_at = core_tables.separator_index(block)
        sep_cols = (core_tables.parse_separator(block[sep_at])
                    if sep_at is not None else None)
        rows, aligns = [], []
        for i, line in enumerate(block):
            if i == sep_at:
                continue
            rows.append(core_tables.split_row(line))
            aligns.append(core_tables.cell_alignments(line))
        return rows, aligns, sep_cols, sep_at

    def _grid_read_rows(self, first, nrows):
        return [core_tables.split_row(
                    self.body_text.get(f"{n}.0", f"{n}.end"))
                for n in range(first, first + nrows)]

    def _grid_read_aligns(self, first, nrows):
        return [core_tables.cell_alignments(
                    self.body_text.get(f"{n}.0", f"{n}.end"))
                for n in range(first, first + nrows)]

    def _grid_replace_block(self, first, old_nrows, rows, aligns=None,
                            sep_cols=None, source=None):
        """Wholesale rewrite for the structural ops that reshape columns.

        The text is rewritten whole, but no cell the operation did not
        touch may change: each cell's styles are read off the old block
        first and laid back on the cell they belong to afterwards. It used
        to be "the accepted cost of reshaping" -- and the same rewrite
        served clearing one cell with Delete, dropping one checkbox and
        deleting one row, so a bold word anywhere in the table died for an
        edit three cells away. *source* maps a new (row, column) to the
        old one it came from, for the ops that move cells (an inserted or
        deleted row or column, copies appended at an edge); the identity
        otherwise. See _grid_lay_cell_styles for what a changed cell keeps.
        """
        b = self.body_text
        # The rewrite deletes the tagged text, and the table's position on
        # the page would go with it -- read it first, put it back after.
        table_align = self._grid_table_align_of(first)
        carried = self._grid_read_cell_styles(first, old_nrows)
        b.delete(f"{first}.0", f"{first + old_nrows - 1}.end")
        lines = core_tables.format_table(rows, aligns)
        if sep_cols is not None and lines:
            while len(sep_cols) < len(core_tables.column_widths(rows)):
                sep_cols.append({"width": None, "align": None,
                                 "hidden": False})
            sep_line = core_tables.CELL + core_tables.CELL.join(
                " " + cell + " "
                for cell in core_tables.make_separator(sep_cols)
            ) + core_tables.CELL
            lines = [lines[0], sep_line] + lines[1:]
        b.insert(f"{first}.0", "\n".join(lines))
        self._grid_lay_cell_styles(first, lines, carried, source)
        if table_align in ("center", "right"):
            for n in range(first, first + len(lines)):
                b.tag_add(f"align_{table_align}", f"{n}.0", f"{n}.end")

    def _grid_read_cell_styles(self, first, nrows):
        """Every data cell's styles, read off the block's tags before a
        rewrite deletes them: ``{(row, col): {"value", "runs", "pad_bg",
        "paint_bg"}}``.

        *runs* are the character-format tags on the cell's text, as
        ``(tag, start, end)`` in the value's own characters. *pad_bg* is a
        CELL-level highlight -- one reaching into the padding, where the
        table's highlight action puts it. *paint_bg* is the colour the
        drawing washes the whole cell with (the highlight on its first
        character, or on its padding when empty; see _grid_cell_paint),
        which is what a person sees as "a coloured cell". Read range by
        range, not character by character: a table of hundreds of cells
        is a few dozen Tk calls this way.
        """
        b = self.body_text
        block = [b.get(f"{n}.0", f"{n}.end")
                 for n in range(first, first + nrows)]
        sep_at = core_tables.separator_index(block)
        data = [i for i in range(len(block)) if i != sep_at]
        runs = {i: [] for i in data}
        top, bottom = f"{first}.0", f"{first + nrows - 1}.end"
        for tag in b.tag_names():
            if not is_format_tag(tag):
                continue
            ranges = b.tag_ranges(tag)
            for k in range(0, len(ranges) - 1, 2):
                s, e = str(ranges[k]), str(ranges[k + 1])
                if b.compare(e, "<=", top) or b.compare(s, ">=", bottom):
                    continue
                s_line, s_col = (int(p) for p in s.split("."))
                e_line, e_col = (int(p) for p in e.split("."))
                for n in range(max(s_line, first),
                               min(e_line, first + nrows - 1) + 1):
                    i = n - first
                    if i not in runs:
                        continue
                    line = block[i]
                    a = self._py_col(line, s_col) if n == s_line else 0
                    z = self._py_col(line, e_col) if n == e_line else len(line)
                    if z > a:
                        runs[i].append((tag, a, z))
        cells = {}
        for r, i in enumerate(data):
            line = block[i]
            pipes = core_tables.pipe_positions(line)
            for c, (s, e) in enumerate(core_tables.cell_bounds(line)):
                lo = pipes[c] + 1 if c < len(pipes) else s
                hi = pipes[c + 1] if c + 1 < len(pipes) else e
                paint_at = s if e > s else lo
                rec = {"value": line[s:e], "runs": [], "pad_bg": None,
                       "paint_bg": None}
                for tag, a, z in runs[i]:
                    if not (a < hi and z > lo):
                        continue
                    if a < e and z > s:
                        rec["runs"].append((tag, max(a, s) - s,
                                            min(z, e) - s))
                    if tag.startswith("highlight_"):
                        if a < s or z > e or s == e:
                            rec["pad_bg"] = tag
                        if a <= paint_at < z:
                            rec["paint_bg"] = tag
                cells[(r, c)] = rec
        return cells

    def _grid_lay_cell_styles(self, first, lines, carried, source=None):
        """Lay the styles _grid_read_cell_styles read back on the cells of
        the freshly written *lines*.

        A cell whose text is exactly what it was gets every style back,
        where it was on that text, and its cell-level highlight over its
        new padding. A cell the operation CHANGED keeps only the colour it
        was drawn with, over the whole cell: its character styles
        described text that is no longer there, while a coloured cell is
        still the same cell (a dropped checkbox or a cleared cell keeps
        its colour, as the fill always promised).
        """
        b = self.body_text
        sep_at = core_tables.separator_index(lines)
        r = -1
        for i, line in enumerate(lines):
            if i == sep_at:
                continue
            r += 1
            line_no = first + i
            pipes = core_tables.pipe_positions(line)
            for c, (s, e) in enumerate(core_tables.cell_bounds(line)):
                src = source(r, c) if source is not None else (r, c)
                rec = carried.get(src) if src is not None else None
                if rec is None:
                    continue
                same = line[s:e] == rec["value"]
                wash = rec["pad_bg"] if same else rec["paint_bg"]
                if wash and c + 1 < len(pipes):
                    b.tag_add(wash,
                              f"{line_no}.{self._tk_col(line, pipes[c] + 1)}",
                              f"{line_no}.{self._tk_col(line, pipes[c + 1])}")
                if not same:
                    continue
                for tag, a, z in rec["runs"]:
                    b.tag_add(tag,
                              f"{line_no}.{self._tk_col(line, s + a)}",
                              f"{line_no}.{self._tk_col(line, s + z)}")

    def _dissolve_orphan_markers(self, rows):
        _spans, covered = core_tables.merge_map(rows)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                if (value in (core_tables.MERGE_LEFT, core_tables.MERGE_UP)
                        and (r, c) not in covered):
                    rows[r][c] = ""
        return rows

    @_undo_atom
    def _grid_insert_row(self, info, at):
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, ncols = context
        rows, _aligns, _sep, sep_at = self._grid_block_parts(first, nrows)
        data_off = [i for i in range(nrows) if i != sep_at]
        blank = core_tables.blank_table(1, ncols)[0]
        if at >= len(data_off):
            self.body_text.insert(f"{first + nrows - 1}.end", "\n" + blank)
        else:
            # *at* is a data-row index; the separator shifts the line it
            # maps to. A new first row still goes above the separator only
            # when there is no header to keep -- above everything.
            self.body_text.insert(f"{first + data_off[at]}.0", blank + "\n")
        self._grid_after_op(first)

    @_undo_atom
    def _grid_insert_col(self, info, at):
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        for row in rows:
            row.insert(min(at, len(row)), "")
        for row_aligns in aligns:
            row_aligns.insert(min(at, len(row_aligns)),
                              core_tables.ALIGN_LEFT)
        if sep_cols is not None:
            sep_cols.insert(min(at, len(sep_cols)),
                            {"width": None, "align": None, "hidden": False})
        self._grid_replace_block(
            first, nrows, rows, aligns, sep_cols,
            source=lambda r, c: ((r, c) if c < at
                                 else (r, c - 1) if c > at else None))
        self._grid_after_op(first)

    @_undo_atom
    def _grid_delete_row(self, info, r):
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        if nrows <= 1:
            self._grid_after_op(first)
            return
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        if r >= len(rows):
            self._grid_after_op(first)
            return
        del rows[r]
        del aligns[r]
        rows = self._dissolve_orphan_markers(rows)
        gone = r
        self._grid_replace_block(
            first, nrows, rows, aligns, sep_cols,
            source=lambda rr, c: (rr if rr < gone else rr + 1, c))
        self._grid_after_op(first)

    @_undo_atom
    def _grid_delete_col(self, info, c):
        """At two columns, deleting empties the chosen column instead.

        A one-column row reads as prose, not as a table -- "| just one |"
        is deliberately not a row, or quoting something between pipes would
        redraw it as a grid -- so two columns is the floor. Removing the
        table outright is its own menu entry.
        """
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        source = None
        if ncols <= 2:
            for row in rows:
                if c < len(row):
                    row[c] = ""
            rows = self._dissolve_orphan_markers(rows)
        else:
            source = (lambda r, cc: (r, cc if cc < c else cc + 1))
            spans, _covered = core_tables.merge_map(rows)
            for (ar, ac), (rs, cs) in spans.items():
                if ac <= c < ac + cs:
                    for rr in range(ar, ar + rs):
                        for cc in range(ac, ac + cs):
                            if (rr, cc) != (ar, ac) and cc < len(rows[rr]):
                                rows[rr][cc] = ""
            for row in rows:
                if c < len(row):
                    del row[c]
            for row_aligns in aligns:
                if c < len(row_aligns):
                    del row_aligns[c]
            if sep_cols is not None and c < len(sep_cols):
                del sep_cols[c]
            rows = self._dissolve_orphan_markers(rows)
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols,
                                 source=source)
        self._grid_after_op(first)

    @_undo_atom
    def _grid_set_marker(self, info, r, c, marker):
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        if r < len(rows) and c < len(rows[r]):
            rows[r][c] = marker
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols)
        self._grid_after_op(first)

    @_undo_atom
    def _grid_split(self, info, r, c):
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        spans, _covered = core_tables.merge_map(rows)
        for (ar, ac), (rs, cs) in spans.items():
            if ar <= r < ar + rs and ac <= c < ac + cs:
                for rr in range(ar, ar + rs):
                    for cc in range(ac, ac + cs):
                        if (rr, cc) != (ar, ac) and cc < len(rows[rr]):
                            rows[rr][cc] = ""
                break
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols)
        self._grid_after_op(first)

    def _grid_column_mechanics(self, info, mutate):
        """Shared body for width, hide and autofit: parts, a separator
        conjured if the table has none yet, *mutate* applied, written back."""
        first = self._grid_first_line(info)
        if first is None:
            return
        self._commit_cell_editor()
        again = self._grid_at_line(first)
        if again is not None:
            info = again
            first = self._grid_first_line(info) or first
        nrows = info["nrows"]
        self._grid_saved_view = self._capture_grid_views()
        self._teardown_table_grids()
        rows, aligns, sep_cols, sep_at = self._grid_block_parts(first, nrows)
        if sep_cols is None:
            widths = core_tables.layout_widths(rows, aligns)
            sep_cols = [{"width": width, "align": None, "hidden": False}
                        for width in widths]
        mutate(sep_cols, rows, aligns)
        # These ops change ONLY the separator's story (widths, hidden
        # flags) -- no data row's text moves. The wholesale
        # _grid_replace_block this used to go through re-formatted every
        # row, and every character style in the table died for a column
        # drag that touched none of them (field-tested: colour a cell,
        # resize a column, colour gone). Writing just the separator line
        # leaves every tag exactly where it is.
        self._grid_write_separator(first, nrows, rows, sep_cols, sep_at)
        self._grid_after_op(first)

    def _grid_write_separator(self, first, nrows, rows, sep_cols, sep_at):
        """Write the block's separator line surgically: replace it in
        place when it exists, insert one under the header when it does
        not. Tags elsewhere in the block are never touched -- an insert
        shifts them along, a same-line replace never reaches them (the
        separator itself holds only mechanics, never user styling)."""
        b = self.body_text
        while len(sep_cols) < len(core_tables.column_widths(rows)):
            sep_cols.append({"width": None, "align": None,
                             "hidden": False})
        sep_line = core_tables.CELL + core_tables.CELL.join(
            " " + cell + " "
            for cell in core_tables.make_separator(sep_cols)
        ) + core_tables.CELL
        table_align = self._grid_table_align_of(first)
        if sep_at is not None:
            line_no = first + sep_at
            b.delete(f"{line_no}.0", f"{line_no}.end")
            b.insert(f"{line_no}.0", sep_line)
        else:
            line_no = first + 1
            b.insert(f"{first}.end", "\n" + sep_line)
        if table_align in ("center", "right"):
            b.tag_add(f"align_{table_align}",
                      f"{line_no}.0", f"{line_no}.end")

    @_undo_atom
    def _grid_set_col_width(self, info, c, width):
        def mutate(sep_cols, rows, aligns):
            if c < len(sep_cols):
                # Floor 4, not 1: parse_separator reads a <=3-char cell as
                # markdown's conventional "no width opinion", so an
                # authored 2-3 wrote "---" and came straight back as
                # unclamped — the narrowest a hand-set column can be is
                # the narrowest width that still round-trips as authored.
                sep_cols[c]["width"] = max(4, int(width))
                sep_cols[c]["hidden"] = False
        self._grid_column_mechanics(info, mutate)

    @_undo_atom
    def _grid_autofit_col(self, info, c):
        def mutate(sep_cols, rows, aligns):
            widths = core_tables.layout_widths(rows, aligns)
            if c < len(sep_cols) and c < len(widths):
                sep_cols[c]["width"] = widths[c]
                sep_cols[c]["hidden"] = False
        self._grid_column_mechanics(info, mutate)

    @_undo_atom
    def _grid_autofit_cols(self, info, c0, c1):
        """Autofit every column a selection touches, in ONE pass -- the
        per-column call exists on the single-cell menu, and running it
        once per selected column would tear the grid down that many
        times for one gesture."""
        def mutate(sep_cols, rows, aligns):
            widths = core_tables.layout_widths(rows, aligns)
            for c in range(c0, min(c1 + 1, len(sep_cols))):
                if c < len(widths):
                    sep_cols[c]["width"] = widths[c]
                    sep_cols[c]["hidden"] = False
        self._grid_column_mechanics(info, mutate)

    @_undo_atom
    def _grid_hide_col(self, info, c, hidden=True):
        def mutate(sep_cols, rows, aligns):
            if c < len(sep_cols):
                sep_cols[c]["hidden"] = hidden
        self._grid_column_mechanics(info, mutate)

    @_undo_atom
    def _grid_hide_span(self, info, c0, c1):
        def mutate(sep_cols, rows, aligns):
            for c in range(c0, min(c1 + 1, len(sep_cols))):
                sep_cols[c]["hidden"] = True
        self._grid_column_mechanics(info, mutate)

    @_undo_atom
    def _grid_append_cols(self, info, c0, c1):
        """The selected columns joined again to the table's right edge --
        text and all, exactly as written, empty cells staying empty."""
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        # The copies carry their originals' styles: "text and all".
        old_len = [len(row) for row in rows]

        def source(r, c):
            if c < old_len[r]:
                return (r, c)
            k = c - old_len[r]
            return (r, c0 + k) if k <= c1 - c0 else None

        for row in rows:
            copied = [row[c] if c < len(row) else ""
                      for c in range(c0, c1 + 1)]
            # A merge reaching in from the LEFT of the copied span points
            # at a cell that did not travel; it lands as an empty cell.
            if copied and copied[0] == core_tables.MERGE_LEFT:
                copied[0] = ""
            row.extend(copied)
        for row_aligns in aligns:
            row_aligns.extend([row_aligns[c] if c < len(row_aligns)
                               else core_tables.ALIGN_LEFT
                               for c in range(c0, c1 + 1)])
        if sep_cols is not None:
            sep_cols.extend(dict(sep_cols[c]) if c < len(sep_cols)
                            else {"width": None, "align": None,
                                  "hidden": False}
                            for c in range(c0, c1 + 1))
        rows = self._dissolve_orphan_markers(rows)
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols,
                                 source=source)
        self._grid_after_op(first)

    @_undo_atom
    def _grid_append_rows(self, info, r0, r1):
        """The selected rows joined again to the table's bottom edge --
        the vertical twin of copying columns to the end. A merge
        reaching DOWN into the copied span from above points at a row
        that did not travel; it lands as an empty cell."""
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        copied_rows, copied_aligns = [], []
        for r in range(r0, min(r1 + 1, len(rows))):
            copied_rows.append(list(rows[r]))
            copied_aligns.append(list(aligns[r]) if r < len(aligns)
                                 else [core_tables.ALIGN_LEFT] * len(rows[r]))
        if copied_rows:
            copied_rows[0] = ["" if v == core_tables.MERGE_UP else v
                              for v in copied_rows[0]]
        n_old = len(rows)
        rows.extend(copied_rows)
        aligns.extend(copied_aligns)
        rows = self._dissolve_orphan_markers(rows)
        # The copies carry their originals' styles, as the columns' do.
        self._grid_replace_block(
            first, nrows, rows, aligns, sep_cols,
            source=lambda r, c: (r, c) if r < n_old else (r0 + r - n_old, c))
        self._grid_after_op(first)

    @_undo_atom
    def _grid_unhide_all(self, info):
        def mutate(sep_cols, rows, aligns):
            for column in sep_cols:
                column["hidden"] = False
        self._grid_column_mechanics(info, mutate)

    def _grid_double(self, info, event):
        """A double-click on a rule autofits its column. On a checkbox
        cell it toggles AGAIN: Tk turns the second of two fast clicks
        into a double-click instead of a plain one, and without this a
        quick tick-untick only ticked."""
        canvas = info["canvas"]
        boundary = self._grid_boundary_at(info, canvas.canvasx(event.x))
        if boundary is not None:
            self._grid_resizing = None
            self._grid_autofit_col(info, boundary)
            return "break"
        hit = self._grid_cell_at_xy(info, canvas.canvasx(event.x),
                                    canvas.canvasy(event.y))
        if hit is not None and self._grid_toggle_checkbox(info, *hit):
            self._grid_pressed = None
            return "break"
        return None

    def _grid_motion(self, info, event):
        """The cursor telegraphs a grabbable rule -- vertical or
        horizontal."""
        canvas = info["canvas"]
        near = self._grid_boundary_at(info, canvas.canvasx(event.x))
        near_row = (None if near is not None
                    else self._grid_row_boundary_at(
                        info, canvas.canvasy(event.y)))
        try:
            canvas.configure(cursor=(
                "sb_h_double_arrow" if near is not None
                else "sb_v_double_arrow" if near_row is not None
                else "arrow"))
        except tk.TclError:
            pass

    _TABLE_ALIGN_TAGS = ("align_center", "align_right")

    @_undo_atom
    def _grid_add_line_above(self, info):
        """A blank line above the table -- the menu twin of pressing
        Enter under a leading table, working for any table and needing
        no gesture knowledge at all."""
        first = self._grid_first_line(info)
        if first is None:
            return
        self._commit_cell_editor()
        again = self._grid_at_line(first)
        if again is not None:
            first = self._grid_first_line(again) or first
        # Like the Enter gesture: no view snapshot -- the insert lands at
        # the note's top, the Text keeps the view on its content, and a
        # restore against estimated grid heights measurably yanks it.
        self._teardown_table_grids()
        self.body_text.insert(f"{first}.0", "\n")
        self.body_text.mark_set("insert", f"{first}.0")
        self._resync_list_tags()
        self._render_table_grids()
        self._schedule_autosave()

    @_undo_atom
    def _grid_set_table_align(self, info, align):
        """The whole table sits left, centred or right on the page.

        The block's lines carry an ordinary paragraph-alignment tag, which
        is what positions the embedded window -- and what the paragraphs
        store already saves and reloads. Deliberate, so it survives; the
        PASTE path scrubs the same tags, so a table copied from a centred
        source still lands flush left.
        """
        first = self._grid_first_line(info)
        if first is None:
            return
        for n in range(first, first + info["nrows"]):
            for stray in self._TABLE_ALIGN_TAGS:
                self.body_text.tag_remove(stray, f"{n}.0", f"{n}.end")
            if align in ("center", "right"):
                self.body_text.tag_add(f"align_{align}",
                                       f"{n}.0", f"{n}.end")
        self._schedule_autosave()

    def _grid_table_align_of(self, first):
        """Which position the block's window line carries.

        Read off the line's LAST character: the first may be the embedded
        window, whose character arrives untagged on every rebuild.
        """
        for tag in self.body_text.tag_names(f"{first}.end-1c"):
            if tag == "align_center":
                return "center"
            if tag == "align_right":
                return "right"
        return "left"

    @_undo_atom
    def _grid_add_caption(self, info):
        """A system-managed caption under the table: a centred, numbered
        label line plus a source line -- ordinary body text after that,
        editable like anything else. Exists so nobody has to hand-build
        a caption above or below a table and fight its alignment (the
        field request: "the system should insert an editable label")."""
        first = self._grid_first_line(info)
        if first is None:
            return
        below = first + info["nrows"] - 1
        b = self.body_text
        # Count only caption-shaped lines ("Table 3:"), not any prose that
        # happens to start with the word -- and keep counting the "Tab. N:"
        # captions inserted before the labels went English, so numbering in
        # an older note carries on instead of restarting at 1.
        n = 1 + sum(1 for ln in b.get("1.0", "end-1c").split("\n")
                    if re.match(r"(?:Table|Tab\.) \d+:", ln.strip()))
        caption_text = f"Table {n}: description"
        b.insert(f"{below}.end", "\n" + caption_text + "\nSource: ")
        cap_line = below + 1
        # SCRUB, then dress: text inserted at the table's last line can
        # inherit whatever styling that line's edge happens to carry
        # (field-tested: the caption arrived wearing the table's cell
        # highlight, full-width bars included). The caption starts from
        # zero, always.
        for tag in b.tag_names():
            if (tag.startswith("highlight_") or tag.startswith("text_color_")
                    or tag in ("bold", "italic", "bold_italic",
                               "underline", "strike")
                    or tag.startswith("align_")):
                b.tag_remove(tag, f"{cap_line}.0", f"{cap_line + 2}.0")
        # Both lines follow the TABLE's own place on the page -- a left
        # table gets a left caption, a centred one a centred pair
        # (field request: the label and the source line must never sit
        # at two different alignments).
        place = self._grid_table_align_of(first)
        if place in ("center", "right"):
            b.tag_add(f"align_{place}", f"{cap_line}.0", f"{cap_line}.end")
            b.tag_add(f"align_{place}",
                      f"{cap_line + 1}.0", f"{cap_line + 1}.end")
        # The placeholder comes selected, so typing replaces it at once.
        start = f"{cap_line}.{len(caption_text) - len('description')}"
        b.tag_remove("sel", "1.0", "end")
        b.tag_add("sel", start, f"{cap_line}.end")
        b.mark_set("insert", f"{cap_line}.end")
        b.focus_set()
        self._resync_list_tags()
        self._schedule_autosave()

    @_undo_atom
    def _grid_delete_table(self, info):
        first = self._grid_first_line(info)
        if first is None:
            return
        nrows = info["nrows"]
        self._commit_cell_editor()
        # Capture BEFORE teardown+delete, like every other grid op: the
        # deletion shifts body_text's scroll on the spot, and without this
        # snapshot the render below faithfully pins the already-jumped
        # view — deleting a table yanked the page.
        self._grid_saved_view = self._capture_grid_views()
        self._teardown_table_grids()
        self.body_text.delete(f"{first}.0", f"{first + nrows - 1}.end +1c")
        self._resync_list_tags()
        self._render_table_grids()
        self._schedule_autosave()

    def _grid_selection_matrix(self, sel):
        info = sel["info"]
        r0, c0, r1, c1 = sel["box"]
        first = self._grid_first_line(info)
        if first is None:
            return None
        # DATA rows: reading raw text rows shifted every copy one row up
        # in a table with a separator -- the user copied what they saw,
        # and got the line above it.
        rows, _aligns, _sep, _at = self._grid_block_parts(
            first, info["nrows"])
        return [[rows[r][c] if r < len(rows) and c < len(rows[r]) else ""
                 for c in range(c0, c1 + 1)]
                for r in range(r0, r1 + 1)]

    def _grid_copy_selection(self, sel):
        """Cells leave three ways at once: tab-separated text (what a
        spreadsheet reads), an HTML table (what Word and mail clients
        read -- pasted outside the app, the cells used to arrive as one
        line of raw tabs), and an internal note of the copied columns'
        set widths, so pasting the table back into a note rebuilds it
        at the SAME widths instead of shrinking to the default."""
        matrix = self._grid_selection_matrix(sel)
        if matrix is None:
            return
        self._grid_cell_clip = [list(row) for row in matrix]
        tsv = "\n".join("\t".join(row) for row in matrix)
        self._grid_cell_clip_text = tsv
        self._grid_cell_clip_widths = None
        info, (r0, c0, r1, c1) = sel["info"], sel["box"]
        first = self._grid_first_line(info)
        if first is not None:
            _rows, _aligns, sep_cols, _sep_at = self._grid_block_parts(
                first, info["nrows"])
            if sep_cols is not None:
                self._grid_cell_clip_widths = [
                    dict(sep_cols[c]) if c < len(sep_cols)
                    else {"width": None, "align": None, "hidden": False}
                    for c in range(c0, c1 + 1)]
            # The table's place on the page travels with the cells
            # too, so a duplicated centred table comes back centred.
            self._grid_cell_clip_place = self._grid_table_align_of(first)
        # The HTML mirror of the copy follows the file export's rules:
        # the table's first row leaves as <th>, merges leave as real
        # colspan/rowspan cells instead of literal markers, hidden
        # columns stay hidden, and a checkbox leaves as its glyph. The
        # TSV keeps every cell verbatim -- it is what a spreadsheet
        # reads AND what pasting back into the app rebuilds from, so
        # fidelity lives there.
        m_spans, m_covered = core_tables.merge_map(matrix)
        hidden = {i for i, col in enumerate(self._grid_cell_clip_widths or [])
                  if col.get("hidden")}
        parts = []
        for ri, mrow in enumerate(matrix):
            cells = []
            for ci, v in enumerate(mrow):
                if (ri, ci) in m_covered or ci in hidden:
                    continue
                rs, cs = m_spans.get((ri, ci), (1, 1))
                cs -= len([h for h in hidden if ci < h < ci + cs])
                attr = ((f' colspan="{cs}"' if cs > 1 else "")
                        + (f' rowspan="{rs}"' if rs > 1 else ""))
                state = core_tables.checkbox_state(v)
                if state is not None:
                    inner = "☑" if state else "☐"
                else:
                    inner = escape(v).replace(
                        escape(core_tables.LINE_BREAK), "<br>")
                tag = "th" if r0 + ri == 0 else "td"
                # Without inline borders Word paints nothing: the pasted
                # table was a selectable phantom (round-8 field report).
                # A checkbox rides centred, the way the app draws it.
                css = "border:1px solid #999;padding:4px 10px;"
                if state is not None:
                    css = "text-align:center;" + css
                cells.append(f'<{tag}{attr} style="{css}">{inner}</{tag}>')
            parts.append("<tr>" + "".join(cells) + "</tr>")
        html_rows = "".join(parts)
        if not clipboard.write(
                tsv, html=('<table style="border-collapse:collapse;">'
                           f"{html_rows}</table>")):
            # Off Windows (the CI runners included) the CF_HTML writer
            # does nothing at all -- the plain text still has to land.
            try:
                self.clipboard_clear()
                self.clipboard_append(tsv)
            except tk.TclError:
                pass

    @_undo_atom
    def _grid_fill_selection(self, sel, value, align=None):
        info = sel["info"]
        r0, c0, r1, c1 = sel["box"]
        # The rewrite keeps every other cell exactly as it was and a
        # filled cell's colour -- a CELL-level highlight describes the
        # cell, not the text (see _grid_lay_cell_styles).
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        for r in range(r0, min(r1 + 1, len(rows))):
            for c in range(c0, min(c1 + 1, len(rows[r]))):
                if rows[r][c] not in (core_tables.MERGE_LEFT,
                                      core_tables.MERGE_UP):
                    rows[r][c] = value
                    if align is not None and c < len(aligns[r]):
                        aligns[r][c] = align
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols)
        self._grid_after_op(first)

    @_undo_atom
    def _grid_toggle_checkbox(self, info, r, c):
        """One click on a checkbox cell flips it. The colour spans on the
        marker characters are re-laid after the write, so a coloured box
        keeps its colour through every toggle."""
        cell = info["cells"].get((r, c))
        if cell is None:
            return False
        state = core_tables.checkbox_state(cell["value"])
        if state is None:
            return False
        line_no = self._grid_line_of_row(info, r)
        if line_no is None:
            return False
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        styles = self._cell_value_styles(line_no, line, c)
        new_value = (core_tables.CHECKBOX_EMPTY if state
                     else core_tables.CHECKBOX_DONE)
        self._write_cell(info, r, c, new_value)
        cell["value"] = new_value
        # Same length either way, so the styles land where they were.
        self._apply_styles_to_cell(info, r, c, new_value,
                                   styles[:len(new_value)])
        self._grid_redraw_cell_text(info, r, c)
        self._schedule_autosave()
        return True

    def _grid_checkmark_popup(self, info, box, x_root, y_root):
        """The checkbox palette: an UNCHECKED box lands in the cell(s),
        already wearing the picked colour -- ready to be ticked with a
        click once its condition is met. Same swatches ordinary text
        offers, plus the theme's own ink for a plain one."""
        self._dismiss_mini_popup()
        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])
        outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        grid_frame = tk.Frame(outer, bg=self.colors["card"])
        grid_frame.pack(padx=10, pady=(8, 0))
        anchor_line = self._grid_first_line(info)

        def choose(color):
            self._dismiss_mini_popup()
            # Surgical writes, NOT the wholesale fill: the fill's block
            # rewrite expelled the caret to the line under the table
            # (the caret guard walks it out of rebuilt table lines) and
            # the view scrolled after it -- "the cursor lands outside
            # the table and the scroll jumps". An emoji dropped into a
            # cell never moved anything because it goes through
            # surgical paths; the checkbox now does the same.
            fresh = (self._grid_at_line(anchor_line)
                     if anchor_line is not None else None)
            if fresh is None:
                return
            # One palette gesture = one undo unit, however many cells it
            # dresses (a closure cannot wear the @_undo_atom decorator).
            self._undo_atom_begin()
            try:
                r0, c0, r1, c1 = box
                for r in range(r0, r1 + 1):
                    for c in range(c0, c1 + 1):
                        cell = fresh["cells"].get((r, c))
                        if cell is None:
                            continue
                        self._write_cell(fresh, r, c,
                                         core_tables.CHECKBOX_EMPTY)
                        cell["value"] = core_tables.CHECKBOX_EMPTY
                        self._grid_redraw_cell_text(fresh, r, c)
                # No forced centring: it went through the alignment op's
                # full teardown-and-rebuild and the whole table visibly
                # flickered for one dropped checkbox. The box sits with
                # the cell's own alignment, redrawn in place -- same
                # quiet path a toggle uses.
                if color:
                    self._grid_apply_style(fresh, box, "text_color", color)
            finally:
                self._undo_atom_end()
            self._schedule_autosave()

        for i, hex_color in enumerate(PRESET_NOTE_COLORS):
            swatch = tk.Button(
                grid_frame, bg=hex_color, activebackground=hex_color,
                width=3, height=1, relief="flat", cursor="hand2",
                command=lambda h=hex_color: choose(h))
            swatch.grid(row=i // 5, column=i % 5, padx=4, pady=4)
        plain = tk.Button(
            outer, text="Theme color", relief="flat", cursor="hand2",
            bg=self.colors["card"], fg=self.colors["text"],
            command=lambda: choose(None))
        plain.pack(pady=(4, 8))
        popup.update_idletasks()
        popup.geometry(f"+{x_root}+{y_root}")
        popup.bind("<FocusOut>",
                   lambda _e: (None if getattr(self, "_hiding_popups", False)
                               else self._dismiss_mini_popup()))
        popup.focus_set()

    @_undo_atom
    def _grid_merge_selection(self, sel):
        """The selected rectangle becomes one cell, anchored top-left.

        Merges it touches are dissolved first -- the selection already grew
        to swallow them whole, so nothing is half-merged afterwards.
        """
        info = sel["info"]
        r0, c0, r1, c1 = sel["box"]
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        rows, aligns, sep_cols, _sep_at = self._grid_block_parts(first, nrows)
        spans, _covered = core_tables.merge_map(rows)
        for (ar, ac), (rs, cs) in spans.items():
            if ar <= r1 and ar + rs - 1 >= r0 and ac <= c1 and ac + cs - 1 >= c0:
                for rr in range(ar, ar + rs):
                    for cc in range(ac, ac + cs):
                        if (rr, cc) != (ar, ac) and cc < len(rows[rr]):
                            rows[rr][cc] = ""
        # Nothing the merge swallows is thrown away: every cell's text
        # moves into the merged cell, joined in reading order. Merging "A"
        # with an empty neighbour used to keep whichever cell was the
        # anchor -- and lose the text when the anchor was the empty one.
        pieces = []
        for r in range(r0, min(r1 + 1, len(rows))):
            for c in range(c0, min(c1 + 1, len(rows[r]))):
                value = rows[r][c]
                if value and value not in (core_tables.MERGE_LEFT,
                                           core_tables.MERGE_UP):
                    pieces.append(value)
        rows[r0][c0] = " ".join(pieces)
        for r in range(r0, min(r1 + 1, len(rows))):
            for c in range(c0, min(c1 + 1, len(rows[r]))):
                if (r, c) == (r0, c0):
                    continue
                rows[r][c] = (core_tables.MERGE_LEFT if r == r0
                              else (core_tables.MERGE_UP if c == c0
                                    else core_tables.MERGE_LEFT))
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols)
        self._grid_after_op(first)

    @_undo_atom
    def _grid_paste_cells(self, info, r, c):
        """Copied cells land as a block starting at the clicked cell,
        growing the table downward when they need more rows, and
        rightward when they need more columns."""
        matrix = getattr(self, "_grid_cell_clip", None)
        try:
            raw = self.clipboard_get()
        except tk.TclError:
            raw = None
        # The system clipboard is the ground truth. The remembered matrix is
        # only trusted while it still MATCHES the clipboard -- someone who
        # copied something newer meant the newer thing, and the remembered
        # matrix used to shadow it.
        if matrix is not None and raw is not None:
            remembered = "\n".join("\t".join(row) for row in matrix)
            if raw != remembered:
                matrix = None
        if not matrix:
            # Cells copied from a browser: the plain text stacks every
            # cell on its own line ("A\nB" for two side-by-side cells),
            # but the HTML still knows the true rows and columns. Read
            # the shape from there, through the same parser a whole-table
            # paste already trusts.
            html = clipboard.read_html()
            if html and "<table" in html.lower():
                try:
                    html_text, _spans, _paras = html_to_note(html)
                    blocks = core_tables.find_blocks(html_text)
                    if blocks:
                        lines = html_text.split("\n")
                        block = lines[blocks[0][0]:blocks[0][1] + 1]
                        sep_at = core_tables.separator_index(block)
                        matrix = [
                            ["" if value in (core_tables.MERGE_LEFT,
                                             core_tables.MERGE_UP)
                             else value
                             for value in core_tables.split_row(line)]
                            for i, line in enumerate(block) if i != sep_at]
                    # The plain clipboard stays the authority on
                    # FRESHNESS: the HTML only supplies the shape when
                    # its cells are the same ones the plain text holds --
                    # i.e. both came from the same copy. A newer,
                    # unrelated plain copy wins over stale HTML.
                    if matrix is not None and raw is not None:
                        html_cells = [v.strip() for row in matrix
                                      for v in row if v.strip()]
                        raw_cells = [t.strip() for line in raw.split("\n")
                                     for t in line.split("\t")
                                     if t.strip()]
                        if html_cells != raw_cells:
                            matrix = None
                except Exception:
                    matrix = None
        if not matrix and raw:
            matrix = [line.split("\t") for line in raw.split("\n") if line]
        if not matrix:
            return
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, ncols = context
        rows, aligns, sep_cols, sep_at = self._grid_block_parts(first, nrows)
        # Columns grow the way rows always have: four columns copied from a
        # spreadsheet into a two-column table used to lose the last two
        # without a word. Tables carry no column cap (a pasted TSV table,
        # an inserted or appended column never had one), so nothing here
        # is clipped; the separator gains its columns in the rewrite.
        width = max([ncols] + [c + len(line) for line in matrix])
        for row in rows:
            row.extend([""] * (width - len(row)))
        while r + len(matrix) > len(rows):
            rows.append([""] * width)
            aligns.append([core_tables.ALIGN_LEFT] * width)
        for dr, source_row in enumerate(matrix):
            for dc, value in enumerate(source_row):
                if c + dc < len(rows[r + dr]):
                    rows[r + dr][c + dc] = value.replace(
                        core_tables.CELL, "/").strip()
                    if c + dc < len(aligns[r + dr]):
                        aligns[r + dr][c + dc] = core_tables.ALIGN_LEFT
        # The block may have grown; rewrite against its original height and
        # let format_table emit the extra rows, the separator restored
        # after the header.
        self._grid_replace_block(first, nrows, rows, aligns, sep_cols)
        self._grid_after_op(first)

    def _grid_copy_cell(self, info, r, c):
        cell = info["cells"].get((r, c))
        if cell is None:
            return
        # Remembered exactly like a multi-cell copy: pasting cells used to
        # prefer whatever matrix an OLDER copy had remembered, so a fresh
        # single-cell copy pasted stale content.
        self._grid_cell_clip = [[cell["value"]]]
        try:
            self.clipboard_clear()
            self.clipboard_append(cell["value"])
        except tk.TclError:
            pass

    def _grow_cell_editor(self, win, canvas):
        """The editor widens over its neighbours as its content grows.

        A spreadsheet does exactly this: the cell itself resizes on commit,
        but while typing, the overlay simply spreads -- hiding the overflow
        until click-away read as the emoji not arriving at all.
        """
        self._schedule_autosave()
        editor = getattr(self, "_cell_editor", None)
        if editor is None:
            return
        header_font, cell_font = self._grid_fonts()
        font = header_font if editor["r"] == 0 else cell_font
        try:
            content = editor["entry"].get("1.0", "end-1c")
            # Typing an emoji gets its face live, per character -- the
            # whole-box font switch went with the Entry.
            self._editor_retag_emoji(editor["entry"])
            emoji_font = self._measuring_font(
                ("Segoe UI Emoji", self.editor_font_size))
            needed = 24 + max(
                (max(font.measure(seg), emoji_font.measure(seg))
                 if any(self._char_is_emoji(ch) for ch in seg)
                 else font.measure(seg)
                 for seg in content.split("\n")), default=0)
            if needed > int(float(canvas.itemcget(win, "width"))):
                canvas.itemconfigure(win, width=needed)
            self._editor_fit_window()
        except tk.TclError:
            pass

    def _editor_paste(self, info):
        """Ctrl+V in a cell: a copied block of cells spreads from here.

        Only when the clipboard actually holds a block -- several cells, or
        the remembered matrix -- so pasting a plain word into a cell still
        behaves like typing it.
        """
        editor = getattr(self, "_cell_editor", None)
        if editor is None:
            return None
        try:
            raw = self.clipboard_get()
        except tk.TclError:
            raw = None
        remembered = getattr(self, "_grid_cell_clip", None)
        block = ("\t" in (raw or "") or "\n" in (raw or "").strip()
                 or (remembered is not None and raw is not None
                     and raw == "\n".join("\t".join(r) for r in remembered)))
        if not block:
            return None
        r, c = editor["r"], editor["c"]
        anchor_line = self._grid_first_line(info)
        self._commit_cell_editor()
        fresh = (self._grid_at_line(anchor_line)
                 if anchor_line is not None else None)
        if fresh is not None:
            self._grid_paste_cells(fresh, r, c)
        return "break"

    def _editor_context_menu(self, info, event):
        editor = getattr(self, "_cell_editor", None)
        if editor is None:
            return "break"
        r, c = editor["r"], editor["c"]
        anchor_line = self._grid_first_line(info)
        self._commit_cell_editor()
        fresh = (self._grid_at_line(anchor_line)
                 if anchor_line is not None else None)
        if fresh is not None:
            self._grid_menu(fresh, event, at=(r, c))
        return "break"

    @_undo_atom
    def _grid_set_alignment(self, info, box, align):
        """Alignment is the cell's padding, so setting it edits ONLY the
        padding -- through the same space-level ops the block aligner
        uses, because Tk carries a tag along with the text around it. The
        old wholesale-rewrite path silently dropped the bold (and every
        other character style) from the very cells being aligned."""
        r0, c0, r1, c1 = box
        context = self._grid_op_context(info)
        if not context:
            return
        first, nrows, _ncols = context
        b = self.body_text
        lines = [b.get(f"{n}.0", f"{n}.end")
                 for n in range(first, first + nrows)]
        aligns = [core_tables.cell_alignments(line) for line in lines]
        rows = [core_tables.split_row(line) for line in lines]
        # The grid numbers its rows with the separator skipped; the block
        # lines include it.
        sep_at = core_tables.separator_index(lines)
        for r in range(r0, r1 + 1):
            off = r if sep_at is None or r < sep_at else r + 1
            if off >= len(lines):
                continue
            for c in range(c0, c1 + 1):
                if (c < len(rows[off])
                        and rows[off][c] not in (core_tables.MERGE_LEFT,
                                                 core_tables.MERGE_UP)
                        and c < len(aligns[off])):
                    aligns[off][c] = align
        widths = core_tables.layout_widths(rows, aligns)
        for offset, line in enumerate(lines):
            row = first + offset
            base = self._col_base(row)
            for at, delta in core_tables.pad_ops(
                    line, widths,
                    aligns[offset] if offset < len(aligns) else None):
                t_at = base + self._tk_col(line, at)
                if delta > 0:
                    b.insert(f"{row}.{t_at}", " " * delta)
                else:
                    b.delete(f"{row}.{t_at}", f"{row}.{t_at + (-delta)}")
        self._grid_after_op(first)

    def _highlight_swatch_column(self, popup, choose):
        """The one way a highlight palette looks anywhere in the app:
        full-width swatches parted by true one-pixel hairlines in the
        theme's rule colour, with Clear underneath. The table popup's
        pattern, shared so the toolbar and the context menu cannot
        drift away from it again."""
        outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        # The same header the text-colour popup beside it has carried all
        # along. It lived at that popup's own call site, inside the branch
        # `kind == "highlight"` never takes, so the highlight palette drew
        # none -- on either route here. Putting it in the shared function
        # rather than at a call site is what gives the toolbar popup and
        # the table cell's popup the same one.
        header = tk.Label(outer, text="Pick a highlight color",
                          font=("Segoe UI", 10, "bold"),
                          bg=self.colors["card"], fg=self.colors["text"])
        header.pack(padx=15, pady=(12, 8))
        # The hairline is the COLUMN's background peeking through the
        # one-pixel gaps between swatches: the theme's accent softened
        # toward the card, so a purple theme parts them with a paler
        # purple, dark or light alike.
        column = tk.Frame(outer, bg=self._blend_hex(
            self.colors["accent"], self.colors["card"], 0.35))
        column.pack(padx=8, pady=8)
        for i, hex_color in enumerate(HIGHLIGHT_COLOR_PALETTE):
            swatch = tk.Button(
                column, bg=hex_color, activebackground=hex_color,
                width=14, height=1, relief="flat", bd=0, cursor="hand2",
                command=lambda h=hex_color: choose(h))
            swatch.pack(pady=(0 if i == 0 else 1, 0))
        clear = tk.Button(
            outer, text="Clear highlight", relief="flat", cursor="hand2",
            bg=self.colors["card"], fg=self.colors["text"],
            command=lambda: choose(None))
        clear.pack(pady=(0, 8))
        return outer

    def _grid_highlight_popup(self, info, box, x_root, y_root):
        """The highlight palette as the app's own themed popup -- a
        tk.Menu cannot draw the hairlines, its separators are the OS's."""
        self._dismiss_mini_popup()
        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])

        def choose(color):
            self._dismiss_mini_popup()
            self._grid_apply_style(info, box, "highlight", color)

        self._highlight_swatch_column(popup, choose)
        popup.update_idletasks()
        popup.geometry(f"+{x_root}+{y_root}")
        popup.bind("<FocusOut>",
                   lambda _e: (None if getattr(self, "_hiding_popups", False)
                               else self._dismiss_mini_popup()))
        popup.focus_set()

    def _grid_align_context(self):
        """The alignment of the cell the user is in -- the open editor's,
        or the selection's anchor -- or None outside any table."""
        editor = getattr(self, "_cell_editor", None)
        sel = getattr(self, "_grid_sel", None)
        if editor is not None:
            info, r, c = editor["info"], editor["r"], editor["c"]
        elif sel is not None:
            info, r, c = sel["info"], sel["box"][0], sel["box"][1]
        else:
            return None
        line_no = self._grid_line_of_row(info, r)
        if line_no is None:
            return None
        aligns = core_tables.cell_alignments(
            self.body_text.get(f"{line_no}.0", f"{line_no}.end"))
        return aligns[c] if c < len(aligns) else core_tables.ALIGN_LEFT

    def _grid_cell_text_range(self, info, r, c, pad_ok=False, full=False):
        """The body-text indices of one cell's content, or None when the
        cell is empty -- padding never carries formatting, EXCEPT that a
        highlight (pad_ok) may sit on an empty cell's padding: it is the
        only style with something to show on nothing, and text typed into
        the cell later lands inside the tagged region and inherits it.

        ``full`` widens the range to the whole pipe-to-pipe region even
        when the cell HOLDS text. A cell-level highlight lives there so
        that everything later inserted inside the cell -- typed text on
        commit, the pad spaces a re-align shuffles, a checkbox marker --
        lands strictly INSIDE the tagged region and inherits it. Applied
        to the text alone, the highlight died the moment a commit wrote
        new characters beside it (logically at once, visibly at the next
        rebuild -- 'drag the column and the colour is gone' in the field
        report)."""
        line_no = self._grid_line_of_row(info, r)
        first = self._grid_first_line(info)
        if line_no is None or first is None:
            return None
        base = 1 if line_no == first else 0
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        bounds = core_tables.cell_bounds(line)
        if c >= len(bounds):
            return None
        start, end = bounds[c]
        if full or start >= end:
            if not (pad_ok or full):
                return None
            pipes = core_tables.pipe_positions(line)
            if c + 1 >= len(pipes) or pipes[c] + 1 >= pipes[c + 1]:
                return None
            start, end = pipes[c] + 1, pipes[c + 1]
        return (f"{line_no}.{base + self._tk_col(line, start)}",
                f"{line_no}.{base + self._tk_col(line, end)}")

    def _grid_style_target(self):
        """Where toolbar formatting should land instead of the body: the
        selected cells, or the one open in the editor. None means the
        toolbar keeps its ordinary meaning."""
        sel = getattr(self, "_grid_sel", None)
        if (sel is not None
                and self._grid_first_line(sel["info"]) is not None):
            return sel["info"], sel["box"]
        editor = getattr(self, "_cell_editor", None)
        if editor is not None:
            return editor["info"], (editor["r"], editor["c"],
                                    editor["r"], editor["c"])
        return None

    @_undo_atom
    def _grid_apply_style(self, info, box, kind, value=None):
        """One toolbar action, over every selected cell's text.

        The toggle decision is made once across all the cells -- a mixed
        selection turns the style ON everywhere, the way the body's own
        selection behaves -- and the drawn grid repaints in place.
        """
        r0, c0, r1, c1 = box
        editor = getattr(self, "_cell_editor", None)
        if (editor is not None and editor.get("info") is info
                and (r0, c0, r1, c1) == (editor["r"], editor["c"],
                                         editor["r"], editor["c"])):
            # The cell is OPEN: style the selection inside the editor --
            # a single letter or emoji, not the whole cell -- and let the
            # commit carry it to the body.
            self._editor_apply_style(kind, value)
            return
        ranges = []
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                span = self._grid_cell_text_range(
                    info, r, c, pad_ok=(kind == "highlight"),
                    full=(kind == "highlight"))
                if span:
                    ranges.append(span)
        if not ranges:
            return
        b = self.body_text
        if kind in ("bold", "italic"):
            is_bold = all(self._selection_has_style(
                b, {"bold", "bold_italic"}, s, e) for s, e in ranges)
            is_italic = all(self._selection_has_style(
                b, {"italic", "bold_italic"}, s, e) for s, e in ranges)
            if kind == "bold":
                is_bold = not is_bold
            else:
                is_italic = not is_italic
            tag = self._font_tag_for(is_bold, is_italic)
            for s, e in ranges:
                for t in self._FONT_STYLES:
                    b.tag_remove(t, s, e)
                if tag:
                    b.tag_add(tag, s, e)
        elif kind in ("underline", "strike"):
            on = all(self._selection_has_style(b, {kind}, s, e)
                     for s, e in ranges)
            for s, e in ranges:
                if on:
                    b.tag_remove(kind, s, e)
                else:
                    b.tag_add(kind, s, e)
        else:
            for s, e in ranges:
                for tag_name in b.tag_names():
                    if tag_name.startswith(kind + "_"):
                        b.tag_remove(tag_name, s, e)
                if value:
                    tag = self._ensure_color_tag(b, kind, value)
                    b.tag_add(tag, s, e)
        self._grid_restyle(info)
        self._schedule_autosave()

    def _grid_cell_paint(self, info, r, c):
        """What the cell's text tags ask the drawing to look like."""
        paint = {"bg": None, "fg": None, "bold": False, "italic": False,
                 "underline": False, "strike": False}
        # pad_ok so an empty cell's padding-borne highlight still paints.
        span = self._grid_cell_text_range(info, r, c, pad_ok=True)
        if not span:
            return paint
        tags = set(self.body_text.tag_names(span[0]))
        for t in tags:
            if t.startswith("highlight_"):
                paint["bg"] = "#" + t[len("highlight_"):]
            elif t.startswith("text_color_"):
                paint["fg"] = "#" + t[len("text_color_"):]
        paint["bold"] = bool(tags & {"bold", "bold_italic"})
        paint["italic"] = bool(tags & {"italic", "bold_italic"})
        paint["underline"] = "underline" in tags
        paint["strike"] = "strike" in tags
        return paint

    @staticmethod
    def _blend_hex(top, base, opacity):
        """Fake transparency on a canvas that has none: *top* at *opacity*
        over *base*, channel by channel."""
        try:
            tr, tg, tb = (int(top.lstrip("#")[i:i + 2], 16)
                          for i in (0, 2, 4))
            br, bg_, bb = (int(base.lstrip("#")[i:i + 2], 16)
                           for i in (0, 2, 4))
        except (ValueError, AttributeError):
            return top
        return "#%02x%02x%02x" % tuple(
            round(t * opacity + b * (1 - opacity))
            for t, b in ((tr, br), (tg, bg_), (tb, bb)))

    def _grid_restyle(self, info):
        """Repaint every drawn cell from its text tags, in place.

        The text is redrawn as runs, so a single coloured letter shows as
        itself; the highlight stays a whole-cell wash -- a background is
        the one style the drawing paints cell-wide."""
        canvas = info["canvas"]
        for (r, c), cell in info["cells"].items():
            paint = self._grid_cell_paint(info, r, c)
            surface = (inset_surface(self.colors) if r == 0
                       else self.colors["card"])
            # The saved colour stays pure; only the DRAWING blends it
            # toward the cell's own surface, so the text stays readable
            # on either theme -- a solid palette fill buried it.
            bg = (self._blend_hex(paint["bg"], surface, 0.45)
                  if paint["bg"] else surface)
            try:
                canvas.itemconfigure(cell["rect"], fill=bg)
            except tk.TclError:
                pass
            self._grid_redraw_cell_text(info, r, c)

    def _grid_stub_menu(self, info, event, c):
        """The only menu a hidden column can offer: bring it back."""
        menu = tk.Menu(self, tearoff=0, bg=self.colors["card"],
                       fg=self.colors["text"],
                       activebackground=self.colors["accent"],
                       activeforeground="#ffffff")
        menu.add_command(label="Unhide column",
                         command=lambda: self._grid_hide_col(info, c, False))
        menu.add_command(label="Unhide all columns",
                         command=lambda: self._grid_unhide_all(info))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _grid_menu(self, info, event, at=None):
        canvas = info["canvas"]
        hit = at if at is not None else self._grid_cell_at_xy(
            info, canvas.canvasx(event.x), canvas.canvasy(event.y))
        if hit is None or hit not in info["cells"]:
            # A hidden column's sliver has no cells; without a menu of its
            # own, hiding every column would lock Unhide away for good.
            x = canvas.canvasx(event.x)
            for c in info.get("hidden_cols", ()):
                if info["col_x"][c] <= x < info["col_x"][c + 1]:
                    return self._grid_stub_menu(info, event, c)
            return "break"
        r, c = hit
        cell = info["cells"][(r, c)]
        menu = tk.Menu(self, tearoff=0, bg=self.colors["card"],
                       fg=self.colors["text"],
                       activebackground=self.colors["accent"],
                       activeforeground="#ffffff")
        sel = getattr(self, "_grid_sel", None)
        if (sel and sel["info"] is info
                and sel["box"][0] <= r <= sel["box"][2]
                and sel["box"][1] <= c <= sel["box"][3]):
            menu.add_command(label="Copy cells",
                             command=lambda: self._grid_copy_selection(sel))
            menu.add_command(label="Paste cells here",
                             command=lambda: self._grid_paste_cells(
                                 info, sel["box"][0], sel["box"][1]))
            menu.add_command(label="Insert checkboxes\u2026",
                             command=lambda xr=event.x_root,
                             yr=event.y_root: self._grid_checkmark_popup(
                                 info, sel["box"], xr, yr))
            menu.add_command(label="Clear cells",
                             command=lambda: self._grid_fill_selection(
                                 sel, ""))
            menu.add_command(label="Merge cells",
                             command=lambda: self._grid_merge_selection(sel))
            menu.add_command(
                label=("Autofit column width"
                       if sel["box"][1] == sel["box"][3]
                       else "Autofit column widths"),
                command=lambda: self._grid_autofit_cols(
                    info, sel["box"][1], sel["box"][3]))
            # Hide asks for a whole column selected top to bottom -- the
            # user can SEE what is about to disappear. Anything less and
            # the option stays away, on purpose.
            if (sel["box"][0] == 0
                    and sel["box"][2] >= info["data_rows"] - 1):
                menu.add_command(
                    label=("Hide column" if sel["box"][1] == sel["box"][3]
                           else "Hide columns"),
                    command=lambda: self._grid_hide_span(
                        info, sel["box"][1], sel["box"][3]))
                span_cols = sel["box"][3] - sel["box"][1] + 1
                menu.add_command(
                    label=("Copy column to the end" if span_cols == 1
                           else f"Copy {span_cols} columns to the end"),
                    command=lambda box=sel["box"]:
                        self._grid_append_cols(info, box[1], box[3]))
            # The vertical twin: whole ROWS selected edge to edge can be
            # duplicated downward.
            if (sel["box"][1] == 0
                    and sel["box"][3] >= info["ncols"] - 1):
                span_rows = sel["box"][2] - sel["box"][0] + 1
                menu.add_command(
                    label=("Copy row to the end" if span_rows == 1
                           else f"Copy {span_rows} rows to the end"),
                    command=lambda box=sel["box"]:
                        self._grid_append_rows(info, box[0], box[2]))
            menu.add_separator()
            menu.add_command(
                label="Highlight cells\u2026",
                command=lambda box=sel["box"], xr=event.x_root,
                               yr=event.y_root:
                    self._grid_highlight_popup(info, box, xr, yr))
            menu.add_separator()
            for label, align_value in (
                    ("Align left", core_tables.ALIGN_LEFT),
                    ("Center text", core_tables.ALIGN_CENTER),
                    ("Align right", core_tables.ALIGN_RIGHT)):
                menu.add_command(
                    label=label,
                    command=lambda a=align_value, box=sel["box"]:
                        self._grid_set_alignment(info, box, a))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
            return "break"

        def emoji_here():
            self._open_cell_editor(info, r, c, select=False)
            editor = getattr(self, "_cell_editor", None)
            if editor:
                self._show_emoji_picker(editor["entry"])

        menu.add_command(label="Copy cell",
                         command=lambda: self._grid_copy_cell(info, r, c))
        menu.add_command(label="Paste cells here",
                         command=lambda: self._grid_paste_cells(info, r, c))
        menu.add_command(label="Insert checkbox\u2026",
                         command=lambda xr=event.x_root,
                         yr=event.y_root: self._grid_checkmark_popup(
                             info, (r, c, r, c), xr, yr))
        if core_tables.checkbox_state(
                info["cells"].get((r, c), {}).get("value")) is not None:
            # A click on a checkbox toggles it, so the way into its text
            # lives here: delete the marker and type, and the cell is an
            # ordinary text cell again.
            menu.add_command(label="Edit cell as text",
                             command=lambda: self._open_cell_editor(
                                 info, r, c))
        menu.add_command(label="Insert emoji…", command=emoji_here)
        menu.add_command(label="Clear cell",
                         command=lambda: self._grid_fill_selection(
                             {"info": info, "box": (r, c, r, c)}, ""))
        menu.add_command(
            label="Highlight cell\u2026",
            command=lambda xr=event.x_root, yr=event.y_root:
                self._grid_highlight_popup(info, (r, c, r, c), xr, yr))
        menu.add_separator()
        # Grouped: the flat run had grown past fifteen entries and
        # "finding the one you need takes minutes" (field report). The
        # everyday cell actions stay on top; everything about rows,
        # columns, merging, or the table as a whole lives one hover
        # away, under the word you would look for.

        def _sub():
            m = tk.Menu(menu, tearoff=0, bg=self.colors["card"],
                        fg=self.colors["text"],
                        activebackground=self.colors["accent"],
                        activeforeground="white",
                        relief="flat", bd=0, font=("Segoe UI", 9))
            return m

        align_menu = _sub()
        for label, align_value in (
                ("Align left", core_tables.ALIGN_LEFT),
                ("Center text", core_tables.ALIGN_CENTER),
                ("Align right", core_tables.ALIGN_RIGHT)):
            align_menu.add_command(
                label=label,
                command=lambda a=align_value: self._grid_set_alignment(
                    info, (r, c, r, c), a))
        menu.add_cascade(label="Align cell", menu=align_menu)

        rows_menu = _sub()
        rows_menu.add_command(label="Insert row above",
                              command=lambda: self._grid_insert_row(info, r))
        rows_menu.add_command(
            label="Insert row below",
            command=lambda: self._grid_insert_row(info, r + 1))
        rows_menu.add_command(
            label="Delete row",
            state=("normal" if info["data_rows"] > 1 else "disabled"),
            command=lambda: self._grid_delete_row(info, r))
        menu.add_cascade(label="Rows", menu=rows_menu)

        cols_menu = _sub()
        cols_menu.add_command(label="Insert column left",
                              command=lambda: self._grid_insert_col(info, c))
        cols_menu.add_command(
            label="Insert column right",
            command=lambda: self._grid_insert_col(info, c + 1))
        cols_menu.add_command(label="Autofit column width",
                              command=lambda: self._grid_autofit_col(info, c))
        cols_menu.add_command(
            label="Unhide all columns",
            state=("normal" if info.get("hidden_cols") else "disabled"),
            command=lambda: self._grid_unhide_all(info))
        cols_menu.add_command(label="Delete column",
                              command=lambda: self._grid_delete_col(info, c))
        menu.add_cascade(label="Columns", menu=cols_menu)

        merged = cell["rs"] > 1 or cell["cs"] > 1
        merge_menu = _sub()
        merge_menu.add_command(label="Merge with cell to the left",
                               state="normal" if c > 0 else "disabled",
                               command=lambda: self._grid_set_marker(
                                   info, r, c, core_tables.MERGE_LEFT))
        merge_menu.add_command(label="Merge with cell above",
                               state="normal" if r > 0 else "disabled",
                               command=lambda: self._grid_set_marker(
                                   info, r, c, core_tables.MERGE_UP))
        merge_menu.add_command(label="Split merged cell",
                               state="normal" if merged else "disabled",
                               command=lambda: self._grid_split(info, r, c))
        menu.add_cascade(label="Merge", menu=merge_menu)

        table_menu = _sub()
        for pos_label, pos in (("Table left on page", "left"),
                               ("Center table on page", "center"),
                               ("Table right on page", "right")):
            table_menu.add_command(
                label=pos_label,
                command=lambda p=pos: self._grid_set_table_align(info, p))
        table_menu.add_separator()
        table_menu.add_command(
            label="Add caption below…",
            command=lambda: self._grid_add_caption(info))
        table_menu.add_command(
            label="Add a line above the table",
            command=lambda: self._grid_add_line_above(info))
        table_menu.add_separator()
        table_menu.add_command(
            label="Delete table",
            command=lambda: self._grid_delete_table(info))
        menu.add_cascade(label="Table", menu=table_menu)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"


    def _configure_table_tag(self, text_widget):
        """Draw table rows in a monospace face, at the editor's own size.

        Derived from the text rather than stored with the note, exactly like
        the list margins: what makes a line a table row is the pipes in it,
        and this tag is only how that is shown. Nothing about it reaches
        ``formatting``, so a table exported, shared as a code, or pasted
        into another application carries no font of its own.
        """
        available = set(tkfont.families())
        family = next((f for f in MONOSPACE_FAMILIES if f in available),
                      self.editor_font_family)
        # A table's rows sit closer together than prose wants to, because
        # each one is a single line. The extra space above and below is what
        # turns a run of bordered lines into cells with something in them.
        text_widget.tag_configure(self.TABLE_TAG,
                                  font=(family, self.editor_font_size),
                                  spacing1=4, spacing3=4)

    def _configure_paragraph_tag(self, text_widget, name):
        """Set one margin tag's options.

        Split out from _paragraph_tag so the tags can be rebuilt when the
        editor's font size changes: the margins are in pixels and the marker
        they leave room for is not.
        """
        kind, indent = self._paragraph_tags[name]
        left = indent * self.INDENT_STEP
        options = {}
        if kind:
            options["lmargin1"] = 18 + left
            options["lmargin2"] = 18 + left + self._marker_room(kind)
        else:
            options["lmargin1"] = options["lmargin2"] = left
        text_widget.tag_configure(name, **options)

    def _clear_paragraph_tags(self, text_widget, line_no):
        """Strip every margin tag from a line, whatever kind or depth."""
        for name in text_widget.tag_names(f"{line_no}.0"):
            if name.startswith("para_"):
                text_widget.tag_remove(name, f"{line_no}.0", f"{line_no}.end+1c")

    def _paragraph_indent_of(self, text_widget, line_no):
        """How deep this line is pushed.

        Read from the margin tag, with one fallback: a bullet's glyph also
        says which level it is at, so a bullet whose tag was lost -- pasted
        in from elsewhere, say -- still comes back at the right depth.
        """
        for name in text_widget.tag_names(f"{line_no}.0"):
            if name.startswith("para_"):
                # Looked up rather than parsed out of the name, which is
                # a format this does not need to know.
                return self._paragraph_tags.get(name, (None, 0))[1]
        line = text_widget.get(f"{line_no}.0", f"{line_no}.end")
        kind, marker, _ = parse_list_marker(line)
        return bullet_level_of(marker) if kind == "bullet" else 0

    def _paragraph_align_of(self, text_widget, line_no):
        """The alignment of this line: "left", "center" or "right".

        Read from the tag rather than the text, because unlike a list marker
        alignment leaves nothing behind in the body to read back.
        """
        tags = text_widget.tag_names(f"{line_no}.0")
        for align in ("center", "right"):
            if f"align_{align}" in tags:
                return align
        return "left"

    @_undo_atom
    def _set_paragraph_align(self, align):
        """Align the selected lines left, centre or right.

        Clicking the alignment a line already has puts it back to left, the
        same way clicking a list button again turns the list off -- a button
        that is already pressed should undo itself rather than do nothing.
        """
        # With cells selected, the toolbar buttons mean those cells: the
        # paragraph path would apply an alignment the table lines shed at
        # once, which read as "it snaps back to the left".
        sel = getattr(self, "_grid_sel", None)
        if (sel is not None
                and self._grid_first_line(sel["info"]) is not None):
            self._grid_set_alignment(sel["info"], sel["box"], {
                "center": core_tables.ALIGN_CENTER,
                "right": core_tables.ALIGN_RIGHT,
            }.get(align, core_tables.ALIGN_LEFT))
            return
        # With a table cell open, the toolbar buttons mean that cell --
        # reaching for the same button that aligns a paragraph is exactly
        # what someone centring a cell will try first.
        editor = getattr(self, "_cell_editor", None)
        if editor is not None:
            info, r, c = editor["info"], editor["r"], editor["c"]
            anchor_line = self._grid_first_line(info)
            self._grid_set_alignment(info, (r, c, r, c), {
                "center": core_tables.ALIGN_CENTER,
                "right": core_tables.ALIGN_RIGHT,
            }.get(align, core_tables.ALIGN_LEFT))
            fresh = (self._grid_at_line(anchor_line)
                     if anchor_line is not None else None)
            if fresh is not None and (r, c) in fresh["cells"]:
                self._open_cell_editor(fresh, r, c, select=False)
            return
        first, last = self._selected_line_range()
        if all(self._paragraph_align_of(self.body_text, n) == align
               for n in range(first, last + 1)):
            align = "left"
        for line_no in range(first, last + 1):
            for name in ("center", "right"):
                self.body_text.tag_remove(f"align_{name}",
                                          f"{line_no}.0", f"{line_no}.end+1c")
            if align != "left":
                # Includes the newline, unlike the list tags: justify applies
                # to the whole display line, and a range stopping at .end
                # leaves an empty line unaligned, so the caret jumps back to
                # the left the moment you press Enter on a centred line.
                self.body_text.tag_add(f"align_{align}",
                                       f"{line_no}.0", f"{line_no}.end+1c")
        self._refresh_list_buttons()
        self._schedule_autosave()

    def _list_kind_of(self, text_widget, line_no):
        """Which kind of list line this is, or None if it is not one.

        Decided by the marker in the text, not by the tag. The marker is the
        thing that is actually saved, and the tag is only the hanging indent
        drawn over it -- and Tk hands a tag on to text inserted beside it, so
        reading the tag once let a pasted line come back as a bullet that had
        no bullet in it.
        """
        line = text_widget.get(f"{line_no}.0", f"{line_no}.end")
        return parse_list_marker(line)[0]

    def _extract_paragraphs(self, text_widget):
        """Read the list tags back out as plain data, for saving.

        Line numbers rather than character offsets: a list applies to a whole
        line, and a line index survives being reloaded into a window of a
        different width, which is the same reason formatting uses offsets
        rather than Tk's own line.column indices.
        """
        paragraphs = []
        total = int(text_widget.index("end-1c").split(".")[0])
        for line_no in range(1, total + 1):
            kind = self._list_kind_of(text_widget, line_no)
            align = self._paragraph_align_of(text_widget, line_no)
            indent = self._paragraph_indent_of(text_widget, line_no)
            if not kind and align == "left" and not indent:
                continue            # an ordinary paragraph records nothing
            entry = {"line": line_no - 1}
            if kind:
                entry["kind"] = kind
            if indent:
                entry["indent"] = indent
            if align != "left":
                entry["align"] = align
            paragraphs.append(entry)
        return paragraphs

    def _resync_list_tags(self, line_no=None):
        """Redraw the indent tags from the markers actually in the text.

        Tk only passes a tag on to text inserted between two characters that
        both carry it, so anything typed at the *end* of an item arrives
        untagged -- and a wrap point in untagged text loses the hanging
        indent, so a long item's second line slides back under its marker.
        Re-tagging from the markers keeps the two in step.

        Defaults to the cursor's line only. Typing happens one line at a
        time, and rebuilding every line on every keystroke is exactly the
        kind of refresh work that has cost this app real responsiveness
        before (see docs/ISSUES_LOG.md). The whole-body pass is for paste,
        which is rare and can change many lines at once.
        """
        if line_no is None:
            first = 1
            last = int(self.body_text.index("end-1c").split(".")[0])
        else:
            first = last = line_no
        for n in range(first, last + 1):
            # A table row is drawn in a monospace face for the same reason
            # its pipes live in the text: the columns cannot line up
            # otherwise. Done here because it is the same question as the
            # list margins -- what does this line say it is -- asked at the
            # same moments. Removing it covers the newline as well, so a
            # row that stops being one does not pass the face on to what is
            # typed after it.
            line = self.body_text.get(f"{n}.0", f"{n}.end")
            if is_table_row(line):
                self.body_text.tag_add(self.TABLE_TAG, f"{n}.0", f"{n}.end")
                # An alignment tag on a table's line positions the embedded
                # window -- since "Center table on page" that is a feature,
                # not a stray. The accidental path (pasted centred content)
                # is scrubbed where it enters, in _apply_paragraphs. Only
                # the tag's spill over the newline is trimmed here, so a
                # line typed under the table does not inherit the position.
                for tag in ("align_center", "align_right"):
                    self.body_text.tag_remove(tag, f"{n}.end", f"{n}.end+1c")
            else:
                self.body_text.tag_remove(self.TABLE_TAG, f"{n}.0", f"{n}.end+1c")
            kind = self._list_kind_of(self.body_text, n)
            indent = self._paragraph_indent_of(self.body_text, n)
            wanted = (self._paragraph_tag(self.body_text, kind, indent)
                      if (kind or indent) else None)
            for name in self.body_text.tag_names(f"{n}.0"):
                if name.startswith("para_") and name != wanted:
                    self.body_text.tag_remove(name, f"{n}.0", f"{n}.end+1c")
            if wanted:
                self.body_text.tag_add(wanted, f"{n}.0", f"{n}.end")

    def _on_comments_paste(self, event=None):
        """Keep tables OUT of the comments box.

        Comments are drawn as plain text -- there is no grid renderer for
        them the way there is for the body -- so a pasted table only ever
        showed as raw pipe rows ("| a | b |"), never a real table. Rather
        than let that broken-looking soup in, a paste that carries table
        rows has them stripped and the prose kept, with a quiet note that
        it happened. A paste with no table rows falls through to Tk's own
        paste untouched (return None)."""
        raw = clipboard.read_text()
        if raw is None:
            try:
                raw = self.comments_text.clipboard_get()
            except tk.TclError:
                return None
        if not raw:
            return None
        lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if not any(core_tables.is_table_row(ln) for ln in lines):
            return None                      # no table -- let Tk paste it
        kept = [ln for ln in lines if not core_tables.is_table_row(ln)]
        # Collapse the blank runs a removed table leaves behind, so the
        # prose does not arrive with a gap where the grid was.
        cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip("\n")
        try:
            self.comments_text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        if cleaned:
            self.comments_text.insert("insert", cleaned)
        self._schedule_autosave()
        self._show_toast("Comments keep text only — the table wasn't added")
        return "break"

    def _on_body_paste(self, event=None):
        """Paste, keeping the source's formatting where there is any.

        Falls through to Tk's own plain-text paste when the clipboard holds
        nothing rich, when this is not Windows, or when anything at all goes
        wrong reading it -- returning None leaves the default handler to
        run, which is exactly what happened before this existed.
        """
        # With cells selected, Ctrl+V means those cells -- it used to
        # paste into the body beside the table.
        sel = getattr(self, "_grid_sel", None)
        if sel is not None:
            first = self._grid_first_line(sel["info"])
            if first is not None:
                self._grid_paste_cells(sel["info"],
                                       sel["box"][0], sel["box"][1])
                return "break"
        # Our own cell copy puts an HTML table on the clipboard for Word's
        # sake, and on Windows the rich-paste route saw it FIRST -- so
        # pasting a copied table back into a note took the generic HTML
        # road: no set widths, no placement, and the first row glued onto
        # the caret's line ("Sursa: | fff |..." in the field report). The
        # TSV route carries everything the copy knew, so our own copies go
        # there; the rich route is for content from OTHER applications.
        # Detection reads the system clipboard directly, no Tk fallback:
        # our copy always writes the plain text alongside the HTML, and
        # when the clipboard is momentarily locked the HTML is unreadable
        # too, so the paste falls through to the TSV route anyway.
        own = getattr(self, "_grid_cell_clip_text", None)
        own_copy = bool(own) and clipboard.read_text() == own
        if own_copy:
            if self._paste_tsv_as_table():
                return "break"
            # A single copied cell has no tabs: it pastes as the plain
            # text it is, never as a one-cell table the HTML would make.
        elif self._paste_formatted():
            return "break"
        if not own_copy and self._paste_tsv_as_table():
            return "break"
        if self._paste_pipe_text_on_own_lines():
            return "break"
        # Plain paste: Tk inserts the text after this returns, so the list
        # tags can only be brought back into step once that has happened.
        self._body_follow_caret = True
        self.after_idle(self._resync_list_tags)
        self.after_idle(self._render_table_grids)
        return None

    @_undo_atom
    def _paste_pipe_text_on_own_lines(self):
        """Plain text whose edge lines are table rows lands on its own
        lines, never glued into the caret's line.

        Copying half a table plus its caption as ordinary body text and
        pasting it mid-line spliced the first pipe row onto the caret's
        line -- '|   | [x] |fig2...' in the field report -- and the
        caption onto the last one. Tk's default paste is right for
        prose; pipe rows only mean something at a line start, so they
        get the newlines that keep them rows. Selection replacement is
        left to the default handler -- this path only runs caret-only.
        """
        try:
            if self.body_text.tag_ranges("sel"):
                return False
        except tk.TclError:
            return False
        raw = clipboard.read_text()
        if raw is None:
            try:
                raw = self.body_text.clipboard_get()
            except tk.TclError:
                return False
        if not raw or "\n" not in raw.strip():
            single = raw or ""
            if not core_tables.is_table_row(single.strip("\n")):
                return False
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        lines = raw.strip("\n").split("\n")
        if not (core_tables.is_table_row(lines[0])
                or core_tables.is_table_row(lines[-1])):
            return False
        b = self.body_text
        before = b.get("insert linestart", "insert")
        after = b.get("insert", "insert lineend")
        text = raw.strip("\n")
        if core_tables.is_table_row(lines[0]) and before.strip():
            text = "\n" + text
        if core_tables.is_table_row(lines[-1]) and after.strip():
            text = text + "\n"
        b.insert("insert", text)
        self._body_follow_caret = True
        self._resync_list_tags()
        self._render_table_grids()
        self._schedule_autosave()
        return True

    @_undo_atom
    def _paste_tsv_as_table(self, raw=None):
        """Tab-separated clipboard text pasted into the body becomes a
        real table.

        This is what makes duplicating a table WORK: copying cells puts
        tab-separated lines on the clipboard (what a spreadsheet reads),
        and pasting that below the table used to fall through to the
        plain-text path -- raw tabs on one line, stored <br> markers
        showing as text, "nothing happens or <br> <br> appears" in the
        field report. Same shape arrives from a spreadsheet copied as
        plain text, so both now land as a grid. Single cells (no tab)
        keep pasting as ordinary text.
        """
        if raw is None:
            raw = clipboard.read_text()
            if raw is None:
                try:
                    raw = self.body_text.clipboard_get()
                except tk.TclError:
                    return False
        if not raw or "\t" not in raw:
            return False
        raw = raw.replace("\r\n", "\n").replace("\r", "\n")
        b = self.body_text
        try:
            here = b.get("insert linestart", "insert lineend")
        except tk.TclError:
            return False
        if core_tables.is_table_row(here):
            # Inside a table, pasting cells is the grid's business (the
            # cell-selection branch above); don't nest pipes into pipes.
            return False
        rows = [line.split("\t") for line in raw.strip("\n").split("\n")]
        ncols = max(len(row) for row in rows)
        rows = [row + [""] * (ncols - len(row)) for row in rows]
        aligns = [[core_tables.ALIGN_LEFT] * ncols for _ in rows]
        lines = core_tables.format_table(rows, aligns)
        # Our own copy remembers the source columns' set widths -- a
        # duplicated table comes back at the SAME widths, not shrunk
        # to the default. Text from elsewhere gets the plain rule.
        clip_widths = None
        if (raw == getattr(self, "_grid_cell_clip_text", None)
                and getattr(self, "_grid_cell_clip_widths", None)):
            clip_widths = list(self._grid_cell_clip_widths)
            while len(clip_widths) < ncols:
                clip_widths.append({"width": None, "align": None,
                                    "hidden": False})
        if clip_widths:
            sep = core_tables.CELL + core_tables.CELL.join(
                " " + cell + " "
                for cell in core_tables.make_separator(clip_widths)
            ) + core_tables.CELL
        else:
            sep = ("|" + "|".join([" --- "] * ncols) + "|")
        lines = [lines[0], sep] + lines[1:]
        clip_place = None
        if raw == getattr(self, "_grid_cell_clip_text", None):
            clip_place = getattr(self, "_grid_cell_clip_place", None)
        prefix = "" if not here.strip() else "\n"
        if not here.strip():
            # Pasting ONTO an empty line directly under a table would
            # glue the new rows to that block and merge the two tables
            # into one misshapen grid -- keep the empty line as the gap.
            try:
                ln = int(b.index("insert").split(".")[0])
                above = b.get(f"{ln - 1}.0", f"{ln - 1}.end") if ln > 1 else ""
            except (tk.TclError, ValueError):
                above = ""
            if core_tables.is_table_row(above):
                prefix = "\n"
        ins_line = int(b.index("insert").split(".")[0])
        b.insert("insert lineend", prefix + "\n".join(lines) + "\n")
        if clip_place in ("center", "right"):
            first_new = ins_line + (1 if prefix else 0)
            for n in range(first_new, first_new + len(lines)):
                b.tag_add(f"align_{clip_place}", f"{n}.0", f"{n}.end")
        self._body_follow_caret = True
        self._resync_list_tags()
        self._render_table_grids()
        self._schedule_autosave()
        return True

    def _paste_plain(self, event=None):
        """Paste the clipboard's text with none of its formatting.

        The escape hatch for pasting from a web page into a note without
        dragging its styling along.
        """
        text = clipboard.read_text()
        if text is None:
            try:
                text = self.body_text.clipboard_get()
            except tk.TclError:
                return "break"
        # Plenty of sources write their own bullets into the plain text they
        # offer, and a marker in the text is what makes a line a list line
        # here -- so pasting it verbatim produced the very formatting this
        # was meant to leave behind.
        # A PDF's line breaks are where its column ended, not where the
        # writer did. Rejoined before the markers are stripped, because that
        # decision reads the line structure and refuses to touch a list.
        self._replace_selection_with(strip_list_markers(reflow_wrapped(text)))
        self._body_follow_caret = True
        self.after_idle(self._resync_list_tags)
        self.after_idle(self._render_table_grids)
        self._schedule_autosave()
        return "break"

    def _replace_selection_with(self, text):
        """Drop the selection, if any, and put *text* where the cursor is."""
        self._caret_out_of_hidden()
        try:
            self.body_text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        self.body_text.insert("insert", text)

    @_undo_atom
    def _paste_formatted(self):
        """Paste rich clipboard content. True if that actually happened."""
        markup = clipboard.read_html()
        if not markup:
            return False
        text, spans, paragraphs = html_to_note(markup)
        if not text:
            return False
        # Only when the source offered no formatting of its own, which is the
        # case a PDF presents: bare lines broken by a column. Reflowing moves
        # every character after each join, and the spans are offsets into this
        # same text -- so a source that did send formatting keeps its line
        # breaks rather than have its bold slide out of place. Such a source
        # sent real block tags anyway, which means real paragraphs already.
        if not spans and not paragraphs:
            text = reflow_wrapped(text)

        try:
            self.body_text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        # Where it lands, before inserting: everything after this point
        # shifts, and Tk moves its own tags along with the text, so only
        # what arrives needs placing.
        at = self._char_offset(self.body_text, self.body_text.index("insert"))
        line = int(self.body_text.index("insert").split(".")[0]) - 1
        self.body_text.insert("insert", text)

        self._apply_formatting(
            self.body_text,
            [dict(s, start=s["start"] + at, end=s["end"] + at) for s in spans])
        self._apply_paragraphs(
            self.body_text,
            [dict(p, line=p["line"] + line) for p in paragraphs],
            scrub_table_align=True)
        # A pasted list starts its own numbering at one; renumbering makes
        # it continue whatever it was dropped into.
        self._renumber_lists()
        # A whole-body pass, which this is the case the cheap per-line one
        # is not for: a paste can bring in many lines at once, and the tags
        # derived from what those lines say -- a list's margin, a table's
        # monospace face -- are not carried by the text itself.
        self._body_follow_caret = True
        self._resync_list_tags()
        self._render_table_grids()
        self._refresh_format_buttons()
        self._schedule_autosave()
        return True

    def _copy_formatted(self, event=None):
        """Copy the selection so it arrives elsewhere still formatted.

        The plain text goes on the clipboard too, so pasting into something
        that cannot read markup still gives words rather than tags.

        With table cells selected, Ctrl+C means those cells: it used to
        copy the (empty) text selection instead, which left the OLD
        clipboard in place -- pasting then produced last week's copy.
        """
        sel = getattr(self, "_grid_sel", None)
        if sel is not None:
            self._grid_copy_selection(sel)
            return "break"
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
        except tk.TclError:
            return None                      # nothing selected; let Tk decide
        text = self.body_text.get(start, end)
        if not text:
            return None
        first = self._char_offset(self.body_text, start)
        last = self._char_offset(self.body_text, end)
        first_line = int(start.split(".")[0]) - 1

        clipped = []
        for span in self._extract_formatting(self.body_text):
            lo, hi = max(span["start"], first), min(span["end"], last)
            if hi > lo:
                clipped.append(dict(span, start=lo - first, end=hi - first))
        paragraphs = [
            dict(p, line=p["line"] - first_line)
            for p in self._extract_paragraphs(self.body_text)
            if 0 <= p["line"] - first_line < len(text.split("\n"))]

        # inline_tables: a clipboard fragment travels without the file
        # export's stylesheet, and Word shows a bare HTML table with no
        # borders at all -- a selectable phantom (the round-8 field
        # report, with screenshots of the invisible table).
        if not clipboard.write(text, note_to_html(text, clipped, paragraphs,
                                                  inline_tables=True)):
            return None                      # nothing written; Tk's copy runs
        return "break"

    def _refresh_list_buttons(self):
        """Show the bullet/number button as pressed when the cursor sits in
        a list of that kind, matching how the four style buttons behave.

        Deliberately reads the line the cursor is on rather than the whole
        selection: dragging across a plain line and a bullet line should not
        make the button claim the selection is a list.
        """
        if not getattr(self, "_list_buttons", None):
            return
        line_no = int(self.body_text.index("insert").split(".")[0])
        current = self._list_kind_of(self.body_text, line_no)
        for kind, btn in self._list_buttons.items():
            self._set_button_pressed(btn, kind == current)
        current_align = self._grid_align_context()
        if current_align is None:
            current_align = self._paragraph_align_of(self.body_text, line_no)
        for align, btn in getattr(self, "_align_buttons", {}).items():
            self._set_button_pressed(btn, align == current_align)

    def _attach_tooltip(self, widget, title, detail=""):
        """Explain a widget while the cursor rests on it.

        Every button on the formatting toolbar is an icon or a single
        letter, so what each one does is a guess at best. Bound with add="+"
        because several of these widgets already carry their own <Enter> or
        <Button-1> handlers.
        """
        widget.bind("<Enter>",
                    lambda e, w=widget: self._schedule_tooltip(w, title, detail),
                    add="+")
        widget.bind("<Leave>", lambda e: self._hide_tooltip(), add="+")
        # Clicking should get on with the job, not leave a label hanging over
        # the result of it. Through ONE command registered on the window,
        # not a lambda of the widget's own: Tk expands every script bound to
        # a click before running any, and a click whose own handler destroys
        # the widget -- a bin that redraws its row -- deleted this one while
        # it was still queued. "invalid command name", in silence, on every
        # such click (the popups' bind lines had the same lesson).
        hide = getattr(self, "_hide_tooltip_command", None)
        if hide is None:
            hide = self._hide_tooltip_command = self.register(self._hide_tooltip)
        # The "+" is spelled into the script: given a string, tkinter's
        # bind ignores add="+" and REPLACES the widget's other click
        # handlers -- measured, it took every icon's own action with it.
        widget.bind("<Button-1>", "+" + hide)

    def _schedule_tooltip(self, widget, title, detail):
        """Wait a moment before showing, so sweeping across the toolbar on
        the way somewhere else doesn't flash a row of labels."""
        self._hide_tooltip()
        self._tooltip_after = self.after(
            450, lambda: self._show_tooltip(widget, title, detail))

    def _hide_tooltip(self, event=None):
        """Take the tooltip down, and cancel one that has not appeared yet."""
        pending = getattr(self, "_tooltip_after", None)
        if pending is not None:
            try:
                self.after_cancel(pending)
            except (tk.TclError, ValueError):
                pass
            self._tooltip_after = None
        tip = getattr(self, "_tooltip", None)
        if tip is not None:
            try:
                if tip.winfo_exists():
                    tip.destroy()
            except tk.TclError:
                pass
            self._tooltip = None

    def _show_tooltip(self, widget, title, detail):
        self._tooltip_after = None
        try:
            if not widget.winfo_exists() or not widget.winfo_ismapped():
                return
        except tk.TclError:
            return

        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        self._tooltip = tip

        outer = tk.Frame(tip, bg=self.colors["accent"], padx=1, pady=1)
        outer.pack()
        box = tk.Frame(outer, bg=self.colors["card"], padx=10, pady=7)
        box.pack()
        tk.Label(box, text=title, bg=self.colors["card"],
                 fg=self.colors["text"], font=("Segoe UI", 9, "bold"),
                 justify="left").pack(anchor="w")
        if detail:
            tk.Label(box, text=detail, bg=self.colors["card"],
                     fg=self.colors["subtext"], font=("Segoe UI", 8),
                     justify="left").pack(anchor="w", pady=(2, 0))

        # Positioned under the button and measured against the app window,
        # never the screen -- the whole virtual desktop spans every monitor,
        # and measuring against that has put a popup on a display the app was
        # not on before (see docs/ISSUES_LOG.md).
        tip.update_idletasks()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        right_edge = self.winfo_rootx() + self.winfo_width() - 8
        if x + tip.winfo_width() > right_edge:
            x = max(self.winfo_rootx() + 8, right_edge - tip.winfo_width())
        tip.geometry(f"+{x}+{y}")

    def _add_fmt_item(self, widget, padx=(0, 2), ipady=0, fill=None, pady=0):
        """Record a formatting control, in the order it should appear.

        Not packed here: which row it lands on depends on how much room
        there is, which is not known until the editor has a width.
        """
        self._fmt_bar_items.append((widget, padx, ipady, fill, pady))

    def _on_format_bar_resize(self, event):
        """Reflow, but only when the width the controls have actually changed.

        Packing widgets changes the frame's size, which fires <Configure>
        again -- so reacting to every one of them is a loop.
        """
        if event.width == getattr(self, "_fmt_bar_width", None):
            return
        self._fmt_bar_width = event.width
        self._reflow_format_bar(event.width)

    def _reflow_format_bar(self, available=None):
        """Deal the controls into rows, breaking when one would not fit.

        Everything fits a single row at the sizes this app is used at. The
        second row is for the cases a fixed pixel budget cannot cover: a
        narrow window, a display at a different scaling, or a machine
        without the font this was measured on -- CI is all three, and the
        same bar that needs 577px here needs 827px there.
        """
        if not getattr(self, "_fmt_bar_items", None):
            return
        if available is None:
            available = self._fmt_bar.winfo_width()
        if available <= 1:                   # not laid out yet
            return

        measured = [(w.winfo_reqwidth() + px[0] + px[1], fl == "y")
                    for w, px, _ip, fl, _py in self._fmt_bar_items]
        # The arithmetic lives in core/formatting.py so it can be tested
        # against made-up widths rather than against whatever font this
        # machine happens to have -- see split_toolbar_rows.
        rows = [[self._fmt_bar_items[i] for i in row]
                for row in split_toolbar_rows(measured, available,
                                              len(self._fmt_bar_rows))]

        # The rows' packed/unpacked state is tracked here rather than
        # read back from winfo_ismapped(): mapping is asynchronous, so a
        # row packed a moment ago can still answer "not mapped" -- under
        # Xvfb the reflow then declined to fold an empty row away and the
        # bar kept two rows with room for one. Same lesson the calendar's
        # deferred rebuild records: reliable state, not winfo_ismapped().
        used = getattr(self, "_fmt_rows_used",
                       [False] * len(self._fmt_bar_rows))
        for widget, _padx, _ipady, _fill, _pady in self._fmt_bar_items:
            widget.pack_forget()
        for n, row_items in enumerate(rows):
            row = self._fmt_bar_rows[n]
            if row_items and not used[n]:
                row.pack(side="top", fill="x")
            elif not row_items and used[n]:
                row.pack_forget()
            for widget, padx, ipady, fill, pady in row_items:
                opts = {"side": "left", "padx": padx, "in_": row}
                if ipady:
                    opts["ipady"] = ipady
                if fill:
                    opts["fill"] = fill
                if pady:
                    opts["pady"] = pady
                widget.pack(**opts)
        for n in range(len(rows), len(self._fmt_bar_rows)):
            if used[n]:
                self._fmt_bar_rows[n].pack_forget()
        self._fmt_rows_used = [
            n < len(rows) and bool(rows[n])
            for n in range(len(self._fmt_bar_rows))]

    def _make_align_button(self, parent, align):
        """One alignment button, drawn as four bars on a small canvas.

        The ragged edge is the whole icon: bars flush left, centred, or
        flush right. Drawn rather than written because nothing in a normal
        font says "align right", and because canvas items can be recoloured
        on a theme switch.
        """
        canvas = tk.Canvas(parent, width=24, height=20, highlightthickness=0,
                           bd=0, cursor="hand2", relief="flat")
        for row, width in enumerate((15, 9, 15, 9)):
            y = 5 + row * 3.5
            if align == "left":
                x0 = 5
            elif align == "right":
                x0 = 19 - width
            else:
                x0 = 12 - width / 2
            canvas.create_line(x0, y, x0 + width, y, width=2, tags="bar")
        canvas.bind("<Button-1>",
                    lambda e, a=align: self._set_paragraph_align(a))
        return canvas

    def _set_button_pressed(self, btn, active):
        """The pressed/unpressed look shared by the paragraph buttons.

        Handles both real Buttons and the drawn alignment canvases: a canvas
        has no foreground of its own, so the bars are recoloured instead.
        """
        bg = self.colors["accent"] if active else self.colors["sidebar"]
        fg = "white" if active else self.colors["text"]
        btn.configure(relief="sunken" if active else "flat", bg=bg)
        if isinstance(btn, tk.Canvas):
            btn.itemconfigure("bar", fill=fg)
        else:
            btn.configure(fg=fg)

    def _apply_paragraphs(self, text_widget, paragraphs,
                          scrub_table_align=False):
        """Re-apply saved list lines as live tags, for loading.

        A stored entry only earns an indent if the line still starts with a
        marker of that kind. Otherwise a note edited outside the app, or one
        whose body was rewritten while its paragraphs were not, would come back
        with a plain line indented as though it were an item.

        *scrub_table_align* is the paste path: alignment a SOURCE document
        carried on its table rows is not a decision the user made here, and
        honouring it re-centred pasted tables "for no reason". A saved note
        loads with False, so a deliberately placed table keeps its place.
        """
        total = int(text_widget.index("end-1c").split(".")[0])
        for paragraph in normalize_paragraphs(paragraphs, total):
            line_no = paragraph["line"] + 1
            if line_no > total:
                continue
            align = paragraph.get("align", "left")
            line_text = text_widget.get(f"{line_no}.0", f"{line_no}.end")
            if (align != "left" and scrub_table_align
                    and is_table_row(line_text)):
                align = "left"
            if align != "left":
                # On a table row the tag stops at the text: covering the
                # newline let the writable line the renderer keeps under a
                # table be born inside the tag -- a phantom centred empty
                # line that kept the note reading as dirty forever.
                end_index = (f"{line_no}.end" if is_table_row(line_text)
                             else f"{line_no}.end+1c")
                text_widget.tag_add(f"align_{align}",
                                    f"{line_no}.0", end_index)
            kind = paragraph.get("kind")
            indent = paragraph.get("indent", 0)
            line = text_widget.get(f"{line_no}.0", f"{line_no}.end")
            if kind and parse_list_marker(line)[0] != kind:
                continue
            if not kind and not indent:
                continue
            text_widget.tag_add(
                self._paragraph_tag(text_widget, kind, indent),
                f"{line_no}.0", f"{line_no}.end")

    def _set_paragraph_indent(self, line_no, indent):
        """Put one line at a given depth, rewriting its marker if it has one.

        A bullet's glyph changes with depth, so the marker in the text has to
        be replaced, not just the tag -- otherwise a demoted item keeps the
        parent's bullet and the two levels look identical.
        """
        kind = self._list_kind_of(self.body_text, line_no)
        self._clear_paragraph_tags(self.body_text, line_no)
        if kind == "bullet":
            line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
            _, marker, _rest = parse_list_marker(line)
            new_marker = marker_for("bullet", 1, indent)
            if marker != new_marker:
                self.body_text.delete(f"{line_no}.0",
                                      f"{line_no}.0+{len(marker)}c")
                self.body_text.insert(f"{line_no}.0", new_marker)
        if kind or indent:
            self.body_text.tag_add(
                self._paragraph_tag(self.body_text, kind, indent),
                f"{line_no}.0", f"{line_no}.end")

    @_undo_atom
    def _change_paragraph_indent(self, delta):
        """Push the selected lines one step deeper, or pull them back out.

        Applies to any paragraph, not only list items: indenting a plain
        block of text is the other half of what people reach for here. Lines
        move as a group and each is clamped on its own, so a selection that
        already has one line at the left margin still indents the rest
        instead of refusing.
        """
        first, last = self._selected_line_range()
        for line_no in range(first, last + 1):
            current = self._paragraph_indent_of(self.body_text, line_no)
            self._set_paragraph_indent(
                line_no, max(0, min(MAX_INDENT, current + delta)))
        self._renumber_lists()
        self._refresh_list_buttons()
        self._schedule_autosave()

    def _cell_at(self, line_no, column):
        """Which cell of this row the given column falls in, and where it is.

        Returns ``(index, start, end)`` for the cell containing *column*, or
        the nearest one when the column sits on a pipe or in the padding.
        None if the line is not a row.
        """
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        bounds = core_tables.cell_bounds(line)
        if not bounds:
            return None
        # `column` arrives as a Tk column (UTF-16 units); `bounds` are
        # Python character offsets. Convert once so an emoji in an earlier
        # cell can't shift which cell the caret is judged to be in.
        column = self._py_col(line, column)
        for i, (start, end) in enumerate(bounds):
            # The cell owns everything up to the pipe that closes it, so a
            # caret sitting in the padding after a short cell counts as being
            # in that cell rather than in nothing.
            closing = line.index(core_tables.CELL, end)
            if column <= closing:
                return i, start, end
        last = len(bounds) - 1
        return last, bounds[last][0], bounds[last][1]

    def _move_to_cell(self, line_no, index):
        """Put the caret at the start of one cell's text, selecting it.

        Selecting is what makes tabbing through a table useful: the next
        thing typed replaces the cell rather than being appended to it,
        which is what every other table does.
        """
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        bounds = core_tables.cell_bounds(line)
        if not bounds or index >= len(bounds):
            return False
        start, end = bounds[index]
        # bounds are Python character offsets; Tk indices count UTF-16
        # units, so an emoji in an earlier cell used to land the caret —
        # and the selection — one place short per emoji.
        tk_start = self._tk_col(line, start)
        tk_end = self._tk_col(line, end)
        self.body_text.tag_remove("sel", "1.0", "end")
        self.body_text.mark_set("insert", f"{line_no}.{tk_start}")
        if end > start:
            self.body_text.tag_add("sel", f"{line_no}.{tk_start}",
                                   f"{line_no}.{tk_end}")
        self.body_text.see("insert")
        return True

    def _tab_in_table(self, delta):
        """Move to the next or previous cell. True if that happened.

        At the end of the last row a new one is added rather than the caret
        leaving: it is what lets a whole table be typed without reaching for
        the mouse, and it is what every word processor does. Backwards out of
        the first cell does nothing -- there is nowhere sensible to go, and
        silently leaving the table would be worse than staying.
        """
        line_no = int(self.body_text.index("insert").split(".")[0])
        column = int(self.body_text.index("insert").split(".")[1])
        # A rendered table is entered through its grid, not its text.
        rendered = self._table_block_at(line_no)
        if rendered:
            grid = self._grid_at_line(rendered[0])
            if grid is not None:
                if delta > 0 and grid["cells"]:
                    self._open_cell_editor(grid, *sorted(grid["cells"])[0])
                return True
        here = self._cell_at(line_no, column)
        if here is None:
            return False
        index, _start, _end = here
        block = self._table_block_at(line_no)
        if not block:
            return False
        first, last = block
        count = len(core_tables.cell_bounds(
            self.body_text.get(f"{line_no}.0", f"{line_no}.end")))

        if delta > 0:
            if index + 1 < count:
                return self._move_to_cell(line_no, index + 1)
            if line_no < last:
                return self._move_to_cell(line_no + 1, 0)
            # The last cell of the last row: make somewhere to go.
            self.body_text.insert(f"{line_no}.end", "\n"
                                  + core_tables.blank_table(1, count)[0])
            self._align_table_block(line_no)
            self._resync_list_tags()
            return self._move_to_cell(line_no + 1, 0)

        if index > 0:
            return self._move_to_cell(line_no, index - 1)
        if line_no > first:
            above = len(core_tables.cell_bounds(
                self.body_text.get(f"{line_no - 1}.0", f"{line_no - 1}.end")))
            return self._move_to_cell(line_no - 1, above - 1)
        return True

    TABLE_GRID_ROWS = 6
    TABLE_GRID_COLUMNS = 8

    @_undo_atom
    def _insert_table(self, rows, columns):
        """Put a blank table at the caret, on lines of its own.

        A table is lines, so it cannot share one with anything else: a
        newline is added before it when the caret sits in the middle of
        something, and after it so there is somewhere to carry on writing.
        """
        rows = max(1, min(self.TABLE_GRID_ROWS * 4, int(rows)))
        # Never fewer than two columns: is_table_row needs two cells to
        # tell a row from prose containing a pipe, so a one-column table
        # would insert as dead pipe text that never becomes a grid.
        columns = max(2, min(self.TABLE_GRID_COLUMNS, int(columns)))
        line_no = int(self.body_text.index("insert").split(".")[0])
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        # Two adjacent runs of pipe rows read as ONE block, so a table
        # created right under another fused with it -- mismatched column
        # counts and all. An empty line above (and below, when the next
        # line is also a table) keeps every table a block of its own.
        above = (self.body_text.get(f"{line_no - 1}.0", f"{line_no - 1}.end")
                 if line_no > 1 else "")
        below = self.body_text.get(f"{line_no + 1}.0", f"{line_no + 1}.end")
        before = ("\n" if (line.strip()
                           or core_tables.is_table_row(above)) else "")
        after = "\n" + ("\n" if core_tables.is_table_row(below) else "")
        block = "\n".join(core_tables.blank_table(rows, columns))
        self.body_text.insert("insert", before + block + after)
        first = line_no + (1 if before else 0)
        self._align_table_block(first)
        self._resync_list_tags()
        self._render_table_grids()
        made = self._grid_at_line(first)
        if made is not None and made["cells"]:
            self._open_cell_editor(made, *sorted(made["cells"])[0])
        self._schedule_autosave()
        return first

    def _open_table_size_popup(self):
        """Choose the size by pointing at it, the way a word processor does.

        A grid rather than two number fields: the shape of a table is the
        thing being chosen, and a grid shows it. Reuses the same anchored
        mini-popup the colour swatches use.
        """
        self._dismiss_mini_popup()
        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])
        outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
        outer.pack()
        body = tk.Frame(outer, bg=self.colors["card"])
        body.pack()

        caption = tk.Label(body, text="Insert table", font=("Segoe UI", 10, "bold"),
                           bg=self.colors["card"], fg=self.colors["text"])
        caption.pack(padx=15, pady=(12, 6))

        grid = tk.Frame(body, bg=self.colors["card"])
        grid.pack(padx=15)
        cells = {}

        def highlight(rows, columns):
            for (r, c), cell in cells.items():
                inside = r <= rows and c <= columns
                cell.configure(bg=self.colors["accent"] if inside
                               else inset_surface(self.colors))
            caption.configure(text=f"{rows} x {columns} table")

        def leave(_event=None):
            highlight(0, 0)
            caption.configure(text="Insert table")

        # Columns start at two: a one-column run of pipes is not
        # recognisable as a table row (| x | in prose would be one), so
        # the picker never offers a shape that cannot exist.
        for r in range(1, self.TABLE_GRID_ROWS + 1):
            for c in range(2, self.TABLE_GRID_COLUMNS + 1):
                cell = tk.Frame(grid, width=14, height=14, cursor="hand2",
                                bg=inset_surface(self.colors))
                cell.grid(row=r, column=c, padx=1, pady=1)
                cell.bind("<Enter>", lambda e, r=r, c=c: highlight(r, c))
                cell.bind("<Button-1>", lambda e, r=r, c=c: (
                    self._dismiss_mini_popup(), self._insert_table(r, c)))
                cells[(r, c)] = cell
        grid.bind("<Leave>", leave)

        hint = tk.Label(body, text="Tab moves between cells",
                        font=("Segoe UI", 8), bg=self.colors["card"],
                        fg=self.colors["subtext"])
        hint.pack(padx=15, pady=(6, 12))

        self._place_mini_popup(popup, self.table_btn)
        return popup

    def _on_body_tab(self, event, delta):
        """Tab and Shift+Tab move between table cells, or change list depth.

        Only inside one or the other: in ordinary prose Tab should still type
        a tab, which is what returning None leaves Tk to do. Shift+Tab always
        stops here, since its default is to move focus out of the editor
        mid-sentence.
        """
        if self._tab_in_table(delta):
            return "break"
        first, last = self._selected_line_range()
        in_list = any(self._list_kind_of(self.body_text, n)
                      for n in range(first, last + 1))
        if not in_list:
            return "break" if delta < 0 else None
        self._change_paragraph_indent(delta)
        return "break"

    def _selected_line_range(self):
        """The line numbers the cursor or selection covers."""
        try:
            first = int(self.body_text.index("sel.first").split(".")[0])
            last = int(self.body_text.index("sel.last").split(".")[0])
        except tk.TclError:
            first = last = int(self.body_text.index("insert").split(".")[0])
        return first, last

    @_undo_atom
    def _toggle_list(self, kind):
        """Turn the selected lines into a list, or back into plain lines.

        Toggling off is deliberate: pressing the same button twice should undo
        itself rather than stack a second marker onto the line.
        """
        # A table is not a list. A marker in front of a pipe row broke the
        # row's shape and dissolved the whole grid back into bare lines --
        # with cells selected the buttons simply decline, and table lines
        # inside a text selection are left out of the walk below.
        if getattr(self, "_grid_sel", None) is not None:
            self.set_status("A table cannot be a list")
            return
        first, last = self._selected_line_range()

        def blank(line_no):
            line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
            return (core_tables.is_table_row(line)
                    or not parse_list_marker(line)[2].strip())

        # An empty line is not a list item. Numbering a selection that had
        # blank lines between its items put a number on those too, so the
        # list read 1, 3, 5 with the even numbers sitting on nothing.
        # Blank lines are still visited when turning a list off, because one
        # of them may be carrying a marker put there before this.
        items = [n for n in range(first, last + 1) if not blank(n)]
        if not items:
            if first != last or core_tables.is_table_row(
                    self.body_text.get(f"{first}.0", f"{first}.end")):
                return
            # A single empty line is not a gap between items -- it is the
            # user asking to START a list here, marker first, text after.
            items = [first]
        turning_off = all(self._list_kind_of(self.body_text, n) == kind
                          for n in items)
        for line_no in range(first, last + 1):
            if not turning_off and line_no not in items:
                continue
            line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
            existing, marker, rest = parse_list_marker(line)
            # Depth is read before the tags go, and put back after: turning a
            # nested item into a bullet should leave it where it sits rather
            # than snapping it back to the left margin.
            indent = self._paragraph_indent_of(self.body_text, line_no)
            if marker:
                self.body_text.delete(f"{line_no}.0", f"{line_no}.0+{len(marker)}c")
            self._clear_paragraph_tags(self.body_text, line_no)
            if turning_off:
                if indent:
                    self.body_text.tag_add(
                        self._paragraph_tag(self.body_text, None, indent),
                        f"{line_no}.0", f"{line_no}.end")
                continue
            self.body_text.insert(f"{line_no}.0", marker_for(kind, 1, indent))
            # Stops at .end, deliberately: a tag that covered the newline
            # too would be inherited by whatever gets typed or pasted on
            # the next line.
            self.body_text.tag_add(
                self._paragraph_tag(self.body_text, kind, indent),
                f"{line_no}.0", f"{line_no}.end")
        self._renumber_lists()
        self._refresh_list_buttons()
        self._schedule_autosave()
        self.update_word_count()

    def _renumber_lists(self):
        """Make every numbered run read 1, 2, 3 again after any change.

        The arithmetic is in core/formatting.py; this applies the result and
        moves the formatting spans by however much the markers grew or shrank,
        so bold text does not slide sideways when 9 becomes 10.
        """
        body = self.body_text.get("1.0", "end-1c")
        paragraphs = self._extract_paragraphs(self.body_text)
        new_body, shifts = renumber(body, paragraphs)
        if new_body == body:
            return
        # The rewrite below is delete-everything + reinsert. Left as two
        # recorded edits, one Ctrl+Z undid the reinsert but not the
        # delete and the note showed EMPTY; bracket it as ONE undo unit.
        # The bracket sits AFTER the no-change early return, so a keystroke
        # that doesn't renumber emits no separator — normal typing undo is
        # untouched. Re-entrant, so when a wrapped list op called this the
        # whole op stays one unit.
        self._undo_atom_begin()
        try:
            spans = shift_spans(self._extract_formatting(self.body_text), shifts)
            insert_at = self.body_text.index("insert")
            self.body_text.delete("1.0", "end-1c")
            self.body_text.insert("1.0", new_body)
            self._apply_formatting(self.body_text, spans)
            self._apply_paragraphs(self.body_text, paragraphs)
            # The whole-body delete also tore out any drawn table grids
            # (their embedded window characters). If the body still holds
            # a table, redraw it or it dissolves into raw pipe rows — the
            # exact "Enter in a list dissolves my table" field failure.
            # Skipped when there's no table, so a plain list keeps its
            # keystroke-cheap path. _render_table_grids is undo-hidden, so
            # this adds no undo noise inside the atom.
            if core_tables.find_blocks(new_body):
                self._render_table_grids()
            try:
                self.body_text.mark_set("insert", insert_at)
            except tk.TclError:
                pass
        finally:
            self._undo_atom_end()

    def _on_body_return(self, event):
        """Enter inside a list continues it, or ends it on an empty item.

        Pressing Enter on an item you have not typed anything into is how
        people leave a list, so that removes the marker instead of adding
        another one.
        """
        # A specific binding beats the general <KeyPress> the caret guard
        # rides on, so Enter beside a table used to write into the hidden
        # text and surface the caret at the table's right edge.
        self._caret_out_of_hidden()
        line_no = int(self.body_text.index("insert").split(".")[0])
        # A note that BEGINS with a table has nowhere to type above it.
        # Clicking beside the table parks the caret at the start of the
        # line below (the guard's doing); Enter there pushes the table
        # down a line instead, and the caret takes the fresh first line.
        first_block = (self._table_block_at(1)
                       if is_table_row(self.body_text.get("1.0", "1.end"))
                       else None)
        if (first_block is not None
                and line_no == first_block[1] + 1
                and self.body_text.index("insert") == f"{line_no}.0"
                # ...unless a SECOND table follows right after: Enter on
                # the separating line then means space between tables,
                # as it always did.
                and not is_table_row(self.body_text.get(
                    f"{line_no + 1}.0", f"{line_no + 1}.end"))):
            # No snapshot here, deliberately: the edit happens at line 1,
            # far above wherever the user is scrolled, so the Text keeps
            # the view on the same content by itself -- and a snapshot
            # restored against the fresh grids' estimated heights was
            # MEASURED yanking a mid-note view nine lines up (0.30 to
            # 0.14). Render's own late capture still guards the page.
            self._teardown_table_grids()
            self.body_text.insert("1.0", "\n")
            self.body_text.mark_set("insert", "1.0")
            self._resync_list_tags()
            self._render_table_grids()
            self._schedule_autosave()
            return "break"
        kind = self._list_kind_of(self.body_text, line_no)
        if not kind:
            return None
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        _, marker, rest = parse_list_marker(line)
        indent = self._paragraph_indent_of(self.body_text, line_no)
        if not rest.strip():
            # An empty nested item steps out one level first. Pressing Enter
            # twice to leave a list is muscle memory, but from three levels
            # deep it should climb out rather than drop straight to a plain
            # paragraph -- which is what every other editor does.
            if indent:
                self._set_paragraph_indent(line_no, indent - 1)
                self._renumber_lists()
                return "break"
            self.body_text.delete(f"{line_no}.0", f"{line_no}.end")
            self._clear_paragraph_tags(self.body_text, line_no)
            self._renumber_lists()
            return "break"
        self.body_text.insert("insert", "\n" + marker_for(kind, 1, indent))
        new_line = line_no + 1
        self.body_text.tag_add(
            self._paragraph_tag(self.body_text, kind, indent),
            f"{new_line}.0", f"{new_line}.end")
        self._renumber_lists()
        self._schedule_autosave()
        return "break"

    def _on_body_delete_key(self, event=None):
        """Delete (and Backspace) with cells selected clears them, the way
        a spreadsheet does -- the table's text is hidden, so Tk's own
        deletion has nothing sensible to do there anyway.

        Without cells selected, Delete at the end of the line above a
        drawn table does nothing (see _deletion_joins_table). BackSpace
        comes through here for the cells only and asks about its own
        direction in _on_body_backspace."""
        sel = getattr(self, "_grid_sel", None)
        if sel is not None and self._grid_first_line(sel["info"]) is not None:
            self._grid_fill_selection(sel, "")
            return "break"
        if self._deletion_joins_table(True):
            return "break"
        return None

    def _on_body_backspace(self, event):
        """Backspace just after a marker removes the marker, not a character.

        Otherwise the only way out of a list is to delete the bullet one
        character at a time, which reads as the app fighting you.
        """
        sel = getattr(self, "_grid_sel", None)
        if sel is not None and self._grid_first_line(sel["info"]) is not None:
            return self._on_body_delete_key(event)
        self._caret_out_of_hidden()
        # At the start of the line under a drawn table, the character
        # before the caret is the table's own line break: nothing to take.
        if self._deletion_joins_table(False):
            return "break"
        index = self.body_text.index("insert")
        line_no, col = (int(p) for p in index.split("."))
        kind = self._list_kind_of(self.body_text, line_no)
        if not kind:
            return None
        line = self.body_text.get(f"{line_no}.0", f"{line_no}.end")
        _, marker, _rest = parse_list_marker(line)
        if not marker or col != len(marker):
            return None
        # Nested first: Backspace against the marker climbs out one level,
        # and only removes the marker once the item is back at the margin.
        # Deleting a bullet three levels in would otherwise leave its text
        # stranded at a depth with nothing above it.
        indent = self._paragraph_indent_of(self.body_text, line_no)
        if indent:
            self._set_paragraph_indent(line_no, indent - 1)
            self._renumber_lists()
            self._refresh_list_buttons()
            self._schedule_autosave()
            return "break"
        self.body_text.delete(f"{line_no}.0", f"{line_no}.0+{len(marker)}c")
        for tag in ("list_bullet", "list_number"):
            self.body_text.tag_remove(tag, f"{line_no}.0", f"{line_no}.end+1c")
        self._renumber_lists()
        self._schedule_autosave()
        return "break"

    def _setup_body_formatting_tags(self, text_widget):
        """Define the Tkinter tags the formatting toolbar/menu apply. Font
        objects are kept on self so they aren't garbage-collected (Tkinter
        needs a live Python reference to keep using them)."""
        base = tkfont.Font(font=text_widget["font"])
        family, size = base.actual("family"), base.actual("size")
        # Kept for the composite font tags: a span that sets only a size
        # still needs a family to build a Font from, and vice versa.
        self._body_base_family, self._body_base_size = family, size
        # Live references to those tags' Font objects, keyed by tag name.
        # Tkinter drops a font nothing holds, and the tag then silently
        # stops applying -- the same reason the three below sit on self.
        self._font_tag_fonts = {}
        self._fmt_bold_font = tkfont.Font(family=family, size=size, weight="bold")
        self._fmt_italic_font = tkfont.Font(family=family, size=size, slant="italic")
        self._fmt_bold_italic_font = tkfont.Font(
            family=family, size=size, weight="bold", slant="italic")
        text_widget.tag_configure("bold", font=self._fmt_bold_font)
        text_widget.tag_configure("italic", font=self._fmt_italic_font)
        text_widget.tag_configure("bold_italic", font=self._fmt_bold_italic_font)
        text_widget.tag_configure("underline", underline=True)
        text_widget.tag_configure("strike", overstrike=True)
        # Find-in-note highlights: background ONLY, so any text style under a
        # match keeps its exact look. Raised over highlight_* at find time.
        # Their names match no serialized style, so they never dirty the note.
        # Blended from the palette, so apply_theme re-runs this to re-tint them.
        self._retint_find_tags(text_widget)
        # Tk gives later-configured tags higher display priority, and "sel"
        # is created before any of these -- left alone, a highlight/text
        # color tag always paints over the selection color, making selected
        # highlighted text look unselected even though it really is (see
        # _ensure_color_tag, which re-raises "sel" for the same reason
        # whenever a new color tag is created later).
        text_widget.tag_raise("sel")

    @staticmethod
    def _char_offset(w, index):
        # PYTHON characters -- the exact space the saved body string
        # lives in. Tk's count("chars") counts UTF-16 units (an emoji is
        # two) while the "+Nc" arithmetic that APPLIES spans counts
        # characters (an emoji is one): extracting with the former
        # against spans applied with the latter shifted every span one
        # right per preceding emoji. The phantom difference then re-saved
        # the note -- "Note updated" on every startup, no edit anywhere,
        # and the stored span walked one character further each launch.
        # Both len(get()) and count("chars") skip embedded window
        # characters, which the drawn tables add — measured 2026-09-11,
        # after this comment had claimed for a while that they differ.
        # The astral difference above is the real one.
        return len(w.get("1.0", index))


    @classmethod
    def _char_class(cls, ch):
        """Which of three classes a character belongs to (see core.formatting)."""
        return core_char_class(ch)

    @staticmethod
    def _color_tag_name(style, hex_color):
        return core_color_tag_name(style, hex_color)

    def _ensure_color_tag(self, text_widget, style, hex_color):
        tag = self._color_tag_name(style, hex_color)
        if style == "text_color":
            text_widget.tag_configure(tag, foreground=hex_color)
        else:
            # The saved colour stays pure (the tag NAME carries it); only
            # the paint blends toward the page surface, exactly as the
            # table cells draw theirs -- the solid palette fill buried
            # the text under it. Theme switches re-blend via
            # _retint_highlight_tags.
            text_widget.tag_configure(tag, background=self._blend_hex(
                hex_color, self.colors["card"], 0.45))
        # A newly created tag becomes the new highest display priority,
        # which would bury "sel" underneath it -- see the matching
        # tag_raise("sel") in _setup_body_formatting_tags for why that
        # matters.
        text_widget.tag_raise("sel")
        # Same trap for the find highlights: a colour applied from the
        # toolbar fires no KeyRelease, so the edit-rescan that normally
        # re-raises them wouldn't run. Lift them back over the new tag now.
        if getattr(self, "_find_open", False) and text_widget is getattr(self, "body_text", None):
            self._find_raise_tags()
        return tag

    def _retint_highlight_tags(self, text_widget):
        """Re-blend every highlight tag's paint toward the CURRENT
        theme's surface. The tag names carry the pure colour, so the
        stored data never changes -- only the ink follows the theme."""
        for tag in text_widget.tag_names():
            if tag.startswith("highlight_"):
                try:
                    text_widget.tag_configure(
                        tag, background=self._blend_hex(
                            "#" + tag[len("highlight_"):],
                            self.colors["card"], 0.45))
                except (tk.TclError, ValueError):
                    pass

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

    def _ensure_font_tag(self, text_widget, is_bold, is_italic, size, family):
        """The tag carrying one whole font combination, made on demand.

        The Font object is held on self because Tkinter needs a live Python
        reference to keep using it -- let it be collected and the tag
        quietly stops applying. Built lazily because the combinations
        multiply, weight by slant by size by family: creating all 192 of the
        ones this app can offer measured 193ms, which is startup time spent
        on tags almost every note never uses.
        """
        name = core_font_tag_for(is_bold, is_italic, size, family)
        if name is None or name in KNOWN_FORMAT_STYLES:
            return name          # plain bold/italic/bold_italic, set up already
        if name not in self._font_tag_fonts:
            self._font_tag_fonts[name] = tkfont.Font(
                family=family or self._body_base_family,
                size=size or self._body_base_size,
                weight="bold" if is_bold else "normal",
                slant="italic" if is_italic else "roman",
            )
            # Configured now, so it lands later in Tk's tag order than bold
            # and italic and therefore wins the font option -- which is the
            # whole point, since those two set it as well.
            text_widget.tag_configure(name, font=self._font_tag_fonts[name])
        return name

    def _apply_font_runs(self, text_widget, spans):
        """Lay composite font tags over the ranges that need one.

        Runs alongside the plain style tags rather than instead of them: a
        bold run inside a resized paragraph keeps its "bold" tag, which is
        what the toolbar reads, while the composite on top decides what the
        text actually looks like.
        """
        length = len(text_widget.get("1.0", "end-1c"))
        for start, end, is_bold, is_italic, size, family in resolve_font_runs(
                spans, length):
            tag = self._ensure_font_tag(text_widget, is_bold, is_italic,
                                        size, family)
            if not tag:
                continue
            try:
                text_widget.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")
            except tk.TclError:
                pass

    @staticmethod
    def _char_offsets(text_widget, indices):
        """The same answer :meth:`_char_offset` gives, for many indices at
        once, paid ONCE for the whole widget instead of once per index.

        _char_offset is ``len(get("1.0", index))`` -- it re-reads the note
        from its start every time it is asked. That is fine for the four
        callers that ask once, and it was the whole cost of opening a
        heavily styled note: every styled piece has two ends, the reader
        below runs three times per open, and 500 pieces on one line
        measured 14.18 s of a 15.5 s startup.

        The trick is that the offsets are wanted for a SET of indices.
        Sorted, each one only needs the gap from the one before it, and
        the gaps add up to the note read exactly once. The character space
        is identical because it is the same ``len(get(...))`` -- Python
        characters, embedded window characters skipped, astral characters
        counted as one. That last part is not incidental: Tk's own
        ``count("chars")`` counts UTF-16 units, and using it here once
        shifted every span one place right per preceding emoji, re-saving
        the note on every launch.
        """
        wanted = {str(index) for index in indices}
        if not wanted:
            return {}

        def position(index):
            line, _, column = index.partition(".")
            return int(line), int(column)

        offsets, previous, running = {}, "1.0", 0
        for index in sorted(wanted, key=position):
            running += len(text_widget.get(previous, index))
            offsets[index] = running
            previous = index
        return offsets

    def _extract_formatting(self, text_widget):
        """Read the widget's current tags back out as a plain span list,
        for saving. Character offsets (not Tkinter's own line.col indices)
        so they're stable plain data, independent of line wrapping.

        Every tag range is collected first and the offsets worked out in
        one pass (see :meth:`_char_offsets`), because asking per range end
        is what made opening a heavily styled note feel like a freeze.
        """
        plain, fonts, colors = [], [], []
        for style in KNOWN_FORMAT_STYLES:
            ranges = text_widget.tag_ranges(style)
            for i in range(0, len(ranges), 2):
                plain.append((style, ranges[i], ranges[i + 1]))
        # Composite font tags carry size and family. Weight and slant are
        # folded into them for rendering, but are read back from their own
        # bold/italic tags above -- taking them from here as well would save
        # the same run twice.
        for tag_name in text_widget.tag_names():
            parsed = parse_font_tag(tag_name)
            if not parsed:
                continue
            _is_bold, _is_italic, size, family = parsed
            ranges = text_widget.tag_ranges(tag_name)
            for i in range(0, len(ranges), 2):
                fonts.append((size, family, ranges[i], ranges[i + 1]))

        for tag_name in text_widget.tag_names():
            for style in COLOR_FORMAT_STYLES:
                prefix = style + "_"
                if not tag_name.startswith(prefix):
                    continue
                hex_color = "#" + tag_name[len(prefix):]
                if not _is_valid_hex_color(hex_color):
                    continue
                ranges = text_widget.tag_ranges(tag_name)
                for i in range(0, len(ranges), 2):
                    colors.append((style, hex_color, ranges[i], ranges[i + 1]))

        offsets = self._char_offsets(text_widget, [
            index
            for group in (plain, fonts, colors)
            for entry in group
            for index in entry[-2:]
        ])

        # Built in the same order the three loops used to append in, so the
        # list handed to merge_spans is byte-for-byte what it always was.
        spans = []
        for style, first, last in plain:
            start, end = offsets[str(first)], offsets[str(last)]
            if end > start:
                spans.append({"start": start, "end": end, "style": style})
        for size, family, first, last in fonts:
            start, end = offsets[str(first)], offsets[str(last)]
            if end <= start:
                continue
            if size is not None:
                spans.append({"start": start, "end": end,
                              "style": "font_size", "value": size})
            if family is not None:
                spans.append({"start": start, "end": end,
                              "style": "font_family", "value": family})
        for style, hex_color, first, last in colors:
            start, end = offsets[str(first)], offsets[str(last)]
            if end > start:
                spans.append({"start": start, "end": end, "style": style,
                              "value": hex_color})
        # Merged before returning: a composite font tag is split into one
        # range per bold/italic boundary inside it, so a single size across a
        # paragraph reads back in pieces and would be written to the note
        # that way, then split again on the next save.
        return merge_spans(spans)

    def _apply_formatting(self, text_widget, spans):
        """Re-apply a saved span list as live Tkinter tags, for loading."""
        for span in normalize_formatting(spans):
            # Size and family are not applied one span at a time: they have
            # to be merged with whatever bold/italic covers the same
            # characters into a single tag, which _apply_font_runs does once
            # the whole list is known.
            if span["style"] in FONT_VALUE_STYLES:
                continue
            try:
                start_idx = text_widget.index(f"1.0+{span['start']}c")
                end_idx = text_widget.index(f"1.0+{span['end']}c")
                if span["style"] in COLOR_FORMAT_STYLES:
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
        self._apply_font_runs(text_widget, spans)

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
        """The single font tag for this bold/italic pair, or None.

        Two Tk tags that both set the font option do not compose, which is
        why bold+italic is one compound tag -- see core.formatting.
        """
        return core_font_tag_for(is_bold, is_italic)

    @staticmethod
    def _contrasting_fg(hex_color):
        """Black or near-white, whichever reads better against hex_color."""
        return core_contrasting_fg(hex_color)

    @_undo_atom
    def _toggle_body_style(self, style):
        """Bold/Italic/Underline/Strikethrough toolbar + right-click handler.

        With an active selection, toggles that style on exactly the
        selected text (existing behavior). With NO selection, toggles a
        "pending" style instead: it has no effect on existing text, but
        every character typed from now on picks it up, until the same
        style is toggled off again the same way — a manual on/off switch,
        not "match whatever formatting is already at the cursor" the way
        some editors infer it. See _apply_pending_style_to_typed_char."""
        target = self._grid_style_target()
        if target:
            # Cells are selected, or one is open in the editor: the button
            # means THOSE, not a pending style for the body.
            self._flush_table_grids()
            self._grid_apply_style(target[0], target[1], style)
            return
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

    @_undo_atom
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
        target = self._grid_style_target()
        if target:
            self._flush_table_grids()
            self._grid_apply_style(target[0], target[1], kind, hex_color)
            return
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

    @_undo_atom
    def _apply_body_font(self, style, value):
        """Font size / family picker handler.

        Closer to a colour than to Bold: "one of a list, or nothing" rather
        than on/off. With no selection it becomes a pending choice for
        whatever gets typed next, through the same anchor-tracking machinery
        the boolean styles and colours already use.
        """
        try:
            start = self.body_text.index("sel.first")
            end = self.body_text.index("sel.last")
            has_selection = self.body_text.compare(start, "<", end)
        except tk.TclError:
            has_selection = False

        label = "Font size" if style == "font_size" else "Font"
        if not has_selection:
            if style == "font_size":
                self._pending_font_size = value
            else:
                self._pending_font_family = value
            self.set_status(f"{label} set — applies to what you type next"
                            if value else f"{label} back to the default")
            if self._has_any_pending_style():
                self.body_text.mark_set(self._PENDING_STYLE_ANCHOR, tk.INSERT)
                self.body_text.mark_gravity(self._PENDING_STYLE_ANCHOR, "left")
                self._pending_style_last_length = self._pending_style_text_length()
            self._refresh_format_buttons()
            return

        # Size and family cannot be tagged in place the way a colour can:
        # what a run should look like depends on the bold and italic around
        # it too. So the spans are edited as data and the whole resolution
        # is redone -- clip this style out of the selection, put the new
        # value back over it, and let _apply_font_runs work out the tags.
        first = self._char_offset(self.body_text, start)
        last = self._char_offset(self.body_text, end)
        spans = []
        for span in self._extract_formatting(self.body_text):
            if span["style"] != style or span["end"] <= first or span["start"] >= last:
                spans.append(span)
                continue
            if span["start"] < first:
                spans.append({**span, "end": first})
            if span["end"] > last:
                spans.append({**span, "start": last})
        if value is not None:
            spans.append({"start": first, "end": last, "style": style,
                          "value": value})

        for name in self.body_text.tag_names():
            if parse_font_tag(name):
                self.body_text.tag_remove(name, "1.0", "end")
        self._apply_font_runs(self.body_text, spans)
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

        popup = tk.Toplevel(self)
        self._mini_popup = popup
        popup.wm_overrideredirect(True)
        popup.configure(bg=self.colors["accent"])

        def _choose(color):
            self._apply_body_color(kind, color)
            self._dismiss_mini_popup()

        if kind == "highlight":
            # The same column the table's highlight popup shows -- flat
            # full-width swatches parted by theme-coloured hairlines --
            # so every road to a highlight looks like every other.
            self._highlight_swatch_column(popup, _choose)
        else:
            outer = tk.Frame(popup, bg=self.colors["card"], padx=1, pady=1)
            outer.pack()
            body = tk.Frame(outer, bg=self.colors["card"])
            body.pack()

            # Only this branch draws a header, and only text_color reaches
            # it, so the text is written out rather than chosen here. It used
            # to be picked above by a conditional whose highlight half was
            # computed on every open and never displayed -- the highlight
            # popup takes the branch above and carries its own header now.
            label = tk.Label(body, text="Pick a text color",
                             font=("Segoe UI", 10, "bold"),
                             bg=self.colors["card"], fg=self.colors["text"])
            label.pack(padx=15, pady=(12, 8))

            swatch_grid = tk.Frame(body, bg=self.colors["card"])
            swatch_grid.pack(padx=15)

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
            or bool(self._pending_highlight_color) \
            or bool(self._pending_font_size) or bool(self._pending_font_family)

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
            is_bold = "bold" in self._pending_styles
            is_italic = "italic" in self._pending_styles
            tag = self._font_tag_for(is_bold, is_italic)
            if tag:
                self.body_text.tag_add(tag, start_idx, end_idx)
            if self._pending_font_size or self._pending_font_family:
                # The plain tag above stays as the marker the toolbar reads;
                # this one goes over it and decides how the text looks.
                self.body_text.tag_add(
                    self._ensure_font_tag(
                        self.body_text, is_bold, is_italic,
                        self._pending_font_size, self._pending_font_family),
                    start_idx, end_idx)
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
        # The clicked column is a Tk column (UTF-16 units); the word walk
        # below runs on Python characters, and the selection goes back to
        # Tk. Convert in both directions, or an emoji earlier on the line
        # shifts which word gets selected — and where the highlight lands.
        col = min(self._py_col(line_text, int(col)), len(line_text) - 1)
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
        w.tag_add("sel", f"{line}.{self._tk_col(line_text, start)}",
                  f"{line}.{self._tk_col(line_text, end)}")
        w.mark_set("insert", f"{line}.{self._tk_col(line_text, end)}")
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

    def _uniform_font_in_selection(self, style, start, end):
        """The one size (or family) covering the WHOLE range, or None.

        None also means "a mix", which is the honest answer for a dropdown:
        showing the first run's size for a selection spanning two of them
        would claim the whole selection is that size, and the next click
        would then be understood as "leave it as it is".
        """
        wanted = None
        idx = start
        while self.body_text.compare(idx, "<", end):
            found = None
            for name in self.body_text.tag_names(idx):
                parsed = parse_font_tag(name)
                if parsed:
                    found = parsed[2] if style == "font_size" else parsed[3]
                    break
            if found is None:
                return None
            if wanted is None:
                wanted = found
            elif wanted != found:
                return None
            idx = self.body_text.index(f"{idx}+1c")
        return wanted

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
        self._resync_list_tags(int(self.body_text.index("insert").split(".")[0]))
        self._refresh_list_buttons()
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

        if hasattr(self, "font_size_var"):
            if has_selection:
                size = self._uniform_font_in_selection("font_size", start, end)
                family = self._uniform_font_in_selection("font_family", start, end)
            else:
                size = self._pending_font_size
                family = self._pending_font_family
            # A mix across the selection reads as "Default" rather than as
            # the first run's value, which would claim the whole selection
            # is that size.
            self.font_size_var.set(str(size) if size else self.DEFAULT_FONT_LABEL)
            self.font_family_var.set(family or self.DEFAULT_FONT_LABEL)

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

    def _show_emoji_picker(self, text_widget, anchor=None):
        """Small themed popup for inserting an emoji at the current cursor
        position of whichever field opened it (title, body, comments, etc.).
        Anchored to that field, not a separate window.

        A field that lives INSIDE a popup -- the template editor, a rename
        box -- gets the picker as a popup within that one, the way a
        dropdown in the template editor does. Closing the host first, as
        every other opener does, destroyed it and everything typed in it,
        and left the picker at the screen's corner, aimed at a field that
        no longer existed."""
        host = getattr(self, "_mini_popup", None)
        nested = host is not None and self._is_inside_popup(text_widget, host)
        if nested:
            self._close_nested_popup()
        elif not self._dismiss_mini_popup_asking():
            return
        pop = tk.Toplevel(self)
        if nested:
            # Remembered where Escape and the host's own closing look.
            self._nested_dropdown = pop
        else:
            self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        outer = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        outer.pack(padx=1, pady=1)

        head = tk.Frame(outer, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Insert emoji", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(head, text="✕",
                  command=pop.destroy if nested else self._dismiss_mini_popup,
                  relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")
        if nested:
            # Its own Escape closes just it, as a nested dropdown's does.
            pop.bind("<Escape>", lambda e: pop.destroy())

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
                # focus_get raises KeyError, not TclError, while the focus
                # sits in an override-redirect popup like this picker -- it
                # is what made the second emoji die where the first landed.
                try:
                    has_focus = self.focus_get() is text_widget
                except KeyError:
                    has_focus = False
                if not has_focus:
                    text_widget.focus_set()
                if isinstance(text_widget, tk.Text):
                    text_widget.insert(tk.INSERT, emoji)
                else:
                    pos = text_widget.index(tk.INSERT)
                    text_widget.insert(pos, emoji)
                    # A Tk Entry counts UTF-16 units, not characters, so an
                    # astral emoji is TWO steps wide. Advancing by Python's
                    # len() parked the caret between the surrogates of the
                    # emoji just placed, and the next one speared it apart
                    # -- which the save's mend then faithfully turned into
                    # replacement-character diamonds.
                    text_widget.icursor(pos + self._tk_units(emoji))
                # Best-effort: nudge autosave if this field participates in it.
                # skip_word_count avoids re-reading the whole body on every
                # single click — that's what made rapid emoji-clicking laggy.
                # A popup's field never does: its popup saves it.
                if not nested:
                    self._schedule_autosave(skip_word_count=True)
            except (tk.TclError, KeyError):
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

        self._place_dropdown_popup(pop, anchor or text_widget)

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
        self.track_theme(self.import_box, bg="card", fg="text", insertbackground="text")
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
        if self._is_placed(self.import_panel):
            self.import_panel.pack_forget()
        else:
            if self._is_placed(self.share_panel):
                self.share_panel.pack_forget()
            self.import_panel.pack(fill="x", padx=8, pady=(0, 8))
            self.import_box.focus()
        self._fit_sidebar_panel()

    # How far an open panel's scrolling middle gives when the window is
    # short: (natural, comfortable, least) -- pixels of Share's list of
    # notes, lines of Import's paste box.
    SIDEBAR_PANEL_BODY = {"share": (130, 56, 28), "import": (4, 2, 1)}

    def _fit_sidebar_panel(self, _event=None):
        """Keep the open panel's own buttons -- and a generated code -- on
        screen in a short window.

        The bottom zone is packed before the note list, so the list gives
        up its height first. At the smallest window that is not enough:
        the sidebar's fixed parts leave the panel about a hundred pixels,
        Import needs 157 and Share with its code 329, and pack took the
        difference off the bottom of the zone -- the panel's own buttons,
        then the code itself, so "Generate code" seemed to do nothing.

        Only when the room runs out, then: the panel's scrolling middle
        gives up rows down to a comfortable few, the zone's other buttons
        step aside while the panel is open -- Settings, then the other
        panel's button, then New Note -- the middle goes down to one row,
        and last the panel's own button steps aside too (its Close still
        closes it). It is worked out from the sizes things ask for, not from
        what is drawn, and everything comes back when the panel closes or
        the window grows. Measured: 640x600 and 1366x690 both hold the
        panels whole; at 1150x860 nothing changes at all."""
        zone = getattr(self, "_sidebar_bottom", None)
        buttons = getattr(self, "_sidebar_zone_buttons", None)
        if zone is None or not buttons or getattr(self, "_fitting_sidebar", False):
            return
        if self._is_placed(self.share_panel):
            panel, which = self.share_panel, "share"
        elif self._is_placed(self.import_panel):
            panel, which = self.import_panel, "import"
        else:
            panel, which = None, None
        wrap = getattr(self, "_share_list_wrap", None)
        try:
            natural_state = (
                all(self._is_placed(b) for b, _kw in buttons)
                and int(self.import_box.cget("height")) == self.SIDEBAR_PANEL_BODY["import"][0]
                and (wrap is None or not wrap.winfo_exists()
                     or int(wrap.cget("height")) == self.SIDEBAR_PANEL_BODY["share"][0]))
        except tk.TclError:
            return
        if panel is None and natural_state:
            return                      # the everyday case: nothing to do
        self._fitting_sidebar = True
        try:
            self._fit_sidebar_panel_now(zone, buttons, panel, which, wrap)
        except tk.TclError:
            pass
        finally:
            self._fitting_sidebar = False

    def _fit_sidebar_panel_now(self, zone, buttons, panel, which, wrap):
        def height(w, kw):
            pady = kw.get("pady", 0)
            pad = sum(pady) if isinstance(pady, (tuple, list)) else 2 * int(pady)
            return w.winfo_reqheight() + 2 * int(kw.get("ipady", 0)) + pad

        hidden = set()
        body = {"share": self.SIDEBAR_PANEL_BODY["share"][0],
                "import": self.SIDEBAR_PANEL_BODY["import"][0]}
        room = self.sidebar.winfo_height()
        if panel is not None and room > 1:
            self.update_idletasks()
            unit = (1 if which == "share" else tkfont.Font(
                font=self.import_box.cget("font")).metrics("linespace"))
            natural, comfortable, least = self.SIDEBAR_PANEL_BODY[which]
            now = int((wrap if which == "share" else self.import_box).cget("height"))
            list_host = self.canvas.master
            top = sum(height(s, s.pack_info()) for s in self.sidebar.pack_slaves()
                      if s is not zone and s is not list_host)
            want = (sum(height(b, kw) for b, kw in buttons)
                    + panel.winfo_reqheight() + (natural - now) * unit
                    + height(panel, panel.pack_info()) - panel.winfo_reqheight())
            over = top + want - room

            def give(to):
                nonlocal over
                units = min(max(0, -(-over // unit)), body[which] - to)
                body[which] -= units
                over -= units * unit

            if over > 0:
                give(comfortable)
            new_b, import_b, share_b, settings_b = (b for b, _kw in buttons)
            own = import_b if which == "import" else share_b
            other = share_b if which == "import" else import_b
            for b in (settings_b, other, new_b):
                if over <= 0:
                    break
                hidden.add(b)
                over -= height(b, dict(buttons)[b])
            if over > 0:
                give(least)
            if over > 0:
                # The very last resort: the panel's own button. Its Close
                # still closes it (measured: the selection bar open above
                # Share with a code, at 1366x690 in the Linux fonts).
                hidden.add(own)
                over -= height(own, dict(buttons)[own])
        # Apply only what changes, the zone's order kept: a button coming
        # back goes in front of the next one still packed.
        order = [b for b, _kw in buttons] + ([panel] if panel is not None else [])
        for i, (b, kw) in enumerate(buttons):
            if b in hidden:
                if self._is_placed(b):
                    b.pack_forget()
            elif not self._is_placed(b):
                nxt = next((w for w in order[i + 1:] if self._is_placed(w)), None)
                if nxt is not None:
                    b.pack(before=nxt, **kw)
                else:
                    b.pack(**kw)
        if int(self.import_box.cget("height")) != body["import"]:
            self.import_box.configure(height=body["import"])
        if wrap is not None and wrap.winfo_exists() \
                and int(wrap.cget("height")) != body["share"]:
            wrap.configure(height=body["share"])

    def _take_known_notes(self, incoming, source):
        """Ask once about the notes in a batch we already have.

        Returns ``(proceed, remaining, updates, unchanged)``: *remaining*
        is what the caller should go on to import as new notes, *proceed*
        is False when the user cancelled, *updates* is what "Update" agreed
        to, and *unchanged* counts the notes that arrived exactly as they
        are here and need nothing at all.

        The updates are NOT applied here. The caller applies them with
        _apply_known_updates once the last question of its import is
        answered: applied here, a Cancel on the question that follows (the
        duplicate check) left the notes already replaced in memory, with
        nothing on screen saying so, and the next unrelated save wrote them
        to disk.

        Both bulk routes -- a share code carrying several notes and a
        restored backup -- come through here, so the two cannot drift
        apart. A note whose identity matches one already here is the SAME
        note, edited elsewhere; the text-matching duplicate check below
        answers a different question and answers it wrongly for exactly
        this case, because an edited note reads as new.

        One question for the whole batch, not one per note: a restored
        backup can hold a hundred, and a hundred dialogs is not consent,
        it is attrition.
        """
        known, fresh = split_by_identity(self.notes, incoming)
        # A note that arrives exactly as it is here needs nothing: not an
        # update (see shared_update_changes for what that used to cost),
        # and not a second copy either.
        differing = [(mine, theirs) for mine, theirs in known
                     if self._known_note_differs(mine, theirs, source)]
        unchanged = len(known) - len(differing)
        known = differing
        if not known:
            return True, fresh, [], unchanged
        count = len(known)
        plural = "" if count == 1 else "s"
        if fresh:
            message = (
                f"{count} of the {len(incoming)} note{'' if len(incoming) == 1 else 's'} "
                f"in this {source} {'is' if count == 1 else 'are'} already here, "
                f"edited elsewhere.\n\n"
                f"Updating replaces this device's copies; each one can be "
                f"undone with \u201c\u21a9 Restore previous\u201d.\n"
                f"Adding leaves both versions, so you can compare them."
            )
        else:
            message = (
                f"All {count} note{plural} in this {source} {'is' if count == 1 else 'are'} "
                f"already here, edited elsewhere.\n\n"
                f"Updating replaces this device's copies; each one can be "
                f"undone with \u201c\u21a9 Restore previous\u201d.\n"
                f"Adding leaves both versions, so you can compare them."
            )
        # "Edited elsewhere" reads as "newer", and a backup from last month
        # is edited elsewhere too. Updating from it trades this device's
        # newer text for older text, so the question says so. (A backup's
        # notes carry when they were last saved; a share code does not.)
        older = 0 if source != "backup" else sum(
            1 for mine, theirs in known
            if str(theirs.get("updated") or "") < str(mine.get("updated") or ""))
        if older:
            who = "It is" if count == 1 else f"{older} of them are"
            message += f"\n\n{who} OLDER than the copy on this device."
        choice = self._themed_dialog(
            f"{count} note{plural} you already have",
            message,
            kind="question",
            buttons=[("Cancel", "cancel"),
                     (f"Add {'it' if count == 1 else 'them'} as new notes", "add"),
                     (f"Update the {count}", "update")],
        )
        if choice is None or choice == "cancel":
            return False, [], [], unchanged
        if choice == "update":
            # Same order as the single-note route, for the same reason:
            # the editor's unsaved work is saved before anything replaces
            # it. Cancel on the day's save question cancels the import:
            # going on would replace the very edit the person just
            # declined to let go of.
            if self._flush_autosave() is False:
                return False, [], [], unchanged
            return True, fresh, known, unchanged
        # "add": the copies go on as new notes, without the identity they
        # arrived with -- two notes wearing one uid is the collision this
        # whole field exists to prevent.
        stripped = []
        for _mine, theirs in known:
            copy = dict(theirs)
            copy.pop("uid", None)
            stripped.append(copy)
        return True, fresh + stripped, [], unchanged

    def _apply_known_updates(self, updates, source):
        """Apply what "Update" agreed to in _take_known_notes; returns how
        many notes changed. The editor is then brought onto the new
        version of any note it holds -- or its next save puts the old
        version straight back."""
        fields = (UPDATABLE_FROM_BACKUP if source == "backup"
                  else UPDATABLE_FROM_SHARED)
        for mine, theirs in updates:
            apply_shared_update(mine, theirs, fields)
            if source == "backup":
                self._adopt_backup_attachments(mine, theirs)
        if updates:
            self._editor_follows_external_change(
                {n.get("id") for n, _ in updates})
        return len(updates)

    def _dup_keys_after(self, updates):
        """The duplicate-check keys of the notebook as it will be once
        *updates* (from _take_known_notes) are applied. They are applied
        only after the duplicate question is answered, but that question
        is about the notebook the import will leave behind."""
        replaced = {id(mine) for mine, _ in updates}
        return ({_dup_key(n) for n in self.notes if id(n) not in replaced}
                | {_dup_key(normalize_note(theirs)) for _, theirs in updates})

    def _known_note_differs(self, mine, theirs, source):
        """Whether importing *theirs* over *mine* would change anything: a
        field the route may update, or -- from a backup, whose files are
        added and never swapped -- a file this device's copy lacks."""
        fields = (UPDATABLE_FROM_BACKUP if source == "backup"
                  else UPDATABLE_FROM_SHARED)
        if shared_update_changes(mine, theirs, fields):
            return True
        return source == "backup" and bool(self._files_to_adopt(mine, theirs))

    def _files_to_adopt(self, mine, theirs):
        """The attachments a backup's copy of a note has and *mine* lacks."""
        have = {a.get("stored_as") for a in mine.get("attachments") or []
                if isinstance(a, dict)}
        return [att for att in normalize_note(dict(theirs)).get("attachments") or []
                if att.get("stored_as") and att.get("stored_as") not in have]

    def _adopt_backup_attachments(self, mine, theirs):
        """Add the files a backup's copy of a note has and this one lacks.

        Added, never swapped: an attachment this device holds and the
        backup does not stays where it is, so updating from a backup can
        only ever bring files in. The backup's files are already in the
        attachments folder by now -- the import's worker copied them --
        and a file another note or a Trash entry already owns gets a copy
        of its own, the same claimed-file discipline the rest of the
        import follows, so deleting one note can never take another's
        file with it.
        """
        have = {a.get("stored_as") for a in mine.get("attachments") or []
                if isinstance(a, dict)}
        claimed = {a.get("stored_as")
                   for n in (self.notes + self.trash)
                   if isinstance(n, dict) and n is not mine
                   for a in (n.get("attachments") or [])
                   if isinstance(a, dict)}
        for att in self._files_to_adopt(mine, theirs):
            name = att.get("stored_as")
            if name in have:
                continue
            if len(mine.setdefault("attachments", [])) >= MAX_ATTACHMENTS:
                break
            att = dict(att)
            if name in claimed:
                new_name = copy_attachment_file(name)
                if not new_name:
                    continue
                att["stored_as"] = new_name
            mine["attachments"].append(att)
            have.add(att["stored_as"])

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
        # Oversized notes are trimmed at normalize (the checklist,
        # attachment and styling-span ceilings) — SAY so instead of
        # silently dropping 19,000 items. Measured on the raw decode,
        # the last moment the original sizes are still visible.
        def _ln(v):
            return len(v) if isinstance(v, (list, tuple)) else 0
        def _line_trimmed(sn):
            spans = sn.get("formatting")
            if not isinstance(spans, list) or len(spans) <= MAX_SPANS_PER_LINE:
                return False
            body = sn.get("body")
            clean = normalize_formatting(spans)
            return len(clamp_spans_per_line(
                body if isinstance(body, str) else "", clean)) < len(clean)

        oversized = sum(
            1 for sn in valid
            if _ln(sn.get("checklist")) > MAX_CHECKLIST_ITEMS
            or _ln(sn.get("attachments")) > MAX_ATTACHMENTS
            or _ln(sn.get("formatting")) > MAX_FORMATTING_SPANS
            or _line_trimmed(sn))
        if len(valid) == 1:
            incoming = valid[0]
            # Identity first, resemblance second. A note that carries the
            # uid of one already here IS that note -- most likely the
            # same note, edited somewhere else and sent back. Asking
            # _dup_key instead would compare the text, and the text is
            # different precisely because it was edited, so it would say
            # "new note" and quietly leave two copies behind.
            mine = find_by_uid(self.notes, normalize_note(incoming).get("uid"))
            if mine is not None and not self._known_note_differs(
                    mine, incoming, "code"):
                # The code holds this note exactly as it is here. "The two
                # differ" was said without comparing, and Update then
                # replaced the rescue copy with a duplicate of the note.
                self.import_status.config(
                    text="This note is already here, exactly as in the code.",
                    fg=self.colors["success"])
                return
            if mine is not None:
                choice = self._themed_dialog(
                    "Same note, a different version",
                    "This note is already here, and the two differ.\n\n"
                    "Updating replaces what is on this device; you can undo "
                    "it with “↩ Restore previous”.\n"
                    "Adding leaves both, so you can compare them and "
                    "delete one.",
                    kind="question",
                    buttons=[("Cancel", "cancel"),
                             ("Add as a new note", "add"),
                             ("Update this note", "update")]
                )
                if choice is None or choice == "cancel":
                    return
                if choice == "update":
                    # The editor is most likely showing this very note --
                    # it is where the code came from. Its unsaved edits
                    # are saved FIRST, so they are what the rescue copy
                    # holds and "↩ Restore previous" gives back; then the
                    # incoming version replaces them. Cancel on a day's
                    # save question stops here, with nothing replaced.
                    if self._flush_autosave() is False:
                        return
                    apply_shared_update(mine, incoming)
                    self.save_notes()
                    self.import_box.delete("1.0", "end")
                    self.toggle_import_panel()
                    self.refresh_note_list()
                    self.render_calendar()
                    # Without flush=False this saves what the editor still
                    # shows -- the version just replaced -- straight back
                    # over the update. The flush above already kept the
                    # user's own work.
                    self.open_note_in_tab(mine, flush=False)
                    self.set_status("Note updated from the code "
                                    "— ↩ Restore previous undoes it")
                    return
                # "add" falls through to the ordinary import below, which
                # opens the copy in a fresh editor tab and lets the user
                # save it as a new note.
                #
                # Dropping the uid here is belt and braces, and honestly
                # so: the review editor carries an arriving identity only
                # when no note here wears it, and this one does, so the
                # saved copy is minted a fresh identity whether or not
                # this line runs. It stays because it puts the intent
                # where the decision is made, instead of resting on a
                # check two calls away. The BULK route two branches down
                # has no second guard and is covered by a check that
                # does bite.
                incoming = dict(incoming)
                incoming.pop("uid", None)
                valid = [incoming]
            existing_keys = {_dup_key(n) for n in self.notes}
            if _dup_key(normalize_note(incoming)) in existing_keys:
                choice = self._themed_dialog(
                    "Possible duplicate",
                    "This note looks identical to one you already have (same "
                    "title, text, comments, category, checklist and\n"
                    "repeat rule).",
                    kind="question",
                    buttons=[("Cancel", "cancel"), ("Open it anyway", "open")]
                )
                if choice is None or choice == "cancel":
                    return
            # Passed DOWN rather than set here: _open_imported_note_in_editor
            # ends by setting its own status, so a set_status at this point
            # was overwritten one frame later and the user never saw that
            # their note had been trimmed. Dead code with a ledger row
            # claiming it shipped.
            if self._open_imported_note_in_editor(
                    incoming, trimmed=bool(oversized)) is False:
                # Cancel on a repeating day's save question: that day stays
                # in the editor, and the code stays in the box to try again.
                return
            self.import_box.delete("1.0", "end")
            self.toggle_import_panel()
            return
        # Identity first: notes this batch says we already have.
        proceed, valid, updates, unchanged = self._take_known_notes(valid, "code")
        if not proceed:
            return
        if not valid:
            updated = self._apply_known_updates(updates, "code")
            if updated:
                self.save_notes()
            self.import_box.delete("1.0", "end")
            self.toggle_import_panel()
            self.refresh_note_list()
            self.render_calendar()
            self.set_status("Notes updated from the code "
                            "— ↩ Restore previous undoes each one" if updated
                            else "Everything in this code is already here, unchanged")
            return
        next_id = max([n["id"] for n in self.notes], default=0) + 1
        # Check each incoming note against what's already here — same
        # matching rule as "Find duplicates" — before blindly appending
        # everything. Importing the same share code twice (or a code that
        # overlaps with notes you already kept) used to silently create
        # duplicates with no way to tell beforehand.
        existing_keys = self._dup_keys_after(updates)
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
        # Every question is answered: only now do the updates happen.
        updated = self._apply_known_updates(updates, "code")
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
        oversize_note = (f" — {oversized} oversized note(s) trimmed to safe limits"
                         if oversized else "")
        known_note = ((f", updated {updated}" if updated else "")
                      + (f", {unchanged} already here" if unchanged else ""))
        self.import_status.config(
            text=f"Added {added} notes{known_note} ✓{skipped_note}{oversize_note}",
            fg=self.colors["success"])

    def toggle_share_panel(self):
        if self._is_placed(self.share_panel):
            self.share_panel.pack_forget()
        else:
            if self._is_placed(self.import_panel):
                self.import_panel.pack_forget()
            self._build_share_panel()
            self.share_panel.pack(fill="x", padx=8, pady=(0, 8))
        self._fit_sidebar_panel()

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
        # The heading and the select-all share a row: the selection bar a few
        # centimetres above this panel has had a "Select all" since it was
        # built, and this list -- the one where a whole notebook means a
        # hundred clicks, then "Show 100 more", then a hundred more -- had
        # none. Two tick-box lists in one sidebar, one fillable in a click.
        head_row = tk.Frame(p, bg=self.colors["sidebar"])
        head_row.pack(fill="x", padx=6, pady=(6, 2))
        tk.Label(head_row, text="Pick notes to share:",
                 font=("Segoe UI", 8, "bold"), anchor="w",
                 bg=self.colors["sidebar"], fg=self.colors["text"]
                 ).pack(side="left")
        select_all_btn = tk.Button(
            head_row, text="Select all", command=lambda: toggle_select_all(),
            relief="flat", font=("Segoe UI", 8), cursor="hand2",
            bg=self.colors["card"], fg=self.colors["text"], bd=0)
        select_all_btn.pack(side="right", ipadx=4)

        # Scrollable checklist (a notebook can have many notes). Fixed height so
        # it never grows the whole panel off-screen; the scrollbar handles the
        # overflow.
        list_wrap = tk.Frame(p, bg=self.colors["sidebar"],
                             height=self.SIDEBAR_PANEL_BODY["share"][0])
        list_wrap.pack(fill="x", padx=6, pady=(0, 2))
        list_wrap.pack_propagate(False)
        # What gives up rows first when the window is short (_fit_sidebar_panel).
        self._share_list_wrap = list_wrap
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

        # What render_checkboxes last actually drew. "Select all" acts on
        # what is ON SCREEN, and that is not the same as self.notes[:n]:
        # the list is paginated, so a button that silently ticked a hundred
        # notes nobody had seen would be the opposite of the control this
        # asks for -- and the panel is not live, so a note deleted while it
        # is open leaves the drawn list behind. Reading self.notes here
        # ticked ids that had no tick box on screen, which is how the first
        # version of this was caught.
        rendered = {"ids": []}

        def _revealed():
            """The ids the panel is actually showing right now."""
            return list(rendered["ids"])

        def _all_revealed_ticked():
            ids = _revealed()
            return bool(ids) and all(
                self._share_vars.get(i) and self._share_vars[i].get()
                for i in ids)

        def toggle_select_all():
            want = not _all_revealed_ticked()
            for i in _revealed():
                if i in self._share_vars:
                    self._share_vars[i].set(want)
            refresh_select_all_label()

        def refresh_select_all_label():
            all_on = _all_revealed_ticked()
            try:
                select_all_btn.configure(
                    text="Unselect all" if all_on else "Select all")
            except tk.TclError:
                pass

        def render_checkboxes():
            for w in inner.winfo_children():
                w.destroy()
            visible_notes = self.notes[:shown["n"]]
            rendered["ids"] = [n["id"] for n in visible_notes]
            for n in visible_notes:
                if n["id"] not in self._share_vars:
                    self._share_vars[n["id"]] = tk.BooleanVar(value=False)
                var = self._share_vars[n["id"]]
                title = (n["title"].strip() or "(untitled)")[:24]
                extra = " 📎" if n.get("attachments") else ""
                cb = tk.Checkbutton(inner, text=title + extra, variable=var,
                                    command=refresh_select_all_label,
                                    bg=self.colors["sidebar"], fg=self.colors["text"],
                                    selectcolor=self.colors["check_well"],
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
            # "Show 100 more" reveals notes that are not ticked, so a button
            # reading "Unselect all" would be wrong the moment the page grows.
            refresh_select_all_label()

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
        # The code needs room of its own; in a short window it is made here.
        self._fit_sidebar_panel()

    def _clear_inline_code(self, area):
        """Take a generated share code off the panel it was drawn on.

        The children are destroyed rather than the frame being
        pack_forget()ed, because that frame is packed once when the Share
        panel is built and is part of its layout -- the same gesture
        _generate_inline_share makes before redrawing into it.

        Deferred because the ✕ that calls this lives INSIDE the frame being
        emptied, so a synchronous loop destroys the button whose callback is
        still running. That is a documented Tk hazard rather than something
        measured here: a generated click cannot press this button in the test
        harness at all (`tk.Button` fires on release, and even a generated
        press+release does not reach it), so the synchronous version could not
        be shown to break. The editor's own ✕ avoids the same hazard a
        different way, by pack_forget()ing an ancestor instead of destroying
        itself. One idle cycle is a cheap way not to rely on luck.
        """
        def clear():
            for w in area.winfo_children():
                w.destroy()
            # The room the code took is given back (_fit_sidebar_panel).
            self._fit_sidebar_panel()
        self.after_idle(clear)

    def _render_inline_code(self, parent, code, count, had_attachments):
        """Show a generated code inline with a Copy button (used by share)."""
        noun = "note" if count == 1 else "notes"
        head = tk.Frame(parent, bg=self.colors["sidebar"])
        head.pack(fill="x", pady=(4, 2))
        # "chars" and not "characters" on purpose: this line lives in a 250px
        # sidebar at font 8, where the editor's roomier wording would clip.
        # The note count is information the editor's version cannot carry,
        # since that one is always about the open note.
        tk.Label(head, text=f"Code for {count} {noun} ({len(code)} chars):",
                 font=("Segoe UI", 8, "bold"), anchor="w",
                 bg=self.colors["sidebar"], fg=self.colors["text"]
                 ).pack(side="left")
        # The editor's code area has always had an ✕; this one could only be
        # dismissed by closing the whole Share panel.
        tk.Button(head, text="✕", command=lambda p=parent: self._clear_inline_code(p),
                  bg=self.colors["sidebar"], fg=self.colors["subtext"],
                  relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2", bd=0).pack(side="right")
        if had_attachments:
            tk.Label(parent, text=self.SHARE_ATTACHMENT_WARNING,
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

    def export_note_as_file(self, note, fmt):
        """Write one note to a standalone file the rest of the world reads.

        Two formats: HTML carries everything the note has (styles,
        colours, tables as real tables) and is the road to PDF (open,
        Ctrl+P) and Word (opens .html natively); plain text is the body
        as stored. Attachments never travel with a single-note export --
        that is what the full Backup export is for.

        This said "three formats" and described a Markdown one for a long
        time. `kinds` below has never held it and the menu has never
        offered it, so nothing ever raised -- it was a docstring that
        lied to the next reader rather than a crash waiting to happen,
        which is the harder kind to notice.
        """
        title = (note.get("title") or "").strip() or "Untitled note"
        kinds = {"html": ("HTML file", ".html"),
                 "txt": ("Text file", ".txt")}
        label, ext = kinds[fmt]
        # A title is prose; a filename is not. Strip what Windows forbids.
        safe = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", title).strip(" ._")[:60]
        path = filedialog.asksaveasfilename(
            title=f"Export “{title}” as a {label.lower()}",
            defaultextension=ext,
            initialfile=(safe or "note") + ext,
            filetypes=[(label, "*" + ext), ("All files", "*.*")])
        if not path:
            return
        content = self._note_export_content(note, fmt, title)
        # tmp-then-replace, like the backup zip: re-exporting over an
        # existing file plus a mid-write failure used to destroy it.
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, path)
        except (IOError, OSError) as exc:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            self.show_error("Export failed",
                            f"Couldn't write the file:\n{exc}")
            return
        self._show_toast(f"Exported to {os.path.basename(path)}")
        if note.get("attachments"):
            self.set_status(
                "Attached files aren't part of a note export — "
                "use Settings → Backup → Export for those.")
        # The file itself is the only honest preview of how the note
        # lays out -- the browser's (or Word's) fonts and wrapping,
        # not Tk's. Offer the look right away, so adjusting the note
        # and re-exporting is a tight loop.
        if self.ask_yes_no(
                "Open it now?",
                f"“{os.path.basename(path)}” was saved.\n\n"
                "Open it to see how the note lays out on the page?",
                icon="question"):
            try:
                os.startfile(path)
            except OSError:
                self.set_status(f"Saved to {path}")

    def _note_export_content(self, note, fmt, title):
        """One note rendered for one export format -- shared by the
        single-note export and the bulk export, so the two can never
        drift apart."""
        body = note.get("body", "")
        comments = (note.get("comments") or "").strip()
        # The checklist is its own section beside the body, like the
        # comments -- content, not chrome, so it exports with the note.
        checklist = note.get("checklist") or []
        if fmt == "html":
            fragment = note_to_html(body, note.get("formatting"),
                                    note.get("paragraphs"))
            if checklist:
                # Glyphs, not <input> boxes: a disabled form control is
                # at Word's mercy; a character renders everywhere.
                items = "\n".join(
                    "<div>{} {}</div>".format(
                        "☑" if it.get("done") else "☐",
                        escape(it.get("text", "")))
                    for it in checklist)
                fragment += ("<hr>\n<div><i>Checklist</i></div>\n" + items)
            if comments:
                fragment += ("<hr>\n<div><i>Comments</i></div>\n"
                             + note_to_html(comments))
            content = html_document(title, fragment)
        else:
            content = title + "\n\n" + body
            if checklist:
                content += "\n\nChecklist:\n" + "\n".join(
                    "[{}] {}".format("x" if it.get("done") else " ",
                                     it.get("text", ""))
                    for it in checklist)
            if comments:
                content += "\n\nComments:\n" + comments
            content += "\n"
        # A just-typed astral emoji is a lone UTF-16 surrogate in memory
        # (Tk hands it over that way), and the callers write this straight
        # to a utf-8 file — which raises UnicodeEncodeError, a ValueError
        # NOT caught by their (IOError, OSError) guards, crashing the
        # export. Mending here (the shared choke point) keeps the emoji and
        # covers both the single-note and bulk paths, matching the mend the
        # share-code and disk-write boundaries already do.
        return mend_surrogates(content)

    def share_current_note_as_code(self):
        """Generate a share code for the note currently open and show it inline
        in the editor (no pop-up), with a Copy button."""
        st = self.capture_editor_state()
        # The shared content test, minus the one field a code cannot
        # carry. SHAREABLE_FIELDS covers everything _editor_state_has_content
        # counts EXCEPT attachments (which travel separately, as the
        # had_attachments note below), so masking that one field asks
        # exactly the right question without writing a second list.
        #
        # The hand-rolled two-field version refused a checklist-only or
        # comments-only note with "Write something before copying a
        # code" -- about a note the app itself had just saved as real
        # content, and whose code would have carried that content fine.
        shareable = {k: v for k, v in st.items() if k != "attachments"}
        if not self._editor_state_has_content(shareable):
            self.set_status(
                "Nothing to share yet — a code carries a note's title, "
                "text, comments, checklist and repeat rule.")
            return
        # Built from SHAREABLE_FIELDS, never a hand-rolled list: this dict
        # once named seven fields by hand and silently dropped everything
        # added to sharing later -- a code generated HERE lost the
        # formatting, the paragraphs and the checklist that a code from
        # the multi-note Share panel (which passes whole notes) carried.
        note = {k: st.get(k) for k in SHAREABLE_FIELDS if st.get(k) is not None}
        # The date and repeat a save would store, not the raw field: a code
        # that carried "30.09.2026" delivered a date no save could keep,
        # and every edit to the note that arrived was lost on the far end.
        note["date"], note["recurrence"], _left_out = self._date_and_repeat_to_store()
        # The identity is the one shareable field that is NOT editor
        # content: it belongs to the note this editor has open, and
        # capture_editor_state has no reason to hold it. Building the
        # payload from the snapshot therefore dropped it silently -- the
        # same shape as the hand-rolled list above, one field later.
        #
        # Without it a code says "a note with these words" instead of
        # "this note", so the far end cannot recognise the copy it
        # already has and adds a second one: exactly what the field was
        # added to prevent, on the route a user is most likely to take.
        # A note that has never been saved has no identity yet and
        # correctly travels without one.
        open_note = (self.find_note(st.get("selected_note_id"))
                     if st.get("selected_note_id") is not None else None)
        if open_note and str(open_note.get("uid") or "").strip():
            note["uid"] = open_note["uid"]
        had_attachments = bool(st["attachments"])
        code = encode_share_code(note)
        # Render inline in the editor's code area.
        for w in self.editor_code_area.winfo_children():
            w.destroy()
        if not self._is_placed(self.editor_code_area):
            self.editor_code_area.pack(fill="x", padx=30, pady=(0, 20))
        self._render_editor_code(code, had_attachments)

    def _editor_follows_external_change(self, changed_ids):
        """Make the editor agree with notes that were rewritten behind it.

        A route that writes straight onto a stored note leaves the editor
        holding the version from before — and the editor's next save,
        which is one keystroke away, puts that version back. The change
        then vanishes with nothing to show it ever happened. Field-
        reported on the import route, where it is the LIKELY case rather
        than a corner one: the note you send out is the note you have
        open, so it is the one you are looking at when its code comes
        back.

        Callers flush the editor BEFORE they change anything, so what the
        user had typed is part of what the rescue copy holds instead of
        something this quietly drops.
        """
        if self.selected_note_id is None or self.selected_note_id not in changed_ids:
            return
        note = self.find_note(self.selected_note_id)
        if note is not None:
            self.open_note_in_tab(note, self.current_occurrence_date, flush=False)

    def _share_code_on_context_switch(self):
        """A different note is in the editor now, so the code shown under it
        is not this note's.

        Field-reported: generate a code, click another note, and the code
        stays sitting there — reading as though it belongs to the note now
        open. Copying it then shares the wrong note, and the mistake is
        invisible, because a code is a wall of characters nobody proofreads.
        Cleared at the same three points the find bar's match model is
        (see _find_on_context_switch) — for the same reason: it describes
        a note that is no longer on screen.
        """
        area = getattr(self, "editor_code_area", None)
        if area is None:
            return
        try:
            if self._is_placed(area):
                area.pack_forget()
            for w in area.winfo_children():
                w.destroy()
        except tk.TclError:
            # Teardown: the editor is going away and the code with it.
            pass

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
            tk.Label(parent, text=self.SHARE_ATTACHMENT_WARNING,
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

    def _open_imported_note_in_editor(self, shared_note, trimmed=False):
        """Load an imported single note into a fresh editor tab WITHOUT saving,
        so the user can review or edit it, then hit Save when ready. Crucially
        this stays a NEW note (no selected_note_id) so Save creates a fresh one."""
        note = normalize_note(shared_note)
        self.notebook.select(self.TAB_NOTES)
        # A clean new-note editor -- unless the person chose to stay on a
        # repeating day's edit, and then nothing here may touch the editor.
        if self.open_blank_tab() is False:
            return False
        # The identity it arrived with goes into its first save, unless a
        # note here already wears it. This editor used to drop it, so a
        # note sent out, edited elsewhere and sent back arrived as a
        # stranger and became a second copy. Read from what arrived, not
        # from `note`: normalize_note mints an identity for a note that
        # carries none, and "Add as a new note" removes it on purpose.
        uid = str(shared_note.get("uid") or "").strip()
        self._arrived_uid = (uid if uid and find_by_uid(self.notes, uid) is None
                             else "")

        self.title_entry.delete(0, "end")
        title = note.get("title", "")
        if title:
            self._insert_title(title)
            self.title_entry.config(fg=self.colors["text"])

        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", note.get("body", ""))
        self._apply_formatting(self.body_text, note.get("formatting", []))
        self._apply_paragraphs(self.body_text, note.get("paragraphs", []))
        self._render_table_grids()
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", note.get("comments", ""))

        self._show_date_in_field(note.get("date"))

        cat = note.get("category", "General")
        self.category_var.set(cat if cat in CATEGORY_COLORS else "General")

        self.current_note_color = note.get("color", "")
        self._update_color_swatch()

        self.write_recurrence_to_ui(note.get("recurrence"))

        # Bring the imported note's checklist along -- the one field this
        # loader used to skip, so a shared checklist vanished on import
        # even when the code carried it. Same idiom as loading a template.
        self._working_checklist = [
            {"text": it.get("text", ""), "done": bool(it.get("done"))}
            for it in note.get("checklist", []) if isinstance(it, dict)
        ]
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()
        if self._working_checklist and not self._checklist_open:
            self.toggle_checklist_section()
        else:
            self._sync_checklist_open_state()

        self.update_word_count()
        self.set_status(
            "Imported from code — trimmed to the app's size limits; review, "
            "then Save to keep it" if trimmed
            else "Imported from code — review, then Save to keep it")
        if trimmed:
            # The status bar is not enough for this one: it is a transient
            # line, and the autosave that follows the import overwrites it
            # with "Auto-saved ..." before anyone reads it (measured). A
            # note arriving SHORTER than it was sent is a change to the
            # user's data, so it gets the same channel the backup import
            # uses to report what it did.
            self.show_info(
                "Part of this note was left out",
                "The note in that code was larger than one note can hold, "
                "so it arrived trimmed to the app's limits "
                f"({MAX_CHECKLIST_ITEMS} checklist items, "
                f"{MAX_ATTACHMENTS} files, "
                f"{MAX_FORMATTING_SPANS} styled spans, "
                f"{MAX_SPANS_PER_LINE} of them on any one line).\n\n"
                "Nothing of yours was touched — this is only about what "
                "arrived. Review it before saving.")
        return True

    def import_data(self):
        """Import a previously exported .zip. Notes are MERGED into your
        current list (never overwritten) — safe to use even if this device
        already has notes of its own.

        The slow parts (extracting the zip, copying attachments back) run on
        a background thread, same as export — for a backup with a lot of
        attachments this used to visibly freeze the app while it worked."""
        # Same one-at-a-time guard as export_data (audit Z05-F05).
        if self._export_state is not None or self._import_state is not None:
            self.set_status("An export or import is already running — "
                            "let it finish first.")
            return
        zip_path = filedialog.askopenfilename(
            title="Choose a notes backup (.zip) to import",
            filetypes=[("Zip files", "*.zip")]
        )
        if not zip_path:
            return

        confirm = self.ask_yes_no(
            "Import notes",
            "This will ADD the notes from that backup to your current list. "
            "Nothing you have is removed, and a note you already have is "
            "only replaced if you choose to update it.\n\n"
            "Continue?"
        )
        if not confirm:
            return

        # "copied": the files the worker put in the attachments folder, so
        # an import the window closes on can take them back out again (see
        # _settle_background_work_at_close).
        self._import_state = {"phase": "extracting", "current": 0, "total": 1,
                              "done": False, "error": None,
                              "temp_dir": None, "imported_notes": None,
                              "copied": []}
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
                    state["error"] = "This .zip doesn't look like a Note Organizer backup."
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
                # Templates and trash ride along when the backup has them
                # (older backups don't — both stay optional, and a bad
                # file skips quietly: the notes are the payload).
                for extra, key in (("templates.json", "imported_templates"),
                                   ("trash.json", "imported_trash")):
                    extra_path = os.path.join(temp_dir, extra)
                    if os.path.exists(extra_path):
                        try:
                            with open(extra_path, "r", encoding="utf-8") as f:
                                loaded = json.load(f)
                            if isinstance(loaded, list):
                                state[key] = loaded
                        except (json.JSONDecodeError, IOError, OSError):
                            pass
                # The backup's settings.json has always been IN the zip and
                # was never read back, so every imported note whose category
                # did not exist on this device was silently re-filed under
                # "General" by normalize_note -- the whole filing system of
                # a restored notebook, gone, with "Import complete" as the
                # only feedback. Only the categories are taken; the rest of
                # the file is this device's own business.
                settings_path = os.path.join(temp_dir, "settings.json")
                if os.path.exists(settings_path):
                    try:
                        with open(settings_path, "r", encoding="utf-8") as f:
                            loaded = json.load(f)
                        cats = loaded.get("categories") if isinstance(loaded, dict) else None
                        if isinstance(cats, dict):
                            state["imported_categories"] = cats
                        # The calendar's day colours and emoji markers are
                        # user data the backup carries for the same reason
                        # categories are — dropped on restore, a decorated
                        # calendar came back bare with no word about it.
                        # Raw dicts only here (worker thread, no widgets);
                        # validation happens at the merge on the main
                        # thread.
                        if isinstance(loaded, dict):
                            for decor_key in ("day_colors", "day_emoji"):
                                decor = loaded.get(decor_key)
                                if isinstance(decor, dict):
                                    state["imported_" + decor_key] = decor
                    except (json.JSONDecodeError, IOError, OSError, AttributeError):
                        pass

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
                            # Copy beside, replace whole: the process dying
                            # mid-copy used to leave a TRUNCATED attachment
                            # here — and this very exists-guard then made
                            # every re-import skip it, turning transient
                            # damage permanent.
                            part = dest + ".part"
                            try:
                                shutil.copy2(
                                    os.path.join(imported_attachments_dir, filename), part)
                                os.replace(part, dest)
                                state["copied"].append(filename)
                            except (IOError, OSError):
                                try:
                                    os.remove(part)
                                except OSError:
                                    pass
                                # non-critical — the note metadata still gets imported
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

        self._start_io_worker(worker)
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

        # Bring the backup's categories in FIRST — before the duplicate
        # scan below, not merely before the final merge loop: the scan
        # normalizes every incoming note, and normalize_note re-files a
        # note whose category is still unknown to General. Scanned in
        # that state, a distinct note could read as a duplicate of a
        # local General note and be silently skipped, while this dialog
        # claimed its category matched. Additive — a name this device
        # already uses keeps its own colour — and each colour passes
        # sanitize_color, because a backup's settings.json is as
        # untrusted as any other imported file and a garbage colour
        # reaches a Tk configure in whatever render touches it.
        # In MEMORY only, for now. The scan below needs them, but the user
        # has not agreed to anything yet -- persisting here meant that
        # answering "Cancel" at the duplicate dialog still left a
        # stranger's categories installed in the sidebar, saved to disk,
        # with no note to explain them. What is written is decided after
        # the dialog; this list is what gets rolled back if it is not.
        added_names = []
        refused_categories = 0
        for name, color in list(
                (state.get("imported_categories") or {}).items())[:MAX_CATEGORIES]:
            color = sanitize_color(color)
            name = name.strip() if isinstance(name, str) else ""
            if not (name and color) or name in CATEGORY_COLORS:
                continue
            # Skipped whole, never cut short. Cutting a name to the limit
            # was the very mistake load_categories records: the notes
            # filed under the full name then match nothing, and go to
            # General. Past the 200th category the next launch would drop
            # it anyway, with the same result, so the door refuses what
            # the loader will not keep -- and the dialog says so.
            if category_name_refusal(name) is not None:
                refused_categories += 1
                continue
            CATEGORY_COLORS[name] = color
            added_names.append(name)
        added_categories = len(added_names)

        def _undo_category_merge():
            """Take back what was never agreed to."""
            for _n in added_names:
                CATEGORY_COLORS.pop(_n, None)
            added_names.clear()

        # Identity first, exactly as the share-code route asks it.
        proceed, valid_notes, updates, unchanged = self._take_known_notes(
            valid_notes, "backup")
        if not proceed:
            _undo_category_merge()
            # The extracted backup goes with it, as it does when the
            # duplicate question below is cancelled; this exit left the
            # whole unpacked zip in the temp folder.
            shutil.rmtree(temp_dir, ignore_errors=True)
            return
        existing_keys = self._dup_keys_after(updates)
        fresh = [n for n in valid_notes if _dup_key(normalize_note(n)) not in existing_keys]
        dupe_count = len(valid_notes) - len(fresh)
        to_import = valid_notes
        if dupe_count > 0:
            if fresh:
                choice = self._themed_dialog(
                    "Possible duplicates",
                    f"{dupe_count} of the {len(valid_notes)} note(s) in this backup "
                    "look identical to notes you already have (same title, "
                    "text, comments, category, checklist and repeat rule).",
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
                _undo_category_merge()
                shutil.rmtree(temp_dir, ignore_errors=True)
                return
            if choice == "skip":
                to_import = fresh

        # Agreed to: only now does the category merge reach disk and the
        # sidebar. (It happened in memory above, because the duplicate
        # scan had to see it -- normalize_note re-files a note whose
        # category is still unknown.)
        if added_categories:
            persist_categories()
            self.refresh_category_widgets()
        # ...and only now are the notes you already have updated. Before
        # the claimed-file scan below, because an update can bring files in.
        updated = self._apply_known_updates(updates, "backup")

        # Calendar day colours and emoji markers ride the backup's
        # settings.json exactly like categories do, and used to be dropped
        # the same way. Additive — a day this device already decorated
        # keeps its own decoration — and validated on the way in: the
        # colours through sanitize_color, the markers as up-to-3 non-empty
        # strings, matching the picker's own cap.
        restored_decor = 0
        for d, c in (state.get("imported_day_colors") or {}).items():
            c = sanitize_color(c)
            if isinstance(d, str) and c and d not in self.day_colors:
                self.day_colors[d] = c
                restored_decor += 1
        for d, v in (state.get("imported_day_emoji") or {}).items():
            if isinstance(d, str) and d not in self.day_emoji:
                if isinstance(v, str) and v:
                    v = [v]  # the pre-list format older backups carry
                if isinstance(v, list):
                    kept = [e for e in v if isinstance(e, str) and e][:3]
                    if kept:
                        self.day_emoji[d] = kept
                        restored_decor += 1
        if restored_decor:
            save_setting("day_colors", dict(self.day_colors))
            save_setting("day_emoji", dict(self.day_emoji))

        # Files already spoken for — by a note we're keeping (re-importing
        # your own backup lands here) or by an earlier note in this same
        # import. An imported note that references one of these would share
        # the physical file, so deleting either note would delete the
        # other's file. Give the import its own copy instead. Same fix as
        # duplicate_note; the copy source is the file the copy-loop above
        # already placed in the attachments folder.
        # The trash's files count as claimed too: re-importing your own
        # backup used to append a twin trash entry sharing the original's
        # physical file, and delete-forever on either destroyed the
        # other's attachment.
        claimed = {a.get("stored_as")
                   for n in (self.notes + self.trash)
                   if isinstance(n, dict)
                   for a in (n.get("attachments") or [])
                   if isinstance(a, dict)}
        next_id = max([n["id"] for n in self.notes], default=0) + 1
        for note in to_import:
            note = normalize_note(note)
            for a in note.get("attachments", []):
                if not isinstance(a, dict):
                    continue
                name = a.get("stored_as")
                if name in claimed:
                    new_name = copy_attachment_file(name)
                    if new_name:
                        a["stored_as"] = new_name
                        claimed.add(new_name)
                elif name:
                    claimed.add(name)
            note["id"] = next_id
            next_id += 1
            self.notes.append(note)

        # Templates and trash from the backup merge ADDITIVELY — nothing
        # local is replaced or removed (Z05-F07: both used to be left out
        # of the backup entirely, lost on every device move).
        added_templates = 0
        for tpl in (state.get("imported_templates") or []):
            if not isinstance(tpl, dict):
                continue
            tpl = normalize_template(tpl)
            if tpl.get("name") and not any(
                    t.get("name") == tpl.get("name") for t in self.templates):
                self.templates.append(tpl)
                added_templates += 1
        if added_templates:
            save_templates(self.templates)
        added_trash = 0
        # Skipped with nobody asked, so the question is identity of
        # content, not resemblance: _dup_key ignores the date, the
        # attachments and the per-day edits, and a backup's trashed note
        # differing from a local one in exactly those was dropped -- the
        # only copy of it gone, on a route that says it adds and never
        # removes. content_signature is the strict answer every automatic
        # removal in the app asks.
        existing_trash_keys = {content_signature(normalize_note(e))
                               for e in self.trash if isinstance(e, dict)}
        for entry in (state.get("imported_trash") or []):
            if not isinstance(entry, dict):
                continue
            raw_deleted = entry.get("deleted_at")
            # Whitelist through normalize_note like every other imported
            # dict: a foreign trash.json carrying deleted_at=5 used to
            # reach the Trash panel raw and crash its sort. deleted_at is
            # re-attached afterwards (normalize drops it), as a str only.
            entry = normalize_note(entry)
            entry["deleted_at"] = (raw_deleted
                                   if isinstance(raw_deleted, str) else "")
            key = content_signature(entry)
            if key in existing_trash_keys:
                # Re-importing your own backup must not double the trash.
                continue
            existing_trash_keys.add(key)
            # Same claimed-file discipline as the notes above: a trashed
            # entry pointing at a file an ACTIVE note owns would, on its
            # later purge, delete that file out from under the note.
            atts = []
            for a in (entry.get("attachments") or []):
                if not isinstance(a, dict):
                    continue
                a = dict(a)
                name = a.get("stored_as")
                if name in claimed:
                    new_name = copy_attachment_file(name)
                    if new_name:
                        a["stored_as"] = new_name
                        claimed.add(new_name)
                elif name:
                    claimed.add(name)
                atts.append(a)
            entry["attachments"] = atts
            self.trash.append(entry)
            added_trash += 1
        if added_trash:
            save_trash(self.trash)

        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        shutil.rmtree(temp_dir, ignore_errors=True)

        skipped_note = f" ({dupe_count} duplicate(s) skipped)" if dupe_count and to_import is not valid_notes else ""
        extras_note = ""
        parts = []
        if added_categories:
            parts.append(f"{added_categories} category/categories")
        if restored_decor:
            parts.append(f"{restored_decor} calendar day marking(s)")
        if added_templates:
            parts.append(f"{added_templates} template(s)")
        if added_trash:
            parts.append(f"{added_trash} trashed note(s)")
        if parts:
            extras_note = " Also restored " + " and ".join(parts) + "."
        if refused_categories:
            extras_note += (
                f"\n\n{refused_categories} of the backup's categories could "
                f"not be added (a name over {MAX_CATEGORY_NAME} characters, "
                f"or more than {MAX_CATEGORIES} categories in all), so the "
                "notes filed under them are in General.")
        # The notes it updated and the ones it found unchanged are counted
        # too: "Added 0 note(s)" after an update read as "nothing
        # happened", and invited the second import that used to destroy
        # this device's newer text.
        known_note = ""
        if updated:
            known_note += (f" Updated {updated} note(s) you already had "
                           "(“↩ Restore previous” undoes each one).")
        if unchanged:
            known_note += f" {unchanged} note(s) were already here, unchanged."
        self.show_info("Import complete",
                       f"Added {len(to_import)} note(s) from the backup."
                       f"{known_note}{skipped_note}{extras_note}")

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

    # Tk's own rule for when two presses make one double-click (tkBind.c,
    # NEARBY_MS and NEARBY_PIXELS). Kept here rather than asked of Tk,
    # because Tk pairs two presses only when both land on the SAME widget.
    _DOUBLE_CLICK_MS = 500
    _DOUBLE_CLICK_PX = 5

    def _second_press_of_double_click(self, event):
        """True when *event*, a press on a button that removes its own row,
        is the second half of a double-click.

        Many people double-click every button. The first click removes the
        row and the row below slides up into its place, so the second press
        lands on a DIFFERENT button -- the next row's -- and removed that
        one too, while the toast's single Undo offered back only the second
        (the first was gone for good). Tk cannot tell: it makes a
        double-click of two presses on one widget only. So the pairing is
        done here, by Tk's own rule, across every such button: a press
        within 500 ms and 5 px of the previous one is the echo of the same
        gesture. Every call records its press. Bind it to the press, so
        the second one never arms the button::

            button.bind("<ButtonPress-1>", lambda e: "break"
                        if self._second_press_of_double_click(e) else None,
                        add="+")

        A generated event carries no time; the clock stands in for it.
        """
        stamp = getattr(event, "time", 0) or int(time.monotonic() * 1000)
        here = (stamp, getattr(event, "x_root", 0), getattr(event, "y_root", 0))
        last = getattr(self, "_row_removal_press", None)
        self._row_removal_press = here
        if last is None:
            return False
        # Event times are milliseconds on a 32-bit clock that wraps.
        elapsed = (here[0] - last[0]) & 0xFFFFFFFF
        return (elapsed <= self._DOUBLE_CLICK_MS
                and abs(here[1] - last[1]) <= self._DOUBLE_CLICK_PX
                and abs(here[2] - last[2]) <= self._DOUBLE_CLICK_PX)

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
            # Size the list to match the calculator before showing it.
            self._match_checklist_to_calculator()
            self.checklist_section.pack(fill="x", pady=(0, 8),
                                        after=self.checklist_btn)
            self._checklist_open = True
            self.checklist_btn.config(text="☑ Checklist  ▲")
            # The rows are built on opening (see _render_checklist_items);
            # rows already drawn from this very list need no rebuild.
            if _checklist_rows_current(getattr(self, "_checklist_drawn", None),
                                       self._get_checklist(),
                                       getattr(self, "theme_name", None)):
                self._update_checklist_progress()
            else:
                self._render_checklist_items()

    def _match_checklist_to_calculator(self):
        """Size the checklist list area so the whole box matches the
        calculator beside it -- computed at RUNTIME from the calculator's
        own requested height, not a fixed number.

        The calculator's height is platform-dependent (font metrics differ
        between machines), so a value tuned on one machine left the
        checklist 14px short on the CI runner. winfo_reqheight reports each
        section's wanted height without either panel having to be open, so
        the two can be made genuinely equal wherever the app runs:

            list_compact  = calc height (history closed)  - the checklist's
                            non-list parts
            list_expanded = list_compact + the calculator's history block

        so the boxes match closed-to-closed AND open-to-open."""
        try:
            self.update_idletasks()
            calc_h = self.calculator_section.winfo_reqheight()
            non_list = (self.checklist_section.winfo_reqheight()
                        - int(self._checklist_list_wrap.cget("height")))
            hist_delta = self.calculator_history_section.winfo_reqheight()
            # Guard against a not-yet-realised layout reporting a stub 1px:
            # keep the fallback constants until the real numbers arrive.
            if calc_h > 50 and non_list > 0:
                self._checklist_list_compact = max(120, calc_h - non_list)
                self._checklist_list_expanded = (
                    self._checklist_list_compact + max(40, hist_delta))
            self._checklist_list_wrap.configure(
                height=(self._checklist_list_expanded if self._checklist_expanded
                        else self._checklist_list_compact))
        except (tk.TclError, AttributeError, ValueError):
            pass

    def _toggle_checklist_expand(self):
        """Grow or shrink the checklist list area. Expanded, the whole box
        matches the calculator with its history open; compact, it matches
        the calculator closed. The scroll works in both — this is extra
        reach when the list is long, not a replacement for scrolling."""
        self._checklist_expanded = not getattr(self, "_checklist_expanded", False)
        self._checklist_list_wrap.configure(
            height=(self._checklist_list_expanded if self._checklist_expanded
                    else self._checklist_list_compact))
        self.checklist_expand_btn.config(
            text="Collapse ⌃" if self._checklist_expanded else "Expand ⌄")

    # Fallback sizes, used only until _match_checklist_to_calculator has
    # measured the real ones at runtime (see there for why a fixed number
    # cannot stay equal to the calculator across platforms). These are the
    # values measured on the development machine (calculator 359px closed,
    # 459px open; ~94px of non-list parts).
    CHECKLIST_LIST_COMPACT = 265
    CHECKLIST_LIST_EXPANDED = 365

    def _build_checklist_section(self):
        """Build the (initially hidden) checklist UI: a scrollable list of items
        plus an entry to add new ones and Save/Close buttons."""
        sec = self.checklist_section
        self._checklist_expanded = False
        # Runtime-measured sizes start at the fallback constants; the first
        # open recomputes them from the calculator's actual height.
        self._checklist_list_compact = self.CHECKLIST_LIST_COMPACT
        self._checklist_list_expanded = self.CHECKLIST_LIST_EXPANDED
        # Header: just the progress label. No in-panel Close button -- the
        # "☑ Checklist ▲" bar above already toggles it shut.
        head = tk.Frame(sec, bg=self.colors["card"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        self.checklist_progress_lbl = tk.Label(
            head, text="Checklist", bg=self.colors["card"], fg=self.colors["subtext"],
            font=("Segoe UI", 9, "bold"), anchor="w")
        self.checklist_progress_lbl.pack(side="left")

        # Scrollable list of items.
        wrap = tk.Frame(sec, bg=self.colors["card"],
                        height=self.CHECKLIST_LIST_COMPACT)
        wrap.pack(fill="x", padx=10, pady=(0, 4))
        wrap.pack_propagate(False)
        self._checklist_list_wrap = wrap
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

        # Expand/Collapse bar, the same full-width flat bar the note body and
        # comments boxes carry (_add_text_resize_toggle), so the three read
        # the same. Directly under the list, like those sit under their box.
        self.checklist_expand_btn = tk.Button(
            sec, text="Expand ⌄", command=self._toggle_checklist_expand,
            relief="flat", cursor="hand2", font=("Segoe UI", 8, "bold"), bd=0)
        self.track_theme(self.checklist_expand_btn, bg="card", fg="subtext",
                         activebackground="card", activeforeground="text")
        self.checklist_expand_btn.pack(fill="x", padx=10, pady=(0, 2))

        # Add-item row.
        add_row = tk.Frame(sec, bg=self.colors["card"])
        add_row.pack(fill="x", padx=10, pady=(2, 4))
        self.checklist_add_var = tk.StringVar()
        entry = tk.Entry(add_row, textvariable=self.checklist_add_var, relief="flat",
                         font=("Segoe UI", 10), bg=self.colors["sidebar"],
                         fg=self.colors["text"], insertbackground=self.colors["text"])
        self._guard_entry_astral(entry)
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        entry.bind("<Return>", lambda e: self._add_checklist_item())
        self._add_paste_menu(entry)
        self.checklist_add_entry = entry
        # Long-lived: without tracking, the caret (insertbackground) froze
        # on the build-time palette — invisible after a dark<->light switch.
        self.track_theme(entry, bg="sidebar", fg="text",
                         insertbackground="text")
        # ASCII "+", like every other add-button in the app. A fullwidth
        # U+FF0B renders noticeably wider, and this one sits a few
        # centimetres from the attachments panel's "+ Add file".
        tk.Button(add_row, text="+ Add", command=self._add_checklist_item,
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
        """Redraw the checklist rows from the working list -- while the
        section is OPEN. Closed, no row is built: a note switch collapses
        the section anyway, and each row is four widgets (a frame, a tick
        box, a label, a bin), so building them for a closed section was
        pure cost -- a 50-item note paid ~200 widgets on every open.
        toggle_checklist_section builds them the moment it opens. The
        rows drawn are recorded (see _checklist_rows_current), so a
        change can touch the one row it concerns instead of all of them.
        """
        if not hasattr(self, "checklist_items_frame"):
            return
        self._update_checklist_progress()
        if not getattr(self, "_checklist_open", False):
            # What stands in the closed frame no longer matches the list;
            # the next open redraws it.
            self._checklist_drawn = None
            return
        for w in self.checklist_items_frame.winfo_children():
            w.destroy()
        items = self._get_checklist()
        if not items:
            tk.Label(self.checklist_items_frame, text="No items yet — add one below.",
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 9), anchor="w").pack(fill="x", padx=4, pady=6)
        self._checklist_drawn = {
            "items": items, "theme": getattr(self, "theme_name", None),
            "rows": [self._build_checklist_row(idx, item)
                     for idx, item in enumerate(items)]}

    def _build_checklist_row(self, idx, item):
        """One row, packed at the end. Returns its record for the drawn
        list: ``[item, row frame, (text, done) as drawn]``."""
        row = tk.Frame(self.checklist_items_frame, bg=self.colors["card"])
        row.pack(fill="x", pady=1)
        record = [item, row, (item.get("text", ""), bool(item.get("done")))]
        var = tk.IntVar(value=1 if item.get("done") else 0)

        def on_toggle():
            item["done"] = bool(var.get())
            record[2] = (item.get("text", ""), item["done"])
            self._update_checklist_progress()
            self._restyle_checklist_label(lbl, item["done"])
            self._schedule_autosave()

        cb = tk.Checkbutton(row, variable=var, command=on_toggle,
                            bg=self.colors["card"], activebackground=self.colors["card"],
                            selectcolor=self.colors["check_well"], bd=0,
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
            items = self._get_checklist()
            # The index is read from the list now rather than taken from
            # the idx this row was built with: the pair handed to the undo
            # has to be a position IN THIS LIST. Found by IDENTITY --
            # list.index() finds the first EQUAL item, and two items reading
            # the same are two items; now that a delete takes away only its
            # own row, the wrong one would leave this row standing, tied to
            # an item no longer in the list.
            index = next((i for i, it in enumerate(items) if it is item),
                         None)
            if index is None:
                return
            drawn = getattr(self, "_checklist_drawn", None)
            in_step = (getattr(self, "_checklist_open", False)
                       and _checklist_rows_current(
                           drawn, items, getattr(self, "theme_name", None)))
            items.pop(index)
            if in_step and items:
                # This row goes, the others stay: rebuilding every row
                # took over two seconds at 200 items.
                drawn["rows"].pop(index)
                row.destroy()
                self._update_checklist_progress()
            else:
                self._render_checklist_items()
            self._schedule_autosave()
            # The one thing that could be taken off a note with no way
            # back at all: Ctrl+Z reaches the Text widgets (edit_undo),
            # and a checklist is a list of dicts beside them, so nothing
            # in the editor could return an item. A toast rather than a
            # confirmation because the app's rule is that a destructive
            # action is confirmed in proportion to how recoverable it is
            # -- and a question in front of every tick-list tidy-up would
            # be worse than the risk it guards.
            label = _truncate(item.get("text", ""), 40)
            self._show_toast(
                f"Removed “{label}”" if label else "Checklist item removed",
                action=lambda: self._undo_checklist_delete(items, index, item))

        bin_btn = tk.Button(row, text="🗑", command=delete, relief="flat",
                            cursor="hand2", bg=self.colors["card"],
                            fg=self.colors["danger"], font=("Segoe UI", 9),
                            bd=0)
        bin_btn.pack(side="right")
        # A double-click's second press lands on the NEXT row's bin, slid
        # up into this one's place: it must not remove that row too.
        bin_btn.bind("<ButtonPress-1>",
                     lambda e: "break"
                     if self._second_press_of_double_click(e) else None,
                     add="+")
        return record

    def _restyle_checklist_label(self, lbl, done):
        """Dim + strike-through style for completed items (overstrike font).

        Two fonts shared by every row, made once from the first label's
        font -- a new Font per call was one more Tk font object for every
        row built and every tick."""
        fg = self.colors["subtext"] if done else self.colors["text"]
        try:
            fonts = getattr(self, "_checklist_fonts", None)
            if fonts is None:
                plain = tkfont.Font(font=lbl.cget("font"))
                plain.configure(overstrike=0)
                struck = tkfont.Font(font=lbl.cget("font"))
                struck.configure(overstrike=1)
                fonts = self._checklist_fonts = (plain, struck)
            lbl.configure(font=fonts[1] if done else fonts[0], fg=fg)
        except Exception:
            lbl.configure(fg=fg)

    def _take_pending_checklist_item(self):
        """Add what sits typed in the checklist's add box to this note's list,
        as leaving the note requires (see _flush_autosave). Unlike the Add
        button it leaves the keyboard where it is: the person is on their
        way somewhere else."""
        var = getattr(self, "checklist_add_var", None)
        text = var.get().strip() if var is not None else ""
        if not text:
            return
        self._get_checklist().append({"text": text, "done": False})
        var.set("")
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()

    def _add_checklist_item(self):
        text = self.checklist_add_var.get().strip()
        if not text:
            return
        items = self._get_checklist()
        drawn = getattr(self, "_checklist_drawn", None)
        in_step = (getattr(self, "_checklist_open", False)
                   and _checklist_rows_current(
                       drawn, items, getattr(self, "theme_name", None)))
        item = {"text": text, "done": False}
        items.append(item)
        self.checklist_add_var.set("")
        if in_step:
            # One new row, not the whole list again: rebuilding every row
            # took over two seconds per add at 200 items.
            if not drawn["rows"]:
                for w in self.checklist_items_frame.winfo_children():
                    w.destroy()          # the "No items yet" line
            drawn["rows"].append(self._build_checklist_row(len(items) - 1,
                                                           item))
            self._update_checklist_progress()
        else:
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
        # Also drop the expand back to compact — the expanded height is a
        # transient view choice, not part of the note, so it shouldn't
        # carry from one note into the next.
        if getattr(self, "_checklist_expanded", False):
            self._checklist_expanded = False
            if hasattr(self, "_checklist_list_wrap"):
                self._checklist_list_wrap.configure(
                    height=self._checklist_list_compact)
            if hasattr(self, "checklist_expand_btn"):
                self.checklist_expand_btn.config(text="Expand ⌄")
        if hasattr(self, "checklist_btn"):
            self._update_checklist_progress()

    # ---------- In-note calculator ----------

    def update_word_count(self):
        """Refresh the words · characters readout for the note body.

        Tables are counted by what the user wrote in them, not by their
        plumbing: every pipe used to count as a "word", so an empty 3x3
        table claimed twelve words and inflated the reading time.
        """
        if not hasattr(self, "word_count_lbl"):
            return
        text = self.body_text.get("1.0", "end-1c")
        if core_tables.CELL in text:
            text = core_tables.content_text(text)
        chars = len(text)
        words = len(text.split())
        if chars == 0:
            self.word_count_lbl.config(text="")
        else:
            w = "word" if words == 1 else "words"
            c = "character" if chars == 1 else "characters"
            # The reading estimate goes on its own line under the counts:
            # it answers a different question ("have I got time for this?"
            # rather than "how much have I written?") and reads as an aside
            # rather than as more of the same figure.
            line = f"{words} {w} · {chars} {c}"
            estimate = reading_time(words)
            self.word_count_lbl.config(
                text=f"{line}\n{estimate}" if estimate else line)

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
                                pack_kwargs=None, remember_key=None):
        """Add an Expand/Collapse toggle under a Text box. One click switches its
        height (in rows) between compact and expanded — same flicker-free pattern
        as the Settings panels, no dragging. Also disables the box's expand fill
        so the height setting actually takes effect.

        Dragging a box's edge was tried for the note body and abandoned: the
        editor sits inside a scrolling canvas that recomputes its scrollregion
        whenever its contents resize, and a drag sends that dozens of times a
        second. The canvas fell behind, leaving widgets drawn at stale
        positions. One click is one resize, so it cannot happen.

        Pass *remember_key* to store the chosen state in settings under that
        name; without one the box opens compact every time, which is right for
        a box whose size is incidental and wrong for one someone chose.
        """
        # Nothing is done to the box's packing here. There used to be a
        # pack_configure(expand=False), meant to keep the row count in charge
        # of the height -- but both boxes are packed with side="left", where
        # expand hands out *horizontal* space, not vertical. It never affected
        # the height, and it left the box at its default width of eighty
        # characters inside a much wider frame: 752px of 1027px, with the text
        # wrapping halfway across and no way to make it fill the rest.
        # The height is governed by the frame around the box, which sizes
        # itself to what the box asks for, and the row count sets that.
        text_widget.configure(height=compact)

        start = False
        if remember_key:
            start = bool(get_setting(remember_key, False, bool))
        state = {"expanded": start}
        btn = tk.Button(host, relief="flat", font=("Segoe UI", 8, "bold"),
                        cursor="hand2", bd=0)
        self.track_theme(btn, bg="bg", fg="subtext",
                         activebackground="bg", activeforeground="text")

        def apply():
            try:
                text_widget.configure(height=expanded if state["expanded"] else compact)
            except tk.TclError:
                pass
            btn.configure(text=("Collapse ⌃" if state["expanded"] else "Expand ⌄"))

        def toggle():
            state["expanded"] = not state["expanded"]
            apply()
            if remember_key:
                save_setting(remember_key, state["expanded"])

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
            btn.configure(text=("Collapse ⌃" if state["expanded"] else "Expand ⌄"))

        def toggle():
            state["expanded"] = not state["expanded"]
            apply()

        btn.configure(command=toggle)
        apply()
        return btn



    def _bind_wheel_tree_if_unbound(self, root, handler):
        """Bind a wheel handler to a widget subtree, but skip widgets that
        already have a MouseWheel binding (their own scroll list keeps priority)."""
        if not root.bind("<MouseWheel>"):
            root.bind("<MouseWheel>", handler)
        for child in root.winfo_children():
            self._bind_wheel_tree_if_unbound(child, handler)


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
        self._guard_entry_astral(entry)
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





    def _rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        """Draw a rounded rectangle on a canvas and return the polygon id."""
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)








    @staticmethod
    def _widget_alive(widget):
        try:
            return bool(widget.winfo_exists())
        except tk.TclError:
            return False

    def track_theme(self, widget, **option_map):
        self.themed_widgets.append((widget, option_map))
        # A section rebuilt on every visit registers its widgets again each
        # time, and only a theme switch dropped the dead ones: a session
        # that never switched theme kept every widget it ever drew (339 ->
        # 809 entries over 175 Settings visits, measured). Pruned whenever
        # the registry has doubled since the last prune -- a constant cost
        # per call, averaged.
        if len(self.themed_widgets) >= 2 * getattr(self, "_themed_pruned_at", 256):
            self._prune_themed_widgets()
        widget.configure(**{opt: self.colors[key] for opt, key in option_map.items()})
        return widget

    def _prune_themed_widgets(self):
        """Drop the registry's entries for widgets that no longer exist."""
        self.themed_widgets = [
            (w, m) for w, m in self.themed_widgets
            if self._widget_alive(w)]
        self._themed_pruned_at = max(256, len(self.themed_widgets))


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
        # The window's own frame last, after the contents: the caption and
        # the icon are the outermost things on screen, and changing them
        # before the widgets underneath made the switch look like it
        # happened twice (field-reported: "the top bar changes first and
        # only then the one below it").
        self.after_idle(self._paint_title_bar)
        self.after_idle(self._set_window_icon)
        # Prune dead entries first: the rebuilt Settings panels re-track
        # their dropdowns and buttons on every visit, and the registry
        # kept the destroyed ones forever — the note-card leak class, at
        # the registry level (each dead entry cost a caught TclError on
        # every switch, growing without bound).
        self._prune_themed_widgets()
        for widget, option_map in self.themed_widgets:
            try:
                widget.configure(**{opt: self.colors[key] for opt, key in option_map.items()})
            except tk.TclError:
                pass
        self._refresh_placeholder_colors()
        # The drawn tables carry their colours in canvas items; without a
        # rebuild they kept the OLD theme until the next edit touched them.
        # The commit first: render's contract is "never while focus is in
        # a cell", and a theme switched mid-typing otherwise destroyed the
        # editor's canvas under it -- the keystrokes went with it.
        self._commit_cell_editor()
        self._render_table_grids()
        # Text highlights are painted blended toward the theme surface
        # (the cells' own recipe); the new surface needs a re-blend.
        if hasattr(self, "body_text"):
            self._retint_highlight_tags(self.body_text)
        # The editor's quick toggle shows where a press would take you.
        if hasattr(self, "editor_theme_btn"):
            try:
                self.editor_theme_btn.configure(
                    text="☀" if self.theme_name in DARK_THEMES else "🌙")
            except tk.TclError:
                pass
        self.refresh_weekday_buttons()
        self.on_end_mode_changed()
        self.style_notebook()
        # Statistics is deliberately NOT re-rendered here: a theme switch
        # changes no statistic -- only the palette, which
        # _recolor_stragglers below handles, and the panel's next render
        # rebuilds it in the new palette (it updates its figures in place
        # otherwise). It's on the Settings page, i.e. exactly where the user
        # is standing when they switch themes, so rebuilding it there was
        # visible churn for no new information. Real data changes still
        # redraw it through refresh_note_list(), which is unchanged.
        #
        # Same reasoning for the calendar: rebuilding every day cell is
        # pointless while the calendar isn't even on screen. That test
        # used to be written out here, and here only -- it now lives
        # inside render_calendar() itself, so every caller gets it and
        # this one simply asks for a render like all the others.
        self.render_calendar()
        # Safety net: catch any widget that slipped through the registered list
        # (e.g. built once and never rebuilt) by swapping known theme colors from
        # the OTHER theme to the current one. This guarantees a clean flip.
        self._recolor_stragglers()
        # The Settings nav glyphs are shapes drawn onto small canvases, and
        # nothing above reaches items drawn on a canvas -- track_theme only
        # restores the canvas background. Repaint them explicitly, the same
        # way the theme picker refreshes its own preview cards.
        self._recolor_settings_nav_icons()
        # The alignment icons are canvas-drawn for the same reason and need
        # the same treatment; this repaints their bars along with restoring
        # every paragraph button's pressed state in the new palette.
        self._refresh_list_buttons()
        # Recolour the note cards in place rather than calling
        # refresh_note_list(), which destroys and rebuilds every card. That
        # rebuild was ~85ms of a ~121ms theme switch and made the list
        # visibly empty and refill -- the theme-switch flicker. Nothing here
        # depends on the note DATA having changed (it hasn't; only the
        # palette did), so there is nothing to re-read.
        #
        # Deliberately AFTER _recolor_stragglers: a card's stripe/tag colour
        # comes from the note itself, and a custom note colour that happens
        # to match some other theme's palette entry (e.g. #7c5cff, which is
        # also the dark theme's accent) would otherwise be swapped out by
        # the straggler pass and left showing the wrong colour. Running last
        # makes the note's own data authoritative. See _recolor_note_cards.
        self._recolor_note_cards()
        # Checklist rows rebuild per note load, so they are deliberately
        # untracked — but the straggler net repaints only bg/fg, leaving a
        # switched theme's checkbox wells (selectcolor) on the old palette
        # while the note stays open. Same treatment as the note cards.
        self._recolor_checklist_boxes()
        # The find highlights are blended from the palette, so re-tint them
        # for the new theme; then re-draw the current cell flash, which the
        # grid rebuild above tore off the canvas (a no-op if find is closed).
        if hasattr(self, "body_text"):
            self._retint_find_tags(self.body_text)
        self._find_reflash()
        # (The History register's rebuilt rows need no hook here: the
        # straggler pass above recolors them — qa7's theme-while-open
        # check guards that promise regardless of mechanism.)

    def _recolor_checklist_boxes(self):
        """Repaint the live checklist rows' Checkbutton wells for the
        current palette. The rows rebuild on every note load, so tracking
        them would leak (the note-card lesson); the straggler net covers
        their bg/fg but not selectcolor/activebackground."""
        frame = getattr(self, "checklist_items_frame", None)
        if frame is None:
            return

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Checkbutton):
                    try:
                        c.configure(selectcolor=self.colors["check_well"],
                                    activebackground=self.colors["card"])
                    except tk.TclError:
                        pass
                walk(c)

        try:
            walk(frame)
        except tk.TclError:
            pass

    def _calendar_is_showing(self):
        """True only if the Calendar tab is the one currently selected AND
        the notebook itself is visible (Settings replaces it). Uses the
        notebook's own selection rather than winfo_ismapped(), which
        pack()/pack_forget() don't update synchronously."""
        tab = getattr(self, "_calendar_tab", None)
        if tab is None:
            return True  # unknown layout: rebuild rather than risk staleness
        # Settings replaces the whole notebook, and it used to be spotted
        # here by winfo_ismapped(). That answer lags: pack()/pack_forget()
        # do not settle it until Tk goes idle, so a caller on either side
        # of the swap could read the state from before it. Measured
        # failing for real once deferral rode on this answer -- leaving
        # Settings rebuilt nothing, because the notebook it had just
        # re-packed still read as hidden. The flag is set by the two
        # methods that own the swap and is right the instant they run.
        if getattr(self, "_settings_open", False):
            return False
        try:
            return str(self.notebook.select()) == str(tab)
        except tk.TclError:
            return True

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
        # Surfaces DERIVED from a palette are invisible to the loop above,
        # because they are in no palette: Settings blends card toward text
        # for the well inside a card, and toward subtext for its hairlines.
        # A widget built under one theme therefore kept the other theme's
        # inset -- which is why the information bars in General, Backup and
        # About stayed dark, and unreadable, on a light theme.
        for name, palette in THEMES.items():
            if name == self.theme_name:
                continue
            for derive in (inset_surface, hairline):
                was, now = derive(palette), derive(cur)
                if was.lower() != now.lower():
                    remap[was.lower()] = now

        # Current theme's own colors must never be remapped away.
        for key, val in cur.items():
            if isinstance(val, str) and val.startswith("#"):
                remap.pop(val.lower(), None)
        for derive in (inset_surface, hairline):
            remap.pop(derive(cur).lower(), None)

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
        # An open day's list paints each row's stripe in its note's own
        # colour, and the walk above cannot tell that from a palette's:
        # General's #7c5cff is the dark and light accent, Urgent's #ff5c7c
        # the dark theme's danger, so they were swapped for the new theme's.
        # Drawn again from the notes, as _recolor_note_cards does for the
        # note list -- also while Settings hides it, so that it is right
        # when it shows. (The one-note view has no colour of its own.)
        if getattr(self, "_day_panel_mode", "empty") == "list":
            self.show_day_list()

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
        return core_blend(hex_a, hex_b, t)

    # ---------- Resizing the window by its edge ----------
    # A drag of the window's edge sends a new size every few milliseconds,
    # and laying the whole window out again cost far more than that:
    # measured, 260 ms a step with the Calendar showing, 155 with a note in
    # the editor, 70 on Settings -- 98% of it inside Tk, placing and
    # painting hundreds of widgets, so no Python could make it quicker. The
    # edge crawled behind the pointer (field-reported on the Calendar).
    #
    # So while the mouse button holds the edge, the window waits: its frame
    # follows the pointer, and the content is laid out once, when the drag
    # pauses or the button is let go. A resize with no button held --
    # maximising, a snap, the keyboard -- is laid out at once, as before.
    RESIZE_PAUSE_MS = 120   # a held drag this still is laid out anyway
    RESIZE_WATCH_MS = 40    # how often a held drag looks for the release

    def _on_main_canvas_configure(self, event):
        self._main_size_wanted = (max(event.width, self._main_min_width),
                                  event.height)
        if self._pointer_button_held() and not self._page_follows_the_drag():
            self._wait_for_resize_to_settle()
            return
        self._lay_out_at_window_size()

    def _page_follows_the_drag(self):
        """Whether the page on screen is laid out at every step of a held
        drag, rather than when the drag pauses or ends.

        The calendar's month is drawn on one canvas, and a step of the drag
        costs it under 40 ms there -- quick enough to follow the mouse, which
        is what the field test asked for. Every other page is built of
        widgets and still costs 70 ms or more a step, so it keeps the frame
        light and catches up once the hand stops. The History register is
        rows of widgets too, so it waits with the rest -- and so does an
        open day's panel below the month: a row per note, or a whole note's
        text, laid out again at every step (60 ms a step for an ordinary
        month, 150 and more for a busy one, measured)."""
        return (self._calendar_is_showing()
                and not getattr(self, "_history_visible", False)
                and getattr(self, "_day_panel_mode", "empty") == "empty")

    def _lay_out_at_window_size(self):
        """Give the window's content the window's size: the one place it
        happens, whether at once or when a drag settles."""
        for name in ("_resize_pause_job", "_resize_watch_job"):
            job = getattr(self, name, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass
                setattr(self, name, None)
        size = getattr(self, "_main_size_wanted", None)
        if size is None or size == getattr(self, "_main_size_laid_out", None):
            return
        try:
            self.main_canvas.itemconfig(self._main_window_item,
                                        width=size[0], height=size[1])
        except tk.TclError:
            return
        self._main_size_laid_out = size

    def _wait_for_resize_to_settle(self):
        """A held drag of the edge: lay out after a pause in it, or at the
        release, whichever comes first."""
        job = getattr(self, "_resize_pause_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._resize_pause_job = self.after(self.RESIZE_PAUSE_MS,
                                            self._lay_out_at_window_size)
        if getattr(self, "_resize_watch_job", None) is None:
            self._resize_watch_job = self.after(self.RESIZE_WATCH_MS,
                                                self._watch_resize_release)

    def _watch_resize_release(self):
        """One look at the mouse button during a held drag: still down,
        look again shortly; let go, lay the window out now."""
        self._resize_watch_job = None
        if not self._still_alive():
            return
        if self._pointer_button_held():
            self._resize_watch_job = self.after(self.RESIZE_WATCH_MS,
                                                self._watch_resize_release)
            return
        self._lay_out_at_window_size()

    def _pointer_button_held(self):
        """Whether the mouse's primary button is down right now.

        Asked of Windows, because the window's edge belongs to the
        operating system: Tk hears the new sizes and nothing of the button
        making them. Windows reports the PHYSICAL button, so for someone
        who has swapped the buttons the primary one is the right. Anywhere
        else, or if the question fails, the answer is no -- which is simply
        the behaviour from before."""
        if not sys.platform.startswith("win"):
            return False
        try:
            import ctypes
            user32 = ctypes.windll.user32
            swapped = user32.GetSystemMetrics(23)       # SM_SWAPBUTTON
            key = 0x02 if swapped else 0x01              # VK_RBUTTON, VK_LBUTTON
            return bool(user32.GetAsyncKeyState(key) & 0x8000)
        except Exception:                                # noqa: BLE001
            return False

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

        # Read by _on_main_canvas_configure, which gives the content the
        # window's size -- at once, or when a drag of the edge settles.
        self._main_window_item = main_window
        self._main_min_width = SIDEBAR_WIDTH + EDITOR_MIN_WIDTH

        self.main_inner.bind("<Configure>", _on_inner_configure)
        self.main_canvas.bind("<Configure>", self._on_main_canvas_configure)

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
        self.toast_lbl.pack(side="left")
        # The toast can carry one action -- "Undo", after a delete. Built
        # here and packed on demand, so a plain toast looks exactly as it
        # did. Its colours are set in _show_toast() rather than tracked:
        # the toast is recoloured on every appearance from self.colors,
        # which is the app's other theming pattern and the right one for
        # a widget nobody sees between showings.
        self.toast_action_lbl = tk.Label(
            self.toast_frame, font=("Segoe UI", 9, "bold", "underline"),
            bg=self.colors["success"], fg="white", padx=0, pady=6,
            cursor="hand2")
        self._toast_action = None
        self.toast_action_lbl.bind(
            "<Button-1>", lambda _e: self._run_toast_action())
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
        # Long-lived and shown on demand: untracked, a theme switched
        # before the next export left the bar's frame painted in the old
        # palette (audit Z07-F03's class — track every colour option).
        self.track_theme(self.export_progress_frame, bg="card",
                         highlightbackground="accent")
        self.track_theme(export_inner, bg="card")
        self.track_theme(self.export_progress_lbl, bg="card", fg="text")
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
        # Kept so a theme switch can tell whether the calendar is actually
        # on screen, and skip rebuilding it if not — see apply_theme.
        self._calendar_tab = calendar_tab

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
            # The Calendar tab's home is the month grid; History is only a
            # view of it. Leaving the tab (or returning to it) resets to
            # the grid, so the calendar never reopens showing History
            # from a session two tab-switches ago (field report).
            if getattr(self, "_history_visible", False):
                self._hide_calendar_history()
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
        # Notes <-> Calendar: same rule -- a popup belongs to the page it
        # was opened on.
        self.notebook.bind("<<NotebookTabChanged>>",
                           lambda e: self._dismiss_mini_popup(), add="+")



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
            # The ✕ first, and NOT on the timer: whether the box holds a real
            # query is known now, and a clear button that appeared a fifth of
            # a second after the typing would read as a glitch.
            self._refresh_search_clear()
            # Rebuilding the note list on every keystroke made typing a
            # search term feel laggy with a large note collection, worse the
            # more notes there were (exactly when search matters most) --
            # back when every card was a handful of widgets. A rebuild is
            # cheap now that the list is drawn, but filtering still reads
            # every note; wait for a short pause in typing, as autosave does.
            if self._search_debounce_job is not None:
                try:
                    self.after_cancel(self._search_debounce_job)
                except (tk.TclError, ValueError):
                    pass
            self._search_debounce_job = self.after(180, self.refresh_note_list)

        self.search_var.trace_add("write", _debounced_search_refresh)
        # The entry and its ✕ share a frame wearing the entry's own fill, so
        # the button reads as sitting inside the box rather than beside it.
        # The row carries the padding the entry used to carry itself.
        search_row = tk.Frame(self.sidebar)
        self.track_theme(search_row, bg="card")
        search_row.pack(fill="x", padx=15, pady=(0, 10))
        self.search_entry = search_entry = tk.Entry(
            search_row, textvariable=self.search_var,
            insertbackground=self.colors["text"], relief="flat", font=("Segoe UI", 11)
        )
        self.track_theme(search_entry, bg="card", fg="text", insertbackground="text")
        self._guard_entry_astral(search_entry)
        search_entry.pack(side="left", fill="x", expand=True, ipady=6)
        # The most-used field in the app was the only text field without one.
        self._add_paste_menu(search_entry)
        # Long-lived (this row is built once and never rebuilt), so
        # track_theme — and every colour option it has, not just bg and fg:
        # an untracked activebackground is how a button ends up wearing the
        # old accent after a theme switch.
        self.search_clear_btn = tk.Button(
            search_row, text="✕", command=self._clear_search,
            relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"),
            highlightthickness=0)
        self.track_theme(self.search_clear_btn, bg="card", fg="subtext",
                         activebackground="card", activeforeground="text",
                         highlightbackground="card")
        self.add_placeholder(search_entry, "Search notes...")
        # The placeholder went in through search_var, so the trace has
        # already run once and settled the ✕. Called again anyway, because
        # relying on that ordering is how this breaks when someone reorders
        # these lines.
        self._refresh_search_clear()
        # ...and it scheduled a list rebuild for a search nobody typed: a
        # second full rebuild at every startup, on top of the one the
        # launch runs anyway (~55 ms at 5,000 notes, measured).
        if self._search_debounce_job is not None:
            try:
                self.after_cancel(self._search_debounce_job)
            except (tk.TclError, ValueError):
                pass
            self._search_debounce_job = None

        # Sort + category filter row
        # Captions for the two controls below, because both are labelled with
        # their current VALUE -- "Recently updated ▾", "All ▾" -- so the words
        # "sort" and "show" appeared nowhere on the screen, and "All" in
        # particular reads as a state rather than as a control you can press.
        #
        # ABOVE the row and not inside it, deliberately. The row has 250px for
        # two controls and the comments further down record real clipping
        # fights over exactly that; a caption here competes for none of it.
        # The alignment is free: the sort control below packs left and the
        # filter packs right, so a caption at each end of a frame with the
        # same padding sits over the edge its control is anchored to.
        caption_row = tk.Frame(self.sidebar)
        self.track_theme(caption_row, bg="sidebar")
        caption_row.pack(fill="x", padx=15, pady=(0, 1))
        sort_caption = tk.Label(caption_row, text="Sort", font=("Segoe UI", 8),
                                anchor="w")
        self.track_theme(sort_caption, bg="sidebar", fg="subtext")
        sort_caption.pack(side="left")
        show_caption = tk.Label(caption_row, text="Show", font=("Segoe UI", 8),
                                anchor="e")
        self.track_theme(show_caption, bg="sidebar", fg="subtext")
        show_caption.pack(side="right")

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
            "Calendar: soonest",
            "Calendar: oldest",
            self.SORT_CUSTOM,
        ]
        # Remembered across launches, like the "Group by category" checkbox a
        # few pixels below and the folded groups beside it. Three controls on
        # adjacent rows of one panel, two of which were remembered: someone
        # who prefers Title A–Z re-picked it at every launch with no way to
        # tell why that one preference did not stick.
        #
        # Validated on the way IN, not only on the way out. What comes back is
        # whatever is in a settings file -- possibly written by an older build,
        # possibly hand-edited, possibly naming a sort this version no longer
        # has -- and an unknown key here would reach the sort comparator.
        _stored_sort = load_settings().get("note_sort")
        self.sort_var = tk.StringVar(
            value=_stored_sort if _stored_sort in self.SORT_OPTIONS
            else self.SORT_OPTIONS[0])
        self.sort_var.trace_add(
            "write", lambda *a: save_setting("note_sort", self.sort_var.get()))
        # width_chars=0: content-sized, because this control is the one
        # packed to FLEX below and a width fixed in characters defeats
        # that. 18 was the previous number, chosen by measuring the label
        # alone -- the longest option needs 93px and 18 chars gives 114px,
        # so the label did fit. The ROW then asked for 260px inside a
        # 250px sidebar, and pack took the 10px off this control's right
        # edge: its arrow, then the last letters of "Recently updated".
        # Visible in every scene screenshot, and invisible to any check
        # that measures the label. No fixed number would have worked
        # either -- 16 fits Segoe UI on Windows and is still 19px
        # over-full in DejaVu Sans on the Linux CI image.
        sort_menu = self._build_themed_dropdown(
            filter_row, self.sort_var, self.SORT_OPTIONS,
            on_change=self._on_sort_chosen, width_chars=0)

        # Same as the sort above, with one more thing to be careful about: a
        # stored filter can name a category that has since been deleted, or
        # one this notebook never had. _keep_filter_valid asks the dropdown's
        # own vocabulary rather than a second copy of it, so the load-time
        # answer and the runtime answer cannot drift apart. It runs after the
        # dropdown exists, below.
        self.filter_var = tk.StringVar(
            value=load_settings().get("note_filter", "All"))
        self.filter_var.trace_add(
            "write",
            lambda *a: save_setting("note_filter", self.filter_var.get()))
        self.filter_menu = self._build_themed_dropdown(
            filter_row, self.filter_var, self._filter_options,
            on_change=lambda v: self.refresh_note_list(),
            # Content-sized too, for the same reason as the sort control
            # above: 13 characters is 113px in Segoe UI and 122px in
            # DejaVu Sans, and the row has 250px for both. Anchored right
            # and not flexing, it takes exactly what it is showing; the
            # sort control beside it absorbs whatever is left, including
            # when a long category name is selected here.
            dot_color_fn=lambda v: CATEGORY_COLORS.get(v), width_chars=0)
        # Packed FIRST so pack honours its width — packed last on a full
        # row, the button was squeezed to a bare "🔁 R…" (seen in a
        # screenshot, not guessed). The sort button flexes instead.
        self.filter_menu.pack(side="right")
        sort_menu.pack(side="left", fill="x", expand=True, padx=(0, 4))
        # After the dropdown exists, because the guard checks hasattr on it
        # the same way refresh_category_widgets does. A stored filter naming
        # a category this notebook does not have falls back to All here,
        # before anything reads it.
        self._keep_filter_valid()

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
        self.track_theme(group_cb, bg="sidebar", fg="subtext", selectcolor="check_well",
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
        # The count on its own line, then the four actions two by two.
        #
        # All five used to sit in ONE line across a fixed 280px sidebar,
        # which meant the line could not fit and had no way to say so:
        # the packer gives each control what it asks for in order and the
        # LAST one lives on whatever is left. Everything before it looks
        # perfect, which is why nothing seemed wrong until the end of the
        # row. On Windows that was Export asking 40px and drawn at 27 --
        # the word against the edge with its caret cut off, which is how
        # it was reported. On the Linux CI image, where the fonts are
        # wider, the same four asked 338px of the 250 available and
        # Export was drawn at ONE pixel. It had been that broken there
        # the whole time, and no check had ever measured it.
        #
        # (The comment this replaces recorded the same fight being won by
        # a single pixel: "four controls need 281px and the sidebar is a
        # fixed 280 -- the emoji alone is the overflow". A layout that
        # fits by one pixel is one font away from not fitting, and this
        # one had already lost that bet on the other platform.)
        #
        # Two by two is the fix rather than a smaller font, because it
        # changes what has to be true: the widest row now needs the two
        # widest labels side by side (180px measured on Linux, 105 on
        # Windows) instead of all four, which leaves room to spare on
        # both rather than a margin to be eaten by the next label, glyph
        # or font. Each button expands to fill its half, so they stay the
        # same size as each other whatever the text does.
        self.bulk_selected_lbl = tk.Label(
            self.bulk_action_bar, text="0 selected", font=("Segoe UI", 8, "bold"))
        self.track_theme(self.bulk_selected_lbl, bg="sidebar", fg="text")
        self.bulk_selected_lbl.pack(anchor="w", pady=(0, 3))

        def _bulk_row():
            row = tk.Frame(self.bulk_action_bar)
            self.track_theme(row, bg="sidebar")
            row.pack(fill="x", pady=1)
            return row

        def _bulk_pack(button):
            button.pack(side="left", expand=True, fill="x", padx=1, ipady=3)

        top_row = _bulk_row()
        bulk_select_all_btn = tk.Button(
            top_row, text="Select all", command=self._bulk_select_all,
            relief="flat", font=("Segoe UI", 8), cursor="hand2")
        self.track_theme(bulk_select_all_btn, bg="card", fg="text")
        _bulk_pack(bulk_select_all_btn)
        # Kept, because its label is not fixed: it becomes "Unselect all"
        # once everything on screen is selected.
        self._bulk_select_all_btn = bulk_select_all_btn
        bulk_trash_btn = tk.Button(
            top_row, text="🗑 Trash", command=self._bulk_move_to_trash,
            relief="flat", font=("Segoe UI", 8, "bold"), cursor="hand2")
        self.track_theme(bulk_trash_btn, bg="danger")
        bulk_trash_btn.configure(fg="white")
        _bulk_pack(bulk_trash_btn)

        bottom_row = _bulk_row()
        bulk_category_btn = tk.Button(
            bottom_row, text="🗂 Category ▾",
            relief="flat", font=("Segoe UI", 8), cursor="hand2")
        self._toggles_its_popup(bulk_category_btn, self._bulk_change_category)
        self.track_theme(bulk_category_btn, bg="accent")
        bulk_category_btn.configure(fg="white")
        _bulk_pack(bulk_category_btn)
        self._bulk_category_btn = bulk_category_btn
        bulk_export_btn = tk.Button(
            bottom_row, text="Export ▾",
            relief="flat", font=("Segoe UI", 8), cursor="hand2")
        self._toggles_its_popup(bulk_export_btn, self._bulk_export)
        self.track_theme(bulk_export_btn, bg="card", fg="text")
        _bulk_pack(bulk_export_btn)
        self._bulk_export_btn = bulk_export_btn

        # Pinning had exactly one route in the whole app -- the right-click
        # menu, one note at a time -- so reordering twenty notes meant opening
        # the menu twenty times. It belongs here, where Trash, Category and
        # Export already act on everything ticked.
        #
        # On a THIRD row rather than squeezed beside Export, and that is not
        # fussiness: the comment above records the two-by-two layout being the
        # fix for a bar that once fitted by a single pixel and then did not on
        # the other platform. Two per row is the invariant; a fifth button on
        # a row of two would put three of the widest labels side by side and
        # re-open the fight. Vertical space is cheap here, because this bar
        # only exists while notes are ticked.
        pin_row = _bulk_row()
        self._bulk_pin_btn = tk.Button(
            pin_row, text="📌 Pin", command=self._bulk_toggle_pin,
            relief="flat", font=("Segoe UI", 8), cursor="hand2")
        self.track_theme(self._bulk_pin_btn, bg="card", fg="text")
        _bulk_pack(self._bulk_pin_btn)
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

        # The note list is DRAWN on this canvas -- every card is rectangles
        # and text, not widgets (see _draw_note_card). takefocus: the list
        # is one stop for Tab, and walks with Down and Up from there.
        self.canvas = tk.Canvas(list_container, highlightthickness=0,
                                takefocus=1)
        self.track_theme(self.canvas, bg="sidebar")
        scrollbar = ttk.Scrollbar(list_container, orient="vertical",
                                  command=self._list_scrollbar_moved)
        # The same guard the editor page has carried since 0.32.x: when
        # the content fits (or the origin drifts above the first card),
        # the list pins back to the top instead of sitting displaced.
        self.canvas.bind("<Configure>",
                         lambda e: self._sync_list_scroll(), add="+")
        # Through _list_view_changed rather than straight to the scrollbar:
        # it is also what draws the rest of the list as the view nears it.
        self._list_scrollbar = scrollbar
        self.canvas.configure(yscrollcommand=self._list_view_changed)
        self._bind_list_input()

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
        # Each button's packing is kept (_fit_sidebar_panel packs a button
        # back exactly as it was after it stepped aside for an open panel).
        new_kw = dict(fill="x", padx=15, pady=(10, 4), ipady=8)
        new_btn.pack(**new_kw)

        import_btn = tk.Button(
            bottom_zone, text="📥 Import code", command=self.toggle_import_panel,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(import_btn, bg="card", fg="text")
        import_kw = dict(fill="x", padx=15, pady=(0, 4), ipady=5)
        import_btn.pack(**import_kw)

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
        share_kw = dict(fill="x", padx=15, pady=(0, 12), ipady=5)
        share_multi_btn.pack(**share_kw)

        # Inline share panel — pick notes, get a code, all without a pop-up.
        self.share_panel = tk.Frame(bottom_zone)
        self.track_theme(self.share_panel, bg="sidebar")

        settings_btn = tk.Button(
            bottom_zone, text="⚙ Settings", command=self.show_settings_page,
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(settings_btn, bg="card", fg="text")
        settings_kw = dict(fill="x", padx=15, pady=(0, 12), ipady=5)
        settings_btn.pack(**settings_kw)
        self._sidebar_zone_buttons = [(new_btn, new_kw), (import_btn, import_kw),
                                      (share_multi_btn, share_kw),
                                      (settings_btn, settings_kw)]
        # A window made shorter (or taller) with a panel open fits it again --
        # and so does the zone given less room by something above it, like
        # the selection bar appearing, which leaves the sidebar's size alone.
        self.sidebar.bind("<Configure>", self._fit_sidebar_panel, add="+")
        bottom_zone.bind("<Configure>", self._fit_sidebar_panel, add="+")

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

        self.editor_outer = tk.Frame(right_side)
        self.track_theme(self.editor_outer, bg="bg")
        self.editor_outer.pack(side="top", fill="both", expand=True)

        self.editor_canvas = tk.Canvas(self.editor_outer, highlightthickness=0)
        self.track_theme(self.editor_canvas, bg="bg")
        # The scrollbar, like the wheel, is a deliberate gesture: it
        # cancels any grid rebuild's still-pending view restore.
        editor_scrollbar = ttk.Scrollbar(
            self.editor_outer, orient="vertical",
            command=self._editor_scrollbar_moved)
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

        # Shown only while the editor holds one DAY of a repeating series:
        # the date field shows the series' start date, so without this
        # line the user has to remember which day they opened (field
        # request). Packed/unpacked whole by _update_occurrence_banner().
        self.occurrence_banner = tk.Label(
            self.editor, text="", font=("Segoe UI", 9, "bold"),
            anchor="center"
        )
        self.track_theme(self.occurrence_banner, bg="bg", fg="accent")

        top_row = tk.Frame(self.editor)
        self.track_theme(top_row, bg="bg")
        top_row.pack(fill="x", padx=30, pady=(25, 5))
        self.editor_top_row = top_row

        self.title_entry = tk.Entry(
            top_row, insertbackground=self.colors["text"],
            relief="flat", font=("Segoe UI", 20, "bold"),
            validate="key",
            validatecommand=(self.register(self._title_within_limit), "%P")
        )
        self.track_theme(self.title_entry, bg="bg", fg="text", insertbackground="text")
        self.title_entry.pack(side="left", fill="x", expand=True)
        self.add_placeholder(self.title_entry, "Note title...")
        self._add_paste_menu(self.title_entry)
        # How much of the title is left, shown only once it starts to matter.
        # A permanent "12/200" beside a twelve-character title is noise about
        # a limit nobody is near; the point is to warn before the field stops
        # accepting, not to keep score.
        self.title_count_lbl = tk.Label(top_row, text="", font=("Segoe UI", 8))
        self.track_theme(self.title_count_lbl, bg="bg", fg="subtext")
        self.title_entry.bind("<KeyRelease>", self._schedule_autosave)
        self.title_entry.bind("<KeyRelease>", self._refresh_title_count, add="+")
        # add="+": add_placeholder() above already bound <<Paste>> to clear
        # the placeholder first, and a plain bind() here would replace it --
        # which is exactly how the title came to paste "Note title...X".
        # Registration order is the run order, so the clear happens before
        # the length cap below is measured against the field's contents.
        self.title_entry.bind("<<Paste>>", self._on_title_paste, add="+")
        self._guard_entry_astral(self.title_entry)

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
        self.track_theme(self.category_menu, bg="sidebar",
                         highlightbackground="card")
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
        self.track_theme(self.date_entry, bg="card", fg="text", insertbackground="text")
        self.date_entry.pack(side="left", padx=(6, 4), ipady=3)
        self.add_placeholder(self.date_entry, "YYYY-MM-DD")
        # Typing a date directly (as opposed to using the picker popup, which
        # already autosaves via _pick()) previously had no autosave binding
        # at all, so a typed date change could be silently lost.
        self.date_entry.bind("<KeyRelease>", self._schedule_autosave)
        # And a PASTED date reaches the field without any key release, so the
        # line above never sees it -- measured: a pasted date scheduled no
        # save at all while a typed character did. That is the same silent
        # loss the comment above describes, on the route the paste menu below
        # is about to open. add="+" keeps add_placeholder's own <<Paste>>
        # clear, which runs first and is what stops the paste landing on top
        # of "YYYY-MM-DD".
        self.date_entry.bind("<<Paste>>", self._schedule_autosave, add="+")
        # Pasting a date copied out of an email is an ordinary thing to want,
        # and this was the field that most invited it and refused.
        self._add_paste_menu(self.date_entry)

        pick_date_btn = tk.Button(
            meta_row, text="📅",
            relief="flat", font=("Segoe UI", 9), cursor="hand2"
        )
        self._toggles_its_popup(pick_date_btn, self.open_date_picker)
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
            meta_row, text="", width=3, relief="flat", cursor="hand2")
        self._toggles_its_popup(self.color_swatch_btn, self.open_color_picker)
        self.color_swatch_btn.pack(side="left", padx=(6, 6))

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

        self.word_count_lbl = tk.Label(body_header, text="", font=("Segoe UI", 8),
                                       anchor="e", justify="right")
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

        # Two rows, and the controls are dealt into them by width rather
        # than packed straight in. Everything fits one row at the sizes this
        # app is used at; the second exists so that a narrow window, a
        # different font, or a scaled display can never put a control out of
        # reach. See _reflow_format_bar.
        self._fmt_bar = format_bar
        self._fmt_bar_items = []
        self._fmt_bar_rows = []
        # Three, not two: the number of rows needed depends on the font, and
        # a machine whose substitute font is much wider than this was
        # measured on could want a third. Unused rows cost nothing -- they
        # are never packed.
        for _ in range(3):
            row = tk.Frame(format_bar)
            self.track_theme(row, bg="bg")
            self._fmt_bar_rows.append(row)
        self._fmt_bar_rows[0].pack(side="top", fill="x")
        format_bar.bind("<Configure>", self._on_format_bar_resize)

        self._fmt_buttons = {}
        # List buttons get their own registry rather than sharing _fmt_buttons:
        # dict is driven by _refresh_format_buttons, which asks whether the
        # *selection* carries a character style. A list is a property of a
        # line, so it would answer "no" every time and hold the buttons
        # permanently unpressed.
        self._list_buttons = {}
        self._align_buttons = {}
        self._pending_styles = set()  # styles queued up for the next typed char
        self._pending_text_color = None  # hex, or None
        self._pending_font_size = None    # a size from FONT_SIZES, or None
        self._pending_font_family = None  # a family from FONT_FAMILIES
        self._pending_highlight_color = None  # hex, or None
        self._pending_style_last_length = 0  # baseline for detecting growth
        # No group captions. They cost 182px of a bar that did not fit, and
        # every button now says what it is on hover, which is what they were
        # for. The dividers still separate the groups.
        for style, label, label_font, tip, tip_detail in (
            ("bold", "B", ("Segoe UI", 10, "bold"), "Bold",
             "Ctrl+B \u2014 the selected text, or whatever you type next"),
            ("italic", "I", ("Segoe UI", 10, "italic"), "Italic", "Ctrl+I"),
            ("underline", "U", ("Segoe UI", 10, "underline"), "Underline",
             "Ctrl+U"),
            ("strike", "S", ("Segoe UI", 10, "overstrike"), "Strikethrough",
             "Ctrl+D"),
        ):
            btn = tk.Button(
                format_bar, text=label, font=label_font, width=2,
                relief="flat", cursor="hand2",
                command=lambda s=style: self._toggle_body_style(s)
            )
            self.track_theme(btn, bg="sidebar", fg="text")
            self._add_fmt_item(btn, padx=(0, 2), ipady=2)
            self._attach_tooltip(btn, tip, tip_detail)
            self._fmt_buttons[style] = btn

        # Font: a family and a size, as dropdowns rather than buttons —
        # neither is a toggle, and neither fits in three characters. They
        # sit before Colors because they are the coarsest thing here: the
        # typeface a run is set in, before anything is done to it.
        font_divider = tk.Frame(format_bar, width=1)
        self.track_theme(font_divider, bg="card")
        self._add_fmt_item(font_divider, padx=(5, 5), fill="y", pady=3)
        # "Default" is the app's own font, i.e. no span at all — which is
        # what makes the note follow the Settings default rather than being
        # pinned to whatever that happened to be on the day it was written.
        self.font_family_var = tk.StringVar(value=self.DEFAULT_FONT_LABEL)
        family_dd = self._build_themed_dropdown(
            format_bar, self.font_family_var,
            [self.DEFAULT_FONT_LABEL] + list(FONT_FAMILIES),
            lambda v: self._apply_body_font(
                "font_family", None if v == self.DEFAULT_FONT_LABEL else v),
            width_chars=11)
        self._add_fmt_item(family_dd, padx=(0, 4))
        self._attach_tooltip(family_dd, "Font",
                             "The selected text, or whatever you type next")

        self.font_size_var = tk.StringVar(value=self.DEFAULT_FONT_LABEL)
        size_dd = self._build_themed_dropdown(
            format_bar, self.font_size_var,
            [self.DEFAULT_FONT_LABEL] + [str(s) for s in FONT_SIZES],
            lambda v: self._apply_body_font(
                "font_size", None if v == self.DEFAULT_FONT_LABEL else int(v)),
            width_chars=7)
        self._add_fmt_item(size_dd, padx=(0, 4))
        self._attach_tooltip(size_dd, "Font size",
                             "Default follows the size set in Settings")

        # A thin divider + short label mark the color pickers as their own
        # group, distinct from the four toggle buttons — they work
        # differently (open a picker rather than applying anything
        # directly) and deserve to read that way at a glance, not blend
        # into the row as two more toggle-looking buttons.
        divider = tk.Frame(format_bar, width=1)
        self.track_theme(divider, bg="card")
        self._add_fmt_item(divider, padx=(5, 5), fill="y", pady=3)
        # Text color / Highlight: unlike the four toggle buttons above,
        # these open a swatch picker rather than applying anything
        # directly (there's no single obvious "the" color to toggle).
        # Each button previews the current state as an actual swatch —
        # its own background set to the chosen color, with the "A"/"H"
        # letter's contrast computed to stay legible against it — falling
        # back to the theme's normal button look when nothing is set. See
        # _refresh_format_buttons / _contrasting_fg.
        self.text_color_btn = tk.Button(
            format_bar, text="A", font=("Segoe UI", 10, "bold"), width=2,
            relief="flat", cursor="hand2")
        # A second click closes the palette instead of blinking it.
        self._toggles_its_popup(
            self.text_color_btn,
            lambda: self._open_color_swatch_popup("text_color"))
        self._add_fmt_item(self.text_color_btn, padx=(0, 2), ipady=2)
        self._attach_tooltip(self.text_color_btn, "Text colour",
                             "Colours the letters themselves")
        self.highlight_btn = tk.Button(
            format_bar, text="H", font=("Segoe UI", 10, "bold"), width=2,
            relief="flat", cursor="hand2")
        self._toggles_its_popup(
            self.highlight_btn,
            lambda: self._open_color_swatch_popup("highlight"))
        self._add_fmt_item(self.highlight_btn, padx=(0, 2), ipady=2)
        self._attach_tooltip(self.highlight_btn, "Highlight",
                             "Colours the background behind the letters")

        # Paragraph formatting -- what a whole line looks like -- kept apart
        # from the Style group, which is about the characters inside it. The
        # name is not "Lists": the note already has a Checklist below, and
        # two things called lists in one editor is one too many.
        para_divider = tk.Frame(format_bar, width=1)
        self.track_theme(para_divider, bg="card")
        self._add_fmt_item(para_divider, padx=(5, 5), fill="y", pady=3)
        for kind, label, tip, tip_detail in (
            ("bullet", "\u2022", "Bullet list",
             "Whole lines \u2014 click again to turn the list off"),
            ("number", "1.", "Numbered list",
             "Numbers itself; a nested list restarts at 1"),
        ):
            btn = tk.Button(
                format_bar, text=label, font=("Segoe UI", 10, "bold"), width=2,
                relief="flat", cursor="hand2",
                command=lambda k=kind: self._toggle_list(k)
            )
            self.track_theme(btn, bg="sidebar", fg="text")
            self._add_fmt_item(btn, padx=(0, 2), ipady=2)
            self._attach_tooltip(btn, tip, tip_detail)
            self._list_buttons[kind] = btn

        # Alignment sits in the same group: it is another property of the
        # whole line. The icons are drawn rather than lettered -- there is no
        # icon font to lean on and the app ships no image assets, and drawn
        # bars recolour with the theme, which a picture would not. Same
        # approach as the Settings nav glyphs.
        for align, tip in (("left", "Align left"), ("center", "Centre"),
                           ("right", "Align right")):
            btn = self._make_align_button(format_bar, align)
            self.track_theme(btn, bg="sidebar")
            self._add_fmt_item(btn, padx=(0, 4))
            self._attach_tooltip(
                btn, tip,
                "Applies to whole paragraphs, not to part of one")
            self._align_buttons[align] = btn

        # Indent and outdent. Arrows rather than drawn bars: these do
        # something rather than describe a state, so they never show a
        # pressed look and do not belong in the registries above.
        for delta, glyph, tip, tip_detail in (
            (-1, "⇤", "Outdent", "Shift+Tab inside a list"),
            (+1, "⇥", "Indent", "Tab inside a list — works on any paragraph"),
        ):
            btn = tk.Button(
                format_bar, text=glyph, font=("Segoe UI", 11), width=2,
                relief="flat", cursor="hand2",
                command=lambda d=delta: self._change_paragraph_indent(d)
            )
            self.track_theme(btn, bg="sidebar", fg="text")
            self._add_fmt_item(btn, padx=(0, 2), ipady=2)
            self._attach_tooltip(btn, tip, tip_detail)

        table_divider = tk.Frame(format_bar, width=1)
        self.track_theme(table_divider, bg="card")
        self._add_fmt_item(table_divider, padx=(5, 5), fill="y", pady=3)

        self.table_btn = tk.Button(
            format_bar, text="\u25a6", font=("Segoe UI", 11), width=2,
            relief="flat", cursor="hand2")
        self._toggles_its_popup(self.table_btn, self._open_table_size_popup)
        self.track_theme(self.table_btn, bg="sidebar", fg="text")
        self._add_fmt_item(self.table_btn, padx=(0, 2), ipady=2)
        self._attach_tooltip(
            self.table_btn, "Table",
            "Rows live in the note's own text, so a table survives being "
            "exported, shared as a code, or pasted anywhere else")

        self.emoji_btn = tk.Button(
            format_bar, text="\U0001f600", font=("Segoe UI Emoji", 10),
            width=2, relief="flat", cursor="hand2")
        self._toggles_its_popup(self.emoji_btn, self._insert_emoji_from_toolbar)
        self.track_theme(self.emoji_btn, bg="sidebar", fg="text")
        self._add_fmt_item(self.emoji_btn, padx=(0, 2), ipady=2)
        self._attach_tooltip(
            self.emoji_btn, "Emoji",
            "Lands in the open table cell if there is one, otherwise at "
            "the cursor in the note")

        # The quick light/dark flip, right where the writing happens --
        # the full theme picker stays in Settings; this only swaps
        # between the last light and last dark choice.
        self.editor_theme_btn = tk.Button(
            self.format_toolbar if hasattr(self, "format_toolbar") else
            self.emoji_btn.master,
            text="☀" if self.theme_name in DARK_THEMES else "🌙",
            relief="flat", cursor="hand2", bd=0,
            font=("Segoe UI", 10),
            command=self.toggle_theme)
        self.track_theme(self.editor_theme_btn, bg="sidebar", fg="text")
        self._add_fmt_item(self.editor_theme_btn, padx=(6, 2), ipady=2)
        self._attach_tooltip(
            self.editor_theme_btn, "Light / Dark",
            "Switches between your last light and last dark theme; the "
            "full theme picker stays in Settings")

        text_frame = tk.Frame(self.editor)
        self.track_theme(text_frame, bg="card")
        text_frame.pack(fill="both", expand=True, padx=30, pady=(0, 10))

        body_sb = ttk.Scrollbar(text_frame, orient="vertical")
        self.body_text = tk.Text(
            text_frame, insertbackground=self.colors["text"],
            relief="flat", wrap="word", padx=15, pady=15, height=12,
            font=(self.editor_font_family, self.editor_font_size),
            yscrollcommand=body_sb.set, undo=True, autoseparators=True, maxundo=-1
        )
        body_sb.config(command=self._body_scrollbar_moved)
        self.track_theme(self.body_text, bg="card", fg="text", insertbackground="text")
        body_sb.pack(side="right", fill="y")
        self.body_text.pack(side="left", fill="both", expand=True)
        self._setup_body_formatting_tags(self.body_text)
        self._setup_list_tags(self.body_text)
        self._configure_table_tag(self.body_text)
        self.body_text.bind("<Return>", self._on_body_return)
        self.body_text.bind("<BackSpace>", self._on_body_backspace)
        self.body_text.bind("<Delete>", self._on_body_delete_key)
        self.body_text.bind("<<Paste>>", self._on_body_paste, add="+")
        self.body_text.bind("<<Copy>>", self._copy_formatted, add="+")
        # Ctrl+Shift+V is the usual way to ask for the text without its
        # styling; Ctrl+V keeps it, the way every other editor does.
        self.body_text.bind("<Control-Shift-V>", self._paste_plain)
        self.body_text.bind("<Control-Shift-v>", self._paste_plain)
        self.body_text.bind("<Tab>", lambda e: self._on_body_tab(e, +1))
        self.body_text.bind("<Shift-Tab>", lambda e: self._on_body_tab(e, -1))
        # X11 reports Shift+Tab as its own keysym rather than a modified Tab.
        # Windows has never heard of it, and binding an unknown keysym is an
        # error there, so this is allowed to fail rather than guarded by a
        # platform check -- the same binding is simply unnecessary on Windows.
        try:
            self.body_text.bind("<ISO_Left_Tab>",
                                lambda e: self._on_body_tab(e, -1))
        except tk.TclError:
            pass
        self.body_text.bind("<KeyRelease>", self._schedule_autosave)
        self.body_text.bind("<KeyRelease>", self._apply_pending_style_to_typed_char, add="+")
        self.body_text.bind("<KeyRelease>", self._refresh_format_buttons, add="+")
        self.body_text.bind("<KeyRelease>", self._align_table_on_leaving, add="+")
        # If the find bar is open, an edit invalidates the match model; a
        # guarded, debounced rescan refreshes it WITHOUT moving the view.
        self.body_text.bind("<KeyRelease>",
                            lambda _e: self._find_on_body_edit(), add="+")
        # A click in the body means the user has LEFT the table: a cell
        # selection lingering from an earlier drag would silently catch
        # the next toolbar colour meant for the body text.
        self.body_text.bind("<Button-1>",
                            lambda _e: self._grid_clear_selection(), add="+")
        self.body_text.bind("<ButtonRelease-1>", self._resync_pending_style_anchor, add="+")
        self.body_text.bind("<ButtonRelease-1>", self._refresh_format_buttons, add="+")
        self.body_text.bind("<ButtonRelease-1>", self._align_table_on_leaving, add="+")
        # The text of a rendered table is elided, but Tk still lets the
        # caret wander into it -- and typing there would edit characters
        # nobody can see.
        self.body_text.bind("<KeyPress>", self._caret_out_of_hidden, add="+")
        self.body_text.bind("<Configure>", self._on_body_resize_grids, add="+")
        self.body_text.bind("<KeyRelease>", self._caret_out_of_hidden, add="+")
        self.body_text.bind("<KeyRelease>", self._reassert_line_alignment,
                            add="+")
        self.body_text.bind("<KeyRelease>", self._extend_word_styles_on_typing,
                            add="+")
        # KeyRelease alone re-centred the line one frame LATE -- the
        # character appears left-justified for a blink, then snaps to the
        # middle. An idle callback scheduled at KeyPress runs right after
        # the class binding inserts the character and BEFORE Tk repaints,
        # so the line never shows its uncentred moment.
        self.body_text.bind(
            "<KeyPress>",
            lambda e: self.after_idle(self._reassert_line_alignment),
            add="+")
        self.body_text.bind("<ButtonRelease-1>", self._caret_out_of_hidden, add="+")
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

        # How tall the writing area should be is a property of the note, not
        # of the app: twelve rows suits most notes and is cramped for a long
        # one. This box remembers the choice -- someone who writes long notes
        # wants the taller box every time, not once per launch. (It used to
        # say "unlike the comments box below", which was the only thing
        # written down about that asymmetry: a statement of it, never a reason
        # for it. The comments box remembers too now, by the same argument.)
        # Nothing else has to change for the taller box to work: the editor
        # already scrolls, so the page simply gets longer and the buttons
        # underneath stay reachable.
        self.body_resize_btn = self._add_text_resize_toggle(
            self.editor, self.body_text, compact=12, expanded=26,
            pack_kwargs={"padx": 30, "pady": (0, 8)},
            remember_key="editor_body_expanded")

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
        self.track_theme(self.comments_text, bg="card", fg="text", insertbackground="text")
        comments_sb.pack(side="right", fill="y")
        self.comments_text.pack(side="left", fill="both", expand=True)
        self._bind_text_wheel(self.comments_text)
        self._add_paste_menu(self.comments_text)
        self._bind_text_selection_fixes(self.comments_text)
        # Comments never render tables (only the body does), so a pasted
        # table used to land as raw pipe soup. Strip table rows out of a
        # paste here and say so, rather than leaving broken-looking pipes.
        self.comments_text.bind("<<Paste>>", self._on_comments_paste, add="+")
        self.comments_text.bind("<KeyRelease>", self._schedule_autosave)
        # Expand/Collapse toggle for the comments box (compact 4 rows <-> 12).
        # Remembered, like the body's identical toggle above. The helper's own
        # docstring draws the line at "a box whose size is incidental" versus
        # "one someone chose", and a box someone reached down and expanded is
        # the second kind whichever box it is.
        self._add_text_resize_toggle(self.editor, self.comments_text,
                                     compact=4, expanded=12,
                                     pack_kwargs={"padx": 30, "pady": (0, 8)},
                                     remember_key="editor_comments_expanded")

        # Reliable undo/redo on both editors (Ctrl+Z / Ctrl+Y and
        # Ctrl+Shift+Z). The body goes through _body_undo_redo, which also
        # redraws the tables the undone text describes; the comments box
        # has no tables and keeps the plain stack walk.
        self.body_text.bind("<Control-z>",
                            lambda e: self._body_undo_redo("undo"))
        self.body_text.bind("<Control-y>",
                            lambda e: self._body_undo_redo("redo"))
        self.body_text.bind("<Control-Shift-Z>",
                            lambda e: self._body_undo_redo("redo"))
        _tw = self.comments_text
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
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self._toggles_its_popup(use_template_btn, self.show_template_picker)
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


    # ---------- Calendar tab ----------





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
            # isdecimal(), not isdigit(): isdigit() also passes "2026²",
            # which int() then refuses with a ValueError instead of this
            # message. isdecimal() is exactly what int() reads -- so
            # "٢٠٢٦" and a full-width "２０２６" still work (the
            # calculator learned this first, core/calculator.py).
            if not raw.isdecimal() or not 1 <= int(raw) <= 9999:
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





    # ---------- Daily reminder bar ----------




    def notes_on_date(self, date_str):
        """Every note that lands on this date, recurring ones included."""
        return core_notes_on_date(self.notes, date_str)



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
        self._update_selected_day_outline()

    def _show_day_panel(self):
        """Make the panel visible below the grid. Deliberately does NOT
        auto-scroll down to it — clicking a date used to yank the view down
        every time, which was disruptive if you were just glancing at the
        month. Scroll down yourself when you're ready to see it."""
        if not self._is_placed(self.day_panel):
            self.day_panel.pack(side="bottom", fill="x", padx=30, pady=(0, 20))

    def close_day_panel(self):
        """Hide the panel and give the calendar its full height back."""
        self.selected_day = None
        self._day_panel_mode = "empty"
        self.day_panel.pack_forget()
        self._update_selected_day_outline()





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



    def _return_to_calendar(self):
        """Jump back to the exact month/day the user was viewing before they
        started creating a note from the calendar."""
        # Save first — leaving a dirty occurrence behind rendered the day
        # panel from the store, which still held the OLD content: the
        # edit looked lost. The scope question, if one is pending, rides
        # this click like every other explicit gesture.
        self._flush_autosave()
        # If the editor is STILL dirty, the flush did not finish — the
        # user cancelled the scope prompt, or the date field is mid-edit.
        # Navigating anyway would land them on a day panel showing the
        # old content while their edit sits only in the editor (and the
        # panel's "Open in editor" would then load disk content over it).
        # Stay put instead; the way back stays armed.
        try:
            st = self.capture_editor_state()
            # An emptied SAVED note whose flush was cancelled counts as
            # dirty here too — without the exemption this guard waved the
            # navigation through and the day panel showed the old content
            # over the user's unsaved emptying.
            #
            # But only block for something the flush could actually have
            # saved. A brand-new calendar note holding ONLY a repeat rule
            # is refused by every automatic route (the junk guard), so
            # this guard blocked forever on an edit nothing would ever
            # persist, telling the user to answer a question that was
            # never asked — a dead Back button with no way out.
            _blockable = (self._editing_saved_note()
                          or self._editor_state_has_content(
                              {k: v for k, v in st.items()
                               if k != "recurrence"}))
            if _blockable and not self.editor_state_matches_saved(st):
                self.set_status(
                    "Not saved yet — answer the save question (or fix the "
                    "date) to go back to the calendar")
                return
        except Exception:
            pass
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
            if not self._is_placed(self.calendar_return_btn):
                self.calendar_return_btn.pack(fill="x", padx=30, pady=(14, 0),
                                              anchor="w", before=self.editor_top_row)
        else:
            self.calendar_return_btn.pack_forget()

    def _update_occurrence_banner(self):
        """Show which day of a repeating series the editor holds, or hide
        the line entirely for plain notes and series views. Called wherever
        current_occurrence_date changes (load, new, tab restore)."""
        if not hasattr(self, "occurrence_banner") or not hasattr(self, "editor_top_row"):
            return
        occ = getattr(self, "current_occurrence_date", None)
        text = ""
        if occ:
            try:
                pretty = datetime.strptime(occ, "%Y-%m-%d").strftime("%A, %d %B %Y")
            except ValueError:
                pretty = occ
            text = f"📅 Editing this day of the series: {pretty}"
        elif self.selected_note_id is not None:
            # The series view of a repeating note gets its own line: edits
            # here reach every day — EXCEPT days that were edited with
            # "only this occurrence", which keep their own content and
            # would otherwise look like the edit silently failed (a field
            # report: one day out of three "didn't take" a series edit).
            note = self.find_note(self.selected_note_id)
            if note is not None and is_recurring(note):
                text = (f"🔁 This note repeats ({describe_recurrence(note)}) "
                        "— edits here apply to every day")
                n_over = len(note.get("overrides") or {})
                if n_over == 1:
                    text += " · 1 day keeps its own edits (✎)"
                elif n_over:
                    text += f" · {n_over} days keep their own edits (✎)"
        if text:
            self.occurrence_banner.config(text=text)
            if not self._is_placed(self.occurrence_banner):
                self.occurrence_banner.pack(fill="x", padx=30, pady=(6, 0),
                                            before=self.editor_top_row)
        else:
            self.occurrence_banner.pack_forget()



    # File extensions Windows will execute (or run scripts from) rather than
    # just open in a viewer. Opening one runs code, so we warn first.
    DANGEROUS_EXTENSIONS = {
        # The classics: files Windows executes outright.
        ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".msi", ".msp",
        ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta",
        ".cpl", ".jar", ".reg", ".ps2", ".msc", ".gadget",
        # And the ones actually used to deliver code today, which this
        # list missed: a .lnk carries an arbitrary command line behind an
        # innocent name and icon, .iso/.img mount on double-click, and
        # the rest each hand a path or a command straight to Windows.
        # An attachment arriving inside an imported backup reaches
        # os.startfile through exactly this gate.
        ".lnk", ".url", ".scf", ".iso", ".img", ".vhd", ".vhdx",
        ".chm", ".inf", ".sct", ".appref-ms", ".settingcontent-ms",
        ".msix", ".appx", ".appinstaller", ".library-ms", ".search-ms",
        ".application", ".diagcab", ".ws", ".vb", ".mht", ".mhtml",
    }





    def _update_color_swatch(self):
        """Show the note's colour on the swatch, and nothing else.

        No words beside it. The swatch already shows the colour, and the
        picker is one click away -- naming the state ("custom colour")
        told the user something they could see, in exchange for a second
        thing to read on a row that is mostly labels already.
        """
        color = self.current_note_color or CATEGORY_COLORS.get(
            self.category_var.get(), self.colors["accent"])
        self.color_swatch_btn.config(bg=color, activebackground=color)

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
        self._show_date_in_field("")

    def _show_date_in_field(self, value):
        """Put a date in the note's date field -- or, for none, the grey
        YYYY-MM-DD placeholder. The one way the editor fills that field, so
        the text and its colour cannot come apart between the routes that
        load, restore, import or put back a note's date."""
        self.date_entry.delete(0, "end")
        if value:
            self.date_entry.insert(0, value)
            self.date_entry.config(fg=self.colors["text"])
        else:
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
        self.track_theme(interval_entry, bg="card", fg="text", insertbackground="text")
        interval_entry.pack(side="left", padx=6, ipady=2)
        # Every box in the Repeat panel gets the paste menu, not just the two
        # that obviously invite it. The register's row waved these away as
        # "single digits, reasonable to leave" -- true for this one and the
        # count, and false for the end-date (a date, the same shape as the
        # note's own) and the day list ("1,15"). And they are free: each of
        # these vars traces to update_recurrence_summary, which schedules the
        # autosave, so a paste here saves without a binding of its own --
        # unlike the date field above. Leaving two of four would be the same
        # patchwork the row is about.
        self._add_paste_menu(interval_entry)
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
        self.track_theme(monthdays_entry, bg="card", fg="text", insertbackground="text")
        monthdays_entry.pack(side="left", ipady=2)
        # A list like "1,15", not a single digit -- the one of these four the
        # row's reasoning fits least.
        self._add_paste_menu(monthdays_entry)
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
            # The well is the CARD colour, which is the opposite of what the
            # tick boxes need -- measured, not assumed. Tk on Windows paints
            # a selected radio's dot in the button's own foreground colour
            # (a tick box's mark is dark whatever the palette says), and the
            # foreground is the text colour, light on every dark theme. On
            # the light check_well that dot was invisible: whichever of the
            # three was chosen, all three looked unchosen. card stands well
            # apart from the text colour on every theme, light or dark.
            rb = tk.Radiobutton(
                end_row, text=text, value=value, variable=self.rec_end_mode_var,
                font=("Segoe UI", 9), relief="flat", cursor="hand2",
                command=self.on_end_mode_changed,
                selectcolor=self.colors["card"]
            )
            self.track_theme(rb, bg="bg", fg="text", activebackground="bg", activeforeground="text", selectcolor="card")
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
        self.track_theme(self.rec_end_date_entry, bg="card", fg="text", insertbackground="text")
        self.rec_end_date_entry.pack(side="left", padx=(4, 2), ipady=2)
        # A date, exactly like the note's own date field, and just as likely
        # to be pasted from somewhere else.
        self._add_paste_menu(self.rec_end_date_entry)
        self.rec_end_date_var.trace_add("write", lambda *a: self.update_recurrence_summary())

        self.rec_end_date_pick_btn = tk.Button(
            end_row, text="📅",
            relief="flat", font=("Segoe UI", 9), cursor="hand2"
        )
        self._toggles_its_popup(
            self.rec_end_date_pick_btn,
            lambda: self.open_date_picker(self.rec_end_date_entry,
                                          self.rec_end_date_pick_btn))
        self.track_theme(self.rec_end_date_pick_btn, bg="sidebar", fg="text")
        self.rec_end_date_pick_btn.pack(side="left", padx=(0, 8), ipadx=2)

        _end_radio("after", "After")
        self.rec_count_var = tk.StringVar(value="10")
        self.rec_count_entry = tk.Entry(
            end_row, textvariable=self.rec_count_var, width=4,
            relief="flat", font=("Segoe UI", 9), justify="center",
            insertbackground=self.colors["text"]
        )
        self.track_theme(self.rec_count_entry, bg="card", fg="text", insertbackground="text")
        self.rec_count_entry.pack(side="left", padx=(4, 2), ipady=2)
        self._add_paste_menu(self.rec_count_entry)
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
                # isdecimal(): "3²" passed isdigit() and crashed int() on
                # every read of the rule, saves included (see _go above).
                if chunk.isdecimal() and 1 <= int(chunk) <= 31:
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
        Ctrl+Z can't undo back into a previous note's content. The body's
        formatting journal goes with it (see _body_undo_redo): it is only
        ever read beside the stack it was written next to."""
        for w in (getattr(self, "body_text", None), getattr(self, "comments_text", None)):
            if w is not None:
                try:
                    w.edit_reset()
                except tk.TclError:
                    pass
        self._fmt_undo, self._fmt_redo = [], []

    # How many steps back the formatting journal reaches. Each step holds
    # two snapshots as tuples (a few kB for an ordinary note); the cap
    # keeps a long session on a heavily styled note from growing without
    # bound. Past it, Ctrl+Z still walks Tk's own text stack.
    _FMT_JOURNAL_DEPTH = 100

    def _fmt_state(self):
        """The body as far as undo has to know it: the text's signature,
        its character formatting and its paragraph formatting -- the two
        things Tk's undo stack never records. Tuples, so two snapshots
        compare cheaply and a kept one holds little memory. Measured on
        the heaviest note the perf probes build (86k characters, 279
        spans): about 2 ms."""
        b = self.body_text
        text = b.get("1.0", "end-1c")
        spans = tuple((s["start"], s["end"], s["style"], s.get("value"))
                      for s in self._extract_formatting(b))
        paras = tuple(tuple(sorted(p.items()))
                      for p in self._extract_paragraphs(b))
        return (len(text), hash(text)), spans, paras

    def _fmt_restore(self, state, current=None):
        """Lay a snapshot's formatting back on the text it was taken from
        -- the caller has matched the text's signature. Tags only; the
        text is never touched. The grids come down first: a span counts
        characters, and a drawn table's window would shift every span
        after it by one. The caller draws them again."""
        _sig, spans, paras = state
        if current is None:
            current = self._fmt_state()
        if current[1:] == (spans, paras):
            return False
        b = self.body_text
        self._teardown_table_grids()
        for tag in b.tag_names():
            if (is_format_tag(tag) or tag.startswith("para_")
                    or tag in ("align_center", "align_right")):
                b.tag_remove(tag, "1.0", "end")
        self._apply_formatting(b, [
            dict({"start": s, "end": e, "style": style},
                 **({} if value is None else {"value": value}))
            for s, e, style, value in spans])
        self._apply_paragraphs(b, [dict(p) for p in paras])
        return True

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

    def _undo_atom_begin(self):
        """Open one undo unit on the body (see the _undo_atom decorator).
        Re-entrant: nested opens keep the outermost unit. The outermost
        open also notes the body's formatting, so the unit's Ctrl+Z can
        put back what Tk's text-only stack cannot (see _body_undo_redo)."""
        depth = getattr(self, "_undo_atom_depth", 0)
        self._undo_atom_depth = depth + 1
        if depth == 0 and hasattr(self, "body_text"):
            try:
                self.body_text.edit_separator()
                self.body_text.configure(autoseparators=False)
            except tk.TclError:
                pass
            self._fmt_atom_before = None
            try:
                # Only while the body records undo: an edit made inside
                # _undo_hidden leaves no step on Tk's stack to pair with.
                if self.body_text.tk.getboolean(
                        self.body_text.cget("undo")):
                    self._fmt_atom_before = self._fmt_state()
            except (tk.TclError, ValueError):
                pass

    def _undo_atom_end(self):
        depth = max(0, getattr(self, "_undo_atom_depth", 1) - 1)
        self._undo_atom_depth = depth
        if depth == 0 and hasattr(self, "body_text"):
            try:
                self.body_text.configure(autoseparators=True)
                self.body_text.edit_separator()
            except tk.TclError:
                pass
            before = getattr(self, "_fmt_atom_before", None)
            self._fmt_atom_before = None
            if before is None:
                return
            try:
                after = self._fmt_state()
            except (tk.TclError, ValueError):
                return
            if after == before:
                return
            # A unit that changed the text is a step on Tk's stack as well;
            # one that changed only formatting is a step on this one alone.
            journal = getattr(self, "_fmt_undo", None)
            if journal is None:
                journal = self._fmt_undo = []
            journal.append({"text": after[0] != before[0],
                            "before": before, "after": after})
            del journal[:-self._FMT_JOURNAL_DEPTH]
            self._fmt_redo = []

    def _body_undo_redo(self, action):
        """Ctrl+Z / Ctrl+Y on the note body.

        Tk walks its stack; what Tk cannot know is that the text it just
        put back may hold tables -- the drawn grids would keep showing
        the OLD cells over the new text (the drawing itself is kept off
        the stack by _undo_hidden). So every step resyncs the line tags
        and redraws the grids from the text that undo produced.

        And Tk's stack holds TEXT, never a tag. Making a word bold left
        nothing on it, so Ctrl+Z skipped the bold and took back the last
        burst of typing instead; and text Tk puts back comes back bare,
        so undoing a table operation returned the cells without their
        bold and colours. A formatting journal beside Tk's stack fills
        both gaps: every undo unit (_undo_atom) notes the formatting
        before and after it. A step that changed formatting only is taken
        back here, without Tk, when the text is exactly what it was then;
        a step Tk takes back gets its formatting laid again once Tk lands
        on the text the step started from. Matching on the text itself,
        never on a count of steps, is what keeps the two stacks in step:
        a snapshot is only ever laid on the very text it was taken from.
        A unit nothing noted (typing) is noted on its way back, so Ctrl+Y
        returns its styles too.
        """
        b = self.body_text
        # A still-open cell editor holds uncommitted text; commit it so
        # the undo works against what the note actually says.
        if getattr(self, "_cell_editor", None):
            self._commit_cell_editor()
        undo = action == "undo"
        if getattr(self, "_fmt_undo", None) is None:
            self._fmt_undo = []
        if getattr(self, "_fmt_redo", None) is None:
            self._fmt_redo = []
        mine, other = ((self._fmt_undo, self._fmt_redo) if undo
                       else (self._fmt_redo, self._fmt_undo))
        now = self._fmt_state()
        top = mine[-1] if mine else None
        if top is not None and not top["text"] and top["before"][0] == now[0]:
            # A formatting-only step, taken on exactly this text: it is
            # this whole key press, and Tk's stack is not touched.
            mine.pop()
            other.append(top)
            self._fmt_restore(top["before"] if undo else top["after"], now)
        else:
            can = (self._can_edit_undo if undo else self._can_edit_redo)(b)
            if not can:
                return "break"
            try:
                (b.edit_undo if undo else b.edit_redo)()
            except tk.TclError:
                return "break"
            text = b.get("1.0", "end-1c")
            landed = (len(text), hash(text))
            came, went = ("after", "before") if undo else ("before", "after")
            step = None
            for i in range(len(mine) - 1, -1, -1):
                if (mine[i]["text"] and mine[i][came][0] == now[0]
                        and mine[i][went][0] == landed):
                    step = mine.pop(i)
                    break
            if step is None:
                step = {"text": True, came: now, went: self._fmt_state()}
            else:
                # The side left behind is noted as it really was, for the
                # press that comes back to it.
                step[came] = now
                self._fmt_restore(step[went])
            other.append(step)
            del other[:-self._FMT_JOURNAL_DEPTH]
        self._body_follow_caret = True
        self._resync_list_tags()
        if (getattr(self, "_table_grids", None)
                or core_tables.find_blocks(b.get("1.0", "end-1c"))):
            self._render_table_grids()
        self._refresh_format_buttons()
        self._schedule_autosave()
        return "break"

    def _bind_text_wheel(self, text_widget, fallback_canvas=None):
        """Mousewheel behavior over a text box:
        - if the box has more text than fits, scroll the box's own
          content -- in pixels, see _text_wheel_scroll;
        - if everything fits, forward the scroll to the editor page instead, so
          the user can still reach the buttons below.
        We must return "break" in BOTH cases, otherwise tkinter's built-in Text
        wheel handling fires too and swallows the event."""
        text_widget.bind(
            "<MouseWheel>",
            lambda e: self._text_wheel_scroll(text_widget, e,
                                              fallback_canvas))

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
            # A deliberate scroll beats a rebuild's still-pending restore.
            if canvas is getattr(self, "canvas", None):
                self._list_restore_px = None
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

        def on_paste(e):
            # A paste is not a keystroke, so on_key above never sees it and
            # the pasted text used to land glued to the placeholder --
            # "Note title...My pasted title", measured on the real app.
            # Two routes reach here and BOTH were affected:
            #
            #   * the right-click Paste, which _add_paste_menu performs with
            #     event_generate("<<Paste>>") — no key is pressed at all;
            #   * Ctrl+V on a field that binds <<Paste>> itself (the title
            #     does, for its length cap), because Tk fires one binding
            #     per bindtag and a VIRTUAL event outranks a physical one in
            #     the same tag, so <<Paste>> wins and <KeyPress> never runs.
            #
            # Fixing it here rather than at the two call sites is what makes
            # every placeholder field safe, including the next one added.
            clear_if_placeholder()

        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg=self.colors["subtext"])

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<KeyPress>", on_key)
        # add="+" both ways: this must not displace a field's own <<Paste>>
        # handler, and a field's own handler must not displace this. The
        # title binds one at its call site and is bound the same way.
        entry.bind("<<Paste>>", on_paste, add="+")
        entry.bind("<FocusOut>", on_focus_out)

    # ---------- Note list rendering ----------
    # The sidebar dropdown mixes two kinds of choice: a category name, or
    # one of these two type filters. Every consumer of filter_var goes
    # through _note_passes_filter, so the list render and the bulk
    # select-all can never diverge on what "visible" means.
    FILTER_REPEATING = "🔁 Repeating"
    FILTER_DATED = "📅 Dated"

    def _filter_options(self):
        """Everything the sidebar's filter dropdown offers, in order.

        The dropdown is built from this, and so is every check of whether a
        filter value is still a real choice. It had been written out inline
        at the dropdown and then half-remembered by the guard that keeps the
        selection valid, which asked `not in CATEGORY_COLORS` -- true of both
        type filters above, neither of which is a category. So filtering the
        list to Repeating and then adding a category in Settings silently
        threw the filter away and showed everything. Measured on the real
        app before it was changed, with a control: a real category survived
        the same call and a deleted one was correctly reset.
        """
        return ["All", self.FILTER_REPEATING, self.FILTER_DATED] + \
            list(CATEGORY_COLORS.keys())

    def _keep_filter_valid(self):
        """Fall back to All if the current filter is no longer on offer.

        Called wherever the vocabulary can change -- which today means the
        categories, and at startup, where the value comes off disk and could
        name a category this notebook has never had.
        """
        var = getattr(self, "filter_var", None)
        if var is not None and var.get() not in self._filter_options():
            var.set("All")

    def _note_passes_filter(self, note, selected):
        """One judgment for the sidebar filter dropdown's current choice."""
        if selected == "All":
            return True
        if selected == self.FILTER_REPEATING:
            return is_recurring(note)
        if selected == self.FILTER_DATED:
            return not is_recurring(note) and bool(note.get("date"))
        return note.get("category") == selected

    def refresh_note_list(self):
        if not hasattr(self, "canvas") or not self._still_alive():
            return
        # A card lifted by a drag is drawn away from its record; the
        # rebuild below would draw the list around a card that is not
        # where it seems. The drag ends, and the card goes back first.
        self._cancel_list_drag()
        # The sort this list is drawn in -- what Custom order starts from
        # when it is chosen for the first time (_on_sort_chosen).
        sort_var = getattr(self, "sort_var", None)
        if sort_var is not None:
            self._sort_shown = sort_var.get()
        # The rebuild empties the drawing for a moment, and a Configure
        # landing in that window clamps the canvas to the top -- the
        # 'scroll jumps back to the top' report on the grouped list.
        # The offset is remembered in pixels and put back once the new
        # content exists, whatever happened in between.
        try:
            # If the previous rebuild's restore is still in force, the
            # canvas may sit at a transiently clamped position right now
            # -- carry that restore's target forward instead.
            pending = getattr(self, "_list_restore_px", None)
            if (pending is not None and time.monotonic()
                    <= getattr(self, "_list_restore_until", 0)):
                saved_list_scroll = pending
            else:
                saved_list_scroll = max(0, self.canvas.canvasy(0))
        except (tk.TclError, AttributeError):
            saved_list_scroll = 0
        if saved_list_scroll > 0:
            self.after_idle(lambda px=saved_list_scroll:
                            self._restore_list_scroll(px))
        # Called from everywhere note/category data changes (save, delete,
        # category rename/delete, import, ...) — piggyback the Statistics
        # panel's refresh here too, so it stays live while Settings happens
        # to be open, instead of only updating the next time it's opened.
        # Placed before the early-return branches below (e.g. an empty
        # filtered list) so it isn't skipped in those cases.
        self._render_statistics()
        # Whether the keyboard is on the list decides how far the rebuild
        # draws (see _list_draw_target). The keyboard itself stays where it
        # is: the canvas survives a rebuild, only its drawing is replaced.
        self._restore_focus_wanted = getattr(self, "_keyboard_on_card", False)
        # How deep the list was drawn, asked before the drawing goes.
        drawn_before = len(getattr(self, "_list_drawn", None) or ())
        self.canvas.delete("row")
        # One record per drawn row, in the order the rows stand on screen,
        # and the same records by note id and by category -- what every
        # update that stops short of a rebuild works from. Rebuilt here,
        # so they only ever describe what is drawn.
        self._list_drawn = []
        self._note_cards = {}
        self._group_headers = {}
        self._list_pending = []

        rows = self._list_rows()

        if not rows:
            # Distinguish "no notes at all" from "nothing matches the filter".
            if self.notes:
                msg = "No notes match your search or filter."
            else:
                msg = "No notes yet.\nClick '+ New Note' to start!"
            self.canvas.create_text(
                13, 23, anchor="nw", text=msg, font=("Segoe UI", 10),
                fill=self.colors["subtext"], tags=("row", "list_empty"))
            self._list_extent_changed()
            return

        self._list_pending = rows
        self._draw_list_rows(self._list_draw_target(
            rows, drawn_before, saved_list_scroll))
        # The card with the keyboard's ring is drawn with it; this repaints
        # it once the app is idle, for a rebuild that ran while the list was
        # not the thing holding the keyboard.
        self.after_idle(self._restore_card_focus)
        if getattr(self, "selection_mode", False):
            # What "all" means has just changed -- a search or a filter
            # alters which notes are on screen, and the Select all button
            # says what pressing it would do. Only while the bar is up,
            # so an ordinary refresh pays nothing for it.
            self._update_bulk_selected_label()

    # How many rows -- cards, and category headers when grouped -- the list
    # draws straight away, and how many more each time the view comes
    # within a screen of the end of what is drawn. See _draw_list_rows.
    LIST_FIRST_DRAW = 30
    LIST_DRAW_STEP = 20

    # The list is drawn on its canvas: every card is rectangles and text,
    # not widgets. These reproduce the widget cards they replaced, to the
    # pixel where it could be measured (a card of both kinds, photographed
    # side by side). See _draw_note_card.
    # The sort a person arranges by hand -- by dragging a card, or with
    # Alt+Up and Alt+Down -- stored as each note's "order" (see
    # normalize_note). One name, because the dropdown, the sort and the
    # move all have to mean the same option.
    SORT_CUSTOM = "Custom order"
    DRAG_THRESHOLD = 5          # pixels a press must travel to become a drag
    DRAG_EDGE = 28              # near the list's top or bottom, a drag scrolls
    DRAG_SCROLL_MS = 40         # ...one step this often

    LIST_DRAW_WIDTH = 250       # the list's width, as the old frame's was
    CARD_MARGIN = (5, 5)        # above and below each card
    HEADER_MARGIN = (6, 2)      # above and below each category header
    HEADER_HEIGHT = 22
    CARD_INSET_X = 2            # between the list's edge and a card's
    CARD_RING = 2               # the ring: open note, keyboard, or nothing
    CARD_STRIPE = 5             # the note's colour down the left edge
    CARD_PAD = (10, 8)          # around the text inside a card
    CARD_TEXT_INSET = 3         # what a Label kept around its own text
    CARD_CHECK = 13             # the tick box, in selection mode
    # The tick's mark is dark on every theme, as Windows drew it on the
    # Checkbutton this replaces: the well it sits in is light everywhere.
    CARD_CHECK_MARK = "#22223a"

    @property
    def _list_drawn_keys(self):
        """What is drawn, as ("note", id) and ("header", category), in the
        order it stands on screen."""
        return [rec["key"] for rec in getattr(self, "_list_drawn", None) or ()]

    def _notes_on_the_list(self):
        """The notes the sidebar's search box and filter let through, in
        the notebook's own order.

        The ONE answer to "which notes does the list show", for the reason
        _query_matches_note is one: the list drew from a copy of this
        written out inline, and Select all from another -- the copies
        agreed, which is exactly what copies stop doing.
        """
        query = self._search_query()
        shown = [n for n in self.notes if self._query_matches_note(query, n)]
        # Category/type filter (from the dropdown). "All" shows everything.
        chosen_category = getattr(self, "filter_var", None)
        if chosen_category is not None:
            selected = self.filter_var.get()
            if selected != "All":
                shown = [n for n in shown
                         if self._note_passes_filter(n, selected)]
        return shown

    def _list_rows(self):
        """Every row the note list shows, in screen order, before any of
        them is drawn.

        A row is ("note", note) for a card, or -- when the list is grouped
        -- ("header", category, notes_in_group, collapsed) ahead of each
        group, followed by the group's cards unless it is collapsed. Group
        order follows Manage-categories order; notes within a group keep
        the sort. A note whose category no longer exists falls into its
        own group by that name, so it stays visible rather than
        disappearing.

        One definition for everything that draws the list: the rebuild
        draws the first of these rows, the scrolling draws the rest, and
        a save redrawing its own card asks where in them the card now
        belongs.
        """
        shown = self._notes_on_the_list()
        self._sort_notes(shown)
        if not shown:
            return []
        if not (getattr(self, "group_by_category", None) is not None
                and self.group_by_category.get()):
            return [("note", note) for note in shown]
        groups = {}
        for note in shown:
            groups.setdefault(note.get("category") or "General", []).append(note)
        # Known categories first (in their defined order), then any leftover
        # (stale/deleted) category names so nothing gets silently dropped.
        ordered = [c for c in CATEGORY_COLORS.keys() if c in groups]
        ordered += [c for c in groups.keys() if c not in ordered]
        rows = []
        for cat in ordered:
            collapsed = cat in self.collapsed_groups
            rows.append(("header", cat, groups[cat], collapsed))
            if not collapsed:
                rows.extend(("note", note) for note in groups[cat])
        return rows

    def _list_draw_target(self, rows, drawn_before, scrolled_px):
        """How many rows a rebuild draws before handing back to the user.

        A screenful and some to spare, as a rule. But a rebuild must not
        take the list out from under the person using it: when it was
        scrolled, the old depth is drawn again, so the position restored
        in pixels has content to land on; and when the keyboard was on a
        card, that card is drawn, so the ring has somewhere to be.
        """
        want = self.LIST_FIRST_DRAW
        if scrolled_px > 0:
            want = max(want, drawn_before)
        if getattr(self, "_restore_focus_wanted", False):
            wanted = getattr(self, "_focused_note_id", None)
            for index, row in enumerate(rows):
                if row[0] == "note" and row[1].get("id") == wanted:
                    want = max(want, index + 1)
                    break
        return want

    def _draw_list_rows(self, count):
        """Draw the next `count` waiting rows, below what is already drawn.

        The list used to be drawn whole, on every rebuild. Every card was
        six windows to the operating system, so a list of 300 notes took
        three seconds to rebuild and one of 1,000 over twelve -- and a
        rebuild followed every pause in typing. Switching back to the list
        and closing Settings paid again for every card, on screen or not.

        A rebuild draws a screenful and some to spare, and the rest is
        drawn as the view comes near it: _list_view_changed hears every
        scroll, by wheel, scrollbar or resize, and the keyboard's walk
        draws ahead of itself (_focus_card_by_offset). And since the cards
        became a drawing rather than windows, what is drawn costs Windows
        one window however long the list gets.
        """
        batch = self._list_pending[:count]
        self._list_pending = self._list_pending[count:]
        if not batch:
            return
        y = self._list_end_y()
        for row in batch:
            if row[0] == "header":
                rec = self._draw_group_header(
                    row[1], row[2], row[3], y + self.HEADER_MARGIN[0])
            else:
                rec = self._draw_note_card(row[1], y + self.CARD_MARGIN[0])
            self._list_drawn.append(rec)
            y = rec["y1"] + rec["margin"][1]
        self._list_extent_changed()

    def _list_end_y(self):
        """Where the next row would start: below the last drawn row and
        its margin, or at the top of an empty drawing."""
        drawn = getattr(self, "_list_drawn", None)
        if not drawn:
            return 0
        return drawn[-1]["y1"] + drawn[-1]["margin"][1]

    def _list_extent(self):
        """How far the drawing reaches, as the scrollbar and every scroll
        guard must see it: (0, 0, width, bottom) -- from the very top to
        the last drawn row's bottom margin, or to below the empty-list
        message.

        Worked out from the rows, never asked of Tk. The frame the cards
        once lived in started at y=0, so bbox("all") did too, and every
        guard counts on that; a drawing's bbox starts at its first item,
        at the first card's margin, and the top of the list read as
        "scrolled four pixels" -- every rebuild kept its old depth and a
        snap to the top landed at 4. An empty rectangle from 0 papered
        over it on Windows and failed on the Linux image: Tk 8.6.15 counts
        a pixel round a rectangle with no outline into its bbox and 8.6.16
        does not, so the same rectangle read (0, 0, ...) on one and
        (1, 1, ...) on the other. The app knows where its rows end.
        """
        bottom = self._list_end_y()
        if not bottom:
            try:
                empty = self.canvas.bbox("list_empty")
            except tk.TclError:
                empty = None
            bottom = (empty[3] + 20) if empty else 2
        return (0, 0, self.LIST_DRAW_WIDTH, bottom)

    def _list_extent_changed(self):
        """Tell the canvas how far the drawing reaches now -- what the list
        frame's own <Configure> used to report whenever its size changed --
        and let the guard that keeps the list honest about its top look."""
        try:
            self.canvas.configure(scrollregion=self._list_extent())
        except tk.TclError:
            return
        self._sync_list_scroll()

    def _reflow_list(self, start=0):
        """Move every drawn row from `start` on to its place below the row
        before it. Rows keep their own heights; only where they stand
        changes, by moving their items -- one repaint for the lot."""
        drawn = self._list_drawn
        y = 0
        if start > 0:
            y = drawn[start - 1]["y1"] + drawn[start - 1]["margin"][1]
        for rec in drawn[start:]:
            top = y + rec["margin"][0]
            dy = top - rec["y0"]
            if dy:
                self.canvas.move(rec["tag"], 0, dy)
                rec["y0"] += dy
                rec["y1"] += dy
            y = rec["y1"] + rec["margin"][1]
        self._list_extent_changed()

    def _list_view_changed(self, first, last):
        """The list canvas saying which part of it is in view -- its
        yscrollcommand.

        The scrollbar hears it, as it always did. And while rows are still
        waiting, it asks for a top-up, once however many reports arrive
        before the app is next idle. Every way the view can move comes
        through here -- the wheel, the scrollbar, a window made taller, a
        drawn step making the content longer -- which is what makes it the
        one place to watch.
        """
        try:
            self._list_scrollbar.set(first, last)
        except (tk.TclError, AttributeError):
            return
        self._ask_for_top_up()

    def _ask_for_top_up(self):
        """Look, once the app is idle, whether more rows should be drawn --
        unless nothing waits, or a look is already on its way."""
        if (getattr(self, "_list_pending", None)
                and getattr(self, "_list_top_up_job", None) is None):
            self._list_top_up_job = self.after_idle(self._top_up_list)

    def _top_up_list(self):
        """Draw another step of rows if less than a screen of drawn list is
        left below the view. Drawing lengthens the content, the canvas
        reports it, and this runs again -- until there is a screen to
        spare or nothing left to draw."""
        self._list_top_up_job = None
        if not getattr(self, "_list_pending", None) or not self._still_alive():
            return
        try:
            view_h = self.canvas.winfo_height()
            left_below = self._list_extent()[3] - self.canvas.canvasy(view_h)
        except tk.TclError:
            return
        if left_below < view_h:
            self._draw_list_rows(self.LIST_DRAW_STEP)

    def _draw_group_header(self, cat, notes_in_group, collapsed, top):
        """One collapsible category header, drawn with its top at `top`."""
        cv = self.canvas
        c = self.colors
        self._header_seq = getattr(self, "_header_seq", 0) + 1
        tag = "hdr%d" % self._header_seq
        tags = ("row", tag)
        color = CATEGORY_COLORS.get(cat, c["accent"])
        bottom = top + self.HEADER_HEIGHT
        mid = top + self.HEADER_HEIGHT // 2
        items = {}
        # Across the whole row, like the frame it replaces: a click anywhere
        # on the header's line folds the group, not only on its words.
        items["bg"] = cv.create_rectangle(
            0, top, self.LIST_DRAW_WIDTH, bottom, fill=c["sidebar"],
            outline="", tags=tags)
        items["dot"] = cv.create_oval(5, mid - 4, 13, mid + 4, fill=color,
                                      outline=color, tags=tags)
        items["caret"] = cv.create_text(
            23, mid, anchor="w", text=("▶" if collapsed else "▼"),
            font=("Segoe UI", 8), fill=c["subtext"], tags=tags)
        caret_right = cv.bbox(items["caret"])[2]
        items["label"] = cv.create_text(
            caret_right + 10, mid, anchor="w",
            text=f"{cat} ({len(notes_in_group)})",
            font=("Segoe UI", 9, "bold"), fill=c["text"], tags=tags)
        # The ids, not the cards: a collapsed group draws no cards at
        # all, and its header still has to show the right number.
        rec = {"kind": "header", "key": ("header", cat), "tag": tag,
               "cat": cat, "ids": [n["id"] for n in notes_in_group],
               "collapsed": collapsed, "y0": top, "y1": bottom,
               "margin": self.HEADER_MARGIN, "items": items}
        self._group_headers[cat] = rec
        return rec

    def _sort_notes(self, notes, choice=None):
        """Sort the list in place according to the chosen sort option -- or
        to `choice`, when the question is how the list WAS sorted. All keys
        coerce missing/None fields to safe defaults so a single odd note can't
        crash the whole list."""
        if choice is None:
            choice = getattr(self, "sort_var", None)
            choice = choice.get() if choice is not None else "Recently updated"

        def _s(n, key):
            v = n.get(key, "")
            return v if isinstance(v, str) else ""

        if choice == self.SORT_CUSTOM:
            # Where a person put each note. A note nobody has placed yet --
            # new since, or arrived in a share code -- stands above the
            # placed ones, newest first, so it is found where it was just
            # made. Two passes, the second stable: newest first, then the
            # placed notes by their number below the unplaced.
            notes.sort(key=lambda n: (_s(n, "created"), n.get("id") or 0),
                       reverse=True)
            notes.sort(key=lambda n: (0, 0) if "order" not in n
                       else (1, n["order"]))
        elif choice == "Recently updated":
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
        elif choice == "Calendar: soonest":
            # "Soonest" keeps its promise now: the note's NEXT relevant
            # date, counted from today. A repeating series ranks by its
            # next occurrence (not its start date), upcoming dates come
            # before past ones, the freshest past date leads that group,
            # and undated notes sink to the bottom.
            today = datetime.now().strftime("%Y-%m-%d")

            def _inv(d):
                # Lexicographic inversion, so an ascending sort reads the
                # past newest-first without a second sorting pass.
                return "".join(chr(0x10FFFF - ord(c)) for c in d)

            def soonest_key(n):
                if is_recurring(n):
                    nxt = next_occurrence_on_or_after(n, today)
                    if nxt:
                        return (0, nxt)
                    # The series already ended: rank it with the past by
                    # its start date (its last occurrence would cost a
                    # full expansion here, for a rare case).
                    d = _s(n, "date")
                    return (1, _inv(d)) if parse_date(d) else (2, "")
                d = _s(n, "date")
                if not parse_date(d):
                    return (2, "")
                return (0, d) if d >= today else (1, _inv(d))
            notes.sort(key=soonest_key)
        elif choice == "Calendar: oldest":
            # Plain chronology by the note's own date — the archive walk.
            def date_key(n):
                d = _s(n, "date")
                has = bool(parse_date(d))
                return (not has, d if has else "", )
            notes.sort(key=date_key)

        # Pinned notes always float to the top, keeping their relative order
        # from the chosen sort. Python's sort is stable, so this preserves it.
        notes.sort(key=lambda n: not n.get("pinned", False))

    # ---------- Custom order: the list arranged by hand ----------

    def _on_sort_chosen(self, value):
        """The Sort dropdown's choice. Custom order chosen before anything
        was ever placed starts from the order the list was showing, rather
        than from an order nobody has seen."""
        if (value == self.SORT_CUSTOM
                and not any("order" in n for n in self.notes)):
            before = getattr(self, "_sort_shown", None)
            if before and before != self.SORT_CUSTOM:
                self._place_notes_as_sorted(before)
                self.save_notes()
        self.refresh_note_list()

    def _place_notes_as_sorted(self, choice):
        """Give every note its place in Custom order from the way `choice`
        sorts them -- all of them, not only those a search lets through,
        so what a filter hides keeps its place among the rest."""
        everything = list(self.notes)
        self._sort_notes(everything, choice=choice)
        for place, note in enumerate(everything):
            note["order"] = place

    def _same_list_block(self, a, b):
        """Whether two notes may trade places: both pinned or both not, and
        -- in a grouped list -- in the same group. A pinned note always
        stands above the rest, and a group is its category; a move that
        crossed either would be undone by the next rebuild."""
        if bool(a.get("pinned")) != bool(b.get("pinned")):
            return False
        grouped = getattr(self, "group_by_category", None)
        if grouped is not None and grouped.get():
            return ((a.get("category") or "General")
                    == (b.get("category") or "General"))
        return True

    def _move_note(self, note_id, before_id=None, after_id=None):
        """Put a note just before one note, or just after one, in Custom
        order, and show the list in that order.

        The list may have been sorted some other way: then Custom order
        starts from the order it was showing -- the one the person just
        moved a card in -- and the move is made there. Every note gets its
        place again, in one pass, so a number never has to fit between two
        others. A move is not an edit: nothing's "updated" changes."""
        note = self.find_note(note_id)
        anchor = self.find_note(before_id if before_id is not None else after_id)
        if note is None or anchor is None or anchor is note:
            return False
        if self.sort_var.get() != self.SORT_CUSTOM:
            self._place_notes_as_sorted(self.sort_var.get())
            self.sort_var.set(self.SORT_CUSTOM)
        everything = list(self.notes)
        self._sort_notes(everything, choice=self.SORT_CUSTOM)
        everything.remove(note)
        at = everything.index(anchor) + (0 if before_id is not None else 1)
        everything.insert(at, note)
        for place, each in enumerate(everything):
            each["order"] = place
        self.save_notes()
        self.refresh_note_list()
        return True

    def _list_move_by_keyboard(self, delta):
        """Alt+Up or Alt+Down: the card with the ring moves one place, and
        the ring goes with it."""
        nid = getattr(self, "_focused_note_id", None)
        note = self.find_note(nid) if nid is not None else None
        if note is None or self.selection_mode:
            return "break"
        block = [row[1]["id"] for row in self._list_rows()
                 if row[0] == "note" and self._same_list_block(row[1], note)]
        if nid not in block:
            return "break"
        at = block.index(nid) + delta
        if not 0 <= at < len(block):
            return "break"
        if delta < 0:
            moved = self._move_note(nid, before_id=block[at])
        else:
            moved = self._move_note(nid, after_id=block[at])
        if moved:
            self._put_keyboard_on_card(nid)
        return "break"

    # ---------- Custom order: dragging a card ----------

    def _list_drag_arm(self, rec, event):
        """A press on a card that might become a drag: remembered, nothing
        drawn yet. It becomes one only after the pointer has travelled
        DRAG_THRESHOLD pixels, so an ordinary click never moves anything."""
        try:
            cy = self.canvas.canvasy(event.y)
        except tk.TclError:
            return
        self._drag = {"nid": rec["note"]["id"], "press_y": cy,
                      "grab_dy": cy - rec["y0"], "started": False,
                      "offset": 0, "slot": None, "line": None,
                      "pointer_y": event.y, "scroll_job": None}

    def _list_dragged(self, event):
        """The pointer moving with the button down."""
        drag = getattr(self, "_drag", None)
        if not drag:
            return
        try:
            cy = self.canvas.canvasy(event.y)
        except tk.TclError:
            return
        if not drag["started"]:
            if abs(cy - drag["press_y"]) < self.DRAG_THRESHOLD:
                return
            if not self._start_list_drag():
                self._drag = None
                return
        drag["pointer_y"] = event.y
        self._follow_list_drag()
        self._scroll_list_drag_near_edge()

    def _start_list_drag(self):
        """Lift the card: it is drawn over the others and follows the
        pointer, and a line shows where it would land. Nothing is moved
        in the notebook until the button is let go."""
        drag = self._drag
        rec = (getattr(self, "_note_cards", None) or {}).get(drag["nid"])
        if rec is None:
            return False
        cv = self.canvas
        try:
            cv.tag_raise(rec["tag"])
            drag["line"] = cv.create_line(
                self.CARD_INSET_X, -10, self.LIST_DRAW_WIDTH - self.CARD_INSET_X, -10,
                width=3, fill=self.colors["accent"], tags=("row", "drag_line"))
            cv.configure(cursor="fleur")
        except tk.TclError:
            return False
        drag["started"] = True
        return True

    def _follow_list_drag(self):
        """Keep the lifted card under the pointer and the line at the slot
        it would drop into. The card's record is left where it was: only
        its drawing moves, so a step of rows drawn below while the list
        scrolls under a drag still finds everything where it stands."""
        drag = self._drag
        rec = self._note_cards.get(drag["nid"])
        if rec is None:
            return
        cv = self.canvas
        try:
            cy = cv.canvasy(drag["pointer_y"])
            view_top = cv.canvasy(0)
            view_bottom = cv.canvasy(cv.winfo_height())
        except tk.TclError:
            return
        # Under the pointer, but never out of sight: carried past the top
        # or the bottom of the list, the card stays at that edge while the
        # list scrolls under it. Photographed first without this -- a line
        # at the top of the list, and the card it belonged to nowhere.
        top = cy - drag["grab_dy"]
        top = max(view_top, min(top, view_bottom - (rec["y1"] - rec["y0"])))
        dy = top - (rec["y0"] + drag["offset"])
        if dy:
            cv.move(rec["tag"], 0, dy)
            drag["offset"] += dy
        slot = self._list_drop_slot(rec, cy)
        drag["slot"] = slot
        if slot is None:
            cv.coords(drag["line"], 0, -10, 0, -10)
            return
        kind, other = slot
        target = self._note_cards[other]
        if kind == "before":
            y = target["y0"] - target["margin"][0] / 2.0
        else:
            y = target["y1"] + target["margin"][1] / 2.0
        cv.coords(drag["line"], self.CARD_INSET_X, y,
                  self.LIST_DRAW_WIDTH - self.CARD_INSET_X, y)

    def _list_drop_slot(self, rec, cy):
        """Where the lifted card would land for a pointer at canvas y `cy`:
        ("before", id) or ("after", id), among the drawn cards it may trade
        places with -- or None when that is where it already stands."""
        note = rec["note"]
        block = [r for r in self._list_drawn
                 if r["kind"] == "note" and r is not rec
                 and self._same_list_block(r["note"], note)]
        if not block:
            return None
        slot = None
        for r in block:
            if cy < (r["y0"] + r["y1"]) / 2.0:
                slot = ("before", r["note"]["id"])
                break
        if slot is None:
            slot = ("after", block[-1]["note"]["id"])
        # Dropping a card right where it is moves nothing, and says so by
        # showing no line.
        order = [r["note"]["id"] for r in self._list_drawn
                 if r["kind"] == "note" and self._same_list_block(r["note"], note)]
        at = order.index(note["id"])
        if slot == ("before", order[at + 1] if at + 1 < len(order) else None):
            return None
        if slot == ("after", order[at - 1] if at > 0 else None):
            return None
        return slot

    def _scroll_list_drag_near_edge(self):
        """Near the top or bottom of the list a drag scrolls it, one step
        at a time while the pointer stays there -- or a card could never
        be taken further than the list shows."""
        drag = getattr(self, "_drag", None)
        if not drag or not drag["started"]:
            return
        try:
            height = self.canvas.winfo_height()
        except tk.TclError:
            return
        y = drag["pointer_y"]
        if y < self.DRAG_EDGE:
            depth, direction = self.DRAG_EDGE - y, -1
        elif y > height - self.DRAG_EDGE:
            depth, direction = y - (height - self.DRAG_EDGE), 1
        else:
            if drag["scroll_job"] is not None:
                self.after_cancel(drag["scroll_job"])
                drag["scroll_job"] = None
            return
        # Faster the further the pointer is pushed past the edge: a step a
        # beat at the edge itself, ten beyond it. At one step a beat, taking
        # a card from the bottom of 300 notes to the top took over a minute.
        step = direction * min(10, 1 + int(depth) // 8)
        if drag["scroll_job"] is None:
            drag["scroll_job"] = self.after(self.DRAG_SCROLL_MS,
                                            lambda: self._list_drag_scroll_step(step))

    def _list_drag_scroll_step(self, step):
        drag = getattr(self, "_drag", None)
        if not drag or not drag["started"]:
            return
        drag["scroll_job"] = None
        # A deliberate move beats a rebuild's still-pending restore.
        self._list_restore_px = None
        try:
            self.canvas.yview_scroll(step, "units")
        except tk.TclError:
            return
        self._follow_list_drag()
        self._scroll_list_drag_near_edge()

    def _list_released(self, _event=None):
        """The button let go: a drag drops its card where the line was; a
        press that never became a drag has already done what a click does."""
        drag = getattr(self, "_drag", None)
        self._drag = None
        if not drag or not drag["started"]:
            return
        self._end_list_drag(drag)
        slot = drag["slot"]
        if slot is None:
            self._put_lifted_card_back(drag)
            return
        kind, other = slot
        nid = drag["nid"]
        if kind == "before":
            moved = self._move_note(nid, before_id=other)
        else:
            moved = self._move_note(nid, after_id=other)
        if not moved:
            self._put_lifted_card_back(drag)
            return
        self._put_keyboard_on_card(nid)

    def _list_drag_escape(self, _event=None):
        """Escape during a drag puts the card back and moves nothing."""
        drag = getattr(self, "_drag", None)
        if not drag or not drag["started"]:
            return None
        self._cancel_list_drag()
        return "break"

    def _cancel_list_drag(self):
        """Stop a drag in progress, if there is one, and put its card back
        -- also when the list is about to change under it (a rebuild, a
        save redrawing a card, a delete), which would otherwise reflow the
        rows around a card whose drawing is not where its record says."""
        drag = getattr(self, "_drag", None)
        self._drag = None
        if not drag or not drag["started"]:
            return
        self._end_list_drag(drag)
        self._put_lifted_card_back(drag)

    def _end_list_drag(self, drag):
        if drag.get("scroll_job") is not None:
            try:
                self.after_cancel(drag["scroll_job"])
            except (tk.TclError, ValueError):
                pass
            drag["scroll_job"] = None
        try:
            if drag.get("line") is not None:
                self.canvas.delete(drag["line"])
            self.canvas.configure(cursor="")
        except tk.TclError:
            pass
        self._list_cursor = ""

    def _put_lifted_card_back(self, drag):
        rec = (getattr(self, "_note_cards", None) or {}).get(drag["nid"])
        if rec is None or not drag.get("offset"):
            return
        try:
            self.canvas.move(rec["tag"], 0, -drag["offset"])
        except tk.TclError:
            pass
        drag["offset"] = 0

    def _bind_list_input(self):
        """The list's mouse and keyboard, bound once on the canvas that
        draws it -- a card is a drawing, and has no bindings of its own.

        Pinning, exporting, duplicating and deleting a note live in its
        right-click menu, so the keyboard reaches that menu too, and the
        list is walkable: a click puts the keyboard on the list, Down and Up
        move the ring from card to card, Enter or Space does what a click
        does, and the menu key opens the note's menu at the note.
        """
        cv = self.canvas
        cv.bind("<Button-1>", self._list_pressed)
        cv.bind("<Button-3>", self._list_right_pressed)
        cv.bind("<Motion>", self._list_pointer_moved)
        cv.bind("<Leave>", self._list_pointer_left)
        # A card can be dragged to another place (Custom order): the press
        # above arms it, these carry it and drop it, Escape puts it back.
        cv.bind("<B1-Motion>", self._list_dragged)
        cv.bind("<ButtonRelease-1>", self._list_released)
        cv.bind("<Escape>", self._list_drag_escape)
        cv.bind("<Down>", lambda _e: self._list_step(1))
        cv.bind("<Up>", lambda _e: self._list_step(-1))
        cv.bind("<Alt-Down>", lambda _e: self._list_move_by_keyboard(1))
        cv.bind("<Alt-Up>", lambda _e: self._list_move_by_keyboard(-1))
        cv.bind("<Return>", self._list_activate)
        cv.bind("<space>", self._list_activate)
        # The dedicated menu key has a different keysym per platform --
        # "App" on Windows, "Menu" on X11 -- and Tk RAISES on an unknown
        # one rather than ignoring it, so binding both unguarded takes the
        # whole note list down. It did: every card failed to build and all
        # nine qa scripts died on the Linux image while Windows was green.
        for seq in ("<Shift-F10>", "<App>", "<Menu>"):
            try:
                cv.bind(seq, self._list_open_menu)
            except tk.TclError:
                pass
        cv.bind("<FocusIn>", self._list_focus_in, add="+")
        cv.bind("<FocusOut>", self._list_focus_out, add="+")

    def _list_record_at(self, x, y):
        """The drawn row under a point given in the canvas widget's own
        coordinates, or None -- the gap between two cards is nobody's."""
        try:
            cy = self.canvas.canvasy(y)
        except tk.TclError:
            return None
        if not 0 <= x <= self.LIST_DRAW_WIDTH:
            return None
        for rec in getattr(self, "_list_drawn", None) or ():
            if rec["y0"] <= cy <= rec["y1"]:
                return rec
        return None

    def _list_pressed(self, event):
        """A click on the list: a header folds its group, a card opens its
        note -- or ticks it, in selection mode, where opening would defeat
        the point of picking several without leaving the list. Either way
        the keyboard comes to the list, on the card clicked, so Down and Up
        carry on from there. Nothing is returned: the window's own click
        handling (closing an open popup) still hears the click."""
        self._drag = None
        rec = self._list_record_at(event.x, event.y)
        if rec is None:
            return
        if rec["kind"] == "header":
            self._toggle_group_collapsed(rec["cat"])
            return
        note = rec["note"]
        nid = note["id"]
        if self.selection_mode:
            self._toggle_note_selected(nid, nid not in self.selected_note_ids)
            self._paint_card_check(nid)
            self._put_keyboard_on_card(nid)
            return
        # Not when the open refused to happen: Cancel on a repeating day's
        # save question keeps the person on the day they were editing.
        if self.open_note_in_tab(note) is not False:
            self._put_keyboard_on_card(nid)
            # Asked afresh: the open can have saved the note left behind,
            # and that save can have moved this card.
            rec = (getattr(self, "_note_cards", None) or {}).get(nid)
            if rec is not None:
                self._list_drag_arm(rec, event)

    def _list_right_pressed(self, event):
        """Right-click on a card opens that note's menu. A plain click on
        the same card opens the note, so the menu leaves out Open / Edit."""
        rec = self._list_record_at(event.x, event.y)
        if rec is None or rec["kind"] != "note":
            return
        self.show_note_context_menu(event, rec["note"], click_opens=True)

    def _list_pointer_moved(self, event):
        """The hand over a row, the plain pointer over the gaps -- what each
        card and header widget's own cursor used to say."""
        want = "hand2" if self._list_record_at(event.x, event.y) else ""
        if getattr(self, "_list_cursor", None) != want:
            self._list_cursor = want
            try:
                self.canvas.configure(cursor=want)
            except tk.TclError:
                pass

    def _list_pointer_left(self, _event=None):
        self._list_cursor = ""
        try:
            self.canvas.configure(cursor="")
        except tk.TclError:
            pass

    def _list_step(self, delta):
        """Down or Up on the list: the ring moves one card along."""
        current = getattr(self, "_focused_note_id", None)
        if current not in (getattr(self, "_note_cards", None) or {}):
            order = self._card_order()
            if order:
                self._put_keyboard_on_card(order[0])
            return "break"
        self._focus_card_by_offset(current, delta)
        return "break"

    def _list_activate(self, _event=None):
        """Enter or Space: what a click does -- open the note, or tick it
        in selection mode, where a keyboard that opened the note instead
        would be the one route that ignores the mode."""
        rec = (getattr(self, "_note_cards", None) or {}).get(
            getattr(self, "_focused_note_id", None))
        if rec is None:
            return "break"
        nid = rec["note"]["id"]
        if self.selection_mode:
            self._toggle_note_selected(nid, nid not in self.selected_note_ids)
            self._paint_card_check(nid)
        else:
            self.open_note_in_tab(rec["note"])
        return "break"

    def _list_open_menu(self, _event=None):
        """The note's own menu, opened at the note rather than wherever the
        pointer happens to rest. show_note_context_menu reads nothing off
        the event but x_root and y_root -- checked, not assumed -- so a
        tiny stand-in carries the card's place on screen."""
        rec = (getattr(self, "_note_cards", None) or {}).get(
            getattr(self, "_focused_note_id", None))
        if rec is None:
            return "break"
        try:
            y_on_screen = rec["y1"] - self.canvas.canvasy(0)
            self.show_note_context_menu(
                type("KeyEvent", (), {
                    "x_root": self.canvas.winfo_rootx() + 30,
                    "y_root": self.canvas.winfo_rooty() + int(y_on_screen) - 4,
                })(),
                rec["note"], click_opens=True)
        except tk.TclError:
            pass
        return "break"

    def _list_focus_in(self, _event=None):
        """The keyboard arrived on the list: the ring shows where it is --
        on the card it was last on, else the open note's, else the first."""
        self._keyboard_on_card = True
        cards = getattr(self, "_note_cards", None) or {}
        if getattr(self, "_focused_note_id", None) not in cards:
            order = self._card_order()
            if self.selected_note_id in cards:
                self._focused_note_id = self.selected_note_id
            elif order:
                self._focused_note_id = order[0]
        self._paint_ring(getattr(self, "_focused_note_id", None))

    def _list_focus_out(self, _event=None):
        """The keyboard left the list: the ring goes back to saying only
        which note is open."""
        self._keyboard_on_card = False
        self._paint_ring(getattr(self, "_focused_note_id", None))

    def _put_keyboard_on_card(self, note_id):
        """Give the keyboard to the list, with the ring on this card, and
        bring the card into view."""
        previous = getattr(self, "_focused_note_id", None)
        self._focused_note_id = note_id
        try:
            self.canvas.focus_set()
        except tk.TclError:
            return
        if previous != note_id:
            self._paint_ring(previous)
        self._paint_ring(note_id)
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is not None:
            self._scroll_row_into_view(rec)

    def _scroll_row_into_view(self, rec):
        """Scroll the list just far enough that this row is all on screen.
        The walk used to move the keyboard onto cards scrolled out of
        sight and leave the list where it was, which looks exactly like
        the field report's "Down does nothing" (whose own cause was a
        click that never gave the list the keyboard)."""
        cv = self.canvas
        try:
            region = self._list_extent()
            height = cv.winfo_height()
            if height <= 1:
                return
            total = max(1, region[3] - region[1])
            top = cv.canvasy(0)
            margin = rec["margin"]
            if rec["y0"] - margin[0] < top:
                target = rec["y0"] - margin[0]
            elif rec["y1"] + margin[1] > top + height:
                target = rec["y1"] + margin[1] - height
            else:
                return
            # A deliberate move beats a rebuild's still-pending restore.
            self._list_restore_px = None
            cv.yview_moveto(max(0, target - region[1]) / total)
        except tk.TclError:
            pass

    def _focus_card_by_offset(self, note_id, delta):
        """Move the ring `delta` cards along the list on screen.

        Asked of the ORDER THE CARDS ARE DRAWN IN rather than of
        self.notes: the list is sorted, filtered, searched and grouped, so
        the note after this one in the file is very often not the one
        underneath it on screen.
        """
        order = self._card_order()
        if note_id not in order:
            return
        target = order.index(note_id) + delta
        # The list is drawn a step at a time (see _draw_list_rows), and
        # the keyboard must not stop where the drawing happened to: walking
        # off the end of what is drawn draws the next step first. A loop,
        # because a step of a grouped list can be nothing but the headers
        # of collapsed groups.
        while target >= len(order) and getattr(self, "_list_pending", None):
            self._draw_list_rows(self.LIST_DRAW_STEP)
            order = self._card_order()
        if 0 <= target < len(order):
            self._put_keyboard_on_card(order[target])

    def _restore_card_focus(self):
        """Repaint the keyboard's ring after a rebuild.

        The keyboard itself never moves on a rebuild any more -- the canvas
        that holds it survives, only the drawing is replaced -- which ends
        a whole class of trouble the widget cards had: a keyboard left on
        a destroyed card, and a guard that had to decide, from focus_get()
        (which answers None whenever another program holds the desktop's
        foreground), whether to pull it back.
        """
        self._paint_ring(getattr(self, "_focused_note_id", None))

    def _card_ring_color(self, note_id):
        """What a card's ring says. The text colour where the keyboard is;
        accent for the note that is open; otherwise the card's own fill,
        which is no ring at all -- the thickness is on every card, so
        nothing shifts by two pixels as the ring moves down the list."""
        c = self.colors
        if (note_id == getattr(self, "_focused_note_id", None)
                and getattr(self, "_keyboard_on_card", False)):
            return c["text"]
        if note_id == self.selected_note_id:
            return c["accent"]
        return c["card"]

    def _paint_ring(self, note_id):
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None:
            return
        try:
            self.canvas.itemconfigure(
                rec["items"]["ring"], outline=self._card_ring_color(note_id))
        except tk.TclError:
            pass

    def _paint_card_check(self, note_id):
        """Tick or untick one card's box to match selected_note_ids."""
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None or "mark" not in rec["items"]:
            return
        try:
            self.canvas.itemconfigure(
                rec["items"]["mark"],
                state="normal" if note_id in self.selected_note_ids else "hidden")
        except tk.TclError:
            pass

    def _card_texts(self, note):
        """What a note's card says, and in which colour. The one definition
        the card is drawn from, wherever it is drawn.

        Every field is coerced to a string first, so one odd note (from
        older data, say) can never crash the whole list.
        """
        color = self.get_note_color(note)
        note_title = note.get("title") if isinstance(note.get("title"), str) else ""
        note_body = note.get("body") if isinstance(note.get("body"), str) else ""
        note_category = (note.get("category")
                         if isinstance(note.get("category"), str) else "General")

        title_text = _truncate(note_title, 42) if note_title else "(untitled)"
        if note.get("pinned"):
            title_text = "📌 " + title_text
        if is_recurring(note):
            title_text = "🔁 " + title_text

        # Table rows read as pipe soup at card size, so the preview shows
        # only the note's plain text; the tags row says a table is there.
        table_count = len(core_tables.find_blocks(note_body))
        if table_count:
            preview_src = " ".join(
                ln.strip() for ln in note_body.split("\n")
                if ln.strip() and not is_table_row(ln))
        else:
            preview_src = note_body.replace("\n", " ")
        # The 40-character cap is a glimpse, not a width: the drawing wraps
        # the glimpse to the card, so it stays readable however wide the
        # characters are.
        preview = preview_src[:40] + ("..." if len(preview_src) > 40 else "")

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
        if table_count:
            tags_text += ("   ▦ 1 table" if table_count == 1
                          else f"   ▦ {table_count} tables")
        checklist = note.get("checklist") or []
        if isinstance(checklist, list) and checklist:
            done = sum(1 for it in checklist
                       if isinstance(it, dict) and it.get("done"))
            tags_text += f"   ☑ {done}/{len(checklist)}"
        return {"title": title_text, "preview": preview, "tags": tags_text,
                "color": color}

    def _draw_note_card(self, note, top):
        """Draw one note's card with its top edge at canvas y `top`, and
        return its record.

        The same card the widgets drew -- a ring, the colour stripe, the
        title, a glimpse of the body and the tags row -- as rectangles and
        text on the list's canvas. Six windows to the operating system
        became none: that is what made showing the list again, scrolling
        it fast and rebuilding it cost what they did.

        Everything is wrapped to the card's width, never cut: a Label with
        no wraplength drew one line as long as its text and simply did not
        show the end of it -- a title lost "with the whole team", the tags
        row dropped the attachment count, and a clipped "1/2" read as "1/".
        The three spaces between tags give the wrap somewhere to break, so
        a second line starts at a tag rather than inside one.
        """
        cv = self.canvas
        c = self.colors
        nid = note["id"]
        tag = "card%s" % nid
        tags = ("row", tag)
        says = self._card_texts(note)
        x0 = self.CARD_INSET_X
        x1 = self.LIST_DRAW_WIDTH - self.CARD_INSET_X
        left = x0 + self.CARD_RING
        check_x = None
        if getattr(self, "selection_mode", False):
            # Leftmost, ahead of the stripe, where the Checkbutton stood:
            # packed with 6 pixels before it and 22 wide, measured on the
            # widget card. Guessed at 17 first, the photograph showed the
            # stripe and text five pixels left of where they had been.
            check_x = left + 8
            left += 6 + 22
        stripe_x = left
        content_left = stripe_x + self.CARD_STRIPE + self.CARD_PAD[0]
        content_right = x1 - self.CARD_RING - self.CARD_PAD[0]
        text_x = content_left + 2
        wrap = max(40, content_right - content_left - 4)
        inset = self.CARD_TEXT_INSET
        items = {}
        y = top + self.CARD_RING + self.CARD_PAD[1] + inset
        # " " for an empty line: a Label kept a line's height for no text,
        # and the card must not change shape because a body is empty.
        items["title"] = cv.create_text(
            text_x, y, anchor="nw", width=wrap, text=says["title"] or " ",
            font=("Segoe UI", 11, "bold"), fill=c["text"], tags=tags)
        y = cv.bbox(items["title"])[3] + 2 * inset
        items["preview"] = cv.create_text(
            text_x, y, anchor="nw", width=wrap, text=says["preview"] or " ",
            font=("Segoe UI", 9), fill=c["subtext"], tags=tags)
        y = cv.bbox(items["preview"])[3] + 2 * inset + 3
        items["tags"] = cv.create_text(
            text_x, y, anchor="nw", width=wrap, text=says["tags"] or " ",
            font=("Segoe UI", 8, "bold"), fill=says["color"], tags=tags)
        bottom = (cv.bbox(items["tags"])[3] + inset + self.CARD_PAD[1]
                  + self.CARD_RING)
        items["bg"] = cv.create_rectangle(
            x0, top, x1, bottom, fill=c["card"], outline="", tags=tags)
        cv.tag_lower(items["bg"], items["title"])
        items["stripe"] = cv.create_rectangle(
            stripe_x, top + self.CARD_RING, stripe_x + self.CARD_STRIPE,
            bottom - self.CARD_RING, fill=says["color"], outline="", tags=tags)
        if check_x is not None:
            mid = (top + bottom) // 2
            half = self.CARD_CHECK // 2
            items["check"] = cv.create_rectangle(
                check_x, mid - half, check_x + self.CARD_CHECK, mid + half + 1,
                fill=c["check_well"], outline=c["subtext"], tags=tags)
            items["mark"] = cv.create_line(
                check_x + 3, mid, check_x + 6, mid + 3, check_x + 10, mid - 3,
                width=2, fill=self.CARD_CHECK_MARK, tags=tags,
                state="normal" if nid in self.selected_note_ids else "hidden")
        items["ring"] = cv.create_rectangle(
            x0 + 1, top + 1, x1 - 1, bottom - 1, width=self.CARD_RING,
            outline=self._card_ring_color(nid), tags=tags)
        rec = {"kind": "note", "key": ("note", nid), "tag": tag, "note": note,
               "y0": top, "y1": bottom, "margin": self.CARD_MARGIN,
               "items": items}
        self._note_cards[nid] = rec
        return rec

    def _card_order(self):
        """The ids of the drawn cards, in the order they stand on screen."""
        return [rec["note"]["id"] for rec in getattr(self, "_list_drawn", None) or ()
                if rec["kind"] == "note"]

    def _card_view(self, note_id):
        """What one drawn card shows, read back from the drawing itself --
        its texts, its colours, where it is -- or None when it is not drawn.
        The question the checks ask, now that a card has no widgets to
        read."""
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None:
            return None
        cv = self.canvas
        it = rec["items"]
        view = {
            "title": cv.itemcget(it["title"], "text"),
            "preview": cv.itemcget(it["preview"], "text"),
            "tags": cv.itemcget(it["tags"], "text"),
            "title_fill": cv.itemcget(it["title"], "fill"),
            "preview_fill": cv.itemcget(it["preview"], "fill"),
            "tags_fill": cv.itemcget(it["tags"], "fill"),
            "bg": cv.itemcget(it["bg"], "fill"),
            "stripe": cv.itemcget(it["stripe"], "fill"),
            "ring": cv.itemcget(it["ring"], "outline"),
            "y0": rec["y0"], "y1": rec["y1"],
            "text_boxes": [cv.bbox(it[k]) for k in ("title", "preview", "tags")],
            "box": (self.CARD_INSET_X, rec["y0"],
                    self.LIST_DRAW_WIDTH - self.CARD_INSET_X, rec["y1"]),
            "checked": None,
        }
        if "mark" in it:
            view["checked"] = cv.itemcget(it["mark"], "state") != "hidden"
            view["check_well"] = cv.itemcget(it["check"], "fill")
            view["check_mark"] = cv.itemcget(it["mark"], "fill")
        return view

    def _header_view(self, cat):
        """What one drawn category header shows, or None."""
        rec = (getattr(self, "_group_headers", None) or {}).get(cat)
        if rec is None:
            return None
        cv = self.canvas
        return {"label": cv.itemcget(rec["items"]["label"], "text"),
                "caret": cv.itemcget(rec["items"]["caret"], "text"),
                "y0": rec["y0"], "y1": rec["y1"]}

    def _card_point(self, note_id):
        """A point inside a drawn card, in the canvas widget's coordinates
        -- where a click on it lands. None when it is not drawn."""
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None:
            return None
        return (self.LIST_DRAW_WIDTH // 2,
                int((rec["y0"] + rec["y1"]) / 2 - self.canvas.canvasy(0)))

    def _recolor_note_cards(self):
        """Re-apply the current theme's colours to the drawn list, instead
        of drawing it again just because the palette changed.

        The stripe and tag colours are deliberately RECOMPUTED from the
        note via get_note_color() rather than colour-swapped, so a note's
        own custom colour survives a theme switch exactly as it would
        through a real rebuild. Runs after _recolor_stragglers for the same
        reason, as it always has -- which no longer reaches the list at all
        (a drawing is not a widget), so this is the list's only recolour.
        """
        c = self.colors
        cv = getattr(self, "canvas", None)
        if cv is None:
            return
        try:
            for note_id, rec in list((getattr(self, "_note_cards", None) or {}).items()):
                it = rec["items"]
                note_color = self.get_note_color(rec["note"] or {})
                cv.itemconfigure(it["bg"], fill=c["card"])
                cv.itemconfigure(it["stripe"], fill=note_color)
                cv.itemconfigure(it["title"], fill=c["text"])
                cv.itemconfigure(it["preview"], fill=c["subtext"])
                cv.itemconfigure(it["tags"], fill=note_color)
                cv.itemconfigure(it["ring"], outline=self._card_ring_color(note_id))
                if "check" in it:
                    cv.itemconfigure(it["check"], fill=c["check_well"],
                                     outline=c["subtext"])
            for cat, rec in list((getattr(self, "_group_headers", None) or {}).items()):
                it = rec["items"]
                dot = CATEGORY_COLORS.get(cat, c["accent"])
                cv.itemconfigure(it["bg"], fill=c["sidebar"])
                cv.itemconfigure(it["dot"], fill=dot, outline=dot)
                cv.itemconfigure(it["caret"], fill=c["subtext"])
                cv.itemconfigure(it["label"], fill=c["text"])
            cv.itemconfigure("list_empty", fill=c["subtext"])
        except tk.TclError:
            pass

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

    def _remove_note_cards(self, note_ids):
        """Take deleted notes' cards off the list without rebuilding it.

        The fourth member of a family the list already has -- alongside
        _recolor_note_cards, _apply_selection_mode_to_cards and
        _update_open_highlight, each written because a full rebuild
        "visibly flickered the whole list" for a change that touched a
        few cards. Deleting a note was the one frequent action still
        paying the full price: 120 widgets destroyed and remade, 115ms,
        to take one card away. Field-reported as "the picture breaks a
        little and rebuilds itself".

        On the drawing it is: delete the card's items, slide every row
        below it up by what it took, and bring the headers' counts down.

        Returns True when the list on screen now matches the data, and
        False when it could not be done surgically -- the caller then
        falls back to refresh_note_list(). Every uncertain case returns
        False on purpose: a list that quietly disagrees with the notes
        is far worse than one that flickers.
        """
        # The rows are about to slide; a card lifted by a drag goes back
        # to its record first (see _cancel_list_drag).
        self._cancel_list_drag()
        cards = getattr(self, "_note_cards", None)
        drawn = getattr(self, "_list_drawn", None)
        if cards is None or drawn is None:
            return False
        gone = set(note_ids)
        focused = getattr(self, "_focused_note_id", None)
        order_before = self._card_order()
        kept = []
        try:
            for rec in drawn:
                if rec["kind"] == "note" and rec["note"]["id"] in gone:
                    self.canvas.delete(rec["tag"])
                    cards.pop(rec["note"]["id"], None)
                    continue
                kept.append(rec)
            # Headers, whether or not a card came off: a COLLAPSED group
            # draws no cards at all, so deleting a note from one takes
            # nothing off the screen while its header's count still has to
            # come down. Counts come from the ids each header was drawn
            # with, never from the cards under it. A header left counting
            # nothing goes, with its group.
            headers = getattr(self, "_group_headers", None) or {}
            still_drawn = []
            for rec in kept:
                if rec["kind"] != "header":
                    still_drawn.append(rec)
                    continue
                rec["ids"] = [i for i in rec["ids"] if i not in gone]
                if rec["ids"]:
                    self.canvas.itemconfigure(
                        rec["items"]["label"],
                        text=f"{rec['cat']} ({len(rec['ids'])})")
                    still_drawn.append(rec)
                else:
                    self.canvas.delete(rec["tag"])
                    headers.pop(rec["cat"], None)
        except tk.TclError:
            return False
        self._list_drawn = still_drawn
        # And the rows still waiting to be drawn (see _draw_list_rows):
        # left alone, scrolling down would draw the card of a note that
        # is gone, under a header still counting it.
        waiting = []
        for row in getattr(self, "_list_pending", None) or ():
            if row[0] == "note":
                if row[1].get("id") not in gone:
                    waiting.append(row)
                continue
            kept_notes = [n for n in row[2] if n.get("id") not in gone]
            if kept_notes:
                waiting.append((row[0], row[1], kept_notes, row[3]))
        self._list_pending = waiting
        if not self._list_drawn:
            # Nothing drawn at all now. An empty list is not simply "no
            # cards": it carries a message, and which message depends on
            # whether anything is filtered. That belongs to
            # refresh_note_list().
            return False
        # From the top: only the rows below a gap actually move, so the rows
        # above cost a comparison each.
        self._reflow_list(0)
        # The keyboard's ring was on a card that went: it moves to the card
        # that took its place, so the walk carries on from where it was.
        if focused in gone and focused in order_before:
            order = self._card_order()
            if order:
                place = min(order_before.index(focused), len(order) - 1)
                self._focused_note_id = order[place]
                self._paint_ring(self._focused_note_id)
        # What was taken off may have left less than a screen drawn.
        self._ask_for_top_up()
        # refresh_note_list() recomputes these on its way past, and
        # Settings may be open on them right now. Due even when no card
        # was drawn -- a note still left the notebook.
        self._render_statistics()
        return True

    def _redraw_saved_card(self, note_id):
        """Bring the list up to date after ONE note was saved, by redrawing
        that note's card and nothing else.

        A save used to rebuild the whole list, and autosave saves at every
        pause in typing: each time someone stopped to think, the window
        froze for about a second with 100 notes, three with 300, twelve
        with 1,000 -- where this takes under a tenth of a second. The sixth
        member of the family that exists for this reason (see
        _remove_note_cards).

        What the list shows is worked out afresh (_list_rows) and compared
        with what it showed. When the only difference is this note -- its
        text, where the sort now puts it, whether the search still lets it
        through -- its card is drawn again in its new place and the rows
        between the two places slide, all in one repaint of the one canvas:
        nothing on screen empties or reappears. Anything more returns
        False, and the caller rebuilds: a group whose count changed (the
        note moved category, or is new, while the list is grouped), an
        empty list that needs its message, a list never drawn. A list that
        quietly disagrees with the notes is far worse than one that is slow
        to catch up.
        """
        # As in _remove_note_cards: rows are about to move.
        self._cancel_list_drag()
        cards = getattr(self, "_note_cards", None)
        drawn = getattr(self, "_list_drawn", None)
        pending = getattr(self, "_list_pending", None)
        if cards is None or not drawn or pending is None:
            return False

        def key_of(row):
            return (row[0], row[1] if row[0] == "header" else row[1]["id"])

        rows = self._list_rows()
        new_keys = [key_of(row) for row in rows]
        old_drawn_keys = [rec["key"] for rec in drawn]
        old_keys = old_drawn_keys + [key_of(row) for row in pending]
        own = ("note", note_id)
        if [k for k in new_keys if k != own] != [k for k in old_keys if k != own]:
            return False
        # Leaving the others where they were is not enough when grouped: a
        # header's "(N)" counts its group, and the note may have joined or
        # left one without any other row moving.
        headers = getattr(self, "_group_headers", None) or {}
        waiting_groups = {row[1]: row[2] for row in pending if row[0] == "header"}
        for row in rows:
            if row[0] != "header":
                continue
            if row[1] in headers:
                before = set(headers[row[1]].get("ids", ()))
            elif row[1] in waiting_groups:
                before = {n["id"] for n in waiting_groups[row[1]]}
            else:
                return False
            if {n["id"] for n in row[2]} != before:
                return False

        # Where the card goes: among the drawn rows, or -- when the sort
        # moved it past them -- among the ones still waiting, which is
        # where a rebuild would have left it too. Landing just below the
        # last drawn row, it is drawn if it was before, or if nothing was
        # waiting: a list drawn to its end stays drawn to its end. Left to
        # wait there, the card of a brand-new note in a short list would
        # appear only once something scrolled.
        was_drawn = own in old_drawn_keys
        old_at = old_drawn_keys.index(own) if was_drawn else None
        others_drawn = len(drawn) - (1 if was_drawn else 0)
        new_at = new_keys.index(own) if own in new_keys else None
        drawn_now = new_at is not None and (
            new_at < others_drawn
            or (new_at == others_drawn and (was_drawn or not pending)))
        depth = others_drawn + (1 if drawn_now else 0)
        try:
            if was_drawn:
                old = drawn.pop(old_at)
                cards.pop(note_id, None)
                self.canvas.delete(old["tag"])
            if drawn_now:
                # Drawn anywhere and put in its place by the reflow below,
                # which slides every row between the old place and the new
                # one -- the drawing changes in one repaint.
                drawn.insert(new_at, self._draw_note_card(rows[new_at][1], 0))
        except tk.TclError:
            return False
        starts = [i for i in (old_at, new_at if drawn_now else None) if i is not None]
        self._reflow_list(min(starts) if starts else len(drawn))
        self._list_pending = rows[depth:]
        for row in rows[:depth]:
            if row[0] == "header" and row[1] in headers:
                headers[row[1]]["ids"] = [n["id"] for n in row[2]]
        # A card that went to wait below may have left the drawn part
        # shorter than the view, and whether the canvas reports that
        # depends on whether anything changed size -- so ask directly.
        self._ask_for_top_up()
        # Everything else refresh_note_list does on its way past.
        self._render_statistics()
        if getattr(self, "selection_mode", False):
            self._update_bulk_selected_label()
        return True

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
        """Add or remove the per-card tick box as selection mode turns on or
        off. The box takes room at the card's left, so the text wraps
        again and the cards change height: the drawn part of the list is
        drawn again, as deep as it was and where it was scrolled -- which
        on the drawing is one repaint, not the flicker of the widget list
        that made this surgical in the first place. What a click does is
        decided when the click arrives (_list_pressed), so nothing needs
        rebinding."""
        self.refresh_note_list()

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
        # Same idea as the Select-all label below, from the same place: what
        # "Pin" will do depends on what is ticked at this moment, so the word
        # is worked out wherever the selection changes rather than only when
        # the bar is built.
        self._refresh_bulk_pin_label()
        # The button says what pressing it will do, which changes once
        # everything on screen is already selected. Asked from the same
        # _visible_note_ids() the press itself uses, so the word and the
        # action cannot disagree.
        button = getattr(self, "_bulk_select_all_btn", None)
        if button is None:
            return
        try:
            visible = self._visible_note_ids()
            button.config(text="Unselect all"
                          if visible and visible <= self.selected_note_ids
                          else "Select all")
        except (tk.TclError, AttributeError):
            pass

    @staticmethod
    def _query_matches_note(query, note):
        """The ONE definition of "this note matches the sidebar search".
        The list render and Select-all-visible each carried a hand-rolled
        copy, and the copies drifted: the list stripped table plumbing
        from bodies (searching "---" no longer matches every table note)
        while Select all matched the raw body — so "Select all visible"
        quietly selected notes the filter had hidden, and bulk actions
        hit them. Every field is coerced to a string first, so a
        missing/None field from older data can't crash the render."""
        def _txt(value):
            return value.lower() if isinstance(value, str) else ""

        body = note.get("body")
        if isinstance(body, str) and core_tables.CELL in body:
            body_txt = core_tables.content_text(body).lower()
        else:
            body_txt = _txt(body)
        return (query in _txt(note.get("title"))
                or query in body_txt
                or query in _txt(note.get("comments")))

    def _visible_note_ids(self):
        """The notes the list is showing right now, by id.

        The ONE definition, for the same reason _query_matches_note is
        one: the moment two places work out "what is on screen" for
        themselves, they drift, and this project has already paid for
        that once (see that method's note). Select-all and the label
        that decides whether everything IS selected have to mean exactly
        the same set, or the button offers to select what is already
        selected.

        Asked of the notes, not of the cards: the list draws a step at a
        time, and "all" means every note it shows, drawn yet or not.
        """
        return {n["id"] for n in self._notes_on_the_list()}

    def _bulk_select_all(self):
        """Select every note the list is showing — or, if they are all
        already selected, let them all go again.

        One button rather than two, because the second is only ever
        wanted straight after the first: a mis-aimed "Select all" used to
        mean leaving selection mode entirely and starting over, since
        nothing else clears a selection in one gesture. It respects
        whatever search or category filter is active, so "all" is what is
        on screen, never the whole notebook.
        """
        visible = self._visible_note_ids()
        if visible and visible <= self.selected_note_ids:
            self.selected_note_ids = set()
        else:
            self.selected_note_ids = set(visible)
        self._update_bulk_selected_label()
        # Not refresh_note_list(). Nothing about the notes changed -- only
        # which of them are ticked -- and rebuilding the list to move a
        # tick costs 140 widgets and ~170ms, which is the flicker this
        # button was reported for. The fifth member of the family that
        # already exists for exactly this reason (see _recolor_note_cards,
        # _apply_selection_mode_to_cards, _update_open_highlight,
        # _remove_note_cards).
        self._sync_card_checkboxes()

    def _sync_card_checkboxes(self):
        """Make every drawn card's tick box agree with selected_note_ids.

        Only the drawing changes: nothing here reports a change back, which
        matters -- _toggle_note_selected has already been told, and each box
        re-reporting it would have the label recount twenty times over.

        Cards that are not drawn (filtered out, or inside a collapsed
        group) have no box to update, and need none: _draw_note_card reads
        selected_note_ids for the box it draws.
        """
        for note_id in list((getattr(self, "_note_cards", None) or {})):
            self._paint_card_check(note_id)

    def _series_warning(self, notes):
        """One sentence saying how many of `notes` are whole repeating
        series, or "" when none are.

        A confirmation that counts notes is telling the truth and still
        hiding the consequence: a repeating series is ONE note in every
        list and every count, and deleting it takes every occurrence it
        has. The single-note delete has always asked "Delete this entire
        repeating series?"; none of the routes that act on a selection
        said anything at all -- neither the bulk move to trash, nor
        either of the two permanent deletes in the Trash, where there is
        no way back at all.

        Written once, here, because four copies of a sentence is four
        chances for them to stop agreeing. Field-reported: "it doesn't
        tell me one of them is a series".
        """
        count = sum(1 for n in notes if isinstance(n, dict) and is_recurring(n))
        if not count:
            return ""
        if count == 1:
            if len(notes) == 1:
                return ("\n\nThis is a repeating series — every occurrence "
                        "goes with it.")
            return ("\n\n1 of them is a repeating series — every occurrence "
                    "goes with it.")
        return (f"\n\n{count} of them are repeating series — every occurrence "
                "goes with them.")

    def _category_override_warning(self, notes):
        """Name the notes a category change will not reach all the way into.

        `category` is in OVERRIDABLE_FIELDS, so a repeating note can carry
        a per-day patch giving one occurrence its own category. A bulk
        change writes the series' own category and leaves those days
        alone, which is the right answer — a day filed by hand was filed
        deliberately — but it makes "this replaces the category on each of
        them" not quite true. Said out loud rather than promised away,
        the same way the trash confirmation names attached files.
        """
        count = 0
        for note in notes:
            if not isinstance(note, dict):
                continue
            patches = note.get("overrides") or {}
            if not isinstance(patches, dict):
                continue
            if any(isinstance(p, dict) and p.get("category")
                   for p in patches.values()):
                count += 1
        if not count:
            return ""
        if count == 1:
            return ("\n\nOne of them has a day with its own category, and "
                    "that day keeps it.")
        return (f"\n\n{count} of them have days with their own category, and "
                "those days keep them.")

    def _bulk_move_to_trash(self):
        if not self.selected_note_ids:
            self.show_info("Nothing selected", "Tick one or more notes first.")
            return
        # Save what the editor holds first, as the single delete from a
        # note's menu does: the note on screen may be one of the ticked
        # ones, and its unsaved typing belongs in the Trash copy (and in
        # what Undo brings back), not in an editor about to be cleared.
        # Cancel on a day's save question stops the delete here.
        if self._flush_autosave() is False:
            return
        count = len(self.selected_note_ids)
        to_trash = [n for n in self.notes if n["id"] in self.selected_note_ids]
        attachment_count = sum(len(n.get("attachments") or []) for n in to_trash)
        warning = self._series_warning(to_trash)
        if attachment_count:
            plural = "s" if attachment_count != 1 else ""
            warning += f"\n\n{attachment_count} attached file{plural} will go to trash with them."
        noun = "note" if count == 1 else "notes"
        if not self.ask_yes_no(
            "Move to trash",
            f"Move {count} selected {noun} to the trash? "
            f"You can restore {'it' if count == 1 else 'them'} within "
            f"{trash_retention_days()} days.{warning}",
            # Enter answers a question now, and a reflexive Enter must not
            # be the one that deletes.
            icon="question", default="no"
        ):
            return
        marks = [(e.get("id"), e.get("deleted_at"))
                 for e in self._move_notes_to_trash(to_trash)]
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
        # Otherwise the editor holds a note that was not trashed, and it
        # stays as it is -- see _delete_note for what "switching" to it
        # from its stored copy used to cost.
        self._sync_editor_snapshot()
        self._exit_selection_mode_after_bulk_action()
        self.render_calendar()
        self.set_status(f"Moved {count} note(s) to trash")
        # The bulk route is the easiest one to regret: a tick box, a
        # confirm, and a list that was filtered by whatever was typed in
        # the search box at the time.
        self._show_toast(
            f"Moved {count} {'note' if count == 1 else 'notes'} to Trash",
            action=lambda: self._undo_trash(marks))

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
            # The popup goes first, ahead of anything modal: it is an
            # overrideredirect Toplevel that never takes focus, so a
            # dialog raised while it is still up leaves it floating over
            # the question being asked.
            self._dismiss_mini_popup()
            # The editor may be holding one of these notes, with its own
            # category dropdown still showing the old value -- and the
            # editor's next save writes that dropdown back, undoing the
            # change with nothing on screen to say so. Found by an audit
            # walking a bulk action followed by ordinary typing; the same
            # shape as the import route's, fixed the day before.
            #
            # Flush FIRST so anything typed is saved under the old
            # category rather than dropped, then change, then bring the
            # editor onto the result. It also has to happen before the
            # question rather than only before the write: that dropdown
            # may name a category the note is already leaving, and a
            # dialog counting the categories ahead of the flush would be
            # describing a state that no longer exists by the time the
            # user answers.
            touched = set(self.selected_note_ids)
            if self._flush_autosave() is False:
                return  # Cancel on a day's save question: nothing moves
            to_move = [n for n in self.notes if n["id"] in touched]
            if not to_move:
                # The ticked notes are gone. A dialog naming a count it
                # cannot deliver is worse than saying so plainly.
                self.show_info("Nothing to move", "Those notes are no longer here.")
                return
            count = len(to_move)
            noun = "note" if count == 1 else "notes"
            from_count = len({n.get("category") for n in to_move})
            spread = ("" if from_count < 2
                      else f" They sit in {from_count} different categories today.")
            if not self.ask_yes_no(
                "Change category",
                f"Move {count} selected {noun} to \u201c{cat}\u201d?{spread} "
                f"This replaces the category on "
                f"{'it' if count == 1 else 'each of them'}."
                f"{self._category_override_warning(to_move)}",
                icon="question"
            ):
                return
            # One mark per note, recording what THAT note is being moved
            # out of. A single remembered "old category" for the batch
            # would file every note back under whichever one happened to
            # be read first -- and a mixed selection is precisely what a
            # bulk change is for, so it is also what an undo has to
            # survive.
            marks = [(n["id"], n.get("category"), n.get("updated"))
                     for n in to_move]
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for n in to_move:
                n["category"] = cat
                n["updated"] = stamp
            self.save_notes()
            self._editor_follows_external_change(touched)
            self._exit_selection_mode_after_bulk_action()
            # The calendar draws a note with no colour of its own in its
            # category's -- its dots, and an open day's stripes.
            self.render_calendar()
            self.set_status(f"Moved {count} note(s) to \u201c{cat}\u201d")
            # This was the one action in the bar that changed stored data
            # with neither a question nor a way back, while the button
            # beside it had both -- and the categories it overwrote were
            # gone from the file the moment it ran.
            self._show_toast(
                f"Moved {count} {noun} to \u201c{cat}\u201d",
                action=lambda: self._undo_bulk_category(marks, cat))

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

        # A way out that says so. Every row here refiles every ticked note,
        # and until now the only way to leave without picking one was to
        # click empty space and hope -- no Cancel, no close glyph, and
        # Escape went to the app window, which had no binding for it.
        self._bulk_popup_cancel(frame)
        self._place_dropdown_popup(pop, self._bulk_category_btn)

    def _bulk_export(self):
        """Format picker for exporting every ticked note, one file each."""
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
        tk.Label(frame,
                 text=f"Export {len(self.selected_note_ids)} note(s) as:",
                 bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=6,
                                                    pady=(4, 2))
        for fmt, fmt_label in (("html", "Web pages (.html)"),
                               ("txt", "Plain text (.txt)")):
            row = tk.Frame(frame, bg=self.colors["card"], cursor="hand2")
            row.pack(fill="x")
            lbl = tk.Label(row, text=fmt_label, bg=self.colors["card"],
                           fg=self.colors["text"], font=("Segoe UI", 9),
                           anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=10, pady=5)
            for w in (row, lbl):
                w.bind("<Button-1>",
                       lambda e, f=fmt: (self._dismiss_mini_popup(),
                                         self._bulk_export_run(f)))
        self._bulk_popup_cancel(frame)
        self._place_dropdown_popup(pop, self._bulk_export_btn)

    def _bulk_popup_cancel(self, frame):
        """A worded way out of a bulk popup whose every other row acts.

        The Import and Share panels have carried a "Close" for a long time;
        these two had nothing, so leaving meant clicking empty space and
        trusting that it counted. Escape now works as well, but a keystroke
        is not a visible affordance -- the survey's point was that the way
        out has to be on the screen.
        """
        tk.Button(frame, text="Cancel", command=self._dismiss_mini_popup,
                  relief="flat", cursor="hand2", bd=0,
                  bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 8)).pack(fill="x", padx=6, pady=(6, 4),
                                             ipady=2)

    def _bulk_export_run(self, fmt):
        """Write every ticked note into a chosen folder, one file per
        note, through the same rendering the single-note export uses.
        Same-title notes get " (2)", " (3)" -- never an overwrite."""
        ext = {"html": ".html", "txt": ".txt"}[fmt]
        folder = filedialog.askdirectory(
            title=f"Export {len(self.selected_note_ids)} note(s) into…")
        if not folder:
            return
        written, failed, used = 0, 0, set()
        for note in self.notes:
            if note["id"] not in self.selected_note_ids:
                continue
            title = (note.get("title") or "").strip() or "Untitled note"
            safe = (re.sub(r'[<>:"/\\|?*\n\r\t]', "_", title)
                    .strip(" ._")[:60] or "note")
            name, n = safe, 1
            while (name.lower() in used
                   or os.path.exists(os.path.join(folder, name + ext))):
                n += 1
                name = f"{safe} ({n})"
            used.add(name.lower())
            try:
                with open(os.path.join(folder, name + ext), "w",
                          encoding="utf-8") as f:
                    f.write(self._note_export_content(note, fmt, title))
                written += 1
            except (IOError, OSError):
                failed += 1
        if failed:
            self.show_error(
                "Export incomplete",
                f"{written} note(s) exported, {failed} failed to write.")
        else:
            self._show_toast(f"Exported {written} note(s)")
        self._exit_selection_mode_after_bulk_action()
        if written and not failed and self.ask_yes_no(
                "Open the folder?",
                f"{written} file(s) were saved.\n\nOpen the folder now?",
                icon="question"):
            try:
                os.startfile(folder)
            except OSError:
                self.set_status(f"Saved to {folder}")

    # ---------- Note actions ----------
    # ---------- Editor state snapshot (for multi-note tabs) ----------
    def capture_editor_state(self):
        """Snapshot everything the editor currently holds, so a note tab can be
        set aside and restored later exactly as the user left it — including
        unsaved edits. This is the backbone of having several notes open."""
        # Grid cells buffer their edits in Entry widgets; anything captured
        # here -- autosave, tab switching, the dirty poll -- must see them
        # in the text, or a keystroke still sitting in a cell would be lost.
        self._flush_table_grids()
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
            # Canonical, matching what the save stores -- see
            # with_caret_line. Without it, the dirty comparison reads a
            # table-ending note as changed forever.
            "body": with_caret_line(self.body_text.get("1.0", "end-1c")),
            "formatting": self._extract_formatting(self.body_text),
            "paragraphs": self._extract_paragraphs(self.body_text),
            "pending_styles": sorted(self._pending_styles),
            "pending_text_color": self._pending_text_color,
            "pending_font_size": self._pending_font_size,
            "pending_font_family": self._pending_font_family,
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
            self._insert_title(st["title"])
            self.title_entry.config(fg=self.colors["text"])
        else:
            self._insert_title("Note title...")
            self.title_entry.config(fg=self.colors["subtext"])

        # Restore this tab's own pending style (if any) before inserting
        # its body — set after the insert instead, a leftover pending style
        # from whatever tab was open a moment ago could tag this one's text.
        self._pending_styles = set(st.get("pending_styles") or [])
        self._pending_text_color = st.get("pending_text_color")
        self._pending_font_size = st.get("pending_font_size")
        self._pending_font_family = st.get("pending_font_family")
        self._pending_highlight_color = st.get("pending_highlight_color")
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", st["body"])
        self._apply_formatting(self.body_text, st.get("formatting", []))
        self._apply_paragraphs(self.body_text, st.get("paragraphs", []))
        self._render_table_grids()
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", st["comments"])
        self.category_var.set(st["category"])

        self._show_date_in_field(st["date"])

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
        self._find_on_context_switch()
        self._share_code_on_context_switch()
        self._update_occurrence_banner()
        # A tab snapshot never carries a calendar trip — restoring one
        # means the editor's context changed, so any pending return is
        # over (a stale one made a later Save yank the user onto an
        # unrelated calendar day; see the delete cleanup's switch path).
        self._pending_calendar_return = None
        self._update_calendar_return_button()

    def _editor_state_has_content(self, st):
        """The ONE answer to "does the editor hold anything worth keeping?".

        Six gates used to hand-roll this test with six slightly different
        field lists, and the drift was a real data-loss bug twice over: a
        comments-only note was silently discarded on every route, and the
        emptying of a saved note was thrown away by the automatic gates
        even after the explicit-Save path learned to accept it. Every gate
        asks here now, so the next field a note grows gets counted once,
        in one place, or visibly not at all.

        The date is deliberately NOT counted: the calendar's
        new-note-for-a-day flow prefills the date field, so an abandoned
        empty editor would otherwise auto-save as a junk date-only note on
        every switch-away. The explicit Save path adds the date check
        itself — pressing Save is what makes a bare dated reminder
        deliberate."""
        recurrence = st.get("recurrence") or {}
        freq = recurrence.get("freq") if isinstance(recurrence, dict) else ""
        return bool((st.get("title") or "").strip()
                    or (st.get("body") or "").strip()
                    or (st.get("comments") or "").strip()
                    or st.get("attachments")
                    or st.get("checklist")
                    or freq)

    def _editing_saved_note(self):
        """True when the editor points at a note that exists on disk — the
        exemption that lets a saved note be deliberately emptied (an
        ordinary edit) while a blank never-saved editor stays junk-proof."""
        return (self.selected_note_id is not None
                and self.find_note(self.selected_note_id) is not None)

    def editor_state_matches_saved(self, st):
        """True if the captured state equals what's on disk for its note — i.e.
        there are no unsaved changes. A brand-new note (no id) counts as unsaved
        the moment it has any content."""
        note_id = st["selected_note_id"]
        if note_id is None:
            # New, never-saved note: "clean" only if completely empty.
            # The date DOES count here, unlike in the shared content test:
            # a prefilled date must read as "differs from pristine" so the
            # dirty machinery sees it, while the autosave gates still
            # refuse to persist a date-only editor.
            return not (self._editor_state_has_content(st)
                        or (st.get("date") or "").strip())
        note = self.find_note(note_id)
        if note is None:
            return False  # underlying note deleted -> treat as dirty/gone

        # Compare against the effective (occurrence-aware) content.
        occ = st.get("occurrence_date")
        if occ and is_recurring(note):
            # An occurrence override carries ONLY the overridable fields
            # (title/body/comments/category/color) — it is plain text by
            # design, never its own formatting, paragraphs, checklist,
            # attachments, date or recurrence: those stay the series'.
            # Comparing the series-owned fields here made a just-saved
            # occurrence read as dirty FOREVER (its body differs from
            # the base's, so the base formatting spans never matched) —
            # which made Back to Calendar's cancel guard believe the
            # scope prompt was cancelled and refuse to navigate, asking
            # again on every click (field report).
            shown = effective_note(note, occ)
            # The BODY compares unstripped, matching what the save stores:
            # T0-4 made leading/trailing whitespace part of the note, and a
            # stripped comparison here made every whitespace-only edit read
            # as "no change" — so the autosave, the flush and the dirty dot
            # all ignored exactly the characters the save had just learned
            # to keep. The comments now follow the body's rule, stored as
            # typed, so they compare unstripped too. Titles are STORED
            # stripped, so their stripped comparison is the honest one.
            if not (st["title"].strip() == shown["title"].strip()
                    and st["body"] == shown["body"]
                    and st["comments"] == (shown.get("comments") or "")
                    and st["category"] == shown["category"]
                    and st["color"] == shown.get("color", "")):
                return False
            # ...and the SERIES-owned fields against the BASE note, which
            # is where the editor loaded them from: load_note reads
            # checklist, attachments and date off `note`, never off
            # `shown`, even in occurrence view. So they match on load (a
            # clean occurrence stays clean) and an edit to one of them
            # here is an edit to the series -- which has to be visible,
            # or it is silently thrown away. Left out, a checklist item
            # ticked while looking at one day was invisible to every save
            # gate: the editor asked for the save and the comparator
            # vetoed it, and the tick never reached disk.
            #
            # Formatting and paragraphs stay OUT, for the reason above:
            # an override is plain text, so load_note only re-applies the
            # base's spans when the shown body equals the base's, and
            # comparing them made an overridden occurrence read as dirty
            # forever.
            return (st.get("checklist", []) == note.get("checklist", [])
                    and st.get("attachments", []) == note.get("attachments", [])
                    and st["date"] == note.get("date", "")
                    and st["recurrence"]
                    == normalize_recurrence(note.get("recurrence")))
        shown = note
        if (st["title"].strip() != shown["title"].strip()
                or st["body"] != shown["body"]
                or st.get("formatting", []) != note.get("formatting", [])
                # Paragraphs carry what tags alone hold: list indents, line
                # alignment, and a table's place on the page. Left out of
                # this comparison, a tag-only change read as "nothing new"
                # and the autosave quietly skipped it.
                or st.get("paragraphs", []) != note.get("paragraphs", [])
                or st["comments"] != (shown.get("comments") or "")
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

    def _catch_up_deferred_refresh(self):
        """If a note-list/calendar rebuild was skipped earlier (see
        save_current_note) because a popup was open during autosave, run it
        now. Called at natural transition points — switching notes, changing
        tabs — where an extra rebuild blends into a change that was already
        happening, rather than standing out as an isolated glitch against an
        otherwise static screen."""
        if getattr(self, "_note_list_needs_refresh", False):
            self._note_list_needs_refresh = False
            self._calendar_needs_render = False
            self.refresh_note_list()
            self.render_calendar()
        elif getattr(self, "_calendar_needs_render", False):
            # A theme switch happened while the calendar was off screen, so
            # its rebuild was skipped (see apply_theme). Catch it up now,
            # before it becomes visible.
            self._calendar_needs_render = False
            self.render_calendar()

    def _update_open_highlight(self):
        """Move the 'currently open' ring directly to whichever card needs
        it, without rebuilding the list -- the (at most) two cards that
        actually changed.

        Every place that says which note is open asks _card_ring_color,
        which also knows where the keyboard is: the colour carries the
        meaning (the thickness is on every card), and a card that is both
        open and holding the keyboard shows the keyboard's ring."""
        prev = getattr(self, "_last_highlighted_note_id", None)
        current = self.selected_note_id
        if prev == current:
            return
        self._paint_ring(prev)
        self._paint_ring(current)
        self._last_highlighted_note_id = current

    def open_note_in_tab(self, note, occurrence_date=None, flush=True):
        """Open a saved note in the editor. Only one note is open at a time — any
        unsaved work in the current note is auto-saved first, then this note
        loads in its place.

        ``flush=False`` is for the one case where that is backwards: the
        note has just been rewritten on purpose from outside the editor,
        which is still showing the version from before. Saving that first
        writes the old version straight back over the new one. Callers
        that pass False flush themselves, BEFORE making their change, so
        the user's own unsaved work is kept rather than skipped.
        """
        # Close any open popup (e.g. an emoji picker) FIRST, before flushing
        # autosave below — otherwise the autosave that follows would see a
        # popup still open and skip refreshing the note list, leaving it
        # stale even after switching notes. One holding typed work -- the
        # template editor -- asks first, and choosing to keep editing keeps
        # this note from opening: a card clicked beside a half-written
        # template closed it without the question, the typing gone.
        if not self._dismiss_mini_popup_asking():
            return False
        # Navigating to a different note means we're no longer mid-creation of
        # the calendar-originated one — clear this BEFORE the flush below, so
        # that flush's save can't accidentally trigger an unwanted jump back
        # to the calendar out from under the note the user is trying to open.
        pending_return = getattr(self, "_pending_calendar_return", None)
        self._pending_calendar_return = None
        self._update_calendar_return_button()
        self._catch_up_deferred_refresh()
        # Save whatever is currently in the editor before switching away.
        # Cancel on a repeating day's save question means stay: the edited
        # day remains in the editor, unsaved, and the way back to the
        # calendar is armed again as it was.
        if flush and self._flush_autosave() is False:
            self._pending_calendar_return = pending_return
            self._update_calendar_return_button()
            return False
        self.load_note(note, occurrence_date)
        self._remember_last_open_note(note["id"])
        # Keep a single-entry tab list so the save/flush machinery still works.
        self._tab_counter += 1
        self.open_tabs = [{"key": self._tab_counter, "state": self.capture_editor_state()}]
        self.active_tab_index = 0
        self._sync_editor_snapshot()
        # Moves the highlighted-card border to this note, without rebuilding
        # the whole list — switching notes happens constantly during normal
        # use, and a full refresh_note_list() here just to move a border was
        # a much more noticeable flicker than the same cost is for genuinely
        # rare actions like saving or searching.
        self._update_open_highlight()
        return True

    def open_blank_tab(self):
        """Start a brand-new empty note, replacing whatever was open (after
        auto-saving any unsaved work in it).

        Returns False when the person chose to stay (Cancel on a repeating
        day's question), True otherwise -- as open_note_in_tab does. A
        caller that goes on to fill the editor must stop on False: the
        import did not, and loaded a recipe into the repeating note still
        on screen, whose next save wrote it over the whole series."""
        # A popup holding typed work asks first, as in open_note_in_tab.
        if not self._dismiss_mini_popup_asking():
            return False
        pending_return = getattr(self, "_pending_calendar_return", None)
        self._pending_calendar_return = None
        self._update_calendar_return_button()
        self._catch_up_deferred_refresh()
        if self._flush_autosave() is False:
            # Cancel means stay, exactly as in open_note_in_tab.
            self._pending_calendar_return = pending_return
            self._update_calendar_return_button()
            return False
        self.new_note()
        self._tab_counter += 1
        self.open_tabs = [{"key": self._tab_counter, "state": self.capture_editor_state()}]
        self.active_tab_index = 0
        self._sync_editor_snapshot()
        # Clears any previously-highlighted card's border — a blank new note
        # isn't "the" open note in the list. Same surgical update as
        # open_note_in_tab, not a full rebuild.
        self._update_open_highlight()

    def _flush_autosave(self):
        """Cancel any pending debounced auto-save and, if the current editor has
        real unsaved changes, save them right now. Called before switching notes
        or closing so a late timer can't fire into the wrong note.

        Returns False when the person pressed Cancel on the question a
        repeating note's day asks ("What should Save apply to?"), and True
        otherwise. Every caller about to replace the editor -- another note,
        a new one, closing the window -- stops on False, because Cancel
        means "take me back", in this dialog as in every other. They used
        to carry on regardless, and Cancel quietly threw the day's edit
        away.

        Callers stop on an explicit False only (``is False``), never on
        anything falsy: a return added later without a value, or a test
        standing in for this method, must not turn into a window that
        will not close."""
        self._cancel_pending_autosave()
        if self.selected_note_id is None and not self.open_tabs:
            return True
        # selected_note_id can end up stale — pointing at a note that no
        # longer exists — in the brief window between a delete removing the
        # note from self.notes and the editor being repointed somewhere
        # real (e.g. the flush switch_to_tab performs during the
        # post-delete cleanup, before it restores the next tab's state).
        # If that happens, there's nothing real to flush
        # against; skip silently rather than falling through to a save
        # attempt that fails with a "Note missing" dialog — an automatic,
        # invisible safety net shouldn't ever surface an interruptive error
        # for something the user didn't directly ask to happen.
        if self.selected_note_id is not None and self.find_note(self.selected_note_id) is None:
            return True
        # A checklist item typed but not yet added is typing like any other:
        # it goes into the note it was typed for, before that note is left.
        # It used to stay in the box and be added to whichever note came next.
        self._take_pending_checklist_item()
        try:
            st = self.capture_editor_state()
        except Exception:
            self._log_swallowed("flush: capture_editor_state")
            return True
        # Same shared gate as _autosave_now, same exemption: an emptied
        # SAVED note must flush like any other edit — this was the second
        # of the two gatekeepers that made T0-5's "switch away and come
        # back" route lose the emptying.
        if not self._editor_state_has_content(st) and not self._editing_saved_note():
            return True
        try:
            if not self.editor_state_matches_saved(st):
                if self.save_current_note(auto=True) is self._SAVE_CANCELLED:
                    return False
        except Exception:
            # THE silent spot the audit named: a save failing here, at
            # note-switch or close, is exactly "stopped saving in
            # complete silence" — leave the trace.
            self._log_swallowed("flush: save_current_note")
        # A date or repeat the save could not store exists only on the
        # screen now, and every caller of this is about to replace the
        # screen. Asked, not decided: going back to fix it is the safe
        # answer, so it is what Escape and Enter give.
        try:
            left_out = self._date_and_repeat_to_store()[2]
        except Exception:
            self._log_swallowed("flush: date and repeat check")
            left_out = []
        if left_out:
            if not self._themed_dialog(
                    "Part of this note isn't saved",
                    self._left_out_message(left_out),
                    kind="warning",
                    buttons=[("Go back and fix it", False),
                             ("Continue without it", True)],
                    default="Go back and fix it"):
                return False
            self._put_back_stored_date_and_repeat()
            # Putting the repeat back writes its fields, and their traces
            # schedule an autosave; this method's promise is that no late
            # timer is left to fire into whatever replaces the editor.
            self._cancel_pending_autosave()
        return True

    def switch_to_tab(self, index):
        if index == self.active_tab_index:
            return
        if not (0 <= index < len(self.open_tabs)):
            return
        if self._flush_autosave() is False:
            return
        self._sync_active_tab()
        self.active_tab_index = index
        self.restore_editor_state(self.open_tabs[index]["state"])
        self._sync_editor_snapshot()

    def _sync_editor_snapshot(self):
        """Write the live editor back into the stored state of the note it
        belongs to.

        This was refresh_tab_strip, which drew a row of tabs above the
        editor -- a row that could never appear. Every path that touches
        the list resets it to a single entry and no append exists, so the
        strip's "hidden at 0-1 notes" branch was the only one ever taken
        (recorded as finding C12 in qa/COVERAGE_LEDGER.md, and closed by
        removing it in 0.73.165 rather than by building multi-note tabs).

        What was never dead is the snapshot it refreshed on the way: the
        dirty comparison and the restore after a bulk delete both read it,
        so it is kept under the name of the thing it actually does.
        """
        self._sync_active_tab()

    def _bind_global_shortcuts(self):
        """App-wide keyboard shortcuts, bound with bind_all so they fire
        whichever widget holds focus (same mechanism the app already uses
        for Activate/Deactivate). Neither Ctrl+N nor Ctrl+S carries a
        default Text or Entry binding on this Tk, so nothing is being
        overridden; each handler returns 'break' so the combo is never
        also typed. Both letter cases are bound, to survive Caps Lock --
        the same as the Ctrl+V bindings elsewhere. Ctrl+F opens the
        find-in-the-current-note bar (the editor meaning of Ctrl+F)."""
        for lower, upper, handler in (
                ("<Control-n>", "<Control-N>", self._shortcut_new_note),
                ("<Control-f>", "<Control-F>", self._shortcut_find),
                ("<Control-s>", "<Control-S>", self._shortcut_save_now)):
            self.bind_all(lower, handler, add="+")
            self.bind_all(upper, handler, add="+")

    def _leave_settings_for_the_editor(self):
        """What a shortcut that needs the editor does first: let a popup
        holding typed work have its say, then leave Settings the way the
        Back button does. Returns False when the person has to stay.

        Settings is a page swapped in place of the notebook, not a tab of
        it, so Ctrl+N and Ctrl+F used to select the Notes tab of a notebook
        that was not on screen: nothing visible happened, the hidden editor
        was cleared (or grew an invisible find bar), and the keys typed next
        went nowhere. Worse, with a template half-written in its editor and
        the Calendar tab underneath, that tab change dismissed the editor
        directly -- the template gone without the question a click outside
        it asks. It gets the same three answers everywhere: Cancel (or
        Escape) keeps editing, No discards, Yes saves.
        """
        if not self._dismiss_mini_popup_asking(holding_work_only=True):
            return False
        if getattr(self, "_settings_open", False):
            return self.hide_settings_page() is not False
        return True

    def _shortcut_new_note(self, event=None):
        """Ctrl+N: a fresh note. Switches to the Notes tab first, since the
        editor lives there and the shortcut can fire from the Calendar."""
        if self._a_dialog_is_asking() or not self._leave_settings_for_the_editor():
            return "break"
        self.notebook.select(self.TAB_NOTES)
        # Flush before clearing, like every other route into an empty
        # editor — without it the shortcut silently discarded whatever
        # the debounce hadn't caught yet (and a deferred occurrence
        # session in full). Cancel on the day's question keeps the day.
        if self._flush_autosave() is False:
            return "break"
        self.new_note()
        return "break"

    def _shortcut_save_now(self, event=None):
        """Ctrl+S: save the note being edited. Stays silent when there is
        genuinely nothing to save, rather than popping the "write something"
        warning a global shortcut would otherwise trigger from anywhere
        (same emptiness test the autosave uses)."""
        if self._a_dialog_is_asking():
            return "break"
        # Typing in a popup that saves -- the template editor -- Ctrl+S is
        # that popup's own Save. It used to save the note hidden behind the
        # Settings page instead, or nothing, and say nothing either way.
        # Asked of the key's own widget: that is where the keystroke went.
        pop = getattr(self, "_mini_popup", None)
        save_popup = (getattr(pop, "_save_from_keyboard", None)
                      if pop is not None else None)
        if (save_popup is not None and event is not None
                and self._is_inside_popup(getattr(event, "widget", None), pop)):
            save_popup()
            return "break"
        try:
            st = self.capture_editor_state()
        except Exception:
            return "break"
        # The emptied-saved-note exemption applies to Ctrl+S too: without
        # it the shortcut was a silent no-op on exactly the edit T0-5 is
        # about, while the Save button accepted it.
        #
        # And the date counts here for the same reason it counts in the
        # Save button: both are the user explicitly asking. Left out,
        # Ctrl+S silently refused the bare dated reminder the button
        # accepted, which is the two explicit gestures disagreeing about
        # the same editor.
        deliberate = (self._editor_state_has_content(st)
                      or (st.get("date") or "").strip()
                      or self._editing_saved_note())
        if deliberate:
            self.save_current_note(auto=False)
        return "break"

    # ---------- Find in the current note (Ctrl+F) ----------
    # Read-only: this feature ONLY adds/removes its own two background tags
    # (find_all / find_current) and draws/deletes one throwaway canvas
    # rectangle. It never inserts/deletes body text, never moves the caret,
    # never calls _render_table_grids, and never touches a serialized tag --
    # so it cannot dirty the note, autosave, or fight the grid-render/
    # view-restore machinery. (A pre-existing cell-editor commit-on-focus-
    # loss may still rebuild grids when Ctrl+F steals focus; the canvas
    # flash is always re-resolved live to survive that.)
    FIND_MATCH_CAP = 2000

    def _shortcut_find(self, event=None):
        """Ctrl+F: open the in-note find bar (on the Notes tab)."""
        if self._a_dialog_is_asking() or not self._leave_settings_for_the_editor():
            return "break"
        try:
            self.notebook.select(self.TAB_NOTES)
        except tk.TclError:
            pass
        self._open_find()
        return "break"

    def _build_find_bar(self):
        """The find bar is a Frame place()'d INTO editor_outer (the
        non-scrolling viewport frame), so it lives inside the app window,
        never scrolls away, and -- because place() is outside pack -- never
        reflows the editor or churns the scrollregion."""
        bar = tk.Frame(self.editor_outer, bg=self.colors["card"],
                       highlightthickness=1,
                       highlightbackground=self.colors["accent"])
        # The accent-coloured border must be tracked too, not just the fill:
        # left off the map it stays frozen at the theme the bar was first
        # built under, so changing the accent (mov -> albastru) leaves the
        # old colour framing the bar until it is rebuilt.
        self.track_theme(bar, bg="card", highlightbackground="accent")
        self._find_var = tk.StringVar()
        entry = tk.Entry(bar, textvariable=self._find_var, relief="flat",
                         width=22, font=("Segoe UI", 10),
                         bg=self.colors["sidebar"], fg=self.colors["text"],
                         insertbackground=self.colors["text"])
        self.track_theme(entry, bg="sidebar", fg="text", insertbackground="text")
        entry.pack(side="left", padx=(6, 4), pady=4, ipady=2)
        self._find_entry = entry
        self._add_paste_menu(entry)
        self._guard_entry_astral(entry)
        self._find_var.trace_add("write", lambda *a: self._find_on_query_change())
        entry.bind("<Return>", lambda e: (self._find_nav(1), "break")[1])
        entry.bind("<Shift-Return>", lambda e: (self._find_nav(-1), "break")[1])
        entry.bind("<Escape>", lambda e: (self._close_find(), "break")[1])
        self._find_count_lbl = tk.Label(
            bar, text="", bg=self.colors["card"], fg=self.colors["subtext"],
            font=("Segoe UI", 8), width=8, anchor="w")
        self.track_theme(self._find_count_lbl, bg="card", fg="subtext")
        self._find_count_lbl.pack(side="left", padx=(0, 4))
        for txt, delta in (("▴", -1), ("▾", 1)):
            b = tk.Button(bar, text=txt, command=lambda d=delta: self._find_nav(d),
                          relief="flat", cursor="hand2", bd=0,
                          font=("Segoe UI", 9, "bold"),
                          bg=self.colors["card"], fg=self.colors["text"])
            self.track_theme(b, bg="card", fg="text")
            b.pack(side="left", padx=1)
        self._find_case = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(bar, text="Aa", variable=self._find_case,
                            command=lambda: self._find_rescan(reveal=False),
                            relief="flat", bd=0, font=("Segoe UI", 8, "bold"))
        # Built once with the bar and long-lived, so selectcolor (the box's
        # own fill) and activebackground need LIVE tracking too -- left off
        # the map they stay stuck at whichever theme was active when the bar
        # was first built, leaving a dark box on a light theme where the
        # checkmark can't be read (the group-by checkbox hit the same trap).
        self.track_theme(cb, bg="card", fg="subtext", selectcolor="check_well",
                         activebackground="card")
        self._find_case_cb = cb
        cb.pack(side="left", padx=(2, 2))
        close = tk.Button(bar, text="✕", command=self._close_find,
                          relief="flat", cursor="hand2", bd=0,
                          font=("Segoe UI", 9, "bold"),
                          bg=self.colors["card"], fg=self.colors["subtext"])
        self.track_theme(close, bg="card", fg="subtext")
        close.pack(side="left", padx=(2, 6))
        self._find_bar = bar

    def _open_find(self):
        if not hasattr(self, "body_text"):
            return
        if getattr(self, "_find_bar", None) is None:
            self._build_find_bar()
        # Prefill from the current selection, if any.
        try:
            sel = self.body_text.get("sel.first", "sel.last")
        except tk.TclError:
            sel = ""
        if sel and "\n" not in sel:
            self._find_var.set(sel)
        self._find_bar.place(relx=1.0, x=-8, y=6, anchor="ne")
        self._find_bar.lift()
        self._find_open = True
        self._find_entry.focus_set()
        self._find_entry.select_range(0, "end")
        self._find_rescan(reveal=True)

    def _close_find(self, event=None):
        if getattr(self, "_find_bar", None) is not None:
            self._find_bar.place_forget()
        self._find_open = False
        self._find_clear()
        try:
            self.body_text.focus_set()
        except tk.TclError:
            pass

    def _find_clear(self):
        """Remove ONLY the find tags and the throwaway flash. No existing
        tag is ever in scope."""
        for tag in ("find_all", "find_current"):
            try:
                self.body_text.tag_remove(tag, "1.0", "end")
            except tk.TclError:
                pass
        self._find_delete_flash()
        self._find_matches = []
        self._find_index = -1

    def _find_delete_flash(self):
        """Delete the current cell flash by RE-RESOLVING the live grid --
        never through a cached canvas, which a rebuild may have destroyed."""
        cur = getattr(self, "_find_flash", None)
        if not cur:
            return
        line = cur.get("line")
        info = self._grid_at_line(line) if line is not None else None
        if info is not None:
            try:
                info["canvas"].delete("find_flash")
            except tk.TclError:
                pass
        self._find_flash = None

    def _find_on_query_change(self):
        # Typing in the find box: debounce a rescan that DOES reveal the
        # first hit (this is a search gesture, not a note edit).
        job = getattr(self, "_find_debounce", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._find_debounce = self.after(180, lambda: self._find_rescan(reveal=True))

    def _find_on_body_edit(self):
        # The body changed while the bar is open: the match model is now
        # stale. Gate navigation until a rescan completes, and rescan WITHOUT
        # revealing (revealing here would twitch the view on every keystroke).
        if not getattr(self, "_find_open", False):
            return
        self._find_model_dirty = True
        job = getattr(self, "_find_debounce", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._find_debounce = self.after(180, lambda: self._find_rescan(reveal=False))

    def _find_on_context_switch(self):
        """Note/tab switch or load: the old note's match model is invalid.
        Clear synchronously and cancel any pending debounce so no navigation
        runs against stale indices; rescan the new note if the bar is open."""
        job = getattr(self, "_find_debounce", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
            self._find_debounce = None
        self._find_clear()
        self._find_model_dirty = False
        if getattr(self, "_find_open", False) and getattr(self, "_find_bar", None):
            self._find_rescan(reveal=False)

    def _find_norm_cell(self, value):
        """A cell's searchable text, exactly as the sidebar search sees it
        (core_tables.content_text): the <br> marker becomes a space; merge
        markers and checkboxes are not words."""
        if value in (core_tables.MERGE_LEFT, core_tables.MERGE_UP):
            return None
        if core_tables.checkbox_state(value) is not None:
            return None
        return value.replace(core_tables.LINE_BREAK, " ")

    def _find_scan_model(self, query):
        """Build the ordered match list for `query`. Prose matches are Tk
        ranges (skipping any that cross an elided table); table-cell matches
        are (live_line, data_row, col), located via core/tables and keyed
        the way info['cells'] is (separator excluded)."""
        nocase = not self._find_case.get()
        needle = query.lower() if nocase else query
        matches = []
        b = self.body_text
        # Prose. An astral char in the pattern SEGFAULTS Tcl's -nocase
        # text search outright (Linux Tk 8.6; reproduced in a bare Text,
        # needle "😀ok"), so a query holding one never reaches Tcl at
        # all: scan the same prose in Python and convert offsets with
        # _tk_col — the same units boundary as everywhere else. The
        # hide-tag skip below drops the elided table text Python can see
        # but Tk's own search would have skipped.
        astral_query = any(ord(ch) > 0xFFFF for ch in query)
        if astral_query:
            for li, line in enumerate(
                    b.get("1.0", "end-1c").split("\n"), start=1):
                hay = line.lower() if nocase else line
                at = hay.find(needle)
                while at != -1 and len(matches) < self.FIND_MATCH_CAP:
                    pos = f"{li}.{self._tk_col(line, at)}"
                    end = f"{li}.{self._tk_col(line, at + len(query))}"
                    if not b.tag_nextrange(self.TABLE_HIDE_TAG, pos, end):
                        matches.append({"kind": "prose", "start": pos,
                                        "end": end, "line": li,
                                        "col": int(pos.split(".")[1])})
                    at = hay.find(needle, at + 1)
                if len(matches) >= self.FIND_MATCH_CAP:
                    break
        countv = tk.IntVar()
        start = "1.0"
        while not astral_query and len(matches) < self.FIND_MATCH_CAP:
            pos = b.search(query, start, stopindex="end", nocase=nocase,
                           count=countv)
            if not pos:
                break
            n = countv.get() or self._tk_units(query)
            line = int(pos.split(".")[0])
            col = int(pos.split(".")[1])
            # `n` is UTF-16 units (what search -count returns, and what
            # index COLUMNS count) while "+Nc" arithmetic counts
            # CHARACTERS — so a matched astral emoji widened the range by
            # one character apiece and the highlight swallowed whatever
            # followed the match. Stay in units on both sides.
            end = f"{line}.{col + n}"
            start = f"{pos}+1c"
            # Drop a hit that spans an elided table (search concatenates the
            # prose on either side): it would tag hidden cells and double a
            # cell hit.
            if b.tag_nextrange(self.TABLE_HIDE_TAG, pos, end):
                continue
            matches.append({"kind": "prose", "start": pos, "end": end,
                            "line": line, "col": col})
        # Table cells: read the plain text, walk each block's DATA rows.
        text = b.get("1.0", "end-1c")
        for first0, last0 in core_tables.find_blocks(text):
            info = self._grid_at_line(first0 + 1)
            if info is None:
                continue  # typed pipes not yet a grid -> already prose above
            live_first = self._grid_first_line(info)
            if live_first is None:
                continue
            block = text.split("\n")[first0:last0 + 1]
            sep_at = core_tables.separator_index(block)
            data_r = 0
            for i, line_text in enumerate(block):
                if i == sep_at:
                    continue
                for c, raw in enumerate(core_tables.split_row(line_text)):
                    val = self._find_norm_cell(raw)
                    if val is None:
                        continue
                    hay = val.lower() if nocase else val
                    if needle and needle in hay and (data_r, c) in info["cells"]:
                        matches.append({"kind": "cell", "line": live_first,
                                        "row": data_r, "col": c,
                                        "sortcol": 10000 + c})
                        if len(matches) >= self.FIND_MATCH_CAP:
                            break
                data_r += 1
        # Order top-to-bottom; cell matches sort after prose on the same
        # (table window) line via the large sortcol.
        matches.sort(key=lambda m: (m["line"], m.get("sortcol", m.get("col", 0))))
        return matches

    def _find_rescan(self, reveal=False):
        self._find_debounce = None
        if not getattr(self, "_find_open", False):
            return
        query = self._find_var.get()
        prev = None
        if 0 <= self._find_index < len(getattr(self, "_find_matches", [])):
            prev = self._find_matches[self._find_index]
        # Clear old tags/flash before re-tagging.
        for tag in ("find_all", "find_current"):
            try:
                self.body_text.tag_remove(tag, "1.0", "end")
            except tk.TclError:
                pass
        self._find_delete_flash()
        if not query:
            self._find_matches = []
            self._find_index = -1
            self._find_model_dirty = False
            self._find_count_lbl.config(text="")
            try:
                self._find_entry.configure(bg=self.colors["sidebar"])
            except tk.TclError:
                pass
            return
        self._find_matches = self._find_scan_model(query)
        self._find_model_dirty = False
        # Tag every prose match with the field tag.
        for m in self._find_matches:
            if m["kind"] == "prose":
                try:
                    self.body_text.tag_add("find_all", m["start"], m["end"])
                except tk.TclError:
                    pass
        self._find_raise_tags()
        n = len(self._find_matches)
        if not n:
            self._find_index = -1
            self._find_count_lbl.config(text="0/0")
            try:
                self._find_entry.configure(bg="#5a2b2b")
            except tk.TclError:
                pass
            return
        try:
            self._find_entry.configure(bg=self.colors["sidebar"])
        except tk.TclError:
            pass
        capped = n >= self.FIND_MATCH_CAP
        if reveal:
            self._find_index = 0
            self._find_reveal(self._find_matches[0])
        else:
            # Keep the current position across an edit rescan: clamp to a
            # near match, DO NOT reveal (that would twitch the view).
            self._find_index = min(
                self._find_index if self._find_index >= 0 else 0, n - 1)
            self._find_mark_current(scroll=False)
        self._find_count_lbl.config(
            text=f"{self._find_index + 1}/{n}{'+' if capped else ''}")

    def _find_raise_tags(self):
        # find tags win over highlight_* backgrounds; sel stays on top.
        for tag in ("find_all", "find_current", "sel"):
            try:
                self.body_text.tag_raise(tag)
            except tk.TclError:
                pass

    def _find_nav(self, delta):
        matches = getattr(self, "_find_matches", [])
        if not matches or getattr(self, "_find_model_dirty", False):
            return
        self._find_index = (self._find_index + delta) % len(matches)
        self._find_reveal(matches[self._find_index])
        self._find_count_lbl.config(
            text=f"{self._find_index + 1}/{len(matches)}"
                 f"{'+' if len(matches) >= self.FIND_MATCH_CAP else ''}")

    def _find_mark_current(self, scroll=True):
        matches = getattr(self, "_find_matches", [])
        if not (0 <= self._find_index < len(matches)):
            return
        if scroll:
            self._find_reveal(matches[self._find_index])
        else:
            m = matches[self._find_index]
            try:
                self.body_text.tag_remove("find_current", "1.0", "end")
                if m["kind"] == "prose":
                    self.body_text.tag_add("find_current", m["start"], m["end"])
            except tk.TclError:
                pass
            self._find_raise_tags()

    def _find_reveal(self, m):
        self._grid_view_restore = None
        try:
            self.body_text.tag_remove("find_current", "1.0", "end")
        except tk.TclError:
            pass
        self._find_delete_flash()
        if m["kind"] == "prose":
            try:
                self.body_text.tag_add("find_current", m["start"], m["end"])
                self.body_text.see(m["start"])
            except tk.TclError:
                pass
        else:
            self._find_flash_cell(m)
        self._find_raise_tags()
        self._find_ensure_visible()
        # Win the race against a grid rebuild's own after_idle restore and
        # its 60/160/360ms re-pin timers: re-assert the reveal after them.
        self.after_idle(self._find_reassert_reveal)
        self.after(220, self._find_reassert_reveal)

    def _find_reassert_reveal(self):
        if not getattr(self, "_find_open", False):
            return
        matches = getattr(self, "_find_matches", [])
        if not (0 <= self._find_index < len(matches)):
            return
        self._grid_view_restore = None
        m = matches[self._find_index]
        try:
            if m["kind"] == "prose":
                self.body_text.see(m["start"])
            else:
                info = self._grid_at_line(m["line"])
                if info is not None:
                    self.body_text.see(f"{self._grid_first_line(info)}.0")
        except tk.TclError:
            pass
        self._find_ensure_visible()

    def _find_flash_cell(self, m):
        """Draw a throwaway rectangle on the LIVE grid canvas (re-resolved),
        never a cached one. Bail to a see()-only reveal if the grid is gone."""
        info = self._grid_at_line(m["line"])
        if info is None:
            return
        first = self._grid_first_line(info)
        if first is None:
            return
        try:
            self.body_text.see(f"{first}.0")
        except tk.TclError:
            return
        cell = info["cells"].get((m["row"], m["col"]))
        canvas = info.get("canvas")
        if cell is None or canvas is None:
            self._find_flash = {"line": m["line"]}  # counted, no box (hidden col)
            return
        try:
            x, y = cell["x"], cell["y"]
            w, h = cell["w"], cell.get("h", info.get("row_h", 24))
            canvas.delete("find_flash")
            canvas.create_rectangle(x + 1, y + 1, x + w - 1, y + h - 1,
                                    outline=self.colors["accent"], width=2,
                                    tags="find_flash")
            # Bring a horizontally off-screen cell into view.
            total = canvas.bbox("all")
            if total and total[2] > canvas.winfo_width():
                canvas.xview_moveto(max(0.0, x / total[2]))
        except tk.TclError:
            pass
        self._find_flash = {"line": m["line"]}

    def _retint_find_tags(self, text_widget):
        """(Re)apply the find highlight colours for the current palette.
        Both colours are blended from the theme, so a theme switch must
        refresh them or the next find would paint in the old accent."""
        try:
            text_widget.tag_configure(
                "find_all",
                background=self._blend_hex(self.colors["accent"],
                                           self.colors["card"], 0.35))
            text_widget.tag_configure("find_current",
                                      background=self.colors["accent"])
        except tk.TclError:
            pass

    def _find_reflash(self):
        """Re-draw the current cell flash after a rebuild (e.g. theme
        switch tore the canvas down)."""
        if not getattr(self, "_find_open", False):
            return
        matches = getattr(self, "_find_matches", [])
        if 0 <= self._find_index < len(matches):
            m = matches[self._find_index]
            if m["kind"] == "cell":
                self._find_flash_cell(m)
        self._find_raise_tags()

    def _find_ensure_visible(self):
        """Scroll the editor PAGE (editor_canvas) so the body's own 12-line
        viewport is on screen -- body_text.see() only drives the body's
        inner scroll, not the page it sits inside."""
        try:
            self.editor_canvas.update_idletasks()
            bbox = self.editor_canvas.bbox(self._editor_window)
            if not bbox:
                return
            total = bbox[3] - bbox[1]
            if total <= 0:
                return
            y = self.body_text.winfo_rooty() - self.editor.winfo_rooty()
            h = self.body_text.winfo_height()
            canvas_h = self.editor_canvas.winfo_height()
            cur = self.editor_canvas.yview()[0] * total
            if y < cur:
                self.editor_canvas.yview_moveto(max(0.0, y) / total)
            elif y + h > cur + canvas_h:
                self.editor_canvas.yview_moveto(
                    max(0.0, y + h - canvas_h) / total)
        except (tk.TclError, ZeroDivisionError):
            pass

    def new_note(self):
        self.selected_note_id = None
        self.current_occurrence_date = None
        # Whatever was under review from a share code is no longer here.
        self._arrived_uid = ""
        self.title_entry.delete(0, "end")
        self.title_entry.config(fg=self.colors["text"])
        # Clearing the field does not go through _insert_title, so the
        # counter would otherwise still be showing the last note's length.
        self._refresh_title_count()
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
        # The add box belongs to the note that was open; what was typed in
        # it was saved there on the way out, or dropped with that note.
        if hasattr(self, "checklist_add_var"):
            self.checklist_add_var.set("")
        if hasattr(self, "checklist_items_frame"):
            self._render_checklist_items()
        self._sync_checklist_open_state()
        self._sync_calculator_open_state()
        self.title_entry.focus()
        self.set_status("New note — not yet saved")
        self.update_word_count()
        self._pending_styles = set()
        self._pending_text_color = None
        self._pending_font_size = None
        self._pending_font_family = None
        self._pending_highlight_color = None
        self._refresh_format_buttons()
        self._reset_editor_scroll()
        self._reset_text_undo()
        self._update_restore_button()
        self._find_on_context_switch()
        self._share_code_on_context_switch()
        self._update_occurrence_banner()
        # A fresh editor means any calendar trip is over — a pending
        # return that survived (e.g. across a delete) made a later,
        # unrelated Save yank the user onto a stale calendar day.
        # _add_note_for_date re-arms its own pending right after this.
        self._pending_calendar_return = None
        self._update_calendar_return_button()

    def load_note(self, note, occurrence_date=None):
        """Open a note. If occurrence_date is given, the note is being opened
        from one specific day of a repeating series, and any per-occurrence
        override for that day is shown instead of the base content."""
        self.selected_note_id = note["id"]
        self.current_occurrence_date = occurrence_date if is_recurring(note) else None
        # A saved note has its own identity; one that was under review from
        # a share code is no longer in the editor.
        self._arrived_uid = ""

        shown = effective_note(note, occurrence_date) if occurrence_date else note

        # Clear out any pending style left over from whatever note was open
        # before, BEFORE inserting this note's body — the insert hook that
        # applies pending styles doesn't know or care that this particular
        # insert is "loading a note" rather than "typing", so a stale
        # pending style at this point would silently tag this note's text.
        self._pending_styles = set()
        self._pending_text_color = None
        self._pending_font_size = None
        self._pending_font_family = None
        self._pending_highlight_color = None
        self.title_entry.delete(0, "end")
        self._insert_title(shown["title"])
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
        self._apply_paragraphs(self.body_text, note.get("paragraphs", []))
        self._render_table_grids()
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", shown.get("comments", ""))
        self.category_var.set(shown["category"])

        self._show_date_in_field(note.get("date"))

        self.current_note_color = shown.get("color", "")
        self._update_color_swatch()
        self.current_attachments = list(note.get("attachments", []))
        self.refresh_attachments_list()
        # Checklist: work on a copy so edits aren't committed until save.
        self._working_checklist = [
            {"text": it.get("text", ""), "done": bool(it.get("done"))}
            for it in note.get("checklist", []) if isinstance(it, dict)
        ]
        # An item half-typed for the note that was open does not follow it
        # here (see new_note).
        if hasattr(self, "checklist_add_var"):
            self.checklist_add_var.set("")
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
        self._find_on_context_switch()
        self._share_code_on_context_switch()
        self._update_occurrence_banner()

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
        # The deep copy brought the original's identity with it, and two
        # notes sharing a uid is the exact collision uid exists to
        # prevent — manufactured here, locally, by a feature that has
        # nothing to do with sharing. Dropped so normalize_note below
        # mints a fresh one: a duplicate is a different note that happens
        # to start with the same words.
        clone.pop("uid", None)
        base_title = (note.get("title") or "").strip()
        clone["title"] = f"{base_title} (copy)" if base_title else "(copy)"
        clone["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # A duplicate is its own note; don't carry occurrence-specific edits that
        # only made sense relative to the original's timeline.
        clone = normalize_note(clone)
        # Give the copy its OWN attachment files. The deep-copy above shared
        # the original's stored_as names — i.e. the same files on disk — so
        # permanently deleting either note later removed the file the other
        # still pointed at (silent attachment loss). A failed/absent copy
        # keeps the old reference, no worse than before.
        new_atts = []
        for att in clone.get("attachments", []):
            fresh = copy_attachment_file(att.get("stored_as", "")) if isinstance(att, dict) else None
            new_atts.append(dict(att, stored_as=fresh) if fresh else att)
        clone["attachments"] = new_atts
        self.notes.append(clone)
        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        self.set_status(f"Duplicated as “{clone['title']}”")
        return clone





    # A small curated set for flagging a day — not the full emoji picker,
    # just quick, common markers (star, alert, celebration, etc.).
    DAY_MARKER_EMOJIS = [
        ("⭐", "#FFD166"), ("❤️", "#FF6B6B"), ("❗", "#E63946"), ("🎉", "#FF8FA3"),
        ("✅", "#6BCB77"), ("🔴", "#E63946"), ("🟡", "#FFD166"), ("🟢", "#6BCB77"),
        ("💡", "#FFC145"), ("🎂", "#FF8FA3"), ("✈️", "#A0C4FF"), ("📌", "#FFB4A2"),
        ("🔔", "#FFA630"), ("🎁", "#FF8FA3"), ("💰", "#6BCB77"), ("🩺", "#A0C4FF"),
        ("🍽️", "#FFB4A2"), ("🚗", "#A0C4FF"),
    ]



    def show_note_context_menu(self, event, note, occurrence_date=None,
                               click_opens=False):
        """Native right-click dropdown for a note. Extensible — add items here
        as new actions appear. When opened from the calendar (occurrence_date
        set), it also offers recurrence-specific actions.

        ``click_opens`` says the surface underneath already opens the note on
        an ordinary click — true of the note list, where "Open / Edit" was a
        second way to do what clicking the card just did. It is NOT true of
        the calendar, where a click opens the note inside the day panel, or
        of the History register, where it jumps to a day: there the entry is
        the one step to the editor and stays.
        """
        if note is None:
            return
        menu = tk.Menu(self, tearoff=0)
        menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"], activeforeground="white",
            relief="flat", bd=0, font=("Segoe UI", 9)
        )

        # Two surfaces make this entry redundant, both field-reported. On a
        # calendar day, a recurring note gets the two explicit edit scopes
        # below instead. And in the note list, clicking the card already
        # opens the note for editing — the menu was offering a longer way
        # to do the thing the click had just done.
        redundant = (click_opens
                     or (occurrence_date is not None and is_recurring(note)))
        if not redundant:
            menu.add_command(
                label="✏  Open / Edit",
                command=lambda: self._ctx_open(note, occurrence_date,
                                               return_day=occurrence_date)
            )
        pin_label = "📌  Unpin from top" if note.get("pinned") else "📌  Pin to top"
        menu.add_command(label=pin_label, command=lambda: self.toggle_pin(note))

        # One note out into the world as a file. HTML is the complete
        # export (colours, tables, everything) and doubles as the road
        # to PDF (browser, Ctrl+P) and Word (opens .html natively);
        # plain text is the body as stored.
        #
        # (This said "Markdown is portable but drops what Markdown cannot
        # say", describing a third format the menu below has never built.
        # A sibling of the docstring corrected in 0.76.195, and missed by
        # that sweep because it greps as a comment about Markdown rather
        # than as a claim about the formats on offer.)
        export_menu = tk.Menu(menu, tearoff=0)
        export_menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"], activeforeground="white",
            relief="flat", bd=0, font=("Segoe UI", 9)
        )
        for fmt, fmt_label in (
                ("html", "Web page (.html) — full formatting; opens in a browser or Word"),
                ("txt", "Plain text (.txt)")):
            export_menu.add_command(
                label=fmt_label,
                command=lambda f=fmt: self.export_note_as_file(note, f))
        menu.add_cascade(label="💾  Export as file", menu=export_menu)

        # Recategorising one note had exactly one route that did not mean
        # opening it: the bulk popup, which requires ticking it first. The
        # selection bar can change a category but not duplicate; this menu
        # could duplicate but not change a category. Neither gap was a rule
        # anyone could learn, and this is the cheaper half to close.
        cat_menu = tk.Menu(menu, tearoff=0)
        cat_menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"], activeforeground="white",
            relief="flat", bd=0, font=("Segoe UI", 9)
        )
        current_cat = (note or {}).get("category")
        for cat_name in CATEGORY_COLORS.keys():
            cat_menu.add_command(
                # A tick beside the one it is already in, so the menu answers
                # "which is this?" as well as offering to change it.
                label=("✓  " if cat_name == current_cat else "     ") + cat_name,
                command=lambda c=cat_name: self._ctx_move_to_category(note, c))
        menu.add_cascade(label="🗂  Move to category", menu=cat_menu)

        # Recurrence-specific actions, only meaningful from the calendar.
        if occurrence_date is not None:
            if is_recurring(note):
                menu.add_separator()
                menu.add_command(
                    label="✏  Edit only this occurrence",
                    command=lambda: self._ctx_open(note, occurrence_date,
                                                   return_day=occurrence_date)
                )
                menu.add_command(
                    label="✏  Edit whole series",
                    command=lambda: self._ctx_open(note, None,
                                                   return_day=occurrence_date)
                )
                if occurrence_date in (note.get("overrides") or {}):
                    menu.add_command(
                        label="↺  Reset this day to the series content",
                        command=lambda: self._reset_occurrence_override(
                            note, occurrence_date)
                    )
            else:
                # A plain dated note: offer to turn it into a repeating series.
                menu.add_separator()
                menu.add_command(
                    label="🔁  Make this repeat…",
                    command=lambda: self._ctx_make_recurring(
                        note, return_day=occurrence_date)
                )

        menu.add_separator()
        menu.add_command(
            label="📄  Duplicate",
            command=lambda: (self.duplicate_note(note), self.refresh_day_panel())
        )
        # Say what it aims at, before the click rather than after it. With
        # no occurrence_date the target is the stored note, so on a
        # repeating one that is every day of it -- and the two surfaces
        # that open this menu without a date are the sidebar card and the
        # History register's series row, where the whole series really is
        # what Delete means. The confirmation has always said so; it just
        # said it second.
        #
        # A day row keeps the plain word on purpose: from there the scope
        # is still a question the user answers (Cancel / the entire series
        # / this occurrence only), so naming one scope in the label would
        # pre-empt a choice that has not been made.
        delete_label = ("🗑  Delete the whole series"
                        if occurrence_date is None and is_recurring(note)
                        else "🗑  Delete")
        menu.add_command(
            label=delete_label,
            command=(lambda: self._delete_note_from_calendar(note, occurrence_date))
                    if occurrence_date is not None else
                    (lambda: (self._context_delete_note(note, occurrence_date),
                             self.refresh_day_panel()))
        )

        # A hover preview drew itself ON TOP of this menu: the mouse only
        # has to drift a few pixels onto a neighbouring calendar cell,
        # and tk_popup does not stop the app's own <Enter> bindings from
        # firing -- it runs a nested event loop, which is precisely why
        # the tooltip still appeared. Field-reported with a screenshot.
        #
        # The flag works because tk_popup BLOCKS until the menu is
        # dismissed, measured rather than assumed: posted for real with
        # nothing to dismiss it, the call never came back. So it is set
        # for exactly as long as the menu is on screen.
        self.hide_day_tooltip()
        self._context_menu_open = True
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            self._context_menu_open = False

    def toggle_pin(self, note):
        """Flip a note's pinned state and re-sort the list."""
        real = self.find_note(note["id"])
        if real is None:
            return
        real["pinned"] = not real.get("pinned", False)
        self.save_notes()
        self.refresh_note_list()
        self.set_status("Pinned to top" if real["pinned"] else "Unpinned")

    def _ctx_move_to_category(self, note, category):
        """Change one note's category from its own menu.

        No question and no undo toast, unlike the bulk route beside it, and
        that is the app's rule rather than an oversight: a confirmation is
        asked in proportion to how recoverable the action is. This replaces
        one field on one note, the menu says which category it is in now,
        and picking another is how you put it back -- which is exactly what
        the editor's own category dropdown has always done with no ceremony
        at all. The bulk version asks because it overwrites a mixed set of
        categories on notes you cannot all see at once.

        The flush and the reconciliation are NOT optional. The editor may be
        holding this very note with its dropdown still showing the old
        value, and the editor's next save would write that back -- undoing
        this with nothing on screen to say so. Same shape as the bulk route,
        which learned it the hard way.
        """
        real = self.find_note((note or {}).get("id"))
        if real is None:
            self.show_info("Not here any more", "That note is no longer in the list.")
            return
        if real.get("category") == category:
            return
        if self._flush_autosave() is False:
            return  # Cancel on a day's save question: nothing moves
        # Re-read after the flush: the note object above was fetched before
        # anything the editor was holding reached the store.
        real = self.find_note(note["id"])
        if real is None:
            return
        real["category"] = category
        self.save_notes()
        self._editor_follows_external_change({real["id"]})
        self.refresh_note_list()
        # A note with no colour of its own is drawn in its category's, as
        # a dot on its days and a stripe in an open day's list.
        self.render_calendar()
        title = (real.get("title") or "").strip() or "Untitled note"
        self.set_status("Moved “%s” to “%s”"
                        % (_truncate(title, 30), category))

    def _bulk_toggle_pin(self):
        """Pin every ticked note, or unpin them if they are all pinned.

        The label flips the same way "Select all" does, and for the same
        reason: one button whose word is always the thing it will do, rather
        than two buttons of which one is usually the wrong one. A mixed
        selection pins -- that is the reading of "Pin" that does something
        for every note in it, and it leaves an unambiguous state behind.
        """
        chosen = [n for n in self.notes if n["id"] in self.selected_note_ids]
        if not chosen:
            self.show_info("Nothing selected", "Tick one or more notes first.")
            return
        # No confirmation and no undo, deliberately: pinning takes nothing out
        # of the list and is undone by pressing the same button again, so the
        # rule this app follows -- confirm in proportion to how recoverable it
        # is -- asks for neither.
        pinning = not all(n.get("pinned", False) for n in chosen)
        for note in chosen:
            note["pinned"] = pinning
        self.save_notes()
        self.refresh_note_list()
        self._refresh_bulk_pin_label()
        word = "Pinned" if pinning else "Unpinned"
        self.set_status("%s %d note%s"
                        % (word, len(chosen), "" if len(chosen) == 1 else "s"))

    def _refresh_bulk_pin_label(self):
        """Say what pressing it will do, given what is ticked right now."""
        btn = getattr(self, "_bulk_pin_btn", None)
        if btn is None:
            return
        chosen = [n for n in self.notes if n["id"] in self.selected_note_ids]
        all_pinned = bool(chosen) and all(n.get("pinned", False)
                                          for n in chosen)
        btn.configure(text="📌 Unpin" if all_pinned else "📌 Pin")

    def _ctx_open(self, note, occurrence_date, return_day=None):
        """Open a note in the editor tab from the context menu.

        `return_day` is set when the menu was raised on a calendar day:
        the editor then remembers the way back, exactly like the day
        panel's own Edit button — the right-click routes silently losing
        the "Back to Calendar" button was a field report. Origin 'edit'
        keeps an explicit Save from yanking the user out of the editor.
        """
        self.notebook.select(self.TAB_NOTES)
        # Not opened -- Cancel on the day still in the editor -- means no
        # way back to arm either: it would point at a note never opened.
        if not self.open_note_in_tab(note, occurrence_date=occurrence_date):
            return
        if return_day is not None:
            self._pending_calendar_return = {
                "year": self.cal_year, "month": self.cal_month,
                "date_str": return_day, "origin": "edit",
            }
            self._update_calendar_return_button()

    def _ctx_make_recurring(self, note, return_day=None):
        """Open a plain dated note in the editor and focus the Repeat control so
        the user can turn it into a recurring series."""
        self.notebook.select(self.TAB_NOTES)
        if not self.open_note_in_tab(note):
            return  # Cancel on the day still in the editor: see _ctx_open
        if return_day is not None:
            # Raised on a calendar day — same way-back memory as _ctx_open.
            self._pending_calendar_return = {
                "year": self.cal_year, "month": self.cal_month,
                "date_str": return_day, "origin": "edit",
            }
            self._update_calendar_return_button()

    def _reset_occurrence_override(self, note, occurrence_date):
        """Drop one day's separate edits so it follows the series again.

        An override is the only way a day stops tracking series edits —
        and until this entry existed there was no way back: the day kept
        its own content forever, invisibly (a field report: a series edit
        that seemed to skip one day out of three)."""
        note = self.find_note(note["id"])
        if note is None or occurrence_date not in (note.get("overrides") or {}):
            return
        if not self.ask_yes_no(
                "Reset this day",
                f"Return {occurrence_date} to the series content?\n\n"
                "The separate edits made for this day will be discarded.",
                icon="warning", default="no"):
            return
        note["overrides"].pop(occurrence_date, None)
        note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_notes()
        # If the editor is showing exactly this day, reload it so the
        # series content replaces the dropped override on screen too.
        if (self.selected_note_id == note["id"]
                and self.current_occurrence_date == occurrence_date):
            self.load_note(note, occurrence_date)
        self.refresh_note_list()
        self.render_calendar()
        self.refresh_day_panel()
        self.set_status("This day follows the series again")
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
        # selected_note_id, so the list re-render after the delete shows the
        # editor's latest content rather than a stale preview. Cancel on a
        # day's save question stops the delete before it asks anything.
        if self._flush_autosave() is False:
            return
        # The target travels as a parameter — never by repointing the
        # editor's selection at it. An earlier version did exactly that,
        # and when the user cancelled the confirm dialog the selection
        # stayed on the wrong note, so the next autosave overwrote it
        # with the open note's content (see ISSUES_LOG).
        self._delete_note(note, occurrence_date)

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
            # The shared test, so a checklist, attachments or a repeat rule
            # also earn the "replace?" question — the old three-field list
            # let a template wipe an attachments-only note without asking.
            has_content = self._editor_state_has_content(st)
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
            self._insert_title(tpl["title"])
            self.title_entry.config(fg=self.colors["text"])
        if tpl.get("body"):
            self.body_text.delete("1.0", "end")
            self.body_text.insert("1.0", tpl["body"])
            self._apply_formatting(self.body_text, tpl.get("formatting", []))
            self._apply_paragraphs(self.body_text, tpl.get("paragraphs", []))
            # A template can hold a table; without the render it applied
            # as raw pipe rows. The import path does this already -- the
            # qa check that carries a table through a template found the
            # one path that did not.
            self._render_table_grids()
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

    def _paste_table_aware(self, text_widget):
        """Paste for a plain text box that should still understand tables.

        The template editor's body is a bare tk.Text: pasting a table
        from Excel, Word or a web page dropped the structure and left
        the words. When the clipboard's HTML holds a table, the same
        converter the main editor trusts turns it into the note's own
        pipe-text form; anything else falls through to the normal paste.
        """
        try:
            html = clipboard.read_html()
        except Exception:
            html = None
        if html and "<table" in html.lower():
            try:
                text, _spans, _paras = html_to_note(html)
            except Exception:
                return None
            if core_tables.find_blocks(text):
                try:
                    text_widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                text_widget.insert("insert", text)
                return "break"
        return None

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
        # Deliberately NARROWER than _editor_state_has_content: a template
        # carries title, body, comments and checklist, and nothing else —
        # so an attachment or a repeat rule alone really would make an
        # empty template. The checklist, though, belongs here: do_save
        # below stores it, so refusing a checklist-only note told the user
        # "this note is empty" about a note the app had just saved for
        # them, and threw away the one thing the template could have kept.
        if not (title or body or comments or st.get("checklist")):
            self.show_info(
                "Nothing to save",
                "A template keeps a note's title, text, comments and "
                "checklist — this note has none of those yet.")
            return

        default_name = title[:30] if title else "My template"

        def do_save(name):
            name = name.strip()
            if not name:
                return False  # keep the box open
            if any(t.get("name") == name for t in self.templates):
                # Never overwrite silently: the same name may hold
                # entirely different content someone still needs.
                if not self.ask_yes_no(
                        "Template name taken",
                        f"You already have a template named “{name}”.\n\n"
                        "Replace the old template with this one?\n"
                        "Choose No to give this one another name.",
                        icon="warning", default="no"):
                    return False  # keep the box open for a new name
            tpl = normalize_template({
                "name": name,
                "title": st.get("title", ""),
                "body": st.get("body", ""),
                "formatting": st.get("formatting", []),
                "paragraphs": st.get("paragraphs", []),
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
                # Cancel on a repeating day's save question means stay:
                # nothing saved, so nothing duplicated either.
                if self.save_current_note() is self._SAVE_CANCELLED:
                    return
                note = self.find_note(self.selected_note_id)

        clone = self.duplicate_note(note)
        # Open the fresh copy so the user can edit it right away.
        if clone is not None:
            self.open_note_in_tab(clone)

    def find_note(self, note_id):
        """The note with this id, or None."""
        return core_find_note(self.notes, note_id)

    # ---------- Category management ----------
    def count_notes_in_category(self, name):
        """How many notes use this category, per-occurrence overrides included."""
        return core_count_in_category(self.notes, name)

    def rename_category_everywhere(self, old_name, new_name):
        """Rewrite every reference to a category when it is renamed."""
        self._refile_category_everywhere(old_name, new_name, renamed=True)

    def reassign_category_everywhere(self, old_name, new_name):
        """Move every note from one category to another.

        Kept distinct from rename_category_everywhere despite doing the same
        thing: the call sites read very differently -- one is the user
        renaming a category, the other is a category being deleted and its
        notes being kept.
        """
        self._refile_category_everywhere(old_name, new_name, renamed=False)

    def _refile_category_everywhere(self, old_name, new_name, renamed):
        """Every holder of a category's name, moved to another name.

        The notes used to be the only holder rewritten, and every other one
        went on using the old name. The editor's own category box fell back
        to General, so the next save filed the open note there. Templates
        and the Trash kept a category that no longer existed, and a note
        restored from the Trash brought it back. A folded group unfolded,
        and its old name stayed folded in the settings for good. Every
        holder is here, so the next one is added here or visibly not at all.

        A rename carries the list's state with it -- the fold, the filter,
        the open note's box. A deletion (``renamed=False``) only lets go of
        the old name: General does not become folded, or the list filtered,
        because a deleted category was.
        """
        core_rename_category(self.notes, old_name, new_name)
        trashed = [e for e in self.trash if isinstance(e, dict)]
        if core_count_in_category(trashed, old_name):
            core_rename_category(trashed, old_name, new_name)
            save_trash(self.trash)
        moved_templates = False
        for tpl in self.templates:
            if isinstance(tpl, dict) and tpl.get("category") == old_name:
                tpl["category"] = new_name
                moved_templates = True
        if moved_templates:
            save_templates(self.templates)
        if old_name in self.collapsed_groups:
            self.collapsed_groups.discard(old_name)
            if renamed:
                self.collapsed_groups.add(new_name)
            save_setting("collapsed_groups", sorted(self.collapsed_groups))
        if renamed:
            if self.category_var.get() == old_name:
                self.category_var.set(new_name)
            var = getattr(self, "filter_var", None)
            if var is not None and var.get() == old_name:
                var.set(new_name)

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
            self._keep_filter_valid()




    def _update_restore_button(self):
        """Show the Restore-previous button only when the open note has a
        recoverable previous version. Uses grid (row 2) to match the action row."""
        if not hasattr(self, "restore_prev_btn"):
            return
        note = self.find_note(self.selected_note_id) if self.selected_note_id else None
        has_prev = bool(note and note.get("_prev"))
        if has_prev and not self._is_placed(self.restore_prev_btn):
            self.restore_prev_btn.grid(row=2, column=0, columnspan=3, sticky="w",
                                       padx=(0, 8), pady=(0, 6), ipadx=10, ipady=5)
        elif not has_prev and self._is_placed(self.restore_prev_btn):
            self.restore_prev_btn.grid_forget()

    # What "↩ Restore previous" can bring back beyond the text, in the
    # words its question uses. The keys are exactly the fields an update
    # replaces beyond PREV_TEXT_FIELDS (core.model); test_data_safety
    # holds the two lists together, so a field the update learns to
    # replace cannot be left out of the restore without a red.
    _PREV_EXTRA_LABELS = (
        ("checklist", "checklist"), ("date", "date"),
        ("recurrence", "repeat rule"), ("color", "colour"),
        ("category", "category"), ("overrides", "per-day edits"),
        ("exceptions", "skipped days"), ("pinned", "pin"),
    )

    def restore_previous_version(self):
        """Bring back the rescue copy: the text a drastic shortening
        replaced, or everything an update from a share code or backup
        replaced."""
        note = self.find_note(self.selected_note_id) if self.selected_note_id else None
        if not (note and note.get("_prev")):
            return
        prev = note["_prev"]
        # Looking at ONE DAY of a series, say so: the rescue copy is of
        # the note itself, so restoring it changes the whole series, and
        # a per-day edit on the day being viewed keeps showing instead.
        viewing_occurrence = bool(self.current_occurrence_date
                                  and is_recurring(note))
        extra = ("\n\nThis note repeats, and the earlier version is of the "
                 "whole note — not just the day you are looking at."
                 if viewing_occurrence else "")
        # A drastic shrink's rescue copy is the text alone; an update's
        # holds everything the update replaced (apply_shared_update), and
        # the question has to name all of it -- "this note's text" was
        # true of the one and a promise the other could not keep.
        also = [label for key, label in self._PREV_EXTRA_LABELS
                if key in prev]
        if also:
            question = (
                "Bring back this note as it was before it was updated? "
                "Its text comes back, and so do its "
                + ", ".join(also[:-1])
                + (" and " if len(also) > 1 else "") + also[-1]
                + ". What the note holds now will be replaced.")
        else:
            question = ("Bring back the earlier version of this note's text? "
                        "The current text will be replaced.")
        if not self.ask_yes_no(
            "Restore previous version", question + extra,
            icon="warning", default="no"
        ):
            return
        # Put the previous content back into the editor and save it. Clear
        # any pending style first — the insert hook that applies pending
        # styles doesn't know this insert is a restore rather than typing,
        # so a stale pending style at this point would silently tag it.
        self._pending_styles = set()
        self._pending_text_color = None
        self._pending_font_size = None
        self._pending_font_family = None
        self._pending_highlight_color = None
        self.title_entry.delete(0, "end")
        self._insert_title(prev.get("title", ""))
        self.title_entry.config(fg=self.colors["text"])
        self.body_text.delete("1.0", "end")
        self.body_text.insert("1.0", prev.get("body", ""))
        self._apply_formatting(self.body_text, prev.get("formatting", []))
        self._apply_paragraphs(self.body_text, prev.get("paragraphs", []))
        # Mirror restore_editor_state's tail: this was the one body-loader
        # that skipped the redraw, so a restored table came back as raw
        # pipe rows and the word count kept describing the replaced text.
        self._render_table_grids()
        self._refresh_format_buttons()
        self.comments_text.delete("1.0", "end")
        self.comments_text.insert("1.0", prev.get("comments", ""))
        # Written straight onto the NOTE, not routed through the editor's
        # save. The rescue copy belongs to the note, and the save path
        # asks a scope question on a repeating note: answering "this
        # occurrence" put the recovered text into a per-day override,
        # which carries only plain text — so the formatting came back
        # stripped, the SERIES stayed shortened, and the rescue copy was
        # spent anyway under a success message. The other answer had its
        # own failure: with an override present the editor still showed
        # the override afterwards, so the landing probe read "not saved"
        # and left _prev armed, and the stale button later overwrote new
        # text with the old version.
        #
        # A direct write has neither problem: there is no scope to get
        # wrong, and no probe to misread — the note holds the restored
        # text the moment this returns.
        note["title"] = prev.get("title", "")
        note["body"] = with_caret_line(prev.get("body", ""))
        note["comments"] = prev.get("comments", "")
        note["formatting"] = normalize_formatting(prev.get("formatting", []))
        note["paragraphs"] = normalize_paragraphs(
            prev.get("paragraphs", []), len(note["body"].split("\n")))
        # ...and whatever else the update replaced. Already shaped when it
        # was loaded or snapshotted; the one thing that can have changed
        # since is the category map, so a category deleted in between
        # comes back as General, the way normalize_note would file it.
        for key, _label in self._PREV_EXTRA_LABELS:
            if key in prev:
                note[key] = copy.deepcopy(prev[key])
        if note.get("category") not in CATEGORY_COLORS:
            note["category"] = "General"
        note.pop("_prev", None)
        # Seconds included, matching what save_current_note stamps: the
        # minute-resolution version sorted a just-restored note BELOW
        # notes touched earlier in the same minute under "Recently
        # updated" (the precision-is-part-of-the-contract lesson, in
        # ISSUES_LOG).
        note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_notes()
        # Reload from the note so the editor and the dirty machinery agree
        # with what is now on disk (the widgets above were filled for the
        # user to see; this makes them the note's official state).
        self.load_note(note, occurrence_date=self.current_occurrence_date)
        self.refresh_note_list()
        # The rescue copy can bring back a date, a repeat, a colour, a
        # category and a series' days -- all of them drawn on the calendar,
        # which this was the one note-writing route never to redraw.
        self.render_calendar()
        self.set_status(
            "Restored the previous version of the whole note"
            if viewing_occurrence else "Restored the previous version")
        self.update_word_count()
        self._update_restore_button()

    def _date_and_repeat_to_store(self):
        """What a save can store from the date and repeat fields, and what
        it has to leave out: ``(date, rule, left_out)``.

        One field the app cannot read used to veto the WHOLE save, and the
        automatic routes -- a pause in typing, another note, Ctrl+N,
        closing the window -- took that refusal for success and replaced
        the editor. A date typed as 30/09/2026, the way many people write
        it, quietly cost every word typed after it. Now a field that cannot
        be stored keeps the value the note already had, everything else is
        saved, and ``left_out`` says what was not, in words for the person.

        Three things can be left out: a date that is not a date (the field
        reads YYYY-MM-DD), a repeat's end date that is not one, and a repeat
        with no start date to hang on. The save and the question asked on
        the way out of the note both ask here, so they cannot disagree about
        what stayed behind.
        """
        note = (self.find_note(self.selected_note_id)
                if self.selected_note_id is not None else None)
        kept_date = (note or {}).get("date") or ""
        kept_rule = normalize_recurrence((note or {}).get("recurrence"))
        left_out = []

        typed = self.date_entry.get().strip()
        if typed == "YYYY-MM-DD":
            typed = ""
        date_value = typed
        if typed and not parse_date(typed):
            left_out.append(f"the date “{typed}” "
                            "(dates are written like 2026-09-30)")
            date_value = kept_date

        rule = self.read_recurrence_from_ui()
        end_typed = (self.rec_end_date_var.get().strip()
                     if self.rec_end_mode_var.get() == "on" else "")
        if rule["freq"] and end_typed and not parse_date(end_typed):
            left_out.append(f"the repeat's end date “{end_typed}” "
                            "(dates are written like 2026-12-31)")
            rule = normalize_recurrence(dict(
                rule, end=kept_rule["end"], count=kept_rule["count"]))

        if rule["freq"] and not parse_date(date_value):
            if parse_date(kept_date):
                # Most often the date was cleared on the way to typing a
                # new one: the series keeps the day it already starts on.
                left_out.append("the cleared date (a repeating note needs "
                                f"a start date, so it still starts {kept_date})")
                date_value = kept_date
            else:
                left_out.append("the repeat (a repeating note needs a "
                                "start date)")
                rule = normalize_recurrence({})
        return date_value, rule, left_out

    def _left_out_message(self, left_out,
                          lead="Everything else in this note is saved, but not:"):
        """The words for what a save could not store (see
        _date_and_repeat_to_store) -- one list, whoever is asking."""
        return lead + "\n\n" + "\n".join(f"• {item}" for item in left_out)

    def _put_back_stored_date_and_repeat(self):
        """Show the date and repeat the note has on disk, over whatever the
        save had to leave out -- what "Continue without it" means, so the
        editor agrees with the note again and nothing reads as unsaved."""
        note = (self.find_note(self.selected_note_id)
                if self.selected_note_id is not None else None)
        self._show_date_in_field((note or {}).get("date"))
        self.write_recurrence_to_ui((note or {}).get("recurrence"))

    # What save_current_note returns when the person pressed Cancel on the
    # occurrence-scope question -- the one outcome a caller that is about
    # to replace the editor must not carry on past.
    _SAVE_CANCELLED = object()

    def save_current_note(self, auto=False):
        title = self.title_entry.get().strip()
        if title == "Note title...":
            title = ""
        # "end" always includes the newline Tk keeps at the end of a Text,
        # so exactly that one character comes off — and nothing else. The
        # old .strip() also ate the user's own leading indentation on the
        # first line and every trailing blank line, silently, on every
        # single save: a pasted code block or quoted email lost its shape
        # the next time the note loaded.
        # with_caret_line: the editor draws a line under a trailing table
        # (the caret must have somewhere to live), so a body read BEFORE
        # that draw is one newline short of the same body read after.
        # Storing the short form made every table-ending note look
        # permanently unsaved — canonical on both sides, always.
        body = with_caret_line(self.body_text.get("1.0", "end-1c"))
        # No remapping any more: `body` IS the widget's content, so span
        # offsets and paragraph line numbers already line up. The two
        # _for_stripped_body adapters existed only to undo the .strip()
        # above, and went with it.
        formatting = self._extract_formatting(self.body_text)
        paragraphs = self._extract_paragraphs(self.body_text)
        # As typed, less the one newline Tk keeps at the end -- the body's
        # rule (see above). A .strip() here ate a pasted code block's first
        # indent and every trailing blank line on each save, long after the
        # body had stopped doing it.
        comments = self.comments_text.get("1.0", "end-1c")
        category = self.category_var.get()

        # A date or repeat the app cannot read is left out and keeps what
        # the note already had; it no longer stops the rest from saving.
        # Autosave fires while someone may still be mid-keystroke on a
        # date ("2026-1"), so the automatic routes stay quiet about it --
        # the status line says it, the explicit Save says it out loud, and
        # leaving the note asks (_flush_autosave).
        date_value, recurrence, left_out = self._date_and_repeat_to_store()

        has_attachments = bool(self.current_attachments)
        has_checklist_items = bool(self._get_checklist())
        # The date and the repeat rule count as content ONLY on an
        # explicit Save. That is what "a bare dated reminder is
        # deliberate" actually means, and the first version of this
        # guard said it in a comment while the code counted them on
        # every route -- including the window-close sweep, which saves
        # with auto=True. The calendar's "+ note for this day" prefills
        # the date, so a day clicked and then abandoned was persisted as
        # a blank dated note the moment the app closed: a regression
        # against main, introduced by widening this very guard.
        # The automatic routes ask _editor_state_has_content, which
        # excludes the date for the same reason; this keeps the two in
        # step while leaving the deliberate gesture its meaning.
        deliberate_only = (date_value or recurrence["freq"]) and not auto
        if (not title and not body.strip() and not comments.strip()
                and not has_attachments and not has_checklist_items
                and not deliberate_only):
            # The guard exists to stop a stray "+ New Note" click becoming
            # a junk note — so it applies to a note that was never saved.
            # Applied to one that EXISTS, it refused to record a deliberate
            # emptying: clear an untitled note, switch away, come back, and
            # the old text was still on disk and reappeared, while Ctrl+S
            # answered "Write something before saving!". Deleting your own
            # text is a legitimate edit; it saves like any other. The field
            # list here mirrors _editor_state_has_content PLUS the date:
            # on an explicit Save a bare dated reminder is deliberate,
            # while comments-only used to be refused with the same false
            # "Write something" — comments are content everywhere now.
            already_saved = (self.selected_note_id is not None
                             and self.find_note(self.selected_note_id) is not None)
            if not already_saved:
                # A background autosave must never interrupt with a
                # dialog — skip quietly and leave the warning to the Save
                # button. There, a date or repeat that could not be read
                # is the real reason nothing was saved, not an empty note.
                if not auto:
                    if left_out:
                        self.show_warning(
                            "Nothing saved yet",
                            self._left_out_message(
                                left_out, lead="This note can't be saved with:"))
                    else:
                        self.show_warning("Empty note", "Write something before saving!")
                return

        if recurrence["freq"] == "weekly" and not recurrence["weekdays"]:
            # Empty selection is legal — it means "the same weekday as the
            # start date" — and the summary label already says so.
            pass

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.selected_note_id is None:
            new_id = max([n["id"] for n in self.notes], default=0) + 1
            # A note under review from a share code keeps the identity it
            # arrived with (see _open_imported_note_in_editor) -- checked
            # again here, since another import may have brought that very
            # note in meanwhile, and two notes never wear one identity.
            arrived_uid = getattr(self, "_arrived_uid", "") or ""
            if arrived_uid and find_by_uid(self.notes, arrived_uid) is not None:
                arrived_uid = ""
            self._arrived_uid = ""
            self.notes.append(normalize_note({
                "id": new_id,
                "uid": arrived_uid,
                "title": title,
                "body": body,
                "formatting": formatting,
                "paragraphs": paragraphs,
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
                self._show_toast("Note created", yield_to_action=True)
        else:
            note = self.find_note(self.selected_note_id)
            if note is None:
                self.show_error("Note missing", "That note no longer exists.")
                return

            scope = "series"
            # Read once, before any question is asked. The question runs a
            # nested event loop, and whatever else happens while it waits
            # must not decide which day this save writes to: a Ctrl+N
            # pressed under the question used to clear the day, and the
            # answer then wrote the edit under a key of None.
            occurrence_date = self.current_occurrence_date
            # Whether "The entire series" was the person's answer or the
            # save's own conclusion: they mean different writes below.
            asked = False
            if is_recurring(note) and occurrence_date:
                # Only ask when the answer could actually change anything.
                # An override carries OVERRIDABLE_FIELDS and nothing else,
                # so when the edit is in a SERIES-owned field — a ticked
                # checklist item above all — "this day" has nowhere to put
                # it: the old code wrote an override duplicating the
                # series' own text, threw the tick away, and left the
                # editor still dirty, so the question came back on every
                # switch. If nothing overridable differs from what this
                # day shows, the edit belongs to the series by
                # construction; save it there without asking.
                shown_now = effective_note(note, occurrence_date)
                overridable_changed = (
                    title.strip() != (shown_now.get("title") or "").strip()
                    or body != (shown_now.get("body") or "")
                    or comments != (shown_now.get("comments") or "")
                    or category != shown_now.get("category")
                    or self.current_note_color != (shown_now.get("color") or ""))
                if overridable_changed:
                    scope = self.ask_occurrence_scope("Save", occurrence_date)
                    if scope is None:
                        # Said out loud, because Cancel means "take me
                        # back": a caller about to leave this note (another
                        # note, Ctrl+N, closing the window) has to know the
                        # edit was NOT saved, or it replaces the editor and
                        # the edit is gone without a word.
                        return self._SAVE_CANCELLED
                    asked = True
            # The day on screen has text of its own: the editor's words are
            # that day's, not the series'.
            own_day = (occurrence_date is not None and is_recurring(note)
                       and occurrence_date in (note.get("overrides") or {}))

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
                note.setdefault("overrides", {})[occurrence_date] = {
                    "title": title,
                    "body": body,
                    "comments": comments,
                    "category": category,
                    "color": self.current_note_color,
                }
                note["updated"] = now
                self.set_status(("Auto-saved " if auto else "Saved ") + f"{occurrence_date} only")
                if auto:
                    self._show_toast("Note updated", yield_to_action=True)
            elif own_day and not asked:
                # Only a series-owned field changed -- a ticked checklist
                # item, an attachment, the repeat rule -- while looking at a
                # day with text of its own, so nobody was asked. The whole
                # editor used to be written to the series here: one day's
                # words replaced every day's, and the series' formatting was
                # wiped, since a day's own text carries none. Only what
                # belongs to the series is written; its text, and this
                # day's, stay as they were.
                note["date"] = date_value
                note["attachments"] = self.current_attachments
                note["recurrence"] = recurrence
                note["checklist"] = [dict(it) for it in self._get_checklist()]
                note["updated"] = now
                if not recurrence["freq"]:
                    note["exceptions"] = []
                    note["overrides"] = {}
                self.set_status(("Auto-saved " if auto else "Saved at ") + now)
                if auto:
                    self._show_toast("Note updated", yield_to_action=True)
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
                # Emptied completely counts however short it was. The
                # thresholds above were written when an empty save could
                # not happen at all -- the guard refused it -- so they
                # only ever had to catch a drastic SHRINK. Now that
                # clearing a saved note is a legitimate edit on every
                # route, a short one (a 17-character shopping list, say)
                # slipped under all three and was written to disk with no
                # rescue copy, nothing in the Trash, and the undo history
                # reset by the note switch that persisted it. The case
                # that most needs the safety net had none.
                emptied = old_len > 0 and new_len == 0
                # A day with text of its own, saved to "The entire series"
                # by the person's own answer: that day's words become every
                # day's words. The series' own text is replaced wholesale by
                # something typed on one day, so it keeps a rescue copy
                # whatever the lengths say.
                series_text_replaced = own_day and (
                    title.strip() != (note.get("title") or "").strip()
                    or body != (note.get("body") or ""))
                if (emptied or series_text_replaced
                        or (removed > 40 and (big_fraction or big_absolute))):
                    note["_prev"] = {
                        "title": note.get("title", ""),
                        "body": note.get("body", ""),
                        "formatting": note.get("formatting", []),
                        "paragraphs": note.get("paragraphs", []),
                        "comments": note.get("comments", ""),
                    }
                if own_day:
                    # ...and the day's own copy goes: it now says what the
                    # series says. Kept, it made the day read as unsaved
                    # forever -- the editor showed the series' new text,
                    # the day still held its old one -- so every way out
                    # of the note asked the same question again.
                    note["overrides"].pop(occurrence_date, None)
                note["title"] = title
                note["body"] = body
                note["formatting"] = formatting
                note["paragraphs"] = paragraphs
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
                    self._show_toast("Note updated", yield_to_action=True)
            # A series save can have just removed the recurrence — an
            # occurrence view of a note that no longer repeats is a lie
            # the day banner must not keep telling.
            if self.current_occurrence_date and not is_recurring(note):
                self.current_occurrence_date = None
        # Recurrence or override counts may have just changed either way.
        self._update_occurrence_banner()

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
            # One note changed, so one card is redrawn; the whole list is
            # rebuilt only when that cannot be known to be enough.
            if not self._redraw_saved_card(self.selected_note_id):
                self.refresh_note_list()
            self.render_calendar()
            self._note_list_needs_refresh = False
        # The saved note now matches disk; update this tab's snapshot so its
        # dirty dot clears, and refresh the strip labels/markers.
        self._sync_active_tab()
        self._sync_editor_snapshot()
        self._update_restore_button()
        # If the calendar day panel is showing, reflect the edit there too.
        if getattr(self, "_day_panel_mode", "empty") != "empty":
            self.refresh_day_panel()
        # What the save had to leave out is still on screen, waiting to be
        # fixed. The status line says so on every route and the explicit
        # Save says it out loud -- which is also why that Save does not
        # send anyone back to the calendar with a date still to fix.
        if left_out:
            self.set_status(("Auto-saved " if auto else "Saved at ") + now
                            + " — except " + "; ".join(left_out))
            if not auto:
                self.show_warning("Part of this note isn't saved",
                                  self._left_out_message(left_out))
                return
        # Only an explicit Save click sends you back, and only on the
        # quick add-a-note-for-a-day flow — when the user opened an
        # EXISTING note from the calendar, Save must not yank them out
        # of the editor mid-session (field feedback: with occurrence
        # saves now riding on explicit gestures, the yank fired on every
        # one). The Back to Calendar button is the way back there.
        _pending = getattr(self, "_pending_calendar_return", None)
        if not auto and _pending and _pending.get("origin") == "add":
            self._return_to_calendar()

    # ---------- Trash / recently deleted ----------
    def _restore_from_trash(self, entry):
        """Bring a trashed note back, then redraw what shows it."""
        self._restore_trash_entries([entry])

    def _restore_trash_entries(self, entries):
        """Bring trashed notes back -- one, or a batch -- then redraw once.
        Returns the notes that came back.

        The data half is in core/storage.py (restore_many_from_trash). A
        note whose category was deleted meanwhile comes back under
        "General" -- normalize_note guarantees that, so nothing here needs
        to re-check it.

        One pass, one write of each file, one redraw, whatever the count:
        a batch used to come back one note at a time, each with its own
        write of the whole trash file, and an Undo of a thousand notes
        froze the app for over half a minute. The notes are written FIRST:
        if that write fails, the notes are still in the trash file -- a
        duplicate at worst, where the old order could leave a note in
        neither file.
        """
        self.notes, self.trash, restored = core_restore_many_from_trash(
            self.notes, self.trash, entries)
        if not restored:
            return restored
        if self.save_notes():
            save_trash(self.trash)
        self.refresh_note_list()
        self.render_calendar()
        return restored

    def _refresh_open_trash_panel(self):
        """Redraw Settings -> Recently deleted if it is the section on
        screen: its rows hold the entries they were drawn for, and a
        restore made from outside the panel leaves them stale."""
        redraw = getattr(self, "_trash_panel_redraw", None)
        if (redraw is None or not getattr(self, "_settings_open", False)
                or getattr(self, "_settings_selected_section", None) != "trash"):
            return
        try:
            redraw()
        except tk.TclError:
            # The panel was rebuilt or torn down since this was recorded.
            self._trash_panel_redraw = None

    def _undo_trash(self, marks):
        """Put back the notes the toast's Undo was offered for.

        `marks` are (id, deleted_at) pairs rather than the trash entries
        themselves: the trash list is rebuilt whenever it is reloaded or
        purged, so an object held from a moment ago can be a stranger by
        the time anybody clicks. Matching on the pair means a later
        delete cannot be mistaken for this one -- a bulk delete shares
        one stamp across its notes, and their ids differ.

        Restores through the same core function Settings uses, so the two
        routes cannot drift into meaning different things. That function
        gives the note a NEW id (the old one may have been reused while
        it sat in the trash), so what comes back is identified by where
        it lands -- appended -- and never by the id that went in.
        """
        # A set of the marks, looked up in one pass over the trash: finding
        # each one with its own scan made a bulk Undo quadratic as well.
        wanted = set(marks)
        entries = [e for e in self.trash
                   if isinstance(e, dict)
                   and (e.get("id"), e.get("deleted_at")) in wanted]
        restored = self._restore_trash_entries(entries)

        if not restored:
            # Emptied, purged, or already put back -- a second click on a
            # toast that had not yet faded. Nothing to apologise for: the
            # note is simply not where the click expected it.
            self._show_toast("Nothing left to put back", kind="info")
            return
        # The toast floats over Settings too, and the Trash's rows are the
        # one view of the trash that does not redraw itself.
        self._refresh_open_trash_panel()

        if len(restored) == 1:
            # Back in front of whoever asked for it: the click meant "I
            # did not mean to delete this", and leaving it in the list
            # answers only half of that. A bulk undo opens nothing --
            # five tabs is not a favour.
            self.open_note_in_tab(restored[0])
            title = (restored[0].get("title") or "").strip() or "Untitled note"
            self.set_status(f"Put back: {title}")
        else:
            self.set_status(f"Put back {len(restored)} notes")

    def _undo_bulk_category(self, marks, applied):
        """Put each note back in the category it was moved out of.

        `marks` carry one (id, category, updated) per note rather than one
        old value for the batch, because the ticked notes can sit in
        several categories at once -- which is the case a bulk change
        exists for, and therefore the case its undo has to get right.

        Only notes still filed under the category this undo is about are
        touched. A second click on a toast that has not yet faded, or a
        category set by hand in the seconds since, must not be overwritten
        by a stale memory of what used to be there -- the same guard
        _undo_trash gets by matching on (id, deleted_at).

        `updated` goes back too. _undo_occurrence_delete stamps `now`
        instead, because it has no record of the old value; here the mark
        carries it, and restoring it means the notes do not all jump to
        the top of a "Recently updated" list on account of a change the
        user just said they did not want.
        """
        # The editor may be holding one of these notes and may have been
        # typed into while the toast was up: save that under the category
        # it was typed against, then move the note, then bring the editor
        # onto the result -- the same order the change itself uses.
        if self._flush_autosave() is False:
            return  # Cancel on a day's save question: the undo waits
        restored = []
        homeless = 0
        for note_id, old_category, old_updated in marks:
            note = self.find_note(note_id)
            if note is None or note.get("category") != applied:
                continue
            if old_category not in CATEGORY_COLORS:
                # Renamed or deleted while the toast was up. There is
                # nowhere to put this note back into, and normalize_note
                # would file it under General on the next load anyway --
                # so leave it where it is and say so, rather than invent
                # a destination.
                homeless += 1
                continue
            note["category"] = old_category
            if isinstance(old_updated, str) and old_updated:
                note["updated"] = old_updated
            restored.append(note)

        if not restored:
            # Already put back, filed elsewhere by hand, or the old
            # categories are gone: a second click on a toast that had not
            # yet faded. Nothing to apologise for -- the notes are simply
            # not where the click expected them.
            self._show_toast("Nothing left to put back", kind="info")
            return

        self.save_notes()
        self._editor_follows_external_change({n["id"] for n in restored})
        self.refresh_note_list()
        # The calendar draws a note with no colour of its own in its
        # category's (get_note_color falls back to CATEGORY_COLORS): its
        # dots, and an open day's stripes. A comment here once said the
        # calendar never read a category, and the dots stayed in the
        # colour the undo had just taken back.
        self.render_calendar()
        if homeless:
            self.set_status(
                f"Put back {len(restored)} note(s); {homeless} could not go "
                "back to a category that no longer exists")
        else:
            self.set_status(f"Put back {len(restored)} note(s)")

    def _undo_checklist_delete(self, items, index, item):
        """Put a removed checklist item back where it was.

        `items` is the working list the item came out of, and it is
        checked by IDENTITY rather than by note id. Every route that
        changes what the editor is holding -- another note, another
        occurrence, a template applied, a new note started -- rebinds
        `_working_checklist` to a fresh list, so a toast clicked after any
        of them is pointing at an editing session that has ended.

        Without that check the item would go back into the captured list,
        which nothing reads any more: the visible result is a redraw of
        somebody else's checklist, a save of the note now open, and a
        status line claiming the item was put back. Not corruption --
        a confident lie, which is the harder one to notice. (Measured:
        the mutant that removes this guard leaves the other note's list
        untouched, so a check watching that list cannot see it.)

        Unlike _undo_bulk_category, this does not restore the note's
        `updated` stamp. There the user was saying "I did not want this at
        all" about notes they were not editing; here they were in the
        editor, working on this note, and the edit genuinely happened --
        a fresh stamp is the honest answer.
        """
        if self._get_checklist() is not items:
            self._show_toast("That note is no longer open", kind="info")
            return
        if any(existing is item for existing in items):
            # A second click on a toast that has not yet faded. Matched by
            # identity, not equality, so an item the user has since typed
            # again by hand is not mistaken for this one.
            self._show_toast("That item is already back", kind="info")
            return
        # The list can have shrunk since -- other items deleted while the
        # offer was up -- so the remembered position is a preference, not
        # a promise. No clamping written here: list.insert already treats
        # an index past the end as "at the end", and a min() in front of
        # it would be code no test could ever make matter.
        drawn = getattr(self, "_checklist_drawn", None)
        in_step = (getattr(self, "_checklist_open", False)
                   and _checklist_rows_current(
                       drawn, items, getattr(self, "theme_name", None)))
        items.insert(index, item)
        if in_step and drawn["rows"]:
            # The one row back where it was, the others untouched.
            at = min(index, len(drawn["rows"]))
            record = self._build_checklist_row(at, item)
            if at < len(drawn["rows"]):
                after = drawn["rows"][at][1]
                record[1].pack_configure(before=after)
                # The stacking order too, not only the packing: Tab walks
                # the tick boxes in it, and winfo_children() lists the rows
                # in it -- a row put back in the middle was reached last.
                record[1].lower(after)
            drawn["rows"].insert(at, record)
            self._update_checklist_progress()
        else:
            self._render_checklist_items()
        self._schedule_autosave()
        self.set_status("Checklist item put back")

    def _undo_occurrence_delete(self, note_id, date_str, own_edit=None):
        """Put back the one day a repeating note was removed from.

        This half has no other way home. Deleting a single occurrence
        writes the date into the note's `exceptions`, and nothing in the
        app takes it out again -- so without this the choice was
        permanent, made from a dialog offering no hint that it was.

        `own_edit` is the day's own title and text the delete took with
        it, if the day had any: the day comes back as it was, not showing
        the series' text in its place.
        """
        note = self.find_note(note_id)
        if note is None:
            self._show_toast("That note is no longer here", kind="info")
            return
        exceptions = set(note.get("exceptions") or [])
        if date_str not in exceptions:
            self._show_toast("That day is already back", kind="info")
            return
        exceptions.discard(date_str)
        note["exceptions"] = sorted(exceptions)
        # Its own edit goes back with it -- unless the day somehow has one
        # again already, which is newer than the one this Undo remembers.
        if own_edit and date_str not in (note.get("overrides") or {}):
            note.setdefault("overrides", {})[date_str] = dict(own_edit)
        note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_notes()
        self.refresh_note_list()
        self.render_calendar()
        self.open_note_in_tab(note, occurrence_date=date_str)
        self.set_status("Put that day back")

    def _attach_dup_preview(self, widget, note):
        """Show a small floating preview of a note's contents while the mouse
        hovers over its row in the duplicates dialog, so the user can tell the
        copies apart before choosing. Vanishes on mouse-leave — no clicking."""
        tip = {"win": None}

        def show(event):
            if tip["win"] is not None:
                return
            # Parented to the WINDOW, not to the row it describes. A
            # Toplevel whose master is a widget appears in that widget's
            # winfo_children(), so a floating preview parented to a row
            # joins the panel's tree -- and everything that walks a panel
            # meets it: a theme sweep, the wheel binding, and any check
            # counting what is on screen.
            #
            # That is not theoretical. It turned CI red on two pull
            # requests while the same script passed on this desktop and on
            # the local Linux image: qa3 counts the trash rows by walking
            # the panel, and on a headless display the pointer sits still
            # over whatever is drawn under it, so one row's preview opened
            # and was counted as a twenty-sixth row. On a desktop the
            # pointer is somewhere else and it never happened. Measured
            # before it was changed -- hovering one row took the count
            # from 25 to 26, with exactly one Toplevel inside the tree.
            win = tk.Toplevel(widget.winfo_toplevel())
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



    def _days_left_in_trash(self, deleted_at):
        """How many days until this trashed note auto-purges. None if unknown."""
        return core_days_left_in_trash(deleted_at)

    def _move_notes_to_trash(self, notes_to_trash):
        """Move one or more notes into the trash rather than destroying them.

        The work is in core/storage.py; this keeps the method name, which
        every delete path and the QA suite call.

        Returns the entries it appended, so a caller offering Undo can
        name exactly what it deleted -- the timestamp is stamped down
        there, and reading it back off the end of the trash is the kind
        of guess that is right until two deletes land together.
        """
        before = len(self.trash)
        core_move_to_trash(self.trash, notes_to_trash)
        return self.trash[before:]

    def delete_current_note(self):
        """Delete the note open in the editor (the Delete button / shortcut)."""
        note = (self.find_note(self.selected_note_id)
                if self.selected_note_id is not None else None)
        if note is None:
            self.show_info("Nothing to delete", "No note is selected.")
            return
        # The typing not yet saved goes with the note, so the Trash copy
        # and the toast's Undo give back what was on screen -- the same
        # first step as a delete from the note's menu.
        if self._flush_autosave() is False:
            return
        self._delete_note(note, self.current_occurrence_date)

    def _delete_note(self, note, occurrence_date):
        """Delete a specific note (or one occurrence of it), no matter what
        the editor is showing. The target arrives as a parameter and the
        editor's selection is never touched on the way in, so cancelling
        either prompt leaves every bit of editor state exactly as it was —
        the selection-repointing shortcut this replaces let a cancelled
        delete aim the next autosave at the wrong note (see ISSUES_LOG)."""
        # Re-anchor on the stored dict: the calendar hands out
        # per-occurrence copies, and mutations below must land in
        # self.notes, not in a copy.
        note = self.find_note(note["id"])
        if note is None:
            return

        if is_recurring(note) and occurrence_date:
            scope = self.ask_occurrence_scope("Delete", occurrence_date)
            if scope is None:
                return
            if scope == "occurrence":
                exceptions = set(note.get("exceptions") or [])
                exceptions.add(occurrence_date)
                note["exceptions"] = sorted(exceptions)
                # Kept for the Undo below: the day's own title and text
                # went with it, and the Undo used to bring back the day
                # showing the series' text instead -- the edit gone for good.
                own_edit = note["overrides"].pop(occurrence_date, None)
                note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_notes()
                if (self.selected_note_id == note["id"]
                        and self.current_occurrence_date == occurrence_date):
                    # The editor was showing the occurrence that just
                    # stopped existing; start it fresh. Deleting some
                    # other note's occurrence leaves the editor alone.
                    self.new_note()
                self.refresh_note_list()
                self.render_calendar()
                self.set_status("Removed that one occurrence")
                # This one had no way back at all: the date goes into the
                # note's exceptions and no screen in the app takes it out
                # again. The toast is not a convenience here.
                self._show_toast(
                    "Occurrence removed",
                    action=lambda nid=note["id"], day=occurrence_date,
                    edit=own_edit: self._undo_occurrence_delete(nid, day, edit))
                return

        attachment_count = len(note.get("attachments") or [])
        warning = ""
        if attachment_count:
            plural = "s" if attachment_count != 1 else ""
            warning = f"\n\n{attachment_count} attached file{plural} will go to trash with it."
        confirm = self.ask_yes_no(
            "Delete note",
            ("Delete this entire repeating series?" if is_recurring(note)
             else "Are you sure you want to delete this note?") + warning,
            # Enter answers a question now: a reflexive one keeps the note.
            default="no"
        )
        if confirm:
            deleted_id = note["id"]
            # Move to trash (30-day recovery) rather than destroying it.
            doomed = [n for n in self.notes if n["id"] == deleted_id]
            marks = [(e.get("id"), e.get("deleted_at"))
                     for e in self._move_notes_to_trash(doomed)]
            self.notes = [n for n in self.notes if n["id"] != deleted_id]
            self.save_notes()
            # Close any open tab that pointed at the deleted note (force: its
            # underlying note is gone, so there's nothing to save).
            self.open_tabs = [t for t in self.open_tabs
                              if t["state"]["selected_note_id"] != deleted_id]
            if not self.open_tabs:
                self.active_tab_index = None
                self.new_note()
            # Otherwise the editor holds some OTHER note, and it stays
            # exactly as it is. This used to "switch" to the one tab left
            # -- the note already on screen -- restoring it from the copy
            # taken when it was opened. Anything saved since (a Restore
            # previous, a day's edit) was put back to that older version,
            # and the next switch wrote the old text over the new.
            self._sync_editor_snapshot()
            # Take the one card off rather than rebuilding all of them.
            # Falls back to the full rebuild whenever the surgical path
            # is not certain -- an emptied list, a grouping header that
            # would not update, a card that is not where the registry
            # says it is.
            if not self._remove_note_cards([deleted_id]):
                self.refresh_note_list()
            self.render_calendar()
            # The window is a setting (Settings -> Recently deleted), so the
            # number is read, never written: this line promised thirty days
            # to someone who had chosen seven.
            self.set_status("Note moved to Trash (recoverable for "
                            f"{trash_retention_days()} days)")
            # The status line says where it went; the toast is the way
            # back. Settings -> Recently deleted was the only route home
            # until now, and it asks you to know the trash exists.
            self._show_toast("Note moved to Trash",
                             action=lambda: self._undo_trash(marks))

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
        """Closing is just switching away from everything -- and switching
        away autosaves without asking. The old quit-time dialog could only
        ever 'protect' the last half-second of typing (anything older was
        already autosaved), so it read as the app doubting its own
        autosave. Whatever is still unsaved is saved, silently, and the
        window closes. One exception is no longer silent: a dirty
        occurrence view (whose background autosave defers rather than
        ask -- see _autosave_now) raises its occurrence-scope question
        here, at the gesture. Cancelling it keeps the window open, on the
        edited day: it used to close anyway and discard the edit, which
        is the opposite of what Cancel means anywhere else.

        Two things come before any of that. A question on screen owns the
        window until it is answered, as a modal question does on Windows:
        the close is refused and the question brought to the front.
        Closing under it destroyed the window while the question still
        waited, and the process lived on with no window, holding the
        notebook lock -- every later launch was refused as "already
        open". And a popup holding typed work (the template editor) has
        its say, as it does on a click outside it; Cancel keeps the
        window open there too."""
        if self._a_dialog_is_asking():
            self._bring_question_forward()
            return
        if not self._dismiss_mini_popup_asking(holding_work_only=True):
            return
        if self._flush_autosave() is False:
            return
        self._sync_active_tab()
        for i in range(len(self.open_tabs)):
            try:
                if not self.editor_state_matches_saved(
                        self.open_tabs[i]["state"]):
                    self.switch_to_tab(i)
                    self.save_current_note(auto=True)
            except Exception:
                # Closing must not get stuck behind a broken tab; the
                # autosaves along the way have the rest.
                self._log_swallowed("close: per-tab final save")
                continue
        # A backup export/import may still be writing on its worker thread;
        # destroy() would kill it mid-file. Wait (capped) for it to finish,
        # then do what its completion would have done on the main thread.
        self._wait_for_io_workers()
        self._settle_background_work_at_close()
        self.destroy()

    def set_status(self, text):
        self.status_lbl.config(text=text)

    def _on_data_write_failure(self, path, exc):
        """core/storage's on_write_failure callback: a data-file write
        failed and would otherwise be invisible. notes_data.json is NOT
        excluded: most of its saves go through the save_notes wrapper and
        raise a louder dialog too (the toast then shows briefly behind
        it — redundant, harmless), but the one-time cleanup rewrite in
        core writes DATA_FILE directly, and excluding it here made that
        failure fully invisible. Scheduled via after() so a failure
        surfacing mid-operation can never interrupt or re-enter the code
        that saved."""
        name = os.path.basename(str(path))
        try:
            self.after(0, lambda: self._show_toast(
                f"Couldn't save {name} — details in crash_log.txt",
                kind="error"))
        except (tk.TclError, RuntimeError):
            pass

    def _run_toast_action(self):
        """Do whatever the toast on screen is offering, once.

        Cleared before it runs, so a double click cannot run it twice, and
        so a click landing as the toast disappears does nothing at all.
        """
        action, self._toast_action = self._toast_action, None
        self._hide_toast()
        if action is not None:
            action()

    def _hide_toast(self):
        try:
            self.toast_frame.place_forget()
        except tk.TclError:
            pass
        self._toast_action = None
        if self._toast_hide_job is not None:
            try:
                self.after_cancel(self._toast_hide_job)
            except (tk.TclError, ValueError):
                pass
            self._toast_hide_job = None

    def _show_toast(self, text, kind="success", action=None, action_text="Undo",
                    yield_to_action=False):
        """Briefly show a small floating banner near the top of the window —
        visible regardless of scroll position or which tab is active. Used for
        'auto-saved' feedback so it's never missed inside a long note.

        With an `action`, the banner also carries one clickable word and
        stays up far longer. 1.8 seconds is feedback; it is not a window
        in which to decide anything, and an Undo nobody can reach is
        decoration.

        `yield_to_action` marks a banner that is only reassurance, and so
        must not stand on top of a one-time chance. The autosave's own
        "Note updated" is the case: a plain banner replaces `_toast_action`
        with None, so an Undo offered a moment earlier was wiped as soon
        as the debounce fired — about a second, not the eight it appeared
        to promise. Measured on the checklist route, and it was already
        true of the bulk category route, where typing anything at all
        removed the offer.
        """
        if not hasattr(self, "toast_frame"):
            return
        if (yield_to_action and getattr(self, "_toast_hide_job", None) is not None
                and (getattr(self, "_toast_action", None) is not None
                     or getattr(self, "_toast_kind", None) == "error")):
            # An offer is on screen right now and has been neither taken
            # nor expired — both of those clear _toast_action, so this
            # cannot mistake a stale one for a live offer. Nothing is
            # lost by staying quiet: every caller that yields also writes
            # the same news to the status line. An error on screen is
            # yielded to as well: the autosave that follows a failed
            # action within its delay covered "something went wrong" with
            # "Note updated", and the one message that mattered was gone.
            return
        color = {"success": self.colors["success"],
                 "info": self.colors["accent"],
                 "error": self.colors["danger"]}.get(kind, self.colors["success"])
        # The mark follows the kind. It used to be a tick whatever had
        # happened, so the banner reporting a failure opened with a tick
        # of success -- and the "nothing left to put back" answer to an
        # Undo would have read as a job well done.
        mark = {"success": "✓", "info": "i", "error": "!"}.get(kind, "✓")
        self._toast_action = action
        self._toast_kind = kind
        try:
            self.toast_frame.configure(bg=color)
            self.toast_lbl.configure(text=f"{mark}  {text}", bg=color, fg="white")
            if action is not None:
                # Recoloured here, not tracked: see where it is built.
                self.toast_action_lbl.configure(text=action_text, bg=color,
                                                fg="white", padx=0)
                self.toast_action_lbl.pack(side="left", padx=(0, 14))
            else:
                self.toast_action_lbl.pack_forget()
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
            self._toast_hide_job = None
            self._hide_toast()

        self._toast_hide_job = self.after(8000 if action else 1800, hide)


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
        # One notebook, one app. Two windows on the same data directory
        # each hold their own copy of the whole notebook and each save
        # rewrites the file wholesale, so the second one to autosave
        # silently deletes everything the first wrote. The lock is taken
        # here rather than in __init__ so the qa scripts, which build
        # several app objects inside one process, are unaffected.
        #
        # BEFORE initialise(), not after: initialise migrates files out of
        # older locations, purges stale copies and stamps the version —
        # so a second launch that was about to be refused had already
        # moved and deleted things in the shared folder, and consumed the
        # one-shot pre-upgrade backup the FIRST instance may still need.
        # Only the data folder has to be resolved first, and resolving is
        # pure: it picks a path and proves it writable, nothing more.
        #
        # Resolved ONCE, and that answer is the one initialise() opens.
        # It used to ask again, and the two answers could differ: two
        # launches probing AppData at the same instant made one of them
        # read it as unwritable, so that launch locked a fallback folder
        # -- then its second answer came back AppData, and it opened the
        # notebook its twin was holding, unlocked and with no warning.
        _resolved = resolve_data_dir(
            os.path.dirname(os.path.abspath(__file__)))
        _data_dir = _resolved[0]
        if not single_instance.acquire(
                os.path.join(_data_dir, single_instance.LOCK_FILENAME)):
            import tkinter.messagebox as _mb
            root = tk.Tk()
            root.withdraw()
            _mb.showinfo(
                "Note Organizer is already open",
                "Note Organizer is already running on this notebook.\n\n"
                "Only one window can be open at a time: two would each keep "
                "their own copy of your notes, and whichever saved last "
                "would overwrite the other's work.\n\n"
                "Switch to the window that is already open — look for it in "
                "the taskbar.")
            root.destroy()
            return
        initialise(resolved=_resolved)
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
            msg = ("Note Organizer hit an unexpected error and needs to close.\n\n"
                   f"{type(exc).__name__}: {exc}\n\n"
                   "Your saved notes are safe on disk.")
            if log_path:
                msg += f"\n\nDetails were written to:\n{log_path}"
            # A plain standard-library dialog on purpose, not our own themed
            # one: if we got here, app construction itself may have failed,
            # so nothing that depends on the app's own widgets/theming can be
            # trusted to work either.
            from tkinter import messagebox as _messagebox
            _messagebox.showerror("Note Organizer", msg)
            root.destroy()
        except Exception:
            # Even the error dialog failed — print as a final fallback.
            print(details)


if __name__ == "__main__":
    _main()