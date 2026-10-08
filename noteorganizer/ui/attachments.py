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
from ..core.model import MAX_ATTACHMENTS
from ..core.storage import _attachment_path_within, _delete_attachment_files


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
                    icon="warning", default="no"):
                return
            if asked_about != (getattr(self, "selected_note_id", None),
                               self.current_attachments):
                return
            filepaths = filepaths[:room]
        added_any = False
        for src_path in filepaths:
            original_name = os.path.basename(src_path)
            unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{original_name}"
            dest_path = os.path.join(paths.ATTACHMENTS_DIR, unique_name)
            try:
                shutil.copy2(src_path, dest_path)
            except (IOError, OSError) as e:
                self.show_error("Couldn't attach file", f"Failed to attach '{original_name}':\n{e}")
                continue
            self.current_attachments.append({"filename": original_name, "stored_as": unique_name})
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
                f"Remove “{target.get('filename', 'this file')}” from the "
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
        _delete_attachment_files([{"attachments": [removed]}])
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

            original_name = attachment.get("filename", stored_as)
            # The safety decision keys off the REAL on-disk file's
            # extension (stored_as preserves the original extension — see
            # add_attachment), NOT the display filename a crafted note
            # controls separately, so a ".exe" masquerading as "doc.pdf"
            # can't skip the warning. Trailing dots/spaces come off first,
            # because Windows strips them when it OPENS a path: to
            # splitext, "invoice.lnk. " has no extension at all, while
            # os.startfile on that same string executes invoice.lnk —
            # normalize_note already stores clean names, and this repeats
            # the rstrip at the sink so the two can never disagree even
            # for a record that predates that rule.
            ext = os.path.splitext(stored_as.rstrip(". "))[1].lower()

            # Pillow decodes all of these — shown large, right in the app,
            # instead of handing off to whatever image viewer Windows has
            # associated with the file type. Anything else still opens
            # externally below.
            if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
                self._show_image_preview(path, original_name)
                return

            # Warn before opening anything Windows would execute as a program
            # or script — opening it runs code, not just views a file.
            if ext in self.DANGEROUS_EXTENSIONS:
                proceed = self.ask_yes_no(
                    "⚠ Potentially unsafe file",
                    f"“{original_name}” is a type of file that can run programs "
                    "or commands on your computer.\n\n"
                    "Only open it if you completely trust where it came from. "
                    "Opening an unsafe file can harm your computer.\n\n"
                    "Open it anyway?",
                    icon="warning", default="no"
                )
                if not proceed:
                    return

            try:
                os.startfile(path)  # Windows-only, matches this app's target platform
            except (AttributeError, OSError):
                self.show_info("Can't open automatically", f"File is located at:\n{path}")

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

        def _scaled(frame):
            w, h = frame.size
            if w > target_w or h > target_h:
                frame = frame.copy()
                frame.thumbnail((target_w, target_h), Image.LANCZOS)
            elif w > 0 and h > 0 and w < target_w * 0.6 and h < target_h * 0.6:
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
                pil_img = Image.open(path)
            except Exception:
                self.show_warning("Can't preview this file",
                                 "This file couldn't be read as an image.")
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
                # Pillow composites disposal-method-aware frames onto the
                # right canvas internally as you seek — converting to RGBA
                # here is what actually captures that composited result,
                # not just this frame's own raw (possibly partial) pixels.
                frames = [ImageTk.PhotoImage(_scaled(pil_img.convert("RGBA")))]
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
        tk.Button(header, text="✕ Close", command=self._dismiss_mini_popup,
                  relief="flat", cursor="hand2", bg=self.colors["card"],
                  fg=self.colors["text"], font=("Segoe UI", 9)
                  ).pack(side="right", ipadx=6, ipady=2)
        tk.Button(header, text="Open externally",
                  command=lambda: (self._dismiss_mini_popup(), self._open_externally(path)),
                  relief="flat", cursor="hand2", bg=self.colors["accent"],
                  fg="white", font=("Segoe UI", 9)
                  ).pack(side="right", padx=(0, 6), ipadx=6, ipady=2)

        img_lbl = tk.Label(overlay, image=frames[0], bg=self.colors["bg"])
        img_lbl.pack(padx=16, pady=(4, 16))

        self._gif_anim_job = None  # explicit even for the single-frame case,
        # so this attribute always exists after this function runs, not just
        # when an animation actually starts — any code checking it directly
        # (rather than via getattr with a default) can rely on that.
        if source is not None or len(frames) > 1:
            state = {"i": 0}

            def _next_frame():
                if not img_lbl.winfo_exists():
                    return
                nxt = state["i"] + 1
                if nxt >= len(frames) and self._preview_source is source \
                        and source is not None:
                    # First time round: this frame is not decoded yet. In
                    # order, one per tick, because Pillow composites each
                    # frame onto the one before as it seeks.
                    try:
                        source.seek(nxt)
                        frames.append(ImageTk.PhotoImage(
                            _scaled(source.convert("RGBA"))))
                        delays.append(source.info.get("duration", 100) or 100)
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
                elif nxt >= len(frames):
                    nxt = 0
                state["i"] = nxt
                img_lbl.configure(image=frames[nxt])
                self._gif_anim_job = self.after(delays[nxt], _next_frame)

            self._gif_anim_job = self.after(delays[0], _next_frame)

        overlay.place(relx=0.5, rely=0.5, anchor="center")
        overlay.lift()
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

    def _open_externally(self, path):
        """Hand a file off to whatever program Windows has associated with
        it — the plain, no-preview fallback used for file types this app
        can't show inline itself."""
        try:
            os.startfile(path)
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
            display_name = att.get("filename") or att.get("stored_as") or ""
            ext = os.path.splitext(display_name)[1].lower()
            icon = "🖼️" if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp") else "📄"
            can_preview_inline = ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

            row = tk.Frame(self.attachments_frame, bg=self.colors["card"])
            row.pack(fill="x", pady=2)

            top_row = tk.Frame(row, bg=self.colors["card"])
            top_row.pack(fill="x")

            name_lbl = tk.Label(top_row, text=f"{icon} {display_name}", font=("Segoe UI", 9),
                                 anchor="w", cursor="hand2",
                                 bg=self.colors["card"], fg=self.colors["text"])
            name_lbl.pack(side="left", fill="x", expand=True, padx=8, pady=4)
            name_lbl.bind("<Button-1>", lambda e, idx=i: self.open_attachment(idx))

            remove_btn = tk.Button(
                top_row, text="✕", command=lambda idx=i: self.remove_attachment(idx),
                relief="flat", font=("Segoe UI", 8), cursor="hand2", width=2,
                bg=self.colors["danger"], fg="white"
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
