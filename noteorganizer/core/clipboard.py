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

import re
import sys
from html.parser import HTMLParser

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
    it is part of what was copied -- save the table or list the markers sit
    in, which is (fragment_of).
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
        return fragment_of(raw.decode("utf-8", "replace").rstrip("\x00"))
    except Exception:
        return None


# The elements whose absence changes what a fragment's text means: a cell
# outside a row, a row outside a table, an item outside its list.
_STRUCTURE = ("table", "tr", "td", "th", "ul", "ol")
# A row or cell begun ends the open one of its kind, as HTML has it.
_ENDS = {"tr": ("tr", "td", "th"), "td": ("td", "th"), "th": ("td", "th")}


class _OpenAtMarker(HTMLParser):
    """The structural elements still open where a document's text ends."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open = []
        # How many of each tag are open: asked of the list itself, every
        # stray end tag walked it whole, and 30,000 unclosed tables with as
        # many stray </td> took seconds to read.
        self.how_many = dict.fromkeys(_STRUCTURE, 0)

    def handle_starttag(self, tag, attrs):
        if tag not in _STRUCTURE:
            return
        while self.open and self.open[-1] in _ENDS.get(tag, ()):
            self.how_many[self.open.pop()] -= 1
        self.open.append(tag)
        self.how_many[tag] += 1

    def handle_endtag(self, tag):
        if self.how_many.get(tag):
            while True:
                closed = self.open.pop()
                self.how_many[closed] -= 1
                if closed == tag:
                    break


def fragment_of(document):
    """The fragment a CF_HTML *document* marks, inside the structure its
    markers sit in.

    Excel puts the markers inside the table: around the rows, and for one
    row around its cells -- so the fragment alone was cells with no row, and
    a row copied from Excel pasted as loose text (2026-10-25). The table,
    row, cell or list open at the start marker is opened again around the
    fragment and closed after it. Formatting open there is left out: only
    structure changes what the text is.
    """
    start, end = document.find(_START_MARK), document.find(_END_MARK)
    if start == -1 or end == -1 or end <= start:
        # Some applications omit the markers and give the whole document.
        # Found where it is: lower() makes two characters of "İ", and an
        # offset in the lowered copy fell past the tag in this one (round 10).
        found = re.search("<body", document, re.IGNORECASE)
        return (document[document.find(">", found.start()) + 1:] if found
                else document)
    fragment = document[start + len(_START_MARK):end]
    reader = _OpenAtMarker()
    try:
        reader.feed(document[:start])
    except Exception:
        return fragment
    return ("".join("<%s>" % tag for tag in reader.open) + fragment
            + "".join("</%s>" % tag for tag in reversed(reader.open)))


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
