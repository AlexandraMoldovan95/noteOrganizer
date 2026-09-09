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
        the first button's value (the safe/cancel choice) regardless."""
        if buttons is None:
            buttons = [("OK", True)]
        focus_index = self._dialog_focus_index(buttons, default)

        # The overlay lives INSIDE the main window, and a -topmost
        # popup floats above that -- so a question ABOUT the popup (save
        # your changes?) rendered underneath it, unreachable. The popups
        # step back for the dialog's duration and return after.
        stepped_back = self._popups_step_back()
        icon = {"info": "ℹ️", "warning": "⚠️", "error": "⛔",
                "question": "❓", "success": "✅"}.get(kind, "ℹ️")
        accent = {"error": self.colors["danger"], "warning": self.colors["danger"],
                  "success": self.colors["success"]}.get(kind, self.colors["accent"])

        result = {"value": None}
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
        card.pack(padx=2, pady=2)

        head = tk.Frame(card, bg=self.colors["card"])
        head.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(head, text=f"{icon}  {title}", bg=self.colors["card"],
                 fg=self.colors["text"], font=("Segoe UI", 12, "bold"),
                 anchor="w").pack(side="left")

        tk.Label(card, text=message, bg=self.colors["card"], fg=self.colors["subtext"],
                 font=("Segoe UI", 10), wraplength=380, justify="left", anchor="w"
                 ).pack(fill="x", padx=20, pady=(0, 16))

        btn_row = tk.Frame(card, bg=self.colors["card"])
        btn_row.pack(fill="x", padx=20, pady=(0, 16))

        def choose(val):
            result["value"] = val
            done.set(1)

        for i, spec in enumerate(buttons):
            label, value = spec[0], spec[1]
            color_key = spec[2] if len(spec) > 2 else None
            is_primary = (i == len(buttons) - 1)
            if color_key:
                btn_color = self.colors.get(color_key, self.colors["sidebar"])
                fg_color = "white"
            else:
                btn_color = accent if is_primary else self.colors["sidebar"]
                fg_color = "white" if is_primary else self.colors["text"]
            b = tk.Button(
                btn_row, text=label, command=lambda v=value: choose(v),
                relief="flat", cursor="hand2", font=("Segoe UI", 10, "bold"),
                bg=btn_color, fg=fg_color,
                activebackground=btn_color, activeforeground=fg_color)
            b.pack(side="right", padx=(8, 0), ipadx=12, ipady=4)
            if i == focus_index:
                b.focus_set()

        # Escape = the "safe" (first) value, usually cancel/no.
        safe_val = buttons[0][1] if len(buttons) > 1 else buttons[-1][1]
        esc_bind = self.bind("<Escape>", lambda e: choose(safe_val), add="+")

        # Modal, but the background stays fully visible (we don't cover it). A
        # local grab on the dialog frame routes input to the dialog only; because
        # this is an ordinary in-window Frame (not a borderless Toplevel), the
        # grab is safe and won't freeze the app.
        self.update_idletasks()
        try:
            border.grab_set()
        except tk.TclError:
            pass
        try:
            self.wait_variable(done)
        finally:
            try:
                border.grab_release()
            except tk.TclError:
                pass
            try:
                self.unbind("<Escape>", esc_bind)
            except tk.TclError:
                pass
            try:
                border.destroy()
            except tk.TclError:
                pass
            self._popups_step_forward(stepped_back)
        return result["value"]

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

    @staticmethod
    def _kind_from_kw(kw, fallback):
        """Callers use messagebox's vocabulary: an `icon=` naming the glyph
        ("warning"/"error"/"question"/"info"). Those names ARE our `kind`
        keys, so honour `icon=` (and an explicit `kind=`) instead of
        silently dropping it and always drawing the fallback glyph."""
        return kw.get("kind") or kw.get("icon") or fallback

    def show_info(self, title, message, **kw):
        return self._themed_dialog(title, message,
                                   kind=self._kind_from_kw(kw, "info"),
                                   buttons=[("OK", True)])

    def show_warning(self, title, message, **kw):
        return self._themed_dialog(title, message,
                                   kind=self._kind_from_kw(kw, "warning"),
                                   buttons=[("OK", True)])

    def show_error(self, title, message, **kw):
        return self._themed_dialog(title, message,
                                   kind=self._kind_from_kw(kw, "error"),
                                   buttons=[("OK", True)])

    def ask_yes_no(self, title, message, **kw):
        # `default=` (messagebox's word) names which button keyboard focus
        # lands on — pass default="no" on a destructive confirm so a
        # reflexive Enter doesn't fire "Yes".
        return self._themed_dialog(title, message,
                                   kind=self._kind_from_kw(kw, "question"),
                                   buttons=[("No", False), ("Yes", True)],
                                   default=kw.get("default"))

    def ask_yes_no_cancel(self, title, message, **kw):
        # Returns True (yes), False (no), or None (cancel) — matches messagebox.
        return self._themed_dialog(title, message,
                                   kind=self._kind_from_kw(kw, "question"),
                                   buttons=[("Cancel", None), ("No", False), ("Yes", True)],
                                   default=kw.get("default"))

    def _build_themed_dropdown(self, parent, var, options, on_change,
                               dot_color_fn=None, width_chars=14, nested=False):
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
        self.track_theme(btn, bg="sidebar")
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
                pop = tk.Toplevel(self)
                btn._nested_popup = pop
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
                self._dismiss_mini_popup()
                pop = tk.Toplevel(self)
                self._mini_popup = pop
                btn._dd_popup = pop
            pop.wm_overrideredirect(True)
            pop.configure(bg=self.colors["accent"])
            frame = tk.Frame(pop, bg=self.colors["card"], padx=4, pady=4)
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
                row.pack(fill="x", pady=1)
                widgets = [row]
                color = dot_color_fn(opt) if dot_color_fn else None
                if color:
                    dot = tk.Label(row, text="●", bg=row_bg, fg=color,
                                   font=("Segoe UI", 11), cursor="hand2")
                    dot.pack(side="left", padx=(10, 6), pady=4)
                    widgets.append(dot)
                lbl2 = tk.Label(row, text=opt, bg=row_bg,
                               fg=self.colors["accent"] if is_cur else self.colors["text"],
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
                    else:
                        self._dismiss_mini_popup()
                    on_change(v)

                for w in widgets:
                    w.bind("<Button-1>", lambda e, v=opt: pick(v))
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
        return btn

    def _place_dropdown_popup(self, pop, anchor_widget=None, anchor_xy=None,
                              enable_click_outside=True):
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
                if anchor_widget is not None:
                    anchor_widget.update_idletasks()
                    ax = anchor_widget.winfo_rootx()
                    ay = anchor_widget.winfo_rooty()
                    ah = anchor_widget.winfo_height()
                else:
                    ax, ay = anchor_xy
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
        # Cleaned up in _dismiss_mini_popup so it doesn't linger once closed.
        self._mini_popup_configure_bind = self.bind("<Configure>", throttled_reposition, add="+")
        pop.bind("<Escape>", lambda e: self._dismiss_mini_popup())
        if enable_click_outside:
            self._mini_popup_click_bind = self.bind(
                "<Button-1>", self._maybe_dismiss_mini_popup, add="+")
        else:
            self._mini_popup_click_bind = None

    def _place_mini_popup(self, pop, anchor_widget=None, anchor_xy=None):
        """Position a mini popup (inline rename, color palette, etc.) just
        below the anchor, flipping above and clamping within the app window's
        own bounds when needed — same safe logic as _place_dropdown_popup, so
        these popups can't run off a different monitor or off the window edge
        on a multi-monitor setup either."""
        self._place_dropdown_popup(pop, anchor_widget, anchor_xy=anchor_xy)

    def _maybe_dismiss_mini_popup(self, event):
        pop = getattr(self, "_mini_popup", None)
        if pop is None:
            return
        # If the click was inside the popup, keep it open.
        w = event.widget
        while w is not None:
            if w is pop:
                return
            try:
                w = w.master
            except AttributeError:
                break
        # A popup holding real work may want a word first: its
        # _confirm_dismiss returns False to stay open (or after having
        # handled the closing itself, e.g. by saving).
        confirm = getattr(pop, "_confirm_dismiss", None)
        if confirm is not None and not confirm():
            return
        self._dismiss_mini_popup()

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

    def _dismiss_mini_popup(self):
        gif_job = getattr(self, "_gif_anim_job", None)
        if gif_job is not None:
            try:
                self.after_cancel(gif_job)
            except (tk.TclError, ValueError):
                pass
            self._gif_anim_job = None
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
        bind_id = getattr(self, "_mini_popup_click_bind", None)
        if bind_id is not None:
            try:
                self.unbind("<Button-1>", bind_id)
            except tk.TclError:
                pass
            self._mini_popup_click_bind = None
        configure_bind_id = getattr(self, "_mini_popup_configure_bind", None)
        if configure_bind_id is not None:
            try:
                self.unbind("<Configure>", configure_bind_id)
            except tk.TclError:
                pass
            self._mini_popup_configure_bind = None
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
