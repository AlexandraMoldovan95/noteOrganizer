"""The note itself: what a note is, and making sure it stays that way.

:data:`NOTE_DEFAULTS` names every field a note has and its empty value.
:func:`normalize_note` is the one gate every note passes before the rest
of the app touches it -- on load, on import, on paste from a share code --
so a field that is missing, mistyped or nonsensical becomes a safe value,
and one corrupt entry cannot take down the list. Validate once, at the
edge, then trust the data inwards. :func:`note_is_empty` and
:func:`note_richness` decide what the cleanup drops and which copy of a
duplicate it keeps. docs/CODE_TOUR.md walks through it.
"""

import copy
import math
import os
import re
import uuid
from datetime import datetime

from .categories import CATEGORY_COLORS
from .formatting import (normalize_formatting, normalize_paragraphs,
                         clamp_spans_per_line)
from .tables import with_caret_line, is_table_row
from .recurrence import (
    normalize_recurrence,
    parse_date,
    format_date,
    read_date,
    expand_occurrences,
    OVERRIDABLE_FIELDS,
    MAX_OCCURRENCES,
    is_recurring,
)

# ---- Note schema + one-time cleanup ----

# The most checklist items one note may carry. Rendering is one Frame +
# Checkbutton + Label + IntVar per item, so an unbounded list is a way to
# kill the app with a pasted share code (see normalize_note).
MAX_CHECKLIST_ITEMS = 1000

# The same ceiling for attachments, which render a row of widgets each and
# arrive by the same untrusted routes. 200 paint in about 0.6 s on a fast
# machine; real notebooks hold tens of files, so none is ever cut short.
MAX_ATTACHMENTS = 200

# Days coloured, or marked with emoji, on the calendar: every day of 54 years.
# Each rides every settings write, and a backup's million made every note take
# seconds to open (ISSUES_LOG: "Limits that held at the door but not after it").
MAX_DAY_DECORATIONS = 20_000
# A marker is one emoji from the picker; the longest, joiners in, is far less.
MAX_DAY_MARKER_CHARS = 16


def is_calendar_day(value):
    """Whether *value* names a day as the calendar writes and looks one up:
    a real date, spelled ``YYYY-MM-DD``. Any other key was never drawn."""
    day = parse_date(value) if isinstance(value, str) else None
    return day is not None and format_date(day) == value


