"""Which misspellings to show, and which to leave alone: Windows judges the
words (core/winspell.py), this decides what the editor does with them --
plain strings and numbers, tested without Windows or a window. It keeps
quiet: a sentence mostly unknown is in a language with no dictionary here and
shows nothing (a short one takes its paragraph's verdict, then the note's);
a word is wrong only if every installed language says so, one dictionary per
language; links, addresses, file names, words with digits and capitals
("PDF") never are. Positions are UTF-16 units, as Windows and Tk's columns
count them -- one apart from Python's for every emoji before the word.
"""

import re
from bisect import bisect_right

# settings.json keys: Settings -> Appearance -> Spelling, on unless turned
# off, and the words the person chose to ignore on this computer.
SPELLING_SETTING = "spelling"
SPELLING_IGNORED_SETTING = "spelling_ignored"

# A line longer than this, in UTF-16 units, is asked about in pieces: one
# 28,000-word paste asked whole kept Windows busy for 1.5 s, and the editor
# with it.
PIECE_UNITS = 4000

# A sentence or a paragraph shorter than this says too little about its
# language to be judged on its own: a sentence takes its paragraph's verdict,
# a paragraph the whole note's.
MIN_WORDS_TO_JUDGE = 4
# More than this share of the words unknown, and the text is taken to be in
# a language the computer has no dictionary for.
FOREIGN_SHARE = 0.5
# The whole note is judged only once it has this many words.
MIN_WORDS_IN_NOTE = 6
# How many ignored words are kept: settings.json is read whole at every
# start, and a list that only ever grows must stop somewhere.
IGNORE_LIMIT = 5000
# The underlines a line, and a box, may hold, as the find bar holds its hits.
# Each is two toggles of a tag, and Tk's cost to read a line grows with their
# square: the save reads it at every pause (final audit, round 10).
MAX_UNDERLINES_PER_LINE = 500
MAX_UNDERLINES = 2000

# A run of letters, with an apostrophe or a hyphen allowed between two of
# them ("don't", "well-known"). Digits and underscores are not letters.
_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
# Inside a flagged range, any of these makes it a link, an address, a
# path, a file name or a time rather than a word of a language.
_NOT_A_WORD = re.compile(r"[\d@/\\.:_#&=?%+]")


def word_count(text):
    """How many words of letters *text* holds."""
    return len(_WORD.findall(text))


