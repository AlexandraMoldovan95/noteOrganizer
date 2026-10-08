# HERMETIC SEED -- BEFORE the note_organizer import below: the module
# resolves its data directory and runs the data MIGRATIONS at import
# time, so this script's data directory must be its own before that
# happens. hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to
# run at all outside a scratch run, or beside a notebook it cannot
# prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import note_organizer as NO, tkinter as tk
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         pin_popup_visibility as _qa_pin)
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
# On the Calendar tab first, the way a person is when they look at one.
# render_calendar() defers a rebuild for a month that is not on screen --
# 36ms and 98 widgets nobody sees, on every save and delete -- so asking
# for cells from the Notes tab now asks for something the app
# deliberately has not drawn yet.
app.notebook.select(app.TAB_CALENDAR)
app.update()
try:
    app.render_calendar()
    app.update()
    check('calendar renders without error', True)
except Exception as e:
    check(f'calendar renders without error ({e})', False)

# The month is a drawing: a cell is a record of what was drawn for a day.
rendered_cells = len(getattr(app, '_cal_cells', {}))
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

app.notes = [{'id': 400 + i, 'title': f'Many{i}', 'body': 'b',
              'category': 'General', 'date': _D13,
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []} for i in range(12)]
app.show_day_summary_tooltip(_D13)
app.update()
_lbls = _tip_labels()
check('twelve notes cap at ten titles plus a "+2 more" line',
      _lbls is not None and any('+2 more' in t for t in _lbls)
      and sum(1 for t in _lbls if t.startswith('Many')) == 10)
app.hide_day_tooltip(); app.update()

_rich = {'id': 500, 'title': 'Hover', 'body': 'some body text',
         'category': 'General', 'date': _D13, 'comments': 'a comment',
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
      and any('some body text' in t for t in _lbls)
      and any('\U0001F4AC' in t and '\U0001F4CE' in t and '1/2' in t
              for t in _lbls))
check('a repeating note is flagged in its preview title',
      any('\U0001F501' in t for t in _lbls))
app.hide_day_tooltip(); app.update()

# ============================================================
# THE CHIP IS THE NOTE, AND BEHAVES LIKE ONE (C-8)
# ============================================================
# Hovering a note's title in the month grid has always previewed THAT
# note -- and then clicking it opened the whole day, so someone who had
# just read "Dentist, 14:00" landed on a list of the day's notes and had
# to find it again. Right-click, this app's own route to a note's
# actions, offered "Color this day...". Every action a note has was
# unreachable from the grid, although the same-looking row in the day
# panel carries all of them.
import datetime as _c8_dt
_c8_d = _c8_dt.date.fromisoformat(_D13)
app.cal_year, app.cal_month = _c8_d.year, _c8_d.month
app.render_calendar()
app.update()


def _c8_chips():
    """The note titles drawn in the grid, as (day, index) -- read from the
    drawing, since a title is text on the month's canvas, not a Label."""
    found = []
    for _d in sorted(app._cal_cells):
        for _i, _t in enumerate(app._cal_cell_view(_d)['chips']):
            if 'Hover' in _t:
                found.append((_d, _i))
    return found


_c8_found = _c8_chips()
check(f'the grid draws the note as a chip ({len(_c8_found)} found)',
      bool(_c8_found))
