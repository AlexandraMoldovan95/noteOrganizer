"""The in-note calculator panel.

The collapsible calculator that sits beside the checklist in the note
editor: its buttons, display, history, and the "insert into note" action.

This is the *interface* only. The arithmetic itself lives in
:mod:`noteorganizer.core.calculator`, which knows nothing about windows and
is tested without one — this module turns button presses into calls on it
and puts the answer on screen.

Worth knowing while reading:

* ``_calc_press`` handles every button through one path, so a digit, an
  operator and "=" all go through the same validation.
* The display is editable, so an expression can be typed or pasted in as
  well as built by tapping. Both end up as plain text handed to
  ``evaluate_calculator_expression``, which is why there is no separate
  "typed input" path to keep in sync.
* ``insert into note`` writes the whole formula, not just the answer, and
  each insertion lands on its own line — see ``_calc_insert_into_note``.
* ``_sync_calculator_open_state`` is called whenever the open note changes,
  so the panel resets rather than carrying one note's working into another.
"""

import tkinter as tk
from tkinter import ttk

from ..core.calculator import (
    evaluate_calculator_expression,
    format_calculator_result,
)


class CalculatorPanelMixin:
    """Calculator panel behaviour for :class:`NoteOrganizer`.

    Not usable on its own — it reads ``self.colors``, ``self.body_text`` and
    other state owned by the app, and is only ever mixed into it.
    """

    def toggle_calculator_section(self):
        """Show or hide the in-note calculator panel."""
        if self._calculator_open:
            self.calculator_section.pack_forget()
            self._calculator_open = False
            self.calculator_btn.config(text="🧮 Calculator")
        else:
            # No padx here — this and the button both live inside a column
            # Frame (see build_notes_tab) that already carries the outer
            # margin, now that Checklist and Calculator sit side by side.
            self.calculator_section.pack(fill="x", pady=(0, 8),
                                         after=self.calculator_btn)
            self._calculator_open = True
            self.calculator_btn.config(text="🧮 Calculator  ▲")
            # Ready to paste into immediately, no extra click needed.
            self.calculator_display.focus_set()

    def _build_calculator_section(self):
        """Build the (initially hidden) in-note calculator: an editable
        expression display (buttons, typing, or pasting all feed the same
        field) plus a compact keypad, an optional row of extra functions,
        and a collapsible history of this session's calculations. Purely
        a computation tool — nothing here is persisted on the note (no
        new note field, no share-code/export changes); it starts empty
        every time it's opened. Built once per editor (like the checklist
        section above), not rebuilt on every note switch."""
        sec = self.calculator_section
        head = tk.Frame(sec, bg=self.colors["card"])
        head.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(head, text="Calculator", bg=self.colors["card"],
                 fg=self.colors["subtext"], font=("Segoe UI", 9, "bold"),
                 anchor="w").pack(side="left")
        tk.Button(head, text="✕ Close", command=self.toggle_calculator_section,
                  relief="flat", cursor="hand2", bg=self.colors["card"],
                  fg=self.colors["subtext"], font=("Segoe UI", 8, "bold"), bd=0
                  ).pack(side="right")

        self._calc_display_var = tk.StringVar(value="")
        self._calc_just_evaluated = False
        self._calc_last_full_expr = ""
        self._calc_history = []

        self.calculator_display = tk.Entry(
            sec, textvariable=self._calc_display_var, relief="flat",
            font=("Consolas", 14), justify="right",
            bg=self.colors["sidebar"], fg=self.colors["text"],
            insertbackground=self.colors["text"])
        self.track_theme(self.calculator_display, bg="sidebar", fg="text",
                         insertbackground="text")
        self.calculator_display.pack(fill="x", padx=10, pady=(0, 4), ipady=8)
        # Right-click Cut/Copy/Paste, same as every other text field in the
        # app — plus a normal Ctrl+V/<<Paste>> binding below, so pasting an
        # expression copied from somewhere else just works either way.
        # (No Return-triggers-"=" binding: it would only fire reliably when
        # this exact field has keyboard focus, which isn't guaranteed after
        # a sequence of button clicks — the "=" button already covers this
        # without that fragility.)
        self._add_paste_menu(self.calculator_display)
        self.calculator_display.bind("<KeyRelease>", self._calc_on_direct_edit)
        self.calculator_display.bind("<<Paste>>", self._calc_on_direct_edit)

        grid = tk.Frame(sec, bg=self.colors["card"])
        grid.pack(fill="x", padx=10, pady=(0, 2))
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1)

        rows = [
            ["(", ")", "C", "⌫"],
            ["7", "8", "9", "÷"],
            ["4", "5", "6", "×"],
            ["1", "2", "3", "−"],
            ["0", ".", "=", "+"],
        ]
        for r, row in enumerate(rows):
            for c, label in enumerate(row):
                is_op = label in ("÷", "×", "−", "+", "=")
                btn = tk.Button(
                    grid, text=label, relief="flat", cursor="hand2",
                    font=("Segoe UI", 10, "bold"),
                    command=lambda t=label: self._calc_press(t))
                if is_op:
                    self.track_theme(btn, bg="accent")
                    btn.configure(fg="white")
                else:
                    self.track_theme(btn, bg="sidebar", fg="text")
                btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1, ipady=3)

        # --- Extra functions: extra bracket styles, √, a general power
        # operator '^' (e.g. "3^4" for 3 to the 4th, not just a fixed
        # square), and % — collapsed by default so the everyday keypad
        # above stays the main focus. ---
        self._calc_more_open = False
        self.calculator_more_btn = tk.Button(
            sec, text="More functions  ▾", command=self._toggle_calc_more,
            relief="flat", cursor="hand2", font=("Segoe UI", 8, "bold"))
        self.track_theme(self.calculator_more_btn, bg="card", fg="subtext")
        self.calculator_more_btn.pack(fill="x", padx=10, pady=(0, 2))

        self.calculator_more_frame = tk.Frame(sec, bg=self.colors["card"])
        self.track_theme(self.calculator_more_frame, bg="card")
        # Not packed yet — toggled open by the button above.
        for col in range(4):
            self.calculator_more_frame.grid_columnconfigure(col, weight=1)
        more_rows = [["√", "^", "%", "{"], ["}", "[", "]", ""]]
        for r, row in enumerate(more_rows):
            for c, label in enumerate(row):
                if not label:
                    continue
                btn = tk.Button(
                    self.calculator_more_frame, text=label, relief="flat",
                    cursor="hand2", font=("Segoe UI", 10, "bold"),
                    command=lambda t=label: self._calc_press(t))
                self.track_theme(btn, bg="sidebar", fg="text")
                btn.grid(row=r, column=c, sticky="nsew", padx=1, pady=1, ipady=3)

        self.calculator_insert_btn = tk.Button(
            sec, text="⬇ Insert into note", command=self._calc_insert_into_note,
            relief="flat", cursor="hand2", font=("Segoe UI", 9, "bold"),
            state="disabled", disabledforeground=self.colors["subtext"])
        self.track_theme(self.calculator_insert_btn, bg="sidebar", fg="text")
        self.calculator_insert_btn.pack(fill="x", padx=10, pady=(2, 8), ipady=4)

        # --- History: this session's past calculations, newest first.
        # Collapsed by default, like the extra-functions row — a toggle
        # button reveals it rather than it always taking up space. Not
        # persisted anywhere — clears with the rest of the calculator on
        # note switch, same as the expression itself. Each entry is
        # clickable to insert that specific formula into the note (the
        # same "own line, right after the last insertion" placement the
        # main Insert button uses), so an earlier result is still one
        # click away without having to recompute it. ---
        self._calc_history_open = False
        self.calculator_history_head = hist_head = tk.Frame(sec, bg=self.colors["card"])
        hist_head.pack(fill="x", padx=10, pady=(0, 0))
        self.calculator_history_btn = tk.Button(
            hist_head, text="History  ▾", command=self._toggle_calc_history,
            relief="flat", cursor="hand2", font=("Segoe UI", 8, "bold"),
            bg=self.colors["card"], fg=self.colors["subtext"], bd=0, anchor="w")
        self.track_theme(self.calculator_history_btn, bg="card", fg="subtext")
        self.calculator_history_btn.pack(side="left")
        self.calculator_history_clear_btn = tk.Button(
            hist_head, text="Clear", command=self._calc_clear_history,
            relief="flat", cursor="hand2", font=("Segoe UI", 8), bd=0)
        self.track_theme(self.calculator_history_clear_btn, bg="card", fg="subtext")
        self.calculator_history_clear_btn.pack(side="right")

        self.calculator_history_section = tk.Frame(sec, bg=self.colors["card"])
        self.track_theme(self.calculator_history_section, bg="card")
        # Not packed yet — toggled open by the button above.
        hist_wrap = tk.Frame(self.calculator_history_section, bg=self.colors["card"], height=90)
        hist_wrap.pack(fill="x", pady=(2, 8))
        hist_wrap.pack_propagate(False)
        hist_canvas = tk.Canvas(hist_wrap, bg=self.colors["card"], highlightthickness=0)
        hist_sb = ttk.Scrollbar(hist_wrap, orient="vertical", command=hist_canvas.yview)
        self.calculator_history_frame = tk.Frame(hist_canvas, bg=self.colors["card"])
        self.calculator_history_frame.bind(
            "<Configure>", lambda e: hist_canvas.configure(scrollregion=hist_canvas.bbox("all")))
        hist_cwin = hist_canvas.create_window((0, 0), window=self.calculator_history_frame, anchor="nw")
        hist_canvas.bind("<Configure>", self._canvas_width_sync(hist_canvas, hist_cwin))
        hist_canvas.configure(yscrollcommand=hist_sb.set)
        hist_sb.pack(side="right", fill="y")
        hist_canvas.pack(side="left", fill="both", expand=True)
        self._bind_wheel_tree(self.calculator_history_frame,
                              lambda e: self._panel_or_page_wheel(hist_canvas, e))
        self._calc_render_history()

    def _toggle_calc_more(self):
        """Show or hide the extra-functions row (brackets, √, ^, %)."""
        if self._calc_more_open:
            self.calculator_more_frame.pack_forget()
            self._calc_more_open = False
            self.calculator_more_btn.config(text="More functions  ▾")
        else:
            self.calculator_more_frame.pack(fill="x", padx=10, pady=(0, 4),
                                            after=self.calculator_more_btn)
            self._calc_more_open = True
            self.calculator_more_btn.config(text="More functions  ▴")

    def _toggle_calc_history(self):
        """Show or hide the calculation history — collapsed by default so
        it doesn't take up space until actually wanted."""
        if self._calc_history_open:
            self.calculator_history_section.pack_forget()
            self._calc_history_open = False
            self.calculator_history_btn.config(text="History  ▾")
        else:
            self.calculator_history_section.pack(
                fill="x", padx=10, after=self.calculator_history_head)
            self._calc_history_open = True
            self.calculator_history_btn.config(text="History  ▲")

    def _calc_clear_history(self):
        """Wipe this session's calculation history — the current
        expression/result on display is untouched, only the log below it."""
        self._calc_history = []
        self._calc_render_history()

    def _calc_on_direct_edit(self, event=None):
        """Fired when the user types or pastes directly into the display
        instead of using the buttons. Treated like any manual text edit:
        no auto-clearing, and Insert stays unavailable until a fresh "="
        produces a real result from whatever's now in the field."""
        self._calc_just_evaluated = False
        self._calc_refresh_insert_state()

    def _calc_press(self, token):
        """Handle one calculator button press. Reads and writes the same
        editable display field a user could also type or paste into
        directly — see evaluate_calculator_expression() for the actual
        math."""
        current = self._calc_display_var.get()
        if token == "C":
            current = ""
            self._calc_just_evaluated = False
        elif token == "⌫":
            current = "" if self._calc_just_evaluated else current[:-1]
            self._calc_just_evaluated = False
        elif token == "=":
            if current and current != "Error":
                result = evaluate_calculator_expression(current)
                if result is not None:
                    formatted = format_calculator_result(result)
                    self._calc_last_full_expr = current
                    self._calc_history.insert(0, f"{current}={formatted}")
                    self._calc_render_history()
                    current = formatted
                    self._calc_just_evaluated = True
                else:
                    current = "Error"
                    self._calc_just_evaluated = False
        elif token in ("+", "−", "×", "÷", "^", "%"):
            # Binary (+−×÷^) and postfix (%) operators all continue
            # chaining off a just-computed result instead of clearing it.
            if current == "Error":
                current = ""
            self._calc_just_evaluated = False
            current += token
        else:  # a digit, ".", "√", or a bracket — starts a fresh entry
            if self._calc_just_evaluated or current == "Error":
                current = ""
                self._calc_just_evaluated = False
            current += token
        self._calc_display_var.set(current)
        # Button presses set the StringVar programmatically, which doesn't
        # move the Entry's own cursor the way normal typing would — without
        # this, the cursor can end up stuck mid-text instead of following
        # what was just "typed" via the button.
        self.calculator_display.icursor(tk.END)
        self._calc_refresh_insert_state()

    def _calc_refresh_insert_state(self):
        """Insert-into-note is only ever active right after '=' produced
        a real result — never for an in-progress expression or an error,
        so there's nothing meaningful to insert until then."""
        if not hasattr(self, "calculator_insert_btn"):
            return
        current = self._calc_display_var.get()
        enabled = self._calc_just_evaluated and bool(current) and current != "Error"
        self.calculator_insert_btn.config(state=("normal" if enabled else "disabled"))

    def _calc_render_history(self):
        if not hasattr(self, "calculator_history_frame"):
            return
        for w in self.calculator_history_frame.winfo_children():
            w.destroy()
        if not self._calc_history:
            tk.Label(self.calculator_history_frame, text="No calculations yet.",
                     bg=self.colors["card"], fg=self.colors["subtext"],
                     font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=6, pady=4)
            return
        for entry in self._calc_history:
            lbl = tk.Label(self.calculator_history_frame, text=entry,
                           bg=self.colors["card"], fg=self.colors["subtext"],
                           font=("Consolas", 9), anchor="e", justify="right",
                           cursor="hand2")
            lbl.pack(fill="x", padx=6, pady=2)
            lbl.bind("<Button-1>", lambda e, formula=entry: self._calc_insert_formula(formula))

    def _calc_insert_formula(self, formula):
        """Shared insertion logic: type `formula` into the note body,
        landing on a fresh line right after the previous calculator
        insertion (tracked via a Text mark), so repeated use — whether
        from the main Insert button or clicking a history entry — builds
        a clean log downward instead of gluing results onto wherever the
        cursor happens to be sitting."""
        # With a table cell open, the result belongs in the cell -- the
        # insert used to land beside the table, where the caret guard had
        # parked the body cursor.
        editor = getattr(self, "_cell_editor", None)
        if editor is not None:
            try:
                # The cell editor is a Text now: inserting at the caret
                # leaves the caret after what landed, no icursor needed.
                editor["entry"].insert("insert", formula)
            except tk.TclError:
                pass
            self._schedule_autosave(skip_word_count=True)
            return
        has_prior = "calc_insert_end" in self.body_text.mark_names()
        if self.focus_get() is not self.body_text:
            self.body_text.focus_set()
        if has_prior:
            self.body_text.mark_set(tk.INSERT, "calc_insert_end")
            self.body_text.insert(tk.INSERT, "\n" + formula)
        else:
            self.body_text.insert(tk.INSERT, formula)
        self.body_text.mark_set("calc_insert_end", tk.INSERT)
        self._schedule_autosave(skip_word_count=True)

    def _calc_insert_into_note(self):
        """Insert the full formula just computed ("expr=result") into the
        note body — only reachable right after a successful "=" (the
        button is disabled otherwise)."""
        if not self._calc_just_evaluated:
            return
        result = self._calc_display_var.get()
        if not result or result == "Error" or not self._calc_last_full_expr:
            return
        self._calc_insert_formula(f"{self._calc_last_full_expr}={result}")

    def _sync_calculator_open_state(self):
        """Collapse and fully reset the calculator on note switch — it's a
        transient tool, not part of any note's saved content, so carrying
        a half-finished sum, history, or insertion point over from a
        previous note would be confusing rather than useful."""
        if getattr(self, "_calculator_open", False):
            self.calculator_section.pack_forget()
            self._calculator_open = False
        if getattr(self, "_calc_more_open", False):
            self.calculator_more_frame.pack_forget()
            self._calc_more_open = False
            if hasattr(self, "calculator_more_btn"):
                self.calculator_more_btn.config(text="More functions  ▾")
        if getattr(self, "_calc_history_open", False):
            self.calculator_history_section.pack_forget()
            self._calc_history_open = False
            if hasattr(self, "calculator_history_btn"):
                self.calculator_history_btn.config(text="History  ▾")
        if hasattr(self, "_calc_display_var"):
            self._calc_display_var.set("")
        self._calc_just_evaluated = False
        self._calc_last_full_expr = ""
        self._calc_history = []
        self._calc_render_history()
        if hasattr(self, "calculator_btn"):
            self.calculator_btn.config(text="🧮 Calculator")
        self._calc_refresh_insert_state()
        if "calc_insert_end" in self.body_text.mark_names():
            self.body_text.mark_unset("calc_insert_end")
