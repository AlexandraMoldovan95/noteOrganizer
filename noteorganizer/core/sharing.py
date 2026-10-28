"""Share codes: moving notes between devices as copy-paste text.

WHAT THIS MODULE IS FOR
-----------------------
A share code is a block of text you can paste into a chat or an email
that another copy of the app turns back into notes. The pipeline is::

    notes -> JSON -> zlib compress -> Base64 -> "NOTE1:" + text

and exactly the reverse coming back. The prefix is a version marker, so a
future format can be recognised rather than misread.

**This is compression, not encryption.** Anyone holding the code can read
it. It exists to make notes portable, not private - worth stating plainly,
because Base64 output *looks* scrambled.

Attachments are deliberately excluded: binary files would push a code into
millions of characters, well past what any chat box will accept. The ZIP
export handles those instead.

THE INTERESTING PART: DISTRUSTING YOUR OWN INPUT
------------------------------------------------
Decoding runs on text the user pasted from somewhere unknown, so every
stage assumes the worst:

* :data:`MAX_SHARE_CODE_CHARS` - refuse absurdly long input before doing
  any work at all.
* :func:`_bounded_decompress` - decompress in chunks with a hard ceiling.
  A "zip bomb" is a tiny compressed payload that expands to gigabytes;
  calling ``zlib.decompress()`` on one would exhaust memory before it ever
  returned. Feeding it through a decompressor object and stopping at the
  limit checks the size *while* expanding rather than after.
* :data:`MAX_SHARED_NOTES` - cap how many notes a single code may carry.
* :func:`_safe_extract_zip` - for ZIP import, reject any entry whose
  resolved path escapes the destination folder. Without this an archive
  containing ``../../something`` could write anywhere on disk. The attack
  has a name, "Zip Slip", and the defence is to resolve each path and
  confirm it still sits under the destination. It also refuses an entry
  shaped like a zip bomb, and a backup the disk has no room for.
* :class:`StoppableFile` - the file a backup's worker hands zipfile, so
  closing the window stops a long export or import between two chunks
  and its unfinished files can be taken away, instead of the process
  dying mid-file with them on disk.

The pattern worth taking away: when data comes from outside, enforce
limits *during* processing instead of trusting it to be reasonable.

The other half: every limit on reading is also a promise about writing.
The app makes share codes and backups itself, and each is checked
against the same limits it will meet coming back (encode_share_code,
backup_entries_problem). A limit only on the reading side once made
backups the app wrote that it then refused to restore.
"""

import base64
import json
import os
import shutil
import zlib

from .paths import JSON_UNREADABLE
from .storage import mend_surrogates

# ---- Share codes (move notes between devices as copy-paste text) ----
#
# A share code is: a small JSON payload -> zlib-compressed -> Base64 text,
# tagged with a version prefix. It carries note CONTENT (title, body, comments,
# category, date, color, recurrence) but NOT attachments — binary files
# would bloat the code to millions of characters, past what any chat box or
# email will paste. For attachments, the ZIP export is the right tool.

SHARE_CODE_PREFIX = "NOTE1:"

# Safety limits for importing share codes. These stop a malformed or malicious
# code from exhausting memory or flooding the notebook.
MAX_SHARE_CODE_CHARS = 5_000_000      # reject absurdly long pasted text outright
MAX_DECOMPRESSED_BYTES = 20_000_000   # cap zlib output — guards against zip bombs
MAX_SHARED_NOTES = 200                # most notes one code may carry

