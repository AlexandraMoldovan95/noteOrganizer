"""A user story, walked on the real app, across real restarts.

WHY THIS EXISTS
---------------
The qa suite asks the app questions. This walks it somewhere. The
difference is not academic: four user-visible bugs shipped in 0.73.159
and 0.73.161 and none of them was reachable by the suite as it stood,
because each needed something a question cannot express --

* a RESTART between two steps (the identity a note is given has to be
  the same one after the app has been closed);
* a SEQUENCE (generate a code, then open a different note, and look at
  what is still on screen);
* a SECOND VISIT (delete a note, then arrive at Settings again);
* a WHAT-HAPPENS-NEXT (update a note from a code, then carry on typing,
  and see whether the update survives the save that follows).

Every step here presses the button a person would press -- the note card,
"📋 Generate code", the dialog's own buttons -- rather than calling the
method behind it. A check that calls the method with the argument the app
is supposed to pass proves only that the method obeys an argument nobody
had to send; that exact mistake was made and caught on 2026-09-13.

HOW IT RUNS
-----------
``py qa/story_note_travels.py`` from anywhere. The driver copies the app,
the package and this file into a scratch directory far outside the
project (the same rule the whole suite follows: real notes have been lost
to a wrong working directory four times) and then runs each chapter as
its OWN PROCESS in that directory. Separate processes are the point: that
is what makes "close the app and open it again" real rather than
simulated.

Screenshots land beside the scratch directory and their paths are
printed. They are meant to be LOOKED AT, not just written: two bugs in
this project were invisible in the source and obvious in a photograph.

``--chapter N`` is how the driver re-enters this file inside the scratch
directory. Not meant to be run by hand.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

RESULTS = "story_results.json"
CODE_FILE = "the_code.txt"


# --------------------------------------------------------------------
# The driver: scratch copy, then one process per chapter.
# --------------------------------------------------------------------

def _project_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def drive():
    sys.stdout.reconfigure(encoding="utf-8")
    root = _project_root()
    work = tempfile.mkdtemp(prefix="story-")
    shots = os.path.join(work, "shots")
    os.makedirs(shots)

    shutil.copy2(os.path.join(root, "note_organizer.py"), work)
    shutil.copytree(os.path.join(root, "noteorganizer"),
                    os.path.join(work, "noteorganizer"))
    shutil.copy2(os.path.join(root, "qa", "_qa_support.py"), work)
    shutil.copy2(os.path.abspath(__file__),
                 os.path.join(work, "story_note_travels.py"))

    # A hermetic notebook, so the story never meets the real one.
    io.open(os.path.join(work, "notes_data.json"), "w", encoding="utf-8").write(
        json.dumps([
            {"id": 1, "title": "Bread recipe", "body": "500g flour\n300ml water",
             "category": "General", "created": "2026-09-01 09:00",
             "updated": "2026-09-01 09:00"},
            {"id": 2, "title": "Shopping", "body": "milk\neggs",
             "category": "General", "created": "2026-09-02 09:00",
             "updated": "2026-09-02 09:00"},
        ], indent=2))
    io.open(os.path.join(work, "settings.json"), "w", encoding="utf-8").write(
        json.dumps({"cleanup_done": True, "reclaimed_from_appdata": True}))

    # %APPDATA% of its own, empty. The app reads that folder on every
    # start -- it is where the installed app keeps its notebook -- and a
    # story that loses its settings.json on purpose (chapter 6) would
    # otherwise walk straight into the one-time migration that copies the
    # real notebook in. Pointing it here makes that impossible rather
    # than merely unlikely, for every chapter.
    sandbox = os.path.join(work, "appdata-sandbox")
    os.makedirs(sandbox)
    env = dict(os.environ, APPDATA=sandbox, XDG_DATA_HOME=sandbox)

    print("the story is played in: %s" % work)
    print()

    chapters = [
        (1, "I make a code for a note, from the editor", None),
        (2, "I close the app, reopen it, edit the note and bring the code back", None),
        (3, "I generate a code and move to another note", None),
        (4, "I delete a note and go back into Settings", None),
        (5, "I name a category too long, then make a real one and file a note in it", None),
        (6, "My settings file is gone, and I open the app again", _lose_the_settings),
        (7, "A note comes back from a code; I update it, then take the update back",
         _a_list_from_yesterday),
    ]
    results = []
    for number, title, before in chapters:
        print("--- chapter %d: %s" % (number, title))
        if before is not None:
            before(work)
        run = subprocess.run(
            [sys.executable, "story_note_travels.py", "--chapter", str(number)],
            cwd=work, capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace")
        found = _read_results(work)
        results.extend(found)
        for name, ok, detail in found:
            print("    %s %s%s" % ("PASS" if ok else "FAIL", name,
                                   "" if ok else "   <- %s" % detail))
        if not found:
            print("    THE CHAPTER SAID NOTHING (did it crash?)")
            tail = (run.stdout + run.stderr).strip().splitlines()[-6:]
            for line in tail:
                print("      | %s" % line)
            results.append(("chapter %d ran" % number, False, "no results"))
        _clear_results(work)

    print()
    shot_files = sorted(os.path.join(shots, f) for f in os.listdir(shots))
    for path in shot_files:
        print("picture: %s" % path)
    failed = [name for name, ok, _ in results if not ok]
    print()
    print("STORY FAILURES: %s" % (failed if failed else "none"))
    # The pictures outlive the run, green or red. The first version of
    # this deleted them whenever the story passed -- which is exactly the
    # run where nobody is forced to look, and therefore the run where
    # looking is worth the most: a story asserts what it was told to
    # assert, and the photograph is the only part that can show something
    # nobody thought to ask about. On a failure the whole scratch
    # directory stays, so the notebook it walked can be read too.
    if not failed:
        for name in os.listdir(work):
            if name == "shots":
                continue
            path = os.path.join(work, name)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
    return 1 if failed else 0


def _lose_the_settings(work):
    """What a person does between two sessions to reset the preferences:
    the settings file goes. The notebook stays."""
    path = os.path.join(work, "settings.json")
    if os.path.exists(path):
        os.remove(path)


def _a_list_from_yesterday(work):
    """A note left in an earlier session: a checklist with two of its three
    items ticked, and a date. (Chapter 4 sent "Shopping" to the Trash, so
    this is a note of its own.)"""
    path = os.path.join(work, "notes_data.json")
    notes = json.load(io.open(path, encoding="utf-8"))
    notes.append({"id": 50, "title": "Groceries", "body": "for the weekend",
                  "category": "General", "date": "2026-10-01",
                  "checklist": [{"text": "milk", "done": True},
                                {"text": "eggs", "done": True},
                                {"text": "bread", "done": False}],
                  "created": "2026-09-20 09:00", "updated": "2026-09-20 09:00"})
    io.open(path, "w", encoding="utf-8").write(json.dumps(notes, indent=2))


def _read_results(work):
    path = os.path.join(work, RESULTS)
    if not os.path.exists(path):
        return []
    try:
        return [tuple(row) for row in json.load(io.open(path, encoding="utf-8"))]
    except Exception:
        return []


def _clear_results(work):
    path = os.path.join(work, RESULTS)
    if os.path.exists(path):
        os.remove(path)


# --------------------------------------------------------------------
# Inside a chapter: the app, and the hands that drive it.
# --------------------------------------------------------------------

def _chapter_setup():
    import tkinter as tk
    sys.path.insert(0, ".")
    import note_organizer as NO
    from _qa_support import pin_popup_visibility
    pin_popup_visibility(NO)
    app = NO.NoteOrganizer()
    app._poll_active_dirty = lambda: None
    app.show_info = lambda *a, **k: True
    app.show_warning = lambda *a, **k: True
    app.ask_yes_no = lambda *a, **k: True
    app.geometry("1150x860+40+40")
    app.update()
    return tk, NO, app


def _button(widget, label, exact=False):
    """The first button whose text contains `label`, anywhere below.

    `exact` strips the decoration and compares the whole word, which
    matters more than it looks: the sidebar's "📥 Import code" contains
    "Import", so a loose search for the import panel's own "Import"
    button found the sidebar one and closed the panel instead. The story
    then walked on and reported that the app had asked nothing -- a
    story that presses the wrong button accuses the app of ITS mistake.
    """
    import tkinter as tk
    for child in widget.winfo_children():
        if isinstance(child, tk.Button):
            text = str(child.cget("text")).strip()
            if (text == label) if exact else (label in text):
                return child
        found = _button(child, label, exact)
        if found:
            return found
    return None


def _text_widget(widget):
    import tkinter as tk
    for child in widget.winfo_children():
        if isinstance(child, tk.Text):
            return child
        found = _text_widget(child)
        if found:
            return found
    return None


def _click_dialog(app, label):
    """Press a button on whatever themed dialog is showing."""
    app.update()
    for frame in app.place_slaves():
        button = _button(frame, label)
        if button:
            button.invoke()
            app.update()
            return True
    return False


def _dialog_titles(app):
    import tkinter as tk
    seen = []

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                seen.append(str(child.cget("text")))
            walk(child)
    for frame in app.place_slaves():
        walk(frame)
    return seen


def _open_note_by_clicking(app, title):
    """Click the note's card in the list, the way a person opens a note."""
    app.refresh_note_list()
    app.update()
    for note in app.notes:
        if note.get("title") == title:
            card = (app._note_card_widgets.get(note["id"]) or {}).get("card")
            if card is not None:
                card.event_generate("<Button-1>", x=5, y=5)
                app.update()
                return True
    return False


