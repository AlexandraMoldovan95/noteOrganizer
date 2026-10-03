"""Dedicated recurrence-engine test suite, separate from the GUI-based QA
scripts — runs headlessly with no tkinter needed, fast enough to run after
every change to expand_occurrences/normalize_recurrence."""
import note_organizer as NO
from datetime import date
import time
import sys

fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

# Weekly
n = {'id':1,'date':'2026-07-01','recurrence':{'freq':'weekly','weekdays':[0,2,4]}}
d = NO.expand_occurrences(n, date(2026,7,1), date(2026,7,31))
check('weekly Mon/Wed/Fri = 14 dates in July', len(d)==14)
check('weekly dates all fall on Mon/Wed/Fri', all(date.fromisoformat(x).weekday() in (0,2,4) for x in d))

# Daily with interval
n2 = {'id':2,'date':'2026-01-01','recurrence':{'freq':'daily','interval':3}}
d2 = NO.expand_occurrences(n2, date(2026,1,1), date(2026,1,31))
check('daily every-3 gives correct count', len(d2)==11)

# Monthly with clamp
n3 = {'id':3,'date':'2026-01-31','recurrence':{'freq':'monthly','month_days':[31],'month_day_policy':'clamp'}}
d3 = NO.expand_occurrences(n3, date(2026,1,1), date(2026,6,30))
check('monthly day-31 clamp includes Feb 28', '2026-02-28' in d3)
check('monthly day-31 clamp includes Apr 30', '2026-04-30' in d3)

# "The end of the month", typed the way people type it: days 28-31, with
# the default clamp policy. 29, 30 and 31 all land on Feb 28, and each
# landing used to count as its own occurrence -- the note sat in one
# calendar cell four times, and a "stop after N times" series spent four
# of its N on a single day.
_eom = {'id': 30, 'date': '2026-01-01',
        'recurrence': {'freq': 'monthly', 'month_days': [28, 29, 30, 31]}}
_eom_feb = NO.expand_occurrences(_eom, date(2026, 2, 1), date(2026, 2, 28))
check('month-end days that clamp onto one date occur on it ONCE',
      _eom_feb == ['2026-02-28'])
_eom_apr = NO.expand_occurrences(_eom, date(2026, 4, 1), date(2026, 4, 30))
check('...in a 30-day month too (30 and 31 are one day)',
      _eom_apr == ['2026-04-28', '2026-04-29', '2026-04-30'])
_eom8 = dict(_eom, recurrence=dict(_eom['recurrence'], count=8))
_eom8_all = NO.expand_occurrences(_eom8, date(2026, 1, 1), date(2026, 12, 31))
check('"8 times" means 8 different days, not 8 landings',
      len(_eom8_all) == 8 and len(set(_eom8_all)) == 8
      and _eom8_all[-1] == '2026-03-30')

# Monthly with skip
n4 = {'id':4,'date':'2026-01-31','recurrence':{'freq':'monthly','month_days':[31],'month_day_policy':'skip'}}
d4 = NO.expand_occurrences(n4, date(2026,1,1), date(2026,6,30))
check('monthly day-31 skip excludes Feb', not any(x.startswith('2026-02') for x in d4))
check('monthly day-31 skip includes Mar 31', '2026-03-31' in d4)

# Yearly
n5 = {'id':5,'date':'2026-03-15','recurrence':{'freq':'yearly'}}
d5 = NO.expand_occurrences(n5, date(2026,1,1), date(2030,12,31))
check('yearly gives 5 occurrences over 5 years', len(d5)==5)

# Count limit
n6 = {'id':6,'date':'2026-01-01','recurrence':{'freq':'daily','count':7}}
d6 = NO.expand_occurrences(n6, date(2026,1,1), date(2027,1,1))
check('count=7 stops at exactly 7', len(d6)==7)

# End date
n7 = {'id':7,'date':'2026-01-01','recurrence':{'freq':'daily','end':'2026-01-10'}}
d7 = NO.expand_occurrences(n7, date(2026,1,1), date(2027,1,1))
check('end date respected', d7[-1]=='2026-01-10' and len(d7)==10)

# Exceptions
n8 = {'id':8,'date':'2026-01-01','recurrence':{'freq':'daily','count':5},'exceptions':['2026-01-02','2026-01-04']}
d8 = NO.expand_occurrences(n8, date(2026,1,1), date(2026,12,31))
check('exceptions correctly removed', len(d8)==3 and '2026-01-02' not in d8 and '2026-01-04' not in d8)

