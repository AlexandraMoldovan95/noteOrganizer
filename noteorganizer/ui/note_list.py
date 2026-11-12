"""The note list: the sidebar's cards, drawn on one canvas.

The cards and category headers (what is on screen first, the rest as the
view nears it), filtering, searching, sorting, the keyboard ring, dragging
into Custom order, and Select mode. Nine in ten of the calls these methods
make go to each other, which is why they left the hub (tools/call_graph.py;
docs/ARCHITECTURE.md, "The list, measured again"). The bulk actions and
their questions act on notes, not on the list, and Settings asks them too,
so they stay on the app class, with add_placeholder, which every entry
field uses. :mod:`noteorganizer.ui` says what a mixin is.
"""

import time
import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

from ..core import tables as core_tables
from ..core.categories import CATEGORY_COLORS
from ..core.model import _truncate, fold_for_search
from ..core.recurrence import (
    describe_recurrence,
    history_entries,
    is_recurring,
    next_occurrence_on_or_after,
    parse_date,
    show_date,
)
from ..core.storage import load_settings, save_settings
from ..core.themes import legible_on


class NoteListMixin:
    """The note list. Mixed into :class:`note_organizer.NoteOrganizer`."""

    def _on_toggle_group_by_category(self):
        settings = load_settings()
        settings["group_by_category"] = bool(self.group_by_category.get())
        save_settings(settings)
        self.refresh_note_list()

    def _sync_list_scroll(self, _event=None):
        """Keep the note list honest about where its top is: content that
        fits sits AT the top, and the origin never rests above the first card
        (which showed as unexplained space under the top bar). The editor's
        canvas carries the same guard."""
        canvas = self.canvas
        if canvas is None:
            return
        try:
            # While a rebuild's restore is in force, every Configure re-applies
            # it: a rebuilt list settles over several passes (heights 106 ->
            # 276 -> 820, measured), each re-clamping, and one restore loses.
            pending = getattr(self, "_list_restore_px", None)
            if pending is not None:
                if time.monotonic() <= getattr(self, "_list_restore_until", 0):
                    self._apply_list_scroll_px(pending)
                    return
                self._list_restore_px = None
            # The region set to the truth first, from the rows (_list_extent):
            # yview_moveto works in its fractions, and Tk then clamps an origin
            # left past a new, shorter end, which would show a blank view.
            region = self._list_extent()
            canvas.configure(scrollregion=region)
            content_h = region[3] - region[1]
            if (content_h <= canvas.winfo_height()
                    or canvas.canvasy(0) < 0):
                canvas.yview_moveto(0)
        except tk.TclError:
            pass

    def _apply_list_scroll_px(self, pixels):
        """Scroll the list to `pixels` from the top, clamped into the content
        as it is now; content that fits pins to the top. The region is set
        from the list's own extent first: content that just shrank under a
        view scrolled past its new end would leave it in blank space."""
        canvas = self.canvas
        if canvas is None:
            return
        try:
            region = self._list_extent()
            canvas.configure(scrollregion=region)
            content_h = max(1, region[3] - region[1])
            view_h = canvas.winfo_height()
            if content_h <= view_h:
                canvas.yview_moveto(0)
                return
            pixels = max(0, min(pixels, content_h - view_h))
            canvas.yview_moveto(pixels / content_h)
        except tk.TclError:
            pass

    def _restore_list_scroll(self, pixels):
        """Put the list back where it was before a rebuild, in PIXELS (the
        height can change, so a fraction would land elsewhere), and keep it
        there for 0.4 s against every Configure and by the timers below: the
        geometry settles over several passes. ISSUES_LOG: "The list that lost
        its place, twice, for two silent reasons"."""
        self._list_restore_px = pixels
        self._list_restore_until = time.monotonic() + 0.4
        self._apply_list_scroll_px(pixels)
        for delay in (60, 160, 360):
            self.after(delay, self._reapply_list_restore)

    def _begin_list_restore(self):
        """Start the timed restore a rebuild left in force -- unless a
        deliberate scroll has cancelled it since (see refresh_note_list)."""
        pending = getattr(self, "_list_restore_px", None)
        if pending is not None and self._still_alive():
            self._restore_list_scroll(pending)

    def _reapply_list_restore(self):
        """One timed beat of a still-in-force rebuild restore."""
        pending = getattr(self, "_list_restore_px", None)
        if pending is None or not self._still_alive():
            return
        if time.monotonic() > getattr(self, "_list_restore_until", 0):
            self._list_restore_px = None
            return
        self._apply_list_scroll_px(pending)

    def _list_scrollbar_moved(self, *args):
        """The list scrollbar's command: a deliberate drag beats a
        rebuild's still-pending restore, then scrolls as normal."""
        self._list_scrolled_by_hand()
        try:
            self.canvas.yview(*args)
        except tk.TclError:
            pass

    def _list_scrolled_by_hand(self):
        """The person is scrolling the list (wheel, scrollbar, a drag held at
        its edge). A deliberate move beats a rebuild's pending restore, and a
        ring it leaves out of sight was left on purpose: the keyboard coming
        back takes a card in view (_list_focus_in), where a save or a search
        brings the ringed card back. Judged once the view has moved. ISSUES_LOG,
        smaller lessons: _list_scrolled_by_hand."""
        self._list_restore_px = None
        if getattr(self, "_hand_scroll_check", None) is None:
            try:
                self._hand_scroll_check = self.after_idle(
                    self._note_hand_scroll)
            except tk.TclError:
                self._hand_scroll_check = None

    def _note_hand_scroll(self):
        """After a scroll of the person's: did it leave the ring's row out
        of sight (see _list_scrolled_by_hand)? A row the list has not drawn
        is out of sight too."""
        self._hand_scroll_check = None
        # Drawn or not: _ring_row answers None for a row not drawn, and such a
        # scroll once read as none, so the keyboard's return drew every row to
        # it and pulled the view from where the person had put it.
        cat = getattr(self, "_focused_header", None)
        key = (("header", cat) if cat is not None
               else ("note", getattr(self, "_focused_note_id", None)))
        if key[1] is None:
            return
        rec = self._list_row_record(key)
        self._list_hand_scrolled = (rec is None
                                    or self._row_on_screen(rec) == "none")

    def _what_hides_notes(self, note=None):
        """In words, what keeps notes off the list now -- the search, Show,
        *note*'s folded group, and of those only what keeps *note* off when
        one is given -- or '' when nothing does. A new note filed under
        General vanished as it was written, with Show picked once and
        forgotten, and the empty list blamed a search nobody had typed."""
        parts = []
        query, show = self._search_query(), self.filter_var.get()
        if query and (note is None or not self._query_matches_note(query, note)):
            parts.append("your search")
        if show != "All" and (note is None or not self._note_passes_filter(note, show)):
            parts.append("Show: " + show)
        if (note is not None and self.group_by_category.get()
                and self._list_group_of(note) in self.collapsed_groups):
            parts.append("its folded group")
        return " and ".join(parts)

    def _show_all_notes(self, note=None):
        """The list with nothing hiding: Show at All, the search emptied,
        *note*'s group unfolded, drawn again at once (Show's variable set by
        hand draws nothing). The search box is emptied without the focus:
        the banner comes while a new note is being written, and the words
        typed after Show all went into the search."""
        # Settings is left first, as Back leaves it; a
        # popup holding typed work asks, and kept, nothing moves: the tab
        # change below destroyed it, words and all.
        if not self._leave_settings_for_the_editor():
            return
        # ...and from the Calendar, or with the list put away, the list is
        # brought where it is seen.
        try:
            if self.notebook.index("current") != self.TAB_NOTES:
                self.notebook.select(self.TAB_NOTES)
        except tk.TclError:
            pass
        if getattr(self, "_sidebar_hidden", False):
            self.toggle_sidebar()
        if note is not None and self._list_group_of(note) in self.collapsed_groups:
            self._toggle_group_collapsed(self._list_group_of(note))
        self.filter_var.set("All")
        if self.search_var.get() and not self._hint_shown(self.search_entry):
            try:
                in_box = self.focus_get() is self.search_entry
            except (KeyError, tk.TclError):
                in_box = False
            if in_box:
                self.search_var.set("")
            else:
                self.search_entry.show_hint()
        self.refresh_note_list()
        # Its card in sight: the list keeps its place, and the notes Show
        # had hidden can come in above it.
        if note is not None:
            self._bring_card_into_view(note.get("id"))

    def _list_empty_link(self, y, text, tag, command):
        """A link drawn under the empty list's words, at *y*: its item."""
        item = self.canvas.create_text(
            13, y, anchor="nw", text=text, font=("Segoe UI", 10, "underline"),
            fill=self.colors["accent_text"], tags=("row", tag))
        self.canvas.tag_bind(tag, "<Button-1>", lambda _e: command())
        self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.configure(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.configure(cursor=""))
        return item

    def _say_hidden_arrivals(self, notes, what):
        """*notes*, just brought in -- an import, a restore -- said with the
        banner a new note has when the list hides any of them: they landed
        where Show or the search kept the list from looking, under "Added 3
        notes" and a list that had not changed."""
        shown = self._visible_note_ids()
        hidden = [n for n in notes or () if n.get("id") not in shown]
        hides = self._what_hides_notes(hidden[0]) if hidden else ""
        if hides:
            tail = (f"hidden by {hides}" if len(notes) == 1
                    else f"{len(hidden)} of them hidden by {hides}")
            said = f"{what}, {tail}"

            def say():
                # Asked again when shown, as it can wait behind an Undo -- its
                # words too, or they named a filter changed since.
                # The list read once: per note, a big import froze.
                shown_now = self._visible_note_ids()
                held = {id(m) for m in self.notes}
                still = [n for n in hidden if id(n) in held and n.get("id") not in shown_now]
                if still:
                    hides_now = self._what_hides_notes(still[0])
                    now = (f"hidden by {hides_now}" if len(notes) == 1
                           else f"{len(still)} of them hidden by {hides_now}")
                    self._show_toast(f"{what}, {now}", kind="info",
                                     action=lambda: self._show_all_notes(still[0]), action_text="Show all")
            # Not over an Undo still showing: 'Day removed' holds the day's
            # text in it alone.
            self._banner_after_undo(said, say)

    def _bring_card_into_view(self, note_id):
        """Draw the list down to *note_id*'s card, if it is still waiting to
        be drawn, and scroll it all into sight."""
        pending = getattr(self, "_list_pending", None) or ()
        index = next((i for i, row in enumerate(pending)
                      if row[0] == "note" and row[1].get("id") == note_id), None)
        if index is not None:
            self._draw_list_rows(index + 1)
        rec = self._list_row_record(("note", note_id))
        if rec is not None and self._row_on_screen(rec) != "all":
            self._scroll_row_into_view(rec)

    def _toggle_group_collapsed(self, category):
        if category in self.collapsed_groups:
            self.collapsed_groups.discard(category)
        else:
            self.collapsed_groups.add(category)
        settings = load_settings()
        settings["collapsed_groups"] = sorted(self.collapsed_groups)
        save_settings(settings)
        self.refresh_note_list()

    # ---------- Note list rendering ----------
    # The filter dropdown offers a category or one of these types; every
    # reader goes through _note_passes_filter, so "visible" means one thing.
    FILTER_REPEATING = "🔁 Repeating"
    FILTER_DATED = "📅 Dated"
    FILTER_FILES = "📎 With files"

    def _filter_options(self):
        """Everything the sidebar's filter dropdown offers, in order: the
        dropdown and every check that a filter is still a real choice read
        it. A half-remembered copy asked `not in CATEGORY_COLORS`, true of
        both type filters, so adding a category threw a Repeating filter
        away. ISSUES_LOG, smaller lessons: _filter_options."""
        return ["All", self.FILTER_REPEATING, self.FILTER_DATED,
                self.FILTER_FILES] + list(CATEGORY_COLORS.keys())

    def _keep_filter_valid(self):
        """Fall back to All if the current filter is no longer on offer.

        Called wherever the vocabulary can change -- which today means the
        categories, and at startup, where the value comes off disk and could
        name a category this notebook has never had.
        """
        var = self.filter_var
        if var is not None and var.get() not in self._filter_options():
            var.set("All")

    def _note_passes_filter(self, note, selected):
        """One judgment for the sidebar filter dropdown's current choice."""
        if selected == "All":
            return True
        if selected == self.FILTER_REPEATING:
            return is_recurring(note)
        if selected == self.FILTER_DATED:
            return not is_recurring(note) and bool(note.get("date"))
        if selected == self.FILTER_FILES:
            # The notes whose card shows 📎×N.
            return bool(note.get("attachments"))
        return note.get("category") == selected

    def refresh_note_list(self):
        if not self._still_alive():
            return
        # A card lifted by a drag is drawn away from its record; the
        # rebuild below would draw the list around a card that is not
        # where it seems. The drag ends, and the card goes back first.
        self._cancel_list_drag()
        # Every route that takes notes out of the notebook ends here or in
        # _remove_note_cards, so the ticks of notes that are gone go here.
        self._prune_selection()
        # The sort this list is drawn in -- what Custom order starts from
        # when it is chosen for the first time (_on_sort_chosen).
        sort_var = self.sort_var
        if sort_var is not None:
            self._sort_shown = sort_var.get()
        # The rebuild empties the drawing for a moment, and a Configure then
        # clamps the canvas to the top ("the scroll jumps back to the top"):
        # the offset is kept in pixels and put back once the rows exist.
        try:
            # If the previous rebuild's restore is still in force, the
            # canvas may sit at a transiently clamped position right now
            # -- carry that restore's target forward instead.
            pending = getattr(self, "_list_restore_px", None)
            if (pending is not None and time.monotonic()
                    <= getattr(self, "_list_restore_until", 0)):
                saved_list_scroll = pending
            else:
                saved_list_scroll = max(0, self.canvas.canvasy(0))
        except (tk.TclError, AttributeError):
            saved_list_scroll = 0
        # A new search starts its results at the top: kept in place, its
        # first matches could sit above the screen (the owner's call,
        # 2026-10-21). Any other rebuild -- a save, a sort -- keeps its place.
        query = self._search_query()
        if query != getattr(self, "_list_query_drawn", query):
            saved_list_scroll = 0
            self._list_restore_px = None
            try:
                self.canvas.yview_moveto(0)
            except (tk.TclError, AttributeError):
                pass
        self._list_query_drawn = query
        # Every data change ends here, so the Statistics panel refreshes too,
        # live while Settings is open -- before the early returns below.
        self._render_statistics()
        # And an open Share panel keeps to the list's order.
        self._share_panel_follows()
        # Whether the keyboard is on the list decides how far the rebuild
        # draws (see _list_draw_target). The keyboard itself stays where it
        # is: the canvas survives a rebuild, only its drawing is replaced.
        self._restore_focus_wanted = getattr(self, "_keyboard_on_card", False)
        # A ring the person could see is followed if this rebuild moves its
        # row (a card pinned from its menu goes to the top); set only here, so
        # two rebuilds before the app is idle cannot forget it.
        ring = self._ring_row()
        if (self._restore_focus_wanted and ring is not None
                and self._row_on_screen(self._list_row_record(ring)) == "all"):
            self._ring_follow = True
        # How deep the list must be drawn again, asked before the drawing
        # goes: as deep as the view needs, not as deep as it once went.
        drawn_before = self._list_depth_for(saved_list_scroll)
        self.canvas.delete("row")
        # One record per drawn row in screen order, and the same records by
        # note id and by category: what every update short of a rebuild uses.
        self._list_drawn = []
        self._note_cards = {}
        self._group_headers = {}
        self._list_pending = []
        # The drawing is replaced, and every card drawn below notes afresh
        # whether it is painted as the open note (_ring_to_paint).
        self._open_ring_ids = set()

        rows = self._list_rows()

        if not rows:
            # Distinguish "no notes at all" from "nothing matches the filter",
            # and name what is hiding them, with the way back.
            hides = self._what_hides_notes() if self.notes else ""
            if self.notes:
                msg = "No notes match " + (hides or "the list's choices") + "."
            else:
                msg = "No notes yet.\nClick '+ New Note' to start!"
            # Kept inside the list's width, like every other text on it:
            # a message that fits here can run off the edge in another
            # font or at another scaling.
            text_id = self.canvas.create_text(
                13, 23, anchor="nw", text=msg, font=("Segoe UI", 10),
                width=self.LIST_DRAW_WIDTH - 2 * 13,
                fill=self.colors["subtext"], tags=("row", "list_empty"))
            if hides:
                below = self.canvas.bbox(text_id)[3] + self.px(6)
                link = self._list_empty_link(below, "Show all notes", "list_show_all",
                                             self._show_all_notes)
                # A day's own words (auto_expand) the list does not read: said,
                # with the way to the History (the owner's choice). Not
                # a dated note Show hid, which the History lists too.
                typed = self.search_var.get().strip()
                if (self._search_query()
                        and any(e.get("auto_expand")
                                for e in history_entries(self.notes, query=typed))):
                    below = self.canvas.bbox(link)[3] + self.px(12)
                    said = self.canvas.create_text(
                        13, below, anchor="nw", font=("Segoe UI", 10),
                        text="A day of a repeating note holds these words.",
                        width=self.LIST_DRAW_WIDTH - 2 * 13,
                        fill=self.colors["subtext"], tags=("row", "list_history_said"))
                    self._list_empty_link(self.canvas.bbox(said)[3] + self.px(6),
                                          "Search the Calendar's History", "list_history",
                                          lambda: self._search_history_for(typed))
            self._list_extent_changed()
            return

        self._list_pending = rows
        self._draw_list_rows(self._list_draw_target(
            rows, drawn_before, saved_list_scroll))
        if saved_list_scroll > 0:
            # In force from here, not from idle: a deliberate scroll cancels it
            # by clearing _list_restore_px, which a queued bare callback could
            # not see. ISSUES_LOG, smaller lessons: refresh_note_list.
            self._list_restore_px = saved_list_scroll
            self._list_restore_until = time.monotonic() + 0.4
            self.after_idle(self._begin_list_restore)
        # The card with the keyboard's ring is drawn with it; this repaints
        # it once the app is idle, for a rebuild that ran while the list was
        # not the thing holding the keyboard.
        self.after_idle(self._restore_card_focus)
        if self.selection_mode:
            # What "all" means just changed (a search or filter), and the
            # Select all button says what a press would do; only while the
            # bar is up, so an ordinary refresh pays nothing.
            self._update_bulk_selected_label()

    # How many rows -- cards, and category headers when grouped -- the list
    # draws straight away, and how many more each time the view comes
    # within a screen of the end of what is drawn. See _draw_list_rows.
    LIST_FIRST_DRAW = 30
    LIST_DRAW_STEP = 20
    # Where a card redrawn by a save is drawn before the reflow puts it in
    # its place: above the list, where no row ever stands (_reflow_list).
    LIST_OUT_OF_THE_WAY = -100000

    # The sort a person arranges by hand (a drag, or Alt+Up/Down), stored as
    # each note's "order"; one name, so the dropdown, sort and move agree.
    SORT_CUSTOM = "Custom order"
    LIST_DOUBLE_PRESS_S = 0.5   # how long a double-click's first press counts
    DRAG_THRESHOLD = 5          # pixels a press must travel to become a drag
    DRAG_EDGE = 28              # near the list's top or bottom, a drag scrolls
    DRAG_SCROLL_MS = 40         # ...one step this often
    DRAG_EDGE_DWELL_MS = 400    # ...a drag that began there, once held this long
    DRAG_SCROLL_RAMP = 10       # ...its steps growing to full over these beats

    # A card is rectangles and text on the canvas, not widgets; these match
    # the widget cards they replaced, to the pixel where it could be measured.
    LIST_DRAW_WIDTH = 250       # the list's width, as the old frame's was
    CARD_MARGIN = (5, 5)        # above and below each card
    HEADER_MARGIN = (6, 2)      # above and below each category header
    HEADER_HEIGHT = 22
    HEADER_FONT = ("Segoe UI", 9, "bold")
    CARD_TITLE_FONT = ("Segoe UI", 11, "bold")
    CARD_PREVIEW_FONT = ("Segoe UI", 9)
    CARD_TAGS_FONT = ("Segoe UI", 8, "bold")
    CARD_TITLE_CHARS = 42       # a longer title is shortened, then wrapped
    CARD_PREVIEW_CHARS = 40     # a glimpse of the body, wrapped to the card
    CARD_INSET_X = 2            # between the list's edge and a card's
    CARD_RING = 2               # the ring: open note, keyboard, or nothing
    CARD_STRIPE = 5             # the note's colour down the left edge
    CARD_PAD = (10, 8)          # around the text inside a card
    CARD_TEXT_INSET = 3         # what a Label kept around its own text
    CARD_CHECK = 13             # the tick box, in selection mode
    # The tick's mark is dark on every theme, as Windows drew it on the
    # Checkbutton this replaces: the well it sits in is light everywhere.
    CARD_CHECK_MARK = "#22223a"

    @property
    def _list_drawn_keys(self):
        """What is drawn, as ("note", id) and ("header", category), in the
        order it stands on screen."""
        return [rec["key"] for rec in getattr(self, "_list_drawn", None) or ()]

    def _notes_on_the_list(self):
        """The notes the sidebar's search box and filter let through, in the
        notebook's own order: the ONE answer to "which notes does the list
        show", as _query_matches_note is for one note. The list and Select all
        once each kept a copy, and copies agree only until they stop."""
        query = self._search_query()
        if not query:
            shown = list(self.notes)
        else:
            # The same rule as _query_matches_note, over texts kept from the
            # last scan: a keystroke used to lowercase every body and parse
            # every table again (70 ms a pause at 5,000 notes).
            shown = [n for n in self.notes
                     if self._query_in_texts(query, self._cached_search_texts(n))]
            cache = self.__dict__.setdefault("_search_text_cache", {})
            if len(cache) > len(self.notes) + 64:
                # Notes deleted since: their entries go.
                alive = {n.get("id") for n in self.notes}
                for gone in [k for k in cache if k not in alive]:
                    del cache[gone]
        # Category/type filter (from the dropdown). "All" shows everything.
        chosen_category = self.filter_var
        if chosen_category is not None:
            selected = self.filter_var.get()
            if selected != "All":
                shown = [n for n in shown
                         if self._note_passes_filter(n, selected)]
        return shown

    @staticmethod
    def _list_group_of(note):
        """The group a note's card stands in when the list is grouped: its
        category, or General for a note with none. One answer for the rows
        themselves and for every question asked about them -- which group a
        card may be dragged within, and which notes a folded group hides."""
        return note.get("category") or "General"

    def _list_rows(self):
        """Every row the note list shows, in screen order, before any is drawn:
        ("note", note), or when grouped ("header", category, notes, collapsed)
        ahead of each group's cards. Groups follow Manage-categories order, a
        vanished category keeps a group of its own, and the rebuild, the
        scrolling and a save redrawing its card all ask this one definition."""
        shown = self._notes_on_the_list()
        self._sort_notes(shown)
        if not shown:
            return []
        if not (self.group_by_category is not None
                and self.group_by_category.get()):
            return [("note", note) for note in shown]
        groups = {}
        for note in shown:
            groups.setdefault(self._list_group_of(note), []).append(note)
        # Known categories first (in their defined order), then any leftover
        # (stale/deleted) category names so nothing gets silently dropped.
        ordered = [c for c in CATEGORY_COLORS.keys() if c in groups]
        ordered += [c for c in groups.keys() if c not in ordered]
        rows = []
        for cat in ordered:
            collapsed = cat in self.collapsed_groups
            rows.append(("header", cat, groups[cat], collapsed))
            if not collapsed:
                rows.extend(("note", note) for note in groups[cat])
        return rows

    def _list_draw_target(self, rows, drawn_before, scrolled_px):
        """How many rows a rebuild draws before handing back: a screenful and
        some, as a rule -- but as deep as reached a screen below a scrolled
        view (`drawn_before`, from _list_depth_for), so the restored position
        has rows to land on, and down to the ring's card when the keyboard
        was on one."""
        want = self.LIST_FIRST_DRAW
        if scrolled_px > 0:
            want = max(want, drawn_before)
        if getattr(self, "_restore_focus_wanted", False):
            index = self._ring_index_in(rows)
            if index is not None:
                want = max(want, index + 1)
        return want

    def _list_depth_for(self, scrolled_px):
        """How many drawn rows reach a screen below a view scrolled
        `scrolled_px` down (the margin the top-up keeps, so a wheel turn finds
        rows), asked of the drawing a rebuild replaces. Drawing again every row
        drawn before cost 90-360 ms a pin or a search after one trip to the end
        of 1,000 notes and back."""
        drawn = getattr(self, "_list_drawn", None) or ()
        if scrolled_px <= 0 or not drawn:
            return 0
        try:
            bottom = scrolled_px + 2 * self.canvas.winfo_height()
        except tk.TclError:
            return len(drawn)
        depth = 0
        for rec in drawn:
            depth += 1
            if rec["y0"] >= bottom:
                break
        return depth

    def _draw_list_rows(self, count):
        """Draw the next `count` waiting rows, below what is already drawn.
        A rebuild draws a screenful and some; the rest is drawn as the view
        comes near it (_list_view_changed) or the keyboard walks ahead of it
        (_focus_card_by_offset). ISSUES_LOG: "The list that was drawn whole,
        for every pause in typing"."""
        batch = self._list_pending[:count]
        self._list_pending = self._list_pending[count:]
        if not batch:
            return
        y = self._list_end_y()
        for row in batch:
            if row[0] == "header":
                rec = self._draw_group_header(
                    row[1], row[2], row[3], y + self.HEADER_MARGIN[0])
            else:
                rec = self._draw_note_card(row[1], y + self.CARD_MARGIN[0])
            self._list_drawn.append(rec)
            y = rec["y1"] + rec["margin"][1]
        self._list_extent_changed()

    def _list_end_y(self):
        """Where the next row would start: below the last drawn row and
        its margin, or at the top of an empty drawing."""
        drawn = getattr(self, "_list_drawn", None)
        if not drawn:
            return 0
        return drawn[-1]["y1"] + drawn[-1]["margin"][1]

    def _list_extent(self):
        """How far the drawing reaches, as the scrollbar and every scroll
        guard must see it: (0, 0, width, bottom of the last row's margin, or
        below the empty-list message). Worked out from the rows, never from
        Tk's bbox, which starts at the first item and pads differently in Tk
        8.6.15 and 8.6.16. ISSUES_LOG, smaller lessons: _list_extent."""
        bottom = self._list_end_y()
        if not bottom:
            try:
                empty = self.canvas.bbox("list_empty")
            except tk.TclError:
                empty = None
            bottom = (empty[3] + 20) if empty else 2
        return (0, 0, self.LIST_DRAW_WIDTH, bottom)

    def _list_extent_changed(self):
        """Tell the canvas how far the drawing reaches now -- what the list
        frame's own <Configure> used to report whenever its size changed --
        and let the guard that keeps the list honest about its top look."""
        try:
            self.canvas.configure(scrollregion=self._list_extent())
        except tk.TclError:
            return
        self._sync_list_scroll()

    def _reflow_list(self, start=0):
        """Move every drawn row from `start` on to its place below the row
        before it, by moving items, in one repaint. Rows that move alike move
        as one tagged band (a tag per row cost rows x items: 2.6 s at 5,000
        notes), trusted only if it holds exactly its rows' items; hidden tick
        marks join by id, since a search for what lies inside skips them.
        ISSUES_LOG, smaller lessons: _reflow_list."""
        drawn = self._list_drawn
        y = 0
        if start > 0:
            y = drawn[start - 1]["y1"] + drawn[start - 1]["margin"][1]
        runs = []                       # [dy, first row, last row]
        for i in range(start, len(drawn)):
            rec = drawn[i]
            dy = y + rec["margin"][0] - rec["y0"]
            if dy:
                if runs and runs[-1][0] == dy and runs[-1][2] == i - 1:
                    runs[-1][2] = i
                else:
                    runs.append([dy, i, i])
            y = rec["y1"] + dy + rec["margin"][1]
        cv = self.canvas
        bands = []
        for n, (dy, first, last) in enumerate(runs):
            tag = "reflow%d" % n
            # Rows stand at least 7px apart (their margins); three pixels
            # either side is room for how Tk pads a bbox, and no more.
            cv.addtag_enclosed(tag, -10, drawn[first]["y0"] - 3,
                               self.LIST_DRAW_WIDTH + 10, drawn[last]["y1"] + 3)
            for i in range(first, last + 1):
                mark = drawn[i]["items"].get("mark")
                if mark is not None:
                    cv.addtag_withtag(tag, mark)
            owned = sum(len(drawn[i]["items"]) for i in range(first, last + 1))
            bands.append((tag, dy, first, last,
                          len(cv.find_withtag(tag)) == owned))
        for tag, dy, first, last, whole in bands:
            if whole:
                cv.move(tag, 0, dy)
            else:
                for i in range(first, last + 1):
                    cv.move(drawn[i]["tag"], 0, dy)
            cv.dtag(tag)
            for i in range(first, last + 1):
                drawn[i]["y0"] += dy
                drawn[i]["y1"] += dy
        self._list_extent_changed()

    def _list_view_changed(self, first, last):
        """The canvas's yscrollcommand: the scrollbar hears which part is in
        view, and while rows wait, a top-up is asked for, once per idle. Every
        way the view moves -- wheel, scrollbar, a taller window, a drawn step
        -- comes through here, which makes it the one place to watch."""
        try:
            self._list_scrollbar.set(first, last)
        except (tk.TclError, AttributeError):
            return
        self._ask_for_top_up()

    def _ask_for_top_up(self):
        """Look, once the app is idle, whether more rows should be drawn --
        unless nothing waits, or a look is already on its way."""
        if (getattr(self, "_list_pending", None)
                and getattr(self, "_list_top_up_job", None) is None):
            self._list_top_up_job = self.after_idle(self._top_up_list)

    def _top_up_list(self):
        """Draw another step of rows if less than a screen of drawn list is
        left below the view. Drawing lengthens the content, the canvas
        reports it, and this runs again -- until there is a screen to
        spare or nothing left to draw."""
        self._list_top_up_job = None
        if not getattr(self, "_list_pending", None) or not self._still_alive():
            return
        try:
            view_h = self.canvas.winfo_height()
            left_below = self._list_extent()[3] - self.canvas.canvasy(view_h)
        except tk.TclError:
            return
        if left_below < view_h:
            self._draw_list_rows(self.LIST_DRAW_STEP)

    def _draw_group_header(self, cat, notes_in_group, collapsed, top):
        """One collapsible category header, drawn with its top at `top`."""
        cv = self.canvas
        c = self.colors
        self._header_seq = getattr(self, "_header_seq", 0) + 1
        tag = "hdr%d" % self._header_seq
        tags = ("row", tag)
        color = CATEGORY_COLORS.get(cat, c["accent"])
        bottom = top + self.HEADER_HEIGHT
        mid = top + self.HEADER_HEIGHT // 2
        items = {}
        # Across the whole row, like the frame it replaces: a click anywhere
        # on the header's line folds the group, not only on its words.
        items["bg"] = cv.create_rectangle(
            0, top, self.LIST_DRAW_WIDTH, bottom, fill=c["sidebar"],
            outline="", tags=tags)
        items["dot"] = cv.create_oval(
            self.px(5), mid - self.px(4), self.px(13), mid + self.px(4),
            fill=color, outline=color, tags=tags)
        items["caret"] = cv.create_text(
            self.px(23), mid, anchor="w", text=("▶" if collapsed else "▼"),
            font=("Segoe UI", 8), fill=c["subtext"], tags=tags)
        caret_right = cv.bbox(items["caret"])[2]
        label_x = caret_right + 10
        items["label"] = cv.create_text(
            label_x, mid, anchor="w",
            text=self._header_label_text(cat, len(notes_in_group), label_x),
            font=self.HEADER_FONT, fill=c["text"], tags=tags)
        # The keyboard's ring, drawn the way a card's is: the header is a
        # stop on the keyboard's walk. The header's own fill when the ring
        # is elsewhere, which is no ring at all.
        items["ring"] = cv.create_rectangle(
            self.CARD_INSET_X + 1, top + 1,
            self.LIST_DRAW_WIDTH - self.CARD_INSET_X - 1, bottom - 1,
            width=self.CARD_RING, outline=self._header_ring_color(cat),
            tags=tags)
        # The ids, not the cards: a collapsed group draws no cards at
        # all, and its header still has to show the right number.
        rec = {"kind": "header", "key": ("header", cat), "tag": tag,
               "cat": cat, "ids": [n["id"] for n in notes_in_group],
               "collapsed": collapsed, "y0": top, "y1": bottom,
               "margin": self.HEADER_MARGIN, "items": items,
               "label_x": label_x}
        self._group_headers[cat] = rec
        return rec

    def _header_label_text(self, cat, count, left):
        """What a category header says -- its name and note count -- fitted
        between `left` and the edge the card texts keep to. The count always
        shows (on a folded group it is all there is); a long name (up to 80
        characters) gives way to an ellipsis instead of running off the edge."""
        font = getattr(self, "_header_font", None)
        if font is None:
            # A Font object, not the tuple: _ellipsize measures a tuple
            # with its family and size only, and this one is bold.
            font = self._header_font = tkfont.Font(
                family=self.HEADER_FONT[0], size=self.HEADER_FONT[1],
                weight=self.HEADER_FONT[2])
        tail = f" ({count})"
        right = self.LIST_DRAW_WIDTH - self.CARD_INSET_X - self.CARD_PAD[0]
        room = max(1, right - left - font.measure(tail))
        return self._ellipsize(cat, font, room) + tail

    def _sort_notes(self, notes, choice=None):
        """Sort the list in place according to the chosen sort option -- or
        to `choice`, when the question is how the list WAS sorted. All keys
        coerce missing/None fields to safe defaults so a single odd note can't
        crash the whole list."""
        if choice is None:
            choice = self.sort_var
            choice = choice.get() if choice is not None else "Recently updated"

        def _s(n, key):
            v = n.get(key, "")
            return v if isinstance(v, str) else ""

        if choice == self.SORT_CUSTOM:
            # Where a person put each note; one nobody placed yet (new, or from
            # a share code) stands above, newest first, where it was just made.
            # Two passes, the second stable.
            notes.sort(key=lambda n: (_s(n, "created"), n.get("id") or 0),
                       reverse=True)
            notes.sort(key=lambda n: (0, 0) if "order" not in n
                       else (1, n["order"]))
        elif choice == "Recently updated":
            notes.sort(key=lambda n: _s(n, "updated"), reverse=True)
        elif choice == "Oldest updated":
            notes.sort(key=lambda n: _s(n, "updated"))
        elif choice == "Title A–Z":
            # Untitled notes sink to the bottom rather than clustering at top.
            # Folded as a search folds: by code point, É and every letter
            # with a mark came after Z.
            notes.sort(key=lambda n: (not _s(n, "title").strip(),
                                      fold_for_search(_s(n, "title")), _s(n, "title")))
        elif choice == "Title Z–A":
            # Untitled notes sink here too: A–Z's whole key reversed raised
            # them to the top, so their mark is turned over before the reverse.
            notes.sort(key=lambda n: (bool(_s(n, "title").strip()),
                                      fold_for_search(_s(n, "title")), _s(n, "title")),
                       reverse=True)
        elif choice == "Category":
            notes.sort(key=lambda n: (fold_for_search(_s(n, "category")), _s(n, "category"),
                                      _s(n, "updated")),
                       reverse=False)
        elif choice == "Calendar: soonest":
            # Each note's NEXT relevant date from today (a series by its next
            # occurrence): upcoming first, then the past newest first, then
            # the undated.
            today = datetime.now().strftime("%Y-%m-%d")

            def _inv(d):
                # Lexicographic inversion, so an ascending sort reads the
                # past newest-first without a second sorting pass.
                return "".join(chr(0x10FFFF - ord(c)) for c in d)

            def soonest_key(n):
                if is_recurring(n):
                    nxt = next_occurrence_on_or_after(n, today)
                    if nxt:
                        return (0, nxt)
                    # The series already ended: rank it with the past by
                    # its start date (its last occurrence would cost a
                    # full expansion here, for a rare case).
                    d = _s(n, "date")
                    return (1, _inv(d)) if parse_date(d) else (2, "")
                d = _s(n, "date")
                if not parse_date(d):
                    return (2, "")
                return (0, d) if d >= today else (1, _inv(d))
            notes.sort(key=soonest_key)
        elif choice == "Calendar: oldest":
            # Plain chronology by the note's own date — the archive walk.
            def date_key(n):
                d = _s(n, "date")
                has = bool(parse_date(d))
                return (not has, d if has else "", )
            notes.sort(key=date_key)

        # Pinned notes always float to the top, keeping their relative order
        # from the chosen sort. Python's sort is stable, so this preserves it.
        notes.sort(key=lambda n: not n.get("pinned", False))

    # ---------- Custom order: the list arranged by hand ----------

    def _on_sort_chosen(self, value):
        """The Sort dropdown's choice. Custom order chosen before anything was
        placed starts from the order the list was showing; chosen after a move
        replaced an arrangement made by hand (_move_note), it asks once whether
        to bring that back. ISSUES_LOG, smaller lessons: the Custom order
        offer."""
        replaced = getattr(self, "_replaced_custom_order", None)
        if value == self.SORT_CUSTOM and replaced is not None:
            self._replaced_custom_order = None
            marks, sort_before = replaced
            if (self._put_back_custom_order(marks, dry_run=True)
                    and self.ask_yes_no(
                        "Bring back your Custom order?",
                        f"Moving a note while the list was sorted by "
                        f"{sort_before} started Custom order again from that "
                        f"sort, and the arrangement you had made by hand was "
                        f"replaced.\n\n"
                        f"Bring back the arrangement you made by hand? Moves "
                        f"made since then will be undone. With No, the list "
                        f"stays as it is now, and this is not asked again.",
                        icon="question")):
                self._put_back_custom_order(marks)
                self.save_notes()
                self.set_status("Put back your Custom order")
        if (value == self.SORT_CUSTOM
                and not any("order" in n for n in self.notes)):
            before = getattr(self, "_sort_shown", None)
            if before and before != self.SORT_CUSTOM:
                self._place_notes_as_sorted(before)
                self.save_notes()
        self.refresh_note_list()

    def _place_notes_as_sorted(self, choice):
        """Give every note its place in Custom order from the way `choice`
        sorts them -- all of them, not only those a search lets through,
        so what a filter hides keeps its place among the rest."""
        everything = list(self.notes)
        self._sort_notes(everything, choice=choice)
        for place, note in enumerate(everything):
            note["order"] = place

    def _same_list_block(self, a, b):
        """Whether two notes may trade places: both pinned or both not, and
        -- in a grouped list -- in the same group. A pinned note always
        stands above the rest, and a group is its category; a move that
        crossed either would be undone by the next rebuild."""
        if bool(a.get("pinned")) != bool(b.get("pinned")):
            return False
        grouped = self.group_by_category
        if grouped is not None and grouped.get():
            return self._list_group_of(a) == self._list_group_of(b)
        return True

    def _move_note(self, note_id, before_id=None, after_id=None):
        """Put a note just before or just after another in Custom order, and
        show the list so. From another sort, Custom order starts from the order
        shown, every note numbered again in one pass; a move is not an edit.
        An arrangement made by hand that this replaces is offered back.
        ISSUES_LOG, smaller lessons: the Custom order offer."""
        note = self.find_note(note_id)
        anchor = self.find_note(before_id if before_id is not None else after_id)
        if note is None or anchor is None or anchor is note:
            return False
        replaced = None
        was = None
        by_hand = self.sort_var.get() == self.SORT_CUSTOM
        if not by_hand:
            sort_before = self.sort_var.get()
            # What every note carried, held by the note itself: an id freed
            # by a delete while the toast is up can name a new note by then.
            marks = [(n, "order" in n, n.get("order")) for n in self.notes]
            placed = [n for n in self.notes if "order" in n]
            was_notes = sorted(placed, key=lambda n: n["order"])
            was = [id(n) for n in was_notes]
            self._place_notes_as_sorted(sort_before)
            self.sort_var.set(self.SORT_CUSTOM)
            # Replaced only if the notes placed by hand no longer stand in
            # the order they were put in; a renumbering that keeps it is
            # not a loss, and says nothing.
            now = [id(n) for n in sorted(placed, key=lambda n: n["order"])]
            if was != now:
                replaced = (marks, sort_before)
        everything = list(self.notes)
        self._sort_notes(everything, choice=self.SORT_CUSTOM)
        if by_hand:
            self._custom_order_knows(everything)
        everything.remove(note)
        at = everything.index(anchor) + (0 if before_id is not None else 1)
        everything.insert(at, note)
        for place, each in enumerate(everything):
            each["order"] = place
        self.save_notes()
        # A drop and Alt+Up/Down put the ring on the moved card next.
        self._show_note_moved(note["id"], keep_ring=True)
        if replaced is not None:
            # Kept beyond the toast, for _on_sort_chosen: the newest arrangement
            # made by hand, judged by the order it left, not by the moves made.
            # ISSUES_LOG, smaller lessons: the Custom order offer.
            if (getattr(self, "_replaced_custom_order", None) is None
                    or self._arranged_since_last_replace(was_notes)):
                self._replaced_custom_order = replaced
            self._custom_order_left = [self._order_identity(n)
                                       for n in everything]
            self._show_toast(
                f"Custom order started again from {replaced[1]}",
                action=lambda: self._undo_custom_order(*replaced))
        return True

    @staticmethod
    def _order_identity(note):
        """A note as anything kept across a session knows it (the Custom
        order offer, the Share panel's ticks, History's open groups): by its
        uid, which a note back from the Trash keeps and a new note's reused
        id does not."""
        return note.get("uid") or id(note)

    def _arranged_since_last_replace(self, was_notes):
        """Whether the Custom order a move in a sorted view replaces (its placed
        notes, in order) was arranged by hand since the last such move: whether
        the notes both know stand in another order now. A note deleted since
        arranges nothing; one that move did not know is placed in the record
        by _custom_order_knows."""
        left = getattr(self, "_custom_order_left", None)
        if left is None or was_notes is None:
            return True
        was = [self._order_identity(n) for n in was_notes]
        common = set(left) & set(was)
        return ([i for i in was if i in common]
                != [i for i in left if i in common])

    def _custom_order_knows(self, shown):
        """Put the notes the last move in a sorted view did not know into its
        record (_custom_order_left), each just under the known note it stands
        under in *shown*, so a move past a new note compares like any other.
        ISSUES_LOG, smaller lessons: the Custom order offer."""
        left = getattr(self, "_custom_order_left", None)
        if left is None:
            return
        known = set(left)
        under = {}
        above = None
        for each in shown:
            i = self._order_identity(each)
            if i in known:
                above = i
            else:
                under.setdefault(above, []).append(i)
        if not under:
            return
        record = list(under.get(None, ()))
        for i in left:
            record.append(i)
            record.extend(under.get(i, ()))
        self._custom_order_left = record

    def _undo_custom_order(self, marks, sort_before):
        """Put back the arrangement a move replaced, and the sort the move
        was made in (see _move_note) -- the moves made on top of the new
        one since go with it, because they were made on the replacement."""
        # The offer kept for the session ends here only if it is this
        # toast's own; a later move's toast puts back that move's.
        kept = getattr(self, "_replaced_custom_order", None)
        if kept is not None and kept[0] is marks:
            self._replaced_custom_order = None
        self._put_back_custom_order(marks)
        # What this puts back was not arranged by hand since that move: a
        # later move in a sorted view keeps the offer it finds.
        placed = [n for n in self.notes if "order" in n]
        self._custom_order_left = [
            self._order_identity(n)
            for n in sorted(placed, key=lambda n: n["order"])]
        self.save_notes()
        self.sort_var.set(sort_before)
        self.refresh_note_list()
        self.set_status(f"Put back your Custom order; the list is sorted by "
                        f"{sort_before} again")

    def _put_back_custom_order(self, marks, dry_run=False):
        """Give every note in `marks` -- (note, had a place, the place), as
        _move_note took them -- the place it had or its having none; with
        dry_run, only count. Returns how many places change. A note is found
        by the dict or by its uid, so one back from the Trash (a new dict)
        gets its place back too; a note made since keeps its own."""
        present = {id(n) for n in self.notes}
        by_uid = {n.get("uid"): n for n in self.notes if n.get("uid")}
        changed = 0
        for note, had, old in marks:
            target = note if id(note) in present else by_uid.get(
                note.get("uid") or None)
            if target is None:
                continue
            if ("order" in target) == had and (not had
                                               or target["order"] == old):
                continue
            changed += 1
            if dry_run:
                continue
            if had:
                target["order"] = old
            else:
                target.pop("order", None)
        return changed

    def _list_move_by_keyboard(self, delta):
        """Alt+Up or Alt+Down: the card with the ring moves one place, and
        the ring goes with it."""
        nid = getattr(self, "_focused_note_id", None)
        note = self.find_note(nid) if nid is not None else None
        if note is None or self.selection_mode:
            return "break"
        block = [row[1]["id"] for row in self._list_rows()
                 if row[0] == "note" and self._same_list_block(row[1], note)]
        if nid not in block:
            return "break"
        at = block.index(nid) + delta
        if not 0 <= at < len(block):
            return "break"
        if delta < 0:
            moved = self._move_note(nid, before_id=block[at])
        else:
            moved = self._move_note(nid, after_id=block[at])
        if moved:
            self._put_keyboard_on_card(nid)
        return "break"

    # ---------- Custom order: dragging a card ----------

    def _list_drag_arm(self, rec, event):
        """A press on a card that might become a drag: remembered, nothing
        drawn yet. It becomes one only after the pointer has travelled
        DRAG_THRESHOLD pixels, so an ordinary click never moves anything."""
        try:
            cy = self.canvas.canvasy(event.y)
        except tk.TclError:
            return
        self._drag = {"nid": rec["note"]["id"], "press_y": cy,
                      "grab_dy": cy - rec["y0"], "started": False,
                      "offset": 0, "slot": None, "line": None,
                      "pointer_y": event.y, "press_wy": event.y,
                      "scroll_job": None,
                      # Pressed in the open list, an edge may scroll at once;
                      # pressed at an edge (or a slip from one), only once the
                      # pointer has left it or stayed there a moment.
                      "edge_free": not self._list_near_edge(event.y),
                      "edge_since": None, "edge_beats": 0}

    def _list_dragged(self, event):
        """The pointer moving with the button down."""
        drag = getattr(self, "_drag", None)
        if not drag:
            return
        if not drag["started"]:
            # How far the HAND has moved, in widget pixels: in canvas pixels a
            # view moved under a held button (a restore landing after the
            # press) counted as travel, and a 1px jitter started a drag.
            if abs(event.y - drag["press_wy"]) < self.DRAG_THRESHOLD:
                return
            if not self._start_list_drag():
                self._drag = None
                return
        drag["pointer_y"] = event.y
        self._follow_list_drag()
        self._scroll_list_drag_near_edge()

    def _start_list_drag(self):
        """Lift the card: it is drawn over the others and follows the
        pointer, and a line shows where it would land. Nothing is moved
        in the notebook until the button is let go."""
        drag = self._drag
        rec = (getattr(self, "_note_cards", None) or {}).get(drag["nid"])
        if rec is None:
            return False
        cv = self.canvas
        try:
            cv.tag_raise(rec["tag"])
            drag["line"] = cv.create_line(
                self.CARD_INSET_X, -10, self.LIST_DRAW_WIDTH - self.CARD_INSET_X, -10,
                width=3, fill=self.colors["accent"], tags=("row", "drag_line"))
            cv.configure(cursor="fleur")
            # Said where the pointer's own shape is remembered, too: left
            # saying "hand2", _list_pointer_moved saw nothing to change and
            # the four-way arrow outlived the drag over every card.
            self._list_cursor = "fleur"
        except tk.TclError:
            return False
        drag["started"] = True
        return True

    def _follow_list_drag(self):
        """Keep the lifted card under the pointer and the line at the slot
        it would drop into. The card's record is left where it was: only
        its drawing moves, so a step of rows drawn below while the list
        scrolls under a drag still finds everything where it stands."""
        drag = self._drag
        rec = self._note_cards.get(drag["nid"])
        if rec is None:
            return
        cv = self.canvas
        try:
            cy = cv.canvasy(drag["pointer_y"])
            view_top = cv.canvasy(0)
            view_bottom = cv.canvasy(cv.winfo_height())
        except tk.TclError:
            return
        # Under the pointer, but never out of sight: carried past an edge, the
        # card stays there while the list scrolls under it (photographed
        # without this: a line at the top, and its card nowhere).
        top = cy - drag["grab_dy"]
        top = max(view_top, min(top, view_bottom - (rec["y1"] - rec["y0"])))
        dy = top - (rec["y0"] + drag["offset"])
        if dy:
            cv.move(rec["tag"], 0, dy)
            drag["offset"] += dy
        slot = self._list_drop_slot(rec, cy)
        drag["slot"] = slot
        if slot is None:
            cv.coords(drag["line"], 0, -10, 0, -10)
            return
        kind, other = slot
        target = self._note_cards[other]
        if kind == "before":
            y = target["y0"] - target["margin"][0] / 2.0
        else:
            y = target["y1"] + target["margin"][1] / 2.0
        cv.coords(drag["line"], self.CARD_INSET_X, y,
                  self.LIST_DRAW_WIDTH - self.CARD_INSET_X, y)

    def _list_drop_slot(self, rec, cy):
        """Where the lifted card would land for a pointer at canvas y `cy`:
        ("before", id) or ("after", id), among the drawn cards it may trade
        places with -- or None when that is where it already stands."""
        note = rec["note"]
        block = [r for r in self._list_drawn
                 if r["kind"] == "note" and r is not rec
                 and self._same_list_block(r["note"], note)]
        if not block:
            return None
        slot = None
        for r in block:
            if cy < (r["y0"] + r["y1"]) / 2.0:
                slot = ("before", r["note"]["id"])
                break
        if slot is None:
            slot = ("after", block[-1]["note"]["id"])
        # Dropping a card right where it is moves nothing, and says so by
        # showing no line.
        order = [r["note"]["id"] for r in self._list_drawn
                 if r["kind"] == "note" and self._same_list_block(r["note"], note)]
        at = order.index(note["id"])
        if slot == ("before", order[at + 1] if at + 1 < len(order) else None):
            return None
        if slot == ("after", order[at - 1] if at > 0 else None):
            return None
        return slot

    def _list_edge_depth(self, y):
        """How far a pointer at widget y is inside the list's top or bottom
        edge, and which way a drag there scrolls the list: (depth, -1 or 1),
        or None in the open list between the two."""
        try:
            height = self.canvas.winfo_height()
        except tk.TclError:
            return None
        if y < self.DRAG_EDGE:
            return self.DRAG_EDGE - y, -1
        if y > height - self.DRAG_EDGE:
            return y - (height - self.DRAG_EDGE), 1
        return None

    def _list_near_edge(self, y):
        """Whether widget y is at the list's top or bottom edge, or a slip
        away from it. A press a pixel or three outside the edge counted as
        one in the open list, so a hand that slipped into the edge
        scrolled the list at once and dropped the card a place away; the
        same press a few pixels further in waited, as a slip should."""
        slip = 2 * self.DRAG_THRESHOLD
        return any(self._list_edge_depth(y + d) is not None
                   for d in (0, -slip, slip))

    def _scroll_list_drag_near_edge(self):
        """Near the list's top or bottom a drag scrolls it, a step at a time,
        or a card could never go further than the list shows. A drag that
        BEGAN there waits until the pointer has been out in the open list or
        held the edge for DRAG_EDGE_DWELL_MS, and every arrival starts slowly
        (_list_drag_scroll_step). ISSUES_LOG, smaller lessons: dragging at the
        list's edge."""
        drag = getattr(self, "_drag", None)
        if not drag or not drag["started"]:
            return
        if self._list_edge_depth(drag["pointer_y"]) is None:
            # Out in the open list: an edge reached from here scrolls
            # without waiting, from its slowest step again -- once the
            # pointer is clear of the edge, not a slip away from it.
            if not self._list_near_edge(drag["pointer_y"]):
                drag["edge_free"] = True
            drag["edge_since"] = None
            drag["edge_beats"] = 0
            if drag["scroll_job"] is not None:
                self.after_cancel(drag["scroll_job"])
                drag["scroll_job"] = None
            return
        if drag["edge_since"] is None:
            drag["edge_since"] = time.monotonic()
        if drag["scroll_job"] is None:
            delay = self.DRAG_SCROLL_MS
            if not drag["edge_free"]:
                waited = (time.monotonic() - drag["edge_since"]) * 1000
                delay = max(delay, int(self.DRAG_EDGE_DWELL_MS - waited) + 1)
            drag["scroll_job"] = self.after(delay, self._list_drag_scroll_step)

    def _list_drag_scroll_step(self):
        """One beat of a drag's scrolling at the list's edge: from a tenth of
        the view a beat at the edge to the whole view beyond it, the first
        beats at an edge ramping up over DRAG_SCROLL_RAMP. ISSUES_LOG, smaller
        lessons: dragging at the list's edge."""
        drag = getattr(self, "_drag", None)
        if not drag or not drag["started"]:
            return
        drag["scroll_job"] = None
        edge = self._list_edge_depth(drag["pointer_y"])
        if edge is None:
            return
        if not drag["edge_free"]:
            if ((time.monotonic() - drag["edge_since"]) * 1000
                    < self.DRAG_EDGE_DWELL_MS):
                # Still a hand that slipped, as far as anyone can tell.
                self._scroll_list_drag_near_edge()
                return
            drag["edge_free"] = True
        depth, direction = edge
        drag["edge_beats"] += 1
        try:
            unit = self.canvas.winfo_height() / 10.0
            top = self.canvas.canvasy(0)
        except tk.TclError:
            return
        step = min(10, 1 + int(depth) // 8) * unit * min(
            1.0, drag["edge_beats"] / float(self.DRAG_SCROLL_RAMP))
        self._list_scrolled_by_hand()
        self._apply_list_scroll_px(top + direction * max(1, round(step)))
        self._follow_list_drag()
        self._scroll_list_drag_near_edge()

    def _list_released(self, _event=None):
        """The button let go: a drag drops its card where the line was; a
        press that never became a drag has already done what a click does."""
        drag = getattr(self, "_drag", None)
        self._drag = None
        if not drag or not drag["started"]:
            return
        self._end_list_drag(drag)
        slot = drag["slot"]
        if slot is None:
            self._put_lifted_card_back(drag)
            return
        kind, other = slot
        nid = drag["nid"]
        if kind == "before":
            moved = self._move_note(nid, before_id=other)
        else:
            moved = self._move_note(nid, after_id=other)
        if not moved:
            self._put_lifted_card_back(drag)
            return
        self._put_keyboard_on_card(nid)

    def _list_drag_escape(self, _event=None):
        """Escape during a drag puts the card back and moves nothing."""
        drag = getattr(self, "_drag", None)
        if not drag or not drag["started"]:
            return None
        self._cancel_list_drag()
        return "break"

    def _cancel_list_drag(self):
        """Stop a drag in progress, if there is one, and put its card back
        -- also when the list is about to change under it (a rebuild, a
        save redrawing a card, a delete), which would otherwise reflow the
        rows around a card whose drawing is not where its record says."""
        drag = getattr(self, "_drag", None)
        self._drag = None
        if not drag or not drag["started"]:
            return
        self._end_list_drag(drag)
        self._put_lifted_card_back(drag)

    def _end_list_drag(self, drag):
        if drag.get("scroll_job") is not None:
            try:
                self.after_cancel(drag["scroll_job"])
            except (tk.TclError, ValueError):
                pass
            drag["scroll_job"] = None
        try:
            if drag.get("line") is not None:
                self.canvas.delete(drag["line"])
            self.canvas.configure(cursor="")
        except tk.TclError:
            pass
        self._list_cursor = ""

    def _put_lifted_card_back(self, drag):
        rec = (getattr(self, "_note_cards", None) or {}).get(drag["nid"])
        if rec is None or not drag.get("offset"):
            return
        try:
            self.canvas.move(rec["tag"], 0, -drag["offset"])
        except tk.TclError:
            pass
        drag["offset"] = 0

    def _bind_list_input(self):
        """The list's mouse and keyboard, bound once on the canvas that draws
        it (a card is a drawing, with no bindings of its own). The list is
        walkable: Down and Up move the ring, Enter or Space does what a click
        does, and the menu key opens the note's own menu at the note."""
        cv = self.canvas
        cv.bind("<Button-1>", self._list_pressed)
        # Tk hands the second press of a double-click to this instead of
        # <Button-1>; it goes where the first press went.
        cv.bind("<Double-Button-1>", self._list_double_pressed)
        cv.bind("<Button-3>", self._list_right_pressed)
        cv.bind("<Motion>", self._list_pointer_moved)
        cv.bind("<Leave>", self._list_pointer_left)
        # A card can be dragged to another place (Custom order): the press
        # above arms it, these carry it and drop it, Escape puts it back.
        cv.bind("<B1-Motion>", self._list_dragged)
        cv.bind("<ButtonRelease-1>", self._list_released)
        cv.bind("<Escape>", self._list_drag_escape)
        cv.bind("<Down>", lambda _e: self._list_step(1))
        cv.bind("<Up>", lambda _e: self._list_step(-1))
        # A grouped list folds and opens from the keyboard, as a tree does.
        cv.bind("<Left>", lambda _e: self._list_fold_by_keyboard(True))
        cv.bind("<Right>", lambda _e: self._list_fold_by_keyboard(False))
        cv.bind("<Alt-Down>", lambda _e: self._list_move_by_keyboard(1))
        cv.bind("<Alt-Up>", lambda _e: self._list_move_by_keyboard(-1))
        cv.bind("<Return>", self._list_activate)
        cv.bind("<space>", self._list_activate)
        # The menu key is "App" on Windows and "Menu" on X11, and Tk RAISES on
        # an unknown keysym: bound unguarded, it took the whole list down on
        # the Linux image while Windows stayed green.
        for seq in ("<Shift-F10>", "<App>", "<Menu>"):
            try:
                cv.bind(seq, self._list_open_menu)
            except tk.TclError:
                pass
        cv.bind("<FocusIn>", self._list_focus_in, add="+")
        cv.bind("<FocusOut>", self._list_focus_out, add="+")

    def _list_record_at(self, x, y):
        """The drawn row under a point given in the canvas widget's own
        coordinates, or None -- the gap between two cards is nobody's."""
        try:
            cy = self.canvas.canvasy(y)
        except tk.TclError:
            return None
        if not 0 <= x <= self.LIST_DRAW_WIDTH:
            return None
        for rec in getattr(self, "_list_drawn", None) or ():
            if rec["y0"] <= cy <= rec["y1"]:
                return rec
        return None

    def _list_pressed(self, event):
        """A click on the list: a header folds its group, a card opens its note
        (or ticks it, in selection mode), and the keyboard comes to the list on
        that row. The window's own click handling still hears the click, unless
        the note's opening was refused ("break", see _list_press_row)."""
        # A card still lifted lost its release (to another window, say): it is
        # put back first, or its drawing, line and pointer shape stayed behind.
        self._cancel_list_drag()
        # Only the second press of a double-click may follow the first
        # press's aim (_list_double_pressed); any other press forgets it.
        self._list_press_aim = None
        rec = self._list_record_at(event.x, event.y)
        if rec is not None:
            return self._list_press_row(rec, event)
        return None

    def _list_double_pressed(self, event):
        """The second press of a double-click (Tk's own judgement, replacing
        <Button-1> for that press) goes where the first press went: a first
        press that opens a note can save the one left, and under a date sort
        that slides another card under the pointer. ISSUES_LOG: "The list that
        moved under the pointer"."""
        self._cancel_list_drag()
        aim = getattr(self, "_list_press_aim", None)
        self._list_press_aim = None
        rec = None
        # Only for as long as a double-click takes: a program-made event has
        # no timestamp, so two presses a minute apart read as one double-click,
        # and an old aim redirected the later press.
        if (aim is not None
                and time.monotonic() - aim[1] <= self.LIST_DOUBLE_PRESS_S):
            rec = self._list_row_record(aim[0])
        if rec is None:
            rec = self._list_record_at(event.x, event.y)
        if rec is not None:
            return self._list_press_row(rec, event)
        return None

    def _list_row_record(self, key):
        """The drawn record of the row ("note", id) or ("header", category),
        or None when that row is not drawn."""
        if key[0] == "note":
            return (getattr(self, "_note_cards", None) or {}).get(key[1])
        return (getattr(self, "_group_headers", None) or {}).get(key[1])

    def _list_press_row(self, rec, event):
        """What a press does to the row it is for (see _list_pressed)."""
        key = rec["key"]
        # Where the row stands on the SCREEN before the press acts: opening a
        # note can save the one left and move this card, and folding a group
        # near the end shortens the list under the header.
        try:
            on_screen = rec["y0"] - self.canvas.canvasy(0)
        except tk.TclError:
            return
        if rec["kind"] == "header":
            self._toggle_group_collapsed(rec["cat"])
            self._keep_row_under_pointer(key, on_screen)
        else:
            note = rec["note"]
            nid = note["id"]
            if self.selection_mode:
                self._toggle_note_selected(nid, nid not in self.selected_note_ids)
                self._paint_card_check(nid)
                self._put_keyboard_on_card(nid)
                return
            # A refused open (Cancel on a day's or a template's save question)
            # returns "break": the window's click-outside, still to run for
            # this press, would ask again, and its "No" lost the template.
            if self._open_unless_shown(note) is False:
                return "break"
            # Before the ring's scroll-into-view, which then still brings a
            # card clicked at the list's edge fully into sight.
            self._keep_row_under_pointer(key, on_screen)
            self._put_keyboard_on_card(nid)
        # A drag is armed only on a row still under the pointer: one armed on a
        # card that slid away dropped it before its neighbour on a slip, and
        # switched the list to Custom order. Else the aim is left behind.
        rec = self._list_row_record(key)
        if rec is None:
            return
        if self._list_record_at(event.x, event.y) is not rec:
            self._list_press_aim = (key, time.monotonic())
        elif rec["kind"] == "note":
            self._list_drag_arm(rec, event)

    def _keep_row_under_pointer(self, key, on_screen):
        """Scroll the list so this row stands where it stood on the screen
        -- `on_screen` pixels below the view's top -- as far as the list can
        scroll. What the hand is over stays what it was over; the saved
        note's card still goes where the sort puts it, above or below."""
        rec = self._list_row_record(key)
        if rec is None:
            return
        try:
            top = self.canvas.canvasy(0)
        except tk.TclError:
            return
        want = rec["y0"] - on_screen
        if abs(want - top) < 1:
            return
        # Held like a rebuild's restore, and replacing any: this is the one
        # place the view should be now (see _restore_list_scroll).
        self._restore_list_scroll(max(0, want))

    def _list_right_pressed(self, event):
        """Right-click on a card opens that note's menu, without Open (a plain
        click opens it). During a drag it cancels the drag and opens nothing:
        the drawing under the pointer is the lifted card, the record there
        its neighbour's."""
        drag = getattr(self, "_drag", None)
        if drag and drag["started"]:
            self._cancel_list_drag()
            return
        rec = self._list_record_at(event.x, event.y)
        if rec is None or rec["kind"] != "note":
            return
        self.show_note_context_menu(event, rec["note"], click_opens=True)

    def _list_pointer_moved(self, event):
        """The hand over a row, the plain pointer over the gaps -- what each
        card and header widget's own cursor used to say."""
        # This hears motion with the button UP (<B1-Motion> takes it while
        # the button is down), so a card still lifted here lost its
        # release: it goes back before anything else is decided.
        drag = getattr(self, "_drag", None)
        if drag and drag["started"]:
            self._cancel_list_drag()
        want = "hand2" if self._list_record_at(event.x, event.y) else ""
        if getattr(self, "_list_cursor", None) != want:
            self._list_cursor = want
            try:
                self.canvas.configure(cursor=want)
            except tk.TclError:
                pass

    def _list_pointer_left(self, _event=None):
        self._list_cursor = ""
        try:
            self.canvas.configure(cursor="")
        except tk.TclError:
            pass

    def _list_step(self, delta):
        """Down or Up on the list: the ring moves one row along -- a card,
        or the header of a group when the list is grouped."""
        key = self._ring_row()
        if key is None:
            first = self._first_ring_row()
            if first is not None:
                self._put_keyboard_on_row(first)
            return "break"
        self._focus_row_by_offset(key, delta)
        return "break"

    def _list_fold_by_keyboard(self, fold):
        """Left folds, Right unfolds -- the tree list's keys, for a list
        grouped by category. Left on a card folds its group and takes the
        ring to the group's header; Left on an open header folds it, Right
        on a folded one opens it. Without these (and Enter on a header) a
        folded group could be opened only with the mouse, and a list with
        every group folded gave the keyboard nothing at all to do."""
        grouped = self.group_by_category
        key = self._ring_row()
        if key is None or grouped is None or not grouped.get():
            return "break"
        if key[0] == "note":
            note = self.find_note(key[1])
            if not fold or note is None:
                return "break"
            cat = self._list_group_of(note)
            if cat not in self.collapsed_groups:
                self._toggle_group_collapsed(cat)
            self._put_keyboard_on_header(cat)
            return "break"
        if fold != (key[1] in self.collapsed_groups):
            self._toggle_group_collapsed(key[1])
        return "break"

    def _list_activate(self, event=None):
        """Enter or Space: what a click does -- open the note, or tick it
        in selection mode, where a keyboard that opened the note instead
        would be the one route that ignores the mode. On a header, what a
        click on it does: fold or unfold its group. Enter held down presses
        once (_enter_repeats): a header folded and opened at every repeat,
        writing settings.json each time."""
        if self._enter_repeats(event):
            return "break"
        self._bring_ring_into_view()
        key = self._ring_row()
        if key is not None and key[0] == "header":
            self._toggle_group_collapsed(key[1])
            return "break"
        rec = (getattr(self, "_note_cards", None) or {}).get(
            getattr(self, "_focused_note_id", None))
        if rec is None:
            return "break"
        nid = rec["note"]["id"]
        if self.selection_mode:
            self._toggle_note_selected(nid, nid not in self.selected_note_ids)
            self._paint_card_check(nid)
        else:
            self._open_unless_shown(rec["note"])
        return "break"

    def _list_open_menu(self, _event=None):
        """The note's own menu, opened at the note rather than wherever the
        pointer happens to rest. show_note_context_menu reads nothing off
        the event but x_root and y_root -- checked, not assumed -- so a
        tiny stand-in carries the card's place on screen."""
        rec = (getattr(self, "_note_cards", None) or {}).get(
            getattr(self, "_focused_note_id", None))
        if rec is None:
            return "break"
        # At a card the person can see: the ring may have been scrolled out
        # of sight by the wheel, and the menu then opened hundreds of pixels
        # off the screen. The place is kept to the list, too, whatever it is.
        self._bring_ring_into_view()
        try:
            y_on_screen = max(0, min(self.canvas.winfo_height(),
                                     rec["y1"] - self.canvas.canvasy(0)))
            self.show_note_context_menu(
                type("KeyEvent", (), {
                    "x_root": self.canvas.winfo_rootx() + 30,
                    "y_root": self.canvas.winfo_rooty() + int(y_on_screen) - 4,
                })(),
                rec["note"], click_opens=True)
        except tk.TclError:
            pass
        return "break"

    def _list_focus_in(self, _event=None):
        """The keyboard arrived on the list: the ring shows on the row it was
        last on, else the open note's card, else the first row -- always in
        sight. Scrolled away by the person, it moves to the first row in view;
        moved away by the list (a save, a search), its row is brought back into
        view, so Enter never acts on a note out of sight or on another one.
        ISSUES_LOG, smaller lessons: _list_focus_in."""
        self._keyboard_on_card = True
        by_hand = getattr(self, "_list_hand_scrolled", False)
        own = self._ring_row()
        if own is None and not by_hand:
            # Not drawn: a rebuild made while the keyboard was elsewhere
            # draws no further than the view needs.
            own = self._draw_down_to_ring()
        if own is None:
            cards = getattr(self, "_note_cards", None) or {}
            if self.selected_note_id in cards:
                self._set_ring_row(("note", self.selected_note_id))
            else:
                first = self._first_ring_row()
                if first is not None:
                    self._set_ring_row(first)
        key = self._ring_row()
        if key is not None:
            rec = self._list_row_record(key)
            seen = self._row_on_screen(rec)
            if seen == "none" and (by_hand or key != own):
                shown = self._rows_on_screen()
                if shown:
                    self._set_ring_row(shown[0])
                    # The row it left, repainted now that it is not there.
                    self._paint_row(key)
            elif seen != "all":
                self._scroll_row_into_view(rec)
        self._list_hand_scrolled = False
        self._paint_ring_row()

    def _ring_index_in(self, rows):
        """Where the ring's row stands among `rows` (as _list_rows gives
        them, drawn or waiting), or None when it is not among them."""
        wanted = getattr(self, "_focused_note_id", None)
        header = getattr(self, "_focused_header", None)
        for index, row in enumerate(rows):
            if ((row[0] == "note" and row[1].get("id") == wanted)
                    or (row[0] == "header" and row[1] == header)):
                return index
        return None

    def _draw_down_to_ring(self):
        """Draw the waiting rows down to the ring's, when the list still
        shows it, and return its key -- else None."""
        index = self._ring_index_in(getattr(self, "_list_pending", None) or ())
        if index is None:
            return None
        self._draw_list_rows(index + 1)
        return self._ring_row()

    def _row_on_screen(self, rec):
        """How much of a drawn row the view shows: "all", "part" or "none"."""
        try:
            top = self.canvas.canvasy(0)
            bottom = top + self.canvas.winfo_height()
        except tk.TclError:
            return "all"
        if rec["y0"] >= top and rec["y1"] <= bottom:
            return "all"
        if rec["y1"] <= top or rec["y0"] >= bottom:
            return "none"
        return "part"

    def _rows_on_screen(self):
        """The drawn rows the view shows whole, in screen order -- or, when
        none is whole (a row taller than the view), those it shows part of."""
        whole, part = [], []
        for rec in getattr(self, "_list_drawn", None) or ():
            seen = self._row_on_screen(rec)
            if seen == "all":
                whole.append(rec["key"])
            elif seen == "part":
                part.append(rec["key"])
        return whole or part

    def _bring_ring_into_view(self):
        """Scroll the ring's row into view, if it has one -- before anything
        the keyboard does to it, so no key acts on a row out of sight."""
        key = self._ring_row()
        if key is not None:
            rec = self._list_row_record(key)
            if self._row_on_screen(rec) != "all":
                self._scroll_row_into_view(rec)
            # In sight again: a scroll made before this no longer counts.
            self._list_hand_scrolled = False

    def _list_focus_out(self, _event=None):
        """The keyboard left the list: the ring goes back to saying only
        which note is open. A drag cannot outlive it either -- the window
        losing the keyboard (Alt+Tab, another program) is exactly how a
        release goes missing -- so a lifted card goes back."""
        self._cancel_list_drag()
        self._keyboard_on_card = False
        self._paint_ring_row()

    def _ring_row(self):
        """The drawn row the keyboard's ring is on, as ("note", id) or
        ("header", category) -- or None when that row is not drawn."""
        cat = getattr(self, "_focused_header", None)
        if cat is not None:
            key = ("header", cat)
        else:
            key = ("note", getattr(self, "_focused_note_id", None))
        return key if self._list_row_record(key) is not None else None

    def _first_ring_row(self):
        """Where a ring with nowhere to be goes: the first card, else --
        a list whose every group is folded -- the first header."""
        order = self._card_order()
        if order:
            return ("note", order[0])
        keys = self._list_drawn_keys
        return keys[0] if keys else None

    def _set_ring_row(self, key):
        """Put the ring's place on this row, without painting or scrolling:
        on a card, _focused_note_id says which; on a header, _focused_header
        does, and no card holds the ring."""
        if key[0] == "header":
            self._focused_header = key[1]
            self._focused_note_id = None
        else:
            self._focused_header = None
            self._focused_note_id = key[1]

    def _paint_ring_row(self):
        """Repaint the ring where it is, card or header."""
        cat = getattr(self, "_focused_header", None)
        if cat is not None:
            self._paint_header_ring(cat)
        else:
            self._paint_ring(getattr(self, "_focused_note_id", None))

    def _paint_row(self, key):
        """Repaint one row's ring, card or header, as it should be now."""
        if key[0] == "header":
            self._paint_header_ring(key[1])
        else:
            self._paint_ring(key[1])

    def _put_keyboard_on_row(self, key):
        if key[0] == "header":
            self._put_keyboard_on_header(key[1])
        else:
            self._put_keyboard_on_card(key[1])

    def _put_keyboard_on_card(self, note_id):
        """Give the keyboard to the list, with the ring on this card, and
        bring the card into view."""
        previous = getattr(self, "_focused_note_id", None)
        header = getattr(self, "_focused_header", None)
        self._set_ring_row(("note", note_id))
        try:
            self.canvas.focus_set()
        except tk.TclError:
            return
        if header is not None:
            self._paint_header_ring(header)
        if previous != note_id:
            self._paint_ring(previous)
        self._paint_ring(note_id)
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is not None:
            self._scroll_row_into_view(rec)
            # The ring is where the person can see it, and was put there.
            self._list_hand_scrolled = False

    def _put_keyboard_on_header(self, cat):
        """The same for a category header: the ring on it, in view."""
        previous = getattr(self, "_focused_note_id", None)
        header = getattr(self, "_focused_header", None)
        self._set_ring_row(("header", cat))
        try:
            self.canvas.focus_set()
        except tk.TclError:
            return
        self._paint_ring(previous)
        if header is not None and header != cat:
            self._paint_header_ring(header)
        self._paint_header_ring(cat)
        rec = (getattr(self, "_group_headers", None) or {}).get(cat)
        if rec is not None:
            self._scroll_row_into_view(rec)
            self._list_hand_scrolled = False

    def _header_ring_color(self, cat):
        """A header's ring: the text colour while the keyboard's ring is on
        it, else the header's own fill -- no ring at all."""
        if (cat == getattr(self, "_focused_header", None)
                and getattr(self, "_keyboard_on_card", False)):
            return self.colors["text"]
        return self.colors["sidebar"]

    def _paint_header_ring(self, cat):
        rec = (getattr(self, "_group_headers", None) or {}).get(cat)
        if rec is None:
            return
        try:
            self.canvas.itemconfigure(rec["items"]["ring"],
                                      outline=self._header_ring_color(cat))
        except tk.TclError:
            pass

    def _scroll_row_into_view(self, rec):
        """Scroll the list just far enough that this row is all on screen.
        The walk used to move the keyboard onto cards scrolled out of
        sight and leave the list where it was, which looks exactly like
        the field report's "Down does nothing" (whose own cause was a
        click that never gave the list the keyboard)."""
        cv = self.canvas
        try:
            region = self._list_extent()
            height = cv.winfo_height()
            if height <= 1:
                return
            total = max(1, region[3] - region[1])
            top = cv.canvasy(0)
            margin = rec["margin"]
            if rec["y0"] - margin[0] < top:
                target = rec["y0"] - margin[0]
            elif rec["y1"] + margin[1] > top + height:
                target = rec["y1"] + margin[1] - height
            else:
                return
            # A deliberate move beats a rebuild's still-pending restore.
            self._list_restore_px = None
            cv.yview_moveto(max(0, target - region[1]) / total)
        except tk.TclError:
            pass

    def _focus_card_by_offset(self, note_id, delta):
        """Move the ring `delta` rows along the list on screen, from this
        card (see _focus_row_by_offset)."""
        self._focus_row_by_offset(("note", note_id), delta)

    def _focus_row_by_offset(self, key, delta):
        """Move the ring `delta` rows along the list on screen -- cards, and a
        grouped list's headers, which are stops too. Asked of the order the
        rows are DRAWN in, not of self.notes: sorted, filtered and grouped, the
        next note in the file is often not the one below it on screen."""
        order = self._list_drawn_keys
        if key not in order:
            return
        target = order.index(key) + delta
        # The list is drawn a step at a time (see _draw_list_rows), and
        # the keyboard must not stop where the drawing happened to: walking
        # off the end of what is drawn draws the next step first.
        while target >= len(order) and getattr(self, "_list_pending", None):
            self._draw_list_rows(self.LIST_DRAW_STEP)
            order = self._list_drawn_keys
        if 0 <= target < len(order):
            self._put_keyboard_on_row(order[target])

    def _restore_card_focus(self):
        """Repaint the keyboard's ring after a rebuild, which no longer moves
        the keyboard (the canvas survives; only the drawing is replaced). A
        ring the person could see stays in sight, the view following its row;
        one the wheel scrolled away stays there until a key acts on it
        (_bring_ring_into_view). ISSUES_LOG, smaller lessons:
        _restore_card_focus."""
        self._paint_ring_row()
        follow = getattr(self, "_ring_follow", False)
        self._ring_follow = False
        if follow and getattr(self, "_keyboard_on_card", False):
            self._bring_ring_into_view()

    def _card_ring_color(self, note_id):
        """What a card's ring says. The text colour where the keyboard is;
        accent for the note that is open; otherwise the card's own fill,
        which is no ring at all -- the thickness is on every card, so
        nothing shifts by two pixels as the ring moves down the list."""
        c = self.colors
        if (note_id == getattr(self, "_focused_note_id", None)
                and getattr(self, "_keyboard_on_card", False)):
            return c["text"]
        if note_id == self.selected_note_id:
            return c["accent"]
        return c["card"]

    def _ring_to_paint(self, note_id):
        """_card_ring_color, for a ring about to be painted -- and a note of
        whether the card is being painted as the open note. A card can be
        painted so without anyone moving the outline off another: a new
        note's first save draws its card as open, and the note before it
        kept the outline. _update_open_highlight takes it off every card
        noted here that is no longer the open one."""
        painted = self.__dict__.setdefault("_open_ring_ids", set())
        if note_id == self.selected_note_id:
            painted.add(note_id)
        else:
            painted.discard(note_id)
        return self._card_ring_color(note_id)

    def _paint_ring(self, note_id):
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None:
            getattr(self, "_open_ring_ids", set()).discard(note_id)
            return
        try:
            self.canvas.itemconfigure(
                rec["items"]["ring"], outline=self._ring_to_paint(note_id))
        except tk.TclError:
            pass

    def _paint_card_check(self, note_id):
        """Tick or untick one card's box to match selected_note_ids."""
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None or "mark" not in rec["items"]:
            return
        try:
            self.canvas.itemconfigure(
                rec["items"]["mark"],
                state="normal" if note_id in self.selected_note_ids else "hidden")
        except tk.TclError:
            pass

    def _card_texts(self, note):
        """What a note's card says, and in which colour. The one definition
        the card is drawn from, wherever it is drawn.

        Every field is coerced to a string first, so one odd note (from
        older data, say) can never crash the whole list.
        """
        color = self.get_note_color(note)
        note_title = note.get("title") if isinstance(note.get("title"), str) else ""
        note_body = note.get("body") if isinstance(note.get("body"), str) else ""
        note_category = (note.get("category")
                         if isinstance(note.get("category"), str) else "General")

        title_text = (_truncate(note_title, self.CARD_TITLE_CHARS)
                      if note_title else "(untitled)")
        if note.get("pinned"):
            title_text = "📌 " + title_text
        if is_recurring(note):
            title_text = "🔁 " + title_text

        # Table rows read as pipe soup at card size, so the preview shows
        # only the note's plain text; the tags row says a table is there.
        # The calendar's rule, so a row typed past its last cell goes too.
        prose, table_count = core_tables.preview_text(note_body)
        preview_src = core_tables.lines_apart(prose if table_count else note_body)
        # A glimpse, not a width: the drawing wraps it to the card.
        preview = core_tables.glimpse(preview_src, self.CARD_PREVIEW_CHARS)

        # Two lines in fixed places (the owner's choice, 2026-11-11): when the
        # note belongs, then what it holds. A sign's own spaces are U+00A0,
        # which Tk never breaks at: "▦ 1" and "table" fell on two lines.
        nb = "\xa0"
        when = [note_category]
        if is_recurring(note):
            when.append(f"🔁{nb}{describe_recurrence(note)}")
            if note.get("exceptions"):
                when.append(f"✕{len(note['exceptions'])}")
            if note.get("overrides"):
                when.append(f"✎{len(note['overrides'])}")
        elif note.get("date"):
            when.append(f"📅{nb}{show_date(note['date'])}")
        holds = []
        if note.get("comments"):
            holds.append("💬")
        if note.get("attachments"):
            holds.append(f"📎×{len(note['attachments'])}")
        if table_count:
            holds.append(f"▦{nb}1{nb}table" if table_count == 1
                         else f"▦{nb}{table_count}{nb}tables")
        checklist = note.get("checklist") or []
        if isinstance(checklist, list) and checklist:
            done = sum(1 for it in checklist
                       if isinstance(it, dict) and it.get("done"))
            holds.append(f"☑{nb}{done}/{len(checklist)}")
        tags_text = "   ".join(when)
        if holds:
            tags_text += "\n" + "   ".join(holds)
        # The stripe wears the colour whole; the tags row's words a shade of
        # it that reads on the card (a pale yellow was 1.6:1 on white).
        words = legible_on(color, self.colors["card"], self.colors["text"])
        return {"title": title_text, "preview": preview, "tags": tags_text,
                "color": color, "words": words}

    def _draw_note_card(self, note, top):
        """Draw one note's card with its top edge at canvas y `top`, and return
        its record: ring, colour stripe, title, a glimpse of the body and the
        tags row, as rectangles and text rather than six windows a card. All
        text wraps to the card, never cut (a Label without wraplength hid the
        end of a long title, and "1/2" read as "1/"); three spaces between
        tags give the wrap somewhere to break."""
        cv = self.canvas
        c = self.colors
        nid = note["id"]
        tag = "card%s" % nid
        tags = ("row", tag)
        says = self._card_texts(note)
        x0 = self.CARD_INSET_X
        x1 = self.LIST_DRAW_WIDTH - self.CARD_INSET_X
        left = x0 + self.CARD_RING
        check_x = None
        if self.selection_mode:
            # Leftmost, ahead of the stripe, where the Checkbutton stood: 6
            # pixels before it and 22 wide, measured on the widget card (17,
            # guessed first, put the stripe five pixels off in the photograph).
            check_x = left + self.px(8)
            left += self.px(6 + 22)
        stripe_x = left
        content_left = stripe_x + self.CARD_STRIPE + self.CARD_PAD[0]
        content_right = x1 - self.CARD_RING - self.CARD_PAD[0]
        text_x = content_left + 2
        wrap = max(self.px(40), content_right - content_left - 4)
        inset = self.CARD_TEXT_INSET
        items = {}
        y = top + self.CARD_RING + self.CARD_PAD[1] + inset
        # " " for an empty line: a Label kept a line's height for no text,
        # and the card must not change shape because a body is empty.
        items["title"] = cv.create_text(
            text_x, y, anchor="nw", width=wrap, text=says["title"] or " ",
            font=self.CARD_TITLE_FONT, fill=c["text"], tags=tags)
        y = cv.bbox(items["title"])[3] + 2 * inset
        items["preview"] = cv.create_text(
            text_x, y, anchor="nw", width=wrap, text=says["preview"] or " ",
            font=self.CARD_PREVIEW_FONT, fill=c["subtext"], tags=tags)
        y = cv.bbox(items["preview"])[3] + 2 * inset + 3
        items["tags"] = cv.create_text(
            text_x, y, anchor="nw", width=wrap, text=says["tags"] or " ",
            font=self.CARD_TAGS_FONT, fill=says["words"], tags=tags)
        bottom = (cv.bbox(items["tags"])[3] + inset + self.CARD_PAD[1]
                  + self.CARD_RING)
        items["bg"] = cv.create_rectangle(
            x0, top, x1, bottom, fill=c["card"], outline="", tags=tags)
        cv.tag_lower(items["bg"], items["title"])
        items["stripe"] = cv.create_rectangle(
            stripe_x, top + self.CARD_RING, stripe_x + self.CARD_STRIPE,
            bottom - self.CARD_RING, fill=says["color"], outline="", tags=tags)
        if check_x is not None:
            mid = (top + bottom) // 2
            half = self.CARD_CHECK // 2
            items["check"] = cv.create_rectangle(
                check_x, mid - half, check_x + self.CARD_CHECK, mid + half + 1,
                fill=c["check_well"], outline=c["subtext"], tags=tags)
            px = self.px
            items["mark"] = cv.create_line(
                check_x + px(3), mid, check_x + px(6), mid + px(3),
                check_x + px(10), mid - px(3),
                width=px(2), fill=self.CARD_CHECK_MARK, tags=tags,
                state="normal" if nid in self.selected_note_ids else "hidden")
        items["ring"] = cv.create_rectangle(
            x0 + 1, top + 1, x1 - 1, bottom - 1, width=self.CARD_RING,
            outline=self._ring_to_paint(nid), tags=tags)
        rec = {"kind": "note", "key": ("note", nid), "tag": tag, "note": note,
               "y0": top, "y1": bottom, "margin": self.CARD_MARGIN,
               "items": items}
        self._note_cards[nid] = rec
        return rec

    def _card_order(self):
        """The ids of the drawn cards, in the order they stand on screen."""
        return [rec["note"]["id"] for rec in getattr(self, "_list_drawn", None) or ()
                if rec["kind"] == "note"]

    def _card_view(self, note_id):
        """What one drawn card shows, read back from the drawing itself --
        its texts, its colours, where it is -- or None when it is not drawn.
        The question the checks ask, now that a card has no widgets to
        read."""
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None:
            return None
        cv = self.canvas
        it = rec["items"]
        view = {
            "title": cv.itemcget(it["title"], "text"),
            "preview": cv.itemcget(it["preview"], "text"),
            "tags": cv.itemcget(it["tags"], "text"),
            "title_fill": cv.itemcget(it["title"], "fill"),
            "preview_fill": cv.itemcget(it["preview"], "fill"),
            "tags_fill": cv.itemcget(it["tags"], "fill"),
            "bg": cv.itemcget(it["bg"], "fill"),
            "stripe": cv.itemcget(it["stripe"], "fill"),
            "ring": cv.itemcget(it["ring"], "outline"),
            "y0": rec["y0"], "y1": rec["y1"],
            "text_boxes": [cv.bbox(it[k]) for k in ("title", "preview", "tags")],
            "box": (self.CARD_INSET_X, rec["y0"],
                    self.LIST_DRAW_WIDTH - self.CARD_INSET_X, rec["y1"]),
            "checked": None,
        }
        if "mark" in it:
            view["checked"] = cv.itemcget(it["mark"], "state") != "hidden"
            view["check_well"] = cv.itemcget(it["check"], "fill")
            view["check_mark"] = cv.itemcget(it["mark"], "fill")
        return view

    def _header_view(self, cat):
        """What one drawn category header shows, or None."""
        rec = (getattr(self, "_group_headers", None) or {}).get(cat)
        if rec is None:
            return None
        cv = self.canvas
        return {"label": cv.itemcget(rec["items"]["label"], "text"),
                "caret": cv.itemcget(rec["items"]["caret"], "text"),
                "y0": rec["y0"], "y1": rec["y1"]}

    def _card_point(self, note_id):
        """A point inside a drawn card, in the canvas widget's coordinates
        -- where a click on it lands. None when it is not drawn."""
        rec = (getattr(self, "_note_cards", None) or {}).get(note_id)
        if rec is None:
            return None
        return (self.LIST_DRAW_WIDTH // 2,
                int((rec["y0"] + rec["y1"]) / 2 - self.canvas.canvasy(0)))

    def _recolor_note_cards(self):
        """Re-apply the theme's colours to the drawn list instead of drawing it
        again. Stripe and tag colours are RECOMPUTED from the note
        (get_note_color), not swapped, so a note's own colour survives a theme
        switch as through a rebuild; _recolor_stragglers never reaches the
        list (a drawing is not a widget), so this is its only recolour."""
        c = self.colors
        cv = self.canvas
        if cv is None:
            return
        try:
            for note_id, rec in list((getattr(self, "_note_cards", None) or {}).items()):
                it = rec["items"]
                note_color = self.get_note_color(rec["note"] or {})
                cv.itemconfigure(it["bg"], fill=c["card"])
                cv.itemconfigure(it["stripe"], fill=note_color)
                cv.itemconfigure(it["title"], fill=c["text"])
                cv.itemconfigure(it["preview"], fill=c["subtext"])
                cv.itemconfigure(it["tags"], fill=legible_on(
                    note_color, c["card"], c["text"]))
                cv.itemconfigure(it["ring"], outline=self._ring_to_paint(note_id))
                if "check" in it:
                    cv.itemconfigure(it["check"], fill=c["check_well"],
                                     outline=c["subtext"])
            for cat, rec in list((getattr(self, "_group_headers", None) or {}).items()):
                it = rec["items"]
                dot = CATEGORY_COLORS.get(cat, c["accent"])
                cv.itemconfigure(it["bg"], fill=c["sidebar"])
                cv.itemconfigure(it["dot"], fill=dot, outline=dot)
                cv.itemconfigure(it["caret"], fill=c["subtext"])
                cv.itemconfigure(it["label"], fill=c["text"])
                cv.itemconfigure(it["ring"], outline=self._header_ring_color(cat))
            cv.itemconfigure("list_empty", fill=c["subtext"])
        except tk.TclError:
            pass

    # ---------- Multi-select for bulk actions ----------
    def _toggle_selection_mode(self):
        """Turn the pick-several-notes mode on or off. Turning it off always
        clears whatever was selected — re-entering starts fresh, rather than
        surprising the user with an old selection still active."""
        self.selection_mode = not self.selection_mode
        self.selected_note_ids = set()
        if self.selection_mode:
            self.select_toggle_btn.config(text="✕ Cancel select")
            self.bulk_action_bar.pack(fill="x", padx=15, pady=(0, 8), after=self._selection_anchor_row())
        else:
            self.select_toggle_btn.config(text="☑ Select")
            self.bulk_action_bar.pack_forget()
        self._update_bulk_selected_label()
        self._apply_selection_mode_to_cards()

    def _remove_note_cards(self, note_ids):
        """Take deleted notes' cards off the list without rebuilding it: delete
        their items, slide the rows below up, bring the headers' counts down.
        Returns False whenever it cannot be sure -- the caller then rebuilds,
        since a list that quietly disagrees with the notes is far worse than
        one that flickers. ISSUES_LOG, smaller lessons: the surgical updates."""
        # The rows are about to slide; a card lifted by a drag goes back
        # to its record first (see _cancel_list_drag).
        self._cancel_list_drag()
        cards = getattr(self, "_note_cards", None)
        drawn = getattr(self, "_list_drawn", None)
        if cards is None or drawn is None:
            return False
        gone = set(note_ids)
        focused = getattr(self, "_focused_note_id", None)
        order_before = self._card_order()
        ringed_header = getattr(self, "_focused_header", None)
        rows_before = self._list_drawn_keys
        kept = []
        try:
            for rec in drawn:
                if rec["kind"] == "note" and rec["note"]["id"] in gone:
                    self.canvas.delete(rec["tag"])
                    cards.pop(rec["note"]["id"], None)
                    continue
                kept.append(rec)
            # Headers too, card or not: a COLLAPSED group draws no cards, yet
            # its count must come down. Counts come from the ids each header
            # was drawn with; a header left counting nothing goes.
            headers = getattr(self, "_group_headers", None) or {}
            still_drawn = []
            for rec in kept:
                if rec["kind"] != "header":
                    still_drawn.append(rec)
                    continue
                rec["ids"] = [i for i in rec["ids"] if i not in gone]
                if rec["ids"]:
                    self.canvas.itemconfigure(
                        rec["items"]["label"],
                        text=self._header_label_text(
                            rec["cat"], len(rec["ids"]), rec["label_x"]))
                    still_drawn.append(rec)
                else:
                    self.canvas.delete(rec["tag"])
                    headers.pop(rec["cat"], None)
        except tk.TclError:
            return False
        self._list_drawn = still_drawn
        # And the rows still waiting to be drawn (see _draw_list_rows):
        # left alone, scrolling down would draw the card of a note that
        # is gone, under a header still counting it.
        waiting = []
        for row in getattr(self, "_list_pending", None) or ():
            if row[0] == "note":
                if row[1].get("id") not in gone:
                    waiting.append(row)
                continue
            kept_notes = [n for n in row[2] if n.get("id") not in gone]
            if kept_notes:
                waiting.append((row[0], row[1], kept_notes, row[3]))
        self._list_pending = waiting
        if not self._list_drawn:
            # Nothing drawn at all: an empty list carries a message, which
            # depends on the filter -- refresh_note_list's business.
            return False
        # From the top: only the rows below a gap actually move, so the rows
        # above cost a comparison each.
        self._reflow_list(0)
        # The keyboard's ring was on a card that went: it moves to the card
        # that took its place, so the walk carries on from where it was.
        if focused in gone and focused in order_before:
            order = self._card_order()
            if order:
                place = min(order_before.index(focused), len(order) - 1)
                self._focused_note_id = order[place]
                self._paint_ring(self._focused_note_id)
        # ...and a header's, when its group went with the delete: to the row
        # now standing where the header stood.
        if (ringed_header is not None and ringed_header not in headers
                and ("header", ringed_header) in rows_before):
            rows = self._list_drawn_keys
            place = min(rows_before.index(("header", ringed_header)),
                        len(rows) - 1)
            self._set_ring_row(rows[place])
            self._paint_ring_row()
        # What was taken off may have left less than a screen drawn.
        self._ask_for_top_up()
        # refresh_note_list() recomputes these on its way past, and
        # Settings may be open on them right now. Due even when no card
        # was drawn -- a note still left the notebook.
        self._render_statistics()
        # ...and so does taking the ticks of the notes that went.
        self._prune_selection()
        # A delete can leave the editor empty, and no card is open then.
        self._update_open_highlight()
        return True

    def _show_note_moved(self, note_id, keep_ring=False):
        """The list after ONE note's place or look changed (a pin, a new
        category, a move in Custom order): its card alone is redrawn, as a
        save's is, or the whole list when that is not enough or the ring
        must be followed. *keep_ring*: the caller puts the ring on this card
        and brings it into view itself (Alt+Up/Down). ARCHITECTURE: "Large
        lists", one note changed."""
        if ((getattr(self, "_keyboard_on_card", False) and not keep_ring)
                or not self._redraw_saved_card(note_id)
                or (keep_ring and note_id not in (getattr(self, "_note_cards", None) or {}))):
            self.refresh_note_list()
            return
        # What refresh_note_list does on its way past that the one card does not.
        self._share_panel_follows()

    def _redraw_saved_card(self, note_id):
        """Bring the list up to date after ONE note was saved, redrawing only
        its card. The rows are worked out afresh (_list_rows); when only this
        note differs (text, place, search), its card is drawn in its new place
        and the rows between slide, in one repaint. Anything more returns
        False and the caller rebuilds. ISSUES_LOG: "The list that was drawn
        whole, for every pause in typing"."""
        # As in _remove_note_cards: rows are about to move.
        self._cancel_list_drag()
        cards = getattr(self, "_note_cards", None)
        drawn = getattr(self, "_list_drawn", None)
        pending = getattr(self, "_list_pending", None)
        if cards is None or not drawn or pending is None:
            return False

        def key_of(row):
            return (row[0], row[1] if row[0] == "header" else row[1]["id"])

        rows = self._list_rows()
        new_keys = [key_of(row) for row in rows]
        old_drawn_keys = [rec["key"] for rec in drawn]
        old_keys = old_drawn_keys + [key_of(row) for row in pending]
        own = ("note", note_id)
        if [k for k in new_keys if k != own] != [k for k in old_keys if k != own]:
            return False
        # Leaving the others where they were is not enough when grouped: a
        # header's "(N)" counts its group, and the note may have joined or
        # left one without any other row moving.
        headers = getattr(self, "_group_headers", None) or {}
        waiting_groups = {row[1]: row[2] for row in pending if row[0] == "header"}
        for row in rows:
            if row[0] != "header":
                continue
            if row[1] in headers:
                before = set(headers[row[1]].get("ids", ()))
            elif row[1] in waiting_groups:
                before = {n["id"] for n in waiting_groups[row[1]]}
            else:
                return False
            if {n["id"] for n in row[2]} != before:
                return False

        # The card goes among the drawn rows, or among the waiting ones when
        # the sort moved it past them; just below the last drawn row it is
        # drawn if it was, or if nothing waits (a new note in a short list).
        was_drawn = own in old_drawn_keys
        old_at = old_drawn_keys.index(own) if was_drawn else None
        others_drawn = len(drawn) - (1 if was_drawn else 0)
        new_at = new_keys.index(own) if own in new_keys else None
        drawn_now = new_at is not None and (
            new_at < others_drawn
            or (new_at == others_drawn and (was_drawn or not pending)))
        depth = others_drawn + (1 if drawn_now else 0)
        try:
            if was_drawn:
                old = drawn.pop(old_at)
                cards.pop(note_id, None)
                self.canvas.delete(old["tag"])
            if drawn_now:
                # Drawn out of the way, then put in place by the reflow below:
                # drawn over the rows, it made its band hold items that were
                # not its rows', and every row moved alone.
                drawn.insert(new_at, self._draw_note_card(
                    rows[new_at][1], self.LIST_OUT_OF_THE_WAY))
        except tk.TclError:
            return False
        starts = [i for i in (old_at, new_at if drawn_now else None) if i is not None]
        self._reflow_list(min(starts) if starts else len(drawn))
        self._list_pending = rows[depth:]
        for row in rows[:depth]:
            if row[0] == "header" and row[1] in headers:
                headers[row[1]]["ids"] = [n["id"] for n in row[2]]
        # A card that went to wait below may have left the drawn part
        # shorter than the view, and whether the canvas reports that
        # depends on whether anything changed size -- so ask directly.
        self._ask_for_top_up()
        # Everything else refresh_note_list does on its way past.
        self._render_statistics()
        if self.selection_mode:
            self._update_bulk_selected_label()
        # A new note's first save draws its card as the open one, and the card
        # open before it still wears the outline: one card redrawn repaints
        # only itself.
        self._update_open_highlight()
        return True

    def _exit_selection_mode_after_bulk_action(self):
        """Turn selection mode off as _toggle_selection_mode does, then rebuild
        the list in full: after a bulk action (Trash, a category change) some
        cards show notes that are gone or no longer belong in the view, and
        the surgical update only adds or removes tick boxes."""
        self.selection_mode = False
        self.selected_note_ids = set()
        self.select_toggle_btn.config(text="☑ Select")
        self.bulk_action_bar.pack_forget()
        self._update_bulk_selected_label()
        self.refresh_note_list()

    def _apply_selection_mode_to_cards(self):
        """Add or remove the per-card tick box as selection mode turns on or
        off: the box takes room, the text wraps again and cards change height,
        so the drawn part is drawn again where it was -- one repaint on the
        canvas. What a click does is decided when it arrives (_list_pressed)."""
        self.refresh_note_list()

    def _selection_anchor_row(self):
        """The row the bulk-action bar should appear directly under. Looked
        up by walking the sidebar rather than stored separately, so it stays
        correct even if the sidebar layout changes elsewhere."""
        return self.select_toggle_btn.master

    def _prune_selection(self):
        """Keep the ticks to notes that still exist, and the bar's words with
        them: a deleted note kept its tick, and a new note could take its freed
        id (the highest plus one) and arrive ticked, to be trashed by a Trash
        nobody aimed at it."""
        chosen = self.selected_note_ids
        if not chosen:
            return
        kept = chosen & {n["id"] for n in self.notes}
        if kept != chosen:
            self.selected_note_ids = kept
            self._update_bulk_selected_label()

    def _toggle_note_selected(self, note_id, now_selected):
        if now_selected:
            self.selected_note_ids.add(note_id)
        else:
            self.selected_note_ids.discard(note_id)
        self._update_bulk_selected_label()
        # No refresh_note_list(): a rebuild for one tick flickered on every
        # click. The caller repaints the one mark (_paint_card_check).

    def _update_bulk_selected_label(self):
        n = len(self.selected_note_ids)
        self.bulk_selected_lbl.config(text=f"{n} selected")
        # What "Pin" will do depends on what is ticked now, so its word is
        # worked out wherever the selection changes, like Select all's below.
        self._refresh_bulk_pin_label()
        # The button says what a press will do, asked of the same
        # _visible_note_ids() the press uses, so word and action agree.
        button = self._bulk_select_all_btn
        if button is None:
            return
        try:
            visible = self._visible_note_ids()
            button.config(text="Unselect all"
                          if visible and visible <= self.selected_note_ids
                          else "Select all")
        except (tk.TclError, AttributeError):
            pass

    @staticmethod
    def _query_matches_note(query, note):
        """The ONE definition of "this note matches the sidebar search", every
        field coerced to text first. Two hand-rolled copies once drifted, and
        Select all ticked notes the filter hid. An empty query matches every
        note without reading one (each rebuild and tick used to parse every
        table to learn that). ISSUES_LOG, smaller lessons:
        _query_matches_note."""
        if not query:
            return True
        return NoteListMixin._query_in_texts(
            query, NoteListMixin._search_texts(note))

    @staticmethod
    def _search_texts(note):
        """What the sidebar search looks through in a note: its title, its
        body as text -- a table's plumbing stripped -- its comments and its
        checklist's rows, folded (core.model.fold_for_search)."""
        def _txt(value):
            return fold_for_search(value) if isinstance(value, str) else ""

        body = note.get("body")
        if isinstance(body, str) and core_tables.CELL in body:
            body_txt = fold_for_search(core_tables.content_text(body))
        else:
            body_txt = _txt(body)
        rows = "\n".join(it.get("text") or "" for it in note.get("checklist") or []
                         if isinstance(it, dict) and isinstance(it.get("text"), str))
        return (_txt(note.get("title")), body_txt, _txt(note.get("comments")), _txt(rows))

    @staticmethod
    def _query_in_texts(query, texts):
        """The search's one rule, for texts from _search_texts."""
        return any(query in text for text in texts)

    def _cached_search_texts(self, note):
        """_search_texts, kept for each note until one of its fields is
        replaced. The three texts are asked by the objects themselves: a save
        writes new strings, and the cache holds on to the old ones, so an old
        one's identity cannot be reused by a new string while it is compared.
        The checklist's rows are compared as words: a row is edited in place."""
        cache = self.__dict__.setdefault("_search_text_cache", {})
        fields = (note.get("title"), note.get("body"), note.get("comments"))
        rows = tuple(it.get("text") for it in note.get("checklist") or [] if isinstance(it, dict))
        hit = cache.get(note.get("id"))
        if (hit is None or hit[0][0] is not fields[0]
                or hit[0][1] is not fields[1] or hit[0][2] is not fields[2]
                or hit[1] != rows):
            hit = (fields, rows, self._search_texts(note))
            cache[note.get("id")] = hit
        return hit[2]

    def _visible_note_ids(self):
        """The notes the list is showing right now, by id: the ONE definition,
        so Select all and the label saying whether all ARE selected mean the
        same set. Asked of the notes, not the drawn cards ("all" includes rows
        not drawn yet), and leaving out a folded group's notes: counted, they
        let Select all and then bulk Trash take notes nobody could see."""
        shown = self._notes_on_the_list()
        grouped = self.group_by_category
        folded = self.collapsed_groups
        if grouped is not None and grouped.get() and folded:
            shown = [n for n in shown if self._list_group_of(n) not in folded]
        return {n["id"] for n in shown}

    def _bulk_select_all(self):
        """Select every note the list is showing, or let them all go if all
        are selected already: one button, since the second is only wanted right
        after the first. "All" respects the search and the filter -- what is on
        screen, never the whole notebook."""
        visible = self._visible_note_ids()
        if visible and visible <= self.selected_note_ids:
            self.selected_note_ids = set()
        else:
            self.selected_note_ids = set(visible)
        self._update_bulk_selected_label()
        # Not refresh_note_list(): only the ticks changed, and a rebuild to
        # move them was the flicker this button was reported for. ISSUES_LOG,
        # smaller lessons: the surgical updates.
        self._sync_card_checkboxes()

    def _sync_card_checkboxes(self):
        """Make every drawn card's tick box agree with selected_note_ids. Only
        the drawing changes, with no change reported back (the label would
        recount once per box); a card not drawn needs nothing, since
        _draw_note_card reads selected_note_ids for the box it draws."""
        for note_id in list((getattr(self, "_note_cards", None) or {})):
            self._paint_card_check(note_id)
