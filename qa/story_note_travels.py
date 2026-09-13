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
            {"id": 1, "title": "Reteta de paine", "body": "500g faina\n300ml apa",
             "category": "General", "created": "2026-09-01 09:00",
             "updated": "2026-09-01 09:00"},
            {"id": 2, "title": "De cumparat", "body": "lapte\noua",
             "category": "General", "created": "2026-09-02 09:00",
             "updated": "2026-09-02 09:00"},
        ], indent=2))
    io.open(os.path.join(work, "settings.json"), "w", encoding="utf-8").write(
        json.dumps({"cleanup_done": True, "reclaimed_from_appdata": True}))

    print("povestea se joaca in: %s" % work)
    print()

    chapters = [
        (1, "Fac un cod pentru o notita, din editor"),
        (2, "Inchid aplicatia, o redeschid, editez notita si aduc codul inapoi"),
        (3, "Generez un cod si trec la alta notita"),
        (4, "Sterg o notita si ma intorc in Settings"),
    ]
    results = []
    for number, title in chapters:
        print("--- capitolul %d: %s" % (number, title))
        run = subprocess.run(
            [sys.executable, "story_note_travels.py", "--chapter", str(number)],
            cwd=work, capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        found = _read_results(work)
        results.extend(found)
        for name, ok, detail in found:
            print("    %s %s%s" % ("PASS" if ok else "FAIL", name,
                                   "" if ok else "   <- %s" % detail))
        if not found:
            print("    CAPITOLUL NU A SPUS NIMIC (a crapat?)")
            tail = (run.stdout + run.stderr).strip().splitlines()[-6:]
            for line in tail:
                print("      | %s" % line)
            results.append(("capitolul %d a rulat" % number, False, "fara rezultate"))
        _clear_results(work)

    print()
    shot_files = sorted(os.path.join(shots, f) for f in os.listdir(shots))
    for path in shot_files:
        print("poza: %s" % path)
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

    story.check("notita se deschide cand dau click pe ea in lista",
                _open_note_by_clicking(app, "Reteta de paine"))

    generate = _button(app, "Generate code")
    story.check("butonul 'Generate code' e acolo, in editor", generate is not None)
    if generate is not None:
        generate.invoke()
        app.update()

    shown = app.editor_code_area.winfo_ismapped()
    story.check("codul apare sub notita", shown)
    code = ""
    if shown:
        widget = _text_widget(app.editor_code_area)
        if widget is not None:
            code = widget.get("1.0", "end-1c").strip()
    story.check("codul arata a cod de partajare", code.startswith("NOTE1"),
                code[:20])
    io.open(CODE_FILE, "w", encoding="utf-8").write(code)
    _photograph("1-codul-facut-in-editor")
    story.save()


def chapter_2():
    """A NEW PROCESS: the app was closed and opened again. She edits the
    note, then brings the code back."""
    tk, NO, app = _chapter_setup()
    story = Chapter()
    code = io.open(CODE_FILE, encoding="utf-8").read().strip()

    _open_note_by_clicking(app, "Reteta de paine")
    app.body_text.insert("end", "\n-- schimbat dupa ce am inchis aplicatia")
    save = _button(app, "Save")
    if save is not None:
        save.invoke()
    app.update()

    imported = _button(app, "Import code")
    story.check("butonul 'Import code' e in bara laterala", imported is not None)
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
        _photograph("2-ce-ma-intreaba-la-import")
        for label in ("Update this note", "Open it anyway", "Cancel"):
            if _click_dialog(app, label):
                seen["answered"] = label
                return
    app.wait_variable = answer_the_dialog

    go = _button(app, "Import", exact=True)
    story.check("butonul 'Import' e in panou", go is not None)
    if go is not None:
        go.invoke()
        app.update()

    titles = seen["titles"]
    asked_about_the_note = any("Same note" in t for t in titles)
    story.check("ma intreaba despre NOTITA MEA, nu despre un duplicat",
                asked_about_the_note,
                "pe ecran scria: %s" % [t[:45] for t in titles if t][:3])
    story.check("si raspunsul pe care il vreau e acolo de apasat",
                seen["answered"] == "Update this note",
                "am putut apasa doar: %r" % seen["answered"])

    notes = json.load(io.open("notes_data.json", encoding="utf-8"))
    story.check("nu mi-a aparut o a doua copie a notitei",
                len([n for n in notes if "Reteta" in (n.get("title") or "")]) == 1,
                "titluri: %s" % [n.get("title") for n in notes])
    mine = next((n for n in notes if "Reteta" in (n.get("title") or "")), {})
    story.check("notita arata versiunea adusa de cod",
                "schimbat dupa ce am inchis" not in (mine.get("body") or ""),
                (mine.get("body") or "")[:60])

    # And what happens NEXT: she carries on typing, which saves.
    app.body_text.insert("end", " ")
    app._flush_autosave()
    app.update()
    notes = json.load(io.open("notes_data.json", encoding="utf-8"))
    mine = next((n for n in notes if "Reteta" in (n.get("title") or "")), {})
    story.check("...si ramane asa dupa ce scriu mai departe",
                "schimbat dupa ce am inchis" not in (mine.get("body") or ""),
                (mine.get("body") or "")[:60])
    _photograph("3-dupa-actualizare")
    story.save()


def chapter_3():
    """She makes a code, then goes to another note."""
    tk, NO, app = _chapter_setup()
    story = Chapter()

    _open_note_by_clicking(app, "De cumparat")
    generate = _button(app, "Generate code")
    if generate is not None:
        generate.invoke()
        app.update()
    story.check("codul e pe ecran pentru notita la care sunt",
                app.editor_code_area.winfo_ismapped())

    _open_note_by_clicking(app, "Reteta de paine")
    _photograph("4-dupa-ce-am-trecut-la-alta-notita")
    story.check("codul NU mai e pe ecran la notita urmatoare",
                not app.editor_code_area.winfo_ismapped(),
                "a ramas codul notitei dinainte")
    story.save()


def chapter_4():
    """She deletes a note and comes back to Settings."""
    tk, NO, app = _chapter_setup()
    story = Chapter()

    settings = _button(app, "Settings")
    story.check("butonul 'Settings' e in bara laterala", settings is not None)
    if settings is not None:
        settings.invoke()
        app.update()
    app.toggle_settings_panel("trash")
    app.update()
    app.hide_settings_page()
    app.update()

    _open_note_by_clicking(app, "De cumparat")
    delete = _button(app, "Delete")
    story.check("butonul de stergere e in editor", delete is not None)
    if delete is not None:
        delete.invoke()
        app.update()

    if settings is not None:
        settings.invoke()
        app.update()
    _photograph("5-cosul-dupa-ce-am-sters")

    def labels(widget, out):
        for child in widget.winfo_children():
            if isinstance(child, tk.Label):
                out.append(str(child.cget("text")))
            labels(child, out)
        return out

    shown = labels(app.settings_trash_panel, [])
    story.check("notita stearsa e in cos cand ajung acolo",
                any("De cumparat" in t for t in shown),
                "in cos scrie: %s" % [t[:30] for t in shown if t][:4])
    story.save()


CHAPTERS = {1: chapter_1, 2: chapter_2, 3: chapter_3, 4: chapter_4}


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
