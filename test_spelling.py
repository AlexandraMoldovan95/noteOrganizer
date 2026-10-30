"""Tests for the spelling rules: what is underlined, and what is left alone.

Headless and pure, like test_tables.py: core/spelling.py turns strings and
numbers into strings and numbers, and the dictionaries are stood in for, so
this needs no window and no Windows. The real checker is asked in qa6.

Check descriptions stay ASCII-only, for the same reason test_calculator.py
does: printing a bullet crashes a plain Windows console on cp1252.
"""
import os
import sys
# Settled as a guest of this computer before the app's code (qa/_qa_support,
# beside this file in a scratch copy, in qa/ where CI runs it).
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa"))
from _qa_support import as_a_guest  # noqa: E402
as_a_guest()
from noteorganizer.core import spelling  # noqa: E402

fails = []


def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond:
        fails.append(name)


# --- positions, counted the way Windows and Tk count them ----------------
_party = "Party \U0001F389 tommorow"
_at = _party.index("tommorow")
check("an emoji counts two units, so the word after it starts one place later "
      "than Python's index", spelling.utf16_units(_party[:_at]) == _at + 1)
check("...and slicing in those units returns the word itself",
      spelling.utf16_slice(_party, _at + 1, 8) == "tommorow")
check("utf16_units of plain text is its length",
      spelling.utf16_units("plain words") == len("plain words"))

# --- what a word is -------------------------------------------------------
check("words are runs of letters, with an inner apostrophe or hyphen",
      spelling.word_count("I don't like well-known 10:30 things") == 5)
check("letters of any alphabet are words",
      spelling.word_count("M\u00e2ine pia\u021b\u0103 \u043c\u0438\u0440") == 3)
check("digits and punctuation alone are not words",
      spelling.word_count("12 34 -- ... 10:30") == 0)

# --- what is worth underlining -------------------------------------------
for word, want, why in (
        ("tommorow", True, "an ordinary misspelling"),
        ("PDF", False, "an abbreviation in capitals"),
        ("NASA's", False, "capitals with an apostrophe"),
        ("I", True, "a single capital is still a word"),
        ("file.txt", False, "a file name"),
        ("www.example.com", False, "a link"),
        ("ana@example.ro", False, "an address"),
        ("abc123", False, "a word with digits"),
        ("C:\\Users", False, "a path"),
        ("#tag", False, "a tag"),
        ("", False, "nothing"),
        ("'''", False, "only apostrophes"),
):
    check(f"worth_flagging({word!r}) is {want}: {why}",
          spelling.worth_flagging(word) is want)
check("an ignored word is not underlined, whatever its case",
      not spelling.worth_flagging("Bucuresti", {spelling.ignored_key("bucuresti")}))
check("...and ignoring it does not hide a different word",
      spelling.worth_flagging("Brasov", {spelling.ignored_key("bucuresti")}))

# --- the ignored list as read from a hand-editable file ------------------
check("the ignored list keeps strings once, in lookup form",
      spelling.normalize_ignored(["Foo", "foo", " ", 7, None, "Bar"]) == ["foo", "bar"])
check("...and is empty for anything that is not a list",
      spelling.normalize_ignored({"a": 1}) == [] and spelling.normalize_ignored(None) == [])
check("...and stops at its limit",
      len(spelling.normalize_ignored([f"w{i}" for i in range(spelling.IGNORE_LIMIT + 50)]))
      == spelling.IGNORE_LIMIT)

# --- several languages ----------------------------------------------------
check("a range is wrong only if every dictionary calls it wrong",
      spelling.line_errors([[(0, 5), (10, 3)], [(10, 3), (20, 4)]]) == [(10, 3)])
check("...one dictionary's answer is its own",
      spelling.line_errors([[(4, 2), (0, 3)]]) == [(0, 3), (4, 2)])
check("...and no dictionary at all reports nothing",
      spelling.line_errors([]) == [])

# --- another language is left alone --------------------------------------
# German, standing for any language the computer has no dictionary for: an
# English dictionary flags most of its words.
import re


def _unknown(text, known):
    """What a dictionary that knows only *known* calls wrong in *text*."""
    return [(m.start(), len(m.group())) for m in re.finditer(r"[^\W\d_]+", text)
            if m.group() not in known]


_de = ("Morgen fr\u00fch gehen wir auf den Markt und kaufen frisches "
       "Gem\u00fcse f\u00fcr die Suppe am Sonntag")
