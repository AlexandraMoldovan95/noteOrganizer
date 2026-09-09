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
from datetime import datetime, date as date_cls, timedelta

__all__ = [
    "WEEKDAY_NAMES",
    "FREQ_LABELS",
    "RECURRENCE_DEFAULTS",
    "OVERRIDABLE_FIELDS",
    "MAX_OCCURRENCES",
    "parse_date",
    "format_date",
    "normalize_recurrence",
    "is_recurring",
    "expand_occurrences",
    "next_occurrence_on_or_after",
    "history_entries",
    "effective_note",
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
        out["interval"] = max(1, int(rec.get("interval", 1)))
    except (TypeError, ValueError):
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

    end = rec.get("end", "")
    out["end"] = end.strip() if isinstance(end, str) and parse_date(end) else ""

    try:
        out["count"] = max(0, int(rec.get("count", 0)))
    except (TypeError, ValueError):
        out["count"] = 0

    return out


def is_recurring(note):
    """True if this note repeats at all."""
    return bool((note.get("recurrence") or {}).get("freq"))


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


def expand_occurrences(note, range_start, range_end):
    """Every date this note lands on between range_start and range_end
    (inclusive), as 'YYYY-MM-DD' strings. Exceptions are already removed.

    This is the heart of the module. One branch per frequency, each
    walking forward from the anchor and calling the shared ``take()``
    below to record a hit and decide whether to keep going.

    Args:
        note: The note dict, providing its date, rule and exceptions.
        range_start: First date of interest (a ``date`` object).
        range_end: Last date of interest, inclusive.

    Returns:
        A sorted list of date strings. Empty if the note has no valid
        anchor date, or simply doesn't occur in this range.
    """
    anchor = parse_date(note.get("date", ""))
    if anchor is None:
        return []

    rec = normalize_recurrence(note.get("recurrence"))
    exceptions = set(note.get("exceptions") or [])

    if not rec["freq"]:
        one_off = format_date(anchor)
        if range_start <= anchor <= range_end and one_off not in exceptions:
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
        N times"), but only collects the ones inside the visible range.
        """
        nonlocal produced
        if candidate < anchor:
            return True
        if end_date is not None and candidate > end_date:
            return False
        produced += 1
        if range_start <= candidate <= range_end:
            results.append(candidate)
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
                candidate = week_start + timedelta(days=weekday)
                if candidate > horizon:
                    continue
                if not take(candidate):
                    stop = True
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
            if date_cls(year, month, 1) > horizon:
                break
            for wanted in month_days:
                candidate = _day_in_month(year, month, wanted, policy)
                if candidate is None or candidate > horizon:
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

    return [format_date(d) for d in sorted(results) if format_date(d) not in exceptions]


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


def history_entries(notes, query="", year_bucket="All", today=None):
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

    Returns:
        A list of dicts, newest activity first. A dated note:
        ``{"kind": "note", "note_id", "date", "title"}``. A series:
        ``{"kind": "series", "note_id", "title", "freq_label",
        "children": [{"date", "title"} newest-first], "auto_expand"}``.
    """
    if today is None:
        today = date_cls.today()

    def bucket_ok(d):
        return year_bucket == "All" or _history_bucket_of(d, today) == year_bucket

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

            # A BOUNDED, small series lists ALL its occurrences — the
            # field expectation: a "10 times" group opens to its 10 days.
            # An unbounded rule would drown the register in identical
            # rows, so it lists only the separately-edited days instead.
            rec = normalize_recurrence(note.get("recurrence"))
            anchor = parse_date(note.get("date") or "")
            occ_days = None
            if anchor is not None:
                if 0 < rec["count"] <= 50:
                    occ_days = expand_occurrences(
                        note, anchor, anchor + timedelta(days=36600))
                elif rec["end"]:
                    end_d = parse_date(rec["end"])
                    if end_d is not None:
                        got = expand_occurrences(note, anchor, end_d)
                        if len(got) <= 50:
                            occ_days = got

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
                    })
            else:
                children_kind = "edited"
                for day, override in sorted(overrides.items(), reverse=True):
                    if day in exceptions or parse_date(day) is None:
                        # A deleted day's override is normally popped with
                        # the exception; a stray one must not resurface.
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
                    })

            base_in_bucket = bucket_ok(note.get("date") or "")
            if children or (base_matches and (base_in_bucket
                                              or year_bucket == "All")):
                sort_date = (children[0]["date"] if children
                             else (note.get("date") or ""))
                entry = {
                    "kind": "series",
                    "note_id": note.get("id"),
                    "title": title,
                    "freq_label": describe_recurrence(note),
                    "children": children,
                    "children_kind": children_kind,
                    "n_occurrences": (len(occ_days) if occ_days is not None
                                      else None),
                    "n_edited": sum(1 for c in children if c["edited"]),
                    "auto_expand": any_child_match,
                    "_sort": sort_date,
                }
                if not children:
                    # Nothing to unfold: the row itself becomes the door —
                    # it jumps to the series' next (or first) day on the
                    # calendar instead of opening an empty group.
                    entry["jump_date"] = (
                        next_occurrence_on_or_after(
                            note, format_date(today))
                        or note.get("date") or "")
                entries.append(entry)
        else:
            d = note.get("date") or ""
            if parse_date(d) is None:
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
    override = (note.get("overrides") or {}).get(occurrence_date)
    if not isinstance(override, dict):
        return note
    merged = dict(note)
    for field in OVERRIDABLE_FIELDS:
        if field in override:
            merged[field] = override[field]
    return merged


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
        base += f", until {rec['end']}"

    return base
