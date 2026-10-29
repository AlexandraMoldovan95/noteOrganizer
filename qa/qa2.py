# HERMETIC SEED -- BEFORE the note_organizer import below. Building the
# app calls initialise(), which resolves the data directory and runs the
# data MIGRATIONS, so this script's data directory must be its own by
# then; seeding it before the import leaves no step in between.
# hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to run at all
# outside a scratch run, or beside a notebook it cannot prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import note_organizer as NO, tkinter as tk
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         ignore_pointer as _qa_ignore_pointer,
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
# The previews below are opened by call and read back; a real mouse moving
# over the window would take them down first (_qa_support.ignore_pointer).
_qa2_hear_pointer = _qa_ignore_pointer(app.cal_canvas)
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
_qa2_hear_pointer()

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
# A text edit, which an override can carry, is that day's own: saved to the
# day, asking nothing either (a day opened on its own is edited on its own).
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'only this day')
app.update()
_sq_asked2 = []
app.ask_occurrence_scope = lambda *a, **k: (_sq_asked2.append(1), 'occurrence')[1]
app.save_current_note(auto=False)
app.update()
check('while a text edit on one day is saved to that day, asking nothing',
      _sq_asked2 == []
      and (app.find_note(4302).get('overrides') or {}).get('2026-07-08', {}).get('body')
      == 'only this day'
      and app.find_note(4302)['body'] == 'body')
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
check("...and the copy now holds the series' text it replaced, not a day's",
      ((_rs_after.get('_prev') or {}).get('body') or '').rstrip('\n') == 'short')
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

# Words typed on such a day are that day's: they used to wait for "This
# occurrence only, or the entire series?", whose second answer made them
# every day's. A day opened on its own now saves to itself, asking nothing;
# the whole series has its own view (the day strip's "Edit the whole
# series").
_od_note = _od_series()
app.open_note_in_tab(_od_note, occurrence_date='2026-09-15'); app.update()
app.body_text.insert('end', ', room B')
_od_asked = []
app.ask_occurrence_scope = lambda *a, **k: (_od_asked.append(a), 'series')[1]
app._flush_autosave(); app.update()
app.ask_occurrence_scope = _od_scope
_od_back = app.find_note(1)
check('words typed on a day with its own text stay that day\'s, asking nothing',
      _od_back['body'] == 'stretch 20 min'
      and _od_back['formatting'] == [{'start': 0, 'end': 7, 'style': 'bold'}]
      and (_od_back.get('overrides') or {}).get('2026-09-15', {}).get('body')
      == 'class moved to 7pm, room B'
      and _od_asked == [])
check('...and the editor reads as saved afterwards',
      app.editor_state_matches_saved(app.capture_editor_state()))
app.ask_yes_no = _od_yes
app.new_note(); app.update()
app.notes = _od_saved
app.save_notes()

# ---- LONG LISTS SCROLL TO THEIR END ----
# Round 5 of the final audit: every long list was one frame on a canvas, and
# Tk keeps a canvas window's place in 16 bits, so none scrolled past about
# 32,767 px (ISSUES_LOG: "The list that ended in the middle"). Each list here
# runs past that -- reaches_the_end refuses one that does not -- and is
# asked for its last row, which is then pressed or ticked from the keyboard.
import time
from _qa_support import reaches_the_end as _ll_reaches


def _ll_settle(n=6):
    for _ in range(n):
        app.update()
        time.sleep(0.02)


def _ll_all(w):
    for c in w.winfo_children():
        yield c
        yield from _ll_all(c)


def _ll_focus(widget):
    """The keyboard on *widget*, by Tk's own record: True once it is."""
    try:
        widget.focus_force()
    except tk.TclError:
        return False
    for _ in range(60):
        app.update()
        if str(app.tk.call('focus')) == str(widget):
            return True
        time.sleep(0.01)
    return False


def _ll_in_view(w, canvas):
    top = w.winfo_rooty() - canvas.winfo_rooty()
    return (bool(w.winfo_viewable()) and 0 <= top
            and top + w.winfo_height() <= canvas.winfo_height())


def _ll_stack_canvas(top):
    return next((c for c in _ll_all(top)
                 if getattr(c, '_row_stack', None) is not None), None)


def _ll_text(row, needle=''):
    return next((c for c in _ll_all(row) if isinstance(c, tk.Label)
                 and needle in str(c.cget('text'))), None)


def _ll_note(i, **fields):
    return NO.normalize_note(dict({'id': i, 'title': f'Note {i}', 'body': '',
                                   'category': 'General'}, **fields))


_ll_kept = (list(app.notes), list(app.templates), list(app.trash))
_ll_yes = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: False
_ll_toasts = []
app._show_toast = lambda *a, **k: _ll_toasts.append(k.get('action'))
_LL_WORDS = ('steady ' * 290)[:1990]       # as long as an item may be


