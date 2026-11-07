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
import functools
import math
import os
import re
import unicodedata
import uuid
from collections import Counter

from .categories import CATEGORY_COLORS
from .storage import now_stamp
from .formatting import (normalize_formatting, normalize_paragraphs,
                         clamp_spans_per_line, strip_list_markers,
                         day_paragraphs, list_lines)
from .tables import with_caret_line
from .recurrence import (
    effective_note,
    normalize_recurrence,
    parse_date,
    format_date,
    read_date,
    expand_occurrences,
    OVERRIDABLE_FIELDS,
    MAX_OCCURRENCES,
    day_as_kept,
    is_recurring,
    off_schedule_days,
    _rule_days_among,
)


# ---- What a search compares ----

@functools.lru_cache(maxsize=1)
def _search_fold_table():
    """Each character of the basic plane as a search compares it: its base
    letter, the diacritic dropped, then lowered -- always one character for
    one, so a match's place in the text is its place in the folded text.
    Only marks are dropped: a Korean syllable comes apart into letters, and
    cut to its first it found every syllable that starts with the same one."""
    table = {}
    for code in range(0x10000):
        if 0xD800 <= code <= 0xDFFF:
            continue
        ch = chr(code)
        parts = unicodedata.normalize("NFD", ch)
        marks = all(unicodedata.category(m) == "Mn" for m in parts[1:])
        base = parts[0] if marks else ch
        low = base.lower()
        folded = low if len(low) == 1 else base
        if folded != ch:
            table[code] = folded
    return table


def fold_for_search(text):
    """*text* as every search in the app compares it -- the list, Find in
    note, the History: case and diacritics gone, so "creme brulee" finds
    "Crème brûlée", and an s with a comma below finds one with a cedilla."""
    if text.isascii():
        return text.lower()          # the same answer, without the table
    return text.translate(_search_fold_table())


# ---- Note schema + one-time cleanup ----

# The most checklist items one note may carry. Rendering is one Frame +
# Checkbutton + Label + IntVar per item, so an unbounded list is a way to
# kill the app with a pasted share code (see normalize_note).
MAX_CHECKLIST_ITEMS = 1000

# And the longest item a box adds: each is drawn as one wrapped label, as tall
# as its text, and a pasted page made one tens of thousands of pixels tall. One
# already longer is kept whole, and drawn cut (checklist_shown).
MAX_CHECKLIST_ITEM_CHARS = 2_000
# The lines of one item its row draws: a line break is a line however short.
CHECKLIST_SHOWN_LINES = 100

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


def checklist_shown(text):
    """A checklist item as its row draws it: as it is, unless longer than
    MAX_CHECKLIST_ITEM_CHARS or CHECKLIST_SHOWN_LINES, then cut there with an
    ellipsis. Display only: an item saved before the limit, or brought by a
    share code, keeps every word in the note."""
    if not isinstance(text, str):
        return ""
    lines = text.split("\n")
    if (len(text) <= MAX_CHECKLIST_ITEM_CHARS
            and len(lines) <= CHECKLIST_SHOWN_LINES):
        return text
    shown = "\n".join(lines[:CHECKLIST_SHOWN_LINES])[:MAX_CHECKLIST_ITEM_CHARS]
    return shown.rstrip() + "…"


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


# A day's words, which go with a repeat turned off; the rest of a day's edit,
# its look, says nothing the person typed (spend_series_days keeps both).
DAY_WORDS = ("title", "body", "comments")
_DAY_LOOK = tuple(key for key in OVERRIDABLE_FIELDS if key not in DAY_WORDS)


def _same_word(word, a, b):
    """Whether two of a day's words say the same: a title without the spaces
    around it, as day_matches_series reads one; a text with the line under a
    closing table on both sides or neither (with_caret_line) -- a copy the
    phone made keeps its series' text as typed and its days with the line,
    and a colour-only day read as words."""
    a, b = str(a or ""), str(b or "")
    if word == "title":
        return a.strip() == b.strip()
    if word == "body":
        return with_caret_line(a) == with_caret_line(b)
    return a == b


def day_has_words(note, day):
    """Whether *note*'s edit of *day* holds a title, text or comments of its
    own -- what the day holds (day_as_kept), not what it shows."""
    shown = day_as_kept(note, day)
    return any(not _same_word(key, shown.get(key), note.get(key)) for key in DAY_WORDS)


