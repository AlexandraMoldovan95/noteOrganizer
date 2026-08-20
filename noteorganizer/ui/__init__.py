"""The user interface, split into mixins.

WHY MIXINS
----------
The whole interface is one object: a single ``NoteOrganizer`` that owns the
note list, the editor, the calendar, Settings and everything else, and whose
methods talk to each other through ``self``. ``self.colors`` alone is read
in 655 places.

That is a genuinely cohesive design, but at ~9,700 lines in one file it is
hard to navigate. So the methods are being grouped into mixin classes, one
per area, and recombined:

    class NoteOrganizer(CalculatorPanelMixin, ..., tk.Tk):

Python builds a single class with all of those methods on it, exactly as
before. Every method still writes ``self.colors``, ``self.notes`` and calls
``self.other_method()`` with no change — which is the point: each move is
cut-and-paste, so the app behaves identically and the tests stay green.

WHAT THIS IS AND IS NOT
-----------------------
This is **organisation, not decoupling**. The mixins are not independent
components: they all still operate on one shared object, and a method in one
freely calls a method in another. Splitting them into genuinely separate
components would mean rewriting those ~982 internal calls, which is a
redesign rather than a move.

So: treat a mixin as a chapter of one book, not a book of its own.

TWO RULES WORTH KEEPING
-----------------------
1. A method belongs in exactly one mixin. If the same name ends up in two,
   Python silently picks whichever class is listed first and the other is
   ignored — with no error. ``tools/check_class_api.py`` guards against this
   by comparing the class's whole method list against a recorded baseline.
2. Mixins do not define ``__init__``. Construction stays in
   ``NoteOrganizer`` itself, so there is one place that builds the app.
"""