# The note's checklist: 100 items of 1,000 letters, each row some hundreds of
# px tall -- on Linux taller than the list's own view.
app.notebook.select(app.TAB_NOTES)
app.new_note(); _ll_settle()
app._working_checklist = [{'text': f'{i:03d} {_LL_WORDS[:996]}', 'done': False}
                          for i in range(100)]
if app._checklist_open:
    app._render_checklist_items()
else:
    app.toggle_checklist_section()
_ll_settle(10)
_ll_rows = app._checklist_rows.rows()
_ll_box = (next((c for c in _ll_rows[-1].winfo_children()
                 if isinstance(c, tk.Checkbutton)), None) if _ll_rows else None)
_ll_ok, _ll_said = (_ll_reaches(app, app._checklist_canvas, _ll_rows[-1], _ll_settle)
                    if _ll_box is not None else (False, 'no rows'))
_ll_ticked = False
if _ll_ok and _ll_focus(_ll_box):
    # Where Tab would put it: the box stands in its row's middle.
    app._bring_into_sight(_ll_box); _ll_settle(2)
    _ll_box.event_generate('<space>')
    _ll_settle(2)
    _ll_ticked = (app._working_checklist[-1]['done'] is True
                  and _ll_in_view(_ll_box, app._checklist_canvas))
check(f'a note\'s checklist longer than one frame can scroll shows its last item '
      f'at its end, and Space ticks it there ({_ll_said}; ticked: {_ll_ticked})',
      _ll_ok and _ll_ticked)


def _ll_cl_label(r):
    return next((c for c in r.winfo_children() if isinstance(c, tk.Label)
                 and '▲' not in str(c.cget('text'))), None)


def _ll_cl_shown():
    """The items as drawn, chunk by chunk in packing order; as Tab walks."""
    drawn = [str(_ll_cl_label(r).cget('text'))
             for c in app._checklist_rows.chunks for r in c.pack_slaves()]
    walked = [str(_ll_cl_label(r).cget('text')) for r in app._checklist_rows.rows()]
    return drawn, walked


# A row cannot leave its chunk: Alt+Down over the edge of one makes both rows
# again, each in the other's place, and the keyboard goes with the item.
_LL_N = app._checklist_rows.every              # short items to a chunk
app._working_checklist = [{'text': f'item {i}', 'done': False}
                          for i in range(2 * _LL_N)]
app._render_checklist_items(); _ll_settle()
_ll_chunks = [len(c.winfo_children()) for c in app._checklist_rows.chunks]
_ll_b3 = next(c for c in app._checklist_rows.rows()[_LL_N - 1].winfo_children()
              if isinstance(c, tk.Checkbutton))
_ll_moved = None
if _ll_focus(_ll_b3):
    _ll_b3.event_generate('<Alt-Down>')
    _ll_settle(2)
    _ll_moved = _ll_cl_shown()
_ll_want = [f'item {i}' for i in range(2 * _LL_N)]
_ll_want[_LL_N - 1], _ll_want[_LL_N] = _ll_want[_LL_N], _ll_want[_LL_N - 1]
_ll_now = app._checklist_rows.rows()[_LL_N]
check(f'Alt+Down over the edge of a chunk moves the item, drawn and walked in '
      f'its new order, the keyboard with it (chunks {_ll_chunks}; '
      f'{_ll_moved and _ll_moved[0][_LL_N - 2:_LL_N + 2]})',
      _ll_chunks == [_LL_N, _LL_N]
      and [it['text'] for it in app._working_checklist] == _ll_want
      and _ll_moved == (_ll_want, _ll_want)
      and str(app.tk.call('focus')) == str(next(
          (c for c in _ll_now.winfo_children() if isinstance(c, tk.Checkbutton)),
          None)))


def _ll_bin_of(row):
    return next((c for c in row.winfo_children()
                 if isinstance(c, tk.Button) and '🗑' in str(c.cget('text'))), None)


def _ll_delete_undo(count, at, first_empty=0):
    """Item *at* of *count* deleted by its bin and put back by the toast's
    Undo -- after the bins of the *first_empty* items from *at* on emptied
    its chunk down to it: (chunk sizes, the items in order, its chunk)."""
    app._working_checklist = [{'text': f'item {i}', 'done': False}
                              for i in range(count)]
    app._render_checklist_items(); _ll_settle()
    for _ in range(first_empty):
        _ll_bin_of(app._checklist_rows.rows()[at]).invoke()
    _ll_settle(2)
    kept = [it['text'] for it in app._working_checklist]
    del _ll_toasts[:]
    _ll_bin_of(app._checklist_rows.rows()[at]).invoke(); _ll_settle(2)
    if _ll_toasts and callable(_ll_toasts[-1]):
        _ll_toasts[-1](); _ll_settle(2)
    back = app._checklist_rows.rows()[at].master
    return ([len(c.winfo_children()) for c in app._checklist_rows.chunks],
            _ll_cl_shown() == (kept, kept),
            next((k for k, c in enumerate(app._checklist_rows.chunks)
                  if c is back), None))


