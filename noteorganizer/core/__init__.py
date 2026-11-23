"""The data and rules layer — everything that is *not* the user interface.

The one rule that matters in here: **no module in `core` may import
tkinter.** It is what lets the unit suites (`test_recurrence.py`,
`test_data_safety.py` and the rest) test these modules without opening a
window, and what would let a different front end reuse them unchanged.

Each module and its job are listed in `docs/ARCHITECTURE.md`.
"""