def _let_it_paint(app, seconds=0.6):
    """Let the app draw before a picture is taken from inside a dialog.

    A chapter answers a dialog by standing in for the wait the dialog
    blocks on -- and the real wait processes events while it waits, so the
    window paints behind the question. The stand-in does not, so a
    picture taken at once showed the startup notice over a window of white
    rectangles: a portrait of the harness, not of the app."""
    end = time.time() + seconds
    while time.time() < end:
        try:
            app.update()
        except Exception:
            return
        time.sleep(0.03)


def _photograph(name):
    """Photograph the screen. Best effort: a missing picture is not a
    failed story, it is a missing picture."""
    here = os.path.abspath(".")
    out = os.path.join(here, "shots", name + ".png")
    script = os.path.join(here, "shot.ps1")
    if not os.path.exists(script):
        io.open(script, "w", encoding="utf-8").write(
            "param([string]$Out, [int]$Delay = 1)\n"
            "Add-Type -AssemblyName System.Windows.Forms, System.Drawing\n"
            "Start-Sleep -Seconds $Delay\n"
            "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen\n"
            "$bmp = New-Object System.Drawing.Bitmap($b.Width, $b.Height)\n"
            "$g = [System.Drawing.Graphics]::FromImage($bmp)\n"
            "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)\n"
            "$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)\n"
            "$g.Dispose(); $bmp.Dispose()\n")
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                        "-File", script, "-Out", out, "-Delay", "1"],
                       capture_output=True, timeout=60)
    except Exception:
        pass


