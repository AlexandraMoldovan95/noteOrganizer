# User Guide

A full walkthrough of Note Organizer — what it does, and how to use it. Screenshots are marked with placeholders; see [Adding your own screenshots](#adding-your-own-screenshots) at the bottom for where to drop them in.

---

## Getting started

Note Organizer runs as a single window with three tabs: **Notes**, **Calendar**, and **Settings**. Everything is stored locally, next to the app — there's no account to create and no internet connection required.

![Main window](screenshots/main-window.png)

---

## Notes

### Creating and editing

Click **+ New Note** in the sidebar to open a blank editor. A note has a title, a body, optional comments, a category, an optional date, an optional color, and an optional checklist. There's only ever one editor open at a time — clicking a different note in the list automatically saves whatever you were working on first, so there's no tab-juggling and no risk of losing an edit.

![Note editor](screenshots/note-editor.png)

Notes save automatically a moment after you stop typing (look for the "Auto-saved" status), and always save immediately when you switch to a different note.

### Organizing

- **Pin** a note (right-click → Pin) to keep it at the top of the list regardless of sort order.
- **Duplicate** a note to create an editable copy, titled "(copy)".
- **Categories** act as folders — create, rename, recolor, or delete them from Settings → Manage categories. Deleting a category with notes in it asks where to move them first; nothing is ever silently lost.
- **Group by category** (checkbox above the note list) clusters the list under collapsible category headers.
- **Search** the note list by keyword, and **sort** by recency, title, category, or date.

![Categories panel](screenshots/categories-panel.png)

### Checklists

Any note can have a checklist. Click **☑ Checklist** in the editor to open it, add items, and check them off as you go — the note's card in the list shows progress at a glance (e.g. "☑ 2/5").

### Templates

Save any note as a reusable template (📋 **Save as template**), or build one from scratch in Settings → Manage templates. Starting a new note with **Use template** fills in the title, body, category, and checklist from the template — the template itself is never affected by what you do with the note afterward.

![Templates panel](screenshots/templates-panel.png)

### Trash

Deleting a note moves it to **Recently deleted** (Settings), where it's recoverable for a configurable retention window before being purged automatically. Restore individual notes, delete them permanently one at a time, or empty the whole trash at once.

### Finding & cleaning up duplicates

Settings → **Clean up duplicates** groups notes that match on title, body, comments, and category. Within a group, tick specific copies to remove (the rest are kept — nothing forces "keep exactly one"), or use **Clean up ALL groups** to apply "keep the first, remove the rest" across every group in one click.

![Duplicates panel](screenshots/duplicates-panel.png)

---

## Recurring notes

Any note can repeat. Open the **Repeat** section in the editor and choose:

- **Daily**, with a custom interval (every N days)
- **Weekly**, on specific weekdays
- **Monthly**, on specific days of the month — with a choice of what happens in shorter months (e.g. a note set for "the 31st": either land on that month's *last* day, or be *skipped* entirely that month)
- **Yearly**, on a specific date

Set an end condition if the note shouldn't repeat forever: after a number of occurrences, or by a specific date.

![Recurrence setup](screenshots/recurrence-setup.png)

Editing or deleting one specific occurrence (rather than the whole series) is always offered as a separate choice — your edit only applies where you meant it to.

---

## Calendar

The Calendar tab shows every note (including every occurrence of every recurring note) on the day it falls on. Navigate month-to-month, jump directly to a specific month/year, or return to today. Multiple notes on one day show up to two title previews plus a "+N more" indicator; hovering a day gives a quick summary.

![Calendar view](screenshots/calendar-view.png)

You can also paint a specific calendar day a custom color (right-click it), independent of any note's own color — useful for marking something about the day itself, like a holiday or deadline.

---

## Sharing & backup

**Share a note as a code**: open a note → Copy code. This generates a compact block of text representing that note's content (not its attachments) — paste it to someone else, and they can import it with **Import code** in the sidebar. You can also select several notes at once and generate one code covering all of them.

**Full backup**: Settings → Export notes creates a single `.zip` containing every note, your settings, and every attachment — the one file you need to move everything to another device. Import it there with Settings → Import notes. Both directions check for notes that look identical to ones you already have, and ask before creating duplicates.

![Share panel](screenshots/share-panel.png)

---

## Appearance

Switch between Dark and Light mode, and pick from four variants of each, in Settings → Appearance. The choice is remembered the next time you open the app.

![Theme picker](screenshots/theme-picker.png)

---

## Adding your own screenshots

Drop image files into `docs/screenshots/` using the filenames referenced above (e.g. `main-window.png`, `note-editor.png`). Once a file exists at that path, it will render automatically wherever this guide references it — no other changes needed.