if _c8_found:
    _c8_day, _c8_index = _c8_found[0]
    _c8_at = app._cal_point(_c8_day, chip=_c8_index)
    # THE PROMISE THE HOVER MAKES. Clicking the chip must land on that one
    # note, not on the day's list -- which is what the day cell around it
    # still does, and rightly. A real click, on the canvas, at the title.
    _qa_click(app.cal_canvas, x=_c8_at[0], y=_c8_at[1])
    app.update()
    check('clicking the chip lands on that one note, not the whole day',
          getattr(app, '_day_panel_mode', None) == 'note')
    # And the right-click is the note's menu, not the day's.
    _c8_posted = []
    _c8_real = NO.tk.Menu.tk_popup
    NO.tk.Menu.tk_popup = lambda _m, *a, **k: _c8_posted.append(_m)
    try:
        _qa_fire(app.cal_canvas, '<Button-3>', x=_c8_at[0], y=_c8_at[1])
        app.update()
        _c8_labels = []
        if _c8_posted:
            for _i in range(_c8_posted[-1].index('end') + 1):
                try:
                    _c8_labels.append(
                        str(_c8_posted[-1].entrycget(_i, 'label')))
                except tk.TclError:
                    _c8_labels.append('---')
        check(f'right-clicking the chip offers the NOTE\'s actions '
              f'({len(_c8_labels)} entries)',
              any('Pin' in _l for _l in _c8_labels)
              and any('Duplicate' in _l for _l in _c8_labels))
        check('...and not the day menu it used to give',
              not any('Color this day' in _l for _l in _c8_labels))
        # THE CONTROL: the DAY's own menu must still be there, on the cell
        # around the chip -- the day number and the background are the day,
        # and taking its menu away would trade one gap for another.
        _c8_posted.clear()
        _c8_cell_at = app._cal_point(_c8_day)
        _qa_fire(app.cal_canvas, '<Button-3>', x=_c8_cell_at[0], y=_c8_cell_at[1])
        app.update()
        _c8_day_labels = []
        if _c8_posted:
            for _i in range(_c8_posted[-1].index('end') + 1):
                try:
                    _c8_day_labels.append(
                        str(_c8_posted[-1].entrycget(_i, 'label')))
                except tk.TclError:
                    _c8_day_labels.append('---')
        check(f'the cell around it still offers the DAY\'s menu '
              f'({len(_c8_day_labels)} entries)',
              any('day' in _l.lower() for _l in _c8_day_labels))
    finally:
        NO.tk.Menu.tk_popup = _c8_real
app.update()

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

# ---- THE CAP SAYS WHY, INSTEAD OF SWALLOWING THE CLICK (C-16) ----
# The header says "up to 3" once at the top, and the rule was then kept by
# silence: the fourth click simply did nothing, which reads as the app being
# broken rather than as a limit being enforced. Every other ceiling here
# speaks -- the title cap sets a status line, the attachment cap warns.
def _cap_note_text(pop):
    """The line under the grid, found by being the one wordy Label."""
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Label) and len(str(c.cget('text'))) > 12:
                out.append(str(c.cget('text')))
            walk(c)
    walk(pop)
    return out

_before_cap = ' '.join(_cap_note_text(_emopop))
check('before the cap, nothing is complaining',
      'unpick' not in _before_cap.lower())
_chip_bgs_before = [str(c.cget('bg')) for c in _chips]
for chip in _chips[:3]:
    _qa_click(chip)
    app.update()
# Three chosen: the rest must READ as unavailable before a dead click is
# ever made, which is the half a message alone does not cover.
_flat = [c for c in _chips[3:] if str(c.cget('bg')) != _chip_bgs_before[
    _chips.index(c)]]
check(f'at the cap the unpicked chips go flat ({len(_flat)} of '
      f'{len(_chips) - 3})', len(_flat) == len(_chips) - 3)
check('and the popup says why, without waiting to be clicked',
      'unpick' in ' '.join(_cap_note_text(_emopop)).lower())
# THE CONTROL: the three that ARE chosen must keep their own colour, or
# "everything went flat" would pass this just as well.
_chosen_kept = [c for c in _chips[:3]
                if str(c.cget('bg')) == _chip_bgs_before[_chips.index(c)]]
check(f'while the three chosen keep their colour ({len(_chosen_kept)} of 3)',
      len(_chosen_kept) == 3)
# And unpicking one puts the rest back, so the state is not a one-way door.
_qa_click(_chips[0])
app.update()
_back = [c for c in _chips[3:] if str(c.cget('bg')) == _chip_bgs_before[
    _chips.index(c)]]
check(f'unpicking one lights the others again ({len(_back)} of '
      f'{len(_chips) - 3})', len(_back) == len(_chips) - 3)
# Put every chip back to unchosen before the original five-click check
# below, so that check still means what its name says -- five clicks on
# five chips, the last two refused by the cap -- rather than a toggle
# sequence that happens to land on three.
for chip in _chips[1:3]:
    _qa_click(chip)
    app.update()
check('fixture: nothing is chosen again before the five-click check',
      'unpick' not in ' '.join(_cap_note_text(_emopop)).lower()
      and all(str(c.cget('bg')) == _chip_bgs_before[_chips.index(c)]
              for c in _chips))
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
    'id': 4101, 'title': 'Sport', 'body': 'training',
    'category': 'General', 'date': '2026-07-01',
    'recurrence': {'freq': 'weekly', 'weekdays': [2]},
    'checklist': [{'text': 'shoes', 'done': False},
                  {'text': 'towel', 'done': False}],
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
app.body_text.insert('1.0', 'only this day is different')
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

