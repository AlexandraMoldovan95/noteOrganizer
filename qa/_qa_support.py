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

    The spelling dictionaries: Windows' are this machine's languages, and
    a Linux runner has none, so a check near a misspelling would answer
    differently on each. No dictionary at all here; the spelling checks
    give their app a stand-in that knows exactly which words are wrong.

    The keyboard cannot be pinned: a test app can hold the focus while
    someone types. Every key a keyboard sends is noted instead
    (``REAL_KEYS``) and said when the run ends, so a red that came from
    someone typing names itself rather than reading as a flake.

    A question nobody answers: a check that meets one of the app's own
    modal questions without having stubbed it waits for an answer that
    never comes, and the suite stood there for its whole timeout -- under
    a mutant that left a date out, "Part of this note isn't saved" stopped
    qa5, and the mutant run behind it. A question still waiting after
    ``QUESTION_WAIT_MS`` is answered with its safe button (Escape's
    answer), named on a FAIL line, and the run ends red
    (``_fail_for_unanswered``): one red line instead of a stopped suite.

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
    copied safety rule does not stay in. ``seed_here()`` is its seed, for
    the tools that photograph or measure the app (no scratch marker).

``as_a_guest()``
    The first act of every suite, qa and unit alike (``hermetic_seed``
    calls it): settles the script as tools/guest.py's runners settle. One
    a runner started shares its turn, homes and ceiling; one started by
    hand or by CI takes its own, and refuses without guest.py -- and
    beside an app whose notebook_location.txt names a folder.

``where_the_app_opens(app_dir)``
    The folder the app found at *app_dir* would open its notebook in,
    asked of the app's own resolver (core.paths) as ``initialise()`` asks
    it. The guards looked for a notebook in their own folder while the
    app opened the one notebook_location.txt names: in a checkout, the
    owner's (final audit, round ten).

``waiting_timers(app, name)``
    The Tcl timers waiting to run a callback called *name*, asked of Tcl
    rather than of the job attribute the app keeps. The attribute answers
    only for the timer it tracks: a job set to None instead of cancelled
    left its timer scheduled with nothing tracking it, and the autosave's
    did that in a relay through a whole qa1 run.

``ignore_pointer(widget)``
    Take *widget*'s ``<Motion>`` and ``<Leave>`` bindings away, and return
    the function that gives them back. For a check that opens a hover
    preview by call and then reads it: the preview hides when the pointer
    moves or leaves, and a person's real mouse over the window while the
    suite runs did that to qa2's day preview in two runs of five.

``leaves_nothing_behind(app, redraw, times)``
    Whether calling *redraw* over and over leaves Tcl commands behind for
    good: one batch of *times* calls to absorb what is done only once,
    then two more, each counted with the waiting timers left out. A leak
    adds something in every batch; a window that opens once -- a hover
    preview under a pointer that never moves, a timer's popup -- can only
    fall between two of the three counts, so the smaller growth is the
    one that counts. Four scripts counted this four ways, one of them with
    a timer filter that had stopped filtering.

``photograph(app, path, box=None)`` and ``grab(app, box=None)``
    The one shutter for every tool that photographs the app (the stories,
    doc_screenshots, visual_scenes). A picture copies the SCREEN where the
    window is, so whatever lies over it is saved: an emulator once sat in
    nineteen documentation pictures, and story_look's are committed. The
    box is cut to the window and to the primary screen's work area; before
    and after the copy, points across it are asked which window is on top
    there, and one of another program's means no picture, said rather than
    saved. The window is put on top for the shot and taken off after it.