class Chapter:
    """Records what the story saw, so the driver can print it."""

    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), str(detail)[:200]))

    def save(self):
        io.open(RESULTS, "w", encoding="utf-8").write(
            json.dumps(self.rows, ensure_ascii=False))


def chapter_1():
    """She opens a note and makes a code for it, from the editor."""
    tk, NO, app = _chapter_setup()
    story = Chapter()

    story.check("the note opens when I click it in the list",
                _open_note_by_clicking(app, "Bread recipe"))

    generate = _button(app, "Generate code")
    story.check("the 'Generate code' button is there, in the editor",
                generate is not None)
    if generate is not None:
        generate.invoke()
        app.update()

    shown = app.editor_code_area.winfo_ismapped()
    story.check("the code appears under the note", shown)
    code = ""
    if shown:
        widget = _text_widget(app.editor_code_area)
        if widget is not None:
            code = widget.get("1.0", "end-1c").strip()
    story.check("the code looks like a share code", code.startswith("NOTE1"),
                code[:20])
    io.open(CODE_FILE, "w", encoding="utf-8").write(code)
    _photograph("1-the-code-made-in-the-editor")
    story.save()


def chapter_2():
    """A NEW PROCESS: the app was closed and opened again. She edits the
    note, then brings the code back."""
    tk, NO, app = _chapter_setup()
    story = Chapter()
    code = io.open(CODE_FILE, encoding="utf-8").read().strip()

    _open_note_by_clicking(app, "Bread recipe")
    app.body_text.insert("end", "\n-- changed after I closed the app")
    save = _button(app, "Save")
    if save is not None:
        save.invoke()
    app.update()

    imported = _button(app, "Import code")
    story.check("the 'Import code' button is in the sidebar",
                imported is not None)
    if imported is not None:
        imported.invoke()
        app.update()
    app.import_box.delete("1.0", "end")
    app.import_box.insert("1.0", code)

    # A themed dialog BLOCKS: it waits on a variable, so the code after
    # the click never runs until an answer arrives. The answer therefore
    # has to be given from inside the wait -- which is also the only
    # moment the question is on screen to be photographed. (Discovered by
    # hanging the story for ten minutes.)
    seen = {"titles": [], "answered": ""}

    def answer_the_dialog(_var):
        seen["titles"] = _dialog_titles(app)
        _let_it_paint(app)
        _photograph("2-what-it-asks-me-on-import")
        for label in ("Update this note", "Open it anyway", "Cancel"):
            if _click_dialog(app, label):
                seen["answered"] = label
                return
    app.wait_variable = answer_the_dialog

    go = _button(app, "Import", exact=True)
    story.check("the 'Import' button is in the panel", go is not None)
    if go is not None:
        go.invoke()
        app.update()

    titles = seen["titles"]
    asked_about_the_note = any("Same note" in t for t in titles)
    story.check("it asks me about MY NOTE, not about a duplicate",
                asked_about_the_note,
                "what the screen said: %s" % [t[:45] for t in titles if t][:3])
    story.check("and the answer I want is there to press",
                seen["answered"] == "Update this note",
                "the only answer I could press: %r" % seen["answered"])

    notes = json.load(io.open("notes_data.json", encoding="utf-8"))
    story.check("no second copy of the note appeared",
                len([n for n in notes if "Bread" in (n.get("title") or "")]) == 1,
                "titles: %s" % [n.get("title") for n in notes])
    mine = next((n for n in notes if "Bread" in (n.get("title") or "")), {})
    story.check("the note shows the version the code brought",
                "changed after I closed" not in (mine.get("body") or ""),
                (mine.get("body") or "")[:60])

    # And what happens NEXT: she carries on typing, which saves.
    app.body_text.insert("end", " ")
    app._flush_autosave()
    app.update()
    notes = json.load(io.open("notes_data.json", encoding="utf-8"))
    mine = next((n for n in notes if "Bread" in (n.get("title") or "")), {})
    story.check("...and it stays that way after I keep typing",
                "changed after I closed" not in (mine.get("body") or ""),
                (mine.get("body") or "")[:60])
    _photograph("3-after-the-update")
    story.save()