def days_hold_own_text(note):
    """Whether a day of *note* shows a title, text or comments of its own --
    asked of a note that may no longer repeat, so of what each day holds
    (day_as_kept), not of what it shows."""
    return any(day_has_words(note, day) for day in (note.get("overrides") or {}))


# What only an update's copy holds (apply_shared_update, the phone's too): a
# series' own copy -- a turn-off's, on either app -- holds the text, the date,
# the repeat and the days, and nothing of these.
_UPDATE_COPY_ONLY = ("category", "color", "checklist", "pinned")


def _series_own_copy(prev):
    """Whether *prev* is the copy a repeat's turn-off made of its series."""
    return (isinstance(prev, dict) and is_recurring(prev)
            and not any(key in prev for key in _UPDATE_COPY_ONLY))


def update_copy(prev):
    """Whether *prev* is the copy an import's Update made: the note as it
    was here before the backup's version replaced it."""
    return isinstance(prev, dict) and any(key in prev for key in _UPDATE_COPY_ONLY)


def comments_kept_by_copy(copy_comments, comments):
    """Which comments a waiting copy keeps when a save clears *comments*
    over a copy that holds *copy_comments*: the ones whose loss would be
    the larger, counted by what is gone (_lost). Two letters cleared after
    a long comment was deleted lose to it, as the body's words do; a long
    comment cleared over a short one takes its place."""
    if _lost(comments, copy_comments) < _lost(copy_comments, comments):
        return copy_comments
    return comments


def _same_series(day, rule, other_day, other_rule):
    """Whether two starts and rules are one series. A weekly rule's start
    weekday lit, or left to the start, is the same rule -- as a monthly
    rule's day: the editor stores both, and a series turned back on as it
    was read as another."""
    if day != other_day:
        return False
    rules = (normalize_recurrence(rule), normalize_recurrence(other_rule))
    when = parse_date(day)
    for rec in rules if when is not None else ():
        if rec["freq"] == "weekly" and not rec["weekdays"]:
            rec["weekdays"] = [when.weekday()]
        if rec["freq"] == "monthly" and not rec["month_days"]:
            rec["month_days"] = [when.day]
    # A field the frequency never reads changes no day: kept hidden (the
    # phone's sheet stores all three), it made a series turned back on as it
    # was read as another.
    for rec in rules:
        if rec["freq"] != "weekly":
            rec["weekdays"] = []
        if rec["freq"] != "monthly":
            rec["month_days"] = []
        # "Skip that month" is read only where a month can lack the day.
        if not (rec["freq"] == "monthly" and any(day > 28 for day in rec["month_days"])
                or rec["freq"] == "yearly" and when is not None and (when.month, when.day) == (2, 29)):
            rec["month_day_policy"] = "clamp"
    return rules[0] == rules[1]


def _repeats_as(note, prev):
    """Whether *note* repeats as the series *prev* holds: its date and rule."""
    return (is_recurring(note) and _same_series(prev.get("date"), prev.get("recurrence"),
                                                note.get("date"), note.get("recurrence")))


def copy_holds_this_series(note):
    """Whether *note*'s rescue copy is the copy a turn-off made of the very
    series the note repeats as again: same date, same rule."""
    prev = note.get("_prev")
    return _series_own_copy(prev) and _repeats_as(note, prev)


def _dates_held(note):
    """The dates *note*'s own days speak for: a day edited, deleted or
    moved, and the dates days are moved to."""
    moved = note.get("moved") or {}
    return (set(note.get("overrides") or {}) | set(note.get("exceptions") or [])
            | set(moved) | set(moved.values()))