# ---- A per-day edit ending in a table is not "unsaved" forever ----
# The caret-line canonicalisation reached the base body but not the
# override patches, and an override is shown in the SAME editor -- so the
# renderer added the line, the stored day text did not have it, and the
# day read as unsaved on every open: a save-scope question nobody asked
# for at every note switch and at close, whose "whole series" answer
# replaces the series text with that one day's.
_TBL_O = '| a | b |\n| --- | --- |\n| 1 | 2 |'
_ov_note = NO.normalize_note({
    'id': 4301, 'title': 'Series', 'body': 'the base body',
    'category': 'General', 'date': '2026-07-01',
    'recurrence': {'freq': 'weekly', 'weekdays': [2]},
    'overrides': {'2026-07-08': {'title': 'The day', 'body': 'intro\n' + _TBL_O}},
    'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00'})
app.notes = [_ov_note]
app.save_notes()
app.update()
check('a stored override ending in a table is canonical on load',
      app.find_note(4301)['overrides']['2026-07-08']['body']
      == 'intro\n' + _TBL_O + '\n')
app.load_note(app.find_note(4301), occurrence_date='2026-07-08')
app.update()
check('...so that day opens CLEAN instead of unsaved forever',
      app.editor_state_matches_saved(app.capture_editor_state()))

# ---- A series-owned edit does not raise a question it cannot answer ----
# An override carries the five overridable fields and nothing else, so
# "this day" has nowhere to put a ticked checklist item: the old code
# asked anyway, wrote an override duplicating the series' own text, threw
# the tick away, and left the editor dirty so it asked again next time.
_sq_note = NO.normalize_note({
    'id': 4302, 'title': 'Series2', 'body': 'body',
    'category': 'General', 'date': '2026-07-01',
    'recurrence': {'freq': 'weekly', 'weekdays': [2]},
    'checklist': [{'text': 'one', 'done': False}],
    'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00'})
app.notes = [_sq_note]
app.save_notes()
app.update()
app.load_note(app.find_note(4302), occurrence_date='2026-07-08')
app.update()
app._working_checklist[0]['done'] = True
app.update()
_sq_asked = []
app.ask_occurrence_scope = lambda *a, **k: (_sq_asked.append(1), 'occurrence')[1]
app._flush_autosave()
app.update()
_sq_after = app.find_note(4302)
check('a series-owned edit asks no scope question at all', _sq_asked == [])
check('...the tick lands on the series', _sq_after['checklist'][0]['done'] is True)
check('...no phantom override is written for that day',
      '2026-07-08' not in (_sq_after.get('overrides') or {}))
check('...and the editor is clean afterwards, so it cannot ask again',
      app.editor_state_matches_saved(app.capture_editor_state()))
# The question MUST still be asked when an override really could carry
# the edit -- otherwise this fix would have quietly removed the feature.
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'only this day')
app.update()
_sq_asked2 = []
app.ask_occurrence_scope = lambda *a, **k: (_sq_asked2.append(1), 'occurrence')[1]
app.save_current_note(auto=False)
app.update()
check('while a text edit on one day still asks, and still overrides',
      _sq_asked2 == [1]
      and '2026-07-08' in (app.find_note(4302).get('overrides') or {}))
del app.ask_occurrence_scope
app.notes = []
app.save_notes()
app.new_note(); app.update()

# ---- "Restore previous" on a repeating note restores the SERIES ----
# It used to run through the editor's save, which asks a scope question
# on a repeating note. Answering "this occurrence" wrote the recovered
# text into a per-day override -- plain text only, so the formatting came
# back stripped, the SERIES stayed shortened, and the rescue copy was
# spent anyway under a success message. The other answer left _prev armed
# with an override present, and the stale button later overwrote new
# text. It writes straight to the note now: no scope to get wrong.
_rs_note = NO.normalize_note({
    'id': 4201, 'title': 'Repeated', 'date': '2026-07-01',
    'body': 'the long original version, with plenty of text worth keeping',
    'formatting': [{'start': 0, 'end': 9, 'style': 'bold'}],
    'recurrence': {'freq': 'weekly', 'weekdays': [2]},
    'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00'})
