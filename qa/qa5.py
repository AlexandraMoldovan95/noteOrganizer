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

# ---- TURNING THE REPEAT OFF ON A DAY WITH ITS OWN TEXT KEEPS THAT TEXT ----
# Only the repeat changed, so nobody was asked; the note kept the series'
# text, and the day's -- the text on screen a moment before -- went with
# the per-day edits, in no file and without a word. It is the rescue copy
# now, as the series' text is when the day's replaces it.
_ro_real_dlg = app._themed_dialog
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT',
                       'formatting': [{'start': 0, 'end': 6, 'style': 'bold'}],
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {
                           'title': 'Standup (moved)',
                           'body': 'DAY TEXT: room 9'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
check('fixture: the day on screen shows its own text',
      app.body_text.get('1.0', 'end-1c') == 'DAY TEXT: room 9'
      and app.current_occurrence_date == '2026-09-14')
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
_ro_asked = []
app._themed_dialog = lambda *a, **k: (_ro_asked.append(a[0]), True)[1]
app.open_note_in_tab(app.find_note(2)); app.update()
app._themed_dialog = _ro_real_dlg
_ro = app.find_note(1)
check(f'fixture: only the repeat changed, so nothing was asked ({_ro_asked}), '
      'and the note no longer repeats, keeping the series\' text',
      _ro_asked == [] and not _ro['recurrence']['freq']
      and _ro['body'].rstrip('\n') == 'SERIES TEXT' and _ro['overrides'] == {})
check("turning the repeat off on a day with its own text keeps that text "
      f"as the rescue copy ({(_ro.get('_prev') or {}).get('body')!r})",
      (_ro.get('_prev') or {}).get('title') == 'Standup (moved)'
      and (_ro.get('_prev') or {}).get('body') == 'DAY TEXT: room 9')
app.open_note_in_tab(_ro); app.update()
_ro_yes = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version(); app.update()
app.ask_yes_no = _ro_yes
check('...which Restore previous brings back',
      app.find_note(1)['body'].rstrip('\n') == 'DAY TEXT: room 9'
      and app.find_note(1)['title'] == 'Standup (moved)')
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
app.new_note(); app.update()
app.notes = []; app.save_notes()

print(f"=== QA5 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
