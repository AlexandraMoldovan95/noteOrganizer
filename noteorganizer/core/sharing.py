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
  confirm it still sits under the destination.

The pattern worth taking away: when data comes from outside, enforce
limits *during* processing instead of trusting it to be reasonable.
"""

import base64
import json
import os
import zlib

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
# on import), attachments, updated, overrides/exceptions.
# "paragraphs" carries list indents/alignment and a table's place on the
# page -- without it a shared note arrived flush left with flat lists.
SHAREABLE_FIELDS = [
    "title", "body", "formatting", "comments", "category", "date", "color", "recurrence",
    "paragraphs", "checklist",
]


def _shareable_view(note):
    """The slice of a note that a share code carries."""
    return {k: note.get(k) for k in SHAREABLE_FIELDS if k in note}


def encode_share_code(notes):
    """Turn one or more notes into a copy-paste share code. Accepts a single
    note dict or a list of them."""
    if isinstance(notes, dict):
        notes = [notes]
    payload = {"v": 1, "notes": [_shareable_view(n) for n in notes]}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    b64 = base64.urlsafe_b64encode(compressed).decode("ascii")
    return SHARE_CODE_PREFIX + b64


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
            "That code is far too large to import safely. Use Import (ZIP) for "
            "very large transfers."
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
            "sender to send it again, or use Import (ZIP) for large transfers."
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        raise ValueError(
            "This share code is damaged or incomplete. Ask the sender to copy "
            "the whole code again."
        )
    if not isinstance(payload, dict) or "notes" not in payload:
        raise ValueError("This share code doesn't contain any notes.")
    if payload.get("v", 1) > 1:
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
            "split it into smaller codes, or to use Export (ZIP) instead."
        )
    return notes


def _safe_extract_zip(zf, dest_dir):
    """Extract a zip safely: block path-traversal ('../' escapes) and refuse
    archives that would expand past a sane size. extractall() does neither, so
    a malicious backup zip could otherwise write files anywhere or fill the disk."""
    MAX_TOTAL = 500_000_000   # 500 MB uncompressed ceiling for a whole backup
    MAX_FILES = 10_000
    dest_root = os.path.abspath(dest_dir)

    infos = zf.infolist()
    if len(infos) > MAX_FILES:
        raise ValueError("This backup contains too many files to import safely.")

    total = sum(max(i.file_size, 0) for i in infos)
    if total > MAX_TOTAL:
        raise ValueError("This backup is too large to import safely.")

    for info in infos:
        # Reject absolute paths and anything that escapes the destination.
        target = os.path.abspath(os.path.join(dest_root, info.filename))
        if not (target == dest_root or target.startswith(dest_root + os.sep)):
            raise ValueError("This backup contains unsafe file paths and was blocked.")
    zf.extractall(dest_dir)
