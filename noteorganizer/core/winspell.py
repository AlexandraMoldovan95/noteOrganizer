"""Windows' own spell checker, reached through COM with ctypes.

Windows 8 and later check every language whose typing features are
installed: no dictionary ships, nothing new installs, no dependency. Kept
to the platform part -- a checker per language, the ranges it calls wrong,
suggestions, a word added; what the editor does is core/spelling.py.
Off Windows, with no dictionary, or when COM refuses, every function returns
an empty answer. Speller.add, the one call that writes, adds to the person's
Windows dictionary, only on "Add to Windows dictionary" -- never in a test.
"""

import sys

_WINDOWS = sys.platform == "win32"

if _WINDOWS:                                   # pragma: no cover - platform
    import ctypes
    import ctypes.wintypes as _wt

    _ole32 = ctypes.windll.ole32
    _kernel32 = ctypes.windll.kernel32
    _HRESULT = ctypes.c_long

    class _GUID(ctypes.Structure):
        _fields_ = [("a", _wt.DWORD), ("b", _wt.WORD), ("c", _wt.WORD),
                    ("d", ctypes.c_ubyte * 8)]

# The Spell Checking API's identities (spellcheck.h).
_CLSID_FACTORY = "{7AB36653-1796-484B-BDFA-E74F1DB7C1DC}"
_IID_FACTORY = "{8E018A9D-2415-4677-BF08-794EA61F94BB}"
# Slots in the interfaces' method tables, after IUnknown's three.
_FACTORY_LANGUAGES, _FACTORY_CREATE = 3, 5
_CHECKER_CHECK, _CHECKER_SUGGEST, _CHECKER_ADD = 4, 5, 6
_ENUM_NEXT = 3
_ERROR_START, _ERROR_LENGTH = 3, 4
_RELEASE = 2
# GetLocaleInfoEx: the language's name in English ("Romanian").
_LOCALE_SENGLISHLANGUAGENAME = 0x00001001

_state = {"factory": None, "tried": False, "spellers": {}}


def available():
    """True if Windows' spell checker could be reached at all."""
    return _factory() is not None


def _method(obj, index, *argtypes):
    """Method *index* of the COM object *obj*, ready to call."""
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    fn = ctypes.WINFUNCTYPE(_HRESULT, ctypes.c_void_p, *argtypes)(table[index])
    return lambda *args: fn(obj, *args)


def _release(obj):
    if obj:
        table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(table[_RELEASE])(obj)


def _guid(text):
    g = _GUID()
    if _ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g)) != 0:
        raise OSError("bad GUID " + text)
    return g


def _factory():
    """The checker factory, made once; None when there is none to be had."""
    if not _WINDOWS:
        return None
    if _state["tried"]:
        return _state["factory"]
    _state["tried"] = True
    try:
        # Apartment-threaded, as Tk's own thread is. Already initialised
        # either way is fine: the answer only says how.
        _ole32.CoInitializeEx(None, 2)
        factory = ctypes.c_void_p()
        hr = _ole32.CoCreateInstance(
            ctypes.byref(_guid(_CLSID_FACTORY)), None, 1,
            ctypes.byref(_guid(_IID_FACTORY)), ctypes.byref(factory))
        if hr == 0 and factory:
            _state["factory"] = factory
    except Exception:                          # noqa: BLE001 - degrade, never raise
        _state["factory"] = None
    return _state["factory"]


def _strings(enum):
    """Every string an IEnumString holds, which is then released."""
    out = []
    try:
        nxt = _method(enum, _ENUM_NEXT, ctypes.c_ulong,
                      ctypes.POINTER(ctypes.c_wchar_p), ctypes.POINTER(ctypes.c_ulong))
        while True:
            s, got = ctypes.c_wchar_p(), ctypes.c_ulong()
            if nxt(1, ctypes.byref(s), ctypes.byref(got)) != 0 or not got.value:
                break
            out.append(s.value or "")
            _ole32.CoTaskMemFree(s)
    finally:
        _release(enum)
    return out


def languages():
    """The language tags Windows can check here, as it lists them."""
    factory = _factory()
    if factory is None:
        return []
    try:
        enum = ctypes.c_void_p()
        if _method(factory, _FACTORY_LANGUAGES,
                   ctypes.POINTER(ctypes.c_void_p))(ctypes.byref(enum)) != 0:
            return []
        return _strings(enum)
    except Exception:                          # noqa: BLE001
        return []


