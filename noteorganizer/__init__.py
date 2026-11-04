"""Note Organizer — the application package.

`note_organizer.py` at the project root stays the entry point people run
(``py note_organizer.py``) and the interface's hub; this package holds what
moved out of it:

* ``noteorganizer.core`` — the data and rules, which never import tkinter;
* ``noteorganizer.ui`` — the interface, as mixins over the one app class.

The design is in `docs/ARCHITECTURE.md`; `docs/CODE_TOUR.md` walks the code.
"""