def chapter_3():
    """She makes a code, then goes to another note."""
    tk, NO, app = _chapter_setup()
    story = Chapter()

    _open_note_by_clicking(app, "Shopping")
    generate = _button(app, "Generate code")
    if generate is not None:
        generate.invoke()
        app.update()
    story.check("the code on screen belongs to the note I am on",
                app.editor_code_area.winfo_ismapped())

    _open_note_by_clicking(app, "Bread recipe")
    _photograph("4-after-moving-to-another-note")
    story.check("the code is NOT still on screen at the next note",
                not app.editor_code_area.winfo_ismapped(),
                "the previous note's code is still on screen")
    story.save()


def chapter_4():
    """She deletes a note and comes back to Settings."""
    tk, NO, app = _chapter_setup()
    story = Chapter()

    settings = _button(app, "Settings")
    story.check("the 'Settings' button is in the sidebar", settings is not None)
    if settings is not None:
        settings.invoke()
        app.update()
    app.toggle_settings_panel("trash")
    app.update()
    app.hide_settings_page()
    app.update()

    _open_note_by_clicking(app, "Shopping")
    delete = _button(app, "Delete")
    story.check("the delete button is in the editor", delete is not None)
    if delete is not None:
        delete.invoke()
        app.update()

    if settings is not None:
        settings.invoke()
        app.update()
    _photograph("5-the-trash-after-deleting")

    def labels(widget, out):
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                out.append(str(child.cget("text")))
            labels(child, out)
        return out

    shown = labels(app.settings_trash_panel, [])
    story.check("the deleted note is in the trash when I get there",
                any("Shopping" in t for t in shown),
                "the trash says: %s" % [t[:30] for t in shown if t][:4])
    story.save()


