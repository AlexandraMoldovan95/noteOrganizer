"""Repeating notes: the rules, and working out which dates they land on.

WHAT THIS MODULE IS FOR
-----------------------
A note can repeat — daily, weekly, monthly, yearly — and the calendar
needs to know which days it appears on. This module owns that.

The central idea, and the reason the app scales at all:

    **A recurring note is stored exactly ONCE.**

Its occurrences are *computed on demand* for whatever date range is being
displayed, and never written to the notes file. A note repeating daily
since 1990 is still one entry on disk. If occurrences were saved instead,
the file would grow without limit and "edit the series" would mean
rewriting thousands of records.

Four fields on a note describe the whole thing:

===================== ======================================================
``note["date"]``      the series anchor — the day it starts
``note["recurrence"]``the rule (see :data:`RECURRENCE_DEFAULTS`)
``note["exceptions"]``dates the user deleted individually
``note["overrides"]`` per-date content edits, keyed by date string
===================== ======================================================

WHAT'S EXPORTED
---------------
* :func:`normalize_recurrence` — force any stored rule into a safe shape.
* :func:`expand_occurrences` — the main event: rule + date range → dates.
* :func:`is_recurring`, :func:`describe_recurrence` — small helpers the UI
  uses for labels and checks.
* :func:`effective_note` — a note as it appears on one specific day, with
  that day's override applied.
* :func:`parse_date` / :func:`format_date` — the app's date-string
  convention (``YYYY-MM-DD``) in one place.
* :func:`read_date` / :func:`show_date` — dates as people write them
  (17.10.2026, 17 octombrie 2026) and the one form the app shows them in;
  the store keeps ``YYYY-MM-DD`` whatever was typed.

IDEAS WORTH TAKING AWAY
-----------------------
**Normalising input at the edge.** :func:`normalize_recurrence` never
raises and never returns something odd. Hand it ``None``, a string, a dict
with ``interval`` set to ``"banana"`` — it returns a valid rule, degrading
to "does not repeat" if it must. Everything downstream can then assume the
shape is correct, instead of every function re-checking. This is the same
pattern ``normalize_note()`` uses for notes, and it's why one corrupt
entry can't take down the calendar.

**Guard rails on loops that compute rather than iterate.** Each branch of
:func:`expand_occurrences` loops until it passes the horizon — but also
counts iterations against :data:`MAX_OCCURRENCES`. If a rule were ever
malformed in a way that stopped the date advancing, the guard ends the
loop instead of hanging the app. When a loop's end condition depends on
computed data, a bound is cheap insurance.

**Skip ahead instead of walking.** For an unlimited rule the code jumps
straight to the visible window with arithmetic rather than stepping day by
day from the anchor::

    skipped = (range_start - anchor).days // interval
    current = anchor + step * skipped

A daily note anchored in 1990 costs the same to display in 2026 as one
created last week. There's a test pinning this: a 36-year-old yearly
recurrence resolves in well under a millisecond.

**Why ``nonlocal``.** The inner ``take()`` function updates ``produced``
in the enclosing function. Assigning to a name inside a nested function
would normally create a *new local* variable; ``nonlocal produced`` says
"no, update the outer one". (The calculator module solves the same problem
a different way, with a one-item list — both are common.)
"""

import calendar as cal_module
import re
import unicodedata
from datetime import datetime, date as date_cls, timedelta

__all__ = [
    "WEEKDAY_NAMES",
    "FREQ_LABELS",
    "RECURRENCE_DEFAULTS",
    "OVERRIDABLE_FIELDS",
    "MAX_OCCURRENCES",
    "MAX_RECURRENCE_INTERVAL",
    "parse_date",
    "format_date",
    "DATE_FORM",
    "read_date",
    "show_date",
    "show_stamp",
    "show_day",
    "same_date",
    "normalize_recurrence",
    "is_recurring",
    "expand_occurrences",
    "next_occurrence_on_or_after",
    "history_entries",
    "effective_note",
    "day_matches_series",
    "moved_from",
    "drawn_moves",
    "move_day",
    "off_schedule_days",
    "describe_recurrence",
]

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

FREQ_LABELS = {
    "": "Does not repeat",
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}

RECURRENCE_DEFAULTS = {
    "freq": "",               # "" means this is a normal one-off note
    "interval": 1,            # every N days / weeks / months / years
    "weekdays": [],           # weekly only: 0=Mon .. 6=Sun
    "month_days": [],         # monthly only: 1..31
    "month_day_policy": "clamp",   # "clamp" -> Feb 28/29, "skip" -> no occurrence
    "end": "",                # "" = never ends
    "count": 0,               # 0 = unlimited; otherwise stop after N occurrences
}

# Fields a per-occurrence override is allowed to replace.
OVERRIDABLE_FIELDS = ["title", "body", "comments", "category", "color"]

# Safety valve: no rule may ever generate more than this in one expansion.
MAX_OCCURRENCES = 5000

# Upper bound on a rule's interval ("every N days/weeks/months/years").
# 1000 is already beyond any real use — every 1000 years — while staying
# far below the point where timedelta(days=interval) overflows (its
# ceiling is 999,999,999 days). Without this cap, a hostile share code
# or a hand-edited notes_data.json carrying interval=1e10 crashed
# expand_occurrences with OverflowError — and since the calendar renders
# at startup, that could make the app unlaunchable (see ISSUES_LOG).
MAX_RECURRENCE_INTERVAL = 1000


