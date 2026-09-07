# User Guide

[← Back to the README](../README.md)

A full walkthrough of Note Organizer — what it does, and how to use it, with a screenshot for
every major feature.

## Contents

- [Getting started](#getting-started)
- [Notes](#notes)
  - [Creating and editing](#creating-and-editing)
  - [Formatting](#formatting)
  - [Pasting and copying](#pasting-and-copying)
  - [Tables](#tables)
  - [Attachments](#attachments)
  - [Checklists](#checklists)
  - [Calculator](#calculator)
  - [Emoji](#emoji)
  - [How long a note takes to read](#how-long-a-note-takes-to-read)
  - [Finding notes: search, sort, and grouping](#finding-notes-search-sort-and-grouping)
  - [Organizing](#organizing)
  - [Templates](#templates)
  - [Trash](#trash)
  - [Finding & cleaning up duplicates](#finding--cleaning-up-duplicates)
- [Recurring notes](#recurring-notes)
- [Calendar](#calendar)
- [Sharing & backup](#sharing--backup)
  - [Share a note as a code](#share-a-note-as-a-code)
  - [Import a code](#import-a-code)
  - [Export one note as a file](#export-one-note-as-a-file)
  - [Full backup: export](#full-backup-export)
  - [Full backup: import](#full-backup-import)
- [Settings](#settings)
  - [Your name](#your-name)
  - [Statistics](#statistics)
  - [Keyboard shortcuts](#keyboard-shortcuts)
  - [Appearance](#appearance)

---

## Getting started

Note Organizer runs as a single window with two tabs, **Notes** and **Calendar**, plus a
**Settings** page reached via its own button at the bottom of the sidebar. Everything is stored
locally on your own computer — there's no account to create and no internet connection required.
Run from source, the data folder sits next to the script; the installed app keeps it per-user
under `%APPDATA%\NoteOrganizer` (worth knowing if you ever go looking for your notes folder).

![Main window](screenshots/main-window.png)

---

## Notes

### Creating and editing

Click **+ New Note** in the sidebar to open a blank editor. A note has a title, a body, optional
comments, a category, an optional date, an optional colour, and an optional checklist. There's only
ever one editor open at a time — clicking a different note in the list automatically saves
whatever you were working on first, so there's no tab-juggling and no risk of losing an edit.

![Note editor](screenshots/note-editor.png)

Notes save automatically a moment after you stop typing (look for the "Auto-saved" status), and
always save immediately when you switch to a different note. Closing the app works the same way:
anything still unsaved is saved on the way out, silently — no "unsaved changes" question, because
there is nothing to lose.

The one exception is editing a single day of a repeating note (opened from the calendar): saving
that needs an answer — "this occurrence or the whole series?" — and the app never asks questions
on its own while you type. Your edits wait in the editor, and the question comes when *you* act:
pressing Save, switching notes, or closing the app. Answer it and the edit is saved where you
chose; cancel it and the edit stays only as long as you stay on that view.

The writing area starts at twelve lines. **Expand**, underneath it, makes it roughly twice as tall
for a long note, and **Collapse** puts it back — the note itself is unaffected either way, only
how much of it you can see at once. The buttons at the bottom of the editor do not go out of
reach; the page simply gets longer and scrolls. The app remembers which you chose. The comments
box has the same toggle, though it always opens small. Comments are plain text only — pasting a
table there keeps the words and drops the table (tables live in the body, which draws them as a
real grid), with a brief note telling you it happened.

For the quick light/dark switch at the end of the formatting toolbar, see
[Appearance](#appearance).

### Formatting

A small toolbar above the note body is split into four groups, separated by thin dividers. If the
window is too narrow to hold them all on one line, the toolbar wraps onto a second rather than
hiding anything.

- The first three — the style toggles, the font dropdowns, and the two colour buttons — change the
  characters you select. The last changes whole lines.
- Hover any button and it tells you what it does.
- **Style**: **Bold**, *Italic*, <u>Underline</u>, and ~~Strikethrough~~ — also on the right-click
  menu, and available as keyboard shortcuts (**Ctrl+B**, **Ctrl+I**, **Ctrl+U**, **Ctrl+D**).
- **Colours**: text colour and highlight, each opening a small swatch picker (no hex codes to type —
  just pick a colour) with a Clear option to remove it again.
- All six work the same way: select some text and click (or press) one to apply it there, or click
  one with nothing selected — it "sticks" for whatever you type next, until you click it again to
  turn it off.
- Text colour and highlight can be combined with each other and with any of the four styles.

![Formatting toolbar](screenshots/formatting-toolbar.png)

**Paragraph** applies to whole lines — whichever lines your cursor or selection touches, so you
don't need to select a line exactly.

- **Lists.** The **•** and **1.** buttons turn those lines into a bullet or numbered list. Click
  the same button again to turn the list off. Press **Enter** to start the next item; press it on
  an item you haven't typed anything into and the list ends there. **Backspace** with the cursor
  just after a marker removes the marker rather than deleting it one character at a time.
- **Nesting.** **Tab** pushes a list item one level in, **Shift+Tab** pulls it back out — or use
  the **⇤** and **⇥** buttons. A numbered sub-list counts from 1 again under each parent, and
  picks the outer numbering back up when it ends. Bullets change shape as they go deeper
  (•, ◦, ▪). Outside a list, Tab still types a tab; the two indent buttons work on any paragraph,
  list or not, up to eight levels.
- **Alignment.** The three bar icons set a line left, centred, or right. Clicking the alignment a
  line already has puts it back to left.

These combine: a bullet can be centred, an indented paragraph can be right-aligned, and any of it
can carry bold or a text colour.

List markers are part of the note's own text — a bullet really is a "• " at the start of the line.

*Why: it means a list still looks like a list when you export the note, share it as a code, or
paste it into an email.*

The indenting is drawn by the app on top of that.

**Font** sets the typeface and size. Pick from either dropdown to change the selected text, or
pick with nothing selected and it applies to whatever you type next — the same way the Style
buttons work.

- **Default** means "no setting of its own", so that text follows whatever the editor's default
  is. It is how you undo a size or a typeface, rather than setting it back by hand.
- If you select text that mixes two sizes, the dropdown shows **Default** rather than picking one
  of them.

  *Why: otherwise it would look like the whole selection was already that size.*

- The eight typefaces are ones that come with Windows.

  *Why: if a note used a font the person you send it to doesn't have, their computer would quietly
  swap in a different one and nothing would say so.*

**To make everything bigger**, don't format each note — go to **Settings → Appearance** and set
**Editor font** and **Text size**. That is the size notes start at; anything you set from the
toolbar overrides it just for that text. This is the setting to reach for if the default is simply
too small to read comfortably.

A title can be up to 200 characters.

*Why: that is far more than a title needs, and it keeps the field quick to type in — a very long
one makes the box itself sluggish.*

You do not have to count: once you are within 40 characters of the limit, a small counter appears
beside the title (`175/200`) and turns red when it is full. Pasting something longer shortens it
to fit rather than refusing it. Titles saved before this limit existed are left exactly as they
are, however long they are.

### Pasting and copying

Copy something from a web page, an email or Word, paste it into a note with **Ctrl+V**, and the
bold, the colours and the lists come with it.

- **Ctrl+Shift+V** pastes the words on their own, with none of the styling — and no bullets
  either, even when the thing you copied from puts bullet characters into its own plain-text
  version. There is a **Paste without formatting** entry on the right-click menu too.
- Copying works the same way outwards: select part of a note, copy it, and paste it into an email
  or a document, and it arrives still formatted. Copying between two notes keeps everything.

Pasting from a PDF is a special case, because a PDF has no paragraphs — only lines placed on a
page. Pasting those as they come gives a note broken into narrow ragged lines a third of the way
across. They are rejoined instead, using where each line ends to work out which breaks the page
forced and which the writer meant: a line ending mid-sentence was broken by the column, a line
falling well short of the others ended on purpose, and an indented first line says outright where
a paragraph starts. It is worked out rather than known, so it is occasionally wrong — always by
joining two paragraphs into one, never by cutting a sentence in half. Lists, addresses and poems
are left exactly as they came.

Colours are treated carefully. If you copy from a site in dark mode, you get its words, its bold
and its lists — not its dark background and pale text, which would be unreadable in your note. A
colour comes through when it was clearly a choice, like a red warning or a yellow highlight;
greys, blacks and whites are the page's own styling and are left behind.

Not every kind of styling can survive. A note can be bold, italic, underlined, struck through,
coloured, highlighted, set in one of eight fonts, made into a list, indented and aligned. Anything
a web page does beyond that — a heading style, a box, a background image — is dropped and its
words kept, rather than being turned into an approximation of itself. Font sizes and typefaces
from a web page are dropped for the same reason.

*Why: the page is almost certainly using something this app does not offer, and picking the
nearest one would claim the note is set in something it never was.*

### Tables

The table button on the toolbar opens a small size grid — sweep across it to choose how many rows
and columns, and a table appears at the cursor with the first cell ready to type into. (Tables
start at two columns: a single-column row of pipes reads as ordinary text, not a table, so the
picker never offers one.)

![A table in a note, with a highlighted header row](screenshots/tables.png)

A table works the way a spreadsheet has taught your hands to expect:

| Key | Inside a table |
| --- | --- |
| **Tab** | Moves to the next cell, and is one way to leave the cell you are typing in. On the very last cell it adds a fresh row, so a whole table can be filled without touching the mouse. |
| **Shift+Tab** | Goes back to the previous cell. |
| **Enter** (or **Shift+Enter**) | Starts a new line *inside* the cell — the whole row grows to fit, on screen the moment you press it, so nothing below is ever covered. Stored as Markdown's own `<br>`, so export still round-trips. |
| **Escape** | Leaves the cell (clicking anywhere else works too). |
| **Delete** | Clears the selected block of cells. |
| **Ctrl+A** | Selects the whole cell. |

- A table wider than the editor gets its own horizontal scrollbar, drawn just underneath it.
- **Click** any cell to edit it. **Drag** across cells to select a block of them — a firm drag
  *inside* one cell selects just that cell; drag toward an edge and the view scrolls along with
  you, so a selection can reach cells that started off screen — then **Ctrl+C** copies it and
  **Ctrl+V** somewhere else pastes it in the same shape.
- Copying works with the outside world in both directions: cells copied here paste into Excel as
  cells and into Word as a real table with visible borders, and a table copied from Excel or a web
  page lands here as a real table.
- **Right-click** a cell for everything else — the everyday actions sit on top, and **Align cell /
  Rows / Columns / Merge / Table** each hold their group one hover away.
- Under **Table** lives **Add caption below…**: a centred, auto-numbered "Table N: description"
  label (typing replaces the selected placeholder) plus a "Source:" line for links and sources —
  plain, editable body text ever after, so the wording is yours to change.
- The full set: merge the selected cells into one (their texts join), split a merge back apart,
  insert or delete rows and columns, duplicate whole columns to the end of the table (and whole
  rows to the bottom), insert a **checkbox** (with its own colour palette) or an emoji, and
  highlight cells from a small colour palette.
- A checkbox is a real little box, not text: **click it to tick and untick it** — for marking when
  a row's condition is met, a habit done, anything you invent. It is stored as Markdown's own task
  syntax (`[ ]` / `[x]`), so it survives share codes as readable text; the exported page draws it
  as a real box (☑ / ☐), and importing that page back turns the boxes into clickable checkboxes
  again. To turn that cell back into words, right-click it and choose **Edit cell as text**,
  delete the marker, and type.
- **Drag the line between two columns** to make a column wider or narrower; **double-click** the
  line to snap the column to its content. With several columns selected, **Autofit column
  width(s)** in the right-click menu snaps them all at once. **Drag the line between two rows** up
  or down to make a row taller or shorter — the whole row resizes together, and a drag can never
  cut into text a cell actually holds. Narrowing below the content only shortens what is *drawn*
  (with an `…`) — the text itself is never cut.
- **Hide a column** by selecting it top to bottom and right-clicking — it shrinks to a thin
  sliver, and right-clicking the sliver brings it back. Hiding only ever works on a fully selected
  column, so it is always clear what is about to disappear. A hidden column stays hidden in the
  exported page and in cells copied to Word, too — the data itself never leaves the note, so
  unhiding brings it straight back.
- **Ctrl+Z understands tables**: one undo takes back one whole operation — a cell edit, a resize,
  a fill, a dropped checkbox — never half of one, and the drawn table follows the text every step.
- The **formatting toolbar works inside tables** too: select cells and Bold, colours and
  highlights apply to them whole.
- With a cell *open*, the toolbar styles just the part you selected inside it — a single word,
  letter, or emoji can carry its own colour — and the open cell shows its colours while you edit,
  not after. Typing continues the style it lands beside: adding to a blue word stays blue.
- Pick a colour with nothing selected and it becomes the *active* colour — the toolbar button
  wears it as a swatch so you can see what you are writing with — and everything you type next, in
  a cell or in the note body, comes out in that colour until you pick another or click the same
  colour off.
- The alignment buttons align the text inside the selected cells; to move the *table itself*,
  right-click it and choose **Center table on page** (or left / right).

Under the hood a table is stored as plain, readable text inside the note — the same pipe-and-dash
layout Markdown uses.

*Why: search finds words inside cells, tables survive share codes, backups and export unchanged,
and a table pasted into any Markdown-aware tool arrives as a table.*

Search and the word count read a table the way you do: the pipes, dashes and markers themselves
are invisible to both, so searching "---" matches nothing and an empty table counts no words. The
bullet and numbering buttons deliberately do nothing to a table.

*Why: a table is not a list, and turning its rows into list items would break it apart.*

### Attachments

Attach one or more files to a note from the editor. Attached files show as a small list with their
name and a way to remove them; click a file to open it. Removing an attachment deletes it from
that note only — it doesn't touch anything else.

![Attachments](screenshots/attachments.png)

### Checklists

Any note can have a checklist. Click **☑ Checklist** in the editor to open it, add items, and
check them off as you go — the note's card in the list shows progress at a glance (e.g. "☑ 2/5").
The box sits beside the calculator at the same size; when a list gets long, **⤢ Expand** in its
header grows it to give more room (and it always scrolls, expanded or not). The expanded size is a
per-view choice — switching notes returns it to the compact size.

![Checklist](screenshots/checklist.png)

### Calculator

Click **🧮 Calculator** in the editor, next to Checklist, for a collapsible built-in calculator —
standard arithmetic with real operator precedence, three interchangeable bracket styles, a square
root, powers, and percent, either from the on-screen buttons or by typing/pasting an expression
directly. Press **=** to see the result, then **Insert into note** to drop the whole formula (not
just the answer) into the note body — repeated inserts stack cleanly below each other. A
collapsible history keeps every calculation from the session, with a Clear button and
click-to-insert on any past entry.

![Calculator](screenshots/calculator.png)

### Emoji

Any text field in a note (title, body, comments) can have an emoji inserted at the cursor via the
right-click menu, without leaving the keyboard to hunt through the system emoji picker.

![Emoji picker](screenshots/emoji-picker.png)

### How long a note takes to read

Under the word and character counts, each note shows roughly how long it takes to read — "under a
minute to read" for a short one, "about 4 minutes to read" for a longer one.

It is worked out from the word count at 200 words a minute, which is the slow end of normal adult
reading.

*Why: finishing sooner than promised costs you nothing, whereas being told a note is shorter than
it really is does.*

### Finding notes: search, sort, and grouping

Search the note list by keyword, and sort by recency, title, category, or date, from the controls
above the list. This is the search for finding *which* note you want, across the whole notebook.

To search *within* the note you already have open, press **Ctrl+F**. A small find bar appears in
the top-right corner of the editor — inside the window, not a separate dialog. It looks through
the note's text and its tables: type a word and every match highlights, with the current one
picked out; **Enter** and **Shift+Enter** step forward and back (wrapping around at the ends), the
count reads "3/12", and **Aa** switches on case-sensitivity. A match inside a table scrolls the
table into view and outlines the cell it's in. Find only highlights — it never changes the note —
and **Esc** or the **✕** closes the bar.

Each note's card previews its first words. A table would be pipe soup at that size, so the preview
shows only the note's plain text and the card's tag row marks the table itself — **▦ 1 table**, or
how many the note holds — next to the comment and attachment marks.

![Search and sort](screenshots/search-and-sort.png)

**Group by category** (checkbox above the note list) clusters the list under collapsible category
headers instead of one flat list — click a group's header to collapse or expand it; the state is
remembered.

![Notes grouped by category](screenshots/grouped-notes.png)

### Organizing

- **Pin** a note (right-click → Pin) to keep it at the top of the list regardless of sort order.
- **Duplicate** a note to create an editable copy, titled "(copy)".
- **Categories** act as folders — create, rename, recolour, or delete them from Settings →
  Categories. Deleting a category with notes in it asks where to move them first; nothing is ever
  silently lost.

![Categories panel](screenshots/categories-panel.png)

### Templates

Save any note as a reusable template (📋 **Save as template**), or build one from scratch in
Settings → Templates. Starting a new note with **Use template** fills in the title, body,
category, and checklist from the template — the template itself is never affected by what you do
with the note afterward. Deleting a template is the one delete in the app that skips the Trash —
it can't be undone, and the confirmation says so plainly.

![Templates panel](screenshots/templates-panel.png)

### Trash

Deleting a note moves it to the Trash — **Recently deleted**, in Settings — where it's recoverable for 30 days
before being purged automatically — or for however long you choose: a **Keep deleted notes for**
selector at the top of the same panel offers 7 to 90 days, and a change applies from the next
startup's cleanup. Restore individual notes, delete them permanently one at a time, or empty the
whole trash at once. With a lot of deleted notes, the list loads the most recent batch first, with
a button to reveal more — so it stays quick to open no matter how much has accumulated there.

![Trash panel](screenshots/trash-panel.png)

### Finding & cleaning up duplicates

Settings → **Duplicates** groups notes that match on title, body, comments, and category. Within a
group, tick specific copies to remove (the rest are kept — nothing forces "keep exactly one"), or
use **Clean up ALL groups** to apply "keep the first, remove the rest" across every group in one
click.

![Duplicates panel](screenshots/duplicates-panel.png)

---

## Recurring notes

Any note can repeat. Open the **Repeat** section in the editor and choose:

- **Daily**, with a custom interval (every N days)
- **Weekly**, on specific weekdays
- **Monthly**, on specific days of the month — with a choice of what happens in shorter months
  (e.g. a note set for "the 31st": either land on that month's *last* day, or be *skipped*
  entirely that month)
- **Yearly**, on a specific date

Set an end condition if the note shouldn't repeat forever: after a number of occurrences, or by a
specific date.

![Recurrence setup](screenshots/recurrence-setup.png)

Editing or deleting one specific occurrence (rather than the whole series) is always offered as a
separate choice — your edit only applies where you meant it to.

A day you edited with **"only this occurrence"** keeps its own content from then on: later edits
to the series deliberately do not touch it (that day is *yours*), which can look surprising — a
series edit appears everywhere except there. The app now says this out loud wherever it matters:
the editor shows a line above the title — "🔁 This note repeats — edits here apply to every day ·
1 day keeps its own edits (✎)" — and in the calendar, such a day carries a ✎ mark in the day list
and an "✎ edited for this day" chip in the preview. To make a day follow the series again,
right-click it in the calendar and choose **↺ Reset this day to the series content**.

The small symbols on a repeating note's card in the list mean: `✎N` — N days edited separately,
`✕N` — N occurrences deleted individually. The sidebar's filter dropdown also offers
**🔁 Repeating** and **📅 Dated** alongside your categories, to see just the notes that live on
the calendar.

---

## Calendar

The Calendar tab shows every note (including every occurrence of every recurring note) on the day
it falls on. Navigate month-to-month, jump directly to a specific month/year, or return to today.
Multiple notes on one day show up to two title previews plus a "+N more" indicator; hovering a day
gives a quick summary.

Clicking a note in the day panel opens a **quick-look preview** — the note's plain text, plus a
line of small flags saying what else it carries (▦ a table, ☑ a checklist, 💬 comments). Like the
note-list cards, the preview does not draw the table or spell out the checklist and comments;
those show when you open the note in the editor (**✏ Open in editor**).

Opening a note from the calendar — the panel's Edit button or any right-click edit entry —
remembers where you came from: a **← Back to Calendar** link appears at the top of the editor and
returns you to that exact month and day, saving your edits on the way (for one day of a repeating
note, it asks the usual "this occurrence or the whole series?" first — cancel that question and
you simply stay in the editor, nothing lost). While you're editing one
day of a repeating note, a line above the title names that day — the date field always shows the
series' start date, so this is what tells you *which* day you opened. Saving stays in the editor;
only the quick "Add note for this day" flow returns you to the calendar on Save.

![Calendar view](screenshots/calendar-view.png)

You can also paint a specific calendar day a custom colour (right-click it), independent of any
note's own colour — useful for marking something about the day itself, like a holiday or deadline.

![Calendar day colouring](screenshots/calendar-day-color.png)

---

## Sharing & backup

### Share a note as a code

Open a note → Generate code. This generates a compact block of text representing that note's
content, checklist included (attachments stay home — use Export for files) — paste it to someone
else, and they can import it with **Import code** in the sidebar. You can also select several notes at once and generate one code covering
all of them.

![Share panel](screenshots/share-panel.png)

### Import a code

Paste a code you received into **Import code** in the sidebar. If any of the notes it contains
look identical to ones you already have, you'll be asked whether to skip the duplicates, import
everything anyway, or cancel — nothing is silently duplicated.

![Import code](screenshots/import-code.png)

### Export one note as a file

Right-click any note in the list (or on the calendar) → **Export as file** and pick a format — the
menu says plainly what each one keeps:

- **Web page (.html)** — the complete note: styles, colours, highlights, and tables as real
  tables. It opens in any browser (press **Ctrl+P** there and "Save as PDF" to get a PDF) and Word
  opens it directly too (then Save As → .docx if you need one).
- **Plain text (.txt)** — the words alone.

The note's checklist and comments come along too, as their own sections, and a table centred (or
right-placed) in the note keeps its place on the exported page. When you print the page to PDF,
highlights and cell colours survive — the export tells the browser to keep them. After a save the
app offers to open the file right away — the exported file itself is the honest preview of how the
note lays out on a page, so adjusting the note and re-exporting is a quick loop. To export
**several notes at once**, turn on ☑ Select above the list, tick the notes, and use **Export ▾**
in the action bar: pick a format and a folder, and each note becomes its own file (same-titled
notes get “(2)”, “(3)” — nothing ever overwrites). Attached files never travel with a single-note
export — that's what the full backup below is for, and the app reminds you when the note has
attachments.

### Full backup: export

Settings → Export notes creates a single `.zip` containing every note, your settings, and every
attachment — the one file you need to move everything to another device. A line under the button
remembers when you last did this — worth a glance now and then, because that `.zip` is the only
copy of your notes outside the app's data folder (see Getting started for where that lives). With a lot of attachments this can take a moment;
a progress bar stays visible at the bottom of the window the whole time, and the app remains fully
usable while it works.

### Full backup: import

Settings → Import notes brings a previously exported `.zip` back in — notes, settings, and
attachments together. Just like importing a code, you'll be asked about any notes that look
identical to what you already have before anything is added.

![Import backup](screenshots/import-backup.png)

### If the data file itself ever breaks

A bad shutdown or a disk problem can leave `notes_data.json` unreadable. The app never papers
over that: it preserves the unreadable file beside the original (named
`notes_data_corrupt_<date>.json`, kept forever), starts with an empty list, and tells you at
startup exactly what happened and where the preserved copy sits — so you can restore your most
recent backup while the broken file stays available for repair. The same quiet preserve-aside
protects the trash, templates and settings files.

---

## Settings

Categories, templates, trash, duplicate cleanup, appearance, your name, usage statistics, and a
keyboard-shortcut reference all live on one page, reached via the **⚙ Settings** button at the
bottom of the sidebar. The page is split in two: a list of settings on the left, and whichever one
you picked on the right. One section shows at a time, so you're only ever looking at the setting
you came for. A **← Back to Notes** button at the top returns you to your notes.

![Settings overview](screenshots/settings-overview.png)

### Your name

Settings → Your name sets the greeting shown above the note list ("Hi \<name\>,"). Leave it blank
for no greeting.

### Statistics

A quick snapshot of your total note count and this week's activity, with a clickable chip per
category — click one to jump straight to your notes filtered to that category.

### Keyboard shortcuts

Three shortcuts work from anywhere in the app: **Ctrl+N** starts a new note, **Ctrl+S** saves the
note you're editing, and **Ctrl+F** opens the find bar for searching within the current note (see
*Finding notes*, above). They, and every other bound combo, are listed under Settings → Keyboard
shortcuts.

| Shortcut | Where | What it does |
| --- | --- | --- |
| **Ctrl+N** | anywhere | Starts a new note. |
| **Ctrl+S** | anywhere | Saves the note you're editing. |
| **Ctrl+F** | anywhere | Opens the find bar for searching within the current note. |
| **Ctrl+B** / **Ctrl+I** / **Ctrl+U** / **Ctrl+D** | editor | Bold / Italic / Underline / Strikethrough. |
| **Ctrl+V** | editor | Pastes — the bold, the colours and the lists come with it. |
| **Ctrl+Shift+V** | editor | Pastes the words on their own, with none of the styling. |
| **Enter** | in a list | Starts the next item; on an item you haven't typed anything into, the list ends there. |
| **Backspace** | in a list | With the cursor just after a marker, removes the marker. |
| **Tab** / **Shift+Tab** | in a list | Pushes an item one level in / pulls it back out. |
| **Tab** / **Shift+Tab** | in a table | Moves to the next / previous cell; Tab on the very last cell adds a fresh row. |
| **Enter** / **Shift+Enter** | in a table | Starts a new line inside the cell. |
| **Escape** | in a table | Leaves the cell. |
| **Ctrl+A** | in a table | Selects the whole cell. |
| **Ctrl+C** / **Ctrl+V** | in a table | Copies the selected cells / pastes them in the same shape. |
| **Delete** | in a table | Clears the selected cells. |
| **Ctrl+Z** | in a table | Takes back one whole operation. |
| **Enter** / **Shift+Enter** | find bar | Step forward and back through matches. |
| **Esc** | find bar | Closes the bar. |

### Appearance

Switch between Dark and Light mode, and pick from four variants of each, in Settings → Appearance.
The choice is remembered the next time you open the app.

At the end of the formatting toolbar sits a small **light/dark switch** (☀ / 🌙): one press flips
between your last light and last dark theme without leaving the note. The full theme picker, with
all eight variants, stays in **Settings → Appearance**.

![Theme picker](screenshots/theme-picker.png)

---

**What changed recently:** see the [CHANGELOG](../CHANGELOG.md).