# Range boundary: occurrences before/after the query window are excluded
n9 = {'id':9,'date':'2026-01-01','recurrence':{'freq':'daily'}}
d9 = NO.expand_occurrences(n9, date(2026,6,1), date(2026,6,5))
check('range restricts to window even for open-ended recurrence', d9==['2026-06-01','2026-06-02','2026-06-03','2026-06-04','2026-06-05'])

# One-off (non-recurring) note
n10 = {'id':10,'date':'2026-05-15','recurrence':{}}
d10 = NO.expand_occurrences(n10, date(2026,5,1), date(2026,5,31))
check('one-off note returns exactly its single date', d10==['2026-05-15'])

# No date at all
n11 = {'id':11,'recurrence':{}}
d11 = NO.expand_occurrences(n11, date(2026,1,1), date(2026,12,31))
check('note with no date returns empty', d11==[])

# normalize_recurrence robustness
check('normalize_recurrence handles None', NO.normalize_recurrence(None)['freq']=='')
check('normalize_recurrence handles garbage dict', NO.normalize_recurrence({'freq':'bogus'})['freq']=='')
check('normalize_recurrence clamps negative interval to 1', NO.normalize_recurrence({'freq':'daily','interval':-5})['interval']==1)

# ---- interval upper clamp: a hostile/huge interval can't crash the app ----
from noteorganizer.core.recurrence import MAX_RECURRENCE_INTERVAL as _MAXI
from noteorganizer.core.model import normalize_note as _nn
check('normalize_recurrence clamps a huge interval to the cap',
      NO.normalize_recurrence({'freq':'daily','interval':10**10})['interval'] == _MAXI)
check('a legit small interval is preserved',
      NO.normalize_recurrence({'freq':'daily','interval':3})['interval'] == 3)
check('an interval exactly at the cap is kept',
      NO.normalize_recurrence({'freq':'daily','interval':_MAXI})['interval'] == _MAXI)
_poison = {'id':300,'title':'x','date':'2026-01-01',
           'recurrence':{'freq':'daily','interval':10**10}}
check('the clamp reaches through normalize_note (the import route)',
      _nn(_poison)['recurrence']['interval'] == _MAXI)
_crash = False
try:
    NO.expand_occurrences(_poison, date(2026,9,1), date(2026,9,30))
except Exception:
    _crash = True
check('expand_occurrences no longer overflows on a poisoned interval', not _crash)
_crash2 = False
try:
    from noteorganizer.core.recurrence import next_occurrence_on_or_after as _noa
    _noa(_poison, '2026-09-01')
except Exception:
    _crash2 = True
check('next_occurrence_on_or_after survives a poisoned interval too', not _crash2)

# count clamped both ways too (no asymmetry left in this validator): a
# huge count can't exceed what a rule could ever generate.
from noteorganizer.core.recurrence import MAX_OCCURRENCES as _MAXO
check('a huge count is clamped to MAX_OCCURRENCES',
      NO.normalize_recurrence({'freq':'daily','count':10**9})['count'] == _MAXO)
check('a legit small count is preserved',
      NO.normalize_recurrence({'freq':'daily','count':5})['count'] == 5)

# 36-year stress (performance + correctness at scale)
n_stress = {'id':99,'date':'1990-07-04','recurrence':{'freq':'yearly'}}
t0 = time.perf_counter()
d_stress = NO.expand_occurrences(n_stress, date(2026,7,1), date(2026,7,31))
elapsed = (time.perf_counter()-t0)*1000
check(f'36-year-old yearly recurrence still finds July 2026 occurrence ({elapsed:.2f}ms)',
      d_stress==['2026-07-04'])

# ---- next_occurrence_on_or_after: the "Calendar: soonest" sort key ----
from noteorganizer.core.recurrence import next_occurrence_on_or_after as _nxt

n_wk = {'id': 200, 'date': '2026-01-05', 'recurrence': {'freq': 'weekly'}}
check('weekly series: next occurrence lands on the right weekday',
      _nxt(n_wk, '2026-07-01') == '2026-07-06')  # Jan 5 is a Monday
check('a date ON an occurrence returns that same day',
      _nxt(n_wk, '2026-07-06') == '2026-07-06')
n_day = {'id': 201, 'date': '2026-01-01', 'recurrence': {'freq': 'daily'}}
check('daily series: next occurrence is the asked day itself',
      _nxt(n_day, '2026-07-15') == '2026-07-15')
n_end = {'id': 202, 'date': '2026-01-01',
         'recurrence': {'freq': 'daily', 'end': '2026-02-01'}}