# An item deleted and put back stands where it was, in a chunk with room for
# it: at the end of a chunk, first in the next, alone at the list's end, and
# alone in a chunk between two full ones. Put back into the chunk before, a
# chunk's first item grew that chunk at every delete and Undo, until it was
# taller than where a chunk is parked, and hung over the list.
_ll_undo = {'end of a chunk': _ll_delete_undo(2 * _LL_N, _LL_N - 1),
            'first of a chunk': _ll_delete_undo(2 * _LL_N, _LL_N),
            'alone at the end': _ll_delete_undo(2 * _LL_N + 1, 2 * _LL_N),
            'alone between': _ll_delete_undo(3 * _LL_N, _LL_N, _LL_N - 1)}
check(f'an item deleted at the end of a chunk and put back stands there again, '
      f'as one first in its chunk or alone in it does ((chunk sizes, in order, '
      f'its chunk): {_ll_undo})',
      _ll_undo == {'end of a chunk': ([_LL_N, _LL_N], True, 0),
                   'first of a chunk': ([_LL_N, _LL_N], True, 1),
                   'alone at the end': ([_LL_N, _LL_N, 1], True, 2),
                   'alone between': ([_LL_N, 1, _LL_N], True, 1)})


# A chunk out of sight is parked beside the list, never over it, however tall
# it has grown; and one scrolled further into than its parking place stands at
# its true place. Parked only above, a chunk taller than its 20,000 px hung
# down over the rows in sight, and one scrolled 20,000 px into was drawn short
# of where it stood, its last rows never shown. TALLEST is lifted here, so
# long items make chunks that tall, as the fonts on each system decide.
_LLS = type(app._checklist_rows.stack)
_ll_tallest, _ll_every = _LLS.TALLEST, app._checklist_rows.every
_ll_park = {}
try:
    _LLS.TALLEST = 10 ** 9
    app._working_checklist = [{'text': f'000 {_LL_WORDS}', 'done': False}]
    app._render_checklist_items(); _ll_settle(6)
    _ll_h = max(1, app._checklist_rows.rows()[0].winfo_height())
    _ll_k = app._checklist_rows.every = max(2, int(25_000 // _ll_h) + 1)
    app._working_checklist = [{'text': f'{i:03d} {_LL_WORDS}', 'done': False}
                              for i in range(3 * _ll_k)]
    app._render_checklist_items(); _ll_settle(10)
    _ll_stk, _ll_cv = app._checklist_rows.stack, app._checklist_canvas
    _ll_stk.size(); _ll_settle(4)
    _ll_hs = [c.winfo_height() for c in app._checklist_rows.chunks]
    _ll_park['chunks'] = _ll_hs

    def _ll_overlaps_view(c):
        """Whether *c* is drawn anywhere in the canvas's view."""
        x, y = c.winfo_x(), c.winfo_y()
        return (x < _ll_cv.winfo_width() and x + c.winfo_width() > 0
                and y < _ll_cv.winfo_height() and y + c.winfo_height() > 0)

    def _ll_out_of_view(c):
        box, top = _ll_stk.box(c), _ll_cv.canvasy(0)
        return box[3] <= top or box[1] >= top + _ll_cv.winfo_height()

    if len(_ll_hs) == 3 and all(_LLS.PARK < h < 32_000 for h in _ll_hs):
        _ll_cv.yview_moveto(0); _ll_settle(4)
        _ll_park['parked over the view'] = [
            k for k, c in enumerate(app._checklist_rows.chunks)
            if _ll_out_of_view(c) and _ll_overlaps_view(c)]
        _ll_c1 = app._checklist_rows.chunks[1]
        _ll_cv.yview_moveto((_ll_stk.box(_ll_c1)[1] + _LLS.PARK + 1000) / _ll_stk.total)
        _ll_settle(6)
        _ll_top = _ll_cv.canvasy(0)
        _ll_park['rows in sight, true and drawn'] = [
            (int(_ll_stk.box(_ll_c1)[1] + r.winfo_y() - _ll_top),
             r.winfo_rooty() - _ll_cv.winfo_rooty())
            for r in _ll_c1.winfo_children()
            if -r.winfo_height() < _ll_stk.box(_ll_c1)[1] + r.winfo_y() - _ll_top
            < _ll_cv.winfo_height()]
finally:
    _LLS.TALLEST, app._checklist_rows.every = _ll_tallest, _ll_every
check(f'a chunk taller than its parking place is parked beside the list, not over '
      f'it, and stands at its true place when scrolled further into ({_ll_park})',
      _ll_park.get('parked over the view') == []
      and len(_ll_park.get('rows in sight, true and drawn', [])) >= 1
      and all(abs(t - d) <= 2 for t, d in _ll_park['rows in sight, true and drawn']))

# ...and a list of tall items is built in chunks that stay inside 16 bits:
# thirty-two items of 100 lines made one chunk past the 32,767 px X and
# Windows place a window within. A chunk takes no row more once it is
# RowStack.TALLEST tall, by its rows' heights as they are made.
app._working_checklist = [{'text': f'{i:02d} ' + 'line\n' * 99 + 'end', 'done': False}
                          for i in range(40)]
app._render_checklist_items(); _ll_settle(10)
app._checklist_rows.stack.size(); _ll_settle(4)
_ll_hs = [c.winfo_reqheight() for c in app._checklist_rows.chunks]
_ll_rows = app._checklist_rows.rows()
_ll_ok, _ll_said = _ll_reaches(app, app._checklist_canvas, _ll_rows[-1], _ll_settle)
check(f'a checklist of 40 items of 100 lines is built in chunks inside 16 bits, '
      f'its last item drawn at its end ({_ll_said}; {len(_ll_hs)} chunks, the '
      f'tallest {max(_ll_hs)} px)',
      _ll_ok and max(_ll_hs) < 32_767 and len(_ll_hs) > 2)

# ...and long items moved together by the keyboard do not gather in one chunk:
# each trade over a chunk's edge brings one in, and enough of them passed what
# X and Windows can place. Past four times TALLEST the rows are chunked again.
# TALLEST is lowered here, so two items of 100 lines are enough.
_ll_tall = 'line\n' * 99 + 'end'
app._working_checklist = (
    [{'text': f's{i}', 'done': False} for i in range(3)]
    + [{'text': f'Ta {_ll_tall}', 'done': False}, {'text': f'Tb {_ll_tall}', 'done': False}]
    + [{'text': f's{i}', 'done': False} for i in range(5, 8)])
_ll_grp = app._checklist_rows
_ll_gather = {}
try:
    _LLS.TALLEST = 600
    app._render_checklist_items(); _ll_settle(6)
    _ll_gather['chunks made'] = [len(c.winfo_children()) for c in _ll_grp.chunks]

    def _ll_box_of(prefix):
        rec = next(r for r in app._checklist_drawn['rows']
                   if r[0]['text'].startswith(prefix))
        return next(c for c in rec[1].winfo_children() if isinstance(c, tk.Checkbutton))

    for _ll_who in ('Tb', 'Tb', 'Ta'):
        _ll_b = _ll_box_of(_ll_who)
        if _ll_focus(_ll_b):
            _ll_b.event_generate('<Alt-Up>')
            _ll_settle(3)
    _ll_gather['order'] = [it['text'][:2] for it in app._working_checklist]
    _ll_gather['tallest chunk'] = max(_ll_grp.height(c) for c in _ll_grp.chunks)
    _ll_gather['keyboard on Ta'] = str(app.tk.call('focus')) == str(_ll_box_of('Ta'))
finally:
    _LLS.TALLEST = _ll_tallest
check(f'long checklist items moved together by Alt+Up are chunked again before '
      f'one chunk holds them all ({_ll_gather})',
      _ll_gather.get('chunks made') == [4, 1, 3]
      and _ll_gather.get('order') == ['s0', 's1', 'Tb', 'Ta', 's2', 's5', 's6', 's7']
      and _ll_gather.get('tallest chunk', 10 ** 9) <= 4 * 600
      and _ll_gather.get('keyboard on Ta') is True)

# A scroll step moves only the chunks in the view, or coming into it or leaving
# it: one stood at its true place for a view above and two below, and every
# step moved them all, 7.4 a step at 1,000 items, 18 ms on Windows. And short
# items go 32 to a chunk, so fewer move.
app._working_checklist = [{'text': f'item {i:04d}', 'done': False} for i in range(1000)]
app._render_checklist_items(); _ll_settle(10)
_ll_stk, _ll_cv = app._checklist_rows.stack, app._checklist_canvas
_ll_cv.yview_moveto(0.5); _ll_settle(4)


def _ll_in_sight():
    top, view = _ll_cv.canvasy(0), _ll_cv.winfo_height()
    return {c for c in app._checklist_rows.chunks
            if _ll_stk.box(c) is not None and _ll_stk.box(c)[3] > top
            and _ll_stk.box(c)[1] < top + view}


_ll_moves = []
tk.Frame.place_configure = (lambda self, *a, **k:
                            (_ll_moves.append(self), tk.Place.place_configure(self, *a, **k))[1])
_ll_strays, _ll_all_moves = [], 0
_ll_chunkset = set(app._checklist_rows.chunks)
try:
    for _ in range(90):
        _ll_before = _ll_in_sight()
        del _ll_moves[:]
        _ll_cv.yview_scroll(1, 'units'); app.update_idletasks(); app.update()
        _ll_moved_now = [c for c in _ll_moves if c in _ll_chunkset]
        _ll_all_moves += len(_ll_moved_now)
        _ll_strays += [c for c in _ll_moved_now
                       if c not in _ll_before | _ll_in_sight()]
finally:
    del tk.Frame.place_configure
check(f'a scroll step of a 1,000-item checklist moves only the chunks in sight '
      f'({_ll_all_moves} moves in 90 steps, {len(_ll_strays)} of chunks out of '
      f'sight; {len(app._checklist_rows.chunks)} chunks)',
      _ll_all_moves > 0 and not _ll_strays
      and len(app._checklist_rows.chunks) <= 1000 // 32 + 1)
app._working_checklist = []
app._render_checklist_items()
app.new_note(); _ll_settle()

# The template picker, with the 1,000 templates a notebook may hold. End goes
# to the last of them and shows it; Up from there goes to the one before.
app.templates = [{'name': 'Template %04d' % i, 'title': '', 'body': 'x',
                  'comments': '', 'category': 'General', 'checklist': []}
                 for i in range(1000)]
app.show_template_picker(); _ll_settle(10)
_ll_pop = app._mini_popup
_ll_btns = [b for b in _ll_all(_ll_pop) if isinstance(b, tk.Button)
            and 'Template ' in str(b.cget('text'))]
_ll_view = _ll_stack_canvas(_ll_pop)
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_btns[-1], _ll_settle)
                    if _ll_view is not None and _ll_btns else (False, 'no picker'))
_ll_keys = []
if _ll_ok:
    _ll_view.yview_moveto(0); _ll_settle()
    if _ll_focus(_ll_btns[0]):
        _ll_btns[0].event_generate('<End>'); _ll_settle(4)
        _ll_keys.append(str(app.tk.call('focus')) == str(_ll_btns[-1])
                        and _ll_in_view(_ll_btns[-1], _ll_view))
        _ll_btns[-1].event_generate('<Up>'); _ll_settle(4)
        _ll_keys.append(str(app.tk.call('focus')) == str(_ll_btns[-2])
                        and _ll_in_view(_ll_btns[-2], _ll_view))
check(f'the picker with 1,000 templates scrolls to the last; End takes the '
      f'keyboard there, in sight, and Up to the one before ({_ll_said}; {_ll_keys})',
      _ll_ok and _ll_keys == [True, True])
app._dismiss_mini_popup(); _ll_settle()

# The template editor, its checklist 70 of the longest items: its Add box and
# Category at the end; an item typed there is drawn where it can be seen, and
# Tab from the last row, drawn again since, goes on to the Add box.
_ll_tpl = {'name': 'Long', 'title': '', 'body': '', 'comments': '',
           'category': 'General',
           'checklist': [{'text': f'{i:02d} {_LL_WORDS}', 'done': False}
                         for i in range(70)]}
app.templates = [_ll_tpl]
app._edit_template(_ll_tpl, lambda: None); _ll_settle(10)
_ll_pop = app._mini_popup
_ll_view = _ll_stack_canvas(_ll_pop)
_ll_stack = _ll_view._row_stack if _ll_view is not None else None
_ll_tail = _ll_stack.groups[-1].rows() if _ll_stack is not None else []
_ll_add = next((e for t in _ll_tail[:1] for e in _ll_all(t)
                if isinstance(e, tk.Entry)), None)
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_tail[-1], _ll_settle)
                    if _ll_tail else (False, 'no editor'))
