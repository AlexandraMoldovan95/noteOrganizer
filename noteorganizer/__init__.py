"""Note Organizer — the application package.

This package is being introduced gradually. Historically the whole app
lived in a single file, `note_organizer.py`, at the project root; code is
being moved in here one module at a time, and `note_organizer.py` remains
the entry point people actually run:

    py note_organizer.py

Two sub-packages are planned:

* ``noteorganizer.core`` — the data and rules layer. Reads and writes the
  JSON files, validates notes, works out recurring dates, evaluates
  calculator expressions. **Nothing in here imports tkinter**, so it can
  be tested without opening a window, and could be reused by a different
  front end one day.
* ``noteorganizer.ui`` — everything the user actually sees. Not created
  yet; the interface still lives in `note_organizer.py`.

If you are reading the code to learn it, start with `docs/CODE_TOUR.md`,
which walks through the modules in a sensible order and explains what
each one is doing and why.
"""
