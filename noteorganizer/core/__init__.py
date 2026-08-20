"""The data and rules layer — everything that is *not* the user interface.

The one rule that matters in here: **no module in `core` may import
tkinter.** That is what lets these modules be tested without opening a
window (see `test_calculator.py`, `test_recurrence.py`,
`test_data_safety.py`, which all run headless), and what would let a
different front end reuse them unchanged.

Modules, as they get moved across from `note_organizer.py`:

* ``calculator`` — evaluates the in-note calculator's expressions.
* ``recurrence`` — the repeat rules, and which dates a note lands on.
* ``themes`` — colour palettes and the fixed layout numbers. Pure data.
* ``formatting`` — how rich-text spans are stored on a note.
* ``sharing`` — share codes, and the guards that make importing them safe.
* ``duplicates`` — deciding when two notes are really the same note.
* ``paths`` — where data lives, migrations, and the cleanup that must
  never delete the wrong thing. Importing it does nothing on its own;
  ``paths.configure(app_dir)`` fills in the individual file locations.
* ``storage`` — reading and writing settings, templates and trash, plus
  the pre-flight backup of the notes file.

Still to come: the note model and the live category map, which are
entangled with each other (``normalize_note`` consults
``CATEGORY_COLORS``), and the change that makes migrations run on an
explicit call rather than on import.
"""