app.notes = [_rs_note]
app.save_notes()
app.update()
_RS_OCC = '2026-07-08'

app.load_note(app.find_note(4201))
app.update()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'short')
app.save_current_note(auto=False)
app.update()
check('a drastic shrink on a repeating note leaves a rescue copy',
      isinstance(app.find_note(4201).get('_prev'), dict))

# Now do the restore from the OCCURRENCE view, answering "this
# occurrence" to any scope question that might still be asked.
app.load_note(app.find_note(4201), occurrence_date=_RS_OCC)
app.update()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version()
app.update()
_rs_after = app.find_note(4201)
check('restoring from a day brings the SERIES body back, not an override',
      'original version' in _rs_after.get('body', ''))
check('...with its formatting intact, not flattened to plain text',
      _rs_after.get('formatting') == [{'start': 0, 'end': 9, 'style': 'bold'}])
check('...and no per-day override was manufactured for that day',
      _RS_OCC not in (_rs_after.get('overrides') or {}))
check('...and the rescue copy is spent exactly once',
      _rs_after.get('_prev') is None)
del app.ask_occurrence_scope
app.notes = []
app.save_notes()
app.new_note(); app.update()


# ---- FIELD CASES AUTOMATED (test plan 68, 69, 70, 71, 72, 73, 74) ----
# The duplicates panel, driven through its own buttons rather than
# through the function behind them: the panel decides which copies are
# ticked, and a check that calls the cleanup with a list it built itself
# would not notice the panel ticking the wrong ones.
def _dp_button(widget, label):
    for child in widget.winfo_children():
        if isinstance(child, tk.Button) and label in str(child.cget('text')):
            return child
        found = _dp_button(child, label)
        if found:
            return found
    return None


def _dp_boxes(widget, found=None):
    """Every duplicate row's tick box, in the order the panel drew them."""
    if found is None:
        found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Checkbutton):
            found.append(child)
        _dp_boxes(child, found)
    return found


def _dp_seed(groups):
    """A notebook holding `groups` groups of identical notes."""
    app.notes = []
    app.trash = []
    nid = 1
    for gi, copies in enumerate(groups):
        for _ in range(copies):
            app.notes.append({
                'id': nid, 'title': 'Twin %d' % gi, 'body': 'the same text %d' % gi,
                'comments': '', 'category': 'General', 'date': '', 'color': '',
                'recurrence': {}, 'checklist': [], 'attachments': [],
                'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'})
            nid += 1
    app.save_notes()
    app.show_settings_page(); app.update()
    app.toggle_settings_panel('duplicates'); app.update()


_dp_saved_notes, _dp_saved_trash = list(app.notes), list(app.trash)
app.ask_yes_no = lambda *a, **k: True

# 68: ticking two copies of four moves exactly those two.
_dp_seed([4])
_dp_all = _dp_boxes(app.settings_duplicates_panel)
check('the duplicates panel draws one tick box per copy (plan 68)',
      len(_dp_all) == 4)
if len(_dp_all) == 4:
    _dp_all[1].invoke(); _dp_all[3].invoke()      # the 2nd and the 4th
    app.update()
    _dp_go = _dp_button(app.settings_duplicates_panel, 'Move ticked')
    if _dp_go is not None:
        _dp_go.invoke(); app.update()
    check('only the ticked copies go to the trash (plan 68)',
          len(app.notes) == 2 and len(app.trash) == 2)
    check('...and the ones left are the ones nobody ticked',
          sorted(n['id'] for n in app.notes) == [1, 3])
    # 74: and they are recoverable, not destroyed.
    check('the removed copies are in the Trash, not gone (plan 74)',
          sorted(e['id'] for e in app.trash) == [2, 4])

# 69: the tool does not insist on keeping exactly one.
_dp_seed([3])
_dp_all = _dp_boxes(app.settings_duplicates_panel)
if len(_dp_all) == 3:
    _dp_all[2].invoke(); app.update()
    _dp_go = _dp_button(app.settings_duplicates_panel, 'Move ticked')
    if _dp_go is not None:
        _dp_go.invoke(); app.update()
    check('two copies may be kept -- nothing forces "keep exactly one" (plan 69)',
          len(app.notes) == 2)