NOTE_DEFAULTS = {
    # Identity, which "id" is not: two devices both number a new note
    # max + 1. A note coming back by share code is recognised by it, not
    # guessed from its text. Set by normalize_note, so no migration is needed.
    "uid": "",
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
    "moved": {},        # date the rule gives a day -> the date it is held on
    "pinned": False,    # pinned notes float to the top of the list
    "checklist": [],    # list of {"text": str, "done": bool} items
    "paragraphs": [],       # list lines: {"line": int, "kind": "bullet"|"number"}
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


_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def sanitize_color(value, default=""):
    """*value* if it is a colour Tk can draw, else *default*; #rgb comes
    back as #rrggbb, the form every reader that works with a colour expects.

    Colours arrive from share codes, backups and hand edits, and a note is
    saved before it is drawn, so garbage here crashed every launch after.
    ISSUES_LOG: "The colour the door let in and the drawing could not read"."""
    if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
        value = value.strip()
        if len(value) == 4:
            value = "#" + "".join(ch * 2 for ch in value[1:])
        return value
    return default


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


def new_note_uid():
    """A fresh note identity: a random uuid4, so two devices can each mint
    one in the same second without consulting the other. Plain text."""
    return str(uuid.uuid4())


def find_by_uid(notes, uid):
    """The note that IS this one, by identity, or None.

    Not :func:`~noteorganizer.core.duplicates._dup_key`, which asks from the
    text whether a note LOOKS like one we have, and so says no exactly when
    it was edited -- the only time anyone re-sends one. Asked first."""
    wanted = _uid_wanted(uid)
    if wanted is None:
        return None
    for note in notes:
        if isinstance(note, dict) and note.get("uid") == wanted:
            return note
    return None


def _uid_wanted(uid):
    """The identity a lookup asks for, or None when it names none."""
    if not isinstance(uid, str) or not uid.strip():
        return None
    return uid.strip()


# The fields an incoming copy replaces. The rest is this device's: its id and
# place, its attachment files (a share code carries none), and the per-day
# exceptions, overrides and moves, a timeline the sender's copy may not share.
UPDATABLE_FROM_SHARED = [
    "title", "body", "formatting", "paragraphs",
    "comments", "category", "date", "color", "recurrence", "checklist",
]

# A backup is the user's OWN notebook, so its copy also owns its timeline and
# pin (its attachment files are the caller's to add). ISSUES_LOG: "Eleven
# decisions about your notes, made from half the evidence".
UPDATABLE_FROM_BACKUP = UPDATABLE_FROM_SHARED + [
    "exceptions", "overrides", "moved", "pinned",
]

# The text half of a rescue copy: what a drastic shrink keeps, and the
# part every rescue copy has. Anything beyond it in ``_prev`` came from
# an update, and "↩ Restore previous" puts that back as well.
PREV_TEXT_FIELDS = ("title", "body", "formatting", "paragraphs", "comments")

# A series' own days, which hang on its repeat and mean nothing without one.
DAY_FIELDS = ("exceptions", "overrides", "moved")


def days_to_rescue(before, recurrence):
    """The days of *before* that writing *recurrence* over it takes away:
    none unless it repeats now and will not after, and only the kinds it
    holds. Whatever ends a repeat COPIES these into its rescue copy and
    leaves the note's own: one copy slot, and the next copy erased days
    moved there (2026-10-28, the final audit, rounds two and three)."""
    if not is_recurring(before) or is_recurring({"recurrence": recurrence}):
        return {}
    return {key: copy.deepcopy(before[key]) for key in DAY_FIELDS if before.get(key)}


def apply_shared_update(note, incoming, fields=UPDATABLE_FROM_SHARED):
    """Overwrite *note*'s *fields* from *incoming* (normalised first),
    keeping every replaced field in ``_prev``, the rescue copy "↩ Restore
    previous" puts back. An update that changes nothing leaves the note
    alone (see shared_update_changes). *fields*: UPDATABLE_FROM_SHARED or
    UPDATABLE_FROM_BACKUP. ISSUES_LOG: "Eleven decisions about your notes,
    made from half the evidence"."""
    fresh = normalize_note(dict(incoming))
    if not shared_update_changes(note, fresh, fields):
        return note
    prev = {
        "title": note.get("title") or "",
        "body": note.get("body") or "",
        "formatting": note.get("formatting") or [],
        "paragraphs": note.get("paragraphs") or [],
        "comments": note.get("comments") or "",
    }
    for field in fields:
        if field not in prev:
            prev[field] = copy.deepcopy(note.get(field, NOTE_DEFAULTS.get(field)))
    # A share code's repeat turned off: this device's days are copied beside
    # the repeat they hang on, and stay in the note -- moved, the next copy
    # erased them. A backup brings its own (UPDATABLE_FROM_BACKUP).
    if "overrides" not in fields and "recurrence" in fields:
        prev.update(days_to_rescue(note, fresh["recurrence"]))
    note["_prev"] = prev
    for field in fields:
        note[field] = copy.deepcopy(fresh[field])
    note["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return note


def rescue_copy_spent(note):
    """Whether *note* holds again everything its rescue copy ``_prev`` kept
    -- the words, their styles and comments, and each other field the copy
    brings back -- so "↩ Restore previous" has nothing left to rescue.
    Undo after a big deletion brought the words back while the button
    stayed, and pressed later it put the old version over everything
    written since (2026-10-22, the owner's call, on both apps)."""
    prev = note.get("_prev")
    if not isinstance(prev, dict):
        return False
    body = note.get("body") or ""
    if ((note.get("title") or "") != (prev.get("title") or "")
            or body != (prev.get("body") or "")
            or (note.get("comments") or "") != (prev.get("comments") or "")):
        return False
    lines = len(body.split("\n"))
    if (normalize_formatting(note.get("formatting") or [])
            != normalize_formatting(prev.get("formatting") or [])):
        return False
    if (normalize_paragraphs(note.get("paragraphs") or [], lines)
            != normalize_paragraphs(prev.get("paragraphs") or [], lines)):
        return False
    return all(prev[key] == note.get(key, NOTE_DEFAULTS.get(key))
               for key in prev if key not in PREV_TEXT_FIELDS)


def text_lost(old, new):
    """How many characters of *old* *new* does not keep at either end: its
    length less the longest start the two share and, of what follows, the
    longest end. Words kept in the middle count as lost, so the measure
    errs towards keeping a copy."""
    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1
    end = 0
    while end < limit - start and old[-1 - end] == new[-1 - end]:
        end += 1
    return len(old) - start - end


_PADDING = re.compile(r" {2,}|-{2,}")


def _without_padding(body):
    """*body* with each table row's padding taken out: what a save loses is
    measured in cells, not in the spaces and dashes lining them up. A cell
    grown wider re-pads every row, and read as the whole table lost, its
    copy replaced the rescue copy the note held (2026-10-28, the audit)."""
    if "|" not in body:
        return body
    return "\n".join(_PADDING.sub(lambda m: m.group()[0], line) if is_table_row(line)
                     else line for line in body.split("\n"))


def rescue_copy_due(old_title, old_body, title, body):
    """Whether a save of *title* and *body* over *old_title* and *old_body*
    keeps the old text as the rescue copy "↩ Restore previous" brings back:
    emptied; more than 40 characters gone, 30% of it or 200; or most of a
    short note, 70% and 15 characters at least. Counted by what is gone, not
    by how much shorter the text got. ISSUES_LOG: "The safety net that
    measured the wrong thing"."""
    old_body, body = _without_padding(old_body), _without_padding(body)
    old_len = len(old_title) + len(old_body)
    if old_len == 0:
        return False
    if len(title) + len(body) == 0:
        return True
    lost = text_lost(old_title, title) + text_lost(old_body, body)
    if lost > 40 and (lost >= old_len * 0.3 or lost >= 200):
        return True
    return lost >= 15 and lost >= old_len * 0.7


def copy_replaced_by_restore(note, prev):
    """What "↩ Restore previous" keeps of the version it replaces, to be
    the rescue copy in its turn: its text, each other field *prev* brings
    back, and a copy of the series' days when the restore ends the repeat
    (days_to_rescue; the note keeps its own). None when it holds nothing
    the restored version lacks: a button offering that would mislead."""
    title = note.get("title") or ""
    taken = {key: days for key, days in
             (days_to_rescue(note, prev["recurrence"]) if "recurrence" in prev else {}).items()
             if key not in prev}
    nothing_lost = ((note.get("body") or "").strip() in (prev.get("body") or "")
                    and (not title.strip() or title == (prev.get("title") or ""))
                    and all(prev[key] == note.get(key, NOTE_DEFAULTS.get(key))
                            for key in prev if key not in PREV_TEXT_FIELDS)
                    and not taken)
    if nothing_lost:
        return None
    kept = {key: copy.deepcopy(note.get(key, NOTE_DEFAULTS.get(key)))
            for key in list(PREV_TEXT_FIELDS) + [k for k in prev if k not in PREV_TEXT_FIELDS]}
    kept.update(taken)
    return kept


def shared_update_changes(note, incoming, fields=UPDATABLE_FROM_SHARED):
    """Whether updating *note* from *incoming* would change any of *fields*,
    both compared as a load shapes them.

    A no-change update would replace the rescue copy with a duplicate and
    lose the one earlier version. ISSUES_LOG: "Importing the same backup
    twice, the second time"; smaller lessons: shared_update_changes."""
    fresh = normalize_note(dict(incoming))
    mine = normalize_note(dict(note))
    return any(mine[field] != fresh[field] for field in fields)


def split_by_identity(notes, incoming):
    """Sort an incoming batch into ``(known, fresh)``: *known* holds
    ``(mine, theirs)`` pairs, *fresh* the notes nothing here matches.

    Both bulk imports -- a share code with several notes, a restored backup
    -- ask this one function: two hand-rolled copies of one judgement is how
    the search rules once drifted apart."""
    # One walk through the notebook, not one per incoming note: a backup of
    # 10,000 notes into a notebook of 10,000 took 1.8 s, frozen. The first
    # note to carry an identity is the one find_by_uid would give.
    mine_by_uid = {}
    for note in notes:
        if isinstance(note, dict) and isinstance(note.get("uid"), str):
            mine_by_uid.setdefault(note["uid"], note)
    known, fresh = [], []
    for note in incoming:
        if not isinstance(note, dict):
            continue
        mine = mine_by_uid.get(_uid_wanted(note.get("uid")))
        if mine is None:
            fresh.append(note)
        else:
            known.append((mine, note))
    return known, fresh


def clean_override(patch):
    """One day's edit of a repeating note, in the shape a load gives it.

    Applied by normalize_note and by the save that writes the edit, so memory
    and a restart agree. A bad colour is dropped, not the whole edit: it
    would raise in Tk while the calendar is drawn at startup. ISSUES_LOG,
    smaller lessons: clean_override."""
    out = {}
    for k, v in patch.items():
        if k not in OVERRIDABLE_FIELDS or not isinstance(v, str):
            continue
        if k == "color":
            v = sanitize_color(v)
            if not v:
                continue
        if k == "category" and v not in CATEGORY_COLORS:
            # A day filed under a deleted category comes back under General,
            # as the note does (a load adopts the notes' own names first).
            # ISSUES_LOG: "The category renamed in one place of six".
            v = "General"
        if k == "body":
            # The base body's canonical form too: the editor draws a line under
            # a trailing table, so without it a day's edit ending in a table
            # always read as unsaved.
            v = with_caret_line(v)
        out[k] = v
    return out


def _bare_file_name(name):
    """*name* as the app stores an attachment: one bare file name.

    basename flattens a smuggled path ("../../x", a UNC root); the rstrip
    drops the trailing dots and spaces Windows ignores when opening, so
    "invoice.lnk. " cannot pass the warn-before-opening gate as harmless."""
    return os.path.basename(name.replace("\\", "/")).rstrip(". ")


# What changes how a name reads without being seen -- controls, bidi marks
# and overrides (U+202E shows "Invoice<U+202E>fdp.exe" as "Invoiceexe.pdf"),
# line separators, the BOM -- out of every name shown and every name written.
HIDDEN_IN_NAMES = re.compile(
    r"[\x00-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069"
    r"\u2028\u2029\ufeff]")


def _type_suffix(name):
    """The last dot and what follows it, as typed; "" when there is none."""
    name = name.rstrip(". ")
    dot = name.rfind(".")
    return name[dot:] if dot >= 0 else ""


def file_type_of(name):
    """The kind of file *name* is as Windows opens it: what follows the last
    dot, lower-case, once the trailing dots and spaces Windows ignores are
    gone; "" when there is none. Not os.path.splitext, for which ".rdp" has
    no extension: to Windows it is an .rdp file, and the app's stamp_ prefix
    made "stamp_.bashrc" a .bashrc where the person's own name was not."""
    if not isinstance(name, str):
        return ""
    return _type_suffix(os.path.basename(name.replace("\\", "/"))).lower()


# The pictures the app shows itself, large, instead of handing them to
# Windows (ui/attachments.py, _show_image_preview). Asked of the stored file,
# never of the label: the row's icon, its hint and the click all agree.
PREVIEWED_IN_APP = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"})

# Kinds whose usual app only shows what is in them: handed to Windows at once.
# Every other kind asks first, since a list of the dangerous ones is never
# complete. ISSUES_LOG: "The photo that was a remote connection".
OPENS_WITHOUT_ASKING = PREVIEWED_IN_APP | frozenset({
    ".jfif", ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico",
    # Formats that cannot carry macros or scripts: not .doc, .xls, .ppt or
    # OpenDocument, which can, nor web pages, .svg or .xml, which a browser runs.
    ".pdf", ".txt", ".md", ".markdown", ".csv", ".log", ".rtf",
    ".docx", ".xlsx", ".pptx",
    # Sound and video; not .wma, .wmv or .asf, whose container can carry
    # script commands and web addresses, nor playlists, which are addresses.
    ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus",
    ".mp4", ".m4v", ".mov", ".avi", ".mkv", ".webm",
})

# Kinds Windows runs, or that run code or reach out when opened: these ask with
# the stronger warning. Missing one costs only the wording -- it still asks.
DANGEROUS_EXTENSIONS = frozenset({
    # Programs and scripts Windows runs outright.
    ".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".msi", ".msp", ".mst",
    ".ps1", ".ps2", ".psm1", ".psd1", ".ps1xml", ".ps2xml", ".psc1", ".psc2",
    ".msh", ".msh1", ".msh2", ".mshxml", ".msh1xml", ".msh2xml",
    ".vbs", ".vbe", ".vb", ".bas", ".js", ".jse", ".wsf", ".wsh", ".ws",
    ".wsc", ".sct", ".hta", ".cpl", ".jar", ".jnlp", ".reg", ".msc",
    ".gadget", ".py", ".pyw", ".pyz", ".pyzw", ".pyc", ".pyo",
    # Shortcuts, installers, disk images and settings files that hand Windows
    # a command, a package, a remote connection or a theme to apply.
    ".lnk", ".url", ".website", ".scf", ".iso", ".img", ".vhd", ".vhdx",
    ".chm", ".hlp", ".inf", ".ins", ".isp", ".appref-ms", ".application",
    ".settingcontent-ms", ".library-ms", ".search-ms", ".appcontent-ms",
    ".msix", ".msixbundle", ".appx", ".appxbundle", ".appinstaller", ".msu",
    ".cab", ".diagcab", ".diagpkg", ".diagcfg", ".xbap", ".rdp", ".theme",
    ".themepack", ".deskthemepack", ".cer", ".crt", ".der", ".mht", ".mhtml",
    ".shs", ".shb", ".mcf", ".xnk", ".glk", ".wiz", ".wsb",
    # Documents and add-ins that carry macros or fetch data when opened.
    ".docm", ".dotm", ".xlsm", ".xltm", ".xlsb", ".xlam", ".xla", ".xll",
    ".pptm", ".potm", ".ppsm", ".ppam", ".sldm", ".iqy", ".slk",
    ".one", ".onepkg", ".pub", ".mdb", ".accdb", ".accde", ".mde", ".mda",
    ".ade", ".adp",
})


def how_to_open(name):
    """How the attachment stored as *name* opens -- judged from the stored
    file, never from its label: "preview" (the app shows it), "open" (handed
    to Windows at once), "warn" (asks, saying it can run programs) or "ask"
    (asks, saying the app does not know the kind)."""
    kind = file_type_of(name)
    if kind in PREVIEWED_IN_APP:
        return "preview"
    if kind in OPENS_WITHOUT_ASKING:
        return "open"
    if kind in DANGEROUS_EXTENSIONS:
        return "warn"
    return "ask"


# What Windows refuses in a file name: its reserved punctuation and every
# control character. A title holding a control character could not be exported.
_FORBIDDEN_IN_FILE_NAMES = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def export_file_stem(title):
    """A file name made from a note's title, before its extension: what Windows
    refuses becomes "_", what hides or reorders text goes, the ends lose their
    dots and spaces, and 60 characters are kept -- "note" when none are left.
    The single-note export and the bulk one both name their files by it."""
    stem = HIDDEN_IN_NAMES.sub("", _FORBIDDEN_IN_FILE_NAMES.sub("_", title))
    return stem.strip(" ._")[:60] or "note"


def attachment_display_name(filename, stored_as):
    """The name a person is shown for an attachment: *filename*, a label a
    backup can write over any file, cleaned of HIDDEN_IN_NAMES and made to
    end in the type of *stored_as*, the file that opens ("Holiday photo.jpg"
    over an .rdp shows "Holiday photo.rdp"). The app's own records already
    agree, so they show as they were; a second pass changes nothing.
    ISSUES_LOG: "The photo that was a remote connection"."""
    stored = stored_as if isinstance(stored_as, str) else ""
    stored_name = HIDDEN_IN_NAMES.sub("", os.path.basename(stored.replace("\\", "/")))
    name = HIDDEN_IN_NAMES.sub("", filename if isinstance(filename, str) else "")
    if not name.strip(". "):
        name = stored_name
    if not stored:
        return name
    # Cleaned too, so the name shown never carries a hidden character the
    # stored one has. A type that held one is no type Windows knows.
    real = HIDDEN_IN_NAMES.sub("", file_type_of(stored))
    if file_type_of(name) == real:
        return name
    stem = name.rstrip(". ")
    if real:
        stem = stem[:len(stem) - len(_type_suffix(stem))]
    else:
        # A file with no type shows none: "photo.tar.jpg" over a file that
        # has none would still read as a .tar.
        while _type_suffix(stem):
            stem = stem[:len(stem) - len(_type_suffix(stem))].rstrip(". ")
    return (stem + real) or stored_name


def normalize_note(note):
    """Guarantee every note has every field, with the right type. Older notes
    were saved before 'comments', 'date', 'color' and 'attachments' existed,
    and code that reads note['title'] directly crashes on those."""
    clean = {}
    # Coerced like the rest: a string, list or None id survived load and broke
    # every max(ids) + 1 in the app (new note, duplicate, import, restore).
    raw_id = note.get("id", 0)
    if isinstance(raw_id, bool) or not isinstance(raw_id, int):
        try:
            raw_id = int(str(raw_id).strip())
        except (TypeError, ValueError):
            raw_id = 0
    clean["id"] = raw_id
    # The rescue copy ("↩ Restore previous") is not part of a note's shape,
    # but dropped here the button promised what the next launch had already
    # thrown away. Carried through, shallowly validated.
    prev = note.get("_prev")
    if isinstance(prev, dict):
        clean["_prev"] = {
            "title": prev.get("title") if isinstance(prev.get("title"), str) else "",
            "body": prev.get("body") if isinstance(prev.get("body"), str) else "",
            "comments": prev.get("comments") if isinstance(prev.get("comments"), str) else "",
            # Restoring a previous version puts these spans straight into
            # the editor, so the line ceiling has to hold here too.
            "formatting": clamp_spans_per_line(
                prev.get("body") if isinstance(prev.get("body"), str) else "",
                normalize_formatting(
                    prev.get("formatting")
                    if isinstance(prev.get("formatting"), list) else [])),
            "paragraphs": normalize_paragraphs(
                prev.get("paragraphs") if isinstance(prev.get("paragraphs"), list) else []),
        }
        # What an update replaced beyond the text rides along, shaped by the
        # note's own rules (a restore puts it back INTO the note). An absent
        # key stays absent: that tells an update's copy from a shrink's.
        extra = {key: prev[key] for key in UPDATABLE_FROM_BACKUP
                 if key not in PREV_TEXT_FIELDS and key in prev}
        if extra:
            shaped = normalize_note(extra)
            for key in extra:
                clean["_prev"][key] = shaped[key]
    for key, default in NOTE_DEFAULTS.items():
        value = note.get(key, default)
        if isinstance(default, str) and not isinstance(value, str):
            value = default
        if isinstance(default, list) and not isinstance(value, list):
            value = []
        if isinstance(default, dict) and not isinstance(value, dict):
            value = {}
        clean[key] = value
    # After the defaults loop, which rewrites every key and once wiped an
    # identity minted earlier. A uid already there is trusted as text: another
    # program may have minted it, and uniqueness is all that is needed.
    clean["uid"] = clean["uid"].strip() or new_note_uid()
    if not clean["updated"]:
        # Includes seconds (not just minutes) so two notes saved in the same
        # minute still sort correctly by "Recently updated" instead of tying.
        clean["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Old notes predate the 'created' field — approximate it with 'updated' so
    # they still show a sensible creation date.
    if not clean["created"]:
        clean["created"] = clean["updated"]
    clean["pinned"] = bool(clean.get("pinned"))
    # The place in Custom order, absent until a person moves the note: "not
    # placed yet" is its own answer, so it is not in NOTE_DEFAULTS. Kept only
    # if a finite number -- True, "3" or NaN would reach the sort comparator.
    order = note.get("order")
    if (isinstance(order, (int, float)) and not isinstance(order, bool)
            and math.isfinite(order)):
        clean["order"] = order
    if clean["category"] not in CATEGORY_COLORS:
        clean["category"] = "General"

    clean["recurrence"] = normalize_recurrence(clean["recurrence"])

    # A date written another readable way (day first, from an older share code
    # or a hand edit) is stored in the one form the calendar places notes by;
    # an unreadable one is kept as it came (see _date_and_repeat_to_store).
    if clean["date"] and not parse_date(clean["date"]):
        day = read_date(clean["date"])
        if day is not None:
            clean["date"] = format_date(day)

    # A recurring rule with no anchor date can't be placed on a calendar,
    # so it degrades to a normal note instead of silently disappearing.
    if clean["recurrence"]["freq"] and not parse_date(clean["date"]):
        clean["recurrence"] = normalize_recurrence({})

    clean["exceptions"] = sorted({
        d for d in clean["exceptions"] if isinstance(d, str) and parse_date(d)
    })

    # A day held on another date ("Move this day"): both real dates, never
    # the same one, no two days on one date, and no move of a deleted day.
    # Capped as a rule's days are: each is worked out on every calendar draw.
    moved, held_on = {}, set()
    # A set: the sorted list, walked whole for every moved day, took the
    # square of their number to load.
    deleted = set(clean["exceptions"])
    for orig, new in sorted((k, v) for k, v in clean["moved"].items()
                            if isinstance(k, str) and isinstance(v, str)):
        if (parse_date(orig) and parse_date(new) and orig != new
                and new not in held_on and orig not in deleted):
            moved[orig] = new
            held_on.add(new)
            if len(moved) >= MAX_OCCURRENCES:
                break
    clean["moved"] = moved

    # The line the editor guarantees under a trailing table, carried into
    # the stored form so the two can never disagree. See with_caret_line.
    clean["body"] = with_caret_line(clean["body"])

    # Bounded by the body's real line count, so an entry left pointing past
    # the end of a note that was later shortened is dropped rather than kept
    # around to indent a line that no longer exists.
    clean["paragraphs"] = normalize_paragraphs(
        clean["paragraphs"], len(clean["body"].split("\n")))

    clean["overrides"] = {
        d: clean_override(patch)
        for d, patch in clean["overrides"].items()
        if isinstance(d, str) and parse_date(d) and isinstance(patch, dict)
    }


    # Tags were removed as a feature — drop any leftover "tags" key from
    # notes saved before this cleanup, so old data doesn't keep carrying it
    # around indefinitely once re-saved.
    clean.pop("tags", None)

    # Each item coerced to {"text": str, "done": bool}, and the count capped
    # here, where every route passes: each item is widgets when drawn.
    # ISSUES_LOG, smaller lessons: the checklist ceiling.
    checklist = []
    for item in clean.get("checklist", []):
        if isinstance(item, dict):
            text = item.get("text", "")
            if not isinstance(text, str):
                text = ""
            checklist.append({"text": text, "done": bool(item.get("done"))})
        if len(checklist) >= MAX_CHECKLIST_ITEMS:
            break
    clean["checklist"] = checklist

    # stored_as kept to a bare file name, closing path traversal for every
    # route at once (the app itself writes nothing else). ISSUES_LOG: "The
    # share code that could delete your files".
    attachments = []
    for att in clean.get("attachments", []):
        if not isinstance(att, dict):
            continue
        # The two names are all a record is: copied whole, a crafted record
        # carried anything else it held into every save, and a value nested
        # a few hundred deep made Duplicate fail.
        item = {key: att[key] for key in ("filename", "stored_as") if key in att}
        stored = item.get("stored_as")
        if isinstance(stored, str) and stored:
            stored = _bare_file_name(stored)
            item["stored_as"] = stored
        else:
            stored = ""
        # Both names made strings: a record without them aborted the note's
        # load halfway, and the next save wrote the PREVIOUS note's checklist
        # onto this one. A record naming no file at all is dropped.
        display = item.get("filename")
        if not isinstance(display, str) or not display:
            display = stored
        if not stored and not display:
            continue
        item["filename"] = display
        if not isinstance(item.get("stored_as"), str) or not item["stored_as"]:
            # The display name stands in, flattened the same way: taken as it
            # was, a filename of "../../x" kept the path the rule above removes.
            item["stored_as"] = _bare_file_name(display)
            if not item["stored_as"]:
                continue
        # The label agrees with the file that opens, and hides nothing.
        # ISSUES_LOG: "The photo that was a remote connection".
        item["filename"] = attachment_display_name(display, item["stored_as"])
        attachments.append(item)
        if len(attachments) >= MAX_ATTACHMENTS:
            # Same class as the checklist cap above: an unbounded list a
            # share code can inflate for free, met by a renderer that
            # rebuilds a row per entry.
            break
    clean["attachments"] = attachments

    # Two anti-bomb ceilings: the note's total spans, and those on any ONE
    # line, the shape that stops Tk finishing the draw (MAX_SPANS_PER_LINE).
    clean["formatting"] = clamp_spans_per_line(
        clean["body"], normalize_formatting(clean.get("formatting")))

    # A colour the app can't draw must not survive to the render: the
    # note is saved before it is first drawn, so garbage here used to be
    # a crash on every subsequent launch.
    clean["color"] = sanitize_color(clean.get("color"))

    return clean


def reading_time(word_count, wpm=200):
    """Roughly how long this many words takes to read, as a phrase; "" for
    none. 200 words a minute is the slow end of adult reading: a reader who
    finishes early has lost nothing, and one who runs over was misled."""
    if not isinstance(word_count, int) or isinstance(word_count, bool):
        return ""
    if word_count <= 0:
        return ""
    if word_count < wpm:
        return "under a minute to read"
    minutes = int(round(word_count / wpm))
    return f"about {minutes} minute{'' if minutes == 1 else 's'} to read"


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
    """A note with no content at all: a stray '+ New Note' click.

    "Content" means what the editor means by it, or the cleanup deletes
    notes the app let you make: a checklist, a repeat rule and a date all
    count. ISSUES_LOG: "The note the editor let you make and the launcher
    deleted"."""
    def _s(v):
        return v.strip() if isinstance(v, str) else ""
    recurrence = note.get("recurrence")
    repeats = isinstance(recurrence, dict) and recurrence.get("freq")
    checklist = note.get("checklist")
    return not (
        _s(note.get("title"))
        or _s(note.get("body"))
        or _s(note.get("comments"))
        or note.get("attachments")
        or (isinstance(checklist, list) and checklist)
        or repeats
        or _s(note.get("date"))
    )


def _stable(value):
    """Any JSON-ish value as something hashable and comparable. Defensive:
    the stale-copy purge signs raw dicts read straight off disk, and an
    exception here would abort a startup."""
    if isinstance(value, dict):
        return tuple(sorted((str(k), _stable(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_stable(v) for v in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _checklist_signature(checklist):
    """A checklist as a hashable tuple, for the duplicate test."""
    if not isinstance(checklist, list):
        return ()
    out = []
    for item in checklist:
        if isinstance(item, dict):
            text = item.get("text")
            out.append(((text.strip() if isinstance(text, str) else ""),
                        bool(item.get("done"))))
    return tuple(out)


def _attachment_signature(attachments):
    if not isinstance(attachments, list):
        return ()
    return tuple(sorted(
        str(a.get("stored_as") or "") for a in attachments
        if isinstance(a, dict)))


def _recurrence_signature(recurrence):
    """A repeat rule as a hashable tuple: its meaning, not its spelling. A
    no-repeat rule is ``{}`` by hand and a defaulted dict once normalised;
    signed differently, the purge and the duplicate scan stopped matching a
    note whenever one side had been normalised and the other had not."""
    if not isinstance(recurrence, dict):
        return ()
    normalized = normalize_recurrence(recurrence)
    if not normalized.get("freq"):
        return ()
    return tuple(sorted(
        (k, str(v)) for k, v in normalized.items() if k != "freq"
    )) + (str(normalized["freq"]),)


def content_signature(note):
    """THE identity of a note's content: one definition, every consumer.

    Three routes remove notes with nobody asked (the startup collapse, the
    stale-copy purge, a backup's Trash skip), so it is strict: all but 'id',
    'uid' and 'updated' counts. ISSUES_LOG: "The note the editor let you make
    and the launcher deleted", then "Eleven decisions about your notes"."""
    def _text(value):
        return value.strip() if isinstance(value, str) else ""
    return (
        _text(note.get("title")),
        _text(note.get("body")),
        _text(note.get("comments")),
        str(note.get("category") or ""),
        str(note.get("date") or ""),
        _checklist_signature(note.get("checklist")),
        _attachment_signature(note.get("attachments")),
        _recurrence_signature(note.get("recurrence")),
        _stable(note.get("formatting")),
        _stable(note.get("paragraphs")),
        _stable(note.get("overrides")),
        _stable(note.get("exceptions")),
        _stable(note.get("moved")),
        bool(note.get("pinned")),
        _text(note.get("color")),
    )


def clean_notes(notes):
    """Drop empty notes, collapse exact duplicates, and re-number IDs.
    Returns (cleaned_notes, stats)."""
    stats = {"before": len(notes), "empty_removed": 0, "duplicates_removed": 0}

    kept = [n for n in notes if not note_is_empty(n)]
    stats["empty_removed"] = len(notes) - len(kept)

    # Two notes are "the same" if their actual content matches — as
    # defined ONCE, for every consumer, by content_signature above.
    best_by_signature = {}
    order = []
    for note in kept:
        signature = content_signature(note)
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


def repair_note_ids(notes):
    """Make every note's id a positive number no other note shares; True
    when anything changed. Run on every load: the first holder of a number
    keeps it, so a remembered open note is still the same one, and later
    holders get the next free number. ISSUES_LOG, smaller lessons:
    repair_note_ids."""
    next_id = max((n["id"] for n in notes if n["id"] > 0), default=0) + 1
    seen = set()
    changed = False
    for note in notes:
        if note["id"] > 0 and note["id"] not in seen:
            seen.add(note["id"])
            continue
        note["id"] = next_id
        seen.add(next_id)
        next_id += 1
        changed = True
    return changed


# ---- Looking notes up, and moving them between categories ----
# Reads and rewrites of the notes list, taken as the first argument. Each also
# handles per-day edits, which can name a category of their own.

def find_note(notes, note_id):
    """The note with this id, or None."""
    for n in notes:
        if n["id"] == note_id:
            return n
    return None


def count_notes_in_category(notes, name):
    """How many notes use this category.

    A note counts once even if several of its overrides name the category,
    which is why this breaks out of the inner loop.
    """
    total = 0
    for n in notes:
        if n.get("category") == name:
            total += 1
            continue
        for patch in (n.get("overrides") or {}).values():
            if patch.get("category") == name:
                total += 1
                break
    return total


def rename_category_everywhere(notes, old_name, new_name):
    """Rewrite every reference to a category: base notes, per-day edits and
    each rescue copy ("↩ Restore previous"). Used for a rename and for moving
    notes out of a deleted category; returns how many notes held the name.
    ISSUES_LOG: "The category renamed in one place of six"; smaller lessons:
    rename_category_everywhere."""
    held = 0
    for n in notes:
        found = False
        for holder in (n, n.get("_prev")):
            if not isinstance(holder, dict):
                continue
            if holder.get("category") == old_name:
                holder["category"] = new_name
                found = True
            # Trash entries are kept as the file held them, unshaped.
            overrides = holder.get("overrides")
            for patch in (overrides.values() if isinstance(overrides, dict)
                          else ()):
                if isinstance(patch, dict) and patch.get("category") == old_name:
                    patch["category"] = new_name
                    found = True
        held += found
    return held


def notes_on_date(notes, date_str):
    """Every note that lands on this date, recurring ones included.

    A recurring note has one stored entry but appears on many days, so this
    asks the recurrence engine to expand each note over a single-day window
    rather than comparing stored dates.
    """
    target = parse_date(date_str)
    if target is None:
        return []
    return [n for n in notes if expand_occurrences(n, target, target)]
