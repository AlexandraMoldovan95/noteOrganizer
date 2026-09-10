"""Shared helpers for driving the app's widgets and popups from the qa suite.

Why this module exists
----------------------
Tk silently DISCARDS a generated ``<Button-1>`` when the target widget has
no native window yet. No error, no warning, no return value: the binding
simply never runs, and the script sails on to assert on state that nothing
was ever asked to change.

A widget gets its native window when it is first mapped — so a freshly
built popup, or one the app has hidden, is exactly the case that swallows
the click. And the app *does* hide popups: they are ``-topmost`` by design
(the app's own focus shuffles must not bury them), so a heartbeat withdraws
them whenever another program holds the Windows foreground, which a test
process never owns — the terminal that launched the run does.

Put together, ``chip.event_generate('<Button-1>')`` was really asking "did
the 300 ms watch tick land before my click?", and answering green or red by
luck. qa2's 3-marker cap check answered it by luck for weeks: measured
mid-run, all five chips still read ``highlightthickness=0`` — not one of
the five clicks had ever been delivered.

The two rules that close it
---------------------------
``pin_popup_visibility(NO)``
    A test process cannot own the OS foreground, so popup visibility must
    not depend on it. Patches the class, not an instance, so every app the
    script builds — including ones built later — is deterministic, and a
    new qa script needs one line rather than remembering to repeat it.
    The hide/restore behaviour keeps its real coverage: qa1 drives
    ``_popup_watch_step()`` directly with both answers stubbed on the
    instance, which shadows this and asserts both outcomes.

``click(widget)``
    Asks for ``winfo_id()`` first. That is not a query — it calls Tk's
    ``Tk_MakeWindowExist``, so the native window is created on the spot and
    the event has somewhere to land. The dropped click is *eliminated*
    rather than detected: measured directly, a never-mapped popup child
    receives the click after ``winfo_id()`` and drops it without.

Why the obvious predicates were rejected
----------------------------------------
Both ``winfo_ismapped()`` and ``winfo_viewable()`` look like the right
question and are not: a widget scrolled out of a canvas, and a popup that
was mapped and then withdrawn, report 0 for both and still receive the
event. Gating on them refused clicks that would have worked perfectly —
qa6's category swatch lives below the fold of a scrolling settings panel
and was refused on Windows *and* Linux alike. Window existence is the
condition Tk actually cares about, and unlike the other two it can be
satisfied instead of merely waited for.

One thing this deliberately does NOT police: whether a human could have
clicked the widget where it currently sits. Delivery and realism are
different questions, and a check that wants the second asserts it itself
(scroll the row into view, then assert it is viewable).
"""

import tkinter as tk


class ClickNotDelivered(AssertionError):
    """A click could not be delivered, so the check below it means nothing."""


def pin_popup_visibility(NO):
    """Make popup visibility independent of who owns the OS foreground."""
    NO.NoteOrganizer._foreground_is_ours = lambda self: True


def click(widget, **kwargs):
    """Generate ``<Button-1>`` on *widget*, guaranteeing it can land.

    Extra keyword arguments (``x=``, ``y=``, ...) pass straight through to
    ``event_generate``.
    """
    try:
        # Not a query: this creates the native window if it has none, which
        # is the whole fix. Without it Tk throws the event away in silence.
        widget.winfo_id()
    except tk.TclError as exc:
        raise ClickNotDelivered(
            "%s has no window to receive a click (destroyed?): %s"
            % (widget, exc))
    widget.event_generate("<Button-1>", **kwargs)
