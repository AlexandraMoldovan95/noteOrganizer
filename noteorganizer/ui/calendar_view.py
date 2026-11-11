"""The calendar tab, the day panel, and the daily reminder: everything that
shows notes by date -- the month grid, a day's panel, the hover previews,
the days' colours and emoji, and the bar saying what is due today, which
asks the grid's own question of one day. Grouped by the call graph (62% of
these methods' calls are to each other); the rounded rectangle and the
colour palette serve more than the calendar and stay on the app class.

Nothing here compares stored dates: a repeating note is stored once, and
expand_occurrences says which notes fall in a window. What a mixin is, and
the two rules that keep them working: :mod:`noteorganizer.ui`.
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


# What the open day's panel says, for render_calendar to ask whether it
# still does: one answer for the drawing and the question. Functions, not
# methods -- they only read, and the class's surface is pinned.

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
    """The notes on one day, as the drawn month holds them when it can --
    asked again of every note, a hover cost 14 ms at 5,000 notes. Used when
    it is the day's month and nothing changed since: no render pending, no
    refresh deferred, the same notes. Anything else asks the notes.
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

        # Far right, History outermost and Today beside it: one toggle whose
        # label says where it goes -- "📋 History" on the grid, "📅 Calendar"
        # on the register (field feedback).
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

        # Bound once, asking what the panel shows: bound per note, it grew a
        # Tcl command each time and offered the last note's menu on the list.
        def _panel_menu(event):
            shows = getattr(self, "_day_panel_shows", None)
            if self._day_panel_mode == "note" and shows and shows[0] == "note":
                self.show_note_context_menu(event, shows[2],
                                            occurrence_date=shows[1])
        self.day_panel.bind("<Button-3>", _panel_menu)

        # History: the frame persists (track_theme), its ROWS are rebuilt at
        # every render with plain colours -- the two theming patterns.
        self.history_frame = tk.Frame(self.cal_scroll_inner)
        self.track_theme(self.history_frame, bg="bg")
        self._history_visible = False
        self._history_built = False
        self._history_bucket = "All"
        self._history_expanded = set()   # series the user opened (_order_identity)
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

        # The month is DRAWN here, shapes and text rather than widgets
        # (_draw_calendar_grid); built once, only redrawn.
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
        # The grid's own <Configure>: it changes size exactly when the step
        # can, a resize made on another tab included. On the window, it ran
        # for every widget laid out anywhere -- 3,882 times a list rebuild.
        self.cal_grid_frame.bind("<Configure>", _on_resize, add="+")

        self.bind_all("<Prior>", lambda e: self._calendar_key(e, months=-1))
        self.bind_all("<Next>", lambda e: self._calendar_key(e, months=1))
        self.bind_all("<Control-Prior>", lambda e: self._calendar_key(e, years=-1))
        self.bind_all("<Control-Next>", lambda e: self._calendar_key(e, years=1))
        self.bind_all("<Home>", lambda e: self._calendar_key(e, today=True))

    def _is_calendar_visible(self):
        """True only if the Calendar tab is both selected AND on screen: the
        Settings page covers it without changing the selected tab, and the
        calendar's keys and relayout acted on a calendar nobody could see."""
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

        # The event's own widget is the signal (focus_get() only for synthetic
        # calls); every kind of box Tk types into, built here or not.
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
        if not self._leave_history_for_the_month():
            self.render_calendar()

    def go_to_today(self):
        today = datetime.now()
        self.cal_year, self.cal_month = today.year, today.month
        self._cal_key_day = today.strftime("%Y-%m-%d")
        if not self._leave_history_for_the_month():
            self.render_calendar()

    def _leave_history_for_the_month(self):
        """A month asked for by a button is shown, as a History row's date
        is: moved behind the register, it showed only on the way back. True
        when it left, the month (set first) drawn by the leaving, once."""
        if getattr(self, "_history_visible", False):
            self._hide_calendar_history()
            return True
        return False

    def _cal_note_font_size(self):
        """Two-step sizing: bigger note previews in a wide window, smaller in a
        narrow one. Two fixed steps (not continuous) so there's no flicker."""
        try:
            w = self.winfo_width()
        except tk.TclError:
            w = self.px(900)
        return 11 if w >= self.px(1150) else 9

    # The grid's geometry: seven equal columns, a row of weekday names, week
    # rows as tall as the busiest day needs (at least 90), cells inset by 3;
    # 520 pixels tall until it takes the month's height.
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
        # The badge keeps to the room right of the day's number, and markers
        # that do not fit are counted -- "⭐+2", not a covered "15".
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
        # A month nobody sees is not drawn (36 ms at every delete, from the
        # Notes tab), decided here for every caller; each way back to the
        # calendar catches up (_on_tab_changed, hide_settings_page).
        if not self._calendar_is_showing():
            self._calendar_needs_render = True
            return

        # Every note's days in the visible month, worked out BEFORE the title
        # changes: when this raised (December 9999), the new title stood over
        # the old month's days.
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
        # The open day is redrawn with the month, when what it shows changed:
        # an Undo's note was missing from it, a category's stripe stale.
        _redraw_open_day(self, notes_by_date, self.cal_year, self.cal_month)
        # render_calendar is the one "the data changed" signal: the History,
        # when shown, refreshes here too -- a delete showed only after a trip
        # to the grid and back (field report).
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
        """Draw the month on the calendar's canvas, as rectangles and text --
        as widgets, 216 windows for 46 notes were placed again at every step
        of a resize. Laid out as the widget grid was: columns of
        floor(i * width / 7), a 26-pixel row of weekday names, week rows as
        the CAL_* constants say. A day is drawn at the origin, then moved
        once the tallest day of its row is known.
        """
        cv = self.cal_canvas
        cv.delete("cal")
        self._cal_cells = {}
        # The hover and its preview go with the drawing: the pointer had not
        # moved (PgDn changed the month), and July's preview sat over August.
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
        # On a painted day, near-black or white, whichever reads on it --
        # white vanished on the yellows (1.3:1); else the theme's colours.
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
            # As many dots as the cell holds, the last saying "and more": a
            # drawing clips nothing, and eight colours spilled into the next day.
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
        # The text jumps to today's notes. Kept on a half-written template
        # (Cancel), the click stops here, or click-outside asked again.
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
        """A compact, TITLES-ONLY list for hovering a day cell -- no bodies,
        or a busy day ballooned. Nothing hovers over an open menu: the mouse
        drifting onto the next cell drew this over the menu being read.
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

        # The panel's rule: the note's words and a chip for what else it
        # carries -- the raw body hovered as a wall of table pipes.
        preview, tables_here = core_tables.preview_text(_note_str(note, "body"))
        preview = preview.strip()
        if preview:
            preview = core_tables.glimpse(preview, 150)
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

            # No delete button on a row, as on the list's cards: a slipped
            # click by the scrollbar destroyed a note. Its actions are in the
            # right-click menu; Delete is labelled where one note is open.
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
        """Land on ONE note from a chip in the month grid: the day's list
        first, which its "← Back" returns to, then the note -- the landing
        the History's rows use.
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
        # A repeating note names both ways to open, this day or the series:
        # one "Open in editor" hid how to edit one day (field test).
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

        # The actions menu every note surface has, given the day: the panel
        # is opened ON a date, so the menu edits THAT day, not the series.
        def _panel_menu(event):
            self.show_note_context_menu(event, base_note,
                                        occurrence_date=date_str)

        # The panel's own edge is bound once, in build_calendar_tab.
        for widget in (top, title_lbl):
            widget.bind("<Button-3>", _panel_menu)

        # A QUICK LOOK: plain text, and only SAYS what else the note carries.
        # The count and the text from one pass, or "five tables" stood over
        # a sixth drawn as pipes (field report: "I only see vertical lines").
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
        # Gone back to fix a date the editor could not save, this note was not
        # opened; the note on screen is left as it is (_open_unless_shown).
        if not self._open_unless_shown(
                base_note, occurrence_date=None if whole_series else date_str):
            return
        self._pending_calendar_return = remembered
        self._update_calendar_return_button()

    def _add_note_for_date(self, date_str):
        """Start a new note pre-filled with this date. Editing still happens on
        the Notes tab (the editor lives there), but we remember where we came
        from in the calendar so saving (or 'Back to Calendar') returns you to
        the exact same month/day — it shouldn't feel like being sent away."""
        # Flushed first, as every route into an empty editor is; going back to
        # fix a date the save could not store means stay.
        if self._flush_autosave() is False:
            return
        self.notebook.select(self.TAB_NOTES)
        self.new_note()
        # Set AFTER new_note, which clears any pending return: one that
        # outlived a delete made a later Save jump to a stale calendar day.
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
        words, which the list's search does not (the empty list's link).
        Opened once the tab change is handled -- its handler shuts the
        History, and the link landed on the month grid -- on every year."""
        self.notebook.select(self.TAB_CALENDAR)
        self.after_idle(lambda: self._open_history_searching(query))

    def _open_history_searching(self, query):
        self._history_bucket = "All"
        if not getattr(self, "_history_visible", False):
            self._show_calendar_history()
        entry = self._history_search_entry
        entry.delete(0, "end")
        entry.insert(0, query)
        entry.config(fg=self.colors["text"])

    def _render_calendar_history(self):
        """The rebuilt half: rows re-created per render, coloured with
        plain .configure so they always wear the CURRENT theme."""
        # Cancelled, not forgotten: a direct render makes the waiting one
        # redundant, and a forgotten timer ran untracked (_autosave_now).
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
                    or (note is not None
                        and self._order_identity(note) in self._history_expanded))
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
                            # A day the series no longer lands on opens the walk
                            # through such days, not a day no calendar shows.
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
        # Kept by uid: a series deleted frees its id, and the next note
        # given that id would open unfolded.
        note = self.find_note(note_id)
        if note is None:
            return
        key = self._order_identity(note)
        if key in self._history_expanded:
            self._history_expanded.discard(key)
        else:
            self._history_expanded.add(key)
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
        """Back to the grid, on that exact month, with the day panel showing
        this note's preview -- the landing for a row click. It only
        navigates, never writes into the editor: a date prefill left here
        re-dated whatever note was open (ISSUES_LOG: "The History row that
        re-dated the open note").
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
            self._while_native(lambda: menu.tk_popup(event.x_root, event.y_root))
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
            # "No color" here is the menu's Clear by another route, and gets
            # the same way back.
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
        """Put back a day's colour, or its markers, after a clear -- four
        routes discarded them unasked, one menu row from the entries that
        make them. Not a question before every change but an Undo after, in
        proportion to the loss. One method for both stores; `value` is what
        was there, taken before it went. The markers are named, not echoed.
        """
        store, persist, done, occupied = {
            "color": (self.day_colors, self._persist_day_colors,
                      "Day colour put back", "That day has a colour again"),
            "markers": (self.day_emoji, self._persist_day_emoji,
                        "Day markers put back", "That day has markers again"),
        }[kind]
        # Only an EMPTY slot takes it back: anything there now is the same
        # value or one chosen since, which a stale memory must not overwrite.
        # No guard on an empty `value`: every caller makes sure of it.
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
        """A small anchored popup marking a day with emoji, note or not:
        chips toggle, and nothing is written or redrawn until Save (✕
        discards) -- written at every click, it lagged and never felt saved."""
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

        # A silent fourth click read as broken: at three, the other chips go
        # flat (unavailable BEFORE the click) and a line says why when one is
        # clicked anyway, as every ceiling in the app speaks.
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
                # Clicked anyway: said. More than three would show in the cell
                # as an anonymous "+N".
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
            # Only this day's badge changes: a full render flickered as the
            # popup closed.
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
