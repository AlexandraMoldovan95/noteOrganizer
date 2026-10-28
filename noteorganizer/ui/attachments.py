"""Files attached to a note, and previewing them.

WHAT THIS IS FOR
----------------
Adding and removing attachments, the list shown under the editor, and the
in-app preview -- including animated GIFs, which is why Pillow is the
app's one runtime dependency.

WHY THESE BELONG TOGETHER
-------------------------
Chosen from the call graph: 67% of the calls these methods make are to
each other, the highest of any remaining group once dialogs and the
calendar had moved out. That number rose from 38% when the dialogs left,
which is the useful part -- much of what looked like outside traffic was
this group asking for a confirmation box.

DELETING A FILE IS NOT THE SAME AS REMOVING A REFERENCE
-------------------------------------------------------
Removing an attachment from a note removes the *reference*. Whether the
file on disk goes too depends on where the note is heading: a note moved
to the trash keeps its files, because restoring it has to restore them
as well. Only the permanent-deletion paths call
``_delete_attachment_files``. See ``docs/ISSUES_LOG.md``, "The
attachments that were never deleted".

See :mod:`noteorganizer.ui` for what a mixin is and the two rules that
keep them working.
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
                          how_to_open)
from ..core.storage import (_attachment_path_within, _delete_attachment_files,
                            attachment_names_in)


class AttachmentsMixin:
    """Attachment handling for :class:`NoteOrganizer`.

    Not usable on its own -- every method reads state owned by the app
    (``self.notes``, ``self.colors``, ``self.attachments_frame``).
    """

    def add_attachment(self):
        filepaths = filedialog.askopenfilenames(title="Choose file(s) to attach")
        if not filepaths:
            return
        # The ceiling exists because a note carrying thousands of
        # attachment records is a way to make the app unopenable (see
        # MAX_ATTACHMENTS) -- but normalize_note enforces it by
        # TRUNCATING, which is right for a hostile share code and wrong
        # for a person adding their own files: they would be copied to
        # disk, shown in the list, and then silently dropped on the next
        # load. Refuse here instead, and say so.
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
            asked_about = (getattr(self, "selected_note_id", None),
                           self.current_attachments)
            if not self.ask_yes_no(
                    "More files than this note can hold",
                    f"A note can keep {MAX_ATTACHMENTS} attached files, and "
                    f"there is room for {room} more.\n\n"
                    f"Attach the first {room} and leave the rest?",
                    icon="question", default="no"):
                return
            if asked_about != (getattr(self, "selected_note_id", None),
                               self.current_attachments):
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
        note_id = getattr(self, "selected_note_id", None)
        # This deletes the STORED FILE, permanently — the one destructive
        # gesture the audit's confirm sweep missed (it bypassed the
        # dialogs entirely, so no sweep of ask_yes_no callers could see
        # it). Same contract as every irreversible confirm: warning
        # glyph, No pre-selected, Escape backs out.
        if not self.ask_yes_no(
                "Remove attachment",
                f"Remove “{attachment_display_name(target.get('filename'), target.get('stored_as')) or 'this file'}” from the "
                "note?\n\nThe stored copy is deleted with it — this can't "
                "be undone.",
                icon="warning", default="no"):
            return
        # The file asked about, found again: while the question waited the
        # editor could move on to another note, and the index would then
        # name ANOTHER attachment -- of another note -- whose stored file
        # this deletes for good. Gone or moved on means nothing is removed.
        if getattr(self, "selected_note_id", None) != note_id:
            return
        stored = target.get("stored_as")
        index = next((i for i, a in enumerate(self.current_attachments)
                      if a is target
                      or (stored and a.get("stored_as") == stored)), None)
        if index is None:
            return
        removed = self.current_attachments.pop(index)
        # Not a file another note or a Trash entry still shows -- a
        # duplicate or an import that could not copy it kept its name --
        # nor one this note lists twice. This note's own saved copy is left
        # out: it names the file until the autosave below, and would spare
        # it for ever.
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
            # Resolve through the same containment guard the delete side
            # uses: a crafted stored_as ("../../x", "C:\\...", UNC) must
            # never let os.startfile open — and possibly EXECUTE — a file
            # outside the attachments folder. None => refuse.
            stored_as = attachment.get("stored_as")
            path = _attachment_path_within(stored_as) if stored_as else None
            if path is None or not os.path.isfile(path):
                self.show_warning("File missing", "This attached file can't be found on disk.")
                return

            # The name the question quotes ends in the type of the file
            # that opens, whatever label the record carries.
            original_name = attachment_display_name(attachment.get("filename"), stored_as)
            # Every decision keys off the REAL on-disk file -- the path the
            # resolver reached, which is the one startfile opens -- never the
            # display filename a crafted note controls separately, so a ".exe"
            # masquerading as "doc.pdf" can't skip the question. how_to_open
            # reads the type as Windows does, trailing dots and spaces off
            # ("invoice.lnk. " executes invoice.lnk).
            # Pillow decodes the pictures — shown large, right in the app,
            # instead of handing off to whatever image viewer Windows has
            # associated with the file type. Anything else opens externally,
            # through the one gate that asks.
            if how_to_open(os.path.basename(path)) == "preview":
                self._show_image_preview(path, original_name)
                return
            self._open_externally(path, original_name)

    def _show_image_preview(self, path, filename):
        """A large, in-app image preview — most of the window, not a tiny
        thumbnail and not handed off to an external program. Uses Pillow
        (not plain Tk) for two reasons: plain Tk only decodes PNG/GIF, and
        for animated GIFs it only ever shows each frame's own raw pixels at
        that frame's own size — many GIFs only store the part of the frame
        that CHANGED from the previous one, at whatever size that patch
        happens to be, relying on the viewer to composite it onto a fixed
        canvas in the right place. Plain Tk doesn't do that compositing, so
        the image visibly jumped and resized itself every frame. Pillow
        handles this correctly and gives real per-frame timing too, instead
        of a guessed fixed delay.

        Quick to appear, which it was not: every frame of an animation was
        decoded, composited and rescaled before the first was shown -- a
        second and a quarter of nothing for a 60-frame GIF, and again on
        every opening. Now the first frame is shown at once and the rest
        are decoded as the animation reaches them; a JPEG photo is decoded
        straight at the size it will be shown rather than at full size;
        and a preview already seen comes back from memory
        (_cached_preview) instead of from the file."""
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
                # Small image, room to spare — enlarge so it's actually easy
                # to see. Capped so a tiny icon doesn't get blown up absurdly
                # large just because the window happens to be big.
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
                # Pillow knows a file by what is in it, not by its name: a
                # ".png" could be a TIFF, an icon set, or an EPS that Pillow
                # hands to Ghostscript. Only the decoders of the pictures
                # the preview is for may read it.
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
                    # A JPEG can be decoded straight at a half, a quarter or
                    # an eighth of its size, and draft() asks for the
                    # smallest that is still at least as big as the preview
                    # -- _scaled() then fits it exactly, as before. Every
                    # other format ignores the request.
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
                # Pillow composites disposal-method-aware frames onto the
                # right canvas internally as you seek — converting to RGBA
                # here is what actually captures that composited result,
                # not just this frame's own raw (possibly partial) pixels.
                frames = [ImageTk.PhotoImage(
                    _scaled(pil_img.convert("RGBA"), grow=not animated))]
                delays = [(pil_img.info.get("duration", 100) or 100)
                          if animated else 100]
            except Exception:
                # A file that opens and then fails to decode -- truncated,
                # say -- is the same news to the user as one that never
                # opened at all.
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
        tk.Label(header, text=filename, font=("Segoe UI", 10, "bold"),
                 bg=self.colors["bg"], fg=self.colors["text"]).pack(side="left")
        close_btn = tk.Button(header, text="✕ Close", command=self._dismiss_mini_popup,
                              relief="flat", cursor="hand2", bg=self.colors["card"],
                              fg=self.colors["text"], font=("Segoe UI", 9))
        close_btn.pack(side="right", ipadx=6, ipady=2)
        tk.Button(header, text="Open externally",
                  command=lambda: (self._dismiss_mini_popup(), self._open_externally(path)),
                  relief="flat", cursor="hand2", bg=self.colors["accent"],
                  fg=self._on_fill("accent"), font=("Segoe UI", 9)
                  ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)

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
                        # Judged before it is decoded, as the first frame is:
                        # seeking reads a frame's size, not its pixels, and a
                        # later frame can be any size the file likes. Each
                        # frame is composited onto the whole canvas, so the
                        # animation's frames are judged together as well.
                        canvas_px = source.size[0] * source.size[1]
                        past_budget = (
                            canvas_px > self.PREVIEW_PIXEL_BUDGET
                            or state["decoded"] + canvas_px
                            > self.ANIMATION_PIXEL_BUDGET)
                        if not past_budget:
                            shown = ImageTk.PhotoImage(
                                _scaled(source.convert("RGBA"), grow=False))
                            frames.append(shown)
                            delays.append(source.info.get("duration", 100) or 100)
                            state["decoded"] += canvas_px
                            state["held"] += shown.width() * shown.height() * 4
                    except EOFError:
                        # The last frame has been seen: from here on the
                        # animation plays from memory, and so does the next
                        # opening of this file.
                        self._release_preview_source()
                        self._remember_preview(cache_key, frames, delays)
                        nxt = 0
                    except Exception:
                        # A frame that will not decode ends the animation
                        # where it is, playing what it has, rather than
                        # stopping the app.
                        self._release_preview_source()
                        nxt = 0
                    else:
                        if past_budget:
                            # A frame past the budget ends it the same way:
                            # a TIFF's 169-megapixel second page took 46 s and
                            # 2 GB, and a 105 KB GIF of one-pixel frames on a
                            # 50-megapixel canvas kept the app busy for
                            # minutes. ISSUES_LOG: "The preview that kept every frame".
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
        # Opened from the keyboard (Space or Return on the row), it takes the
        # keyboard on Close, and gives it back to the row when it goes.
        opener = getattr(self, "_key_pressing", None)
        if opener is not None:
            self.update_idletasks()        # placed now, so it can take it
            close_btn.focus_set()
            path, place = str(overlay), self._place_of(opener)
            clicks = getattr(self, "_pointer_presses", 0)
            overlay.bind("<Destroy>", lambda e: (
                self._keyboard_back(path, place, clicks)
                if str(e.widget) == path else None), add="+")
        # Click-outside-to-dismiss, matching every other in-app overlay —
        # bound on a short delay so the click that OPENED this preview isn't
        # also immediately seen as a click "outside" it. Bound for THIS
        # preview and only while it is still the one open: closed within
        # the delay, it used to bind anyway, a handler nothing would ever
        # take off again -- one more on the window per quick close.
        def _bind_click_outside():
            if not self._still_alive():
                return
            if getattr(self, "_mini_popup", None) is not overlay:
                return
            self._bind_click_outside(overlay)
        self.after(50, _bind_click_outside)

    # How much decoded preview is kept for reopening, in bytes of pixels
    # (four to a pixel). A photo at preview size is about two megabytes,
    # so this holds a good many; one long animation can fill it, and one
    # bigger than all of it is simply not kept.
    PREVIEW_MEMORY_BYTES = 64 * 1024 * 1024
    # The largest image decoded for a preview, in pixels: a 50-megapixel
    # photo still shows (a JPEG is decoded small anyway); past it, the
    # program Windows opens images with shows it instead. Asked of every
    # frame of an animation, before that frame is decoded.
    PREVIEW_PIXEL_BUDGET = 50_000_000
    # The canvas pixels decoded for one animation, all its frames together:
    # Pillow composites every frame onto the whole canvas, and a wide canvas
    # shown as a strip a few pixels tall never fills PREVIEW_MEMORY_BYTES.
    # A 4K animation still plays two dozen frames.
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
        """Close the file an animation was still decoding frames from.

        An animation is read a frame at a time, so its file stays open
        while it plays the first time round -- and an open file cannot be
        deleted or replaced on Windows. Closed when the last frame has
        been read, and when the preview goes away before that."""
        source = getattr(self, "_preview_source", None)
        self._preview_source = None
        if source is not None:
            try:
                source.close()
            except Exception:
                pass

    def _open_externally(self, path, shown=None):
        """Hand a file to whatever program Windows has for its kind -- the
        one way an attachment leaves the app, so the one place that asks.

        A kind whose usual app only shows it opens at once. A kind that
        runs code asks with the warning; any other kind asks calmly, since
        a list of dangerous kinds is never complete (how_to_open). *shown*
        is the name the question quotes, from attachment_display_name."""
        shown = shown or os.path.basename(path)
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
        # Direct .configure() calls, not self.track_theme(): this list is
        # destroyed and rebuilt on every note switch (load_note runs this
        # every single time you open a different note), so it always picks
        # up the current theme fresh anyway. Same leak as the note list and
        # calendar had — track_theme() never prunes entries for widgets that
        # get destroyed, so this ran up fast given how often switching notes
        # happens in a normal session.
        for widget in self.attachments_frame.winfo_children():
            widget.destroy()

        if not self.current_attachments:
            empty_lbl = tk.Label(self.attachments_frame, text="No files attached.",
                                  font=("Segoe UI", 8), anchor="w",
                                  bg=self.colors["bg"], fg=self.colors["subtext"])
            empty_lbl.pack(fill="x")
            return

        for i, att in enumerate(self.current_attachments):
            # .get, not [ ]: normalize_note now guarantees every stored
            # record carries string names, but this render runs mid
            # load_note — a KeyError here once aborted the load halfway
            # and left the editor holding the PREVIOUS note's checklist,
            # which the next save wrote onto the wrong note. A blank name
            # draws an odd row; a crash here corrupts data.
            # The name, the icon and the hint all from the file that opens,
            # as the click is: a label is whatever a backup wrote.
            display_name = attachment_display_name(att.get("filename"), att.get("stored_as"))
            can_preview_inline = how_to_open(
                att.get("stored_as") or display_name) == "preview"
            icon = "🖼" if can_preview_inline else "📄"

            row = tk.Frame(self.attachments_frame, bg=self.colors["card"])
            row.pack(fill="x", pady=2)

            top_row = tk.Frame(row, bg=self.colors["card"])
            top_row.pack(fill="x")

            name_lbl = tk.Label(top_row, text=f"{icon} {display_name}", font=("Segoe UI", 9),
                                 anchor="w", cursor="hand2",
                                 bg=self.colors["card"], fg=self.colors["text"])
            name_lbl.pack(side="left", fill="x", expand=True, padx=7, pady=3)
            name_lbl.bind("<Button-1>", lambda e, idx=i: self.open_attachment(idx))
            # A Tab stop that Space and Return open, as a click does: the ✕
            # beside it was all the keyboard could reach. Its ring rests in
            # its own fill, a pixel taken from the padding round it.
            self._ring_round(name_lbl)
            self._pressable(name_lbl, lambda idx=i: self.open_attachment(idx))

            remove_btn = tk.Button(
                top_row, text="✕", command=lambda idx=i: self.remove_attachment(idx),
                relief="flat", font=("Segoe UI", 8), cursor="hand2", width=2,
                bg=self.colors["danger"], fg=self._on_fill("danger")
            )
            remove_btn.pack(side="right", padx=4, pady=2)

            if not can_preview_inline:
                # Common image formats show large, right in the app (see
                # _show_image_preview) — everything else still opens in
                # whatever program the system has for that file type. Said
                # generically on purpose, since the app can't know for sure
                # which program that'll actually be (varies per computer).
                hint_lbl = tk.Label(row, text="Opens in your default app for this file type",
                                    font=("Segoe UI", 7), anchor="w",
                                    bg=self.colors["card"], fg=self.colors["subtext"])
                hint_lbl.pack(fill="x", padx=(28, 8), pady=(0, 4))
