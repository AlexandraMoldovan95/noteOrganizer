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

import os
import re
from datetime import datetime

from .categories import CATEGORY_COLORS
from .formatting import normalize_formatting, normalize_paragraphs
from .tables import with_caret_line
from .recurrence import (
    normalize_recurrence,
    parse_date,
    expand_occurrences,
    OVERRIDABLE_FIELDS,
)

# ---- Note schema + one-time cleanup ----

# The most checklist items one note may carry. Rendering is one Frame +
# Checkbutton + Label + IntVar per item, so an unbounded list is a way to
# kill the app with a pasted share code (see normalize_note).
MAX_CHECKLIST_ITEMS = 1000

# Same class, sibling field: attachments render a row of widgets each and
# arrive through every one of the same untrusted routes (share code,
# imported backup, hand-edited file). Far above any real notebook — the
# point is a ceiling, not a budget. Measured: 200 records paint in ~0.6 s
# on a fast machine (a few seconds on a weak one), and real use tops out
# around tens of files, so 200 protects the app without ever truncating
# a genuine notebook.
MAX_ATTACHMENTS = 200


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


_HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def sanitize_color(value, default=""):
    """*value* if it is a colour Tk can draw, else *default*.

    Colour strings arrive from every untrusted door the app has — a share
    code, an imported backup's settings.json, a hand-edited file — and
    end their journey inside a Tk ``configure(bg=...)``, which raises
    TclError on garbage. Because a note is SAVED before it is first
    drawn, one bad colour used to mean a crash on every launch after:
    the T0-7 brick, on a different field. Only #rgb/#rrggbb pass; the
    app itself never writes anything else."""
    if isinstance(value, str) and _HEX_COLOR.match(value.strip()):
        return value.strip()
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


