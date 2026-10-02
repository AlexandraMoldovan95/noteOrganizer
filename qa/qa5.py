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
from _qa_support import click as _qa_click, pin_popup_visibility as _qa_pin
from _qa_support import waiting_timers as _qa_waiting
_qa_pin(NO)
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

def safe(name, fn):
    try:
        fn()
        check(name, True)
    except Exception as e:
        check(f'{name} ({type(e).__name__}: {e})', False)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

# ---- CORRUPT / MISSING FIELD NOTES DON'T CRASH THE APP ----
app.notes = [
    {'id':1,'title':None,'body':None,'comments':None,'category':None,'date':None,
     'color':None,'pinned':None,'attachments':None},
    {'id':2},  # nearly empty
    {'id':3,'title':'ok','body':'ok','category':'DoesNotExist','checklist':'not a list'},
]
def all_ops():
    app.refresh_note_list()
    app.render_calendar()
    NO.find_duplicate_groups(app.notes)
    app.update()
safe('all operations survive corrupt notes', all_ops)

# normalize_note repairs bad data
n = NO.normalize_note({'id':1,'title':None,'checklist':'garbage','attachments':None})
check('normalize_note coerces bad checklist to empty list', n['checklist']==[])
check('normalize_note coerces None attachments to empty list', n['attachments']==[])
check('normalize_note fills missing category with General', n.get('category')=='General')

# ---- SPECIAL CHARACTERS / UNICODE ----
app.new_note()
app.title_entry.delete(0,'end'); app.title_entry.insert(0,'Emoji 🎉 title & <script>alert(1)</script>')
app.body_text.insert('1.0', 'Ünïcödé bödy with 中文 and \n newlines \t tabs')
app.save_current_note(auto=False)
app.update()
special_note = app.find_note(app.selected_note_id)
check('special chars + unicode survive save', '🎉' in special_note['title'] and '中文' in special_note['body'])

# ---- RAPID SAVE SPAM doesn't create duplicates ----
app.new_note()
app.title_entry.insert(0,'SpamTest')
app.body_text.insert('1.0','x')
before = len(app.notes)
for _ in range(10):
    app.save_current_note(auto=False)
    app.update()
after = len(app.notes)
check('rapid save spam creates exactly one note, not 10', after==before+1)

# ---- INVALID DATES handled gracefully ----
app.new_note()
app.title_entry.insert(0,'BadDate')
app.body_text.insert('1.0','x')
app.date_entry.delete(0,'end'); app.date_entry.insert(0,'not-a-date')
def bad_date_save():
    app.save_current_note(auto=False)
    app.update()
safe('invalid date input handled gracefully', bad_date_save)

# ---- DATE FIELD AUTOSAVE (regression: typing a date had no autosave
# binding at all, so a typed date change was silently lost) ----
app.new_note()
app.title_entry.insert(0,'DateAutosaveTest')
app.body_text.insert('1.0','x')
app.save_current_note(auto=False)
app.update()
app.date_entry.delete(0,'end')
app.date_entry.insert(0,'2026-12-25')
# A generated KEY event follows the FOCUS, wherever it was aimed — with
# focus elsewhere this KeyRelease lands there instead and the positive
# check below reads a false red under load. Force + poll first.
import time as _t5f
app.date_entry.focus_force()
for _ in range(60):
    app.update(); app.update_idletasks()
    if app.focus_get() is app.date_entry:
        break
    _t5f.sleep(0.01)
# The REQUEST is counted, not the pending timer. A queued job is a fact
# about a moment: between the keystroke and the read there is an update(),
# and on a loaded machine that can outlast the 500ms debounce -- the timer
# fires, the job is cleared, and the check reports a missing request about
# an app that made one. A sibling of this shape went red on CI while
# passing here three times running; proved by pausing past the debounce,
# which turns the old form red on an unmodified app.
_d5_fired = {'n': 0}
_d5_real_now = app._autosave_now


def _d5_counting_now(*a, **k):
    _d5_fired['n'] += 1
    return _d5_real_now(*a, **k)


# Replacing _schedule_autosave here would catch nothing: every binding
# captured the bound method when it was bound. The timer captures
# _autosave_now at SCHEDULE time, which is after this line.
# Cleared and ASSERTED first. Without this the check passes on a job that
# was already pending from something earlier in this script, whatever the
# keystroke does -- which is exactly how the mutant that removed the
# <KeyRelease> binding survived it.
app._flush_autosave()
app.update()
check('fixture: no save is pending before the keystroke',
      getattr(app, '_autosave_job', None) is None)
app._autosave_now = _d5_counting_now
try:
    app.date_entry.event_generate('<KeyRelease>')
    app.update()
finally:
    app._autosave_now = _d5_real_now
check(f'typing a date schedules an autosave '
      f'(pending={getattr(app, "_autosave_job", None) is not None}, '
      f'fired={_d5_fired["n"]})',
      getattr(app, '_autosave_job', None) is not None or _d5_fired['n'] >= 1)
# Flush it now rather than leaving it pending — the same thing the real app
# does when switching notes. Left dangling, this timer could fire later in
# this script (e.g. after a subsequent test clears app.notes entirely),
# pointing at a note that's no longer there.
app._flush_autosave()
app.update()

# ---- HUGE NOTE (50k chars) ----
app.new_note()
app.title_entry.insert(0,'HugeNote')
app.body_text.insert('1.0', 'x'*50000)
def huge_note():
    app.save_current_note(auto=False)
    app.update()
safe('save 50k-char note', huge_note)

# ---- EMPTY STATE: no notes at all ----
app.notes = []
def empty_state():
    app.refresh_note_list()
    app.render_calendar()
    app.update()
safe('empty note list renders without error', empty_state)

# ---- PURGE survives bad deleted_at in trash ----
app.trash = [
    {'id':1,'title':'ok','deleted_at':'2026-01-01 00:00:00'},
    {'id':2,'title':'bad_date','deleted_at':'garbage'},
    {'id':3,'title':'missing_date'},
]
def purge():
    if hasattr(app, 'purge_old_trash'):
        app.purge_old_trash()
    app.update()
safe('purge survives bad deleted_at in trash', purge)

# ---- MULTI-SCRIPT INPUT ----
# The app's own functions speak English; the USER writes in whatever
# language they choose. The DATA guarantees are asserted on every CI
# platform through the core routes, which involve no display at all.
# The WIDGET routes run on Windows -- the platform the app ships on --
# because Linux's Xft font stack can segfault the Tk interpreter
# outright when asked to RENDER exotic glyph sequences (ZWJ emoji,
# complex scripts), which says nothing about the shipped product. Same
# rule as the pixel checks: aim the assertion, never delete it. Glyph
# shaping itself (RTL display) is the platform's job, eyeballed via
# the manual test plan.
import io as _mio, json as _mjson
_SCRIPTS = {
    'arabic':   'مرحبا بالعالم',
    'hebrew':   'שלום עולם',
    'chinese':  '你好世界',
    'japanese': 'こんにちは世界',
    'korean':   '안녕하세요 세계',
    'hindi':    'नमस्ते दुनिया',
    'cyrillic': 'Привет мир',
    'greek':    'Γειά σου Κόσμε',
    'emoji':    '👨‍👩‍👧‍👦✨',
}
_all_scripts = ' '.join(_SCRIPTS.values())
_mbody = (_all_scripts + chr(10)
          + '| ' + _SCRIPTS['arabic'] + ' | '
          + _SCRIPTS['chinese'] + ' |' + chr(10)
          + '| --- | --- |' + chr(10)
          + '| ' + _SCRIPTS['hindi'] + ' | '
          + _SCRIPTS['emoji'] + ' |')

# -- Data level, every platform: normalize -> share code -> export. --
_mnorm = NO.normalize_note({
    'id': 424242, 'title': ('多言語 ' + _SCRIPTS['arabic'])[:80],
    'body': _mbody, 'comments': _SCRIPTS['hebrew'],
    'checklist': [{'text': _SCRIPTS['korean'], 'done': False}]})
check('multi-script: normalize_note keeps every script intact',
      all(v in (_mnorm['title'] + _mnorm['body'] + _mnorm['comments']
                + _mjson.dumps(_mnorm['checklist'], ensure_ascii=False))
          for v in _SCRIPTS.values()))

# Share codes carry the note's content -- checklist included since the
# field joined SHAREABLE_FIELDS; attachments stay home by design.
from noteorganizer.core import sharing as _msharing
_mback = _msharing.decode_share_code(
    _msharing.encode_share_code([_mnorm]))
check('multi-script: a share code round-trips every script unchanged',
      bool(_mback)
      and all(v in (_mback[0]['title'] + _mback[0]['body']
                    + _mback[0].get('comments', ''))
              for v in _SCRIPTS.values())
      and _SCRIPTS['korean'] in _mjson.dumps(
          _mback[0].get('checklist', []), ensure_ascii=False))

_mhtml = app._note_export_content(_mnorm, 'html', _mnorm['title'])
check('multi-script: the HTML export carries every script',
      all(v in _mhtml for v in _SCRIPTS.values()))

