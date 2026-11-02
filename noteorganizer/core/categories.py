"""The user's categories: the live map, and loading/saving it.

WHAT THIS MODULE IS FOR
-----------------------
Categories are name -> colour pairs the user can add, rename, recolour
and delete. The immutable starting set lives in :mod:`.themes`; what is
here is the *live* map, the two functions that move it to and from
``settings.json``, the ceilings (MAX_CATEGORIES, MAX_CATEGORY_NAME), the
one rule for a name from any door (``category_name_refusal``), and
``adopt_categories_of``, which believes the notes over the settings.

WHY CATEGORY_COLORS IS A MODULE-LEVEL DICT
------------------------------------------
:data:`CATEGORY_COLORS` is shared mutable state - the UI adds, renames
and removes entries directly, and the note model reads it to decide
whether a note's category still exists.

It is safe to share this way only because of one rule: **the name is
bound exactly once, and every change after that mutates the dict in
place** (``.clear()``, ``.update()``, ``[name] = colour``, ``.pop()``).
``from ... import CATEGORY_COLORS`` copies a *reference*, so every module
ends up pointing at the same dict and sees every change.

Rebinding it - writing ``CATEGORY_COLORS = something`` anywhere - would
silently break that: the module doing the rebinding would get a fresh
dict while everyone else kept the old one, and the two would drift apart
with no error. If this ever needs replacing wholesale, clear it and
update it instead::

    CATEGORY_COLORS.clear()
    CATEGORY_COLORS.update(load_categories())

which is exactly what the app does at startup.

GENERAL IS SPECIAL
------------------
:data:`~noteorganizer.core.themes.PROTECTED_CATEGORY` ("General") always
exists and always sorts first. It is the fallback home for notes whose
category is deleted, so it can never itself be removed - guaranteed here
in :func:`load_categories` rather than trusted to the UI.
"""

from .storage import load_settings, save_settings
from .themes import DEFAULT_CATEGORY_COLORS, PROTECTED_CATEGORY

# The live category map. Starts from the defaults, then gets overlaid with the
# user's saved categories on startup. Referenced everywhere the old
# CATEGORY_COLORS constant was, so the whole app reads from one place.
CATEGORY_COLORS = dict(DEFAULT_CATEGORY_COLORS)

# Ceilings, same class as the checklist and attachment ones: the category
# map arrives from settings.json and from any imported backup, and the
# sidebar builds a widget per entry with the name drawn in full. A
# thousand categories, or one named with 100,000 characters, is a way to
# make the app unopenable through a door that had no limit at all. Far
# above any real notebook -- the point is a ceiling, not a budget.
MAX_CATEGORIES = 200
MAX_CATEGORY_NAME = 80


def load_categories():
    """Read the user's categories from settings, falling back to defaults.
    Guarantees General exists and stays first."""
    # Lazy import: model itself imports this module (for the live map),
    # so a top-level import of model from here would close a cycle while
    # model is still half initialised.
    from .model import sanitize_color
    saved = load_settings().get("categories")
    result = {}
    if isinstance(saved, dict) and saved:
        # Keep only well-formed name -> #hex entries. startswith('#') was
        # the old test, and it waved through "#not-a-colour", which then
        # raised TclError inside whatever render touched that category —
        # settings.json is hand-editable and travels inside backups, so
        # this is an untrusted door like any other.
        for name, color in list(saved.items())[:MAX_CATEGORIES]:
            color = sanitize_color(color)
            if not (isinstance(name, str) and name.strip() and color):
                continue
            name = name.strip()
            # A COUNT can be capped by truncating the list; a NAME cannot
            # be capped by truncating the name. The first version did
            # exactly that, and a category whose name was over the limit
            # came back shortened on the next launch -- so every note
            # filed under the full name no longer matched a category that
            # existed, and normalize_note re-filed them all to General.
            # A pathological name is dropped instead. That is NOT loud --
            # an earlier comment here said it was, and the notes under it
            # still went to General in silence -- which is why the doors
            # a name comes in by now refuse it up front
            # (category_name_refusal), so only a hand-edited file can
            # reach this line at all.
            if len(name) > MAX_CATEGORY_NAME:
                continue
            result[name] = color
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


def category_name_refusal(name, adding=True):
    """Why *name* cannot join the category map, or None when it can.

    The one rule for every door a category name comes in by -- Add,
    Rename and a restored backup -- and it is the rule load_categories
    applies on the next launch. The doors used to take anything, and the
    loader then dropped what it would not keep: a category with a long,
    descriptive name worked all day, and the next morning it was gone and
    every note filed under it was in General, for good after the first
    save. The 201st category went the same way.

    *adding* is False for a rename, which does not change the count.
    Duplicate names are not this function's business: each door answers
    those its own way (Add and Rename refuse, a backup keeps the local
    colour).
    """
    if len(name) > MAX_CATEGORY_NAME:
        return (f"A category name can be at most {MAX_CATEGORY_NAME} "
                f"characters long, and this one has {len(name)}.")
    if adding and len(CATEGORY_COLORS) >= MAX_CATEGORIES:
        return (f"You already have {MAX_CATEGORIES} categories, which is "
                "the most the app keeps. Delete or rename one first.")
    return None


def adopt_categories_of(raw_notes):
    """Give every category a note is filed under a place in the live map.

    A note stores only its category's NAME; which names exist, and their
    colours, live in settings.json. When the two files disagree,
    normalize_note re-files the note to General and the next save makes
    that permanent -- and they disagree more easily than it looks:
    deleting settings.json to reset the preferences, copying only
    notes_data.json to a new PC, a crash between a rename's two writes.
    Each of those used to empty all of the user's filing into General
    without a word.

    So the notes are believed. A name a note -- or one day of a repeating
    note -- is filed under comes back with a colour from the default
    palette, under the same ceilings every door has. Called on the raw
    notes, before normalize_note sees them. Returns the names it added;
    saving them is the caller's call.
    """
    palette = list(DEFAULT_CATEGORY_COLORS.values())
    added = []
    for note in raw_notes:
        if not isinstance(note, dict):
            continue
        names = [note.get("category")]
        overrides = note.get("overrides")
        if isinstance(overrides, dict):
            names.extend(patch.get("category") for patch in overrides.values()
                         if isinstance(patch, dict))
        for name in names:
            # Only a name normalize_note would match exactly: it compares
            # the stored string as it is, so a padded name adopted here in
            # stripped form would still miss.
            if (not isinstance(name, str) or not name
                    or name != name.strip() or name in CATEGORY_COLORS):
                continue
            if category_name_refusal(name) is not None:
                continue
            CATEGORY_COLORS[name] = palette[len(CATEGORY_COLORS) % len(palette)]
            added.append(name)
    return added
