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
app.date_entry.event_generate('<KeyRelease>')
app.update()
check('typing a date schedules an autosave', getattr(app, '_autosave_job', None) is not None)
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

print(f"=== QA5 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
