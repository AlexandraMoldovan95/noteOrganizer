"""The calendar tab, the day panel, and the daily reminder.

WHAT THIS IS FOR
----------------
Everything that shows notes by date: the month grid, the panel that opens
when a day is clicked, the hover tooltips, per-day colours and emoji, and
the reminder bar that appears when something is due today.

WHY THESE BELONG TOGETHER
-------------------------
Chosen from the call graph rather than from a heading: about 62% of the
calls these methods make are to each other, the highest of any group in
the class once the dialogs had moved out. The comment markers in the
entry module were no help -- the block headed "Daily reminder bar"
contained the attachments, the colour picker and the date picker.

The reminder bar is here because it is date-driven: it asks which notes
land on today and offers to open them, which is the same question the
month grid asks for every visible day.

WHAT DELIBERATELY STAYED BEHIND
-------------------------------
``_rounded_rect`` and ``_show_color_palette`` are used by the calendar
but are not *of* it -- one is a drawing primitive, the other picks
colours for categories as well as for days. Both stay on the app class.

RECURRING NOTES
---------------
A repeating note is stored once and appears on many days, so nothing here
compares stored dates. :func:`~noteorganizer.core.recurrence.expand_occurrences`
is asked which notes fall in a window instead, which is also why a day can
show a note whose own ``date`` field says something else entirely.

See :mod:`noteorganizer.ui` for what a mixin is and the two rules that
keep them working.
"""

import calendar as cal_module
import re
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta, date as date_cls
from types import SimpleNamespace

from ..core.model import (
    MAX_DAY_DECORATIONS,
    _darken_hex,
    _extract_first_emoji,
    _note_str,
    _truncate,
)
from ..core.recurrence import (
    describe_recurrence,
    effective_note,
    expand_occurrences,
    history_entries,
    is_recurring,
    moved_from,
    parse_date,
    show_date,
    show_day,
)
from ..core.storage import (
    load_settings,
    save_setting,
    save_settings,
)
from ..core.themes import contrasting_fg
from ..core import tables as core_tables
from .dialogs import one_line


# The open day's panel is drawn from the notes at the moment it opens, and
# render_calendar -- the one signal that the notes changed -- asks whether
# it still says the same thing. These say what it says, so the drawing and
# that question cannot disagree. Plain functions rather than methods: they
# only read, and the app class's method surface is pinned by
# tools/class_api_baseline.json.

def _day_row_parts(app, base_note, date_str):
    """One row of a day's list as it is drawn: the title (🔁 first for a
    series), the marks after it, and the note's own colour for the stripe."""
    note = effective_note(base_note, date_str)
    title_text = _note_str(note, "title") or "(untitled)"
    if is_recurring(base_note):
        title_text = "🔁 " + title_text
    icons = ""
    # A series' marks only: a note that no longer repeats keeps its days
    # unused, for a turn-back-on (effective_note).
    if is_recurring(base_note) and date_str in (base_note.get("overrides") or {}):
        # This day was edited with "only this occurrence" — it
        # keeps its own content and series edits don't reach it.
        icons += "  ✎"
    if moved_from(base_note, date_str) is not None:
        # A day of the series held here from another date.
        icons += "  ↷"
    if note.get("comments"):
        icons += "  💬"
    if note.get("attachments"):
        icons += f"  📎×{len(note['attachments'])}"
    return title_text, icons, app.get_note_color(note)


def _day_list_rows(app, day_notes, date_str):
    return [(n, _day_row_parts(app, n, date_str)) for n in day_notes]


def _day_list_key(rows):
    """Everything a day's list shows, in order: which notes, and each row's
    words and colour. Which note OBJECT too: a row's clicks act on the dict
    it was drawn from, so a note replaced by an equal copy is drawn again."""
    return tuple((id(n), n.get("id"), parts) for n, parts in rows)


def _day_note_key(base_note, date_str):
    """What the one-note view is drawn from: a change to any of it changes
    what that view shows."""
    note = effective_note(base_note, date_str)
    return (base_note.get("id"), _note_str(note, "title"), _note_str(note, "body"),
            _note_str(note, "comments"), repr(note.get("checklist")),
            len(note.get("attachments") or []),
            is_recurring(base_note) and date_str in (base_note.get("overrides") or {}),
            moved_from(base_note, date_str))


def _notes_on_day(app, date_str):
    """The notes on one day, as the drawn month holds them when it can.

    render_calendar has already asked every note which days of the month
    it lands on; hovering a day or opening its list asked all of them
    again, for one day (14 ms at 5,000 notes, at every hover). The month's
    answer is used when it is the day's month and nothing has changed
    since it was worked out: no render pending, no refresh deferred, the
    same list of notes, as many of them. Anything else asks the notes.
    """
    data = getattr(app, "_cal_month_data", None)
    if (data is not None
            and not getattr(app, "_calendar_needs_render", False)
            and not getattr(app, "_note_list_needs_refresh", False)
            and data.get("notes") is app.notes
            and data.get("count") == len(app.notes)
            and date_str[:7] == "%04d-%02d" % (data["year"], data["month"])):
        return list(data["notes_by_date"].get(date_str, []))
    return app.notes_on_date(date_str)


def _fit_title(app, label, head, title, tail, font):
    """Show head + title + tail in `label`, shortening only the TITLE, with
    an ellipsis, to the label's own width. What follows a title -- a day
    row's ✎ 💬 📎, a History group's "· 20 occurrences · 1 edited (✎)" --
    is what the label's edge used to cut first. The width is the label's
    own (it is stretched by its row), read each time it changes. A line
    that fits costs one measure, when the row is made."""
    # One line, and no more of it than can ever show: a name kept whole in
    # its file -- 3,000 lines, or 60,000 letters -- passed X's limit.
    title = one_line(title, app.NAME_SHOWN_CHARS)
    whole = head + title + tail
    label.configure(text=whole, font=font)
    inset = 2 * sum(int(str(label.cget(o))) for o in
                    ("borderwidth", "padx", "highlightthickness"))
    needs = font.measure(whole)
    showing = [whole]

    def fit(event=None):
        width = label.winfo_width() if event is None else event.width
        if width - inset >= needs:
            text = whole
        else:
            room = width - inset - font.measure(head) - font.measure(tail)
            text = head + (app._ellipsize(title, font, room)
                           if room > 0 else "…") + tail
        if text != showing[0]:
            showing[0] = text
            label.configure(text=text)
    label.bind("<Configure>", fit, add="+")


def _redraw_open_day(app, notes_by_date, year, month):
    """Draw the open day's panel again if the notes have changed what it
    shows; leave it alone (its scroll, its keyboard) if they have not."""
    mode = getattr(app, "_day_panel_mode", "empty")
    date_str = getattr(app, "selected_day", None)
    if mode == "empty" or not date_str:
        return
    shows = getattr(app, "_day_panel_shows", None) or ("", "", None, None)
    # The month just worked out holds the day's answer when the day is in
    # it; a day open under another month is asked for on its own.
    if date_str[:7] == "%04d-%02d" % (year, month):
        day_notes = notes_by_date.get(date_str, [])
    else:
        day_notes = app.notes_on_date(date_str)
    if mode == "note":
        shown_id = shows[2].get("id") if isinstance(shows[2], dict) else None
        base = (next((n for n in day_notes if n.get("id") == shown_id), None)
                if shows[:2] == ("note", date_str) else None)
        if base is None:
            # Gone from this day -- deleted, moved, or this one day of it
            # removed: the day's list, as refresh_day_panel falls back.
            app.show_day_list()
        elif base is not shows[2] or _day_note_key(base, date_str) != shows[3]:
            app.show_day_note(base, date_str)
    elif (shows[:2] != ("list", date_str)
          or _day_list_key(_day_list_rows(app, day_notes, date_str)) != shows[2]):
        app.show_day_list()