def _entries_under(widget, out=None):
    import tkinter as tk
    out = [] if out is None else out
    for child in widget.winfo_children():
        if isinstance(child, tk.Entry):
            out.append(child)
        _entries_under(child, out)
    return out


def chapter_5():
    """She makes a category with a long, descriptive name. The app says
    no, and why; she makes a shorter one and files a note under it."""
    tk, NO, app = _chapter_setup()
    story = Chapter()
    # The real warning, not the stub the setup installs: the point is to
    # see the message a person gets, so it has to be on screen.
    del app.show_warning
    said = []

    def answer(_var):
        said[:] = _dialog_titles(app)
        _let_it_paint(app)
        _photograph("6-a-category-name-that-is-too-long")
        _click_dialog(app, "OK")
    app.wait_variable = answer

    settings = _button(app, "Settings")
    if settings is not None:
        settings.invoke()
        app.update()
    app.toggle_settings_panel("categories")
    app.update()
    panel = app.settings_categories_panel
    boxes = _entries_under(panel)
    story.check("the Categories panel has a box to type a new name in",
                bool(boxes))
    long_name = ("Kitchen and bathroom renovation for the new apartment - "
                 "quotes, invoices, contacts")
    if boxes:
        boxes[-1].insert(0, long_name)
        add = _button(panel, "+ Add")
        if add is not None:
            add.invoke()
            app.update()
    story.check("a name longer than 80 characters is refused",
                long_name not in NO.CATEGORY_COLORS)
    story.check("...and the message says why, naming the limit",
                any("80" in t for t in said),
                "what the screen said: %s" % [t[:60] for t in said if t][:3])

    boxes = _entries_under(panel)
    if boxes:
        boxes[-1].delete(0, "end")
        boxes[-1].insert(0, "Clients 2026")
        add = _button(panel, "+ Add")
        if add is not None:
            add.invoke()
            app.update()
    story.check("a shorter name is added", "Clients 2026" in NO.CATEGORY_COLORS)
    app.hide_settings_page()
    app.update()

    _open_note_by_clicking(app, "Bread recipe")
    app.category_var.set("Clients 2026")
    save = _button(app, "Save")
    if save is not None:
        save.invoke()
    app.update()
    notes = json.load(io.open("notes_data.json", encoding="utf-8"))
    bread = next((n for n in notes if n.get("title") == "Bread recipe"), {})
    story.check("the note is filed under it, on disk",
                bread.get("category") == "Clients 2026", bread.get("category"))
    story.save()


def chapter_6():
    """A NEW PROCESS, and the settings file is gone: she deleted it to
    reset her preferences. The notebook is untouched."""
    import tkinter as tk
    sys.path.insert(0, ".")
    import note_organizer as NO
    from _qa_support import pin_popup_visibility
    pin_popup_visibility(NO)
    story = Chapter()
    said = []
    app = NO.NoteOrganizer()
    app._poll_active_dirty = lambda: None

    # The startup notice is scheduled a moment after the window appears,
    # and it blocks until answered -- so it is read, photographed and
    # answered from inside the wait, the way chapter 2 answers its dialog.
    def answer(_var):
        said[:] = _dialog_titles(app)
        _let_it_paint(app)
        _photograph("7-what-the-app-says-after-the-settings-were-lost")
        _click_dialog(app, "OK")
    app.wait_variable = answer
    app.geometry("1150x860+40+40")
    deadline = time.time() + 5
    while time.time() < deadline and not said:
        app.update()
        time.sleep(0.05)

    story.check("the app tells me something happened, instead of saying nothing",
                bool(said))
    story.check("...and it names the category that came back",
                any("Clients 2026" in t for t in said),
                "what the screen said: %s" % [t[:70] for t in said if t][:3])
    notes = json.load(io.open("notes_data.json", encoding="utf-8"))
    bread = next((n for n in notes if n.get("title") == "Bread recipe"), {})
    story.check("my note is still filed where I put it, not in General",
                bread.get("category") == "Clients 2026", bread.get("category"))
    story.check("...and the category is back in the app",
                "Clients 2026" in NO.CATEGORY_COLORS)
    _photograph("7b-the-list-after-the-settings-were-lost")
    story.save()