"""

import atexit
import collections
import io
import json
import os
import re
import sys
import time
import tkinter as tk

# Declares the working folder a throwaway: set by the runners
# (tools/run_tests.py, run_coverage.py, check_guest.py) and by CI for the
# scripts they start, or by hand in a scratch copy (CLAUDE.md).
SCRATCH_MARKER = "NOTEORG_SCRATCH"

_SETTLED = []   # tools/guest.py, once this process has settled


def as_a_guest():
    """Settle this script before it imports or builds the app, as every
    runner does (tools/guest.py): a suite that a settled run started shares
    its turn, homes and memory ceiling, and one started any other way --
    by hand, or by CI -- takes its own. The suites were let off that rule
    because "a runner starts them", and nothing made it so (final audit,
    round nine). guest.py is found beside this file, as every scratch copy
    has it, or in the repository's tools/; without it, the script refuses.

    Settled, it refuses beside an app whose notebook_location.txt names a
    folder: that app opens someone's own notebook, and a copy made to test
    in never carries the file (round ten)."""
    if _SETTLED:
        return _SETTLED[0]
    here = os.path.dirname(os.path.abspath(__file__))
    for folder in (here, os.path.join(os.path.dirname(here), "tools")):
        if os.path.isfile(os.path.join(folder, "guest.py")):
            sys.path.insert(0, folder)
            try:
                import guest
            finally:
                sys.path.remove(folder)
            break
    else:
        sys.exit(
            "REFUSING to run: tools/guest.py is not beside this script. A "
            "suite settles as a guest of this computer before it starts -- "
            "the machine's turn, a memory ceiling, APPDATA of its own -- "
            "and needs it for that. Run it through tools/run_tests.py, or "
            "copy guest.py in beside it (CLAUDE.md, 'QA testing safety').")
    for line in guest.settle():
        print(line, flush=True)
    _SETTLED.append(guest)
    app_dir = _app_dir()
    if app_dir is not None:
        paths = _resolver(app_dir)
        named = paths.chosen_notebook_dir(app_dir)
        if named is not None:
            sys.exit(
                "REFUSING to run: the app this script would start, at %s, keeps "
                "its notebook in the folder its %s names:\n%s\nThat is someone's "
                "own notebook: a copy made to test in never carries the file. Run "
                "it through tools/run_tests.py (CLAUDE.md, 'QA testing safety')."
                % (app_dir, paths.LOCATION_FILE, named))
    return guest


def _app_dir():
    """The folder ``import note_organizer`` would load the app from, found
    without importing it; None when there is none to find."""
    import importlib.util
    try:
        spec = importlib.util.find_spec("note_organizer")
    except (ImportError, ValueError):
        return None
    origin = getattr(spec, "origin", None)
    if not origin or not os.path.isfile(origin):
        return None
    return os.path.dirname(os.path.abspath(origin))


def _resolver(app_dir):
    """The app's own core.paths, as ``import note_organizer`` would find it."""
    try:
        from noteorganizer.core import paths
    except ImportError as exc:
        sys.exit("REFUSING to run: the app's own resolver (noteorganizer.core."
                 "paths) cannot be asked where the app at %s opens its notebook "
                 "(%s)." % (app_dir, exc))
    return paths


def where_the_app_opens(app_dir):
    """(folder, named): the folder the app at *app_dir* opens its notebook
    in, and whether its notebook_location.txt named it -- asked of the app's
    own resolver, as initialise() asks it. A named folder is not probed:
    resolve_data_dir proves a folder writable by writing in it."""
    as_a_guest()
    paths = _resolver(app_dir)
    named = paths.chosen_notebook_dir(app_dir)
    if named is not None:
        return named, True
    return paths.resolve_data_dir(app_dir)[0], False