# -- Widget level, the shipping platform's real routes. --
if sys.platform == 'win32':
    app.new_note()
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, _mnorm['title'])
    app.body_text.insert('1.0', _mbody)
    app.comments_text.insert('1.0', _SCRIPTS['hebrew'])
    app._working_checklist = [{'text': _SCRIPTS['korean'], 'done': False}]
    app._render_table_grids()
    app.update()
    app.save_current_note(auto=False)
    app.update()
    _msid = app.selected_note_id
    _mdisk = _mjson.load(_mio.open('notes_data.json', encoding='utf-8'))
    _mnote = next(n for n in _mdisk if n['id'] == _msid)
    _mflat = (_mnote['title'] + _mnote['body'] + _mnote.get('comments', '')
              + _mjson.dumps(_mnote.get('checklist', []),
                             ensure_ascii=False))
    check('multi-script: every script survives the disk round-trip intact',
          all(v in _mflat for v in _SCRIPTS.values()))

    _mgrid = app._grid_at_line(2)
    check('multi-script: a table cell holds Devanagari and renders as a grid',
          _mgrid is not None
          and _mgrid['cells'][(1, 0)]['value'] == _SCRIPTS['hindi'])

    app._open_find()
    app._find_var.set(_SCRIPTS['hindi'])
    app._find_rescan(reveal=True)
    app.update()
    _mhits = list(app._find_matches)
    check('multi-script: find-in-note matches Devanagari in prose AND cell',
          any(m['kind'] == 'prose' for m in _mhits)
          and any(m['kind'] == 'cell' for m in _mhits))
    app._close_find()
    app.update()

    app.search_var.set(_SCRIPTS['chinese'])
    app.update()
    app.refresh_note_list()
    app.update()
    _mq = app.search_var.get().lower()
    check('multi-script: the sidebar search query lowercases safely and '
          'matches the note body',
          _mq == _SCRIPTS['chinese'] and _mq in _mnote['body'])
    app.search_var.set('')
    app.update()
else:
    print('SKIP multi-script widget routes (non-Windows display stack; '
          'asserted in full on the Windows CI job)')

# ============================================================
# CORRUPT NOTES FILE AT STARTUP: LOUD, PRESERVED, NEVER SILENT
# ============================================================
# A notes_data.json that fails to parse used to become an empty notebook
# with no trace — and the next save overwrote the corrupt file, turning
# recoverable corruption into permanent loss. The loader now preserves
# the unreadable original aside and the startup notice says so plainly.
import glob as _glob5, time as _time5
with open('notes_data.json', 'w', encoding='utf-8') as _f5:
    _f5.write('this is not json')
_msgs5 = []
app5c = NO.NoteOrganizer(); app5c._poll_active_dirty = lambda: None
app5c.show_info = lambda t, m: _msgs5.append((t, m))
_t05 = _time5.time()
while not _msgs5 and _time5.time() - _t05 < 3:
    app5c.update(); _time5.sleep(0.05)
_corr5 = _glob5.glob('notes_data_corrupt_*.json')
check('corrupt notes file at startup surfaces a message', bool(_msgs5))
check('the message says the file was unreadable and preserved where',
      bool(_msgs5) and 'could not be read' in _msgs5[0][1]
      and 'notes_data_corrupt_' in _msgs5[0][1])
check('the unreadable original was preserved bit for bit',
      bool(_corr5)
      and open(_corr5[0], encoding='utf-8').read() == 'this is not json')
check('the app starts with an empty list, not a crash', app5c.notes == [])
app5c.destroy()

# When even the preserve fails, the notice must still appear and carry
# the do-not-save warning — the corrupt flag travels separately from
# the copy's path, precisely so this branch cannot go silent.
from noteorganizer.core import storage as _st5
_real_pres5 = _st5._preserve_corrupt
_st5._preserve_corrupt = lambda p: None
with open('notes_data.json', 'w', encoding='utf-8') as _f5:
    _f5.write('also not json')
_msgs5b = []
app5d = NO.NoteOrganizer(); app5d._poll_active_dirty = lambda: None
app5d.show_info = lambda t, m: _msgs5b.append((t, m))
_t05b = _time5.time()
while not _msgs5b and _time5.time() - _t05b < 3:
    app5d.update(); _time5.sleep(0.05)
_st5._preserve_corrupt = _real_pres5
check('a failed preserve is announced with the do-not-save warning',
      bool(_msgs5b)
      and 'Preserving a copy of it also failed' in _msgs5b[0][1])
app5d.destroy()

# ============================================================
# A POISONED RECURRENCE INTERVAL CANNOT MAKE THE APP UNLAUNCHABLE
# ============================================================
# A hand-edited notes_data.json (or a crafted share code) carrying an
# enormous interval used to overflow timedelta in expand_occurrences —
# and the calendar renders at startup, so the whole app crashed on
# launch. The normalize_recurrence clamp closes it at the choke point;
# here the app is built AND its calendar rendered against such a file.
import json as _json5e
with open('notes_data.json', 'w', encoding='utf-8') as _f5e:
    _json5e.dump([{'id': 1, 'title': 'Poison', 'body': 'x',
                   'category': 'General', 'date': '2026-01-01',
                   'recurrence': {'freq': 'daily', 'interval': 10 ** 10},
                   'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
                   'checklist': [], 'attachments': [],
                   'exceptions': [], 'overrides': {}}], _f5e)
_launched = True
try:
    app5e = NO.NoteOrganizer(); app5e._poll_active_dirty = lambda: None
    app5e.show_info = lambda *a, **k: True
    app5e.cal_year, app5e.cal_month = 2026, 9
    app5e.render_calendar()
    app5e.update()
except Exception:
    _launched = False
check('the app launches and renders the calendar despite a poisoned interval',
      _launched)
if _launched:
    check('the poisoned interval was clamped on load',
          app5e.notes and app5e.notes[0]['recurrence']['interval']
          == NO.normalize_recurrence({'freq': 'daily', 'interval': 10 ** 10})['interval'])
    app5e.destroy()

# ---- The setup notice only speaks when it did something (T2-1) ----
# The one-time cleanup runs whenever settings.json lacks its flag, which
# on a fresh install is always -- and it announced itself regardless. The
# literal first screen of the product was a blocking modal reading
# "Cleanup pass (runs once): ... 0 note(s) remain, IDs renumbered 1-0":
# internal maintenance vocabulary, about nothing, over an empty notebook.
app5f = NO.NoteOrganizer()
app5f._poll_active_dirty = lambda: None
app5f.update()
_notices = []
app5f.show_info = lambda title, msg, **k: (_notices.append((title, msg)), True)[1]

app5f._version_backup_path = None
app5f._corrupt_notes_report = None
app5f._cleanup_report = ({'before': 0, 'empty_removed': 0,
                          'duplicates_removed': 0, 'after': 0}, None)
app5f.announce_startup_changes()
app5f.update()
check('a cleanup that changed nothing says nothing', _notices == [])

app5f._cleanup_report = ({'before': 5, 'empty_removed': 1,
                          'duplicates_removed': 2, 'after': 2}, None)
app5f.announce_startup_changes()
app5f.update()
check('a cleanup that DID something still reports it, in plain words',
      len(_notices) == 1 and '1 empty note(s)' in _notices[0][1]
      and 'removed' in _notices[0][1]
      # the words the product review flagged as maintenance vocabulary
      # must be gone from a dialog that reports a permanent deletion
      and 'Cleanup pass' not in _notices[0][1]
      and 'renumbered' not in _notices[0][1]
      and 'setup complete' not in _notices[0][0])

# ---- Categories brought back from the notes are announced ----
# When settings.json has lost categories the notes are filed under, the
# load now puts them back with default colours instead of re-filing the
# notes to General. The colours change, so the user is told why.
_notices.clear()
app5f._cleanup_report = None
app5f._categories_adopted = ['Clients 2026', 'Gym']
app5f.announce_startup_changes()
app5f.update()
check('categories recovered from the notes are named in the startup notice',
      len(_notices) == 1 and 'Clients 2026' in _notices[0][1]
      and 'Gym' in _notices[0][1] and 'default colours' in _notices[0][1])
app5f._categories_adopted = []

# ---- The migration notice says only what is true ----
# A fixed tail followed every migration message: "the script and
# dist\NoteOrganizer.exe both read this same folder, so they can never
# drift apart" -- false in source mode after a reclaim, jargon in the
# built app.
_notices.clear()
_mig_was = NO.MIGRATION_INFO
NO.MIGRATION_INFO = 'Copied your notebook into the app folder: X'
try:
    app5f.announce_startup_changes()
    app5f.update()
finally:
    NO.MIGRATION_INFO = _mig_was
check('the migration notice carries no promise that the two copies agree',
      len(_notices) == 1 and 'drift apart' not in _notices[0][1]
      and 'dist\\' not in _notices[0][1])
app5f.destroy()

print()
# ============================================================
# GARBAGE COLOURS CANNOT MAKE THE APP UNOPENABLE
# ============================================================
# A colour string ends its journey in a Tk configure(), which raises on
# garbage -- and settings.json/notes_data.json are hand-editable and ride
# inside backups. Because a note is saved before it is first drawn, one
# bad value used to be a crash on EVERY launch: the brick class, through
# the colour door. Both intakes must drop the garbage and open normally.
import json as _json5g
with open('settings.json', 'w', encoding='utf-8') as _f5g:
    _json5g.dump({'reclaimed_from_appdata': True,
                  'day_colors': {'2026-04-01': '#ff0000',
                                 '2026-04-02': 'not-a-colour',
                                 '2026-04-03': '#12zz34'},
                  'categories': {'General': '#4f6d7a',
                                 'Rupt': '#nu-e-hex'}}, _f5g)
with open('notes_data.json', 'w', encoding='utf-8') as _f5g:
    _json5g.dump([{'id': 1, 'title': 'Colorata', 'body': 'x',
                   'category': 'General', 'color': '#zzzzzz',
                   'updated': '2026-01-01 00:00',
                   'created': '2026-01-01 00:00'},
                  # A per-day override carries 'color' exactly like the
                  # base note does, and it reaches the SAME Tk configure
                  # when the calendar draws that day -- the one colour
                  # door the first sweep missed. The day's text edit must
                  # survive; only the undrawable colour is dropped.
                  {'id': 2, 'title': 'Serie', 'body': 'y',
                   'category': 'General', 'date': '2026-04-01',
                   'recurrence': {'freq': 'weekly', 'weekdays': [2]},
                   'overrides': {'2026-04-08': {'title': 'ziua aia',
                                                'color': '#nu-e-hex'},
                                 '2026-04-15': {'color': '#00ff00'}},
                   'updated': '2026-01-01 00:00',
                   'created': '2026-01-01 00:00'}], _f5g)
