"""The user's categories: the live map, and loading/saving it.

WHAT THIS MODULE IS FOR
-----------------------
Categories are name -> colour pairs the user can add, rename, recolour
and delete. The immutable starting set lives in :mod:`.themes`; what is
here is the *live* map plus the two functions that move it to and from
``settings.json``.

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
        for name, color in saved.items():
            color = sanitize_color(color)
            if isinstance(name, str) and name.strip() and color:
                result[name.strip()] = color
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
