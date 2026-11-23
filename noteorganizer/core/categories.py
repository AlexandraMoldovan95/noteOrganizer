"""The user's categories: the live name -> colour map, and loading/saving it.

The starting set is in :mod:`.themes`; here are the live
:data:`CATEGORY_COLORS`, its trips to and from ``settings.json``, the
ceilings, the one rule for a name from any door, and ``adopt_categories_of``.
The map is shared by reference, so it is bound once and only changed in
place (``.clear()`` then ``.update()``; ``CATEGORY_COLORS = ...`` would
leave every other module on the old dict, with no error). General always
exists and sorts first: it is where a deleted category's notes go.
"""

from .storage import load_settings, save_settings
from .themes import DEFAULT_CATEGORY_COLORS, PROTECTED_CATEGORY

# The live category map. Starts from the defaults, then gets overlaid with the
# user's saved categories on startup. Referenced everywhere the old
# CATEGORY_COLORS constant was, so the whole app reads from one place.
CATEGORY_COLORS = dict(DEFAULT_CATEGORY_COLORS)

# Ceilings, as the checklist's and the attachments': the map arrives from
# settings.json and any backup, and the sidebar draws every name in full.
# Far above any real notebook -- a ceiling, not a budget.
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
        # Only well-formed name -> #hex entries: settings.json is hand-editable
        # and travels in backups, and "#not-a-colour" raised TclError in a render.
        for name, color in list(saved.items())[:MAX_CATEGORIES]:
            color = sanitize_color(color)
            if not (isinstance(name, str) and name.strip() and color):
                continue
            name = name.strip()
            # Dropped, not shortened: shortened, it no longer matched the
            # notes filed under the full name, which went to General. The doors
            # refuse it first (category_name_refusal): only a hand-edited file gets here.
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
    """Write the current category map back to settings; True when the file
    took it (a refusal reaches the write-failure banner either way)."""
    settings = load_settings()
    settings["categories"] = dict(CATEGORY_COLORS)
    return save_settings(settings)[0]


def category_name_refusal(name, adding=True):
    """Why *name* cannot join the category map, or None when it can: the one
    rule for every door a name comes in by -- Add, Rename, a restored backup
    -- and the rule load_categories applies at the next launch, so nothing
    taken today is dropped tomorrow with its notes sent to General.
    *adding* is False for a rename, which does not change the count;
    duplicate names are each door's own business."""
    if len(name) > MAX_CATEGORY_NAME:
        return (f"A category name can be at most {MAX_CATEGORY_NAME} "
                f"characters long, and this one has {len(name)}.")
    if adding and len(CATEGORY_COLORS) >= MAX_CATEGORIES:
        return (f"You already have {MAX_CATEGORIES} categories, which is "
                "the most the app keeps. Delete or rename one first.")
    return None


def adopt_categories_of(raw_notes, refused=None):
    """Give every category a note (or one day of a series) is filed under a
    place in the live map: the notes are believed over settings.json, which
    a reset, a notes file copied alone or a crash mid-rename leaves without
    them. Back with a palette colour, under every door's ceilings (one refused
    goes into the list *refused*, if given). Called on the raw notes, before
    normalize_note; returns the names added, unsaved."""
    palette = list(DEFAULT_CATEGORY_COLORS.values())
    added = []
    for name in _unknown_names(raw_notes):
        if category_name_refusal(name) is not None:
            if refused is not None and name not in refused:
                refused.append(name)
            continue
        CATEGORY_COLORS[name] = palette[len(CATEGORY_COLORS) % len(palette)]
        added.append(name)
    return added


def _unknown_names(raw_notes):
    """The names *raw_notes* (or one day of a series) are filed under that the live map
    lacks, in order, as adopt_categories_of meets them -- only a name normalize_note
    would match exactly: it compares the stored string as it is, so a padded name
    adopted in stripped form would still miss."""
    for note in raw_notes:
        if not isinstance(note, dict):
            continue
        names = [note.get("category")]
        overrides = note.get("overrides")
        if isinstance(overrides, dict):
            names.extend(patch.get("category") for patch in overrides.values()
                         if isinstance(patch, dict))
        for name in names:
            if isinstance(name, str) and name and name == name.strip() and name not in CATEGORY_COLORS:
                yield name


def would_adopt(raw_notes):
    """Whether adopt_categories_of would add a name for *raw_notes*, the map left as it
    is: the import's question whether a backup brings more asks it of the Trash it
    would take, whose names the merge adopts before it signs."""
    return any(category_name_refusal(name) is None for name in _unknown_names(raw_notes))
