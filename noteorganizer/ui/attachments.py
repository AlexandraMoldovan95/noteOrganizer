"""Files attached to a note, and previewing them: adding and removing, the
list under the editor, and the in-app preview -- animated GIFs among them,
which is why Pillow is the app's one runtime dependency. Grouped by the call
graph (67% of these methods' calls are to each other; ARCHITECTURE).

A note in the Trash keeps its files, for a restore to bring back. Deleting
for good, and removing one attachment, go through _delete_attachment_files,
which spares a file another note or Trash entry still names (ISSUES_LOG:
"Files that outlived the notes they belonged to"). What a mixin is, and the
two rules that keep them working: :mod:`noteorganizer.ui`.
"""

import os
import shutil
import tkinter as tk
from collections import OrderedDict
from tkinter import ttk, filedialog
from datetime import datetime

from PIL import Image, ImageTk

from ..core import paths
from ..core.model import (MAX_ATTACHMENTS, attachment_display_name,
                          file_type_of, how_to_open)
from ..core.storage import (_attachment_path_within, _delete_attachment_files,
                            attachment_names_in)
from .calendar_view import _fit_title
from .dialogs import one_line


def _name_and_type(display_name):
    """*display_name* as (the name, its type) -- "Holiday photo", ".rdp" --
    or (display_name, "") when it shows no type. Cut by length from the end,
    never by an index found in a lower-cased copy: "İ" lower-cases to two
    characters, and each one moved the cut a letter into the type."""
    kind = file_type_of(display_name)
    cut = len(display_name.rstrip(". ")) - len(kind)
    if kind and cut > 0 and display_name[cut:cut + len(kind)].lower() == kind:
        return display_name[:cut], display_name[cut:]
    return display_name, ""


def _quoted(display_name):
    """An attachment's name as a question quotes it: one line, and a long
    name cut before its type, which always shows -- a backup's label of
    60,000 letters made the question taller than X can draw."""
    stem, kind = _name_and_type(display_name)
    return one_line(stem, 100) + kind


