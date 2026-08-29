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

Notes save automatically a moment after you stop typing (look for the "Auto-saved" status), and always save immediately when you switch to a different note. Closing the app works the same way: anything still unsaved is saved on the way out, silently — no "unsaved changes" question, because there is nothing to lose.

The writing area starts at twelve lines. **Expand**, underneath it, makes it roughly twice as tall for a long note, and **Collapse** puts it back — the note itself is unaffected either way, only how much of it you can see at once. The buttons at the bottom of the editor do not go out of reach; the page simply gets longer and scrolls. The app remembers which you chose. The comments box has the same toggle, though it always opens small.

At the end of the formatting toolbar sits a small **light/dark switch** (☀ / 🌙): one press flips between your last light and last dark theme without leaving the note. The full theme picker, with all eight variants, stays in **Settings → Appearance**.

### Formatting

A small toolbar above the note body is split into four groups, separated by thin dividers. If the window is too narrow to hold them all on one line, the toolbar wraps onto a second rather than hiding anything. The first three — the style toggles, the font dropdowns, and the two colour buttons — change the characters you select. The last changes whole lines. Hover any button and it tells you what it does. **Style**: **Bold**, *Italic*, <u>Underline</u>, and ~~Strikethrough~~ — also on the right-click menu, and available as keyboard shortcuts (**Ctrl+B**, **Ctrl+I**, **Ctrl+U**, **Ctrl+D**). **Colors**: text color and highlight, each opening a small swatch picker (no hex codes to type — just pick a color) with a Clear option to remove it again. All six work the same way: select some text and click (or press) one to apply it there, or click one with nothing selected — it "sticks" for whatever you type next, until you click it again to turn it off. Text color and highlight can be combined with each other and with any of the four styles.

![Formatting toolbar](screenshots/formatting-toolbar.png)

**Paragraph** applies to whole lines — whichever lines your cursor or selection touches, so you don't need to select a line exactly.

- **Lists.** The **•** and **1.** buttons turn those lines into a bullet or numbered list. Click the same button again to turn the list off. Press **Enter** to start the next item; press it on an item you haven't typed anything into and the list ends there. **Backspace** with the cursor just after a marker removes the marker rather than deleting it one character at a time.
- **Nesting.** **Tab** pushes a list item one level in, **Shift+Tab** pulls it back out — or use the **⇤** and **⇥** buttons. A numbered sub-list counts from 1 again under each parent, and picks the outer numbering back up when it ends. Bullets change shape as they go deeper (•, ◦, ▪). Outside a list, Tab still types a tab; the two indent buttons work on any paragraph, list or not, up to eight levels.
- **Alignment.** The three bar icons set a line left, centred, or right. Clicking the alignment a line already has puts it back to left.

These combine: a bullet can be centred, an indented paragraph can be right-aligned, and any of it can carry bold or a text colour.

List markers are part of the note's own text — a bullet really is a "• " at the start of the line. That's deliberate: it means a list still looks like a list when you export the note, share it as a code, or paste it into an email. The indenting is drawn by the app on top of that.

**Font** sets the typeface and size. Pick from either dropdown to change the selected text, or pick with nothing selected and it applies to whatever you type next — the same way the Style buttons work.

- **Default** means "no setting of its own", so that text follows whatever the editor's default is. It is how you undo a size or a typeface, rather than setting it back by hand.
- If you select text that mixes two sizes, the dropdown shows **Default** rather than picking one of them — otherwise it would look like the whole selection was already that size.
- The eight typefaces are ones that come with Windows. That is deliberate: if a note used a font the person you send it to doesn't have, their computer would quietly swap in a different one and nothing would say so.

**To make everything bigger**, don't format each note — go to **Settings → Appearance** and set **Editor font** and **Text size**. That is the size notes start at; anything you set from the toolbar overrides it just for that text. This is the setting to reach for if the default is simply too small to read comfortably.


A title can be up to 200 characters. That is far more than a title needs, and it keeps the field quick to type in — a very long one makes the box itself sluggish. You do not have to count: once you are within 40 characters of the limit, a small counter appears beside the title (`175/200`) and turns red when it is full. Pasting something longer shortens it to fit rather than refusing it. Titles saved before this limit existed are left exactly as they are, however long they are.

### Pasting and copying

Copy something from a web page, an email or Word, paste it into a note with **Ctrl+V**, and the bold, the colours and the lists come with it.