def chapter_7():
    """She makes a code for a list, changes the list, and brings the code
    back as an update. Then she changes her mind."""
    tk, NO, app = _chapter_setup()
    story = Chapter()
    # Both questions for real: the one the import asks, and the one
    # Restore previous asks -- the second is the one whose words matter.
    del app.ask_yes_no
    asked = []

    def answer(_var):
        titles = _dialog_titles(app)
        asked.append(titles)
        if any("Same note" in t for t in titles):
            _click_dialog(app, "Update this note")
        elif any("Restore previous" in t for t in titles):
            _let_it_paint(app)
            _photograph("8-the-question-before-restoring")
            _click_dialog(app, "Yes")
        else:
            _click_dialog(app, "Cancel") or _click_dialog(app, "OK")
    app.wait_variable = answer

    story.check("the list opens when I click it",
                _open_note_by_clicking(app, "Groceries"))
    generate = _button(app, "Generate code")
    if generate is not None:
        generate.invoke()
        app.update()
    code = ""
    if app.editor_code_area.winfo_ismapped():
        widget = _text_widget(app.editor_code_area)
        if widget is not None:
            code = widget.get("1.0", "end-1c").strip()
    story.check("I have a code for the list as it is", code.startswith("NOTE1"))

    # Now she changes it: everything unticked, the date taken off.
    for box in [w for w in _all_children(app.checklist_items_frame)
                if isinstance(w, tk.Checkbutton)]:
        if box.cget("variable") and int(app.getvar(box.cget("variable"))):
            box.invoke()
    app.date_entry.delete(0, "end")
    save = _button(app, "Save")
    if save is not None:
        save.invoke()
    app.update()

    imported = _button(app, "Import code")
    if imported is not None:
        imported.invoke()
        app.update()
    app.import_box.delete("1.0", "end")
    app.import_box.insert("1.0", code)
    go = _button(app, "Import", exact=True)
    if go is not None:
        go.invoke()
        app.update()

    def on_disk():
        notes = json.load(io.open("notes_data.json", encoding="utf-8"))
        return next((n for n in notes if n.get("title") == "Groceries"), {})

    after_update = on_disk()
    story.check("the update brings the code's version: two ticked, and the date",
                [i.get("done") for i in after_update.get("checklist", [])]
                == [True, True, False]
                and after_update.get("date") == "2026-10-01",
                after_update.get("checklist"))

    restore = _button(app, "Restore previous")
    story.check("the editor offers Restore previous, on screen",
                restore is not None and restore.winfo_ismapped())
    if restore is not None:
        restore.invoke()
        app.update()
    restored = on_disk()
    story.check("Restore previous puts my changes back: nothing ticked",
                [i.get("done") for i in restored.get("checklist", [])]
                == [False, False, False], restored.get("checklist"))
    story.check("...and no date, as I had left it",
                not restored.get("date"), restored.get("date"))
    story.check("...on screen too, not only in the file",
                not any(i.get("done") for i in
                        app.capture_editor_state().get("checklist", [])))
    question = next((t for titles in asked for t in titles
                     if "Bring back" in t), "")
    story.check("the question named the checklist, not just the text",
                "checklist" in question, question[:90])
    _photograph("9-after-restoring")
    story.save()


def _all_children(widget, out=None):
    out = [] if out is None else out
    for child in widget.winfo_children():
        out.append(child)
        _all_children(child, out)
    return out


CHAPTERS = {1: chapter_1, 2: chapter_2, 3: chapter_3, 4: chapter_4,
            5: chapter_5, 6: chapter_6, 7: chapter_7}


if __name__ == "__main__":
    if "--chapter" in sys.argv:
        number = int(sys.argv[sys.argv.index("--chapter") + 1])
        story = None
        try:
            CHAPTERS[number]()
        except Exception:
            import traceback
            traceback.print_exc()
            io.open(RESULTS, "w", encoding="utf-8").write(json.dumps(
                [["capitolul %d a mers pana la capat" % number, False,
                  traceback.format_exc().strip().splitlines()[-1]]],
                ensure_ascii=False))
        sys.exit(0)
    sys.exit(drive())
