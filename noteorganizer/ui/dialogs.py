"""In-app dialogs, dropdowns and popups.

WHAT THIS IS FOR
----------------
Everything the app puts *over* itself: the message and confirmation
dialogs, the themed dropdowns, and the small floating popups. No native
OS dialog appears anywhere in the app except the last-resort startup
crash box, so all of this is drawn from scratch.

WHY THESE BELONG TOGETHER
-------------------------
This group was chosen from the call graph rather than from a heading:
roughly 60% of the calls these methods make are to each other, which is
the highest of any group in the class. They are also the most *called*
code in the app -- show_info alone has eleven callers -- so having one
place that decides how an overlay looks and where it goes matters more
here than almost anywhere else.

THE POSITIONING RULE WORTH KNOWING
----------------------------------
:meth:`_place_dropdown_popup` measures against the app window's own
bounds, never the screen's. Measuring against the screen looks equivalent
until someone has two monitors, at which point a popup can open on a
display the app is not on. Every popup goes through this one function for
that reason -- see ``docs/ISSUES_LOG.md``, "The dropdown that opened on
the wrong monitor".

See :mod:`noteorganizer.ui` for what a mixin is and the two rules that
keep them working.
"""

import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ..core.themes import letters_on, palette_value


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
        """A modal, in-theme replacement for tkinter's messagebox. Renders as an
        overlay INSIDE the app window (not a separate OS window), so it can't be
        dragged off-screen and moves/minimizes with the app. Blocks until the
        user picks a button, then returns that button's value.

        `default` is the LABEL (case-insensitive) of the button that should
        take keyboard focus, i.e. the one Enter triggers. Without it the
        last (primary) button is focused — which is wrong for a
        destructive confirm, where Enter would fire "Yes": pass
        default="No" so a reflexive Enter is safe. Escape still returns
        the first button's value (the safe/cancel choice) regardless.

        Both keys answer only the innermost question when one is asked
        over another, and Enter takes the button holding the keyboard --
        the default, unless the person moved it (Tab)."""
        if buttons is None:
            buttons = [("OK", True)]
        focus_index = self._dialog_focus_index(buttons, default)
        # Where the keyboard was, so it goes back there when the question
        # is answered. The dialog takes the focus onto its own button and
        # is then destroyed, and Tk handed the keyboard to the bare window:
        # someone typing a note, interrupted by a question, answered it and
        # kept typing into nothing until they clicked back in. focus_get()
        # answers None while another program holds the desktop foreground
        # (qa/README), so the window's own record is the fallback.
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

        # The overlay lives INSIDE the main window, and a -topmost
        # popup floats above that -- so a question ABOUT the popup (save
        # your changes?) rendered underneath it, unreachable. The popups
        # step back for the dialog's duration and return after.
        stepped_back = self._popups_step_back()
        icon = {"info": "ℹ", "warning": "⚠", "error": "⛔",
                "question": "❓", "success": "✅"}.get(kind, "ℹ")
        accent = {"error": self.colors["danger"], "warning": self.colors["danger"],
                  "success": self.colors["success"]}.get(kind, self.colors["accent"])

        result = {"value": None, "answered": False}
        done = tk.IntVar(value=0)

        # A thin transparent-ish "click catcher" that keeps the background
        # VISIBLE but swallows clicks/keys so the app underneath can't be used
        # while the dialog is open. It's a 1x1-anchored full-size frame drawn
        # only where the card isn't — but since tk frames are opaque, we instead
        # place the card directly and block interaction via an event grab on a
        # tiny transparent overlay strip. Simpler and flicker-free: place the
        # card over the window (background stays visible) and intercept clicks
        # through a global binding while the dialog is up.
        border = tk.Frame(self, bg=accent, highlightthickness=0)
        border.place(relx=0.5, rely=0.42, anchor="center")
        card = tk.Frame(border, bg=self.colors["card"])
        card.pack(padx=2, pady=2, fill="both", expand=True)

        # The answers first, against the bottom. When the card is given less
        # height than it asks for, pack takes the shortfall from what was
        # packed LAST -- the message, which then scrolls (fit, below) -- so
        # no length of message can push a button out of the window. A
        # startup notice joining four messages drew its only button below a
        # 600px window, with the X refused while it asked.
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
        msg_lbl = tk.Label(msg_view, text=message, bg=self.colors["card"],
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

        # Tab walks the question's own answers and comes back round, as a
        # Windows message box does. The grab holds the pointer only, and
        # Tab walked on out of the card: into the note under the question,
        # where typing landed, and onto the note list, whose Shift+F10 menu
        # holds Delete. The order is the one Tab always took. Shift+Tab is
        # <<PrevWindow>> too: on X11 it arrives as ISO_Left_Tab.
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
            # The docstring above and ARCHITECTURE always said Enter takes
            # the default, and it did nothing at all: a tk.Button answers
            # Space and the mouse, and nothing bound Return. The button
            # holding the keyboard is what Enter presses. A key typed into
            # some other field (Tab stays in the card now, but a timer can
            # still move the keyboard) is that field's own business.
            if not innermost():
                return
            w = getattr(event, "widget", None)
            if w in dialog_buttons:
                w.invoke()
            elif w is self or self._is_inside_popup(w, border):
                asking["default"].invoke()

        esc_bind = self.bind("<Escape>", escape, add="+")
        enter_binds = [(seq, self.bind(seq, enter, add="+"))
                       for seq in ("<Return>", "<KP_Enter>")]
        # No wait may outlive its window. Closing the app under a question
        # destroyed the window while this still waited for `done`, which
        # nothing would ever set again: the process lived on with no
        # window, holding the notebook lock, and every later launch was
        # refused as "already open". on_app_close refuses the close while
        # a question asks; this is the net under every other route.
        border.bind("<Destroy>", lambda e: choose(safe_val), add="+")

        # The card inside the window, its answers on screen, whatever the
        # message's length and the window's size: placed at 0.42 of the
        # height as it always was when it fits; otherwise the message's
        # viewport gives way, and a row of buttons wider than the window
        # stands one under another. Asked again when the window is resized
        # while the question waits.
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

        # Modal, but the background stays fully visible (we don't cover it). A
        # local grab on the dialog frame routes input to the dialog only; because
        # this is an ordinary in-window Frame (not a borderless Toplevel), the
        # grab is safe and won't freeze the app.
        self.update_idletasks()
        try:
            border.grab_set()
        except tk.TclError:
            pass
        # While this waits for an answer, the app's global shortcuts stand
        # still (_a_dialog_is_asking). A grab confines the POINTER only;
        # keys bound with bind_all still ran underneath -- Ctrl+S twice
        # stacked the same question on itself, and Ctrl+N under the
        # repeating-day question cleared the editor so the answer wrote
        # the edit under a day of None. Raised here, right beside the
        # finally that lowers it, so no failure can leave it raised.
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
            # Tk has ONE grab. A question asked inside this one's wait -- a
            # timer's "Export complete" over a waiting "Move to trash?" --
            # took it, and its release above left none: the question still
            # on screen, and the app under it taking clicks (a note ticked
            # there was removed with no Trash copy). The question asked
            # before it, still waiting, gets the grab back.
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
        """Make a button open its popup on one click and close it on the next.

        A tk.Button acts on the RELEASE, and the app-wide click-outside
        handler closes the open popup on the PRESS -- so a second click on
        the button that opened a popup closed it and then opened a fresh
        one: a blink instead of a toggle. The themed dropdowns were fixed
        for exactly this after a field report (their guard, in
        _build_themed_dropdown, is the same idea); eleven other openers --
        the text colour, the highlight, the emoji, both date pickers, the
        note's colour, the table size, the template picker, the calendar's
        month, and the selection bar's Category and Export -- never were.

        The decision is taken on the press, in the button's own binding,
        which runs before the window's: at that moment the popup is still
        open and it is knowable whether it is this button's. It is taken
        afresh on every press, so a press dragged off the button leaves
        nothing behind to swallow the next click.
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

    # These five took **kw and forwarded a subset of it, so anything a
    # caller sent that they did not understand was dropped without a word.
    # That has cost this project twice: first a `default="no"` on a
    # destructive confirm that never reached the dialog (ISSUES_LOG, "the
    # safety request the dialog never read"), then seven `parent=`
    # arguments that read like they anchored the dialog somewhere and did
    # nothing at all — this is an overlay inside the app window, and
    # _themed_dialog has never had such a parameter.
    #
    # Named parameters instead, keyword-only, so Python itself refuses
    # anything else at the call rather than swallowing it. A stray keyword
    # is now a TypeError the first time that path runs, which is the whole
    # point: the failure this class produces is silence.

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
        # width_chars=0 means "as wide as whatever is showing" -- Tk's own
        # content sizing. Use it for a dropdown that shares a row and is
        # packed to flex: a width fixed in CHARACTERS makes the control
        # ask for more than the row has, and pack takes the difference off
        # its right edge (arrow first, then letters) instead of the label
        # simply shrinking. No fixed number can be right for both
        # platforms anyway -- the same count that fits Segoe UI on Windows
        # is 19px over-full in DejaVu Sans on the Linux CI image.
        """Build a small themed dropdown button (replaces ttk.Combobox for
        simple single-choice selectors like sort/filter). Returns the button
        Frame; pack it into the caller's layout. `dot_color_fn(value)` — if
        given — returns a hex color to show a bullet next to each option (used
        for the category filter); return None/falsy to skip the bullet for
        that option (e.g. "All").

        `nested=True` — use when this dropdown lives INSIDE another popup
        (e.g. the category picker inside the template editor). The default
        path calls self._dismiss_mini_popup() to close whatever popup was
        open before opening a new, unrelated one — but a dropdown nested
        inside another popup IS that popup's content, not something separate
        to replace; calling the shared dismiss would destroy the very editor
        this dropdown is sitting inside, before its own list even opens.
        Nested mode tracks its own small popup instead, leaving whatever the
        app's main self._mini_popup is completely alone."""
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
                # Close only THIS dropdown's own previous popup, if any —
                # never touch self._mini_popup, which belongs to whatever
                # popup this dropdown is living inside. (No toggle here,
                # deliberately: adding one destabilized qa9's template
                # flows intermittently, and the nested blink was never
                # field-reported — tracked in the triage list instead.)
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
                # Also remembered app-wide, so the app-window Escape can
                # close THIS list rather than the popup it lives inside.
                # btn._nested_popup alone is not enough: the handler runs on
                # the window, and has no button to ask.
                self._nested_dropdown = pop
            else:
                # Clicking the button while its OWN list is open closes
                # it and stops. Without this, the shared dismiss below
                # closed the list and the reopen brought it straight
                # back — a blink instead of a toggle (field report:
                # the only way to close it was clicking elsewhere).
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
                    # "break": the pick destroys the popup this row lives
                    # in, and Tk has already read every script of this
                    # click -- a later one naming the popup's commands
                    # would call them dead (the rename box's Escape did).
                    w.bind("<Button-1>", lambda e, v=opt: (pick(v), "break")[1])
                    if not is_cur:
                        w.bind("<Enter>", lambda e, r=row, ws=widgets:
                               [x.configure(bg=self.colors["sidebar"]) for x in ws])
                        w.bind("<Leave>", lambda e, r=row, ws=widgets:
                               [x.configure(bg=self.colors["card"]) for x in ws])

            if nested:
                # Escape is this dropdown's own way to back out without
                # picking anything, since it can't rely on the shared
                # click-outside-dismiss (that's scoped to self._mini_popup,
                # which nested mode deliberately never touches).
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

    # ---- Window-level bindings that belong to one popup ----
    #
    # A popup listens on the app window for two things while it is open: a
    # click outside it (to close) and the window moving (to follow). These
    # used to be kept in ONE attribute per kind, overwritten by every
    # placement -- and a dropdown nested inside a popup is placed while its
    # host is still open, so the host's ids were lost and its handlers
    # stayed bound for good. From then on every click ran a stale
    # click-outside that closed the dropdown the same click had just
    # opened: after one nested list, no dropdown in the app would open.
    #
    # So each popup keeps its own, and they go when IT goes, by whatever
    # route. And they are lines that NAME their popup and call one command
    # that is never deleted: Tk expands every script for a click before it
    # runs any of them, so unbinding a handler from a widget's own
    # <Button-1> deleted a command the same click was still about to call
    # -- a silent background error on every such click. A line removed
    # after Tk read it now just calls with a popup that is no longer
    # registered, and does nothing.

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
        """Position a popup like a dropdown anchored to a button: directly below
        it if there's room, otherwise flipped above so it never runs off-screen.
        Horizontally aligned to the button's left edge (nudged in if needed).

        Pass either `anchor_widget` (a button/label to dock under) or
        `anchor_xy` (an (x, y) root-coordinate pair, e.g. from a right-click
        event) when there's no persistent widget to anchor to — a calendar day
        cell reached via a context menu, for instance.

        Clamped to the APP WINDOW's own bounds, not the system screen. On a
        multi-monitor setup, winfo_screenwidth/height() reports the primary
        display's size even when the app sits on a different monitor, which
        used to yank the dropdown back onto the wrong screen entirely. The
        app window's own root x/y/width/height are always correct for
        whichever monitor it's actually on, so anchoring to those keeps the
        dropdown next to the button regardless of monitor arrangement.

        Also re-anchors LIVE while the popup is open: if the user drags or
        resizes the app window, the popup used to stay put at its original
        screen position — visibly detached from the app. Binding this to the
        app's own <Configure> event keeps it docked the whole time.

        Marked -topmost so it can't get pushed behind the main window when
        focus shifts elsewhere in the app (e.g. inserting an emoji sets focus
        on the text field being edited) — without this, a borderless Toplevel
        with no owner/topmost relationship can silently drop behind its
        parent window on focus changes, which looks exactly like the popup
        having closed even though it's technically still open."""
        try:
            pop.attributes("-topmost", True)
        except tk.TclError:
            pass

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
                    # The anchor is gone. Asking it for its place raised,
                    # the error was swallowed, and the popup was never
                    # placed at all -- it sat at the screen's corner,
                    # detached from the app. The window's middle instead.
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

                # Horizontal: align left edges, nudge in if it would run past
                # the app window's own right edge.
                x = ax
                if x + pw > win_right - 8:
                    x = max(win_left + 8, win_right - pw - 8)
                pop.wm_geometry(f"+{int(x)}+{int(y)}")
            except tk.TclError:
                pass

        reposition()

        # Configure fires a LOT — not just window move/resize, but also
        # cascading from things like text insertion changing a Text widget's
        # geometry. Coalescing rapid bursts into one actual reposition (via
        # after_idle) keeps the popup docked without redoing the work on
        # every single event, which was contributing to visible stutter
        # while quickly inserting several emojis in a row.
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
        # Never clobber a popup's OWN Escape: a nested dropdown binds
        # Escape→close-just-this-list before being placed, and replacing
        # that here made Escape tear down the HOST editor the list sits
        # inside instead of the list itself. Innermost first, like the
        # window's own Escape below, and asking where there is work.
        if not pop.bind("<Escape>"):
            pop.bind("<Escape>", lambda e: self._escape_backs_out())
        # ...and that binding could never fire. These popups are borderless
        # and take no keyboard focus, so Tk delivers a keypress to whatever
        # DOES hold it — the app window, which had no Escape binding at all
        # while a popup was open. Measured: with the focus forced inside the
        # popup the binding above closes it at once, so the handler was
        # always sound and the key simply went elsewhere.
        #
        # Bound here the way _themed_dialog binds its own, and bound ONCE:
        # a nested dropdown is placed through this same method while the
        # host's binding is still live, and a second one would mean a
        # single Escape closing both levels.
        if getattr(self, "_mini_popup_escape_bind", None) is None:
            self._mini_popup_escape_bind = self.bind(
                "<Escape>", self._escape_backs_out, add="+")
        if enable_click_outside:
            self._bind_click_outside(pop)
        # *keyboard_from* is the opener of a popup placed at a point, not on
        # a widget: the calendar's day, its menu opened from the keyboard.
        opener = anchor_widget if anchor_widget is not None else keyboard_from
        if self._opened_from_keyboard(opener):
            self._keyboard_into_popup(pop, opener)

    def _place_mini_popup(self, pop, anchor_widget=None, anchor_xy=None,
                          keyboard_from=None):
        """Position a mini popup (inline rename, color palette, etc.) just
        below the anchor, flipping above and clamping within the app window's
        own bounds when needed — same safe logic as _place_dropdown_popup, so
        these popups can't run off a different monitor or off the window edge
        on a multi-monitor setup either."""
        self._place_dropdown_popup(pop, anchor_widget, anchor_xy=anchor_xy,
                                   keyboard_from=keyboard_from)

    def _maybe_dismiss_mini_popup(self, event):
        pop = getattr(self, "_mini_popup", None)
        if pop is None:
            return
        # If the click was inside the popup, keep it open.
        if self._is_inside_popup(getattr(event, "widget", None), pop):
            return
        self._dismiss_mini_popup_asking()

    def _dismiss_mini_popup_asking(self, holding_work_only=False):
        """Close the open popup the way a person closing it means it: one
        holding typed work -- the template editor -- asks first, through its
        _confirm_dismiss. Every close a PERSON makes comes through here: a
        click outside, Escape, a widget that opens something in its place,
        leaving the page it sits on, closing the window. Programmatic closes
        (after a save, an explicit Cancel) call _dismiss_mini_popup.

        Returns True when no popup is left open, False when it stays: the
        person chose to keep editing, or the save they asked for could not
        happen. With `holding_work_only`, a popup with nothing to lose is
        left alone rather than closed -- for callers that are not about
        popups at all (a shortcut, a Settings section, the window closing).

        A widget's own <Button-1> runs before the window's click-outside,
        so a widget opening something in the popup's place closed it
        without the question -- the template half written, gone. Such a
        widget calls this first, and on False returns "break": otherwise
        the window's click-outside, still to run for the same click, asks
        the same question a second time.
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
        """Is the OS foreground window one of this app's windows?

        The only honest witness: override-redirect popups can hold the
        activation without ever receiving <Activate>/<Deactivate>, so
        event-based detection missed exactly the case where the user had
        typed into a popup and then switched away. Off Windows there is
        no GetForegroundWindow; answer "ours" so nothing ever hides.
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
        """Escape, arriving at the app window, closes the innermost popup.

        It has to be the innermost, and that is the whole difficulty. A
        nested dropdown — a category list inside the template editor, say —
        is deliberately NOT `self._mini_popup`; the host popup is. So a
        handler that simply called `_dismiss_mini_popup()` would tear down
        the editor the list is sitting in, which is exactly the breakage
        recorded beside the per-popup binding in `_place_dropdown_popup`.
        One level at a time: the list first, its host only once the list is
        gone.

        No "break" returned, deliberately. `_themed_dialog` binds its own
        Escape on this same window, and breaking here would leave a modal
        dialog open while the popup underneath it closed — the wrong one
        answered. Widget-level Escapes (the find bar, an inline rename
        entry) already return "break" of their own, so they never reach
        this at all.

        And nothing at all while a question is on screen: its own Escape
        answers it. Closing the popup here too meant Escape on the template
        editor's "Save changes?" threw away the template it was asking
        about.
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
                # Force Tk to fully finish processing the destroy (and its
                # own OS-level repaint) right now, synchronously, instead of
                # letting it overlap with whatever runs next. A fixed-length
                # timer alone was a guess at "enough time" that didn't always
                # hold; this actually waits for the pending work to drain.
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
        # Run any deferred work now that the popup is actually closing — e.g.
        # a full note-list/calendar rebuild, which is heavy enough to cause a
        # visible flicker if it runs WHILE a popup is open on top of it (this
        # is a list, not a single slot, so several independent features can
        # each defer their own work without overwriting one another).
        #
        # Scheduled via after() — on top of the update_idletasks() above —
        # rather than called immediately: running a heavy rebuild in the very
        # same call stack as destroying the popup Toplevel still caused a
        # visible tear even after settling the destroy first. Giving the
        # event loop one more full cycle before the rebuild starts keeps the
        # two from ever overlapping into a single glitchy frame.
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
        # Counted so a popup closing can tell a click's keyboard from one
        # Windows moved for it (_keyboard_back).
        self._pointer_presses = 0
        self.bind_all("<ButtonPress>", self._count_pointer_press, add="+")

    def _count_pointer_press(self, _event=None):
        self._pointer_presses = getattr(self, "_pointer_presses", 0) + 1

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

    def _ring_round(self, widget, rest):
        """The keyboard's ring as *widget*'s one-pixel border, drawn in
        *rest* -- the colour around it -- while the keyboard is elsewhere."""
        widget._ring_rest = rest
        widget.configure(highlightthickness=1, highlightbackground=rest,
                         highlightcolor=self._focus_ring())
        return widget

    def _ring_shown(self, widget, on):
        """Both border colours, as the keyboard comes and goes: Windows draws
        no focus colour round a label, only its resting one."""
        rest = getattr(widget, "_ring_rest", None)
        if rest is None:
            return
        try:
            widget.configure(highlightbackground=self._focus_ring() if on else rest)
        except tk.TclError:
            pass

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
        place = self._place_of(widget)
        press()
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
    def _place_of(widget):
        """Where *widget* stands: its path and its place among its siblings,
        then its parent's, up to its window -- enough to find what stands
        there once a list or a page has been drawn again."""
        place = []
        w = widget
        try:
            while w is not None and not isinstance(w, (tk.Tk, tk.Toplevel)):
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
        being taken down -- rather than somewhere a person put it."""
        try:
            now = str(self.tk.call("focus"))
            if now not in ("", ".") and not (
                    gone and (now == gone or now.startswith(gone + "."))):
                return self.nametowidget(now).winfo_exists() == 0
        except KeyError:
            return True
        except tk.TclError:
            return False
        return True

    def _keyboard_stays(self, widget, place):
        """After a press from the keyboard: a press that drew its list or
        page again took the control with it, and the keyboard fell to the
        window. It goes to what stands in that control's place now."""
        try:
            if widget.winfo_exists():
                return
        except tk.TclError:
            pass
        if not self._keyboard_nowhere():
            return
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
        return sorted(found, key=lambda w: (w.winfo_rooty(), w.winfo_rootx()))

    @staticmethod
    def _centre_of(w):
        return (w.winfo_rootx() + w.winfo_width() / 2,
                w.winfo_rooty() + w.winfo_height() / 2)

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
        """A popup opened from the keyboard takes it, on its current choice,
        else its first, else its first control -- unless it has already
        placed it -- and hands it back to *opener* when it closes."""
        try:
            if str(self.tk.call("focus", "-lastfor", pop)) == str(pop):
                choices = self._walk_choices(pop, drawn=False)
                current = [c for c in choices if getattr(c, "_key_current", False)]
                target = (current or choices or [pop.tk_focusNext()])[0]
                if target is not None:
                    target.focus_set()
        except (tk.TclError, KeyError):
            return
        path, place = str(pop), self._place_of(opener)
        clicks = getattr(self, "_pointer_presses", 0)
        pop.bind("<Destroy>", lambda e: (self._keyboard_back(path, place, clicks)
                                         if str(e.widget) == path else None),
                 add="+")

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

    def _bring_into_sight(self, widget):
        """Scroll each canvas holding *widget* on a page just far enough to
        show it, innermost first: the editor, Settings and its menu, and the
        Trash, Share and emoji lists are frames drawn on canvases."""
        try:
            child = widget
            while child is not None and not isinstance(child, (tk.Tk, tk.Toplevel)):
                parent = child.master
                if (isinstance(parent, tk.Canvas) and isinstance(child, tk.Frame)
                        and child.winfo_manager() == "canvas"):
                    self._show_on_canvas(parent, child, widget)
                child = parent
        except (tk.TclError, AttributeError, ValueError, TypeError):
            pass

    @staticmethod
    def _canvas_window_item(canvas, child):
        for item in canvas.find_all():
            if (canvas.type(item) == "window"
                    and str(canvas.itemcget(item, "window")) == str(child)):
                return item
        return None

    def _offset_within(self, widget, page, axis):
        """How far *widget* lies from *page*'s top (axis "y") or left edge.
        A canvas on the way is crossed by its scroll, which it updates at
        once; the windows on it move only when it next draws."""
        total, w = 0.0, widget
        while w is not None and w is not page:
            parent = w.master
            item = (self._canvas_window_item(parent, w)
                    if isinstance(parent, tk.Canvas)
                    and w.winfo_manager() == "canvas" else None)
            if item is not None:
                shown = parent.canvasy(0) if axis == "y" else parent.canvasx(0)
                total += parent.bbox(item)[1 if axis == "y" else 0] - shown
            else:
                total += w.winfo_y() if axis == "y" else w.winfo_x()
            w = parent
        return total

    def _show_on_canvas(self, canvas, page, widget):
        """Scroll *canvas*, which draws *page*, until *widget* is inside its
        view with a small margin -- the least movement that shows it."""
        item = self._canvas_window_item(canvas, page)
        if item is None:
            return
        box = canvas.bbox(item)
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
