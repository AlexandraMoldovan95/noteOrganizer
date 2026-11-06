"""In-app dialogs, dropdowns and popups: everything the app puts *over*
itself, drawn from scratch -- the system's own dialogs only choose files
and report a start that failed. Grouped by the call graph (60% of these
methods' calls are to each other), and the most called code in the app, so
one place decides how an overlay looks and where it goes.

:meth:`_place_dropdown_popup` measures against the app window, never the
screen, or a popup opened on another monitor (ISSUES_LOG: "The dropdown
that opened on the wrong monitor"). What a mixin is, and the two rules that
keep them working: :mod:`noteorganizer.ui`.
"""

import time
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ..core.model import _truncate
from ..core.themes import letters_on, palette_value


def one_line(text, limit):
    """*text* drawn as one line of at most *limit* characters, with "…"
    where it was cut -- and exactly as it is when it already is one. For a
    name a file keeps whole: drawn whole, 3,000 lines or 60,000 letters
    asked Tk for a label past the 32,767 pixels X can draw."""
    text = str(text)
    if len(text) > limit or "\n" in text or "\r" in text:
        return _truncate(text, limit)
    return text


# The most of a message a dialog lays out: its label is as tall as its text,
# and a name quoted whole -- a backup's title of 300,000 letters, or 3,000
# lines -- passed the 32,767 pixels X can draw, even at 225%.
MESSAGE_SHOWN_CHARS = 12_000
MESSAGE_SHOWN_LINES = 300


def message_shown(message):
    """*message* as a dialog draws it: whole when it fits the limits above,
    else its start and its end -- where the question is -- with "…" for
    what lies between."""
    message = str(message)
    lines = message.split("\n")
    if (len(message) <= MESSAGE_SHOWN_CHARS
            and len(lines) <= MESSAGE_SHOWN_LINES):
        return message
    half_c, half_l = MESSAGE_SHOWN_CHARS // 2, MESSAGE_SHOWN_LINES // 2
    head = "\n".join(lines[:half_l])[:half_c]
    tail = "\n".join(lines[-half_l:])[-half_c:]
    return head + "\n…\n" + tail


def _natural_height(widget):
    """How tall *widget* stands once laid out: Tk's own height, or, for a
    frame whose children pack has not yet arranged, theirs -- the tallest of
    those packed side by side, and those one above the other added. A row is
    measured as it is made, before an idle round lays it out, when its own
    requested height still reads 1."""
    kids = widget.winfo_children()
    if not kids:
        return widget.winfo_reqheight()
    across = above = 0
    for kid in kids:
        height = _natural_height(kid)
        try:
            info = [str(v) for v in kid.tk.splitlist(
                kid.tk.call("pack", "info", kid))]
            side = info[info.index("-side") + 1]
        except (tk.TclError, ValueError, IndexError):
            side = "top"            # not packed: counted in full
        if side in ("left", "right"):
            across = max(across, height)
        else:
            above += height
    try:
        edge = 2 * (int(str(widget.cget("bd")))
                    + int(str(widget.cget("highlightthickness"))))
    except (tk.TclError, ValueError):
        edge = 0
    return max(widget.winfo_reqheight(), edge + above + across)


class RowStack:
    """A scrolled list's rows, in chunk frames of a few rows that the stack
    places on *canvas* itself: one frame for all stopped at 32,767 px, as
    places are kept in 16 bits (ISSUES_LOG: "The list that ended in the
    middle"). A chunk in view stands at its true place, every other parked
    beside it -- placed, never unmapped, so Tab reaches it."""

    # A chunk out of sight is parked this far left of the view and above it:
    # only above, a tall one hung over the rows in sight; and inside 16 bits,
    # where X and Windows keep a window's place.
    PARK = 20_000
    # Rows to a chunk unless a list says otherwise...
    EVERY = 8
    # ...and no row more once a chunk is this tall (_RowGroup.height): four
    # long checklist items stood 42,656 px at 300%. Rows that grow later are
    # chunked again (_RowGroup.too_tall).
    TALLEST = 4_000
    # The farthest from its parent's corner X keeps a window's place, in 16
    # bits; Windows pins a row there. No chunk is placed past it.
    REACH = 32_767

    def __init__(self, app, canvas, scrolled=None, on_chunk=None,
                 on_change=None, own_width=False):
        self.app, self.canvas = app, canvas
        self.scrolled, self.on_chunk, self.on_change = (scrolled, on_chunk,
                                                        on_change)
        # Given its width by its popup (set_width), as wide as the widest row,
        # as one frame was -- the picker's heading is wider; else the canvas's.
        self.own_width = own_width
        self.groups = []
        self.total = self.widest = 0
        self._box = {}          # chunk -> (x0, y0, x1, y1) on the canvas
        self._placed = {}       # chunk -> the (x, y) it stands at now
        self._width = None      # the width the chunks are given, once known
        self._job = None
        canvas._row_stack = self
        canvas.configure(yscrollcommand=self._scrolled)
        canvas.bind("<Configure>", self._resized, add="+")

    def group(self, bg="card", padx=0, pady=(0, 0), every=EVERY):
        """Rows that read as one block, below those already asked for: *bg*
        is a palette key, *padx* and *pady* its margins."""
        group = _RowGroup(self, bg, padx, pady, every)
        self.groups.append(group)
        return group

    def drop(self, group):
        """*group* gone, and its rows with it."""
        group.clear()
        self.groups.remove(group)

    def rows(self):
        return [row for group in self.groups for row in group.rows()]

    def group_of(self, chunk):
        """The block *chunk* belongs to, or None when it is none of ours."""
        return next((g for g in self.groups if chunk in g.chunks), None)

    def place_of_row(self, row):
        """(block, row) for *row*: which block it stands in, and where among
        that block's rows, counted across its chunks -- or None. Its place in
        its chunk named a frame the next redraw may not make again: sent
        there after a press, the keyboard went to another chunk's first row."""
        group = self.group_of(row.master)
        if group is None:
            return None
        count = 0
        for chunk in group.chunks:
            names = self.canvas.tk.splitlist(
                self.canvas.tk.call("winfo", "children", chunk))
            if chunk is row.master:
                return (self.groups.index(group),
                        count + [str(n) for n in names].index(str(row)))
            count += len(names)
        return None

    def box(self, chunk):
        """Where *chunk* stands on the canvas, as a window item's bbox."""
        return self._box.get(chunk)

    def y_of(self, widget):
        """The canvas y of *widget*'s top, wherever its chunk is placed."""
        y, w = 0, widget
        while w is not None and w.master is not self.canvas:
            y, w = y + w.winfo_y(), w.master
        box = self._box.get(w)
        return None if box is None else box[1] + y

    def size(self):
        """(widest, total) as the rows stand now, laid out first."""
        if self._job is not None:
            try:
                self.app.after_cancel(self._job)
            except tk.TclError:
                pass
        self._restack(notify=False)
        return self.widest, self.total

    def changed(self):
        """Stack the chunks again once the moment has passed. Asked of the
        app: a canvas destroyed first took the waiting call's command with
        it, and Tk reported "invalid command name"."""
        if self._job is None:
            try:
                self._job = self.app.after_idle(self._restack)
            except tk.TclError:
                pass

    def remeasure(self):
        """Measured again by its popup, once all is laid out: a row grown
        only wider resizes no chunk, and a restack asked for at once read its
        width before the frames around it had heard."""
        (self.on_change or self.changed)()

    def _new_chunk(self, group, before=None):
        """A new chunk at the end of *group*, or in its middle, just ahead of
        its chunk *before*."""
        chunk = tk.Frame(self.canvas, bg=self.app.colors[group.bg])
        later = before if before is not None else (
            None if group is self.groups[-1] else next(
                (g.chunks[0] for g in self.groups[self.groups.index(group) + 1:]
                 if g.chunks), None))
        if later is not None:
            chunk.lower(later)      # Tab follows the stacking order
        width = {"width": max(1, self._width - 2 * group.padx)} if self._width else {}
        chunk.place(x=-self.PARK, y=-self.PARK, **width)
        self._placed[chunk] = (-self.PARK, -self.PARK)
        chunk.bind("<Configure>", self._chunk_resized)
        if before is not None:
            group.chunks.insert(group.chunks.index(before), chunk)
        else:
            group.chunks.append(chunk)
        if self.on_chunk is not None:
            self.on_chunk(chunk)
        self.changed()
        return chunk

    def _forget(self, chunk):
        self._box.pop(chunk, None)
        self._placed.pop(chunk, None)

    def _chunk_resized(self, event):
        box = self._box.get(event.widget)
        if box is None or box[3] - box[1] != event.height:
            self.changed()

    def _resized(self, event):
        if not self.own_width:
            self.set_width(event.width)
        self._follow()

    def set_width(self, width):
        """Every chunk *width* wide. Measured where the rows were laid out
        first: read mid-layout, a wrapped row's width swung for good."""
        if width > 1 and width != self._width:
            self._width = width
            for group in self.groups:
                # Its rows wrap again at this width: chunked again if they
                # now stand too tall, once for each width (_restack).
                group.rechunked = False
                for chunk in group.chunks:
                    chunk.place_configure(width=max(1, width - 2 * group.padx))
            self.changed()

    def _scrolled(self, first, last):
        if self.scrolled is not None:
            self.scrolled(first, last)
        self._follow()

    def _restack(self, notify=True):
        self._job = None
        boxes, y, widest = {}, 0, 0
        try:
            if not self.canvas.winfo_exists():
                return
            for group in self.groups:
                if not group.chunks:
                    continue
                y += group.pady[0]
                for chunk in group.chunks:
                    # An emptied frame keeps the size it had; it takes none.
                    held = self.canvas.tk.call("winfo", "children", chunk)
                    h = chunk.winfo_reqheight() if held else 0
                    w = chunk.winfo_reqwidth()
                    boxes[chunk] = (group.padx, y, (self._width or w) - group.padx, y + h)
                    widest = max(widest, w + 2 * group.padx)
                    y += h
                y += group.pady[1]
        except tk.TclError:
            return
        grew = (y, widest) != (self.total, self.widest)
        self._box, self.total, self.widest = boxes, y, widest
        try:
            self.canvas.configure(
                scrollregion=(0, 0, max(1, self._width or widest), y))
        except tk.TclError:
            return
        self._follow()
        self._rechunk_too_tall()
        if notify and grew and self.on_change is not None:
            self.on_change()

    def _rechunk_too_tall(self):
        """A block whose rows grew past what its chunks can hold -- a
        narrower window wraps a checklist's long items again, and a chunk of
        them measured at 13,740 px stood 41,684 -- is chunked again by its
        owner (*rebuild*), once for each width, so a block that cannot be
        helped is never drawn over and over."""
        tall = 4 * self.TALLEST
        for group in self.groups:
            if group.rebuild is None or group.rechunked:
                continue
            # Laid out, as a restack reads them: only a chunk that stands
            # past the bound has its rows looked at.
            if not any(c in self._box and self._box[c][3] - self._box[c][1] > tall
                       and group.too_tall(c) for c in group.chunks):
                continue
            group.rechunked = True
            try:
                self.app.after_idle(group.rebuild)
            except tk.TclError:
                pass

    def _follow(self):
        """Each chunk in the view to its true place, the rest parked beside
        it: only what moved is placed again. A chunk out of the view stays
        parked as the list scrolls -- one stood at its true place for a view
        above and two below, and each scroll step moved them all, three to
        ten times what drawing the step cost."""
        try:
            top = self.canvas.canvasy(0)
            view = max(1, self.canvas.winfo_height())
            parked = (-self.PARK, -self.PARK)
            for chunk, (x0, y0, _x1, y1) in self._box.items():
                if y1 <= y0 or y1 <= top or y0 >= top + view:
                    want = parked
                else:
                    # Its true place, however far above: clamped to the
                    # parking place, a chunk scrolled 20,000 px into stood
                    # short of it, and its last rows were never drawn.
                    want = (x0, int(round(y0 - top)))
                    if want[1] < -self.REACH:
                        # Never past 16 bits, whatever its rows did: placed
                        # there, X drew it nowhere and the view was blank.
                        # Its block is chunked again (_rechunk_too_tall).
                        want = (x0, -self.REACH)
                if self._placed.get(chunk) != want:
                    self._placed[chunk] = want
                    chunk.place_configure(x=want[0], y=want[1])
        except tk.TclError:
            pass


