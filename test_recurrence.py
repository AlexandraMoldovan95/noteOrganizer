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

print()
print(f"FAILURES: {fails if fails else 'none'}")

sys.exit(1 if fails else 0)