def _same_folder(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:      # one of them is not there: not the same folder
        return False


def seed_here(app_dir=None):
    """Seed an empty notebook in the working folder, where the app will open
    it -- or refuse. hermetic_seed's guard without its scratch marker, for
    the tools that photograph or measure the app. *app_dir* is where the
    app is, for a check that stands one somewhere; by default, where
    ``import note_organizer`` finds it. The rules: hermetic_seed."""
    as_a_guest()
    here = os.getcwd()
    app_dir = app_dir or _app_dir()
    if app_dir is None:
        sys.exit(
            "REFUSING to run: no note_organizer.py can be found from here, so "
            "where the app would open its notebook cannot be asked. Copy it, "
            "with the noteorganizer/ package, in beside this script.")
    opens, named = where_the_app_opens(app_dir)
    if not _same_folder(opens, here):
        sys.exit(
            "REFUSING to run: this script seeds and rewrites the notebook in "
            "this folder,\n%s\nbut the app it starts, at %s, would open\n%s%s\n"
            "Run it in a scratch copy, from the copy's own folder (CLAUDE.md, "
            "'QA testing safety')." % (here, app_dir, opens,
                                       " (the folder its %s names)"
                                       % _resolver(app_dir).LOCATION_FILE
                                       if named else ""))
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


def hermetic_seed(app_dir=None):
    """Give this script a data folder of its own -- or refuse to run.

    Called first, BEFORE ``import note_organizer`` and so before the app
    is built: building it calls ``initialise()``, which resolves the data
    folder and runs the data MIGRATIONS, so by the first line of test code
    the adoption has already happened. An empty
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
    * unless the folder the app will open is this one, asked of the app's
      own resolver (``where_the_app_opens``). The guard looked for a
      notebook here while the app opened the folder notebook_location.txt
      names -- in the owner's checkout, her own (final audit, round ten).

    Declared a scratch run, it settles as a guest (``as_a_guest``) before
    it writes anything. *app_dir*: see ``seed_here``.
    """
    if os.environ.get(SCRATCH_MARKER) != "1":
        sys.exit(
            "REFUSING to run: this script wipes the data files in its "
            "working folder, and nothing says this folder is a throwaway "
            "copy. Run it through tools/run_tests.py, or set %s=1 yourself "
            "in a scratch folder outside the project, with tools/guest.py "
            "beside it (see CLAUDE.md, 'QA testing safety')." % SCRATCH_MARKER)
    seed_here(app_dir)


class EventNotDelivered(AssertionError):
    """An event could not be delivered, so the check below it means nothing."""


# The original name, from when click() was this module's only door; kept so
# older tracebacks and anything that names it stay true.
ClickNotDelivered = EventNotDelivered


def pin_the_desktop(NO):
    """Make the app's two questions about the desktop -- who owns the
    foreground, whether the mouse button is down -- answer the same way
    whoever is using the machine, give every app the script builds a
    clipboard of the script's own, note every key a keyboard sends it
    (_note_real_keys), and never let one of its questions wait for an
    answer nobody will give (_answer_what_waits). See the module
    docstring."""
    cls = NO.NoteOrganizer
    _answer_what_waits(cls)
    cls._foreground_is_ours = lambda self: True
    # The machine's spelling dictionaries are the desktop's too: an English
    # Windows underlines what a Linux runner never does, so a check that
    # touched a misspelling would take its verdict from the machine. No
    # dictionary here; the spelling checks give an app one of their own
    # (app._spellers_found), whose every word they know.
    cls._spellers_found = []
    # Every app the script builds may take any size a check asks for. Tk caps
    # a window at the size of its screen, and a CI runner's screen is smaller
    # than the windows the checks ask for: a request past it is cut, in silence.
    if not getattr(cls, "_qa_outgrows_the_screen", False):
        made = cls.__init__

        def __init__(self, *args, **kwargs):
            made(self, *args, **kwargs)
            self.maxsize(10000, 10000)

        cls.__init__ = __init__
        cls._qa_outgrows_the_screen = True
    real = getattr(cls, "_pointer_button_held", None)
    if real is not None and not hasattr(cls, "_desktop_pointer_button_held"):
        cls._desktop_pointer_button_held = real
    cls._pointer_button_held = lambda self: False
    if not getattr(cls, "_qa_keeps_the_clipboard", False):
        built = cls.__init__

        def __init__(self, *args, **kwargs):
            built(self, *args, **kwargs)
            _keep_the_clipboard(self)
            _note_real_keys(self)

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


# Keys that came from a keyboard -- whoever is at the machine -- and not from
# the script: a generated key carries time 0, a real one the clock. Nothing
# keeps them out, since the test app can hold the keyboard while someone
# types; so they are noted, and said once the run ends. Twice a check went
# red once in dozens of runs on a developer machine, with the editor changed
# between two reads, and nothing could say whether a key had reached it.
REAL_KEYS = []


def _note_real_keys(app):
    """Note every key event a keyboard sends *app* (REAL_KEYS). Bound on the
    'all' tag beside whatever the app binds there, and never breaking: a key
    a binding before it breaks off goes unseen, so this can only add to what
    a red says, never change what the app does."""
    def note(event, sequence):
        try:
            when = int(event.time)
        except (TypeError, ValueError):
            return
        if when:
            if not REAL_KEYS:
                atexit.register(_say_real_keys)
            REAL_KEYS.append((sequence, str(getattr(event, "keysym", "?"))))
    for sequence in ("<KeyPress>", "<KeyRelease>"):
        app.bind_all(sequence, lambda e, s=sequence: note(e, s), add="+")


def _say_real_keys():
    print("REAL KEYS: %d key event(s) came from the keyboard while this "
          "script ran -- someone typed on this machine, and a red in this "
          "run may be theirs: %s" % (len(REAL_KEYS), REAL_KEYS[:12]),
          flush=True)


# Far longer than any check takes to answer a question it means to answer
# (they do it in milliseconds), and far shorter than the suite's timeout.
QUESTION_WAIT_MS = 20000

# The titles of questions nobody answered, in the order they were asked.
UNANSWERED = []


def _answer_what_waits(cls):
    """Wrap the app's modal question (``_themed_dialog``) so that one still
    waiting after QUESTION_WAIT_MS is answered with its safe button -- the
    first, Escape's answer -- and named on a FAIL line; the run then ends
    red (_fail_for_unanswered). A check that stubs the question on the app
    itself never reaches this: the stub shadows the class."""
    real = cls._themed_dialog
    if getattr(real, "_qa_answers_what_waits", False):
        return

    def _themed_dialog(self, title, message, *args, **kwargs):
        def answer():
            stack = getattr(self, "_asking_dialogs", None) or []
            if not stack:
                return
            if not UNANSWERED:
                atexit.register(_fail_for_unanswered)
            UNANSWERED.append(str(title))
            print("FAIL a question was left waiting, and nobody answered it: "
                  "%r" % (str(title),), flush=True)
            try:
                stack[-1]["buttons"][0].invoke()
            except (tk.TclError, IndexError, KeyError):
                pass

        try:
            job = self.after(QUESTION_WAIT_MS, answer)
        except tk.TclError:
            job = None
        try:
            return real(self, title, message, *args, **kwargs)
        finally:
            if job is not None:
                try:
                    self.after_cancel(job)
                except (tk.TclError, ValueError):
                    pass

    _themed_dialog._qa_answers_what_waits = True
    cls._themed_dialog = _themed_dialog


def _fail_for_unanswered():
    """The run ends red when a question was left waiting: its FAIL line is
    not in the script's own list, so the script's exit code would say
    green. Said with the real keys too, when there were any -- this exits
    before the handler that says them would run."""
    print("UNANSWERED QUESTIONS: %d -- each was answered with its safe "
          "button after %d s, and this run fails: %s"
          % (len(UNANSWERED), QUESTION_WAIT_MS // 1000, UNANSWERED[:8]),
          flush=True)
    if REAL_KEYS:
        _say_real_keys()
    sys.stdout.flush()
    os._exit(1)


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

# Which widget each mouse button was last pressed on, by its path: a release
# may find that its own press destroyed it (fire, below).
_BUTTON = re.compile(r"(ButtonPress|ButtonRelease|Button)-([1-5])>$")
_PRESSED = {}


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
    button = _BUTTON.search(sequence)
    try:
        # Not a query: this creates the native window if it has none, which
        # is the whole fix. Without it Tk throws the event away in silence.
        widget.winfo_id()
    except tk.TclError as exc:
        # The one release with nowhere to land: on the widget its own press
        # destroyed -- a checklist row rebuilt under the pointer. A person's
        # release lands on nothing then, and so does this one; the check
        # after it fails on what it finds. Raised, it killed the script
        # before its footer, and the mutant behind it read as NO-RUN.
        if (button and button.group(1) == "ButtonRelease"
                and _PRESSED.get(button.group(2)) == str(widget)):
            return
        raise EventNotDelivered(
            "%s has no window to receive %s (destroyed?): %s"
            % (widget, sequence, exc))
    widget.event_generate(sequence, **kwargs)
    if button and button.group(1) != "ButtonRelease":
        _PRESSED[button.group(2)] = str(widget)


def click(widget, **kwargs):
    """Generate ``<Button-1>`` on *widget*, guaranteeing it can land.

    Extra keyword arguments (``x=``, ``y=``, ...) pass straight through to
    ``event_generate``.
    """
    fire(widget, "<Button-1>", **kwargs)


_HOLDS_KEYS = (tk.Entry, tk.Text, tk.Button, tk.Checkbutton, tk.Radiobutton,
               tk.Spinbox, tk.Listbox)


def ring_mismatches(top):
    """Bordered frames under *top* that would lose their border colour.

    Tk paints a frame's border in ``highlightbackground`` until the
    keyboard is on anything INSIDE the frame, and then in
    ``highlightcolor`` -- the system grey unless it is set. The find bar's
    accent border was grey the whole time anyone typed in it, which no
    check saw and a photograph did. Returns the frames, by path, whose two
    colours differ and which hold something that can take the keyboard.
    """
    def holds_keys(w):
        return any((isinstance(c, _HOLDS_KEYS)
                    and str(c.cget("takefocus")) != "0") or holds_keys(c)
                   for c in w.winfo_children()
                   if not isinstance(c, tk.Toplevel))

    out = []

    def walk(w):
        for c in w.winfo_children():
            if (isinstance(c, tk.Frame)
                    and int(str(c.cget("highlightthickness")))
                    and str(c.cget("highlightcolor")).lower()
                    != str(c.cget("highlightbackground")).lower()
                    and holds_keys(c)):
                out.append(str(c))
            walk(c)
    walk(top)
    return out


# What a person reads or presses, at the width it asks for. Entries are not
# here: a text box given less than it asks scrolls its text, as it should.
_FIXED = (tk.Button, tk.Label, tk.Checkbutton, tk.Radiobutton, tk.Menubutton)


def out_of_sight(top):
    """The buttons, labels and tick boxes under *top* that are not wholly on
    screen while what holds them is: not drawn at all, cut at the edge of
    what holds them, or given less width than they ask -- all but a label
    that wraps, which asks for its unwrapped width and is given its wrap.
    A box (an Entry) counts as out of sight only when not drawn or cut.

    A packed or gridded row given less than it asks drops what was placed
    last, and says nothing: the colour's swatch, "This day:", a dropdown's
    arrow and a button's words were lost so before a check asked. Each is
    named by its text and class, and what holds it. Pumps nothing: the
    caller waits for the state it was promised (mapping is asynchronous
    under Xvfb)."""
    out = []

    def name(w):
        text = str(w.cget("text"))[:30] if "text" in w.keys() else ""
        return f"{w.winfo_class()} {text!r} in {w.master.winfo_class()}"

    def first_control(w):
        for c in w.winfo_children():
            if isinstance(c, _FIXED):
                return c
            found = None if isinstance(c, tk.Toplevel) else first_control(c)
            if found is not None:
                return found
        return None

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Toplevel):
                continue
            placed = c.winfo_manager() in ("pack", "grid", "place")
            if (placed and w.winfo_ismapped() and not c.winfo_ismapped()
                    and not isinstance(c, _FIXED + (tk.Entry,))):
                # A frame squeezed to nothing takes everything in it along,
                # and nothing in it is drawn to be asked: a Settings row's
                # button was given 1 px of 81 this way.
                held = first_control(c)
                if held is not None:
                    out.append(f"not drawn: {c.winfo_class()} holding " + name(held))
                continue
            if (isinstance(c, _FIXED + (tk.Entry,))
                    and placed and w.winfo_ismapped()):
                wraps = isinstance(c, tk.Label) and int(str(c.cget("wraplength")) or 0) > 0
                if not c.winfo_ismapped():
                    out.append("not drawn: " + name(c))
                elif c.winfo_x() + c.winfo_width() > w.winfo_width() + 1:
                    out.append("cut: " + name(c))
                elif (isinstance(c, _FIXED) and not wraps
                      and c.winfo_width() + 1 < c.winfo_reqwidth()):
                    out.append(f"squeezed {c.winfo_width()} of {c.winfo_reqwidth()}: "
                               + name(c))
            walk(c)
    walk(top)
    return out


def _waiting(app):
    """Each waiting Tcl timer's id and the command it will run."""
    for job in app.tk.splitlist(app.tk.call("after", "info")):
        try:
            script = app.tk.splitlist(app.tk.call("after", "info", job))[0]
        except tk.TclError:
            continue
        yield str(job), str(script)


def ignore_pointer(widget, sequences=("<Motion>", "<Leave>")):
    """Deafen *widget* to the pointer's moves; return what restores them.
    See the module docstring."""
    saved = {seq: widget.bind(seq) for seq in sequences}
    for seq in sequences:
        widget.unbind(seq)

    def restore():
        for seq, script in saved.items():
            if script:
                widget.bind(seq, script)
    return restore


def waiting_timers(app, name):
    """The ids of the Tcl timers waiting to run a callback called *name*,
    tracked or not. Tkinter names a timer's command after its callback."""
    return [job for job, script in _waiting(app) if script.endswith(name)]


# A leak adds at least one command per call, so a batch of ten or more
# shows ten or more; a few either way is the app's own business.
LEAK_FLOOR = 5


def _kept_commands(app):
    """Every Tcl command, less those a timer is waiting to run: a timer's
    command lives from scheduling to running, so how many wait says how
    fast the machine is, not what leaked."""
    timers = {script for _job, script in _waiting(app)}
    return {str(c) for c in app.tk.splitlist(app.tk.call("info", "commands"))
            } - timers


def _kind(name):
    """A widget's command is its path, a callback's an id and its
    function's name: what kind of thing a command is, without the numbers."""
    if name.startswith("."):
        return re.sub(r"-?\d+$", "", name.rsplit(".", 1)[-1])
    return re.sub(r"^\d+", "", name)


def leaves_nothing_behind(app, redraw, times):
    """Call *redraw* three batches of *times*, and say whether it leaves
    Tcl commands behind for good: ``(clean, said)``.

    The first batch absorbs what a redraw does only once. The next two are
    counted, and the smaller growth is the verdict: a leak grows in both,
    while something that appears once can only land between two counts.
    That once was real. On a CI runner the pointer rests where the display
    put it, over a Recently deleted row, and that row's hover preview --
    one window, three frames, four labels -- opened inside one batch and
    read as nine leaked commands. CI counted exactly nine on two pull
    requests; the second time the kinds were named, and they were those.
    """
    for _ in range(times):
        redraw()
    app.update()
    counts = [_kept_commands(app)]
    for _ in range(2):
        for _ in range(times):
            redraw()
        app.update()
        counts.append(_kept_commands(app))
    grew = [collections.Counter(map(_kind, after)) -
            collections.Counter(map(_kind, before))
            for before, after in zip(counts, counts[1:])]
    growth = min(len(after) - len(before)
                 for before, after in zip(counts, counts[1:]))
    said = "%d -> %d -> %d" % tuple(len(c) for c in counts)
    both = grew[0] & grew[1]
    once = (grew[0] | grew[1]) - both
    if both:
        said += "; grew in both: " + ", ".join(
            "%s +%d" % kv for kv in both.most_common(6))
    if once:
        said += "; once: " + ", ".join(
            "%s +%d" % kv for kv in once.most_common(6))
    return growth < LEAK_FLOOR, said


# Tk keeps a canvas window's place, and X a window's, in 16 bits: one frame
# holding a list could not be scrolled further than this.
ONE_FRAME_REACH = 32_767


def reaches_the_end(app, canvas, last, settle):
    """Whether a list drawn on *canvas* -- longer than one frame could ever
    be scrolled through, or the check proves nothing -- shows *last*, its
    last control, once scrolled to its end: ``(ok, said)``. *settle* lets
    the app lay out and draw before *last* is looked at."""
    try:
        region = [float(v) for v in str(canvas.cget("scrollregion")).split()]
    except (tk.TclError, ValueError):
        region = []
    tall = region[3] - region[1] if len(region) == 4 else 0
    canvas.yview_moveto(1.0)
    settle()
    view = canvas.winfo_height()
    top = last.winfo_rooty() - canvas.winfo_rooty()
    bottom = top + last.winfo_height()
    # All of it, or -- a row taller than the view -- its last pixels.
    seen = (bool(last.winfo_viewable()) and 0 < bottom <= view
            and (top >= 0 or last.winfo_height() > view))
    return (tall > ONE_FRAME_REACH + view and seen,
            "%d px of rows; the last at %d in a view of %d%s"
            % (tall, top, view, "" if last.winfo_viewable() else ", not drawn"))


# ---- The shutter: a picture of the app holds only the app's pixels ----

# One sample every this many of Tk's pixels, across the box and on its last
# row and column: a notification is about 100 px tall, and doc_screenshots'
# old 7 x 7 grid stepped up to 160 px at a time.
SHUTTER_STEP = 16
_WIN32 = {}


def _win32():
    if not _WIN32:
        import ctypes
        import ctypes.wintypes as wt

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT),
                        ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

        user = ctypes.WinDLL("user32", use_last_error=True)
        user.WindowFromPoint.restype = wt.HWND
        user.WindowFromPoint.argtypes = [wt.POINT]
        user.GetWindowThreadProcessId.restype = wt.DWORD
        user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
        user.GetAncestor.restype = wt.HWND
        user.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
        user.MonitorFromWindow.restype = wt.HANDLE
        user.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
        user.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.POINTER(MonitorInfo)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = wt.HANDLE
        kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                                      ctypes.POINTER(wt.DWORD)]
        kernel.CloseHandle.argtypes = [wt.HANDLE]
        _WIN32.update(ctypes=ctypes, wt=wt, user=user, kernel=kernel, MonitorInfo=MonitorInfo)
    return _WIN32


