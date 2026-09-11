"""Finding notes that are effectively the same note.

WHAT THIS MODULE IS FOR
-----------------------
Duplicates appear easily - importing a backup twice, or using "Duplicate"
and then editing neither copy. This module decides what counts as a
duplicate so Settings can offer to clean them up.

HOW "THE SAME" IS DECIDED
-------------------------
:func:`_dup_key` builds a comparison key from title, body, comments and
category — after two deliberate normalisations — plus the checklist and
the repeat rule, compared exactly:

* :func:`_strip_copy_suffix` removes any number of trailing ``" (copy)"``
  markers, so a note and its duplicate still match even though the app
  renamed one of them.
* :func:`_normalize_ws` collapses runs of whitespace and trims, so notes
  differing only by a stray blank line or trailing space still match.
* The checklist and recurrence join the key un-fuzzed, because cleanup
  does not merge them: whichever copy is dropped takes its checklist and
  its series with it, so notes that differ there must never group.

Date, colour, attachments and pinned state are ignored on purpose. Two
notes with identical text are the same note to a person even if one is
pinned — and attachments are safe to ignore because the cleanup hands
the kept note the group's combined files.

(The signature helpers are imported inside :func:`_dup_key`, not at module
top: storage imports this module while model is still half initialised —
model → categories → storage → here — so a top-level import of model
closes that loop and crashes the package.)

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
    """The signature used to decide whether two notes are 'the same' —
    text compared case/whitespace-insensitively, ignoring a trailing
    ' (copy)' in the title. Shared by duplicate-group detection and by
    the import flow's duplicate check, so both agree on what counts as a
    match.

    The checklist and the repeat rule are part of the key: neither is
    merged when a duplicate group is cleaned up (only attachments are),
    so treating two notes that differ there as 'the same' silently
    destroyed whichever copy the cleanup dropped — and on the import
    routes it skipped the incoming note outright, with no user in the
    loop at all. Attachments stay OUT of the key on purpose: the cleanup
    gives the kept note the group's combined attachments, so differing
    files are preserved, not lost. Date stays out too — a copy carrying
    a different date is still, to a person, the same note twice."""
    from .model import _checklist_signature, _recurrence_signature
    return (
        _normalize_ws(_strip_copy_suffix(note.get("title") or "")).lower(),
        _normalize_ws(note.get("body") or "").lower(),
        _normalize_ws(note.get("comments") or "").lower(),
        note.get("category") or "",
        _checklist_signature(note.get("checklist")),
        _recurrence_signature(note.get("recurrence")),
    )


def find_duplicate_groups(notes):
    """Group notes that are the same in title, body, comments, category,
    checklist and repeat rule. Text matching ignores case and normalizes
    whitespace, and a trailing ' (copy)' in the title is ignored; the
    checklist and recurrence compare exactly, because cleanup does not
    merge them. Date, attachments, color and IDs are IGNORED — attachments
    safely so: when the user cleans up, the kept copy inherits the group's
    combined attachments so nothing is lost."""
    groups = {}
    for n in notes:
        groups.setdefault(_dup_key(n), []).append(n)
    return [g for g in groups.values() if len(g) > 1]
