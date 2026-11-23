"""The user interface, as mixin classes over the one ``NoteOrganizer`` object.

Each mixin holds one area's methods, and all of them work on the same
``self``: organisation, not decoupling, a chapter of one book rather than a
book of its own. A method lives in exactly one mixin (Python would pick one
of two silently; `tools/check_class_api.py` checks), and no mixin defines
``__init__``. Why, and where the split stopped: `docs/ARCHITECTURE.md`.
"""