def _shutter_box(app, box):
    """*box* (or the whole window) cut to the window and to the work area of
    the primary screen, in Tk's pixels; (None, why) when nothing is left."""
    w = _win32()
    frame = (app.winfo_rootx(), app.winfo_rooty(),
             app.winfo_rootx() + app.winfo_width(), app.winfo_rooty() + app.winfo_height())
    box = frame if box is None else tuple(int(round(v)) for v in box)
    box = (max(box[0], frame[0]), max(box[1], frame[1]),
           min(box[2], frame[2]), min(box[3], frame[3]))
    top_level = w["user"].GetAncestor(app.winfo_id(), 2)            # GA_ROOT
    info = w["MonitorInfo"]()
    info.cbSize = w["ctypes"].sizeof(info)
    monitor = w["user"].MonitorFromWindow(top_level, 2)               # NEAREST
    if not monitor or not w["user"].GetMonitorInfoW(monitor, w["ctypes"].byref(info)):
        return None, "the screen the window is on could not be read"
    if not info.dwFlags & 1:                                          # PRIMARY
        return None, "the window is not on the primary screen"
    work = info.rcWork
    box = (max(box[0], work.left), max(box[1], work.top),
           min(box[2], work.right), min(box[3], work.bottom))
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        return None, "no part of the window is on the screen"
    return box, ""