def parse_date(value):
    """'2026-07-24' -> date object, or None if it isn't a valid date.

    Returning ``None`` rather than raising is deliberate: dates arrive
    from stored files and from things the user typed, so "not a date" is
    an ordinary case to handle, not an error.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def format_date(d):
    """A date object -> the 'YYYY-MM-DD' string form used everywhere."""
    return d.strftime("%Y-%m-%d")


# ---- Dates as people write them, and as the app shows them ----
#
# The files keep one form, YYYY-MM-DD (parse_date and format_date above).
# People write a date in many: the day first, with dots, slashes or dashes;
# the year first; the month as a word, in English or in Romanian. read_date
# understands those, and show_date is the one form a date is shown in. What
# reaches a note goes through format_date, so the store never learns there
# was a choice. In figures the day comes first, as the field's own form
# asks, and the month first only where the day first cannot be: 10/17/2026
# is October 17th, the American way, while 10/12/2026 is the tenth of
# December, never the twelfth of October.

#: What the empty date field shows: the order a typed date is read in.
DATE_FORM = "DD.MM.YYYY"

# The month names a typed date may use, in English and in Romanian. The
# Romanian ones are the only Romanian in this repository, kept by agreement
# for exactly this: they are read, never shown (tools/check_english.py says
# so as well). None of them carries a diacritic, and typed ones are folded
# away regardless. A word names a month when it is a whole name or the
# start of one, three letters at least, and every name it starts agrees on
# the month: "oct", "octom" and "October" all do, "ma" does not.
_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4, "mai": 5,
    "iunie": 6, "iulie": 7, "septembrie": 9, "octombrie": 10,
    "noiembrie": 11, "decembrie": 12,
}

# Written-out English names, kept here rather than taken from strftime, so
# the language Windows is set to never changes what the app says.
_LONG_MONTHS = ("January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November",
                "December")
_LONG_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
              "Saturday", "Sunday")

# The English day names a written-out date may carry ("Saturday, October
# 17, 2026", "Sat, Oct 17"): read, and set aside -- the figures say which
# day it is. A word names a weekday as a word names a month: a whole name or
# the start of one, three letters at least.
_WEEKDAY_NAMES = tuple(day.casefold() for day in _LONG_DAYS)
# Words English sets around a date that say nothing about which day it is:
# "the 17th of October".
_DATE_FILLERS = ("the", "of")

# A typed date: figures and words, with spaces, dots, slashes, dashes or
# commas between them -- and nothing else. Figures are 0-9 only: digits of
# another script are not a date, and int() would read them as one. Checked
# by taking the allowed runs away and seeing whether anything is left: one
# pass, each run taken whole. A single pattern for the whole shape needs a
# repeated group of repeated runs, and that is the form which backtracks
# without end on thirty figures and a stray symbol -- in the field's own
# keystroke, on the app's one thread.
# A day may carry its ordinal ending, "17th", "1st": one part, the figures
# kept. The ending is taken only straight after one or two figures.
_DATE_PART = re.compile(r"[0-9]{1,2}(?:st|nd|rd|th)|[0-9]+|[^\W\d_]+",
                        re.IGNORECASE)
_DATE_RUNS = re.compile(r"[0-9]+|[^\W\d_]+|[\s./,\-]+")
_DATE_FIGURES = re.compile(r"[0-9]+")
# Far longer than any date anyone writes ("17 septembrie 2026" is 18).
_DATE_MAX_CHARS = 40


def _fold(word):
    """*word* without case or diacritics, for comparing with a name."""
    return "".join(c for c in unicodedata.normalize("NFKD", word)
                   if not unicodedata.combining(c)).casefold()


def _names_started_by(word, names):
    """The *names* that *word* is, or starts -- three letters at least."""
    folded = _fold(word)
    if len(folded) < 3:
        return []
    return [name for name in names if name.startswith(folded)]


def _month_from_word(word):
    """The month *word* names, or None (see _MONTH_NAMES)."""
    months = {_MONTH_NAMES[name]
              for name in _names_started_by(word, _MONTH_NAMES)}
    return months.pop() if len(months) == 1 else None


def read_date(text, settled=False, today=None):
    """A date as a person writes it -> date object, or None.

    Read: 17.10.2026, 17/10/2026, 17-10-2026 (the day first, one or two
    figures for the day and the month -- and the month first only where the
    day first cannot be, so 10/17/2026 is October 17th while 10/12/2026 is
    the tenth of December); 2026-10-17 (four figures first mean the year
    comes first); and the month as a word, before or after the day -- 17
    oct 2026, 17 octombrie 2026, October 17, 2026. English trimmings are
    read and set aside: a day name ("Saturday, October 17, 2026"), an
    ordinal ending ("October 17th"), "the" and "of" ("the 17th of October").

    *settled*: the person has finished with the field (left it, saved,
    left the note). Only then is a short year read as this century's
    (17.10.26) and a missing one as this year's (17.10, 17 oct): read while
    someone is still typing, "17.10.20" on its way to 2026 would be saved
    as 2020. *today* is injectable for tests.
    """
    if not isinstance(text, str):
        return None
    text = text.strip()
    if (not text or len(text) > _DATE_MAX_CHARS
            or _DATE_RUNS.sub("", text)):
        return None
    numbers = []
    words = []
    weekdays = 0
    for part in _DATE_PART.findall(text):
        # A figure from 0 to 9 only: str.isdigit() also passes "²", "①" and
        # "₂", which the patterns above take for letters, so "17²" reached
        # the match below, found no figure there, and raised -- and with it
        # in the date field, every autosave of the note.
        if part[0] in "0123456789":
            numbers.append(_DATE_FIGURES.match(part).group())
        elif _fold(part) in _DATE_FILLERS:
            continue
        # No three letters start both a day's name and a month's, in either
        # language, so a word is one or the other, never both.
        elif len(set(_names_started_by(part, _WEEKDAY_NAMES))) == 1:
            weekdays += 1
        else:
            words.append(part)
    if weekdays > 1:
        return None

    def year_of(figures):
        if len(figures) == 4 and figures[0] != "0":
            return int(figures)
        if len(figures) == 2 and settled:
            return 2000 + int(figures)
        return None

    def this_year():
        return (today or date_cls.today()).year if settled else None

    if not words:
        if len(numbers) == 3 and len(numbers[0]) == 4:
            year, month, day = year_of(numbers[0]), numbers[1], numbers[2]
        elif len(numbers) in (2, 3):
            first, second = numbers[0], numbers[1]
            year = year_of(numbers[2]) if len(numbers) == 3 else this_year()
            # The day first, as the field's form asks; the month first only
            # where the day first cannot be -- a second figure past 12 is no
            # month, so 10/17/2026 is October 17th, written the American
            # way. 10/12/2026 stays the tenth of December.
            if (len(first) <= 2 and len(second) <= 2
                    and int(second) > 12 >= int(first)):
                day, month = second, first
            else:
                day, month = first, second
        else:
            return None
        if len(day) > 2 or len(month) > 2:
            return None
        month = int(month)
    elif len(words) == 1:
        month = _month_from_word(words[0])
        if month is None:
            return None
        if len(numbers) == 2:
            # The year is the figure written as one -- four figures -- and
            # where both are short, the second: "17 oct 26".
            if len(numbers[0]) == 4:
                year, day = year_of(numbers[0]), numbers[1]
            elif len(numbers[1]) == 4:
                day, year = numbers[0], year_of(numbers[1])
            else:
                day, year = numbers[0], year_of(numbers[1])
        elif len(numbers) == 1:
            day, year = numbers[0], this_year()
        else:
            return None
        if len(day) > 2:
            return None
    else:
        return None
    if year is None:
        return None
    try:
        return date_cls(year, month, int(day))
    except ValueError:
        return None


def show_date(value):
    """A stored date as the app shows it: 2026-10-17 -> 17.10.2026.

    Anything that is not a stored date -- empty, or text the app cannot
    read, which a field may carry as it was typed -- comes back as it was.
    """
    if not isinstance(value, str):
        return ""
    d = parse_date(value)
    if d is None:
        return value
    return "%02d.%02d.%04d" % (d.day, d.month, d.year)


def show_stamp(value):
    """A stored moment as the app shows it: 2026-10-17 09:30 -> 17.10.2026
    09:30. The date part is shown as show_date shows a date; the rest is
    kept as it is."""
    if not isinstance(value, str):
        return ""
    head, gap, rest = value.partition(" ")
    return show_date(head) + gap + rest


def show_day(d, year=True, short_month=False):
    """A day written out, the day first: Saturday, 3 October 2026."""
    month = _LONG_MONTHS[d.month - 1]
    if short_month:
        month = month[:3]
    text = "%s, %d %s" % (_LONG_DAYS[d.weekday()], d.day, month)
    return text + (" %d" % d.year if year else "")


def same_date(a, b):
    """Whether two date texts name the same day, or are the same text.

    The date field shows 17.10.2026 where the note stores 2026-10-17; asked
    as text, every dated note would read as changed the moment it opened.
    """
    a = a.strip() if isinstance(a, str) else ""
    b = b.strip() if isinstance(b, str) else ""
    if a == b:
        return True
    first, second = read_date(a), read_date(b)
    return first is not None and first == second


def normalize_recurrence(rec):
    """Coerce a recurrence rule into a known-good shape. Anything unexpected
    degrades to 'does not repeat' rather than crashing the calendar.

    Every field is checked independently, so one bad value doesn't discard
    the rest of an otherwise valid rule.

    Args:
        rec: Whatever was stored on the note. Any type is accepted.

    Returns:
        A dict with exactly the keys of :data:`RECURRENCE_DEFAULTS`.
    """
    out = dict(RECURRENCE_DEFAULTS)
    # The defaults dict holds shared list objects; give this rule its own
    # so writing to one note's weekdays can never affect another's.
    out["weekdays"] = []
    out["month_days"] = []
    if not isinstance(rec, dict):
        return out

    freq = rec.get("freq", "")
    out["freq"] = freq if freq in ("daily", "weekly", "monthly", "yearly") else ""

    try:
        # Clamped BOTH ways: below at 1 (a zero/negative interval would
        # loop or divide by zero downstream), above at
        # MAX_RECURRENCE_INTERVAL (an unbounded value overflowed
        # timedelta and crashed the calendar — the choke point that
        # protects every route: load, share/zip import, hand-edit, UI).
        out["interval"] = max(1, min(int(rec.get("interval", 1)),
                                     MAX_RECURRENCE_INTERVAL))
    except (TypeError, ValueError, OverflowError):
        # OverflowError: JSON's 1e999 reads as infinity, and int() of it
        # stopped the app at every start (ISSUES_LOG: "The number too big to start").
        out["interval"] = 1

    weekdays = rec.get("weekdays", [])
    if isinstance(weekdays, list):
        # set() removes duplicates, sorted() gives a predictable order.
        out["weekdays"] = sorted({d for d in weekdays if isinstance(d, int) and 0 <= d <= 6})

    month_days = rec.get("month_days", [])
    if isinstance(month_days, list):
        out["month_days"] = sorted({d for d in month_days if isinstance(d, int) and 1 <= d <= 31})

    policy = rec.get("month_day_policy", "clamp")
    out["month_day_policy"] = policy if policy in ("clamp", "skip") else "clamp"

    # Read as a typed date is read: an end written day first -- by an older
    # share code, a hand edit, the end-date box -- is that end, not "never
    # ends". Stored in the one form, whatever form it came in.
    end_day = read_date(rec.get("end", ""))
    out["end"] = format_date(end_day) if end_day else ""

    try:
        # Clamped above at MAX_OCCURRENCES too (0 = unlimited): a rule can
        # never produce more occurrences than that anyway, so a crafted
        # huge count is meaningless — same both-sides discipline as the
        # interval clamp, no asymmetry left in this validator.
        out["count"] = max(0, min(int(rec.get("count", 0)), MAX_OCCURRENCES))
    except (TypeError, ValueError, OverflowError):
        out["count"] = 0

    return out


def is_recurring(note):
    """True if this note repeats at all.

    The type check is not belt-and-braces. This used to read
    ``(note.get("recurrence") or {}).get("freq")``, which is safe for a
    note that has been through :func:`normalize_note` and fatal for one
    that has not: a ``recurrence`` holding a string is truthy, and
    ``.get`` on a string raises. Live notes are normalised on load;
    TRASH entries are not -- ``load_trash`` returns each entry as the file
    held it -- so the first caller to ask a trashed note whether it repeats
    would have taken the whole Trash panel down with it. Found by a
    check written for exactly that, the day such a caller appeared.
    """
    recurrence = note.get("recurrence")
    return bool(isinstance(recurrence, dict) and recurrence.get("freq"))


def _shift_month(year, month, months_to_add):
    """Move a (year, month) pair forward by N months, rolling the year.

    Months are converted to a single running count so the arithmetic is
    one line and there's no wrap-around special case to get wrong.
    """
    total = (year * 12 + (month - 1)) + months_to_add
    return total // 12, (total % 12) + 1


def _day_in_month(year, month, wanted_day, policy):
    """Resolve 'the 31st' inside a month that may not have one.

    ``policy`` is ``"clamp"`` (use the last day that exists — so the 31st
    becomes Feb 28) or ``"skip"`` (no occurrence that month at all).
    Returns a date, or ``None`` when skipping.
    """
    last_day = cal_module.monthrange(year, month)[1]
    if wanted_day <= last_day:
        return date_cls(year, month, wanted_day)
    if policy == "clamp":
        return date_cls(year, month, last_day)
    return None  # "skip"


def _moves(note):
    """A repeating note's days held on other dates, as stored: the date the
    rule gives each one, mapped to the date it is on ("Move this day")."""
    moved = note.get("moved") if is_recurring(note) else None
    return moved if isinstance(moved, dict) else {}


def expand_occurrences(note, range_start, range_end, limit=None):
    """Every date this note lands on between range_start and range_end
    (inclusive), as 'YYYY-MM-DD' strings. Exceptions are already removed,
    and a day moved to another date is drawn there instead.

    This is the heart of the module, and the one place a series' days are
    worked out: the calendar, the History, the sort by next day and the
    days off the schedule all ask it, so a moved day is moved everywhere.

    Args:
        note: The note dict, providing its date, rule, exceptions and moves.
        range_start: First date of interest (a ``date`` object).
        range_end: Last date of interest, inclusive.
        limit: Stop once this many dates are found -- the first ones, in
            order. For a caller asking "more than fifty?", which needs
            fifty-one and not a decade of them.

    Returns:
        A sorted list of date strings. Empty if the note has no valid
        anchor date, or simply doesn't occur in this range.
    """
    moved = _moves(note)
    # The rule's own days, less the ones moved away: each still counts as
    # one of a "10 times" series' ten, wherever it is held.
    dates = _expand_rule(note, range_start, range_end, limit, set(moved))
    if not moved:
        return dates
    # ...and each moved day on its new date, while the day it was moved from
    # is still one the rule gives and was not deleted: a move outlives
    # neither. The new date may lie past the rule's end or before its start;
    # the person chose it.
    exceptions = set(note.get("exceptions") or [])
    here = []
    for orig, new in moved.items():
        day = parse_date(new) if isinstance(new, str) else None
        if (day is not None and orig not in exceptions
                and range_start <= day <= range_end):
            here.append((orig, new))
    if not here:
        return dates
    # Whether the rule still gives each day is asked of all of them at once:
    # asked one by one, a series that stops after N times walked from its
    # first day for every moved day in the range (_rule_days_among).
    gives = _rule_days_among(note, [orig for orig, _new in here])
    drawn = set(dates)
    for orig, new in here:
        if new in drawn or orig not in gives:
            continue
        dates.append(new)
        drawn.add(new)
    dates.sort()
    return dates[:limit] if limit is not None else dates


def _rule_days_among(note, days):
    """Which of *days* -- date strings -- the note's rule itself gives, its
    deleted and moved days aside: ``_expand_rule(note, d, d) == [d]`` for
    every *d* of them, asked in one go.

    Asked one day at a time, the question re-read the whole series each
    time, and the callers asked it once for every moved or edited day: a
    series holding 5,000 moved days took a minute and a half to open, at
    every launch while it was the note last open (ISSUES_LOG: "Limits that
    held at the door but not after it"). The answer is the same; only the
    asking changed:

    * a rule with no count jumps straight to the day asked
      (:func:`_expand_rule`), so each day costs the same whatever the span
      -- they are asked one by one, with nothing re-read between them;
    * a rule that stops after N times is walked from its first day whatever
      is asked, so it is walked ONCE, over the span of every day asked: the
      walk each single question took, up to each day, bounded by its N.

    A spelling of a date other than ``YYYY-MM-DD`` is never a day the rule
    gives, as it never equalled what the rule wrote.
    """
    wanted = {}
    for text in days:
        when = parse_date(text) if isinstance(text, str) else None
        if when is not None:
            wanted.setdefault(when, []).append(text)
    if not wanted:
        return set()
    # Deleted days are the caller's to judge; the rule's days are asked here.
    bare = dict(note, exceptions=[])
    if normalize_recurrence(note.get("recurrence"))["count"] > 0:
        hits = set(_expand_rule(bare, min(wanted), max(wanted)))
    else:
        hits = set()
        for when in wanted:
            hits.update(_expand_rule(bare, when, when))
    return {text for texts in wanted.values() for text in texts
            if text in hits}


def _drawn_on_days(note, whens):
    """``{d: expand_occurrences(note, d, d)}`` for every date *d* in
    *whens*, worked out at once: the rule asked once for all of them
    (_rule_days_among), and the moved days read once, not once per date.
    For a question asked about many single days -- which days show a moved
    day, which edited days the schedule still reaches."""
    whens = set(whens)
    if not whens:
        return {}
    moved = _moves(note)
    exceptions = set(note.get("exceptions") or [])
    own = {when: format_date(when) for when in whens}
    candidates = []
    if moved:
        for orig, new in moved.items():
            day = parse_date(new) if isinstance(new, str) else None
            if day in whens and orig not in exceptions:
                candidates.append((orig, new, day))
    gives = _rule_days_among(
        note, list(own.values()) + [orig for orig, _new, _day in candidates])
    out, seen = {}, {}
    for when, text in own.items():
        # The rule's own day, unless deleted or moved away (expand_occurrences
        # skips both).
        mine = ([text] if text in gives and text not in exceptions
                and text not in moved else [])
        out[when], seen[when] = mine, set(mine)
    # ...then each moved day held there, in the order expand_occurrences
    # takes them, once per spelling.
    for orig, new, day in candidates:
        if orig in gives and new not in seen[day]:
            out[day].append(new)
            seen[day].add(new)
    for days in out.values():
        days.sort()
    return out


def drawn_moves(note):
    """The series' moved days whose date shows that day, as ``(date the
    rule gives it, date it is on)`` pairs in the note's order.

    The question the editor's banner ("5 days moved") and the History ask of
    each moved day -- does the calendar, asked about its new date, show
    exactly it -- asked of all of them at once (_drawn_on_days). Asked one
    day at a time, each question read every moved day of the series.
    """
    moved = _moves(note)
    if not moved:
        return []
    pairs = [(orig, new, parse_date(new) if isinstance(new, str) else None)
             for orig, new in moved.items()]
    shown = _drawn_on_days(note, [day for _o, _n, day in pairs
                                  if day is not None])
    # One a date, the move moved_from names: two onto one date were listed
    # twice in History (the phone's list threw on the twin key, round 19).
    came = _moved_from_map(note)
    return [(orig, new) for orig, new, day in pairs
            if day is not None and shown[day] == [new] and came.get(new) == orig]


def _moved_from_map(note):
    """:func:`moved_from` for every date at once: ``{date: date it came
    from}``, the first move wins as there."""
    came = {}
    for orig, new in _moves(note).items():
        came.setdefault(new, orig)
    return came


def moved_from(note, day):
    """The date the series' day now on *day* was moved from, or None when
    *day* holds no moved day of *note*."""
    for orig, new in _moves(note).items():
        if new == day:
            return orig
    return None


def move_day(note, day, to):
    """Hold the series' day that is drawn on *day* on *to* instead.

    The move is recorded against the date the rule gives the day -- and
    dropped, when *to* is that date: the day is home again. The day's own
    edit goes with it, kept under the date it is drawn on, so everything
    that opens a day by its date opens this one. The caller has made sure
    *to* holds no other day of the series (:func:`expand_occurrences`).

    Returns:
        The date the rule gives the day.
    """
    moved = note.get("moved")
    if not isinstance(moved, dict):
        moved = note["moved"] = {}
    orig = moved_from(note, day) or day
    # Another move onto *to*, which the caller found free, is a dead one --
    # its own date no longer the rule's -- and goes: two moves onto one date
    # were read as the dead one, and the next read kept only one (round 17).
    for dead in [other for other, new in moved.items() if new == to and other != orig]:
        del moved[dead]
    if to == orig:
        moved.pop(orig, None)
    else:
        moved[orig] = to
    overrides = note.get("overrides")
    if isinstance(overrides, dict) and day in overrides and to != day:
        overrides[to] = overrides.pop(day)
    return orig


def _expand_rule(note, range_start, range_end, limit=None, skip=()):
    """The dates *note*'s rule gives between range_start and range_end, less
    its exceptions and the dates in *skip* -- which still count towards a
    "stop after N times". One branch per frequency, each walking forward
    from the anchor and calling the shared ``take()`` below to record a hit
    and decide whether to keep going. See :func:`expand_occurrences`, which
    adds the moved days."""
    anchor = parse_date(note.get("date", ""))
    if anchor is None:
        return []

    rec = normalize_recurrence(note.get("recurrence"))
    exceptions = set(note.get("exceptions") or []) | set(skip)

    if not rec["freq"]:
        # The note's own deleted days belong to the series it was: a turned-off
        # series whose first day was deleted fell off the calendar.
        one_off = format_date(anchor)
        if range_start <= anchor <= range_end and one_off not in set(skip):
            return [one_off]
        return []

    interval = rec["interval"]
    end_date = parse_date(rec["end"])
    max_count = rec["count"]
    policy = rec["month_day_policy"]

    # Hard stop for the whole expansion: never look past the requested range,
    # and never past the rule's own end date.
    horizon = range_end if end_date is None else min(range_end, end_date)
    if horizon < anchor:
        return []

    results = []
    produced = 0          # counts occurrences from the anchor, for "count"
    limited = max_count > 0

    def take(candidate):
        """Record one occurrence. Returns False when the rule is exhausted.

        Note it counts EVERY occurrence since the anchor (for "stop after
        N times"), but only collects the ones inside the visible range --
        each formatted once, here, where a skipped day is also told apart.
        """
        nonlocal produced
        if candidate < anchor:
            return True
        if end_date is not None and candidate > end_date:
            return False
        produced += 1
        if range_start <= candidate <= range_end:
            text = format_date(candidate)
            if text not in exceptions:
                results.append((candidate, text))
                if limit is not None and len(results) >= limit:
                    return False
        if limited and produced >= max_count:
            return False
        return True

    if rec["freq"] == "daily":
        step = timedelta(days=interval)
        current = anchor
        # With no count limit we can jump straight to the visible window
        # instead of walking every day since the anchor.
        if not limited and range_start > anchor:
            skipped = (range_start - anchor).days // interval
            current = anchor + step * skipped
        guard = 0
        while current <= horizon and guard < MAX_OCCURRENCES:
            guard += 1
            if not take(current):
                break
            # Measured before stepping, because the step past the horizon
            # is the one a date may be unable to take: from 9999-12-31 it
            # raised OverflowError, and December 9999 failed to draw.
            if horizon - current < step:
                break
            current += step

    elif rec["freq"] == "weekly":
        # Work in whole weeks from the Monday of the anchor's week, so
        # "every 2 weeks on Mon and Thu" advances predictably.
        weekdays = rec["weekdays"] or [anchor.weekday()]
        anchor_week = anchor - timedelta(days=anchor.weekday())
        week_step = timedelta(weeks=interval)
        week_start = anchor_week
        if not limited and range_start > anchor:
            weeks_ahead = (range_start - anchor_week).days // (7 * interval)
            if weeks_ahead > 0:
                week_start = anchor_week + week_step * weeks_ahead
        guard = 0
        stop = False
        while week_start <= horizon and guard < MAX_OCCURRENCES and not stop:
            guard += 1
            for weekday in weekdays:
                # Measured from the week's Monday rather than added to it:
                # the last week of 9999 has no Saturday or Sunday to add.
                if (horizon - week_start).days < weekday:
                    continue
                candidate = week_start + timedelta(days=weekday)
                if not take(candidate):
                    stop = True
                    break
            if horizon - week_start < week_step:
                break
            week_start += week_step

    elif rec["freq"] == "monthly":
        month_days = rec["month_days"] or [anchor.day]
        step_index = 0
        if not limited and range_start > anchor:
            months_ahead = ((range_start.year - anchor.year) * 12
                            + (range_start.month - anchor.month))
            step_index = max(0, months_ahead // interval)
        guard = 0
        stop = False
        while guard < MAX_OCCURRENCES and not stop:
            guard += 1
            year, month = _shift_month(anchor.year, anchor.month, step_index * interval)
            # Compared as numbers, not as a date: the month after December
            # 9999 has no first day to build ("year 10000 is out of range").
            if (year, month) > (horizon.year, horizon.month):
                break
            # Resolved first, THEN counted: under "clamp", days 29, 30 and
            # 31 all land on Feb 28 -- which is exactly what someone who
            # means "the end of the month" types. Taken one by one, each
            # landing was a separate occurrence: the note showed up four
            # times in one calendar cell, and a "stop after N times" series
            # spent four of its N on a single day and ended months early.
            landed = sorted({
                d for d in (_day_in_month(year, month, wanted, policy)
                            for wanted in month_days)
                if d is not None})
            for candidate in landed:
                if candidate > horizon:
                    continue
                if not take(candidate):
                    stop = True
                    break
            step_index += 1

    elif rec["freq"] == "yearly":
        year_index = 0
        if not limited and range_start.year > anchor.year:
            year_index = max(0, (range_start.year - anchor.year) // interval)
        guard = 0
        while guard < MAX_OCCURRENCES:
            guard += 1
            year = anchor.year + year_index * interval
            if year > horizon.year:
                break
            # Feb 29 anchors go through the same clamp/skip policy as
            # "the 31st" does for monthly rules.
            candidate = _day_in_month(year, anchor.month, anchor.day, policy)
            if candidate is not None:
                if candidate > horizon:
                    break
                if not take(candidate):
                    break
            year_index += 1

    return [text for _day, text in sorted(results)]


def _history_bucket_of(date_str, today):
    """Which year-filter bucket a date belongs to, relative to *today*."""
    d = parse_date(date_str)
    if d is None:
        return None
    if d.year == today.year:
        return "This year"
    if d.year == today.year - 1:
        return "Last year"
    if d.year == today.year - 2:
        return "2 years ago"
    return "Older"


def _history_match(query, *texts):
    """Case-insensitive substring match across any of *texts* — the same
    plain judgment the sidebar search uses, so the two can't disagree
    about what 'contains' means (and any script matches, diacritics or
    not, exactly as typed)."""
    if not query:
        return True
    q = query.lower()
    return any(q in (t or "").lower() for t in texts)


_UNKNOWN = object()


def history_entries(notes, query="", year_bucket="All", today=None, memo=None):
    """Build the Calendar History listing: the days that carry real
    content, newest first — not every occurrence a rule generates.

    An entry is one of:
      * a dated one-off note, at its own date;
      * a repeating series, as a collapsible group whose children are
        the days edited with "only this occurrence" (their content is
        the override — the only days that stopped tracking the series);
        a series with no such days still gets a row, so it can be found.

    The volume therefore grows with what the user has written, never
    with the passage of time — a decade of a daily series is still one
    group plus its handful of edited days.

    Args:
        notes: the live notes list (read-only here).
        query: substring filter over title/body/comments — and, for a
            series' children, over that day's OWN override content,
            which the sidebar search cannot see. A child match sets
            ``auto_expand`` on its group.
        year_bucket: "All", "This year", "Last year", "2 years ago" or
            "Older".
        today: injectable date for tests; defaults to the real today.
        memo: a dict the caller may keep between calls. What does not
            depend on the query or the year -- a series' days, label and
            next day, whether a date is one, which year bucket it is in --
            is kept there under exactly what it is worked out from (the
            date, the rule, the skipped days, today), so a search keystroke
            only filters, and a changed note simply misses under its new
            key. Read-only to the caller.

    Returns:
        A list of dicts, newest activity first. A dated note:
        ``{"kind": "note", "note_id", "date", "title"}``. A series:
        ``{"kind": "series", "note_id", "title", "freq_label",
        "children": [{"date", "title"} newest-first], "auto_expand"}``.
    """
    if today is None:
        today = date_cls.today()
    if memo is None:
        memo = {}

    def is_date(d):
        found = memo.get(("date", d), _UNKNOWN)
        if found is _UNKNOWN:
            found = memo[("date", d)] = parse_date(d) is not None
        return found

    def bucket_ok(d):
        if year_bucket == "All":
            return True
        found = memo.get(("bucket", d, today), _UNKNOWN)
        if found is _UNKNOWN:
            found = memo[("bucket", d, today)] = _history_bucket_of(d, today)
        return found == year_bucket

    entries = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        title = note.get("title") or ""
        if is_recurring(note):
            exceptions = set(note.get("exceptions") or [])
            overrides = note.get("overrides") or {}
            base_matches = _history_match(
                query, title, note.get("body"), note.get("comments"))

            # What this series costs to work out, kept under what it is
            # worked out from (see `memo`).
            key = ("series", note.get("date") or "",
                   repr(note.get("recurrence")),
                   tuple(note.get("exceptions") or ()),
                   tuple(sorted(_moves(note).items())), today)
            known = memo.get(key)
            if known is None:
                # A BOUNDED, small series lists ALL its occurrences — the
                # field expectation: a "10 times" group opens to its 10
                # days. An unbounded rule would drown the register in
                # identical rows, so it lists only the separately-edited
                # days instead.
                rec = normalize_recurrence(note.get("recurrence"))
                anchor = parse_date(note.get("date") or "")
                occ_days = None
                if anchor is not None:
                    if 0 < rec["count"] <= 50:
                        # A century is room for fifty of anything -- up to
                        # the last day a date can hold, which a series
                        # dated in the 9900s reaches first (the sum itself
                        # overflowed).
                        far = (anchor + timedelta(days=36600)
                               if (date_cls.max - anchor).days >= 36600
                               else date_cls.max)
                        occ_days = expand_occurrences(note, anchor, far)
                    elif rec["end"]:
                        end_d = parse_date(rec["end"])
                        if end_d is not None:
                            # "Fifty or fewer?" is answered by the
                            # fifty-first: a daily series ending in three
                            # years was worked out day by day to be thrown
                            # away, on every search pause, for every such
                            # series.
                            got = expand_occurrences(note, anchor, end_d,
                                                     limit=51)
                            if len(got) <= 50:
                                occ_days = got
                known = memo[key] = {"occ_days": occ_days,
                                     "freq_label": describe_recurrence(note)}
            occ_days = known["occ_days"]
            # The days whose own edits the schedule no longer reaches, worked
            # out once per set of edited days as well (off_schedule_days).
            off_key = ("off", key, tuple(sorted(
                d for d in overrides if isinstance(d, str))))
            off = memo.get(off_key)
            if off is None:
                off = memo[off_key] = frozenset(off_schedule_days(note))
            # Where each day came from, and which moved days are drawn: once
            # per series, not once per day listed -- asked per day, both read
            # every moved day each time (drawn_moves).
            came = _moved_from_map(note)
            if "drawn" not in known:
                known["drawn"] = drawn_moves(note)
            # A day moved past the end or before the start is drawn, outside
            # the span the rule's days were asked of: listed too, or it was in
            # no row and no search found its words (round 18 of the final audit).
            if occ_days is not None:
                occ_days = sorted(set(occ_days) | {new for _orig, new in known["drawn"]})

            children = []
            any_child_match = False
            if occ_days is not None:
                children_kind = "occurrences"
                for day in sorted(occ_days, reverse=True):
                    if not bucket_ok(day):
                        continue
                    override = overrides.get(day)
                    edited = isinstance(override, dict)
                    ov = override if edited else {}
                    child_match = edited and _history_match(
                        query, ov.get("title"), ov.get("body"),
                        ov.get("comments"))
                    if not (child_match or base_matches):
                        continue
                    if query and child_match:
                        any_child_match = True
                    children.append({
                        "date": day,
                        "title": (ov.get("title") or title),
                        "edited": edited,
                        "off_schedule": False,
                        "moved_from": came.get(day),
                    })
                # A bounded series lists its days from its rule, so a day it
                # no longer has was in no row at all: listed here too, marked.
                for day in off:
                    if not bucket_ok(day):
                        continue
                    ov = overrides.get(day)
                    ov = ov if isinstance(ov, dict) else {}
                    child_match = _history_match(
                        query, ov.get("title"), ov.get("body"),
                        ov.get("comments"))
                    if not (child_match or base_matches):
                        continue
                    if query and child_match:
                        any_child_match = True
                    children.append({
                        "date": day,
                        "title": (ov.get("title") or title),
                        "edited": True,
                        "off_schedule": True,
                        "moved_from": None,
                    })
                children.sort(key=lambda c: c["date"], reverse=True)
            else:
                children_kind = "edited"
                landed = {new for _orig, new in known["drawn"]} | set(off)
                for day, override in sorted(overrides.items(), reverse=True):
                    if (day in exceptions and day not in landed) or not is_date(day):
                        # A deleted day's override is normally popped with
                        # the exception; a stray one must not resurface --
                        # but a day moved onto that date holds its own words
                        # there, drawn or off the schedule (round 18).
                        continue
                    if not bucket_ok(day):
                        continue
                    if not isinstance(override, dict):
                        override = {}
                    child_match = _history_match(
                        query, override.get("title"), override.get("body"),
                        override.get("comments"))
                    if not (child_match or base_matches):
                        continue
                    if query and child_match:
                        any_child_match = True
                    children.append({
                        "date": day,
                        "title": (override.get("title") or title),
                        "edited": True,
                        # Listed as a day of the series, and opened as one: a
                        # day the calendar does not have.
                        "off_schedule": day in off,
                        "moved_from": None if day in off else came.get(day),
                    })
                # A day moved to another date is listed as well, edits of its
                # own or not: where it went is worth finding. Only while the
                # calendar draws it there (drawn_moves), worked out once for
                # what the series is (`memo`).
                for orig, new in known["drawn"]:
                    if (new in overrides or not is_date(new) or not bucket_ok(new)
                            or not base_matches):
                        continue
                    children.append({
                        "date": new,
                        "title": title,
                        "edited": False,
                        "off_schedule": False,
                        "moved_from": orig,
                    })
                children.sort(key=lambda c: c["date"], reverse=True)

            base_in_bucket = bucket_ok(note.get("date") or "")
            if children or (base_matches and (base_in_bucket
                                              or year_bucket == "All")):
                sort_date = (children[0]["date"] if children
                             else (note.get("date") or ""))
                entry = {
                    "kind": "series",
                    "note_id": note.get("id"),
                    "title": title,
                    "freq_label": known["freq_label"],
                    "children": children,
                    "children_kind": children_kind,
                    "n_occurrences": (len(occ_days) if occ_days is not None
                                      else None),
                    "n_edited": sum(1 for c in children
                                    if c["edited"] and not c["off_schedule"]),
                    "n_off": sum(1 for c in children if c["off_schedule"]),
                    "n_moved": sum(1 for c in children if c["moved_from"]),
                    "auto_expand": any_child_match,
                    "_sort": sort_date,
                }
                if not children:
                    # Nothing to unfold: the row itself becomes the door —
                    # it jumps to the series' next (or first) day on the
                    # calendar instead of opening an empty group.
                    if "jump_date" not in known:
                        known["jump_date"] = (
                            next_occurrence_on_or_after(
                                note, format_date(today))
                            or note.get("date") or "")
                    entry["jump_date"] = known["jump_date"]
                entries.append(entry)
        else:
            d = note.get("date") or ""
            if not is_date(d):
                continue  # plain undated notes don't live on the calendar
            if not bucket_ok(d):
                continue
            if not _history_match(query, title, note.get("body"),
                                  note.get("comments")):
                continue
            entries.append({
                "kind": "note",
                "note_id": note.get("id"),
                "date": d,
                "title": title,
                "_sort": d,
            })

    entries.sort(key=lambda e: e["_sort"], reverse=True)
    for e in entries:
        e.pop("_sort", None)
    return entries


def next_occurrence_on_or_after(note, date_str):
    """The first date this note lands on, on or after *date_str* — or None
    when the series never reaches that far (it ended, or the rule is
    empty). 'YYYY-MM-DD' in, 'YYYY-MM-DD' out.

    Probes expand_occurrences over growing windows (a month, a year, a
    decade) rather than expanding the whole rule once: the common
    daily/weekly series answers from the first small window, which keeps
    this cheap enough for a sort key computed on every list refresh.
    """
    start = parse_date(date_str)
    if start is None or not is_recurring(note):
        return None
    for window_days in (31, 366, 3660):
        hits = expand_occurrences(
            note, start, start + timedelta(days=window_days))
        if hits:
            return hits[0]
    return None


def effective_note(note, occurrence_date):
    """The note as it should appear on one specific day: the base note, with
    any per-occurrence override applied on top.

    Returns the original note unchanged when there's no override for that
    day, and otherwise a *copy* with the overridden fields replaced — the
    stored note is never modified.
    """
    # A note that no longer repeats keeps its days only for a turn-back-on:
    # read here, a day's old words stood in for the note on its date.
    if not is_recurring(note):
        return note
    return day_as_kept(note, occurrence_date)


def day_as_kept(note, occurrence_date):
    """The note with *occurrence_date*'s own edit applied, whether or not it
    still repeats: what that day holds, for the saves that decide whether
    a day is worth keeping. What a day SHOWS is :func:`effective_note`."""
    override = (note.get("overrides") or {}).get(occurrence_date)
    if not isinstance(override, dict):
        return note
    merged = dict(note)
    for field in OVERRIDABLE_FIELDS:
        if field in override:
            merged[field] = override[field]
    return merged


def day_matches_series(note, patch):
    """Whether one day's own edit says exactly what the series says.

    A day saved with an edit of its own keeps a copy of every field it may
    override, and stops following the series: a later edit of the series
    no longer reaches it. A day saves itself as it is typed, so a letter
    typed and taken back would leave such a copy behind, the same as the
    series and cut off from it for good. When this is true, the day keeps
    no copy of its own.

    Args:
        note: The repeating note (the series).
        patch: The day's fields as the save shapes them (``clean_override``):
            a field it does not hold counts as empty, as the editor shows it.

    Returns:
        True when every field in :data:`OVERRIDABLE_FIELDS` matches. Titles
        compare without the spaces around them, as they are stored.
    """
    for field in OVERRIDABLE_FIELDS:
        mine = patch.get(field) or ""
        theirs = note.get(field) or ""
        if not isinstance(mine, str) or not isinstance(theirs, str):
            return False
        if field == "title":
            mine, theirs = mine.strip(), theirs.strip()
        if mine != theirs:
            return False
    return True


def off_schedule_days(note):
    """The days a repeating note keeps its own edits for that its schedule
    no longer reaches, oldest first.

    A day saved "only this occurrence" keeps its edit under its date. Change
    the series' start date or its rule afterwards and the edit stays in the
    note, on a date the series no longer lands on: the calendar does not
    show it, and nothing else said it was there. The answer comes from
    :func:`expand_occurrences` itself, asked about that one day, so it
    cannot disagree with the calendar. A day deleted from the series (its
    date in ``exceptions``) is not counted: it was taken out on purpose.

    Args:
        note: The note dict. Any note is accepted; one that does not repeat
            has no schedule to fall off, and gets an empty list.

    Returns:
        A sorted list of ``"YYYY-MM-DD"`` strings.
    """
    if not is_recurring(note):
        return []
    overrides = note.get("overrides")
    if not isinstance(overrides, dict) or not overrides:
        return []
    exceptions = set(note.get("exceptions") or [])
    moved = note.get("moved")
    landed = set(moved.values()) if isinstance(moved, dict) else set()
    # Asked with no day skipped, so a skipped day reads as on the schedule
    # here -- and is left out above, as a deletion rather than a fall. A
    # deleted date a day was moved onto holds that day's words, and is asked
    # of the series as it is: hidden there, they were listed nowhere (round 17).
    schedule = dict(note, exceptions=[])
    asked = [(day, when) for day, when in
             ((d, parse_date(d)) for d in sorted(
                 d for d in overrides if isinstance(d, str)))
             if when is not None and (day not in exceptions or day in landed)]
    # What expand_occurrences(schedule, when, when) says of each day, worked
    # out for all of them at once: asked once per edited day, it read every
    # moved day each time (_drawn_on_days).
    shown = _drawn_on_days(schedule, [when for day, when in asked if day not in exceptions])
    kept = _drawn_on_days(note, [when for day, when in asked if day in exceptions])
    return [day for day, when in asked
            if (kept if day in exceptions else shown)[when] != [day]]


def describe_recurrence(note):
    """Short human-readable summary, e.g. 'Every 2 weeks on Mon, Thu'.

    Returns an empty string for a note that doesn't repeat, so callers can
    drop it straight into a label without checking first.
    """
    rec = normalize_recurrence(note.get("recurrence"))
    freq = rec["freq"]
    if not freq:
        return ""

    interval = rec["interval"]
    unit = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}[freq]
    base = f"Every {unit}" if interval == 1 else f"Every {interval} {unit}s"

    if freq == "weekly" and rec["weekdays"]:
        base += " on " + ", ".join(WEEKDAY_NAMES[d] for d in rec["weekdays"])
    elif freq == "monthly" and rec["month_days"]:
        base += " on day " + ", ".join(str(d) for d in rec["month_days"])

    if rec["count"]:
        base += f", {rec['count']} times"
    elif rec["end"]:
        base += f", until {show_date(rec['end'])}"

    return base
