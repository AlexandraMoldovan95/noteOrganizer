# Screenshots

Every image in this folder is a capture of **this app running** — taken
here, on the build named below, by the person or the script that wrote the
line beside it. None of it comes from anywhere else, and the app's icon is
not a picture at all: it is drawn from code by
[`tools/make_icon.py`](../../tools/make_icon.py) every time the app is
built.

The images illustrate [`docs/USER_GUIDE.md`](../USER_GUIDE.md)
and [`README.md`](../../README.md). They are referenced by exact filename, so
**to replace or add one, drop a PNG here using the filename below** — it then
renders automatically everywhere the docs reference it, no other change needed.

## They are taken by a script, not by hand

    py tools/doc_screenshots.py            # every scene
    py tools/doc_screenshots.py tables     # just one

Run it from a scratch copy, never in place -- the qa safety rule applies
here too, and the script refuses to start beside a `notes_data.json` that
holds real notes.

Every picture in the table below has a scene in that file which stages it
deliberately: it writes a small notebook of its own, opens the panel,
ticks what needs ticking, and photographs the result. Before 2026-09-14
only three did, and the other nineteen were taken by hand on a real
notebook -- which showed, in the pictures: a sidebar counting "General
(71)", notes titled "3" and "5", a Duplicates panel announcing
thirty-three groups. Nothing private was legible, but nothing was chosen
either.

Three things the script does that a careful hand cannot promise:

- **It refuses to photograph a covered window.** Before each shutter it
  asks, at forty-nine points across the frame, which window is actually
  on top there; a window from another program means the shot is not
  taken. An Android emulator sat in the middle of nineteen pictures on
  the first full run, and a browser did it once before that.
- **A crop can never leave the window.** The checklist shot came back
  with the Windows taskbar along its bottom edge. A picture of this app
  is made only of pixels belonging to this app.
- **It puts the screen back between scenes**, not just the notebook. A
  scene that searched for "team" left every later sidebar reading "No
  notes match your search or filter" -- including the hero shot.

Rules that keep the set reading as one app:

- **The current app on screen** — window title **Note Organizer**, current UI
  (the ☀/🌙 theme button visible where a capture includes the toolbar).
- **One theme throughout** — a partial refresh in another theme silently
  produces a mixed set.

**Current set:** retaken 2026-09-15 in the default dark (purple) theme, all
twenty-two by `tools/doc_screenshots.py`, on app version 0.73.167; update
this line whenever the set is recaptured.

| Filename | What to capture |
|---|---|
| `main-window.png` | The main window, Notes tab: sidebar, a note open with a table, and the full formatting toolbar including the ☀/🌙 theme button at its right end |
| `note-editor.png` | A note open in the editor with some content, the toolbar, and the Checklist + Calculator bars below |
| `formatting-toolbar.png` | The formatting toolbar close-up, with bold/italic/coloured/highlighted text in the body — and the ☀/🌙 theme button visible at the right end |
| `tables.png` | A table in a note with a highlighted header row (ideally a checkbox cell and a "Tab. N" caption too) |
| `attachments.png` | The attachments section of a note with at least one file attached |
| `checklist.png` | The checklist open beside the calculator, with a mix of checked and unchecked items and the Expand bar |
| `calculator.png` | The calculator open, with an expression entered and the history showing a calculation |
| `emoji-picker.png` | The emoji picker open over a text field |
| `search-and-sort.png` | The search box and sort dropdown, ideally mid-search |
| `grouped-notes.png` | The note list with "Group by category" on, showing at least two groups (one collapsed, one expanded, if possible) |
| `categories-panel.png` | Settings → Categories, with a few categories listed |
| `templates-panel.png` | Settings → Templates, with at least one template listed |
| `trash-panel.png` | Settings → Recently deleted, showing the "Keep deleted notes for" (7–90 days) selector and a few entries |
| `duplicates-panel.png` | Settings → Duplicates, with at least one group showing |
| `recurrence-setup.png` | The Repeat section of the editor, mid-setup (e.g. Weekly with a couple of days picked) |
| `calendar-view.png` | The Calendar tab, a month with a few notes visible on different days |
| `calendar-day-color.png` | The right-click menu / result of painting a calendar day a custom color |
| `share-panel.png` | The Share notes panel with a couple of notes ticked |
| `import-code.png` | The Import code panel, ideally showing the duplicate-check prompt |
| `import-backup.png` | The Import notes file picker or its resulting confirmation |
| `settings-overview.png` | The Settings page: the section list on the left and a section open on the right |
| `theme-picker.png` | Settings → Appearance, with the theme variant cards visible |
