"""The Settings page and the panels on it.

WHAT IS HERE
------------
The Settings page itself, and each panel it shows: categories, templates,
trash, duplicates, statistics, the theme picker, and the About section.
Also the small pieces those panels are built from — a category row, a
template row, the template editor.

WHAT IS DELIBERATELY NOT HERE
-----------------------------
Several things match the word "settings" or "theme" but belong to the app
as a whole, so they stay on :class:`NoteOrganizer`:

* ``apply_theme``, ``set_theme``, ``toggle_theme``, ``track_theme`` — the
  theming engine. The *whole app* themes itself; the Settings page is just
  one place that triggers it.
* ``_themed_dialog``, ``_build_themed_dropdown`` — shared widgets used all
  over the app.
* category *operations* (``rename_category_everywhere``,
  ``_bulk_change_category``) as opposed to the category management *UI*,
  which is here.

Panels here still call those freely through ``self`` — mixins share one
object, so nothing had to change to keep that working.

A NOTE FOR THE REDESIGN
-----------------------
The plan (see `docs/ROADMAP.md`) is to move from one long scrolling column
to a Chrome-style layout: categories listed down a narrow left column, the
selected section's controls in the middle, space to the right.

Most of this file survives that. Each ``_build_settings_*_panel`` renders
one section and does not care how it is reached. What changes is
:meth:`build_settings_tab`, which currently stacks the panels vertically
and gives each a collapsible header — that assembly is what becomes a left
nav plus a content pane.
"""

import os
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime, timedelta, date as date_cls

from ..core import paths
from ..core.categories import CATEGORY_COLORS, persist_categories
from ..core.formatting import FONT_FAMILIES, FONT_SIZES
from ..core.duplicates import find_duplicate_groups
from ..core.storage import (
    TRASH_RETENTION_DAYS,
    trash_retention_days,
    _delete_attachment_files,
    get_setting,
    save_setting,
    load_settings,
    normalize_template,
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
    inset_surface,
    hairline,
)


def _host():
    """The entry-point module, imported only when actually needed.

    ``note_organizer`` imports this file to build the app class, so importing
    it back at module level would be circular. A local import breaks the
    cycle.

    Use this **only for values that are module-level constants**, such as
    ``APP_VERSION``. Anything ``initialise()`` fills in must not be read
    through here, because there can be two copies of this module at once:
    running the app as ``py note_organizer.py`` makes the running copy
    ``__main__``, and ``import note_organizer`` below then loads a *second*,
    separate copy whose ``initialise()`` has never run — so every value it
    assigns is still ``None``. That is not hypothetical; it blanked the
    storage path in About and printed "since None" in Statistics. Those two
    now read from the core layer instead, which is only ever imported by
    name and so can never be duplicated this way.
    """
    import note_organizer
    return note_organizer