# 70: "Tick all but first" ticks every copy except the first.
_dp_seed([3])
_dp_shortcut = _dp_button(app.settings_duplicates_panel, 'Tick all but first')
check('each group offers "Tick all but first" (plan 70)', _dp_shortcut is not None)
if _dp_shortcut is not None:
    _dp_shortcut.invoke(); app.update()
    _dp_go = _dp_button(app.settings_duplicates_panel, 'Move ticked')
    if _dp_go is not None:
        _dp_go.invoke(); app.update()
    check('...and it leaves the first copy standing, alone (plan 70)',
          len(app.notes) == 1 and app.notes[0]['id'] == 1)

# 71 and 72: the all-groups button appears only when there are groups to
# mean it, and reduces every one of them in a single action.
_dp_seed([2])
check('with a single group there is no all-groups button (plan 72)',
      _dp_button(app.settings_duplicates_panel, 'Clean up ALL') is None)

_dp_seed([3, 2])
_dp_everything = _dp_button(app.settings_duplicates_panel, 'Clean up ALL')
check('with several groups the all-groups button is offered (plan 71)',
      _dp_everything is not None)

# The all-groups button was the quietest thing on the panel: the sidebar
# fill, the theme's ordinary text colour, a smaller font and less padding
# than the button below it, which acts only on what you ticked. Photographed
# before the change, it did not read as a button at all -- it blended into
# the panel behind it. Visual weight is how a reader works out which action
# is the broad one, and it said the opposite (finding C-6).
#
# These run BEFORE the invoke below, which rebuilds the panel and would
# leave the widgets they are about destroyed.
_dp_ticked_btn = _dp_button(app.settings_duplicates_panel, 'Move ticked')
check('the two cleanup buttons are both found for the weight check',
      _dp_everything is not None and _dp_ticked_btn is not None)
if _dp_everything is not None and _dp_ticked_btn is not None:
    check('duplicates: the all-groups button is not painted quieter than '
          'the one that acts on less',
          str(_dp_everything.cget('font')) == str(_dp_ticked_btn.cget('font'))
          and _dp_everything.pack_info().get('ipady')
          == _dp_ticked_btn.pack_info().get('ipady'))
    # The dark red FILL is kept for what cannot be undone; moving notes to
    # the Trash wears the warning's words, here with a border as Empty
    # trash has, so it still reads as a button.
    check('duplicates: it wears the warning\'s words in an outline, as every '
          'move to the Trash does',
          str(_dp_everything.cget('bg')) == str(app.colors['card'])
          and str(_dp_everything.cget('fg')) == str(app.colors['danger_text'])
          and str(_dp_everything.cget('relief')) == 'solid')
    check('duplicates: and it is no longer the sidebar colour it blended into',
          str(_dp_everything.cget('bg')) != str(app.colors['sidebar']))
    check('duplicates: the precise action keeps the accent, so the eye is '
          'warned by the sweeping one rather than drawn to it',
          str(_dp_ticked_btn.cget('bg')) == str(app.colors['accent']))
    # The panel's main action first, the sweeping one below it -- on the
    # screen, where a reader meets them.
    app.update()
    _dp_ys = (_dp_ticked_btn.winfo_rooty(), _dp_everything.winfo_rooty())
    check(f'duplicates: the main action comes first, the sweeping one below it '
          f'({_dp_ys})',
          _dp_ticked_btn.winfo_ismapped() and _dp_everything.winfo_ismapped()
          and _dp_ys[0] < _dp_ys[1])

if _dp_everything is not None:
    _dp_asked = []
    _dp_real_ask = app.ask_yes_no
    app.ask_yes_no = lambda *a, **k: (_dp_asked.append(1), True)[1]
    _dp_everything.invoke(); app.update()
    app.ask_yes_no = _dp_real_ask
    check('...and one click reduces every group to its first copy (plan 71)',
          sorted(n['id'] for n in app.notes) == [1, 4])
    check('...having asked once, not once per group',
          len(_dp_asked) <= 1)

# 73: ticking nothing deletes nothing, and says so.
_dp_seed([3])
_dp_said = []
_dp_real_info = app.show_info
app.show_info = lambda *a, **k: (_dp_said.append(a), True)[1]
_dp_go = _dp_button(app.settings_duplicates_panel, 'Move ticked')
if _dp_go is not None:
    _dp_go.invoke(); app.update()
