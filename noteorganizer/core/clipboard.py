"""Reading and writing the richer clipboard formats Windows keeps.

WHY THIS EXISTS
---------------
Tkinter's ``clipboard_get`` only ever returns plain text. Windows holds
several formats at once -- copying from a browser puts ``CF_HTML``
alongside the plain text -- and reaching those is the difference between a
paste that keeps its bold and one that does not.

It uses ``ctypes``, which is in the standard library, so this costs no new
dependency.

EVERYTHING HERE DEGRADES
------------------------
The app ships for Windows, but its tests run on Linux, and the clipboard
can be locked by another program at the moment we ask. So every function
returns None (or does nothing) rather than raising: a paste that cannot
find rich text falls back to plain text, which is exactly what the app did
before any of this existed. Nothing here is allowed to take the editor
down with it.
"""

import sys

_WINDOWS = sys.platform == "win32"

if _WINDOWS:                                   # pragma: no cover - platform
    import ctypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    # A HANDLE is pointer-sized. Left undeclared, ctypes truncates these to
    # a 32-bit int, and locking the truncated value reads address zero --
    # an access violation rather than a clean failure.
    _user32.GetClipboardData.restype = ctypes.c_void_p
    _kernel32.GlobalAlloc.restype = ctypes.c_void_p
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalSize.restype = ctypes.c_size_t

    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002

# The CF_HTML wrapper: a header of byte offsets, then the markup itself.
_HEADER = ("Version:0.9\r\n"
           "StartHTML:{:09d}\r\nEndHTML:{:09d}\r\n"
           "StartFragment:{:09d}\r\nEndFragment:{:09d}\r\n")
_START_MARK = "<!--StartFragment-->"
_END_MARK = "<!--EndFragment-->"


def available():
    """True if the rich clipboard formats can be reached at all."""
    return _WINDOWS


class _Clipboard:
    """Open the clipboard, and be certain it gets closed again.

    Leaving it open locks every other program out of it, so the close has
    to happen even when what runs in between fails.
    """

    def __enter__(self):
        if not _WINDOWS:
            return False
        # Another program can hold it briefly; a few attempts is enough,
        # and giving up quietly is better than blocking the editor.
        for _ in range(5):
            if _user32.OpenClipboard(0):
                self.open = True
                return True
        self.open = False
        return False

    def __exit__(self, *exc):
        if getattr(self, "open", False):
            _user32.CloseClipboard()
        return False                    # never swallow an exception


def _read_format(fmt):
    """The raw bytes of one clipboard format, or None."""
    handle = _user32.GetClipboardData(fmt)
    if not handle:
        return None
    pointer = _kernel32.GlobalLock(ctypes.c_void_p(handle))
    if not pointer:
        return None
    try:
        size = _kernel32.GlobalSize(ctypes.c_void_p(handle))
        return ctypes.string_at(pointer, size)
    finally:
        _kernel32.GlobalUnlock(ctypes.c_void_p(handle))


def read_html():
    """The HTML fragment on the clipboard, or None if there is not one.

    Only the fragment between the markers is returned -- the surrounding
    document is whatever the source application wrapped it in, and none of
    it is part of what was copied.
    """
    if not _WINDOWS:
        return None
    try:
        with _Clipboard() as ready:
            if not ready:
                return None
            fmt = _user32.RegisterClipboardFormatW("HTML Format")
            raw = _read_format(fmt) if fmt else None
        if not raw:
            return None
        text = raw.decode("utf-8", "replace").rstrip("\x00")
        start, end = text.find(_START_MARK), text.find(_END_MARK)
        if start != -1 and end != -1 and end > start:
            return text[start + len(_START_MARK):end]
        # Some applications omit the markers and give the whole document.
        body = text.lower().find("<body")
        return text[text.find(">", body) + 1:] if body != -1 else text
    except Exception:
        return None


def read_text():
    """The plain text on the clipboard, or None."""
    if not _WINDOWS:
        return None
    try:
        with _Clipboard() as ready:
            if not ready:
                return None
            raw = _read_format(CF_UNICODETEXT)
        if raw is None:
            return None
        return raw.decode("utf-16-le", "replace").split("\x00", 1)[0]
    except Exception:
        return None


def _wrap_html(fragment):
    """A fragment inside the CF_HTML header, as bytes.

    The offsets in that header are counted in **bytes**, not characters.
    Notes are full of bullets and dashes, so computing them on the string
    would put every offset out by the number of multi-byte characters
    before it, and the receiving application would take the wrong slice.
    """
    document = ("<html><body>" + _START_MARK + fragment + _END_MARK
                + "</body></html>")
    head_length = len(_HEADER.format(0, 0, 0, 0).encode("utf-8"))
    encoded = document.encode("utf-8")
    start_fragment = head_length + encoded.find(_START_MARK.encode()) + len(_START_MARK)
    end_fragment = head_length + encoded.find(_END_MARK.encode())
    header = _HEADER.format(head_length, head_length + len(encoded),
                            start_fragment, end_fragment)
    return header.encode("utf-8") + encoded


def _put(fmt, payload):
    handle = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        return False
    pointer = _kernel32.GlobalLock(ctypes.c_void_p(handle))
    if not pointer:
        return False
    ctypes.memmove(pointer, payload, len(payload))
    _kernel32.GlobalUnlock(ctypes.c_void_p(handle))
    # SetClipboardData takes ownership of the block -- it must not be freed
    # here, and must not be touched again afterwards.
    return bool(_user32.SetClipboardData(fmt, ctypes.c_void_p(handle)))


def write(text, html=None):
    """Put text on the clipboard, with an HTML version beside it.

    The plain text always goes on as well. An application that cannot read
    ``CF_HTML`` -- a terminal, a plain-text editor -- then still gets
    something sensible rather than markup.

    Returns True if the HTML made it on; False means the text may still
    have, which is the outcome the caller does not need to care about.
    """
    if not _WINDOWS:
        return False
    try:
        with _Clipboard() as ready:
            if not ready:
                return False
            _user32.EmptyClipboard()
            _put(CF_UNICODETEXT, (text or "").encode("utf-16-le") + bytes(2))
            if not html:
                return False
            fmt = _user32.RegisterClipboardFormatW("HTML Format")
            return bool(fmt) and _put(fmt, _wrap_html(html))
    except Exception:
        return False
