# User Guide

A full walkthrough of Note Organizer — what it does, and how to use it, with a screenshot for every major feature.

---

## Getting started

Note Organizer runs as a single window with two tabs, **Notes** and **Calendar**, plus a **Settings** page reached via its own button at the bottom of the sidebar. Everything is stored locally, next to the app — there's no account to create and no internet connection required.

![Main window](screenshots/main-window.png)

---

## Notes

### Creating and editing

Click **+ New Note** in the sidebar to open a blank editor. A note has a title, a body, optional comments, a category, an optional date, an optional color, and an optional checklist. There's only ever one editor open at a time — clicking a different note in the list automatically saves whatever you were working on first, so there's no tab-juggling and no risk of losing an edit.

![Note editor](screenshots/note-editor.png)

Notes save automatically a moment after you stop typing (look for the "Auto-saved" status), and always save immediately when you switch to a different note.

### Formatting

A small toolbar above the note body offers **Bold**, *Italic*, <u>Underline</u>, and ~~Strikethrough~~ — the same four options are also on the right-click menu, and available as keyboard shortcuts (**Ctrl+B**, **Ctrl+I**, **Ctrl+U**, **Ctrl+D**). Two ways to use them: select some text and click (or press) a style to apply it there, or click a style with nothing selected — it "sticks" for whatever you type next, until you click it again to turn it off.

![Formatting toolbar](screenshots/formatting-toolbar.png)

This is the first phase of a larger effort — font size, font family, text color, highlight color, bullet lists, and paste that keeps (or discards) formatting from wherever it was copied are all still ahead.

### Attachments

Attach one or more files to a note from the editor. Attached files show as a small list with their name and a way to remove them; click a file to open it. Removing an attachment deletes it from that note only — it doesn't touch anything else.

![Attachments](screenshots/attachments.png)

### Checklists

Any note can have a checklist. Click **☑ Checklist** in the editor to open it, add items, and check them off as you go — the note's card in the list shows progress at a glance (e.g. "☑ 2/5").

![Checklist](screenshots/checklist.png)

### Calculator

Click **🧮 Calculator** in the editor, next to Checklist, for a collapsible built-in calculator — standard arithmetic with real operator precedence, three interchangeable bracket styles, a square root, powers, and percent, either from the on-screen buttons or by typing/pasting an expression directly. Press **=** to see the result, then **Insert into note** to drop the whole formula (not just the answer) into the note body — repeated inserts stack cleanly below each other. A collapsible history keeps every calculation from the session, with a Clear button and click-to-insert on any past entry.

![Calculator](screenshots/calculator.png)

### Emoji

Any text field in a note (title, body, comments) can have an emoji inserted at the cursor via the right-click menu, without leaving the keyboard to hunt through the system emoji picker.

![Emoji picker](screenshots/emoji-picker.png)

### Finding notes: search, sort, and grouping

Search the note list by keyword, and sort by recency, title, category, or date, from the controls above the list.

![Search and sort](screenshots/search-and-sort.png)

**Group by category** (checkbox above the note list) clusters the list under collapsible category headers instead of one flat list — click a group's header to collapse or expand it; the state is remembered.

![Notes grouped by category](screenshots/grouped-notes.png)

### Organizing

- **Pin** a note (right-click → Pin) to keep it at the top of the list regardless of sort order.
- **Duplicate** a note to create an editable copy, titled "(copy)".
- **Categories** act as folders — create, rename, recolor, or delete them from Settings → Manage categories. Deleting a category with notes in it asks where to move them first; nothing is ever silently lost.

![Categories panel](screenshots/categories-panel.png)

### Templates

Save any note as a reusable template (📋 **Save as template**), or build one from scratch in Settings → Manage templates. Starting a new note with **Use template** fills in the title, body, category, and checklist from the template — the template itself is never affected by what you do with the note afterward.

![Templates panel](screenshots/templates-panel.png)

### Trash

Deleting a note moves it to **Recently deleted** (Settings), where it's recoverable for a configurable retention window before being purged automatically. Restore individual notes, delete them permanently one at a time, or empty the whole trash at once. With a lot of deleted notes, the list loads the most recent batch first, with a button to reveal more — so it stays quick to open no matter how much has accumulated there.