_ll_seen = {'its Add box': _ll_add is not None and _ll_in_view(_ll_add, _ll_view)}
if _ll_add is not None and _ll_focus(_ll_add):
    _ll_add.insert(0, 'NEWEST ITEM')
    _ll_add.event_generate('<Return>'); _ll_settle(6)
    _ll_new = _ll_text(_ll_stack.groups[1].rows()[-1], 'NEWEST ITEM')
    if _ll_new is not None:
        app._bring_into_sight(_ll_new); _ll_settle(4)
    _ll_seen['the item typed there'] = (_ll_new is not None
                                        and _ll_in_view(_ll_new, _ll_view))
    _ll_icons = [c for c in _ll_stack.groups[1].rows()[-1].winfo_children()
                 if getattr(c, '_icon_kind', None) == 'trash']
    if _ll_icons and _ll_focus(_ll_icons[0]):
        _ll_icons[0].event_generate('<Tab>'); _ll_settle(4)
        _ll_seen['Tab from the last row'] = str(app.tk.call('focus')) == str(_ll_add)
check(f'the template editor with 70 long checklist items scrolls to its Add box '
      f'and Category ({_ll_said}; {_ll_seen})',
      _ll_ok and len(_ll_seen) == 3 and all(_ll_seen.values()))
app._dismiss_mini_popup(); _ll_settle()


