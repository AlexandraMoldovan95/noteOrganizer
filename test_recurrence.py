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
]

_all = _hist(_h_notes, today=_H_TODAY)
check('history lists dated notes, series, and skips undated ones',
      [e['note_id'] for e in _all] == [3, 1, 4, 2])
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

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