def utf16_units(text):
    """How long *text* is in UTF-16 units: one per character, two for each
    character past the basic plane (every emoji)."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


def utf16_slice(text, start, length):
    """The part of *text* from UTF-16 unit *start*, *length* units long."""
    return _units_of(text.encode("utf-16-le", "surrogatepass"), start, length)


def _units_of(raw, start, length):
    """utf16_slice of a text already encoded: *raw* is its UTF-16 bytes, so
    a caller slicing one line many times encodes it once."""
    return raw[2 * start:2 * (start + length)].decode("utf-16-le", "replace")


def pieces(text, size=PIECE_UNITS):
    """*text* as (offset, piece) pairs no longer than *size* UTF-16 units,
    cut after a space where there is one, so no word is split in two.
    *offset* is where the piece starts in *text*, in UTF-16 units. Walked
    by index, the line measured once: the rest of it, copied and measured
    again for every piece, grew with its square (round 9)."""
    out, offset, at = [], 0, 0
    left = utf16_units(text)
    while at < len(text):
        if left <= size:
            out.append((offset, text[at:]))
            break
        cut, units = at, 0
        for i in range(at, len(text)):
            units += 2 if ord(text[i]) > 0xFFFF else 1
            if units > size:
                break
            cut = i + 1
        space = text.rfind(" ", at, cut)
        if space > at:
            cut = space + 1
        cut = max(cut, at + 1)             # always move on, even past one wide character
        piece = text[at:cut]
        out.append((offset, piece))
        width = utf16_units(piece)
        offset, left, at = offset + width, left - width, cut
    return out


def worth_flagging(word, ignored=()):
    """Whether a range a dictionary calls wrong should be underlined.

    *ignored* holds words already passed through ignored_key."""
    word = word.strip("'’-")
    if not word or _NOT_A_WORD.search(word):
        return False
    letters = [c for c in word if c.isalpha()]
    if not letters:
        return False
    # PDF, NASA, OK: capitals throughout are an abbreviation or a name --
    # NASA's too, whose possessive is the one small letter in it.
    stem = re.sub("['’][sS]$", "", word)
    if len(letters) > 1 and all(c.isupper() for c in stem if c.isalpha()):
        return False
    return ignored_key(word) not in ignored


def ignored_key(word):
    """How a word is kept in, and looked up in, the ignored list: without
    the case it was typed in, so "Bucuresti" ignored is "bucuresti" too."""
    return word.strip().strip("'’-").casefold()


def normalize_ignored(value):
    """The ignored list as read from settings.json: strings only, each
    once, in the lookup form, no more than IGNORE_LIMIT of them. Anything
    else a hand-edited file holds is dropped rather than trusted."""
    if not isinstance(value, (list, tuple)):
        return []
    seen, out = set(), []
    for item in value:
        if not isinstance(item, str):
            continue
        key = ignored_key(item)
        if key and len(key) <= 100 and key not in seen:
            seen.add(key)
            out.append(key)
        if len(out) >= IGNORE_LIMIT:
            break
    return out


def line_errors(per_language):
    """The ranges every dictionary calls wrong.

    *per_language* holds one list of (start, length) per dictionary asked,
    for the same text. A word one of them knows is not wrong -- a Romanian
    word in an English sentence, with Romanian installed. No dictionary at
    all means nothing to report."""
    lists = [set(map(tuple, ranges)) for ranges in per_language]
    if not lists:
        return []
    return sorted(set.intersection(*lists))


def is_foreign(words, errors):
    """Whether a text of *words* words, *errors* of them unknown, reads as
    a language this computer has no dictionary for."""
    return words >= MIN_WORDS_TO_JUDGE and errors > FOREIGN_SHARE * words


def visible_errors(lines, results, ignored=()):
    """What to underline, line by line: {line index: [(start, length), ...]}
    in UTF-16 units, from *results* (each line's ranges every dictionary
    called wrong, None for a line not checked, a table row), less what reads
    as another language and what worth_flagging turns down. Each verdict is
    asked of the smallest text long enough to give one: a sentence of
    MIN_WORDS_TO_JUDGE words, else its paragraph, else the whole note."""
    words = errors = 0
    counted = []
    for text, ranges in zip(lines, results):
        if ranges is None:
            counted.append(None)
            continue
        n = word_count(text)
        counted.append(n)
        words += n
        errors += len(ranges)
    note_foreign = words >= MIN_WORDS_IN_NOTE and errors > FOREIGN_SHARE * words
    shown = {}
    for index, (text, ranges, n) in enumerate(zip(lines, results, counted)):
        if not ranges:
            continue
        if n >= MIN_WORDS_TO_JUDGE:
            paragraph_foreign = is_foreign(n, len(ranges))
        else:
            paragraph_foreign = note_foreign
        # The line measured once, each range put in its sentence once: each
        # sentence encoded the whole line and walked every range, and a long
        # line of short sentences took seconds at every pause (round 9).
        raw = text.encode("utf-16-le", "surrogatepass")
        spans = sentence_spans(text)
        starts = [start for start, _end in spans]
        inside = [[] for _span in spans]
        for r in ranges:
            if 0 <= r[0] < spans[-1][1]:
                inside[bisect_right(starts, r[0]) - 1].append(r)
        keep = []
        for (start, end), found in zip(spans, inside):
            if not found:
                continue
            sentence_words = word_count(_units_of(raw, start, end - start))
            if sentence_words >= MIN_WORDS_TO_JUDGE:
                foreign = is_foreign(sentence_words, len(found))
            else:
                foreign = paragraph_foreign
            if not foreign:
                keep += [(s, length) for s, length in found
                         if worth_flagging(_units_of(raw, s, length), ignored)]
        if keep:
            shown[index] = keep
    return shown


# A sentence ends at a full stop, a question or exclamation mark or an
# ellipsis, with a space (or the end of the line) after it. Asked only where
# a run starts: tried at each of 24,000 dots, a look took 4.5 s (round 9).
_SENTENCE_END = re.compile(r"(?<![.!?…])[.!?…]+(?=\s|$)")


def sentence_spans(text):
    """The sentences of a line, as (start, end) in UTF-16 units, covering
    the whole of it: every position belongs to exactly one. Each sentence is
    measured on its own and added on, never the line again from its start."""
    spans, start, at = [], 0, 0
    for m in _SENTENCE_END.finditer(text):
        end = m.end()
        width = utf16_units(text[start:end])
        spans.append((at, at + width))
        start, at = end, at + width
    if start < len(text) or not spans:
        spans.append((at, at + utf16_units(text[start:])))
    return spans


def range_at(ranges, column):
    """The range *column* touches -- inside it or at either end -- or None.
    The editor leaves the word under the caret alone while it is typed."""
    for start, length in ranges:
        if start <= column <= start + length:
            return (start, length)
    return None


def nearest_underlines(shown, line, column, per_line=MAX_UNDERLINES_PER_LINE,
                       total=MAX_UNDERLINES):
    """*shown* (visible_errors' answer) cut to what a box may hold: at most
    *per_line* ranges a line and *total* in all, those nearest the caret at
    (*line*, *column*) kept -- where words are being written. A line above
    the caret keeps its last ranges, a line below its first, the caret's own
    line those around the column."""
    out, room = {}, total
    for index in sorted(shown, key=lambda i: (abs(i - line), i)):
        keep = min(per_line, room)
        if keep <= 0:
            break
        ranges = sorted(shown[index])
        if len(ranges) > keep:
            if index < line:
                ranges = ranges[-keep:]
            elif index > line:
                ranges = ranges[:keep]
            else:
                at = bisect_right([start for start, _length in ranges], column)
                first = max(0, min(at - keep // 2, len(ranges) - keep))
                ranges = ranges[first:first + keep]
        out[index] = ranges
        room -= len(ranges)
    return out


def pick_languages(supported, preferred=()):
    """One dictionary per language, the person's own languages first:
    Windows lists one per region (nineteen for English), and asking each
    gives the same answer slower. The tag kept is the person's (*preferred*:
    display and format languages, best first), else the language's own
    country (de-DE, ro-RO), else en-US for English, else the first listed."""
    by_base = {}
    for tag in supported:
        if isinstance(tag, str) and tag:
            by_base.setdefault(tag.split("-")[0].lower(), []).append(tag)
    lowered = {t.lower(): t for tags in by_base.values() for t in tags}
    order, chosen = [], {}
    for tag in preferred:
        if not isinstance(tag, str):
            continue
        base = tag.split("-")[0].lower()
        if base in by_base and base not in chosen:
            chosen[base] = lowered.get(tag.lower())
            order.append(base)
    for base in by_base:
        if base not in chosen:
            chosen[base] = None
            order.append(base)
    picked = []
    for base in order:
        tags = by_base[base]
        if chosen[base]:
            picked.append(chosen[base])
            continue
        home = lowered.get(f"{base}-{base}".lower())
        if base == "en":
            home = lowered.get("en-us", home)
        picked.append(home or tags[0])
    return picked
