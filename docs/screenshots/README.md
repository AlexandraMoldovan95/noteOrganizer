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

Five things the script does that a careful hand cannot promise:

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
- **A picture stays true whichever day it is taken.** The calendar is
  put on the month a scene staged, not today's, and the panels that
  count from today -- Statistics, the Trash's days left -- get dates
  counted from today. A month after one retake, a September day sat open
  under an October grid and a trash row read "0 day(s) left".
- **No picture ends in half a line.** A whole-window shot stops above
  any line of text the window's bottom edge would cut, and a section
  photographed on its own is scrolled into view first: the checklist
  shot had lost its Add button.

Rules that keep the set reading as one app:

- **The current app on screen** — window title **Note Organizer**, current UI
  (the ☀/🌙 theme button visible where a capture includes the toolbar). One
  picture is the exception, on purpose: see
  [A picture of an earlier version](#a-picture-of-an-earlier-version).
- **One theme throughout** — a partial refresh in another theme silently
  produces a mixed set.

**Current set:** retaken 2026-10-08 in the default dark (purple) theme, all
twenty-two and the demo GIF by `tools/doc_screenshots.py`, on app version
0.89.371 — the open tab raised, the open note's card ringed, dates shown
day first, both calendar pictures on the month they stage and nothing cut
at the bottom edge. On 2026-10-09 the search picture was retaken with three
matches, Statistics with a "since" date inside the app's own lifetime, and
two were added (the main window on a light theme, a search that matches
nothing). On 2026-10-15 `theme-picker.png` was retaken by the same script,
on 0.94.379, to show the Sharp text and Spelling rows added since. On
2026-10-22 `emoji-picker.png` was retaken the same way, on 0.96.392: the
picker opens on the same three groups, and only its scrollbar is shorter,
the picker holding more emoji since. Update this line whenever the set is
recaptured.

| Filename | What to capture |
|---|---|
| `demo.gif` | The README's moving picture, made by the `demo` scene: a note written, given a table and saved; the month on the calendar; the same note on a light theme |
| `main-window.png` | The main window, Notes tab: sidebar, a note open with a table, and the full formatting toolbar including the ☀/🌙 theme button at its right end |
| `main-window-light.png` | The same window on a light theme (Soft Lavender), for the guide's Appearance section |
| `note-editor.png` | A note open in the editor with some content, the toolbar, and the Checklist + Calculator bars below |
| `formatting-toolbar.png` | The formatting toolbar close-up, with bold/italic/coloured/highlighted text in the body — and the ☀/🌙 theme button visible at the right end |
| `tables.png` | A table in a note with a highlighted header row (ideally a checkbox cell and a "Tab. N" caption too) |
| `attachments.png` | The attachments section of a note with at least one file attached |
| `checklist.png` | The checklist open beside the calculator, with a mix of checked and unchecked items and the Expand bar |
| `calculator.png` | The calculator open, with an expression entered and the history showing a calculation |
| `emoji-picker.png` | The emoji picker open over a text field |
| `search-and-sort.png` | The search box and sort dropdown, mid-search, with several matches (in titles and in a body) in the chosen order |
| `no-match.png` | The note list when nothing matches the search, saying so rather than going blank |
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
| `settings-overview-light.png` | The same page on a light theme, its partner on the website (see below) |
| `theme-picker.png` | Settings → Appearance, with the theme variant cards visible |
| `site-*-dark.png`, `site-*-light.png` | The website's pictures — see below |

## The website's pictures

The fourteen `site-*` pictures are the website's own: its six feature cards
(`tables`, `checklist`, `calendar`, `repeat`, `search`, `trash`) and its
themes section (`themes`), each in the dark theme and in the light one, so
the page shows the one it is in. They, and the light partners described
below, are the deliberate exception to *one theme throughout*. The
`site-cards` scene of
`tools/doc_screenshots.py` takes all fourteen: each is cropped close around
what its card is about, then grown to the card's 16:10 so the card crops
none of it away. Whole windows shrunk to a card's size, as the cards had
before 2026-10-24, showed no feature a visitor could make out. Taken on
2026-10-24 on 0.96.395.

The website shows every picture of the apps in the theme its page is in
(the owner's rule, 2026-10-24), and its build refuses a page with a
picture in one theme only. So a picture a published document shows has a
`NAME-light.png` partner beside it, `NAME.png` being the dark one, as
`main-window` has: today `settings-overview` (the scene
`settings-overview-light`) and `settings-before-redesign`, both shown in
In my words.

## A picture of an earlier version

`settings-before-redesign.png` shows Settings as it was on 2026-08-20, the
evening before its redesign: one long column, each section's title on the
left and its buttons in the middle. It sits beside `settings-overview.png` in
[In my words](../IN_MY_WORDS.md#decisions-i-made), and it is the one picture
here that does not show today's app.

It was taken on 2026-10-14 by running the code of that day, taken from git,
in a scratch folder on a made-up notebook, with the same uncovered-window
check as every other picture. That version did not yet know about the
screen's scale, so Windows stretched it like a picture, and its frame let a
pixel or two of the desktop in at the edges and the rounded corners. The
photo is cropped to the inside of the window, title bar off.
`tools/doc_screenshots.py` does not retake it: it photographs only the
current app.

Its light partner, `settings-before-redesign-light.png`, was taken the
same way on 2026-10-24, from commit `8dc0cf0`, the last before the
redesign, with the made-up notebook's settings asking for the light
theme. That code reads `%APPDATA%` on start, to bring an older notebook
forward, so it was run with `APPDATA` pointed at an empty folder of its
own, and stopped if it settled anywhere but its scratch folder; its
start-up notices, which wait for a click, were answered in code. It is
cropped to the same frame as the dark one, so the two match pixel for
pixel in where everything sits.