def spend_series_days(note):
    """Once the note repeats as its series' copy again, the copy's days come
    back into the note and are spent from the copy. A copy's day is dropped
    only where the note deleted that day; one whose words a day already
    holding words lacks is set aside, to be a note of its own (_set_aside).
    ISSUES_LOG: "Round ten: the days a date held without a word", and round
    fifteen: four ways of adding its words to the day each left a case."""
    if not copy_holds_this_series(note):
        return
    prev = note["_prev"]
    held = _dates_held(note)
    moved = dict(note.get("moved") or {})
    moved.update(_copy_moves_taken(prev.get("moved") or {}, held, len(moved)))
    overrides, aside = _copy_days_placed(note, prev, moved)
    exceptions = set(note.get("exceptions") or [])
    exceptions.update(day for day in prev.get("exceptions") or [] if day not in held)
    note["overrides"], note["exceptions"], note["moved"] = overrides, sorted(exceptions), moved
    for key in DAY_FIELDS:
        prev.pop(key, None)
    if aside:
        note["_set_aside"] = (note.get("_set_aside") or []) + aside


def _copy_moves_taken(theirs, held, room):
    """The copy's moves *theirs* the note takes: of a day its own days
    leave alone, onto a date they leave free, while it holds fewer than a
    series' most (*room* its own) -- and none onto a day whose own move
    stays behind: that day stays on its date, and two days on one date were
    drawn as one."""
    taken = {}
    for day, to in sorted(theirs.items()):
        # Never onto a date the note holds: normalize_note keeps one day a
        # date, and the first in order -- the copy's -- would push the note's out.
        if day not in held and to not in held and room + len(taken) < MAX_OCCURRENCES:
            taken[day] = to
    onto = {to: day for day, to in taken.items()}
    home = [day for day in theirs if day not in taken]
    while home:
        day = onto.pop(home.pop(), None)
        if day is not None:
            del taken[day]
            home.append(day)
    return taken


def _own_words_held(prev, key, note, at):
    """Whether *note*'s day *at* holds every word *prev*'s day *key* has of
    its own: each title, text or comments it holds unlike its series'
    (day_as_kept, _same_word) -- the series' words are not the day's."""
    theirs, mine = day_as_kept(prev, key), day_as_kept(note, at)
    return all(_same_word(word, theirs.get(word), prev.get(word))
               or _same_word(word, theirs.get(word), mine.get(word)) for word in DAY_WORDS)


def _aside_entry(prev, key, at):
    """*prev*'s day *key*, drawn on *at*, as the copy kept it: what a note of
    its own is made of (notes_set_aside)."""
    kept = day_as_kept(prev, key)
    entry = {word: str(kept.get(word) or "") for word in OVERRIDABLE_FIELDS}
    entry["day"] = at
    return entry


def copy_days_set_aside(note, incoming=None):
    """Before *note*'s rescue copy is replaced: the days with words of their
    own of a series' copy the note no longer repeats as, set aside to be
    notes of their own. The copy was the only place they were kept, and the
    next turn-off or big delete erased them. An Update's copy too,
    as a restore leaves it; held by the note, or by the *incoming*
    note whose days a backup's Update is about to write."""
    prev = note.get("_prev")
    if not isinstance(prev, dict) or not is_recurring(prev) or _repeats_as(note, prev):
        return
    came = {to: day for day, to in (prev.get("moved") or {}).items()}

    def held(key):
        # A holder's day for it: on its date, on the day the copy moved there
        # from, or where the holder has moved that day since -- by date alone, a
        # day the note moved was set aside as words it still held.
        day = came.get(key, key)
        for holder in (note, incoming) if incoming is not None else (note,):
            mine, moved = holder.get("overrides") or {}, holder.get("moved") or {}
            if any(at in mine and _own_words_held(prev, key, holder, at)
                   for at in {key, day, moved.get(day, day)}):
                return True
        return False

    aside = [_aside_entry(prev, key, key) for key in sorted(prev.get("overrides") or {})
             if day_has_words(prev, key) and not held(key)]
    if aside:
        note["_set_aside"] = (note.get("_set_aside") or []) + aside
    for key in DAY_FIELDS:
        prev.pop(key, None)


def notes_set_aside(note):
    """The notes made of *note*'s days set aside (_set_aside), each on its
    date with its words, look and the series' title marked "(earlier text)",
    taken off the note. Shown on its day, they were read four ways in four
    rounds, each leaving a case; a note of its own is seen and kept as it is
    (the owner's choice)."""
    made = []
    # Shaped as a read shapes them: an entry with no words made an empty
    # note at a save, and none at the start.
    for entry in _shaped_aside(note.pop("_set_aside", None)):
        title = entry.get("title") or note.get("title") or ""
        made.append({"title": (title + " (earlier text)").strip(), "body": entry.get("body", ""),
                     "comments": entry.get("comments", ""),
                     "category": entry.get("category") or note.get("category") or "",
                     "color": entry.get("color", ""), "date": entry.get("day", "")})
    return made


