"""The data and rules layer — everything that is *not* the user interface.

The one rule that matters in here: **no module in `core` may import
tkinter.** That is what lets these modules be tested without opening a
window (see `test_calculator.py`, `test_recurrence.py`,
`test_data_safety.py`, which all run headless), and what would let a
different front end reuse them unchanged.

Modules, as they get moved across from `note_organizer.py`:

* ``calculator`` — evaluates the in-note calculator's expressions.
* ``recurrence`` — the repeat rules, and which dates a note lands on.

Still to come: paths and migrations, the note model, storage, sharing,
and themes.
"""