app.show_info = _dp_real_info
check('cleaning up with nothing ticked deletes nothing (plan 73)',
      len(app.notes) == 3 and not app.trash)
check('...and says that nothing was ticked, rather than doing nothing quietly',
      any('select' in str(a).lower() or 'tick' in str(a).lower() or
          'nothing' in str(a).lower() for a in _dp_said))

app.hide_settings_page()
app.notes = list(_dp_saved_notes)
app.trash = list(_dp_saved_trash)
app.save_notes()
app.new_note(); app.update()



# ---- FIELD CASES AUTOMATED (test plan 52, 53, 55, 77, 78, 83) ----
_b3c_saved = list(app.notes)

# 52: "Today" comes back to this month, with today marked.
import datetime as _b3dt, re as _b3re
_b3_today = _b3dt.date.today()
app.cal_year, app.cal_month = 2020, 1
app.render_calendar(); app.update()
app.go_to_today(); app.update()
check('Today returns the calendar to the current month (plan 52)',
      (app.cal_year, app.cal_month) == (_b3_today.year, _b3_today.month))

# 53: a day with more notes than fit says how many more.
_b3_day = '%04d-%02d-15' % (_b3_today.year, _b3_today.month)
app.notes = [{'id': 6000 + i, 'title': 'Busy day %d' % i, 'body': 'x',
              'comments': '', 'category': 'General', 'date': _b3_day,
              'color': '', 'recurrence': {}, 'checklist': [], 'attachments': [],
              'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'}
             for i in range(4)]
app.save_notes()
app.render_calendar(); app.update()


def _b3_texts(widget, out=None):
    if out is None:
        out = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            out.append(str(child.cget('text')))
        _b3_texts(child, out)
    return out


_b3_all = app._cal_texts()
check('a day holding more notes than fit says how many more (plan 53)',
      any(_b3re.match(r'^\+\d+ more$', t) for t in _b3_all))
check('...and still shows some of them by name',
      sum(1 for t in _b3_all if t.startswith('Busy day')) >= 1)

# 55: a day painted a colour keeps it, and only that day.
app.day_colors = {}
app.day_colors[_b3_day] = '#ff8800'
app._persist_day_colors()
app.render_calendar(); app.update()
check('a day given a colour remembers it (plan 55)',
      app.day_colors.get(_b3_day) == '#ff8800')
check('...and it is written down, so it survives a restart',
      (NO.load_settings().get('day_colors') or {}).get(_b3_day) == '#ff8800')
_b3_neighbour = '%04d-%02d-16' % (_b3_today.year, _b3_today.month)
check('...and the day beside it is left alone',
      _b3_neighbour not in app.day_colors)
app.day_colors = {}
app._persist_day_colors()

# 77 and 83: the sidebar filter, and sorting inside groups.
app.notebook.select(app.TAB_NOTES); app.update()
NO.CATEGORY_COLORS.setdefault('School', '#4477aa')
NO.CATEGORY_COLORS.setdefault('Home', '#aa7744')
app.notes = [
    {'id': 7001, 'title': 'Beta', 'category': 'School'},
    {'id': 7002, 'title': 'Alpha', 'category': 'School'},
    {'id': 7003, 'title': 'Delta', 'category': 'Home'},
    {'id': 7004, 'title': 'Gamma', 'category': 'Home'},
]
app.notes = [NO.normalize_note(n) for n in app.notes]
app.save_notes()
app.filter_var.set('School')
app.refresh_note_list(); app.update()
_b3_shown = set(app._card_order())
check('filtering by a category shows only that category (plan 77)',
      _b3_shown == {7001, 7002})
app.filter_var.set('All')
app.refresh_note_list(); app.update()

# 78: a category added later is in the filter without a restart.
NO.CATEGORY_COLORS['FreshlyAdded'] = '#336699'
app.refresh_category_widgets(); app.update()
# The dropdown keeps no list of its own: it asks for the categories at
# the moment it opens, which IS the promise this case is about. So the
# check opens it the way a click does, and reads what is on offer --
# rather than asking the same source the menu asks and proving nothing.
_qa_click(app.filter_menu)
app.update()
_b3_pop = getattr(app.filter_menu, '_nested_popup', None) or getattr(app, '_mini_popup', None)
_b3_labels = _b3_texts(_b3_pop) if _b3_pop is not None else []
app._dismiss_mini_popup()
app.update()
check('a category added just now is in the filter, no restart (plan 78)',
      'FreshlyAdded' in _b3_labels)
