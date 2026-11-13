"""Share codes -- notes moved between devices as copy-paste text, ``notes ->
JSON -> zlib -> Base64 -> "NOTE1:" + text`` and back -- and a backup zip's
guards. Compression, not encryption: anyone holding a code reads it; files
stay out, a code with them would run to millions of characters.

Decoding distrusts its input and limits it while working, not after: a
length cap, a bounded decompress against zip bombs, a note cap, Zip Slip
refused for a backup's paths, a stoppable file for a closing window. And
every limit on reading is a promise on writing: what the app makes is
checked against what it accepts back. ``docs/CODE_TOUR.md`` walks it.
"""

import base64
import json
import os
import re
import shutil
import zlib

from .paths import JSON_UNREADABLE
from .storage import json_from_text, mend_surrogates

# ---- Share codes: a note's content, never its files (the backup's zip
# carries those); the prefix names the format's version. ----

SHARE_CODE_PREFIX = "NOTE1:"

# Safety limits for importing share codes. These stop a malformed or malicious
# code from exhausting memory or flooding the notebook.
MAX_SHARE_CODE_CHARS = 5_000_000      # reject absurdly long pasted text outright
MAX_DECOMPRESSED_BYTES = 20_000_000   # cap zlib output — guards against zip bombs
MAX_SHARED_NOTES = 200                # most notes one code may carry

# Only these fields travel: no id (a place in one file), files, updated or a
# series' own days. "paragraphs" keeps lists' indents and a table's place.
SHAREABLE_FIELDS = [
    # The uid lets the far end know a note it already has, rather than guess
    # from the text -- a guess that fails just when the note was edited.
    "uid",
    "title", "body", "formatting", "comments", "category", "date", "color", "recurrence",
    "paragraphs", "checklist",
]


def _shareable_view(note):
    """The slice of a note that a share code carries."""
    return {k: note.get(k) for k in SHAREABLE_FIELDS if k in note}


class ShareCodeTooLarge(ValueError):
    """The notes asked for make a code that decode_share_code would refuse.
    Its message is for the person sending them."""


def encode_share_code(notes):
    """Turn one or more notes into a copy-paste share code. Accepts a single
    note dict or a list of them.

    Raises ShareCodeTooLarge rather than return a code the import refuses:
    the Share panel's Select all could pick more notes than one code may
    carry, and a long note could make a code past the size limits."""
    if isinstance(notes, dict):
        notes = [notes]
    if len(notes) > MAX_SHARED_NOTES:
        raise ShareCodeTooLarge(
            "A code can carry at most %d notes, and %d are ticked. Untick "
            "some, or send a backup instead: Settings → Backup → Export."
            % (MAX_SHARED_NOTES, len(notes)))
    payload = {"v": 1, "notes": [_shareable_view(n) for n in notes]}
    # Tk hands an emoji over as a surrogate pair: a note with one just typed,
    # not yet mended by a save, crashed the encode below.
    payload = mend_surrogates(payload)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    b64 = base64.urlsafe_b64encode(compressed).decode("ascii")
    code = SHARE_CODE_PREFIX + b64
    if len(raw) > MAX_DECOMPRESSED_BYTES or len(code) > MAX_SHARE_CODE_CHARS:
        raise ShareCodeTooLarge(
            "That is too much for one code. Share fewer notes at a time, or "
            "send a backup instead: Settings → Backup → Export.")
    return code


def _bounded_decompress(compressed, limit):
    """Decompress, but never produce more than `limit` bytes. A tiny 'zip bomb'
    can expand to gigabytes and crash the app; this stops it cold."""
    dobj = zlib.decompressobj()
    out = dobj.decompress(compressed, limit)
    if dobj.unconsumed_tail:
        # There's more than the limit allows — refuse rather than keep going.
        raise ValueError("decompressed data exceeds the safe size limit")
    out += dobj.flush()
    if len(out) > limit:
        raise ValueError("decompressed data exceeds the safe size limit")
    return out


# A code after its prefix: Base64 in either spelling, the whitespace and the
# invisible break marks (soft hyphen, zero-width space) a chat app wraps it
# with, and its padding.
_CODE_SKIP = "\\s\u00ad\u200b-\u200d\u2060\ufeff"
_CODE_BODY = re.compile("[A-Za-z0-9_\\-+/" + _CODE_SKIP + "]*(?:=[=" + _CODE_SKIP + "]*)?")
_CODE_SKIPPED = re.compile("[" + _CODE_SKIP + "]")


def code_in(text):
    """The share code inside *text*, whitespace and invisible break marks
    taken out (a chat app wraps a long code): from its prefix to its
    padding, or to the first character a code is not written in, so "Hi!
    NOTE1:... Thanks" reads. Without padding, letters past the last whole
    group of four are left (a word after it). With no prefix, *text*
    itself, whitespace out."""
    at = text.find(SHARE_CODE_PREFIX)
    if at < 0:
        return "".join(text.split())
    body = _CODE_SKIPPED.sub("", _CODE_BODY.match(text, at + len(SHARE_CODE_PREFIX)).group(0))
    if "=" not in body:
        body = body[:len(body) - len(body) % 4]
    return SHARE_CODE_PREFIX + body


