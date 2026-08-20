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

import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from datetime import datetime, timedelta, date as date_cls

from ..core.categories import CATEGORY_COLORS, persist_categories
from ..core.duplicates import find_duplicate_groups
from ..core.storage import (
    TRASH_RETENTION_DAYS,
    _delete_attachment_files,
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
)


def _host():
    """The entry-point module, imported only when actually needed.

    ``note_organizer`` imports this file to build the app class, so importing
    it back at module level would be circular. Two labels here show the app
    version and the first-launch date, which live there as module globals —
    and ``FIRST_LAUNCH_DATE`` is only filled in once ``initialise()`` runs,
    so it has to be read when the label is built, not when this file loads.
    A local import does both: it breaks the cycle and reads the current
    value.
    """
    import note_organizer
    return note_organizer


class SettingsPageMixin:
    """The Settings page for :class:`NoteOrganizer`.

    Not usable on its own — every method here reads state owned by the app
    (``self.colors``, ``self.notes``, ``self.settings_canvas`` and so on).
    """

    def toggle_settings_panel(self, which):
        """Accordion for Settings: open the requested inline panel and close any
        other. Panels replace the old pop-up dialogs for categories, trash
        and duplicates."""
        panels = {
            "templates": (getattr(self, "settings_templates_panel", None),
                          self._build_settings_templates_panel),
            "categories": (getattr(self, "settings_categories_panel", None),
                           self._build_settings_categories_panel),
            "trash": (getattr(self, "settings_trash_panel", None),
                      self._build_settings_trash_panel),
            "duplicates": (getattr(self, "settings_duplicates_panel", None),
                           self._build_settings_duplicates_panel),
        }
        target, builder = panels.get(which, (None, None))
        if target is None:
            return
        already_open = target.winfo_ismapped()
        # Close every panel first.
        for panel, _ in panels.values():
            if panel is not None and panel.winfo_ismapped():
                panel.pack_forget()
        if already_open:
            return  # it was open → now closed, done (toggle behavior)
        # Build fresh content and show it.
        for w in target.winfo_children():
            w.destroy()
        self._active_panel_canvas = None  # builder sets this if it has a scroll list
        self._resize_handles_pending = []
        builder(target)
        # Create any resize handles the builder requested, now that the canvas
        # exists — the handle overlays the target's bottom edge and is lifted on
        # top so it stays visible and doesn't repack siblings while dragging.
        for tgt, mn, mx in getattr(self, "_resize_handles_pending", []):
            h = self._add_resize_handle(tgt, min_h=mn, max_h=mx, host=target)
            h.pack(fill="x", padx=12, pady=(2, 8))
        self._resize_handles_pending = []
        target.pack(fill="x", padx=16, pady=(0, 12))
        # One wheel rule for the whole panel: if the panel has an inner scroll
        # list with overflow, scroll it; otherwise scroll the Settings page.
        # This works no matter where the cursor is over the panel.
        inner_canvas = getattr(self, "_active_panel_canvas", None)
        self._bind_wheel_tree(target, lambda e: self._panel_or_page_wheel(inner_canvas, e))

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

    def _settings_panel_header(self, parent, title, subtitle, which):
        """Common header for an inline settings panel: title + close ✕."""
        head = tk.Frame(parent, bg=self.colors["card"])
        head.pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(head, text=title, font=("Segoe UI", 12, "bold"),
                 bg=self.colors["card"], fg=self.colors["text"]).pack(side="left")
        tk.Button(head, text="✕", command=lambda: self.toggle_settings_panel(which),
                  bg=self.colors["card"], fg=self.colors["subtext"], relief="flat",
                  font=("Segoe UI", 11, "bold"), cursor="hand2").pack(side="right")
        if subtitle:
            tk.Label(parent, text=subtitle, font=("Segoe UI", 8),
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     justify="left", wraplength=520, anchor="w"
                     ).pack(fill="x", padx=12, pady=(0, 8))

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

        # --- Summary: total, then a week/month/year/older breakdown for
        # both when notes were added and last updated. Built as a grid —
        # icon, then "Added:"/"Updated:", then each of week/month/year/
        # older in its own column — rather than one big string per row.
        # The icon gets its own column specifically because 🆕 and ✏️
        # aren't the same rendered width, so if the icon and label shared
        # a column, "Added:" and "Updated:" themselves would start at
        # different x positions even though the column as a whole lined
        # up. Splitting it out means every column — icon, label, and each
        # week/month/year/older segment — lines up independently between
        # the two rows, regardless of font/DPI. ---
        tk.Label(
            self.stats_frame, text=f"{total} notes",
            font=("Segoe UI", 9, "bold"), bg=self.colors["card"],
            fg=self.colors["text"], anchor="w"
        ).pack(fill="x", pady=(0, 4))

        breakdown = tk.Frame(self.stats_frame, bg=self.colors["card"])
        breakdown.pack(fill="x", pady=(0, 10))
        stat_font = tkfont.Font(family="Segoe UI", size=9)
        rows_data = [
            ("🆕", "Added:", added_week, added_month, added_year, added_older),
            ("✏️", "Updated:", updated_week, updated_month, updated_year, updated_older),
        ]
        icon_width = max(stat_font.measure(rows_data[0][0]),
                          stat_font.measure(rows_data[1][0])) + 6
        breakdown.grid_columnconfigure(0, minsize=icon_width)
        label_width = max(stat_font.measure(rows_data[0][1]),
                           stat_font.measure(rows_data[1][1])) + 10
        breakdown.grid_columnconfigure(1, minsize=label_width)

        segment_labels = ["this week", "this month", "this year", "older"]
        for seg_idx, seg_label in enumerate(segment_labels):
            col = seg_idx + 2
            texts = [f"{rows_data[0][seg_idx + 2]} {seg_label}",
                     f"{rows_data[1][seg_idx + 2]} {seg_label}"]
            col_width = max(stat_font.measure(t) for t in texts) + 16
            breakdown.grid_columnconfigure(col, minsize=col_width)

        for r, (icon, label_text, week, month, year, older) in enumerate(rows_data):
            tk.Label(breakdown, text=icon, font=("Segoe UI", 9),
                     bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                     ).grid(row=r, column=0, sticky="w")
            tk.Label(breakdown, text=label_text, font=("Segoe UI", 9),
                     bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                     ).grid(row=r, column=1, sticky="w")
            for seg_idx, (value, seg_label) in enumerate(
                    zip((week, month, year, older), segment_labels)):
                tk.Label(breakdown, text=f"{value} {seg_label}",
                         font=("Segoe UI", 9), bg=self.colors["card"],
                         fg=self.colors["text"], anchor="w"
                         ).grid(row=r, column=seg_idx + 2, sticky="w")

        # --- A few standalone counts: templates and checklists are their
        # own things (a template can be reused across many notes; a
        # checklist only ever lives inside the one note it's on), so these
        # count the things themselves, not how many notes reference them.
        # "Deleted" counts what's currently in Trash right now, not an
        # all-time total — it goes back down after Trash is emptied or
        # auto-purges, same as Trash's own count would show. ---
        templates_count = len(self.templates)
        checklists_count = sum(1 for n in notes if n.get("checklist"))
        deleted_count = len(self.trash)
        tk.Label(
            self.stats_frame,
            text=f"🧩 {templates_count} templates   ·   "
                 f"☑ {checklists_count} notes with checklists   ·   "
                 f"🗑 {deleted_count} deleted",
            font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["text"],
            anchor="w"
        ).pack(fill="x")
        tk.Label(
            self.stats_frame, text=f"📅 Using Note Organizer since {_host().FIRST_LAUNCH_DATE}",
            font=("Segoe UI", 9), bg=self.colors["card"], fg=self.colors["text"],
            anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Per-category counts: known categories first (Manage-categories order),
        # then any leftover/stale category names so nothing is silently dropped.
        counts = {}
        for n in notes:
            cat = n.get("category") if isinstance(n.get("category"), str) else None
            cat = cat or "General"
            counts[cat] = counts.get(cat, 0) + 1
        ordered_cats = [c for c in CATEGORY_COLORS.keys() if c in counts]
        ordered_cats += [c for c in counts.keys() if c not in ordered_cats]

        if not ordered_cats:
            tk.Label(self.stats_frame, text="No notes yet.", font=("Segoe UI", 9),
                     bg=self.colors["card"], fg=self.colors["subtext"]
                     ).pack(anchor="w")
            return

        # --- Per-category counts: plain text, no box — a colored dot plus
        # "Category (count)". Deliberately not clickable; this is just a
        # snapshot, not another way to filter notes. Wraps into rows of 4. ---
        grid = tk.Frame(self.stats_frame, bg=self.colors["card"])
        grid.pack(fill="x")
        cols = 4
        for col in range(cols):
            grid.grid_columnconfigure(col, weight=1, uniform="statchip")

        for idx, cat in enumerate(ordered_cats):
            n = counts[cat]
            color = CATEGORY_COLORS.get(cat, self.colors["accent"])
            r, c = divmod(idx, cols)
            row = tk.Frame(grid, bg=self.colors["card"])
            row.grid(row=r, column=c, sticky="ew", padx=3, pady=3)
            tk.Label(row, text="●", font=("Segoe UI", 9), fg=color,
                     bg=self.colors["card"]).pack(side="left", padx=(0, 4))
            tk.Label(row, text=f"{cat} ({n})", font=("Segoe UI", 8),
                     bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                     ).pack(side="left", fill="x", expand=True)

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
        self._settings_panel_header(
            parent, "Categories",
            "Rename, recolor, or remove your categories. “General” is permanent.",
            "categories")
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
            for name in list(CATEGORY_COLORS.keys()):
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
        self._settings_panel_header(
            parent, "Templates",
            "Reusable starting points for new notes. Create one here or use "
            "“🧩 Save as template” on any note. Pick one with “📎 Use template”. "
            "Editing a template only affects notes you make from it afterwards — "
            "notes already created stay as they are.",
            "templates")
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
                for tpl in self.templates:
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
        tk.Label(row, text=f"🧩  {name}", bg=self.colors["sidebar"],
                 fg=self.colors["text"], font=("Segoe UI", 10, "bold"), anchor="w"
                 ).pack(side="left", fill="x", expand=True, padx=10, pady=8)

        def delete():
            if self.ask_yes_no("Delete template",
                                   f"Delete the template “{name}”?", parent=parent):
                self.templates = [t for t in self.templates if t is not tpl]
                save_templates(self.templates)
                redraw()
                self._render_statistics()

        tk.Button(row, text="🗑", command=delete, relief="flat", cursor="hand2",
                  bg=self.colors["sidebar"], fg=self.colors["danger"],
                  font=("Segoe UI", 10)).pack(side="right", padx=(2, 8))
        edit_btn = tk.Button(row, text="✎", relief="flat", cursor="hand2",
                  bg=self.colors["sidebar"], fg=self.colors["text"], font=("Segoe UI", 10))
        edit_btn.configure(command=lambda: self._edit_template(tpl, redraw, edit_btn))
        edit_btn.pack(side="right", padx=2)

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
                return t

        name_var = field("Template name", data["name"])
        title_var = field("Note title (optional)", data["title"])
        body_txt = field("Note body", data["body"], height=4)
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

        def save():
            new_tpl = normalize_template({
                "name": name_var.get(),
                "title": title_var.get(),
                "body": body_txt.get("1.0", "end").rstrip("\n"),
                "comments": comments_txt.get("1.0", "end").rstrip("\n"),
                "category": cat_var.get(),
                "checklist": [dict(it) for it in tpl_checklist],
            })
            if not new_tpl["name"].strip():
                self.show_warning("Name needed", "Give the template a name.", parent=pop)
                return
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

        # Anchored to whichever button opened it — same safe, proven
        # mechanism every other popup uses (multi-monitor safe, correct
        # -topmost ordering, live-tracks the app window if it moves). Falls
        # back to centering on the app window if no anchor was given.
        # click-outside-dismiss is turned off here — this editor holds more
        # content than a typical dropdown, so an accidental outside click
        # shouldn't discard it; Save/Cancel are the explicit ways out.
        if anchor_widget is not None and anchor_widget.winfo_exists():
            self._place_dropdown_popup(pop, anchor_widget, enable_click_outside=False)
        else:
            self._place_dropdown_popup(
                pop, None,
                anchor_xy=(self.winfo_rootx() + self.winfo_width() // 2,
                          self.winfo_rooty() + self.winfo_height() // 3),
                enable_click_outside=False)
        pop.bind("<Escape>", lambda e: self._dismiss_mini_popup())

    def _build_settings_trash_panel(self, parent):
        self._settings_panel_header(
            parent, "Recently deleted",
            f"Kept for {TRASH_RETENTION_DAYS} days, then removed automatically.",
            "trash")
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
        PAGE_SIZE = 50
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

        tk.Button(parent, text="🗑  Empty trash", command=empty_trash,
                  bg=self.colors["danger"], fg="white", relief="flat",
                  font=("Segoe UI", 9, "bold"), cursor="hand2"
                  ).pack(fill="x", padx=12, pady=(4, 10), ipady=5)

    def _build_settings_duplicates_panel(self, parent):
        self._settings_panel_header(
            parent, "Duplicate notes",
            "Notes with the same title, text, comments and category (ignoring "
            "case, spacing, date and color). Tick the copies you want to "
            "remove — the rest are kept.", "duplicates")
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
        """Show the theme variants for the CURRENT mode (dark or light) as
        larger, nicer preview cards. Switching light/dark swaps which set shows.
        The active theme is highlighted."""
        for w in parent.winfo_children():
            w.destroy()

        in_dark = self.theme_name in DARK_THEMES
        names = DARK_THEMES if in_dark else LIGHT_THEMES

        heading = tk.Label(
            parent, text=("Dark themes" if in_dark else "Light themes"),
            bg=self.colors["card"], fg=self.colors["subtext"],
            font=("Segoe UI", 9, "bold"), anchor="w")
        heading.pack(fill="x", pady=(4, 8))

        grid = tk.Frame(parent, bg=self.colors["card"])
        grid.pack(fill="x")
        for col in range(len(names)):
            grid.grid_columnconfigure(col, weight=1, uniform="themecol")

        for i, name in enumerate(names):
            pal = THEMES[name]
            active = (name == self.theme_name)

            cell = tk.Frame(grid, bg=self.colors["card"], cursor="hand2")
            cell.grid(row=0, column=i, padx=6, pady=2, sticky="nsew")

            # A larger preview card: window chrome with sidebar, an accent
            # button, a couple of text bars — a mini snapshot of the theme.
            W, H = 150, 96
            sw = tk.Canvas(cell, width=W, height=H, highlightthickness=0,
                           bg=self.colors["card"], cursor="hand2")
            # Outer rounded card = bg, with a highlight ring if active.
            ring = pal["accent"] if active else pal["sidebar"]
            self._rounded_rect(sw, 2, 2, W - 2, H - 2, 12, fill=pal["bg"], outline=ring)
            if active:
                self._rounded_rect(sw, 4, 4, W - 4, H - 4, 11, fill=pal["bg"], outline=pal["accent"])
            # Sidebar strip on the left.
            self._rounded_rect(sw, 8, 10, 44, H - 10, 8, fill=pal["sidebar"], outline=pal["sidebar"])
            # A "note card" on the right.
            self._rounded_rect(sw, 52, 12, W - 12, H - 12, 8, fill=pal["card"], outline=pal["card"])
            # Accent button + text lines inside the card.
            self._rounded_rect(sw, 60, 20, 108, 32, 5, fill=pal["accent"], outline=pal["accent"])
            self._rounded_rect(sw, 60, 42, W - 20, 48, 3, fill=pal["text"], outline=pal["text"])
            self._rounded_rect(sw, 60, 54, W - 30, 60, 3, fill=pal["subtext"], outline=pal["subtext"])
            self._rounded_rect(sw, 60, 66, W - 40, 72, 3, fill=pal["subtext"], outline=pal["subtext"])
            # Sidebar dots.
            for dy in (18, 30, 42):
                self._rounded_rect(sw, 14, dy, 38, dy + 6, 3,
                                   fill=pal["accent"] if dy == 18 else pal["card"],
                                   outline=pal["accent"] if dy == 18 else pal["card"])
            if active:
                sw.create_text(W - 16, 16, text="✓", fill=pal["accent"],
                               font=("Segoe UI", 13, "bold"))
            sw.pack()

            lbl = tk.Label(cell, text=THEME_LABELS.get(name, name),
                           bg=self.colors["card"],
                           fg=(self.colors["accent"] if active else self.colors["text"]),
                           font=("Segoe UI", 9, "bold" if active else "normal"))
            lbl.pack(pady=(6, 2))

            for w in (cell, sw, lbl):
                w.bind("<Button-1>", lambda e, n=name: self.set_theme(n))

        # Each preview card's canvas otherwise swallows the mouse wheel
        # itself (a plain Tk quirk: Canvas has a built-in default scroll
        # binding, so it never lets the event reach the Settings page
        # underneath) — forward it to the page's own scroll instead, the
        # same pattern used for every other Settings panel.
        def _theme_picker_wheel(event):
            try:
                self.settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        self._bind_wheel_tree(parent, _theme_picker_wheel)

        self._refresh_theme_picker = lambda: self._build_theme_picker(parent)

    def show_settings_page(self):
        """Show the Settings page in place of the Notes/Calendar notebook.
        Settings lives outside the tab strip on purpose — see the comment
        where self.settings_page is created."""
        self._catch_up_deferred_refresh()
        self.notebook.pack_forget()
        self.settings_page.pack(fill="both", expand=True)
        self._render_statistics()

    def hide_settings_page(self):
        """Return from Settings to the Notes/Calendar notebook."""
        self.settings_page.pack_forget()
        self.notebook.pack(fill="both", expand=True)

    # ---------- Settings tab ----------
    def build_settings_tab(self, parent):
        """A calm, scrollable settings page: appearance, categories, and a
        clearly separated backup section. These are all occasional actions,
        so moving them out of the sidebar keeps the notes list front-and-center."""
        outer = tk.Frame(parent)
        self.track_theme(outer, bg="bg")
        outer.pack(fill="both", expand=True)

        # "Back to Notes" lives in its own fixed row, OUTSIDE the scrollable
        # canvas below — packed first with side="top" so it claims its own
        # space and stays visible no matter how far the page underneath is
        # scrolled, instead of being just another row that scrolls away.
        sticky_bar = tk.Frame(outer)
        self.track_theme(sticky_bar, bg="bg")
        sticky_bar.pack(side="top", fill="x")
        back_row = tk.Frame(sticky_bar)
        self.track_theme(back_row, bg="bg")
        back_row.pack(fill="x", padx=40, pady=(20, 0))
        back_btn = tk.Button(
            back_row, text="← Back to Notes", command=self.hide_settings_page,
            relief="flat", font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        self.track_theme(back_btn, bg="card", fg="text")
        back_btn.pack(side="left", ipadx=8, ipady=4)

        canvas = tk.Canvas(outer, highlightthickness=0, bg=self.colors["bg"])
        self.track_theme(canvas, bg="bg")
        self.settings_canvas = canvas  # panels forward scroll here when they don't scroll
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        page = tk.Frame(canvas)
        self.track_theme(page, bg="bg")
        page.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        page_window = canvas.create_window((0, 0), window=page, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(page_window, width=e.width))
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Wheel anywhere over the settings page scrolls the page.
        def _page_wheel(event):
            try:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except (tk.TclError, ValueError):
                pass
            return "break"
        canvas.bind("<MouseWheel>", _page_wheel)
        page.bind("<MouseWheel>", _page_wheel)

        # Clicking a non-interactive part of the Settings page (a section
        # title, card background, blank space) should move keyboard focus
        # away from whatever field currently has it — otherwise a field's
        # cursor stays visibly blinking even after its value has already
        # autosaved. Bound once on the whole app rather than on individual
        # labels/frames (every click bubbles up to the toplevel by default
        # unless something along the way stops it, so this reliably catches
        # all of them) — restricted to only act while Settings is actually
        # showing, and only when focus is genuinely on an Entry/Text that
        # isn't the widget that was just clicked.
        def _clear_settings_field_focus(event):
            if not self.settings_page.winfo_ismapped():
                return
            focused = self.focus_get()
            if isinstance(focused, (tk.Entry, tk.Text)) and event.widget is not focused:
                event.widget.focus_set()
        self.bind("<Button-1>", _clear_settings_field_focus, add="+")

        def section(title, subtitle=None):
            head = tk.Frame(page)
            self.track_theme(head, bg="bg")
            head.pack(fill="x", padx=40, pady=(24, 0))
            tk.Label(head, text=title, font=("Segoe UI", 14, "bold"),
                     bg=self.colors["bg"], fg=self.colors["text"], anchor="w"
                     ).pack(fill="x")
            if subtitle:
                tk.Label(head, text=subtitle, font=("Segoe UI", 9),
                         bg=self.colors["bg"], fg=self.colors["subtext"],
                         anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(2, 0))
            card = tk.Frame(page, bg=self.colors["card"])
            self.track_theme(card, bg="card")
            card.pack(fill="x", padx=40, pady=(10, 0))
            return card

        def big_button(parent_frame, text, command, kind="normal"):
            bg = "accent" if kind == "accent" else "sidebar"
            b = tk.Button(parent_frame, text=text, command=command, relief="flat",
                          font=("Segoe UI", 10, "bold"), cursor="hand2",
                          fg="white" if kind == "accent" else self.colors["text"])
            self.track_theme(b, bg=bg)
            if kind == "accent":
                b.configure(fg="white")
            return b

        tk.Label(page, text="⚙  Settings", font=("Segoe UI", 20, "bold"),
                 bg=self.colors["bg"], fg=self.colors["text"], anchor="w"
                 ).pack(fill="x", padx=40, pady=(24, 0))

        # --- Your name (used for the "Hi <name>," greeting) ---
        name_sec = section(
            "Your name",
            "What should we call you? Shows up as a friendly greeting above "
            "your notes — 30 characters max."
        )
        name_row = tk.Frame(name_sec, bg=self.colors["card"])
        name_row.pack(fill="x", padx=16, pady=16)
        self.username_var = tk.StringVar(value=self.load_username())
        # Cap at 30 characters — an unbounded name could look broken in the
        # sidebar greeting. Only limits new typing; an existing longer name
        # (saved before this cap existed) still loads and displays in full.
        USERNAME_MAX_LEN = 30
        name_len_vcmd = (self.register(lambda p: len(p) <= USERNAME_MAX_LEN), "%P")
        name_entry = tk.Entry(
            name_row, textvariable=self.username_var, relief="flat",
            font=("Segoe UI", 10), bg=self.colors["sidebar"], fg=self.colors["text"],
            insertbackground=self.colors["text"],
            validate="key", validatecommand=name_len_vcmd
        )
        name_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self._add_paste_menu(name_entry)

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
            self.set_status("Name saved" if current.strip() else "Name cleared")

        def schedule_name_save(event=None):
            # Real-time correction: the per-keystroke block above can miss
            # very fast/held-down typing, so check again on every key
            # release (a plain event binding, not the special validate hook
            # that has the reliability gap) and snap back immediately if it
            # slipped past 30 — rather than letting it grow freely and only
            # fixing it later when the name is actually saved.
            current = self.username_var.get()
            if len(current) > USERNAME_MAX_LEN:
                self.username_var.set(current[:USERNAME_MAX_LEN])
            # Autosave after a short pause, same convention as note editing —
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
        # No separate Save button — the field already autosaves shortly
        # after typing stops, and immediately on Enter or clicking away.

        # --- Appearance ---
        appearance = section("Appearance", "How the app looks.")
        self.theme_toggle_btn = tk.Button(
            appearance,
            text="☀️  Switch to Light mode" if self.theme_name in DARK_THEMES
            else "🌙  Switch to Dark mode",
            command=self.toggle_theme, relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(self.theme_toggle_btn, bg="sidebar", fg="text")
        self.theme_toggle_btn.pack(fill="x", padx=16, pady=(16, 8), ipady=6)

        # Theme picker — pick any color scheme, grouped Dark / Light.
        self.theme_picker_frame = tk.Frame(appearance, bg=self.colors["card"])
        self.track_theme(self.theme_picker_frame, bg="card")
        self.theme_picker_frame.pack(fill="x", padx=16, pady=(0, 16))
        self._build_theme_picker(self.theme_picker_frame)

        # --- Organization: categories ---
        org = section("Organization",
                      "Categories are folders for your notes.")
        big_button(org, "🗂  Manage categories",
                   lambda: self.toggle_settings_panel("categories")
                   ).pack(fill="x", padx=16, pady=(16, 6), ipady=6)
        self.settings_categories_panel = tk.Frame(org, bg=self.colors["card"])
        self.track_theme(self.settings_categories_panel, bg="card")

        big_button(org, "🧩  Manage templates",
                   lambda: self.toggle_settings_panel("templates")
                   ).pack(fill="x", padx=16, pady=(0, 6), ipady=6)
        # Inline panel for templates.
        self.settings_templates_panel = tk.Frame(org, bg=self.colors["card"])
        self.track_theme(self.settings_templates_panel, bg="card")
        # Reserve trailing space under the last button/panel.
        tk.Frame(org, bg=self.colors["card"], height=10).pack(fill="x")

        # --- Backup (deliberately separate: these act on your data) ---
        backup = section("Backup",
                         "Save all your notes to a file, or bring them in from one. "
                         "Use this to move notes between computers.")
        row = tk.Frame(backup, bg=self.colors["card"])
        self.track_theme(row, bg="card")
        row.pack(fill="x", padx=16, pady=16)
        big_button(row, "⬆  Export notes", self.export_data, kind="accent"
                   ).pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=6)
        big_button(row, "⬇  Import notes", self.import_data
                   ).pack(side="left", fill="x", expand=True, padx=(6, 0), ipady=6)

        # --- Trash (recover recently deleted notes) ---
        trash_sec = section("Recently deleted",
                            f"Deleted notes are kept here for {TRASH_RETENTION_DAYS} "
                            "days, then removed automatically. You can restore them "
                            "until then.")
        self.trash_btn = tk.Button(
            trash_sec, text="🗑  Open Recently Deleted",
            command=lambda: self.toggle_settings_panel("trash"),
            relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2"
        )
        self.track_theme(self.trash_btn, bg="sidebar", fg="text")
        self.trash_btn.pack(fill="x", padx=16, pady=(16, 6), ipady=6)
        self.settings_trash_panel = tk.Frame(trash_sec, bg=self.colors["card"])
        self.track_theme(self.settings_trash_panel, bg="card")
        tk.Frame(trash_sec, bg=self.colors["card"], height=10).pack(fill="x")

        # --- Clean up duplicates ---
        dup_sec = section("Clean up duplicates",
                          "Find notes that are exactly identical (same title, "
                          "text, comments, category and date). Tick the "
                          "copies you want to remove; the rest are kept.")
        tk.Button(dup_sec, text="🧹  Find duplicates",
                  command=lambda: self.toggle_settings_panel("duplicates"),
                  relief="flat", font=("Segoe UI", 10, "bold"), cursor="hand2",
                  bg=self.colors["sidebar"], fg=self.colors["text"]
                  ).pack(fill="x", padx=16, pady=(16, 6), ipady=6)
        self.settings_duplicates_panel = tk.Frame(dup_sec, bg=self.colors["card"])
        self.track_theme(self.settings_duplicates_panel, bg="card")
        tk.Frame(dup_sec, bg=self.colors["card"], height=10).pack(fill="x")

        # --- Statistics ---
        stats_sec = section("Statistics", "A quick snapshot of your notes.")
        self.stats_frame = tk.Frame(stats_sec, bg=self.colors["card"])
        self.stats_frame.pack(fill="x", padx=16, pady=16)
        self._render_statistics()

        # --- Storage info ---
        info = section("Where your notes are stored")
        tk.Label(info, text=_host().APP_DIR, font=("Consolas", 9),
                 bg=self.colors["card"], fg=self.colors["subtext"],
                 anchor="w", wraplength=560, justify="left"
                 ).pack(fill="x", padx=16, pady=16)

        # --- About / version ---
        about = section("About")
        about_inner = tk.Frame(about, bg=self.colors["card"])
        self.track_theme(about_inner, bg="card")
        about_inner.pack(fill="x", padx=16, pady=16)
        tk.Label(about_inner, text="Notes Organizer", font=("Segoe UI", 11, "bold"),
                 bg=self.colors["card"], fg=self.colors["text"], anchor="w"
                 ).pack(fill="x")
        tk.Label(about_inner, text=f"Version {_host().APP_VERSION}", font=("Segoe UI", 9),
                 bg=self.colors["card"], fg=self.colors["subtext"], anchor="w"
                 ).pack(fill="x", pady=(2, 0))

        tk.Frame(page, bg=self.colors["bg"], height=30).pack()
        self._bind_mousewheel_recursive(page, canvas)

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
            tk.Button(
                row, text="✎", command=rename, relief="flat", cursor="hand2",
                bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10)
            ).pack(side="right", padx=2)

            def delete():
                self._delete_category(name, redraw)

            tk.Button(
                row, text="🗑", command=delete, relief="flat", cursor="hand2",
                bg=self.colors["card"], fg=self.colors["danger"], font=("Segoe UI", 10)
            ).pack(side="right", padx=2)
        else:
            tk.Label(
                row, text="🔒", bg=self.colors["card"], fg=self.colors["subtext"],
                font=("Segoe UI", 10)
            ).pack(side="right", padx=6)

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
            buttons=[("Cancel", None),
                     ("Delete the notes too (permanent)", "delete_notes", "danger"),
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
            f"You can restore them within {TRASH_RETENTION_DAYS} days.",
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