class AttachmentsMixin:
    """Attachment handling for :class:`NoteOrganizer`.

    Not usable on its own -- every method reads state owned by the app
    (``self.notes``, ``self.colors``, ``self.attachments_frame``).
    """

    def add_attachment(self):
        filepaths = self._while_native(
            lambda: filedialog.askopenfilenames(title="Choose file(s) to attach"))
        if not filepaths:
            return
        # normalize_note enforces MAX_ATTACHMENTS by truncating -- right for
        # a share code, wrong for a person's own files, which went at the
        # next load. Refused here instead, and said.
        room = MAX_ATTACHMENTS - len(self.current_attachments)
        if room <= 0:
            self.show_warning(
                "That's as many files as one note can hold",
                f"A note can keep {MAX_ATTACHMENTS} attached files. Remove "
                "one to add another, or split this into two notes.")
            return
        if len(filepaths) > room:
            # The note the question is about, held across the answer: the
            # editor can move on while a question waits, and the files
            # would then land in whichever note is open by then.
            asked_about = (self.selected_note_id, self.current_attachments)
            if not self.ask_yes_no(
                    "More files than this note can hold",
                    f"A note can keep {MAX_ATTACHMENTS} attached files, and "
                    f"there is room for {room} more.\n\n"
                    f"Attach the first {room} and leave the rest?",
                    icon="question", default="no"):
                return
            if asked_about != (self.selected_note_id, self.current_attachments):
                return
            filepaths = filepaths[:room]
        added_any = False
        for src_path in filepaths:
            original_name = os.path.basename(src_path)
            # No colon in a stored name, which the resolver refuses as a
            # stream (_attachment_path_within): only Linux allows one here.
            unique_name = (f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_"
                           f"{original_name.replace(':', '_')}")
            # Shown as every other route shows it, so the save's
            # normalize_note finds nothing to change.
            shown = attachment_display_name(original_name, unique_name)
            dest_path = os.path.join(paths.ATTACHMENTS_DIR, unique_name)
            try:
                shutil.copy2(src_path, dest_path)
            except (IOError, OSError) as e:
                self.show_error("Couldn't attach file", f"Failed to attach '{shown}':\n{e}")
                continue
            self.current_attachments.append({"filename": shown, "stored_as": unique_name})
            added_any = True
        self.refresh_attachments_list()
        if added_any:
            self._schedule_autosave()

    def remove_attachment(self, index):
        if not (0 <= index < len(self.current_attachments)):
            return
        target = self.current_attachments[index]
        files = self.current_attachments
        # Deletes the STORED FILE for good: asked as every irreversible step
        # is -- the warning glyph, No chosen, Escape backs out.
        if not self.ask_yes_no(
                "Remove attachment",
                f"Remove “{_quoted(attachment_display_name(target.get('filename'), target.get('stored_as'))) or 'this file'}” from the "
                "note?\n\nThe stored copy is deleted with it — this can't "
                "be undone.",
                icon="warning", default="no"):
            return
        # The file found again: under the question the editor can move on,
        # and the index named another note's file. Moved on (its list rebuilt),
        # nothing goes -- a new note's first save is no move.
        if self.current_attachments is not files:
            return
        note_id = self.selected_note_id
        stored = target.get("stored_as")
        index = next((i for i, a in enumerate(self.current_attachments)
                      if a is target
                      or (stored and a.get("stored_as") == stored)), None)
        if index is None:
            return
        removed = self.current_attachments.pop(index)
        # A preview still reading it holds it open, and Windows deletes no
        # open file: the record went and the file stayed for good.
        source = getattr(self, "_preview_source", None)
        held = _attachment_path_within(stored) if stored else None
        if source is not None and held and os.path.normcase(os.path.abspath(
                str(getattr(source, "filename", "")))) == os.path.normcase(held):
            self._release_preview_source()
        # Spared if another note, a Trash entry or this note again names it;
        # this note's saved copy is left out, as it names the file until
        # the autosave below.
        others = [n for n in self.notes
                  if not (isinstance(n, dict) and n.get("id") == note_id)]
        _delete_attachment_files(
            [{"attachments": [removed]}],
            spare=attachment_names_in(
                others + list(self.trash)
                + [{"attachments": self.current_attachments}]))
        self.refresh_attachments_list()
        self._schedule_autosave()

    def open_attachment(self, index):
        if 0 <= index < len(self.current_attachments):
            attachment = self.current_attachments[index]
            # The delete side's containment guard: a crafted stored_as must
            # never let startfile open -- or RUN -- a file outside the folder.
            stored_as = attachment.get("stored_as")
            path = _attachment_path_within(stored_as) if stored_as else None
            if path is None or not os.path.isfile(path):
                self.show_warning("File missing", "This attached file can't be found on disk.")
                return

            # The name the question quotes ends in the type of the file
            # that opens, whatever label the record carries.
            original_name = attachment_display_name(attachment.get("filename"), stored_as)
            # Decided by the REAL file on disk, read as Windows reads a type
            # ("invoice.lnk. " runs invoice.lnk), never the label a note sets:
            # a picture is previewed here, anything else asks at the one gate.
            if how_to_open(os.path.basename(path)) == "preview":
                self._show_image_preview(path, original_name)
                return
            self._open_externally(path, original_name)

    def _show_image_preview(self, path, filename):
        """The preview, or nothing: one that fails half built -- its file
        kept open, its overlay never placed, as every animated PNG's did --
        is taken down before the error is reported, so no file stays held
        and no hidden popup is left for Escape to look for."""
        try:
            self._build_image_preview(path, filename)
        except Exception:
            self._dismiss_mini_popup()
            raise

    @staticmethod
    def _frame_delay(info):
        """A frame's time on screen in whole milliseconds, as Tk's after()
        takes it: Pillow gives an animated PNG's as a float (40.0), and
        after() refuses anything but an integer. None, junk or 10 ms and
        less is 100, as browsers play them: a frame of 0.6 ms ticked every
        millisecond, half a core while the preview was open."""
        try:
            delay = int(round(float(info.get("duration") or 0)))
        except (TypeError, ValueError, OverflowError):
            delay = 0
        return delay if delay > 10 else 100

    def _build_image_preview(self, path, filename):
        """A large in-app image preview, most of the window. Pillow, not Tk:
        Tk decodes only PNG and GIF, and drew a GIF's partial frames without
        compositing them, so the image jumped every frame. The first frame
        shows at once and the rest decode as the animation reaches them (a
        60-frame GIF waited 1.25 s); a JPEG decodes at the size shown; a
        preview seen before comes from memory (_cached_preview)."""
        self.update_idletasks()
        target_w = max(int(self.winfo_width() * 0.7), 200)
        target_h = max(int(self.winfo_height() * 0.7), 200)
        cache_key = self._preview_cache_key(path, target_w, target_h)
        cached = self._cached_preview(cache_key)

        def _scaled(frame, grow=True):
            w, h = frame.size
            if w > target_w or h > target_h:
                frame = frame.copy()
                frame.thumbnail((target_w, target_h), Image.LANCZOS)
            elif grow and w > 0 and h > 0 and w < target_w * 0.6 and h < target_h * 0.6:
                # A small image grows to be easy to see -- at most eightfold.
                scale = min(min(target_w / w, target_h / h), 8)
                frame = frame.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                                     Image.LANCZOS)
            return frame

        # The file the animation's later frames are still being read from;
        # None for a still image or a preview that came from memory.
        source = None
        if cached is not None:
            frames, delays = list(cached[0]), list(cached[1])
        else:
            try:
                # Pillow knows a file by its contents: a ".png" could be an
                # EPS handed to Ghostscript. Only the preview's decoders read.
                pil_img = Image.open(path, formats=self.PREVIEW_DECODERS)
            except Exception:
                # Not a picture the preview reads -- a scanner's TIFF saved
                # as .jpg -- or no picture at all: offered to Windows, not
                # called unreadable with no way to open it.
                self._cannot_preview(path)
                return
            try:
                animated = bool(getattr(pil_img, "is_animated", False))
                if not animated:
                    # draft(): a JPEG decodes at the smallest of 1/2, 1/4, 1/8
                    # still as big as the preview (others ignore it).
                    pil_img.draft(pil_img.mode, (target_w, target_h))
                w, h = pil_img.size
                if w * h > self.PREVIEW_PIXEL_BUDGET:
                    # A 439 KB PNG decoded to 12000x12000 peaked at 1.7 GB;
                    # left to the program Windows opens it with.
                    pil_img.close()
                    self._too_big_to_preview(path)
                    return
                if not animated and (w > target_w or h > target_h):
                    pil_img.thumbnail((target_w, target_h), Image.LANCZOS)
                # Converted to RGBA, the frame is Pillow's composited one,
                # not its raw, possibly partial, pixels.
                frames = [ImageTk.PhotoImage(
                    _scaled(pil_img.convert("RGBA"), grow=not animated))]
                delays = [self._frame_delay(pil_img.info) if animated else 100]
            except Exception:
                # One that opens and fails to decode (truncated, say) is the
                # same news as one that never opened.
                pil_img.close()
                self.show_warning("Can't preview this file",
                                 "This file couldn't be read as an image.")
                return
            if animated:
                source = pil_img
            else:
                pil_img.close()
                self._remember_preview(cache_key, frames, delays)

        self._dismiss_mini_popup()
        # After the dismiss, which closes whatever file the PREVIOUS
        # preview was still reading from.
        self._preview_source = source
        # Both border colours: Tk draws highlightcolor while the keyboard
        # is on one of the overlay's buttons.
        overlay = tk.Frame(self, bg=self.colors["bg"], highlightthickness=1,
                           highlightbackground=self.colors["accent"],
                           highlightcolor=self.colors["accent"])
        self._image_preview_ref = frames  # keep alive — see refresh_attachments_list
        self._mini_popup = overlay

        header = tk.Frame(overlay, bg=self.colors["bg"])
        header.pack(fill="x", padx=12, pady=(10, 4))
        # The overlay is as wide as what it holds: a long name drawn whole
        # made it wider than the window, Close past its edge. Cut to a room
        # no wider than the picture may be, beside the two buttons.
        name_font = self._cal_font(("Segoe UI", 10, "bold"))[0]
        name_lbl = tk.Label(header, font=name_font, anchor="w",
                            bg=self.colors["bg"], fg=self.colors["text"],
                            text=self._fit_name(filename, name_font, max(
                                self.px(120), target_w - self.px(220))))
        close_btn = tk.Button(header, text="✕ Close", command=self._dismiss_mini_popup,
                              relief="flat", cursor="hand2", bg=self.colors["card"],
                              fg=self.colors["text"], font=("Segoe UI", 9))
        close_btn.pack(side="right", ipadx=6, ipady=2)
        open_btn = tk.Button(
            header, text="Open externally",
            command=lambda: (self._dismiss_mini_popup(), self._open_externally(path)),
            relief="flat", cursor="hand2", bg=self.colors["accent"],
            fg=self._on_fill("accent"), font=("Segoe UI", 9))
        open_btn.pack(side="right", padx=(0, 6), ipadx=6, ipady=2)
        name_lbl.pack(side="left", fill="x", expand=True)   # after the buttons

        img_lbl = tk.Label(overlay, image=frames[0], bg=self.colors["bg"])
        img_lbl.pack(padx=16, pady=(4, 16))

        self._gif_anim_job = None  # explicit even for the single-frame case,
        # so this attribute always exists after this function runs, not just
        # when an animation actually starts — any code checking it directly
        # (rather than via getattr with a default) can rely on that.
        if source is not None or len(frames) > 1:
            # What the frames kept hold, and the canvas pixels decoded so far:
            # counted as each frame comes, not summed again on every tick.
            state = {"i": 0,
                     "held": sum(f.width() * f.height() * 4 for f in frames),
                     "decoded": (source.size[0] * source.size[1]
                                 if source is not None else 0)}

            def _next_frame():
                if not img_lbl.winfo_exists():
                    return
                nxt = state["i"] + 1
                if nxt >= len(frames) and self._preview_source is source \
                        and source is not None and (
                            state["held"] > self.PREVIEW_MEMORY_BYTES
                            or len(frames) >= self.PREVIEW_MAX_FRAMES):
                    # Kept frames past what the cache may hold: a 33 KB GIF
                    # ran the app out of memory. It plays the part that fits.
                    self._release_preview_source()
                    nxt = 0
                elif nxt >= len(frames) and self._preview_source is source \
                        and source is not None:
                    # First time round: this frame is not decoded yet. In
                    # order, one per tick, because Pillow composites each
                    # frame onto the one before as it seeks.
                    try:
                        source.seek(nxt)
                        # Judged before it decodes (a later frame can be any
                        # size), and with the frames before it, as each is
                        # composited onto the whole canvas.
                        canvas_px = source.size[0] * source.size[1]
                        past_budget = (
                            canvas_px > self.PREVIEW_PIXEL_BUDGET
                            or state["decoded"] + canvas_px
                            > self.ANIMATION_PIXEL_BUDGET)
                        if not past_budget:
                            shown = ImageTk.PhotoImage(
                                _scaled(source.convert("RGBA"), grow=False))
                            frames.append(shown)
                            delays.append(self._frame_delay(source.info))
                            state["decoded"] += canvas_px
                            state["held"] += shown.width() * shown.height() * 4
                    except EOFError:
                        # The last frame seen: it plays from memory now, and
                        # the next opening of this file too.
                        self._release_preview_source()
                        self._remember_preview(cache_key, frames, delays)
                        nxt = 0
                    except Exception:
                        # A frame that will not decode ends the animation
                        # there, playing what it has.
                        self._release_preview_source()
                        nxt = 0
                    else:
                        if past_budget:
                            # A frame past the budget ends it the same way
                            # (ISSUES_LOG: "The preview that kept every frame").
                            self._release_preview_source()
                            nxt = 0
                elif nxt >= len(frames):
                    nxt = 0
                state["i"] = nxt
                img_lbl.configure(image=frames[nxt])
                self._gif_anim_job = self.after(delays[nxt], _next_frame)

            self._gif_anim_job = self.after(delays[0], _next_frame)

        overlay.place(relx=0.5, rely=0.5, anchor="center")
        overlay.lift()
        # Escape closes it, as it closes every popup.
        if getattr(self, "_mini_popup_escape_bind", None) is None:
            self._mini_popup_escape_bind = self.bind(
                "<Escape>", self._escape_backs_out, add="+")
        # On Close however it was opened, and back on the way out: a frame
        # over the window, not a window, so a click left the caret in the
        # note under it and Tab walked there -- keys edited a hidden note.
        opener = getattr(self, "_key_pressing", None)
        if opener is None:
            try:
                opener = self.nametowidget(
                    str(self.tk.call("focus", "-lastfor", self)))
            except (KeyError, tk.TclError):
                opener = None
        self.update_idletasks()            # placed now, so it can take it
        close_btn.focus_set()
        buttons = (close_btn, open_btn)

        def cycle(button, step):
            buttons[(buttons.index(button) + step) % len(buttons)].focus_set()
            return "break"

        # Tab and Shift+Tab walk its two buttons round (<<PrevWindow>>: X11's
        # ISO_Left_Tab); Enter presses the one holding the keyboard, pressed
        # not held -- held, it closed the preview and reopened it.
        for b in buttons:
            b.bind("<Tab>", lambda e, b=b: cycle(b, 1))
            for seq in ("<Shift-Tab>", "<<PrevWindow>>"):
                b.bind(seq, lambda e, b=b: cycle(b, -1))
            for seq in ("<Return>", "<KP_Enter>"):
                b.bind(seq, lambda e, b=b: (
                    None if self._enter_repeats(e) else b.invoke(), "break")[1])
        if opener is not None and opener is not self:
            # Not named *path*: Open externally's command reads the picture's
            # path when pressed, and it opened the overlay's name instead.
            shown_at, place = str(overlay), self._place_of(opener)
            clicks = getattr(self, "_pointer_presses", 0)
            overlay.bind("<Destroy>", lambda e: (
                self._keyboard_back(shown_at, place, clicks)
                if str(e.widget) == shown_at else None), add="+")
        # A click outside closes it, bound after a moment so the opening click
        # is not one -- and only while THIS preview is open: closed sooner, a
        # handler nothing took off was left on the window.
        def _bind_click_outside():
            if not self._still_alive():
                return
            if getattr(self, "_mini_popup", None) is not overlay:
                return
            self._bind_click_outside(overlay)
        self.after(50, _bind_click_outside)

    # Decoded previews kept for reopening, in bytes (four to a pixel): a
    # photo at preview size is about 2 MB; one larger than all is not kept.
    PREVIEW_MEMORY_BYTES = 64 * 1024 * 1024
    # The largest image decoded, in pixels, asked of every frame before it
    # decodes: past it, the program Windows opens images with shows it.
    PREVIEW_PIXEL_BUDGET = 50_000_000
    # One animation's canvas pixels, all frames together: a wide canvas shown
    # as a thin strip never fills the memory above. 4K still plays 24 frames.
    ANIMATION_PIXEL_BUDGET = 4 * PREVIEW_PIXEL_BUDGET
    # And the frames kept: one of a single pixel still costs Tk an image.
    PREVIEW_MAX_FRAMES = 1_000
    # The only decoders the preview lets Pillow use: those of the pictures
    # it shows (PREVIEWED_IN_APP). A JPEG holding several pictures (MPO)
    # comes through the JPEG decoder, and its frames are judged one by one.
    PREVIEW_DECODERS = ("PNG", "JPEG", "GIF", "BMP", "WEBP")

    def _cannot_preview(self, path):
        """Offer a file the preview's decoders do not read to the program
        Windows opens its kind with, as one too large to show is offered."""
        if self.ask_yes_no(
                "Can't preview this file",
                "Note Organizer can't show this file itself. Open it in the "
                "program your computer uses for it?", icon="question",
                default="yes"):
            self._open_externally(path)

    def _too_big_to_preview(self, path):
        """Offer the image to the program Windows opens it with, rather
        than decode it whole here."""
        if self.ask_yes_no(
                "Too large to preview",
                "This image is too large to show here. Open it in the program "
                "your computer uses for images?", icon="question", default="yes"):
            self._open_externally(path)

    @staticmethod
    def _preview_cache_key(path, width, height):
        """What a remembered preview is good for: this file exactly as it
        is now -- its size and its last change, so a file replaced under
        the same name is read again -- shown at this size."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        return (os.path.normcase(os.path.abspath(path)), st.st_mtime_ns,
                st.st_size, width, height)

    def _cached_preview(self, key):
        """(frames, delays) of a preview seen before, or None."""
        cache = getattr(self, "_preview_cache", None)
        if key is None or not cache or key not in cache:
            return None
        cache.move_to_end(key)
        frames, delays, _size = cache[key]
        return frames, delays

    def _remember_preview(self, key, frames, delays):
        """Keep a finished preview for next time, forgetting the least
        recently shown ones once the total passes PREVIEW_MEMORY_BYTES."""
        if key is None:
            return
        size = sum(f.width() * f.height() * 4 for f in frames)
        if size > self.PREVIEW_MEMORY_BYTES:
            return
        cache = getattr(self, "_preview_cache", None)
        if cache is None:
            cache = self._preview_cache = OrderedDict()
        cache[key] = (tuple(frames), tuple(delays), size)
        cache.move_to_end(key)
        total = sum(entry[2] for entry in cache.values())
        while total > self.PREVIEW_MEMORY_BYTES and len(cache) > 1:
            _key, forgotten = cache.popitem(last=False)
            total -= forgotten[2]

    def _release_preview_source(self):
        """Close the file an animation was still decoding frames from --
        open while it first plays, and Windows deletes no open file. Closed
        at the last frame, or when the preview goes before that."""
        source = getattr(self, "_preview_source", None)
        self._preview_source = None
        if source is not None:
            try:
                source.close()
            except Exception:
                pass

    def _open_externally(self, path, shown=None):
        """Hand a file to whatever program Windows has for its kind -- the
        one way an attachment leaves the app, so the one place that asks: a
        kind that only shows opens at once, one that runs code asks with the
        warning, any other calmly, as no list of dangerous kinds is complete
        (how_to_open). *shown* is the name the question quotes."""
        shown = _quoted(shown or os.path.basename(path))
        kind = how_to_open(os.path.basename(path))
        if kind == "warn":
            if not self.ask_yes_no(
                    "⚠ Potentially unsafe file",
                    f"“{shown}” is a type of file that can run programs "
                    "or commands on your computer.\n\n"
                    "Only open it if you completely trust where it came from. "
                    "Opening an unsafe file can harm your computer.\n\n"
                    "Open it anyway?",
                    icon="warning", default="no"):
                return
        elif kind == "ask":
            # Cancel first: Escape answers it, and Enter lands on it.
            if not self._themed_dialog(
                    "Open this file?",
                    "Note Organizer doesn't know this kind of file, so it "
                    f"can't tell you whether “{shown}” is safe to open.\n\n"
                    "Windows will open it with whatever app it has for files "
                    "like this. Only open it if you trust where it came from.",
                    kind="question",
                    buttons=[("Cancel", False), ("Open", True)],
                    default="Cancel"):
                return
        try:
            os.startfile(path)  # Windows-only, matches this app's target platform
        except (AttributeError, OSError):
            self.show_info("Can't open automatically", f"File is located at:\n{path}")

    def refresh_attachments_list(self):
        # Plain colours, not track_theme(): rebuilt at every note switch, it
        # takes the theme fresh (ARCHITECTURE, the two theming patterns).
        for widget in self.attachments_frame.winfo_children():
            widget.destroy()

        if not self.current_attachments:
            empty_lbl = tk.Label(self.attachments_frame, text="No files attached.",
                                  font=("Segoe UI", 8), anchor="w",
                                  bg=self.colors["bg"], fg=self.colors["subtext"])
            empty_lbl.pack(fill="x")
            return

        for i, att in enumerate(self.current_attachments):
            # .get, not [ ]: this runs mid load_note, where a KeyError left the
            # previous note's checklist to be saved onto this one. Name, icon
            # and hint from the file that opens, not a backup's label.
            display_name = attachment_display_name(att.get("filename"), att.get("stored_as"))
            can_preview_inline = how_to_open(
                att.get("stored_as") or display_name) == "preview"
            icon = "🖼" if can_preview_inline else "📄"

            row = tk.Frame(self.attachments_frame, bg=self.colors["card"])
            row.pack(fill="x", pady=2)

            top_row = tk.Frame(row, bg=self.colors["card"])
            top_row.pack(fill="x")

            name_lbl = tk.Label(top_row, font=("Segoe UI", 9),
                                 anchor="w", cursor="hand2",
                                 bg=self.colors["card"], fg=self.colors["text"])
            # A Tab stop that Space and Return open, as a click does: the ✕
            # beside it was all the keyboard could reach. Its ring rests in
            # its own fill, a pixel taken from the padding round it.
            self._ring_round(name_lbl)
            # The type always shows: a long name gives way before it, not at
            # the row's edge, where blank-looking characters hid ".rdp". Ringed
            # first: the fit reads the border it leaves room for.
            stem, kind = _name_and_type(display_name)
            _fit_title(self, name_lbl, f"{icon} ", stem, kind,
                       self._measuring_font(("Segoe UI", 9)))
            name_lbl.bind("<Button-1>", lambda e, idx=i: self.open_attachment(idx))
            self._pressable(name_lbl, lambda idx=i: self.open_attachment(idx))

            remove_btn = tk.Button(
                top_row, text="✕", command=lambda idx=i: self.remove_attachment(idx),
                relief="flat", font=("Segoe UI", 8), cursor="hand2", width=2,
                bg=self.colors["danger"], fg=self._on_fill("danger")
            )
            remove_btn.pack(side="right", padx=4, pady=2)
            # Packed after the ✕, so a long name cannot squeeze it out of the
            # row; made before it, so Tab still reaches the name first.
            name_lbl.pack(side="left", fill="x", expand=True, padx=7, pady=3)

            if not can_preview_inline:
                # Said generically: which program opens it varies by computer.
                hint_lbl = tk.Label(row, text="Opens in your default app for this file type",
                                    font=("Segoe UI", 7), anchor="w",
                                    bg=self.colors["card"], fg=self.colors["subtext"])
                hint_lbl.pack(fill="x", padx=(28, 8), pady=(0, 4))
