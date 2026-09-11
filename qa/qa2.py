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
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import click as _qa_click, pin_popup_visibility as _qa_pin
_qa_pin(NO)
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

# ---- CALENDAR INTERACTIVITY (coverage-lift C13) ----
# The keyboard navigation, hover tooltips and day color/emoji markers
# were never driven by any script — 65.5% file coverage, the suite's
# worst. Real assertions, not execution theater.

class _Ev2:
    pass

app.notebook.select(app.TAB_CALENDAR)
app.update()
_y0, _m0 = app.cal_year, app.cal_month
_ev = _Ev2(); _ev.widget = None
_r = app._calendar_key(_ev, months=1)
check('PgDn-style key moves the calendar one month and eats the key',
      (app.cal_year * 12 + app.cal_month) == (_y0 * 12 + _m0 + 1)
      and _r == 'break')
_ev_typing = _Ev2(); _ev_typing.widget = app.body_text
_r2 = app._calendar_key(_ev_typing, months=1)
check('the same key while typing does NOT hijack the calendar',
      (app.cal_year * 12 + app.cal_month) == (_y0 * 12 + _m0 + 1)
      and _r2 is None)
app._calendar_key(_ev, today=True)
from datetime import date as _date2
check('the Today key lands on the current month',
      (app.cal_year, app.cal_month) == (_date2.today().year,
                                        _date2.today().month))

def _tip_labels():
    tip = getattr(app, '_day_tooltip', None)
    if tip is None or not tip.winfo_exists():
        return None
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label):
                out.append(str(c.cget('text')))
            walk(c)
    walk(tip)
    return out

_D13 = '2026-08-14'
app.notes = [{'id': 300 + i, 'title': f'ZiNota{i}', 'body': 'b',
              'category': 'General', 'date': _D13,
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []} for i in range(2)]
app.show_day_summary_tooltip(_D13)
app.update()
_lbls = _tip_labels()
check('the day tooltip lists both titles under a 2-note header',
      _lbls is not None and any('2 note(s)' in t for t in _lbls)
      and any('ZiNota0' in t for t in _lbls)
      and any('ZiNota1' in t for t in _lbls))
app.hide_day_tooltip()
app.update()
check('hide_day_tooltip destroys it', _tip_labels() is None)

app.notes = [{'id': 400 + i, 'title': f'Multa{i}', 'body': 'b',
              'category': 'General', 'date': _D13,
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []} for i in range(12)]
app.show_day_summary_tooltip(_D13)
app.update()
_lbls = _tip_labels()
check('twelve notes cap at ten titles plus a "+2 more" line',
      _lbls is not None and any('+2 more' in t for t in _lbls)
      and sum(1 for t in _lbls if t.startswith('Multa')) == 10)
app.hide_day_tooltip(); app.update()

_rich = {'id': 500, 'title': 'Hover', 'body': 'corp de text',
         'category': 'General', 'date': _D13, 'comments': 'un comentariu',
         'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
         'checklist': [{'text': 'a', 'done': True},
                       {'text': 'b', 'done': False}],
         'attachments': [{'filename': 'f.txt', 'stored_as': 'x_f.txt'}],
         'recurrence': {'freq': 'daily', 'interval': 1}}
app.notes = [_rich]
app.show_note_hover_preview(_rich, _D13)
app.update()
_lbls = _tip_labels()
check('the note hover preview carries title, body, and the icon row',
      _lbls is not None
      and any('Hover' in t for t in _lbls)
      and any('corp de text' in t for t in _lbls)
      and any('\U0001F4AC' in t and '\U0001F4CE' in t and '1/2' in t
              for t in _lbls))
check('a repeating note is flagged in its preview title',
      any('\U0001F501' in t for t in _lbls))
app.hide_day_tooltip(); app.update()

# Day COLOUR through the real palette popup: open, click a swatch,
# assert the colour lands, persists, and the reset path clears it.
def _find_swatches(root):
    out = []
    def walk(w):
        for c in w.winfo_children():
            bg = str(c.cget('bg')) if 'bg' in c.keys() else ''
            if isinstance(c, (tk.Frame, tk.Label)) and bg.startswith('#') \
                    and str(c.cget('cursor')) == 'hand2':
                out.append(c)
            walk(c)
    walk(root)
    return out

app._color_day(_D13)
app.update()
_pal = app._mini_popup
check('the day colour palette opens as the app mini-popup',
      _pal is not None and _pal.winfo_exists())
# The swatches are little CANVASES (the colour is a drawn item, not a
# widget bg) — find them by class + cursor.
def _find_canvases(root):
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Canvas) and str(c.cget('cursor')) == 'hand2':
                out.append(c)
            walk(c)
    walk(root)
    return out
