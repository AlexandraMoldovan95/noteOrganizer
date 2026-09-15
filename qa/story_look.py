"""Photograph the app's screens, and say what MOVED since last time.

WHY THIS EXISTS
---------------
The suite answers questions. The stories walk paths. Neither can see a
screen that simply stopped looking right: a control clipped, a panel
sliding under another one, a colour that stayed behind after a theme
switch. Twice in this project a bug was invisible in the source and
obvious in a photograph, and both times a person had to be looking.

This takes the photographs itself and compares them with the ones from
the last run. What it reports is not "this is wrong" -- it cannot know
that -- but "this changed, and nobody said it would". A change you asked
for is approved by running with ``--accept``; anything else is worth a
look before it ships.

WHAT IT IS NOT
--------------
It is not a pixel-perfect gate. Text rendering shifts by a pixel between
runs for reasons nobody controls, so a tiny difference is noise and is
reported as such. It answers one question honestly: did a screen change
shape while we were not looking?

    py qa/story_look.py            # compare against the stored shots
    py qa/story_look.py --accept   # bless what is on screen now

The stored shots live in qa/screens/ and are meant to be committed, so a
change of appearance shows up in a diff like any other change.
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STORE = os.path.join(HERE, "screens")

# Each scene: a name, and what to do to the app before the picture.
SCENES = [
    ("01-note-list", """
app.notebook.select(app.TAB_NOTES)
app.refresh_note_list()
"""),
    ("02-editor", """
app.notebook.select(app.TAB_NOTES)
app.load_note(app.notes[0])
"""),
    ("03-calendar", """
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 9
app.render_calendar()
"""),
    ("04-settings-trash", """
app.show_settings_page()
app.toggle_settings_panel('trash')
"""),
    ("05-settings-categories", """
app.show_settings_page()
app.toggle_settings_panel('categories')
"""),
    ("06-light-theme", """