class _RowGroup:
    """One block of a RowStack, built a chunk at a time."""

    def __init__(self, stack, bg, padx, pady, every):
        self.stack, self.bg, self.padx, self.pady = stack, bg, padx, pady
        self.every = every
        self.chunks = []
        self._heights = {}      # chunk -> {row: height}, as room() measured it
        # The wraplength its rows' long text was last given: a row made later
        # is made at it, and measured as it will stand.
        self.wrap = None
        # Its owner's way to draw its rows again, chunked as they now stand,
        # when rows grown since they were chunked make a chunk too tall
        # (RowStack._rechunk_too_tall); asked once for each width.
        self.rebuild = None
        self.rechunked = False

    def add(self):
        """The frame the next row is made in and packed into."""
        if self.chunks and self.room(self.chunks[-1]):
            return self.chunks[-1]
        return self.stack._new_chunk(self)

    def room(self, chunk):
        """Whether *chunk* may take one row more: it holds fewer than its
        count, and stands shorter than the stack's TALLEST."""
        if len(chunk.winfo_children()) >= self.every:
            return False
        return self.height(chunk) < self.stack.TALLEST

    def _row_heights(self, chunk):
        """Each of *chunk*'s rows' heights: measured when first asked
        (_natural_height), and again once the row is said to have been
        wrapped again (rewrapped)."""
        known = self._heights.get(chunk, {})
        heights = {}
        for row in chunk.winfo_children():
            if row in known:
                heights[row] = known[row]
            else:
                heights[row] = _natural_height(row)
        # Only the rows it holds: one traded away or destroyed is forgotten.
        self._heights[chunk] = heights
        return heights

    def height(self, chunk):
        """How tall *chunk* stands: its rows' heights (_row_heights), or the
        height it is laid out at, if that is more. Measured once and never
        again, a checklist chunk made at its labels' first wrap and narrowed
        stood 2.7 times what it was taken for."""
        heights = self._row_heights(chunk)
        if not heights:
            return 0
        return max(sum(heights.values()), chunk.winfo_reqheight())

    def too_tall(self, chunk):
        """Whether *chunk* must be chunked again: past four times TALLEST,
        with more than twice it in rows beside its tallest. A chunk made from
        rows as they stand holds less than TALLEST beside its last, so one
        chunked again is never asked of again; and a single row that tall is
        no fault of the chunking."""
        if self.height(chunk) <= 4 * self.stack.TALLEST:
            return False
        rows = [max(h, row.winfo_reqheight())
                for row, h in self._row_heights(chunk).items()]
        return sum(rows) - max(rows) > 2 * self.stack.TALLEST

    def rewrapped(self, row):
        """*row*'s text was wrapped again since it was measured: it is
        measured again when next asked."""
        self._heights.get(row.master, {}).pop(row, None)

    def chunk_before(self, chunk):
        """A new, empty chunk in this block, standing just above *chunk*."""
        return self.stack._new_chunk(self, before=chunk)

    def rows(self):
        return [row for chunk in self.chunks for row in chunk.winfo_children()]

    def winfo_children(self):
        """Its rows, as the frame it stands for listed them: a walk down the
        widget tree from where that frame stood still reaches every row."""
        return self.rows()

    def clear(self):
        for chunk in self.chunks:
            self.stack._forget(chunk)
            chunk.destroy()
        self.chunks = []
        self._heights = {}
        self.stack.changed()

    def discard(self, row):
        """Destroy *row*, and its chunk with it once that holds nothing."""
        chunk = row.master
        row.destroy()
        self._heights.get(chunk, {}).pop(row, None)
        if chunk in self.chunks and not chunk.winfo_children():
            self.chunks.remove(chunk)
            self._heights.pop(chunk, None)
            self.stack._forget(chunk)
            chunk.destroy()
        self.stack.changed()


