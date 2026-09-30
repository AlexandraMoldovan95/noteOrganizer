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

The rules that close it
-----------------------
``pin_the_desktop(NO)`` (also still spelled ``pin_popup_visibility``)
    The app asks the desktop two questions, and a test must not hear the
    answers of whoever is using the machine while it runs.

    Who owns the OS foreground: a test process cannot own it, so popup
    visibility must not depend on it.

    Whether the mouse's primary button is down: the window's resize
    freeze asks Windows, anywhere on the desktop, and lays nothing out
    while it is. A click held in another program at the wrong moment left
    the travel story's app with its note list still unlaid -- one pixel
    tall, never mapped -- so its clicks on a card were dropped, and the
    story reported a share code "still on screen" after a switch that had
    never happened. Pinned to "not held"; qa9 answers it for the app where
    a check is about the freeze, and asks the real question through
    ``_desktop_pointer_button_held``.

    Patches the class, not an instance, so every app the script builds —
    including ones built later — is deterministic, and a new qa script
    needs one line rather than remembering to repeat it. The popup
    hide/restore behaviour keeps its real coverage: qa1 drives
    ``_popup_watch_step()`` directly with both answers stubbed on the
    instance, which shadows this and asserts both outcomes.

``fire(widget, sequence)``
    Asks for ``winfo_id()`` first. That is not a query — it calls Tk's
    ``Tk_MakeWindowExist``, so the native window is created on the spot and
    the event has somewhere to land. The dropped event is *eliminated*
    rather than detected: measured directly, a never-mapped popup child
    receives the click after ``winfo_id()`` and drops it without.

    ``<Button-1>`` was only the first caught case, not the whole class: Tk
    delivers EVERY generated pointer event — press, release,
    ``<B1-Motion>``, ``<MouseWheel>``, ``<Enter>``/``<Leave>`` — to the
    window named in the event, so all of them share the same
    no-window/no-delivery/no-error failure. ``fire`` is the one door for
    all of them. A ``<<virtual>>`` event is window-delivered too (qa9
    leans on exactly that to refresh previews without holding focus) and
    may pass through ``fire`` when a check wants the guard.

    Keyboard events are the deliberate exception: Tk hands a generated
    key event to whatever holds the FOCUS, wherever it was aimed, so
    ``winfo_id()`` on the target repairs nothing and would only dress a
    focus problem up as a solved one. ``fire`` refuses them loudly; a key
    event stays on raw ``event_generate`` behind the
    ``take_focus``/``focus_settles_on`` discipline (see qa/README.md).

``click(widget)``
    The ``<Button-1>`` shorthand for ``fire`` — the original helper, kept
    as the everyday spelling of the everyday gesture.

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

``hermetic_seed()``
    The first line of every qa script, before ``import note_organizer``:
    gives the script a data folder of its own, or refuses to run. It lives
    here, once, because it was nine identical copies -- the one state a
    copied safety rule does not stay in.