def normalize_note(note):
    """Guarantee every note has every field, with the right type. Older notes
    were saved before 'comments', 'date', 'color' and 'attachments' existed,
    and code that reads note['title'] directly crashes on those."""
    clean = {}
    # The id is the one field that was never coerced: a string, list or
    # None id survived load intact and then broke every
    # max([n["id"] ...]) + 1 in the app — new note, duplicate, import,
    # restore from trash — with a TypeError.
    raw_id = note.get("id", 0)
    if isinstance(raw_id, bool) or not isinstance(raw_id, int):
        try:
            raw_id = int(str(raw_id).strip())
        except (TypeError, ValueError):
            raw_id = 0
    clean["id"] = raw_id
    # The rescue copy a drastic shrink leaves behind ("↩ Restore
    # previous"). It is not in NOTE_DEFAULTS because it is not part of a
    # note's own shape — but dropping it here meant the button promised
    # something the next launch had already thrown away, even though the
    # text really was on disk. Carried through, shallowly validated.
    prev = note.get("_prev")
    if isinstance(prev, dict):
        clean["_prev"] = {
            "title": prev.get("title") if isinstance(prev.get("title"), str) else "",
            "body": prev.get("body") if isinstance(prev.get("body"), str) else "",
            "comments": prev.get("comments") if isinstance(prev.get("comments"), str) else "",
            "formatting": normalize_formatting(
                prev.get("formatting") if isinstance(prev.get("formatting"), list) else []),
            "paragraphs": normalize_paragraphs(
                prev.get("paragraphs") if isinstance(prev.get("paragraphs"), list) else []),
        }
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

    # The line the editor guarantees under a trailing table, carried into
    # the stored form so the two can never disagree. See with_caret_line.
    clean["body"] = with_caret_line(clean["body"])

    # Bounded by the body's real line count, so an entry left pointing past
    # the end of a note that was later shortened is dropped rather than kept
    # around to indent a line that no longer exists.
    clean["paragraphs"] = normalize_paragraphs(
        clean["paragraphs"], len(clean["body"].split("\n")))
    # An override carries "color" like the base note does -- and like the
    # base note's, it ends inside a Tk configure() when the day is drawn.
    # isinstance(v, str) let "#nope" through, so a single per-day colour
    # from a share code, a backup or a hand-edited file could raise
    # during the startup calendar render: the same make-the-app-
    # unopenable class the note's own colour was closed for, through the
    # one door that fix did not cover. Dropping the bad value (rather
    # than the whole override) keeps the day's text edit intact.
    def _clean_override(patch):
        out = {}
        for k, v in patch.items():
            if k not in OVERRIDABLE_FIELDS or not isinstance(v, str):
                continue
            if k == "color":
                v = sanitize_color(v)
                if not v:
                    continue
            out[k] = v
        return out

    clean["overrides"] = {
        d: _clean_override(patch)
        for d, patch in clean["overrides"].items()
        if isinstance(d, str) and parse_date(d) and isinstance(patch, dict)
    }


    # Tags were removed as a feature — drop any leftover "tags" key from
    # notes saved before this cleanup, so old data doesn't keep carrying it
    # around indefinitely once re-saved.
    clean.pop("tags", None)

    # Checklist: coerce each item to {"text": str, "done": bool}, dropping
    # junk — and cap the count. Every item becomes a Frame, a Checkbutton,
    # a Label and an IntVar when the note is drawn, and nothing upstream
    # limited how many could arrive: a hand-crafted share code carrying
    # 20,000 items is only 60 KB of pasteable text, passes every guard the
    # decoder has, and kills the process on render — permanently, because
    # the note is saved first and re-rendered on the next launch. The cap
    # is far above any real list, and lives here because this is the one
    # choke point every route passes through.
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

    # Attachments: keep each item's stored_as to a bare filename. The app
    # only ever writes bare timestamped names (see add_attachment), so
    # this is a no-op for genuine data — but it flattens any path a
    # crafted share code or hand-edited/imported file tried to smuggle
    # ("../../x", "C:\\...", a UNC root), closing path traversal at the
    # data choke point for EVERY channel, on top of the guards at the
    # delete and open sinks. See ISSUES_LOG.
    attachments = []
    for att in clean.get("attachments", []):
        if not isinstance(att, dict):
            continue
        item = dict(att)
        stored = item.get("stored_as")
        if isinstance(stored, str) and stored:
            # basename flattens smuggled paths; the rstrip removes
            # trailing dots/spaces, which Windows itself strips when
            # opening a file — so "invoice.lnk. " names invoice.lnk on
            # disk while reading as extension-less to the warn-before-
            # opening gate. Normalised here, the name the gate inspects
            # and the file the OS opens can never disagree.
            stored = os.path.basename(stored.replace("\\", "/")).rstrip(". ")
            item["stored_as"] = stored
        else:
            stored = ""
        # A record without usable names aborted load_note halfway (a
        # KeyError mid-render), leaving the editor holding the PREVIOUS
        # note's checklist — which the next save then wrote onto this
        # one. Guarantee both names are strings here, at the choke point,
        # and drop a record that names no file at all.
        display = item.get("filename")
        if not isinstance(display, str) or not display:
            display = stored
        if not stored and not display:
            continue
        item["filename"] = display
        if not isinstance(item.get("stored_as"), str) or not item["stored_as"]:
            item["stored_as"] = display
        attachments.append(item)
        if len(attachments) >= MAX_ATTACHMENTS:
            # Same class as the checklist cap above: an unbounded list a
            # share code can inflate for free, met by a renderer that
            # rebuilds a row per entry.
            break
    clean["attachments"] = attachments

    clean["formatting"] = normalize_formatting(clean.get("formatting"))

    # A colour the app can't draw must not survive to the render: the
    # note is saved before it is first drawn, so garbage here used to be
    # a crash on every subsequent launch.
    clean["color"] = sanitize_color(clean.get("color"))

    return clean