class SettingsPageMixin:
    """The Settings page for :class:`NoteOrganizer`.

    Not usable on its own — every method here reads state owned by the app
    (``self.colors``, ``self.notes``, ``self.settings_canvas`` and so on).
    """

    def toggle_settings_panel(self, which):
        """Show one Settings section, hiding whichever was showing.

        Kept under its original name because it is how the rest of the app --
        and the QA suite, in 8 places -- asks for a Settings section. What
        changed is the meaning: there used to be an accordion where a section
        could be open or closed, and now exactly one is always showing, so this
        selects rather than toggles.
        """
        sections = {key: (getattr(self, "settings_%s_panel" % key, None), builder, eager)
                    for key, _label, builder, eager in self.SETTINGS_SECTIONS}
        target, builder, eager = sections.get(which, (None, None, None))
        if target is None:
            return

        for key, (panel, _b, _e) in sections.items():
            if panel is not None and panel.winfo_ismapped():
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
            # Builders can't create their own resize handle: the handle has to
            # overlay the panel's bottom edge, so it can only be added once the
            # canvas above it exists. They record (frame, min, max) instead and
            # it gets built here, lifted above its siblings so dragging it
            # doesn't repack them.
            for tgt, mn, mx in getattr(self, "_resize_handles_pending", []):
                h = self._add_resize_handle(tgt, min_h=mn, max_h=mx, host=target)
                h.pack(fill="x", padx=12, pady=(2, 8))
            self._resize_handles_pending = []

        target.pack(fill="both", expand=True, padx=48, pady=(40, 60))
        self._settings_selected_section = which
        self._highlight_settings_nav(which)
        if getattr(self, "settings_canvas", None) is not None:
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
        rails = getattr(self, "_settings_nav_rails", {})
        icons = getattr(self, "_settings_nav_icons", {})
        tint = self._blend(self.colors["sidebar"], self.colors["accent"], 0.16)
        for key, btn in getattr(self, "_settings_nav_buttons", {}).items():
            try:
                selected = (key == which)
                btn.configure(
                    bg=tint if selected else self.colors["sidebar"],
                    fg=self.colors["accent"] if selected else self.colors["subtext"],
                    activebackground=tint if selected else self.colors["card"],
                )
                rail = rails.get(key)
                if rail is not None:
                    rail.configure(bg=tint if selected else self.colors["sidebar"])
                    rail.delete("all")
                    if selected:
                        h = max(rail.winfo_height(), 34)
                        top = (h - 16) / 2
                        rail.create_rectangle(0, top, 3, top + 16,
                                              fill=self.colors["accent"],
                                              outline=self.colors["accent"])
                icon = icons.get(key)
                if icon is not None:
                    icon.configure(bg=tint if selected else self.colors["sidebar"])
                    self._draw_icon(
                        icon, key,
                        self.colors["accent"] if selected else self.colors["subtext"])
            except tk.TclError:
                pass

    def _panel_or_page_wheel(self, panel_canvas, event):
        """If the panel's list can scroll, scroll it; else scroll the whole
        Settings page. Used for every widget in an inline settings panel."""
        if panel_canvas is not None:
            try:
                first, last = panel_canvas.yview()
                # Small tolerance instead of exact 0.0/1.0: yview() can come
                # back as e.g. 0.0/0.997 rather than a clean 0.0/1.0 depending
                # on how the platform rounds the scroll fraction, which would
                # make an already-fully-visible panel (like an empty trash
                # list) look like it still has more to scroll — trapping the
                # wheel on a tiny, already-fully-shown panel instead of
                # falling through to the page underneath it.
                if not (first <= 0.001 and last >= 0.999):
                    panel_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return "break"
            except (tk.TclError, ValueError):
                pass
        page_canvas = getattr(self, "settings_canvas", None)
        if page_canvas is not None:
            try:
                page_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
        return "break"

    def _settings_subtitle(self, parent, text):
        """The explanatory line under a section title.

        This replaced a header that drew the title itself plus a close ✕.
        Both stopped making sense once the nav took over naming sections and
        one section is always showing: the title appeared twice, and the ✕
        had nothing left to close -- it re-selected the section it was
        already on.
        """
        lbl = tk.Label(parent, text=text, font=("Segoe UI", 10), anchor="w",
                       justify="left", wraplength=self.SETTINGS_CONTENT_MAX - 20,
                       bg=self.colors["bg"], fg=self.colors["subtext"])
        lbl.pack(fill="x", pady=(0, 22))
        return lbl

    def _render_statistics(self):
        """Compute and draw a compact, read-only snapshot: total notes; a
        week/month/year/older breakdown of when notes were added and last
        updated; standalone counts of templates, notes with a checklist,
        and notes currently in Trash; the date this install was first
        used; and per-category counts as plain lines (no box, not
        clickable — this is a snapshot, not another way to filter notes).
        Recomputed on every note-list refresh (not just when the Settings
        tab is opened), so category renames/deletes, new notes, and any
        other change stay reflected live while Settings happens to be
        open — not just after leaving and coming back. Deliberately does
        NOT gate on the Settings page's winfo_ismapped() state — that
        looked like the right optimization (skip the work when Settings
        isn't visible), but pack()/pack_forget() don't always update
        ismapped() synchronously, so that check could skip a real update
        and leave stale data on screen. Redrawing every time is cheap
        (this panel is at most a couple dozen small widgets) compared to
        the note-card rebuild refresh_note_list() already does around it,
        so there's no real cost to just always doing it. Every field is
        read defensively — a note with a missing/odd timestamp or
        category just gets skipped from that specific count instead of
        crashing the whole panel."""
        if not hasattr(self, "stats_frame"):
            return
        for w in self.stats_frame.winfo_children():
            w.destroy()

        notes = self.notes
        total = len(notes)

        def _parse_ts(raw):
            if not isinstance(raw, str) or not raw:
                return None
            try:
                return datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
            except ValueError:
                return None

        today = date_cls.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        def _bucket_counts(field):
            # Cumulative from the start of each period (so "this year"
            # already includes "this month"); "older" is the one true
            # complement — notes not touched at all since Jan 1st.
            week = month = year = older = 0
            for n in notes:
                ts = _parse_ts(n.get(field))
                if not ts:
                    continue
                d = ts.date()
                if d >= week_start:
                    week += 1
                if d >= month_start:
                    month += 1
                if d >= year_start:
                    year += 1
                else:
                    older += 1
            return week, month, year, older

        added_week, added_month, added_year, added_older = _bucket_counts("created")
        updated_week, updated_month, updated_year, updated_older = _bucket_counts("updated")

        # --- Presentation. The figures above are the same as they always
        # were; what changed is that they are shown as figures rather than
        # as sentences. This used to render "Added: 0 this week 0 this
        # month 5 this year 0 older" as one run of same-size text, so the
        # number and the word carried identical weight and nothing could be
        # read at a glance -- which is the whole point of a snapshot.
        #
        # Now: three tiles for the standalone counts, then a small table
        # with a real header row for the time breakdown, then the category
        # split. Numbers lead, captions follow quietly. ---
        # Tallied up here because the tiles below report the category count as
        # well as the split further down.
        counts = {}
        for n in notes:
            cat = n.get("category") or PROTECTED_CATEGORY
            counts[cat] = counts.get(cat, 0) + 1
        # Templates and checklists are their own things -- a template can be
        # reused across many notes, a checklist only ever lives inside the one
        # note it is on -- so these count the things themselves, not how many
        # notes reference them. "In trash" is what is there right now, not an
        # all-time total, so it drops back after Trash is emptied or purges.
        templates_count = len(self.templates)
        checklists_count = sum(1 for n in notes if n.get("checklist"))
        deleted_count = len(self.trash)

        tiles = tk.Frame(self.stats_frame, bg=self.colors["bg"])
        tiles.pack(fill="x", pady=(0, 22))
        for i in range(3):
            tiles.grid_columnconfigure(i, weight=1, uniform="stat")
        # Three across, as in the reference design -- but six figures rather
        # than three, wrapping to a second row. The reference was a sketch
        # with three; dropping to match it exactly would have deleted the
        # template, checklist and trash counts, which are real figures this
        # panel has always shown and has regression tests for.
        for i, (value, caption) in enumerate((
                (total, "Total notes"),
                (added_week, "Added this week"),
                (len(counts), "Categories"),
                (templates_count, "Templates"),
                (checklists_count, "With a checklist"),
                (deleted_count, "In trash"))):
            edge = tk.Frame(tiles, bg=self._border_color())
            edge.grid(row=i // 3, column=i % 3, sticky="nsew",
                      padx=(0 if i % 3 == 0 else 12, 0),
                      pady=(0 if i < 3 else 12, 0))
            tile = tk.Frame(edge, bg=self._surface())
            tile.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(tile, text=str(value), font=("Segoe UI", 20, "bold"),
                     bg=self._surface(), fg=self.colors["text"], anchor="w"
                     ).pack(fill="x", padx=18, pady=(16, 0))
            tk.Label(tile, text=caption, font=("Segoe UI", 9, "bold"),
                     bg=self._surface(), fg=self.colors["subtext"], anchor="w"
                     ).pack(fill="x", padx=18, pady=(3, 16))

        # --- The time breakdown, as a table with a header rather than a
        # sentence. Counts are right-aligned so digits line up down each
        # column, and the header says once what the old version repeated on
        # every single cell ("this week" appeared four times). ---
        SEGMENTS = ("this week", "this month", "this year", "older")
        table = tk.Frame(self.stats_frame, bg=self.colors["bg"])
        table.pack(fill="x", pady=(0, 4))
        table.grid_columnconfigure(0, weight=0, minsize=76)
        for c in range(1, 5):
            table.grid_columnconfigure(c, weight=1, uniform="seg")

        for c, seg in enumerate(SEGMENTS):
            tk.Label(table, text=seg, font=("Segoe UI", 8), bg=self.colors["bg"],
                     fg=self.colors["subtext"], anchor="e"
                     ).grid(row=0, column=c + 1, sticky="ew", padx=(8, 0), pady=(0, 2))

        rule = tk.Frame(table, height=1, bg=self._border_color())
        rule.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(0, 4))

        for r, (caption, values) in enumerate((
                ("Added", (added_week, added_month, added_year, added_older)),
                ("Updated", (updated_week, updated_month, updated_year, updated_older)))):
            tk.Label(table, text=caption, font=("Segoe UI", 9), bg=self.colors["bg"],
                     fg=self.colors["subtext"], anchor="w"
                     ).grid(row=r + 2, column=0, sticky="w", pady=2)
            for c, value in enumerate(values):
                tk.Label(table, text=str(value), font=("Segoe UI", 10, "bold"),
                         bg=self.colors["bg"],
                         fg=self.colors["text"] if value else self.colors["subtext"],
                         anchor="e"
                         ).grid(row=r + 2, column=c + 1, sticky="ew", padx=(8, 0), pady=2)

        # --- Per-category split. Known categories first (Manage-categories
        # order), then any leftover/stale names so nothing is silently
        # dropped. Deliberately not clickable: this is a snapshot, not
        # another way to filter notes -- see docs/ISSUES_LOG.md. ---
        ordered_cats = [c for c in CATEGORY_COLORS.keys() if c in counts]
        ordered_cats += [c for c in counts.keys() if c not in ordered_cats]

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
                tk.Label(pill, text=cat, font=("Segoe UI", 9, "bold"),
                         bg=self._surface(), fg=self.colors["subtext"], anchor="w"
                         ).pack(side="left", fill="x", expand=True)
                tk.Label(pill, text=str(n), font=("Consolas", 9),
                         bg=self._surface(), fg=self.colors["text"], anchor="e"
                         ).pack(side="right", padx=(6, 12))

        # Read the stamp back from settings rather than the entry module's
        # FIRST_LAUNCH_DATE -- see _host()'s docstring for why that global
        # can be None here. Purely a read: the stamp is written once, at
        # startup, by get_first_launch_date().
        since = load_settings().get("first_launch_date") or "\u2014"
        tk.Label(
            self.stats_frame, text=f"Using Note Organizer since {since}",
            font=("Segoe UI", 9), bg=self.colors["bg"],
            fg=self.colors["subtext"], anchor="w"
        ).pack(fill="x", pady=(18, 0))


        # Same wheel-forwarding pattern used elsewhere in Settings (theme
        # picker, inline panels) — without it, scrolling with the cursor
        # over the summary text or a category chip does nothing, since
        # those widgets have no scroll behavior of their own to fall back
        # to. Rebound every time this panel rebuilds (it's redrawn on every
        # Settings-page open, to stay fresh).
        def _stats_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        self._bind_wheel_tree(self.stats_frame, _stats_wheel)

    def _build_settings_categories_panel(self, parent):
        self._settings_subtitle(
            parent,
            "Rename, recolor, or remove your categories. “General” is permanent.")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=220)
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

        def redraw():
            for w in rows_frame.winfo_children():
                w.destroy()
            for i, name in enumerate(list(CATEGORY_COLORS.keys())):
                if i:
                    self._row_divider(rows_frame)
                self._build_category_row(rows_frame, name, redraw)
            self._bind_wheel_tree(rows_frame, lambda e: self._panel_or_page_wheel(canvas, e))
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

        def add_new():
            name = new_name_var.get().strip()
            if not name:
                return
            if name in CATEGORY_COLORS:
                self.show_warning("Already exists",
                                       f"A category named “{name}” already exists.")
                return
            palette = list(DEFAULT_CATEGORY_COLORS.values())
            CATEGORY_COLORS[name] = palette[len(CATEGORY_COLORS) % len(palette)]
            persist_categories()
            new_name_var.set("")
            redraw()
            self.refresh_category_widgets()

        new_entry.bind("<Return>", lambda e: add_new())
        tk.Button(add_row, text="+ Add", command=add_new, bg=self.colors["accent"],
                  fg="white", relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="right", ipadx=10, ipady=4)

    def _build_settings_templates_panel(self, parent):
        self._settings_subtitle(
            parent,
            "Reusable starting points for new notes. Create one here or use "
            "“🧩 Save as template” on any note. Pick one with “📎 Use template”. "
            "Editing a template only affects notes you make from it afterwards — "
            "notes already created stay as they are.")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=240)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        rows = tk.Frame(canvas, bg=self.colors["card"])
        rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        def redraw():
            for w in rows.winfo_children():
                w.destroy()
            if not self.templates:
                tk.Label(rows, text="No templates yet. Create one below, or use "
                                    "“Save as template” on a note.",
                         bg=self.colors["card"], fg=self.colors["subtext"],
                         font=("Segoe UI", 9), wraplength=460, justify="left"
                         ).pack(pady=10, padx=6, anchor="w")
            else:
                for i, tpl in enumerate(self.templates):
                    if i:
                        self._row_divider(rows)
                    self._build_template_row(rows, tpl, redraw)
            self._bind_wheel_tree(rows, lambda e: self._panel_or_page_wheel(canvas, e))
        redraw()
        self._refresh_templates_panel = redraw

        # New-from-scratch row.
        add_row = tk.Frame(parent, bg=self.colors["card"])
        add_row.pack(fill="x", padx=12, pady=(6, 10))
        new_tpl_btn = tk.Button(add_row, text="＋ New template",
                  command=lambda: self._edit_template(None, redraw, new_tpl_btn),
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2")
        new_tpl_btn.pack(fill="x", ipady=4)

    def _build_template_row(self, parent, tpl, redraw):
        name = tpl.get("name", "Untitled template")
        row = tk.Frame(parent, bg=self.colors["sidebar"])
        row.pack(fill="x", pady=4, padx=2)
        self._icon_button(row, "templates", bg_key="sidebar").pack(side="left", padx=(6, 0))
        tk.Label(row, text=name, bg=self.colors["sidebar"],
                 fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w"
                 ).pack(side="left", fill="x", expand=True, padx=6, pady=8)

        def delete():
            # Honest about the stakes: notes go to the Trash and can come
            # back for the whole retention window -- templates do not.
            if self.ask_yes_no(
                    "Delete template",
                    f"Delete the template “{name}” for good?\n\n"
                    "Templates don't go to the Trash — this can't be undone.",
                    parent=parent):
                self.templates = [t for t in self.templates if t is not tpl]
                save_templates(self.templates)
                redraw()
                self._render_statistics()

        self._icon_button(row, "trash", delete, danger=True, bg_key="sidebar"
                          ).pack(side="right", padx=(1, 6))
        edit_btn = self._icon_button(row, "pencil", bg_key="sidebar")
        edit_btn.bind("<Button-1>",
                      lambda _e: self._edit_template(tpl, redraw, edit_btn))
        edit_btn.pack(side="right", padx=1)

    def _draw_template_table_preview(self, canvas, body_text):
        """A read-only rendering of the body's tables, for the template
        dialog: the editor's visual language (bold header on its own
        surface, hairline rules, separator-aware widths, hidden columns
        as slivers, merges as spanned cells) without its machinery.
        Every table and every row is drawn -- the canvas scrolls when it
        grows past the dialog's budget. Returns the table blocks, empty
        when there is nothing to draw."""
        from noteorganizer.core import tables as core_tables
        from noteorganizer.core.themes import hairline, inset_surface
        canvas.delete("all")
        text = body_text.get("1.0", "end-1c")
        blocks = core_tables.find_blocks(text)
        if not blocks:
            return []
        lines = text.split("\n")
        font = tkfont.Font(family="Consolas", size=9)
        pad_x, row_h, y = 6, 22, 2
        rule = hairline(self.colors)
        max_x = 100
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
                    widths.append(8)
                    continue
                longest = max((font.measure(seg) for r in rows
                               if c < len(r)
                               and r[c] not in (core_tables.MERGE_LEFT,
                                                core_tables.MERGE_UP)
                               for seg in core_tables.cell_display_lines(
                                   r[c])),
                              default=20)
                if column and column.get("width"):
                    longest = max(longest,
                                  font.measure("0") * column["width"])
                widths.append(min(longest + 2 * pad_x, 160))
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
                            shown = seg
                            if font.measure(seg) > w_span - 2 * pad_x:
                                while (len(shown) > 1 and
                                       font.measure(shown + "\u2026")
                                       > w_span - 2 * pad_x):
                                    shown = shown[:-1]
                                shown += "\u2026"
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
        shown_h = min(y, 240)
        shown_w = min(max_x + 6, 430)
        canvas.configure(height=shown_h, width=shown_w,
                         bg=self.colors["card"], highlightthickness=0,
                         scrollregion=(0, 0, max_x, y))
        canvas._preview_overflows = y > shown_h
        canvas._preview_overflows_x = max_x > shown_w
        return blocks

    def _edit_template(self, tpl, redraw, anchor_widget=None):
        """Open a small editor (inline window) to create or edit a template's
        name, title, body, comments and category."""
        is_new = tpl is None
        data = normalize_template(tpl or {})

        self._dismiss_mini_popup()
        pop = tk.Toplevel(self)
        self._mini_popup = pop
        pop.wm_overrideredirect(True)
        pop.configure(bg=self.colors["accent"])
        frame = tk.Frame(pop, bg=self.colors["card"], padx=12, pady=12)
        frame.pack(padx=1, pady=1)

        head = tk.Frame(frame, bg=self.colors["card"])
        head.pack(fill="x", pady=(0, 8))
        tk.Label(head, text=("New template" if is_new else "Edit template"),
                 bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Button(head, text="✕", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["card"], fg=self.colors["subtext"],
                  font=("Segoe UI", 10, "bold"), bd=0).pack(side="right")

        def field(label, initial, height=1):
            tk.Label(frame, text=label, bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
            if height == 1:
                var = tk.StringVar(value=initial)
                e = tk.Entry(frame, textvariable=var, relief="flat", font=("Segoe UI", 10),
                             bg=self.colors["sidebar"], fg=self.colors["text"],
                             insertbackground=self.colors["text"], width=40)
                e.pack(fill="x", ipady=3)
                self._add_paste_menu(e)
                return var
            else:
                t = tk.Text(frame, height=height, width=40, relief="flat",
                            font=("Segoe UI", 10), bg=self.colors["sidebar"],
                            fg=self.colors["text"], insertbackground=self.colors["text"],
                            wrap="word")
                t.insert("1.0", initial)
                t.pack(fill="x")
                self._add_paste_menu(t)
                # A table copied from Excel, Word or a web page arrives
                # as pipe text instead of losing its shape to the plain
                # clipboard.
                t.bind("<<Paste>>",
                       lambda e, w=t: self._paste_table_aware(w))
                return t

        name_var = field("Template name", data["name"])
        title_var = field("Note title (optional)", data["title"])
        body_txt = field("Note body", data["body"], height=4)
        # Tables in the body show AS tables, right here -- the same
        # visual language as the editor, in preview form. Hidden until
        # the body actually holds one.
        # The holder is packed NOW, right under the body box, so the
        # preview appears here rather than at the frame's tail when it
        # first shows up.
        preview_holder = tk.Frame(frame, bg=self.colors["card"])
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
            # The body box shows only the NON-table text: the preview is
            # where tables are seen, and raw pipe rows with merge markers
            # read as noise. The box still HOLDS the full body -- elide
            # hides the lines without touching the stored text.
            body_txt.tag_remove("tblhide", "1.0", "end")
            # Blank lines glued to a hidden table hide with it -- they
            # exist to separate blocks in the STORED text, and keeping
            # them visible left the remaining text full of gaps. A blank
            # line between two runs of text is left alone.
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
                # A caret inside hidden text would edit a table row
                # invisibly; park it at the end, after a visible newline.
                # ONLY when it actually sits in hidden text: parking it
                # unconditionally yanked the caret to the end after every
                # keystroke, scattering mid-text edits to the tail.
                last_line = body_txt.get("end-1c linestart", "end-1c")
                from noteorganizer.core import tables as core_tables
                if core_tables.is_table_row(last_line):
                    body_txt.insert("end", "\n")
                if "tblhide" in body_txt.tag_names("insert"):
                    body_txt.mark_set("insert", "end")
            if blocks and not preview_row.winfo_ismapped():
                preview_lbl.pack(fill="x", pady=(4, 0))
                preview_row.pack(anchor="w", pady=(0, 2))
            elif not blocks and preview_row.winfo_ismapped():
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

        def paste_and_preview(_e=None):
            # One combined handler: the table-aware paste returns "break"
            # (stopping every later binding), so the preview refresh is
            # scheduled FIRST -- after_idle runs it once the pasted text
            # has actually landed, whichever path handled it.
            pop.after_idle(refresh_preview)
            return self._paste_table_aware(body_txt)

        # A click in the box can land the caret INSIDE the elided table
        # text (a table-only body looks empty, so anywhere the user
        # clicks resolves into hidden rows). Typing there glued letters
        # onto an invisible pipe row: the row stopped being a table row,
        # the block broke, and its leftover rows surfaced in the box as
        # bare pipe lines. The caret is herded to visible text BEFORE a
        # character lands, and deletions refuse to eat hidden text.
        def caret_to_visible(_e=None):
            try:
                if "tblhide" in body_txt.tag_names("insert"):
                    body_txt.mark_set("insert", "end")
            except tk.TclError:
                pass

        def guard_backspace(_e=None):
            # Deleting the newline that parts visible text from a hidden
            # block glues the text onto an invisible pipe row -- the
            # newline itself sits OUTSIDE the tag, so the char behind it
            # is what gives the danger away.
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
        tk.Label(frame, text="Checklist", bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(6, 0))
        tpl_cl_list_frame = tk.Frame(frame, bg=self.colors["sidebar"])
        tpl_cl_list_frame.pack(fill="x", pady=(0, 2))

        def render_tpl_checklist():
            for w in tpl_cl_list_frame.winfo_children():
                w.destroy()
            if not tpl_checklist:
                tk.Label(tpl_cl_list_frame, text="No items yet — type below and press Enter.",
                         bg=self.colors["sidebar"], fg=self.colors["subtext"],
                         font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=6, pady=4)
                return
            for item in tpl_checklist:
                row = tk.Frame(tpl_cl_list_frame, bg=self.colors["sidebar"])
                row.pack(fill="x", padx=4, pady=1)
                v = tk.IntVar(value=1 if item.get("done") else 0)

                def on_tog(it=item, var=v, lb=None):
                    it["done"] = bool(var.get())
                    render_tpl_checklist()

                cb = tk.Checkbutton(row, variable=v, command=on_tog,
                                    bg=self.colors["sidebar"], activebackground=self.colors["sidebar"],
                                    selectcolor=self.colors["card"], bd=0, highlightthickness=0)
                cb.pack(side="left")
                lbl = tk.Label(row, text=item.get("text", ""), bg=self.colors["sidebar"],
                               fg=self.colors["subtext"] if item.get("done") else self.colors["text"],
                               font=("Segoe UI", 9), anchor="w", wraplength=320, justify="left")
                lbl.pack(side="left", fill="x", expand=True, padx=(2, 4))

                def do_del(it=item):
                    try:
                        tpl_checklist.remove(it)
                    except ValueError:
                        pass
                    render_tpl_checklist()

                tk.Button(row, text="🗑", command=do_del, relief="flat", cursor="hand2",
                          bg=self.colors["sidebar"], fg=self.colors["danger"],
                          font=("Segoe UI", 8), bd=0).pack(side="right")

        render_tpl_checklist()

        cl_add_row = tk.Frame(frame, bg=self.colors["card"])
        cl_add_row.pack(fill="x", pady=(0, 6))
        cl_add_var = tk.StringVar()
        cl_entry = tk.Entry(cl_add_row, textvariable=cl_add_var, relief="flat",
                            font=("Segoe UI", 10), bg=self.colors["sidebar"],
                            fg=self.colors["text"], insertbackground=self.colors["text"])
        cl_entry.pack(side="left", fill="x", expand=True, ipady=3)
        self._add_paste_menu(cl_entry)

        def add_tpl_item():
            text = cl_add_var.get().strip()
            if not text:
                return
            tpl_checklist.append({"text": text, "done": False})
            cl_add_var.set("")
            render_tpl_checklist()
            cl_entry.focus_set()

        cl_entry.bind("<Return>", lambda e: add_tpl_item())
        tk.Button(cl_add_row, text="＋ Add", command=add_tpl_item,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(side="left", padx=(6, 0), ipadx=8, ipady=2)

        tk.Label(frame, text="Category", bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(4, 0))
        cat_var = tk.StringVar(value=data["category"] if data["category"] in CATEGORY_COLORS else "General")
        cat_menu = self._build_themed_dropdown(
            frame, cat_var, lambda: list(CATEGORY_COLORS.keys()),
            on_change=lambda v: None,
            dot_color_fn=lambda v: CATEGORY_COLORS.get(v), width_chars=16,
            nested=True)
        cat_menu.pack(fill="x", pady=(0, 6))

        def collect():
            return normalize_template({
                "name": name_var.get(),
                "title": title_var.get(),
                "body": body_txt.get("1.0", "end").rstrip("\n"),
                "comments": comments_txt.get("1.0", "end").rstrip("\n"),
                "category": cat_var.get(),
                "checklist": [dict(it) for it in tpl_checklist],
                # The dialog cannot edit these, but it must not lose
                # them either: a template saved from the editor carries
                # its formatting, and saving it here used to wipe it.
                "formatting": data.get("formatting", []),
                "paragraphs": data.get("paragraphs", []),
            })

        def save():
            # Checked on the RAW field: normalize defaults an empty name
            # to "Untitled template", so checking after it made this
            # guard unreachable -- the junk rows named exactly that in
            # the templates list were its silent proof.
            if not name_var.get().strip():
                self.show_warning("Name needed", "Give the template a name.", parent=pop)
                return
            new_tpl = collect()
            # A colliding name never overwrites (or duplicates) silently:
            # saving a NEW template under a taken name, or renaming one
            # onto a neighbour, both ask first.
            taken_name = new_tpl.get("name")
            others = [t for t in self.templates
                      if t is not tpl and t.get("name") == taken_name]
            if others:
                if not self.ask_yes_no(
                        "Template name taken",
                        f"You already have a template named “{taken_name}”.\n\n"
                        "Replace the old template with this one?\n"
                        "Choose No to give this one another name.",
                        parent=pop):
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
            self._dismiss_mini_popup()
            redraw()
            self._render_statistics()

        btns = tk.Frame(frame, bg=self.colors["card"])
        btns.pack(fill="x", pady=(4, 0))
        tk.Button(btns, text="Save", command=save, relief="flat", cursor="hand2",
                  bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold")
                  ).pack(side="left", ipadx=10, ipady=3)
        tk.Button(btns, text="Cancel", command=self._dismiss_mini_popup, relief="flat",
                  cursor="hand2", bg=self.colors["sidebar"], fg=self.colors["text"],
                  font=("Segoe UI", 9)).pack(side="left", padx=(6, 0), ipadx=10, ipady=3)

        # A click elsewhere closes the editor like any dropdown -- but
        # never at the price of typed work: when something was changed, a
        # small ask decides whether the change is saved first. Unchanged
        # dialogs just close, no ceremony.
        confirm_state = {"asking": False}
        # Dirty is measured against what the very same collector reads at
        # open time -- comparing against the raw template tripped on
        # normalization details (a trailing newline, filled defaults).
        opened_snapshot = collect()

        def confirm_dismiss():
            if confirm_state["asking"]:
                return False              # the ask itself is on screen
            if collect() == opened_snapshot:
                return True               # nothing changed: just close
            confirm_state["asking"] = True
            try:
                wants_save = self.ask_yes_no(
                    "Save changes?",
                    "You changed this template. Save the changes "
                    "before closing?", icon="question", default="yes")
            finally:
                confirm_state["asking"] = False
            if wants_save:
                save()                    # dismisses itself on success
                # A failed save (no name) keeps the dialog for fixing.
                return False
            return True

        pop._confirm_dismiss = confirm_dismiss
        if anchor_widget is not None and anchor_widget.winfo_exists():
            self._place_dropdown_popup(pop, anchor_widget)
        else:
            self._place_dropdown_popup(
                pop, None,
                anchor_xy=(self.winfo_rootx() + self.winfo_width() // 2,
                          self.winfo_rooty() + self.winfo_height() // 3))
        pop.bind("<Escape>",
                 lambda e: (self._dismiss_mini_popup()
                            if confirm_dismiss() else None))

    def _build_trash_row(self, parent, entry, redraw):
        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", pady=3)

        left = tk.Frame(row, bg=self.colors["card"])
        left.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        title = (entry.get("title") or "").strip() or "(untitled)"
        tk.Label(left, text=title[:42], bg=self.colors["card"], fg=self.colors["text"],
                 font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x")
        # Show when it was deleted and how long remains.
        meta = entry.get("deleted_at", "")
        remaining = self._days_left_in_trash(meta)
        sub = f"deleted {meta[:10]}" if meta else "deleted"
        if remaining is not None:
            sub += f" · {remaining} day(s) left"
        tk.Label(left, text=sub, bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 8), anchor="w").pack(fill="x")

        def restore():
            self._restore_from_trash(entry)
            redraw()

        def delete_forever():
            if self.ask_yes_no(
                "Delete permanently",
                f"Permanently delete “{title}”? This can't be undone.",
                parent=row, icon="warning", default="no"
            ):
                _delete_attachment_files([entry])
                self.trash = [e for e in self.trash if e is not entry]
                save_trash(self.trash)
                redraw()

        tk.Button(row, text="Delete", command=delete_forever, relief="flat",
                  cursor="hand2", bg=self.colors["danger"], fg="white",
                  font=("Segoe UI", 8, "bold")).pack(side="right", padx=(2, 8), ipadx=4, ipady=1)
        tk.Button(row, text="Restore", command=restore, relief="flat",
                  cursor="hand2", bg=self.colors["accent"], fg="white",
                  font=("Segoe UI", 8, "bold")).pack(side="right", padx=2, ipadx=4, ipady=1)

    def _build_settings_trash_panel(self, parent):
        self._trash_subtitle_lbl = self._settings_subtitle(
            parent,
            f"Kept for {trash_retention_days()} days, then removed automatically.")

        card = self._settings_card(parent)
        row = self._card_row(
            card, "Keep deleted notes for",
            "How long the trash holds a note before removing it for good. "
            "A change applies from the next startup's cleanup.",
            first=True)
        self.trash_retention_var = tk.StringVar(
            value=f"{trash_retention_days()} days")

        def set_retention(value):
            try:
                days = int(value.split()[0])
            except (ValueError, IndexError):
                return
            save_setting("trash_retention_days", days)
            # The subtitle above quotes the window -- keep it honest
            # without rebuilding the panel under the dropdown's feet.
            try:
                self._trash_subtitle_lbl.config(
                    text=f"Kept for {trash_retention_days()} days, "
                         "then removed automatically.")
            except (tk.TclError, AttributeError):
                pass

        self._build_themed_dropdown(
            row, self.trash_retention_var,
            ["7 days", "14 days", "30 days", "60 days", "90 days"],
            set_retention, width_chars=10
        ).pack(side="right")
        wrap = tk.Frame(parent, bg=self.colors["card"], height=240)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 100, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        rows = tk.Frame(canvas, bg=self.colors["card"])
        rows.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=rows, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        # Paginated: rendering all 600+ rows (and recursively binding the
        # mousewheel across every one of them) at once was measurably slow —
        # over a second and a half with 600 entries, and this only grows over
        # time since trash accumulates. Showing the most recent batch first,
        # with a button to reveal more, keeps opening the panel fast
        # regardless of how large the trash gets.
        #
        # 25 rather than 50 since Settings started showing one section at a
        # time. A page of 50 costs about 585ms to open with a full trash, and
        # profiling puts ~95% of that in Tk laying the widgets out, not in any
        # code here — so the only real lever is how many rows get painted up
        # front. 25 halves it to about 405ms. This used to be hidden: the old
        # accordion re-opened the panel on every other click, so half the
        # time it was cheaply closing rather than rebuilding.
        PAGE_SIZE = self.TRASH_PAGE_SIZE
        shown_count = {"n": PAGE_SIZE}

        def redraw():
            for w in rows.winfo_children():
                w.destroy()
            if not self.trash:
                tk.Label(rows, text="Trash is empty.", bg=self.colors["card"],
                         fg=self.colors["subtext"], font=("Segoe UI", 10)).pack(pady=20)
                self._bind_wheel_tree(rows, lambda e: self._panel_or_page_wheel(canvas, e))
                return
            ordered = sorted(self.trash, key=lambda e: e.get("deleted_at", ""), reverse=True)
            visible = ordered[:shown_count["n"]]
            for entry in visible:
                self._build_trash_row(rows, entry, redraw)
            remaining = len(ordered) - len(visible)
            if remaining > 0:
                def show_more():
                    shown_count["n"] += PAGE_SIZE
                    redraw()
                tk.Button(rows, text=f"Show {min(remaining, PAGE_SIZE)} more "
                                     f"({remaining} not shown)",
                          command=show_more, relief="flat", cursor="hand2",
                          bg=self.colors["sidebar"], fg=self.colors["text"],
                          font=("Segoe UI", 8)).pack(fill="x", pady=(6, 2), ipady=4)
            self._bind_wheel_tree(rows, lambda e: self._panel_or_page_wheel(canvas, e))
        redraw()

        def empty_trash():
            if not self.trash:
                return
            if self.ask_yes_no(
                "Empty trash",
                f"Permanently delete all {len(self.trash)} note(s) in the trash? "
                "This can't be undone.", icon="warning", default="no"
            ):
                _delete_attachment_files(self.trash)
                self.trash = []
                save_trash(self.trash)
                shown_count["n"] = PAGE_SIZE
                redraw()

        self._settings_big_button(
            parent, "Empty trash", empty_trash, kind="danger"
        ).pack(fill="x", padx=12, pady=(4, 10), ipady=5)

    def _build_settings_duplicates_panel(self, parent):
        self._settings_subtitle(
            parent,
            "Notes with the same title, text, comments and category (ignoring "
            "case, spacing, date and color). Tick the copies you want to "
            "remove — the rest are kept.")
        groups = find_duplicate_groups(self.notes)
        if not groups:
            tk.Label(parent, text="No duplicates found — every note is unique. 🎉",
                     font=("Segoe UI", 10), bg=self.colors["card"], fg=self.colors["subtext"],
                     wraplength=520, justify="left").pack(padx=12, pady=(0, 12), anchor="w")
            return

        total_dupes = sum(len(g) - 1 for g in groups)
        tk.Label(parent, text=f"Found {len(groups)} group(s), up to {total_dupes} note(s) "
                              "could be removed.",
                 font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["subtext"],
                 wraplength=520, justify="left").pack(padx=12, pady=(0, 2), anchor="w")
        tk.Label(parent, text="Tick the copies you want to remove. Keep as many as "
                              "you like — anything left unticked stays. Attachments "
                              "from removed copies are merged into a kept one.",
                 font=("Segoe UI", 8, "italic"), bg=self.colors["card"],
                 fg=self.colors["accent"], wraplength=520, justify="left"
                 ).pack(padx=12, pady=(0, 8), anchor="w")

        wrap = tk.Frame(parent, bg=self.colors["card"], height=260)
        wrap.pack(fill="x", padx=12, pady=(0, 0))
        wrap.pack_propagate(False)
        self._resize_handles_pending = getattr(self, "_resize_handles_pending", [])
        self._resize_handles_pending.append((wrap, 120, 800))
        canvas = tk.Canvas(wrap, bg=self.colors["card"], highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=self.colors["card"])
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        cwin = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", self._canvas_width_sync(canvas, cwin))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._active_panel_canvas = canvas

        del_vars = []  # (var, note, group) across all groups
        all_group_vars = []  # list of per-group var lists, for the "clean up everything" button
        for group in groups:
            box = tk.Frame(inner, bg=self.colors["sidebar"])
            box.pack(fill="x", pady=5, padx=2)
            title = (group[0].get("title") or "").strip() or "(untitled)"
            tk.Label(box, text=f"“{title[:36]}” — {len(group)} copies",
                     font=("Segoe UI", 10, "bold"), bg=self.colors["sidebar"],
                     fg=self.colors["text"], anchor="w").pack(fill="x", padx=10, pady=(8, 2))

            hints = []
            if any(n.get("attachments") for n in group) and \
               len({bool(n.get("attachments")) for n in group}) > 1:
                hints.append("attachments")
            if hints:
                tk.Label(box, text=f"↳ differing {' & '.join(hints)} will be merged "
                                   "into a kept copy",
                         font=("Segoe UI", 7, "italic"), bg=self.colors["sidebar"],
                         fg=self.colors["accent"], anchor="w", wraplength=460, justify="left"
                         ).pack(fill="x", padx=14, pady=(0, 2))

            group_vars = []
            for note in group:
                created = note.get("created", "")
                updated = note.get("updated", "")
                meta = f"created {created[:10]}" if created else ""
                if updated and updated != created:
                    meta += f" · updated {updated[:10]}"
                var = tk.IntVar(value=0)
                del_vars.append((var, note, group))
                group_vars.append(var)
                cb = tk.Checkbutton(
                    box, text=f"Delete this copy   ({meta})" if meta else "Delete this copy",
                    variable=var,
                    bg=self.colors["sidebar"], fg=self.colors["text"],
                    selectcolor=self.colors["card"],
                    activebackground=self.colors["sidebar"], activeforeground=self.colors["text"],
                    font=("Segoe UI", 8), anchor="w")
                cb.pack(fill="x", padx=20)
                self._attach_dup_preview(cb, note)

            # Shortcut: tick every copy except the first (old "keep one" behavior).
            def check_all_but_first(gv=group_vars):
                for i, v in enumerate(gv):
                    v.set(0 if i == 0 else 1)

            def clear_group(gv=group_vars):
                for v in gv:
                    v.set(0)

            all_group_vars.append(group_vars)

            btn_row = tk.Frame(box, bg=self.colors["sidebar"])
            btn_row.pack(fill="x", padx=10, pady=(2, 8))
            tk.Button(btn_row, text="Tick all but first", command=check_all_but_first,
                      bg=self.colors["card"], fg=self.colors["text"], relief="flat",
                      font=("Segoe UI", 8), cursor="hand2"
                      ).pack(side="left", ipadx=6, ipady=2)
            tk.Button(btn_row, text="Clear", command=clear_group,
                      bg=self.colors["card"], fg=self.colors["subtext"], relief="flat",
                      font=("Segoe UI", 8), cursor="hand2"
                      ).pack(side="left", padx=(6, 0), ipadx=6, ipady=2)

        self._bind_wheel_tree(inner, lambda e: self._panel_or_page_wheel(canvas, e))

        def do_cleanup():
            self._cleanup_selected_duplicates(
                del_vars, parent,
                refresh=lambda: self._reopen_dup_panel(), announce=True)

        def clean_up_everything():
            # Same "keep first, remove the rest" shortcut as each group's own
            # button, just applied to every group in one click instead of
            # working through them one at a time.
            for gv in all_group_vars:
                for i, v in enumerate(gv):
                    v.set(0 if i == 0 else 1)
            do_cleanup()

        if len(groups) > 1:
            tk.Button(parent, text=f"🧹✨  Clean up ALL {len(groups)} groups (keep first in each)",
                      command=clean_up_everything,
                      bg=self.colors["sidebar"], fg=self.colors["text"], relief="flat",
                      font=("Segoe UI", 9, "bold"), cursor="hand2"
                      ).pack(fill="x", padx=12, pady=(4, 4), ipady=5)

        tk.Button(parent, text="🧹  Move ticked duplicates to trash", command=do_cleanup,
                  bg=self.colors["accent"], fg="white", relief="flat",
                  font=("Segoe UI", 10, "bold"), cursor="hand2"
                  ).pack(fill="x", padx=12, pady=(4, 10), ipady=6)

    def _reopen_dup_panel(self):
        """Rebuild the duplicates panel in place after a cleanup."""
        panel = getattr(self, "settings_duplicates_panel", None)
        if panel is None:
            return
        for w in panel.winfo_children():
            w.destroy()
        self._build_settings_duplicates_panel(panel)
        if not panel.winfo_ismapped():
            panel.pack(fill="x", padx=16, pady=(0, 12))

    def _build_theme_picker(self, parent):
        """The theme swatches for the current mode, as in the reference design.

        Four across, each a bordered tile holding a small preview of that
        theme -- its own sidebar strip and three text lines painted in its own
        colours -- with the name beneath and a tick badge on the selected one.
        Switching light/dark swaps which set is shown.
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
        CARD_W = 132
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

            W, H = 116, 46
            sw = tk.Canvas(cell, width=W, height=H, highlightthickness=0, bd=0,
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

            lbl = tk.Label(cell, text=THEME_LABELS.get(name, name),
                           bg=self._surface(), cursor="hand2",
                           fg=(self.colors["accent"] if active
                               else self.colors["subtext"]),
                           font=("Segoe UI", 8, "bold"))
            lbl.pack(pady=(0, 8))

            if active:
                badge = tk.Canvas(cell, width=16, height=16, highlightthickness=0,
                                  bd=0, bg=self._surface())
                badge.place(relx=1.0, rely=0.0, x=-4, y=4, anchor="ne")
                badge.create_oval(0, 0, 15, 15, fill=self.colors["accent"],
                                  outline=self.colors["accent"])
                badge.create_line(4, 8, 6.5, 10.5, 11.5, 5,
                                  fill="white", width=1.8)

            for w in (edge, cell, sw, lbl):
                w.bind("<Button-1>", lambda e, n=name: self.set_theme(n))

        # Each preview canvas otherwise swallows the mouse wheel itself (a
        # plain Tk quirk: Canvas has a built-in default scroll binding, so it
        # never lets the event reach the Settings page underneath) -- forward
        # it to the page's own scroll instead, the same pattern used for
        # every other Settings panel.
        def _theme_picker_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        self._bind_wheel_tree(parent, _theme_picker_wheel)

        # Re-wrap when the column's width changes. Only an actual change in
        # the number of columns rebuilds, so ordinary Configure noise -- which
        # fires for height changes too -- doesn't churn the cards.
        def _rewrap(event):
            fits = max(1, min(per_group, max(event.width, 1) // CARD_W))
            balanced = -(-per_group // (-(-per_group // fits)))
            if balanced != getattr(self, "_theme_picker_cols", None):
                self._build_theme_picker(parent)
        parent.bind("<Configure>", _rewrap)

        self._refresh_theme_picker = lambda: self._build_theme_picker(parent)

    def show_settings_page(self):
        """Show the Settings page in place of the Notes/Calendar notebook.
        Settings lives outside the tab strip on purpose — see the comment
        where self.settings_page is created."""
        # A popup anchored to the page being swapped out would keep
        # floating over the new one -- the Settings dropdown was still on
        # screen back in the editor.
        self._dismiss_mini_popup()
        self._catch_up_deferred_refresh()
        self.notebook.pack_forget()
        self.settings_page.pack(fill="both", expand=True)
        self._render_statistics()

    def hide_settings_page(self):
        self._dismiss_mini_popup()
        """Return from Settings to the Notes/Calendar notebook."""
        self.settings_page.pack_forget()
        self.notebook.pack(fill="both", expand=True)

    # ---------- Settings tab ----------
    # One row per section: nav order, the builder that fills the pane, and
    # whether it is cheap enough to build up front. This list is the single
    # source of truth for the navigation — adding a section means adding a row.
    #
    # The four that used to hide behind an "expand" button (categories,
    # templates, trash, duplicates) are ordinary sections now. That removes a
    # whole interaction layer: previously you scrolled to a section, clicked to
    # expand its panel, then closed it again.
    # The keys are an API: the QA suite selects sections by them and reads
    # ``settings_<key>_panel`` attributes, so they stay put even when a label
    # changes. "name" is now shown as "General" because it carries the
    # greeting settings rather than only a name field.
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

    # Nine entries in one flat run mixed four different kinds of thing:
    # preferences, managers for content you made, tools that delete things,
    # and read-only information. Grouping is kept separate from the tuple
    # above so section keys and their order stay independent of how the nav
    # happens to be arranged.
    SETTINGS_GROUPS = (
        ("General", ("name", "appearance")),
        ("Content", ("categories", "templates")),
        ("Data",    ("backup", "trash", "duplicates")),
        ("More",    ("statistics", "shortcuts", "about")),
    )

    # The nav is a fixed width. It does not need a narrow breakpoint: the app
    # holds its whole content area to at least SIDEBAR_WIDTH + EDITOR_MIN_WIDTH
    # (900px) and scrolls horizontally below that rather than reflowing -- see
    # _on_main_canvas_configure in note_organizer.py -- and Settings sits
    # inside that same canvas, so its pane never gets narrower than ~890px.
    SETTINGS_NAV_WIDTH = 240
    # How many trash rows are painted before "Show more". A tuning knob, not
    # a feature: see the note in _build_settings_trash_panel for the numbers.
    TRASH_PAGE_SIZE = 25
    # Content stops growing past this; the space left on the right is
    # deliberate, so a short form is not stretched across the whole window.
    SETTINGS_CONTENT_MAX = 640

    def build_settings_tab(self, parent):
        """Settings as a navigation column plus a content pane.

        Sections used to be stacked in one long scrolling column, four of them
        hiding an expandable panel behind a button. Everything competed for the
        same vertical space, and section titles sat left while their buttons sat
        centred, so reading the page meant zig-zagging.

        Now one section shows at a time, picked from the list on the left, and
        everything inside it lines up against the same left edge.
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
        mark = tk.Canvas(brand, width=26, height=26, highlightthickness=0, bd=0,
                         bg=self.colors["sidebar"])
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

        # --- Back to Notes, in the rail rather than in its own bar above ---
        # It used to sit in a strip across the top of the whole page, which
        # spent a band of vertical space on every section to hold one control.
        # The foot is claimed before the scrolling area, so it reserves its
        # height rather than being pushed off the bottom by a list that
        # expands -- the same ordering the note sidebar uses for its own
        # bottom zone.
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
        back_ico = tk.Canvas(back_row, width=14, height=14, highlightthickness=0,
                             bd=0, bg=self.colors["sidebar"], cursor="hand2")
        back_ico.pack(side="left", padx=(8, 6), pady=8)
        back_ico.create_line(12, 7, 3, 7, fill=self.colors["subtext"], width=1.6)
        back_ico.create_line(6.5, 3.5, 3, 7, 6.5, 10.5,
                             fill=self.colors["subtext"], width=1.6)
        back_lbl = tk.Button(
            back_row, text="Back to Notes", anchor="w", relief="flat", bd=0,
            highlightthickness=0, font=("Segoe UI", 9, "bold"), cursor="hand2",
            bg=self.colors["sidebar"], fg=self.colors["subtext"],
            activebackground=self.colors["card"],
            activeforeground=self.colors["text"],
            command=self.hide_settings_page)
        back_lbl.pack(side="left", fill="x", expand=True)
        for w in (back_row, back_ico):
            w.bind("<Button-1>", lambda _e: self.hide_settings_page())

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


        # Each entry is a rail plus a button, not just a button: a tk.Button
        # cannot draw a border on one side only, and the selected state reads
        # far more quietly as a thin accent bar beside a tinted row than as a
        # fully saturated block. The rail is a 3px Frame that is simply the
        # same colour as the sidebar when the entry isn't selected.
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

        # The wheel has to work over the entries themselves, not only over
        # the canvas behind them, since the entries cover it completely.
        # _bind_wheel_tree_if_unbound skips anything with a binding of its
        # own, so nothing that already scrolls loses its handler.
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
            # event.widget can arrive as a bare STRING: Tk hands the path
            # name when the clicked widget was destroyed and rebuilt (a
            # theme switch does exactly that) before the event got here.
            # Calling focus_set() on that string was the intermittent
            # "something went wrong" while flipping themes.
            target = event.widget
            if not hasattr(target, "focus_set"):
                return
            if isinstance(focused, (tk.Entry, tk.Text)) and target is not focused:
                try:
                    target.focus_set()
                except tk.TclError:
                    pass
        self.bind("<Button-1>", _clear_settings_field_focus, add="+")

        # A frame per section, all created now so callers can reach them (the
        # QA suite reads self.stats_frame straight after opening Settings). The
        # light ones are filled immediately; the four heavy panels build their
        # contents when first selected, as they always have -- the trash list
        # alone can run to hundreds of rows.
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

        # The reference marks the selected entry with a short bar beside it --
        # 3px wide, 16px tall, vertically centred -- not a rule running the
        # full height of the row. A canvas gives that without a nest of
        # spacer frames, and lets the ends be rounded on the outer edge.
        rail = tk.Canvas(row, width=3, height=34, highlightthickness=0, bd=0,
                         bg=self.colors["sidebar"])
        rail.pack(side="left", fill="y")

        icon = tk.Canvas(row, width=self.NAV_ICON_SIZE, height=self.NAV_ICON_SIZE,
                         highlightthickness=0, bd=0, bg=self.colors["sidebar"],
                         cursor="hand2")
        icon.pack(side="left", padx=(9, 0))
        # The glyph is decoration; the button beside it is the control, so
        # clicking the glyph has to reach the same place.
        icon.bind("<Button-1>", lambda _e, k=key: self.toggle_settings_panel(k))

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

    # Each glyph is drawn as plain geometry in a 16x16 box rather than set as
    # a character or loaded as an image. That is what lets it take the theme's
    # colour: emoji are fixed-colour bitmaps and would stay the same on all
    # eight themes, and a PNG would need one copy per theme or a tinting pass.
    # Shapes just get redrawn in whatever colour is current.
    NAV_ICON_SIZE = 17

    def _draw_icon(self, canvas, kind, color, size=None):
        """(Re)draw one glyph in ``color``.

        Shapes are laid out in a 16-unit box and scaled at the end, so one
        definition serves the 16px nav and the smaller row-action buttons.
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
        elif kind == "plus":                    # add
            canvas.create_line(8, 3.5, 8, 12.5, fill=color, width=1.8,
                               tags="glyph")
            canvas.create_line(3.5, 8, 12.5, 8, fill=color, width=1.8,
                               tags="glyph")

        if size and size != 16:
            canvas.scale("glyph", 0, 0, size / 16.0, size / 16.0)

    # ---- the small design system the panels are built from --------------
    #
    # Three surface steps and one border colour, all derived from the theme
    # rather than hardcoded, so every one of the eight themes gets a
    # consistent set. "surface" is the card, "inset" is a well *inside* a
    # card (inputs, preview strips), and the border is what gives a card an
    # edge now that corners stay square.
    def _surface(self, kind="card"):
        """One of the reference design's three surface steps.

        The order matters and is the same in both modes: the page ground is
        furthest from the text colour, a card sits one step toward it, and a
        well *inside* a card sits one step further again. On a dark theme
        that reads as progressively lighter, on a light theme progressively
        darker -- which is why this blends toward ``text`` rather than
        hardcoding a direction.
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
            tk.Label(text_col, text=hint, font=("Segoe UI", 9),
                     bg=self._surface(), fg=self.colors["subtext"], anchor="w",
                     justify="left", wraplength=self.SETTINGS_CONTENT_MAX - 260
                     ).pack(fill="x", pady=(2, 0))
        control = tk.Frame(row, bg=self._surface())
        control.pack(side="right", padx=(16, 0))
        return control

    def _add_row(self, parent, text, command):
        """The "+ Add category" affordance: accent text, not a filled block.

        A full-width saturated button for "add another one" outweighed every
        real control on the page.
        """
        row = tk.Frame(parent, bg=self._surface(), cursor="hand2")
        row.pack(fill="x", pady=(8, 0))
        icon = self._icon_button(row, "plus", bg_key="card")
        icon.pack(side="left")
        lbl = tk.Label(row, text=text, font=("Segoe UI", 10, "bold"),
                       bg=self._surface(), fg=self.colors["accent"], anchor="w",
                       cursor="hand2")
        lbl.pack(side="left", padx=(2, 0))
        for w in (row, lbl, icon):
            w.bind("<Button-1>", lambda _e: command())
        self._draw_icon(icon, "plus", self.colors["accent"],
                        size=self.ROW_ICON_SIZE)
        icon.move("glyph", 5, 5)
        return row

    def _note_banner(self, parent, text):
        """An informational strip -- retention notices and the like."""
        bg = self._surface("inset")
        wrap = tk.Frame(parent, bg=bg)
        wrap.pack(fill="x", pady=(0, 12))
        ico = tk.Canvas(wrap, width=16, height=16, highlightthickness=0, bd=0, bg=bg)
        ico.pack(side="left", padx=(12, 8), pady=11)
        self._draw_icon(ico, "about", self.colors["accent"], size=16)
        tk.Label(wrap, text=text, font=("Segoe UI", 9), bg=bg,
                 fg=self.colors["subtext"], anchor="w", justify="left",
                 wraplength=self.SETTINGS_CONTENT_MAX - 90
                 ).pack(side="left", fill="x", expand=True, pady=10, padx=(0, 12))
        return wrap

    def _text_button(self, parent, text, command, kind="normal"):
        """A button sized to its label rather than stretched across the pane."""
        if kind == "danger":
            fg, border = self.colors["danger"], self.colors["danger"]
            bg = self._surface()
            hover = self._blend(bg, self.colors["danger"], 0.14)
        elif kind == "primary":
            fg, border = "white", self.colors["accent"]
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
        b.bind("<Enter>", lambda _e: b.configure(bg=hover))
        b.bind("<Leave>", lambda _e: b.configure(bg=bg))
        return b

    ROW_ICON_SIZE = 15

    def _icon_button(self, parent, kind, command=None, danger=False, bg_key="card"):
        """A small drawn-glyph button for a list row.

        Replaces the emoji these rows used to use. Emoji are fixed-colour
        bitmaps, so a red wastebasket stayed the same shade of red on all
        eight themes and read as clipart against a flat interface; the
        pencil beside it was a monochrome dingbat that *did* recolour, so
        the two never matched. Drawn shapes give one consistent set that
        follows whatever theme is on.

        Passing no ``command`` makes it a plain indicator (the padlock on a
        protected category), not something clickable.
        """
        size = self.ROW_ICON_SIZE
        # Faint at rest even for destructive actions: the reference colours
        # them only on hover, so a list of rows does not read as a column of
        # red warnings before anyone has reached for anything.
        base = self.colors["subtext"]
        pad = 6
        c = tk.Canvas(parent, width=size + pad * 2, height=size + pad * 2,
                      highlightthickness=0, bd=0, bg=self.colors[bg_key],
                      cursor="hand2" if command else "")
        # A canvas has no text to search for the way a Button does, so record
        # which glyph this is. The QA scripts locate row actions by it, and it
        # keeps them from depending on how a given icon happens to be drawn.
        c._icon_kind = kind
        # The glyph is drawn from the top-left, so nudge it into the padding.
        def paint(color):
            self._draw_icon(c, kind, color, size=size)
            c.move("glyph", pad, pad)

        paint(base)
        if command is not None:
            c.bind("<Button-1>", lambda _e: command())
            hot = self.colors["danger"] if danger else self.colors["text"]
            rest_bg = self.colors[bg_key]
            hover_bg = (self._blend(rest_bg, self.colors["danger"], 0.16) if danger
                        else self._surface("inset"))

            def _on(_e):
                c.configure(bg=hover_bg)
                paint(hot)

            def _off(_e):
                c.configure(bg=rest_bg)
                paint(base)

            c.bind("<Enter>", _on)
            c.bind("<Leave>", _off)
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
        c = getattr(self, "_settings_brand_mark", None)
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
            b = tk.Canvas(inner, width=26, height=20, highlightthickness=0, bd=0,
                          bg=self.colors["sidebar"], cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda _e, m=mode: self._pick_settings_mode(m))
            self._settings_mode_buttons[mode] = b
        self._refresh_mode_toggle()

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
                fg = self.colors["accent"] if active else self.colors["subtext"]
                c.configure(bg=bg)
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
        if not getattr(self, "_settings_nav_icons", None):
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

    def _settings_section_note(self, parent, subtitle):
        """Optional explanatory line, then the frame a section builds into.

        Replaces the old ``section()`` closure. That one created its own title
        as well; titles now come from the nav list via
        :meth:`_settings_section_heading`, so there is one place deciding what
        a section is called.
        """
        if subtitle:
            self._settings_subtitle(parent, subtitle)
        holder = tk.Frame(parent, bg=self.colors["card"])
        self.track_theme(holder, bg="card")
        holder.pack(fill="x", padx=4)
        return holder

    def _settings_big_button(self, parent_frame, text, command, kind="normal"):
        """A full-width action button, left-aligned like its section.

        Three kinds. ``accent`` is the one primary action a section may have;
        ``normal`` is everything else; ``danger`` is outlined rather than
        filled -- it keeps the warning colour, which is reserved for exactly
        this, but stops a destructive action from being the heaviest thing on
        the page. Emptying the trash should be findable, not inviting.
        """
        if kind == "danger":
            b = tk.Button(parent_frame, text=text, command=command,
                          relief="solid", bd=1, font=("Segoe UI", 10, "bold"),
                          cursor="hand2", fg=self.colors["danger"],
                          bg=self.colors["card"],
                          highlightbackground=self.colors["danger"],
                          activeforeground=self.colors["danger"],
                          activebackground=self.colors["card"])
            self.track_theme(b, bg="card", fg="danger")
            hover_bg = self._blend(self.colors["card"], self.colors["danger"], 0.14)
            rest_bg = self.colors["card"]
        else:
            bg = "accent" if kind == "accent" else "sidebar"
            b = tk.Button(parent_frame, text=text, command=command, relief="flat",
                          font=("Segoe UI", 10, "bold"), cursor="hand2",
                          fg="white" if kind == "accent" else self.colors["text"])
            self.track_theme(b, bg=bg)
            if kind == "accent":
                b.configure(fg="white")
            rest_bg = self.colors[bg]
            hover_bg = (self.colors["accent_hover"] if kind == "accent"
                        else self.colors["card"])

        # Same hover convention as the rest of the app.
        b.bind("<Enter>", lambda _e, w=b, c=hover_bg: w.configure(bg=c))
        b.bind("<Leave>", lambda _e, w=b, c=rest_bg: w.configure(bg=c))
        return b

    def _build_category_row(self, parent, name, redraw):
        protected = (name == PROTECTED_CATEGORY)
        color = CATEGORY_COLORS[name]

        row = tk.Frame(parent, bg=self.colors["card"])
        row.pack(fill="x", pady=3)

        swatch = tk.Frame(row, bg=color, width=22, height=22, cursor="hand2")
        swatch.pack(side="left", padx=8, pady=8)
        swatch.pack_propagate(False)

        count = self.count_notes_in_category(name)
        name_lbl = tk.Label(
            row, text=f"{name}   ({count})", bg=self.colors["card"],
            fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w"
        )
        name_lbl.pack(side="left", fill="x", expand=True, padx=(2, 6))

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
            self._show_color_palette(swatch, CATEGORY_COLORS[name], apply_color,
                                     allow_reset=False)

        # Click the swatch itself to recolor (no separate button, no OS dialog).
        swatch.bind("<Button-1>", lambda e: recolor())

        def rename():
            def do_rename(new):
                new = new.strip()
                if not new or new == name:
                    return True
                if new in CATEGORY_COLORS:
                    self.show_warning("Already exists",
                                           f"A category named “{new}” already exists.",
                                           parent=row)
                    return False
                CATEGORY_COLORS[new] = CATEGORY_COLORS.pop(name)
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

    def _delete_category(self, name, redraw):
        """Delete a category, asking what to do with any notes it holds."""
        count = self.count_notes_in_category(name)

        if count == 0:
            if not self.ask_yes_no("Delete category",
                                       f"Delete “{name}”? It has no notes."):
                return
            CATEGORY_COLORS.pop(name, None)
            persist_categories()
            redraw()
            self.refresh_category_widgets()
            return

        # Notes exist — ask what happens to them.
        choice = self._ask_category_deletion(name, count)
        if choice is None:
            return
        if choice == "move":
            self.reassign_category_everywhere(name, PROTECTED_CATEGORY)
        elif choice == "delete_notes":
            # Move the affected notes to trash rather than destroying them.
            doomed = [n for n in self.notes if n.get("category") == name]
            self._move_notes_to_trash(doomed)
            self.notes = [n for n in self.notes
                          if n.get("category") != name]
            # Also strip overrides that point at the dead category.
            for n in self.notes:
                overrides = n.get("overrides") or {}
                for d in list(overrides):
                    if overrides[d].get("category") == name:
                        del overrides[d]

        CATEGORY_COLORS.pop(name, None)
        persist_categories()
        self.save_notes()
        redraw()
        self.refresh_category_widgets()
        self.refresh_note_list()
        self.render_calendar()
        if self.selected_note_id and not self.find_note(self.selected_note_id):
            self.new_note()

    def _ask_category_deletion(self, name, count):
        """Returns 'move', 'delete_notes', or None (cancel). Uses the in-app
        themed dialog overlay (not a separate window)."""
        return self._themed_dialog(
            "Delete category",
            f"“{name}” has {count} note(s). What should happen to them?",
            kind="warning",
            # "delete_notes" does NOT destroy anything -- it calls
            # _move_notes_to_trash, so the notes are restorable for the full
            # retention window like any other delete. The label used to say
            # "(permanent)", which was simply untrue and frightened people off
            # a safe choice -- or worse, convinced them notes were gone when
            # they were sitting in Trash.
            buttons=[("Cancel", None),
                     (f"Delete the notes too (restorable for "
                      f"{trash_retention_days()} days)", "delete_notes", "danger"),
                     (f"Move them to “{PROTECTED_CATEGORY}” (keep the notes)", "move")]
        )

    def _cleanup_selected_duplicates(self, del_vars, dlg, refresh, announce=False):
        """Move the checkbox-selected duplicates to trash. `del_vars` is a list of
        (delete_var, note, group) — a note is removed when its var is set. Within
        each group, the attachments of removed notes are merged into a
        surviving copy (the first note in that group NOT marked for deletion), so
        nothing unique is lost. If a whole group is checked, all are removed."""
        # Figure out, per group, which notes are being removed and which survive.
        by_group = {}
        for var, note, group in del_vars:
            gid = id(group)
            by_group.setdefault(gid, {"group": group, "remove": []})
            if var.get():
                by_group[gid]["remove"].append(note)

        to_trash = []
        for info in by_group.values():
            group = info["group"]
            remove = info["remove"]
            if not remove:
                continue
            survivors = [n for n in group if n not in remove]
            if survivors:
                # Merge removed notes' attachments into the first survivor.
                kept = survivors[0]
                merged_attach = list(kept.get("attachments", []))
                seen_attach = {a.get("stored_as") for a in merged_attach}
                for note in remove:
                    for a in note.get("attachments", []):
                        if a.get("stored_as") not in seen_attach:
                            merged_attach.append(a)
                            seen_attach.add(a.get("stored_as"))
                kept["attachments"] = merged_attach
            to_trash.extend(remove)

        if not to_trash:
            self.show_info(
                "Nothing selected",
                "Tick the duplicates you want to remove first.", parent=dlg)
            return
        if not self.ask_yes_no(
            "Move duplicates to trash",
            f"Move {len(to_trash)} selected note(s) to the trash? "
            f"You can restore them within {trash_retention_days()} days.",
            parent=dlg, icon="question"
        ):
            return
        trash_ids = {id(n) for n in to_trash}
        self._move_notes_to_trash(to_trash)
        self.notes = [n for n in self.notes if id(n) not in trash_ids]
        self.save_notes()
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
        name_len_vcmd = (self.register(lambda p: len(p) <= USERNAME_MAX_LEN), "%P")
        name_entry = tk.Entry(
            inner, textvariable=self.username_var, relief="flat", bd=0,
            highlightthickness=0, font=("Segoe UI", 11),
            bg=self._surface("inset"), fg=self.colors["text"],
            insertbackground=self.colors["text"],
            validate="key", validatecommand=name_len_vcmd
        )
        name_entry.pack(side="left", fill="x", expand=True, padx=(12, 6), pady=9)
        self._add_paste_menu(name_entry)

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
                              bg=self._surface(), fg=self.colors["success"],
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
                fg=self.colors["danger"] if used >= USERNAME_MAX_LEN - 3
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
            # Hard safety net: the key-by-key length check above can miss very
            # fast/held-down typing (a known Tk reliability gap under rapid
            # keystrokes), so enforce the limit again here, at the moment of
            # actually saving, regardless of how the field got too long.
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
            # Real-time correction: the per-keystroke block above can miss
            # very fast/held-down typing, so check again on every key
            # release (a plain event binding, not the special validate hook
            # that has the reliability gap) and snap back immediately if it
            # slipped past 30 -- rather than letting it grow freely and only
            # fixing it later when the name is actually saved.
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
        name_entry.bind("<Return>", lambda e: save_name())
        # No separate Save button -- the field already autosaves shortly
        # after typing stops, and immediately on Enter or clicking away.
        # No separate Save button — the field already autosaves shortly
        # after typing stops, and immediately on Enter or clicking away.

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
        # Bottom padding here rather than top padding on the card below:
        # _settings_card deliberately has none, because everywhere else a
        # card follows a subtitle. This is the one place one follows a grid
        # of swatches, which would otherwise sit right against it.
        self.theme_picker_frame.pack(fill="x", pady=(0, 20))
        self._build_theme_picker(self.theme_picker_frame)

        # The editor's own font. This is the baseline every note starts
        # from; the toolbar's Font group overrides it for a selection. Kept
        # here rather than per note deliberately -- "I want my notes bigger"
        # is a statement about reading, not about one note.
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
            "Bigger text everywhere, without reformatting a single note.")
        self.editor_font_size_var = tk.StringVar(value=str(self.editor_font_size))
        self._build_themed_dropdown(
            row, self.editor_font_size_var, [str(s) for s in FONT_SIZES],
            lambda v: self._set_editor_font(size=int(v)), width_chars=8
        ).pack(side="right")

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

    # Every combo listed here is verified against a real binding -- the
    # groups below name the widget the binding lives on, and the calendar
    # keys only act while that tab is showing (see _calendar_key's guard).
    SHORTCUT_GROUPS = (
        ("Text formatting", (
            ("Ctrl+B", "Bold the selection — or with nothing selected, "
                       "bold whatever you type next."),
            ("Ctrl+I", "Italic, the same way."),
            ("Ctrl+U", "Underline."),
            ("Ctrl+D", "Strikethrough."),
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
        ("Calendar (while the Calendar tab is showing)", (
            ("Page Up  /  Page Down", "Previous / next month."),
            ("Ctrl+Page Up  /  Ctrl+Page Down", "Previous / next year."),
            ("Home", "Jump back to today."),
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
            "Everything the keyboard can do. The formatting four are also "
            "on the note body's right-click menu.")
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
        """Version, where the data lives, and what changed."""
        self._settings_subtitle(parent, "Version info and where your notes live.")
        head = tk.Frame(parent, bg=self.colors["bg"])
        self.track_theme(head, bg="bg")
        head.pack(fill="x", pady=(0, 14))
        mark = tk.Canvas(head, width=44, height=44, highlightthickness=0, bd=0,
                         bg=self.colors["bg"])
        mark.pack(side="left", padx=(2, 12))
        self._rounded_rect(mark, 0, 0, 44, 44, 12,
                           fill=self.colors["accent"], outline=self.colors["accent"])
        mark.create_rectangle(15, 11, 29, 33, fill="white", outline="white")
        for y in (17, 22, 27):
            mark.create_line(18, y, 26, y, fill=self.colors["accent"], width=1.6)
        titles = tk.Frame(head, bg=self.colors["bg"])
        self.track_theme(titles, bg="bg")
        titles.pack(side="left", fill="x", expand=True)
        tk.Label(titles, text="Note Organizer", font=("Segoe UI", 13, "bold"),
                 anchor="w", bg=self.colors["bg"], fg=self.colors["text"]
                 ).pack(fill="x", pady=(3, 0))
        tk.Label(titles, text=f"Version {_host().APP_VERSION}",
                 font=("Consolas", 9), anchor="w",
                 bg=self.colors["bg"], fg=self.colors["subtext"]).pack(fill="x")

        card = self._settings_card(parent)
        self._field_label(card, "Where your notes are stored")
        # paths.APP_DIR, not the entry module's -- see _host()'s docstring.
        path_text = paths.APP_DIR or "(not set yet)"
        well = tk.Frame(card, bg=self._surface("inset"))
        well.pack(fill="x")
        tk.Label(well, text=path_text, font=("Consolas", 9),
                 bg=self._surface("inset"), fg=self.colors["subtext"],
                 anchor="w", justify="left",
                 wraplength=self.SETTINGS_CONTENT_MAX - 110
                 ).pack(fill="x", padx=12, pady=10)

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