def decode_share_code(code):
    """Parse a share code back into a list of note dicts. Raises ValueError with
    a human-readable message if the code is malformed, oversized, or from a
    newer version."""
    if not isinstance(code, str):
        raise ValueError("That doesn't look like a share code.")
    code = code_in(code)
    if not code:
        raise ValueError("No code was pasted.")
    if len(code) > MAX_SHARE_CODE_CHARS:
        raise ValueError(
            "That code is far too large to import safely. For a transfer this "
            "large, send a backup instead: Settings → Backup → Export, then "
            "Import on the other computer."
        )
    if not code.startswith(SHARE_CODE_PREFIX):
        raise ValueError(
            "This isn't a Note Organizer share code. A valid code starts "
            f"with \u201c{SHARE_CODE_PREFIX}\u201d."
        )
    body = code[len(SHARE_CODE_PREFIX):]
    try:
        compressed = base64.urlsafe_b64decode(body)
    except (base64.binascii.Error, ValueError):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again — chat apps sometimes cut long codes short."
        )
    try:
        raw = _bounded_decompress(compressed, MAX_DECOMPRESSED_BYTES)
    except (zlib.error, ValueError):
        raise ValueError(
            "This share code is damaged, or too large to import safely. Ask the "
            "sender to send it again, or to send a backup instead (Settings → "
            "Backup → Export)."
        )
    try:
        # Half an emoji spelled as an escape, mended (json_from_text).
        payload = json_from_text(raw.decode("utf-8"))
    except (*JSON_UNREADABLE, ValueError):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again."
        )
    if not isinstance(payload, dict) or "notes" not in payload:
        raise ValueError("This share code doesn't contain any notes.")
    # The version is the code's own claim, in text anyone can edit: a string
    # or null compared unchecked raised TypeError past the import box. bool
    # is refused by name, an int to Python.
    version = payload.get("v", 1)
    if isinstance(version, bool) or not isinstance(version, (int, float)):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again."
        )
    if version > 1:
        raise ValueError(
            "This code was made by a newer version of Note Organizer. "
            "Update the app to import it."
        )
    notes = payload.get("notes")
    if not isinstance(notes, list) or not notes:
        raise ValueError("This share code doesn't contain any notes.")
    if len(notes) > MAX_SHARED_NOTES:
        raise ValueError(
            f"This code contains {len(notes)} notes, which is over the "
            f"{MAX_SHARED_NOTES}-note limit for a single code. Ask the sender to "
            "split it into smaller codes, or to send a backup instead "
            "(Settings → Backup → Export)."
        )
    # The same slice encode makes, so a hand-made code carries only what a
    # real one would: no attachment whose stored_as could point a later
    # delete at a file outside the folder. normalize_note filters again.
    return [_shareable_view(n) if isinstance(n, dict) else {} for n in notes]


# ---- Backups (the .zip of Settings -> Backup): what the app writes it must
# read back, so the limits are about a HOSTILE archive, and the export checks
# itself against them (backup_entries_problem). ----
MAX_BACKUP_FILES = 100_000
# More than this many times its packed size, and past BOMB_MIN_BYTES, is a
# zip bomb, not a photo or a video; asked of each entry and of the whole
# archive, which a thousand entries each just under it would pass.
BOMB_RATIO = 100
BOMB_MIN_BYTES = 50_000_000
# What an import leaves free on each disk it writes to. A size cap on the
# backup stood in for this, and refused honest backups on empty disks.
DISK_MARGIN = 200_000_000


def size_text(n):
    """A byte count as people read it: 350 MB, 1.2 GB."""
    if n >= 1_000_000_000:
        return "%.1f GB" % (n / 1_000_000_000)
    return "%d MB" % max(1, round(n / 1_000_000))


def backup_entries_problem(infos):
    """Why a backup's entries cannot be imported, whatever disk they land
    on -- or None. *infos* are its ZipInfo entries. The import asks this
    before unpacking, and the export asks it of what it has just written."""
    if len(infos) > MAX_BACKUP_FILES:
        return ("This backup holds %d files, more than an import takes (%d)."
                % (len(infos), MAX_BACKUP_FILES))
    sizes = [(info.filename, max(info.file_size, 0), max(info.compress_size, 0))
             for info in infos]
    sizes.append(("The backup", sum(s for _n, s, _p in sizes), sum(p for _n, _s, p in sizes)))
    for name, size, packed in sizes:
        if size > BOMB_MIN_BYTES and size > BOMB_RATIO * max(packed, 1):
            return ("%s would expand to %s from %s packed, which is how a "
                    "damaged or hostile backup looks."
                    % (name, size_text(size), size_text(packed)))
    return None