# A table in a template's body given more columns, at the same height and
# with no scrollbar of its own: no chunk changes height, and the editor is
# measured again for it all the same. Columns are added until the preview
# is wider than the editor was, as the fonts on each system decide.
_ll_tpl = {'name': 'Wide', 'title': '', 'body': '| c0 | c1 |\n| x | x |',
           'comments': '', 'category': 'General', 'checklist': []}
app._edit_template(_ll_tpl, lambda: None); _ll_settle(10)
_ll_pop = app._mini_popup
_ll_view = _ll_stack_canvas(_ll_pop)
_ll_body = next((t for t in _ll_all(_ll_pop) if isinstance(t, tk.Text)
                 and '| c0 |' in t.get('1.0', 'end')), None)
_ll_wide = None
if _ll_view is not None and _ll_body is not None and _ll_focus(_ll_body):
    _ll_was = _ll_view.winfo_width()
    _ll_prev = next((c for c in _ll_all(_ll_pop) if isinstance(c, tk.Canvas)
                     and c.find_all() and c is not _ll_view), None)
    _ll_tall = int(str(_ll_prev.cget('height'))) if _ll_prev is not None else None
    for _ll_n in range(3, 40):
        _ll_body.delete('1.0', 'end')
        _ll_body.insert('1.0', '| ' + ' | '.join('c%d' % i for i in range(_ll_n))
                        + ' |\n| ' + ' | '.join('x' * _ll_n) + ' |')
        _ll_body.event_generate('<KeyRelease-a>'); _ll_settle(4)
        if (_ll_prev is None or getattr(_ll_prev, '_preview_overflows_x', False)
                or int(str(_ll_prev.cget('width'))) > _ll_was + 20):
            break
    _ll_settle(6)
    if _ll_prev is not None:
        _ll_wide = {'before': _ll_was, 'after': _ll_view.winfo_width(),
                    'preview': int(str(_ll_prev.cget('width'))),
                    'same height': int(str(_ll_prev.cget('height'))) == _ll_tall,
                    'no scrollbar': not getattr(_ll_prev, '_preview_overflows_x', True),
                    'shown whole': _ll_prev.winfo_rootx() + int(str(_ll_prev.cget('width')))
                    <= _ll_view.winfo_rootx() + _ll_view.winfo_width() + 1}
