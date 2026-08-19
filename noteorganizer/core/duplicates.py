"""Finding notes that are effectively the same note.

WHAT THIS MODULE IS FOR
-----------------------
Duplicates appear easily - importing a backup twice, or using "Duplicate"
and then editing neither copy. This module decides what counts as a
duplicate so Settings can offer to clean them up.

HOW "THE SAME" IS DECIDED
-------------------------
:func:`_dup_key` builds a comparison key from title, body, comments and
category, after two deliberate normalisations:

* :func:`_strip_copy_suffix` removes any number of trailing ``" (copy)"``
  markers, so a note and its duplicate still match even though the app
  renamed one of them.
* :func:`_normalize_ws` collapses runs of whitespace and trims, so notes
  differing only by a stray blank line or trailing space still match.

Everything else - date, colour, attachments, pinned state - is ignored on
purpose. Two notes with identical text are the same note to a person, even
if one of them is pinned.

Grouping is then a dict of key -> list of notes, keeping only groups with
more than one member. Using a dict rather than comparing every note with
every other note keeps this linear in the number of notes instead of
quadratic, which starts to matter at a few thousand notes.
"""

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
