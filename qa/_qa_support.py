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
    The app asks the desktop two questions, and shares one thing with it;
    a test must not hear the answers of whoever is using the machine while
    it runs, nor share anything with them.

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

    The clipboard: a stand-in kept in this process (``CLIPBOARD``) for
    every app the script builds -- Tcl's ``clipboard`` command, Tk's
    CLIPBOARD selection (which Text's and Entry's own paste read), and,
    on Windows, the app's own clipboard module. The machine's clipboard is
    shared with every program on it: one holding it open for an instant
    made a paste read nothing, and qa1's copy-and-paste check went red
    three times on a developer machine while Linux stayed green. Waiting
    until one read succeeded only moved the race to the paste's own read.
    And a run wrote over the owner's clipboard while she worked. Off
    Windows the app's module already reads nothing and writes nothing, so
    it is left as it is: the app's fallback to Tk is what runs there.

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

``waiting_timers(app, name)``
    The Tcl timers waiting to run a callback called *name*, asked of Tcl
    rather than of the job attribute the app keeps. The attribute answers
    only for the timer it tracks: a job set to None instead of cancelled
    left its timer scheduled with nothing tracking it, and the autosave's
    did that in a relay through a whole qa1 run.
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
    whoever is using the machine, and give every app the script builds a
    clipboard of the script's own. See the module docstring."""
    cls = NO.NoteOrganizer
    cls._foreground_is_ours = lambda self: True
    real = getattr(cls, "_pointer_button_held", None)
    if real is not None and not hasattr(cls, "_desktop_pointer_button_held"):
        cls._desktop_pointer_button_held = real
    cls._pointer_button_held = lambda self: False
    if not getattr(cls, "_qa_keeps_the_clipboard", False):
        built = cls.__init__

        def __init__(self, *args, **kwargs):
            built(self, *args, **kwargs)
            _keep_the_clipboard(self)

        cls.__init__ = __init__
        cls._qa_keeps_the_clipboard = True
    if sys.platform == "win32":
        module = NO.clipboard
        module.read_text = lambda: CLIPBOARD["text"]
        module.read_html = lambda: CLIPBOARD["html"]
        module.write = _write_clipboard


# The clipboard every app the script builds shares, as apps on one machine
# share the machine's: None until something is put there. "tk" says whether
# Tk last claimed it (see _clipboard_command).
CLIPBOARD = {"text": None, "html": None, "tk": False}


def _write_clipboard(text, html=None):
    """The app's clipboard.write, on Windows: plain text and, when given,
    the HTML beside it, as the machine's clipboard holds both."""
    CLIPBOARD.update(text=text, html=html, tk=False)
    return True


def _clipboard_command(*args):
    """Tcl's ``clipboard``: clear, append and get, any options (-displayof,
    -format, -type, --) read past. As Tk's own: an append claims the
    clipboard, clearing it first when another writer held it, and replaces
    every format, so the HTML goes; an empty clipboard refuses a get."""
    args = [str(a) for a in args]
    if args and args[0] == "clear":
        CLIPBOARD.update(text="", html=None, tk=True)
    elif args and args[0] == "append":
        held = CLIPBOARD["text"] if CLIPBOARD["tk"] else ""
        CLIPBOARD.update(text=(held or "") + args[-1], html=None, tk=True)
    elif args and args[0] == "get":
        return _clipboard_selection()
    return ""


def _clipboard_selection():
    if CLIPBOARD["text"] is None:
        raise tk.TclError("CLIPBOARD selection doesn't exist")
    return CLIPBOARD["text"]


def _keep_the_clipboard(app):
    """Put the stand-in in place of the machine's clipboard for *app*'s
    interpreter. Tk's Text and Entry paste through ::tk::GetSelection, so
    only its CLIPBOARD answer is replaced; PRIMARY stays Tk's own."""
    tcl = app.tk
    tcl.eval("rename clipboard ::_qa_machine_clipboard")
    tcl.createcommand("clipboard", _clipboard_command)
    tcl.eval("rename ::tk::GetSelection ::tk::_qa_machine_GetSelection")
    tcl.createcommand("::qa_clipboard_selection", _clipboard_selection)
    tcl.eval("proc ::tk::GetSelection {w {sel PRIMARY}} {"
             " if {$sel eq \"CLIPBOARD\"} {return [::qa_clipboard_selection]};"
             " return [::tk::_qa_machine_GetSelection $w $sel] }")


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


def waiting_timers(app, name):
    """The ids of the Tcl timers waiting to run a callback called *name*,
    tracked or not. Tkinter names a timer's command after its callback."""
    waiting = []
    for job in app.tk.splitlist(app.tk.call("after", "info")):
        try:
            script = app.tk.splitlist(app.tk.call("after", "info", job))[0]
        except tk.TclError:
            continue
        if str(script).endswith(name):
            waiting.append(str(job))
    return waiting