check('an ended series has no next occurrence', _nxt(n_end, '2026-07-01') is None)
check('a non-recurring note has no next occurrence',
      _nxt({'id': 203, 'date': '2026-07-01'}, '2026-06-01') is None)
n_far = {'id': 204, 'date': '2026-01-01',
         'recurrence': {'freq': 'yearly'}}
check('a far-future occurrence is still found past the small windows',
      _nxt(n_far, '2026-01-02') == '2027-01-01')
check('garbage date in -> None out', _nxt(n_wk, 'not a date') is None)

# ---- history_entries: the Calendar History builder ----
from noteorganizer.core.recurrence import history_entries as _hist

_H_TODAY = date(2026, 9, 9)
_h_notes = [
    {'id': 1, 'title': 'Meeting X', 'body': 'plan Q4', 'comments': '',
     'date': '2026-07-20'},
    {'id': 2, 'title': 'Old dated', 'body': 'x', 'comments': '',
     'date': '2023-03-05'},
    {'id': 3, 'title': 'Daily sync', 'body': 'agenda', 'comments': '',
     'date': '2026-01-01', 'recurrence': {'freq': 'daily'},
     'exceptions': ['2026-02-02'],
     'overrides': {
         '2026-08-15': {'title': '', 'body': 'discutat bugetul',
                        'comments': '', 'category': 'General', 'color': ''},
         '2025-12-01': {'title': 'Year-end sync', 'body': 'retro',
                        'comments': '', 'category': 'General', 'color': ''},
         '2026-02-02': {'title': 'stray', 'body': 'on an excepted day',
                        'comments': '', 'category': 'General', 'color': ''},
     }},
    {'id': 4, 'title': 'Lonely series', 'body': 'no edited days',
     'comments': '', 'date': '2026-05-01', 'recurrence': {'freq': 'weekly'}},
    {'id': 5, 'title': 'No date note', 'body': 'off-calendar', 'comments': ''},
    {'id': 6, 'title': 'Bounded3', 'body': 'x', 'comments': '',
     'date': '2026-06-01', 'recurrence': {'freq': 'monthly', 'count': 3},
     'overrides': {'2026-07-01': {'title': 'MidRun', 'body': 'edited',
                                  'comments': '', 'category': 'General',
                                  'color': ''}}},
    {'id': 7, 'title': 'BigCount', 'body': 'x', 'comments': '',
     'date': '2026-04-01', 'recurrence': {'freq': 'daily', 'count': 100}},
]

_all = _hist(_h_notes, today=_H_TODAY)
check('history lists dated notes, series, and skips undated ones',
      [e['note_id'] for e in _all] == [3, 6, 1, 4, 7, 2])

# The bounded-and-small hybrid: a "3 times" series opens to its 3 days.
_s6 = next(e for e in _all if e['note_id'] == 6)
check('a bounded small series lists ALL its occurrences, newest first',
      _s6['children_kind'] == 'occurrences'
      and [c['date'] for c in _s6['children']]
      == ['2026-08-01', '2026-07-01', '2026-06-01']
      and _s6['n_occurrences'] == 3)
check('occurrence children carry honest edited flags',
      [c['edited'] for c in _s6['children']] == [False, True, False]
      and _s6['n_edited'] == 1
      and _s6['children'][1]['title'] == 'MidRun')
_s7 = next(e for e in _all if e['note_id'] == 7)
check('a big count falls back to edited-days-only',
      _s7['children_kind'] == 'edited' and _s7['children'] == [])
check('a childless ENDED series jumps to its start date',
      _s7['jump_date'] == '2026-04-01')
_s4 = next(e for e in _all if e['note_id'] == 4)
check('a childless LIVE series jumps to its next occurrence',
      _s4['jump_date'] == '2026-09-11')
_s3 = next(e for e in _all if e['note_id'] == 3)
check('a series child exists per edited day, newest first, exceptions skipped',
      [c['date'] for c in _s3['children']] == ['2026-08-15', '2025-12-01'])
check("a child with no override title borrows the series'",
      _s3['children'][0]['title'] == 'Daily sync'
      and _s3['children'][1]['title'] == 'Year-end sync')
check('a series with no edited days still gets a row',
      any(e['note_id'] == 4 and e['kind'] == 'series' for e in _all))

_q = _hist(_h_notes, query='bugetul', today=_H_TODAY)
check('search reaches into a day\'s own override content',
      [e['note_id'] for e in _q] == [3]
      and [c['date'] for c in _q[0]['children']] == ['2026-08-15']
      and _q[0]['auto_expand'] is True)