check(f'a template\'s table given more columns at the same height widens its '
      f'editor to show it whole ({_ll_wide})',
      _ll_wide is not None and _ll_wide['preview'] > _ll_wide['before']
      and _ll_wide['same height'] and _ll_wide['no scrollbar']
      and _ll_wide['after'] > _ll_wide['before'] and _ll_wide['shown whole'])
app._dismiss_mini_popup(); _ll_settle()

# Settings > Templates, the only place a template is deleted: its last row's
# pencil, at the end, opens that template.
app.templates = [{'name': 'Template %04d' % i, 'title': '', 'body': 'x',
                  'comments': '', 'category': 'General', 'checklist': []}
                 for i in range(1000)]
app.show_settings_page(); app.toggle_settings_panel('templates'); _ll_settle(10)
_ll_view = app._active_panel_canvas
_ll_pencils = [c for c in _ll_all(_ll_view) if getattr(c, '_icon_kind', None) == 'pencil']
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_pencils[-1], _ll_settle)
                    if _ll_pencils else (False, 'no rows'))
_ll_opened = None
if _ll_ok and _ll_focus(_ll_pencils[-1]):
    _ll_pencils[-1].event_generate('<space>'); _ll_settle(6)
    _ll_opened = getattr(app._mini_popup, 'edited_template', None)
check(f'Settings > Templates with 1,000 templates scrolls to the last, whose '
      f'pencil opens it ({_ll_said}; opened {(_ll_opened or {}).get("name")})',
      _ll_ok and _ll_opened is app.templates[-1])
app._dismiss_mini_popup(); _ll_settle()
# Emptied again before the next section: on Windows every widget is a window,
# and a process may hold only 10,000 of them (a long list left built here and
# another built beside it ran Tk out of them: "No more menus can be allocated").
app.templates = []
app._refresh_templates_panel(); _ll_settle()