NO.CATEGORY_COLORS.pop('FreshlyAdded', None)
app.refresh_category_widgets(); app.update()

# 83: with grouping on, the sort still orders inside each group.
app.group_by_category.set(True)
# Taken from the app's own list, not typed: the label uses an EN
# DASH, and a hyphen here set the variable to a value no sort
# matches -- the list stayed as it was and the check passed on
# the wrong order.
app.sort_var.set(next(o for o in app.SORT_OPTIONS if o.startswith('Title A')))
app.refresh_note_list(); app.update()
_b3_order = [n['title'] for n in app._visible_notes_in_order()] \
    if hasattr(app, '_visible_notes_in_order') else None
if _b3_order is None:
    # The cards in the order they are drawn, top to bottom.
    _b3_order = [app.find_note(_cid)['title'] for _cid in app._card_order()]
check('sorting A-Z orders the notes inside each group (plan 83)',
      _b3_order == ['Delta', 'Gamma', 'Alpha', 'Beta']
      or _b3_order == ['Alpha', 'Beta', 'Delta', 'Gamma'])
app.group_by_category.set(False)
app.sort_var.set('Recently updated')
app.refresh_note_list(); app.update()

app.notes = list(_b3c_saved)
app.save_notes()
app.new_note(); app.update()



# ---- FIELD CASE AUTOMATED (test plan 109) ----
# Cleaning up duplicates and then looking in the Trash: the copies are
# recoverable, which is what makes the cleanup safe to offer at all.
_b4d_saved_notes, _b4d_saved_trash = list(app.notes), list(app.trash)
app.notes = []
app.trash = []
app.notes = [NO.normalize_note({'id': i + 1, 'title': 'Identical',
                                'body': 'the very same body', 'category': 'General',
                                'created': '2026-03-01 09:00:00',
                                'updated': '2026-03-02 10:00:00'})
             for i in range(3)]
app.save_notes()
app.ask_yes_no = lambda *a, **k: True
app.show_settings_page(); app.update()
app.toggle_settings_panel('duplicates'); app.update()


def _b4d_boxes(w):
    out = []
    for c in w.winfo_children():
        if isinstance(c, tk.Checkbutton):
            out.append(str(c.cget('text')))
        out.extend(_b4d_boxes(c))
    return out


# A copy's dates are shown as every date in the app is: day first.
_b4d_said = _b4d_boxes(app.settings_duplicates_panel)
check(f'a duplicate says when it was created and updated, day first '
      f'({_b4d_said[:1]})',
      any('created 01.03.2026' in t and 'updated 02.03.2026' in t
          for t in _b4d_said))
_b4d_shortcut = _dp_button(app.settings_duplicates_panel, 'Tick all but first')
if _b4d_shortcut is not None:
    _b4d_shortcut.invoke(); app.update()
    _b4d_go = _dp_button(app.settings_duplicates_panel, 'Move ticked')
    if _b4d_go is not None:
        _b4d_go.invoke(); app.update()
check('cleaning up duplicates leaves one copy (plan 109)', len(app.notes) == 1)
check('...and the removed copies are in the Trash, recoverable (plan 109)',
      len(app.trash) == 2)
app.toggle_settings_panel('trash'); app.update()
_b4d_restore = _dp_button(app.settings_trash_panel, 'Restore')
if _b4d_restore is not None:
    _b4d_restore.invoke(); app.update()
    check('...and one of them really comes back (plan 109)',
          len(app.notes) == 2 and len(app.trash) == 1)
app.hide_settings_page()
app.notes = list(_b4d_saved_notes)
app.trash = list(_b4d_saved_trash)
app.save_notes()
app.new_note(); app.update()

# ---- A DAY WITH TEXT OF ITS OWN, AND WHAT CAN HAPPEN TO IT ----
# Three routes lost one day's own title and text, or spread it over every
# day of the series. See docs/ISSUES_LOG.md.
_od_saved = list(app.notes)