_de_errors = _unknown(_de, {"am", "die", "den", "Markt"})
check("a paragraph where most words are unknown shows nothing",
      spelling.visible_errors([_de], [_de_errors]) == {})
_en = "I recieve teh letters every Tuesday and the meeting is at noon"
_en_errors = [(2, 7), (10, 3)]
check("an English paragraph with two typos shows both",
      spelling.visible_errors([_en], [_en_errors]) == {0: [(2, 7), (10, 3)]})
check("...in a note that also holds a paragraph in another language, which "
      "shows nothing",
      spelling.visible_errors([_en, _de], [_en_errors, _de_errors]) == {0: [(2, 7), (10, 3)]})
_list = ["Milch", "Brot", "Eier", "Kaffee", "\u00c4pfel", "K\u00e4se"]
check("a note of short lines in another language is judged whole, and shows "
      "nothing",
      spelling.visible_errors(_list, [[(0, len(w))] for w in _list]) == {})
check("...while one foreign word in a short English line is underlined",
      spelling.visible_errors(["Buy milk and Brot", "Call Ana tomorrow morning please"],
                              [[(13, 4)], []]) == {0: [(13, 4)]})
# Sentence by sentence: an English sentence beside a German one keeps its typo
# underlined, though the paragraph -- here the whole note -- is mostly unknown
# words.
_mix = ("I recieve the letters every day. Morgen früh gehen wir auf den Markt "
        "und kaufen Gemüse am Sonntag.")
_mix_errors = _unknown(_mix, {"I", "the", "letters", "every", "day", "den", "am"})
check("a paragraph of mostly unknown words still shows the typo in its English "
      "sentence, and nothing in its German one",
      spelling.is_foreign(spelling.word_count(_mix), len(_mix_errors))
      and spelling.visible_errors([_mix], [_mix_errors]) == {0: [(2, 7)]})
check("...and so does a note of two such paragraphs",
      spelling.visible_errors([_mix, _de], [_mix_errors, _de_errors]) == {0: [(2, 7)]})
# The note around it is mostly English, so only the paragraph can say that
# "Ja." is not English.
_ja = "Ja. Morgen gehen wir auf den Markt."
check("a sentence too short to judge takes its paragraph's verdict: quiet in a "
      "German paragraph",
      spelling.visible_errors([_ja, _en], [_unknown(_ja, ()), _en_errors])
      == {1: [(2, 7), (10, 3)]})
check("...and shown in an English one",
      spelling.visible_errors(["Teh. I bought the bread and the milk today."],
                              [[(0, 3)]]) == {0: [(0, 3)]})
check("a line's sentences cover the whole of it, in UTF-16 units",
      spelling.sentence_spans("One two. Three \U0001F389 four! Five")
      == [(0, 8), (8, 23), (23, 28)])
check("...and a line with no sentence end is one sentence",
      spelling.sentence_spans("no full stop here") == [(0, 17)])
check("...and a run of ends is one end, only with a space or the line's end after it",
      spelling.sentence_spans("e.g. this... and that?!x end…")
      == [(0, 4), (4, 12), (12, 29)])
# A run of ends with no space after it was tried at each of its dots: 24,000
# took 4.5 s at every look the editor takes (round 9). Timed in this run
# against the same run with a space after it, the quickest of three each.
import gc as _gc
import time as _time


def _quickest(fn, *args):
    """The quickest of three calls, in seconds."""
    best = None
    for _ in range(3):
        _gc.collect()
        started = _time.perf_counter()
        fn(*args)
        took = _time.perf_counter() - started
        best = took if best is None else min(best, took)
    return best


_se_run = _quickest(spelling.sentence_spans, "xqzt" + "." * 12000 + "zqtx")
_se_ended = _quickest(spelling.sentence_spans, "xqzt" + "." * 12000 + " zqtx")
check("a run of 12,000 dots with no space after it takes what the same run ending "
      "a sentence takes (%.1f ms against %.1f ms)" % (_se_run * 1000, _se_ended * 1000),
      _se_run < 4 * _se_ended + 0.25)

# Each range goes to its sentence, in the order it came, with an emoji before
# it counted two units; a range outside the line is no one's.
_vo_line = "Teh \U0001F389 cat sat on the mat. Xqzt the brede and the milk was fresh today! Zorp"
check("a line's ranges are shown sentence by sentence, each sentence's in the order "
      "they came, a repeated one twice, one outside the line not at all",
      spelling.visible_errors([_vo_line], [[(36, 5), (27, 4), (36, 5), (-1, 2), (79, 2),
                                            (72, 4), (0, 3)]])
      == {0: [(0, 3), (36, 5), (27, 4), (36, 5), (72, 4)]})
