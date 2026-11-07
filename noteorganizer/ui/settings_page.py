"""The Settings page and the panels on it: categories, templates, Trash,
duplicates, statistics, the theme picker and About, with the rows and the
template editor they are built from. Each ``_build_settings_*_panel`` draws
one section; :meth:`build_settings_tab` lays them beside a navigation column.

The theming engine, the shared dialogs and dropdowns, and the category
*operations* belong to the whole app and stay on :class:`NoteOrganizer`;
panels call them through ``self``, as mixins share one object.
"""

import os
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime, timedelta, date as date_cls

from ..core import diagnostics, paths
from ..core.categories import (CATEGORY_COLORS, category_name_refusal,
                               persist_categories)
from ..core.formatting import FONT_FAMILIES, FONT_SIZES
from ..core.spelling import SPELLING_SETTING
from ..core.duplicates import SAME_AS, find_duplicate_groups
# The Trash says which rows are whole repeating series: a Trash entry is a
# copy of the note, and answers these as the note would.
from ..core.recurrence import describe_recurrence, is_recurring, show_date
# Shortens with an ellipsis rather than by slicing: a title cut at N
# characters with nothing to show for it is the same defect as a
# sentence clipped by a layout, only cheaper to make.
from ..core.model import (MAX_ATTACHMENTS, MAX_CHECKLIST_ITEM_CHARS, MAX_CHECKLIST_ITEMS,
                          _truncate, checklist_shown, normalize_note)
from ..core.storage import (
    MAX_TEMPLATES,
    TRASH_RETENTION_DAYS,
    trash_retention_days,
    trash_window_words,
    choose_trash_window,
    # The entries a window outlived, deleting none: the purge's own answer,
    # so the confirmation cannot promise another number.
    trash_entries_past_window,
    _delete_attachment_files,
    attachment_names_in,
    attachments_of,
    copy_attachment_file,
    get_setting,
    save_setting,
    load_settings,
    normalize_template,
    same_attached_file,
    save_templates,
    save_trash,
)
from ..core.themes import (
    THEMES,
    DARK_THEMES,
    LIGHT_THEMES,
    THEME_LABELS,
    DEFAULT_CATEGORY_COLORS,
    PROTECTED_CATEGORY,
    SHARP_TEXT_SETTING,
    inset_surface,
    hairline,
)
from .calendar_view import _fit_title
from .dialogs import one_line


def _host():
    """The entry-point module, imported here, as at the top it is circular.
    ONLY for constants such as ``APP_VERSION``: run as a script, the app is
    ``__main__``, and this import loads a second copy whose ``initialise()``
    never ran -- About's storage path came out blank. What initialise()
    fills in is read from the core layer instead.
    """
    import note_organizer
    return note_organizer


def _trash_tick_key(entry):
    """Which Trash entry a tick in Settings -> Recently deleted belongs to:
    an id is handed out again after a delete, and one tick ticked two rows.
    When it was deleted tells them apart, and the uid within one second.
    """
    key = (entry.get("id"), entry.get("deleted_at"), entry.get("uid"))
    try:
        hash(key)
    except TypeError:
        # The trash file is read as it was written, and a hand-edited one
        # can hold a list where a value goes; a dict key must be hashable.
        key = tuple(repr(part) for part in key)
    return key


