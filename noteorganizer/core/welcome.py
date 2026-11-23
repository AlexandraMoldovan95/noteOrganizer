"""The note a brand-new notebook opens with.

A notebook that did not exist until this launch -- a first install -- opens
on it, once; an upgraded, moved-in or emptied one has a notes file already
and never sees it. Settings -> About offers it again. Built here to be
checked without a window, and stored as the editor would have stored it
typed: list markers in the text, bold as spans, bullets as paragraph entries
(``formatting.py`` explains that shape). The words are the owner's.
"""

from .formatting import BULLET

TITLE = "Welcome to Note Organizer 👋"

# A line at a time: "# " a heading, "- " a bullet, "" a blank, else a
# paragraph; **double asterisks** bold. No U+FE0F (Tk draws a blank after
# it); heading icons from the emoji block, so every title starts level.
LINES = (
    "Hi, and welcome! This is your own space for everything worth keeping: "
    "ideas, plans, lists, recipes, the things you don't want to forget. It "
    "all stays on this computer, with no account and no internet needed. "
    "Here is a quick look at what you can do. When you no longer need this "
    "note, delete it; you can always bring it back (see the end).",
    "",
    "# 📝 Write",
    "- **+ New Note** starts a note. Give it a title and write; it saves "
    "itself as you go.",
    "- The toolbar shapes your words: bold, colours, highlights, sizes, "
    "lists, alignment, emoji, and tables for anything that fits in rows and "
    "columns.",
    "- Under the text you'll find a checklist for to-dos, a calculator, "
    "comments, and files you can attach.",
    "",
    "# 🗂 Organise",
    "- The search box above the list looks through all your notes at once.",
    "- **Sort** and **Show** arrange the list. Categories give notes a "
    "colour, and **Group by category** gathers them together.",
    "- Right-click a note to pin it, move it to a category, duplicate it, "
    "export it as a file, or delete it.",
    "- **☑ Select** acts on many notes at once.",
    "",
    "# 📅 Plan",
    "- Give a note a date and it appears on the **Calendar**; on the day "
    "itself, the app reminds you at the top.",
    "- A note can repeat daily, weekly, monthly or yearly.",
    "- **Save as template** keeps a note's shape, and **Use template** "
    "starts a new note from it.",
    "",
    "# 🔒 Share and keep safe",
    "- **Generate code** (on a note) or **Share notes** (in the sidebar) "
    "turns notes into a short code someone else can bring in with "
    "**Import code**.",
    "- **Settings → Backup** saves your whole notebook in one file, to keep "
    "it safe or move it to another computer.",
    "- Deleted notes wait in **Settings → Recently deleted**, so a slip can "
    "be undone.",
    "",
    "# 🛡 Your privacy",
    "- The app collects nothing and sends nothing anywhere. A note leaves "
    "this computer only when you share or export it, or save a backup.",
    "- **Settings → About → Privacy policy** has the whole of it.",
    "",
    "# 🎨 Make it yours",
    "- Pick one of eight light and dark themes in **Settings → Appearance**, "
    "or switch between light and dark with the ☀ / 🌙 button on the toolbar.",
    "",
    "# 💡 Good to know",
    "- **Settings → About** shows where your notes are saved on this "
    "computer, with buttons to open that folder or copy its path. It is also "
    "where you can bring this note back after deleting it.",
    "- Handy keys: **Ctrl+N** a new note · **Ctrl+S** save now · **Ctrl+F** "
    "find in this note · **Ctrl+B** / **Ctrl+I** bold / italic · **Ctrl+Z** "
    "undo. **Settings → Keyboard shortcuts** lists them all.",
    "",
    "Good luck, and may your notes bring you success! 🍀",
)


def _runs(line):
    """A line's ``(text, bold)`` pieces, split at its double asterisks."""
    return [(part, index % 2 == 1)
            for index, part in enumerate(line.split("**")) if part]


def build_welcome_note():
    """The welcome note's own fields: title, body, formatting, paragraphs.

    The caller gives it an id and passes it through ``normalize_note``, as
    every note is, so nothing here decides anything a note decides itself.
    """
    body, spans, paragraphs = [], [], []
    offset = 0
    for number, line in enumerate(LINES):
        if line.startswith("# "):
            runs = [(line[2:], True)]
        elif line.startswith("- "):
            runs = [(BULLET, False)] + _runs(line[2:])
            paragraphs.append({"line": number, "kind": "bullet"})
        else:
            runs = _runs(line)
        for text, bold in runs:
            if bold:
                spans.append({"start": offset, "end": offset + len(text),
                              "style": "bold"})
            body.append(text)
            offset += len(text)
        body.append("\n")
        offset += 1
    return {"title": TITLE, "body": "".join(body).rstrip("\n"),
            "formatting": spans, "paragraphs": paragraphs}