def settle_set_aside(notes):
    """Each note of *notes* whose days were set aside given them as notes of
    their own (notes_set_aside), added at the end and numbered on from the
    highest, worked out once -- asked for each, the whole notebook was walked
    for every note made. Returns how many. At the start (core load_notes,
    which writes them at once: left for the next save, each start made them
    again under new identities) and at every save."""
    stamp = now_stamp()
    made, next_id, held = 0, None, set()
    for note in list(notes):
        if not isinstance(note, dict) or not note.get("_set_aside"):
            continue
        if next_id is None:
            next_id = max([n["id"] for n in notes], default=0) + 1
            # A note already holding the same words on the same day is that
            # note: a backup's Update made it again at every import.
            held = {(n.get("title"), n.get("date"), n.get("body"), n.get("comments"))
                    for n in notes if isinstance(n, dict)}
        for fresh in notes_set_aside(note):
            made_note = normalize_note(dict(fresh, id=next_id, created=stamp, updated=stamp))
            # Its comments among its words: other comments are another note.
            key = (made_note["title"], made_note["date"], made_note["body"], made_note["comments"])
            if key in held:
                continue
            held.add(key)
            notes.append(made_note)
            next_id += 1
            made += 1
    return made


def _shaped_aside(entries):
    """A note's days set aside, as a load reads them: each with a real date,
    written as the calendar keys one, and a word, every field text."""
    kept = []
    for entry in entries if isinstance(entries, list) else []:
        when = parse_date(entry.get("day")) if isinstance(entry, dict) else None
        if when is None:
            continue
        shaped = {key: entry.get(key) if isinstance(entry.get(key), str) else ""
                  for key in OVERRIDABLE_FIELDS}
        shaped["day"] = format_date(when)
        if any(shaped[word].strip() for word in DAY_WORDS):
            kept.append(shaped)
            # Capped as moved days are: each becomes a note at the next start,
            # and a file can say anything. A save empties the list each time.
            if len(kept) >= MAX_OCCURRENCES:
                break
    return kept


def _copy_days_placed(note, prev, moved):
    """*note*'s days' edits with *prev*'s put in on the dates the note draws
    their days (*moved*, the copy's moves taken), not where it deleted the
    day; an edit with no words of its own takes the copy's, its look kept.
    Returns those edits, and the copy's days whose words a day holding words
    lacks, or the note deleted, set aside (_aside_entry)."""
    mine = note.get("overrides") or {}
    overrides = dict(mine)
    deleted = set(note.get("exceptions") or [])
    came = {}
    for day, to in (prev.get("moved") or {}).items():
        came.setdefault(to, day)
    # An edit the copy draws on no day -- off its schedule, or under a date
    # its day left or it deleted -- stays on its date, as the app keys one.
    undrawn = set(off_schedule_days(prev)) | {
        day for day in prev.get("exceptions") or [] if day not in came}
    wanted, gone = [], []
    for key, patch in (prev.get("overrides") or {}).items():
        day = key if key in undrawn else came.get(key, key)
        if day not in deleted:
            at = key if key in undrawn else moved.get(day, day)
            rank = 2 if key in undrawn else 0 if at == day else 1
            wanted.append((not day_has_words(prev, key), rank, at, key, patch))
        elif day_has_words(prev, key):
            gone.append(key)
    # Two of the copy's edits for one date: the one with words goes in, then
    # the one its day is drawn on there; the other is set aside. A day moved
    # onto a day off the schedule wrote one (round eleven).
    taken, aside = set(), []
    # A day the note deleted stays deleted, but the copy's words for it are
    # set aside, not dropped: the phone's older build showed such a day blank,
    # its words in the copy alone (the owner's choice).
    for key in sorted(gone):
        if not _own_words_held(prev, key, note, key):
            aside.append(_aside_entry(prev, key, key))
    for no_words, _rank, at, key, patch in sorted(wanted, key=lambda want: want[:3]):
        look = mine.get(at)
        if at in taken or (look is not None and not no_words and day_has_words(note, at)):
            if not no_words and not _own_words_held(prev, key, dict(note, overrides=overrides), at):
                aside.append(_aside_entry(prev, key, at))
            taken.add(at)
            continue
        taken.add(at)
        if look is None:
            overrides[at] = copy.deepcopy(patch)
        elif not no_words:
            look = look if isinstance(look, dict) else {}
            overrides[at] = dict(copy.deepcopy(patch),
                                 **{key: look[key] for key in _DAY_LOOK if key in look})
    return overrides, aside