_sw = _find_canvases(_pal)
check('the palette offers clickable swatches', len(_sw) >= 5)
if _sw:
    _qa_click(_sw[0])
    app.update()
    _picked = app.day_colors.get(_D13)
    check('clicking a swatch colours the day and persists it',
          isinstance(_picked, str) and _picked.startswith('#')
          and NO.get_setting('day_colors', {}).get(_D13) == _picked)
app._clear_day_color(_D13)
check('clearing the day colour removes it from disk too',
      _D13 not in NO.get_setting('day_colors', {}))

# Day EMOJI markers: toggle two, hit the 3-marker cap, Save persists.
app._mark_day_emoji(_D13)
app.update()
_emopop = app._mini_popup
_chips = [c for c in _find_swatches(_emopop)
          if isinstance(c, tk.Label) and str(c.cget('text')).strip()]
check('the emoji marker popup offers its chips', len(_chips) >= 6)
for chip in _chips[:5]:
    _qa_click(chip)
    app.update()
_save_btn = None
def _find_btn2(w, txt):
    global _save_btn
    for c in w.winfo_children():
        if isinstance(c, tk.Button) and txt in str(c.cget('text')):
            _save_btn = c
        _find_btn2(c, txt)
_find_btn2(_emopop, 'Save')
_save_btn.invoke()
app.update()
_saved_marks = app.day_emoji.get(_D13, [])
check('clicking five chips saves exactly the 3-marker cap',
      len(_saved_marks) == 3
      and NO.get_setting('day_emoji', {}).get(_D13) == _saved_marks)
app.day_emoji.pop(_D13, None)
app._persist_day_emoji()

# ---- An edit to the SERIES, made while looking at one day ----
# The occurrence branch of the dirty check compared only the five
# overridable fields, so anything series-owned that the user changed
# while viewing a single day -- a ticked checklist item above all -- was
# invisible to every save gate: the editor asked for the save and the
# comparator vetoed it, and the tick never reached disk.
# It now compares the series-owned fields against the BASE note, which
# is where load_note read them from in the first place. Formatting and
# paragraphs stay out on purpose, and the second half of this block is
# what proves that: an override is plain text, so comparing them made a
# just-saved occurrence read as dirty FOREVER (field report, 0.71.111).
_occ_series = NO.normalize_note({
    'id': 4101, 'title': 'Sport', 'body': 'antrenament',
    'category': 'General', 'date': '2026-07-01',
    'recurrence': {'freq': 'weekly', 'weekdays': [2]},
    'checklist': [{'text': 'incaltari', 'done': False},
                  {'text': 'prosop', 'done': False}],
    # The series carries a styling span ON PURPOSE. An override is plain
    # text, so load_note only re-applies the base's spans when the shown
    # body equals the base's -- which is exactly why formatting must stay
    # OUT of the occurrence comparison. With no span in the fixture the
    # two states are indistinguishable and the check cannot catch a
    # regression that puts formatting back in.
    'formatting': [{'start': 0, 'end': 4, 'style': 'bold'}],
    'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00'})
app.notes = [_occ_series]
app.save_notes()
app.update()
_OCC = '2026-07-08'

app.load_note(app.find_note(4101), occurrence_date=_OCC)
app.update()
check('an untouched occurrence opens clean',
      app.editor_state_matches_saved(app.capture_editor_state()))
app._working_checklist[0]['done'] = True
app.update()
check('ticking a checklist item there reads as an unsaved change',
      not app.editor_state_matches_saved(app.capture_editor_state()))
app.ask_occurrence_scope = lambda *a, **k: 'series'
app._flush_autosave()
app.update()
check('...and the tick actually reaches the note',
      app.find_note(4101)['checklist'][0]['done'] is True)

# The half this must NOT undo: a saved occurrence stays clean.
app.notes = [NO.normalize_note(dict(_occ_series, overrides={}))]
app.save_notes()
app.update()
app.load_note(app.find_note(4101), occurrence_date=_OCC)
app.update()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'doar ziua asta e altfel')
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app.save_current_note(auto=False)
app.update()
check('saving just this day writes an override',
      _OCC in (app.find_note(4101).get('overrides') or {}))
app.load_note(app.find_note(4101), occurrence_date=_OCC)
app.update()
check('and re-opening that day reads CLEAN, not dirty forever',
      app.editor_state_matches_saved(app.capture_editor_state()))
# The precondition that gives the check above its teeth: the base note
# really does hold a span the overridden view does not show, so a
# comparison that included formatting WOULD read dirty.
check('...with the base note genuinely holding a span the day does not',
      app.find_note(4101).get('formatting')
      and not app.capture_editor_state().get('formatting'))
del app.ask_occurrence_scope
app.notes = []
app.save_notes()
app.new_note(); app.update()

print()
print(f"=== QA2 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
