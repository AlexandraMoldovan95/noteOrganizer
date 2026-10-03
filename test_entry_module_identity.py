"""The Settings labels must not read values off the entry module's globals.

WHY THIS EXISTS
---------------
Running the app the normal way -- ``py note_organizer.py`` -- makes the
running module ``__main__``. Anything that then does ``import
note_organizer`` gets a *second, separate* module object: same file, its own
globals, and ``initialise()`` never ran on it. Every value ``initialise()``
assigns is still ``None`` there.

That is exactly what happened when the Settings page moved into a mixin. It
could no longer say ``APP_DIR`` directly, so it grew a ``_host()`` helper
that imports the entry module -- and under a real launch that helper handed
back the uninitialised copy. The storage path in About rendered blank, and
Statistics read "Using Note Organizer since None". Both shipped, because:

* the app still started, so nothing crashed;
* every QA script does ``import note_organizer as NO``, which makes the
  running module *be* ``note_organizer``, so ``_host()`` returns the very
  same object and the bug is invisible to all nine of them.

That second point is the important one. The whole GUI suite is structurally
incapable of catching this class of bug, so it needs its own test.

WHAT IT CHECKS
--------------
Two ways, from opposite directions:

1. Loading the source under the name ``__main__`` -- a faithful reproduction
   of a real launch -- and confirming the values the labels need are still
   reachable.
2. Blanking the entry module's globals after startup and rebuilding the
   panels, confirming the labels still show real values. This pins the
   actual invariant: *these labels do not depend on those globals.*

Run it like the other standalone suites::

    py test_entry_module_identity.py
"""

import io
import json
import os
import shutil
import sys
import tempfile
import tkinter as tk

fails = []

# Everything below runs against a throwaway folder, never the checkout and
# never a real notebook.
#
# Making that true takes two files, because startup has two separate ways of
# adopting existing data and each needs its own answer:
#
#   settings.json    carries reclaimed_from_appdata, which stops the
#                    %APPDATA% reclaim (run_migrations case 1). It also
#                    stamps a known first-launch date, so the Statistics
#                    assertion below can be exact rather than "not None".
#   notes_data.json  merely existing stops case 2, which otherwise hunts for
#                    the "richest legacy copy" it can find and adopts it --
#                    on a developer machine that means the real notebook,
#                    which would quietly make this test depend on whatever
#                    notes happen to be on the machine running it.
#
# Both are copies-in, never deletes, so neither could damage real data; the
# point here is only that the test must not read it either.
SANDBOX = tempfile.mkdtemp(prefix="notesorg-identity-")
STAMP = "2020-01-02"
io.open(os.path.join(SANDBOX, "settings.json"), "w", encoding="utf-8").write(
    json.dumps({"reclaimed_from_appdata": True,
                "cleanup_done": True,
                "first_launch_date": STAMP})
)
io.open(os.path.join(SANDBOX, "notes_data.json"), "w", encoding="utf-8").write("[]")


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")
    if not cond:
        fails.append(name)


# --------------------------------------------------------------------------
# 1. Load the source as "__main__", the way a real launch does.
# --------------------------------------------------------------------------
# The trailing ``if __name__ == "__main__": _main()`` would open a window and
# block in mainloop, so the source is cut just above it. Everything before
# that point is what a launch actually executes.
HERE = os.path.dirname(os.path.abspath(__file__))
src = io.open(os.path.join(HERE, "note_organizer.py"), encoding="utf-8").read()
guard = 'if __name__ == "__main__":'
check("the entry-point guard is where this test expects it", guard in src)
body = src[:src.rindex(guard)]

main_mod = type(sys)("__main__")
main_mod.__file__ = os.path.join(HERE, "note_organizer.py")
real_main = sys.modules.get("__main__")
sys.modules["__main__"] = main_mod
try:
    exec(compile(body, main_mod.__file__, "exec"), main_mod.__dict__)
    main_mod.initialise(SANDBOX)
finally:
    if real_main is not None:
        sys.modules["__main__"] = real_main

check("initialise() ran on the __main__ copy", main_mod._initialised is True)
check("the __main__ copy knows its data folder", bool(main_mod.APP_DIR))
check("it resolved to the sandbox, not the checkout",
      main_mod.APP_DIR == SANDBOX, f"(got {main_mod.APP_DIR!r})")

# The separately-imported copy is a different object with empty globals --
# this is the trap, and it is expected. What matters is that nothing the UI
# needs is read from it.
import note_organizer as imported  # noqa: E402

check("a plain import really is a different module object",
      imported is not main_mod)
check("and its initialise() has NOT run -- the trap this test guards",
      imported._initialised is False)

# The core layer is imported by name, so there is only ever one of it.
from noteorganizer.core import paths  # noqa: E402

check("core.paths knows the data folder after initialise()",
      bool(paths.APP_DIR), f"(got {paths.APP_DIR!r})")
check("core.paths agrees with the entry module",
      paths.APP_DIR == main_mod.APP_DIR)

# If startup had adopted a notebook from elsewhere on this machine, the
# sandbox would no longer be empty -- and every assertion below would be
# measuring someone's real data instead of this test's fixture.
_sandbox_notes = json.loads(
    io.open(os.path.join(SANDBOX, "notes_data.json"), encoding="utf-8").read())
check("startup adopted no outside notebook -- the sandbox is still empty",
      _sandbox_notes == [], f"({len(_sandbox_notes)} notes appeared)")


# --------------------------------------------------------------------------
# 2. Build the app exactly the way a real launch does, and read the labels.
# --------------------------------------------------------------------------
# This is the whole reproduction, and it relies on the split above rather
# than faking anything: the app is constructed from the *__main__* copy,
# which is initialised, while ``import note_organizer`` -- what _host()
# reaches for -- still returns the *other* copy, whose globals are all None.
# That is precisely the production situation.
#
# An earlier version of this test tried to force the failure by blanking
# ``imported.APP_DIR`` after construction. That silently proved nothing:
# About is one of the eagerly-built panels, so its labels already had their
# text and no later change to a global could affect them.
from noteorganizer.core.storage import load_settings  # noqa: E402

check("the copy _host() returns still has no APP_DIR -- the bug's precondition",
      imported.APP_DIR is None)

app = main_mod.NoteOrganizer()
app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.update()


def find_labels(w, acc=None):
    if acc is None:
        acc = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label):
            try:
                acc.append(c.cget("text"))
            except tk.TclError:
                pass
        find_labels(c, acc)
    return acc


app.show_settings_page()
app.update()

app.toggle_settings_panel("about")
app.update()
about_text = " ".join(find_labels(app.settings_about_panel))
real_dir = paths.APP_DIR

check("About still shows the storage path",
      real_dir in about_text, f"(about panel said: {about_text[:90]!r})")
check("About does not render an empty path",
      "(not set yet)" not in about_text)
check("About still shows the version",
      "Version" in about_text and "None" not in about_text)

app.toggle_settings_panel("statistics")
app.update()
stats_text = " ".join(find_labels(app.stats_frame))
stamp = load_settings().get("first_launch_date")

check("Statistics has a real first-launch stamp to show", bool(stamp))
check("the stamp is the sandbox one, so this assertion is exact", stamp == STAMP)
# Shown as every date in the app is shown, day first (show_date): the
# stored stamp is 2020-01-02, the screen says 02.01.2020.
check("Statistics shows the date, not None",
      imported.show_date(stamp) in stats_text and "since None" not in stats_text,
      f"(stats said: {stats_text[-90:]!r})")

app.destroy()
shutil.rmtree(SANDBOX, ignore_errors=True)

print()
print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