# Guarded construction: under the unvalidated-load mutant the garbage
# reaches render_calendar inside __init__ itself, and an unguarded
# constructor would kill the script before its FAILURES footer -- the
# mutant would then read as "ran nothing" instead of failing red (the
# norelease lesson, again).
try:
    app5g = NO.NoteOrganizer()
    _built5g = True
except Exception:
    app5g = None
    _built5g = False
check('the app opens over garbage colours instead of crashing',
      _built5g and bool(app5g.winfo_exists()))
if _built5g:
    app5g._poll_active_dirty = lambda: None
    app5g.show_info = lambda *a, **k: True
    app5g.update()
check('the valid day colour is kept, both garbage ones dropped',
      _built5g and app5g.day_colors.get('2026-04-01') == '#ff0000'
      and '2026-04-02' not in app5g.day_colors
      and '2026-04-03' not in app5g.day_colors)
check('the garbage category colour never enters the palette map',
      NO.CATEGORY_COLORS.get('Rupt') is None)
check('the note survives with its undrawable colour blanked',
      _built5g and app5g.notes and app5g.notes[0]['color'] == ''
      and app5g.notes[0]['title'] == 'Colorata')
_ovr5g = (app5g.find_note(2) or {}).get('overrides', {}) if _built5g else {}
check('a per-day override loses only its undrawable colour',
      _ovr5g.get('2026-04-08') == {'title': 'ziua aia'})
check('...while a valid per-day colour is kept',
      _ovr5g.get('2026-04-15') == {'color': '#00ff00'})
# The calendar is where day colours are painted -- drive the render
# over the exact month the garbage pointed at rather than assuming,
# guarded for the same footer reason as the constructor.
_rendered5g = False
if _built5g:
    try:
        app5g.cal_year, app5g.cal_month = 2026, 4
        app5g.render_calendar(); app5g.update()
        _rendered5g = bool(app5g.winfo_exists())
    except Exception:
        _rendered5g = False
check('the calendar survives rendering the month the garbage aimed at',
      _rendered5g)
if _built5g:
    app5g.destroy()

# ---- A FIELD THE APP CANNOT READ NO LONGER COSTS THE REST OF THE NOTE ----
# One unreadable field vetoed the whole save, and the automatic routes took
# the veto for success and replaced the editor: a date typed as 30/09/2026,
# the way many people write it, quietly cost every word typed after it.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Shopping', 'body': 'milk',
                                'date': '2026-09-01'})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.body_text.insert('end', '\neggs')
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '30/09/2026')
app._autosave_now(); app.update()
check('a pause after an unreadable date still saves the words',
      app.find_note(1)['body'].rstrip('\n').endswith('eggs'))
check('...keeping the date the note already had',
      app.find_note(1)['date'] == '2026-09-01')
check('...and the status line says what was left out',
      '30/09/2026' in str(app.status_lbl.cget('text')))
_real_dlg5 = app._themed_dialog
_asked5 = []
app._themed_dialog = lambda *a, **k: (_asked5.append(a[0]), False)[1]
check('leaving asks first -- and "Go back and fix it" stays on the note',
      app._flush_autosave() is False and len(_asked5) == 1
      and app.date_entry.get() == '30/09/2026')
app._themed_dialog = lambda *a, **k: True
check('..."Continue without it" goes on',
      app._flush_autosave() is True)
app._themed_dialog = _real_dlg5
check('...showing the date the note keeps, so nothing reads as unsaved',
      app.date_entry.get() == '2026-09-01'
      and app.editor_state_matches_saved(app.capture_editor_state()))
# A code made in the editor carries what a save would keep: one carrying
# "30.09.2026" delivered a date no save could store, and every edit to the
# note that arrived was lost on the far end.
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '30.09.2026')
app.share_current_note_as_code(); app.update()
_code_w5 = [w for w in app.editor_code_area.winfo_children()
            if isinstance(w, tk.Text)]
_payload5 = NO.decode_share_code(_code_w5[0].get('1.0', 'end-1c')) if _code_w5 else []
_shared5 = ((_payload5['notes'] if isinstance(_payload5, dict) else _payload5)
            or [{}])[0]
check('a code made in the editor carries the date a save would keep',
      _shared5.get('date') == '2026-09-01')
app._show_date_in_field('2026-09-01')
# The repeat's end date, typed day-first, was dropped without a word and
# the series stored as never-ending while the field still showed the date.
app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
app.on_recurrence_changed()
app.rec_end_mode_var.set('on')
app.rec_end_date_var.set('31/12/2026')
app._autosave_now(); app.update()
check('a repeat whose end date cannot be read saves without that end',
      app.find_note(1)['recurrence']['freq'] == 'weekly'
      and app.find_note(1)['recurrence']['end'] == '')
check('...and says so instead of storing "never ends" in silence',
      any('end date' in item for item in app._date_and_repeat_to_store()[2]))