_q2 = _hist(_h_notes, query='agenda', today=_H_TODAY)
check('a base-only match keeps the group collapsed (no auto-expand)',
      [e['note_id'] for e in _q2] == [3] and _q2[0]['auto_expand'] is False)

_y = _hist(_h_notes, year_bucket='Last year', today=_H_TODAY)
check('the year filter keeps only that year\'s activity',
      [e['note_id'] for e in _y] == [3]
      and [c['date'] for c in _y[0]['children']] == ['2025-12-01'])
_o = _hist(_h_notes, year_bucket='Older', today=_H_TODAY)
check('"Older" catches everything before two years ago',
      [e['note_id'] for e in _o] == [2])
check('"2 years ago" is its own bucket, not part of Older',
      _hist(_h_notes, year_bucket='2 years ago', today=_H_TODAY) == [])

# ---------------------------------------------------------------------
# is_recurring on a note that never went through normalize_note.
#
# Live notes are normalised on load, so this question was always asked of
# a well-formed dict. Trash entries are not -- load_trash() returns each
# entry as the file held it -- so the first caller to ask a TRASHED note
# whether it repeats met whatever a hand-edit, an older format or a
# crafted backup had left in the field. A string there is truthy, and
# .get() on a string raises: the whole Trash panel went down with it.
# ---------------------------------------------------------------------
check('a proper recurrence still reads as one',
      NO.is_recurring({'recurrence': {'freq': 'daily'}}) is True)
check('a missing recurrence is not one',
      NO.is_recurring({}) is False)
check('an empty recurrence is not one',
      NO.is_recurring({'recurrence': {}}) is False)
check('a recurrence with no freq is not one',
      NO.is_recurring({'recurrence': {'count': 3}}) is False)
for _junk in ('daily', 0, 1, [], ['freq'], 3.5, True):
    try:
        _answer = NO.is_recurring({'recurrence': _junk})
        check('a %r recurrence answers instead of raising' % (_junk,),
              _answer is False)
    except Exception as _e:
        check('a %r recurrence answers instead of raising (%s)' % (_junk, _e),
              False)


# ---------------------------------------------------------------------
# Dates the way people write them (read_date), and the one form the app
# shows them in (show_date). The files keep YYYY-MM-DD whatever was typed.
# A short or a missing year is read only once the person has finished
# with the field (settled): read while typing, "17.10.20" on its way to
# 2026 would be stored as 2020.
# ---------------------------------------------------------------------
_RD_TODAY = date(2026, 10, 3)
_RD = date(2026, 10, 17)


def _rd(text, settled=False):
    return NO.read_date(text, settled=settled, today=_RD_TODAY)


for _form in ('17.10.2026', '17/10/2026', '17-10-2026', '17 10 2026',
              '17. 10. 2026', ' 17.10.2026 ', '2026-10-17', '2026.10.17',
              '2026/10/17', '17 oct 2026', '17 Oct. 2026', '17-oct-2026',
              '17 octombrie 2026', '17 OCTOMBRIE 2026', 'October 17, 2026',
              'oct 17 2026', '17 octo 2026'):
    check('the date is read from %r' % _form, _rd(_form) == _RD)
check('one figure for the day or the month is enough',
      _rd('1.2.2026') == date(2026, 2, 1) and _rd('01.02.2026') == date(2026, 2, 1))
check('figures are read day first: 10/12/2026 is the tenth of December',
      _rd('10/12/2026') == date(2026, 12, 10))
for _form, _want in (('17 mai 2026', 5), ('17 may 2026', 5),
                     ('3 martie 2026', 3), ('3 mar 2026', 3),
                     ('5 iun 2026', 6), ('5 iul 2026', 7),
                     ('5 noi 2026', 11), ('5 nov 2026', 11),
                     ('5 sept 2026', 9), ('5 ianuarie 2026', 1),
                     ('5 decembrie 2026', 12)):
    _got = _rd(_form)
    check('the month in %r is read as month %d' % (_form, _want),
          _got is not None and _got.month == _want)
check('a leap day is read in a leap year, and refused in another',
      _rd('29.02.2028') == date(2028, 2, 29) and _rd('29.02.2027') is None)
for _form in ('17.10', '17 oct', '17.10.26', '17 oct 26', 'oct 17'):
    check('%r waits until the field is left' % _form, _rd(_form) is None)
    check('...and is read then, as 17.10.2026 (%r)' % _form,
          _rd(_form, settled=True) == _RD)
check('a two-figure year being typed is never read as a year of its own',
      _rd('17.10.20') is None and _rd('17.10.202') is None)