class SettingsPageMixin:
    """The Settings page for :class:`NoteOrganizer`.

    Not usable on its own — every method here reads state owned by the app
    (``self.colors``, ``self.notes``, ``self.settings_canvas`` and so on).
    """

    def toggle_settings_panel(self, which):
        """Show one Settings section, hiding whichever was showing. Named
        "toggle" from the old accordion, as the app and the qa suite ask for
        sections by it; one is always showing now, so this selects.
        """
        sections = {key: (getattr(self, "settings_%s_panel" % key, None), builder, eager)
                    for key, _label, builder, eager in self.SETTINGS_SECTIONS}
        target, builder, eager = sections.get(which, (None, None, None))
        if target is None:
            return

        # Leaving or rebuilding a section takes the template editor with it:
        # it asks first, as on a click outside; False when the person stays.
        if not self._dismiss_mini_popup_asking(holding_work_only=True):
            return False

        for key, (panel, _b, _e) in sections.items():
            if panel is not None and self._is_placed(panel):
                panel.pack_forget()

        if not eager:
            # Heavy panels rebuild on each visit, so they reflect the current
            # notes rather than whatever was true when Settings was opened.
            for w in target.winfo_children():
                w.destroy()
            self._active_panel_canvas = None
            self._resize_handles_pending = []
            label = next(l for k, l, _b, _e in self.SETTINGS_SECTIONS if k == which)
            self._settings_section_heading(target, label)
            builder_fn = getattr(self, builder)
            builder_fn(target)
            # A resize handle overlays a panel's bottom edge, so it is built
            # here from what the builders recorded, lifted above its siblings.
            for tgt, mn, mx in getattr(self, "_resize_handles_pending", []):
                h = self._add_resize_handle(tgt, min_h=mn, max_h=mx, host=target)
                h.pack(fill="x", padx=12, pady=(2, 8))
            self._resize_handles_pending = []

        target.pack(fill="both", expand=True, padx=48, pady=(40, 60))
        self._settings_selected_section = which
        self._highlight_settings_nav(which)
        # The keyboard, already in the list, follows the entry chosen: a click
        # does not move it, and its ring stayed on another entry than the one
        # marked selected. Here, not in the highlight a theme repaint runs too.
        chosen = self._settings_nav_buttons.get(which)
        try:
            held = self.focus_get()
        except (KeyError, tk.TclError):
            held = None
        if (chosen is not None and held is not None and held is not chosen
                and held in self._settings_nav_buttons.values()):
            try:
                chosen.focus_set()
            except tk.TclError:
                pass
        if self.settings_canvas is not None:
            try:
                self.settings_canvas.yview_moveto(0)
            except tk.TclError:
                pass

    def _highlight_settings_nav(self, which):
        """Mark the selected nav entry, clear the rest.

        A solid accent block was the loudest thing on the page and sat there
        permanently. The same information -- you are here -- carries fine on
        an accent rail plus a tint of the accent mixed into the sidebar, with
        the label in the accent colour rather than reversed out to white.
        """
        rails = self._settings_nav_rails
        icons = self._settings_nav_icons
        tint = self._blend(self.colors["sidebar"], self.colors["accent"], 0.16)
        for key, btn in self._settings_nav_buttons.items():
            try:
                selected = (key == which)
                btn.configure(
                    bg=tint if selected else self.colors["sidebar"],
                    fg=self.colors["accent_text"] if selected else self.colors["subtext"],
                    activebackground=tint if selected else self.colors["card"],
                )
                rail = rails.get(key)
                if rail is not None:
                    rail.configure(bg=tint if selected else self.colors["sidebar"])
                    rail.delete("all")
                    if selected:
                        h = max(rail.winfo_height(), self.px(34))
                        top = (h - self.px(16)) / 2
                        rail.create_rectangle(0, top, self.px(3), top + self.px(16),
                                              fill=self.colors["accent"],
                                              outline=self.colors["accent"])
                icon = icons.get(key)
                if icon is not None:
                    icon.configure(bg=tint if selected else self.colors["sidebar"])
                    self._draw_icon(
                        icon, key,
                        self.colors["accent_text"] if selected else self.colors["subtext"])
            except tk.TclError:
                pass

    def _panel_or_page_wheel(self, panel_canvas, event):
        """If the panel's list can scroll, scroll it; else scroll the whole
        Settings page. Used for every widget in an inline settings panel."""
        if panel_canvas is not None:
            try:
                first, last = panel_canvas.yview()
                # A tolerance: yview() can say 0.997 for a panel shown whole,
                # which then trapped the wheel instead of passing it on.
                if not (first <= 0.001 and last >= 0.999):
                    panel_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return "break"
            except (tk.TclError, ValueError):
                pass
        page_canvas = self.settings_canvas
        if page_canvas is not None:
            try:
                page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
        return "break"

    def _settings_page_key(self, event, how):
        """Page Up and Down, the arrows, Home and End scroll the Settings page
        -- *how* is a (count, "pages"/"units") step or a place to move to --
        from anywhere on it but a box being typed in, or a popup over it."""
        if not getattr(self, "_settings_open", False) or self._a_dialog_is_asking():
            return None
        widget = getattr(event, "widget", None)
        try:
            # A box out of sight is no box being typed in.
            if (isinstance(widget, str) or widget.winfo_toplevel() is not self
                    or (widget.winfo_class() in self._TYPING_CLASSES
                        and widget.winfo_viewable())):
                return None
            canvas = self.settings_canvas
            if isinstance(how, float):
                canvas.yview_moveto(how)
            else:
                canvas.yview_scroll(*how)
        except (tk.TclError, AttributeError):
            return None
        return "break"

    def _wrap_to_own_width(self, label, inset=4):
        """Wrap where the label ends, taken from the label once it has a
        width -- guessed wraplengths cut three labels' lines mid-word, by up
        to 69 px. Only for labels the parent stretches (fill="x"), or it
        shrinks and re-wraps for ever. `inset` is the label's own border and
        padding, measured at three pixels.
        """
        def fit(event):
            want = max(self.px(160), event.width - inset)
            if int(label.cget("wraplength") or 0) != want:
                label.configure(wraplength=want)
        label.bind("<Configure>", fit, add="+")
        return label

    def _settings_subtitle(self, parent, text):
        """The explanatory line under a section title -- the navigation
        names the section, and one always shows, so there is no title or ✕.
        """
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 10), anchor="w",
                       justify="left",
                       bg=self.colors["bg"], fg=self.colors["subtext"])
        lbl.pack(fill="x", pady=(0, 22))
        return self._wrap_to_own_width(lbl)

    def _render_statistics(self):
        """Draw a read-only snapshot: totals, when notes were added and
        updated, templates, checklists, the Trash, the first-use date, and
        per category (not clickable: no other way to filter). Redrawn at
        every list refresh while Settings is open -- ``_settings_open``, set
        by the swap itself, not winfo_ismapped(), which lags -- and on the
        way in. An odd field is skipped from its count, never fatal."""
        if not hasattr(self, "stats_frame"):
            return
        if not getattr(self, "_settings_open", False):
            return

        notes = self.notes
        total = len(notes)

        today = date_cls.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        # Days compared as "YYYY-MM-DD" text, which sorts as the dates do.
        week_day, month_day, year_day = (week_start.isoformat(),
                                         month_start.isoformat(),
                                         year_start.isoformat())
        real_days = {}

        def _day(raw):
            # The app's own "YYYY-MM-DD HH:MM" is read as text, each day once;
            # strptime on every stamp was most of a 200 ms render. Any other
            # shape still goes through strptime, so the same stamps count.
            if not isinstance(raw, str) or not raw:
                return None
            head = raw[:16]
            if (len(head) == 16 and head.isascii() and head[4] == "-"
                    and head[7] == "-" and head[10] == " " and head[13] == ":"
                    and (head[:4] + head[5:7] + head[8:10] + head[11:13]
                         + head[14:16]).isdigit()):
                if int(head[11:13]) > 23 or int(head[14:16]) > 59:
                    return None
                day = head[:10]
                real = real_days.get(day)
                if real is None:
                    try:
                        date_cls.fromisoformat(day)
                        real = True
                    except ValueError:
                        real = False
                    real_days[day] = real
                return day if real else None
            try:
                return datetime.strptime(head, "%Y-%m-%d %H:%M").date().isoformat()
            except ValueError:
                return None

        def _bucket_counts(field):
            # Cumulative from the start of each period (so "this year"
            # already includes "this month"); "older" is the one true
            # complement — notes not touched at all since Jan 1st.
            week = month = year = older = 0
            for n in notes:
                d = _day(n.get(field))
                if d is None:
                    continue
                if d >= week_day:
                    week += 1
                if d >= month_day:
                    month += 1
                if d >= year_day:
                    year += 1
                else:
                    older += 1
            return week, month, year, older

        added_week, added_month, added_year, added_older = _bucket_counts("created")
        updated_week, updated_month, updated_year, updated_older = _bucket_counts("updated")

        # --- Shown as figures, not sentences: tiles, a table with a header,
        # then the categories -- numbers lead, captions follow. Tallied here,
        # as the tiles count the categories too. ---
        counts = {}
        for n in notes:
            cat = n.get("category") or PROTECTED_CATEGORY
            counts[cat] = counts.get(cat, 0) + 1
        # The things themselves, not the notes naming them; "In trash" is what
        # is there now, not an all-time total.
        templates_count = len(self.templates)
        checklists_count = sum(1 for n in notes if n.get("checklist"))
        deleted_count = len(self.trash)
        tile_values = (total, added_week, len(counts), templates_count,
                       checklists_count, deleted_count)
        table_values = ((added_week, added_month, added_year, added_older),
                        (updated_week, updated_month, updated_year, updated_older))
        # --- Per category: the known ones in their order, then any stale
        # name, so nothing is dropped. ---
        ordered_cats = [c for c in CATEGORY_COLORS.keys() if c in counts]
        ordered_cats += [c for c in counts.keys() if c not in ordered_cats]
        # From settings, not the entry module's global, which can be None
        # here (_host); written once, at start, by get_first_launch_date().
        since = show_date(load_settings().get("first_launch_date")) or "\u2014"

        # The wheel passed on, as elsewhere in Settings; bound on the frame
        # once -- at every render, it left a Tcl command behind each time.
        def _stats_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        if not getattr(self.stats_frame, "_wheel_bound", False):
            self.stats_frame._wheel_bound = True
            self.stats_frame.bind("<MouseWheel>", _stats_wheel)

        # The widgets stay and their figures change, built again only when
        # what is DRAWN changes: the palette, or the categories.
        shape = tuple((c, CATEGORY_COLORS.get(c)) for c in ordered_cats)
        view = getattr(self, "_stats_view", None)
        try:
            same_drawing = (view is not None and view["colors"] is self.colors
                            and view["shape"] == shape
                            and view["since"].winfo_exists())
        except tk.TclError:
            same_drawing = False
        if same_drawing:
            for lbl, value in zip(view["tiles"], tile_values):
                lbl.configure(text=str(value))
            for row, values in zip(view["table"], table_values):
                for lbl, value in zip(row, values):
                    lbl.configure(text=str(value),
                                  fg=self.colors["text"] if value else self.colors["subtext"])
            for lbl, cat in zip(view["cat_counts"], ordered_cats):
                lbl.configure(text=str(counts[cat]))
            view["since"].configure(text=f"Using Note Organizer since {since}")
            return
        for w in self.stats_frame.winfo_children():
            w.destroy()
        view = self._stats_view = {"colors": self.colors, "shape": shape,
                                   "tiles": [], "table": [], "cat_counts": [],
                                   "since": None}

        tiles = tk.Frame(self.stats_frame, bg=self.colors["bg"])
        tiles.pack(fill="x", pady=(0, 22))
        for i in range(3):
            tiles.grid_columnconfigure(i, weight=1, uniform="stat")
        # Three across, as designed, but six figures on two rows: matching the
        # sketch's three would have dropped real, tested counts.
        for i, (value, caption) in enumerate(zip(tile_values, (
                "Total notes", "Added this week", "Categories", "Templates",
                "With a checklist", "In trash"))):
            edge = tk.Frame(tiles, bg=self._border_color())
            edge.grid(row=i // 3, column=i % 3, sticky="nsew",
                      padx=(0 if i % 3 == 0 else 12, 0),
                      pady=(0 if i < 3 else 12, 0))
            tile = tk.Frame(edge, bg=self._surface())
            tile.pack(fill="both", expand=True, padx=1, pady=1)
            figure = tk.Label(tile, text=str(value), font=("Segoe UI", 20, "bold"),
                              bg=self._surface(), fg=self.colors["text"], anchor="w")
            figure.pack(fill="x", padx=18, pady=(16, 0))
            view["tiles"].append(figure)
            tk.Label(tile, text=caption, font=("Segoe UI", 9, "bold"),
                     bg=self._surface(), fg=self.colors["subtext"], anchor="w"
                     ).pack(fill="x", padx=18, pady=(3, 16))

        # --- The time breakdown as a table: digits right-aligned, the header
        # saying once what each cell repeated. ---
        SEGMENTS = ("this week", "this month", "this year", "older")
        table = tk.Frame(self.stats_frame, bg=self.colors["bg"])
        table.pack(fill="x", pady=(0, 4))
        table.grid_columnconfigure(0, weight=0, minsize=self.px(76))
        for c in range(1, 5):
            table.grid_columnconfigure(c, weight=1, uniform="seg")

        for c, seg in enumerate(SEGMENTS):
            tk.Label(table, text=seg, font=("Segoe UI", 8), bg=self.colors["bg"],
                     fg=self.colors["subtext"], anchor="e"
                     ).grid(row=0, column=c + 1, sticky="ew", padx=(8, 0), pady=(0, 2))

        rule = tk.Frame(table, height=1, bg=self._border_color())
        rule.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(0, 4))

        for r, (caption, values) in enumerate(zip(("Added", "Updated"), table_values)):
            tk.Label(table, text=caption, font=("Segoe UI", 9), bg=self.colors["bg"],
                     fg=self.colors["subtext"], anchor="w"
                     ).grid(row=r + 2, column=0, sticky="w", pady=2)
            row_figures = []
            for c, value in enumerate(values):
                figure = tk.Label(table, text=str(value), font=("Segoe UI", 10, "bold"),
                                  bg=self.colors["bg"],
                                  fg=self.colors["text"] if value else self.colors["subtext"],
                                  anchor="e")
                figure.grid(row=r + 2, column=c + 1, sticky="ew", padx=(8, 0), pady=2)
                row_figures.append(figure)
            view["table"].append(row_figures)

        tk.Label(self.stats_frame, text="BY CATEGORY", font=("Segoe UI", 8, "bold"),
                 bg=self.colors["card"], fg=self.colors["subtext"], anchor="w"
                 ).pack(fill="x", pady=(16, 6))

        if not ordered_cats:
            tk.Label(self.stats_frame, text="No notes yet.", font=("Segoe UI", 9),
                     bg=self.colors["bg"], fg=self.colors["subtext"], anchor="w"
                     ).pack(fill="x")
        else:
            grid = tk.Frame(self.stats_frame, bg=self.colors["bg"])
            grid.pack(fill="x")
            cols = 3
            for col in range(cols):
                grid.grid_columnconfigure(col, weight=1, uniform="cat")
            for idx, cat in enumerate(ordered_cats):
                n = counts[cat]
                color = CATEGORY_COLORS.get(cat, self.colors["subtext"])
                edge = tk.Frame(grid, bg=self._border_color())
                edge.grid(row=idx // cols, column=idx % cols, sticky="ew",
                          padx=(0 if idx % cols == 0 else 8, 0), pady=4)
                pill = tk.Frame(edge, bg=self._surface())
                pill.pack(fill="both", expand=True, padx=1, pady=1)
                dot = tk.Frame(pill, bg=color, width=7, height=7)
                dot.pack(side="left", padx=(8, 6), pady=8)
                dot.pack_propagate(False)
                cat_lbl = tk.Label(pill, bg=self._surface(),
                                   fg=self.colors["subtext"], anchor="w")
                _fit_title(self, cat_lbl, "", cat, "",
                           self._cal_font(("Segoe UI", 9, "bold"))[0])
                figure = tk.Label(pill, text=str(n), font=("Consolas", 9),
                                  bg=self._surface(), fg=self.colors["text"], anchor="e")
                # The count before the name: packed after it, a long name
                # took the pill and the count had no room.
                figure.pack(side="right", padx=(6, 12))
                cat_lbl.pack(side="left", fill="x", expand=True)
                view["cat_counts"].append(figure)

        view["since"] = tk.Label(
            self.stats_frame, text=f"Using Note Organizer since {since}",
            font=("Segoe UI", 9), bg=self.colors["bg"],
            fg=self.colors["subtext"], anchor="w")
        view["since"].pack(fill="x", pady=(18, 0))
        # The wheel on what was just built; the frame itself is bound once.
        for child in self.stats_frame.winfo_children():
            self._bind_wheel_tree(child, _stats_wheel)

    def _build_settings_categories_panel(self, parent):
        self._settings_subtitle(
            parent,
            "Rename, recolor, or remove your categories. “General” is permanent.")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=self.px(220))
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        rows_frame = tk.Frame(canvas, bg=self.colors["card"])
        rows_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        # The frame gets the wheel once; each redraw binds only its new rows
        # (re-bound, the frame kept a Tcl command per rename).
        wheel = lambda e: self._panel_or_page_wheel(canvas, e)  # noqa: E731
        rows_frame.bind("<MouseWheel>", wheel)

        def redraw():
            for w in rows_frame.winfo_children():
                w.destroy()
            for i, name in enumerate(list(CATEGORY_COLORS.keys())):
                if i:
                    self._row_divider(rows_frame)
                self._build_category_row(rows_frame, name, redraw)
            for child in rows_frame.winfo_children():
                self._bind_wheel_tree(child, wheel)
        redraw()

        # Add-new row
        add_row = tk.Frame(parent, bg=self.colors["card"])
        add_row.pack(fill="x", padx=12, pady=(6, 10))
        new_name_var = tk.StringVar()
        new_entry = tk.Entry(add_row, textvariable=new_name_var, relief="flat",
                             font=("Segoe UI", 10), bg=self.colors["sidebar"],
                             fg=self.colors["text"], insertbackground=self.colors["text"])
        new_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))
        self._add_paste_menu(new_entry)
        self._guard_entry_astral(new_entry)

        def add_new():
            name = new_name_var.get().strip()
            if not name:
                return
            if name in CATEGORY_COLORS:
                self.show_warning("Already exists",
                                       f"A category named “{name}” already exists.")
                return
            refusal = category_name_refusal(name)
            if refusal:
                self.show_warning("Can't add that category", refusal)
                return
            palette = list(DEFAULT_CATEGORY_COLORS.values())
            CATEGORY_COLORS[name] = palette[len(CATEGORY_COLORS) % len(palette)]
            persist_categories()
            new_name_var.set("")
            redraw()
            self.refresh_category_widgets()
            # In sight, at the list's foot: below the 220 pixels shown, "+ Add"
            # looked as if it did nothing.
            canvas.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(1.0)

        # Pressed, not held (_enter_repeats), as every Enter that acts.
        new_entry.bind("<Return>", lambda e: (
            None if self._enter_repeats(e) else add_new()))
        tk.Button(add_row, text="+ Add", command=add_new, bg=self.colors["accent"],
                  fg=self._on_fill("accent"), relief="flat", font=("Segoe UI", 9, "bold"),
                  cursor="hand2"
                  ).pack(side="right", ipadx=10, ipady=4)

    def _build_settings_templates_panel(self, parent):
        self._settings_subtitle(
            parent,
            "Reusable starting points for new notes. Create one here or use "
            "“🧩 Save as template” on any note. Pick one with “📎 Use template”. "
            "Editing a template only affects notes you make from it afterwards — "
            "notes already created stay as they are.")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=self.px(240))
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        # Each redraw gives the wheel to what it builds, chunks included (a
        # chunk dies with its rows): binding a frame that outlived the
        # redraws left a Tcl command behind at every save, delete and rename.
        wheel = lambda e: self._panel_or_page_wheel(canvas, e)  # noqa: E731
        rows = self._row_stack(canvas, scrolled=sb.set).group(every=32)

        def redraw():
            # A list this section no longer shows: rebuilt since, its rows
            # are gone, and there is nothing to redraw.
            if not canvas.winfo_exists():
                return
            rows.clear()
            if not self.templates:
                tk.Label(rows.add(), text="No templates yet. Create one below, or use "
                                          "“Save as template” on a note.",
                         bg=self.colors["card"], fg=self.colors["subtext"],
                         font=("Segoe UI", 9), wraplength=self.px(460), justify="left"
                         ).pack(pady=10, padx=6, anchor="w")
            else:
                for i, tpl in enumerate(self.templates):
                    if i:
                        self._row_divider(rows.add())
                    self._build_template_row(rows.add(), tpl, redraw)
            for chunk in rows.chunks:
                self._bind_wheel_tree(chunk, wheel)
        redraw()
        self._refresh_templates_panel = redraw

        # New-from-scratch row.
        add_row = tk.Frame(parent, bg=self.colors["card"])
        add_row.pack(fill="x", padx=12, pady=(6, 10))
        # ASCII "+": the category panel's own "+ Add" a few sections up uses
        # it, and the two characters are visibly different widths.
        new_tpl_btn = tk.Button(add_row, text="+ New template",
                  command=lambda: self._edit_template(None, redraw, new_tpl_btn),
                  bg=self.colors["accent"], fg=self._on_fill("accent"), relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2")
        new_tpl_btn.pack(fill="x", ipady=4)

    def _build_template_row(self, parent, tpl, redraw):
        name = tpl.get("name", "Untitled template")
        row = tk.Frame(parent, bg=self.colors["sidebar"])
        row.pack(fill="x", pady=4, padx=2)
        self._icon_button(row, "templates", bg_key="sidebar").pack(side="left", padx=(6, 0))
        # Kept whole, drawn cut to its room: 5,000 letters drawn whole asked
        # X for a label past its 32,767 pixels, at every visit.
        name_lbl = tk.Label(row, bg=self.colors["sidebar"],
                            fg=self.colors["text"], anchor="w")
        _fit_title(self, name_lbl, "", name, "",
                   self._cal_font(("Segoe UI", 10, "bold"))[0])
        shown = one_line(name, 200)

        def delete():
            # Answered here alone: click-outside's "Save changes?" after it
            # wrote back the template just deleted. Its own open editor is
            # covered by the delete question; another's asks first.
            pop = getattr(self, "_mini_popup", None)
            own = pop is not None and getattr(pop, "edited_template", None) is tpl
            if not own and not self._dismiss_mini_popup_asking():
                return "break"
            # The editor's save may have replaced this very template ("Replace"):
            # nothing is left for this bin to delete.
            if not any(t is tpl for t in self.templates):
                self.set_status(f"“{shown}” was replaced by the template "
                                "you saved")
                return "break"
            # Honest about the stakes: notes go to the Trash and can come
            # back for the whole retention window -- templates do not.
            if self.ask_yes_no(
                    "Delete template",
                    f"Delete the template “{shown}” for good?\n\n"
                    "Templates don't go to the Trash — this can't be undone.",
                    icon="warning", default="no"):
                if own:
                    self._dismiss_mini_popup()
                self.templates = [t for t in self.templates if t is not tpl]
                save_templates(self.templates)
                redraw()
                self._render_statistics()
            return "break"

        self._icon_button(row, "trash", delete, danger=True, bg_key="sidebar"
                          ).pack(side="right", padx=(1, 6))
        edit_btn = self._icon_button(row, "pencil", bg_key="sidebar",
                                     keys=lambda: edit())

        def edit(_e=None):
            # Another template's editor, half written, stayed open: this
            # click is spent, and must not reach the window's click-outside
            # to ask the same question twice.
            if self._edit_template(tpl, redraw, edit_btn) is False:
                return "break"

        edit_btn.bind("<Button-1>", edit)
        edit_btn.pack(side="right", padx=1)
        # After the bin and the pencil, as an attachment's name is after its
        # ✕: packed first, a 50-letter name took the row and both.
        name_lbl.pack(side="left", fill="x", expand=True, padx=6, pady=8)

    def _draw_template_table_preview(self, canvas, body_text):
        """A read-only drawing of the body's tables for the template dialog,
        in the editor's look without its machinery; every row drawn, the
        canvas scrolling past the dialog's budget. Returns the table
        blocks, empty when there is nothing to draw."""
        from noteorganizer.core import tables as core_tables
        from noteorganizer.core.themes import hairline, inset_surface
        text = body_text.get("1.0", "end-1c")
        blocks = core_tables.find_blocks(text)
        lines = text.split("\n")
        # Drawn again only when what it draws changed: every key redrew one
        # item per line of every cell, 0.16 s a key for one paste of breaks,
        # and the tables are out of the box's sight, so typing never does.
        drawn = (tuple("\n".join(lines[a:b + 1]) for a, b in blocks),
                 hairline(self.colors), inset_surface(self.colors),
                 self.colors["card"], self.colors["text"], self.px(22))
        if blocks and getattr(canvas, "_preview_drawn", None) == drawn:
            return blocks
        canvas._preview_drawn = drawn
        canvas.delete("all")
        if not blocks:
            return []
        # One font for every redraw, so a width measured once is remembered
        # (_measure_text): the preview is drawn again at every key.
        font = self._measuring_font(("Consolas", 9))
        pad_x, row_h, y = 6, self.px(22), 2
        rule = hairline(self.colors)
        max_x = self.px(100)
        for first, last in blocks:
            block = lines[first:last + 1]
            sep_at = core_tables.separator_index(block)
            sep_cols = (core_tables.parse_separator(block[sep_at])
                        if sep_at is not None else None)
            rows = [core_tables.split_row(line)
                    for i, line in enumerate(block) if i != sep_at]
            ncols = max((len(r) for r in rows), default=0)
            spans, covered = core_tables.merge_map(rows)
            widths = []
            for c in range(ncols):
                column = (sep_cols[c] if sep_cols and c < len(sep_cols)
                          else None)
                if column and column.get("hidden"):
                    widths.append(self.px(8))
                    continue
                longest = max((self._measure_text(font, seg) for r in rows
                               if c < len(r)
                               and r[c] not in (core_tables.MERGE_LEFT,
                                                core_tables.MERGE_UP)
                               for seg in core_tables.cell_display_lines(
                                   r[c])),
                              default=20)
                if column and column.get("width"):
                    longest = max(longest,
                                  font.measure("0") * column["width"])
                widths.append(min(longest + 2 * pad_x, self.px(160)))
            # A cell can hold <br> line breaks; its row grows to fit.
            row_lines = []
            for row in rows:
                n = 1
                for v in row:
                    if v not in (core_tables.MERGE_LEFT,
                                 core_tables.MERGE_UP):
                        n = max(n, len(core_tables.cell_display_lines(v)))
                row_lines.append(n)
            row_ys = [y]
            for n in row_lines:
                row_ys.append(row_ys[-1] + n * row_h)
            x0 = 2
            for r, row in enumerate(rows):
                x = x0
                for c in range(ncols):
                    w = widths[c]
                    if (r, c) in covered:
                        x += w
                        continue
                    rs, cs = spans.get((r, c), (1, 1))
                    w_span = sum(widths[c:c + cs])
                    cell_h = (row_ys[min(r + rs, len(rows))] - row_ys[r])
                    canvas.create_rectangle(
                        x, row_ys[r], x + w_span, row_ys[r] + cell_h,
                        fill=(inset_surface(self.colors) if r == 0
                              else self.colors["card"]),
                        outline=rule)
                    value = row[c] if c < len(row) else ""
                    hidden = (sep_cols and c < len(sep_cols)
                              and sep_cols[c].get("hidden"))
                    if value and not hidden:
                        segs = core_tables.cell_display_lines(value)
                        top = row_ys[r] + (cell_h - len(segs) * row_h) / 2
                        for li, seg in enumerate(segs):
                            # Halved, not cut a letter at a time: a long cell
                            # was measured whole once per letter, 2 s a key.
                            shown = self._ellipsize(
                                seg, font, max(w_span - 2 * pad_x, 1))
                            canvas.create_text(
                                x + pad_x, top + li * row_h + row_h / 2,
                                anchor="w",
                                font=("Consolas", 9,
                                      "bold" if r == 0 else "normal"),
                                fill=self.colors["text"], text=shown)
                    x += w
            y = row_ys[-1]
            max_x = max(max_x, x0 + sum(widths))
            y += 8
        shown_h = min(y, self.px(240))
        shown_w = min(max_x + 6, self.px(430))
        canvas.configure(height=shown_h, width=shown_w,
                         bg=self.colors["card"], highlightthickness=0,
                         scrollregion=(0, 0, max_x, y))
        canvas._preview_overflows = y > shown_h
        canvas._preview_overflows_x = max_x > shown_w
        return blocks

    def _edit_template(self, tpl, redraw, anchor_widget=None):
        """Open a small editor (inline window) to create or edit a template's
        name, title, body, comments and category. Returns False when it
        could not: the editor already open holds typed work and the person
        chose to keep it."""
        is_new = tpl is None
        data = normalize_template(tpl or {})

        # Another template's open editor asks first: the pencil acts before
        # click-outside, and closed it unasked, half-written.
        if not self._dismiss_mini_popup_asking():
            return False
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        # Which template it edits (None for a new one), for that row's bin.
        pop.edited_template = tpl
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        shell = tk.Frame(pop, bg=self.colors["card"], padx=12, pady=12)
        shell.pack(padx=1, pady=1)

        head = tk.Frame(shell, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text=("New template" if is_new else "Edit template"),
                 bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        # A person's close, so it asks as Escape does: it threw a half-written
        # template away without a word.
        tk.Button(head, text="✕", command=self._dismiss_mini_popup_asking, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 10, "bold"), bd=0).pack(side="right")
        # What a box's limit did is said here, under the heading: the status
        # line it was said on stands hidden behind Settings, where this editor
        # opens, and a paste was shortened without a word (_say_by_the_box).
        notice = tk.Label(shell, bg=self.colors["card"], fg=self.colors["subtext"],
                          font=("Segoe UI", 8), anchor="w", justify="left")

        def say_here(text):
            try:
                notice.configure(text=one_line(text, 300),
                                 wraplength=max(self.px(200), head.winfo_width()))
                if not self._is_placed(notice):
                    notice.pack(fill="x", pady=(0, 6), after=head)
            except tk.TclError:
                pass
        pop._say_here = say_here
        # Everything between the header and Save scrolls once the editor is
        # taller than the window: it grew with its checklist, and 25 items,
        # or one long one, put Save, Category and the Add box off the screen.
        stack = self._scrolling_rows(shell, "card", pop)
        fields = stack.group()

        def field(label, initial, height=1, limit=None):
            tk.Label(fields.add(), text=label, bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
            if height == 1:
                var = tk.StringVar(value=initial)
                e = tk.Entry(fields.add(), textvariable=var, relief="flat", font=("Segoe UI", 10),
                             bg=self.colors["sidebar"], fg=self.colors["text"],
                             insertbackground=self.colors["text"], width=40)
                e.pack(fill="x", ipady=3)
                self._add_paste_menu(e)
                self._guard_entry_astral(e)
                if limit is not None:
                    self._limit_entry(e, *limit)
                return var
            else:
                t = tk.Text(fields.add(), height=height, width=40, relief="flat",
                            font=("Segoe UI", 10), bg=self.colors["sidebar"],
                            fg=self.colors["text"], insertbackground=self.colors["text"],
                            wrap="word")
                t.insert("1.0", initial)
                t.pack(fill="x")
                self._add_paste_menu(t)
                self._swallow_format_keys(t)
                # A table copied from Excel, Word or a web page arrives
                # as pipe text instead of losing its shape to the plain
                # clipboard.
                t.bind("<<Paste>>",
                       lambda e, w=t: self._paste_table_aware(w))
                # The middle button's paste keeps the same ceiling.
                t.bind("<<PasteSelection>>", self._paste_selection_capped)
                # Tk's own Ctrl+K, Ctrl+O and Ctrl+T, which no Windows box has,
                # edited a box with no Undo for good.
                for seq in ("<Control-k>", "<Control-K>", "<Control-o>", "<Control-O>",
                            "<Control-t>", "<Control-T>"):
                    t.bind(seq, lambda _e: "break")
                return t

        # The note's own title box holds TITLE_MAX_LEN; these two took any paste.
        name_var = field("Template name", data["name"],
                         limit=(self.TITLE_MAX_LEN, "A template name"))
        title_var = field("Note title (optional)", data["title"],
                          limit=(self.TITLE_MAX_LEN, "A note title"))
        body_txt = field("Note body", data["body"], height=4)
        # Its styles and list lines ride on the text as tags, as in the
        # editor, so an edit carries them along. Kept as offsets beside the
        # text, they landed on other words after any edit before them.
        self._apply_formatting(body_txt, data.get("formatting", []))
        self._apply_paragraphs(body_txt, data.get("paragraphs", []))
        # The body's tables show AS tables here, once it holds one -- packed
        # NOW, under the body box, not at the frame's tail.
        preview_holder = tk.Frame(fields.add(), bg=self.colors["card"])
        preview_holder.pack(fill="x")
        preview_lbl = tk.Label(preview_holder, text="Table preview",
                               bg=self.colors["card"],
                               fg=self.colors["subtext"],
                               font=("Segoe UI", 8, "bold"), anchor="w")
        preview_row = tk.Frame(preview_holder, bg=self.colors["card"])
        preview_canvas = tk.Canvas(preview_row, height=10,
                                   bg=self.colors["card"],
                                   highlightthickness=0)
        preview_scroll = ttk.Scrollbar(preview_row, orient="vertical",
                                       command=preview_canvas.yview)
        preview_hscroll = ttk.Scrollbar(preview_row, orient="horizontal",
                                        command=preview_canvas.xview)
        preview_canvas.configure(yscrollcommand=preview_scroll.set,
                                 xscrollcommand=preview_hscroll.set)
        preview_canvas.grid(row=0, column=0, sticky="w")
        body_txt.tag_configure("tblhide", elide=True)

        def refresh_preview(_e=None):
            try:
                blocks = self._draw_template_table_preview(
                    preview_canvas, body_txt)
            except Exception:
                # Broad on purpose: the draw wipes the canvas FIRST, so a
                # failure escaping here left an empty preview and stale
                # hiding for the rest of the dialog's life.
                return
            # The box shows only the NON-table text, still HOLDING all of it:
            # elide hides the pipe rows the preview draws.
            body_txt.tag_remove("tblhide", "1.0", "end")
            # Blank lines glued to a hidden table hide with it, or the text
            # was full of gaps; one between two runs of text stays.
            all_lines = body_txt.get("1.0", "end-1c").split("\n")
            for first, last in blocks:
                a, z = first, last
                while a - 1 >= 0 and not all_lines[a - 1].strip():
                    a -= 1
                while z + 1 < len(all_lines) and not all_lines[z + 1].strip():
                    z += 1
                # Never over the text's own final newline: a hide range
                # clamped to "end" swallows it, and everything typed at
                # the end thereafter lands INSIDE the tag -- invisible.
                hide_end = f"{z + 1}.end+1c"
                if body_txt.compare(hide_end, ">=", "end"):
                    hide_end = "end-1c"
                body_txt.tag_add("tblhide", f"{a + 1}.0", hide_end)
            if blocks:
                # A caret in hidden text is parked at the end -- ONLY then,
                # or every keystroke threw it to the tail.
                last_line = body_txt.get("end-1c linestart", "end-1c")
                from noteorganizer.core import tables as core_tables
                if core_tables.is_table_row(last_line):
                    body_txt.insert("end", "\n")
                if "tblhide" in body_txt.tag_names("insert"):
                    body_txt.mark_set("insert", "end")
            if blocks and not self._is_placed(preview_row):
                preview_lbl.pack(fill="x", pady=(4, 0))
                preview_row.pack(anchor="w", pady=(0, 2))
            elif not blocks and self._is_placed(preview_row):
                preview_lbl.pack_forget()
                preview_row.pack_forget()
            if blocks and getattr(preview_canvas, "_preview_overflows",
                                  False):
                preview_scroll.grid(row=0, column=1, sticky="ns")
            else:
                preview_scroll.grid_forget()
            if blocks and getattr(preview_canvas, "_preview_overflows_x",
                                  False):
                preview_hscroll.grid(row=1, column=0, sticky="ew")
            else:
                preview_hscroll.grid_forget()
            # A table grown wider at the same height resizes no chunk: the
            # editor is measured again for it.
            stack.remeasure()

        def paste_and_preview(_e=None):
            # The refresh is scheduled FIRST, as the table paste returns
            # "break"; after_idle runs it once the text has landed.
            pop.after_idle(refresh_preview)
            return self._paste_table_aware(body_txt)

        # A click can land the caret INSIDE the hidden rows, where typing
        # broke the table: it goes to visible text BEFORE a character lands,
        # and deletions refuse hidden text.
        def caret_to_visible(_e=None):
            try:
                if "tblhide" in body_txt.tag_names("insert"):
                    body_txt.mark_set("insert", "end")
            except tk.TclError:
                pass

        def guard_backspace(_e=None):
            # The newline before a hidden block is outside its tag: the
            # character behind it gives the danger away.
            try:
                if ("tblhide" in body_txt.tag_names("insert - 1c")
                        or "tblhide" in body_txt.tag_names("insert")
                        or (body_txt.get("insert - 1c") == "\n"
                            and "tblhide"
                            in body_txt.tag_names("insert - 2c"))):
                    return "break"
            except tk.TclError:
                pass

        def guard_delete(_e=None):
            try:
                if ("tblhide" in body_txt.tag_names("insert")
                        or (body_txt.get("insert") == "\n"
                            and "tblhide"
                            in body_txt.tag_names("insert + 1c"))):
                    return "break"
            except tk.TclError:
                pass

        body_txt.bind("<ButtonRelease-1>",
                      lambda e: pop.after_idle(caret_to_visible), add="+")
        body_txt.bind("<KeyPress>", caret_to_visible, add="+")
        body_txt.bind("<BackSpace>", guard_backspace, add="+")
        body_txt.bind("<Delete>", guard_delete, add="+")
        body_txt.bind("<KeyRelease>",
                      lambda e: pop.after_idle(refresh_preview), add="+")
        body_txt.bind("<<Paste>>", paste_and_preview)
        pop.after_idle(refresh_preview)
        comments_txt = field("Comments (optional)", data["comments"], height=2)

        # Interactive checklist editor (same feel as in a note): type + Enter
        # adds an item with a checkbox; each row can be ticked or deleted.
        tpl_checklist = [
            {"text": it.get("text", ""), "done": bool(it.get("done"))}
            for it in data.get("checklist", []) if isinstance(it, dict)
        ]
        tk.Label(fields.add(), text="Checklist", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 8, "bold"),
                 anchor="w").pack(fill="x", pady=(6, 0))
        # Its own block, as tall as a note's checklist can be (RowStack).
        tpl_cl_rows = stack.group(bg="sidebar", pady=(0, 2), every=32)
        # Each row's tick box, by item, for the keyboard after a move.
        tpl_boxes = {}

        def move_tpl_item(it, step):
            """One place up (-1) or down (+1), as in a note's checklist; at
            either end nothing moves, and the keyboard is on the item."""
            at = next((i for i, x in enumerate(tpl_checklist) if x is it), None)
            if at is not None and 0 <= at + step < len(tpl_checklist):
                to = at + step
                tpl_checklist[at], tpl_checklist[to] = (tpl_checklist[to],
                                                        tpl_checklist[at])
                render_tpl_checklist()
            box = tpl_boxes.get(id(it))
            if box is not None:
                box.focus_set()

        def render_tpl_checklist():
            tpl_cl_rows.clear()
            tpl_boxes.clear()
            if not tpl_checklist:
                tk.Label(tpl_cl_rows.add(), text="No items yet — type below and press Enter.",
                         bg=self.colors["sidebar"], fg=self.colors["subtext"],
                         font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=6, pady=4)
                return
            for item in tpl_checklist:
                # The border is the ring of the item the keyboard is on.
                row = tk.Frame(tpl_cl_rows.add(), bg=self.colors["sidebar"],
                               highlightthickness=1,
                               highlightbackground=self.colors["sidebar"],
                               highlightcolor=self.colors["sidebar"])
                row.pack(fill="x", padx=4, pady=1)
                v = tk.IntVar(value=1 if item.get("done") else 0)

                def on_tog(it=item, var=v, lb=None):
                    it["done"] = bool(var.get())
                    render_tpl_checklist()

                # ▲ over ▼ at the left, as in a note's checklist: the top
                # half moves the item up, the bottom half down.
                self._icon_button(
                    row, "updown", bg_key="sidebar", removes_row=True,
                    takes_event=True,
                    command=lambda e, it=item: move_tpl_item(
                        it, -1 if e.y < e.widget.winfo_height() / 2 else 1)
                ).pack(side="left")
                cb = tk.Checkbutton(row, variable=v, command=on_tog,
                                    bg=self.colors["sidebar"], activebackground=self.colors["sidebar"],
                                    selectcolor=self.colors["check_well"], bd=0, highlightthickness=0)
                cb.pack(side="left")
                cb.bindtags(("TemplateChecklistBox",) + cb.bindtags())
                cb.bind("<Alt-Up>", lambda e, it=item: (move_tpl_item(it, -1),
                                                        "break")[1])
                cb.bind("<Alt-Down>", lambda e, it=item: (move_tpl_item(it, 1),
                                                          "break")[1])
                tpl_boxes[id(item)] = cb

                def do_del(it=item):
                    try:
                        tpl_checklist.remove(it)
                    except ValueError:
                        pass
                    render_tpl_checklist()

                # Settings' drawn bin, no track_theme (these rows are rebuilt),
                # packed before the text so a long item cannot squeeze it.
                self._icon_button(row, "trash", do_del, danger=True,
                                  bg_key="sidebar", removes_row=True
                                  ).pack(side="right")
                lbl = tk.Label(row, text=checklist_shown(item.get("text", "")),
                               bg=self.colors["sidebar"],
                               fg=self.colors["subtext"] if item.get("done") else self.colors["text"],
                               font=("Segoe UI", 9), anchor="w", wraplength=self.px(320),
                               justify="left")
                lbl.pack(side="left", fill="x", expand=True, padx=(2, 4))
                # Wrapped at the width it is given, as in a note's checklist,
                # and measured as it will stand.
                if lbl.winfo_reqwidth() > self.CHECKLIST_SHORT:
                    lbl.bindtags(("ChecklistText",) + lbl.bindtags())
                    self._wrap_as_its_rows(lbl, tpl_cl_rows)

        render_tpl_checklist()

        below = stack.group()
        cl_add_row = tk.Frame(below.add(), bg=self.colors["card"])
        cl_add_row.pack(fill="x", pady=(0, 6))
        cl_add_var = tk.StringVar()
        cl_entry = tk.Entry(cl_add_row, textvariable=cl_add_var, relief="flat",
                            font=("Segoe UI", 10), bg=self.colors["sidebar"],
                            fg=self.colors["text"], insertbackground=self.colors["text"])
        cl_entry.pack(side="left", fill="x", expand=True, ipady=3)
        self._add_paste_menu(cl_entry)
        self._guard_entry_astral(cl_entry)
        self._limit_entry(cl_entry, MAX_CHECKLIST_ITEM_CHARS, "A checklist item")

        def add_tpl_item():
            text = cl_add_var.get().strip()[:MAX_CHECKLIST_ITEM_CHARS]
            if not text or self._checklist_full(tpl_checklist, text):
                return
            tpl_checklist.append({"text": text, "done": False})
            cl_add_var.set("")
            render_tpl_checklist()
            cl_entry.focus_set()

        # Pressed, not held: held over a full list, a repeat answered its
        # "Checklist full" and the next asked it again (_enter_repeats).
        cl_entry.bind("<Return>", lambda e: (
            None if self._enter_repeats(e) else add_tpl_item()))
        tk.Button(cl_add_row, text="+ Add", command=add_tpl_item,
                  bg=self.colors["accent"], fg=self._on_fill("accent"), relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", padx=(6, 0), ipadx=8, ipady=2)

        tk.Label(below.add(), text="Category", bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
        cat_var = tk.StringVar(value=data["category"] if data["category"] in CATEGORY_COLORS else "General")
        cat_menu = self._build_themed_dropdown(
            below.add(), cat_var, lambda: list(CATEGORY_COLORS.keys()),
            on_change=lambda v: None,
            dot_color_fn=lambda v: CATEGORY_COLORS.get(v), width_chars=16,
            nested=True)
        cat_menu.pack(fill="x", pady=(0, 6))

        def collect():
            # An item typed and not yet added is part of the template, as of
            # a note (_take_pending_checklist_item); every save reads this.
            pending = cl_add_var.get().strip()[:MAX_CHECKLIST_ITEM_CHARS]
            return normalize_template({
                "name": name_var.get(),
                "title": title_var.get(),
                "body": body_txt.get("1.0", "end").rstrip("\n"),
                "comments": comments_txt.get("1.0", "end").rstrip("\n"),
                "category": cat_var.get(),
                "checklist": [dict(it) for it in tpl_checklist]
                             + ([{"text": pending, "done": False}] if pending else []),
                # Read back from the tags the body carries (above): a
                # template saved from the editor keeps its formatting, on
                # the words it was on.
                "formatting": self._extract_formatting(body_txt),
                "paragraphs": self._extract_paragraphs(body_txt),
            })

        def save():
            # The RAW field: normalized, an empty name is "Untitled template",
            # and the guard never fired.
            if not name_var.get().strip():
                self.show_warning("Name needed", "Give the template a name.")
                return
            # Words in the Add box past a full list would be cut by
            # normalize_template, unsaid: refused, as the name above is.
            waiting = cl_add_var.get().strip()
            if waiting and self._checklist_full(tpl_checklist, waiting):
                return
            new_tpl = collect()
            # A colliding name never overwrites (or duplicates) silently:
            # saving a NEW template under a taken name, or renaming one
            # onto a neighbour, both ask first.
            taken_name = new_tpl.get("name")
            if self._templates_full(taken_name,
                                    replacing=None if is_new else tpl):
                return
            others = [t for t in self.templates
                      if t is not tpl and t.get("name") == taken_name]
            if others:
                if not self.ask_yes_no(
                        "Template name taken",
                        f"You already have a template named “{one_line(taken_name, 200)}”.\n\n"
                        "Replace the old template with this one?\n"
                        "Choose No to give this one another name.",
                        icon="warning", default="no"):
                    return
                self.templates = [t for t in self.templates
                                  if t not in others]
            if is_new:
                self.templates.append(new_tpl)
            else:
                idx = self.templates.index(tpl) if tpl in self.templates else -1
                if idx >= 0:
                    self.templates[idx] = new_tpl
                else:
                    self.templates.append(new_tpl)
            save_templates(self.templates)
            # Saved after all: a cancelled sign-out's word that it was not
            # kept is untrue now, and the next start must not say it.
            if get_setting("template_not_kept", None, expect=str):
                save_setting("template_not_kept", None)
            self._dismiss_mini_popup()
            # The list as the page shows it NOW: rebuilt under the editor, the
            # rows handed over were gone, and a saved template said it failed.
            live = getattr(self, "_refresh_templates_panel", None) or redraw
            live()
            self._render_statistics()

        btns = tk.Frame(shell, bg=self.colors["card"])
        btns.pack(fill="x", pady=(4, 0))
        tk.Button(btns, text="Save", command=save, relief="flat", cursor="hand2",
                  bg=self.colors["accent"], fg=self._on_fill("accent"),
                  font=("Segoe UI", 9, "bold")
                  ).pack(side="left", ipadx=10, ipady=3)
        tk.Button(btns, text="Cancel", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 9)).pack(side="left", padx=(6, 0), ipadx=10, ipady=3)

        # A click elsewhere closes the editor as any dropdown -- asking first
        # when something changed.
        confirm_state = {"asking": False}
        # Dirty is measured against what the very same collector reads at
        # open time -- comparing against the raw template tripped on
        # normalization details (a trailing newline, filled defaults).
        opened_snapshot = collect()

        def confirm_dismiss():
            if confirm_state["asking"]:
                return False              # the ask itself is on screen
            # Words waiting past a full list are cut from collect(): the
            # editor still asks, and Save says why they cannot go in.
            over = (cl_add_var.get().strip()
                    and len(tpl_checklist) >= MAX_CHECKLIST_ITEMS)
            if collect() == opened_snapshot and not over:
                return True               # nothing changed: just close
            confirm_state["asking"] = True
            try:
                # Three answers, not two. Asked as Yes/No, Escape -- the
                # key for "never mind" -- answered No and threw the typed
                # work away. Cancel is first, so Escape takes it.
                choice = self.ask_yes_no_cancel(
                    "Save changes?",
                    "You changed this template. Save the changes "
                    "before closing?", icon="question", default="yes")
            finally:
                confirm_state["asking"] = False
            if choice is None:
                return False              # Cancel or Escape: keep editing
            if choice:
                save()                    # dismisses itself on success
                # A failed save (no name) keeps the dialog for fixing.
                return False
            return True                   # No: close without saving

        def save_quietly():
            """The end of a Windows session, which asks nothing: a changed
            template is kept, under its own name when that is free, else
            beside the one that has it -- never over it. It used to go with
            the session."""
            nonlocal tpl, is_new, opened_snapshot
            if collect() == opened_snapshot:
                return
            new_tpl = collect()
            taken = {t.get("name") for t in self.templates if t is not tpl}
            base = new_tpl.get("name") or "Untitled template"
            name, n = base, 2
            while name in taken:
                name, n = f"{base} ({n})", n + 1
            new_tpl["name"] = name
            if not is_new and tpl in self.templates:
                self.templates[self.templates.index(tpl)] = new_tpl
            elif len(self.templates) >= MAX_TEMPLATES:
                # Written, the next start keeps the first 1,000 and cut it
                # unsaid; refused, the next start says so.
                save_setting("template_not_kept", name)
                return
            else:
                self.templates.append(new_tpl)
            save_templates(self.templates)
            # The sign-out can still be cancelled, and the editor then stays:
            # it edits what was just written, or a second sign-out added a
            # "Name (2)" and its own Save asked about a name it held itself.
            tpl, is_new, opened_snapshot = new_tpl, False, collect()
            pop.edited_template = new_tpl

        pop._confirm_dismiss = confirm_dismiss
        pop._save_without_asking = save_quietly
        # Ctrl+S while the keyboard is in this editor (_shortcut_save_now).
        pop._save_from_keyboard = save
        if anchor_widget is not None and anchor_widget.winfo_exists():
            self._place_dropdown_popup(pop, anchor_widget)
        else:
            self._place_dropdown_popup(
                pop, None,
                anchor_xy=(self.winfo_rootx() + self.winfo_width() // 2,
                          self.winfo_rooty() + self.winfo_height() // 3))
        # Innermost first (an open Category list, an emoji picker), then
        # this editor -- asking, when something was typed.
        pop.bind("<Escape>", lambda e: self._escape_backs_out())

    def _build_trash_row(self, parent, entry, redraw, on_tick=None):
        # The border is the ring of the row whose box has the keyboard
        # (TrashTickBox); the padding inside gives back its pixel.
        row = tk.Frame(parent, bg=self.colors["card"], highlightthickness=1,
                       highlightbackground=self.colors["card"],
                       highlightcolor=self.colors["card"])
        row.pack(fill="x", pady=3)

        # A tick box, so restoring forty notes is not forty clicks; kept on
        # the app, not the row, which redraw() destroys (as Duplicates does).
        key = _trash_tick_key(entry)
        var = self._trash_sel.get(key)
        if var is None:
            var = tk.IntVar(value=0)
            self._trash_sel[key] = var
        tick = tk.Checkbutton(
            row, variable=var, command=(on_tick or (lambda: None)),
            bg=self.colors["card"], activebackground=self.colors["card"],
            selectcolor=self.colors["check_well"], bd=0, highlightthickness=0)
        tick.pack(side="left", padx=(7, 0))
        tick.bindtags(("TrashTickBox",) + tick.bindtags())

        # Built now, packed LAST: pack gives the rest to what comes last, and
        # packed first, a long title squeezed Restore and Delete to slivers.
        left = tk.Frame(row, bg=self.colors["card"])
        # The entry is as the file held it; what the row shows is read from
        # a shaped copy, or a title of 7 kept the whole panel from opening.
        shown = normalize_note(dict(entry))
        title = shown["title"].strip() or "(untitled)"
        # A series is marked, as every list marks one: its Delete destroys
        # every day, and cannot be undone.
        repeats = is_recurring(shown)
        tk.Label(left, text=("🔁 " if repeats else "") + _truncate(title, 42),
                 bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        # Show when it was deleted and how long remains.
        meta = entry.get("deleted_at", "")
        if not isinstance(meta, str):
            # Only a hand-edited trash.json gets here (the backup import
            # keeps text only): the date is unknown, and slicing a number
            # below raised and kept the whole panel from opening.
            meta = ""
        remaining = self._days_left_in_trash(meta)
        sub = f"deleted {show_date(meta[:10])}" if meta else "deleted"
        if remaining is not None:
            sub += f" · {remaining} day(s) left"
        if repeats:
            sub += f" · repeats {describe_recurrence(shown).lower()}"
        sub_lbl = tk.Label(left, text=sub, bg=self.colors["card"],
                           fg=self.colors["subtext"], font=("Segoe UI", 8),
                           anchor="w", justify="left")
        sub_lbl.pack(fill="x")
        # A series' line is long, and was cut mid-word: wrapped at the label's
        # OWN width, the one number that cannot disagree with the layout.
        self._wrap_to_own_width(sub_lbl)

        # Two "Notes" deleted the same day are told apart by a preview, as in
        # Duplicates: a Trash entry is a note.
        self._attach_dup_preview(left, entry)

        # The toast's Undo can take this entry out under the row: Restore made
        # a second copy, Delete destroyed the restored note's file.
        def still_in_trash():
            return any(e is entry for e in self.trash)

        # The rows it stands among: its block of the list, across chunks the
        # redraw makes again (RowStack), not the chunk it was made in.
        block = self._block_of(row)

        def restore():
            keyed = self._holds_keyboard(restore_btn)
            place = self._trash_row_place(row, block)
            if still_in_trash():
                self._restore_from_trash(entry)
            redraw()
            if keyed:
                self._keyboard_to_trash_row(block, place, "restore")

        def delete_forever():
            keyed = self._holds_keyboard(delete_btn)
            place = self._trash_row_place(row, block)
            if not still_in_trash():
                redraw()
                return
            if self.ask_yes_no(
                "Delete permanently",
                f"Permanently delete “{one_line(title, 200)}”"
                f"{self._attached_files_words([entry])}? This can't be undone."
                + self._series_warning([entry]),
                icon="warning", default="no"
            ) and still_in_trash():
                _delete_attachment_files(
                    [entry], spare=attachment_names_in(
                        self.notes + [e for e in self.trash if e is not entry]))
                self.trash = [e for e in self.trash if e is not entry]
                save_trash(self.trash)
                # As the bulk delete's: Statistics' "In trash" kept the old
                # figure.
                self._render_statistics()
            redraw()
            if keyed:
                self._keyboard_to_trash_row(block, place, "delete")

        # Restore made first, Delete packed first: Delete stays at the edge
        # and Tab still reads the row left to right.
        restore_btn = tk.Button(row, text="Restore", command=restore, relief="flat",
                                cursor="hand2", bg=self.colors["accent"],
                                fg=self._on_fill("accent"),
                                font=("Segoe UI", 8, "bold"))
        delete_btn = tk.Button(row, text="Delete", command=delete_forever,
                               relief="flat", cursor="hand2",
                               bg=self.colors["danger"], fg=self._on_fill("danger"),
                               font=("Segoe UI", 8, "bold"))
        delete_btn.pack(side="right", padx=(2, 7), ipadx=4, ipady=1)
        restore_btn.pack(side="right", padx=2, ipadx=4, ipady=1)
        row._trash_buttons = {"restore": restore_btn, "delete": delete_btn}
        # A double-click's second press lands on the row that slid up into
        # this one's place when the first restore redrew the list -- and
        # restored that note too. The checklist bin's hazard, and its guard.
        restore_btn.bind(
            "<ButtonPress-1>",
            lambda e: "break" if self._second_press_of_double_click(e) else None,
            add="+")
        # The text last, on what the buttons left: a shortened title, never
        # an unclickable Restore (field report).
        left.pack(side="left", fill="x", expand=True, padx=10, pady=7)

    @staticmethod
    def _trash_row_place(row, block):
        """Where *row* stands among the Trash's rows in *block*."""
        try:
            rows = [w for w in block.winfo_children()
                    if getattr(w, "_trash_buttons", None)]
            return rows.index(row)
        except (tk.TclError, ValueError):
            return 0

    def _keyboard_to_trash_row(self, block, place, which):
        """After a row's Restore or Delete pressed from the keyboard, the
        row drawn in its place takes the keyboard, on the same button --
        or the last row, or what follows the list once it is empty."""
        try:
            rows = [w for w in block.winfo_children()
                    if getattr(w, "_trash_buttons", None)]
            after = getattr(getattr(block, "stack", None), "canvas", block)
            target = (rows[min(place, len(rows) - 1)]._trash_buttons[which]
                      if rows else after.tk_focusNext())
        except (tk.TclError, KeyError, AttributeError):
            return
        if target is not None:
            target.focus_set()
            self.update_idletasks()     # the redrawn rows, laid out
            self._bring_into_sight(target)

    def _retention_loss_warning(self, doomed, days, current):
        """What shortening the window to `days` is about to cost, in words:
        `doomed` is the purge's own answer (trash_entries_past_window), and
        the attached files are named, as the purge deletes them too.
        """
        count = len(doomed)
        noun = "note" if count == 1 else "notes"
        attached = self._attached_files_words(doomed)
        # `current` is None while the window before could not be read:
        # there is no "instead of" to name, and nothing was going before.
        instead = "" if current is None else f" instead of {current}"
        return (
            f"The trash holds {count} {noun} older than {days} days.\n\n"
            f"Keeping deleted notes for {days} days{instead} "
            f"removes {'it' if count == 1 else 'them'} for good the next time "
            f"the app starts{attached}. This can't be undone."
            + self._series_warning(doomed)
        )

    @staticmethod
    def _attached_files_words(entries):
        """", along with N attached files" for Trash entries about to go
        for good, or "" when they carry none: the files leave the disk too."""
        files = sum(len(attachments_of(entry)) for entry in entries)
        if not files:
            return ""
        return f", along with {files} attached {'file' if files == 1 else 'files'}"

    @staticmethod
    def _trash_window_line():
        """The trash panel's subtitle: the window, or -- while it is not
        known -- that nothing leaves the Trash until one is chosen."""
        days = trash_retention_days()
        if days is None:
            return ("The length chosen before couldn't be read, so nothing "
                    "is removed automatically until you choose one below.")
        return f"Kept for {days} days, then removed automatically."

    def _build_settings_trash_panel(self, parent):
        self._trash_subtitle_lbl = self._settings_subtitle(
            parent, self._trash_window_line())

        card = self._settings_card(parent)
        row = self._card_row(
            card, "Keep deleted notes for",
            "How long the trash holds a note before removing it for good. "
            "A change applies from the next startup's cleanup.",
            first=True)

        def shown(days):
            return "Choose…" if days is None else f"{days} days"

        self.trash_retention_var = tk.StringVar(
            value=shown(trash_retention_days()))

        def set_retention(value):
            try:
                days = int(value.split()[0])
            except (ValueError, IndexError):
                return
            current = trash_retention_days()
            # Only a SHORTER window with something old enough to lose asks: a
            # needless question teaches dismissing them. One not known is
            # longer than any.
            if current is None or days < current:
                doomed = trash_entries_past_window(self.trash, days)
                if doomed and not self.ask_yes_no(
                        "Keep deleted notes for less time",
                        self._retention_loss_warning(doomed, days, current),
                        icon="warning", default="no"):
                    # The dropdown already shows the new label: backing out
                    # puts the old one back.
                    try:
                        self.trash_retention_var.set(shown(current))
                    except tk.TclError:
                        pass
                    return
            choose_trash_window(days)
            # The subtitle and every row's "days left" quote the window: the
            # rows alone are redrawn, not the panel under the dropdown.
            try:
                self._trash_subtitle_lbl.config(text=self._trash_window_line())
            except (tk.TclError, AttributeError):
                pass
            redraw()

        self._build_themed_dropdown(
            row, self.trash_retention_var,
            ["7 days", "14 days", "30 days", "60 days", "90 days"],
            set_retention, width_chars=10
        ).pack(side="right")
        # Tall enough to find one note among several (240 showed three rows);
        # Expand, a two-state toggle, takes it to 680 (_add_resize_handle).
        wrap = tk.Frame(parent, bg=self.colors["card"], height=self.px(340))
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas
        # Each page goes in under the last, so the rows grow past what one
        # frame can scroll through (RowStack).
        rows = self._row_stack(canvas, scrolled=sb.set).group(every=16)

        # Paged, newest first: 600 rows at once took over 1.5 s. 25 a page,
        # as 95% of the cost is Tk laying rows out (50: 585 ms, 25: 405 ms).
        PAGE_SIZE = self.TRASH_PAGE_SIZE
        shown_count = {"n": PAGE_SIZE}
        # Rebuilt each time the panel is opened, so ticks do not survive
        # leaving Settings and coming back -- which would be a selection
        # nobody can see.
        self._trash_sel = {}

        def ticked_entries():
            """The trashed notes currently ticked, in the trash's own order.

            Read from self.trash rather than from the tick dict, so an entry
            that has since been restored or destroyed cannot be acted on
            twice: the ticks outlive individual rows on purpose.
            """
            return [e for e in self.trash
                    if self._trash_sel.get(_trash_tick_key(e))
                    and self._trash_sel[_trash_tick_key(e)].get()]

        def refresh_restore_btn():
            """The buttons that act on the ticks, and Select all's word."""
            picked = ticked_entries()
            try:
                if picked:
                    restore_btn.configure(
                        text="↩ Restore %d selected" % len(picked),
                        state="normal")
                    delete_btn.configure(
                        text="Delete %d selected permanently" % len(picked))
                    for button in (restore_btn, delete_btn):
                        if not self._is_placed(button):
                            button.pack(fill="x", padx=12, pady=(6, 0),
                                        ipady=4, before=empty_holder)
                else:
                    for button in (restore_btn, delete_btn):
                        if self._is_placed(button):
                            button.pack_forget()
                # It says what a press will do, as the note list's does.
                if self.trash:
                    select_btn.configure(
                        text="Unselect all" if len(picked) == len(self.trash)
                        else "Select all")
                    if not self._is_placed(select_btn):
                        select_btn.pack(anchor="e", padx=12, pady=(0, 4),
                                        ipadx=4, before=wrap)
                elif self._is_placed(select_btn):
                    select_btn.pack_forget()
            except tk.TclError:
                pass

        def toggle_all():
            # Every entry in the Trash, drawn or not: paging is only there
            # to open the panel fast, and hides nothing the way a filter
            # does. The buttons name the count (the owner's call, 2026-10-26).
            everything = len(ticked_entries()) == len(self.trash)
            for entry in self.trash:
                key = _trash_tick_key(entry)
                var = self._trash_sel.get(key)
                if var is None:
                    var = tk.IntVar(value=0)
                    self._trash_sel[key] = var
                var.set(0 if everything else 1)
            refresh_restore_btn()

        def destroy(named):
            """These entries gone for good, and their files -- but not a file
            a note or a kept entry still uses. What the question named is
            what goes: an entry a toast's Undo took back meanwhile stays."""
            named_ids = {id(e) for e in named}
            gone = [e for e in self.trash if id(e) in named_ids]
            kept = [e for e in self.trash if id(e) not in named_ids]
            _delete_attachment_files(
                gone, spare=attachment_names_in(list(self.notes) + kept))
            self.trash = kept
            save_trash(self.trash)
            # Statistics' "In trash" is what is there now: it kept the old
            # figure until the list next changed.
            self._render_statistics()

        def delete_selected():
            named = ticked_entries()
            if not named:
                return
            count = len(named)
            if self.ask_yes_no(
                "Delete permanently",
                f"Permanently delete {count} selected "
                f"{'note' if count == 1 else 'notes'}"
                f"{self._attached_files_words(named)}? This can't be undone."
                + self._series_warning(named),
                icon="warning", default="no"
            ):
                destroy(named)
                self.set_status("Deleted %d note%s permanently"
                                % (count, "" if count == 1 else "s"))
            redraw()

        def restore_selected():
            picked = ticked_entries()
            if not picked:
                return
            # No question: restoring is undone by the Delete beside it. One
            # batch -- note by note, each wrote both files and rebuilt the list.
            if self._restore_trash_entries(picked) is None:
                return  # could not be kept, and said so; still ticked
            for entry in picked:
                self._trash_sel.pop(_trash_tick_key(entry), None)
            self.set_status("Restored %d note%s"
                            % (len(picked), "" if len(picked) == 1 else "s"))
            shown_count["n"] = max(PAGE_SIZE, shown_count["n"])
            redraw()

        # Each redraw gives the wheel to what it builds, its chunks included,
        # which die with their rows: a fresh handler on a frame outliving the
        # redraws left a Tcl command behind for good at every one of them.
        wheel = lambda e: self._panel_or_page_wheel(canvas, e)  # noqa: E731

        def wheel_on_rows():
            for chunk in rows.chunks:
                self._bind_wheel_tree(chunk, wheel)

        def ordered_trash():
            # str(): a hand-edited trash.json can hold a number or a list
            # beside the dates, and sorting them together raised.
            return sorted(self.trash, key=lambda e: str(e.get("deleted_at", "")),
                          reverse=True)

        drawn = {"ids": []}     # the entries on screen, in their order

        def draw_rows(ordered, first):
            """The rows from *first* up to the page's end, and the button
            for the rest."""
            drawn["ids"] = drawn["ids"][:first] + [
                id(e) for e in ordered[first:shown_count["n"]]]
            for entry in ordered[first:shown_count["n"]]:
                self._build_trash_row(rows.add(), entry, redraw,
                                      on_tick=refresh_restore_btn)
            remaining = len(ordered) - min(len(ordered), shown_count["n"])
            if remaining > 0:
                more = tk.Button(rows.add(), text=f"Show {min(remaining, PAGE_SIZE)} more "
                                            f"({remaining} not shown)",
                                 relief="flat", cursor="hand2",
                                 bg=self.colors["sidebar"], fg=self.colors["text"],
                                 font=("Segoe UI", 8))
                more.configure(command=lambda: show_more(more))
                more.pack(fill="x", pady=(6, 2), ipady=4)

        def show_more(button):
            # The next page goes in under the rows already drawn: drawing
            # every row again flickered, and grew with every page.
            first = shown_count["n"]
            shown_count["n"] += PAGE_SIZE
            ordered = ordered_trash()
            if [id(e) for e in ordered[:first]] != drawn["ids"]:
                # The Trash changed under the rows on screen -- a note
                # deleted from the sidebar while this is open: all drawn
                # again, or one row would show twice and the new one never.
                redraw()
                return
            button.destroy()
            before = set(rows.chunks) | set(rows.rows())
            draw_rows(ordered, first)
            for chunk in rows.chunks:
                if chunk not in before:
                    chunk.bind("<MouseWheel>", wheel)
                for child in chunk.winfo_children():
                    if child not in before:
                        self._bind_wheel_tree(child, wheel)
            refresh_restore_btn()

        def redraw():
            rows.clear()
            if not self.trash:
                tk.Label(rows.add(), text="Trash is empty.", bg=self.colors["card"],
                         fg=self.colors["subtext"], font=("Segoe UI", 10)).pack(pady=20)
                wheel_on_rows()
                # Emptied with notes ticked, "Restore 3 selected" stayed up
                # over an empty Trash, and did nothing.
                refresh_restore_btn()
                return
            draw_rows(ordered_trash(), 0)
            wheel_on_rows()
            refresh_restore_btn()

        def empty_trash():
            if not self.trash:
                return
            # The entries the question counts are the entries deleted: a
            # note that reaches the Trash while it waits was never asked
            # about, and goes nowhere but the Trash.
            named = list(self.trash)
            if self.ask_yes_no(
                "Empty trash",
                f"Permanently delete all {len(named)} "
                f"{'note' if len(named) == 1 else 'notes'} in the trash"
                f"{self._attached_files_words(named)}? "
                "This can't be undone." + self._series_warning(named),
                icon="warning", default="no"
            ):
                destroy(named)
                shown_count["n"] = PAGE_SIZE
                redraw()

        # Built first, for `before=empty_holder`; shown only while something is
        # ticked. Quieter than Empty trash on purpose: here the sweeping action
        # IS the irreversible one, and wears `danger`.
        restore_btn = tk.Button(
            parent, text="↩ Restore selected", command=restore_selected,
            relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
            bg=self.colors["accent"], fg=self._on_fill("accent"))
        # A double-click's second press landed on Empty trash, which slid up
        # into its place.
        restore_btn.bind(
            "<ButtonPress-1>",
            lambda e: "break" if self._second_press_of_double_click(e) else None,
            add="+")
        # Cannot be undone, so it is outlined in `danger` as Empty trash is:
        # filled, under thirty ticks, it was the heaviest thing on the page.
        # With Select all, it keeps a few and deletes the rest.
        delete_btn = self._settings_big_button(
            parent, "Delete selected permanently", delete_selected, kind="danger")
        # Above the rows, shown while the Trash holds anything -- and first
        # in Tab's order too, which follows the stacking order, not the page.
        select_btn = tk.Button(
            parent, text="Select all", command=toggle_all, relief="flat",
            cursor="hand2", font=("Segoe UI", 8), bd=0,
            bg=self.colors["card"], fg=self.colors["text"])
        select_btn.lower(wrap)
        empty_holder = self._settings_big_button(
            parent, "Empty trash", empty_trash, kind="danger")
        empty_holder.pack(fill="x", padx=12, pady=(4, 10), ipady=5)
        # ...and it answers that echo too: the guard is on the press it lands on.
        empty_holder.bind(
            "<ButtonPress-1>",
            lambda e: "break" if self._second_press_of_double_click(e) else None,
            add="+")
        # A change from outside -- the toast's Undo -- redraws the rows while
        # the panel shows (_refresh_open_trash_panel), or they offered entries gone.
        self._trash_panel_redraw = redraw
        redraw()

    def _build_settings_duplicates_panel(self, parent):
        self._settings_subtitle(
            parent,
            "Notes with the " + SAME_AS + " (ignoring "
            "case, spacing, a “(copy)” after the title, the text's styling, "
            "date, color and pin). Tick the copies you want to "
            "remove — the rest are kept.")
        groups = find_duplicate_groups(self.notes)
        if not groups:
            tk.Label(parent, text="No duplicates found — every note is unique. 🎉",
                     font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["subtext"],
                     wraplength=self.px(520), justify="left").pack(padx=12, pady=(0, 12), anchor="w")
            return

        total_dupes = sum(len(g) - 1 for g in groups)
        tk.Label(parent, text=f"Found {len(groups)} group(s), up to {total_dupes} note(s) "
                              "could be removed.",
                 font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["subtext"],
                 wraplength=self.px(520), justify="left").pack(padx=12, pady=(0, 2), anchor="w")
        tk.Label(parent, text="Tick the copies you want to remove. Keep as many as "
                              "you like — anything left unticked stays. Attachments "
                              "from removed copies are merged into a kept one.",
                 font=("Segoe UI", 8, "italic"), bg=self.colors["card"],
                 fg=self.colors["accent_text"], wraplength=self.px(520), justify="left"
                 ).pack(padx=12, pady=(0, 8), anchor="w")

        wrap = tk.Frame(parent, bg=self.colors["card"], height=self.px(260))
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 120, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas
        # Each group is a block of its own, its copies in chunks: pages grow
        # past what one frame can scroll through, and so can one group.
        stack = self._row_stack(canvas, scrolled=sb.set)

        del_vars = []  # (var, note, group) across all groups
        all_group_vars = []  # list of per-group var lists, for the "clean up everything" button
        # A tick for every copy in every group, drawn or not: the groups are
        # drawn a page at a time, and "Clean up ALL" still has to reach the
        # copies on pages nobody has opened yet.
        for group in groups:
            group_vars = [tk.IntVar(value=0) for _note in group]
            all_group_vars.append(group_vars)
            del_vars.extend((var, note, group) for var, note in zip(group_vars, group))
        wheel = lambda e: self._panel_or_page_wheel(canvas, e)  # noqa: E731
        canvas.bind("<MouseWheel>", wheel)      # the gaps between the groups

        def draw_group(group, group_vars):
            box = stack.group(bg="sidebar", padx=2, pady=(5, 5), every=32)
            title = (group[0].get("title") or "").strip() or "(untitled)"
            tk.Label(box.add(), text=f"“{title[:36]}” — {len(group)} copies",
                     font=("Segoe UI", 10, "bold"), bg=self.colors["sidebar"],
                     fg=self.colors["text"], anchor="w").pack(fill="x", padx=10, pady=(8, 2))

            hints = []
            # By the names shown: copies that each hold files, but not the
            # same ones, got no word that a merge was coming.
            if len({tuple(sorted(str(a.get("filename") or "")
                                 for a in (n.get("attachments") or [])))
                    for n in group}) > 1:
                hints.append("attachments")
            if hints:
                tk.Label(box.add(), text=f"↳ differing {' & '.join(hints)} will be merged "
                                   f"into a kept copy, up to the {MAX_ATTACHMENTS} a "
                                   "note holds; the rest stay with their copy in "
                                   "the Trash",
                         font=("Segoe UI", 7, "italic"), bg=self.colors["sidebar"],
                         fg=self.colors["accent_text"], anchor="w",
                         wraplength=self.px(460),
                         justify="left"
                         ).pack(fill="x", padx=14, pady=(0, 2))

            for note, var in zip(group, group_vars):
                created = note.get("created", "")
                updated = note.get("updated", "")
                meta = f"created {show_date(created[:10])}" if created else ""
                if updated and updated != created:
                    meta += f" · updated {show_date(updated[:10])}"
                cb = tk.Checkbutton(
                    box.add(), text=f"Delete this copy   ({meta})" if meta else "Delete this copy",
                    variable=var, font=("Segoe UI", 8), anchor="w")
                self._drawn_tick_box(cb, "sidebar", "text", track=False)
                cb.pack(fill="x", padx=20)
                self._attach_dup_preview(cb, note)

            # Shortcut: tick every copy except the first (old "keep one" behavior).
            def check_all_but_first(gv=group_vars):
                for i, v in enumerate(gv):
                    v.set(0 if i == 0 else 1)

            def clear_group(gv=group_vars):
                for v in gv:
                    v.set(0)

            btn_row = tk.Frame(box.add(), bg=self.colors["sidebar"])
            btn_row.pack(fill="x", padx=10, pady=(2, 8))
            tk.Button(btn_row, text="Tick all but first", command=check_all_but_first,
                      bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                      font=("Segoe UI", 8), cursor="hand2"
                      ).pack(side="left", ipadx=6, ipady=2)
            tk.Button(btn_row, text="Clear", command=clear_group,
                      bg=self.colors["card"], fg=self.colors["subtext"], relief="flat",
                      font=("Segoe UI", 8), cursor="hand2"
                      ).pack(side="left", padx=(6, 0), ipadx=6, ipady=2)
            for chunk in box.chunks:
                self._bind_wheel_tree(chunk, wheel)

        # A page of groups at a time (all at once, 900 ms at 5,000 notes);
        # "Show more" draws the next from the groups already found.
        DUP_PAGE_SIZE = 20
        drawn = {"n": 0, "more": None}

        def draw_next_page():
            if drawn["more"] is not None:
                stack.drop(drawn["more"])
                drawn["more"] = None
            start = drawn["n"]
            drawn["n"] = min(len(groups), start + DUP_PAGE_SIZE)
            for gi in range(start, drawn["n"]):
                draw_group(groups[gi], all_group_vars[gi])
            remaining = len(groups) - drawn["n"]
            if remaining > 0:
                drawn["more"] = stack.group()
                more = tk.Button(
                    drawn["more"].add(),
                    text=f"Show {min(remaining, DUP_PAGE_SIZE)} more groups "
                         f"({remaining} not shown)",
                    command=draw_next_page, relief="flat", cursor="hand2",
                    bg=self.colors["sidebar"], fg=self.colors["text"],
                    font=("Segoe UI", 8))
                more.pack(fill="x", pady=(6, 2), ipady=4)
                for chunk in drawn["more"].chunks:
                    self._bind_wheel_tree(chunk, wheel)

        draw_next_page()

        def do_cleanup():
            self._cleanup_selected_duplicates(
                del_vars,
                refresh=lambda: self._reopen_dup_panel(), announce=True)

        def clean_up_everything():
            # Same "keep first, remove the rest" shortcut as each group's own
            # button, just applied to every group in one click instead of
            # working through them one at a time.
            for gv in all_group_vars:
                for i, v in enumerate(gv):
                    v.set(0 if i == 0 else 1)
            do_cleanup()

        # The panel's main action first; the sweeping one, when there is
        # more than one group, below it.
        sweeping = len(groups) > 1
        tk.Button(parent, text="🧹  Move ticked duplicates to trash", command=do_cleanup,
                  bg=self.colors["accent"], fg=self._on_fill("accent"), relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2"
                  ).pack(fill="x", padx=12, pady=(4, 4 if sweeping else 10), ipady=6)

        if sweeping:
            # Painted as the bigger action it is (finding C-6), outlined in
            # the warning's colour -- the red FILL is kept for what cannot be
            # undone. Plain colours: _reopen_dup_panel rebuilds it.
            tk.Button(parent, text=f"🧹✨  Clean up ALL {len(groups)} groups (keep first in each)",
                      command=clean_up_everything, relief="solid", bd=1,
                      font=("Segoe UI", 10, "bold"), cursor="hand2",
                      bg=self.colors["card"], fg=self.colors["danger_text"],
                      highlightbackground=self.colors["danger_text"],
                      activebackground=self.colors["card"],
                      activeforeground=self.colors["danger_text"]
                      ).pack(fill="x", padx=12, pady=(4, 10), ipady=6)

    def _reopen_dup_panel(self):
        """Rebuild the duplicates panel in place after a cleanup -- the way
        the nav builds it. Calling the builder directly skipped the section's
        heading and its resize handle: after a cleanup the section lost its
        title and its Expand toggle until it was chosen again."""
        if getattr(self, "settings_duplicates_panel", None) is None:
            return
        self.toggle_settings_panel("duplicates")

    def _build_theme_picker(self, parent):
        """The theme swatches, dark and light together, four across: each a
        tile previewing the theme in its own colours, its name beneath, a
        tick on the selected one -- the other mode one click away.
        """
        for w in parent.winfo_children():
            w.destroy()

        # Both groups, as in the reference. Showing only the current mode's
        # set meant picking a light theme took two steps -- flip the mode,
        # then choose -- when one click will do.
        names = list(DARK_THEMES) + list(LIGHT_THEMES)

        # How many fit depends on the column width; the reference shows four
        # and that is what a 640px column takes, but it re-wraps rather than
        # letting the last one hang off the edge.
        CARD_W = self.px(132)
        per_group = max(len(DARK_THEMES), len(LIGHT_THEMES))
        avail = parent.winfo_width()
        if avail <= 1:
            avail = self.SETTINGS_CONTENT_MAX
        fit = max(1, min(per_group, avail // CARD_W))
        rows = -(-per_group // fit)
        per_row = -(-per_group // rows)
        self._theme_picker_cols = per_row

        grid = None
        group = None
        for i, name in enumerate(names):
            this_group = "DARK" if name in DARK_THEMES else "LIGHT"
            if this_group != group:
                group = this_group
                tk.Label(parent, text=group, bg=self.colors["bg"],
                         fg=self.colors["subtext"], font=("Segoe UI", 9, "bold"),
                         anchor="w").pack(fill="x", pady=(0 if grid is None else 18, 10))
                grid = tk.Frame(parent, bg=self.colors["bg"])
                grid.pack(fill="x")
                for col in range(per_row):
                    grid.grid_columnconfigure(col, weight=1, uniform="themecol")
                base = i
            pal = THEMES[name]
            active = (name == self.theme_name)
            edge_col = self.colors["accent"] if active else self._border_color()

            edge = tk.Frame(grid, bg=edge_col, cursor="hand2")
            j = i - base
            edge.grid(row=j // per_row, column=j % per_row, sticky="nsew",
                      padx=(0 if j % per_row == 0 else 10, 0),
                      pady=(0 if j < per_row else 10, 0))
            cell = tk.Frame(edge, bg=self._surface(), cursor="hand2")
            cell.pack(fill="both", expand=True, padx=2, pady=2)

            W, H = 116, 46                      # drawn at 100%, then scaled
            sw = tk.Canvas(cell, width=self.px(W), height=self.px(H),
                           highlightthickness=0, bd=0,
                           bg=self._surface(), cursor="hand2")
            sw.pack(padx=8, pady=(8, 6))
            # the theme's own page, its sidebar strip, and three text lines
            sw.create_rectangle(0, 0, W, H, fill=pal["bg"], outline=pal["bg"])
            sw.create_rectangle(0, 0, W * 0.28, H, fill=pal["sidebar"],
                                outline=pal["sidebar"])
            x0 = W * 0.28 + 7
            for idx, (frac, colour) in enumerate((
                    (0.60, pal["accent"]),
                    (0.85, pal["text"]),
                    (0.40, pal["subtext"]))):
                y = 10 + idx * 9
                sw.create_rectangle(x0, y, x0 + (W - x0 - 8) * frac, y + 4,
                                    fill=colour, outline=colour)
            self._scale_drawing(sw)

            lbl = tk.Label(cell, text=THEME_LABELS.get(name, name),
                           bg=self._surface(), cursor="hand2",
                           fg=(self.colors["accent_text"] if active
                               else self.colors["subtext"]),
                           font=("Segoe UI", 8, "bold"))
            lbl.pack(pady=(0, 8))

            if active:
                badge = tk.Canvas(cell, width=self.px(16), height=self.px(16),
                                  highlightthickness=0, bd=0, bg=self._surface())
                badge.place(relx=1.0, rely=0.0, x=-4, y=4, anchor="ne")
                badge.create_oval(0, 0, 15, 15, fill=self.colors["accent"],
                                  outline=self.colors["accent"])
                badge.create_line(4, 8, 6.5, 10.5, 11.5, 5,
                                  fill=self._on_fill("accent"), width=1.8)
                self._scale_drawing(badge)

            for w in (edge, cell, sw, lbl):
                w.bind("<Button-1>", lambda e, n=name: self.set_theme(n))
            # From the keyboard: the tile's edge is its ring, in the
            # keyboard's colour while the keyboard is on it.
            edge._theme_name = name
            self._pressable(edge, lambda n=name: self._pick_theme_by_key(n))
            edge.bind("<FocusIn>", lambda e, w=edge: w.configure(bg=self._focus_ring()))
            edge.bind("<FocusOut>", lambda e, w=edge, c=edge_col: w.configure(bg=c))

        # A Canvas keeps the wheel for itself: passed on to the page, as in
        # every other Settings panel.
        def _theme_picker_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"

        # Re-wrap when the column's width changes. Only an actual change in
        # the number of columns rebuilds, so ordinary Configure noise -- which
        # fires for height changes too -- doesn't churn the cards.
        def _rewrap(event):
            fits = max(1, min(per_group, max(event.width, 1) // CARD_W))
            balanced = -(-per_group // (-(-per_group // fits)))
            if balanced != getattr(self, "_theme_picker_cols", None):
                self._build_theme_picker(parent)

        # The column's own handlers are bound once (at every theme switch they
        # left Tcl commands behind); what each rebuild makes gets them afresh.
        if not getattr(parent, "_picker_bound", False):
            parent._picker_bound = True
            parent.bind("<MouseWheel>", _theme_picker_wheel)
            parent.bind("<Configure>", _rewrap)
        for child in parent.winfo_children():
            self._bind_wheel_tree(child, _theme_picker_wheel)

        self._refresh_theme_picker = lambda: self._build_theme_picker(parent)

    def show_settings_page(self):
        """Show the Settings page in place of the Notes/Calendar notebook.
        Settings lives outside the tab strip on purpose — see the comment
        where self.settings_page is created."""
        # A popup anchored to the page being swapped out would keep
        # floating over the new one -- the Settings dropdown was still on
        # screen back in the editor. Asking first if it holds typed work.
        if not self._dismiss_mini_popup_asking():
            return
        self._catch_up_deferred_refresh()
        # Read before anything below moves it (the find bar, a cell's editor),
        # so the keyboard comes back to the note's body.
        held = self._keyboard_inside(self.notebook)
        if held is not None and any(
                str(held).startswith(str(part) + ".")
                for part in (self.body_text, getattr(self, "_find_bar", None))
                if part is not None):
            held = self.body_text
        # The find bar belongs to the note being left (her re-test, 600).
        self._hide_find()
        self.notebook.pack_forget()
        # Stated, not inferred: winfo_ismapped() lags pack_forget() until Tk is
        # idle, and _calendar_is_showing() decides on it. Set only by the two
        # methods that swap the page and the notebook.
        self._settings_open = True
        self.settings_page.pack(fill="both", expand=True)
        # The section the page was left on is rebuilt on arrival, which is a
        # visit: Recently deleted lacked the notes deleted since (field report).
        showing = getattr(self, "_settings_selected_section", None)
        if showing:
            self.toggle_settings_panel(showing)
        self._render_statistics()
        # A click on Settings takes no keyboard, which stayed in the hidden
        # note: Tab typed tabs into it, Backspace deleted a letter, and both
        # were saved. It comes onto the page, and goes back on the way out.
        self._keyboard_before_settings = held
        if held is not None:
            self._keyboard_to(self._toast_landing())

    def hide_settings_page(self):
        """Return from Settings to the Notes/Calendar notebook. Returns False
        when the person stays: the template editor was open with typed work
        and they chose to keep it. The arrow beside "Back to Notes" acts on
        its own press, before the window's click-outside ever runs, so this
        is where that question has to be asked."""
        if not self._dismiss_mini_popup_asking():
            return False
        self.settings_page.pack_forget()
        self.notebook.pack(fill="both", expand=True)
        self._settings_open = False
        # The one way back to the calendar that fires no tab change, so the
        # deferred rebuild catches up here -- synchronously, as the flag above
        # answers at once (after_idle still read "not showing").
        self._catch_up_deferred_refresh()
        before = getattr(self, "_keyboard_before_settings", None)
        self._keyboard_before_settings = None
        if self._keyboard_inside(self.settings_page) is not None:
            try:
                if before is None or not before.winfo_exists():
                    before = self._toast_landing()
            except tk.TclError:
                before = self._toast_landing()
            self._keyboard_to(before)
        return True

    # ---------- Settings tab: one row per section, the navigation's one source
    # (key, label, builder, cheap to build up front). The keys are an API the
    # qa suite selects by ("name" is labelled General); a label may change.
    SETTINGS_SECTIONS = (
        ("name",       "General",          "_build_settings_name_panel",       True),
        ("appearance", "Appearance",       "_build_settings_appearance_panel", True),
        ("categories", "Categories",       "_build_settings_categories_panel", False),
        ("templates",  "Templates",        "_build_settings_templates_panel",  False),
        ("backup",     "Backup",           "_build_settings_backup_panel",     True),
        ("trash",      "Recently deleted", "_build_settings_trash_panel",      False),
        ("duplicates", "Duplicates",       "_build_settings_duplicates_panel", False),
        ("statistics", "Statistics",       "_build_settings_statistics_panel", True),
        ("shortcuts",  "Keyboard shortcuts", "_build_settings_shortcuts_panel", True),
        ("about",      "About",            "_build_settings_about_panel",      True),
    )

    # The sections grouped by kind -- preferences, your content, tools that
    # delete, information -- apart from the tuple above, which keeps its order.
    SETTINGS_GROUPS = (
        ("General", ("name", "appearance")),
        ("Content", ("categories", "templates")),
        ("Data",    ("backup", "trash", "duplicates")),
        ("More",    ("statistics", "shortcuts", "about")),
    )

    # A fixed width, no narrow breakpoint: the app scrolls below 900px rather
    # than reflow (_on_main_canvas_configure). As at 100%, scaled by
    # NoteOrganizer._SIZES_AT_100.
    SETTINGS_NAV_WIDTH = 240
    # How many trash rows are painted before "Show more". A tuning knob, not
    # a feature: see the note in _build_settings_trash_panel for the numbers.
    TRASH_PAGE_SIZE = 25
    # Content stops growing past this; the space left on the right is
    # deliberate, so a short form is not stretched across the whole window.
    SETTINGS_CONTENT_MAX = 640

    def build_settings_tab(self, parent):
        """Settings as a navigation column plus a content pane: one section
        at a time, everything in it on one left edge -- stacked in one long
        column, reading the page meant zig-zagging.
        """
        outer = tk.Frame(parent)
        self.track_theme(outer, bg="bg")
        outer.pack(fill="both", expand=True)

        # There is no bar across the top any more: Back to Notes lives in
        # the rail, beside the section list. A full-width strip spent a band
        # of vertical space on every section to carry one control.

        body = tk.Frame(outer)
        self.track_theme(body, bg="bg")
        body.pack(fill="both", expand=True)

        # ---- left: the navigation ----
        self.settings_nav = tk.Frame(body, width=self.SETTINGS_NAV_WIDTH)
        self.track_theme(self.settings_nav, bg="sidebar")
        self.settings_nav.pack(side="left", fill="y")
        self.settings_nav.pack_propagate(False)   # hold our width, ignore children

        # --- brand block: mark, product name, and what this screen is ---
        brand = tk.Frame(self.settings_nav)
        self.track_theme(brand, bg="sidebar")
        brand.pack(fill="x", padx=14, pady=(16, 14))
        mark = tk.Canvas(brand, width=self.px(26), height=self.px(26),
                         highlightthickness=0, bd=0, bg=self.colors["sidebar"])
        mark.pack(side="left", padx=(0, 9))
        self._settings_brand_mark = mark
        self._paint_brand_mark()
        names = tk.Frame(brand)
        self.track_theme(names, bg="sidebar")
        names.pack(side="left", fill="x", expand=True)
        tk.Label(names, text="Note Organizer", font=("Segoe UI", 10, "bold"),
                 anchor="w", bg=self.colors["sidebar"], fg=self.colors["text"]
                 ).pack(fill="x")
        tk.Label(names, text="Settings", font=("Segoe UI", 8), anchor="w",
                 bg=self.colors["sidebar"], fg=self.colors["subtext"]
                 ).pack(fill="x")

        # --- Back to Notes, at the rail's foot, claimed before the scrolling
        # area so a list that grows cannot push it off, as in the note
        # sidebar ---
        self._settings_theme_toggle()

        # Everything between the brand and that foot scrolls. Nine entries in
        # four groups do not fit a short window, and a plain Frame simply
        # clipped whatever was past the bottom with no way to reach it.
        nav_scroll = tk.Canvas(self.settings_nav, highlightthickness=0, bd=0,
                               width=self.SETTINGS_NAV_WIDTH)
        self.track_theme(nav_scroll, bg="sidebar")
        nav_scroll.pack(side="top", fill="both", expand=True)
        self._settings_nav_canvas = nav_scroll
        self._settings_nav_body = tk.Frame(nav_scroll)
        self.track_theme(self._settings_nav_body, bg="sidebar")
        nav_window = nav_scroll.create_window(
            (0, 0), window=self._settings_nav_body, anchor="nw",
            width=self.SETTINGS_NAV_WIDTH)

        def _nav_scrollregion(_event=None):
            nav_scroll.configure(scrollregion=nav_scroll.bbox("all"))

        def _nav_fit(event):
            nav_scroll.itemconfigure(nav_window, width=event.width)
            _nav_scrollregion()

        self._settings_nav_body.bind("<Configure>", _nav_scrollregion)
        nav_scroll.bind("<Configure>", _nav_fit)

        back_row = tk.Frame(self._settings_nav_body, cursor="hand2")
        self.track_theme(back_row, bg="sidebar")
        back_row.pack(fill="x", padx=8, pady=(0, 8))
        back_ico = tk.Canvas(back_row, width=self.px(14), height=self.px(14),
                             highlightthickness=0, bd=0,
                             bg=self.colors["sidebar"], cursor="hand2")
        back_ico.pack(side="left", padx=(8, 6), pady=8)
        back_ico.create_line(12, 7, 3, 7, fill=self.colors["subtext"], width=1.6)
        back_ico.create_line(6.5, 3.5, 3, 7, 6.5, 10.5,
                             fill=self.colors["subtext"], width=1.6)
        self._scale_drawing(back_ico)
        back_lbl = tk.Button(
            back_row, text="Back to Notes", anchor="w", relief="flat", bd=0,
            highlightthickness=0, font=("Segoe UI", 9, "bold"), cursor="hand2",
            bg=self.colors["sidebar"], fg=self.colors["subtext"],
            activebackground=self.colors["card"],
            activeforeground=self.colors["text"],
            command=self.hide_settings_page)
        # Long-lived and pressed often: the press colours froze on the
        # build-time palette (the same active* pair the danger big-button
        # fix tracked, one screen away).
        self.track_theme(back_lbl, bg="sidebar", fg="subtext",
                         activebackground="card", activeforeground="text")
        back_lbl.pack(side="left", fill="x", expand=True)
        for w in (back_row, back_ico):
            # "break" when the person stayed (a half-written template):
            # the window's click-outside must not ask them a second time.
            w.bind("<Button-1>",
                   lambda _e: None if self.hide_settings_page() else "break")
            w._key_route = back_lbl     # the keyboard's way to the same

        def _back_hover(on, _ws=(back_row, back_ico, back_lbl)):
            c = self.colors["card"] if on else self.colors["sidebar"]
            for w in _ws:
                try:
                    w.configure(bg=c)
                except tk.TclError:
                    pass

        for w in (back_row, back_ico, back_lbl):
            w.bind("<Enter>", lambda _e: _back_hover(True))
            w.bind("<Leave>", lambda _e: _back_hover(False))


        # Each entry is a rail and a button: the selected one reads quietly as
        # a thin accent bar by a tinted row, which a tk.Button cannot draw.
        self._settings_nav_buttons = {}
        self._settings_nav_rails = {}
        self._settings_nav_icons = {}
        labels = {k: l for k, l, _b, _e in self.SETTINGS_SECTIONS}
        for group_name, group_keys in self.SETTINGS_GROUPS:
            tk.Label(self._settings_nav_body, text=group_name.upper(),
                     font=("Segoe UI", 8, "bold"), anchor="w",
                     bg=self.colors["sidebar"], fg=self.colors["subtext"]
                     ).pack(fill="x", padx=17, pady=(12, 4))
            for key in group_keys:
                label = labels[key]
                self._build_nav_entry(key, label)

        # The wheel over the entries too, which cover the canvas; anything
        # with a binding of its own keeps it (_bind_wheel_tree_if_unbound).
        def _nav_wheel(event):
            try:
                if nav_scroll.bbox("all") and \
                        nav_scroll.bbox("all")[3] > nav_scroll.winfo_height():
                    nav_scroll.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError, TypeError):
                pass
            return "break"

        self._settings_nav_wheel = _nav_wheel
        self.after_idle(
            lambda: self._bind_wheel_tree_if_unbound(self.settings_nav, _nav_wheel))

        # ---- right: the scrolling content pane ----
        content_host = tk.Frame(body)
        self.track_theme(content_host, bg="bg")
        content_host.pack(side="left", fill="both", expand=True)

        canvas = tk.Canvas(content_host, highlightthickness=0, bg=self.colors["bg"])
        self.track_theme(canvas, bg="bg")
        self.settings_canvas = canvas   # panels forward their scroll here
        sb = ttk.Scrollbar(content_host, orient="vertical", command=canvas.yview)
        page = tk.Frame(canvas)
        self.track_theme(page, bg="bg")
        self.settings_content = page
        page.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        page_window = canvas.create_window((0, 0), window=page, anchor="nw")

        def _fit(event):
            canvas.itemconfigure(page_window,
                                 width=min(event.width, self.SETTINGS_CONTENT_MAX))
        canvas.bind("<Configure>", _fit)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _page_wheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        canvas.bind("<MouseWheel>", _page_wheel)
        page.bind("<MouseWheel>", _page_wheel)
        # And from the keyboard: a section with nothing to Tab to -- the
        # Keyboard shortcuts, four fifths below the fold -- could not be read
        # without a mouse. After the calendar's own bind_all, which replaces.
        for seq, how in (("<Prior>", (-1, "pages")), ("<Next>", (1, "pages")),
                         ("<Up>", (-1, "units")), ("<Down>", (1, "units")),
                         ("<Home>", 0.0), ("<End>", 1.0)):
            self.bind_all(seq, lambda e, h=how: self._settings_page_key(e, h),
                          add="+")

        # Clicking a non-interactive part of the page takes focus off whatever
        # field has it, so a cursor is not left blinking in an already-saved
        # field. Bound on the toplevel because clicks bubble there anyway.
        def _clear_settings_field_focus(event):
            if not self.settings_page.winfo_ismapped():
                return
            try:
                focused = self.focus_get()
            except (tk.TclError, KeyError):
                return
            # event.widget can be a bare STRING, the widget rebuilt by a theme
            # switch before the event came: focus_set() on it raised.
            target = event.widget
            if not hasattr(target, "focus_set"):
                return
            if isinstance(focused, (tk.Entry, tk.Text)) and target is not focused:
                try:
                    target.focus_set()
                except tk.TclError:
                    pass
        self.bind("<Button-1>", _clear_settings_field_focus, add="+")

        # A frame per section, made now for callers to reach (the qa suite reads
        # stats_frame at once); the four heavy ones fill when first selected.
        for key, label, builder, eager in self.SETTINGS_SECTIONS:
            # On the page ground, so the cards inside read as raised surfaces.
            # The whole panel used to be card-coloured, which flattened every
            # section into one slab with nothing to separate its groups.
            frame = tk.Frame(page, bg=self.colors["bg"])
            self.track_theme(frame, bg="bg")
            setattr(self, "settings_%s_panel" % key, frame)
            if eager:
                self._settings_section_heading(frame, label)
                getattr(self, builder)(frame)

        self._bind_mousewheel_recursive(page, canvas)
        self.toggle_settings_panel(self.SETTINGS_SECTIONS[0][0])


    def _build_nav_entry(self, key, label):
        """One row in the section list: accent rail, glyph, label."""
        row = tk.Frame(self._settings_nav_body)
        self.track_theme(row, bg="sidebar")
        row.pack(fill="x", padx=0, pady=1)

        # The selected entry's short bar, 3 by 16 px and centred, drawn on a
        # canvas so its outer ends can be rounded.
        rail = tk.Canvas(row, width=self.px(3), height=self.px(34),
                         highlightthickness=0, bd=0, bg=self.colors["sidebar"])
        rail.pack(side="left", fill="y")

        icon = tk.Canvas(row, width=self.px(self.NAV_ICON_SIZE),
                         height=self.px(self.NAV_ICON_SIZE),
                         highlightthickness=0, bd=0, bg=self.colors["sidebar"],
                         cursor="hand2")
        icon.pack(side="left", padx=(9, 0))
        # The glyph clicks as its button does; "break" when the person stayed
        # with a half-written template, or click-outside asks again.
        icon.bind("<Button-1>",
                  lambda _e, k=key: (None if self.toggle_settings_panel(k)
                                     is not False else "break"))

        btn = tk.Button(
            row, text=label, anchor="w", relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2", bd=0,
            highlightthickness=0, activebackground=self.colors["card"],
            activeforeground=self.colors["text"],
            command=lambda k=key: self.toggle_settings_panel(k)
        )
        # Unselected entries are muted, not full-strength text -- that is what
        # lets the selected one read as selected without shouting.
        self.track_theme(btn, bg="sidebar", fg="subtext")
        btn.pack(side="left", fill="x", expand=True, padx=(10, 10), ipady=7)

        # Hover feedback, the same <Enter>/<Leave> pattern the sort menu,
        # emoji picker and category picker already use. The selected entry
        # is skipped so hovering it doesn't undo its own highlight.
        def _enter(_e, k=key, b=btn, ic=icon):
            if getattr(self, "_settings_selected_section", None) != k:
                b.configure(bg=self.colors["card"])
                ic.configure(bg=self.colors["card"])

        def _leave(_e, k=key, b=btn, ic=icon):
            if getattr(self, "_settings_selected_section", None) != k:
                b.configure(bg=self.colors["sidebar"])
                ic.configure(bg=self.colors["sidebar"])

        for w in (btn, icon):
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)

        self._settings_nav_buttons[key] = btn
        self._settings_nav_rails[key] = rail
        self._settings_nav_icons[key] = icon
        icon._key_route = btn       # the keyboard's way to what it does

    # Each glyph is geometry in a 16x16 box, so it takes the theme's colour --
    # an emoji is a fixed-colour bitmap, a PNG one copy per theme.
    NAV_ICON_SIZE = 17

    def _draw_icon(self, canvas, kind, color, size=None):
        """(Re)draw one glyph in ``color``.

        Shapes are laid out in a 16-unit box and scaled at the end, so one
        definition serves the 16px nav and the smaller row-action buttons.
        ``size`` is the box as drawn at 100%; the screen's scale is applied
        on top, with the canvas sized to match by its caller (px).
        """
        canvas.delete("glyph")
        o = {"tags": "glyph", "outline": color, "width": 1.6}
        # Filled shapes say outline="" explicitly: a canvas item's outline
        # defaults to the system text colour, which width=0 happens to hide
        # but which would otherwise be one more thing not following the theme.
        f = {"tags": "glyph", "fill": color, "outline": "", "width": 0}

        if kind == "name":                      # a person
            canvas.create_oval(5.5, 2.5, 10.5, 7.5, **o)
            canvas.create_arc(3, 9, 13, 19, start=0, extent=180, style="arc", **o)
        elif kind == "appearance":              # half-filled disc: light/dark
            canvas.create_oval(2.5, 2.5, 13.5, 13.5, **o)
            canvas.create_arc(2.5, 2.5, 13.5, 13.5, start=90, extent=180,
                              style="pieslice", **f)
        elif kind == "categories":              # a folder
            canvas.create_polygon(2.5, 4, 6, 4, 7.5, 6, 13.5, 6, 13.5, 13,
                                  2.5, 13, fill="", **o)
        elif kind == "templates":               # a page with a folded corner
            canvas.create_polygon(3.5, 2.5, 9.5, 2.5, 12.5, 5.5, 12.5, 13.5,
                                  3.5, 13.5, fill="", **o)
            canvas.create_line(9.5, 2.5, 9.5, 5.5, 12.5, 5.5, fill=color, width=1.2,
                               tags="glyph")
        elif kind == "backup":                  # arrow landing in a tray
            canvas.create_line(8, 2.5, 8, 8.5, fill=color, width=1.6, tags="glyph")
            canvas.create_line(5, 5.8, 8, 8.8, 11, 5.8, fill=color, width=1.6,
                               tags="glyph")
            canvas.create_line(2.8, 11, 2.8, 13.2, 13.2, 13.2, 13.2, 11,
                               fill=color, width=1.6, tags="glyph")
        elif kind == "trash":                   # a bin
            # Filled, not outlined. At the ~15px these are drawn at, a 1.6px
            # outline collapses into a small box that reads as nothing in
            # particular -- a solid silhouette still reads as a bin.
            canvas.create_rectangle(6.2, 2.4, 9.8, 4.2, **f)
            canvas.create_rectangle(2.8, 4.4, 13.2, 5.9, **f)
            canvas.create_polygon(4.6, 6.5, 11.4, 6.5, 10.6, 13.6, 5.4, 13.6, **f)
        elif kind == "duplicates":              # two overlapping cards
            canvas.create_rectangle(2.5, 2.5, 9.5, 9.5, fill="", **o)
            canvas.create_rectangle(6.5, 6.5, 13.5, 13.5, fill="", **o)
        elif kind == "statistics":              # a bar chart
            canvas.create_rectangle(2.8, 9, 5.2, 13.6, **f)
            canvas.create_rectangle(6.8, 5, 9.2, 13.6, **f)
            canvas.create_rectangle(10.8, 7, 13.2, 13.6, **f)
        elif kind == "shortcuts":               # a keyboard
            canvas.create_rectangle(2.2, 4.6, 13.8, 12.0, fill="", **o)
            # Filled keys, not outlined -- at nav size an outlined 1.4px
            # square collapses into noise, same reason as the bin above.
            for x in (4.3, 6.75, 9.2, 11.65):
                canvas.create_rectangle(x - 0.75, 6.2, x + 0.75, 7.7, **f)
            canvas.create_rectangle(5.0, 9.2, 11.0, 10.6, **f)  # space bar
        elif kind == "about":                   # an info disc
            canvas.create_oval(2.5, 2.5, 13.5, 13.5, **o)
            canvas.create_oval(7.2, 4.8, 8.8, 6.4, **f)
            canvas.create_rectangle(7.3, 7.6, 8.7, 11.8, **f)
        elif kind == "pencil":                  # edit
            # Filled for the same reason as the bin above.
            canvas.create_polygon(2.6, 13.4, 3.7, 10.1, 6.0, 12.4, **f)
            canvas.create_polygon(4.6, 9.2, 10.4, 3.4, 12.6, 5.6, 6.8, 11.4, **f)
            canvas.create_polygon(11.2, 2.6, 13.4, 4.8, 12.6, 5.6, 10.4, 3.4, **f)
        elif kind == "lock":                    # protected, not editable
            canvas.create_rectangle(4, 7.5, 12, 13.5, fill="", **o)
            canvas.create_arc(5.6, 2.8, 10.4, 9.2, start=0, extent=180,
                              style="arc", **o)
        elif kind == "updown":                  # ▲ over ▼: move one place
            canvas.create_polygon(8, 1.6, 12.6, 6.8, 3.4, 6.8, **f)
            canvas.create_polygon(3.4, 9.2, 12.6, 9.2, 8, 14.4, **f)

        if size and size != 16:
            canvas.scale("glyph", 0, 0, size / 16.0, size / 16.0)
        self._scale_drawing(canvas, "glyph")

    # ---- the small design system the panels are built from: three surface
    # steps and a border, derived from each theme -- the card, a well inside
    # it, and the edge a square card needs ----
    def _surface(self, kind="card"):
        """One of the three surface steps: the page furthest from the text
        colour, a card a step toward it, a well inside a card a step more --
        lighter on a dark theme, darker on a light one, as it blends toward
        ``text``.
        """
        if kind == "page":
            return self.colors["bg"]
        if kind == "inset":
            return inset_surface(self.colors)
        return self.colors["card"]

    def _border_color(self):
        return hairline(self.colors)

    def _settings_card(self, parent, pad=(22, 20)):
        """A bordered panel that groups related controls.

        Square-cornered on purpose: Tk has no border radius, and faking it
        means drawing the card on a canvas and placing every child onto it.
        A 1px border plus real padding carries the same grouping.
        """
        outer = tk.Frame(parent, bg=self._border_color())
        outer.pack(fill="x", pady=(0, 16))
        inner = tk.Frame(outer, bg=self._surface())
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        body = tk.Frame(inner, bg=self._surface())
        body.pack(fill="both", expand=True, padx=pad[0], pady=pad[1])
        return body

    def _field_label(self, parent, text):
        """The small uppercase caption above an input."""
        tk.Label(parent, text=text.upper(), font=("Segoe UI", 9, "bold"),
                 bg=self._surface(), fg=self.colors["subtext"], anchor="w"
                 ).pack(fill="x", pady=(0, 6))

    def _card_row(self, parent, label, hint=None, first=False):
        """One setting: label (and optional hint) left, control returned right.

        The caller packs its control into the frame this returns, which is
        the standard settings anatomy -- what the setting *is* on the left,
        what you do about it on the right, on one baseline.
        """
        if not first:
            tk.Frame(parent, height=1, bg=self._border_color()).pack(fill="x")
        row = tk.Frame(parent, bg=self._surface())
        row.pack(fill="x", pady=12)
        text_col = tk.Frame(row, bg=self._surface())
        text_col.pack(side="left", fill="x", expand=True)
        tk.Label(text_col, text=label, font=("Segoe UI", 10, "bold"),
                 bg=self._surface(), fg=self.colors["text"], anchor="w"
                 ).pack(fill="x")
        if hint:
            note = tk.Label(text_col, text=hint, font=("Segoe UI", 9),
                            bg=self._surface(), fg=self.colors["subtext"],
                            anchor="w", justify="left")
            note.pack(fill="x", pady=(2, 0))
            self._wrap_to_own_width(note)
        control = tk.Frame(row, bg=self._surface())
        # Packed first, built second: packed after its words, which took their
        # width unwrapped, a dropdown kept 18 px of its 74 under CI's fonts.
        control.pack(side="right", padx=(16, 0), before=text_col)
        return control

    def _note_banner(self, parent, text):
        """An informational strip -- retention notices and the like."""
        bg = self._surface("inset")
        wrap = tk.Frame(parent, bg=bg)
        wrap.pack(fill="x", pady=(0, 12))
        ico = tk.Canvas(wrap, width=self.px(16), height=self.px(16),
                        highlightthickness=0, bd=0, bg=bg)
        ico.pack(side="left", padx=(12, 8), pady=11)
        self._draw_icon(ico, "about", self.colors["accent_text"], size=16)
        band = tk.Label(wrap, text=text, font=("Segoe UI", 9), bg=bg,
                        fg=self.colors["subtext"], anchor="w", justify="left")
        band.pack(side="left", fill="x", expand=True, pady=10, padx=(0, 12))
        self._wrap_to_own_width(band)
        return wrap

    def _text_button(self, parent, text, command, kind="normal"):
        """A button sized to its label rather than stretched across the pane."""
        if kind == "danger":
            fg = border = self.colors["danger_text"]
            bg = self._surface()
            hover = self._blend(bg, self.colors["danger"], 0.14)
        elif kind == "primary":
            fg, border = self._on_fill("accent"), self.colors["accent"]
            bg = self.colors["accent"]
            hover = self.colors["accent_hover"]
        else:
            fg, border = self.colors["text"], self._border_color()
            bg = self._surface("inset")
            hover = self._blend(bg, self.colors["text"], 0.08)
        b = tk.Button(parent, text=text, command=command, relief="solid", bd=1,
                      font=("Segoe UI", 9, "bold"), cursor="hand2",
                      fg=fg, bg=bg, activeforeground=fg, activebackground=hover,
                      highlightbackground=border, padx=14, pady=6)
        # On built-once panels, so the palette-KEYED options are tracked; the
        # derived ones are the straggler net's, or refreshed on hover below.
        if kind == "danger":
            self.track_theme(b, fg="danger_text", activeforeground="danger_text",
                             highlightbackground="danger_text")
        elif kind == "primary":
            self.track_theme(b, fg="on_accent", activeforeground="on_accent",
                             highlightbackground="accent")
        else:
            self.track_theme(b, fg="text", activeforeground="text")

        # Hover from the LIVE palette, not the build-time capture — a
        # button that outlives a theme switch otherwise hovers in the old
        # theme's colours (audit Z07-F04, same class as the big buttons).
        def _tb_rest():
            if kind == "danger":
                return self._surface()
            if kind == "primary":
                return self.colors["accent"]
            return self._surface("inset")

        def _tb_hover():
            if kind == "danger":
                return self._blend(self._surface(), self.colors["danger"], 0.14)
            if kind == "primary":
                return self.colors["accent_hover"]
            return self._blend(self._surface("inset"), self.colors["text"], 0.08)

        b.bind("<Enter>", lambda _e: b.configure(bg=_tb_hover(),
                                                 activebackground=_tb_hover()))
        b.bind("<Leave>", lambda _e: b.configure(bg=_tb_rest(),
                                                 activebackground=_tb_hover()))
        return b

    ROW_ICON_SIZE = 15

    # What each wordless row icon does, in words, as the toolbar's buttons
    # say on hover -- here the actions are permanent. Keyed by glyph, so the
    # next icon gets one too; `tip=` says more where a row needs it.
    ICON_TIPS = {
        "pencil":     ("Rename", "Change what this is called."),
        "trash":      ("Delete", "Removes this one. Categories and templates "
                                 "do not go to the Trash."),
        "lock":       ("Protected", "A built-in item — it can't be renamed or "
                                    "deleted."),
        "templates":  ("Template", ""),
        "updown":     ("Move", "The top arrow moves this item up, the bottom "
                               "one down. Alt+Up and Alt+Down on its box do "
                               "the same."),
    }

    def _icon_button(self, parent, kind, command=None, danger=False,
                     bg_key="card", tip=None, removes_row=False,
                     takes_event=False, keys=None):
        """A small drawn-glyph button for a list row, in the theme's colour.
        ``removes_row``: it takes its row away unasked, so a double-click's
        second press, landing on the next row, is ignored
        (_second_press_of_double_click). ``takes_event`` hands the press to
        ``command``. No ``command``: an indicator (a padlock), unless
        ``keys``, the keyboard's press for a click the caller binds itself.
        """
        size = self.ROW_ICON_SIZE
        # Faint at rest even for destructive actions: the reference colours
        # them only on hover, so a list of rows does not read as a column of
        # red warnings before anyone has reached for anything.
        base = self.colors["subtext"]
        pad = 6
        # A press from the keyboard too, but not for a glyph whose halves do
        # different things: its row's box has Alt+Up and Alt+Down for that.
        if keys is None and command is not None and not takes_event:
            keys = command
        ring = 2 if keys else 0     # the ring's pixels, on the canvas's edge
        c = tk.Canvas(parent, width=self.px(size + pad * 2) - ring,
                      height=self.px(size + pad * 2) - ring,
                      highlightthickness=0, bd=0, bg=self.colors[bg_key],
                      cursor="hand2" if command else "")
        if keys:
            self._ring_round(c)
        # A canvas has no text to search for the way a Button does, so record
        # which glyph this is. The QA scripts locate row actions by it, and it
        # keeps them from depending on how a given icon happens to be drawn.
        c._icon_kind = kind
        # The glyph is drawn from the top-left, so nudge it into the padding.
        def paint(color):
            self._draw_icon(c, kind, color, size=size)
            c.move("glyph", self.px(pad), self.px(pad))

        paint(base)
        if command is not None:
            def _press(event):
                if removes_row and self._second_press_of_double_click(event):
                    return "break"
                # A command that has answered the press says "break", so
                # the window's click-outside does not answer it again.
                return command(event) if takes_event else command()

            c.bind("<Button-1>", _press)
            hot = self.colors["danger_text"] if danger else self.colors["text"]
            rest_bg = self.colors[bg_key]
            hover_bg = (self._blend(rest_bg, self.colors["danger"], 0.16) if danger
                        else self._surface("inset"))

            def _on(_e):
                self._fill(c, hover_bg)
                paint(hot)

            def _off(_e):
                self._fill(c, rest_bg)
                paint(base)

            c.bind("<Enter>", _on)
            c.bind("<Leave>", _off)
        if keys:
            self._pressable(c, keys)
        # After the hover bindings (add="+"), so the glyph still lights up; the
        # padlock too, for "why can't I rename this one".
        words = tip if tip is not None else self.ICON_TIPS.get(kind)
        if words:
            title, detail = words if isinstance(words, tuple) else (words, "")
            self._attach_tooltip(c, title, detail)
            # Recorded, as _icon_kind is, for a check to read: <Enter> is bound
            # for the hover colour anyway, and a mutant removing every tooltip
            # was seen only by the padlock.
            c._icon_tip = title
        return c

    def _row_divider(self, parent):
        """A hairline between list rows.

        Material's guidance is dividers *between groups*, not between every
        item -- but these rows each carry their own controls, so without a
        rule they read as one undifferentiated block of text.
        """
        line = tk.Frame(parent, height=1,
                        bg=self._blend(self.colors["card"],
                                       self.colors["subtext"], 0.22))
        line.pack(fill="x", padx=2)
        return line

    def _paint_brand_mark(self):
        """The small app mark at the top of the rail.

        A flat accent tile with a page glyph on it. The reference design used
        a gradient; Tk canvases have no gradient fill, and faking one by
        drawing 26 stacked lines would cost more than it is worth at this
        size, so it is a solid accent instead.
        """
        c = self._settings_brand_mark
        if c is None:
            return
        try:
            c.delete("all")
            c.configure(bg=self.colors["sidebar"])
            self._rounded_rect(c, 0, 0, 26, 26, 8,
                               fill=self.colors["accent"],
                               outline=self.colors["accent"])
            # a small page: body plus two text lines
            c.create_rectangle(9, 7, 17, 19, fill="white", outline="white")
            c.create_line(11, 11, 15, 11, fill=self.colors["accent"], width=1.2)
            c.create_line(11, 14, 15, 14, fill=self.colors["accent"], width=1.2)
            self._scale_drawing(c)
        except tk.TclError:
            pass

    def _settings_theme_toggle(self):
        """Light/dark, as a segmented control pinned to the foot of the rail.

        Moving it here takes the one control people flip most often out of
        the Appearance panel, so it is reachable from every section rather
        than only after navigating to one.
        """
        foot = tk.Frame(self.settings_nav)
        self.track_theme(foot, bg="sidebar")
        foot.pack(side="bottom", fill="x", padx=14, pady=14)
        tk.Label(foot, text="THEME", font=("Segoe UI", 8, "bold"), anchor="w",
                 bg=self.colors["sidebar"], fg=self.colors["subtext"]
                 ).pack(side="left")

        holder = tk.Frame(foot, bg=self._border_color())
        holder.pack(side="right")
        inner = tk.Frame(holder, bg=self.colors["sidebar"])
        inner.pack(padx=1, pady=1)
        self._settings_mode_buttons = {}
        for mode, glyph in (("dark", "moon"), ("light", "sun")):
            # Two pixels less: the keyboard's ring, resting in the canvas's
            # own fill, is the outermost pixel, where nothing is drawn.
            b = tk.Canvas(inner, width=self.px(26) - 2, height=self.px(20) - 2,
                          highlightthickness=0, bd=0,
                          bg=self.colors["sidebar"], cursor="hand2")
            self._ring_round(b)
            b.pack(side="left")
            b.bind("<Button-1>", lambda _e, m=mode: self._pick_settings_mode(m))
            self._pressable(b, lambda m=mode: self._pick_settings_mode(m))
            # Two drawn shapes at the very bottom of the nav, with nothing
            # written near them. They do not go through _icon_button, so the
            # words are attached here.
            self._attach_tooltip(
                b, "Dark mode" if mode == "dark" else "Light mode",
                "Switches to the last %s theme you used. The full list is "
                "under Appearance." % ("dark" if mode == "dark" else "light"))
            self._settings_mode_buttons[mode] = b
        self._refresh_mode_toggle()

    def _pick_theme_by_key(self, name):
        """A theme tile pressed from the keyboard: the theme changes, the
        page is drawn again in it, and the keyboard is on that theme's tile."""
        self.set_theme(name)
        found = []

        def walk(w):
            for c in w.winfo_children():
                if getattr(c, "_theme_name", None) == name:
                    found.append(c)
                walk(c)
        try:
            walk(self.theme_picker_frame)
        except (tk.TclError, AttributeError):
            return
        if found:
            found[0].focus_set()
            found[0].update_idletasks()       # the page drawn again, laid out
            self._bring_into_sight(found[0])

    def _pick_settings_mode(self, mode):
        """Switch to the remembered theme for this mode, if not already on it."""
        in_dark = self.theme_name in DARK_THEMES
        if (mode == "dark") == in_dark:
            return
        self.toggle_theme()

    def _refresh_mode_toggle(self):
        """Mark whichever half of the toggle matches the current theme."""
        buttons = getattr(self, "_settings_mode_buttons", None)
        if not buttons:
            return
        in_dark = self.theme_name in DARK_THEMES
        for mode, c in buttons.items():
            active = (mode == "dark") == in_dark
            try:
                c.delete("all")
                bg = self.colors["card"] if active else self.colors["sidebar"]
                fg = self.colors["accent_text"] if active else self.colors["subtext"]
                self._fill(c, bg)
                if mode == "dark":
                    c.create_oval(8, 5, 18, 15, outline=fg, width=1.5)
                    c.create_oval(11, 3, 22, 14, outline=bg, fill=bg, width=0)
                else:
                    c.create_oval(10, 7, 16, 13, outline=fg, width=1.5)
                    for x1, y1, x2, y2 in ((13, 2, 13, 4), (13, 16, 13, 18),
                                           (5, 10, 7, 10), (19, 10, 21, 10),
                                           (7.5, 4.5, 9, 6), (17, 14, 18.5, 15.5),
                                           (7.5, 15.5, 9, 14), (17, 6, 18.5, 4.5)):
                        c.create_line(x1, y1, x2, y2, fill=fg, width=1.3)
                self._scale_drawing(c)
            except tk.TclError:
                pass

    def _recolor_settings_nav_icons(self):
        """Repaint the nav glyphs for the current theme.

        Called from ``apply_theme``: ``track_theme`` restores each canvas's
        background, but nothing it does reaches items *drawn on* a canvas, so
        without this the glyphs keep the old theme's colour.
        """
        self._paint_brand_mark()
        self._refresh_mode_toggle()
        if not self._settings_nav_icons:
            return
        self._highlight_settings_nav(
            getattr(self, "_settings_selected_section", None))

    def _settings_section_heading(self, parent, title):
        """A section's title, left-aligned with everything beneath it.

        The previous layout put titles left and their buttons centred, which is
        exactly what made the page tiring to scan.
        """
        tk.Label(parent, text=title, font=("Segoe UI", 16, "bold"), anchor="w",
                 bg=self.colors["bg"], fg=self.colors["text"]
                 ).pack(fill="x", pady=(0, 6))

    def _settings_big_button(self, parent_frame, text, command, kind="normal"):
        """A full-width action button, left-aligned like its section:
        ``accent`` for a section's one primary action, ``normal`` for the
        rest, ``danger`` outlined in the warning colour rather than filled --
        emptying the Trash should be findable, not inviting.
        """
        if kind == "danger":
            b = tk.Button(parent_frame, text=text, command=command,
                          relief="solid", bd=1, font=("Segoe UI", 10, "bold"),
                          cursor="hand2", fg=self.colors["danger_text"],
                          bg=self.colors["card"],
                          highlightbackground=self.colors["danger_text"],
                          activeforeground=self.colors["danger_text"],
                          activebackground=self.colors["card"])
            self.track_theme(b, bg="card", fg="danger_text",
                             highlightbackground="danger_text",
                             activebackground="card",
                             activeforeground="danger_text")
        else:
            b = tk.Button(parent_frame, text=text, command=command, relief="flat",
                          font=("Segoe UI", 10, "bold"), cursor="hand2",
                          fg=self.colors["text"])
            if kind == "accent":
                self.track_theme(b, bg="accent", fg="on_accent")
            else:
                self.track_theme(b, bg="sidebar")

        # Hover colours worked out at EVENT time: taken at build, a button
        # hovered in the theme it was built under (audit Z07-F04).
        def _rest_bg():
            if kind == "danger":
                return self.colors["card"]
            return self.colors["accent" if kind == "accent" else "sidebar"]

        def _hover_bg():
            if kind == "danger":
                return self._blend(self.colors["card"], self.colors["danger"], 0.14)
            return (self.colors["accent_hover"] if kind == "accent"
                    else self.colors["card"])

        b.bind("<Enter>", lambda _e: b.configure(bg=_hover_bg()))
        b.bind("<Leave>", lambda _e: b.configure(bg=_rest_bg()))
        return b

    def _build_category_row(self, parent, name, redraw):
        protected = (name == PROTECTED_CATEGORY)
        color = CATEGORY_COLORS[name]

        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", pady=3)

        # 26 with a two-pixel ring that rests in the row's colour: the colour
        # is the 22 it always was, and the padding gives the ring its room.
        swatch = tk.Frame(row, bg=color, width=26, height=26, cursor="hand2")
        self._ring_round(swatch, self.colors["card"], width=2)
        swatch.pack(side="left", padx=6, pady=6)
        swatch.pack_propagate(False)

        count = self.count_notes_in_category(name)
        name_lbl = tk.Label(row, bg=self.colors["card"],
                            fg=self.colors["text"], anchor="w")
        # The name gives way before its count, and is packed after the icons
        # (below): an 80-letter name took the row and its rename and delete.
        _fit_title(self, name_lbl, "", name, f"   ({count})",
                   self._cal_font(("Segoe UI", 10, "bold"))[0])

        def recolor():
            def apply_color(chosen):
                # Categories always need a color; ignore an empty (reset) pick.
                if not chosen:
                    return
                CATEGORY_COLORS[name] = chosen
                persist_categories()
                redraw()
                self.refresh_note_list()
                self.render_calendar()
                self._update_color_swatch()
                # The open note's category button too: its dot kept the old
                # colour beside a new swatch, card and calendar.
                self._refresh_category_button_safe()
            self._show_color_palette(swatch, CATEGORY_COLORS[name], apply_color,
                                     allow_reset=False)

        # Click the swatch itself to recolor (no separate button, no OS dialog).
        swatch.bind("<Button-1>", lambda e: recolor())
        self._pressable(swatch, recolor)

        def rename():
            def do_rename(new):
                new = new.strip()
                if not new or new == name:
                    return True
                if new in CATEGORY_COLORS:
                    self.show_warning(
                        "Already exists",
                        f"A category named “{new}” already exists.")
                    return False
                refusal = category_name_refusal(new, adding=False)
                if refusal:
                    self.show_warning("Can't rename it to that", refusal)
                    return False
                # Renamed where it stands: pop-and-insert moved the
                # category to the end of the list's groups.
                in_order = [(new if key == name else key, colour)
                            for key, colour in CATEGORY_COLORS.items()]
                CATEGORY_COLORS.clear()
                CATEGORY_COLORS.update(in_order)
                self.rename_category_everywhere(name, new)
                persist_categories()
                self.save_notes()
                redraw()
                self.refresh_category_widgets()
                self.refresh_note_list()
                self.render_calendar()
                return True
            self._show_inline_rename(name_lbl, name, do_rename)

        if not protected:
            self._icon_button(row, "pencil", rename).pack(side="right", padx=1)

            def delete():
                self._delete_category(name, redraw)

            self._icon_button(row, "trash", delete, danger=True
                              ).pack(side="right", padx=1)
        else:
            self._icon_button(row, "lock").pack(side="right", padx=5)
        name_lbl.pack(side="left", fill="x", expand=True, padx=(2, 6))

    def _delete_category(self, name, redraw):
        """Delete a category, asking what to do with any notes it holds."""
        count = self.count_notes_in_category(name)

        if count == 0:
            if not self.ask_yes_no("Delete category",
                                       f"Delete “{name}”? It has no notes.",
                                       icon="warning", default="no"):
                return
            # No notes, but templates, the Trash and a folded group can
            # still hold the name -- and a note restored from the Trash
            # would bring the category straight back.
            self.reassign_category_everywhere(name, PROTECTED_CATEGORY)
            CATEGORY_COLORS.pop(name, None)
            persist_categories()
            redraw()
            self.refresh_category_widgets()
            return

        # Saved first, as every delete route: its typing belongs in the Trash
        # copy. The unstorable date is asked only when the note on screen is
        # filed here; a pending repeat turn-off waits (_context_delete_note).
        shown = (self.find_note(self.selected_note_id)
                 if self.selected_note_id is not None else None)
        leaving = (self.category_var.get() == name
                   or (shown is not None and shown.get("category") == name))
        if self._flush_autosave(leaving=leaving, hold_repeat_off=True) is False:
            return
        # Counted after the save, which may have filed the open note here or
        # out: only a note FILED here can go; a series' day here moves to General.
        count = self.count_notes_in_category(name)
        named = {n["id"] for n in self.notes if n.get("category") == name}
        choice = self._ask_category_deletion(name, len(named),
                                             days_only=count - len(named))
        if choice is None:
            return
        if choice == "move":
            self.reassign_category_everywhere(name, PROTECTED_CATEGORY)
        elif choice == "delete_notes":
            # To the Trash: only the notes the question counted, still filed
            # here; one filed while it waited goes to General with the rest.
            doomed = [n for n in self.notes
                      if n["id"] in named and n.get("category") == name]
            gone = {n["id"] for n in doomed}
            if self._move_notes_to_trash(doomed) is None:
                return   # trash.json refused them: the category and its notes stay
            self.notes = [n for n in self.notes if n["id"] not in gone]
            # A series' day filed here is re-filed under General, never
            # deleted (it was, under "restorable"); so are the templates and
            # a folded group. A trashed note restored brings the name back.
            self.reassign_category_everywhere(name, PROTECTED_CATEGORY)

        CATEGORY_COLORS.pop(name, None)
        persist_categories()
        self.save_notes()
        redraw()
        self.refresh_category_widgets()
        self.refresh_note_list()
        self.render_calendar()
        if self.selected_note_id and not self.find_note(self.selected_note_id):
            self.new_note()

    def _ask_category_deletion(self, name, count, days_only=0):
        """Returns 'move', 'delete_notes', or None (cancel), asked in the
        app's own dialog. `count` notes are filed under the category;
        `days_only` repeating notes have only a day there, which moves to
        General either way, and are named apart."""
        days = ""
        if days_only:
            days = (f"{days_only} repeating note(s) have a day filed under "
                    f"“{name}”; those days move to “{PROTECTED_CATEGORY}” "
                    "either way.")
        if not count:
            # Nothing here can go to the Trash, so there is nothing to
            # choose between: only whether the category goes. Enter keeps
            # it, as on the question asked of an empty category.
            return self._themed_dialog(
                "Delete category",
                f"Delete “{name}”? No note is filed under it. {days}",
                kind="warning",
                buttons=[("Cancel", None),
                         ("Delete the category", "move", "danger")],
                default="Cancel")
        return self._themed_dialog(
            "Delete category",
            f"“{name}” has {count} note(s). What should happen to them?"
            + (f"\n\n{days}" if days else ""),
            kind="warning",
            # "delete_notes" moves to the Trash, restorable like any delete: a
            # "(permanent)" label was untrue and frightened people off it.
            buttons=[("Cancel", None),
                     (f"Delete the notes too (restorable"
                      f"{trash_window_words('for')})", "delete_notes", "danger"),
                     (f"Move them to “{PROTECTED_CATEGORY}” (keep the notes)", "move")],
            # Either answer deletes the category, and no Undo brings back
            # each note's filing under it: Enter keeps it, as above.
            default="Cancel")

    def _cleanup_selected_duplicates(self, del_vars, refresh, announce=False):
        """Move the checkbox-selected duplicates to trash. `del_vars` is a list of
        (delete_var, note, group) — a note is removed when its var is set. Within
        each group, the attachments of removed notes are merged into a
        surviving copy (the first note in that group NOT marked for deletion), up
        to the MAX_ATTACHMENTS a note holds -- the rest stay with their copy in
        the Trash. If a whole group is checked, all are removed."""
        # Figure out, per group, which notes are being removed and which survive.
        by_group = {}
        for var, note, group in del_vars:
            gid = id(group)
            by_group.setdefault(gid, {"group": group, "remove": []})
            if var.get():
                by_group[gid]["remove"].append(note)

        plan = []   # (the first survivor or None, the notes removed)
        to_trash = []
        for info in by_group.values():
            remove = info["remove"]
            if not remove:
                continue
            survivors = [n for n in info["group"] if n not in remove]
            plan.append((survivors[0] if survivors else None, remove))
            to_trash.extend(remove)

        if not to_trash:
            self.show_info(
                "Nothing selected",
                "Tick the duplicates you want to remove first.")
            return
        # Saved first, as every delete route: its typing belongs in the Trash
        # copy. The unstorable date is asked only when the editor is about to
        # be cleared or reloaded (see the end).
        affected = ({n.get("id") for n in to_trash}
                    | {kept.get("id") for kept, _remove in plan
                       if kept is not None})
        # A repeat's turn-off waiting there is held back for the question:
        # a No made it all the same (see _context_delete_note).
        if self._flush_autosave(
                leaving=self.selected_note_id in affected,
                hold_repeat_off=True) is False:
            return
        if not self.ask_yes_no(
            "Move duplicates to trash",
            f"Move {len(to_trash)} selected note(s) to the trash? "
            f"You can restore them{trash_window_words('within')}.",
            # Enter answers a question now: a reflexive one deletes nothing.
            icon="question", default="no"
        ):
            return
        # Into the Trash first: when trash.json cannot be written nothing
        # changes, the merge's file copies included.
        trash_ids = {id(n) for n in to_trash}
        if self._move_notes_to_trash(to_trash) is None:
            return
        # Only now, after Yes, are the files merged. The merge copies each
        # file, and it used to run before the question: "No" still gave
        # the kept note new files, and every retry made another copy.
        grew = set()
        for kept, remove in plan:
            if kept is None:
                continue
            # The survivor gets its OWN copy of each merged file: the copy
            # going to the Trash keeps its references, and the purge deletes
            # them (as duplicate_note does).
            merged_attach = list(kept.get("attachments", []))
            seen_attach = {a.get("stored_as") for a in merged_attach}
            for note in remove:
                for a in note.get("attachments", []):
                    # At MAX_ATTACHMENTS, as the backup's merge stops: the rest
                    # stay with their copy, restorable from the Trash.
                    if len(merged_attach) >= MAX_ATTACHMENTS:
                        break
                    if a.get("stored_as") in seen_attach:
                        continue
                    seen_attach.add(a.get("stored_as"))
                    # Duplicate gave the copy each file again under a new
                    # name: the kept note holds it already, and merged, it
                    # listed every file twice.
                    if any(same_attached_file(a, k) for k in merged_attach):
                        continue
                    new_name = copy_attachment_file(a.get("stored_as"))
                    if new_name:
                        merged_attach.append(dict(a, stored_as=new_name))
                    # If the copy can't be made, skip it rather than
                    # alias a file the purge will delete out from under
                    # the survivor.
            if merged_attach != list(kept.get("attachments", [])):
                kept["attachments"] = merged_attach
                grew.add(kept.get("id"))
        self.notes = [n for n in self.notes if id(n) not in trash_ids]
        self.save_notes()
        # The editor is told: its copy went (it starts fresh), or its kept copy
        # gained files (it moves onto that version, or saved the old list back).
        if (self.selected_note_id is not None
                and self.find_note(self.selected_note_id) is None):
            self.new_note()
            self._sync_editor_snapshot()
        else:
            # A repeat's turn-off held back for the question goes across the
            # reload, still waiting: the merge changed the kept copy's
            # files, never its date or repeat.
            carried = (self._schedule_to_carry()
                       if self.selected_note_id in grew else {})
            self._editor_follows_external_change(grew)
            self._put_back_schedule(carried)
        self.refresh_note_list()
        self.render_calendar()
        if announce:
            self.show_info("Cleaned up",
                                f"Moved {len(to_trash)} duplicate(s) to the trash.")
        refresh()

    def _build_settings_name_panel(self, parent):
        """The greeting shown above the note list, plus a live preview."""
        self._settings_subtitle(
            parent,
            "The basics — how the app greets you, and what shows in the sidebar.")
        card = self._settings_card(parent)
        self._field_label(card, "Your name")

        field = tk.Frame(card, bg=self._border_color())
        field.pack(fill="x")
        inner = tk.Frame(field, bg=self._surface("inset"))
        inner.pack(fill="x", padx=1, pady=1)

        self.username_var = tk.StringVar(value=self.load_username())
        # Cap at 30 characters -- an unbounded name could look broken in the
        # sidebar greeting. Only limits new typing; an existing longer name
        # (saved before this cap existed) still loads and displays in full.
        USERNAME_MAX_LEN = 30
        name_entry = tk.Entry(
            inner, textvariable=self.username_var, relief="flat", bd=0,
            highlightthickness=0, font=("Segoe UI", 11),
            bg=self._surface("inset"), fg=self.colors["text"],
            insertbackground=self.colors["text"],
        )
        name_entry.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=9)
        # Kept as every limited box is (_limit_entry): a paste past the cap
        # shortened and said so. Its own check refused one whole, without a
        # word.
        self._limit_entry(name_entry, USERNAME_MAX_LEN, "Your name")
        self._add_paste_menu(name_entry)
        self._guard_entry_astral(name_entry)

        # How much room is left, in the field itself, rather than only in the
        # description above it.
        counter = tk.Label(inner, font=("Consolas", 8), bg=self._surface("inset"),
                           fg=self.colors["subtext"])
        counter.pack(side="right", padx=(0, 12))

        preview = tk.Frame(card, bg=self._surface("inset"))
        preview.pack(fill="x", pady=(12, 0))
        tk.Label(preview, text="Sidebar shows", font=("Segoe UI", 8),
                 bg=self._surface("inset"), fg=self.colors["subtext"]
                 ).pack(side="left", padx=(12, 8), pady=10)
        preview_value = tk.Label(preview, text="", font=("Segoe UI", 9, "bold"),
                                 bg=self._surface("inset"), fg=self.colors["text"])
        preview_value.pack(side="left", pady=10)

        saved_note = tk.Label(card, text="", font=("Segoe UI", 8),
                              bg=self._surface(), fg=self.colors["success_text"],
                              anchor="w")
        saved_note.pack(fill="x", pady=(8, 0))

        def refresh_preview():
            current = self.username_var.get().strip()
            preview_value.configure(
                text=f"Hi {current}," if current else "no greeting",
                fg=self.colors["text"] if current else self.colors["subtext"])
            used = len(self.username_var.get())
            counter.configure(
                text=f"{used}/{USERNAME_MAX_LEN}",
                fg=self.colors["danger_text"] if used >= USERNAME_MAX_LEN - 3
                else self.colors["subtext"])

        refresh_preview()

        def save_name():
            if getattr(self, "_username_save_job", None) is not None:
                try:
                    self.after_cancel(self._username_save_job)
                except (tk.TclError, ValueError):
                    pass
                self._username_save_job = None
            if not self._still_alive():
                return
            # The limit again at saving: the key-by-key check can miss typing
            # held down (a Tk gap under rapid keystrokes).
            current = self.username_var.get()
            if len(current) > USERNAME_MAX_LEN:
                current = current[:USERNAME_MAX_LEN]
                self.username_var.set(current)
            self.save_username(current)
            self._refresh_greeting()
            refresh_preview()
            self.set_status("Name saved" if current.strip() else "Name cleared")
            try:
                saved_note.configure(text="Saved automatically")
                self.after(2200, lambda: saved_note.winfo_exists()
                           and saved_note.configure(text=""))
            except tk.TclError:
                pass

        def schedule_name_save(event=None):
            # And at every key release, a plain binding without validate's gap:
            # past 30, snapped back at once rather than at the save.
            current = self.username_var.get()
            if len(current) > USERNAME_MAX_LEN:
                self.username_var.set(current[:USERNAME_MAX_LEN])
            refresh_preview()
            # Autosave after a short pause, same convention as note editing --
            # so clearing the field and clicking away still saves the change.
            if getattr(self, "_username_save_job", None) is not None:
                try:
                    self.after_cancel(self._username_save_job)
                except (tk.TclError, ValueError):
                    pass
            self._username_save_job = self.after(600, save_name)

        name_entry.bind("<KeyRelease>", schedule_name_save)
        name_entry.bind("<FocusOut>", lambda e: save_name())
        # Pressed, not held: each repeat wrote the settings file again
        # (_enter_repeats).
        name_entry.bind("<Return>", lambda e: (
            None if self._enter_repeats(e) else save_name()))
        # No Save button: the field saves shortly after typing stops, and at
        # once on Enter or clicking away.

    def _build_settings_appearance_panel(self, parent):
        """Light/dark toggle and the theme picker.

        Moved out of build_settings_tab unchanged when Settings became a
        nav plus a content pane; only the frame it builds into differs.
        """
        self._settings_subtitle(
            parent, "Pick a look that feels right. Changes apply instantly, everywhere.")
        appearance = parent
        # No light/dark button here any more: the mode switch is a
        # segmented control in the rail footer, reachable from every
        # section instead of only after navigating to this one.

        # Theme picker — pick any color scheme, grouped Dark / Light.
        self.theme_picker_frame = tk.Frame(appearance, bg=self.colors["bg"])
        self.track_theme(self.theme_picker_frame, bg="bg")
        # Padding here, not on the card below: a card has none, as it follows a
        # subtitle everywhere but here, after the swatches.
        self.theme_picker_frame.pack(fill="x", pady=(0, 20))
        self._build_theme_picker(self.theme_picker_frame)

        # The editor's own font, every note's baseline (the toolbar overrides a
        # selection): "my notes bigger" is about reading, not one note.
        card = self._settings_card(appearance)
        row = self._card_row(
            card, "Editor font",
            "The typeface notes are written in, unless a note says otherwise.",
            first=True)
        self.editor_font_family_var = tk.StringVar(
            value=self.editor_font_family or FONT_FAMILIES[0])
        self._build_themed_dropdown(
            row, self.editor_font_family_var, list(FONT_FAMILIES),
            lambda v: self._set_editor_font(family=v), width_chars=16
        ).pack(side="right")

        row = self._card_row(
            card, "Text size",
            "Bigger text in every note, without reformatting a single one.")
        self.editor_font_size_var = tk.StringVar(value=str(self.editor_font_size))
        self._build_themed_dropdown(
            row, self.editor_font_size_var, [str(s) for s in FONT_SIZES],
            lambda v: self._set_editor_font(size=int(v)), width_chars=8
        ).pack(side="right")

        # Only Windows stretches a program as a picture, so only there is a
        # choice -- in words for someone who never heard of DPI.
        if sys.platform.startswith("win"):
            row = self._card_row(
                card, "Sharp text",
                "Keeps text crisp when Windows makes everything bigger "
                "(Scale above 100% in the Windows display settings), as most "
                "laptops do. On a second screen that isn't enlarged, the app "
                "may then look a little blurry — choose Off if that's "
                "where you keep it. Takes effect the next time you open "
                "Note Organizer.")
            self.sharp_text_var = tk.StringVar(
                value="On" if get_setting(SHARP_TEXT_SETTING, True, expect=bool)
                else "Off")
            self._build_themed_dropdown(
                row, self.sharp_text_var, ["On", "Off"], self._set_sharp_text,
                width_chars=8
            ).pack(side="right")

            # Spelling, judged by Windows' own dictionaries (ui/spelling.py).
            # The row says which languages those are, because "why is my
            # Romanian not checked" has its answer in Windows, not here.
            languages = self._spell_languages_text()
            checking = ("Checking: %s." % languages if languages else
                        "Windows has no spelling dictionary on this computer yet.")
            row = self._card_row(
                card, "Spelling",
                "Underlines misspelled words in red in your notes and their "
                "comments; right-click one for suggestions. Text in a language "
                "Windows has no dictionary for is left alone. " + checking +
                " To check another language too, add it in the Windows "
                "language settings.")
            self.spelling_var = tk.StringVar(
                value="On" if get_setting(SPELLING_SETTING, True, expect=bool)
                else "Off")
            self._build_themed_dropdown(
                row, self.spelling_var, ["On", "Off"], self._set_spelling,
                width_chars=8
            ).pack(side="right")

    def _set_sharp_text(self, value):
        """Settings → Appearance → Sharp text, kept for the next start.

        Windows lets a program say how it draws only before its first
        window exists (_draw_sharp_on_scaled_screens), so nothing on screen
        can change now; the row's own words say when it will, and the
        banner says it again at the moment of choosing."""
        on = value == "On"
        if on == get_setting(SHARP_TEXT_SETTING, True, expect=bool):
            return
        save_setting(SHARP_TEXT_SETTING, on)
        self._show_toast("Saved — you'll see it the next time you open "
                         "Note Organizer")

    def _build_settings_backup_panel(self, parent):
        """Export everything to a file, or import from one."""
        self._settings_subtitle(
            parent,
            "Move your notes between computers, or keep a copy somewhere safe.")
        self._note_banner(
            parent,
            "Everything stays on this computer. An export is the only copy of "
            "your notes that is not in the app's own folder.")
        card = self._settings_card(parent)

        control = self._card_row(
            card, "Export notes",
            "Writes every note, setting and attachment into one .zip file.",
            first=True)
        self._text_button(control, "Export", self.export_data,
                          kind="primary").pack()
        # The app is offline by design, so an export is the only copy of
        # the notes outside the app's own folder -- and this line is the
        # only thing that says when that copy was last made.
        last = get_setting("last_export_at", "", expect=str)
        self.last_export_lbl = tk.Label(
            card, text=(f"Last exported: {last}" if last
                        else "Never exported from this computer."),
            font=("Segoe UI", 8), anchor="w",
            bg=self._surface(), fg=self.colors["subtext"])
        self.last_export_lbl.pack(fill="x", pady=(0, 6))

        control = self._card_row(
            card, "Import notes",
            "Brings a previously exported .zip back in. You are asked before "
            "anything that looks like a duplicate is added.")
        self._text_button(control, "Import", self.import_data).pack()

    def _build_settings_statistics_panel(self, parent):
        """A read-only snapshot of the notebook."""
        self._settings_subtitle(parent, "A quick snapshot of your notes.")
        # No wrapping card: the tiles and chips below are the raised surfaces,
        # so a card around them would box a box.
        self.stats_frame = tk.Frame(parent, bg=self.colors["bg"])
        self.track_theme(self.stats_frame, bg="bg")
        self.stats_frame.pack(fill="x")
        self._render_statistics()

    # Every combo here is a real binding, and every real binding is here --
    # the list's keys once shipped without their rows: a key bound gets its
    # row in the same change. The calendar's act only while it shows.
    SHORTCUT_GROUPS = (
        ("App", (
            ("Ctrl+N", "New note (switches to the Notes tab first)."),
            ("Ctrl+S", "Save the current note now."),
            ("Ctrl+F", "Find in the current note — searches its text and "
                       "its tables; Enter / Shift+Enter step the matches."),
        )),
        ("Anywhere", (
            ("Tab  /  Shift+Tab", "The next / previous control. The page "
                                  "scrolls to show it."),
            ("Ctrl+Tab  /  Ctrl+Shift+Tab", "Leave the note or the comments "
                                            "box, where Tab types a tab."),
            ("Escape", "Close a popup or a dropdown's list. On a question: "
                       "its safe answer (No, Cancel)."),
            ("Space  /  Enter", "Press what the keyboard is on — a drawn "
                                "button too: a theme, an alignment, a "
                                "category's rename or colour."),
            ("Ctrl+Z", "While the banner offers Undo — a delete, a "
                       "removed row, a move: take it, anywhere but a box "
                       "with typing of its own to take back."),
        )),
        ("Text formatting, in the note", (
            ("Ctrl+B", "Bold the selection — or with nothing selected, "
                       "bold whatever you type next."),
            ("Ctrl+I", "Italic, the same way."),
            ("Ctrl+U", "Underline."),
            ("Ctrl+D", "Strikethrough. In an open table cell with nothing "
                       "selected, the four style the whole cell."),
        )),
        ("Clipboard", (
            ("Ctrl+V", "Paste, keeping the source's bold, colours, lists "
                       "and tables."),
            ("Ctrl+Shift+V", "Paste the words alone, with no styling."),
            ("Ctrl+C", "Copy — a selected block of table cells copies as "
                       "cells, and pastes into Excel as cells too."),
        )),
        ("Editing", (
            ("Ctrl+Z", "Undo, in the note body and comments."),
            ("Ctrl+Y  /  Ctrl+Shift+Z", "Redo."),
        )),
        ("Tables", (
            ("Tab  /  Shift+Tab", "Next / previous cell — Tab on the very "
                                  "last cell adds a fresh row."),
            ("Enter  /  Shift+Enter", "A new line inside the cell; the row "
                                      "grows to fit."),
            ("Ctrl+A", "Select the whole cell."),
            ("Escape", "Leave the cell."),
            ("Delete", "Clear the selected cells."),
        )),
        ("Note list (click a note, or Tab into it from the search box)", (
            ("Up  /  Down", "Walk from card to card, in the order the list "
                            "is showing them — over the category headers "
                            "too, when the list is grouped."),
            ("Enter  /  Space", "Open the note — or tick it, while "
                                "☑ Select is on. On a category header: "
                                "fold or open its group."),
            ("Left  /  Right", "In a list grouped by category: Left folds "
                               "the group (from a note or its header), Right "
                               "opens a folded one."),
            ("Alt+Up  /  Alt+Down", "Move the note one place up or down. "
                                    "The list switches to Custom order, "
                                    "starting from the order it was "
                                    "showing."),
            ("Escape", "While dragging a note to a new place: put it "
                       "back where it was."),
            ("Shift+F10", "That note's own right-click menu, opened at the "
                          "note. The menu key does the same where a "
                          "keyboard has one."),
        )),
        ("Dropdowns (Sort, Show, Repeat, the font, the settings)", (
            ("Space  /  Enter  /  Down", "Open the list, on the choice it "
                                         "shows now."),
            ("Up  /  Down  /  Home  /  End", "Walk the list."),
            ("Enter  /  Space", "Choose. The keyboard goes back to the "
                                "dropdown."),
            ("Escape", "Close the list without choosing."),
        )),
        ("Pickers (colours, emoji, a table's size, a date)", (
            ("Arrow keys  /  Home  /  End", "Move between the swatches, emoji, "
                                            "cells or days."),
            ("Enter  /  Space", "Pick it. An emoji goes in and the picker "
                                "stays open, for the next one."),
            ("Escape", "Close the picker. The keyboard goes back to the "
                       "button that opened it."),
        )),
        ("Checklist (click an item's ▲ ▼, or Tab to its box)", (
            ("Alt+Up  /  Alt+Down", "Move the item one place up or down, as "
                                    "the ▲ ▼ at its left do; in a template's "
                                    "checklist too."),
        )),
        ("Calendar (while the Calendar tab is showing)", (
            ("Page Up  /  Page Down", "Previous / next month."),
            ("Ctrl+Page Up  /  Ctrl+Page Down", "Previous / next year."),
            ("Home", "Jump back to today."),
            ("Arrow keys", "With Tab on the month: move its ring a day, or a "
                           "week, into the next month or the last."),
            ("Enter  /  Space", "Open the day with the ring, as a click does."),
            ("Shift+F10", "That day's right-click menu: add a note, colour or "
                          "mark the day."),
            ("Enter  /  Shift+F10", "On a note in an open day's list, or a "
                                    "row of History: open it, or its "
                                    "right-click menu."),
        )),
        ("Settings (while this page is showing)", (
            ("Page Up  /  Page Down", "Scroll the section a page at a time — "
                                      "Up / Down a little, Home / End to its "
                                      "top or bottom. Not in a text box."),
        )),
    )

    def _build_settings_shortcuts_panel(self, parent):
        """A read-only reference of every keyboard shortcut the app binds.

        Thirteen combos were bound and only the formatting four were
        discoverable (via the right-click menu) -- everything else lived
        in the user guide or in nobody's memory.
        """
        self._settings_subtitle(
            parent,
            "The keyboard's shortcuts, by where they work — Page Down reads "
            "on. The formatting four are also on the note body's right-click "
            "menu.")
        for title, rows in self.SHORTCUT_GROUPS:
            tk.Label(parent, text=title, font=("Segoe UI", 9, "bold"),
                     anchor="w", bg=self.colors["bg"],
                     fg=self.colors["subtext"]).pack(fill="x", pady=(0, 6))
            card = self._settings_card(parent, pad=(22, 6))
            for i, (combo, what) in enumerate(rows):
                row = self._card_row(card, combo, what, first=(i == 0))
                # No control on the right -- the row IS the information.
                row.pack_forget()

    def _build_settings_about_panel(self, parent):
        """Version, where the data lives, the welcome note, the privacy
        policy, the licenses, and -- once the app is in the Store -- a way
        to review it."""
        self._settings_subtitle(
            parent, "Version info, where your notes live, the welcome note, "
                    "the privacy policy and the licenses.")
        head = tk.Frame(parent, bg=self.colors["bg"])
        self.track_theme(head, bg="bg")
        head.pack(fill="x", pady=(0, 14))
        mark = tk.Canvas(head, width=self.px(44), height=self.px(44),
                         highlightthickness=0, bd=0, bg=self.colors["bg"])
        mark.pack(side="left", padx=(2, 12))
        self._rounded_rect(mark, 0, 0, 44, 44, 12,
                           fill=self.colors["accent"], outline=self.colors["accent"])
        mark.create_rectangle(15, 11, 29, 33, fill="white", outline="white")
        for y in (17, 22, 27):
            mark.create_line(18, y, 26, y, fill=self.colors["accent"], width=1.6)
        self._scale_drawing(mark)
        titles = tk.Frame(head, bg=self.colors["bg"])
        self.track_theme(titles, bg="bg")
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text="Note Organizer", font=("Segoe UI", 13, "bold"),
                 anchor="w", bg=self.colors["bg"], fg=self.colors["text"]
                 ).pack(fill="x", pady=(3, 0))
        tk.Label(titles, text=f"Version {_host().APP_VERSION}",
                 font=("Consolas", 9), anchor="w",
                 bg=self.colors["bg"], fg=self.colors["subtext"]).pack(fill="x")
        terms = tk.Label(titles, text=diagnostics.ABOUT_TERMS, font=("Segoe UI", 9), anchor="w",
                         justify="left", bg=self.colors["bg"], fg=self.colors["subtext"])
        terms.pack(fill="x", pady=(4, 0))
        self._wrap_to_own_width(terms)

        card = self._settings_card(parent)
        self._field_label(card, "Where your notes are stored")
        # paths.APP_DIR, not the entry module's -- see _host()'s docstring.
        path_text = paths.APP_DIR or "(not set yet)"
        well = tk.Frame(card, bg=self._surface("inset"))
        well.pack(fill="x")
        where = tk.Label(well, text=path_text, font=("Consolas", 9),
                         bg=self._surface("inset"), fg=self.colors["subtext"],
                         anchor="w", justify="left")
        where.pack(fill="x", padx=12, pady=10)
        self._wrap_to_own_width(where)

        buttons = tk.Frame(card, bg=self._surface())
        buttons.pack(fill="x", pady=(10, 0))

        def open_folder():
            target = paths.APP_DIR
            if not target or not os.path.isdir(target):
                self.show_warning("Folder not found",
                                  "The data folder could not be opened.")
                return
            try:
                os.startfile(target)   # Windows-only, matches this app's target
            except OSError as exc:
                self.show_warning("Could not open folder", str(exc))

        def copy_path():
            target = paths.APP_DIR or ""
            self.clipboard_clear()
            self.clipboard_append(target)
            self.set_status("Folder path copied")

        self._text_button(buttons, "Open folder", open_folder).pack(side="left")
        self._text_button(buttons, "Copy path", copy_path).pack(side="left", padx=(8, 0))

        # The note a first start opens on, offered again (core/welcome.py).
        start = self._settings_card(parent)
        control = self._card_row(
            start, "Welcome note",
            "A short guide to every part of the app. Deleted, it comes back "
            "from here.", first=True)
        self._text_button(control, "Show", self.show_welcome_note).pack()

        # The pages this opens are in the browser: the app itself connects to
        # nothing (core/diagnostics). Feedback is a Store review, so until the
        # app has a Store page there is no Feedback card at all.
        policy = self._settings_card(parent)
        control = self._card_row(
            policy, "Privacy policy",
            "Your notes stay on this computer. The policy says what leaves "
            "it, and that it leaves only when you send it.", first=True)
        self._text_button(
            control, "Read",
            lambda: self._open_in_browser(diagnostics.PRIVACY_URL)).pack()
        licenses = self._settings_card(parent)
        control = self._card_row(
            licenses, "Open-source licenses",
            "Note Organizer is built with Python, Tcl/Tk and Pillow. Their "
            "licenses, and its own, are in one text file.", first=True)
        self._text_button(control, "Open", self._open_licenses).pack()
        if diagnostics.STORE_REVIEW_URL:
            talk = self._settings_card(parent)
            control = self._card_row(
                talk, "Feedback",
                "Something not working, slow, or an idea? Write a review in "
                "the Microsoft Store — I read each one and answer there.",
                first=True)
            self._text_button(
                control, "Write a review",
                lambda: self._open_in_browser(diagnostics.STORE_REVIEW_URL)).pack()

    def _technical_details(self):
        """What the running app may say about itself (core/diagnostics): how
        it draws on this screen, and how big the notebook is -- never what
        the notes say."""
        sharp = get_setting(SHARP_TEXT_SETTING, True, expect=bool)
        return ([("scale", "%d%%" % round(self._ui_scale * 100)),
                 ("sharp", "on" if sharp else "off"),
                 ("theme", THEME_LABELS.get(self.theme_name, self.theme_name))]
                + diagnostics.notebook(self.notes))

    def _open_licenses(self):
        """Open the licenses file that ships with the app, in the person's
        text editor."""
        path = paths.bundled_file(diagnostics.NOTICES)
        if not os.path.isfile(path):
            self.show_warning("Licenses not found",
                              "The licenses file is missing from this copy "
                              "of the app.")
            return
        try:
            os.startfile(path)   # Windows-only, matches this app's target
        except OSError as exc:
            self.show_warning("Could not open the licenses", str(exc))

    def _open_in_browser(self, url):
        """Open *url* in the person's browser. Where that fails, the link is
        copied, and the words say where to paste it."""
        try:
            opened = webbrowser.open(url)
        except Exception:  # noqa: BLE001 -- any failure has the same answer
            opened = False
        if opened:
            self.set_status("Opened in your browser")
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
        except tk.TclError:
            pass
        self.show_warning(
            "Couldn't open your browser",
            "The link is copied. Paste it into your browser's address bar "
            "to open the page.")