def preferred_languages():
    """The person's own languages, best first: their Windows display
    languages, then the language their formats are set to."""
    if not _WINDOWS:
        return []
    out = []
    try:
        count, size = ctypes.c_ulong(), ctypes.c_ulong()
        # MUI_LANGUAGE_NAME: tags ("en-US"), not numbers.
        if _kernel32.GetUserPreferredUILanguages(0x8, ctypes.byref(count), None,
                                                  ctypes.byref(size)):
            buf = ctypes.create_unicode_buffer(size.value)
            if _kernel32.GetUserPreferredUILanguages(0x8, ctypes.byref(count), buf,
                                                      ctypes.byref(size)):
                out += [t for t in buf[:size.value].split("\0") if t]
        name = ctypes.create_unicode_buffer(85)
        if _kernel32.GetUserDefaultLocaleName(name, 85):
            out.append(name.value)
    except Exception:                          # noqa: BLE001
        pass
    return out


def language_name(tag):
    """The language's name in English ("Romanian"), or the tag itself."""
    if not _WINDOWS:
        return tag
    try:
        buf = ctypes.create_unicode_buffer(100)
        if _kernel32.GetLocaleInfoEx(ctypes.c_wchar_p(tag),
                                     _LOCALE_SENGLISHLANGUAGENAME, buf, 100):
            return buf.value or tag
    except Exception:                          # noqa: BLE001
        pass
    return tag


class Speller:
    """One language's checker."""

    def __init__(self, tag, obj):
        self.tag = tag
        self._obj = obj

    def errors(self, text):
        """(start, length) of every range the checker calls wrong, in the
        UTF-16 units Windows counts in; empty on any failure."""
        out = []
        if not text:
            return out
        try:
            enum = ctypes.c_void_p()
            if _method(self._obj, _CHECKER_CHECK, ctypes.c_wchar_p,
                       ctypes.POINTER(ctypes.c_void_p))(text, ctypes.byref(enum)) != 0:
                return out
            try:
                nxt = _method(enum, _ENUM_NEXT, ctypes.POINTER(ctypes.c_void_p))
                while True:
                    err = ctypes.c_void_p()
                    if nxt(ctypes.byref(err)) != 0 or not err:
                        break
                    try:
                        start, length = ctypes.c_ulong(), ctypes.c_ulong()
                        _method(err, _ERROR_START,
                                ctypes.POINTER(ctypes.c_ulong))(ctypes.byref(start))
                        _method(err, _ERROR_LENGTH,
                                ctypes.POINTER(ctypes.c_ulong))(ctypes.byref(length))
                        out.append((start.value, length.value))
                    finally:
                        _release(err)
            finally:
                _release(enum)
        except Exception:                      # noqa: BLE001
            return []
        return out

    def suggest(self, word, limit=5):
        """Up to *limit* replacements for *word*, best first."""
        try:
            enum = ctypes.c_void_p()
            if _method(self._obj, _CHECKER_SUGGEST, ctypes.c_wchar_p,
                       ctypes.POINTER(ctypes.c_void_p))(word, ctypes.byref(enum)) != 0:
                return []
            return [s for s in _strings(enum) if s and s != word][:limit]
        except Exception:                      # noqa: BLE001
            return []

    def add(self, word):
        """Put *word* in the person's Windows dictionary. True if it took."""
        try:
            return _method(self._obj, _CHECKER_ADD, ctypes.c_wchar_p)(word) == 0
        except Exception:                      # noqa: BLE001
            return False


def speller(tag):
    """The checker for language *tag*, made once; None if Windows has none."""
    if tag in _state["spellers"]:
        return _state["spellers"][tag]
    made = None
    factory = _factory()
    if factory is not None:
        try:
            obj = ctypes.c_void_p()
            if _method(factory, _FACTORY_CREATE, ctypes.c_wchar_p,
                       ctypes.POINTER(ctypes.c_void_p))(tag, ctypes.byref(obj)) == 0 and obj:
                made = Speller(tag, obj)
        except Exception:                      # noqa: BLE001
            made = None
    _state["spellers"][tag] = made
    return made