def reading_time(word_count, wpm=200):
    """Roughly how long this many words takes to read, as a phrase.

    200 words a minute is the slow end of the usual adult silent-reading
    range, and that is the end worth picking: a reader who finishes sooner
    than promised has lost nothing, while one who runs over was told the
    note was shorter than it is.

    Returns "" for an empty note, so the caller can show nothing at all
    rather than "0 minutes".
    """
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
    """A note with no content at all is a stray '+ New Note' click.

    "Content" must mean exactly what the editor means by it, or the
    one-time cleanup deletes notes the app itself let you create: a
    checklist counts (``save_current_note`` and ``_autosave_now`` both
    treat a checklist as real content and will happily save a note that
    is nothing else), and so does a recurrence rule — a repeating
    reminder whose whole point is its schedule has no body to speak of.
    Leaving the checklist out of this test cost a real user their
    untitled shopping list; the product review found it.
    """
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
    """Any JSON-ish value as something hashable and comparable.

    Defensive about shapes throughout, because the stale-copy purge feeds
    content_signature raw dicts parsed straight off disk, before any
    normalization has run: an exception raised while building a signature
    would abort a startup."""
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
    """A repeat rule as a hashable tuple — SEMANTICS, not representation.

    The raw form and the normalized form of the same rule must sign
    identically: a no-repeat note stores ``{}`` when hand-written and a
    fully-defaulted dict after normalize_recurrence, and signing those
    differently made every consumer see two different notes — the purge
    stopped recognising covered folders, and the duplicate scan stopped
    recognising true duplicates, the moment one side of the comparison
    had been normalized and the other had not."""
    if not isinstance(recurrence, dict):
        return ()
    normalized = normalize_recurrence(recurrence)
    if not normalized.get("freq"):
        return ()
    return tuple(sorted(
        (k, str(v)) for k, v in normalized.items() if k != "freq"
    )) + (str(normalized["freq"]),)


def content_signature(note, strict=False):
    """THE identity of a note's content — one definition, every consumer.

    Two other modules ask "is this the same note?" with life-or-death
    stakes: clean_notes below collapses duplicates at startup, and
    core/paths.py's stale-copy purge uses it to authorise deleting a whole
    leftover notebook folder from disk. Each used to carry its own
    hand-rolled field tuple, and the two drifted: when the checklist
    joined this one, the purge's copy still judged notes by
    (title, body, comments, category, date) alone, so a legacy folder
    whose notes differed from the local ones ONLY by their checklists
    still read as "fully covered" and was deleted — no Trash, no undo.
    A field list that exists twice WILL fall out of step; this function
    is the fix at the root of that class.

    'id' and 'updated' are deliberately excluded — those differ on
    copies. Defensive about shapes throughout, because the purge feeds it
    raw dicts parsed straight from disk, before any normalization."""
    def _text(value):
        return value.strip() if isinstance(value, str) else ""
    signature = (
        _text(note.get("title")),
        _text(note.get("body")),
        _text(note.get("comments")),
        str(note.get("category") or ""),
        str(note.get("date") or ""),
        _checklist_signature(note.get("checklist")),
        _attachment_signature(note.get("attachments")),
        _recurrence_signature(note.get("recurrence")),
    )
    if not strict:
        return signature
    # The STRICT tail, for the one caller whose wrong answer is
    # unrecoverable. Styling, layout, per-day edits and skipped dates are
    # all real work a person did, and none of them show up above -- so a
    # leftover notebook whose notes differ from the local ones ONLY in
    # those was judged "already covered" and deleted outright, while the
    # startup message said "nothing was deleted unless every note and
    # attachment in it already existed".
    #
    # They stay out of the DEFAULT answer on purpose: the startup
    # duplicate collapse is about two notes a person would call the same
    # note, and a stray bold word does not make a duplicate into a
    # different note. One definition, one explicit axis of strictness,
    # both halves written down -- rather than two field lists drifting
    # apart again.
    return signature + (
        _stable(note.get("formatting")),
        _stable(note.get("paragraphs")),
        _stable(note.get("overrides")),
        _stable(note.get("exceptions")),
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