app.new_note(); app.update()
# A repeating note whose date is cleared -- on the way to typing a new one
# -- keeps the day it starts on, and the words typed meanwhile are saved.
app.notes = [NO.normalize_note({'id': 2, 'title': 'Yoga', 'body': 'stretch',
                                'date': '2026-09-01',
                                'recurrence': {'freq': 'weekly'}})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.body_text.insert('end', '\nbring the mat')
app.date_entry.delete(0, 'end')
app._autosave_now(); app.update()
check('clearing a series date keeps its start while the words are saved',
      app.find_note(2)['date'] == '2026-09-01'
      and app.find_note(2)['recurrence']['freq'] == 'weekly'
      and 'bring the mat' in app.find_note(2)['body'])
app.new_note(); app.update()
app.notes = []; app.save_notes()

# Comments keep their shape: the save stripped them, so a pasted code
# block lost its first indent and every trailing blank line on each save
# -- long after the body had stopped doing it to the text above.
app.notes = [NO.normalize_note({'id': 3, 'title': 'Snippet', 'body': 'x'})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.comments_text.insert('1.0', '    for x in items:\n        print(x)\n\n')
app._flush_autosave(); app.update()
check('comments keep their first indent and trailing blank lines on save',
      app.find_note(3)['comments'] == '    for x in items:\n        print(x)\n\n')
app.new_note(); app.update()
app.load_note(app.find_note(3)); app.update()
check('...and reopen exactly as typed, reading as saved',
      app.comments_text.get('1.0', 'end-1c')
      == '    for x in items:\n        print(x)\n\n'
      and app.editor_state_matches_saved(app.capture_editor_state()))
app.comments_text.insert('end', '\n')
check('...so adding only a blank line is an edit the autosave sees',
      not app.editor_state_matches_saved(app.capture_editor_state()))
app.new_note(); app.update()

# A checklist item typed but not yet added goes into the note it was typed
# for: it stayed in the box and was added to whichever note opened next.
app.notes = [NO.normalize_note({'id': 4, 'title': 'Groceries', 'body': 'x',
                                'checklist': [{'text': 'milk', 'done': False}]}),
             NO.normalize_note({'id': 5, 'title': 'Gym', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(4)); app.update()
app.checklist_add_var.set('eggs')
app.open_note_in_tab(app.find_note(5)); app.update()
check('a half-typed checklist item is saved into the note it was typed for',
      [it['text'] for it in app.find_note(4)['checklist']] == ['milk', 'eggs'])
check('...and does not follow into the next note',
      app.checklist_add_var.get() == '' and not app.find_note(5)['checklist'])
app.new_note(); app.update()
app.notes = []; app.save_notes()

# The theme registry lets go of dead widgets without waiting for a theme
# switch: a session that never switched kept every widget it ever drew.
_tw_start = len(app.themed_widgets)
# Enough to cross the registry's pruning point whatever it holds now: it
# prunes when it has doubled since the last prune, so this many cannot
# all be added without one happening.
_tw_n = 2 * max(256, _tw_start) + 10
for _tw_i in range(_tw_n):
    _tw = tk.Frame(app)
    app.track_theme(_tw, bg='bg')
    _tw.destroy()
check('the theme registry lets go of widgets that no longer exist, unswitched',
      len(app.themed_widgets) < _tw_start + _tw_n // 2)

# A superscript digit passes str.isdigit() and then fails int(): the
# month-jump's year and a monthly repeat's days raised instead of giving
# their own answer. isdecimal() is exactly what int() reads.
_sd_errors = []
_sd_real_report = app.report_callback_exception
app.report_callback_exception = lambda *a: _sd_errors.append(a[1])
app.notebook.select(app.TAB_CALENDAR); app.update()
app.open_month_jump(); app.update()
_sd_pop = app._mini_popup


def _sd_widgets(w, cls):
    out = []
    for c in w.winfo_children():
        if isinstance(c, cls):
            out.append(c)
        out.extend(_sd_widgets(c, cls))
    return out


_sd_entry = _sd_widgets(_sd_pop, tk.Entry)[0] if _sd_pop else None
_sd_go = next((b for b in _sd_widgets(_sd_pop, tk.Button)
               if str(b.cget('text')) == 'Go'), None) if _sd_pop else None
if _sd_entry is not None and _sd_go is not None:
    _sd_entry.delete(0, 'end'); _sd_entry.insert(0, '2026²')
    _sd_go.invoke(); app.update()
_sd_said = [str(l.cget('text')) for l in _sd_widgets(_sd_pop, tk.Label)] if _sd_pop else []
check('a superscript in the month-jump year gets the picker\'s own message',
      not _sd_errors and any('between 1 and 9999' in t for t in _sd_said))
app._dismiss_mini_popup(); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['monthly']); app.on_recurrence_changed()
app.rec_monthdays_var.set('3², 15')
try:
    _sd_rule = app.read_recurrence_from_ui()
except ValueError:
    _sd_rule = None
check('...and in a monthly repeat\'s days it is skipped, the rest read',
      _sd_rule is not None and _sd_rule['month_days'] == [15])
app.report_callback_exception = _sd_real_report
app.new_note(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()

# "Restore previous" can bring back a date and a repeat, both drawn on the
# calendar -- the one note-writing route that never redrew it.
_rp_drawn = []
_rp_real_render = app.render_calendar
app.notes = [NO.normalize_note({'id': 7, 'title': 'Moved', 'body': 'x',
                                'date': '2026-10-05'})]
app.notes[0]['_prev'] = {'title': 'Moved', 'body': 'x', 'formatting': [],
                         'paragraphs': [], 'comments': '', 'date': '2026-10-20'}
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
_rp_yes = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
app.render_calendar = lambda *a, **k: (_rp_drawn.append(1), _rp_real_render(*a, **k))[1]
app.restore_previous_version(); app.update()
app.render_calendar = _rp_real_render
app.ask_yes_no = _rp_yes
check('Restore previous brings the date back and redraws the calendar',
      app.find_note(7)['date'] == '2026-10-20' and _rp_drawn)
app.new_note(); app.update()
app.notes = []; app.save_notes()

# ---- THE DATE A NOTE ALREADY HAS IS NOT "LEFT OUT" ----
# A share code or a backup keeps a one-off note's date as it came, so a
# note can hold "30.09.2026". Opened and left untouched, it asked "Part of
# this note isn't saved" at every exit -- the window's close included --
# and "Continue without it" put back that same date for the next time.
_bd_real_dlg = app._themed_dialog
app.notes = [NO.normalize_note({'id': 1, 'title': 'Arrived', 'body': 'x',
                                'date': '30.09.2026'}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
check('fixture: a note holding a date the app cannot read, shown as it is',
      app.find_note(1)['date'] == '30.09.2026'
      and not NO.parse_date('30.09.2026')
      and app.date_entry.get() == '30.09.2026')
_bd_asked = []
app._themed_dialog = lambda *a, **k: (_bd_asked.append(a[0]), True)[1]
app.open_note_in_tab(app.find_note(2)); app.update()
app._themed_dialog = _bd_real_dlg
check(f'leaving it untouched asks nothing ({_bd_asked})',
      _bd_asked == [] and app.selected_note_id == 2)
check('...and the note keeps the date it came with',
      app.find_note(1)['date'] == '30.09.2026')
app.open_note_in_tab(app.find_note(1)); app.update()
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '01.10.2026')
check('...while a different unreadable date typed there is still left out',
      any('01.10.2026' in item for item in app._date_and_repeat_to_store()[2]))
app._show_date_in_field('30.09.2026')
app.new_note(); app.update()
app.notes = []; app.save_notes()

# ---- A ROUTE THAT KEEPS THE EDITOR DOES NOT ASK THE LEAVING QUESTION ----
# The question about a date the save could not store is for the way OUT
# of a note. Asked by a route that leaves the editor where it is --
# deleting or moving ANOTHER note, an import updating others -- "Continue"
# reset the date in a note that stayed open, and "Go back" silently
# cancelled an action that was about something else.
_nl_real_dlg = app._themed_dialog
_nl_real_yes = app.ask_yes_no
NO.CATEGORY_COLORS['Temp5nl'] = '#33aa77'
_nl_asked = []


def _nl_dialog(*a, **k):
    _nl_asked.append(a[0])
    if 'already have' in a[0]:
        return 'update'
    if a[0] == 'Delete category':
        return 'move'
    return True


def _nl_setup():
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Open one', 'body': 'x',
                           'date': '2026-09-01'}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'same',
                           'category': 'Temp5nl', 'updated': '2026-09-01 08:00:00'}),
        NO.normalize_note({'id': 3, 'title': 'Other', 'body': 'same',
                           'category': 'Temp5nl'})]
    app.trash = []
    app.save_notes(); NO.save_trash(app.trash)
    app.open_note_in_tab(app.find_note(1)); app.update()
    app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '14/10/2026')
    _nl_asked.clear()
    app._themed_dialog = _nl_dialog
    app.ask_yes_no = lambda *a, **k: (_nl_asked.append(a[0]), True)[1]


class _NlVar:
    def __init__(self, v):
        self._v = v

    def get(self):
        return self._v


def _nl_update_code():
    other = dict(app.find_note(2), body='edited elsewhere')
    return app._take_known_notes([other], 'code')


_nl_routes = [
    ('deleting another note from its menu',
     lambda: app._context_delete_note(app.find_note(2))),
    ('moving other ticked notes to the Trash',
     lambda: (setattr(app, 'selected_note_ids', {2}),
              app._bulk_move_to_trash())),
    ("undoing another note's category move",
     lambda: (app.find_note(2).__setitem__('category', 'General'),
              app._undo_bulk_category([(2, 'Temp5nl', '2026-09-01 08:00:00')],
                                      'General'))),
    ("an import's Update of another note", _nl_update_code),
    ('cleaning up duplicates of another note',
     lambda: app._cleanup_selected_duplicates(
         [(_NlVar(False), app.find_note(2), [app.find_note(2), app.find_note(3)]),
          (_NlVar(True), app.find_note(3), [app.find_note(2), app.find_note(3)])],
         None, refresh=lambda: None)),
    ("deleting another note's category",
     lambda: app._delete_category('Temp5nl', lambda: None)),
    ('moving another note to a category from its menu',
     lambda: app._ctx_move_to_category(app.find_note(2), 'General')),
    ('moving other ticked notes to a category from the bar',
     lambda: _nl_bar_category({2})),
]


def _nl_bar_category(ids):
    """The selection bar's Category: tick, open its list, click General."""
    app.selected_note_ids = set(ids)
    app._bulk_change_category()
    app.update()
    _pop = getattr(app, '_mini_popup', None)
    _todo = [_pop] if _pop is not None else []
    while _todo:
        _w = _todo.pop()
        if isinstance(_w, tk.Label) and str(_w.cget('text')).strip() == 'General':
            _qa_click(_w)
            app.update()
            return
        _todo.extend(_w.winfo_children())
    raise RuntimeError('the bar\'s category list offered no General')


for _nl_label, _nl_action in _nl_routes:
    _nl_setup()
    try:
        _nl_action()
        app.update()
        _nl_error = None
    except Exception as _nl_e:
        _nl_error = _nl_e
    app._themed_dialog = _nl_real_dlg
    app.ask_yes_no = _nl_real_yes
    app.selected_note_ids = set()
    NO.CATEGORY_COLORS['Temp5nl'] = '#33aa77'
    check(f'{_nl_label} does not ask about the open note\'s date ({_nl_asked}, '
          f'{_nl_error!r})',
          _nl_error is None and "Part of this note isn't saved" not in _nl_asked
          and app.selected_note_id == 1
          and app.date_entry.get() == '14/10/2026')
# The asymmetry: deleting the note ON SCREEN still asks, and "Go back and
# fix it" keeps it -- and so does a ticked note on screen.
for _nl_label, _nl_action in [
        ('deleting the note on screen',
         lambda: app._context_delete_note(app.find_note(1))),
        ('moving the ticked note on screen to the Trash',
         lambda: (setattr(app, 'selected_note_ids', {1}),
                  app._bulk_move_to_trash()))]:
    _nl_setup()
    app._themed_dialog = lambda *a, **k: (_nl_asked.append(a[0]), False)[1]
    _nl_action(); app.update()
    app._themed_dialog = _nl_real_dlg
    app.ask_yes_no = _nl_real_yes
    app.selected_note_ids = set()
    check(f'...while {_nl_label} still asks first, and Go back keeps it '
          f'({_nl_asked})',
          _nl_asked == ["Part of this note isn't saved"]
          and app.find_note(1) is not None
          and app.date_entry.get() == '14/10/2026')
app._show_date_in_field('2026-09-01')
app.new_note(); app.update()
NO.CATEGORY_COLORS.pop('Temp5nl', None)
app.notes = []; app.trash = []
app.save_notes(); NO.save_trash(app.trash)

# ---- TURNING A REPEAT OFF KEEPS EVERY DAY'S OWN TEXT ----
# A repeat turned off takes every day's own edits with it, and nobody is
# asked (only a series field changed). The day on screen used to be kept
# alone, as the note's next text; every other day's was in no file, and
# turned off from the series view, not even that one. Pressed Save first,
# the editor went on showing the day's text as the note's, and leaving
# wrote it over the series' -- which was then in no file. The note as it
# was, repeat and days included, is the rescue copy now, and Restore
# previous brings the series back whole.
_ro_real_dlg = app._themed_dialog
_ro_yes = app.ask_yes_no


def _ro_fixture():
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT',
                           'formatting': [{'start': 0, 'end': 6, 'style': 'bold'}],
                           'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                           'overrides': {
                               '2026-09-14': {'title': 'Standup (moved)',
                                              'body': 'DAY TEXT: room 9'},
                               '2026-09-21': {'body': 'DAY 21: decisions'}}}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()


def _ro_off(day, save_first=False):
    """Turn note 1's repeat off on *day* (None: the series view), maybe
    press Save, then open note 2. Returns the questions asked and what the
    editor showed after the Save."""
    app.open_note_in_tab(app.find_note(1), occurrence_date=day); app.update()
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    asked, seen = [], None
    app._themed_dialog = lambda *a, **k: (asked.append(a[0]), True)[1]
    if save_first:
        app.save_current_note(); app.update()
        seen = (app.body_text.get('1.0', 'end-1c').rstrip('\n'),
                app.current_occurrence_date,
                app.editor_state_matches_saved(app.capture_editor_state()),
                str(app.status_lbl.cget('text')))
    app.open_note_in_tab(app.find_note(2)); app.update()
    app._themed_dialog = _ro_real_dlg
    return asked, seen