def drop_hidden_moves(note):
    """Each move of *note* onto a date its rule now gives -- the day drawn
    nowhere there, a delete there taking it -- dropped; its words stay where
    they showed, on the rule's day there. Words never move on their own (the
    owner's choice). Not off a date whose own day stays deleted or moved
    away; each chain walked once. At every read, save, update and restore of
    the series (ISSUES_LOG: "Round seventeen")."""
    moved = note.get("moved")
    if not moved or not isinstance(moved, dict) or not is_recurring(note):
        return
    deleted = set(note.get("exceptions") or [])
    gives = _rule_days_among(note, list(moved.values()))
    goes = {}
    for start in moved:
        path, on_path, at = [], set(), start
        while at in moved and at not in goes and at not in on_path:
            path.append(at)
            on_path.add(at)
            at = moved[at]
        # The chain's end, a day already settled, or a loop -- none of whose
        # days is ever free to come back to.
        after = False if at in on_path else goes.get(at, True)
        for orig in reversed(path):
            new = moved[orig]
            after = after and new in gives and new not in deleted
            goes[orig] = after
    for orig in [day for day, leaving in goes.items() if leaving]:
        del moved[orig]


def _days_back_from_copy(note):
    """A note that no longer repeats keeps its days' own text in itself, as
    a turn-off here does; a turn-off by the phone, or by this app before the
    final audit, kept them only in the series' copy, which the next copy
    erased. Brought back into the note once, as it is read -- and
    into a note the phone turned back on as it was, which got none of them
    back, the copy's days then spent (spend_series_days)."""
    prev = note.get("_prev")
    # Only the series' own copy: an update's holds days it replaced on
    # purpose, and taken in they made the same backup read as changed.
    if not _series_own_copy(prev):
        return
    if is_recurring(note) and not _repeats_as(note, prev):
        return              # another series now: its days are not these
    if not any(note.get(key) for key in DAY_FIELDS) and days_hold_own_text(prev):
        for key in DAY_FIELDS:
            note[key] = copy.deepcopy(prev.get(key) or NOTE_DEFAULTS[key])
    spend_series_days(note)


def kept_days_fit(note, date_value, recurrence):
    """Whether the days a turned-off *note* kept belong to it turned back on
    with *date_value* and *recurrence*: only when both are as the series had
    them, which its rescue copy holds. True when it kept none, or nothing
    says what the series was: kept, they lose nothing. An old deleted day
    hid a series restarted on it (round five of the final audit)."""
    if is_recurring(note) or not is_recurring({"recurrence": recurrence}):
        return True
    kept = {key: note.get(key) for key in DAY_FIELDS if note.get(key)}
    prev = note.get("_prev")
    if not kept or not (isinstance(prev, dict) and is_recurring(prev)
                        and all(prev.get(key) == value for key, value in kept.items())):
        return True
    return _same_series(prev.get("date"), prev.get("recurrence"), date_value, recurrence)


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
    restarted = ("overrides" not in fields and "recurrence" in fields
                 and not kept_days_fit(note, fresh.get("date"), fresh["recurrence"]))
    if "overrides" not in fields and "recurrence" in fields:
        prev.update(days_to_rescue(note, fresh["recurrence"]))
    # Turned back on another way: the old series' deleted days, which hold
    # nothing, go with this copy instead of hiding the new series' own.
    if restarted and note.get("exceptions"):
        prev["exceptions"] = copy.deepcopy(note["exceptions"])
    # The copy this one replaces may hold another series' days alone: set
    # aside once kept_days_fit has read them -- held by the days
    # a backup brings, too.
    copy_days_set_aside(note, fresh if "overrides" in fields else None)
    note["_prev"] = prev
    for field in fields:
        note[field] = copy.deepcopy(fresh[field])
    # A backup's note sets aside what its own copy kept, as it is read: an
    # Add kept those, an Update dropped them (the audit's twenty-second round).
    if "overrides" in fields and fresh.get("_set_aside"):
        note["_set_aside"] = (note.get("_set_aside") or []) + copy.deepcopy(fresh["_set_aside"])
    if restarted:
        note["exceptions"] = []
    drop_hidden_moves(note)
    note["updated"] = now_stamp()
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
    return all(_copy_field_held(note, prev, key) for key in prev if key not in PREV_TEXT_FIELDS)


