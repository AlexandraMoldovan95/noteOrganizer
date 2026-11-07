"""Finding notes that are effectively the same note -- a backup imported
twice, a Duplicate never edited -- for Settings to offer to clean up.

:func:`_dup_key` compares title, body, comments and category with case,
spacing and a trailing " (copy)" set aside, and the checklist, the repeat
rule and a series' own days exactly, as the cleanup merges none of them.
Date, colour, pinning and attachments are left out on purpose. Grouping by
key in a dict keeps it linear in the number of notes. The model's helpers
are imported inside :func:`_dup_key`: at the top, model -> categories ->
storage -> here closed an import loop. The walk is in docs/CODE_TOUR.md.
"""

# What _dup_key compares, as every text about duplicates says it: three of
# five copies written by hand missed the checklist and the repeat rule.
SAME_AS = ("same title, text, comments, category, checklist, repeat rule "
           "and a series' own days")


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
    """The signature deciding whether two notes are 'the same', shared by
    the duplicate groups and the import's check so both agree. The
    checklist, the repeat rule and a series' own days are in it, as no
    cleanup merges them -- left out, the dropped copy took them along.
    Attachments stay out (the cleanup gives the kept note the group's
    files, up to the cap); a date does too."""
    from .model import _checklist_signature, _recurrence_signature, _stable
    exceptions, overrides, moved = (note.get("exceptions"), note.get("overrides"),
                                    note.get("moved"))
    return (
        _normalize_ws(_strip_copy_suffix(note.get("title") or "")).lower(),
        _normalize_ws(note.get("body") or "").lower(),
        _normalize_ws(note.get("comments") or "").lower(),
        note.get("category") or "",
        _checklist_signature(note.get("checklist")),
        _recurrence_signature(note.get("recurrence")),
        # The days a series keeps of its own: a copy holding a deleted, an
        # edited or a moved day grouped with one that did not, and the
        # cleanup could drop it.
        (tuple(sorted(str(d) for d in exceptions)) if isinstance(exceptions, list) else (),
         _stable(overrides if isinstance(overrides, dict) else {}),
         _stable(moved if isinstance(moved, dict) else {})),
    )


def find_duplicate_groups(notes):
    """Group notes the same by :func:`_dup_key` (SAME_AS says it in words):
    only groups of more than one. Date, attachments, colour and ids are
    ignored -- the kept copy inherits the group's files, up to the cap,
    and the rest stay with their copies in the Trash."""
    groups = {}
    for n in notes:
        groups.setdefault(_dup_key(n), []).append(n)
    return [g for g in groups.values() if len(g) > 1]