# Only these fields travel in a share code. Notably absent: id (assigned fresh
# on import), attachments, updated, overrides/exceptions/moved days.
# "paragraphs" carries list indents/alignment and a table's place on the
# page -- without it a shared note arrived flush left with flat lists.
SHAREABLE_FIELDS = [
    # "uid" travels; "id" does not. The id is only a note's place in one
    # file and means nothing anywhere else, but the uid is what lets the
    # far end recognise a note it already has instead of guessing from
    # the text -- a guess that fails exactly when the note was edited,
    # which is the only time anyone re-sends one.
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
    # In-memory notes can hold lone UTF-16 surrogates: Tk hands an astral
    # emoji over as a surrogate pair, and mend_surrogates only ran when
    # SAVING to disk — so sharing a note with a just-typed emoji hit the
    # .encode("utf-8") below and crashed. Mend at this boundary too.
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


def decode_share_code(code):
    """Parse a share code back into a list of note dicts. Raises ValueError with
    a human-readable message if the code is malformed, oversized, or from a
    newer version."""
    if not isinstance(code, str):
        raise ValueError("That doesn't look like a share code.")
    # Tolerate extra whitespace/newlines from a chat app.
    code = "".join(code.split())
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
        payload = json.loads(raw.decode("utf-8"))
    except (*JSON_UNREADABLE, ValueError):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again."
        )
    if not isinstance(payload, dict) or "notes" not in payload:
        raise ValueError("This share code doesn't contain any notes.")
    # The version is the code's own claim about its format, and the code
    # is text anyone can edit. Compared unchecked, a string, null or list
    # here raised TypeError -- which the import box does not catch, so a
    # hand-edited code got an internal error instead of the message
    # below. bool is refused by name because it is an int to Python.
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
    # Project each note through the SAME shareable slice encode produces,
    # so a hand-crafted code can carry only the fields a real one would.
    # A genuine code never includes attachments (they aren't in
    # SHAREABLE_FIELDS); dropping them here means an imported note can't
    # smuggle in an attachment reference whose stored_as points a later
    # delete at a file outside the attachments folder. normalize_note
    # already whitelists on top of this — this is the boundary that
    # makes the two ends symmetric.
    return [_shareable_view(n) if isinstance(n, dict) else {} for n in notes]


# ---- Backups (the .zip of Settings -> Backup) ----
#
# A backup the app wrote must be one it agrees to read back. The export
# takes every attached file whatever its size, and the import used to
# refuse anything over 500 MB or 10,000 files: one long video, or a few
# hundred phone photos, made a backup that could not be restored. The
# limits are now about what a HOSTILE archive could do, and the export
# checks what it wrote against the same rules (backup_entries_problem).
MAX_BACKUP_FILES = 100_000
# Expanding to more than this many times its packed size, and to more than
# BOMB_MIN_BYTES, is a zip bomb, not anything anyone attached: photos,
# videos and documents pack to within a few times their size. Asked of
# each entry and of the archive as a whole, or a thousand entries just
# under the size each would pass one by one.
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


def _safe_extract_zip(zf, dest_dir, attachments_dir=None):
    """Extract a zip safely: block path-traversal ('../' escapes), zip bombs
    and a full disk. extractall() guards against none of them, so a
    malicious backup could otherwise write files anywhere or fill the disk.
    *attachments_dir* is where the import copies the attachments next."""
    dest_root = os.path.abspath(dest_dir)
    infos = zf.infolist()
    problem = backup_entries_problem(infos)
    if problem is None:
        free_unpack, unpack_disk = _disk_of(dest_root)
        free_attach = None
        if attachments_dir is not None:
            attach_free, attach_disk = _disk_of(attachments_dir)
            if attach_disk != unpack_disk:
                free_attach = attach_free
        problem = backup_space_problem(infos, free_unpack, free_attach)
    if problem:
        raise ValueError(problem)

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


# Windows' "Mark of the Web": the stream a browser or mail program leaves on a
# downloaded file, saying where it came from. SmartScreen, Office's Protected
# View and its block on macros from the internet all read it. A zip keeps it on
# the zip only, so whatever the import takes out of a backup would arrive
# unmarked -- unless the import writes the backup's mark onto each file, as
# Explorer's own unzip does. ISSUES_LOG: "The photo that was a remote connection".
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