# A look measured the line again for each sentence and walked every range for
# each: 358 ms at 24,000 characters, four times that for twice the line, at
# every pause in typing (round 9). Timed against the line's half, in one run.
_vo_long = "xqzt. " * (80_000 // 6)
_vo_half = "xqzt. " * (40_000 // 6)
_vo_long_s = _quickest(spelling.visible_errors, [_vo_long],
                       [[(i * 6, 4) for i in range(len(_vo_long) // 6)]])
_vo_half_s = _quickest(spelling.visible_errors, [_vo_half],
                       [[(i * 6, 4) for i in range(len(_vo_half) // 6)]])
check("a line of 80,000 characters of short misspelled sentences takes twice what "
      "its half takes, not four times (%.1f ms against %.1f ms)"
      % (_vo_long_s * 1000, _vo_half_s * 1000),
      _vo_long_s < 2.6 * _vo_half_s + 0.005)
check("a line not checked at all (a table row) counts for nothing",
      spelling.visible_errors(["| a | b |", _en], [None, _en_errors]) == {1: [(2, 7), (10, 3)]})
check("the judgement is in words, not in characters: three short unknown words "
      "in a line of three are not judged on their own",
      not spelling.is_foreign(3, 3) and spelling.is_foreign(4, 3)
      and not spelling.is_foreign(4, 2))
check("worth_flagging still applies in a paragraph that is shown",
      spelling.visible_errors(["Send the PDF tommorow to the team today"],
                              [[(9, 3), (13, 8)]]) == {0: [(13, 8)]})

# --- a very long line, asked about in pieces -----------------------------
_long = ("word " * 30).strip() + " \U0001F389 " + ("more " * 30).strip()
_parts = spelling.pieces(_long, 40)
check("a long line is cut into pieces no longer than asked",
      all(spelling.utf16_units(p) <= 40 for _o, p in _parts) and len(_parts) > 3)
check("...which put back together are the line",
      "".join(p for _o, p in _parts) == _long)
check("...each cut after a space, so no word is split",
      all(p.endswith(" ") for _o, p in _parts[:-1]))
check("...and each piece's offset is where it starts, in units",
      all(spelling.utf16_slice(_long, o, spelling.utf16_units(p)) == p for o, p in _parts))
check("a short line is one piece at 0", spelling.pieces("short line") == [(0, "short line")])
check("an empty line is no piece", spelling.pieces("") == [])

# --- the word being typed -------------------------------------------------
check("the caret anywhere in a range, or at either end, is that range",
      spelling.range_at([(4, 3)], 4) == (4, 3) and spelling.range_at([(4, 3)], 7) == (4, 3)
      and spelling.range_at([(4, 3)], 5) == (4, 3))
check("...and away from it, none", spelling.range_at([(4, 3)], 8) is None
      and spelling.range_at([(4, 3)], 3) is None)

# --- one dictionary per language -----------------------------------------
_en19 = ["en-029", "en-AU", "en-CA", "en-GB", "en-IN", "en-US", "en-ZA"]
check("nineteen kinds of English give one dictionary, en-US when the person "
      "names none", spelling.pick_languages(_en19) == ["en-US"])
check("...the person's own kind of English when they name it",
      spelling.pick_languages(_en19, ["en-GB"]) == ["en-GB"])
check("the person's languages come first, the others after",
      spelling.pick_languages(_en19 + ["ro-RO", "de-DE", "de-AT"], ["ro-RO", "en-US"])
      == ["ro-RO", "en-US", "de-DE"])
check("a language is checked in its own country's form when the person's is "
      "not installed", spelling.pick_languages(["de-AT", "de-DE"], ["de-CH"]) == ["de-DE"])
check("...Portugal's Portuguese when nothing else says which",
      spelling.pick_languages(["pt-BR", "pt-PT"]) == ["pt-PT"])
check("...and the first Windows lists when the language has no such country",
      spelling.pick_languages(["es-MX", "es-AR"]) == ["es-MX"])
check("no dictionaries, nothing picked", spelling.pick_languages([], ["en-US"]) == [])


print()
print(f"FAILURES: {fails if fails else 'none'}")

import sys
sys.exit(1 if fails else 0)