def _foreign_over(box):
    """The pids of other programs' windows on top anywhere in *box*."""
    w = _win32()
    own, owners, seen = os.getpid(), {}, set()
    left, top, right, bottom = box
    xs = sorted(set(range(left, right, SHUTTER_STEP)) | {right - 1})
    ys = sorted(set(range(top, bottom, SHUTTER_STEP)) | {bottom - 1})
    for y in ys:
        for x in xs:
            hwnd = w["user"].WindowFromPoint(w["wt"].POINT(x, y))
            if not hwnd:
                continue
            if hwnd not in owners:
                pid = w["wt"].DWORD()
                w["user"].GetWindowThreadProcessId(hwnd, w["ctypes"].byref(pid))
                owners[hwnd] = pid.value
            if owners[hwnd] and owners[hwnd] != own:
                seen.add(owners[hwnd])
    return sorted(seen)


def _program_of(pid):
    """A program's file name, for the message -- never a window's title,
    which can be anything of hers."""
    w = _win32()
    handle = w["kernel"].OpenProcess(0x1000, False, pid)              # QUERY_LIMITED
    if not handle:
        return "pid %d" % pid
    try:
        size = w["wt"].DWORD(1024)
        name = w["ctypes"].create_unicode_buffer(1024)
        if w["kernel"].QueryFullProcessImageNameW(handle, 0, name, w["ctypes"].byref(size)):
            return "%s (pid %d)" % (os.path.basename(name.value), pid)
        return "pid %d" % pid
    finally:
        w["kernel"].CloseHandle(handle)