class DialogsMixin:
    """Dialogs, dropdowns and popups for :class:`NoteOrganizer`.

    Not usable on its own -- every method reads state owned by the app
    (``self.colors``, ``self.winfo_rootx()`` and so on).
    """

    def _popups_step_back(self):
        """Drop -topmost on every override-redirect popup and slide them
        under the main window; returns the list for _popups_step_forward."""
        stepped = []
        for child in self.winfo_children():
            if not isinstance(child, tk.Toplevel):
                continue
            try:
                # int(): on X11 the attribute can come back as the STRING
                # '0', which is truthy and read as "still topmost".
                if (child.winfo_exists() and child.wm_overrideredirect()
                        and int(child.attributes("-topmost") or 0)):
                    child.attributes("-topmost", False)
                    # Into the restore list BEFORE the restack: if
                    # lower() errors (window-manager quirks on X11), the
                    # popup must still get its topmost back afterwards.
                    stepped.append(child)
                    try:
                        child.lower(self)
                    except tk.TclError:
                        pass
            except tk.TclError:
                continue
        return stepped

    def _popups_step_forward(self, stepped):
        for child in stepped:
            try:
                if child.winfo_exists():
                    child.attributes("-topmost", True)
                    child.lift()
            except tk.TclError:
                continue

    def _themed_dialog(self, title, message, kind="info", buttons=None,
                       default=None):
        """A modal, in-theme messagebox drawn INSIDE the app window, moving
        with it; blocks until a button is picked and returns its value.
        `default` is the label of the button holding the keyboard (else the
        last): pass "No" for a destructive question. Enter presses the
        button holding the keyboard, Escape answers the first (the safe
        one) -- both only for the innermost question."""
        if buttons is None:
            buttons = [("OK", True)]
        focus_index = self._dialog_focus_index(buttons, default)
        # Where the keyboard was, for it to go back once answered -- typing
        # went into nothing after a question. focus_get() is None while
        # another program is in front, so the window's record backs it up.
        returns_to = None
        try:
            returns_to = self.focus_get()
        except (KeyError, tk.TclError):
            returns_to = None
        if returns_to is None:
            try:
                returns_to = self.nametowidget(
                    self.tk.call("focus", "-lastfor", self._w))
            except (KeyError, tk.TclError):
                returns_to = None

        # A -topmost popup floats over the window, and a question about it
        # sat underneath: the popups step back while it asks.
        stepped_back = self._popups_step_back()
        icon = {"info": "ℹ", "warning": "⚠", "error": "⛔",
                "question": "❓", "success": "✅"}.get(kind, "ℹ")
        accent = {"error": self.colors["danger"], "warning": self.colors["danger"],
                  "success": self.colors["success"]}.get(kind, self.colors["accent"])

        result = {"value": None, "answered": False}
        done = tk.IntVar(value=0)

        # The card is placed over the window, the app still VISIBLE under it;
        # a grab keeps the clicks for the dialog (below).
        border = tk.Frame(self, bg=accent, highlightthickness=0)
        border.place(relx=0.5, rely=0.42, anchor="center")
        card = tk.Frame(border, bg=self.colors["card"])
        card.pack(padx=2, pady=2, fill="both", expand=True)

        # The answers first, against the bottom: short of height, pack takes
        # it from the message, packed last, which scrolls -- four startup
        # messages drew the one button below a 600px window.
        btn_row = tk.Frame(card, bg=self.colors["card"])
        btn_row.pack(side="bottom", fill="x", padx=20, pady=(0, 16))

        head = tk.Frame(card, bg=self.colors["card"])
        head.pack(side="top", fill="x", padx=20, pady=(16, 6))
        tk.Label(head, text=f"{icon}  {title}", bg=self.colors["card"],
                 fg=self.colors["text"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(side="left")

        # The message in a viewport: as tall as the text, or as tall as the
        # window leaves room for, and then it scrolls.
        msg_box = tk.Frame(card, bg=self.colors["card"])
        msg_box.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 16))
        msg_view = tk.Canvas(msg_box, bg=self.colors["card"],
                             highlightthickness=0, bd=0)
        msg_lbl = tk.Label(msg_view, text=message_shown(message),
                           bg=self.colors["card"],
                           fg=self.colors["subtext"], font=("Segoe UI", 10),
                           wraplength=self.px(380), justify="left", anchor="w")
        msg_view.create_window(0, 0, window=msg_lbl, anchor="nw")
        msg_bar = ttk.Scrollbar(msg_box, orient="vertical",
                                command=msg_view.yview)
        msg_view.configure(yscrollcommand=msg_bar.set)
        msg_view.pack(side="left", fill="both", expand=True)

        def scroll_message(amount, what):
            try:
                msg_view.yview_scroll(amount, what)
            except tk.TclError:
                pass
            return "break"

        def wheel(event):
            up = getattr(event, "delta", 0) > 0 or getattr(event, "num", None) == 4
            return scroll_message(-1 if up else 1, "units")

        for w in (msg_view, msg_lbl):
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                w.bind(seq, wheel)

        def choose(val):
            # The first answer is the answer: the <Destroy> safety net
            # below runs again as the card is torn down after a real one.
            if result["answered"]:
                return
            result["answered"] = True
            result["value"] = val
            try:
                done.set(1)
            except tk.TclError:
                pass

        dialog_buttons = []
        for i, spec in enumerate(buttons):
            label, value = spec[0], spec[1]
            color_key = spec[2] if len(spec) > 2 else None
            is_primary = (i == len(buttons) - 1)
            if color_key:
                btn_color = self.colors.get(color_key, self.colors["sidebar"])
                fg_color = letters_on(btn_color)
            else:
                btn_color = accent if is_primary else self.colors["sidebar"]
                fg_color = letters_on(btn_color) if is_primary else self.colors["text"]
            b = tk.Button(
                btn_row, text=label, command=lambda v=value: choose(v),
                relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
                bg=btn_color, fg=fg_color,
                activebackground=btn_color, activeforeground=fg_color)
            b.pack(side="right", padx=(8, 0), ipadx=12, ipady=4)
            # The keyboard reads a message too long for the window: the
            # arrows and Page keys scroll it from the button holding focus.
            for seq, amount, what in (("<Up>", -1, "units"), ("<Down>", 1, "units"),
                                      ("<Prior>", -1, "pages"),
                                      ("<Next>", 1, "pages")):
                b.bind(seq, lambda e, a=amount, k=what: scroll_message(a, k))
            dialog_buttons.append(b)
            if i == focus_index:
                b.focus_set()

        # Tab walks the answers round, as a Windows message box does: the grab
        # holds the pointer only, and Tab walked into the note under it.
        # Shift+Tab is <<PrevWindow>> too (X11's ISO_Left_Tab).
        def cycle(button, step):
            i = dialog_buttons.index(button)
            dialog_buttons[(i + step) % len(dialog_buttons)].focus_set()
            return "break"

        for b in dialog_buttons:
            b.bind("<Tab>", lambda e, b=b: cycle(b, 1))
            for seq in ("<Shift-Tab>", "<<PrevWindow>>"):
                b.bind(seq, lambda e, b=b: cycle(b, -1))

        # Escape = the "safe" (first) value, usually cancel/no.
        safe_val = buttons[0][1] if len(buttons) > 1 else buttons[-1][1]
        asking = {"border": border, "buttons": dialog_buttons,
                  "default": dialog_buttons[focus_index]}

        def innermost():
            stack = getattr(self, "_asking_dialogs", None) or []
            return bool(stack) and stack[-1] is asking

        def escape(_event=None):
            # Both keys are bound on the window, so a question asked over
            # another heard them too: one Escape answered both.
            if innermost():
                choose(safe_val)

        def enter(event):
            # Enter presses the button holding the keyboard -- a tk.Button
            # answers only Space. Pressed, not held: held, it answered the
            # question and asked it again (_enter_repeats).
            held = self._enter_repeats(event)
            if held or not innermost():
                return
            w = getattr(event, "widget", None)
            if w in dialog_buttons:
                w.invoke()
            elif w is self or self._is_inside_popup(w, border):
                asking["default"].invoke()

        esc_bind = self.bind("<Escape>", escape, add="+")
        enter_binds = [(seq, self.bind(seq, enter, add="+"))
                       for seq in ("<Return>", "<KP_Enter>")]
        # No wait outlives its window: closed under a question, the process
        # lived on windowless, holding the lock, and every launch was refused.
        # on_app_close refuses that close; this is the net under the rest.
        border.bind("<Destroy>", lambda e: choose(safe_val), add="+")

        # The card inside the window, its answers on screen: at 0.42 of the
        # height when it fits, else the message gives way and wide buttons
        # stack. Asked again at every resize while it waits.
        margin = 12
        layout = {"natural_w": None, "stacked": False, "job": None,
                  "size": None}

        def stack_buttons(stacked):
            if layout["stacked"] == stacked:
                return
            layout["stacked"] = stacked
            for b in dialog_buttons:
                b.pack_forget()
            if stacked:
                # Top to bottom in the order they read left to right.
                for b in reversed(dialog_buttons):
                    b.pack(side="top", fill="x", pady=(0, 6), ipadx=12, ipady=4)
            else:
                for b in dialog_buttons:
                    b.pack(side="right", padx=(8, 0), ipadx=12, ipady=4)

        def fit():
            layout["job"] = None
            try:
                if not border.winfo_exists():
                    return
                win_w, win_h = self.winfo_width(), self.winfo_height()
                if win_w < 100 or win_h < 100:
                    return          # not laid out yet, or minimised
                layout["size"] = (win_w, win_h)
                # Where the person had scrolled to, kept: the viewport is
                # measured at the text's full height below, which puts the
                # view back at the top.
                scrolled_to = msg_view.yview()[0]
                lbl_w = msg_lbl.winfo_reqwidth()
                lbl_h = msg_lbl.winfo_reqheight()
                msg_view.configure(width=lbl_w, height=lbl_h,
                                   scrollregion=(0, 0, lbl_w, lbl_h))
                msg_bar.pack_forget()
                border.place_configure(height="")
                if layout["natural_w"] is None:
                    self.update_idletasks()
                    layout["natural_w"] = border.winfo_reqwidth()
                stack_buttons(layout["natural_w"] > win_w - 2 * margin)
                self.update_idletasks()
                natural_h = border.winfo_reqheight()
                room = win_h - 2 * margin
                height = natural_h
                if natural_h > room:
                    msg_view.configure(
                        height=max(self.px(48), lbl_h - (natural_h - room)))
                    msg_bar.pack(side="right", fill="y", before=msg_view)
                    height = room
                    # Given, not asked for: if the arithmetic above is ever
                    # short, pack squeezes the message, never the buttons.
                    border.place_configure(height=height)
                centre = max(margin + height / 2,
                             min(0.42 * win_h, win_h - margin - height / 2))
                border.place_configure(relx=0.5, rely=0, y=int(centre),
                                       anchor="center")
                self.update_idletasks()
                msg_view.yview_moveto(scrolled_to)
            except tk.TclError:
                pass

        def refit_later(widget_path):
            # The window's own <Configure>, and only a change of size: a move
            # (or a restack) leaves everything where it is.
            if widget_path != str(self) or layout["job"] is not None:
                return
            try:
                if (self.winfo_width(), self.winfo_height()) == layout["size"]:
                    return
            except tk.TclError:
                return
            try:
                layout["job"] = self.after_idle(fit)
            except tk.TclError:
                pass

        fit()
        self._bind_window_for_popup(border, "<Configure>", refit_later)

        # A local grab on an in-window Frame (not a borderless Toplevel, which
        # could freeze the app) routes input to the dialog only.
        self.update_idletasks()
        try:
            border.grab_set()
        except tk.TclError:
            pass
        # The global shortcuts stand still while it waits (_a_dialog_is_asking):
        # under a grab, Ctrl+N cleared the editor the answer wrote into.
        # Raised beside the finally that lowers it.
        self._modal_depth = getattr(self, "_modal_depth", 0) + 1
        # Innermost last: what the keys answer, and what a close of the
        # window brings to the front (_bring_question_forward).
        if getattr(self, "_asking_dialogs", None) is None:
            self._asking_dialogs = []
        self._asking_dialogs.append(asking)
        try:
            self.wait_variable(done)
        finally:
            try:
                self._asking_dialogs.remove(asking)
            except ValueError:
                pass
            try:
                border.grab_release()
            except tk.TclError:
                pass
            # Tk has ONE grab: a question asked inside this wait took it, and
            # its release left none, the app under a question taking clicks.
            # The question still waiting gets it back.
            still_asking = getattr(self, "_asking_dialogs", None) or []
            if still_asking:
                try:
                    still_asking[-1]["border"].grab_set()
                except tk.TclError:
                    pass
            for seq, bind_id in [("<Escape>", esc_bind)] + enter_binds:
                try:
                    self.unbind(seq, bind_id)
                except tk.TclError:
                    pass
            try:
                border.destroy()
            except tk.TclError:
                pass
            self._popups_step_forward(stepped_back)
            self._modal_depth = max(0, getattr(self, "_modal_depth", 1) - 1)
            try:
                if (returns_to is not None and returns_to is not self
                        and returns_to.winfo_exists()):
                    returns_to.focus_set()
            except tk.TclError:
                pass
        return result["value"]

    def _a_dialog_is_asking(self):
        """True while a themed dialog waits for an answer. Every handler
        bound with bind_all asks this first and does nothing if so."""
        return getattr(self, "_modal_depth", 0) > 0

    def _while_native(self, show):
        """Run *show* -- a file chooser or a posted menu, whose own loop runs
        every timer -- counted in `_natives_open`, so a backup's merge waits
        for it as for a question: under it, its questions opened behind the
        chooser (wave 2, round 12)."""
        self._natives_open = getattr(self, "_natives_open", 0) + 1
        try:
            return show()
        finally:
            self._natives_open -= 1

    def _bring_question_forward(self):
        """The window was asked to close while a question waits: show the
        question instead, as Windows does for a modal one. The window comes
        back from the taskbar if it went there, the question's card is
        lifted, and the keyboard goes to its button -- the one that held
        it, or the default."""
        stack = getattr(self, "_asking_dialogs", None) or []
        if not stack:
            return
        asking = stack[-1]
        try:
            if self.state() == "iconic":
                self.deiconify()
            self.lift()
            asking["border"].lift()
            try:
                holder = self.focus_get()
            except (KeyError, tk.TclError):
                holder = None
            target = (holder if holder in asking["buttons"]
                      else asking["default"])
            target.focus_force()
        except tk.TclError:
            pass

    def _toggles_its_popup(self, btn, open_popup):
        """Make a button open its popup on one click and close it on the
        next: a button acts on the release, click-outside on the press, so a
        second click closed the popup and opened it again -- a blink. Decided
        on each press, in the button's binding, which runs before the
        window's, while it is knowable whether the open popup is this one's.
        """
        state = {"closing": False}

        def on_press(_event=None):
            mine = getattr(btn, "_its_popup", None)
            state["closing"] = (mine is not None
                                and getattr(self, "_mini_popup", None) is mine)

        def on_release_command():
            if state["closing"]:
                state["closing"] = False
                return
            open_popup()
            btn._its_popup = getattr(self, "_mini_popup", None)

        btn.bind("<ButtonPress-1>", on_press, add="+")
        btn.configure(command=on_release_command)
        return btn

    @staticmethod
    def _dialog_focus_index(buttons, default):
        """Which button gets keyboard focus (i.e. which one Enter fires).
        Named by `default` (a button LABEL, case-insensitive); otherwise
        the primary (last) button. A `default` that matches no label
        falls back to the primary rather than leaving nothing focused —
        so a typo can never silently un-focus the whole dialog."""
        if default:
            for i, spec in enumerate(buttons):
                if str(spec[0]).lower() == str(default).lower():
                    return i
        return len(buttons) - 1

    # Keyword-only, named parameters: taking **kw, these dropped what they
    # did not understand -- a destructive confirm's default="no" among it
    # (ISSUES_LOG: "The safety request the dialog never read").

    @staticmethod
    def _kind_from(icon, kind, fallback):
        """Callers use messagebox's vocabulary: an `icon=` naming the glyph
        ("warning"/"error"/"question"/"info"). Those names ARE our `kind`
        keys, so honour `icon=` (and an explicit `kind=`) instead of
        silently dropping it and always drawing the fallback glyph."""
        return kind or icon or fallback

    def show_info(self, title, message, *, icon=None, kind=None):
        return self._themed_dialog(title, message,
                                   kind=self._kind_from(icon, kind, "info"),
                                   buttons=[("OK", True)])

    def show_warning(self, title, message, *, icon=None, kind=None):
        return self._themed_dialog(title, message,
                                   kind=self._kind_from(icon, kind, "warning"),
                                   buttons=[("OK", True)])

    def show_error(self, title, message, *, icon=None, kind=None):
        return self._themed_dialog(title, message,
                                   kind=self._kind_from(icon, kind, "error"),
                                   buttons=[("OK", True)])

    def ask_yes_no(self, title, message, *, icon=None, kind=None, default=None):
        # `default=` (messagebox's word) names which button keyboard focus
        # lands on — pass default="no" on a destructive confirm so a
        # reflexive Enter doesn't fire "Yes".
        return self._themed_dialog(title, message,
                                   kind=self._kind_from(icon, kind, "question"),
                                   buttons=[("No", False), ("Yes", True)],
                                   default=default)

    def ask_yes_no_cancel(self, title, message, *, icon=None, kind=None,
                          default=None):
        # Returns True (yes), False (no), or None (cancel) — matches messagebox.
        return self._themed_dialog(title, message,
                                   kind=self._kind_from(icon, kind, "question"),
                                   buttons=[("Cancel", None), ("No", False), ("Yes", True)],
                                   default=default)

    def _build_themed_dropdown(self, parent, var, options, on_change,
                               dot_color_fn=None, width_chars=14, nested=False):
        # width_chars=0 sizes to what shows, for a dropdown flexing in a
        # shared row: a width in characters asked more than the row had,
        # and pack cut its arrow off (fonts differ on Linux).
        """A small themed dropdown button for single-choice selectors; pack
        the Frame it returns. `dot_color_fn(value)` gives a bullet's colour
        per option (falsy: none). `nested=True` for one INSIDE another popup:
        it keeps its own list rather than closing the shared popup -- which
        is the editor it sits in."""
        btn = tk.Frame(parent, bg=self.colors["sidebar"],
                      highlightthickness=1, highlightbackground=self.colors["card"])
        lbl = tk.Label(btn, textvariable=var, bg=self.colors["sidebar"],
                      fg=self.colors["text"], font=("Segoe UI", 8),
                      anchor="w", width=width_chars)
        lbl.pack(side="left", padx=(8, 2), pady=4)
        caret = tk.Label(btn, text="▾", bg=self.colors["sidebar"],
                         fg=self.colors["subtext"], font=("Segoe UI", 7))
        caret.pack(side="left", padx=(0, 6))
        # The border too, not just the fill: a long-lived widget tracks EVERY
        # colour option it sets, or a theme switch leaves that one frozen on
        # the build-time palette. Its focus colour is the keyboard's ring.
        self.track_theme(btn, bg="sidebar", highlightbackground="card",
                         highlightcolor="focus_ring")
        self.track_theme(lbl, bg="sidebar", fg="text")
        self.track_theme(caret, bg="sidebar", fg="subtext")

        def open_list():
            if nested:
                # Only THIS dropdown's previous list closes, never the host's
                # popup. No toggle: one made qa9's template flows flaky.
                existing = getattr(btn, "_nested_popup", None)
                if existing is not None:
                    try:
                        if existing.winfo_exists():
                            existing.destroy()
                    except tk.TclError:
                        pass
                    if getattr(self, "_nested_dropdown", None) is existing:
                        self._nested_dropdown = None
                # One nested popup at a time: another one open in the same
                # host (an emoji picker) goes, rather than being left
                # behind untracked when this one takes the slot below.
                self._close_nested_popup()
                pop = tk.Toplevel(self)
                btn._nested_popup = pop
                # Remembered app-wide too, for the window's Escape -- which
                # has no button to ask -- to close THIS list, not its host.
                self._nested_dropdown = pop
            else:
                # A click while its OWN list is open closes it and stops --
                # else a blink, not a toggle (field report).
                if (getattr(btn, "_dd_popup", None) is not None
                        and self._mini_popup is btn._dd_popup):
                    self._dismiss_mini_popup()
                    btn._dd_popup = None
                    return
                # A popup holding typed work asks first. Kept open, the
                # click stops here -- "break", or the window's own
                # click-outside would ask the same question again.
                if not self._dismiss_mini_popup_asking():
                    return "break"
                pop = tk.Toplevel(self)
                self._mini_popup = pop
                btn._dd_popup = pop
            pop.wm_overrideredirect(True)
            pop.configure(bg=self.colors["accent"])
            # A pixel less padding: each row's border (the keyboard's ring)
            # takes it back, so the list is drawn as it always was.
            frame = tk.Frame(pop, bg=self.colors["card"], padx=3, pady=4)
            frame.pack(padx=1, pady=1)
            current = var.get()
            # `options` may be a static list or a callable returning the
            # current list live, so category renames/adds/deletes show up
            # without needing to rebuild this dropdown.
            live_options = options() if callable(options) else options

            for opt in live_options:
                is_cur = (opt == current)
                row_bg = self.colors["sidebar"] if is_cur else self.colors["card"]
                row = tk.Frame(frame, bg=row_bg, cursor="hand2")
                self._ring_round(row, self.colors["card"])
                row.pack(fill="x")
                self._pressable(row, lambda v=opt: pick(v), walk=True,
                                current=is_cur)
                widgets = [row]
                color = dot_color_fn(opt) if dot_color_fn else None
                if color:
                    dot = tk.Label(row, text="●", bg=row_bg, fg=color,
                                   font=("Segoe UI", 11), cursor="hand2")
                    dot.pack(side="left", padx=(10, 6), pady=4)
                    widgets.append(dot)
                lbl2 = tk.Label(row, text=opt, bg=row_bg,
                               fg=self.colors["accent_text"] if is_cur else self.colors["text"],
                               font=("Segoe UI", 9, "bold" if is_cur else "normal"),
                               anchor="w")
                lbl2.pack(side="left", padx=(10 if not color else 0, 10))
                widgets.append(lbl2)

                def pick(v=opt):
                    var.set(v)
                    if nested:
                        try:
                            pop.destroy()
                        except tk.TclError:
                            pass
                        btn._nested_popup = None
                        if getattr(self, "_nested_dropdown", None) is pop:
                            self._nested_dropdown = None
                    else:
                        self._dismiss_mini_popup()
                    on_change(v)

                for w in widgets:
                    # "break": the pick destroys this popup, and a later
                    # script of the same click would call its dead commands.
                    w.bind("<Button-1>", lambda e, v=opt: (pick(v), "break")[1])
                    if not is_cur:
                        w.bind("<Enter>", lambda e, r=row, ws=widgets:
                               [x.configure(bg=self.colors["sidebar"]) for x in ws])
                        w.bind("<Leave>", lambda e, r=row, ws=widgets:
                               [x.configure(bg=self.colors["card"]) for x in ws])

            if nested:
                # Its own Escape: the shared click-outside belongs to the
                # host popup, which nested mode never touches.
                pop.bind("<Escape>", lambda e: pop.destroy())
            self._place_dropdown_popup(pop, btn)

        for w in (btn, lbl, caret):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", lambda e: open_list())
        self._opens_list_from_keyboard(btn, open_list)
        return btn

    def _opens_list_from_keyboard(self, opener, open_list):
        """A dropdown's opener, from the keyboard: Tab stops on it; Space,
        Return, Down and Alt+Down open its list, which takes the keyboard
        while it is open (_keyboard_into_popup)."""
        self._pressable(opener, open_list)
        for seq in ("<KeyPress-Down>", "<Alt-KeyPress-Down>"):
            opener.bind(seq, lambda e: (open_list(), "break")[1])

    def _close_nested_popup(self):
        """Close the popup open INSIDE the open popup (a dropdown's list,
        an emoji picker for one of its fields), if there is one."""
        nested = getattr(self, "_nested_dropdown", None)
        self._nested_dropdown = None
        if nested is not None:
            try:
                if nested.winfo_exists():
                    nested.destroy()
            except tk.TclError:
                pass

    @staticmethod
    def _is_inside_popup(widget, pop):
        """Whether `widget` -- a widget, or the path name a window-level
        binding is handed -- is `pop` or lies inside it."""
        if widget is None or pop is None:
            return False
        path, root = str(widget), str(pop)
        return path == root or path.startswith(root + ".")

    # ---- Window-level bindings that belong to one popup: its own, gone when
    # IT goes, lines naming it to one command never deleted (ARCHITECTURE,
    # "The window-level lines a popup adds") ----

    def _bind_window_for_popup(self, pop, sequence, handler):
        """Run handler(widget_path) for `sequence` on the app window for as
        long as `pop` is open, and never for any other popup."""
        try:
            if not pop.winfo_exists():
                return None
        except tk.TclError:
            return None
        cmd = getattr(self, "_popup_event_cmd", None)
        if cmd is None:
            cmd = self._popup_event_cmd = self.register(
                self._on_popup_window_event)
        self._popup_bind_serial = getattr(self, "_popup_bind_serial", 0) + 1
        token = "p%d" % self._popup_bind_serial
        line = "%s %s %%W" % (cmd, token)
        self.tk.call("bind", self._w, sequence, "+" + line)
        binds = getattr(self, "_popup_window_binds", None)
        if binds is None:
            binds = self._popup_window_binds = {}
        binds[token] = (pop, sequence, line, handler)
        if getattr(pop, "_window_bind_tokens", None) is None:
            pop._window_bind_tokens = []
            # A Toplevel's <Destroy> also fires for each widget inside it,
            # so only its own counts. Asked by path: a widget Tk no longer
            # knows arrives as its bare path name.
            pop.bind("<Destroy>",
                     lambda e, p=pop, path=str(pop): (
                         self._unbind_window_for_popup(p)
                         if str(e.widget) == path else None),
                     add="+")
        pop._window_bind_tokens.append(token)
        return token

    def _on_popup_window_event(self, token, widget_path=""):
        entry = (getattr(self, "_popup_window_binds", None) or {}).get(token)
        if entry is None:
            return      # its popup went away while Tk held this line
        entry[3](widget_path)

    def _unbind_window_for_popup(self, pop):
        """Take `pop`'s lines off the app window. Safe to repeat."""
        binds = getattr(self, "_popup_window_binds", None) or {}
        for token in getattr(pop, "_window_bind_tokens", None) or ():
            entry = binds.pop(token, None)
            if entry is None:
                continue
            sequence, line = entry[1], entry[2]
            try:
                script = str(self.tk.call("bind", self._w, sequence))
                rest = "\n".join(l for l in script.split("\n") if l != line)
                self.tk.call("bind", self._w, sequence,
                             rest if rest.strip() else "")
            except tk.TclError:
                pass
        pop._window_bind_tokens = []

    def _bind_click_outside(self, pop):
        """A click on the app window outside `pop` closes it: the open
        popup through _dismiss_mini_popup_asking, a nested one on its own."""
        return self._bind_window_for_popup(
            pop, "<Button-1>",
            lambda path, p=pop: self._click_outside_popup(p, path))

    def _click_outside_popup(self, pop, widget_path):
        if pop is getattr(self, "_mini_popup", None):
            self._maybe_dismiss_mini_popup(SimpleNamespace(widget=widget_path))
        elif pop is getattr(self, "_nested_dropdown", None):
            if not self._is_inside_popup(widget_path, pop):
                self._close_nested_popup()

    def _place_dropdown_popup(self, pop, anchor_widget=None, anchor_xy=None,
                              enable_click_outside=True, keyboard_from=None):
        """Place a popup as a dropdown: under `anchor_widget`, or at
        `anchor_xy` (root coordinates, as a right-click gives), flipped above
        when there is no room. Clamped to the APP WINDOW, not the screen,
        which names the primary monitor wherever the app is; re-placed as
        the window moves; -topmost, or a borderless popup dropped behind the
        window when an emoji's insert moved the focus."""
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass
        placed = {}

        def reposition(event=None):
            try:
                pop.update_idletasks()
                self.update_idletasks()
                if anchor_widget is not None and anchor_widget.winfo_exists():
                    anchor_widget.update_idletasks()
                    ax = anchor_widget.winfo_rootx()
                    ay = anchor_widget.winfo_rooty()
                    ah = anchor_widget.winfo_height()
                elif anchor_xy is not None:
                    ax, ay = anchor_xy
                    ah = 0
                else:
                    # The anchor is gone: unplaced, the popup sat at the
                    # screen's corner. The window's middle instead.
                    ax = self.winfo_rootx() + self.winfo_width() // 3
                    ay = self.winfo_rooty() + self.winfo_height() // 3
                    ah = 0
                pw = pop.winfo_reqwidth()
                ph = pop.winfo_reqheight()

                win_left = self.winfo_rootx()
                win_top = self.winfo_rooty()
                win_right = win_left + self.winfo_width()
                win_bottom = win_top + self.winfo_height()

                # Vertical: below the button, or above if it would overflow the
                # app window's own bottom edge.
                below_y = ay + ah + 2
                if below_y + ph <= win_bottom - 8:
                    y = below_y
                else:
                    above_y = ay - ph - 2
                    # If it also doesn't fit above, clamp within the app window.
                    y = above_y if above_y >= win_top + 8 else max(win_top + 8, win_bottom - ph - 8)
                # And never past the bottom: "above" an anchor scrolled below
                # the fold (the editor's Use template) ran past it.
                y = max(win_top + 8, min(y, win_bottom - ph - 8))

                # Horizontal: align left edges, nudge in if it would run past
                # the app window's own right edge.
                x = ax
                if x + pw > win_right - 8:
                    x = max(win_left + 8, win_right - pw - 8)
                # Only a move that moves it: placing it where it stands
                # tells its <Configure> again, which would place it again.
                if placed.get("at") != (int(x), int(y)):
                    placed["at"] = (int(x), int(y))
                    pop.wm_geometry(f"+{int(x)}+{int(y)}")
            except tk.TclError:
                pass

        reposition()

        # Configure fires a LOT (a Text growing as emoji go in): a burst is
        # one reposition, after_idle -- each one stuttered.
        pending = {"job": None}

        def throttled_reposition(event=None):
            if pending["job"] is not None:
                return
            def run():
                pending["job"] = None
                reposition()
            pending["job"] = self.after_idle(run)

        # Live-track the app window while this popup is open (move + resize).
        # Taken off again when this popup goes, whichever way it goes.
        self._bind_window_for_popup(pop, "<Configure>", throttled_reposition)
        # ...and the popup's own size: one that grows -- a row added, a part
        # shown -- was placed for its old height and ran past the window.
        pop.bind("<Configure>", lambda e: (throttled_reposition()
                                           if e.widget is pop else None), add="+")
        # Once more when the moment has passed: it can grow during the first
        # placing itself, before that binding was there to hear it.
        throttled_reposition()
        # A popup's OWN Escape is kept: a nested list binds one, and replaced
        # it closed the host editor instead. Innermost first, asking first.
        if not pop.bind("<Escape>"):
            pop.bind("<Escape>", lambda e: self._escape_backs_out())
        # ...which never fires: these popups take no focus, so the key goes
        # to the window. Bound there too, ONCE -- a nested list placed here
        # again would have one Escape close both levels.
        if getattr(self, "_mini_popup_escape_bind", None) is None:
            self._mini_popup_escape_bind = self.bind(
                "<Escape>", self._escape_backs_out, add="+")
        if enable_click_outside:
            self._bind_click_outside(pop)
        # *keyboard_from* is the opener of a popup placed at a point, not on
        # a widget: the calendar's day, its menu opened from the keyboard.
        for opener in (anchor_widget, keyboard_from,
                       getattr(self, "_key_pressing", None)):
            if self._opened_from_keyboard(opener):
                self._keyboard_into_popup(pop, opener)
                break

    def _place_mini_popup(self, pop, anchor_widget=None, anchor_xy=None,
                          keyboard_from=None):
        """Position a mini popup (inline rename, color palette, etc.) just
        below the anchor, flipping above and clamping within the app window's
        own bounds when needed — same safe logic as _place_dropdown_popup, so
        these popups can't run off a different monitor or off the window edge
        on a multi-monitor setup either."""
        self._place_dropdown_popup(pop, anchor_widget, anchor_xy=anchor_xy,
                                   keyboard_from=keyboard_from)

    def _row_stack(self, canvas, **options):
        """A RowStack drawing a list's rows on *canvas*."""
        return RowStack(self, canvas, **options)

    def _scrolling_rows(self, parent, bg_key, pop):
        """A RowStack packed into *parent* for the part of *pop* that grows
        with what it holds, shown in a viewport that scrolls once the popup
        would be taller than the app window: the template editor with 25
        checklist items, and the picker with as many templates, ran off the
        screen, Save and the last templates with them. Tab and the arrows
        bring what they land on into sight, the wheel scrolls it."""
        bg = self.colors[bg_key]
        holder = tk.Frame(parent, bg=bg)
        holder.pack(side="top", fill="both", expand=True)
        view = tk.Canvas(holder, bg=bg, highlightthickness=0, bd=0,
                         width=1, height=1)
        bar = ttk.Scrollbar(holder, orient="vertical", command=view.yview)
        view.pack(side="left", fill="both", expand=True)
        pending = {"job": None}

        def fit():
            pending["job"] = None
            try:
                pop.update_idletasks()
                w, h = stack.size()
                others = pop.winfo_reqheight() - view.winfo_reqheight()
                shown = min(h, max(self.px(80), self.winfo_height() - 16 - others))
                stack.set_width(w)
                view.configure(width=max(1, w), height=max(1, shown))
                if h > shown:
                    bar.pack(side="right", fill="y", before=view)
                else:
                    bar.pack_forget()
            except tk.TclError:
                pass

        def fit_later(_e=None):
            if pending["job"] is None:
                pending["job"] = self.after_idle(fit)

        stack = self._row_stack(view, scrolled=bar.set, on_change=fit_later,
                                own_width=True)

        def wheel(event):
            w = event.widget
            if (isinstance(w, (str, tk.Text))
                    or not str(w).startswith(str(holder) + ".")
                    or not self._is_placed(bar)):
                return None
            up = getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4
            view.yview_scroll(-2 if up else 2, "units")
            return "break"

        self._bind_window_for_popup(pop, "<Configure>", fit_later)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            pop.bind(seq, wheel, add="+")
        # Not fitted now: its update_idletasks would map the popup before it
        # is placed, and -topmost set after that does not stick (ISSUES_LOG:
        # "The template editor that "did nothing" when clicked").
        fit_later()
        return stack

    def _maybe_dismiss_mini_popup(self, event):
        pop = getattr(self, "_mini_popup", None)
        if pop is None:
            return
        # If the click was inside the popup, keep it open.
        if self._is_inside_popup(getattr(event, "widget", None), pop):
            return
        self._dismiss_mini_popup_asking()

    def _dismiss_mini_popup_asking(self, holding_work_only=False):
        """Close the open popup as a PERSON closing it means it -- a click
        outside, Escape, a widget opening something in its place, the page
        or window leaving: one holding typed work asks first
        (_confirm_dismiss); programmatic closes call _dismiss_mini_popup.
        True when no popup is left open. `holding_work_only` leaves one with
        nothing to lose alone. A widget's caller returns "break" on False.
        """
        pop = getattr(self, "_mini_popup", None)
        confirm = getattr(pop, "_confirm_dismiss", None) if pop is not None else None
        if callable(confirm):
            try:
                alive = bool(pop.winfo_exists())
            except tk.TclError:
                alive = False
            # A question on screen already has the floor -- its own
            # "Save changes?", for one -- so nothing closes under it.
            if alive and (self._a_dialog_is_asking() or not confirm()):
                # False: stay open -- or "I saved and closed myself".
                # Only a popup still on screen is someone's unfinished work.
                try:
                    if pop.winfo_exists():
                        return False
                except tk.TclError:
                    pass
        elif holding_work_only:
            return True
        self._dismiss_mini_popup()
        return True

    def _foreground_is_ours(self):
        """Is the OS foreground window one of this app's windows? The only
        honest witness: a borderless popup holds activation without
        <Activate>/<Deactivate>. Off Windows, "ours", so nothing hides.
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
        except (ImportError, AttributeError, OSError):
            return True
        try:
            fg = user32.GetAncestor(user32.GetForegroundWindow(), 2)
            if not fg:
                return True
            ours = {user32.GetAncestor(self.winfo_id(), 2)}
            for child in self.winfo_children():
                if isinstance(child, tk.Toplevel):
                    try:
                        if child.winfo_exists():
                            ours.add(user32.GetAncestor(child.winfo_id(), 2))
                    except tk.TclError:
                        continue
            return fg in ours
        except (tk.TclError, OSError):
            return True

    def _popup_foreground_watch(self):
        """A light heartbeat while popups are involved: hide them when
        another program truly holds the front, bring them back when the
        app does. Popups are HIDDEN, never destroyed -- a half-typed
        template dialog must survive a trip to the browser and back;
        that round trip is exactly what the dialog is for."""
        try:
            self._popup_watch_step()
        finally:
            try:
                self.after(300, self._popup_foreground_watch)
            except tk.TclError:
                pass

    def _popup_watch_step(self):
        hidden = getattr(self, "_popups_hidden_by_deactivate", None)
        popups = []
        for child in self.winfo_children():
            if not isinstance(child, tk.Toplevel):
                continue
            try:
                if (child.winfo_exists() and child.wm_overrideredirect()
                        and child.winfo_viewable()):
                    popups.append(child)
            except tk.TclError:
                continue
        if not popups and not hidden:
            return
        ours = self._foreground_is_ours()
        if popups and not ours:
            self._hide_popups_if_left(popups)
        elif hidden and ours:
            self._popups_hidden_by_deactivate = None
            for pop in hidden:
                try:
                    if pop.winfo_exists():
                        pop.deiconify()
                except tk.TclError:
                    pass

    def _hide_popups_if_left(self, popups):
        self._hiding_popups = True
        try:
            for pop in popups:
                try:
                    pop.withdraw()
                except tk.TclError:
                    pass
        finally:
            self.after(200, lambda: setattr(self, "_hiding_popups", False))
        self._popups_hidden_by_deactivate = popups

    def _on_app_deactivated(self, event):
        """Event-path fast lane: when a Deactivate does arrive (the main
        window losing the front directly), react sooner than the timer."""
        if not isinstance(event.widget, (tk.Tk, tk.Toplevel)):
            return
        self.after(150, self._popup_watch_step)

    def _on_app_activated(self, event):
        if not isinstance(event.widget, (tk.Tk, tk.Toplevel)):
            return
        self.after_idle(self._popup_watch_step)

    def _escape_backs_out(self, event=None):
        """Escape, arriving at the app window, closes the INNERMOST popup:
        a nested list (not `_mini_popup`) before its host. No "break", as
        `_themed_dialog` binds Escape here too; and nothing while a question
        asks -- Escape on "Save changes?" threw the template away.
        """
        if self._a_dialog_is_asking():
            return
        nested = getattr(self, "_nested_dropdown", None)
        if nested is not None:
            self._nested_dropdown = None
            try:
                if nested.winfo_exists():
                    nested.destroy()
                    return
            except tk.TclError:
                pass
        if getattr(self, "_mini_popup", None) is not None:
            self._dismiss_mini_popup_asking()

    def _dismiss_mini_popup(self):
        gif_job = getattr(self, "_gif_anim_job", None)
        if gif_job is not None:
            try:
                self.after_cancel(gif_job)
            except (tk.TclError, ValueError):
                pass
            self._gif_anim_job = None
        # An image preview may still be reading its animation's frames, and
        # its frames were kept alive after it closed (only the cache keeps any).
        self._release_preview_source()
        self._image_preview_ref = None
        pop = getattr(self, "_mini_popup", None)
        if pop is not None:
            try:
                pop.destroy()
                # The destroy and its repaint finished now, not overlapping
                # what runs next (a fixed timer only guessed).
                self.update_idletasks()
            except tk.TclError:
                pass
            self._mini_popup = None
            # Its window-level lines went with it (its <Destroy> takes
            # them); asked again for a popup some other route destroyed
            # before this ran. Repeating it is harmless.
            self._unbind_window_for_popup(pop)
        escape_bind_id = getattr(self, "_mini_popup_escape_bind", None)
        if escape_bind_id is not None:
            try:
                self.unbind("<Escape>", escape_bind_id)
            except tk.TclError:
                pass
            self._mini_popup_escape_bind = None
        # A nested list belongs to the popup that is going away with it --
        # and goes WITH it: it is a window of its own, not a child of the
        # host, so forgetting it left it floating over the app.
        self._close_nested_popup()
        # Work deferred while the popup was open (a rebuild under it
        # flickered) runs now -- a list, so features never overwrite each
        # other's -- one event-loop cycle on, or it tore the frame.
        callbacks = getattr(self, "_mini_popup_on_close", None) or []
        self._mini_popup_on_close = []

        def _run_safely(fn):
            try:
                fn()
            except tk.TclError:
                pass

        for cb in callbacks:
            if callable(cb):
                self.after(150, lambda cb=cb: _run_safely(cb))

    # ---- Where the keyboard is, and keeping it in sight ----

    def _focus_ring(self):
        """The colour of the ring round whatever holds the keyboard."""
        return palette_value(self.colors, "focus_ring")

    # Tk's own buttons take Tab and Space. A control the app draws -- a
    # canvas, a label, a frame of labels -- took neither. Two bind tags,
    # bound once at start, give it both, and arrow keys in a popup's list.
    KEY_PRESS_TAG = "NoteOrganizerKeyPress"
    KEY_WALK_TAG = "NoteOrganizerKeyWalk"

    def _bind_keyboard_tags(self):
        """What the two tags do, for every widget that carries them."""
        for seq in ("<KeyPress-space>", "<KeyPress-Return>", "<KeyPress-KP_Enter>"):
            self.bind_class(self.KEY_PRESS_TAG, seq, self._key_press)
        # The menu key is "App" on Windows and "Menu" on X11, and Tk raises
        # on a keysym it does not know (as the note list found).
        for seq in ("<Shift-KeyPress-F10>", "<KeyPress-App>", "<KeyPress-Menu>"):
            try:
                self.bind_class(self.KEY_PRESS_TAG, seq, self._key_menu)
            except tk.TclError:
                pass
        self.bind_class(self.KEY_PRESS_TAG, "<FocusIn>",
                        lambda e: self._ring_shown(e.widget, True))
        self.bind_class(self.KEY_PRESS_TAG, "<FocusOut>",
                        lambda e: self._ring_shown(e.widget, False))
        for seq, step in (("<KeyPress-Up>", "up"), ("<KeyPress-Down>", "down"),
                          ("<KeyPress-Left>", "left"), ("<KeyPress-Right>", "right"),
                          ("<KeyPress-Home>", "first"), ("<KeyPress-End>", "last")):
            self.bind_class(self.KEY_WALK_TAG, seq,
                            lambda e, s=step: self._key_walk(e.widget, s))
        # Counted for _keyboard_back to tell a click's focus from Windows'.
        # Per button: "all" holds <ButtonPress-1>, which a bare one missed.
        self._pointer_presses = 0
        for button in (1, 2, 3):
            self.bind_all(f"<ButtonPress-{button}>", self._count_pointer_press,
                          add="+")
        # Enter let go of, wherever the keyboard is: a press after it is a
        # press of its own, not the key held down (_enter_repeats).
        self._enter_seen = {}
        for seq in ("<KeyRelease-Return>", "<KeyRelease-KP_Enter>"):
            self.bind_all(seq, self._enter_released, add="+")
        # Space on a Tk button skips _key_press, and runs the command 100 ms
        # later: looked at by a timer made just after Tk's. A tick box runs
        # at once, and is looked at at once.
        self._tk_presses = {}
        starts = self.register(self._tk_press_starts)
        ends = self.register(self._tk_press_ends)
        for cls in ("Button", "Checkbutton", "Radiobutton"):
            try:
                script = str(self.tk.call("bind", cls, "<Key-space>"))
                if script.strip():
                    after = ("after 100 [list {} %W]" if cls == "Button"
                             else "{} %W").format(ends)
                    self.tk.call("bind", cls, "<Key-space>",
                                 f"{starts} %W\n{script}\n{after}")
            except tk.TclError:
                pass

    # A press of Enter this soon after the last, no release between (X11
    # sends one at the same stamp), is the key held: Windows' slowest repeat
    # comes within a second.
    KEY_REPEAT_MS = 1_100

    def _enter_repeats(self, event):
        """Whether *event*, a press, is Enter held down repeating rather than
        pressed again -- False for any other key. A control Enter's press gave
        the keyboard to took each repeat as a press of its own: held on an
        attachment, the picture's preview opened, its Close took the keyboard
        and the next repeat, the name got it back and the next, over and over.
        A press Tk is asked to make carries no time, and is never a repeat."""
        key = getattr(event, "keysym", "")
        if key not in ("Return", "KP_Enter"):
            return False
        when = getattr(event, "time", 0)
        when = when if isinstance(when, int) else 0
        seen = getattr(self, "_enter_seen", None)
        if seen is None:
            seen = self._enter_seen = {}
        last = seen.get(key)
        if not when or last is None:
            held = False
        elif last[0] == "press" and last[1] == when:
            held = last[2]          # the same press, heard twice: one answer
        elif last[0] == "release":
            held = last[1] == when
        else:
            held = 0 < when - last[1] <= self.KEY_REPEAT_MS
        seen[key] = ("press", when, held)
        return held

    def _enter_released(self, event):
        """Enter let go of: its next press is a press again (_enter_repeats)."""
        when = getattr(event, "time", 0)
        if getattr(self, "_enter_seen", None) is None:
            self._enter_seen = {}
        self._enter_seen[getattr(event, "keysym", "")] = (
            "release", when if isinstance(when, int) else 0, False)

    def _count_pointer_press(self, event=None):
        self._pointer_presses = getattr(self, "_pointer_presses", 0) + 1
        # What was pressed, and when: where the keyboard goes when the
        # click puts away the part holding it (_keyboard_off_part).
        self._last_press = (getattr(event, "widget", None), time.monotonic())

    def _tk_press_starts(self, path):
        """Space on one of Tk's own buttons, before its command runs: where
        it stands, and the clicks so far, for _tk_press_ends."""
        try:
            widget = self.nametowidget(path)
            self._tk_presses[path] = (widget, self._place_of(widget),
                                      getattr(self, "_pointer_presses", 0))
        except (KeyError, AttributeError, tk.TclError):
            pass

    def _tk_press_ends(self, path):
        """...and after: a button the press destroyed, or hid with its panel
        (a Close, the Trash's bulk delete), hands the keyboard to what stands
        in its place, as a drawn control's press does -- inside a part of its
        window that lived on, not a question or a popup that went, and not
        after a click put the keyboard somewhere."""
        pressed = getattr(self, "_tk_presses", {}).pop(path, None)
        if pressed is None:
            return
        widget, place, clicks = pressed

        def settle():
            try:
                if self._a_dialog_is_asking():
                    self.after(100, settle)    # its answer may draw the list
                    return
                # Still in sight, or its whole window put away (a popup
                # hidden while another program is in front): left alone.
                if ((widget.winfo_exists() and (
                        widget.winfo_viewable()
                        or not widget.winfo_toplevel().winfo_viewable()))
                        or getattr(self, "_pointer_presses", 0) != clicks):
                    return
            except tk.TclError:
                return
            living = next((p for p, _i in place if self._still_there(p)), None)
            if living is not None and living != place[-1][0]:
                self._keyboard_stays(widget, place)
        try:
            self.after_idle(settle)
        except tk.TclError:
            pass

    def _still_there(self, path):
        try:
            return bool(self.nametowidget(path).winfo_exists())
        except (KeyError, tk.TclError):
            return False

    def _pressable(self, widget, command, walk=False, current=False, menu=None):
        """Let Tab stop on *widget*, and Space or Return press it as a click
        does. With *walk* the arrows move between it and the other choices
        of its popup; *current* marks the one the keyboard starts on; *menu*
        is what its right-click opens, for Shift+F10 and the menu key."""
        widget._key_press = command
        widget._key_current = current
        widget._key_menu = menu
        tags = widget.bindtags()
        extra = (self.KEY_PRESS_TAG,) + ((self.KEY_WALK_TAG,) if walk else ())
        widget.bindtags(tags[:1] + extra + tags[1:])
        widget.configure(takefocus=1)
        return widget

    def _ring_round(self, widget, rest=None, on=None, width=1):
        """The keyboard's ring as *widget*'s border, drawn in *rest* -- the
        colour around it, or with None its own fill -- while the keyboard is
        elsewhere, and in *on* (the theme's ring if None) while it is there."""
        widget._ring_rest = rest
        widget._ring_on = on
        widget.configure(highlightthickness=width,
                         highlightbackground=(rest if rest is not None
                                              else widget.cget("bg")),
                         highlightcolor=on or self._focus_ring())
        return widget

    def _ring_shown(self, widget, on):
        """Both border colours, as the keyboard comes and goes: Windows draws
        no focus colour round a label, only its resting one."""
        if not hasattr(widget, "_ring_rest"):
            return
        try:
            if on:
                colour = widget._ring_on or self._focus_ring()
            else:
                colour = (widget._ring_rest if widget._ring_rest is not None
                          else widget.cget("bg"))
            widget.configure(highlightbackground=colour, highlightcolor=colour)
        except tk.TclError:
            pass

    def _fill(self, widget, colour):
        """A new fill for a control whose ring rests in its own fill (a
        hover, a pressed look): the ring follows, unless it is showing."""
        widget.configure(bg=colour)
        if getattr(widget, "_ring_rest", "") is None:
            try:
                held = str(self.tk.call("focus")) == str(widget)
            except tk.TclError:
                held = False
            self._ring_shown(widget, held)     # a new theme's ring, if held

    def _button_choice(self, button, current=False):
        """A Tk button that is one choice of a popup -- a swatch, a day, a
        template: the arrows walk to it, Return presses it as Space does,
        and its ring rests in its own colour, so it is drawn as before."""
        self._ring_round(button, button.cget("bg"))
        return self._pressable(button, button.invoke, walk=True, current=current)

    def _key_press(self, event):
        widget = event.widget
        press = getattr(widget, "_key_press", None)
        if press is None:
            return None
        if self._enter_repeats(event):
            return "break"              # Enter held down: pressed once
        place = self._place_of(widget)
        # A popup this press opens -- wherever it is anchored -- was asked
        # for from the keyboard (_place_dropdown_popup).
        self._key_pressing = widget
        try:
            press()
        finally:
            self._key_pressing = None
        self.after_idle(lambda: self._keyboard_stays(widget, place))
        return "break"

    def _key_menu(self, event):
        """Shift+F10 or the menu key: the widget's right-click menu, opened
        at the widget as a click would open it at the pointer."""
        widget = event.widget
        menu = getattr(widget, "_key_menu", None)
        if menu is None:
            return None
        try:
            at = SimpleNamespace(
                widget=widget, x=8, y=widget.winfo_height() // 2,
                x_root=widget.winfo_rootx() + 8,
                y_root=widget.winfo_rooty() + widget.winfo_height() // 2)
        except tk.TclError:
            return "break"
        menu(at)
        return "break"

    @staticmethod
    def _block_of(row):
        """The rows *row* stands among: its block of a RowStack, across the
        chunks a redraw makes again, or else its own parent."""
        stack = getattr(row.master.master, "_row_stack", None)
        group = stack.group_of(row.master) if stack is not None else None
        return group if group is not None else row.master

    @staticmethod
    def _place_of(widget):
        """Where *widget* stands: its path and its place among its siblings,
        then its parent's, up to its window -- enough to find what stands
        there once a list or a page has been drawn again."""
        place = []
        w = widget
        try:
            while w is not None and not isinstance(w, (tk.Tk, tk.Toplevel)):
                # A RowStack row: its place among its block's rows, not its
                # chunk's, which a redraw may not make again.
                stack = getattr(getattr(w.master, "master", None),
                                "_row_stack", None)
                at = stack.place_of_row(w) if stack is not None else None
                if at is not None:
                    place.append((str(w), at))
                    w = w.master.master
                    continue
                kids = [k for k in w.master.winfo_children()
                        if not isinstance(k, tk.Toplevel)]
                place.append((str(w), kids.index(w)))
                w = w.master
        except (tk.TclError, ValueError, AttributeError):
            pass
        if w is not None:
            place.append((str(w), 0))
        return place

    def _found_at(self, place):
        """What stands at *place* now: the widget itself if it lives, else
        the one at the same places below its nearest ancestor still alive,
        or the first control after that point if none takes the keyboard."""
        for depth, (path, _index) in enumerate(place):
            try:
                w = self.nametowidget(path)
                if w.winfo_exists():
                    break
            except (KeyError, tk.TclError):
                continue
        else:
            return None
        if depth:
            for _path, index in reversed(place[:depth]):
                if isinstance(index, tuple):
                    # (block, row) on a RowStack: the row there now, or the
                    # block's last when it has fewer.
                    stack = getattr(w, "_row_stack", None)
                    groups = stack.groups if stack is not None else []
                    kids = (groups[min(index[0], len(groups) - 1)].rows()
                            if groups else [])
                    index = index[1]
                else:
                    kids = [k for k in w.winfo_children()
                            if not isinstance(k, tk.Toplevel)]
                if not kids:
                    break
                w = kids[min(index, len(kids) - 1)]
        try:
            if str(self.tk.call("tk::FocusOK", w)) == "1":
                return w
            return w.tk_focusNext()
        except (tk.TclError, KeyError):
            return None

    def _keyboard_nowhere(self, gone=""):
        """Whether the keyboard is on nothing -- or on *gone*, a window
        being taken down -- rather than somewhere a person put it. A popup
        holding it itself is nothing too, as the main window is: Tk puts it
        there when the control that held it is destroyed."""
        try:
            now = str(self.tk.call("focus"))
            if now not in ("", ".") and not (
                    gone and (now == gone or now.startswith(gone + "."))):
                held = self.nametowidget(now)
                if isinstance(held, tk.Toplevel):
                    return True
                return not (held.winfo_exists() and held.winfo_viewable())
        except KeyError:
            return True
        except tk.TclError:
            return False
        return True

    def _keyboard_stays(self, widget, place):
        """After a press from the keyboard: a press that drew its list or
        page again took the control with it, or hid it (a bar it closed),
        and the keyboard fell to nothing. It goes to what stands in that
        control's place now, or to the next control on."""
        try:
            if widget.winfo_exists() and widget.winfo_viewable():
                return
        except tk.TclError:
            pass
        if not self._keyboard_nowhere():
            return
        # What was just drawn, mapped: a new row's controls are mapped an
        # idle round after the row, and Tab's own test skips them until then.
        self.update_idletasks()
        target = self._found_at(place)
        if target is not None:
            target.focus_set()
            self._bring_into_sight(target)

    def _walk_choices(self, top, drawn=True):
        """The choices the arrows walk in *top*, in reading order -- or, for
        a popup not yet drawn (*drawn* False), all of them as they were made."""
        found = []

        def gather(w):
            for child in w.winfo_children():
                if isinstance(child, tk.Toplevel):
                    continue
                if (self.KEY_WALK_TAG in child.bindtags()
                        and (not drawn or child.winfo_viewable())):
                    found.append(child)
                gather(child)
        gather(top)
        if not drawn:
            return found
        return sorted(found, key=lambda w: (self._root_y(w), self._root_x(w)))

    def _centre_of(self, w):
        # Where the choice stands in its list, not its parked chunk's place:
        # Left in a one-column picker went to a template 30 rows down.
        return (self._root_x(w) + w.winfo_width() / 2,
                self._root_y(w) + w.winfo_height() / 2)

    def _root_x(self, w):
        """*w*'s rootx where it stands in its list, as _root_y reads its y:
        a chunk in the view stands at its box's left (RowStack._follow)."""
        x, child = w.winfo_rootx(), w
        while child.master is not None and not isinstance(child, (tk.Tk, tk.Toplevel)):
            canvas = child.master
            stack = getattr(canvas, "_row_stack", None)
            box = stack.box(child) if stack is not None else None
            if box is not None:
                x += int(box[0]) - child.winfo_x()
            child = canvas
        return x

    def _root_y(self, w):
        """*w*'s rooty where it stands in its list, though a row stack has
        its chunk placed out of sight (RowStack): sorted by that place, the
        picker's last templates came first."""
        y, child = w.winfo_rooty(), w
        while child.master is not None and not isinstance(child, (tk.Tk, tk.Toplevel)):
            canvas = child.master
            stack = getattr(canvas, "_row_stack", None)
            box = stack.box(child) if stack is not None else None
            if box is not None:
                y += int(round(box[1] - canvas.canvasy(0))) - child.winfo_y()
            child = canvas
        return y

    def _key_walk(self, widget, step):
        """Up, Down, Left and Right go to the nearest choice that way, Home
        and End to the first and the last: one rule for a list, a grid of
        swatches and the emoji picker's groups alike."""
        try:
            choices = self._walk_choices(widget.winfo_toplevel())
            if not choices:
                return "break"
            if step in ("first", "last"):
                target = choices[0] if step == "first" else choices[-1]
            else:
                hx, hy = self._centre_of(widget)
                best = None
                for c in choices:
                    if c is widget:
                        continue
                    cx, cy = self._centre_of(c)
                    ahead, aside = {"down": (cy - hy, cx - hx),
                                    "up": (hy - cy, cx - hx),
                                    "right": (cx - hx, cy - hy),
                                    "left": (hx - cx, cy - hy)}[step]
                    if ahead <= 1:
                        continue
                    score = ahead + 3 * abs(aside)
                    if best is None or score < best[0]:
                        best = (score, c)
                target = best[1] if best else None
        except tk.TclError:
            return "break"
        if target is not None:
            target.focus_set()
            self._bring_into_sight(target)
        return "break"

    def _opened_from_keyboard(self, opener):
        """Whether the popup about to open on *opener* was asked for from
        the keyboard. A box being typed in keeps the keyboard: a popup it
        anchors (the emoji picker of a field) is the mouse's to use."""
        return (opener is not None and self._holds_keyboard(opener)
                and opener.winfo_class() not in self._TYPING_CLASSES)

    def _keyboard_into_popup(self, pop, opener):
        """A popup opened from the keyboard takes it -- its current choice,
        else its first, else its first box, else its first control, unless
        it placed it itself -- and hands it back to *opener* on closing.
        The box before the control: the first control is the header's ✕,
        and a space typed into the template's name closed the editor."""
        try:
            if str(self.tk.call("focus", "-lastfor", pop)) == str(pop):
                choices = self._walk_choices(pop, drawn=False)
                current = [c for c in choices if getattr(c, "_key_current", False)]
                box = self._first_box_in(pop)
                target = (current or choices or [box or pop.tk_focusNext()])[0]
                if target is not None:
                    target.focus_set()
                    if target is box:
                        self._arrive_as_tab_does(box)
        except (tk.TclError, KeyError):
            return
        path, place = str(pop), self._place_of(opener)
        clicks = getattr(self, "_pointer_presses", 0)
        pop.bind("<Destroy>", lambda e: (self._keyboard_back(path, place, clicks)
                                         if str(e.widget) == path else None),
                 add="+")

    def _first_box_in(self, pop):
        """The first box to type in, in the order Tab takes through *pop*
        (the order its widgets stack in), or None. Asked of the tree, not of
        Tk's traversal, which skips everything until the popup is drawn."""
        def placed(w):
            while w is not pop:
                if not w.winfo_manager():
                    return False
                w = w.master
            return True

        def walk(w):
            for c in w.winfo_children():
                if isinstance(c, tk.Toplevel):
                    continue
                if (c.winfo_class() in self._TYPING_CLASSES
                        and str(c.cget("takefocus")) != "0"
                        and str(c.cget("state")) != "disabled" and placed(c)):
                    return c
                found = walk(c)
                if found is not None:
                    return found
            return None
        try:
            return walk(pop)
        except (tk.TclError, AttributeError):
            return None

    @staticmethod
    def _arrive_as_tab_does(box):
        """In a one-line box, what it holds selected and the caret after it,
        as Tk's own Tab arrives there: the first key typed replaces a new
        template's "Untitled template", or the month jump's year. A box of
        many lines is left as it is, as Tab leaves it."""
        try:
            if not isinstance(box, tk.Text):
                box.selection_range(0, "end")
                box.icursor("end")
        except (tk.TclError, AttributeError):
            pass

    def _keyboard_back(self, path, place, clicks):
        """Back to the opener once its popup has gone, by any road -- or to
        what stands in its place, when the choice drew its page again. Not
        while a question is asking, and not where a click put it since."""
        def back():
            if self._a_dialog_is_asking():
                try:
                    self.after(100, back)
                except tk.TclError:
                    pass
                return
            target = self._found_at(place)
            if target is None:
                return
            clicked = getattr(self, "_pointer_presses", 0) != clicks
            # Without a click, a keyboard in another window was put there by
            # Windows, activating whatever was under the closed popup.
            if not self._keyboard_nowhere(gone=path) and (
                    clicked or self._keyboard_in_window_of(target)):
                return
            try:
                if target.winfo_viewable():
                    target.focus_set()
                    self._bring_into_sight(target)
            except tk.TclError:
                pass
        self.after_idle(back)

    def _keyboard_in_window_of(self, widget):
        """Whether the keyboard is somewhere in *widget*'s own window."""
        try:
            now = self.nametowidget(str(self.tk.call("focus")))
            return now.winfo_toplevel() is widget.winfo_toplevel()
        except (KeyError, tk.TclError):
            return False

    def _holds_keyboard(self, widget):
        """Whether the keyboard is on *widget* in its window, by Tk's own
        record (focus -lastfor): it holds while another program has the
        foreground, and a click on a button or a drawn control never sets it."""
        try:
            return str(self.tk.call("focus", "-lastfor", widget)) == str(widget)
        except tk.TclError:
            return False

    def _keyboard_inside(self, container):
        """The widget holding the keyboard, by Tk's own record, when it is
        *container* or inside it; else None."""
        try:
            held = str(self.tk.call("focus", "-lastfor", self))
            if held == str(container) or held.startswith(str(container) + "."):
                return self.nametowidget(held)
        except (KeyError, tk.TclError):
            pass
        return None

    def _keyboard_to(self, target):
        """Put the keyboard on *target*, laid out first. Tk holds a request
        for a window not mapped yet -- a note inside a canvas, a moment after
        its page came back -- until it is, the keys meanwhile going where
        they went: so the window takes them first, and types nothing."""
        if target is None:
            return
        try:
            self.update_idletasks()
            if not target.winfo_viewable():
                self.focus_set()
            target.focus_set()
        except tk.TclError:
            pass

    def _watch_parts_put_away(self):
        """Bound once at start. A part of the window put away while the
        keyboard is in it -- the checklist folded, the calculator, a panel
        closed, a Settings section left -- kept it: a click takes no
        keyboard, and keys went on into what nobody could see, and were
        saved. One watcher for every such part, made now or later."""
        self.bind_all("<Unmap>", self._part_put_away, add="+")

    def _part_put_away(self, event):
        """An unmapped widget its manager has forgotten (pack, grid or place
        forget), with the keyboard inside it, is looked at again once the
        moment has passed: a row laid out again is forgotten and packed back
        in one go. Scrolled out of a canvas, or a tab left, it stays managed."""
        part = event.widget
        if isinstance(part, (str, tk.Tk, tk.Toplevel)):
            return
        try:
            if part.winfo_manager():
                return
            held = str(self.tk.call("focus", "-lastfor", part))
            if not (held == str(part) or held.startswith(str(part) + ".")):
                return
            held = self.nametowidget(held)
        except (KeyError, tk.TclError):
            return
        self.after_idle(lambda: self.after_idle(
            lambda: self._keyboard_off_part(held)))

    def _keyboard_off_part(self, held):
        """The keyboard off *held*, put away with its part: to the control
        just clicked, when it is in sight and takes it (the checklist's own
        bar, a Settings entry), else to the next control on, as a press
        that hid its own button hands it on (_keyboard_stays)."""
        try:
            if not held.winfo_exists():
                return
            top = held.winfo_toplevel()
            # Laid out again, it maps once its row's new size settles: pack
            # asks the parent first, so a toolbar re-dealt by a resize read as
            # put away, and the keyboard went on into the note.
            part, laid_out = held, True
            while laid_out and part is not None and part is not top:
                laid_out, part = bool(part.winfo_manager()), part.master
            now = str(self.tk.call("focus"))
            if (laid_out or str(self.tk.call("focus", "-lastfor", top)) != str(held)
                    or (now and self.nametowidget(now).winfo_toplevel() is not top)
                    or held.winfo_viewable() or not top.winfo_viewable()):
                return      # laid out again, moved since, in sight, or the window away
            target, at = getattr(self, "_last_press", (None, 0.0))
            if not (target is not None and time.monotonic() - at < 1.0
                    and not isinstance(target, str) and target.winfo_exists()
                    and target.winfo_toplevel() is top
                    and str(self.tk.call("tk::FocusOK", target)) == "1"):
                target = held.tk_focusNext()
        except (KeyError, tk.TclError):
            return
        self._keyboard_to(target if target is not None else top)

    def _tab_target_into_sight(self, event, backwards=False):
        """Tab moves the keyboard and never the view, so what it lands on is
        brought into sight. Runs after Tk's own traversal (bound with "+")."""
        try:
            here = event.widget
            target = here.tk_focusPrev() if backwards else here.tk_focusNext()
        except (tk.TclError, KeyError, AttributeError):
            return
        if target is not None:
            self._bring_into_sight(target)

    def _bring_into_sight(self, widget, part=None):
        """Scroll each canvas holding *widget* on a page just far enough to
        show it -- or *part*, a (top, bottom) span of it -- innermost first:
        the editor, Settings, the calendar and the Trash, Share and emoji
        lists are frames drawn on canvases."""
        try:
            child = widget
            while child is not None and not isinstance(child, (tk.Tk, tk.Toplevel)):
                parent = child.master
                if (isinstance(parent, tk.Canvas) and isinstance(child, tk.Frame)
                        and self._drawn_box(parent, child) is not None):
                    self._show_on_canvas(parent, child, widget, part)
                child = parent
        except (tk.TclError, AttributeError, ValueError, TypeError):
            pass

    def _in_sight(self, widget):
        """Whether *widget* stands where the person can see it: mapped, and
        wholly inside the view of every canvas it is scrolled on, as
        _bring_into_sight would leave it. winfo_viewable() alone means mapped:
        the note page's status line, at the foot of the scrolled editor, is
        mapped while far below the view at the window's own sizes."""
        try:
            if not widget.winfo_viewable():
                return False
            child = widget
            while child is not None and not isinstance(child, (tk.Tk, tk.Toplevel)):
                parent = child.master
                box = (self._drawn_box(parent, child)
                       if isinstance(parent, tk.Canvas) and isinstance(child, tk.Frame)
                       else None)
                if box is not None:
                    top = box[1] + self._offset_within(widget, child, "y")
                    shown = parent.canvasy(0)
                    if (top < shown or top + widget.winfo_height()
                            > shown + parent.winfo_height()):
                        return False
                child = parent
            return True
        except (tk.TclError, AttributeError, ValueError, TypeError):
            return False

    @staticmethod
    def _canvas_window_item(canvas, child):
        for item in canvas.find_all():
            if (canvas.type(item) == "window"
                    and str(canvas.itemcget(item, "window")) == str(child)):
                return item
        return None

    def _drawn_box(self, canvas, child):
        """Where *canvas* draws *child*, in its own coordinates: a window
        item's box, or a row stack's chunk's (RowStack); else None."""
        stack = getattr(canvas, "_row_stack", None)
        if stack is not None and stack.box(child) is not None:
            return stack.box(child)
        if child.winfo_manager() != "canvas":
            return None
        item = self._canvas_window_item(canvas, child)
        return canvas.bbox(item) if item is not None else None

    def _offset_within(self, widget, page, axis):
        """How far *widget* lies from *page*'s top (axis "y") or left edge.
        A canvas on the way is crossed by its scroll, which it updates at
        once; the windows on it move only when it next draws."""
        total, w = 0.0, widget
        while w is not None and w is not page:
            parent = w.master
            box = (self._drawn_box(parent, w)
                   if isinstance(parent, tk.Canvas) else None)
            if box is not None:
                shown = parent.canvasy(0) if axis == "y" else parent.canvasx(0)
                total += box[1 if axis == "y" else 0] - shown
            else:
                total += w.winfo_y() if axis == "y" else w.winfo_x()
            w = parent
        return total

    def _show_on_canvas(self, canvas, page, widget, part=None):
        """Scroll *canvas*, which draws *page*, until *widget* (or *part* of
        it) is inside its view with a small margin -- the least movement."""
        box = self._drawn_box(canvas, page)
        if box is None:
            return
        region = str(canvas.cget("scrollregion")).split() or canvas.bbox("all")
        if not box or not region or len(region) != 4:
            return
        region = [float(v) for v in region]
        margin = self.px(6)
        for axis, i in (("y", 1), ("x", 0)):
            view = canvas.winfo_height() if axis == "y" else canvas.winfo_width()
            span = region[i + 2] - region[i]
            if view <= 1 or span <= view:
                continue
            near = box[i] + self._offset_within(widget, page, axis)
            if axis == "y" and part is not None:
                near, far = near + part[0], near + part[1]
            else:
                far = near + (widget.winfo_height() if axis == "y"
                              else widget.winfo_width())
            shown = canvas.canvasy(0) if axis == "y" else canvas.canvasx(0)
            if near - margin < shown:
                start = near - margin
            elif far + margin > shown + view:
                start = min(near - margin, far + margin - view)
            else:
                continue
            fraction = max(0.0, min((start - region[i]) / span, 1.0))
            (canvas.yview_moveto if axis == "y" else canvas.xview_moveto)(fraction)
            # A move the person made, as the scrollbar's is: it beats a
            # table rebuild's restore still in force (_editor_scrollbar_moved).
            if canvas is getattr(self, "editor_canvas", None):
                self._grid_view_restore = None