# Recently deleted, a page as long as the Trash: its last row's box ticks.
app.trash = [{'id': 70000 + i, 'uid': f'll-{i}', 'title': f'Gone {i:04d}',
              'body': 'x', 'category': 'General',
              'deleted_at': f'2026-10-{1 + i % 25:02d} 10:{i % 60:02d}:00'}
             for i in range(1000)]
app.TRASH_PAGE_SIZE = 1000
app.toggle_settings_panel('trash'); _ll_settle(10)
_ll_view = app._active_panel_canvas
_ll_ticks = [c for r in _ll_view._row_stack.rows()
             if getattr(r, '_trash_buttons', None)
             for c in r.winfo_children() if isinstance(c, tk.Checkbutton)]
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_ticks[-1], _ll_settle)
                    if _ll_ticks else (False, 'no rows'))
_ll_picked = None
if _ll_ok and _ll_focus(_ll_ticks[-1]):
    _ll_ticks[-1].event_generate('<space>'); _ll_settle(4)
    _ll_picked = [str(b.cget('text')) for b in _ll_all(app.settings_trash_panel)
                  if isinstance(b, tk.Button) and str(b.cget('text')).startswith('↩')
                  and b.winfo_manager()]
check(f'Recently deleted with 1,000 rows on its page scrolls to the last, whose '
      f'box ticks ({_ll_said}; {_ll_picked})',
      _ll_ok and _ll_picked == ['↩ Restore 1 selected'])

del app.TRASH_PAGE_SIZE
app.trash = []
app._trash_panel_redraw(); _ll_settle()

# Duplicates: one note copied 2,400 times is one group as long as all of
# them; its own buttons stand at its end.
app.notes = [_ll_note(90000 + i, title='Twin', body='same',
                      created='2026-01-01 10:00:00', updated='2026-01-01 10:00:00')
             for i in range(2400)]
app.toggle_settings_panel('duplicates'); _ll_settle(10)
_ll_view = app._active_panel_canvas
_ll_btn = [b for b in _ll_all(_ll_view) if isinstance(b, tk.Button)
           and str(b.cget('text')) == 'Tick all but first']
_ll_boxes = [c for c in _ll_all(_ll_view) if isinstance(c, tk.Checkbutton)]
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_btn[-1], _ll_settle)
                    if _ll_btn else (False, 'no group'))
_ll_last_ticked = None
if _ll_ok and _ll_focus(_ll_btn[-1]):
    _ll_btn[-1].event_generate('<space>'); _ll_settle(6)
    _ll_last_ticked = int(app.getvar(_ll_boxes[-1].cget('variable')))
check(f'Duplicates with a group of 2,400 copies scrolls to the group\'s own '
      f'buttons, which tick its copies ({_ll_said}; last copy {_ll_last_ticked})',
      _ll_ok and _ll_last_ticked == 1)
app.notes = []
app.toggle_settings_panel('duplicates'); _ll_settle()
app.hide_settings_page(); _ll_settle()

# Share: 2,500 notes, every page shown, the last box ticks. The two images
# every drawn tick box shows are painted once, not for each box made: each
# paint redrew every box before it, and these 2,500 took 150 s on Windows.
app.notes = [_ll_note(80000 + i, title=f'Shared {i:04d}') for i in range(2500)]
_ll_paints = []
_ll_paint = app._paint_tick_images
app._paint_tick_images = lambda: (_ll_paints.append(1), _ll_paint())[1]
app.toggle_share_panel(); _ll_settle(6)
_ll_view = app._share_checklist_canvas
for _ in range(40):
    _ll_more = next((b for b in _ll_all(_ll_view) if isinstance(b, tk.Button)
                     and 'more' in str(b.cget('text'))), None)
    if _ll_more is None:
        break
    _ll_more.invoke(); app.update()
_ll_settle(6)
del app._paint_tick_images
_ll_boxes = [c for c in _ll_all(_ll_view) if isinstance(c, tk.Checkbutton)]
check(f'2,500 drawn tick boxes paint the images they share no more than once '
      f'({len(_ll_paints)} paints for {len(_ll_boxes)} boxes)',
      len(_ll_boxes) == 2500 and len(_ll_paints) <= 1)
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_boxes[-1], _ll_settle)
                    if _ll_boxes else (False, 'no boxes'))
_ll_shared = None
if _ll_ok and _ll_focus(_ll_boxes[-1]):
    _ll_boxes[-1].event_generate('<space>'); _ll_settle(2)
    _ll_shared = (len(_ll_boxes), int(app.getvar(_ll_boxes[-1].cget('variable'))))
check(f'Share with every page of 2,500 notes shown scrolls to the last box, '
      f'which ticks ({_ll_said}; {_ll_shared})',
      _ll_ok and _ll_shared == (2500, 1))