def _ro_restored():
    """Restore previous on note 1, answered Yes: what the note is then."""
    app.open_note_in_tab(app.find_note(1)); app.update()
    app.ask_yes_no = lambda *a, **k: True
    app.restore_previous_version(); app.update()
    app.ask_yes_no = _ro_yes
    n = app.find_note(1)
    return (n['body'].rstrip('\n'), n['recurrence']['freq'],
            NO.effective_note(n, '2026-09-14').get('body'),
            NO.effective_note(n, '2026-09-21').get('body'),
            [f.get('style') for f in n.get('formatting') or []])


_RO_WHOLE = ('SERIES TEXT', 'weekly', 'DAY TEXT: room 9', 'DAY 21: decisions',
             ['bold'])
_ro_fixture()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
check('fixture: the day on screen shows its own text',
      app.body_text.get('1.0', 'end-1c') == 'DAY TEXT: room 9'
      and app.current_occurrence_date == '2026-09-14')
_ro_asked, _ = _ro_off('2026-09-14')
_ro = app.find_note(1)
check(f'fixture: only the repeat changed, so nothing was asked ({_ro_asked}), '
      'and the note no longer repeats, keeping the series\' text',
      _ro_asked == [] and not _ro['recurrence']['freq']
      and _ro['body'].rstrip('\n') == 'SERIES TEXT' and _ro['overrides'] == {})
check("turning the repeat off on a day keeps the note as it was -- its repeat "
      "and every day's own text -- as the rescue copy "
      f"({sorted(((_ro.get('_prev') or {}).get('overrides') or {}))})",
      ((_ro.get('_prev') or {}).get('recurrence') or {}).get('freq') == 'weekly'
      and sorted(((_ro.get('_prev') or {}).get('overrides') or {}))
      == ['2026-09-14', '2026-09-21'])
_ro_back = _ro_restored()
check(f'...which Restore previous brings back whole: the series, its bold and '
      f'each day\'s own text ({_ro_back})', _ro_back == _RO_WHOLE)
# Saved first, then left: the editor shows the note it saved.
_ro_fixture()
_ro_asked, _ro_seen = _ro_off('2026-09-14', save_first=True)
check(f'Save on a day whose repeat was just turned off shows the note it '
      f'saved, reading as saved, and says where the days went ({_ro_seen})',
      _ro_seen is not None and _ro_seen[0] == 'SERIES TEXT'
      and _ro_seen[1] is None and _ro_seen[2]
      and 'Restore previous' in _ro_seen[3])
import json as _json5r
with open('notes_data.json', encoding='utf-8') as _f5r:
    _ro_disk = [n for n in _json5r.load(_f5r) if n.get('id') == 1]
check(f'...and leaving it keeps the series\' text and its bold on disk '
      f'({[(n.get("body"), n.get("formatting")) for n in _ro_disk]})',
      len(_ro_disk) == 1 and _ro_disk[0]['body'].rstrip('\n') == 'SERIES TEXT'
      and [f.get('style') for f in _ro_disk[0].get('formatting') or []] == ['bold'])
_ro_back = _ro_restored()
check(f'...and Restore previous brings the series back whole ({_ro_back})',
      _ro_back == _RO_WHOLE)
# Turned off from the series view: the days' own text is kept too.
_ro_fixture()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
app.save_current_note(); app.update()
_ro_back = _ro_restored()
check(f'turned off from the series view, every day\'s own text is kept and '
      f'comes back with Restore previous ({_ro_back})', _ro_back == _RO_WHOLE)
# A day whose words ARE the series' -- its own colour only -- loses no
# text, and the rescue copy the note already holds is not replaced by a
# copy of what the note says.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'color': '#00aa00'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.notes[0]['_prev'] = {'title': 'Standup', 'body': 'AN OLDER VERSION',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
_ro_asked = []
app._themed_dialog = lambda *a, **k: (_ro_asked.append(a[0]), True)[1]
app.open_note_in_tab(app.find_note(2)); app.update()
app._themed_dialog = _ro_real_dlg
check(f'...while a day differing only in its colour keeps the rescue copy '
      f'the note had ({_ro_asked})',
      _ro_asked == [] and not app.find_note(1)['recurrence']['freq']
      and (app.find_note(1).get('_prev') or {}).get('body') == 'AN OLDER VERSION')

# ---- "THIS OCCURRENCE ONLY" KEEPS WHAT A DAY CANNOT HOLD ----
# The day's text goes to the day; a file attached and a tick made in the
# same visit belong to the series -- a day has nowhere to keep either --
# and were dropped: the file stayed in the folder with no note, the tick
# was undone, and the editor's snapshot called it saved.
import tkinter.filedialog as _fd5
import tempfile as _tmp5
import os as _os5
_oc_file = _os5.path.join(_tmp5.gettempdir(), 'qa5_handout.txt')
with open(_oc_file, 'w', encoding='utf-8') as _f5o:
    _f5o.write('handout')
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'checklist': [{'text': 'agenda', 'done': False}]}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
app.body_text.insert('end-1c', ' -- notes for this day')
_oc_real_pick = _fd5.askopenfilenames
_fd5.askopenfilenames = lambda **k: (_oc_file,)
app.add_attachment(); app.update()
_fd5.askopenfilenames = _oc_real_pick
app._working_checklist[0]['done'] = True     # what the tick's box does
_oc_real_scope = app.ask_occurrence_scope
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app.open_note_in_tab(app.find_note(2)); app.update()
app.ask_occurrence_scope = _oc_real_scope
_oc = app.find_note(1)
_oc_files = [a.get('stored_as') for a in _oc.get('attachments') or []]
check(f'"This occurrence only" writes the day\'s text to the day '
      f'({(_oc.get("overrides") or {}).get("2026-09-14", {}).get("body")!r})',
      'notes for this day' in
      ((_oc.get('overrides') or {}).get('2026-09-14', {}).get('body') or ''))
check(f'...and keeps the file attached in the same visit, on the series, its '
      f'file in the folder ({_oc_files})',
      len(_oc_files) == 1 and _os5.path.exists(
          _os5.path.join(NO.ATTACHMENTS_DIR, _oc_files[0] or '')))
check(f'...and the tick made in the same visit ({_oc.get("checklist")})',
      [it.get('done') for it in _oc.get('checklist') or []] == [True])
# ...but not a date or a repeat changed in that visit: they are the
# series', and written for one day they moved the whole series -- every
# day's own text, the one just saved among them, then sat on a day the
# series no longer had. They stay as they were, the question says so, and
# the editor shows them again.
import datetime as _dt5m
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'series',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-21'); app.update()
app.body_text.insert('end-1c', ' -- moved to Tuesday')
app._show_date_in_field('2026-09-22')
_mv_said = []
_mv_real_dlg = app._themed_dialog
app._themed_dialog = lambda *a, **k: (_mv_said.append(a[1] if len(a) > 1 else ''),
                                      'occurrence')[1]
app.save_current_note(); app.update()
app._themed_dialog = _mv_real_dlg
_mv = app.find_note(1)
_mv_days = NO.expand_occurrences(_mv, _dt5m.date(2026, 9, 1), _dt5m.date(2026, 9, 30))
check(f'"This occurrence only" with the date changed too keeps the series '
      f'where it was, every day\'s own text on a day it has (start '
      f'{_mv.get("date")}; occurrences {_mv_days}; days with own text '
      f'{sorted(_mv.get("overrides") or {})})',
      _mv.get('date') == '2026-09-07'
      and '2026-09-14' in _mv_days and '2026-09-21' in _mv_days
      and 'moved to Tuesday' in ((_mv.get('overrides') or {})
                                 .get('2026-09-21', {}).get('body') or ''))
check(f'...the question says so, and the editor shows the series\' date again '
      f'(date field {app.date_entry.get()!r}; status {app.status_lbl.cget("text")!r})',
      len(_mv_said) == 1 and 'keeps them as they are' in _mv_said[0]
      and app.date_entry.get() == '2026-09-07'
      and "stay the whole series'" in str(app.status_lbl.cget('text')))
# The repeat turned off on a day, and a date typed the app cannot read:
# the save fills the editor from the note it left (above), and that wrote
# the stored date over the typed one -- leaving then asked nothing, and
# the typed date was gone.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '30/09/2026')
_lr_asked = []
app._themed_dialog = lambda *a, **k: (_lr_asked.append(a[0]), False)[1]
_lr_left = app.open_note_in_tab(app.find_note(2)); app.update()
app._themed_dialog = _mv_real_dlg
check(f'turning the repeat off on a day with a date the app cannot read '
      f'still asks before leaving, and Go back keeps the typed date (asked '
      f'{_lr_asked}; left: {_lr_left}; date field {app.date_entry.get()!r})',
      "Part of this note isn't saved" in _lr_asked and _lr_left is False
      and app.date_entry.get() == '30/09/2026'
      and app.selected_note_id == 1)
# "Continue without it", as the person would answer at last: the editor
# agrees with the note again, and nothing below is asked about it.
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()