def backup_space_problem(infos, free_unpack, free_attach=None):
    """Why there is not room to import a backup, or None.

    Everything is unpacked in one place, then the attachments are copied
    into the app's folder: *free_unpack* is the free space where it is
    unpacked, *free_attach* that of the attachments' disk when it is a
    different one (None: the same disk, which then holds them twice)."""
    total = sum(max(i.file_size, 0) for i in infos)
    attached = sum(max(i.file_size, 0) for i in infos
                   if i.filename.replace("\\", "/").startswith("attachments/"))
    needs = [(total + (attached if free_attach is None else 0), free_unpack)]
    if free_attach is not None:
        needs.append((attached, free_attach))
    for need, free in needs:
        if need + DISK_MARGIN > free:
            return ("There isn't enough free space to import this backup: it "
                    "needs about %s, and %s is free. Free up some space and "
                    "try again." % (size_text(need + DISK_MARGIN), size_text(free)))
    return None


def _disk_of(path):
    """(free bytes, device) of the disk *path* is on -- or would be on, for
    a folder not made yet."""
    path = os.path.abspath(path)
    while not os.path.exists(path) and os.path.dirname(path) != path:
        path = os.path.dirname(path)
    return shutil.disk_usage(path).free, os.stat(path).st_dev


class BackupRefused(ValueError):
    """A sound backup refused for a reason said whole: no room for it. Said
    as it is, not as a file that could not be read."""


def _safe_extract_zip(zf, dest_dir, attachments_dir=None):
    """Extract a zip safely: block path-traversal ('../' escapes), zip bombs
    and a full disk. extractall() guards against none of them, so a
    malicious backup could otherwise write files anywhere or fill the disk.
    *attachments_dir* is where the import copies the attachments next."""
    dest_root = os.path.abspath(dest_dir)
    infos = zf.infolist()
    problem = backup_entries_problem(infos)
    if problem:
        raise ValueError(problem)
    free_unpack, unpack_disk = _disk_of(dest_root)
    free_attach = None
    if attachments_dir is not None:
        attach_free, attach_disk = _disk_of(attachments_dir)
        if attach_disk != unpack_disk:
            free_attach = attach_free
    room = backup_space_problem(infos, free_unpack, free_attach)
    if room:
        raise BackupRefused(room)

    for info in infos:
        # Reject absolute paths and anything that escapes the destination.
        target = os.path.abspath(os.path.join(dest_root, info.filename))
        if not (target == dest_root or target.startswith(dest_root + os.sep)):
            raise ValueError("This backup contains unsafe file paths and was blocked.")
    zf.extractall(dest_dir)


class BackupStopped(Exception):
    """The window closed while a backup was still being written or read."""


class StoppableFile:
    """An open file whose next read or write raises BackupStopped once
    *stop* (a function) answers true. A backup's worker hands zipfile one,
    so closing the window cuts a long export or import short between two
    chunks, inside zipfile's own loops -- and waits for nothing but that.
    Everything else is the wrapped file's own."""

    def __init__(self, raw, stop):
        self._raw = raw
        self._stop = stop

    def _check(self):
        if self._stop():
            raise BackupStopped("The window closed before the backup was finished.")

    def read(self, *args):
        self._check()
        return self._raw.read(*args)

    def write(self, data):
        self._check()
        return self._raw.write(data)

    def __getattr__(self, name):
        return getattr(self._raw, name)


def copy_file_until_stopped(src, dst, stop):
    """shutil.copy2, a megabyte at a time, asking *stop* between them.
    Nothing is left at *dst* unless the whole file got there."""
    try:
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            shutil.copyfileobj(StoppableFile(fin, stop), fout, 1 << 20)
            # On the disk before the caller's rename, as every data file is
            # (_write_json_atomic): a power cut could leave an empty file.
            fout.flush()
            os.fsync(fout.fileno())
        shutil.copystat(src, dst)
    except BaseException:
        try:
            os.remove(dst)
        except OSError:
            pass
        raise


# Windows' "Mark of the Web", which SmartScreen and Office's Protected View
# read: a zip keeps it on the zip only, so the import marks each file it takes
# out, as Explorer does. ISSUES_LOG: "The photo that was a remote connection".
ZONE_STREAM = ":Zone.Identifier"
MAX_ZONE_MARK = 64 * 1024
# What stands in for a mark too long to be a real one: the Internet zone.
INTERNET_ZONE_MARK = b"[ZoneTransfer]\r\nZoneId=3\r\n"


def zone_mark_of(path):
    """The Mark of the Web *path* carries, as the bytes of its stream, or None:
    there is none, this is not Windows, or the disk keeps no streams."""
    if os.name != "nt":
        return None
    try:
        with open(path + ZONE_STREAM, "rb") as fh:
            mark = fh.read(MAX_ZONE_MARK + 1)
    except (OSError, ValueError):
        return None
    if len(mark) > MAX_ZONE_MARK:
        return INTERNET_ZONE_MARK
    return mark or None


def put_zone_mark(path, mark):
    """Give the file at *path* the Mark of the Web *mark* (from zone_mark_of).
    Never raises, and answers whether the mark was written: on FAT, exFAT or
    a share without streams the file simply goes unmarked, and stays."""
    if not mark or os.name != "nt":
        return False
    try:
        with open(path + ZONE_STREAM, "wb") as fh:
            fh.write(mark)
        return True
    except (OSError, ValueError):
        return False