def _copy_field_held(note, prev, key):
    """Whether *note* holds *prev*'s field *key* again: a repeat rule by the
    days it gives (_same_series), any other as it is. Compared as stored, a
    rule with its weekday lit was never the same, and the copy never spent
   ."""
    if key == "recurrence":
        day = note.get("date")
        return _same_series(prev.get("date", day), prev[key], day, note.get(key, NOTE_DEFAULTS.get(key)))
    return prev[key] == note.get(key, NOTE_DEFAULTS.get(key))


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


def words_lost(old, new):
    """How many characters of the words in *old* are not in *new*, each word
    counted as often as it appears, with the space it went with: the bars
    rescue_copy_due sets count spaces too. A word moved, or a cell padded
    wider, is not lost; a word with one letter changed is lost whole. A
    list's markers are no words: numbers turned to bullets lost none."""
    gone = Counter(_words(old))
    gone.subtract(_words(new))
    return sum((len(word) + 1) * count for word, count in gone.items() if count > 0)


def _words(text):
    """*text*'s words, each line's list marker left out (strip_list_markers)."""
    return strip_list_markers(text).split()


def _lost(old, new):
    """What a save of *new* over *old* takes away: the smaller of two counts
    that each never come out under it. text_lost read a column added to every
    row, or a list renumbered, as the whole span lost; words_lost reads one
    letter changed in a paragraph with no spaces (Chinese, Japanese) as the
    paragraph lost (2026-10-28, the final audit's fourth round)."""
    return min(text_lost(old, new), words_lost(old, new))


def _measured(text):
    """*text*'s length as words_lost counts it: each word with one space."""
    return sum(len(word) + 1 for word in _words(text))


def rescue_copy_due(old_title, old_body, title, body, old_comments="", comments=""):
    """Whether a save keeps the old text as the rescue copy "↩ Restore
    previous" brings back: emptied; more than 40 characters gone, 30% of it
    or 200; or most of a short note, 70% and 15 characters at least -- for
    the title and body, or for the comments as a text of their own.
    Counted by what is gone. ISSUES_LOG: "The safety
    net that measured the wrong thing"."""
    return (_text_rescue_due(old_title, old_body, title, body)
            or _text_rescue_due("", old_comments, "", comments))


def _text_rescue_due(old_title, old_body, title, body):
    """rescue_copy_due's bars, for one text: a title and a body, or the
    comments alone."""
    old_len = len(old_title) + len(old_body)
    if old_len == 0:
        return False
    if len(title) + len(body) == 0:
        return True
    lost = _lost(old_title, title) + _lost(old_body, body)
    # The shares in the units the loss is counted in: set against a length
    # with a table's padding in it, half a table deleted read as a quarter.
    size = _measured(old_title) + _measured(old_body) or old_len
    if lost > 40 and (lost >= size * 0.3 or lost >= 200):
        return True
    return lost >= 15 and lost >= size * 0.7