def _on_top(app):
    """The window above everything for the shot, its own popups above it:
    raising the window raises it over its own Toplevels too."""
    app.attributes("-topmost", True)
    for child in app.winfo_children():
        if isinstance(child, tk.Toplevel):
            try:
                if child.winfo_ismapped():
                    if str(child.attributes("-topmost")) in ("1", "True"):
                        child.attributes("-topmost", True)
                    child.lift()
            except tk.TclError:
                pass
    app.update()
    app.update_idletasks()


def grab(app, box=None):
    """The app's window -- or *box*, (left, top, right, bottom) on the screen
    in Tk's pixels -- as a picture: (image, ''), or (None, why not) when
    the picture would show anything that is not the app."""
    if sys.platform != "win32":
        return None, "photographs are taken on Windows only"
    from PIL import ImageGrab
    try:
        _on_top(app)
        box, why = _shutter_box(app, box)
        if box is None:
            return None, why
        foreign = _foreign_over(box)
        for _ in range(3):              # the order on screen can take a moment
            if not foreign:
                break
            time.sleep(0.15)
            _on_top(app)
            foreign = _foreign_over(box)
        if foreign:
            return None, "%s is over the window" % ", ".join(_program_of(p) for p in foreign)
        screen = ImageGrab.grab()
        foreign = _foreign_over(box)
        if foreign:
            return None, ("%s came over the window while it was photographed"
                          % ", ".join(_program_of(p) for p in foreign))
        scale = screen.size[0] / float(app.winfo_screenwidth())
        cut = [int(round(v * scale)) for v in box]
        cut = (max(0, cut[0]), max(0, cut[1]),
               min(screen.size[0], cut[2]), min(screen.size[1], cut[3]))
        return screen.crop(cut), ""
    finally:
        try:
            app.attributes("-topmost", False)
            app.update_idletasks()
        except tk.TclError:
            pass


def photograph(app, path, box=None):
    """Save grab(app, box) to *path*: (True, (width, height)), or (False,
    why not) -- and then nothing is saved."""
    image, why = grab(app, box)
    if image is None:
        return False, why
    image.save(path)
    return True, image.size