# "This occurrence only" with a field the save had to leave out: the
# put-back of the series' date and repeat was skipped, the changed values
# stayed on screen "to be fixed", and the next leave or Save -- asking
# nothing, the day's text being saved already -- wrote them to the whole
# series: it stopped repeating, or moved, and its days fell off the
# calendar. Nothing of the schedule is stored by such a save, so nothing
# of it is left out.
def _lo_day(changes):
    """A weekly series with its own text on 09-14; on its day 09-21, the
    text typed and *changes* made, then Save answered "This occurrence
    only". Returns every question asked, as (title, message)."""
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'series',
                           'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                           'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-21')
    app.update()
    app.body_text.insert('end-1c', ' -- only this week')
    changes()
    asked = []
    app._themed_dialog = lambda *a, **k: (
        asked.append((a[0], a[1] if len(a) > 1 else '')), 'occurrence')[1]
    _lo_warn_stub = app.show_warning
    app.show_warning = lambda *a, **k: (asked.append((a[0], '')), True)[1]
    try:
        app.save_current_note(); app.update()
    finally:
        app._themed_dialog = _mv_real_dlg
        app.show_warning = _lo_warn_stub
    return asked


def _lo_series():
    n = app.find_note(1)
    days = NO.expand_occurrences(n, _dt5m.date(2026, 9, 1),
                                 _dt5m.date(2026, 9, 30))
    return (n.get('date'), (n.get('recurrence') or {}).get('freq'),
            '2026-09-14' in days and '2026-09-21' in days,
            'only this week' in ((n.get('overrides') or {})
                                 .get('2026-09-21', {}).get('body') or ''))


def _lo_repeat_off_and_bad_date():
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.date_entry.delete(0, 'end')
    app.date_entry.insert(0, '30/09/2026')


_lo_asked = _lo_day(_lo_repeat_off_and_bad_date)
_lo_saved = _lo_series()
_lo_shown = (app.date_entry.get(), app.rec_freq_var.get())
_lo_said = str(app.status_lbl.cget('text'))
_lo_leave = []
app._themed_dialog = lambda *a, **k: (_lo_leave.append(a[0]), True)[1]
try:
    app.open_note_in_tab(app.find_note(2)); app.update()
finally:
    app._themed_dialog = _mv_real_dlg
check(f'"This occurrence only" with the repeat off and a date the app cannot '
      f'read keeps the series, asks only the one question -- no warning that '
      f'something was not saved -- and shows the series\' date and repeat '
      f'again (asked {[q[0] for q in _lo_asked]}; saved {_lo_saved}; shown '
      f'{_lo_shown}; status {_lo_said!r})',
      len(_lo_asked) == 1 and 'keeps them as they are' in _lo_asked[0][1]
      and _lo_saved == ('2026-09-07', 'weekly', True, True)
      and _lo_shown == ('2026-09-07', NO.FREQ_LABELS['weekly'])
      and "stay the whole series'" in _lo_said and 'except' not in _lo_said)
check(f'...and leaving afterwards asks nothing and moves nothing (asked '
      f'{_lo_leave}; {_lo_series()})',
      _lo_leave == [] and _lo_series() == ('2026-09-07', 'weekly', True, True))


def _lo_bad_date_only():
    app.date_entry.delete(0, 'end')
    app.date_entry.insert(0, '22/09/2026')


_lo_asked = _lo_day(_lo_bad_date_only)
check(f'...also when the only change to the schedule is a date the app cannot '
      f'read: the question says the date stays the series\', and the field '
      f'shows it again (asked {_lo_asked}; field {app.date_entry.get()!r})',
      len(_lo_asked) == 1 and 'keeps them as they are' in _lo_asked[0][1]
      and app.date_entry.get() == '2026-09-07'
      and _lo_series() == ('2026-09-07', 'weekly', True, True))

# The reload after a day turned its repeat off, with a date it had to leave
# out: loading the note wrote the repeat's fields, whose traces asked for an
# autosave; the typed date carried back kept the editor unsaved, so half a
# second later that autosave saved again and its status line dropped the
# words saying where the days went.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'series',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
_lo_repeat_off_and_bad_date()
app._themed_dialog = lambda *a, **k: True
try:
    app.save_current_note()
finally:
    app._themed_dialog = _mv_real_dlg
_lo_said = str(app.status_lbl.cget('text'))
_lo_waiting = _qa_waiting(app, '_autosave_now')
app.update(); import time as _t5lo; _t5lo.sleep(0.7); app.update()
check(f'a day that turned its repeat off with a date left out keeps both '
      f'notices in the status line: no autosave is left to say it again '
      f'(waiting {_lo_waiting}; then {_lo_said!r}; after a pause '
      f'{app.status_lbl.cget("text")!r})',
      not _lo_waiting and 'Restore previous' in _lo_said
      and 'except the date' in _lo_said
      and str(app.status_lbl.cget('text')) == _lo_said)
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()

# A file attached after a day was saved "This occurrence only": the save
# stored the editor's own list in the note, so the attach changed the note
# too, the editor read as saved, and closing lost the file's entry.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
app.body_text.insert('end-1c', ' -- for this day')
app._themed_dialog = lambda *a, **k: 'occurrence'
try:
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _mv_real_dlg
_fd5.askopenfilenames = lambda **k: (_oc_file,)
try:
    app.add_attachment(); app.update()
finally:
    _fd5.askopenfilenames = _oc_real_pick
_at_unsaved = not app.editor_state_matches_saved(app.capture_editor_state())
_at_asked = []
app._themed_dialog = lambda *a, **k: (_at_asked.append(a[0]), True)[1]
try:
    app.open_note_in_tab(app.find_note(2)); app.update()
finally:
    app._themed_dialog = _mv_real_dlg
with open('notes_data.json', encoding='utf-8') as _f5a:
    _at_disk = [n for n in _json5r.load(_f5a) if n.get('id') == 1]
check(f'a file attached after a day was saved on its own reads as unsaved '
      f'({_at_unsaved}), and leaving stores it '
      f'({[a.get("filename") for a in (_at_disk[0].get("attachments") or [])] if _at_disk else None})',
      _at_unsaved and len(_at_disk) == 1
      and [a.get('filename') for a in _at_disk[0].get('attachments') or []]
      == ['qa5_handout.txt'])


# Restore previous and "Reset this day" fill the editor from the note. A
# file attached on a day -- which only the day's own save or a way out of
# it stores -- was then left with no note, and a file removed came back
# listed, its stored copy deleted. The editor's files and checklist are
# stored first now.
def _rr_day():
    """A day of a series with a rescue copy, a file attached on screen."""
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                           'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                           'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.notes[0]['_prev'] = {'title': 'Weekly', 'body': 'older series text',
                             'formatting': [], 'paragraphs': [], 'comments': ''}
    app.save_notes()
    app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14')
    app.update()
    _fd5.askopenfilenames = lambda **k: (_oc_file,)
    try:
        app.add_attachment(); app.update()
    finally:
        _fd5.askopenfilenames = _oc_real_pick


def _rr_files(note_id=1):
    return [a.get('filename')
            for a in app.find_note(note_id).get('attachments') or []]


_rr_day()
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
check(f'Restore previous on a day keeps a file attached there before it '
      f'(note {_rr_files()}; editor '
      f'{[a.get("filename") for a in app.current_attachments]})',
      _rr_files() == ['qa5_handout.txt']
      and [a.get('filename') for a in app.current_attachments]
      == ['qa5_handout.txt'])
_rr_day()
app.ask_yes_no = lambda *a, **k: True
try:
    app._reset_occurrence_override(app.find_note(1), '2026-09-14')
    app.update()
finally:
    app.ask_yes_no = _ro_yes
check(f'...and so does "Reset this day" ({_rr_files()})',
      _rr_files() == ['qa5_handout.txt'])
# The right-click Duplicate of the note the editor holds asks about its
# unsaved changes, as the editor's own Duplicate does: it copied the stored
# note in silence, without the file just attached.
_rr_day()
_rr_asked = []
_rr_real_ync = app.ask_yes_no_cancel
app.ask_yes_no_cancel = lambda t, *a, **k: (_rr_asked.append(t), True)[1]
_rr_before = {n['id'] for n in app.notes}
try:
    app._duplicate_from_menu(app.find_note(1)); app.update()
finally:
    app.ask_yes_no_cancel = _rr_real_ync
_rr_copy = [n for n in app.notes if n['id'] not in _rr_before]
check(f'the right-click Duplicate of the open note asks about its unsaved '
      f'changes, and Yes copies them ({_rr_asked}; copy '
      f'{[_rr_files(n["id"]) for n in _rr_copy]})',
      _rr_asked == ['Unsaved changes'] and len(_rr_copy) == 1
      and _rr_files(_rr_copy[0]['id']) == ['qa5_handout.txt'])


# A repeat's number the app cannot read is left out, as a date is. Read as
# 1, "After abc times" ended the series after its first day, and "Every x"
# repeated it every time.
def _rn_series(**rule):
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                           'date': '2026-09-07',
                           'recurrence': dict({'freq': 'weekly'}, **rule)}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()


_rn_warned = []
_rn_warn_stub = app.show_warning
app.show_warning = lambda t, m='', **k: (_rn_warned.append(m), True)[1]
try:
    _rn_series(count=10)
    app.rec_count_var.set('abc'); app.update()
    app.save_current_note(); app.update()
    _rn_count = app.find_note(1)['recurrence']
    _rn_series(interval=2)
    app.rec_interval_var.set('x'); app.update()
    app.save_current_note(); app.update()
    _rn_every = app.find_note(1)['recurrence']
finally:
    app.show_warning = _rn_warn_stub
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'a repeat\'s "After N times" the app cannot read is left out, and '
      f'said so (count {_rn_count.get("count")}; said {_rn_warned[:1]})',
      _rn_count.get('count') == 10 and _rn_warned
      and 'After abc times' in _rn_warned[0])
check(f'...and so is its "Every N" (interval {_rn_every.get("interval")}; '
      f'said {_rn_warned[1:2]})',
      _rn_every.get('interval') == 2 and len(_rn_warned) == 2
      and 'Every x' in _rn_warned[1])