app.hide_settings_page()
app.notebook.select(app.TAB_NOTES)
app.set_theme(NO.LIGHT_THEMES[0])
app.refresh_note_list()
"""),
]

SEED = [
    # English, like the app's own interface, and with real line breaks.
    # Both were wrong: the notes were Romanian, and each body held a
    # backslash followed by an n rather than the newline it stood for --
    # so a note meant to be three lines was drawn across one, with the
    # backslashes showing.
    # The language gate did not catch the first, because none of those
    # words are in its list. It is a net, not a proof, and says so.
    {"id": 1, "title": "Bread recipe",
     "body": "500g flour\n300ml water\n10g salt",
     "category": "General", "date": "2026-09-15",
     "checklist": [{"text": "kneaded", "done": True},
                   {"text": "baked", "done": False}],
     "created": "2026-09-01 09:00", "updated": "2026-09-01 09:00"},
    {"id": 2, "title": "Shopping", "body": "milk\neggs\nbread",
     "category": "General", "created": "2026-09-02 09:00",
     "updated": "2026-09-02 09:00"},
    {"id": 3, "title": "", "body": "a note with no title, as in a real notebook",
     "category": "General", "created": "2026-09-03 09:00",
     "updated": "2026-09-03 09:00"},
]

SHOOTER = '''
import io, json, os, subprocess, sys, time
sys.path.insert(0, ".")
import note_organizer as NO, tkinter as tk
from _qa_support import pin_popup_visibility
pin_popup_visibility(NO)

app = NO.NoteOrganizer()
app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.ask_yes_no = lambda *a, **k: True
app.geometry("1150x820+60+60")
app.update()
# Raised and kept on top before anything is photographed. The grab copies
# from the SCREEN at the window's coordinates, so whatever is in front is
# what gets saved -- and these pictures are committed.
app.lift()
app.attributes("-topmost", True)
app.focus_force()

# PowerShell's CopyFromScreen works in PHYSICAL pixels; Tk reports its
# geometry in LOGICAL ones. On a display with any scaling the two differ,
# and a box built from Tk's numbers lands up and to the left of the
# window: the reference screens carried a strip of the developer's own
# desktop down their left edge, and lost the right edge of the app.
# Measured once, here, rather than assumed to be 1.
from PIL import ImageGrab as _Grab
SCALE = _Grab.grab().size[0] / float(app.winfo_screenwidth())

scenes = json.load(io.open("scenes.json", encoding="utf-8"))
for name, script in scenes:
    exec(script)
    app.update()
    app.update_idletasks()
    time.sleep(0.4)
    app.lift()
    app.attributes("-topmost", True)
    app.update()
    x = int(round(app.winfo_rootx() * SCALE))
    y = int(round(app.winfo_rooty() * SCALE))
    w = int(round(app.winfo_width() * SCALE))
    h = int(round(app.winfo_height() * SCALE))
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", "grab.ps1", "-Out", os.path.join("shots", name + ".png"),
                    "-X", str(x), "-Y", str(y), "-W", str(w), "-H", str(h)],
                   capture_output=True)
app.destroy()
'''

GRAB = """param([string]$Out, [int]$X, [int]$Y, [int]$W, [int]$H)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bmp = New-Object System.Drawing.Bitmap($W, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen((New-Object System.Drawing.Point($X, $Y)),
                  [System.Drawing.Point]::Empty,
                  (New-Object System.Drawing.Size($W, $H)))
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
"""


def take_the_pictures():
    """Run the app in a scratch copy and photograph each scene."""
    work = tempfile.mkdtemp(prefix="look-")
    os.makedirs(os.path.join(work, "shots"))
    shutil.copy2(os.path.join(ROOT, "note_organizer.py"), work)
    shutil.copytree(os.path.join(ROOT, "noteorganizer"),
                    os.path.join(work, "noteorganizer"))
    shutil.copy2(os.path.join(HERE, "_qa_support.py"), work)
    io.open(os.path.join(work, "notes_data.json"), "w", encoding="utf-8").write(
        json.dumps(SEED))
    io.open(os.path.join(work, "settings.json"), "w", encoding="utf-8").write(
        json.dumps({"cleanup_done": True, "reclaimed_from_appdata": True,
                    "theme": "Midnight"}))
    io.open(os.path.join(work, "scenes.json"), "w", encoding="utf-8").write(
        json.dumps(SCENES))
    io.open(os.path.join(work, "shoot.py"), "w", encoding="utf-8").write(SHOOTER)
    io.open(os.path.join(work, "grab.ps1"), "w", encoding="utf-8").write(GRAB)
    run = subprocess.run([sys.executable, "shoot.py"], cwd=work,
                         capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=600)
    return work, run


def compare(new_dir):
    """How much of each picture changed, as a percentage of its pixels.

    Deliberately coarse: images are reduced to a small grid and compared
    cell by cell, so a pixel of text rendering does not read as a
    change while a moved control does.
    """
    try:
        from PIL import Image
    except ImportError:
        print("Pillow is missing -- I cannot compare the pictures.")
        return None
    results = []
    for name, _script in SCENES:
        fresh = os.path.join(new_dir, name + ".png")
        stored = os.path.join(STORE, name + ".png")
        if not os.path.exists(fresh):
            results.append((name, None, "the picture was not taken"))
            continue
        if not os.path.exists(stored):
            results.append((name, None, "there is no reference picture"))
            continue
        a = Image.open(stored).convert("L").resize((160, 120))
        b = Image.open(fresh).convert("L").resize((160, 120))
        if a.size != b.size:
            results.append((name, 100.0, "a different size"))
            continue
        pa, pb = a.load(), b.load()
        moved = sum(1 for y in range(120) for x in range(160)
                    if abs(pa[x, y] - pb[x, y]) > 12)
        results.append((name, moved * 100.0 / (160 * 120), ""))
    return results


def main():
    accept = "--accept" in sys.argv
    work, run = take_the_pictures()
    shots = os.path.join(work, "shots")
    taken = sorted(os.listdir(shots)) if os.path.isdir(shots) else []
    if not taken:
        print("NO PICTURES. Either the app did not start or PowerShell wrote none.")
        print((run.stdout + run.stderr)[-800:])
        shutil.rmtree(work, ignore_errors=True)
        return 2

    if accept:
        if not os.path.isdir(STORE):
            os.makedirs(STORE)
        for name in taken:
            shutil.copy2(os.path.join(shots, name), os.path.join(STORE, name))
        print("accepted: %d screen(s) are the reference from now on" % len(taken))
        shutil.rmtree(work, ignore_errors=True)
        return 0

    results = compare(shots)
    if results is None:
        shutil.rmtree(work, ignore_errors=True)
        return 2

    changed = []
    for name, pct, note in results:
        if pct is None:
            print("  ?     %-22s %s" % (name, note))
            changed.append(name)
        elif pct < 0.5:
            print("  same    %-22s (%.1f%%)" % (name, pct))
        else:
            print("  CHANGED %-16s %.1f%% of the screen %s" % (name, pct, note))
            changed.append(name)

    print()
    if changed:
        print("SCREENS CHANGED: %s" % ", ".join(changed))
        print("The new pictures are in: %s" % shots)
        print("If the change was wanted, accept it with:  py qa/story_look.py --accept")
        return 1
    print("No screen has changed its shape.")
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