check('...and once the field is left, two figures mean this century',
      _rd('17.10.20', settled=True) == date(2020, 10, 17))
for _form in ('31.09.2026', '00.10.2026', '17.13.2026', '17.10.20262',
              '2026-10', 'abc', '17 ma 2026', '17 xyz 2026', '117.10.2026',
              '17.100.2026', 'oct 2026', '17 oct 2026 18', '17.10.0999',
              'Saturday 17 October 2026', 'DD.MM.YYYY', '17.10.2026!', '',
              '   ', '١٧.10.2026', '17·10·2026', None, 17):
    # ascii(), not %r: a plain Windows console cannot print the digits of
    # another script, and the line would crash the suite instead of naming it.
    check('%s is not read as a date' % ascii(_form), _rd(_form) is None
          and _rd(_form, settled=True) is None)
check('a date stretched past forty characters is not read',
      _rd('17' + ' ' * 40 + '10 2026') is None)
# No three letters start two months' names today, in either language, so
# the rule that such a word names no month is proved by teaching the table
# a name that would make "mar" ambiguous -- and taking it away again.
from noteorganizer.core import recurrence as _rd_rec
_rd_rec._MONTH_NAMES['marzipan'] = 7
try:
    _rd_ambiguous = _rd('17 mar 2026')
finally:
    del _rd_rec._MONTH_NAMES['marzipan']
check("a word starting two months' names is no month",
      _rd_ambiguous is None and _rd('17 mar 2026') == date(2026, 3, 17))
# One pass over the text, never a backtracking search: thirty figures and a
# stray symbol took a single repeated-group pattern hours, in the field's
# own keystroke. The unbacked version answers in microseconds.
_rd_t0 = time.perf_counter()
_rd_hostile = _rd('1' * 26 + '!')
check('twenty-six figures and a symbol are refused at once (%.3f s)'
      % (time.perf_counter() - _rd_t0),
      _rd_hostile is None and time.perf_counter() - _rd_t0 < 1.0)

check('a stored date is shown day first',
      NO.show_date('2026-10-17') == '17.10.2026'
      and NO.show_date('2026-1-5') == '05.01.2026')
check('text that is not a stored date is shown as it is',
      NO.show_date('17.10') == '17.10' and NO.show_date('') == ''
      and NO.show_date(None) == '')
check('a stored moment keeps its time, its date shown day first',
      NO.show_stamp('2026-09-01 09:00') == '01.09.2026 09:00'
      and NO.show_stamp('odd') == 'odd')
check('a day written out comes day first, in English whatever the system',
      NO.show_day(_RD) == 'Saturday, 17 October 2026'
      and NO.show_day(_RD, year=False) == 'Saturday, 17 October'
      and NO.show_day(_RD, year=False, short_month=True) == 'Saturday, 17 Oct')
check('a date and the field showing it are the same date',
      NO.same_date('17.10.2026', '2026-10-17')
      and NO.same_date(' 30.09.2026 ', '30.09.2026')
      and NO.same_date('', ''))
check('...and a half-typed one is not',
      not NO.same_date('17.10', '2026-10-17') and not NO.same_date('x', 'y'))
check('an end date written day first is that end, not "never ends"',
      NO.normalize_recurrence({'freq': 'daily', 'end': '31.12.2026'})['end']
      == '2026-12-31')
check('...and one not yet whole is no end at all, as before',
      NO.normalize_recurrence({'freq': 'daily', 'end': '31.12'})['end'] == '')
check('a note arriving with its date written day first is stored in the '
      'form the calendar places it by',
      NO.normalize_note({'title': 't', 'date': '30.09.2026'})['date'] == '2026-09-30'
      and NO.normalize_note({'title': 't', 'date': '17 oct 2026'})['date'] == '2026-10-17')
check('...while a date no one can read arrives as it came, as before',
      NO.normalize_note({'title': 't', 'date': '31.09.2026'})['date'] == '31.09.2026'
      and NO.normalize_note({'title': 't', 'date': '17.10'})['date'] == '17.10')
check('...and a repeat anchored on a day-first date keeps repeating',
      NO.normalize_note({'title': 't', 'date': '07.09.2026',
                         'recurrence': {'freq': 'weekly'}})['recurrence']['freq']
      == 'weekly')
check('the "until" of a repeat is shown day first',
      NO.describe_recurrence({'recurrence': {'freq': 'weekly', 'interval': 2,
                                             'end': '2026-12-31'}})
      == 'Every 2 weeks, until 31.12.2026')


print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