![Trash panel](screenshots/trash-panel.png)

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

![Calendar day coloring](screenshots/calendar-day-color.png)

---

## Sharing & backup

### Share a note as a code

Open a note → Generate code. This generates a compact block of text representing that note's content (not its attachments) — paste it to someone else, and they can import it with **Import code** in the sidebar. You can also select several notes at once and generate one code covering all of them.

![Share panel](screenshots/share-panel.png)

### Import a code

Paste a code you received into **Import code** in the sidebar. If any of the notes it contains look identical to ones you already have, you'll be asked whether to skip the duplicates, import everyone anyway, or cancel — nothing is silently duplicated.

![Import code](screenshots/import-code.png)

### Full backup: export

Settings → Export notes creates a single `.zip` containing every note, your settings, and every attachment — the one file you need to move everything to another device. With a lot of attachments this can take a moment; a progress bar stays visible at the bottom of the window the whole time, and the app remains fully usable while it works.

![Export progress](screenshots/export-progress.png)

### Full backup: import

Settings → Import notes brings a previously exported `.zip` back in — notes, settings, and attachments together. Just like importing a code, you'll be asked about any notes that look identical to what you already have before anything is added.

![Import backup](screenshots/import-backup.png)

---

## Settings

Categories, templates, trash, duplicate cleanup, appearance, your name, and usage statistics all live on one page, reached via the **⚙ Settings** button at the bottom of the sidebar. A **← Back to Notes** button at the top returns you to your notes.

![Settings overview](screenshots/settings-overview.png)

### Your name

Settings → Your name sets the greeting shown above the note list ("Hi \<name\>,"). Leave it blank for no greeting.

### Statistics

A quick snapshot of your total note count and this week's activity, with a clickable chip per category — click one to jump straight to your notes filtered to that category.

---

## Appearance

Switch between Dark and Light mode, and pick from four variants of each, in Settings → Appearance. The choice is remembered the next time you open the app.

![Theme picker](screenshots/theme-picker.png)

---

## Adding your own screenshots

Drop image files into `docs/screenshots/` using the exact filenames referenced above. Once a file exists at that path, it renders automatically wherever this guide references it — no other changes needed.

| Filename | What to capture |
|---|---|
| `main-window.png` | The main window, Notes tab, with a few notes in the list |
| `note-editor.png` | A note open in the editor, with some content filled in |
| `formatting-toolbar.png` | The formatting toolbar, with a mix of bold/italic/underlined/struck-through text visible in the body |
| `attachments.png` | The attachments section of a note with at least one file attached |
| `checklist.png` | The checklist section open, with a mix of checked and unchecked items |
| `calculator.png` | The calculator section open, with an expression entered and its result inserted into the note |
| `emoji-picker.png` | The emoji picker open over a text field |
| `search-and-sort.png` | The search box and sort dropdown, ideally mid-search |
| `grouped-notes.png` | The note list with "Group by category" on, showing at least two groups (one collapsed, one expanded, if possible) |
| `categories-panel.png` | Settings → Manage categories, with a few categories listed |
| `templates-panel.png` | Settings → Manage templates, with at least one template listed |
| `trash-panel.png` | Settings → Recently deleted, with a few entries |
| `duplicates-panel.png` | Settings → Clean up duplicates, with at least one group showing |
| `recurrence-setup.png` | The Repeat section of the editor, mid-setup (e.g. Weekly with a couple of days picked) |
| `calendar-view.png` | The Calendar tab, a month with a few notes visible on different days |
| `calendar-day-color.png` | The right-click menu / result of painting a calendar day a custom color |
| `share-panel.png` | The Share notes panel with a couple of notes ticked |
| `import-code.png` | The Import code panel, ideally showing the duplicate-check prompt |
| `export-progress.png` | The export progress bar visible at the bottom of the window mid-export |
| `import-backup.png` | The Import notes file picker or its resulting confirmation |
| `settings-overview.png` | The full Settings page, scrolled to show several sections |
| `theme-picker.png` | Settings → Appearance, with the theme variant cards visible |