class CalendarViewMixin:
    """The calendar tab for :class:`NoteOrganizer`.

    Not usable on its own -- every method reads state owned by the app
    (``self.notes``, ``self.colors``, ``self.cal_grid_frame`` and so on).
    """

    def build_calendar_tab(self, parent):
        header = tk.Frame(parent)
        self.track_theme(header, bg="bg")
        header.pack(fill="x", padx=30, pady=(25, 10))

        def nav_button(parent, text, command, side, width=3, font_size=12):
            btn = tk.Button(
                parent, text=text, command=command, relief="flat",
                font=("Segoe UI", font_size, "bold"), cursor="hand2", width=width
            )
            self.track_theme(btn, bg="card", fg="text")
            btn.pack(side=side, padx=2)
            return btn

        # Far right, out of the navigation's way: History outermost, with
        # Today beside it (field feedback: the arrows belong to the title,
        # the register belongs to the edge).
        # One toggle, whose label says where the click takes you:
        # "📋 History" on the grid, "📅 Calendar" on the register. It
        # replaces the old in-view "← Calendar" button, so there is a
        # single, unambiguous switch (field feedback).
        self._history_toggle_btn = nav_button(
            header, "📋 History", self._toggle_calendar_history,
            "right", width=11, font_size=9)
        nav_button(header, "Today", self.go_to_today, "right",
                   width=7, font_size=9)

        # The month title with its arrows hugging it, centered as one
        # cluster: ◀◀ / ▶▶ move a whole year, ◀ / ▶ move a month.
        center = tk.Frame(header)
        self.track_theme(center, bg="bg")
        center.pack(side="left", fill="x", expand=True)
        cluster = tk.Frame(center)
        self.track_theme(cluster, bg="bg")
        cluster.pack(anchor="center")

        nav_button(cluster, "◀◀", lambda: self.shift_calendar(years=-1), "left")
        nav_button(cluster, "◀", lambda: self.shift_calendar(months=-1), "left")

        # The title doubles as a jump target for anything far away.
        self.cal_month_lbl = tk.Button(
            cluster, text="", relief="flat",
            font=("Segoe UI", 16, "bold"), cursor="hand2", borderwidth=0
        )
        # A second click on the title closes the month picker (see
        # _toggles_its_popup) instead of opening a fresh one.
        self._toggles_its_popup(self.cal_month_lbl, self.open_month_jump)
        self.track_theme(self.cal_month_lbl, bg="bg", fg="text",
                         activebackground="bg", activeforeground="accent_text")
        self.cal_month_lbl.pack(side="left", padx=10)

        nav_button(cluster, "▶", lambda: self.shift_calendar(months=1), "left")
        nav_button(cluster, "▶▶", lambda: self.shift_calendar(years=1), "left")

        # Everything below the header lives in a scrollable area, so when the
        # window is short (grid + open day panel taller than the viewport) the
        # user can scroll down to reach the panel instead of it being cut off.
        scroll_host = tk.Frame(parent)
        self.track_theme(scroll_host, bg="bg")
        scroll_host.pack(fill="both", expand=True)

        self.cal_scroll_canvas = tk.Canvas(scroll_host, highlightthickness=0, bg=self.colors["bg"])
        self.track_theme(self.cal_scroll_canvas, bg="bg")
        cal_sb = ttk.Scrollbar(scroll_host, orient="vertical", command=self.cal_scroll_canvas.yview)

        def _cal_view_moved(first, last, _set=cal_sb.set):
            _set(first, last)
            self._cal_scroll_moved(first)
        cal_sb.pack(side="right", fill="y")
        self.cal_scroll_canvas.pack(side="left", fill="both", expand=True)

        # The month, its day and the register's head in one chunk; the
        # register's rows below it, in chunks of their own: its pages, each
        # series unfolded to up to 50 days, grow without end (RowStack).
        self._cal_stack = self._row_stack(self.cal_scroll_canvas,
                                          scrolled=_cal_view_moved)
        self.cal_scroll_inner = self._cal_stack.group(bg="bg").add()
        self.track_theme(self.cal_scroll_inner, bg="bg")
        self._bind_mousewheel_recursive(self.cal_scroll_inner, self.cal_scroll_canvas)

        # Day panel: appears only when a day is selected, at the bottom of the
        # scrollable area. Fixed height; comfortable, not half the page.
        self.day_panel = tk.Frame(self.cal_scroll_inner, height=self.px(240))
        self.track_theme(self.day_panel, bg="sidebar")
        self.day_panel.pack_propagate(False)
        self.selected_day = None          # "YYYY-MM-DD" currently shown
        self._day_panel_mode = "empty"    # empty | list | note

        # The panel outlives every note shown in it, so its right-click is
        # bound once and asks what the panel shows. show_day_note bound it
        # anew each time -- one more Tcl command at every note opened -- and
        # the binding outlived the note: back on the day's list, a
        # right-click on the panel's bare edge offered the menu of the last
        # note opened.
        def _panel_menu(event):
            shows = getattr(self, "_day_panel_shows", None)
            if self._day_panel_mode == "note" and shows and shows[0] == "note":
                self.show_note_context_menu(event, shows[2],
                                            occurrence_date=shows[1])
        self.day_panel.bind("<Button-3>", _panel_menu)

        # History view state. The frame itself is persistent (built once,
        # track_theme); its ROWS are rebuilt on every render and colour
        # themselves with plain .configure — the two theming patterns,
        # each on the right side of the persistent/rebuilt line.
        self.history_frame = tk.Frame(self.cal_scroll_inner)
        self.track_theme(self.history_frame, bg="bg")
        self._history_visible = False
        self._history_built = False
        self._history_bucket = "All"
        self._history_expanded = set()   # note ids the user opened
        self._history_shown = 50         # top-level rows rendered so far
        self._history_search_job = None
        # What each series costs to work out, kept by history_entries while
        # the register is open, so a search keystroke only filters.
        self._history_memo = {}

        # Grid gets a comfortable minimum height so cells never shrink to
        # unusable slivers; if the window is smaller, the scrollbar kicks in.
        self.cal_grid_frame = tk.Frame(self.cal_scroll_inner, height=self.CAL_GRID_HEIGHT)
        self.track_theme(self.cal_grid_frame, bg="bg")
        self.cal_grid_frame.pack(side="top", fill="both", expand=True, padx=30, pady=(0, 10))
        self.cal_grid_frame.pack_propagate(False)

        # The month is DRAWN on this canvas: every day cell, its number,
        # dots, note titles and markers are shapes and text, not widgets
        # (see _draw_calendar_grid). Built once; render_calendar and every
        # change of size only redraw what is on it.
        self.cal_canvas = tk.Canvas(self.cal_grid_frame, highlightthickness=0,
                                    bg=self.colors["bg"])
        self.track_theme(self.cal_canvas, bg="bg")
        self.cal_canvas.pack(fill="both", expand=True)
        self._cal_cells = {}
        self._cal_month_data = None
        self._cal_hover_key = None
        self._cal_cursor = ""
        self.cal_canvas.bind("<Configure>", self._cal_canvas_configured, add="+")
        self.cal_canvas.bind("<Button-1>", self._cal_pressed)
        self.cal_canvas.bind("<Button-3>", self._cal_right_pressed)
        self.cal_canvas.bind("<Motion>", self._cal_pointer_moved)
        self.cal_canvas.bind("<Leave>", self._cal_pointer_left)
        # The keyboard's way round the month, as the note list has its own:
        # a ring on one day, the arrows move it, Return opens the day.
        self.cal_canvas.configure(takefocus=1)
        self._cal_key_day = None
        for seq, days in (("<Left>", -1), ("<Right>", 1), ("<Up>", -7), ("<Down>", 7)):
            self.cal_canvas.bind(seq, lambda e, d=days: self._cal_key_step(d))
        for seq in ("<Return>", "<space>", "<KP_Enter>"):
            self.cal_canvas.bind(seq, self._cal_key_open)
        for seq in ("<Shift-F10>", "<App>", "<Menu>"):
            try:
                self.cal_canvas.bind(seq, self._cal_key_menu)
            except tk.TclError:
                pass        # a keysym this platform does not have
        self._cal_has_keyboard = False
        self.cal_canvas.bind("<FocusIn>", lambda e: self._cal_keyboard_here(True), add="+")
        self.cal_canvas.bind("<FocusOut>", lambda e: self._cal_keyboard_here(False), add="+")
        # The wheel scrolls the calendar's own area, as it did over the old
        # cells; bound once, since the canvas outlives every render.
        self._bind_mousewheel_recursive(self.cal_grid_frame, self.cal_scroll_canvas)

        # Re-render the calendar when the window crosses the size threshold, so
        # note previews switch between small/large. Guarded so it only fires on
        # an actual step change (not on every pixel), avoiding needless redraws.
        self._cal_last_font_size = None

        def _on_resize(event):
            if self.notebook is None:
                return
            if not self._is_calendar_visible():
                return  # only when the Calendar tab is actually showing
            if self._history_visible:
                return  # the grid is hidden behind History; nothing to redraw
            size = self._cal_note_font_size()
            if size != self._cal_last_font_size:
                self._cal_last_font_size = size
                self.render_calendar()
        # On the grid's own <Configure>: the grid changes size exactly when
        # the step can change -- the window resized while the calendar is
        # showing, AND the calendar shown again after the window was
        # resized somewhere else (on the Notes tab, for one -- qa4 walks
        # it), which the window's own Configure never reports. It used to be
        # bound on the window with self.bind, which also ran it for every
        # widget laid out anywhere in the app -- 3,882 times for one
        # rebuild of a 300-note list -- and that storm was what happened
        # to cover the second case. The drawing sets the grid's height to
        # fit the month, which brings this back, but the window's width --
        # and so the step -- has not changed by then, so it cannot feed
        # itself.
        self.cal_grid_frame.bind("<Configure>", _on_resize, add="+")

        self.bind_all("<Prior>", lambda e: self._calendar_key(e, months=-1))
        self.bind_all("<Next>", lambda e: self._calendar_key(e, months=1))
        self.bind_all("<Control-Prior>", lambda e: self._calendar_key(e, years=-1))
        self.bind_all("<Control-Next>", lambda e: self._calendar_key(e, years=1))
        self.bind_all("<Home>", lambda e: self._calendar_key(e, today=True))

    def _is_calendar_visible(self):
        """True only if the Calendar tab is both selected AND actually on
        screen. The notebook's own idea of 'which tab is selected' doesn't
        change just because the Settings page is currently covering it (they're
        siblings, and showing one doesn't clear the other's selection) — so
        checking the tab index alone isn't enough on its own, or calendar
        keyboard shortcuts and resize-driven relayout could silently act on a
        calendar the user can't currently see, behind the Settings page."""
        try:
            if not self.notebook.winfo_ismapped():
                return False
            return self.notebook.index(self.notebook.select()) == self.TAB_CALENDAR
        except tk.TclError:
            return False

    def _calendar_key(self, event, months=0, years=0, today=False):
        """Keyboard navigation, but only while the Calendar tab is showing and
        the user isn't typing — otherwise PgUp/Home would hijack the editor."""
        # Nor while a question is waiting for an answer: the grid would
        # move to another month underneath the question about a day in it.
        if self._a_dialog_is_asking():
            return "break"
        if not self._is_calendar_visible():
            return

        # bind_all delivers the key to whichever widget has focus, so the
        # event's own widget is the reliable signal. focus_get() is only a
        # fallback for synthetic calls.
        # Every kind of box Tk types into, built here or not.
        typing_widgets = (tk.Text, tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox)
        source = getattr(event, "widget", None)
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if any(isinstance(w, typing_widgets) for w in (source, focused)):
            return

        if self._history_visible:
            # The register covers the month: the keys page the register, and
            # Home goes to its top. They used to move the hidden month, which
            # showed on the way back -- three PgDn from July came back October.
            view = self.cal_scroll_canvas
            if today:
                view.yview_moveto(0)
            else:
                first, last = view.yview()
                if not (first <= 0.0 and last >= 1.0):
                    view.yview_scroll(1 if (months or years) > 0 else -1, "pages")
            return "break"

        if today:
            self.go_to_today()
        else:
            self.shift_calendar(months=months, years=years)
        return "break"

    def shift_calendar(self, months=0, years=0):
        total = (self.cal_year * 12 + (self.cal_month - 1)) + years * 12 + months
        year, month = total // 12, (total % 12) + 1
        # datetime can't represent anything outside these bounds, and walking
        # past them would crash the grid rather than just look odd.
        if not 1 <= year <= 9999:
            return
        self.cal_year, self.cal_month = year, month
        self.render_calendar()

    def go_to_today(self):
        today = datetime.now()
        self.cal_year, self.cal_month = today.year, today.month
        self._cal_key_day = today.strftime("%Y-%m-%d")
        self.render_calendar()

    def _cal_note_font_size(self):
        """Two-step sizing: bigger note previews in a wide window, smaller in a
        narrow one. Two fixed steps (not continuous) so there's no flicker."""
        try:
            w = self.winfo_width()
        except tk.TclError:
            w = self.px(900)
        return 11 if w >= self.px(1150) else 9

    # The month grid's geometry, as the widget grid it replaces laid it out:
    # seven equal columns, a row of weekday names, and week rows all as tall
    # as the busiest day needs (never under 90), each cell inset by 3. The
    # grid's frame starts 520 pixels tall and then takes the month's height.
    CAL_GRID_HEIGHT = 520
    CAL_CELL_PAD = 3
    CAL_ROW_MIN = 90
    CAL_CHIP_WRAP = 88          # a note title wraps here, as its Label did
    CAL_MAX_CHIPS = 2           # titles a day shows before "+N more"
    CAL_LABEL_INSET = 3         # what a Label kept round its text (bd + pad)

    def _draw_day_badge(self, date_str):
        """Draw (or redraw) the small marker-emoji badge in a day cell's
        corner, capped to a handful so it can't sprawl across the cell. Its
        item is kept in the day's record, so _refresh_day_badge can replace
        just this one badge later without touching anything else."""
        rec = self._cal_cells.get(date_str)
        if rec is None:
            return
        cv = self.cal_canvas
        old = rec["items"].pop("badge", None)
        if old is not None:
            cv.delete(old)
        markers = self.day_emoji.get(date_str) or []
        if not markers:
            return
        font = self._cal_font(("Segoe UI Emoji", 10))[0]
        right = rec["x1"] - self.CAL_CELL_PAD - self.CAL_LABEL_INSET
        # The corner shares its row with the day's number, centred above it:
        # three markers at the default window's cell width printed over the
        # number (the widget grid's opaque badge hid it instead). So the
        # badge keeps to the room right of the number, and the markers that
        # do not fit there are counted: "⭐+2" rather than a covered "15".
        number = cv.bbox(rec["items"]["day"]) if "day" in rec["items"] else None
        room = right - (number[2] + 4) if number else right - rec["x0"]
        badge_text = f"+{len(markers)}"
        for shown in range(min(3, len(markers)), 0, -1):
            text = "".join(markers[:shown])
            if len(markers) > shown:
                text += f"+{len(markers) - shown}"
            if font.measure(text) <= room:
                badge_text = text
                break
        rec["items"]["badge"] = cv.create_text(
            right, rec["y0"] + self.CAL_CELL_PAD + self.CAL_LABEL_INSET,
            anchor="ne", text=badge_text, font=font,
            fill=rec["fg"], tags=("cal", rec["tag"]))

    def _refresh_day_badge(self, date_str):
        """Update just ONE day's marker badge in place — used after saving
        picks from the Mark-this-day popup, where a whole render would redraw
        every day for a single small change. Nothing to do when that day is
        not drawn (the month changed since the popup opened, or the calendar
        was never shown): the next render picks the markers up."""
        self._draw_day_badge(date_str)

    def render_calendar(self):
        # Rebuilding ~35-42 day cells for a month nobody is looking at is
        # work the user pays for and never sees. Measured from the Notes
        # tab: 36ms and 98 widgets, on every delete, save, import and
        # category change -- a quarter of what a delete costs, spent on
        # the other tab.
        #
        # apply_theme has skipped this since the theme-switch flicker
        # work, with the reasoning written beside it; every OTHER caller
        # went through regardless. The decision belongs here, once, so
        # every call site is right by construction rather than
        # by each having remembered.
        #
        # Deferring is only safe because something catches it up before
        # the calendar can be seen again. There are exactly four ways
        # back to it, and all four are covered: switching tabs
        # (_on_tab_changed), leaving Settings (hide_settings_page),
        # "Back to Calendar" (which selects the tab, so the first), and
        # already standing on it -- where this guard does not fire at
        # all. _calendar_is_showing() answers the question from the
        # notebook's own selection rather than winfo_ismapped(), which
        # pack() does not update synchronously.
        if not self._calendar_is_showing():
            self._calendar_needs_render = True
            return

        # Expand every note's occurrences across the visible month only.
        # Recurring notes are stored once; their dates are computed here.
        # Worked out BEFORE the title and the month's record change: when
        # this raised (it did, for December 9999), the new title went up
        # over the old month's days, and a click opened a day of the month
        # the title said was gone.
        month_start = date_cls(self.cal_year, self.cal_month, 1)
        month_end = date_cls(
            self.cal_year, self.cal_month,
            cal_module.monthrange(self.cal_year, self.cal_month)[1]
        )
        notes_by_date = {}
        for n in self.notes:
            for occurrence in expand_occurrences(n, month_start, month_end):
                notes_by_date.setdefault(occurrence, []).append(n)
        weeks = cal_module.monthcalendar(self.cal_year, self.cal_month)

        month_name = cal_module.month_name[self.cal_month]
        # The caret is the only hint that this opens a jump dialog, so it
        # replaces the instruction text that used to sit under the header.
        self.cal_month_lbl.config(text=f"{month_name} {self.cal_year}  ⌄")

        # What the month shows, kept so a change of size can draw it again
        # without working the occurrences out again.
        self._cal_month_data = {
            "year": self.cal_year, "month": self.cal_month,
            "notes_by_date": notes_by_date,
            "weeks": weeks,
            # Which notes it was worked out from (see _notes_on_day).
            "notes": self.notes, "count": len(self.notes),
        }
        self._draw_calendar_grid()
        # A fresh drawing has no selected-day border -- re-mark the open
        # day, if its month is on screen.
        self._update_selected_day_outline()
        # The open day's panel is one more view of the same data, and it
        # was drawn when the day opened: a delete's Undo put the note back
        # on the grid and left the open list without it, a category change
        # left its stripe in the old colour. So every route that redraws
        # the month redraws the open day -- when what it shows has changed,
        # and only then, so paging the months past a busy day costs nothing.
        _redraw_open_day(self, notes_by_date, self.cal_year, self.cal_month)
        # render_calendar is the single signal "calendar data changed,
        # redraw" — every mutation (delete, restore, save, duplicate)
        # calls it. When the History register is the visible view, it is
        # a THIRD view of the same data and must refresh here too, or a
        # delete only showed after a trip out to the grid and back
        # (field report).
        if self._history_visible:
            self._render_calendar_history()

    # ---------- The month grid, drawn ----------

    def _cal_font(self, spec):
        """A font the grid draws with, and its line height -- measured once,
        because every cell asks the same few."""
        cache = getattr(self, "_cal_font_cache", None)
        if cache is None:
            cache = self._cal_font_cache = {}
        found = cache.get(spec)
        if found is None:
            import tkinter.font as tkfont
            font = tkfont.Font(root=self, font=spec)
            found = cache[spec] = (font, font.metrics("linespace"))
        return found

    def _draw_calendar_grid(self):
        """Draw the month on the calendar's canvas.

        The grid used to be built of widgets -- a Frame per day, a Label for
        its number, each dot, each note title, a Frame per divider: 216
        windows for a month holding 46 notes, every one of which Windows had
        to place and paint again at each step of a window resize. The same
        cells are now rectangles and text on one canvas.

        Laid out as the widget grid did, measured on it: seven columns of
        floor(i * width / 7), a row of weekday names 26 pixels deep, and week
        rows as tall as the tallest day needs (never under 90), each cell
        inset by 3. Inside a cell, everything sits where pack put it -- the
        comments below give the paddings it used. A day's content is drawn
        at the origin first, because the row height depends on the tallest
        day, and moved into place once that is known.
        """
        cv = self.cal_canvas
        cv.delete("cal")
        self._cal_cells = {}
        # The hover is forgotten with the drawing it was about, and so is
        # the preview it put up. Nothing else would take that down: the
        # pointer has not moved (PgDn changed the month under it), and over
        # a gap or the weekday names "nothing under the pointer" matched
        # the forgotten "nothing", so July's preview sat over August.
        self._cal_hover_key = None
        self.hide_day_tooltip()
        data = self._cal_month_data
        if data is None:
            return
        width = cv.winfo_width()
        if width <= 1:
            width = self.cal_grid_frame.winfo_width()
        if width <= 1:
            # Not laid out yet: the canvas's first <Configure> draws it.
            return
        self._cal_drawn_width = width
        c = self.colors
        pad = self.CAL_CELL_PAD
        inset = self.CAL_LABEL_INSET
        cols = [int(i * width / 7) for i in range(8)]

        header_font, header_ls = self._cal_font(("Segoe UI", 9, "bold"))
        header_h = header_ls + 2 * inset + 5        # the Label, and pady (0, 5)
        for i, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            cv.create_text((cols[i] + cols[i + 1]) / 2.0, inset, anchor="n",
                           text=name, font=header_font, fill=c["subtext"],
                           tags=("cal",))

        today_str = datetime.now().strftime("%Y-%m-%d")
        year, month = data["year"], data["month"]
        placed = []
        tallest = 0
        for week_index, week in enumerate(data["weeks"]):
            for col, day in enumerate(week):
                if not day:
                    continue
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                cell_w = cols[col + 1] - cols[col] - 2 * pad
                rec = self._draw_cal_cell_content(
                    date_str, day, data["notes_by_date"].get(date_str, []),
                    date_str == today_str, cell_w)
                tallest = max(tallest, rec["needs"])
                placed.append((week_index, col, rec))
        row_h = max(self.CAL_ROW_MIN, tallest + 2 * pad)

        for week_index, col, rec in placed:
            x0 = cols[col] + pad
            y0 = header_h + week_index * row_h + pad
            x1 = cols[col + 1] - pad
            y1 = y0 + row_h - 2 * pad
            rec.update(x0=x0, y0=y0, x1=x1, y1=y1)
            cv.move(rec["tag"], x0, y0)
            rec["chips"] = [(note, (bx0 + x0, by0 + y0, bx1 + x0, by1 + y0))
                            for note, (bx0, by0, bx1, by1) in rec["chips"]]
            bg = cv.create_rectangle(x0, y0, x1, y1, fill=rec["bg"], outline="",
                                     tags=("cal", rec["tag"]))
            # Under the day's own number, dots and titles, which were drawn
            # first so they could be measured.
            cv.tag_lower(bg)
            rec["items"]["bg"] = bg
            self._cal_cells[rec["date"]] = rec
            self._draw_day_badge(rec["date"])

        # The frame the grid lives in is as tall as the grid, as it was
        # when its rows asked for their height -- one busy day makes every
        # week taller, and the calendar area scrolls.
        total = header_h + len(data["weeks"]) * row_h
        try:
            if int(self.cal_grid_frame.cget("height")) != total:
                self.cal_grid_frame.configure(height=total)
        except tk.TclError:
            pass
        self._cal_paint_key_ring()

    # ---- The keyboard on the month ----

    def _cal_keyboard_here(self, here):
        """The canvas took or lost the keyboard: its ring follows."""
        self._cal_has_keyboard = here
        self._cal_paint_key_ring()

    def _cal_key_date(self):
        """The day the keyboard is on in the month shown: the one it was
        left on; after a change of month, the same day of the month; else
        the open day, today, or the first."""
        cells = self._cal_cells or {}
        if not cells:
            return None
        key = self._cal_key_day
        if key in cells:
            return key
        days = sorted(cells)
        was = parse_date(key) if key else None
        if was is not None:
            key = days[min(was.day, len(days)) - 1]
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            key = next((d for d in (self.selected_day, today) if d in cells),
                       days[0])
        self._cal_key_day = key
        return key

    def _cal_key_step(self, days):
        """An arrow: the ring goes a day, or a week, that way -- into the
        next month or the last one when it runs off this one."""
        here = self._cal_key_date()
        day = parse_date(here) if here else None
        if day is None:
            return "break"
        try:
            to = day + timedelta(days=days)
        except OverflowError:
            return "break"
        self._cal_key_day = to.isoformat()
        if (to.year, to.month) != (self.cal_year, self.cal_month):
            self.cal_year, self.cal_month = to.year, to.month
            self.render_calendar()
        self._cal_paint_key_ring()
        rec = self._cal_cells.get(self._cal_key_day)
        if rec is not None:
            self._bring_into_sight(self.cal_canvas, part=(rec["y0"], rec["y1"]))
        return "break"

    def _cal_key_open(self, event=None):
        """Return or Space: the day opens, as a click on it does. Enter held
        down opens it once, and the day's own controls do not take the
        repeats for presses (_enter_repeats)."""
        if self._enter_repeats(event):
            return "break"
        day = self._cal_key_date()
        if day:
            self.open_day_popup(day)
        return "break"

    def _cal_key_menu(self, _event=None):
        """Shift+F10 or the menu key: the day's right-click menu, at it."""
        day = self._cal_key_date()
        rec = self._cal_cells.get(day) if day else None
        if rec is None:
            return "break"
        cv = self.cal_canvas
        x, y = rec["x0"] + 6, rec["y1"] - 6
        self.show_day_context_menu(
            SimpleNamespace(widget=cv, x=x, y=y, x_root=cv.winfo_rootx() + x,
                            y_root=cv.winfo_rooty() + y), day)
        return "break"

    def _cal_paint_key_ring(self):
        """The keyboard's ring round its day, in the gap between the cells,
        while the canvas holds the keyboard; the open day's own outline
        is drawn inside the cell, in the accent."""
        cv = self.cal_canvas
        if cv is None:
            return
        try:
            cv.delete("cal_key")
            if not self._cal_has_keyboard:
                return
            rec = self._cal_cells.get(self._cal_key_date())
            if rec is None:
                return
            cv.create_rectangle(rec["x0"] - 2, rec["y0"] - 2,
                                rec["x1"] + 2, rec["y1"] + 2,
                                outline=self._focus_ring(), width=self.px(2),
                                tags=("cal_key",))
        except tk.TclError:
            pass

    def _draw_cal_cell_content(self, date_str, day, day_notes, is_today, w):
        """Draw one day's number, dots, titles and "+N more" with the cell's
        top-left corner at the canvas origin, and say how tall it needs to
        be. Returns the day's record; the caller moves it into place."""
        cv = self.cal_canvas
        c = self.colors
        inset = self.CAL_LABEL_INSET
        tag = "calday" + date_str
        tags = ("cal", tag)
        day_color = self.day_colors.get(date_str)
        # On a painted day, whichever of near-black and white reads on that
        # paint -- always white made the number, titles and markers all but
        # vanish on the palette's yellows and light teals (1.3:1). The
        # theme's own colours otherwise.
        fg = contrasting_fg(day_color) if day_color else c["text"]
        items = {}
        chips = []
        y = 0
        if is_today:
            # A thin accent bar marks "today", apart from the category dots
            # so the two are not confused.
            items["today"] = cv.create_rectangle(0, 0, w, 3, fill=c["accent"],
                                                 outline="", tags=tags)
            y = 3
        day_font, day_ls = self._cal_font(("Segoe UI", 11, "bold" if is_today else "normal"))
        y += 4                                          # pady (4, 2)
        items["day"] = cv.create_text(w / 2.0, y + inset, anchor="n", text=str(day),
                                      font=day_font, fill=fg, tags=tags)
        y += day_ls + 2 * inset + 2
        if day_notes:
            dot_font, dot_ls = self._cal_font(("Segoe UI", 9))
            colours = []
            for n in day_notes:
                colour = self.get_note_color(effective_note(n, date_str))
                if colour not in colours:
                    colours.append(colour)
            dot_w = dot_font.measure("●") + 2 * inset   # each dot's Label
            step = dot_w + 2                            # ...and padx 1 either side
            # As many dots as the cell holds, the last place saying "and
            # more" when the colours outnumber them. The widget grid clipped
            # a row of dots at its cell's edge; a drawing clips nothing, and
            # a day of eight colours spilled its dots into the next days.
            fits = max(2, (w - 4) // step)
            shown = colours if len(colours) <= fits else colours[:fits - 1]
            places = len(shown) + (len(shown) < len(colours))
            left = (w - step * places) // 2 + 1
            items["dots"] = [
                cv.create_text(left + i * step + dot_w / 2.0, y + inset, anchor="n",
                               text="●", font=dot_font, fill=colour, tags=tags)
                for i, colour in enumerate(shown)]
            if len(shown) < len(colours):
                items["more_dots"] = cv.create_text(
                    left + len(shown) * step + dot_w / 2.0, y + inset, anchor="n",
                    text="+", font=dot_font,
                    fill=(fg if day_color else c["subtext"]), tags=tags)
            y += dot_ls + 2 * inset + 2                 # pady (0, 2)

            # Up to two titles at a readable size (bigger in a wide
            # window), a thin divider between them, then "+N more".
            note_fs = self._cal_note_font_size()
            chip_font, _chip_ls = self._cal_font(("Segoe UI", note_fs))
            shown = day_notes[:self.CAL_MAX_CHIPS]
            items["chips"] = []
            for index, note in enumerate(shown):
                eff = effective_note(note, date_str)
                full_title = _note_str(eff, "title") or "(untitled)"
                text = _truncate(full_title, 16)
                # An emoji that truncation would cut off is surfaced up
                # front, so the title stays recognisable at a glance.
                found_emoji = _extract_first_emoji(full_title)
                if found_emoji and found_emoji not in text:
                    text = f"{found_emoji} {text}"
                if is_recurring(note):
                    text = "🔁 " + text
                # Wrapped at 88 and centred as a block, left-justified inside
                # -- the Label spanned the cell and centred what it held.
                item = cv.create_text(w / 2.0, y + inset, anchor="n", text=text,
                                      width=self.CAL_CHIP_WRAP, justify="left",
                                      font=chip_font, fill=fg, tags=tags)
                box = cv.bbox(item)
                text_h = (box[3] - box[1]) if box else _chip_ls
                chip_h = text_h + 2 * inset
                # The chip is the NOTE, and behaves like one: found under the
                # pointer by this box (see _cal_hit), it opens that note, its
                # right-click is the note's menu, and hovering previews it.
                chips.append((note, (2, y, w - 2, y + chip_h)))
                items["chips"].append(item)
                y += chip_h + 1                         # pady (0, 1)
                if index < len(shown) - 1:
                    line_y = y + 1                      # a divider, pady 1
                    items.setdefault("dividers", []).append(cv.create_rectangle(
                        10, line_y, w - 10, line_y + 1, fill=c["subtext"],
                        outline="", tags=tags))
                    y = line_y + 2
            if len(day_notes) > self.CAL_MAX_CHIPS:
                more_font, more_ls = self._cal_font(
                    ("Segoe UI", max(note_fs - 1, 8), "italic"))
                items["more"] = cv.create_text(
                    2 + inset, y + inset, anchor="nw",
                    text=f"+{len(day_notes) - self.CAL_MAX_CHIPS} more",
                    font=more_font, fill=(fg if day_color else c["subtext"]), tags=tags)
                y += more_ls + 2 * inset + 4            # pady (0, 4)
            else:
                y += 2                                  # the 2-pixel spacer frame
        else:
            # The empty day's spacer, which kept row heights even.
            y += self._cal_font(("Segoe UI", 4))[1] + 2 * inset
        return {"date": date_str, "tag": tag, "items": items, "chips": chips,
                "bg": day_color or c["card"], "fg": fg, "has_notes": bool(day_notes),
                "needs": y + 12}                        # ipady 6, top and bottom

    def _cal_canvas_configured(self, event):
        """The canvas changed size. A new width lays the month out again
        from what render_calendar worked out -- no occurrences expanded, no
        widget made. A new height alone is the grid's own doing (it sets the
        frame's height to fit its rows), and needs nothing."""
        if event.width == getattr(self, "_cal_drawn_width", None):
            return
        if self._cal_month_data is None:
            return
        if not self._calendar_is_showing():
            return
        self._draw_calendar_grid()
        self._update_selected_day_outline()

    def _cal_hit(self, x, y):
        """What lies under a point of the grid: ("chip", date, note) for a
        note's title, ("day", date, None) for the rest of a day's cell, or
        None for the gaps and the weekday names."""
        for date_str, rec in self._cal_cells.items():
            if rec["x0"] <= x <= rec["x1"] and rec["y0"] <= y <= rec["y1"]:
                for note, (bx0, by0, bx1, by1) in rec["chips"]:
                    if bx0 <= x <= bx1 and by0 <= y <= by1:
                        return ("chip", date_str, note)
                return ("day", date_str, None)
        return None

    def _cal_pressed(self, event):
        """A click on the grid. A note's title opens that one note; the rest
        of the cell -- its number, dots, "+N more", the background -- opens
        the day, as the day's widgets each did."""
        hit = self._cal_hit(event.x, event.y)
        if hit is None:
            return
        kind, date_str, note = hit
        if kind == "chip":
            self._open_note_from_grid(note, date_str)
        else:
            self.open_day_popup(date_str)

    def _cal_right_pressed(self, event):
        """Right-click: the note's own menu on its title, the day's menu on
        the rest of the cell -- those are the day, and a title is a note."""
        hit = self._cal_hit(event.x, event.y)
        if hit is None:
            return
        kind, date_str, note = hit
        if kind == "chip":
            self.show_note_context_menu(event, note, occurrence_date=date_str)
        else:
            self.show_day_context_menu(event, date_str)

    def _cal_pointer_moved(self, event):
        """Hovering. Over a title, a preview of that one note; over the rest
        of a day that has notes, a titles-only summary of the day; each shown
        once, when the pointer arrives. And the hand over a day, the plain
        pointer over the gaps -- what the cells' own cursor said."""
        hit = self._cal_hit(event.x, event.y)
        want = "hand2" if hit is not None else ""
        if want != self._cal_cursor:
            self._cal_cursor = want
            try:
                self.cal_canvas.configure(cursor=want)
            except tk.TclError:
                pass
        if hit is None:
            key = None
        elif hit[0] == "chip":
            key = ("chip", hit[1], id(hit[2]))
        else:
            key = ("day", hit[1])
        if key == self._cal_hover_key:
            return
        self._cal_hover_key = key
        self.hide_day_tooltip()
        if hit is None:
            return
        if hit[0] == "chip":
            self.show_note_hover_preview(hit[2], hit[1])
        elif self._cal_cells[hit[1]]["has_notes"]:
            self.show_day_summary_tooltip(hit[1])

    def _cal_scroll_moved(self, first):
        """The calendar's scroll area moved: the days slid under a pointer
        that stayed still, so a preview describes what is no longer under
        it. The wheel scrolls without a redraw, and only a redraw used to
        take a preview down (_draw_calendar_grid) -- PgDn's fix, which the
        wheel never reached. Only the top of the view counts: content that
        grows or shrinks below leaves every day where it was."""
        if first == getattr(self, "_cal_scroll_first", None):
            return
        self._cal_scroll_first = first
        self._cal_hover_key = None
        self.hide_day_tooltip()

    def _cal_pointer_left(self, _event=None):
        self._cal_hover_key = None
        self._cal_cursor = ""
        try:
            self.cal_canvas.configure(cursor="")
        except tk.TclError:
            pass
        self.hide_day_tooltip()

    def _cal_cell_view(self, date_str):
        """What one drawn day shows, read back from the drawing itself --
        the question checks ask now that a cell has no widgets."""
        rec = self._cal_cells.get(date_str)
        if rec is None:
            return None
        cv = self.cal_canvas
        it = rec["items"]

        def text(item):
            return cv.itemcget(item, "text") if item is not None else ""

        selected = [i for i in cv.find_withtag("cal_selected")
                    if tuple(int(round(v)) for v in cv.coords(i))
                    == (rec["x0"] + 1, rec["y0"] + 1, rec["x1"] - 1, rec["y1"] - 1)]
        return {
            "box": (rec["x0"], rec["y0"], rec["x1"], rec["y1"]),
            "bg": cv.itemcget(it["bg"], "fill"),
            "day": text(it.get("day")),
            "day_fill": cv.itemcget(it["day"], "fill"),
            "today": "today" in it,
            "badge": text(it.get("badge")),
            "badge_fill": cv.itemcget(it["badge"], "fill") if "badge" in it else "",
            "dots": [cv.itemcget(d, "fill") for d in it.get("dots", [])],
            "more_dots": text(it.get("more_dots")),
            "chips": [text(t) for t in it.get("chips", [])],
            "chip_fill": [cv.itemcget(t, "fill") for t in it.get("chips", [])],
            "more": text(it.get("more")),
            "selected_width": (float(cv.itemcget(selected[0], "width")) if selected else 0),
            "selected_colour": (cv.itemcget(selected[0], "outline") if selected else ""),
        }

    def _cal_texts(self):
        """Every text the month grid draws, in no particular order."""
        cv = self.cal_canvas
        return [cv.itemcget(i, "text") for i in cv.find_withtag("cal")
                if cv.type(i) == "text"]

    def _cal_point(self, date_str, chip=None):
        """Where to point, in the canvas's own coordinates, to reach a day
        -- a spot of its cell that holds nothing else -- or one of its
        titles (chip = its index)."""
        rec = self._cal_cells.get(date_str)
        if rec is None:
            return None
        if chip is not None:
            _note, (bx0, by0, bx1, by1) = rec["chips"][chip]
            return (int((bx0 + bx1) / 2), int((by0 + by1) / 2))
        return (rec["x0"] + 6, rec["y1"] - 6)

    def maybe_show_reminder(self):
        """Show a subtle 'you have notes today' bar — but only once per calendar
        day, and only if there actually are notes due today."""
        if not self._still_alive():
            return
        today = datetime.now().strftime("%Y-%m-%d")
        settings = load_settings()
        if settings.get("reminder_last_shown") == today:
            return  # already shown (or dismissed) today
        due = self.notes_on_date(today)
        if not due:
            return
        self._render_reminder_bar(len(due), today)
        # Marked once it is on screen, so it won't reappear on the next
        # launch. Marked first, a bar that failed to draw was spent unseen.
        settings["reminder_last_shown"] = today
        save_settings(settings)

    def _render_reminder_bar(self, count, today):
        self._reminder_bar_day = today
        for w in self.reminder_bar.winfo_children():
            w.destroy()
        # Above whichever page is showing: with Settings open the notebook
        # is not packed, and Tk refused to pack the bar before it.
        page = (self.settings_page if getattr(self, "_settings_open", False)
                else self.notebook)
        self.reminder_bar.pack(fill="x", side="top", before=page)

        noun = "note" if count == 1 else "notes"
        # Written out day first, as every date in the app is shown.
        day = parse_date(today)
        friendly = show_day(day, year=False) if day else today
        msg = tk.Label(
            self.reminder_bar,
            text=f"🔔  You have {count} {noun} for today ({friendly}).",
            bg=self.colors["accent"], fg=self._on_fill("accent"), font=("Segoe UI", 9, "bold"),
            anchor="w", cursor="hand2"
        )
        # Both words are Tab stops, ringed in the bar's own words' colour;
        # a pixel of padding each gives the ring its room.
        self._ring_round(msg, on=self._on_fill("accent"))
        msg.pack(side="left", padx=13, pady=5)
        self._pressable(msg, lambda: self._open_today_from_reminder(today))
        # Clicking the text jumps to today's notes in the calendar. Kept on
        # a half-written template ("Save changes?" answered Cancel), the
        # click stops here: the window's click-outside, still to run for
        # it, would ask the same question again.
        msg.bind("<Button-1>",
                 lambda e: ("break" if self._open_today_from_reminder(today)
                            is False else None))

        close = tk.Label(self.reminder_bar, text="✕", bg=self.colors["accent"],
                         fg=self._on_fill("accent"), font=("Segoe UI", 10, "bold"),
                         cursor="hand2")
        self._ring_round(close, on=self._on_fill("accent"))
        close.pack(side="right", padx=11)
        close.bind("<Button-1>", lambda e: self.dismiss_reminder())
        self._pressable(close, self.dismiss_reminder)

    def _open_today_from_reminder(self, today):
        """The bar's click lands on the day it names, on screen: on its own
        month, from Settings too. The bar sits above every page, and this
        used to open the day behind Settings, where nothing showed, or
        under whichever month was shown, with no day outlined. Returns
        False when the person stayed where they were."""
        # Settings is left the way Ctrl+N leaves it; a popup holding typed
        # work may ask to stay, and then the click does nothing.
        if not self._leave_settings_for_the_editor():
            return False
        self.notebook.select(self.TAB_CALENDAR)
        if self._history_visible:
            self._hide_calendar_history()
        d = parse_date(today)
        if d is not None:
            self.cal_year, self.cal_month = d.year, d.month
        self.render_calendar()
        self.open_day_popup(today)

    def dismiss_reminder(self):
        """Hide the reminder bar for the rest of the session."""
        self.reminder_bar.pack_forget()

    def _watch_the_day(self):
        """Once a minute: when the date has changed since the last look, a
        bar for an earlier day goes and the new day's is asked for. Asked
        only at start, an app left open overnight, or woken from sleep the
        next day, never reminded about the new day's notes."""
        if not self._still_alive():
            return
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            if today != self._reminder_day:
                if getattr(self, "_reminder_bar_day", None) not in (None, today):
                    self.dismiss_reminder()
                self.maybe_show_reminder()
        finally:
            # Whatever the look met, the next one comes: an error here used
            # to end the watch for the rest of the session.
            self._reminder_day = today
            self.after(60_000, self._watch_the_day)

    def show_day_summary_tooltip(self, date_str):
        """Compact, TITLES-ONLY list for hovering the day cell itself (not a
        specific note's chip). Deliberately shows no note bodies — with many
        notes on one day this would otherwise balloon into a huge box, which
        is exactly what this avoids.

        Nothing hovers over an open menu. A right-click menu keeps the
        app's event loop running, so drifting the mouse a few pixels onto
        a neighbouring cell still fires this -- and the preview drew
        itself over the menu the user was reading.
        """
        if getattr(self, "_context_menu_open", False):
            return
        self.hide_day_tooltip()
        day_notes = _notes_on_day(self, date_str)
        if not day_notes:
            return

        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        x = self.winfo_pointerx() + 16
        y = self.winfo_pointery() + 12
        tip.geometry(f"+{x}+{y}")

        outer = tk.Frame(tip, bg=self.colors["accent"], padx=1, pady=1)
        outer.pack()
        container = tk.Frame(outer, bg=self.colors["card"], padx=10, pady=8)
        container.pack()

        day = parse_date(date_str)
        friendly = (show_day(day, year=False, short_month=True) if day
                    else date_str)
        tk.Label(container, text=f"{friendly} — {len(day_notes)} note(s)",
                 bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))

        for base_note in day_notes[:10]:  # a title per line is cheap; cap generously
            note = effective_note(base_note, date_str)
            color = self.get_note_color(note)
            row = tk.Frame(container, bg=self.colors["card"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text="●", fg=color, bg=self.colors["card"],
                     font=("Segoe UI", 8)).pack(side="left", padx=(0, 5))
            title_text = _truncate(_note_str(note, "title") or "(untitled)", 34)
            if is_recurring(base_note):
                title_text = "🔁 " + title_text
            tk.Label(row, text=title_text, bg=self.colors["card"], fg=self.colors["text"],
                     font=("Segoe UI", 9), anchor="w").pack(side="left")

        if len(day_notes) > 10:
            tk.Label(container, text=f"+{len(day_notes) - 10} more — click to see all",
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8, "italic")).pack(anchor="w", pady=(4, 0))

        self._day_tooltip = tip

    def show_note_hover_preview(self, base_note, date_str):
        """Focused preview for hovering ONE specific note's title chip in a
        calendar cell — just that note, not the whole day crammed together.

        Suppressed while a right-click menu is open, for the same reason
        as the day summary above.
        """
        if getattr(self, "_context_menu_open", False):
            return
        self.hide_day_tooltip()
        note = effective_note(base_note, date_str)
        color = self.get_note_color(note)

        tip = tk.Toplevel(self)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        x = self.winfo_pointerx() + 16
        y = self.winfo_pointery() + 12
        tip.geometry(f"+{x}+{y}")

        outer = tk.Frame(tip, bg=self.colors["accent"], padx=1, pady=1)
        outer.pack()
        row = tk.Frame(outer, bg=self.colors["card"])
        row.pack()
        stripe = tk.Frame(row, bg=color, width=3)
        stripe.pack(side="left", fill="y")
        inner = tk.Frame(row, bg=self.colors["card"], padx=10, pady=8)
        inner.pack(side="left")

        title_text = _truncate(_note_str(note, "title") or "(untitled)", 60)
        if is_recurring(base_note):
            title_text = "🔁 " + title_text
        tk.Label(inner, text=title_text, bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w", justify="left",
                 wraplength=self.px(260)).pack(anchor="w")

        if is_recurring(base_note):
            tk.Label(inner, text=describe_recurrence(base_note), bg=self.colors["card"],
                     fg=self.colors["accent_text"], font=("Segoe UI", 8, "italic"),
                     anchor="w", justify="left").pack(anchor="w")

        # The raw body used to go straight in here, tables and all, so a
        # note with a table hovered as a wall of vertical bars -- and
        # unlike the panel below, this preview never even said a table
        # was there. It is the same quick look, so it follows the same
        # rule: the note's words, and a chip for what else it carries.
        preview, tables_here = core_tables.preview_text(_note_str(note, "body"))
        preview = preview.strip()
        if preview:
            if len(preview) > 150:
                preview = preview[:150].strip() + "…"
            tk.Label(inner, text=preview, bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8), anchor="w", justify="left",
                     wraplength=self.px(260)).pack(anchor="w", pady=(3, 0))

        icons = []
        if tables_here:
            icons.append("▦ 1 table" if tables_here == 1
                         else "▦ %d tables" % tables_here)
        if note.get("comments"):
            icons.append("💬")
        if note.get("attachments"):
            icons.append(f"📎×{len(note['attachments'])}")
        checklist = note.get("checklist") or []
        if isinstance(checklist, list) and checklist:
            done = sum(1 for it in checklist if isinstance(it, dict) and it.get("done"))
            icons.append(f"☑ {done}/{len(checklist)}")
        if icons:
            tk.Label(inner, text="   ".join(icons), bg=self.colors["card"],
                     fg=self.colors["subtext"], font=("Segoe UI", 8)
                     ).pack(anchor="w", pady=(4, 0))

        self._day_tooltip = tip

    def _clear_day_panel(self):
        for w in self.day_panel.winfo_children():
            w.destroy()

    def _render_day_panel_empty(self):
        self._clear_day_panel()
        self._day_panel_mode = "empty"

    def show_day_list(self):
        """Show the selected day's notes as a scrollable list inside the panel."""
        if not self.selected_day:
            self._render_day_panel_empty()
            return
        self._clear_day_panel()
        self._day_panel_mode = "list"
        date_str = self.selected_day

        day = parse_date(date_str) if isinstance(date_str, str) else None
        friendly = show_day(day) if day else str(date_str)

        header = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        header.pack(fill="x", padx=15, pady=(10, 6))
        tk.Label(header, text=friendly, font=("Segoe UI", 12, "bold"),
                 bg=self.colors["sidebar"], fg=self.colors["text"], anchor="w"
                 ).pack(side="left")
        tk.Button(header, text="✕", command=self.close_day_panel,
                  bg=self.colors["sidebar"], fg=self.colors["subtext"], relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2"
                  ).pack(side="right", padx=(6, 0))
        tk.Button(header, text="+ Add note", command=lambda: self._add_note_for_date(date_str),
                  bg=self.colors["accent"], fg=self._on_fill("accent"), relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=8, ipady=2)

        # Scrollable list area.
        body = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        body.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        canvas = tk.Canvas(body, bg=self.colors["sidebar"], highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        # A day can hold every note there is: past what one frame scrolls.
        inner = self._row_stack(canvas, scrolled=sb.set).group(bg="sidebar",
                                                               every=32)

        day_notes = _notes_on_day(self, date_str)
        rows = _day_list_rows(self, day_notes, date_str)
        self._day_panel_shows = ("list", date_str, _day_list_key(rows), None)
        if not day_notes:
            tk.Label(inner.add(), text="No notes for this day yet.",
                     bg=self.colors["sidebar"], fg=self.colors["subtext"],
                     font=("Segoe UI", 10)).pack(pady=10)
            for chunk in inner.chunks:
                self._bind_mousewheel_recursive(chunk, canvas)
            return

        for base_note, (title_text, icons, color) in rows:
            row = tk.Frame(inner.add(), bg=self.colors["card"], cursor="hand2")
            # The keyboard's ring rests in the row's own fill; the title's
            # padding gives back the pixel it takes.
            self._ring_round(row)
            row.pack(fill="x", pady=3)
            stripe = tk.Frame(row, bg=color, width=4)
            stripe.pack(side="left", fill="y")

            # No per-row delete button here. It was the only one in the
            # app: a lone grey glyph with no word, packed hard against
            # the scrollbar, where a slipped click destroys a note. The
            # rest of the app already says how a list behaves -- the
            # sidebar's note cards offer their actions through the
            # right-click menu and carry no button of their own, and a
            # labelled Delete appears only where a SINGLE note is open.
            # This row now does the same, and the menu bound below
            # carries six other actions besides.
            lbl = tk.Label(row, bg=self.colors["card"], fg=self.colors["text"],
                           anchor="w")
            _fit_title(self, lbl, "", title_text, icons,
                       self._cal_font(("Segoe UI", 10, "bold"))[0])
            lbl.pack(side="left", fill="x", expand=True, padx=10, pady=7)

            def _open(e, n=base_note, d=date_str):
                self.show_day_note(n, d)

            def _context(e, n=base_note, d=date_str):
                self.show_note_context_menu(e, n, occurrence_date=d)

            for w in (row, stripe, lbl):
                w.bind("<Button-1>", _open)
                w.bind("<Button-3>", _context)
            self._pressable(row, lambda n=base_note, d=date_str:
                            self.show_day_note(n, d), menu=_context)

        # Bind the wheel now that every note row exists.
        for chunk in inner.chunks:
            self._bind_mousewheel_recursive(chunk, canvas)

    def _open_note_from_grid(self, base_note, date_str):
        """Land on ONE note from a chip in the month grid.

        The day panel has to be showing that day before a single note can
        be drawn into it -- show_day_note's own "← Back" returns to the
        day's list, and that list is whatever open_day_popup last put
        there. Both calls, in this order, are the same landing the History
        register's rows already use.
        """
        self.open_day_popup(date_str)
        self.show_day_note(base_note, date_str)

    def show_day_note(self, base_note, date_str):
        """Open a single note inside the day panel, with a Back button that
        returns to the day's note list."""
        self._clear_day_panel()
        self._day_panel_mode = "note"
        self._day_panel_shows = ("note", date_str, base_note,
                                 _day_note_key(base_note, date_str))
        note = effective_note(base_note, date_str)

        top = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        top.pack(fill="x", padx=15, pady=(10, 6))
        tk.Button(top, text="← Back", command=self.show_day_list,
                  bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", ipadx=6, ipady=2)
        # A repeating note opens two ways, and the panel names both: this
        # day on its own, or the whole series. One "Open in editor" opened
        # the day, under the series' date and repeat as fields to change,
        # and a field test could not find how to edit just one day
        # (2026-10-12). The right-click menu says the same two things.
        if is_recurring(base_note):
            tk.Button(top, text="✏ Edit this day",
                      command=lambda: self._open_note_from_calendar(base_note, date_str),
                      bg=self.colors["accent"], fg=self._on_fill("accent"), relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2"
                      ).pack(side="right", ipadx=6, ipady=2)
            tk.Button(top, text="🔁 Edit the whole series",
                      command=lambda: self._open_note_from_calendar(
                          base_note, date_str, whole_series=True),
                      bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2"
                      ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)
        else:
            tk.Button(top, text="✏ Open in editor",
                      command=lambda: self._open_note_from_calendar(base_note, date_str),
                      bg=self.colors["accent"], fg=self._on_fill("accent"), relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2"
                      ).pack(side="right", ipadx=6, ipady=2)
        # Quiet, in the warning's words, as the editor's Delete: the note
        # goes to the Trash. The dark red fill is kept for what cannot be undone.
        tk.Button(top, text="🗑 Delete",
                  command=lambda: self._delete_note_from_calendar(base_note, date_str),
                  bg=self.colors["card"], fg=self.colors["danger_text"], relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)

        title = _note_str(note, "title").strip() or "(untitled)"
        title_lbl = tk.Label(self.day_panel, text=title,
                             font=("Segoe UI", 12, "bold"),
                             bg=self.colors["sidebar"], fg=self.colors["text"],
                             anchor="w", wraplength=self.px(700), justify="left")
        title_lbl.pack(fill="x", padx=15, pady=(2, 4))

        # The actions menu, which this panel was the only note surface in
        # the app to lack. It was not missing "another way to delete" --
        # it was missing Open/Edit, Pin, Export as file, and, for a
        # repeating note, editing just this day, editing the whole
        # series, and resetting this day back to the series content.
        #
        # occurrence_date is passed, and that is the whole point of
        # passing it: this panel is opened ON a date, so the menu must
        # offer to edit THAT day rather than silently acting on the
        # series behind it.
        def _panel_menu(event):
            self.show_note_context_menu(event, base_note,
                                        occurrence_date=date_str)

        # The panel's own edge is bound once, in build_calendar_tab.
        for widget in (top, title_lbl):
            widget.bind("<Button-3>", _panel_menu)

        # The preview is a QUICK LOOK, not the editor: it shows the note's
        # plain text and, like the note-list cards, only SAYS what else the
        # note carries (a table, a checklist, comments) rather than trying
        # to render it. Tables drawn here were raw pipe soup, and comments
        # dumped inline read as part of the body -- both belong in the
        # editor, which is one "Open in editor" click away.
        # Both halves from one pass, because the sentence "this note has
        # N tables" and the text beside it have to be about the same
        # lines. They were not: the count and the strip both asked
        # is_table_row(), which is strict on purpose -- it decides what
        # the EDITOR treats as a row, so a line typed past its last cell
        # is not one. Such a line was therefore neither counted nor
        # removed, and the preview announced five tables and then drew a
        # sixth as pipes. Field-reported: "I only see vertical lines."
        note_body = _note_str(note, "body")
        text_only, table_count = core_tables.preview_text(note_body)
        text_only = re.sub(r"\n{3,}", "\n\n", text_only).strip("\n")

        chips = []
        if is_recurring(base_note) and date_str in (base_note.get("overrides") or {}):
            chips.append("✎ edited for this day")
        came = moved_from(base_note, date_str)
        if came is not None:
            chips.append(f"↷ moved from {show_date(came)}")
        if table_count:
            chips.append("▦ 1 table" if table_count == 1
                         else f"▦ {table_count} tables")
        checklist = note.get("checklist") or []
        if isinstance(checklist, list) and checklist:
            done = sum(1 for it in checklist
                       if isinstance(it, dict) and it.get("done"))
            chips.append(f"☑ {done}/{len(checklist)}")
        if _note_str(note, "comments").strip():
            chips.append("💬 comments")
        if note.get("attachments"):
            chips.append(f"📎×{len(note['attachments'])}")
        if chips:
            tk.Label(self.day_panel, text="   ".join(chips),
                     font=("Segoe UI", 8, "bold"), anchor="w",
                     bg=self.colors["sidebar"], fg=self.colors["accent_text"]
                     ).pack(fill="x", padx=15, pady=(0, 6))

        body = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        body.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        txt_sb = ttk.Scrollbar(body, orient="vertical")
        txt = tk.Text(body, wrap="word", relief="flat", font=("Segoe UI", 10),
                      bg=self.colors["card"], fg=self.colors["text"], padx=10, pady=10,
                      yscrollcommand=txt_sb.set)
        txt_sb.config(command=txt.yview)
        txt_sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        txt.insert("1.0", text_only or "(empty note)")
        txt.config(state="disabled")

    def _open_note_from_calendar(self, base_note, date_str, whole_series=False):
        """Open an EXISTING note (not a new one) from the calendar day panel:
        that day of it, or with *whole_series* the series itself.
        Same 'remember where we came from' treatment as creating a note there —
        open_note_in_tab clears any pending return first (it's meant to, for
        the normal case of switching between notes), so we set it again right
        after, once that's done. Either way the way back is to this day."""
        remembered = {"year": self.cal_year, "month": self.cal_month,
                      "date_str": date_str, "origin": "edit"}
        self.notebook.select(self.TAB_NOTES)
        # Going back to the note still in the editor -- to fix a date it
        # could not save -- means this note was not opened, and the way
        # back must not be re-pointed at it.
        if not self.open_note_in_tab(
                base_note, occurrence_date=None if whole_series else date_str):
            return
        self._pending_calendar_return = remembered
        self._update_calendar_return_button()

    def _add_note_for_date(self, date_str):
        """Start a new note pre-filled with this date. Editing still happens on
        the Notes tab (the editor lives there), but we remember where we came
        from in the calendar so saving (or 'Back to Calendar') returns you to
        the exact same month/day — it shouldn't feel like being sent away."""
        # Flush before clearing, like every other route into an empty
        # editor — this path once discarded pending edits silently. And
        # going back to fix a date the save could not store means stay,
        # here as on every route that would replace the editor.
        if self._flush_autosave() is False:
            return
        self.notebook.select(self.TAB_NOTES)
        self.new_note()
        # Set AFTER new_note — new_note clears any pending return, since
        # every other route into a fresh editor means the calendar trip
        # is over (a pending that outlived a delete once made a later,
        # unrelated Save yank the user onto a stale calendar day).
        self._pending_calendar_return = {
            "year": self.cal_year, "month": self.cal_month,
            "date_str": date_str, "origin": "add",
        }
        # Through the field's one writer, so the day shows as every date
        # in the field does (17.10.2026) -- written here by hand, it was
        # the one route that put the stored form on screen.
        self._show_date_in_field(date_str)
        self.title_entry.focus()
        self._update_calendar_return_button()

    # ---------- Calendar History (the register of days with content) ----------

    def _update_selected_day_outline(self):
        """A thin accent border around the day whose panel is open — the
        'you are here' mark (field request: the open day must jump out,
        including when History lands you on it). Today's own accent top
        bar is a separate device and never changes; a selected today
        simply wears both."""
        selected = (self.selected_day
                    if self._day_panel_mode != "empty"
                    else None)
        cv = self.cal_canvas
        if cv is None:
            return
        try:
            cv.delete("cal_selected")
            rec = (self._cal_cells or {}).get(selected)
            if rec is None:
                return
            # Two pixels inside the cell's edge, where the Frame's
            # highlight ring drew them.
            cv.create_rectangle(rec["x0"] + 1, rec["y0"] + 1, rec["x1"] - 1, rec["y1"] - 1,
                                outline=self.colors["accent"], width=2,
                                tags=("cal", "cal_selected"))
        except tk.TclError:
            pass

    def _toggle_calendar_history(self):
        """Swap the month grid (and day panel) for the History register,
        or bring the grid back."""
        if self._history_visible:
            self._hide_calendar_history()
        else:
            self._show_calendar_history()

    def _show_calendar_history(self):
        if not self._history_built:
            self._build_history_ui()
        # A fresh memo each time the register opens: its keys are what each
        # answer was worked out from, so it is never wrong, only bigger.
        self._history_memo = {}
        self.close_day_panel()
        self.cal_grid_frame.pack_forget()
        self._history_visible = True
        # Its 10 px below go under the rows, which stand under this chunk.
        self.history_frame.pack(side="top", fill="both", expand=True, padx=30)
        self._history_toggle_btn.configure(text="📅 Calendar")
        self._render_calendar_history()

    def _hide_calendar_history(self):
        self._history_visible = False
        self.history_frame.pack_forget()
        self._history_rows.clear()
        self.cal_grid_frame.pack(side="top", fill="both", expand=True,
                                 padx=30, pady=(0, 10))
        self._history_toggle_btn.configure(text="📋 History")
        self.render_calendar()

    def _build_history_ui(self):
        """The persistent half of the view: header, search, year chips,
        rows host. Built once; everything here goes through track_theme."""
        self._history_built = True
        head = tk.Frame(self.history_frame)
        self.track_theme(head, bg="bg")
        head.pack(fill="x", pady=(4, 8))

        # No in-view back button: the header toggle (now labelled
        # "📅 Calendar" while this view is open) is the single way back.
        self._history_search_var = tk.StringVar()
        search = tk.Entry(head, textvariable=self._history_search_var,
                          relief="flat", font=("Segoe UI", 10),
                          insertbackground=self.colors["text"])
        self.track_theme(search, bg="card", fg="text",
                         insertbackground="text")
        search.pack(side="left", fill="x", expand=True, padx=10, ipady=4)
        self.add_placeholder(search, "Search all calendar entries...")
        self._history_search_entry = search
        self._add_paste_menu(search)
        self._guard_entry_astral(search)
        self._history_search_var.trace_add(
            "write", lambda *a: self._history_search_changed())

        chips = tk.Frame(self.history_frame)
        self.track_theme(chips, bg="bg")
        chips.pack(fill="x", pady=(0, 8))
        self._history_chip_btns = {}
        for bucket in ("All", "This year", "Last year", "2 years ago",
                       "Older"):
            b = tk.Button(chips, text=bucket, relief="flat", cursor="hand2",
                          font=("Segoe UI", 8, "bold"),
                          command=lambda v=bucket: self._history_set_bucket(v))
            b.pack(side="left", padx=(0, 6), ipadx=8, ipady=2)
            self._history_chip_btns[bucket] = b

        # The rows stand below this chunk, in chunks a render makes and takes
        # away (RowStack): the wheel goes to each one as it is made.
        self._history_rows = self._cal_stack.group(bg="bg", padx=30,
                                                   pady=(0, 10), every=32)

    def _history_set_bucket(self, bucket):
        self._history_bucket = bucket
        self._history_shown = 50
        self._render_calendar_history()

    def _history_search_changed(self):
        """Debounced re-render — one render per pause, not per keystroke."""
        if self._history_search_job is not None:
            try:
                self.after_cancel(self._history_search_job)
            except (tk.TclError, ValueError):
                pass
        self._history_shown = 50
        self._history_search_job = self.after(
            300, self._render_calendar_history)

    def _history_query(self):
        q = self._history_search_var.get()
        return "" if q == "Search all calendar entries..." else q.strip()

    def _search_history_for(self, query):
        """The Calendar's History, searching for *query*: it reads a day's own
        words, which the list's search does not (the empty list's link)."""
        self.notebook.select(self.TAB_CALENDAR)
        if not getattr(self, "_history_visible", False):
            self._show_calendar_history()
        entry = self._history_search_entry
        entry.delete(0, "end")
        entry.insert(0, query)
        entry.config(fg=self.colors["text"])

    def _render_calendar_history(self):
        """The rebuilt half: rows re-created per render, coloured with
        plain .configure so they always wear the CURRENT theme."""
        # Cancelled, not forgotten: a render run directly (a bucket chosen
        # while a typed search waits) makes the waiting one redundant, and
        # a timer only forgotten stayed scheduled with nothing tracking it
        # -- see _autosave_now.
        job = self._history_search_job
        self._history_search_job = None
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        if not (self._history_visible and self._history_built):
            return
        self._history_rows.clear()

        # Active-chip styling rides every render (including theme ones).
        for bucket, b in self._history_chip_btns.items():
            active = (bucket == self._history_bucket)
            b.configure(
                bg=self.colors["accent"] if active else self.colors["card"],
                fg=self._on_fill("accent") if active else self.colors["text"],
                activebackground=self.colors["accent"],
                activeforeground=self._on_fill("accent"))

        query = self._history_query()
        entries = self._history_entries_now()

        if not entries:
            lbl = tk.Label(self._history_rows.add(),
                           text=("No calendar entries match." if query or
                                 self._history_bucket != "All" else
                                 "Nothing on the calendar yet — give a note "
                                 "a date, or make one repeat."),
                           font=("Segoe UI", 10), bg=self.colors["bg"],
                           fg=self.colors["subtext"])
            lbl.pack(pady=20)
            for chunk in self._history_rows.chunks:
                self._bind_mousewheel_recursive(chunk, self.cal_scroll_canvas)
            return
        self._history_draw_rows(entries, 0)

    def _history_entries_now(self):
        return history_entries(self.notes, query=self._history_query(),
                               year_bucket=self._history_bucket,
                               memo=self._history_memo)

    def _history_draw_rows(self, entries, first):
        """The rows for entries[first:] up to the page's end, under any
        already drawn, and the button for the rest."""
        before = set(self._history_rows.chunks) | set(self._history_rows.rows())

        def one_row(parent, parts, fg, command, context_cmd=None, indent=0,
                    bold=False):
            """`parts` is (before the title, the title, after it): only the
            title gives way when the row is too narrow for all three."""
            row = tk.Frame(parent.add(), bg=self.colors["card"], cursor="hand2")
            self._ring_round(row)       # the title's padding holds its pixel
            row.pack(fill="x", pady=1, padx=(indent, 0))
            lbl = tk.Label(row, anchor="w", bg=self.colors["card"], fg=fg)
            _fit_title(self, lbl, *parts, self._cal_font(
                ("Segoe UI", 9, "bold" if bold else "normal"))[0])
            lbl.pack(side="left", fill="x", expand=True, padx=10, ipady=3)
            for w in (row, lbl):
                w.bind("<Button-1>", lambda e: command())
                if context_cmd is not None:
                    w.bind("<Button-3>", context_cmd)
            self._pressable(row, command, menu=context_cmd)
            return row

        # Each row's note, found once for the whole render rather than by a
        # walk of every note per row; the first of an id, as find_note has.
        by_id = {}
        for n in self.notes:
            by_id.setdefault(n.get("id"), n)
        shown = entries[first:self._history_shown]
        for entry in shown:
            note = by_id.get(entry["note_id"])
            if note is None:
                continue
            if entry["kind"] == "note":
                one_row(
                    self._history_rows,
                    (f"📅 {show_date(entry['date'])}   ", entry['title'] or '(untitled)', ""),
                    self.colors["text"],
                    lambda n=note, d=entry["date"]: self._history_open_day(n, d),
                    context_cmd=lambda e, n=note, d=entry["date"]:
                        self.show_note_context_menu(e, n, occurrence_date=d))
            else:
                expandable = bool(entry["children"])
                expanded = expandable and (
                    entry["auto_expand"]
                    or entry["note_id"] in self._history_expanded)
                if entry["children_kind"] == "occurrences":
                    suffix = f" · {entry['n_occurrences']} occurrences"
                    if entry["n_edited"]:
                        suffix += f" · {entry['n_edited']} edited (✎)"
                else:
                    n_kids = entry["n_edited"]
                    suffix = (f" · {n_kids} edited day"
                              f"{'s' if n_kids != 1 else ''} (✎)"
                              if n_kids else "")
                if entry.get("n_off"):
                    suffix += f" · {entry['n_off']} off the schedule"
                if entry.get("n_moved"):
                    suffix += f" · {entry['n_moved']} moved (↷)"
                if expandable:
                    glyph = "▾" if expanded else "▸"
                    row_cmd = (lambda i=entry["note_id"]:
                               self._history_toggle_group(i))
                else:
                    # Nothing to unfold — the row itself jumps to the
                    # series' next day on the calendar (an arrow opening
                    # an empty group was the confusing thing it replaces).
                    glyph = "→"
                    row_cmd = (lambda n=note, d=entry.get("jump_date", ""):
                               self._history_open_day(n, d) if d else None)
                one_row(
                    self._history_rows,
                    (f"{glyph} 🔁 ", entry['title'] or '(untitled)',
                     f" · {entry['freq_label']}{suffix}"),
                    self.colors["accent_text"],
                    row_cmd,
                    context_cmd=lambda e, n=note:
                        self.show_note_context_menu(e, n),
                    bold=True)
                if expanded:
                    for child in entry["children"]:
                        mark = ("✎" if child.get("edited")
                                else "↷" if child.get("moved_from") else "•")
                        if child.get("off_schedule"):
                            # A day the series no longer lands on: opened as
                            # one, it was a day no calendar could show, and
                            # its menu offered to delete a day that was not
                            # there. It opens the walk through such days.
                            one_row(
                                self._history_rows,
                                (f"{mark} {show_date(child['date'])}   ",
                                 child['title'] or '(untitled)',
                                 "  · off the schedule"),
                                self.colors["subtext"],
                                lambda n=note: self._history_off_schedule(n),
                                context_cmd=lambda e, n=note:
                                    self.show_note_context_menu(e, n),
                                indent=26)
                            continue
                        # A moved day says where it came from: on its new
                        # date alone it reads as a day the rule gives.
                        came = child.get("moved_from")
                        one_row(
                            self._history_rows,
                            (f"{mark} {show_date(child['date'])}   ",
                             child['title'] or '(untitled)',
                             f"  · moved from {show_date(came)}" if came else ""),
                            self.colors["text"],
                            lambda n=note, d=child["date"]:
                                self._history_open_day(n, d),
                            context_cmd=lambda e, n=note, d=child["date"]:
                                self.show_note_context_menu(
                                    e, n, occurrence_date=d),
                            indent=26)
                    if entry["children_kind"] == "edited":
                        info = tk.Label(
                            self._history_rows.add(),
                            text=("    …every other day of this series shows "
                                  "the series content"),
                            font=("Segoe UI", 8), anchor="w",
                            bg=self.colors["bg"], fg=self.colors["subtext"])
                        info.pack(fill="x", padx=(26, 0))

        self._history_more_btn = None
        if len(entries) > self._history_shown:
            more = tk.Button(
                self._history_rows.add(),
                text=f"Show more ({len(entries) - self._history_shown} left)",
                relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
                bg=self.colors["card"], fg=self.colors["accent_text"],
                activebackground=self.colors["sidebar"],
                activeforeground=self.colors["accent_text"],
                command=self._history_show_more)
            more.pack(fill="x", pady=(6, 2))
            self._history_more_btn = more

        # Only what is new: a chunk and all in it, and a row added to an old
        # chunk -- binding again what was bound left one more Tcl command
        # behind at every render, for as long as the app ran.
        for chunk in self._history_rows.chunks:
            if chunk not in before:
                self._bind_mousewheel_recursive(chunk, self.cal_scroll_canvas)
                continue
            for row in chunk.winfo_children():
                if row not in before:
                    self._bind_mousewheel_recursive(row, self.cal_scroll_canvas)

    def _history_toggle_group(self, note_id):
        if note_id in self._history_expanded:
            self._history_expanded.discard(note_id)
        else:
            self._history_expanded.add(note_id)
        self._render_calendar_history()

    def _history_off_schedule(self, note):
        """A History row for a day the series no longer lands on: the walk
        through such days (_show_off_schedule_days), then the register
        drawn again for what it changed. It writes nothing itself."""
        self._show_off_schedule_days(note)
        self._render_calendar_history()

    def _history_show_more(self):
        """The next 50 go in under the rows already drawn: drawing every
        row again flickered, and grew with every page. A search still
        waiting to run means the rows on screen are stale: all of them
        are drawn again then, for the new search."""
        first = self._history_shown
        self._history_shown += 50
        more = getattr(self, "_history_more_btn", None)
        if (self._history_search_job is not None
                or not (self._history_visible and self._history_built)
                or more is None or not more.winfo_exists()):
            self._render_calendar_history()
            return
        more.destroy()
        self._history_more_btn = None
        self._history_draw_rows(self._history_entries_now(), first)

    def _history_open_day(self, note, date_str):
        """Back to the grid, on that exact month, with the day panel
        showing this note's preview — the chosen landing for a row click.

        A landing only navigates; it never writes into the editor. The
        tail of _add_note_for_date -- the new note's date prefill -- was
        once left here by an insertion, and it wrote the row's date into
        whatever note the editor held, which the next flush then saved:
        clicking a row silently re-dated another note, or moved a series.
        """
        d = parse_date(date_str)
        self._hide_calendar_history()
        if d is not None:
            self.cal_year, self.cal_month = d.year, d.month
            self.render_calendar()
        self.open_day_popup(date_str)
        self.show_day_note(note, date_str)

    def show_day_context_menu(self, event, date_str):
        """Right-click menu for a calendar day: add a note, or color the day.
        Left-click still opens the day panel; this is the separate right-click
        action."""
        menu = self._new_context_menu(tearoff=0)
        menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"],
            activeforeground=self._on_fill("accent"),
            relief="flat", bd=0, font=("Segoe UI", 9)
        )
        menu.add_command(
            label="➕  Add note for this day",
            command=lambda: self._add_note_for_date(date_str)
        )
        # No "View this day" entry here — a plain left-click on the day
        # already opens the same panel via open_day_popup(), so this menu
        # only needs the actions a left-click can't already do.
        menu.add_separator()
        menu.add_command(
            label="🎨  Color this day…",
            command=lambda: self._color_day(date_str, event)
        )
        if self.day_colors.get(date_str):
            menu.add_command(
                label="✖  Clear day color",
                command=lambda: self._clear_day_color(date_str)
            )
        menu.add_command(
            label="🏷  Mark this day…",
            command=lambda: self._mark_day_emoji(date_str, event)
        )
        if self.day_emoji.get(date_str):
            menu.add_command(
                label="✖  Clear day markers",
                command=lambda: self._clear_day_markers(date_str)
            )
        # Same guard as the note menu: a hover preview drawing over an
        # open menu is what was reported, and this is the menu it was
        # drawn over. See show_note_context_menu for why the flag holds.
        self.hide_day_tooltip()
        self._context_menu_open = True
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            self._context_menu_open = False

    def _color_day(self, date_str, event=None):
        """Color a calendar day using the same curated in-app palette used
        for categories — not the OS color-chooser dialog. Anchored near where
        the right-click happened, since a day cell has no persistent button
        to dock a dropdown to."""
        current = self.day_colors.get(date_str, "")

        def on_pick(color):
            old = self.day_colors.get(date_str)
            # The most a start or a backup keeps (MAX_DAY_DECORATIONS): a
            # day past it is refused here, never dropped at the next start.
            if (color and old is None
                    and len(self.day_colors) >= MAX_DAY_DECORATIONS):
                self._show_toast(
                    f"You have coloured {MAX_DAY_DECORATIONS:,} days, which is "
                    "the most the app keeps. Clear one first.", kind="info")
                return
            if color:
                self.day_colors[date_str] = color
            else:
                self.day_colors.pop(date_str, None)
            self._persist_day_colors()
            self.render_calendar()
            # "No color" on this palette discards the day's colour exactly
            # as the menu's own Clear entry does: the same loss reached by
            # a second route, so it gets the same way back. Missing this
            # would have left one of the two doors unguarded, which is the
            # shape a sibling sweep exists to catch.
            if not color and old:
                self._show_toast(
                    "Day colour cleared",
                    action=lambda: self._undo_day_clear(date_str, "color", old))

        if event is not None:
            anchor_xy = (event.x_root, event.y_root)
        else:
            anchor_xy = (self.winfo_rootx() + 100, self.winfo_rooty() + 100)
        self._show_color_palette(None, current, on_pick, allow_reset=True,
                                 anchor_xy=anchor_xy, reset_label="No color",
                                 keyboard_from=getattr(event, "widget", None))

    def _clear_day_color(self, date_str):
        if date_str in self.day_colors:
            old = self.day_colors.pop(date_str)
            self._persist_day_colors()
            self.render_calendar()
            self._show_toast(
                "Day colour cleared",
                action=lambda: self._undo_day_clear(date_str, "color", old))

    def _clear_day_markers(self, date_str):
        """Discard a day's markers, and offer the way back.

        This was an inline lambda on the menu entry; it needs a name now
        that it has to remember what it removed.
        """
        old = self.day_emoji.pop(date_str, None)
        if not old:
            return
        self._persist_day_emoji()
        self.render_calendar()
        self._show_toast(
            "Day markers cleared",
            action=lambda: self._undo_day_clear(date_str, "markers", old))

    def _undo_day_clear(self, date_str, kind, value):
        """Put back a day's colour, or its markers, after a clear.

        Four routes discarded a day's decoration and none of them asked:
        the two "Clear day …" menu entries, which sit directly under the
        entries that CREATE the same thing, the palette's own "No color",
        and the marker popup saved empty (Clear, then Save). A mis-aim by
        one menu row turned "change this" into "discard it", permanently.
        No confirmation added, deliberately —
        the app's rule is that a destructive action is confirmed in
        proportion to how recoverable it is, and a question in front of
        every colour change would cost more than the loss it guards. So
        the loss stopped being permanent instead.

        One method for both kinds, because they are the same act on two
        stores; a second copy of this reasoning would drift from the first.
        `value` is what was there, captured by the caller before it went.

        The markers are named, not echoed: they are astral emoji, and the
        sentence does not need them to say what happened.
        """
        store, persist, done, occupied = {
            "color": (self.day_colors, self._persist_day_colors,
                      "Day colour put back", "That day has a colour again"),
            "markers": (self.day_emoji, self._persist_day_emoji,
                        "Day markers put back", "That day has markers again"),
        }[kind]
        # The clear left this slot EMPTY, so an empty slot is the only
        # state this offer still fits. Anything there now is either the
        # same value back (a second click on a toast that has not faded)
        # or something chosen by hand in the seconds since -- and a stale
        # memory must not overwrite either. The weaker test, "is it equal
        # to what I am about to restore?", let a marker picked in between
        # be clobbered; found by probing rather than by review.
        #
        # No guard on an empty `value`: every caller establishes it, the
        # two clears by returning early, the palette and the marker popup
        # by asking. A branch nothing can reach is a branch no check can
        # defend.
        if store.get(date_str):
            self._show_toast(occupied, kind="info")
            return
        store[date_str] = list(value) if isinstance(value, list) else value
        persist()
        self.render_calendar()
        self.set_status(done)

    def _persist_day_colors(self):
        save_setting("day_colors", dict(self.day_colors))

    def _mark_day_emoji(self, date_str, event=None):
        """Small anchored popup for flagging a calendar day with one or more
        emoji markers — independent of whether it has a note. Click any number
        of chips to toggle them; nothing is written to disk or redrawn on the
        calendar until you press Save. ✕ discards whatever you changed here.
        This is deliberate: writing to disk and rebuilding the whole calendar
        on every single click was both slow (visible lag) and confusing (felt
        like nothing had "saved" until you clicked away)."""
        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        outer = tk.Frame(pop, bg=self.colors["card"], padx=8, pady=8)
        outer.pack(padx=1, pady=1)

        head = tk.Frame(outer, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Mark this day — up to 3", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 9, "bold"), bd=0).pack(side="right")

        # Working copy — the real self.day_emoji isn't touched until Save.
        pending = list(self.day_emoji.get(date_str, []))[:3]
        cells = {}
        # Each chip's own fill, kept so a flattened one can be given it back.
        colours = {}
        MAX_DAY_MARKERS = 3

        # The header says "up to 3" once, at the top, and the rule was then
        # enforced by silence: the fourth click simply did nothing, which
        # reads as the app being broken rather than as a limit being kept.
        # Every other ceiling in this app speaks when it is reached -- the
        # title cap sets a status line, the attachment cap raises a warning
        # -- so this one was the outlier.
        #
        # Two things rather than one, because they answer different halves.
        # The unpicked chips go flat once three are chosen, so the fourth
        # click is visibly unavailable BEFORE it is made; and a line under
        # the grid says why, for anyone who clicks anyway.
        capped = {"now": False}

        def refresh_cell(em):
            cell = cells[em]
            selected = em in pending
            cell.configure(highlightthickness=2 if selected else 0,
                           highlightbackground=self.colors["text"],
                           highlightcolor=self.colors["text"])
            # An unpicked chip at the cap wears the theme's own muted surface
            # rather than its own colour, and a hardcoded grey would be wrong
            # on half the eight themes.
            cell.configure(bg=(self.colors["sidebar"]
                               if capped["now"] and not selected
                               else colours[em]))

        def refresh_all_cells():
            was = capped["now"]
            capped["now"] = len(pending) >= MAX_DAY_MARKERS
            for em in cells:
                refresh_cell(em)
            if capped["now"] != was:
                cap_note.configure(
                    text=("Three is the most a day can show — unpick one to "
                          "choose another." if capped["now"] else " "))

        def toggle(em):
            if em in pending:
                pending.remove(em)
            elif len(pending) < MAX_DAY_MARKERS:
                pending.append(em)
            else:
                # Clicked anyway -- the chip is flat but a flat chip is not a
                # disabled one, and saying nothing here is what the row was
                # about. Keeps the calendar cell readable: more than three
                # would show as an anonymous "+N" nobody could identify
                # without reopening this same popup.
                cap_note.configure(
                    text="Three is the most a day can show — unpick one first.")
            refresh_all_cells()
            # Purely local: just updates this chip's highlight. No disk write,
            # no calendar rebuild — that's what made rapid clicking feel
            # laggy before. Stays snappy no matter how many you pick.
            return "break"

        grid = tk.Frame(outer, bg=self.colors["card"])
        grid.pack()
        cols = 6
        for i, (em, color) in enumerate(self.DAY_MARKER_EMOJIS):
            r, c = divmod(i, cols)
            cell = tk.Label(grid, text=em, font=("Segoe UI Emoji", 14),
                            bg=color, cursor="hand2", width=2, height=1)
            cell.grid(row=r, column=c, padx=2, pady=2)
            cells[em] = cell
            colours[em] = color
            hover_color = _darken_hex(color)
            # "break" stops this click from also reaching the app-wide
            # click-outside-closes-the-popup handler — without it, picking an
            # emoji could immediately close this same popup.
            cell.bind("<Button-1>", lambda e, em=em: toggle(em))
            # The hover handlers consult the cap, or resting on a flattened
            # chip would light it up again and undo the one thing that says
            # it is not available.
            cell.bind("<Enter>",
                      lambda e, w=cell, h=hover_color, em=em:
                      None if (capped["now"] and em not in pending)
                      else w.configure(bg=h))
            cell.bind("<Leave>", lambda e, em=em: refresh_cell(em))
            # From the keyboard: the chip it is on wears the pointer's
            # darker shade, as the ring is already the sign of a pick.
            self._pressable(cell, lambda em=em: toggle(em), walk=True)
            cell.bind("<FocusIn>", lambda e, w=cell, h=hover_color:
                      w.configure(bg=h))
            cell.bind("<FocusOut>", lambda e, em=em: refresh_cell(em))

        # Under the grid, and given a blank line's worth of height from the
        # start so that reaching the cap does not shove the buttons down.
        cap_note = tk.Label(outer, text=" ", bg=self.colors["card"],
                            fg=self.colors["subtext"], font=("Segoe UI", 8),
                            wraplength=self.px(230), justify="left", anchor="w")
        cap_note.pack(fill="x", pady=(4, 0))
        # Once, now that every chip and the note exist: a day that already
        # holds three opens with the others flat and the reason showing,
        # rather than waiting for a dead click to explain itself.
        refresh_all_cells()

        def clear_pending():
            pending.clear()
            refresh_all_cells()

        def save_and_close():
            had = list(self.day_emoji.get(date_str) or [])
            if (pending and not had
                    and len(self.day_emoji) >= MAX_DAY_DECORATIONS):
                self._show_toast(
                    f"You have marked {MAX_DAY_DECORATIONS:,} days, which is "
                    "the most the app keeps. Clear one first.", kind="info")
                return
            if pending:
                self.day_emoji[date_str] = list(pending)
            else:
                self.day_emoji.pop(date_str, None)
            self._persist_day_emoji()
            self._mini_popup_on_close = None  # already handled below
            self._dismiss_mini_popup()
            # Only this one day's badge needs to change — a full
            # render_calendar() here was heavy enough (destroying/rebuilding
            # every day cell) to cause a visible flicker right after the
            # popup closes.
            self._refresh_day_badge(date_str)
            # Saved empty over markers that were there: the same loss as the
            # menu's "Clear day markers", by a fourth door, so the same way
            # back. Picking and un-picking chips, and ✕, still write nothing.
            if had and not pending:
                self._show_toast(
                    "Day markers cleared",
                    action=lambda: self._undo_day_clear(date_str, "markers", had))

        btn_row = tk.Frame(outer, bg=self.colors["card"])
        btn_row.pack(fill="x", pady=(8, 0))
        clear = tk.Button(btn_row, text="Clear", command=clear_pending, relief="flat",
                          cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                          font=("Segoe UI", 8))
        clear.pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=4)
        save = tk.Button(btn_row, text="✓ Save", command=save_and_close, relief="flat",
                         cursor="hand2", bg=self.colors["accent"], fg=self._on_fill("accent"),
                         font=("Segoe UI", 8, "bold"))
        save.pack(side="left", fill="x", expand=True, padx=(4, 0), ipady=4)
        for button in (clear, save):
            self._button_choice(button)

        # The day's menu opened from the keyboard hands the keyboard on.
        opener = getattr(event, "widget", None)
        if event is not None:
            anchor_xy = (event.x_root, event.y_root)
            self._place_dropdown_popup(pop, None, anchor_xy=anchor_xy,
                                       keyboard_from=opener)
        else:
            self._place_dropdown_popup(pop, None,
                                       anchor_xy=(self.winfo_rootx() + 100, self.winfo_rooty() + 100))

    def _persist_day_emoji(self):
        # Drop any None/empty entries (from Clear) rather than persisting them.
        self.day_emoji = {d: e for d, e in self.day_emoji.items() if e}
        save_setting("day_emoji", dict(self.day_emoji))