app.toggle_share_panel(); _ll_settle()

# A day holding 1,000 notes: its list scrolls to the last, which opens.
app.notes = [_ll_note(60000 + i, title=f'Day note {i:04d}', date='2026-11-03')
             for i in range(1000)]
app.notebook.select(app.TAB_CALENDAR)
app.cal_year, app.cal_month = 2026, 11
app.render_calendar(); _ll_settle(4)
app.open_day_popup('2026-11-03'); _ll_settle(10)
_ll_view = _ll_stack_canvas(app.day_panel)
_ll_days = [r for r in (_ll_view._row_stack.rows() if _ll_view is not None else [])
            if getattr(r, '_key_press', None)]
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_days[-1], _ll_settle)
                    if _ll_days else (False, 'no rows'))
_ll_title = str(_ll_text(_ll_days[-1]).cget('text')) if _ll_days else ''
_ll_open = None
if _ll_ok and _ll_focus(_ll_days[-1]):
    _ll_days[-1].event_generate('<Return>'); _ll_settle(4)
    _ll_open = (app._day_panel_mode, (app._day_panel_shows or (None,) * 3)[2])
check(f'a day of 1,000 notes scrolls to the last, which Return opens '
      f'({_ll_said}; {_ll_title!r} -> {(_ll_open or ("",))[0]})',
      _ll_ok and _ll_open is not None and _ll_open[0] == 'note'
      and str((_ll_open[1] or {}).get('title', '')) in _ll_title)
app.close_day_panel(); _ll_settle()

# The calendar's History: 30 series of 50 days, each unfolded to its days (a
# series of 50 or fewer lists them all). The page under it is a row stack
# too, the month in one chunk and the days in their own.
app.notes = [_ll_note(95000 + s, title=f'Routine {s:02d}',
                      date=f'2025-{1 + s % 12:02d}-01',
                      recurrence={'freq': 'daily', 'interval': 1, 'count': 50})
             for s in range(30)]
app._show_calendar_history(); _ll_settle(6)
app._history_expanded = {95000 + s for s in range(30)}
app._render_calendar_history(); _ll_settle(10)
_ll_days = [r for r in app._history_rows.rows() if getattr(r, '_key_press', None)]
_ll_ok, _ll_said = (_ll_reaches(app, app.cal_scroll_canvas, _ll_days[-1], _ll_settle)
                    if _ll_days else (False, 'no rows'))
_ll_title = str(_ll_text(_ll_days[-1]).cget('text')) if _ll_days else ''
_ll_landed = None
if _ll_ok and _ll_focus(_ll_days[-1]):
    _ll_days[-1].event_generate('<Return>'); _ll_settle(6)
    _ll_landed = (app._history_visible, app.selected_day)
check(f'the History with 30 series of 50 days unfolded scrolls to its last day, '
      f'which Return opens ({_ll_said}; {len(_ll_days)} rows; {_ll_title!r} -> '
      f'{_ll_landed})',
      _ll_ok and _ll_landed is not None and _ll_landed[0] is False
      and bool(_ll_landed[1]) and NO.show_date(_ll_landed[1]) in _ll_title)
if app._history_visible:
    app._hide_calendar_history()
app.close_day_panel(); _ll_settle()

# The calculator's history after a long sitting: its oldest line inserts.
app.notebook.select(app.TAB_NOTES)
app.new_note(); _ll_settle()
if not app._calculator_open:
    app.toggle_calculator_section()
if not app._calc_history_open:
    app._toggle_calc_history()
app._calc_history = ['%d+1=%d' % (i, i + 1) for i in range(2500)][::-1]
app._calc_render_history(); _ll_settle(10)
_ll_lines = [w for w in app.calculator_history_rows.rows()
             if isinstance(w, tk.Label) and '<Button-1>' in w.bind()]
_ll_view = app.calculator_history_rows.stack.canvas
_ll_ok, _ll_said = (_ll_reaches(app, _ll_view, _ll_lines[-1], _ll_settle)
                    if _ll_lines else (False, 'no lines'))
if _ll_ok:
    _qa_click(_ll_lines[-1]); _ll_settle(2)
check(f'the calculator\'s history of 2,500 sums scrolls to the oldest, which a '
      f'click inserts ({_ll_said})',
      _ll_ok and '0+1=1' in app.body_text.get('1.0', 'end'))
app._calc_history = []
app._calc_render_history()
app.new_note(); _ll_settle()

del app._show_toast
app.ask_yes_no = _ll_yes
app.notes, app.templates, app.trash = (list(_ll_kept[0]), list(_ll_kept[1]),
                                       list(_ll_kept[2]))
app.save_notes()


print()
print(f"=== QA2 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