def copy_replaced_by_restore(note, prev):
    """What "↩ Restore previous" keeps of the version it replaces, to be
    the rescue copy in its turn: its text, each other field *prev* brings
    back, and a copy of the series' days when the restore ends the repeat
    (days_to_rescue; the note keeps its own). None when it holds nothing
    the restored version lacks: a button offering that would mislead."""
    title = note.get("title") or ""
    body = note.get("body") or ""
    taken = {key: days for key, days in
             (days_to_rescue(note, prev["recurrence"]) if "recurrence" in prev else {}).items()
             if key not in prev}
    # Everything the restore writes over is weighed: the comments too, and
    # the styles of the same words. Comments typed since the copy went to no
    # file, the question saying nothing.
    same_words = body == (prev.get("body") or "")
    lines = len(body.split("\n"))
    styles = (normalize_formatting(note.get("formatting") or []),
              normalize_paragraphs(note.get("paragraphs") or [], lines))
    # Words held in the copy's but not the same: their styles cannot be laid
    # beside the copy's, so any style is weighed as lost -- a part made bold
    # since went to no file.
    styles_kept = (styles == (normalize_formatting(prev.get("formatting") or []),
                              normalize_paragraphs(prev.get("paragraphs") or [], lines))
                   if same_words else not any(styles))
    nothing_lost = (body.strip() in (prev.get("body") or "")
                    and (not title.strip() or title == (prev.get("title") or ""))
                    and (note.get("comments") or "").strip() in (prev.get("comments") or "")
                    and styles_kept
                    and all(_copy_field_held(note, prev, key)
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
    # The arriving note read as a load reads it, its copy's days taken back,
    # then both compared bare; this side, held in memory, is not read again
    # (ISSUES_LOG: "Round seven: a copy taken"; ISSUES_LOG: "Round nine: days").
    fresh = {key: value for key, value in normalize_note(dict(incoming)).items() if key != "_prev"}
    mine = normalize_note({key: value for key, value in note.items() if key != "_prev"})
    # The repeat by the days it gives (_same_series): a start weekday lit or
    # not read as changed, and the Update spent the only earlier version.
    # Another start still changes "date".
    return any(not _same_series(mine["date"], mine[field], mine["date"], fresh[field])
               if field == "recurrence" else mine[field] != fresh[field] for field in fields)


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
    # The first arrival claims an identity; a second comes in as a note of
    # its own, as the phone's Importing.plan has it. Paired twice, one note
    # was updated twice and the person's words kept in no copy (wave 3).
    claimed = set()
    known, fresh = [], []
    for note in incoming:
        if not isinstance(note, dict):
            continue
        uid = _uid_wanted(note.get("uid"))
        if uid is not None and uid in claimed:
            fresh.append({k: v for k, v in note.items() if k != "uid"})
            continue
        if uid is not None:
            claimed.add(uid)
        mine = mine_by_uid.get(uid)
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
    # ...and the day's own list lines, kept even empty: a day saved since
    # keeps its lists' structure, one saved before takes the series' by line
    # (day_paragraphs; the owner's choice).
    if isinstance(patch.get("paragraphs"), list):
        out["paragraphs"] = list_lines(patch["paragraphs"], out.get("body"))
    return out


def day_paragraphs_shown(note, day):
    """The lines' looks *note*'s *day* shows (day_paragraphs): what the day
    view puts on, a day's save compares with, and Make it a note keeps."""
    shown = effective_note(note, day)
    own = ((note.get("overrides") or {}).get(day) or {}).get("paragraphs")
    return day_paragraphs(note.get("paragraphs"), shown.get("body"),
                          shown.get("body") == note.get("body"), own)


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
        clean["updated"] = now_stamp()
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
    pairs = sorted((k, v) for k, v in clean["moved"].items()
                   if isinstance(k, str) and isinstance(v, str))
    # Of two moves onto one date, the one the calendar draws -- its own date
    # the rule's -- is kept: by date alone the read kept a dead one, and a
    # meeting moved under the phone's older build jumped back.
    twins = {new for new, count in Counter(v for _k, v in pairs).items() if count > 1}
    if twins and is_recurring(clean):
        live = _rule_days_among(clean, [k for k, v in pairs if v in twins])
        pairs.sort(key=lambda kv: (kv[1] not in twins or kv[0] not in live, kv[0], kv[1]))
    for orig, new in pairs:
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
    drop_hidden_moves(clean)

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
            # Any length kept: an item saved before the box had a limit is
            # the person's words. Its row draws it cut (checklist_shown).
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

    # A copy's days set aside, kept until the notebook makes them notes of
    # their own (notes_set_aside): written to the file meanwhile, not lost.
    aside = _shaped_aside(note.get("_set_aside"))
    if aside:
        clean["_set_aside"] = aside
    _days_back_from_copy(clean)
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