- **Ctrl+Shift+V** pastes the words on their own, with none of the styling — and no bullets either, even when the thing you copied from puts bullet characters into its own plain-text version. There is a **Paste without formatting** entry on the right-click menu too.
- Copying works the same way outwards: select part of a note, copy it, and paste it into an email or a document, and it arrives still formatted. Copying between two notes keeps everything.

Pasting from a PDF is a special case, because a PDF has no paragraphs — only lines placed on a page. Pasting those as they come gives a note broken into narrow ragged lines a third of the way across. They are rejoined instead, using where each line ends to work out which breaks the page forced and which the writer meant: a line ending mid-sentence was broken by the column, a line falling well short of the others ended on purpose, and an indented first line says outright where a paragraph starts. It is worked out rather than known, so it is occasionally wrong — always by joining two paragraphs into one, never by cutting a sentence in half. Lists, addresses and poems are left exactly as they came.

Colours are treated carefully. If you copy from a site in dark mode, you get its words, its bold and its lists — not its dark background and pale text, which would be unreadable in your note. A colour comes through when it was clearly a choice, like a red warning or a yellow highlight; greys, blacks and whites are the page's own styling and are left behind.

Not every kind of styling can survive. A note can be bold, italic, underlined, struck through, coloured, highlighted, set in one of eight fonts, made into a list, indented and aligned. Anything a web page does beyond that — a heading style, a box, a background image — is dropped and its words kept, rather than being turned into an approximation of itself. Font sizes and typefaces from a web page are dropped for the same reason: the page is almost certainly using something this app does not offer, and picking the nearest one would claim the note is set in something it never was.

### Tables

The table button on the toolbar opens a small size grid — sweep across it to choose how many rows and columns, and a table appears at the cursor with the first cell ready to type into.

![A table in a note, with a highlighted header row](screenshots/tables.png)

A table works the way a spreadsheet has taught your hands to expect:

- **Type** in a cell, press **Tab** to move to the next one (**Shift+Tab** goes back). Tab on the very last cell adds a fresh row, so a whole table can be filled without touching the mouse. **Enter** (or **Shift+Enter**) starts a new line *inside* the cell — the whole row grows to fit — stored as Markdown's own `<br>`, so export still round-trips. The row grows on screen the moment you press it, so nothing below is ever covered. To leave the cell, press **Tab**, **Escape**, or click anywhere else; **Ctrl+A** selects the whole cell. A table wider than the editor gets its own horizontal scrollbar, drawn just underneath it.
- **Click** any cell to edit it. **Drag** across cells to select a block of them — a firm drag *inside* one cell selects just that cell — then **Ctrl+C** copies it, **Ctrl+V** somewhere else pastes it in the same shape, and **Delete** clears it. Copying works with the outside world in both directions: cells copied here paste into Excel as cells, and a table copied from Excel or a web page lands here as a real table.
- **Right-click** a cell for everything else: merge the selected cells into one (their texts join), split a merge back apart, insert or delete rows and columns, duplicate whole columns to the end of the table, insert a checkmark (with its own colour palette — a green check, a red one, or the theme's plain ink) or an emoji, and highlight cells from a small colour palette.
- **Drag the line between two columns** to make a column wider or narrower; **double-click** the line to snap the column to its content. **Drag the line between two rows** up or down to make a row taller or shorter — the whole row resizes together, and a drag can never cut into text a cell actually holds. Narrowing below the content only shortens what is *drawn* (with an `…`) — the text itself is never cut.
- **Hide a column** by selecting it top to bottom and right-clicking — it shrinks to a thin sliver, and right-clicking the sliver brings it back. Hiding only ever works on a fully selected column, so it is always clear what is about to disappear.
- The **formatting toolbar works inside tables** too: select cells and Bold, colours and highlights apply to them whole. With a cell *open*, the toolbar styles just the part you selected inside it — a single word, letter, or emoji can carry its own colour — and the open cell shows its colours while you edit, not after. Typing continues the style it lands beside: adding to a blue word stays blue. Pick a colour with nothing selected and it becomes the *active* colour — the toolbar button wears it as a swatch so you can see what you are writing with — and everything you type next, in a cell or in the note body, comes out in that colour until you pick another or click the same colour off. The alignment buttons align the text inside the selected cells; to move the *table itself*, right-click it and choose **Center table on page** (or left / right).

Under the hood a table is stored as plain, readable text inside the note — the same pipe-and-dash layout Markdown uses. That is why search finds words inside cells, why tables survive share codes, backups and export unchanged, and why a table pasted into any Markdown-aware tool arrives as a table. The bullet and numbering buttons deliberately do nothing to a table — a table is not a list, and turning its rows into list items would break it apart.

### How long a note takes to read

Under the word and character counts, each note shows roughly how long it takes to read — "under a minute to read" for a short one, "about 4 minutes to read" for a longer one.

It is worked out from the word count at 200 words a minute, which is the slow end of normal adult reading. That is on purpose: finishing sooner than promised costs you nothing, whereas being told a note is shorter than it really is does.

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

Each note's card previews its first words. A table would be pipe soup at that size, so the preview shows only the note's plain text and the card's tag row marks the table itself — **▦ 1 table**, or how many the note holds — next to the comment and attachment marks.

![Search and sort](screenshots/search-and-sort.png)

**Group by category** (checkbox above the note list) clusters the list under collapsible category headers instead of one flat list — click a group's header to collapse or expand it; the state is remembered.

![Notes grouped by category](screenshots/grouped-notes.png)

### Organizing

- **Pin** a note (right-click → Pin) to keep it at the top of the list regardless of sort order.
- **Duplicate** a note to create an editable copy, titled "(copy)".
- **Categories** act as folders — create, rename, recolor, or delete them from Settings → Categories. Deleting a category with notes in it asks where to move them first; nothing is ever silently lost.

![Categories panel](screenshots/categories-panel.png)

### Templates

Save any note as a reusable template (📋 **Save as template**), or build one from scratch in Settings → Templates. Starting a new note with **Use template** fills in the title, body, category, and checklist from the template — the template itself is never affected by what you do with the note afterward.

![Templates panel](screenshots/templates-panel.png)

### Trash

Deleting a note moves it to **Recently deleted** (Settings), where it's recoverable for 30 days before being purged automatically. Restore individual notes, delete them permanently one at a time, or empty the whole trash at once. With a lot of deleted notes, the list loads the most recent batch first, with a button to reveal more — so it stays quick to open no matter how much has accumulated there.

![Trash panel](screenshots/trash-panel.png)

### Finding & cleaning up duplicates

Settings → **Duplicates** groups notes that match on title, body, comments, and category. Within a group, tick specific copies to remove (the rest are kept — nothing forces "keep exactly one"), or use **Clean up ALL groups** to apply "keep the first, remove the rest" across every group in one click.

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

### Full backup: import

Settings → Import notes brings a previously exported `.zip` back in — notes, settings, and attachments together. Just like importing a code, you'll be asked about any notes that look identical to what you already have before anything is added.

![Import backup](screenshots/import-backup.png)

---

## Settings

Categories, templates, trash, duplicate cleanup, appearance, your name, and usage statistics all live on one page, reached via the **⚙ Settings** button at the bottom of the sidebar. The page is split in two: a list of settings on the left, and whichever one you picked on the right. One section shows at a time, so you're only ever looking at the setting you came for. A **← Back to Notes** button at the top returns you to your notes.

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
| `formatting-toolbar.png` | The formatting toolbar, with a mix of bold/italic/underlined/struck-through/colored/highlighted text visible in the body |
| `attachments.png` | The attachments section of a note with at least one file attached |
| `checklist.png` | The checklist section open, with a mix of checked and unchecked items |
| `calculator.png` | The calculator section open, with an expression entered and its result inserted into the note |
| `emoji-picker.png` | The emoji picker open over a text field |
| `search-and-sort.png` | The search box and sort dropdown, ideally mid-search |
| `grouped-notes.png` | The note list with "Group by category" on, showing at least two groups (one collapsed, one expanded, if possible) |
| `categories-panel.png` | Settings → Categories, with a few categories listed |
| `templates-panel.png` | Settings → Templates, with at least one template listed |
| `trash-panel.png` | Settings → Recently deleted, with a few entries |
| `duplicates-panel.png` | Settings → Duplicates, with at least one group showing |
| `recurrence-setup.png` | The Repeat section of the editor, mid-setup (e.g. Weekly with a couple of days picked) |
| `calendar-view.png` | The Calendar tab, a month with a few notes visible on different days |
| `calendar-day-color.png` | The right-click menu / result of painting a calendar day a custom color |
| `share-panel.png` | The Share notes panel with a couple of notes ticked |
| `import-code.png` | The Import code panel, ideally showing the duplicate-check prompt |
| `export-progress.png` | The export progress bar visible at the bottom of the window mid-export |
| `import-backup.png` | The Import notes file picker or its resulting confirmation |
| `settings-overview.png` | The Settings page, showing the section list on the left and a section open on the right |
| `theme-picker.png` | Settings → Appearance, with the theme variant cards visible |