# A save where only a field it has to leave out differs changes nothing the
# note stores, so its "updated" stamp stays: every way out of a note with
# an unreadable date on screen saved again, and each moved the note up
# "Recently updated" with no edit made.
_rn_series()
app.notes[0]['updated'] = '2026-01-01 00:00:00'
app.save_notes()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '30/09/2026')
app.save_current_note(auto=True); app.update()
_rn_kept = app.find_note(1).get('updated')
app.body_text.insert('end-1c', ' and an edit')
app.save_current_note(auto=True); app.update()
_rn_moved = app.find_note(1).get('updated')
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'a save that only met a field it had to leave out keeps the note\'s '
      f'"updated" stamp ({_rn_kept}), while a real edit beside it moves it '
      f'({_rn_moved})',
      _rn_kept == '2026-01-01 00:00:00' and _rn_moved != '2026-01-01 00:00:00')

# Restore previous keeps what is on screen alone: an item typed in the
# checklist's box goes in, as leaving takes it in, and a date the save had
# to leave out stays on screen to be fixed -- the reload emptied the box and
# wrote the stored date over the typed one in silence. Not asked about
# first: a half-typed date must never block a restore (qa7).
_rn_series()
app.notes[0]['_prev'] = {'title': 'Weekly', 'body': 'older series text',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
app.checklist_add_var.set('half typed item')
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
check(f'Restore previous keeps an item typed in the checklist\'s box '
      f'({[i.get("text") for i in app.find_note(1).get("checklist") or []]})',
      [i.get('text') for i in app.find_note(1).get('checklist') or []]
      == ['half typed item'])
_rn_series()
app.notes[0]['_prev'] = {'title': 'Weekly', 'body': 'older series text',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '30/09/2026')
_rn_asked = []
app.ask_yes_no = lambda *a, **k: True
app._themed_dialog = lambda *a, **k: (_rn_asked.append(a[0]), True)[1]
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
    app._themed_dialog = _mv_real_dlg
check(f'...and keeps a date the save had to leave out on screen, to be '
      f'fixed, asking nothing (asked {_rn_asked}; body '
      f'{app.find_note(1).get("body")!r}; date field {app.date_entry.get()!r})',
      _rn_asked == []
      and app.find_note(1).get('body', '').startswith('older series text')
      and app.date_entry.get() == '30/09/2026')
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()

# The summary under the repeat previews what the save will keep: it read
# the boxes as the old reader did, an unreadable "Every" as 1 -- a rule
# neither typed nor stored.
_rn_series(interval=2, count=10)
app.rec_interval_var.set('x'); app.update()
_rn_said = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'the repeat\'s summary shows the rule the save keeps, and says the '
      f'box is not understood ({_rn_said!r})',
      _rn_said.startswith('Every 2 weeks') and '“Every x”' in _rn_said)
# A monthly repeat's day the app cannot read is left out too: "15th" saved
# as no day at all, and the series moved to its start date's day.
_rn_warned = []
app.show_warning = lambda t, m='', **k: (_rn_warned.append(m), True)[1]
try:
    _rn_series(freq='monthly', month_days=[15])
    app.rec_monthdays_var.set('15th'); app.update()
    app.save_current_note(); app.update()
finally:
    app.show_warning = _rn_warn_stub
_rn_days = app.find_note(1)['recurrence'].get('month_days')
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'a monthly repeat\'s day the app cannot read is left out, and said so '
      f'(days {_rn_days}; said {_rn_warned[:1]})',
      _rn_days == [15] and _rn_warned and 'day(s) “15th”' in _rn_warned[0])

# The end date is a typed repeat value too. Judged apart from the others,
# an unreadable one left the summary previewing a series with no end, and
# no warning, while the save kept "until 2026-12-31".
_rn_series(interval=2, end='2026-12-31')
app.rec_end_date_var.set('31/12/2027'); app.update()
_rn_said = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'the repeat\'s summary keeps the end date the save keeps, and names '
      f'the one it does not understand ({_rn_said!r})',
      _rn_said.startswith('Every 2 weeks, until 2026-12-31')
      and 'the end date “31/12/2027”' in _rn_said)
# ...and a start date it cannot read is named: "needs a start date" said the
# series had none, while the save keeps the one it starts on.
_rn_series(interval=2)
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '30/09/2026')
app.update_recurrence_summary(); app.update()
_rn_said = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'...and names a start date it does not understand, instead of saying '
      f'the series needs one ({_rn_said!r})',
      'the date “30/09/2026”' in _rn_said
      and 'needs a start date' not in _rn_said)
# The warning wraps inside what its row leaves it instead of running past
# the row's end, where a long one was cut off. In a window narrow enough
# that it has to: the premise is asserted (more than one line), or a wide
# window would let the check pass with no wrapping at all.
_rn_geom = app.geometry()
app.geometry('1000x760'); app.update()
_rn_series(freq='monthly', month_days=[15], end='2026-12-31')
app.rec_end_date_var.set('31/12/2027')
app.rec_interval_var.set('every other one')
app.rec_monthdays_var.set('the fifteenth')
app.update()
_rn_lbl = app.rec_summary_lbl
_rn_room = int(str(_rn_lbl.cget('wraplength')) or 0)
_rn_line = int(app.tk.call('font', 'metrics', _rn_lbl.cget('font'),
                           '-linespace'))
_rn_lines = _rn_lbl.winfo_reqheight() // max(_rn_line, 1)
_rn_fits = (_rn_lbl.winfo_x() + _rn_lbl.winfo_reqwidth()
            <= _rn_lbl.master.winfo_width())
_rn_said = str(_rn_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
app.geometry(_rn_geom); app.update()
check(f'...and wraps inside its row, however many boxes it names (wraps at '
      f'{_rn_room} px into {_rn_lines} lines; fits {_rn_fits}; {_rn_said!r})',
      _rn_room > 0 and _rn_lines >= 2 and _rn_fits
      and 'day(s) “the fifteenth”' in _rn_said)

# What the save had to leave out of the repeat is carried across Restore
# previous and "Reset this day" as the date is: the reload wrote the stored
# rule over it in silence, and leaving then asked nothing.
_rn_series(interval=2, end='2026-12-31')
app.notes[0]['_prev'] = {'title': 'Weekly', 'body': 'older series text',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
app.rec_end_date_var.set('31/12/2027'); app.update()
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_box = app.rec_end_date_var.get()
_rn_left = app._date_and_repeat_to_store()[2]
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'Restore previous keeps a repeat value the save had to leave out on '
      f'screen, to be fixed (end date box {_rn_box!r}; left out {_rn_left})',
      _rn_box == '31/12/2027' and bool(_rn_left)
      and app.find_note(1)['recurrence'].get('end') == '2026-12-31'
      and app.find_note(1).get('body', '').startswith('older series text'))
_rr_day()
app.rec_interval_var.set('3x'); app.update()
app.ask_yes_no = lambda *a, **k: True
try:
    app._reset_occurrence_override(app.find_note(1), '2026-09-14')
    app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_box = app.rec_interval_var.get()
_rn_left = app._date_and_repeat_to_store()[2]
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'...and so does "Reset this day" (Every box {_rn_box!r}; left out '
      f'{_rn_left})',
      _rn_box == '3x' and bool(_rn_left)
      and '2026-09-14' not in (app.find_note(1).get('overrides') or {}))
# Not only what a save leaves out: a day of a series never autosaves, and a
# readable "Every 3" typed there went with Restore previous's reload -- or
# stayed, when an unreadable box happened to sit beside it. Reset this day
# discards it, as its question says the day's own edits go: kept, a start
# date typed there moved the whole series on leaving, without a question.
_rn_kept_ok = []
for _rn_route in ('reset', 'restore'):
    _rr_day()
    app.rec_interval_var.set('3'); app.update()
    app.ask_yes_no = lambda *a, **k: True
    try:
        if _rn_route == 'reset':
            app._reset_occurrence_override(app.find_note(1), '2026-09-14')
        else:
            app.restore_previous_version()
        app.update()
    finally:
        app.ask_yes_no = _ro_yes
    _rn_kept_ok.append((_rn_route, app.rec_interval_var.get(),
                        app._date_and_repeat_to_store()[1].get('interval')))
    app._put_back_stored_date_and_repeat()
    app._cancel_pending_autosave()
check(f'...and a readable change typed on a day, not saved yet, stays on '
      f'screen through Restore previous, to be saved, while Reset this day '
      f'discards it ({_rn_kept_ok})',
      _rn_kept_ok == [('reset', '1', 1), ('restore', '3', 3)])
_rr_day()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '2026-09-23')
app.ask_yes_no = lambda *a, **k: True
try:
    app._reset_occurrence_override(app.find_note(1), '2026-09-14')
    app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_reset_date = app.date_entry.get()
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'...and so is a start date typed on the day, which leaving would have '
      f'moved the whole series to ({_rn_reset_date!r})',
      _rn_reset_date == '2026-09-07')
# ...and a box it cannot read keeps only itself: the whole repeat was
# carried for its sake, a weekday ticked beside it with it, and leaving
# saved that weekday to the series. Typed with another frequency, the box
# goes with the change it was typed for.
_rn_beside = []
for _rn_change in ('weekday', 'freq'):
    _rr_day()
    if _rn_change == 'weekday':
        app.rec_weekday_state = [i == 2 for i in range(7)]
        app.refresh_weekday_buttons()
    else:
        app.rec_freq_var.set(NO.FREQ_LABELS['monthly'])
        app.on_recurrence_changed()
    app.rec_interval_var.set('2x'); app.update()
    app.ask_yes_no = lambda *a, **k: True
    try:
        app._reset_occurrence_override(app.find_note(1), '2026-09-14')
        app.update()
    finally:
        app.ask_yes_no = _ro_yes
    _rn_beside.append((_rn_change, app.selected_freq_key(),
                       app.rec_interval_var.get(),
                       [i for i, on in enumerate(app.rec_weekday_state) if on]))
    app._put_back_stored_date_and_repeat()
    app._cancel_pending_autosave()
