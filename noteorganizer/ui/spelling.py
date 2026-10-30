"""Spelling: misspelled words underlined in the note and its comments.

Mixed into the app class (see note_organizer.NoteOrganizer). The words are
judged by Windows' own checker (core/winspell.py); which of its answers are
shown is core/spelling.py; this module is the editor's side -- when to
look, where to underline, and the right-click menu's suggestions.

WHAT IT NEVER DOES
------------------
The underline is a tag of its own, which the editor's save, copy, export
and undo journal do not read: they read character formatting from a closed
list of tags (is_format_tag), and this is not one of them. Nothing about
spelling is ever stored in a note. Nothing is corrected without the person
choosing it.

WHEN IT LOOKS
-------------
A pause in typing, a click elsewhere, leaving the box, a paste, and opening
a note. Each line's answer is kept by its text, so a pause rereads only the
line that changed; a note opening for the first time is read in slices, so a
long one never holds the editor up. The word still being typed is not
underlined until the caret leaves it.
"""

import tkinter as tk

from ..core import spelling, winspell
from ..core.storage import get_setting, save_setting
from ..core.tables import is_table_row


class SpellingMixin:
    SPELL_TAG = "spelling"
    # A pause this long in typing, and the line is looked at.
    SPELL_DELAY_MS = 400
    # Lines read per slice of an idle moment: about 0.8 ms each, measured.
    SPELL_SLICE = 40
    # Lines' answers kept, by text; past this the store starts again.
    SPELL_CACHE_LIMIT = 5000

    # ---- which dictionaries, and whether to look at all ----

    def _spellers(self):
        """One Windows checker per installed language, the person's own
        first; empty off Windows or without a dictionary. Asked once."""
        found = getattr(self, "_spellers_found", None)
        if found is None:
            tags = spelling.pick_languages(winspell.languages(),
                                           winspell.preferred_languages())
            found = [s for s in (winspell.speller(t) for t in tags) if s is not None]
            self._spellers_found = found
        return found

    def _spell_on(self):
        """Whether misspellings are underlined: Settings -> Appearance ->
        Spelling is on (as it is unless turned off), and Windows has a
        dictionary to ask."""
        return (get_setting(spelling.SPELLING_SETTING, True, expect=bool)
                and bool(self._spellers()))

    def _spell_ignored(self):
        """The words ignored on this computer, in lookup form."""
        ignored = getattr(self, "_spell_ignored_words", None)
        if ignored is None:
            ignored = self._spell_ignored_words = set(spelling.normalize_ignored(
                get_setting(spelling.SPELLING_IGNORED_SETTING, [], expect=list)))
        return ignored

    def _spell_languages_text(self):
        """The languages being checked, by name: "English, Romanian"."""
        names = []
        for s in self._spellers():
            name = winspell.language_name(s.tag)
            if name not in names:
                names.append(name)
        return ", ".join(names)

    # ---- the boxes it looks at ----

    # The moments a box is looked at are bound on a tag of their own, put
    # first among the box's tags: a binding on the box itself made later --
    # the comments box's autosave was one, bound with no add="+" -- would
    # replace them, and one that answers "break" would stop them, in
    # silence. Nothing bound here answers "break"; it only schedules a look.
    _SPELL_BINDTAG = "NoteSpelling"

    def _spell_setup(self, widget):
        """Give a Text box its underline and the moments it is looked at."""
        boxes = getattr(self, "_spell_widgets", None)
        if boxes is None:
            boxes = self._spell_widgets = []
        boxes.append(widget)
        widget._spell_job = None
        widget._spell_typing = False
        self._spell_color(widget)
        if not getattr(self, "_spell_bound", False):
            self._spell_bound = True
            self.bind_class(self._SPELL_BINDTAG, "<KeyRelease>",
                            lambda e: self._spell_key(e.widget, e))
            for sequence in ("<ButtonRelease-1>", "<FocusOut>", "<<Paste>>"):
                self.bind_class(self._SPELL_BINDTAG, sequence,
                                lambda e: self._spell_left(e.widget))
        tags = widget.bindtags()
        if self._SPELL_BINDTAG not in tags:
            widget.bindtags((self._SPELL_BINDTAG,) + tuple(tags))

    def _spell_color(self, widget):
        """The underline, in the theme's red for words. Tk older than 8.6.11
        has no colour for an underline; it gets the plain one."""
        try:
            widget.tag_configure(self.SPELL_TAG, underline=True,
                                 underlinefg=self.colors["danger_text"])
        except tk.TclError:
            widget.tag_configure(self.SPELL_TAG, underline=True)

    def _spell_recolor(self):
        """A theme switch: the underline takes the new theme's red."""
        for widget in getattr(self, "_spell_widgets", ()):
            try:
                self._spell_color(widget)
            except tk.TclError:
                pass

    def _spell_key(self, widget, event):
        """A key let go: a letter means a word is being typed, and its own
        word waits; anything else -- a space, a full stop, an arrow -- and
        the word just left is looked at."""
        char = getattr(event, "char", "") or ""
        keysym = getattr(event, "keysym", "") or ""
        if not char and len(keysym) == 1:
            char = keysym                  # a key with no character attached
        widget._spell_typing = bool(char) and (char.isalpha() or char in "'’-")
        self._spell_schedule(widget)

    def _spell_left(self, widget):
        """The caret left the word it was in: look again soon."""
        widget._spell_typing = False
        self._spell_schedule(widget, delay=150)

    def _spell_schedule(self, widget, delay=None):
        """Look at *widget* after *delay* ms, replacing a look already due."""
        job = getattr(widget, "_spell_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        widget._spell_job = self.after(self.SPELL_DELAY_MS if delay is None else delay,
                                       lambda: self._spell_run(widget))

    def _spell_schedule_all(self, delay=1):
        """Look at every box again: a note opened, the setting changed, a
        word ignored or added to the dictionary."""
        for widget in getattr(self, "_spell_widgets", ()):
            widget._spell_typing = False
            self._spell_schedule(widget, delay)

    # ---- looking ----

    def _spell_run(self, widget):
        """Read *widget*'s lines -- the ones not already known, in slices --
        then underline what is left once the quiet rules have spoken."""
        widget._spell_job = None
        try:
            if not widget.winfo_exists():
                return
        except tk.TclError:
            return
        if not self._spell_on():
            widget.tag_remove(self.SPELL_TAG, "1.0", "end")
            return
        lines = widget.get("1.0", "end-1c").split("\n")
        # A line holding a drawn table's window or an image counts that as
        # a character in Tk's columns but not in the text read back, so
        # every position after it would be one off: such lines, like a
        # table's own rows, are not looked at.
        skip = set()
        try:
            for _kind, _value, index in widget.dump("1.0", "end", window=True, image=True):
                skip.add(int(str(index).split(".")[0]) - 1)
        except tk.TclError:
            pass
        cache = getattr(self, "_spell_cache", None)
        if cache is None or len(cache) > self.SPELL_CACHE_LIMIT:
            cache = self._spell_cache = {}
        todo = [i for i, text in enumerate(lines)
                if i not in skip and text.strip() and not is_table_row(text)
                and text not in cache]
        widget._spell_generation = generation = getattr(widget, "_spell_generation", 0) + 1
        self._spell_read(widget, lines, skip, todo, generation)

    def _spell_read(self, widget, lines, skip, todo, generation):
        """One slice of the reading; the next is scheduled after it, and the
        underlining waits for the last. A newer look started meanwhile wins."""
        if getattr(widget, "_spell_generation", 0) != generation:
            return
        # The slice that was due is this one: kept, its id said a look was
        # still due after the last slice, and a wait for it never ended.
        widget._spell_job = None
        cache = self._spell_cache
        spellers = self._spellers()
        for i in todo[:self.SPELL_SLICE]:
            text = lines[i]
            per_language = []
            for speller in spellers:
                found = []
                for offset, piece in spelling.pieces(text):
                    found += [(offset + s, n) for s, n in speller.errors(piece)]
                per_language.append(found)
            cache[text] = spelling.line_errors(per_language)
        rest = todo[self.SPELL_SLICE:]
        if rest:
            widget._spell_job = self.after(
                1, lambda: self._spell_read(widget, lines, skip, rest, generation))
            return
        self._spell_show(widget, lines, skip)

    def _spell_show(self, widget, lines, skip):
        """Underline what the quiet rules leave, and nothing else."""
        results = []
        for i, text in enumerate(lines):
            if i in skip or not text.strip() or is_table_row(text):
                results.append(None)
            else:
                results.append(self._spell_cache.get(text, []))
        shown = spelling.visible_errors(lines, results, self._spell_ignored())
        try:
            line, col = map(int, widget.index("insert").split("."))
        except (tk.TclError, ValueError):
            line, col = 1, 0
        if getattr(widget, "_spell_typing", False):
            try:
                if self.focus_get() is widget:
                    ranges = shown.get(line - 1)
                    typing = spelling.range_at(ranges or [], col)
                    if typing:
                        ranges.remove(typing)
            except (tk.TclError, KeyError, ValueError):
                pass
        # No more than a box may hold, those nearest the caret: a long line
        # of typos made every read of it, the save's at each pause, dear.
        shown = spelling.nearest_underlines(shown, line - 1, col)
        marks = []
        for i, ranges in shown.items():
            for start, length in ranges:
                marks += [f"{i + 1}.{start}", f"{i + 1}.{start + length}"]
        widget.tag_remove(self.SPELL_TAG, "1.0", "end")
        if marks:
            widget.tag_add(self.SPELL_TAG, *marks)

    # ---- the right-click menu ----

    def _spell_menu(self, widget, menu, event):
        """Put the word's suggestions, Ignore and Add to Windows dictionary
        at the top of *widget*'s right-click menu when it opens on an
        underlined word; take them away again when it opens anywhere else."""
        count = getattr(menu, "_spell_items", 0)
        if count:
            menu.delete(0, count - 1)
        menu._spell_items = 0
        if widget not in getattr(self, "_spell_widgets", ()):
            return
        try:
            index = widget.index(f"@{event.x},{event.y}")
            found = widget.tag_prevrange(self.SPELL_TAG, f"{index}+1c")
        except tk.TclError:
            return
        if not found or widget.compare(found[1], "<=", index):
            return
        start, end = (widget.index(found[0]), widget.index(found[1]))
        word = widget.get(start, end)
        spellers = self._spellers()
        suggestions = spellers[0].suggest(word) if spellers else []
        position = 0

        def add(**options):
            nonlocal position
            menu.insert_command(position, **options)
            position += 1

        for suggestion in suggestions:
            add(label=suggestion,
                command=lambda s=suggestion: self._spell_take(widget, start, end, word, s))
        if not suggestions:
            add(label="No suggestions", state="disabled")
        add(label="Ignore “%s”" % word, command=lambda: self._spell_ignore(word))
        # "Windows" in the label: the word is not kept by this app but by
        # Windows, and every other program that asks Windows' checker
        # stops underlining it too.
        add(label="Add to Windows dictionary", command=lambda: self._spell_add(word))
        menu.insert_separator(position)
        menu._spell_items = position + 1

    def _spell_take(self, widget, start, end, word, suggestion):
        """Put *suggestion* where the misspelled *word* stands, keeping its
        formatting -- if the word is still there."""
        try:
            if widget.get(start, end) != word:
                return
        except tk.TclError:
            return
        if widget is getattr(self, "body_text", None):
            self._spell_replace_body(start, end, suggestion)
        else:
            widget.edit_separator()
            widget.delete(start, end)
            widget.insert(start, suggestion)
            widget.edit_separator()
        self._schedule_autosave()
        self._spell_schedule(widget, delay=1)

    def _spell_ignore(self, word):
        """Never underline *word* again on this computer."""
        ignored = self._spell_ignored()
        ignored.add(spelling.ignored_key(word))
        save_setting(spelling.SPELLING_IGNORED_SETTING,
                     spelling.normalize_ignored(sorted(ignored)))
        self._spell_ignored_words = set(spelling.normalize_ignored(sorted(ignored)))
        self._spell_schedule_all()

    def _spell_add(self, word):
        """Put *word* in the Windows dictionary, which other programs that
        use Windows' checker share."""
        spellers = self._spellers()
        if spellers and spellers[0].add(word):
            self._spell_cache = {}
            self._show_toast("Added “%s” to the Windows dictionary — other "
                             "programs know it too" % word)
            self._spell_schedule_all()
        else:
            self._show_toast("Could not add “%s” to the Windows dictionary" % word,
                             kind="error")

    # ---- Settings -> Appearance -> Spelling ----

    def _set_spelling(self, value):
        """Spelling turned On or Off: kept, and shown at once."""
        on = value == "On"
        if on == get_setting(spelling.SPELLING_SETTING, True, expect=bool):
            return
        save_setting(spelling.SPELLING_SETTING, on)
        self._spell_schedule_all()