"""

import io
import json
import os
import re
import sys
import tkinter as tk

# Set by tools/run_tests.py and by the CI workflow for the scripts they
# start, each in a throwaway folder. Nothing else sets it.
SCRATCH_MARKER = "NOTEORG_SCRATCH"


def hermetic_seed():
    """Give this script a data folder of its own -- or refuse to run.

    Called first, BEFORE ``import note_organizer``: the module resolves
    its data folder and runs the data MIGRATIONS at import time, so by the
    first line of test code the adoption has already happened. An empty
    folder invites run_migrations to adopt whatever real notebook
    %APPDATA% holds, and real notes then leak into every scenario -- the
    checks start flaking whenever the owner's data changes. Seeding an
    empty notebook plus the reclaim marker closes both migration doors
    before the app is even constructed.

    It refuses, and fails closed:

    * outside a scratch run. A script started by hand, from whatever
      folder the terminal happened to be in, stops here before it wipes
      anything -- the way three real notebooks were lost.
    * beside a notes_data.json that holds notes, or that it cannot read.
      The nine copies this replaced read an unreadable notebook as EMPTY
      and overwrote it with ``[]`` -- and an unreadable notebook is
      exactly the one the app itself could still have rescued. They also
      overwrote settings.json unconditionally; now nothing is written
      until every check has passed.
    """
    if os.environ.get(SCRATCH_MARKER) != "1":
        sys.exit(
            "REFUSING to run: this script wipes the data files in its "
            "working folder, and nothing says this folder is a throwaway "
            "copy. Run it through tools/run_tests.py, or set %s=1 yourself "
            "in a scratch folder outside the project (see CLAUDE.md, "
            "'QA testing safety')." % SCRATCH_MARKER)
    if os.path.exists("notes_data.json"):
        try:
            with io.open("notes_data.json", encoding="utf-8") as fh:
                held = json.load(fh)
        except (OSError, ValueError) as exc:
            sys.exit(
                "REFUSING to run: notes_data.json here cannot be read (%s). "
                "It may be a real notebook the app could still rescue; this "
                "script would overwrite it." % exc)
        if not isinstance(held, list) or held:
            sys.exit(
                "REFUSING to run: notes_data.json here holds real notes. "
                "Copy this script to a scratch folder instead.")
    with io.open("notes_data.json", "w", encoding="utf-8") as fh:
        fh.write("[]")
    with io.open("settings.json", "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"reclaimed_from_appdata": True}))


class EventNotDelivered(AssertionError):
    """An event could not be delivered, so the check below it means nothing."""


# The original name, from when click() was this module's only door; kept so
# older tracebacks and anything that names it stay true.
ClickNotDelivered = EventNotDelivered


def pin_the_desktop(NO):
    """Make the app's two questions about the desktop -- who owns the
    foreground, whether the mouse button is down -- answer the same way
    whoever is using the machine. See the module docstring."""
    cls = NO.NoteOrganizer
    cls._foreground_is_ours = lambda self: True
    real = getattr(cls, "_pointer_button_held", None)
    if real is not None and not hasattr(cls, "_desktop_pointer_button_held"):
        cls._desktop_pointer_button_held = real
    cls._pointer_button_held = lambda self: False


# The original name, from when the foreground was the only answer pinned;
# kept so every script that calls it, and anything that names it, stays true.
pin_popup_visibility = pin_the_desktop


# Pointer events, with any modifier prefixes (<Double-Button-1>,
# <B1-Motion>, <Shift-ButtonRelease-1>, ...), or a <<virtual>> event —
# everything Tk delivers to the window named in the event. Keyboard
# sequences deliberately do not match: Tk delivers those to the focus
# window instead, which fire() cannot and must not paper over.
_WINDOW_DELIVERED = re.compile(
    r"(?:<(?:[A-Za-z0-9_]+-)*"
    r"(?:Button(?:Press|Release)?|Motion|MouseWheel|Enter|Leave)"
    r"(?:-[1-5])?>"
    r"|<<[^<>]+>>)$")


def fire(widget, sequence, **kwargs):
    """Generate a pointer (or ``<<virtual>>``) *sequence* on *widget*,
    guaranteeing it has a window to land on.

    Extra keyword arguments (``x=``, ``y=``, ``delta=``, ``time=``, ...)
    pass straight through to ``event_generate``. Keyboard sequences are
    refused: Tk delivers them to the focus window, not the named one, so
    the window repair below would be a lie for them — use ``take_focus``
    and a raw ``event_generate`` instead.
    """
    if not _WINDOW_DELIVERED.match(sequence):
        raise ValueError(
            "fire() guarantees window delivery, and %r is not a pointer "
            "or <<virtual>> sequence. Keyboard events are refused by "
            "design: Tk delivers them to the FOCUS window no matter where "
            "they were aimed, so winfo_id() on the target repairs nothing "
            "-- use take_focus()/focus_settles_on() with a raw "
            "event_generate (see qa/README.md). A pointer shorthand like "
            "<Double-1> needs its full spelling (<Double-Button-1>)."
            % (sequence,))
    try:
        # Not a query: this creates the native window if it has none, which
        # is the whole fix. Without it Tk throws the event away in silence.
        widget.winfo_id()
    except tk.TclError as exc:
        raise EventNotDelivered(
            "%s has no window to receive %s (destroyed?): %s"
            % (widget, sequence, exc))
    widget.event_generate(sequence, **kwargs)


def click(widget, **kwargs):
    """Generate ``<Button-1>`` on *widget*, guaranteeing it can land.

    Extra keyword arguments (``x=``, ``y=``, ...) pass straight through to
    ``event_generate``.
    """
    fire(widget, "<Button-1>", **kwargs)
