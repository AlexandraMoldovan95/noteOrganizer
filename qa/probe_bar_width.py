"""What does the selection bar ask for, on whatever system runs this?

Not a check -- a measuring tape. The bar's four actions have to fit a
fixed-width sidebar, and the fonts they are drawn in differ between
Windows and the Linux CI image (DejaVu). A layout that fits on one and
not the other is not a layout, it is a coincidence, so the numbers get
printed on both rather than assumed from one.

    py qa/probe_bar_width.py
    docker run --rm -v "${PWD}:/repo:ro" noteorg-linux-ci probe_bar_width
"""
import io
import json
import os
import sys

import tkinter as tk

if os.path.exists("notes_data.json"):
    prev = json.load(io.open("notes_data.json", encoding="utf-8"))
    if isinstance(prev, list) and prev:
        sys.exit("REFUSING: notes_data.json here holds %d real note(s)."
                 % len(prev))
io.open("notes_data.json", "w", encoding="utf-8").write("[]")
io.open("settings.json", "w", encoding="utf-8").write(
    json.dumps({"reclaimed_from_appdata": True}))

import note_organizer as NO

# The window's resize freeze asks Windows whether the mouse button is down,
# anywhere on the desktop, and lays nothing out while it is: a click held in
# another program would leave the widths below measured before the layout.
# The qa suite pins the same answer (_qa_support's pin_the_desktop).
if hasattr(NO.NoteOrganizer, '_pointer_button_held'):
    NO.NoteOrganizer._pointer_button_held = lambda self: False

app = NO.NoteOrganizer()
app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.geometry("1100x850")
app.update()

app.notes = [NO.normalize_note({"id": 1, "title": "One", "body": "b",
                                "category": "General"})]
app.save_notes()
app.refresh_note_list()
app.update()
if not app.selection_mode:
    app._toggle_selection_mode()
app.update()
app.update_idletasks()

bar = app.bulk_action_bar
print()
print("platform: %s" % sys.platform)
print("sidebar %d px, bar given %d px, bar asks %d px"
      % (app.sidebar.winfo_width(), bar.winfo_width(), bar.winfo_reqwidth()))


def buttons(widget, out=None):
    out = [] if out is None else out
    for child in widget.winfo_children():
        if isinstance(child, tk.Button):
            out.append(child)
        buttons(child, out)
    return out


total = 0
for btn in buttons(bar):
    total += btn.winfo_reqwidth()
    print("  %-18s asks %3d  drawn %3d%s"
          % (str(btn.cget("text")), btn.winfo_reqwidth(), btn.winfo_width(),
             "   <-- CUT" if btn.winfo_width() < btn.winfo_reqwidth() else ""))
print("  four actions ask %d px between them" % total)
app.destroy()