check(f'...and a box it cannot read keeps only itself, never a readable '
      f'change beside it ({_rn_beside})',
      _rn_beside == [('weekday', 'weekly', '2x', []),
                     ('freq', 'weekly', '1', [])])

# The status line names a left-out value until it is put right -- also when
# it is put right to what the note already stores, which leaves nothing to
# save: only a save rewrote the line, and it went on saying "except".
_rn_series(interval=2)
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '07/09/2026')
app.save_current_note(auto=True); app.update()
_rn_said_bad = str(app.status_lbl.cget('text'))
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '2026-09-07')
app._autosave_now(); app.update()
_rn_said_fixed = str(app.status_lbl.cget('text'))
app._cancel_pending_autosave()
check(f'the status line stops naming a left-out date once it is put back to '
      f'the one stored ({_rn_said_bad!r} -> {_rn_said_fixed!r})',
      'except the date' in _rn_said_bad
      and 'except' not in _rn_said_fixed
      and _rn_said_fixed.startswith('Auto-saved'))

# The summary with the date box empty: the save keeps the start the note
# has, and says so; the summary said "needs a start date" as if it had none.
# And with no start date anywhere, the save keeps no repeat at all: the
# summary previewed "Every week" for "Every 3x" and called it kept.
_rn_series(interval=2)
app.date_entry.delete(0, 'end')
app.update_recurrence_summary(); app.update()
_rn_said_cleared = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Undated', 'body': 'x'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
app.on_recurrence_changed()
app.rec_interval_var.set('3x'); app.update()
_rn_said_nodate = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'the summary says an emptied date keeps the start the save keeps, and '
      f'that a repeat with no start date is not saved ({_rn_said_cleared!r}; '
      f'{_rn_said_nodate!r})',
      'still starts 2026-09-07' in _rn_said_cleared
      and 'not saved' in _rn_said_nodate
      and '“Every 3x”' in _rn_said_nodate
      and 'kept as saved' not in _rn_said_nodate
      and not _rn_said_nodate.startswith('Every'))

# The summary reads the start date from the date field, and every route
# that changes the field redraws it -- only the repeat's own boxes did: a
# date typed on an undated weekly note left "needs a start date ... not
# saved" on screen while the file kept the repeat, and the clear button never
# said the series still starts on its date. A date typed as no date at all,
# on a note with none stored, is named as the save names it.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Undated', 'body': 'x'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
app.on_recurrence_changed(); app.update()


def _rn_date_key(text, keysym):
    """The date field holding *text*, then a key released there -- with the
    keyboard on the field first: a generated key follows the focus."""
    app.date_entry.delete(0, 'end')
    app.date_entry.insert(0, text)
    app.date_entry.focus_force()
    for _ in range(60):
        app.update(); app.update_idletasks()
        if app.focus_get() is app.date_entry:
            break
        _t5f.sleep(0.01)
    app.date_entry.event_generate('<KeyRelease>', keysym=keysym)
    app.update()
    return app.focus_get() is app.date_entry


_rn_focus = _rn_date_key('30/09/2026', '6')
_rn_said_bad = str(app.rec_summary_lbl.cget('text'))
_rn_focus = _rn_date_key('2026-09-30', '0') and _rn_focus
_rn_said_typed = str(app.rec_summary_lbl.cget('text'))
app._cancel_pending_autosave()
_rn_series(interval=2)
app.clear_note_date(); app.update()
_rn_said_clear = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'the summary follows the date field as it is typed and cleared, and '
      f'names a date it cannot read on a note with none ({_rn_said_bad!r}; '
      f'{_rn_said_typed!r}; {_rn_said_clear!r})',
      _rn_focus and 'the date “30/09/2026”' in _rn_said_bad
      and _rn_said_typed == 'Every week'
      and 'still starts 2026-09-07' in _rn_said_clear)
# ...and a date pasted there, which lands after the field's own bindings
# return. The clipboard is a stand-in: the person's own is never read.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Undated', 'body': 'x'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
app.on_recurrence_changed(); app.update()
_rn_paste_before = str(app.rec_summary_lbl.cget('text'))
app.tk.eval('rename ::tk::GetSelection ::tk::_qa5_real_GetSelection')
app.tk.createcommand('::qa5_clip', lambda: '2026-09-30')
app.tk.eval('proc ::tk::GetSelection {w {sel PRIMARY}} {'
            ' if {$sel eq "CLIPBOARD"} {return [::qa5_clip]};'
            ' return [::tk::_qa5_real_GetSelection $w $sel] }')
try:
    app.date_entry.delete(0, 'end')
    app.date_entry.event_generate('<<Paste>>')
    app.update()
finally:
    app.tk.eval('rename ::tk::GetSelection {}')
    app.tk.eval('rename ::tk::_qa5_real_GetSelection ::tk::GetSelection')
app._cancel_pending_autosave()
_rn_paste_field = app.date_entry.get()
_rn_paste_after = str(app.rec_summary_lbl.cget('text'))
check(f'...and so does a date pasted into the field ({_rn_paste_field!r}: '
      f'{_rn_paste_before!r} -> {_rn_paste_after!r})',
      _rn_paste_field == '2026-09-30'
      and 'needs a start date' in _rn_paste_before
      and _rn_paste_after == 'Every week')
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed()
app._cancel_pending_autosave()

# "Continue without it" on a route that keeps the note open puts the stored
# date back and cancels the autosave -- the tick that put the status line
# right -- so the line went on saying the date was not saved.
_rn_series(interval=2)
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '07/09/2026')
app.save_current_note(auto=True); app.update()
_rn_said_before = str(app.status_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
_rn_said_after = str(app.status_lbl.cget('text'))
check(f'putting the stored date back puts the status line right at once '
      f'({_rn_said_before!r} -> {_rn_said_after!r})',
      'except the date' in _rn_said_before and 'except' not in _rn_said_after)
# ...and only while that line is still on screen. A day saved "This
# occurrence only" puts the series' date back too, and the put-right wrote
# an EARLIER save's words -- its time, the one that left the date out --
# over the occurrence save's own.
_rr_day()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '30/09/2026')
_rn_warn_real = app.show_warning
app.show_warning = lambda *a, **k: True
app.ask_occurrence_scope = lambda *a, **k: 'series'
try:
    app.save_current_note(); app.update()
    _rn_first = str(app.status_lbl.cget('text'))
    app.body_text.insert('end', ' more')
    app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
    app.save_current_note(); app.update()
    _rn_second = str(app.status_lbl.cget('text'))
finally:
    app.show_warning = _rn_warn_real
    app.ask_occurrence_scope = _oc_real_scope
app._cancel_pending_autosave()
check(f'a day saved on its own keeps its own words in the status line '
      f'({_rn_first!r} -> {_rn_second!r})',
      'except' in _rn_first and '2026-09-14 only' in _rn_second)

# Every key in the date field redraws the repeat's summary beside the
# field's own autosave, and each key read the whole body for its word count
# twice: the summary changes no word of it. On a note that repeats and on
# one that does not (the summary's two ways out).
_rn_counted = []
for _rn_repeats in (True, False):
    if _rn_repeats:
        _rn_series(interval=2)
    else:
        app.new_note(); app.update()
        app.notes = [NO.normalize_note({'id': 1, 'title': 'Plain',
                                        'body': 'x', 'date': '2026-09-07'})]
        app.save_notes()
        app.open_note_in_tab(app.find_note(1)); app.update()
    _rn_n = {'n': 0}
    _rn_count_real = app.update_word_count

    def _rn_counting():
        _rn_n['n'] += 1
        return _rn_count_real()

    app.update_word_count = _rn_counting
    try:
        _rn_key_ok = _rn_date_key('2026-09-07', '7')
    finally:
        del app.update_word_count
    app._cancel_pending_autosave()
    _rn_counted.append((_rn_key_ok, _rn_n['n']))
check(f'a key in the date field counts the note\'s words once '
      f'({_rn_counted})',
      _rn_counted == [(True, 1), (True, 1)])


# Restore previous with a big delete still waiting for its autosave: the
# autosave ran while the question waited and made a new rescue copy of the
# words just deleted, which the restore -- of the copy read before the
# question -- then dropped. The pending save runs first now, and its copy
# is the one restored.
app.new_note(); app.update()
app.notes = [NO.normalize_note({
    'id': 1, 'title': 'Long', 'body': 'CURRENT TEXT, the words just deleted '
    'by the person, many of them, enough to count as a big change'})]
app.notes[0]['_prev'] = {'title': 'Long', 'body': 'OLDEST TEXT',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'x')
# The autosave waiting, as after any edit -- due far off, so what the check
# below reads is whether the restore cancelled its timer, not whether a slow
# machine let it fire meanwhile.
app._autosave_job = app.after(60000, app._autosave_now)
_rn_job = app._autosave_job
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
# The save it ran first was a timer's: cancelled, not just forgotten, or it
# fires again after the restore.
_rn_left = _rn_job in app.tk.splitlist(app.tk.call('after', 'info'))
app.after_cancel(_rn_job)
app._cancel_pending_autosave()
_rn_body = app.find_note(1).get('body', '')
check(f'Restore previous right after a big delete brings the deleted words '
      f'back, and leaves no autosave timer behind ({_rn_body[:40]!r}; '
      f'left: {_rn_left})',
      'the words just deleted' in _rn_body and not _rn_left)

app.new_note(); app.update()
app.notes = []; app.save_notes()

print(f"=== QA5 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
