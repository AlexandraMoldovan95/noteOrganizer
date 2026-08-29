# HERMETIC SEED -- BEFORE the note_organizer import below: the module
# resolves its data directory and runs the data MIGRATIONS at import
# time, so by the first line of test code the adoption has already
# happened. The data directory must be this test's alone. An
# empty directory invites run_migrations to adopt whatever real notebook
# %APPDATA% holds, and real notes then leak into every scenario: the
# checks start flaking whenever the OWNER's data changes. Seeding an
# empty notebook plus the reclaim marker closes both migration doors
# before the app is even constructed. The refusal is the same last-line
# defence test_data_safety carries: run from a folder holding real
# notes, the script stops instead of seeding over them.
import io as _seed_io, json as _seed_json, os as _seed_os, sys as _seed_sys
if _seed_os.path.exists('notes_data.json'):
    try:
        _seed_prev = _seed_json.load(
            _seed_io.open('notes_data.json', encoding='utf-8'))
    except Exception:
        _seed_prev = []
    if isinstance(_seed_prev, list) and _seed_prev:
        _seed_sys.exit(
            'REFUSING to run: notes_data.json here holds %d real note(s). '
            'Copy this script to a scratch directory instead.'
            % len(_seed_prev))
_seed_io.open('notes_data.json', 'w', encoding='utf-8').write('[]')
_seed_io.open('settings.json', 'w', encoding='utf-8').write(
    _seed_json.dumps({'reclaimed_from_appdata': True}))

import sys
import note_organizer as NO, tkinter as tk
from datetime import date
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

# ---- RECURRENCE ENGINE ----
note = {'id':1,'title':'Gym','date':'2026-07-01','recurrence':{'freq':'weekly','weekdays':[0,2,4],'interval':1}}
dates = NO.expand_occurrences(note, date(2026,7,1), date(2026,7,31))
check('weekly Mon/Wed/Fri expands to 14 in July 2026', len(dates)==14)

note_daily = {'id':2,'title':'Daily','date':'2026-01-01','recurrence':{'freq':'daily','interval':2}}
dates2 = NO.expand_occurrences(note_daily, date(2026,1,1), date(2026,1,31))
check('daily-every-2 gives 16 dates in January', len(dates2)==16)

note_monthly = {'id':3,'title':'Monthly','date':'2026-01-31','recurrence':{'freq':'monthly','month_days':[31],'month_day_policy':'clamp'}}
dates3 = NO.expand_occurrences(note_monthly, date(2026,1,1), date(2026,4,30))
check('monthly day-31 with clamp policy handles short months',
      '2026-02-28' in dates3 and '2026-01-31' in dates3)

note_count = {'id':4,'title':'Limited','date':'2026-01-01','recurrence':{'freq':'daily','count':5}}
dates4 = NO.expand_occurrences(note_count, date(2026,1,1), date(2026,12,31))
check('count-limited recurrence stops at 5', len(dates4)==5)

note_end = {'id':5,'title':'Ended','date':'2026-01-01','recurrence':{'freq':'daily','end':'2026-01-05'}}
dates5 = NO.expand_occurrences(note_end, date(2026,1,1), date(2026,12,31))
check('end-dated recurrence respects end date', dates5[-1]=='2026-01-05')

# exceptions removed
note_exc = {'id':6,'title':'HasExc','date':'2026-01-01','recurrence':{'freq':'daily','count':5},
           'exceptions':['2026-01-03']}
dates6 = NO.expand_occurrences(note_exc, date(2026,1,1), date(2026,12,31))
check('exception date removed from expansion', '2026-01-03' not in dates6 and len(dates6)==4)

# is_recurring
check('is_recurring true for recurring note', NO.is_recurring(note)==True)
check('is_recurring false for one-off note', NO.is_recurring({'recurrence':{}})==False)

# ---- CALENDAR RENDER ----
app.notes.append(dict(note, id=100))
app.cal_year, app.cal_month = 2026, 7
try:
    app.render_calendar()
    app.update()
    check('calendar renders without error', True)
except Exception as e:
    check(f'calendar renders without error ({e})', False)

rendered_cells = len(app.cal_grid_frame.winfo_children()) if hasattr(app,'cal_grid_frame') else 0
check('calendar produced grid cells', rendered_cells > 20)

# month navigation
try:
    app.shift_calendar(months=1)
    app.update()
    check('month navigation works', app.cal_month==8)
except Exception as e:
    check(f'month navigation works ({e})', False)

# ---- DUPLICATE DETECTION ----
app.notes = [
    {'id':201,'title':'Dup','body':'same body','comments':'','category':'General',
     'updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
    {'id':202,'title':'DUP','body':'Same Body','comments':'','category':'General',
     'updated':'2026-01-02 00:00','created':'2026-01-02 00:00','checklist':[],'attachments':[]},
    {'id':203,'title':'Different','body':'unique','comments':'','category':'General',
     'updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
]
groups = NO.find_duplicate_groups(app.notes)
check('case-insensitive duplicate detection finds 1 group', len(groups)==1)
check('duplicate group has 2 notes', len(groups[0])==2 if groups else False)

# duplicate detection survives None/corrupt fields
app.notes.append({'id':999,'title':None,'body':None,'comments':None,'category':None})
try:
    NO.find_duplicate_groups(app.notes)
    check('duplicate detection survives None fields', True)
except Exception as e:
    check(f'duplicate detection survives None fields ({e})', False)

print()
print(f"=== QA2 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
