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

from ..core.model import (
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
    parse_date,
)
from ..core.storage import (
    load_settings,
    save_setting,
    save_settings,
)
from ..core import tables as core_tables


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
            cluster, text="", command=self.open_month_jump, relief="flat",
            font=("Segoe UI", 16, "bold"), cursor="hand2", borderwidth=0
        )
        self.track_theme(self.cal_month_lbl, bg="bg", fg="text",
                         activebackground="bg", activeforeground="accent")
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
        self.cal_scroll_canvas.configure(yscrollcommand=cal_sb.set)
        cal_sb.pack(side="right", fill="y")
        self.cal_scroll_canvas.pack(side="left", fill="both", expand=True)

        self.cal_scroll_inner = tk.Frame(self.cal_scroll_canvas)
        self.track_theme(self.cal_scroll_inner, bg="bg")
        self._cal_scroll_win = self.cal_scroll_canvas.create_window(
            (0, 0), window=self.cal_scroll_inner, anchor="nw")

        def _cal_scroll_config(e):
            self.cal_scroll_canvas.configure(scrollregion=self.cal_scroll_canvas.bbox("all"))
        self.cal_scroll_inner.bind("<Configure>", _cal_scroll_config)
        self.cal_scroll_canvas.bind(
            "<Configure>",
            lambda e: self.cal_scroll_canvas.itemconfig(self._cal_scroll_win, width=e.width))
        self._bind_mousewheel_recursive(self.cal_scroll_inner, self.cal_scroll_canvas)

        # Day panel: appears only when a day is selected, at the bottom of the
        # scrollable area. Fixed height; comfortable, not half the page.
        self.day_panel = tk.Frame(self.cal_scroll_inner, height=240)
        self.track_theme(self.day_panel, bg="sidebar")
        self.day_panel.pack_propagate(False)
        self.selected_day = None          # "YYYY-MM-DD" currently shown
        self._day_panel_mode = "empty"    # empty | list | note

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

        # Grid gets a comfortable minimum height so cells never shrink to
        # unusable slivers; if the window is smaller, the scrollbar kicks in.
        self.cal_grid_frame = tk.Frame(self.cal_scroll_inner, height=520)
        self.track_theme(self.cal_grid_frame, bg="bg")
        self.cal_grid_frame.pack(side="top", fill="both", expand=True, padx=30, pady=(0, 10))
        self.cal_grid_frame.pack_propagate(False)

        # Re-render the calendar when the window crosses the size threshold, so
        # note previews switch between small/large. Guarded so it only fires on
        # an actual step change (not on every pixel), avoiding needless redraws.
        self._cal_last_font_size = None

        def _on_resize(event):
            if getattr(self, "notebook", None) is None:
                return
            if not self._is_calendar_visible():
                return  # only when the Calendar tab is actually showing
            if getattr(self, "_history_visible", False):
                return  # the grid is hidden behind History; nothing to redraw
            size = self._cal_note_font_size()
            if size != self._cal_last_font_size:
                self._cal_last_font_size = size
                self.render_calendar()
        self.bind("<Configure>", _on_resize, add="+")

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
        if not self._is_calendar_visible():
            return

        # bind_all delivers the key to whichever widget has focus, so the
        # event's own widget is the reliable signal. focus_get() is only a
        # fallback for synthetic calls.
        typing_widgets = (tk.Text, tk.Entry, tk.Spinbox, ttk.Entry, ttk.Combobox)
        source = getattr(event, "widget", None)
        try:
            focused = self.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if any(isinstance(w, typing_widgets) for w in (source, focused)):
            return

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
        self.render_calendar()

    def _cal_note_font_size(self):
        """Two-step sizing: bigger note previews in a wide window, smaller in a
        narrow one. Two fixed steps (not continuous) so there's no flicker."""
        try:
            w = self.winfo_width()
        except tk.TclError:
            w = 900
        return 11 if w >= 1150 else 9

    def _build_day_badge(self, cell, date_str, cell_bg, day_color):
        """Draw (or redraw) the small marker-emoji badge in a day cell's
        corner, capped to a handful so it can't sprawl across the cell. The
        resulting Label is stashed on the cell itself (cell._marker_badge) so
        _refresh_day_badge can find and replace just this one badge later,
        without touching anything else in the calendar."""
        old = getattr(cell, "_marker_badge", None)
        if old is not None:
            try:
                old.destroy()
            except tk.TclError:
                pass
            cell._marker_badge = None

        markers = self.day_emoji.get(date_str) or []
        if not markers:
            return
        shown_markers = markers[:3]
        badge_text = "".join(shown_markers)
        if len(markers) > 3:
            badge_text += f"+{len(markers) - 3}"
        badge = tk.Label(cell, text=badge_text, font=("Segoe UI Emoji", 10),
                         bg=cell_bg if day_color else self.colors["card"])
        badge.place(relx=1.0, rely=0.0, anchor="ne", x=-3, y=3)
        cell._marker_badge = badge

    def _refresh_day_badge(self, date_str):
        """Update just ONE day's marker badge in place — used after saving
        picks from the Mark-this-day popup. Deliberately avoids a full
        render_calendar() call: destroying/rebuilding all ~35-42 day cells for
        a single small change was visibly heavy enough to cause a brief
        flicker/tear, especially right after a popup closes. This touches
        only the one cell that actually changed."""
        cell = getattr(self, "_cal_cell_widgets", {}).get(date_str)
        if cell is None or not cell.winfo_exists():
            # The visible month changed since the popup opened, or the
            # calendar hasn't been rendered yet — nothing to patch in place,
            # a full render will pick it up naturally next time it's shown.
            return
        day_color = self.day_colors.get(date_str)
        cell_bg = day_color if day_color else self.colors["card"]
        self._build_day_badge(cell, date_str, cell_bg, day_color)

    def render_calendar(self):
        if not hasattr(self, "cal_grid_frame"):
            return
        # Rebuilding ~35-42 day cells for a month nobody is looking at is
        # work the user pays for and never sees. Measured from the Notes
        # tab: 36ms and 98 widgets, on every delete, save, import and
        # category change -- a quarter of what a delete costs, spent on
        # the other tab.
        #
        # apply_theme has skipped this since the theme-switch flicker
        # work, with the reasoning written beside it; every OTHER caller
        # went through regardless. The decision belongs here, once, so
        # all thirty-one call sites are right by construction rather than
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
        # Tracks date_str -> cell Frame, so a single day's marker badge can be
        # refreshed later (see _refresh_day_badge) without tearing down and
        # rebuilding all ~35-42 day cells just for one small change.
        self._cal_cell_widgets = {}
        for widget in self.cal_grid_frame.winfo_children():
            widget.destroy()

        month_name = cal_module.month_name[self.cal_month]
        # The caret is the only hint that this opens a jump dialog, so it
        # replaces the instruction text that used to sit under the header.
        self.cal_month_lbl.config(text=f"{month_name} {self.cal_year}  ⌄")

        # Expand every note's occurrences across the visible month only.
        # Recurring notes are stored once; their dates are computed here.
        month_start = date_cls(self.cal_year, self.cal_month, 1)
        month_end = date_cls(
            self.cal_year, self.cal_month,
            cal_module.monthrange(self.cal_year, self.cal_month)[1]
        )
        notes_by_date = {}
        for n in self.notes:
            for occurrence in expand_occurrences(n, month_start, month_end):
                notes_by_date.setdefault(occurrence, []).append(n)

        # Direct .configure() calls throughout this function, not
        # self.track_theme(): every cell and everything in it is destroyed
        # and rebuilt from scratch on every render_calendar() call (a save,
        # switching months, ...), so it always picks up the CURRENT theme
        # fresh anyway. track_theme() appends to a list that's never pruned
        # when its widgets are destroyed — with ~40 cells rebuilt on every
        # save over a long session, that added up to a slow, ever-growing list.
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, wd in enumerate(weekdays):
            lbl = tk.Label(self.cal_grid_frame, text=wd, font=("Segoe UI", 9, "bold"),
                           bg=self.colors["bg"], fg=self.colors["subtext"])
            lbl.grid(row=0, column=col, sticky="nsew", pady=(0, 5))
            self.cal_grid_frame.grid_columnconfigure(col, weight=1, uniform="calday")

        today_str = datetime.now().strftime("%Y-%m-%d")
        month_weeks = cal_module.monthcalendar(self.cal_year, self.cal_month)

        for row_idx, week in enumerate(month_weeks, start=1):
            for col_idx, day in enumerate(week):
                if day == 0:
                    continue
                date_str = f"{self.cal_year:04d}-{self.cal_month:02d}-{day:02d}"
                day_notes = notes_by_date.get(date_str, [])
                has_notes = bool(day_notes)
                is_today = date_str == today_str

                cell = tk.Frame(self.cal_grid_frame, cursor="hand2")
                day_color = self.day_colors.get(date_str)
                if day_color:
                    # User painted this day: tint the whole cell.
                    cell.configure(bg=day_color)
                else:
                    cell.configure(bg=self.colors["card"])
                cell.grid(row=row_idx, column=col_idx, sticky="nsew", padx=3, pady=3, ipady=6)
                self._cal_cell_widgets[date_str] = cell

                # Background used for this cell's inner labels (matches a
                # painted day so text doesn't sit on a mismatched patch).
                cell_bg = day_color if day_color else self.colors["card"]
                lbl_fg = "#ffffff" if day_color else self.colors["text"]

                if is_today:
                    # A thin accent-colored top bar marks "today", separate
                    # from category dots so the two don't get confused.
                    today_bar = tk.Frame(cell, height=3, bg=self.colors["accent"])
                    today_bar.pack(fill="x", side="top")

                day_lbl = tk.Label(cell, text=str(day), font=("Segoe UI", 11, "bold" if is_today else "normal"),
                                   bg=cell_bg, fg=lbl_fg)
                day_lbl.pack(pady=(4, 2))

                # Manually-flagged day markers (via right-click > Mark this
                # day) show as a small badge cluster in the cell's corner —
                # visible whether or not the day has any notes.
                self._build_day_badge(cell, date_str, cell_bg, day_color)

                hover_targets = [cell, day_lbl]

                if has_notes:
                    dots_row = tk.Frame(cell, bg=cell_bg)
                    dots_row.pack(pady=(0, 2))
                    seen_colors = []
                    for n in day_notes:
                        c = self.get_note_color(effective_note(n, date_str))
                        if c not in seen_colors:
                            seen_colors.append(c)
                    for dot_color in seen_colors:
                        dot = tk.Label(dots_row, text="●", fg=dot_color, font=("Segoe UI", 9), bg=cell_bg)
                        dot.pack(side="left", padx=1)
                    hover_targets.append(dots_row)

                    # Title previews — show up to 2 note titles at a readable
                    # size (bigger in a wide window), plus a "+N more" line.
                    # A thin divider between them makes it clear where one
                    # note's title ends and the next begins.
                    note_fs = self._cal_note_font_size()
                    max_shown = 2
                    shown_notes = day_notes[:max_shown]
                    for idx, dn in enumerate(shown_notes):
                        eff = effective_note(dn, date_str)
                        full_title = _note_str(eff, "title") or "(untitled)"
                        t = _truncate(full_title, 16)
                        # If the title has an emoji that truncation would cut
                        # off (e.g. it sits near the end of a long title),
                        # surface it up front so it's still recognizable at a
                        # glance instead of silently disappearing.
                        found_emoji = _extract_first_emoji(full_title)
                        if found_emoji and found_emoji not in t:
                            t = f"{found_emoji} {t}"
                        if is_recurring(dn):
                            t = "🔁 " + t
                        chip = tk.Label(cell, text=t, font=("Segoe UI", note_fs),
                                        wraplength=88, justify="left",
                                        bg=cell_bg,
                                        fg=(lbl_fg if day_color else self.colors["text"]))
                        chip.pack(pady=(0, 1), padx=2, anchor="w", fill="x")
                        # Hovering THIS specific title previews just that one
                        # note, not the whole day's notes crammed together.
                        chip.bind("<Button-1>", lambda e, d=date_str: self.open_day_popup(d))
                        chip.bind("<Button-3>",
                                  lambda e, d=date_str: self.show_day_context_menu(e, d))
                        chip.bind("<Enter>",
                                  lambda e, n=dn, d=date_str: self.show_note_hover_preview(n, d))
                        chip.bind("<Leave>", lambda e: self.hide_day_tooltip())
                        # A faint divider line under each chip except the last,
                        # so multiple notes in one cell read as separate items.
                        if idx < len(shown_notes) - 1:
                            divider = tk.Frame(cell, bg=self.colors["subtext"], height=1)
                            divider.pack(fill="x", padx=10, pady=1)
                    if len(day_notes) > max_shown:
                        more = tk.Label(cell, text=f"+{len(day_notes) - max_shown} more",
                                        font=("Segoe UI", max(note_fs - 1, 8), "italic"),
                                        bg=cell_bg,
                                        fg=(lbl_fg if day_color else self.colors["subtext"]))
                        more.pack(pady=(0, 4), anchor="w", padx=2)
                        hover_targets.append(more)
                    else:
                        tk.Frame(cell, height=2, bg=cell_bg).pack()
                else:
                    # Keep row heights consistent whether or not a day has notes
                    spacer = tk.Label(cell, text=" ", font=("Segoe UI", 4), bg=cell_bg)
                    spacer.pack()

                # These targets (cell background, day number, the dot row, and
                # "+N more") show a compact, TITLES-ONLY summary of the day on
                # hover — never full note bodies, so it can't balloon into a
                # huge box even when a day has many notes.
                for widget in hover_targets:
                    widget.bind("<Button-1>", lambda e, d=date_str: self.open_day_popup(d))
                    widget.bind("<Button-3>", lambda e, d=date_str: self.show_day_context_menu(e, d))
                    if has_notes:
                        widget.bind("<Enter>", lambda e, d=date_str: self.show_day_summary_tooltip(d))
                        widget.bind("<Leave>", lambda e: self.hide_day_tooltip())

            # Uniform row height so every week is the same size regardless of
            # how many notes a day holds. "uniform" ties all rows to one size.
            self.cal_grid_frame.grid_rowconfigure(row_idx, weight=1, uniform="calweek", minsize=90)

        # Cells are recreated on every render, so (re)bind the mousewheel across
        # the whole calendar area — otherwise the wheel only works when the
        # cursor is over the scrollbar, not over the day cells.
        if hasattr(self, "cal_scroll_canvas"):
            self._bind_mousewheel_recursive(self.cal_grid_frame, self.cal_scroll_canvas)
        # Fresh cells also mean the selected-day border was torn down with
        # the old ones — re-mark the open day, if its month is on screen.
        self._update_selected_day_outline()
        # render_calendar is the single signal "calendar data changed,
        # redraw" — every mutation (delete, restore, save, duplicate)
        # calls it. When the History register is the visible view, it is
        # a THIRD view of the same data and must refresh here too, or a
        # delete only showed after a trip out to the grid and back
        # (field report).
        if getattr(self, "_history_visible", False):
            self._render_calendar_history()

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
        # Mark as shown for today so it won't reappear on the next launch.
        settings["reminder_last_shown"] = today
        save_settings(settings)
        self._render_reminder_bar(len(due), today)

    def _render_reminder_bar(self, count, today):
        for w in self.reminder_bar.winfo_children():
            w.destroy()
        self.reminder_bar.pack(fill="x", side="top", before=self.notebook)

        noun = "note" if count == 1 else "notes"
        try:
            friendly = datetime.strptime(today, "%Y-%m-%d").strftime("%A, %B %d")
        except (ValueError, TypeError):
            friendly = today
        msg = tk.Label(
            self.reminder_bar,
            text=f"🔔  You have {count} {noun} for today ({friendly}).",
            bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold"),
            anchor="w", cursor="hand2"
        )
        msg.pack(side="left", padx=14, pady=6)
        # Clicking the text jumps to today's notes in the calendar.
        msg.bind("<Button-1>", lambda e: self._open_today_from_reminder(today))

        close = tk.Label(self.reminder_bar, text="✕", bg=self.colors["accent"],
                         fg="white", font=("Segoe UI", 10, "bold"), cursor="hand2")
        close.pack(side="right", padx=12)
        close.bind("<Button-1>", lambda e: self.dismiss_reminder())

    def _open_today_from_reminder(self, today):
        self.notebook.select(self.TAB_CALENDAR)
        self.open_day_popup(today)

    def dismiss_reminder(self):
        """Hide the reminder bar for the rest of the session."""
        self.reminder_bar.pack_forget()

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
        day_notes = self.notes_on_date(date_str)
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

        try:
            friendly = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %b %d")
        except (ValueError, TypeError):
            friendly = date_str
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
                 wraplength=260).pack(anchor="w")

        if is_recurring(base_note):
            tk.Label(inner, text=describe_recurrence(base_note), bg=self.colors["card"],
                     fg=self.colors["accent"], font=("Segoe UI", 8, "italic"),
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
                     wraplength=260).pack(anchor="w", pady=(3, 0))

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

        try:
            friendly = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        except (ValueError, TypeError):
            friendly = str(date_str)

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
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=8, ipady=2)

        # Scrollable list area.
        body = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        body.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        canvas = tk.Canvas(body, bg=self.colors["sidebar"], highlightthickness=0)
        sb = ttk.Scrollbar(body, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["sidebar"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        day_notes = self.notes_on_date(date_str)
        if not day_notes:
            tk.Label(inner, text="No notes for this day yet.",
                     bg=self.colors["sidebar"], fg=self.colors["subtext"],
                     font=("Segoe UI", 10)).pack(pady=10)
            self._bind_mousewheel_recursive(inner, canvas)
            return

        for base_note in day_notes:
            note = effective_note(base_note, date_str)
            color = self.get_note_color(note)
            row = tk.Frame(inner, bg=self.colors["card"], cursor="hand2")
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
            title_text = _note_str(note, "title") or "(untitled)"
            if is_recurring(base_note):
                title_text = "🔁 " + title_text
            icons = ""
            if date_str in (base_note.get("overrides") or {}):
                # This day was edited with "only this occurrence" — it
                # keeps its own content and series edits don't reach it.
                icons += "  ✎"
            if note.get("comments"):
                icons += "  💬"
            if note.get("attachments"):
                icons += f"  📎×{len(note['attachments'])}"
            lbl = tk.Label(row, text=title_text + icons, bg=self.colors["card"],
                           fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=10, pady=8)

            def _open(e, n=base_note, d=date_str):
                self.show_day_note(n, d)

            def _context(e, n=base_note, d=date_str):
                self.show_note_context_menu(e, n, occurrence_date=d)

            for w in (row, stripe, lbl):
                w.bind("<Button-1>", _open)
                w.bind("<Button-3>", _context)

        # Bind the wheel now that every note row exists.
        self._bind_mousewheel_recursive(inner, canvas)

    def show_day_note(self, base_note, date_str):
        """Open a single note inside the day panel, with a Back button that
        returns to the day's note list."""
        self._clear_day_panel()
        self._day_panel_mode = "note"
        note = effective_note(base_note, date_str)

        top = tk.Frame(self.day_panel, bg=self.colors["sidebar"])
        top.pack(fill="x", padx=15, pady=(10, 6))
        tk.Button(top, text="← Back", command=self.show_day_list,
                  bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", ipadx=6, ipady=2)
        tk.Button(top, text="✏ Open in editor",
                  command=lambda: self._open_note_from_calendar(base_note, date_str),
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=6, ipady=2)
        tk.Button(top, text="🗑 Delete",
                  command=lambda: self._delete_note_from_calendar(base_note, date_str),
                  bg=self.colors["danger"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)

        title = _note_str(note, "title").strip() or "(untitled)"
        title_lbl = tk.Label(self.day_panel, text=title,
                             font=("Segoe UI", 12, "bold"),
                             bg=self.colors["sidebar"], fg=self.colors["text"],
                             anchor="w", wraplength=700, justify="left")
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

        for widget in (self.day_panel, top, title_lbl):
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
        if date_str in (base_note.get("overrides") or {}):
            chips.append("✎ edited for this day")
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
                     bg=self.colors["sidebar"], fg=self.colors["accent"]
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

    def _open_note_from_calendar(self, base_note, date_str):
        """Open an EXISTING note (not a new one) from the calendar day panel.
        Same 'remember where we came from' treatment as creating a note there —
        open_note_in_tab clears any pending return first (it's meant to, for
        the normal case of switching between notes), so we set it again right
        after, once that's done."""
        remembered = {"year": self.cal_year, "month": self.cal_month,
                      "date_str": date_str, "origin": "edit"}
        self.notebook.select(self.TAB_NOTES)
        self.open_note_in_tab(base_note, occurrence_date=date_str)
        self._pending_calendar_return = remembered
        self._update_calendar_return_button()

    def _add_note_for_date(self, date_str):
        """Start a new note pre-filled with this date. Editing still happens on
        the Notes tab (the editor lives there), but we remember where we came
        from in the calendar so saving (or 'Back to Calendar') returns you to
        the exact same month/day — it shouldn't feel like being sent away."""
        # Flush before clearing, like every other route into an empty
        # editor — this path once discarded pending edits silently.
        self._flush_autosave()
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
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date_str)
        self.date_entry.config(fg=self.colors["text"])
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
                    if getattr(self, "_day_panel_mode", "empty") != "empty"
                    else None)
        for d, cell in (getattr(self, "_cal_cell_widgets", None) or {}).items():
            try:
                if d == selected:
                    cell.configure(highlightthickness=2,
                                   highlightbackground=self.colors["accent"])
                else:
                    cell.configure(highlightthickness=0)
            except tk.TclError:
                pass

    def _toggle_calendar_history(self):
        """Swap the month grid (and day panel) for the History register,
        or bring the grid back."""
        if getattr(self, "_history_visible", False):
            self._hide_calendar_history()
        else:
            self._show_calendar_history()

    def _show_calendar_history(self):
        if not self._history_built:
            self._build_history_ui()
        self.close_day_panel()
        self.cal_grid_frame.pack_forget()
        self._history_visible = True
        self.history_frame.pack(side="top", fill="both", expand=True,
                                padx=30, pady=(0, 10))
        if hasattr(self, "_history_toggle_btn"):
            self._history_toggle_btn.configure(text="📅 Calendar")
        self._render_calendar_history()

    def _hide_calendar_history(self):
        self._history_visible = False
        self.history_frame.pack_forget()
        self.cal_grid_frame.pack(side="top", fill="both", expand=True,
                                 padx=30, pady=(0, 10))
        if hasattr(self, "_history_toggle_btn"):
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

        self._history_rows = tk.Frame(self.history_frame)
        self.track_theme(self._history_rows, bg="bg")
        self._history_rows.pack(fill="both", expand=True)

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

    def _render_calendar_history(self):
        """The rebuilt half: rows re-created per render, coloured with
        plain .configure so they always wear the CURRENT theme."""
        self._history_search_job = None
        if not (self._history_visible and self._history_built):
            return
        for w in self._history_rows.winfo_children():
            w.destroy()

        # Active-chip styling rides every render (including theme ones).
        for bucket, b in self._history_chip_btns.items():
            active = (bucket == self._history_bucket)
            b.configure(
                bg=self.colors["accent"] if active else self.colors["card"],
                fg="white" if active else self.colors["text"],
                activebackground=self.colors["accent"],
                activeforeground="white")

        query = self._history_query()
        entries = history_entries(self.notes, query=query,
                                  year_bucket=self._history_bucket)

        if not entries:
            lbl = tk.Label(self._history_rows,
                           text=("No calendar entries match." if query or
                                 self._history_bucket != "All" else
                                 "Nothing on the calendar yet — give a note "
                                 "a date, or make one repeat."),
                           font=("Segoe UI", 10), bg=self.colors["bg"],
                           fg=self.colors["subtext"])
            lbl.pack(pady=20)
            return

        def one_row(parent, text, fg, command, context_cmd=None, indent=0,
                    bold=False):
            row = tk.Frame(parent, bg=self.colors["card"], cursor="hand2")
            row.pack(fill="x", pady=1, padx=(indent, 0))
            lbl = tk.Label(row, text=text, anchor="w",
                           font=("Segoe UI", 9, "bold" if bold else "normal"),
                           bg=self.colors["card"], fg=fg)
            lbl.pack(side="left", fill="x", expand=True, padx=10, ipady=4)
            for w in (row, lbl):
                w.bind("<Button-1>", lambda e: command())
                if context_cmd is not None:
                    w.bind("<Button-3>", context_cmd)
            return row

        shown = entries[:self._history_shown]
        for entry in shown:
            note = self.find_note(entry["note_id"])
            if note is None:
                continue
            if entry["kind"] == "note":
                one_row(
                    self._history_rows,
                    f"📅 {entry['date']}   {entry['title'] or '(untitled)'}",
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
                    f"{glyph} 🔁 {entry['title'] or '(untitled)'} · "
                    f"{entry['freq_label']}{suffix}",
                    self.colors["accent"],
                    row_cmd,
                    context_cmd=lambda e, n=note:
                        self.show_note_context_menu(e, n),
                    bold=True)
                if expanded:
                    for child in entry["children"]:
                        mark = "✎" if child.get("edited") else "•"
                        one_row(
                            self._history_rows,
                            f"{mark} {child['date']}   "
                            f"{child['title'] or '(untitled)'}",
                            self.colors["text"],
                            lambda n=note, d=child["date"]:
                                self._history_open_day(n, d),
                            context_cmd=lambda e, n=note, d=child["date"]:
                                self.show_note_context_menu(
                                    e, n, occurrence_date=d),
                            indent=26)
                    if entry["children_kind"] == "edited":
                        info = tk.Label(
                            self._history_rows,
                            text=("    …every other day of this series shows "
                                  "the series content"),
                            font=("Segoe UI", 8), anchor="w",
                            bg=self.colors["bg"], fg=self.colors["subtext"])
                        info.pack(fill="x", padx=(26, 0))

        if len(entries) > self._history_shown:
            more = tk.Button(
                self._history_rows,
                text=f"Show more ({len(entries) - self._history_shown} left)",
                relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
                bg=self.colors["card"], fg=self.colors["accent"],
                activebackground=self.colors["sidebar"],
                activeforeground=self.colors["accent"],
                command=self._history_show_more)
            more.pack(fill="x", pady=(6, 2))

        self._bind_mousewheel_recursive(self._history_rows,
                                        self.cal_scroll_canvas)

    def _history_toggle_group(self, note_id):
        if note_id in self._history_expanded:
            self._history_expanded.discard(note_id)
        else:
            self._history_expanded.add(note_id)
        self._render_calendar_history()

    def _history_show_more(self):
        self._history_shown += 50
        self._render_calendar_history()

    def _history_open_day(self, note, date_str):
        """Back to the grid, on that exact month, with the day panel
        showing this note's preview — the chosen landing for a row click."""
        d = parse_date(date_str)
        self._hide_calendar_history()
        if d is not None:
            self.cal_year, self.cal_month = d.year, d.month
            self.render_calendar()
        self.open_day_popup(date_str)
        self.show_day_note(note, date_str)
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date_str)
        self.date_entry.config(fg=self.colors["text"])
        self.title_entry.focus()
        self._update_calendar_return_button()

    def show_day_context_menu(self, event, date_str):
        """Right-click menu for a calendar day: add a note, or color the day.
        Left-click still opens the day panel; this is the separate right-click
        action."""
        menu = tk.Menu(self, tearoff=0)
        menu.configure(
            bg=self.colors["card"], fg=self.colors["text"],
            activebackground=self.colors["accent"], activeforeground="white",
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
                command=lambda: (self.day_emoji.pop(date_str, None),
                                 self._persist_day_emoji(), self.render_calendar())
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
            if color:
                self.day_colors[date_str] = color
            else:
                self.day_colors.pop(date_str, None)
            self._persist_day_colors()
            self.render_calendar()

        if event is not None:
            anchor_xy = (event.x_root, event.y_root)
        else:
            anchor_xy = (self.winfo_rootx() + 100, self.winfo_rooty() + 100)
        self._show_color_palette(None, current, on_pick, allow_reset=True,
                                 anchor_xy=anchor_xy, reset_label="No color")

    def _clear_day_color(self, date_str):
        if date_str in self.day_colors:
            del self.day_colors[date_str]
            self._persist_day_colors()
            self.render_calendar()

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
        MAX_DAY_MARKERS = 3

        def refresh_cell(em):
            cell = cells[em]
            selected = em in pending
            cell.configure(highlightthickness=2 if selected else 0,
                           highlightbackground=self.colors["text"],
                           highlightcolor=self.colors["text"])

        def toggle(em):
            if em in pending:
                pending.remove(em)
            elif len(pending) < MAX_DAY_MARKERS:
                pending.append(em)
            # else: already at the 3-marker cap — ignore, keeps the calendar
            # cell readable and avoids piling on emoji that would just show
            # as an anonymous "+N" nobody could identify without reopening
            # this same popup.
            refresh_cell(em)
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
            hover_color = _darken_hex(color)
            # "break" stops this click from also reaching the app-wide
            # click-outside-closes-the-popup handler — without it, picking an
            # emoji could immediately close this same popup.
            cell.bind("<Button-1>", lambda e, em=em: toggle(em))
            cell.bind("<Enter>", lambda e, w=cell, h=hover_color: w.configure(bg=h))
            cell.bind("<Leave>", lambda e, w=cell, b=color: w.configure(bg=b))
            refresh_cell(em)

        def clear_pending():
            pending.clear()
            for em in cells:
                refresh_cell(em)

        def save_and_close():
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

        btn_row = tk.Frame(outer, bg=self.colors["card"])
        btn_row.pack(fill="x", pady=(8, 0))
        tk.Button(btn_row, text="Clear", command=clear_pending, relief="flat",
                  cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 8)).pack(side="left", fill="x", expand=True,
                                             padx=(0, 4), ipady=4)
        tk.Button(btn_row, text="✓ Save", command=save_and_close, relief="flat",
                  cursor="hand2", bg=self.colors["accent"], fg="white",
                  font=("Segoe UI", 8, "bold")).pack(side="left", fill="x", expand=True,
                                                     padx=(4, 0), ipady=4)

        if event is not None:
            anchor_xy = (event.x_root, event.y_root)
            self._place_dropdown_popup(pop, None, anchor_xy=anchor_xy)
        else:
            self._place_dropdown_popup(pop, None,
                                       anchor_xy=(self.winfo_rootx() + 100, self.winfo_rooty() + 100))

    def _persist_day_emoji(self):
        # Drop any None/empty entries (from Clear) rather than persisting them.
        self.day_emoji = {d: e for d, e in self.day_emoji.items() if e}
        save_setting("day_emoji", dict(self.day_emoji))
