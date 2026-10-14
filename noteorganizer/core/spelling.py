"""Which misspellings to show, and which to leave alone.

WHAT THIS MODULE IS FOR
-----------------------
The words themselves are judged by Windows' own spell checker
(core/winspell.py). This module decides what the editor does with its
answers, and it is plain strings and numbers in and out, so all of it is
tested without Windows and without a window.

A spell checker that underlines everything it does not know is worse than
none: a note written in a language the computer has no dictionary for
comes out red from end to end. So the rules here are about staying quiet:

* **Another language is left alone.** When most of a paragraph's words are
  unknown, the paragraph is in a language this computer cannot check, and
  nothing in it is underlined. The same is asked of the note as a whole, so
  a note of short lines -- a shopping list in Romanian -- is judged by all
  of its words, not by two at a time. A Romanian paragraph read as English
  had 17 of its 21 words flagged; an English one with three typos, 3 of 15.
* **Every installed language counts.** A word is wrong only if every
  dictionary Windows has calls it wrong (line_errors), one dictionary per
  language (pick_languages): Windows offers nineteen kinds of English, and
  asking all nineteen would only be slower.
* **Not everything is a word.** A link, an address, a file name, a word
  with digits in it, and an abbreviation written in capitals ("PDF") are
  never underlined (worth_flagging); nor is a word its owner chose to
  ignore.

Positions are in UTF-16 units throughout, which is what Windows reports and
what a Tk Text widget's columns count -- not Python characters, which differ
by one for every emoji before the word.
"""

import re

# settings.json keys: Settings -> Appearance -> Spelling, on unless turned
# off, and the words the person chose to ignore on this computer.
SPELLING_SETTING = "spelling"
SPELLING_IGNORED_SETTING = "spelling_ignored"

# A line longer than this, in UTF-16 units, is asked about in pieces: one
# 28,000-word paste asked whole kept Windows busy for 1.5 s, and the editor
# with it.
PIECE_UNITS = 4000

# A paragraph shorter than this says too little about its language to be
# judged on its own; the note's verdict covers it.
MIN_WORDS_TO_JUDGE = 4
# More than this share of the words unknown, and the text is taken to be in
# a language the computer has no dictionary for.
FOREIGN_SHARE = 0.5
# The whole note is judged only once it has this many words.
MIN_WORDS_IN_NOTE = 6
# How many ignored words are kept: settings.json is read whole at every
# start, and a list that only ever grows must stop somewhere.
IGNORE_LIMIT = 5000

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
    raw = text.encode("utf-16-le", "surrogatepass")
    return raw[2 * start:2 * (start + length)].decode("utf-16-le", "replace")


def pieces(text, size=PIECE_UNITS):
    """*text* as (offset, piece) pairs no longer than *size* UTF-16 units,
    cut after a space where there is one, so no word is split in two.
    *offset* is where the piece starts in *text*, in UTF-16 units."""
    out, offset = [], 0
    while text:
        if utf16_units(text) <= size:
            out.append((offset, text))
            break
        cut, units = 0, 0
        for i, ch in enumerate(text):
            units += 2 if ord(ch) > 0xFFFF else 1
            if units > size:
                break
            cut = i + 1
        space = text.rfind(" ", 0, cut)
        if space > 0:
            cut = space + 1
        cut = max(cut, 1)                  # always move on, even past one wide character
        piece, text = text[:cut], text[cut:]
        out.append((offset, piece))
        offset += utf16_units(piece)
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
    """What to underline, line by line.

    *lines* are the texts that were checked; *results* holds, for each, the
    ranges every dictionary called wrong (line_errors), or None for a line
    that is not checked at all (a table row). Returns {line index: [(start,
    length), ...]} in UTF-16 units, after the rules this module is for: a
    note that reads as another language shows nothing, nor does such a
    paragraph, nor anything worth_flagging turns down."""
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
    if words >= MIN_WORDS_IN_NOTE and errors > FOREIGN_SHARE * words:
        return {}
    shown = {}
    for index, (text, ranges, n) in enumerate(zip(lines, results, counted)):
        if not ranges or is_foreign(n, len(ranges)):
            continue
        keep = [(s, length) for s, length in ranges
                if worth_flagging(utf16_slice(text, s, length), ignored)]
        if keep:
            shown[index] = keep
    return shown


def range_at(ranges, column):
    """The range *column* touches -- inside it or at either end -- or None.
    The editor leaves the word under the caret alone while it is typed."""
    for start, length in ranges:
        if start <= column <= start + length:
            return (start, length)
    return None


def pick_languages(supported, preferred=()):
    """One dictionary per language, the person's own languages first.

    Windows lists a dictionary for every region of a language -- nineteen
    for English on an ordinary English machine -- and asking each of them
    gives the same answer slower. For each language the tag chosen is the
    one the person uses (*preferred*: their Windows display and format
    languages, best first), else that language's own country (de-DE,
    ro-RO), else en-US for English, else the first Windows lists."""
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
