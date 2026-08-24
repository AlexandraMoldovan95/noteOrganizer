"""The note itself: what a note is, and making sure it stays that way.

WHAT THIS MODULE IS FOR
-----------------------
:data:`NOTE_DEFAULTS` defines every field a note has and what an empty
one looks like. :func:`normalize_note` is the single gate every note
passes through before the rest of the app is allowed to touch it - on
load, on import, on paste from a share code.

WHY normalize_note MATTERS MORE THAN IT LOOKS
---------------------------------------------
Notes come from a JSON file a user can hand-edit, from backups made by
older versions, and from share codes typed in from elsewhere. Any field
might be missing, be the wrong type, or hold something nonsensical.

Rather than defend against that everywhere, the app funnels all of it
through one function that returns a note of known shape - a ``None``
title becomes ``""``, a checklist that is not a list becomes ``[]``, a
category that no longer exists falls back to "General". A single corrupt
entry therefore degrades to a slightly emptier note instead of taking
down the note list.

The same idea appears in :func:`~noteorganizer.core.recurrence.normalize_recurrence`
and :func:`~noteorganizer.core.formatting.normalize_formatting`, which
this delegates to for their parts of the note. **Validate once, at the
edge, then trust the data inwards.**

WHAT "EMPTY" AND "RICHNESS" ARE FOR
-----------------------------------
:func:`note_is_empty` and :func:`note_richness` support cleanup: when
duplicates are merged, richness decides which copy to keep - the one
carrying the most actual content - rather than picking arbitrarily.
:func:`clean_notes` uses both to drop blank notes and de-duplicate on
load, and reports what it did so the app can tell the user.
"""

import re
from datetime import datetime

from .categories import CATEGORY_COLORS
from .formatting import normalize_formatting, normalize_paragraphs
from .recurrence import (
    normalize_recurrence,
    parse_date,
    expand_occurrences,
    OVERRIDABLE_FIELDS,
)

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

    # Bounded by the body's real line count, so an entry left pointing past
    # the end of a note that was later shortened is dropped rather than kept
    # around to indent a line that no longer exists.
    clean["paragraphs"] = normalize_paragraphs(
        clean["paragraphs"], len(clean["body"].split("\n")))
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


# ---- Looking notes up, and moving them between categories ----
#
# These were methods on the app class. None of them drew anything; they read
# and rewrite the notes list, which is what this module is for. Each takes
# the list as its first argument rather than reaching for ``self.notes``.
#
# All three account for per-occurrence overrides. A repeating note can carry
# a patch for one date that sets a different category from the series, so a
# rename that only rewrote ``note["category"]`` would leave those patches
# pointing at a name that no longer exists.

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
    """Rewrite every reference to a category, in base notes and overrides.

    Used both for a real rename and for moving notes out of a category that
    is being deleted -- the operation is the same either way.
    """
    for n in notes:
        if n.get("category") == old_name:
            n["category"] = new_name
        for patch in (n.get("overrides") or {}).values():
            if patch.get("category") == old_name:
                patch["category"] = new_name


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