def _od_series():
    app.new_note(); app.update()
    app.notes = [NO.normalize_note({
        'id': 1, 'title': 'Yoga', 'body': 'stretch 20 min',
        'formatting': [{'start': 0, 'end': 7, 'style': 'bold'}],
        'date': '2026-09-01', 'recurrence': {'freq': 'weekly'},
        'checklist': [{'text': 'mat', 'done': False}],
        'overrides': {'2026-09-15': {'title': 'Yoga', 'body': 'class moved to 7pm'}}})]
    app.save_notes()
    return app.notes[0]


# The Undo of a removed day brings the day back as it was: it came back
# showing the series' text, the day's own edit gone for good.
_od_note = _od_series()
check("fixture: the series has formatting and one day with text of its own",
      _od_note['formatting'] == [{'start': 0, 'end': 7, 'style': 'bold'}]
      and '2026-09-15' in _od_note['overrides'])
_od_scope = app.ask_occurrence_scope
_od_yes = app.ask_yes_no
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._delete_note(_od_note, '2026-09-15')
app.ask_occurrence_scope = _od_scope
app.update()
_od_back = app.find_note(1)
check('removing one day of a series takes its own text with it',
      '2026-09-15' not in (_od_back.get('overrides') or {}))
app._undo_occurrence_delete(1, '2026-09-15',
                            {'title': 'Yoga', 'body': 'class moved to 7pm'})
app.update()
_od_back = app.find_note(1)
check("...and the Undo brings the day back with that text, not the series'",
      (_od_back.get('overrides') or {}).get('2026-09-15', {}).get('body')
      == 'class moved to 7pm'
      and '2026-09-15' not in (_od_back.get('exceptions') or []))
# The toast carries it: the offer made by the delete itself.
_od_note = _od_series()
_od_offers = []
_od_real_toast = app._show_toast
app._show_toast = lambda text, **k: _od_offers.append(k.get('action'))
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._delete_note(_od_note, '2026-09-15')
app.ask_occurrence_scope = _od_scope
app._show_toast = _od_real_toast
if _od_offers and _od_offers[-1]:
    _od_offers[-1]()
app.update()
check("...even when the Undo is the delete's own toast",
      (app.find_note(1).get('overrides') or {}).get('2026-09-15', {}).get('body')
      == 'class moved to 7pm')

# A ticked checklist item on a day with its own text belongs to the
# series, and nobody is asked -- but the whole editor was written to the
# series: that one day's words replaced every day's, and the series'
# formatting was wiped (a day's own text carries none).
_od_note = _od_series()
app.open_note_in_tab(_od_note, occurrence_date='2026-09-15'); app.update()
app._working_checklist[0]['done'] = True
app._flush_autosave(); app.update()
_od_back = app.find_note(1)
check("a tick made on a day with its own text reaches the series' checklist",
      _od_back['checklist'][0]['done'] is True)
check("...without that day's words becoming every day's",
      _od_back['body'] == 'stretch 20 min'
      and _od_back['formatting'] == [{'start': 0, 'end': 7, 'style': 'bold'}])
check("...and the day keeps its own text",
      (_od_back.get('overrides') or {}).get('2026-09-15', {}).get('body')
      == 'class moved to 7pm')
app.new_note(); app.update()

# Answering "The entire series" on such a day makes its words the series'
# -- and the day stops holding a copy of its own: it kept one, the editor
# read as unsaved forever, and every way out asked the question again.
_od_note = _od_series()
app.open_note_in_tab(_od_note, occurrence_date='2026-09-15'); app.update()
app.body_text.insert('end', ', room B')
_od_asked = []
app.ask_occurrence_scope = lambda *a, **k: (_od_asked.append(a), 'series')[1]
app._flush_autosave(); app.update()
app.ask_occurrence_scope = _od_scope
_od_back = app.find_note(1)
check('"The entire series" on a day with its own text gives every day its words',
      _od_back['body'].startswith('class moved to 7pm, room B')
      and '2026-09-15' not in (_od_back.get('overrides') or {}))
check("...keeping the series' own text as the rescue copy",
      (_od_back.get('_prev') or {}).get('body') == 'stretch 20 min')
check('...and the question is not asked again for an edit already saved',
      app.editor_state_matches_saved(app.capture_editor_state())
      and len(_od_asked) == 1)
app.ask_yes_no = _od_yes
app.new_note(); app.update()
app.notes = _od_saved
app.save_notes()


print()
print(f"=== QA2 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
