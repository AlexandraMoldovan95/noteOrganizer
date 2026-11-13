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
from _qa_support import click as _qa_click, pin_popup_visibility as _qa_pin
from _qa_support import waiting_timers as _qa_waiting
from _qa_support import out_of_sight as _qa_out_of_sight
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
_pg_kept = []
def purge():
    kept, _purged = NO.purge_expired_trash(app.trash, app.notes)
    _pg_kept.extend(e.get('id') for e in kept)
    app.update()
safe('purge survives bad deleted_at in trash', purge)
check('...and keeps the entries whose moment it cannot read',
      2 in _pg_kept and 3 in _pg_kept)

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
    # With a default, as every lookup a mutant can empty: a bare next()
    # stopped the suite before its footer.
    _mnote = next((n for n in _mdisk if n['id'] == _msid), {'title': '', 'body': ''})
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
import glob as _glob5, time as _time5, json as _json5c, os
with open('notes_data.json', 'w', encoding='utf-8') as _f5:
    _f5.write('this is not json')
# And an expired Trash entry whose file a note in that unread file may
# show: the startup purge spares files the notes use, and on this launch
# there are no notes to ask, so it must not run at all.
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_cp5_file = os.path.join(NO.ATTACHMENTS_DIR, 'corrupt_launch_shared.txt')
with open(_cp5_file, 'w') as _f5:
    _f5.write('a note in the unread file shows me')
with open('trash.json', 'w', encoding='utf-8') as _f5:
    _json5c.dump([{'id': 77, 'title': 'old copy',
                   'deleted_at': '2020-01-01 00:00:00',
                   'attachments': [{'filename': 'x.txt',
                                    'stored_as': 'corrupt_launch_shared.txt'}]}],
                 _f5)
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
check('...and purges nothing from the Trash on that launch: the entry and '
      'its file are both still there',
      len(app5c.trash) == 1 and os.path.isfile(_cp5_file))
app5c.destroy()
with open('trash.json', 'w', encoding='utf-8') as _f5:
    _f5.write('[]')
if os.path.isfile(_cp5_file):   # a regression purged it; still reach the footer
    os.remove(_cp5_file)

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
      and 'A copy of it could not be kept either' in _msgs5b[0][1]
      and 'will not save anything over it' in _msgs5b[0][1])
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
_notices = []
app5f.show_info = lambda title, msg, **k: (_notices.append((title, msg)), True)[1]
# The app announces its own start from a timer, 250 ms after its window. On
# a slow CI runner that announcement landed inside the checks below and was
# counted as one of theirs, so it has its turn first, and the checks count
# only the notices they ask for.
_t5f_end = _t5f.time() + 5
while _qa_waiting(app5f, 'announce_startup_changes') and _t5f.time() < _t5f_end:
    app5f.update(); _t5f.sleep(0.02)
check("the new app's own startup notice has had its turn before the counting",
      not _qa_waiting(app5f, 'announce_startup_changes'))
_notices.clear()

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

# ---- A FIRST START OPENS ON THE WELCOME NOTE -- ONCE ----
# The owner's request: a first install greets the user with a note that
# shows the app, deletable, and offered again from Settings -> About. Only
# a notebook with no notes file at this start is greeted -- this folder's
# was seeded, so it is taken away first, as on a first install (the
# migrations ran once, when the app was first built -- initialise() does
# nothing the second time -- so nothing can be adopted here).
import os as _os5w
def _w5_reset_settings():
    _s5w = NO.load_settings()
    for _k5w in ('welcome_offered', 'welcome_note_uid', 'last_open_note_id'):
        _s5w.pop(_k5w, None)
    NO.save_settings(_s5w)


def _w5_app():
    _a = NO.NoteOrganizer(); _a._poll_active_dirty = lambda: None
    _a.show_info = lambda *a, **k: True
    _a.ask_yes_no = lambda *a, **k: True
    _a.update()
    return _a


def _w5_show_button(a):
    a.show_settings_page(); a.update()
    a.toggle_settings_panel('about'); a.update()
    found = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, tk.Button) and str(c.cget('text')) == 'Show':
                found.append(c)
            walk(c)
    walk(a.settings_page)
    return found[0] if found else None


_W5_TITLE = NO.build_welcome_note()['title']
if _os5w.path.exists('notes_data.json'):
    _os5w.remove('notes_data.json')
_w5_reset_settings()
app5w = _w5_app()
_w5_open = (app5w.find_note(app5w.selected_note_id)
            if app5w.selected_note_id is not None else None)
check(f'a first start, with no notes file, opens on the welcome note alone '
      f'({[n["title"] for n in app5w.notes]})',
      [n['title'] for n in app5w.notes] == [_W5_TITLE]
      and _w5_open is not None and _w5_open['title'] == _W5_TITLE)
check('...and the editor shows it exactly as it is stored',
      _w5_open is not None
      and app5w.title_entry.get() == _w5_open['title']
      and app5w.body_text.get('1.0', 'end-1c') == _w5_open['body']
      and app5w._extract_formatting(app5w.body_text) == _w5_open['formatting']
      and app5w._extract_paragraphs(app5w.body_text) == _w5_open['paragraphs'])
# Every heading's title starts in one column. Tk draws an icon with the
# first font that has it: ℹ and ✍, older symbols, came from the text font,
# as narrow as letters, and their titles started left of the others -- the
# owner saw it. Measured where the app ships: on Windows the emoji font
# draws the note's icons; another system's fonts are its own.
if sys.platform == 'win32' and _w5_open is not None:
    from noteorganizer.core.welcome import LINES as _W5_LINES
    _w5_heads = [_l[2:] for _l in _W5_LINES if _l.startswith('# ')]
    _w5_t = app5w.body_text
    _w5_starts = {}
    for _w5_head in _w5_heads:
        _w5_words = _w5_head.split(' ', 1)[1]
        _w5_at = _w5_t.search(_w5_head, '1.0')
        _w5_word = (_w5_t.search(_w5_words, _w5_at.split('.')[0] + '.0',
                                 _w5_at.split('.')[0] + '.end')
                    if _w5_at else '')
        _w5_box = None
        if _w5_word:
            _w5_t.see(_w5_word); app5w.update()
            _w5_box = _w5_t.bbox(_w5_word)
        _w5_starts[_w5_words] = _w5_box[0] if _w5_box else None
    check(f'every heading of the welcome note starts its title in one column '
          f'({_w5_starts})',
          len(_w5_starts) == len(_w5_heads) >= 5
          and None not in _w5_starts.values()
          and len(set(_w5_starts.values())) == 1)
app5w.delete_current_note(); app5w.update()
app5w.destroy()
app5x = _w5_app()
check(f'deleted, it does not come back at the next start '
      f'({[n["title"] for n in app5x.notes]})', app5x.notes == [])
_w5_btn = _w5_show_button(app5x)
if _w5_btn is not None:
    _w5_btn.invoke(); app5x.update()
_w5_back = app5x.find_note(app5x.selected_note_id) \
    if app5x.selected_note_id is not None else None
_w5_btn = _w5_show_button(app5x)
if _w5_btn is not None:
    _w5_btn.invoke(); app5x.update()
check(f"Settings -> About's Show brings a deleted welcome note back, and a "
      f"second press opens it rather than adding another "
      f"({[n['title'] for n in app5x.notes]})",
      _w5_back is not None and _w5_back['title'] == _W5_TITLE
      and [n['title'] for n in app5x.notes] == [_W5_TITLE]
      and not app5x._settings_open
      and app5x.selected_note_id == _w5_back['id'])
app5x.destroy()
# A notebook with its file -- emptied by hand -- is never greeted, nor a
# fresh one whose welcome was already offered once.
with open('notes_data.json', 'w', encoding='utf-8') as _f5w:
    _f5w.write('[]')
_w5_reset_settings()
app5y = _w5_app()
_w5_emptied = [n['title'] for n in app5y.notes]
app5y.destroy()
_os5w.remove('notes_data.json')
NO.save_setting('welcome_offered', True)
app5z = _w5_app()
_w5_offered = [n['title'] for n in app5z.notes]
app5z.destroy()
check(f'an emptied notebook gets no welcome note, nor a fresh one that was '
      f'offered it before ({_w5_emptied}; {_w5_offered})',
      _w5_emptied == [] and _w5_offered == [])
with open('notes_data.json', 'w', encoding='utf-8') as _f5w:
    _f5w.write('[]')

# ---- A DAY'S MARKER KEPT WITH THE VARIATION SELECTOR LOSES IT ----
# Tk draws U+FE0F as a gap after the emoji, and older pickers wrote it into
# the day markers. Read back at the start, each comes in without it -- or
# the marker picker, whose own heart has none, would not know the day's.
_VS5 = chr(0xFE0F)
NO.save_setting('day_emoji', {'2026-05-05': [chr(0x2764) + _VS5, chr(0x2B50)]})
app5m = _w5_app()
_m5 = app5m.day_emoji.get('2026-05-05')
app5m.destroy()
NO.save_setting('day_emoji', {})
check(f"a day's markers saved with the variation selector come in without "
      f"it, and match the picker's own ({_m5!r})",
      _m5 == [chr(0x2764), chr(0x2B50)]
      and chr(0x2764) in [em for em, _c in NO.NoteOrganizer.DAY_MARKER_EMOJIS])

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
                                 'Broken': '#not-hex'}}, _f5g)
with open('notes_data.json', 'w', encoding='utf-8') as _f5g:
    _json5g.dump([{'id': 1, 'title': 'Colored', 'body': 'x',
                   'category': 'General', 'color': '#zzzzzz',
                   'updated': '2026-01-01 00:00',
                   'created': '2026-01-01 00:00'},
                  # A per-day override carries 'color' exactly like the
                  # base note does, and it reaches the SAME Tk configure
                  # when the calendar draws that day -- the one colour
                  # door the first sweep missed. The day's text edit must
                  # survive; only the undrawable colour is dropped.
                  {'id': 2, 'title': 'Series', 'body': 'y',
                   'category': 'General', 'date': '2026-04-01',
                   'recurrence': {'freq': 'weekly', 'weekdays': [2]},
                   'overrides': {'2026-04-08': {'title': 'that day',
                                                'color': '#not-hex'},
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
      NO.CATEGORY_COLORS.get('Broken') is None)
check('the note survives with its undrawable colour blanked',
      _built5g and app5g.notes and app5g.notes[0]['color'] == ''
      and app5g.notes[0]['title'] == 'Colored')
_ovr5g = (app5g.find_note(2) or {}).get('overrides', {}) if _built5g else {}
check('a per-day override loses only its undrawable colour',
      _ovr5g.get('2026-04-08') == {'title': 'that day'})
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
# That date is read now (see DATES THE WAY PEOPLE WRITE THEM below), so the
# unreadable date here is one that cannot exist: September has no 31st.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Shopping', 'body': 'milk',
                                'date': '2026-09-01'})]
app.save_notes()
app.open_note_in_tab(app.notes[0]); app.update()
app.body_text.insert('end', '\neggs')
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '31/09/2026')
app._autosave_now(); app.update()
check('a pause after an unreadable date still saves the words',
      app.find_note(1)['body'].rstrip('\n').endswith('eggs'))
check('...keeping the date the note already had',
      app.find_note(1)['date'] == '2026-09-01')
check('...and the status line says what was left out',
      '31/09/2026' in str(app.status_lbl.cget('text')))
_real_dlg5 = app._themed_dialog
_asked5 = []
app._themed_dialog = lambda *a, **k: (_asked5.append(a[0]), False)[1]
check('leaving asks first -- and "Go back and fix it" stays on the note',
      app._flush_autosave() is False and len(_asked5) == 1
      and app.date_entry.get() == '31/09/2026')
app._themed_dialog = lambda *a, **k: True
check('..."Continue without it" goes on',
      app._flush_autosave() is True)
app._themed_dialog = _real_dlg5
check('...showing the date the note keeps, so nothing reads as unsaved',
      app.date_entry.get() == '01.09.2026'
      and app.editor_state_matches_saved(app.capture_editor_state()))
# A code made in the editor carries what a save would keep: one carrying
# "30.09.2026" delivered a date no save could store, and every edit to the
# note that arrived was lost on the far end. (30.09.2026 is read now; a day
# that does not exist stands for every date no save can store.)
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '31.09.2026')
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
# (Day first is read now; an end that cannot exist stands for the rest.)
app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
app.on_recurrence_changed()
app.rec_end_mode_var.set('on')
app.rec_end_date_var.set('32/12/2026')
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

# ---- DATES THE WAY PEOPLE WRITE THEM ----
# The date field reads a date as a person writes it -- 16.11.2026,
# 16/11/2026, 2026-11-16, the month as a word -- shows it day first, and
# stores YYYY-MM-DD whatever was typed. A short or a missing year is read
# only once the person has finished: leaving the field, pressing Save,
# leaving the note, asking for a code. Read while typing, "16.11.20" on its
# way to 2026 would be a wrong year saved. Each check below is a seam the
# feature crosses: the comparator, the autosave's timing, the settling,
# the end date, the card, the picker, the code.
import datetime as _dt5w
import re as _re5w

_W_YEAR = _dt5w.date.today().year


def _w_note(**fields):
    app.new_note(); app.update()
    app.notes = [NO.normalize_note(dict({'id': 1, 'title': 'Dentist',
                                         'body': 'x'}, **fields)),
                 NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._cancel_pending_autosave()


def _w_type(text):
    app.date_entry.delete(0, 'end')
    app.date_entry.insert(0, text)


def _w_widgets(root):
    found, todo = [], [root]
    while todo:
        w = todo.pop()
        found.append(w)
        todo.extend(w.winfo_children())
    return found


# Every question the app asks in this section is recorded and answered
# (True: "Continue without it"), never left waiting: a mutant that leaves
# a date out must turn into a red check here, not a suite stopped in front
# of a question nobody will answer -- the first run of these checks did
# exactly that.
_w_real_dlg = app._themed_dialog
_w_asked = []
app._themed_dialog = lambda *a, **k: (_w_asked.append(a[0]), True)[1]

app.new_note(); app.update()
check('an empty date field shows the form a date is read in',
      app.date_entry.get() == 'DD.MM.YYYY' == NO.DATE_FORM)
_w_note(date='2026-10-17')
check('a dated note shows its date day first, and opens clean',
      app.date_entry.get() == '17.10.2026'
      and app.editor_state_matches_saved(app.capture_editor_state()))
check('...and its card says it day first too',
      '\U0001F4C5\xa017.10.2026' in app._card_texts(app.find_note(1))['tags'])
_w_stored = []
for _w_form in ('16.11.2026', '16/11/2026', '16 nov 2026',
                '16 noiembrie 2026', 'November 16, 2026', '2026-11-16'):
    _w_note(date='2026-10-17')
    _w_type(_w_form)
    app._autosave_now(); app.update()
    _w_stored.append((_w_form, app.find_note(1)['date'],
                      'except' in str(app.status_lbl.cget('text')),
                      app.editor_state_matches_saved(app.capture_editor_state())))
check(f'a date written each way people write it is stored in the one form, '
      f'and the editor reads as saved after ({_w_stored})',
      all(stored == '2026-11-16' and not named and clean
          for _f, stored, named, clean in _w_stored))
check(f'...and the save\'s status line says its moment day first '
      f'({str(app.status_lbl.cget("text"))!r})',
      bool(_re5w.match(r'Auto-saved \d\d\.\d\d\.\d{4} \d\d:\d\d',
                       str(app.status_lbl.cget('text')))))

_w_note(date='2026-10-17')
_w_type('16.11.20')
app._autosave_now(); app.update()
_w_mid = app.find_note(1)['date']
_w_type('16.11.2026')
app._autosave_now(); app.update()
check(f'a year still being typed is never saved as a year of its own '
      f'({_w_mid}, then {app.find_note(1)["date"]})',
      _w_mid == '2026-10-17' and app.find_note(1)['date'] == '2026-11-16')

_w_note(date='2026-10-17')
_w_type('16.11')
app.date_entry.event_generate('<FocusOut>'); app.update()
_w_short = app.date_entry.get()
_w_type('2026-11-16')
app.date_entry.event_generate('<FocusOut>'); app.update()
_w_iso = app.date_entry.get()
_w_type('31/09/2026')
app.date_entry.event_generate('<FocusOut>'); app.update()
_w_bad = app.date_entry.get()
app._cancel_pending_autosave()
check(f'leaving the field writes the date in the form it shows, a missing '
      f'year completed, and leaves what it cannot read as typed '
      f'({_w_short!r}; {_w_iso!r}; {_w_bad!r})',
      _w_short == '16.11.%d' % _W_YEAR and _w_iso == '16.11.2026'
      and _w_bad == '31/09/2026')
check('...and a date no one can read is left out in words that show the form',
      any('(write dates like 30.09.2026)' in item
          for item in app._date_and_repeat_to_store()[2]))

# A click anywhere else finishes with the field as well. In Tk a click on a
# label or an empty stretch of the window moves the keyboard nowhere, so no
# <FocusOut> came: 17.10 typed and a click beside it was read as still
# being typed, and nothing was saved (field report). Enter finishes too.


def _w_focus(entry):
    entry.focus_force()
    for _ in range(60):
        app.update(); app.update_idletasks()
        if app.focus_get() is entry:
            return True
        _t5f.sleep(0.01)
    return False


_w_note(date='2026-10-17')
_w_focused = _w_focus(app.date_entry)
_w_type('16.11')
# A click in the field itself is the person still at work -- moving the
# caret, say -- and finishes nothing.
_qa_click(app.date_entry)
app.update()
_w_inside = app.date_entry.get()
_qa_click(app.date_entry.master)
app.update()
_w_clicked = app.date_entry.get()
# ...and the caret leaves with it: a click on empty space takes the keyboard
# out of the box, app-wide (field pass) -- Tk on its own moves it nowhere.
_w_released = app.focus_get() is not app.date_entry
app._autosave_now(); app.update()
check(f'a click beside the field, on no box at all, finishes with it: the '
      f'date is completed and saved, and the caret leaves the field '
      f'({_w_focused}; {_w_released}; {_w_clicked!r}; '
      f'{app.find_note(1)["date"]})',
      _w_focused and _w_released and _w_clicked == '16.11.%d' % _W_YEAR
      and app.find_note(1)['date'] == '%d-11-16' % _W_YEAR)
check(f'...while a click in the field itself finishes nothing ({_w_inside!r})',
      _w_inside == '16.11')
_w_focus(app.date_entry)
_w_type('15.11.26')
app.date_entry.event_generate('<Return>')
app.update()
_w_entered = app.date_entry.get()
app._cancel_pending_autosave()
check(f'...and so does Enter in it ({_w_entered!r})',
      _w_entered == '15.11.2026')
# Once the keyboard has left the field, a click elsewhere is about something
# else: a value put back into the field by the app -- a half-typed date a
# reload carried over, say -- stays as it was until the person finishes it.
_w_back = _w_focus(app.body_text)
_w_type('14.11')
_qa_click(app.date_entry.master)
app.update()
_w_untouched = app.date_entry.get()
app._show_date_in_field('2026-10-17')
app._cancel_pending_autosave()
check(f'...and once the keyboard has left the field, a click elsewhere '
      f'leaves it alone ({_w_back}; {_w_untouched!r})',
      _w_back and _w_untouched == '14.11')

# Every box, not only the date: a click on empty space takes the caret out
# (field pass -- the calendar History search kept blinking through every
# click around it). What does something with a click keeps its own way, and
# a popup's blank keeps the popup's box, or the popup would close.
_er_seen = {}
for _er_name, _er_box in (('title', app.title_entry), ('body', app.body_text)):
    _er_ok = _w_focus(_er_box)
    _qa_click(app.date_entry.master)
    app.update()
    _er_seen[_er_name] = _er_ok and app.focus_get() is not _er_box
_er_hits = []
_er_link = tk.Label(app, text='a label that does something')
_er_link.bind('<Button-1>', lambda e: _er_hits.append(1))
_er_link.place(x=4, y=4)
app.update()
_w_focus(app.title_entry)
_qa_click(_er_link)
app.update()
_er_seen['clickable label'] = bool(_er_hits) and app.focus_get() is app.title_entry
_er_link.destroy()
_er_pop = tk.Toplevel(app)
_er_pop_box = tk.Entry(_er_pop)
_er_pop_box.pack()
_er_pop_blank = tk.Frame(_er_pop, width=80, height=40)
_er_pop_blank.pack()
app.update()
_w_focus(_er_pop_box)
_qa_click(_er_pop_blank)
app.update()
_er_seen['popup blank'] = app.focus_get() is _er_pop_box
_er_pop.destroy()
app.update()
check(f'a click on empty space releases the caret from any box, and leaves '
      f'clickable things and popups their own ({_er_seen})',
      _er_seen == {'title': True, 'body': True, 'clickable label': True,
                   'popup blank': True})

# An open table cell is left the way any click elsewhere leaves it,
# committed and closed (audit): with the keyboard moved to the window, its
# own FocusOut read the move as passing, and the cell stayed open with no
# keyboard -- the next Bold went to the cell instead of the body.
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', '| a | b |' + chr(10) + '| --- | --- |' + chr(10)
                     + '| c | d |' + chr(10))
app._render_table_grids(); app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 0)
app.update()
_ec_box = app._cell_editor['entry'] if app._cell_editor else None
if _ec_box is not None:
    _ec_box.delete('1.0', 'end')
    _ec_box.insert('1.0', 'typed')
    _w_focus(_ec_box)
_qa_click(app.date_entry.master)
app.update(); app.update_idletasks(); app.update()
_ec_grid = app._grid_at_line(1)
check(f'a click on empty space commits and closes an open table cell '
      f'({app._cell_editor}; '
      f'{_ec_grid["cells"][(1, 0)]["value"] if _ec_grid else None!r})',
      _ec_box is not None and app._cell_editor is None
      and _ec_grid is not None and _ec_grid['cells'][(1, 0)]['value'] == 'typed')
app._cancel_pending_autosave()

# A click on something that does something with it moves no keyboard, so
# the date field's own watch is what finishes it there.
_w_note(date='2026-10-17')
_w_focus(app.date_entry)
_w_type('16.11')
_ed_link = tk.Label(app, text='a label that does something')
_ed_link.bind('<Button-1>', lambda e: None)
_ed_link.place(x=4, y=4)
app.update()
_qa_click(_ed_link)
app.update()
_ed_after = app.date_entry.get()
_ed_link.destroy()
app._cancel_pending_autosave()
check(f'a click on a clickable label beside the date field finishes the date '
      f'too ({_ed_after!r})', _ed_after == '16.11.%d' % _W_YEAR)

_w_note(date='2026-10-17')
_w_type('16.11.26')
del _w_asked[:]
app.open_note_in_tab(app.find_note(2)); app.update()
check(f'leaving the note with a short year typed stores the date whole, '
      f'asking nothing ({app.find_note(1)["date"]}; {_w_asked})',
      app.find_note(1)['date'] == '2026-11-16' and _w_asked == []
      and app.selected_note_id == 2)

_w_note(date='2026-10-17')
_w_type('16.11')
del _w_asked[:]
app.save_current_note(); app.update()
check(f'Save pressed on a date with no year stores this year\'s, and shows it, '
      f'asking nothing ({app.find_note(1)["date"]}; {app.date_entry.get()!r}; '
      f'{_w_asked})',
      app.find_note(1)['date'] == '%d-11-16' % _W_YEAR
      and app.date_entry.get() == '16.11.%d' % _W_YEAR and _w_asked == [])

_w_note(date='2026-10-17')
_w_type('16.11')
app.share_current_note_as_code(); app.update()
_w_code = [w for w in app.editor_code_area.winfo_children()
           if isinstance(w, tk.Text)]
_w_payload = (NO.decode_share_code(_w_code[0].get('1.0', 'end-1c'))
              if _w_code else [])
_w_shared = ((_w_payload['notes'] if isinstance(_w_payload, dict)
              else _w_payload) or [{}])[0]
check(f'a code asked for with a date typed short carries it whole '
      f'({_w_shared.get("date")})',
      _w_shared.get('date') == '%d-11-16' % _W_YEAR)

_w_note(date='2020-01-06', recurrence={'freq': 'weekly'})
app.rec_end_mode_var.set('on'); app.on_end_mode_changed()
app.rec_end_date_var.set('31.12.2026')
app._autosave_now(); app.update()
_w_end = app.find_note(1)['recurrence']['end']
app.rec_end_date_var.set('30.12')
app.rec_end_date_entry.event_generate('<FocusOut>'); app.update()
_w_end_box = app.rec_end_date_var.get()
del _w_asked[:]
app.open_note_in_tab(app.find_note(2)); app.update()
app.open_note_in_tab(app.find_note(1)); app.update()
check(f'an end date written day first is stored, completed on leaving its '
      f'box, and shown day first again, asking nothing ({_w_end}; '
      f'{_w_end_box!r}; {app.rec_end_date_var.get()!r}; '
      f'{app.find_note(1)["recurrence"]["end"]}; {_w_asked})',
      _w_end == '2026-12-31' and _w_end_box == '30.12.%d' % _W_YEAR
      and app.find_note(1)['recurrence']['end'] == '%d-12-30' % _W_YEAR
      and app.rec_end_date_var.get() == '30.12.%d' % _W_YEAR
      and _w_asked == [])

_w_note(date='2026-09-07', recurrence={'freq': 'weekly'})
_w_type('14.09.2026')
app.update_recurrence_summary(); app.update()
_w_summary = str(app.rec_summary_lbl.cget('text'))
app._cancel_pending_autosave()
check(f'the repeat\'s summary reads a start date typed day first as the date '
      f'it is ({_w_summary!r})',
      _w_summary == 'Every week')

# A series and one of its days, named day first wherever the app names
# them: the status line on opening each, what a day's Save says, Reset this
# day's question, and what a save leaves out when the start date is cleared.
_w_note(date='2026-09-07', recurrence={'freq': 'weekly'},
        created='2026-09-01 08:15:00', updated='2026-09-02 10:45:00')
_w_said_series = str(app.status_lbl.cget('text'))
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
_w_said_day = str(app.status_lbl.cget('text'))
app.title_entry.insert('end', ' (moved)')
_w_msgs = []
app._themed_dialog = lambda *a, **k: (
    _w_msgs.append((a[0], a[1] if len(a) > 1 else '')), 'occurrence')[1]
app.save_current_note(); app.update()
_w_said_save = str(app.status_lbl.cget('text'))
_w_reset_msgs = []
_w_real_yes = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (
    _w_reset_msgs.append(a[1] if len(a) > 1 else ''), False)[1]
app._reset_occurrence_override(app.find_note(1), '2026-09-14'); app.update()
app.ask_yes_no = _w_real_yes
app._themed_dialog = lambda *a, **k: (_w_asked.append(a[0]), True)[1]
app.open_note_in_tab(app.find_note(1)); app.update()
_w_type('')
_w_cleared = app._date_and_repeat_to_store()[2]
app._show_date_in_field('2026-09-07')
app._cancel_pending_autosave()
check(f'a series and its day are named day first in the status line '
      f'({_w_said_series!r}; {_w_said_day!r})',
      'Created: 01.09.2026 08:15:00' in _w_said_series
      and 'Last updated: 02.09.2026 10:45:00' in _w_said_series
      and _w_said_day == 'Only this day: 14.09.2026')
check(f'...in what a day\'s Save says, asking nothing, and in Reset this day\'s '
      f'question ({_w_said_save!r}; {_w_msgs}; {_w_reset_msgs[:1]})',
      _w_said_save == 'Saved 14.09.2026 only' and _w_msgs == []
      and any(m.startswith('Return 14.09.2026 to the series content?')
              for m in _w_reset_msgs))
check(f'...and in what a save leaves out when the start date is cleared '
      f'({_w_cleared})',
      any('so it still starts 07.09.2026' in item for item in _w_cleared))

_w_note(date='2026-10-17')
_w_type('16.11.2026')
app.open_date_picker(); app.update()
_w_pop = getattr(app, '_mini_popup', None)
_w_buttons = ([b for b in _w_widgets(_w_pop) if isinstance(b, tk.Button)]
              if _w_pop is not None else [])
_w_marked = [b for b in _w_buttons if str(b.cget('text')) == '16'
             and str(b.cget('bg')) == str(app.colors['accent'])]
_w_picked = [b for b in _w_buttons if str(b.cget('text')) == '20']
if _w_picked:
    _w_picked[0].invoke(); app.update()
app._cancel_pending_autosave()
check(f'the date picker opens on a date typed day first and marks its day, '
      f'and a day picked lands day first ({len(_w_marked)}; '
      f'{app.date_entry.get()!r})',
      len(_w_marked) == 1 and app.date_entry.get() == '20.11.2026')
app.new_note(); app.update()
app.notes = []; app.save_notes()
app._themed_dialog = _w_real_dlg

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
# What differs, named in the message: this went red once in a dozen runs
# on a developer machine, and said nothing about which side moved.
_cm_text = app.comments_text.get('1.0', 'end-1c')
_cm_state = app.capture_editor_state()
_cm_note = app.find_note(3) or {}
_cm_diff = {k: (v, _cm_note.get(k)) for k, v in _cm_state.items()
            if k in _cm_note and v != (
                NO.normalize_recurrence(_cm_note.get(k)) if k == 'recurrence'
                else _cm_note.get(k))}
check(f'...and reopen exactly as typed, reading as saved '
      f'({_cm_text!r}; differs from the note: {_cm_diff})',
      _cm_text == '    for x in items:\n        print(x)\n\n'
      and app.editor_state_matches_saved(_cm_state))
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
# A date written day first is read on the way in now (normalize_note), so
# the date that still arrives unreadable is one that cannot exist.
_bd_real_dlg = app._themed_dialog
app.notes = [NO.normalize_note({'id': 1, 'title': 'Arrived', 'body': 'x',
                                'date': '31.09.2026'}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
check('fixture: a note holding a date the app cannot read, shown as it is',
      app.find_note(1)['date'] == '31.09.2026'
      and not NO.read_date('31.09.2026')
      and app.date_entry.get() == '31.09.2026')
_bd_asked = []
app._themed_dialog = lambda *a, **k: (_bd_asked.append(a[0]), True)[1]
app.open_note_in_tab(app.find_note(2)); app.update()
app._themed_dialog = _bd_real_dlg
check(f'leaving it untouched asks nothing ({_bd_asked})',
      _bd_asked == [] and app.selected_note_id == 2)
check('...and the note keeps the date it came with',
      app.find_note(1)['date'] == '31.09.2026')
app.open_note_in_tab(app.find_note(1)); app.update()
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '32.10.2026')
check('...while a different unreadable date typed there is still left out',
      any('32.10.2026' in item for item in app._date_and_repeat_to_store()[2]))
app._show_date_in_field('31.09.2026')
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
    app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '32/10/2026')
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
         refresh=lambda: None)),
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
          and app.date_entry.get() == '32/10/2026')
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
          and app.date_entry.get() == '32/10/2026')
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
# A day shows no repeat to change -- the series has its own view -- and a
# turn-off reaching its hidden boxes is put back: the series still repeats,
# and every day keeps its own text. (Turned off on a day, it once ended the
# series from there; the rescue copy below kept the days, and is now kept for
# the series view alone.)
_ro_asked, _ = _ro_off('2026-09-14')
_ro = app.find_note(1)
check(f"a repeat turned off behind a day's back is put back: the series still "
      f"repeats, nothing was asked ({_ro_asked}), and every day keeps its own text",
      _ro_asked == [] and _ro['recurrence']['freq'] == 'weekly'
      and _ro['body'].rstrip('\n') == 'SERIES TEXT'
      and sorted(_ro.get('overrides') or {}) == ['2026-09-14', '2026-09-21']
      and _ro.get('_prev') is None)
# Saved first, then left: the editor stays on the day it saved.
_ro_fixture()
_ro_asked, _ro_seen = _ro_off('2026-09-14', save_first=True)
check(f"...and Save there keeps the day on screen, reading as saved, and says "
      f"the repeat stays the series' ({_ro_seen})",
      _ro_seen is not None and _ro_seen[0] == 'DAY TEXT: room 9'
      and _ro_seen[1] == '2026-09-14' and _ro_seen[2]
      and "stay the whole series'" in _ro_seen[3]
      and app.find_note(1)['recurrence']['freq'] == 'weekly')
import json as _json5r
with open('notes_data.json', encoding='utf-8') as _f5r:
    _ro_disk = [n for n in _json5r.load(_f5r) if n.get('id') == 1]
check(f'...and leaving it keeps the series\' text, its bold and its days on disk '
      f'({[(n.get("body"), n.get("formatting")) for n in _ro_disk]})',
      len(_ro_disk) == 1 and _ro_disk[0]['body'].rstrip('\n') == 'SERIES TEXT'
      and [f.get('style') for f in _ro_disk[0].get('formatting') or []] == ['bold']
      and sorted(_ro_disk[0].get('overrides') or {}) == ['2026-09-14', '2026-09-21'])
# Turned off from the series view: the days' own text is kept too.
_ro_fixture()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
# Save asks nothing: a question here would wait for an answer no one gives.
_ro_asked = []
app._themed_dialog = lambda *a, **k: (_ro_asked.append(a[0]), None)[1]
try:
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_ro_back = _ro_restored()
check(f'turned off from the series view, every day\'s own text is kept and '
      f'comes back with Restore previous ({_ro_back}; asked {_ro_asked})',
      _ro_back == _RO_WHOLE and _ro_asked == [])
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
      f'the note had, its series still repeating ({_ro_asked})',
      _ro_asked == [] and app.find_note(1)['recurrence']['freq'] == 'weekly'
      and (app.find_note(1).get('_prev') or {}).get('body') == 'AN OLDER VERSION')

# ---- A REPEAT ENDED ANOTHER WAY KEEPS ITS DAYS TOO ----
# A share code whose copy does not repeat, answered Update, and a Restore
# previous of a version that did not repeat, both ended the repeat outside
# the editor's save: the days stayed in the note out of sight, the rescue
# copy had no room for them, and the next small edit's save dropped them
# with no copy anywhere.
_rd_uid = '11111111-2222-3333-4444-555555555555'


def _rd_edit_and_restore():
    """One small edit, its autosave, then Restore previous answered Yes:
    note 1's repeat and day text after, and whether the words are on disk."""
    app.open_note_in_tab(app.find_note(1)); app.update()
    app.body_text.insert('end-1c', ' and stretch'); app.update()
    app._flush_autosave(); app.update()
    _after_edit = sorted(app.find_note(1).get('overrides') or {})
    app.ask_yes_no = lambda *a, **k: True
    try:
        app.restore_previous_version(); app.update()
    finally:
        app.ask_yes_no = _ro_yes
    n = app.find_note(1)
    with open('notes_data.json', encoding='utf-8') as _f:
        _disk = _f.read()
    return (_after_edit, n['recurrence'].get('freq'),
            NO.effective_note(n, '2026-09-14').get('body'), 'room 9' in _disk)


_ro_fixture()
app.notes[0]['uid'] = _rd_uid
app.save_notes()
app.open_note_in_tab(app.find_note(2)); app.update()
_rd_code = NO.encode_share_code({'uid': _rd_uid, 'title': 'Standup',
                                 'body': 'SERIES TEXT, fixed', 'date': '2026-09-07',
                                 'recurrence': {}})
app._themed_dialog = lambda *a, **k: 'update'
try:
    if not app._is_placed(app.import_panel):
        app.toggle_import_panel(); app.update()
    app.import_box.delete('1.0', 'end'); app.import_box.insert('1.0', _rd_code)
    app._do_inline_import(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_rd = app.find_note(1)
check(f"a share code that ends the repeat copies the series' days into the rescue "
      f"copy and keeps them in the note "
      f"({sorted(_rd.get('overrides') or {})}, {sorted(_rd.get('_prev') or {})})",
      _rd['recurrence'].get('freq') in (None, '')
      and sorted(_rd.get('overrides') or {}) == ['2026-09-14', '2026-09-21']
      and sorted((_rd.get('_prev') or {}).get('overrides') or {})
      == ['2026-09-14', '2026-09-21'])
_rd_back = _rd_edit_and_restore()
check(f'...and after one small edit Restore previous brings the series back with '
      f'every day\'s own text ({_rd_back})',
      _rd_back[1:] == ('weekly', 'DAY TEXT: room 9', True))
# Restore previous of a version that did not repeat, over a series with
# days of its own: the copy it keeps in its turn holds the days.
_ro_fixture()
app.notes[0]['_prev'] = {'title': 'Standup', 'body': 'SERIES TEXT',
                         'formatting': [], 'paragraphs': [], 'comments': '',
                         'recurrence': {'freq': ''}}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
_rd = app.find_note(1)
check(f"a restore that ends the repeat keeps the days in the copy it keeps in "
      f"its turn ({sorted((_rd.get('_prev') or {}).get('overrides') or {})})",
      not _rd['recurrence'].get('freq')
      and sorted(_rd.get('overrides') or {}) == ['2026-09-14', '2026-09-21']
      and sorted((_rd.get('_prev') or {}).get('overrides') or {})
      == ['2026-09-14', '2026-09-21'])
_rd_back = _rd_edit_and_restore()
check(f'...and restoring back after an edit brings the series and its days '
      f'({_rd_back})', _rd_back[1:] == ('weekly', 'DAY TEXT: room 9', True))
# Days a file left on a note that does not repeat are in no other copy:
# the save that clears a one-off note's days keeps these.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT',
                       'date': '2026-09-07', 'recurrence': {},
                       'overrides': {'2026-09-14': {'body': 'DAY TEXT: room 9'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.insert('end-1c', ' more'); app.update()
app.save_current_note(); app.update()
check('a one-off note keeps days with text no copy holds when it is saved',
      'room 9' in (app.find_note(1).get('overrides') or {})
      .get('2026-09-14', {}).get('body', ''))
# The repeat turned off in the editor copies the days and keeps them: in the
# one copy slot alone, the next big rewrite's copy erased them.
_ro_fixture()
app.notes[0]['body'] = 'SERIES TEXT ' + 'long words ' * 10
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
app.save_current_note(); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'Something else entirely')
app.save_current_note(); app.update()
with open('notes_data.json', encoding='utf-8') as _f:
    _rd_disk = _f.read()
check(f"turned off in the editor, then rewritten: every day's own text is still "
      f"in the file ({sorted(app.find_note(1).get('overrides') or {})})",
      'room 9' in _rd_disk and 'DAY 21' in _rd_disk)
# ...and the days it keeps steer nothing while it does not repeat: opened from
# its date on the calendar, the one-off showed its first day's words and the
# save wrote them over the note; a deleted first day hid it.
_ro_fixture()
app.notes[0]['overrides']['2026-09-07'] = {'title': 'Kickoff',
                                           'body': 'FIRST DAY ONLY: room 4'}
app.notes[1].update({'title': 'Gym', 'date': '2026-09-08',
                     'recurrence': {'freq': 'weekly'}, 'exceptions': ['2026-09-08'],
                     'overrides': {'2026-09-15': {'body': 'GYM DAY: legs'}}})
app.notes[1] = NO.normalize_note(app.notes[1])
app.save_notes()
app._themed_dialog = lambda *a, **k: True
try:
    for _kd_id in (1, 2):
        app.open_note_in_tab(app.find_note(_kd_id)); app.update()
        app.rec_freq_var.set(NO.FREQ_LABELS[''])
        app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
from noteorganizer.ui import calendar_view as _kd_cv
_kd_row = _kd_cv._day_row_parts(app, app.find_note(1), '2026-09-07')
check(f'...and its calendar row is the note\'s own, with no day mark ({_kd_row[:2]})',
      'Standup' in _kd_row[0] and '✎' not in ''.join(map(str, _kd_row[:2])))
app._open_note_from_calendar(app.find_note(1), '2026-09-07'); app.update()
_kd_shown =(app.title_entry.get(), app.body_text.get('1.0', 'end-1c').strip())
app.open_note_in_tab(app.find_note(2)); app.update()
_kd_note = app.find_note(1)
_kd_gym = [n.get('title') for n in app.notes_on_date('2026-09-08')]
check(f"a series turned off keeps its days unused: opened from its calendar date "
      f"it shows and keeps its own words ({_kd_shown}, stored "
      f"{(_kd_note['title'], _kd_note['body'][:12])}), and a deleted first day no "
      f"longer hides it ({_kd_gym})",
      _kd_shown == ('Standup', 'SERIES TEXT')
      and (_kd_note['title'], _kd_note['body']) == ('Standup', 'SERIES TEXT')
      and '2026-09-07' in (_kd_note.get('overrides') or {})
      and not app.find_note(2)['recurrence'].get('freq')
      and app.find_note(2).get('exceptions') == ['2026-09-08']
      and 'Gym' in _kd_gym)
# A big delete saved first, the repeat turned off after: the turn-off's copy
# keeps the deleted words with the series. Only the other order was kept.
_ro_fixture()
app.notes[0]['body'] = 'SERIES TEXT ' + 'long words ' * 10
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'x')
app.save_current_note(); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
app.save_current_note(); app.update()
_rd_prev = app.find_note(1).get('_prev') or {}
# One rescue copy per note: an update's takes the place of one the note still
# needs, so the question says so rather than doing it in silence.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'uid': _rd_uid, 'title': 'Passport',
                                'body': 'Passport.'})]
app.notes[0]['_prev'] = {'title': 'Passport', 'body': 'Passport. The blue jacket pocket.',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
_rd_said = []
app._themed_dialog = lambda *a, **k: (_rd_said.append(a[1] if len(a) > 1 else ''), 'cancel')[1]
try:
    if not app._is_placed(app.import_panel):
        app.toggle_import_panel(); app.update()
    app.import_box.delete('1.0', 'end')
    app.import_box.insert('1.0', NO.encode_share_code({'uid': _rd_uid, 'title': 'Passport',
                                                       'body': 'Passport, renewed.'}))
    app._do_inline_import(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
check(f"an update that would replace an earlier version Restore previous holds "
      f"says so ({' '.join(_rd_said)[-90:]!r})",
      any('replaced by the one from before this update' in s for s in _rd_said))
# After an Update, a big delete in the note keeps the Update's copy -- the note
# as it was here before, in no other file -- not the backup's words it deletes,
# which are still in the backup (the copy was replaced).
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'uid': _rd_uid, 'title': 'Passport',
                                'body': 'From the backup: ' + 'renewed in March ' * 6})]
app.notes[0]['_prev'] = {'title': 'Passport', 'body': 'My own words before the update.',
                         'formatting': [], 'paragraphs': [], 'comments': '',
                         'category': 'General', 'color': '', 'checklist': [], 'pinned': False}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'x')
app.save_current_note(); app.update()
_uc_prev = app.find_note(1).get('_prev') or {}
# ...and the words it took away -- written since the Update, or brought back by
# Restore previous -- are kept too, as a note of their own (kept in neither,
# they were in no file).
_uc_aside = next((n for n in app.notes if n.get('title') == 'Passport (earlier text)'), {})
check(f"after an Update, a big delete keeps the copy from before the Update, and the "
      f"words it took away as a note of their own ({(_uc_prev.get('body') or '')[:30]!r}, "
      f"{(_uc_aside.get('body') or '')[:20]!r})",
      _uc_prev.get('body') == 'My own words before the update.'
      and (_uc_aside.get('body') or '').startswith('From the backup:'))
# ...and when those words come back -- Ctrl+Z, a cut pasted back -- their note
# goes again, untouched since (one stayed for good after every Undo).
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'From the backup: ' + 'renewed in March ' * 6)
app.save_current_note(); app.update()
check('...and when the words come back, their note kept aside goes again',
      not any(n.get('title') == 'Passport (earlier text)' for n in app.notes)
      and (app.find_note(1).get('_prev') or {}).get('body') == 'My own words before the update.')
# A paragraph moved -- cut, then pasted elsewhere -- and two big deletes undone
# in turn: each note kept aside goes as its words come back.
_mv_p1 = 'First part: ' + 'packing the tent ' * 4
_mv_p2 = 'Second part: ' + 'buying the tickets ' * 4


def _mv_fixture():
    app.new_note(); app.update()
    app.notes = [NO.normalize_note({'id': 1, 'uid': _rd_uid, 'title': 'Trip',
                                    'body': _mv_p1 + '\n' + _mv_p2})]
    app.notes[0]['_prev'] = {'title': 'Trip', 'body': 'Mine before.', 'formatting': [],
                             'paragraphs': [], 'comments': '', 'category': 'General',
                             'color': '', 'checklist': [], 'pinned': False}
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()


def _mv_body(text):
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', text)
    app.save_current_note(); app.update()


def _mv_asides():
    return sum(1 for n in app.notes if n.get('title') == 'Trip (earlier text)')


_mv_fixture()
_mv_body(_mv_p2)
_mv_made = _mv_asides()
_mv_body(_mv_p2 + '\n' + _mv_p1)
_mv_moved = _mv_asides()
_mv_fixture()
_mv_body(_mv_p2)
_mv_body('x')
_mv_two = _mv_asides()
_mv_body(_mv_p2)
_mv_body(_mv_p1 + '\n' + _mv_p2)
check(f'a paragraph moved, and two deletes undone in turn, leave no note kept aside '
      f'({_mv_made}, {_mv_moved}; {_mv_two}, {_mv_asides()})',
      (_mv_made, _mv_moved, _mv_two, _mv_asides()) == (1, 0, 2, 0))
# The note kept aside, opened in the half second before the words put back are
# saved: that save takes it away, and it was loaded anyway, what was typed into
# it stored by no save.
_mv_fixture()
_mv_body(_mv_p2)
_gh_aside = next((n for n in app.notes if n.get('title') == 'Trip (earlier text)'), None)
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', _mv_p1 + '\n' + _mv_p2)
_gh_opened = app.open_note_in_tab(_gh_aside) if _gh_aside else None
app.update()
check(f'a note kept aside, taken away by the save its opening makes, is not opened '
      f'({_gh_opened}, {app.selected_note_id})',
      _gh_aside is not None and _gh_opened is False and app.selected_note_id == 1
      and _mv_asides() == 0)
# Spent, it is said on the banner too, not only on a status line out of sight,
# whose Show then offered a note just gone...
_sp_toasts = []
_sp_real = app._show_toast
app._show_toast = lambda text, *a, **k: (_sp_toasts.append((text, k.get('action'))), _sp_real(text, *a, **k))[1]
try:
    _mv_fixture()
    _mv_body(_mv_p2)
    _mv_body(_mv_p1 + '\n' + _mv_p2)
finally:
    app._show_toast = _sp_real
check(f'a note kept aside spent again is said on the banner, with no Show ({_sp_toasts[-1:]})',
      bool(_sp_toasts) and 'gone again' in _sp_toasts[-1][0] and _sp_toasts[-1][1] is None)
# ...and held back behind an Undo, then spent before that Undo went: its Show
# is not offered once it goes, waiting for a note gone.
_sp_toasts = []
try:
    _mv_fixture()
    _sp_real('Note moved to Trash', action=lambda: None)
    app._show_toast = lambda text, *a, **k: (_sp_toasts.append((text, k.get('action'))), _sp_real(text, *a, **k))[1]
    _mv_body(_mv_p2)
    _mv_body(_mv_p1 + '\n' + _mv_p2)
    app._hide_toast(); app.update()
    app._hide_toast(); app.update()
finally:
    app._show_toast = _sp_real
check(f'...and held back behind an Undo, then spent, it offers no Show once the Undo goes '
      f'({[t for t, _a in _sp_toasts]})',
      not any('kept as a note of their own' in t for t, _a in _sp_toasts)
      and any('gone again' in t for t, _a in _sp_toasts))
# ...one pinned since, or put back from the Trash, is the person's and stays:
# untouched read as its stamp, it went outright.
_mv_fixture()
_mv_body(_mv_p2)
# None when no note was kept aside: the check's answer, not the suite's end.
_sp_aside = next((n for n in app.notes if n.get('title') == 'Trip (earlier text)'), None)
if _sp_aside:
    _sp_aside['pinned'] = True
_mv_body(_mv_p1 + '\n' + _mv_p2)
_sp_pinned = _mv_asides()
_mv_fixture()
_mv_body(_mv_p2)
_sp_aside = next((n for n in app.notes if n.get('title') == 'Trip (earlier text)'), None)
_sp_gone = _sp_back = None
if _sp_aside:
    # Deleted as a delete does it: out of the notes, into the Trash.
    app.notes.remove(_sp_aside); app._move_notes_to_trash([_sp_aside]); app.save_notes(); app.update()
    _sp_gone = _mv_asides()
    app._restore_trash_entries([e for e in app.trash if e.get('uid') == _sp_aside.get('uid')]); app.update()
    _sp_back = _mv_asides()
_mv_body(_mv_p1 + '\n' + _mv_p2)
check(f'a note kept aside, pinned since or put back from the Trash, stays '
      f'({_sp_pinned}; {_sp_gone} -> {_sp_back} -> {_mv_asides()})',
      _sp_pinned == 1 and (_sp_gone, _sp_back) == (0, 1) and _mv_asides() == 1)
# ...and one the list hides is said so, its Show showing all.
_sp_toasts = []
app._show_toast = lambda text, *a, **k: (_sp_toasts.append((text, k.get('action'))), _sp_real(text, *a, **k))[1]
try:
    _mv_fixture()
    app.filter_var.set(app.FILTER_DATED); app.refresh_note_list(); app.update()
    _mv_body(_mv_p2)
finally:
    app._show_toast = _sp_real
_sp_said = next((t for t, _a in _sp_toasts if 'earlier text' in t), '')
_sp_show = next((a for t, a in _sp_toasts if 'earlier text' in t), None)
if callable(_sp_show):
    _sp_show(); app.update()
check(f'a note kept aside that Show hides is said so, and its Show shows all ({_sp_said!r}, {app.filter_var.get()!r})',
      'hidden by Show: ' + app.FILTER_DATED in _sp_said and app.filter_var.get() == 'All')
app.filter_var.set('All'); app.refresh_note_list(); app.update()
# Comments cleared after an Update: the copy keeps this computer's comments,
# not the backup's, which go to a note of their own.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'uid': _rd_uid, 'title': 'Flat', 'body': 'b',
                                'comments': 'Booked the venue; deposit paid on Friday, receipt in the drawer'})]
app.notes[0]['_prev'] = {'title': 'Flat', 'body': 'b', 'formatting': [], 'paragraphs': [],
                         'comments': 'Call Ana Tue', 'category': 'General', 'color': '',
                         'checklist': [], 'pinned': False}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.comments_text.delete('1.0', 'end')
app.save_current_note(); app.update()
_cc_prev = app.find_note(1).get('_prev') or {}
_cc_aside = next((n for n in app.notes if n.get('title') == 'Flat (earlier text)'), {})
check(f"after an Update, cleared comments leave the copy's own comments, and keep "
      f"theirs as a note ({_cc_prev.get('comments')!r}, {(_cc_aside.get('comments') or '')[:12]!r})",
      _cc_prev.get('comments') == 'Call Ana Tue'
      and (_cc_aside.get('comments') or '').startswith('Booked the venue')
      # the comments alone, not a whole copy of the note
      and _cc_aside.get('body') == '')
# The repeat turned off in the same save as a big delete: the Update's copy
# still kept whole, the words taken as a note of their own.
_ro_fixture()
app.notes[0]['body'] = 'SERIES TEXT ' + 'words from the backup ' * 6
app.notes[0]['_prev'] = {'title': 'Standup', 'body': 'Before the update.', 'formatting': [],
                         'paragraphs': [], 'comments': '', 'category': 'General', 'color': '',
                         'checklist': [], 'pinned': False}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'x')
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_to_prev = app.find_note(1).get('_prev') or {}
_to_aside = next((n for n in app.notes if n.get('title') == 'Standup (earlier text)'), {})
check(f"after an Update, the repeat off and a big delete in one save keep the copy from "
      f"before the Update, and the words as a note ({(_to_prev.get('body') or '')[:20]!r}, "
      f"{(_to_aside.get('body') or '')[:12]!r})",
      _to_prev.get('body') == 'Before the update.'
      and (_to_aside.get('body') or '').startswith('SERIES TEXT'))
check(f"a big delete, then the repeat turned off: the copy holds the deleted words "
      f"and the series ({(_rd_prev.get('body') or '')[:20]!r}, "
      f"{(_rd_prev.get('recurrence') or {}).get('freq')})",
      (_rd_prev.get('body') or '').startswith('SERIES TEXT')
      and (_rd_prev.get('recurrence') or {}).get('freq') == 'weekly')
# ...but when the turn-off's own save also clears the text, the words it takes
# are the newest: the older copy's text in their place left them in no file.
# Select all, type, pick "Does not repeat" and Save, in one save.
_ro_fixture()
app.notes[0]['body'] = 'OLD DRAFT ' + 'old words ' * 10
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'kept line')
app.save_current_note(); app.update()
app.body_text.insert('end-1c', ' NEW WORK ' + 'fresh words ' * 30)
app.save_current_note(); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'done')
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_rd_prev = app.find_note(1).get('_prev') or {}
check(f"a turn-off whose own save clears the text keeps that text, the newest, with "
      f"the series ({(_rd_prev.get('body') or '')[:20]!r}, "
      f"{(_rd_prev.get('recurrence') or {}).get('freq')})",
      'NEW WORK' in (_rd_prev.get('body') or '')
      and (_rd_prev.get('recurrence') or {}).get('freq') == 'weekly')
# ...and so when a save made while the turn-off waited has a copy of its own:
# that copy's older text went in, and the words the last save took were in no
# file. Turn-off picked, a big delete autosaved, words added, cleared.
_ro_fixture()
app.notes[0]['body'] = 'FIRST PART ' + 'early words ' * 25
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed(); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'kept line')
    app._autosave_now(); app.update()
    _rh_held = getattr(app, '_held_text_rescue', None) is not None
    app.body_text.insert('end-1c', ' SECOND PART ' + 'later words ' * 25)
    app._autosave_now(); app.update()
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'done')
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_rd_prev = app.find_note(1).get('_prev') or {}
check(f"...and so when a save made while the turn-off waited holds a copy of its "
      f"own (held: {_rh_held}; {(_rd_prev.get('body') or '')[:24]!r}, "
      f"{(_rd_prev.get('recurrence') or {}).get('freq')})",
      _rh_held and 'SECOND PART' in (_rd_prev.get('body') or '')
      and (_rd_prev.get('recurrence') or {}).get('freq') == 'weekly'
      and not app.find_note(1)['recurrence'].get('freq'))
# ...and when the turn-off's save clears only the comments, the copy a big
# delete made before keeps its words: taken as the newest text, the deleted
# body was in no file.
_ro_fixture()
app.notes[0]['body'] = 'BODY GONE ' + 'packed words ' * 25
app.notes[0]['comments'] = 'ok'
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'kept line')
app.save_current_note(); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.comments_text.delete('1.0', 'end')
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_rc_prev = app.find_note(1).get('_prev') or {}
check(f"...and when it clears only the comments, the copy keeps the body a big "
      f"delete took before ({(_rc_prev.get('body') or '')[:12]!r}, "
      f"{_rc_prev.get('comments')!r}, {(_rc_prev.get('recurrence') or {}).get('freq')})",
      'BODY GONE' in (_rc_prev.get('body') or '') and _rc_prev.get('comments') == 'ok'
      and (_rc_prev.get('recurrence') or {}).get('freq') == 'weekly'
      and not app.find_note(1)['recurrence'].get('freq'))
# A turn-off after an import's Update replaced the update's copy: the note as
# it was here before the Update was in no file, and nothing said.
_ro_fixture()
_uc_note = app.find_note(1)
NO.apply_shared_update(_uc_note, dict(
    {key: _uc_note[key] for key in ('uid', 'created', 'date', 'recurrence', 'overrides')},
    title='Standup', body='FROM THE PHONE'), NO.UPDATABLE_FROM_BACKUP)
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_uc_prev = app.find_note(1).get('_prev') or {}
check(f"a turn-off after an import's Update keeps the update's copy, the series in it "
      f"({(_uc_prev.get('body') or '')[:12]!r}, {(_uc_prev.get('recurrence') or {}).get('freq')})",
      _uc_prev.get('body') == 'SERIES TEXT' and 'category' in _uc_prev
      and (_uc_prev.get('recurrence') or {}).get('freq') == 'weekly'
      and not app.find_note(1)['recurrence'].get('freq'))
# ...kept whole with its own days when it holds another series: they stay in
# it, not set aside as earlier text the turn-off then left out.
_ro_fixture()
_uc2 = app.find_note(1)
NO.apply_shared_update(_uc2, dict(
    {key: _uc2[key] for key in ('uid', 'created')}, title='Standup', body='FROM THE PHONE',
    date='2026-09-08', recurrence={'freq': 'weekly'},
    overrides={'2026-09-15': {'body': 'PHONE TUESDAY'}}), NO.UPDATABLE_FROM_BACKUP)
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_uc2_prev = app.find_note(1).get('_prev') or {}
_uc2_made = [n.get('title') for n in app.notes if n['id'] > 2]
check(f"a turn-off keeps an import's Update copy of another series whole, its days in it, nothing set "
      f"aside ({sorted(_uc2_prev.get('overrides') or {})}, {_uc2_made})",
      sorted(_uc2_prev.get('overrides') or {}) == ['2026-09-14', '2026-09-21'] and _uc2_made == []
      and _uc2_prev.get('body') == 'SERIES TEXT')
# A day reset to the series came back from the turn-off's copy at every
# start, in a duplicate and after a Trash restore: once the note
# repeats as its copy's series again, the copy's days are spent.
_ro_fixture()
app.open_note_in_tab(app.find_note(1)); app.update()
_rz_real_yes = app.ask_yes_no
app._themed_dialog = lambda *a, **k: True
app.ask_yes_no = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
    app.body_text.insert('end-1c', ' and more')
    app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
    _rz_spent = not (app.find_note(1).get('_prev') or {}).get('overrides')
    for _rz_day in ('2026-09-14', '2026-09-21'):
        app._reset_occurrence_override(app.find_note(1), _rz_day); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
    app.ask_yes_no = _rz_real_yes
_rz_disk = next((n for n in _json5e.load(open(NO.DATA_FILE, encoding='utf-8')) if n.get('id') == 1), {})
_rz_read = NO.normalize_note(_rz_disk)
check(f"a day reset after the series came back on stays reset at the next start "
      f"(copy's days spent: {_rz_spent}; days read back: {sorted(_rz_read['overrides'])})",
      _rz_spent and _rz_disk.get('overrides') == {} and _rz_read['overrides'] == {}
      and app.find_note(1)['recurrence'].get('freq') == 'weekly')
# ...and the turn-off's save that clears two letters of comments keeps a long
# comment deleted before, in the copy beside the series.
_ro_fixture()
_tc_long = ' '.join('Book room %d for the planning day' % i for i in range(10))
app.notes[0]['comments'] = _tc_long
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.comments_text.delete('1.0', 'end')
app.save_current_note(); app.update()
app.comments_text.insert('1.0', 'zz')
app.save_current_note(); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.comments_text.delete('1.0', 'end')
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_tc_prev = app.find_note(1).get('_prev') or {}
check(f"a turn-off that clears two letters of comments keeps a long comment deleted before "
      f"({(_tc_prev.get('comments') or '')[:12]!r}, {(_tc_prev.get('recurrence') or {}).get('freq')})",
      _tc_prev.get('comments') == _tc_long
      and (_tc_prev.get('recurrence') or {}).get('freq') == 'weekly')
# A big delete, the repeat off, back on as it was, off again: the second
# turn-off replaced the first one's copy, and the deleted words were in no
# file, Restore previous still offered.
_ro_fixture()
app.notes[0]['body'] = 'MEETING NOTES ' + 'agreed points ' * 25
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'short')
    app.save_current_note(); app.update()
    for _t2_freq in ('', 'weekly', ''):
        app.rec_freq_var.set(NO.FREQ_LABELS[_t2_freq])
        app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_t2_prev = app.find_note(1).get('_prev') or {}
check(f"a repeat turned off a second time keeps the words a big delete took before "
      f"({(_t2_prev.get('body') or '')[:16]!r}, {(_t2_prev.get('recurrence') or {}).get('freq')})",
      'MEETING NOTES' in (_t2_prev.get('body') or '')
      and (_t2_prev.get('recurrence') or {}).get('freq') == 'weekly'
      and not app.find_note(1)['recurrence'].get('freq'))
# ...and when it came back as another series -- another start, every two
# weeks, an end date -- the first turn-off's copy, the deleted words' only
# home, was replaced at the second (found on the phone first).
_t3_seen = []
for _t3_road in ('start', 'interval', 'end'):
    _ro_fixture()
    app.notes[0]['body'] = 'MEETING NOTES ' + 'agreed points ' * 25
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._themed_dialog = lambda *a, **k: True
    app.ask_yes_no = lambda *a, **k: True
    try:
        app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'short')
        app.save_current_note(); app.update()
        app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
        if _t3_road == 'start':
            app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '2026-09-08')
        app.rec_freq_var.set(NO.FREQ_LABELS['weekly']); app.on_recurrence_changed(); app.update()
        if _t3_road == 'interval':
            app.rec_interval_var.set('2'); app.update()
        elif _t3_road == 'end':
            app.rec_end_mode_var.set('on'); app.on_end_mode_changed()
            app.rec_end_date_var.set('01.03.2027'); app.update()
        app.save_current_note(); app.update()
        _t3_series = (app.find_note(1)['date'], dict(app.find_note(1)['recurrence']))
        app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
        _t3_prev = _json5r.loads(_json5r.dumps(app.find_note(1).get('_prev') or {}))
        app.restore_previous_version(); app.update()
        _t3_back = app.find_note(1)
    finally:
        app._themed_dialog = _ro_real_dlg
        app.ask_yes_no = _ro_yes
    _t3_seen.append((_t3_road, 'MEETING NOTES' in (_t3_prev.get('body') or ''),
                     (_t3_prev.get('date'), _t3_prev.get('recurrence')) == _t3_series,
                     'MEETING NOTES' in _t3_back['body'],
                     (_t3_back['date'], _t3_back['recurrence']) == _t3_series))
check(f"...and so when it came back as another series -- another start, every two weeks, an "
      f"end date: the copy keeps the deleted words with the series as it was last, and Restore "
      f"previous brings both back ({_t3_seen})",
      [s[1:] for s in _t3_seen] == [(True, True, True, True)] * 3
      and [s[0] for s in _t3_seen] == ['start', 'interval', 'end'])
# An import's Update, then the repeat off with the comments cleared and the
# autosave let run: the held save's copy is the update's, and the turn-off
# kept only its words -- its category and checklist in no file.
_ro_fixture()
app.notes[0]['comments'] = 'ok'
app.notes[0]['checklist'] = [{'text': 'LOCAL ITEM', 'done': False}]
_uh_note = app.find_note(1)
NO.apply_shared_update(_uh_note, dict(
    {key: _uh_note[key] for key in ('uid', 'created', 'date', 'recurrence', 'overrides')},
    title='Standup', body='FROM THE PHONE', comments='ok',
    checklist=[{'text': 'PHONE ITEM', 'done': False}]), NO.UPDATABLE_FROM_BACKUP)
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.comments_text.delete('1.0', 'end')
    app._autosave_now(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_uh_prev = app.find_note(1).get('_prev') or {}
_uh_line = app.status_lbl.cget('text')
check(f"a held turn-off after an import's Update keeps the update's copy whole "
      f"({[i.get('text') for i in _uh_prev.get('checklist') or []]}, "
      f"{(_uh_prev.get('recurrence') or {}).get('freq')})",
      [i.get('text') for i in _uh_prev.get('checklist') or []] == ['LOCAL ITEM']
      and _uh_prev.get('body') == 'SERIES TEXT'
      and (_uh_prev.get('recurrence') or {}).get('freq') == 'weekly'
      and not app.find_note(1)['recurrence'].get('freq'))
check(f"...and the status line says Restore previous brings back the note from before "
      f"the update, not the series ({_uh_line[-70:]!r})",
      'before it was updated' in _uh_line and "every day's own text" not in _uh_line)
# Turned off, on again from another start, then the start put back: the
# second save spent the copy's deleted day, which came back on the calendar
# with no way to undo it. The owner's rule: kept days come back
# onto the same date and rule -- deleted ones included.
_ro_fixture()
app.notes[0]['exceptions'] = ['2026-09-28']
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS[''])
    app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
    for _sb_date in ('2026-09-08', '2026-09-07'):
        app.date_entry.delete(0, 'end'); app.date_entry.insert(0, _sb_date)
        app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
        app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_sb_note = app.find_note(1)
check(f"a deleted day stays deleted when the series is put back on its own start after "
      f"another ({_sb_note.get('exceptions')}, "
      f"{'Standup' in [n.get('title') for n in app.notes_on_date('2026-09-28')]})",
      _sb_note.get('exceptions') == ['2026-09-28']
      and 'Standup' not in [n.get('title') for n in app.notes_on_date('2026-09-28')]
      and '2026-09-21' in (_sb_note.get('overrides') or {}))
# Turned back on from another date, an old deleted day hid the new series' own
# first day. Her answer: kept days come back only onto the same date
# and rule; a deleted day holds nothing, and the rescue copy keeps them all.
_rr_seen = []
for _rr_date in ('2026-09-07', '2026-09-14'):
    _ro_fixture()
    app.notes[0]['exceptions'] = ['2026-09-14']
    app.notes[0]['overrides'] = {'2026-09-21': {'body': 'DAY 21: decisions'}}
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._themed_dialog = lambda *a, **k: True
    try:
        app.rec_freq_var.set(NO.FREQ_LABELS[''])
        app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
        app.date_entry.delete(0, 'end'); app.date_entry.insert(0, _rr_date)
        app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
        app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
    finally:
        app._themed_dialog = _ro_real_dlg
    _rr_note = app.find_note(1)
    _rr_seen.append((_rr_note.get('exceptions'), sorted(_rr_note.get('overrides') or {}),
                     'Standup' in [n.get('title') for n in app.notes_on_date(_rr_date)]))
check(f"a series turned back on keeps its old days on the same date, and from "
      f"another its old deleted day no longer hides its first ({_rr_seen})",
      _rr_seen[0][0] == ['2026-09-14'] and _rr_seen[1][0] == []
      and all(s[1] == ['2026-09-21'] for s in _rr_seen) and _rr_seen[1][2])
# Off, a line added, on again as it was, off again: the second turn-off's copy
# took the first one's words because they differed, and Restore previous then
# took back the added line, which the next turn-off put in no file.
# An earlier copy's words are given only when the note has LOST words to it.
_ro_fixture()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
app.ask_yes_no = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
    app.body_text.insert('end-1c', '\nAdded later: bring water')
    app.save_current_note(); app.update()
    for _al_freq in ('weekly', ''):
        app.rec_freq_var.set(NO.FREQ_LABELS[_al_freq]); app.on_recurrence_changed(); app.update()
        app.save_current_note(); app.update()
    _al_copy = (app.find_note(1).get('_prev') or {}).get('body') or ''
    _al_line = str(app.status_lbl.cget('text'))
    app.restore_previous_version(); app.update()
    _al_back = app.find_note(1)
    _al_shown = (_al_back['recurrence'].get('freq'), 'Added later' in _al_back['body'],
                 NO.effective_note(_al_back, '2026-09-14').get('body'))
    app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
    app.ask_yes_no = _ro_yes
with open(NO.DATA_FILE, encoding='utf-8') as _f:
    _al_disk = _f.read()
check(f"a repeat turned off a second time, a line added between, keeps the newest words in its "
      f"copy, and Restore previous brings the series back with them ({_al_copy[-26:]!r}, "
      f"{_al_shown}; on disk after one more turn-off: {'Added later' in _al_disk})",
      'Added later' in _al_copy and _al_shown == ('weekly', True, 'DAY TEXT: room 9')
      and 'Added later' in _al_disk and "every day's own text" in _al_line
      and '↩ Restore previous' in _al_line)
# An Update that only turned the repeat on keeps a copy that, given the series'
# days at the turn-off, equals the note and is dropped by the same save: the
# status line promised a Restore previous that was gone.
_ro_fixture()
_np_note = app.find_note(1)
_np_note.update({'recurrence': NO.normalize_recurrence({}), 'overrides': {}})
NO.apply_shared_update(_np_note, dict(
    {key: _np_note[key] for key in ('uid', 'created', 'title', 'body', 'formatting', 'date')},
    recurrence={'freq': 'weekly'}), NO.UPDATABLE_FROM_SHARED)
_np_note['overrides'] = {'2026-09-14': {'body': 'DAY TEXT: room 9'}}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_np_line = str(app.status_lbl.cget('text'))
check(f"a turn-off whose copy the same save drops promises no Restore previous "
      f"({_np_line[-62:]!r}; copy kept: {'_prev' in app.find_note(1)})",
      '_prev' not in app.find_note(1) and 'Restore previous' not in _np_line
      and 'the repeat is off' in _np_line
      and not app._is_placed(app.restore_prev_btn))
# 0.97.405 (or the phone's 0.12.0) turned the repeat off and on as it was, the
# day's own text in the copy alone; then that day moved, or only coloured. The
# first start of this build spent the text: read, the day shows it.
_tb_copy = {'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-09-07',
            'recurrence': {'freq': 'weekly'},
            'overrides': {'2026-09-14': {'body': 'DAY 14 OWN TEXT, room 4B'}}}
_tb_seen = []
for _tb_days, _tb_day in (({'moved': {'2026-09-14': '2026-09-15'}}, '2026-09-15'),
                          ({'overrides': {'2026-09-14': {'title': 'Standup', 'body': 'SERIES TEXT',
                                                         'color': '#ff6b6b'}}}, '2026-09-14')):
    app.new_note(); app.update()
    app.notes = [NO.normalize_note(dict({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT',
                                         'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                                         '_prev': dict(_tb_copy)}, **_tb_days)),
                 NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1), occurrence_date=_tb_day); app.update()
    _tb_seen.append((app.body_text.get('1.0', 'end-1c'), app.current_note_color))
    app.open_note_in_tab(app.find_note(2)); app.update()
with open(NO.DATA_FILE, encoding='utf-8') as _f:
    _tb_disk = _f.read()
check(f"a day the old version moved or only coloured, its own text in the copy alone, shows "
      f"that text where it is drawn, its colour kept ({_tb_seen})",
      _tb_seen == [('DAY 14 OWN TEXT, room 4B', ''), ('DAY 14 OWN TEXT, room 4B', '#ff6b6b')]
      and 'DAY 14 OWN TEXT' in _tb_disk)
# ...and a day holding words of its own keeps them as they are: the copy's
# for it become a note of their own on that date, said on a banner of its
# own, made once (added to the day, four earlier fixes read them four ways).
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT',
                                'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                                'overrides': {'2026-09-14': {'body': 'Moved to room 2'}},
                                '_prev': dict(_tb_copy)}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
_sa_line = str(app.toast_lbl.cget('text'))
app.save_notes()
_sa_made = [(n.get('title'), n.get('body'), n.get('date')) for n in app.notes if n['id'] > 2]
with open(NO.DATA_FILE, encoding='utf-8') as _f:
    _sa_disk = _json5g.load(_f)
check(f"a day with words of its own keeps them, and the copy's words for it become one note of "
      f"their own on that date ({_sa_made}; {_sa_line!r})",
      _sa_made == [('Standup (earlier text)', 'DAY 14 OWN TEXT, room 4B', '2026-09-14')]
      and all(n.get('created') and n.get('updated') for n in app.notes if n['id'] > 2)
      and NO.effective_note(app.find_note(1), '2026-09-14').get('body') == 'Moved to room 2'
      and 'Standup (earlier text)' in [n.get('title') for n in app.notes_on_date('2026-09-14')]
      and 'kept as notes of their own' in _sa_line
      and not any('_set_aside' in n for n in _sa_disk)
      and len(_sa_disk) == 3)
# ...and several at once, from two notes: each its own number, counted on
# from the notebook's highest, worked out once -- asked again for each, the
# whole notebook was walked for every note made (found by a security review).
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'S', 'date': '2026-09-07',
                                'recurrence': {'freq': 'weekly'},
                                '_set_aside': [{'day': '2026-09-14', 'body': 'A'},
                                               {'day': '2026-09-21', 'body': 'B'}]}),
             NO.normalize_note({'id': 7, 'title': 'Gym', 'body': 'G', 'date': '2026-09-08',
                                'recurrence': {'freq': 'weekly'},
                                '_set_aside': [{'day': '2026-09-15', 'body': 'C'}]})]
app.save_notes()
_sm_made = sorted((n['id'], n.get('body')) for n in app.notes if n['id'] not in (1, 7))
check(f"days set aside on two notes become notes numbered on from the highest, one number each "
      f"({_sm_made})",
      _sm_made == [(8, 'A'), (9, 'B'), (10, 'C')])
# ...and a copy of another series than the note repeats as now, replaced by
# the next turn-off: its days with words were in it alone, and the new copy
# put them in no file. Made notes of their own first.
_ob_seen = []
for _ob_view in (None,):    # the series' view: on a day, a turn-off is put back
    _ro_fixture()
    app.notes = [NO.normalize_note(dict(app.find_note(1), _prev={
                     'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-09-08',
                     'recurrence': {'freq': 'weekly'},
                     'overrides': {'2026-09-15': {'body': 'TUESDAY 15 OWN TEXT'}}})),
                 app.find_note(2)]
    app.save_notes()
    _ob_waits = (app.find_note(1).get('_prev') or {}).get('overrides')
    _ro_off(_ob_view)
    with open(NO.DATA_FILE, encoding='utf-8') as _f:
        _ob_disk = _f.read()
    _ob_seen.append((_ob_view, _ob_waits == {'2026-09-15': {'body': 'TUESDAY 15 OWN TEXT'}},
                     [(n.get('title'), n.get('body'), n.get('date')) for n in app.notes if n['id'] > 2],
                     'TUESDAY' in _json5g.dumps(app.find_note(1).get('_prev')),
                     _ob_disk.count('TUESDAY 15 OWN TEXT')))
check(f"a turn-off over another series' copy makes that copy's days with words notes of their "
      f"own first ({_ob_seen})",
      [seen[1:] for seen in _ob_seen] == [
          (True, [('Standup (earlier text)', 'TUESDAY 15 OWN TEXT', '2026-09-15')], False, 1)])
# ...said after the turn-off's own line, not over it: its Restore previous
# promise was lost. The line read as the Save left it.
_ro_fixture()
app.notes = [NO.normalize_note(dict(app.find_note(1), _prev={
                 'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-09-08',
                 'recurrence': {'freq': 'weekly'},
                 'overrides': {'2026-09-15': {'body': 'TUESDAY 15 OWN TEXT'}}})),
             app.find_note(2)]
app.save_notes()
_ob_line = _ro_off(None, save_first=True)[1][3]
_ob_toast = str(app.toast_lbl.cget('text'))
app._run_toast_action(); app.update()
_ob_shown = (app.find_note(app.selected_note_id) or {}).get('title')
check(f"the notes made are said on a banner of their own that opens them, the turn-off's own line "
      f"kept ({_ob_line!r}; {_ob_toast!r}; {_ob_shown!r})",
      'the repeat is off' in _ob_line and 'kept as notes of their own' not in _ob_line
      and 'kept as notes of their own' in _ob_toast and _ob_shown == 'Standup (earlier text)')
# ...Ctrl+Z, which takes a banner's Undo, never takes its Show; and Show from
# Settings -- after a backup's Update there -- opens the note where the
# editor is seen, found by its identity.
_sh_seen = []
app._show_toast("Earlier text of 1 day of a repeating note kept as notes of their own", kind="info",
                action=lambda: _sh_seen.append('show'), action_text="Show")


class _ShKey:
    widget = app


_sh_took = app._toast_undo_key(_ShKey())
app._hide_toast()
# A default, and Settings closed whatever happens: under a mutant that makes
# no such note, a bare next() stopped the suite before its footer.
_sh_note = next((n for n in app.notes if n.get('title') == 'Standup (earlier text)'), None)
_sh_in_settings = _sh_after = None
if _sh_note is not None:
    app.show_settings_page(); app.update()
    try:
        app.toggle_settings_panel('trash'); app.update()
        _sh_in_settings = getattr(app, '_settings_open', None)
        app._show_set_aside(_sh_note['id'], _sh_note.get('uid')); app.update()
        _sh_after = getattr(app, '_settings_open', None)
    finally:
        if getattr(app, '_settings_open', False):
            app.hide_settings_page(); app.update()
check(f"Ctrl+Z leaves a banner's Show alone, and Show from Settings opens the note in sight "
      f"({_sh_took}, {_sh_seen}, {_sh_in_settings} -> {_sh_after}, {app.selected_note_id})",
      _sh_took is None and _sh_seen == [] and _sh_in_settings is True and not _sh_after
      and _sh_note is not None and app.selected_note_id == _sh_note['id'])
# ...and a big delete over such a copy sets its days aside first too: no
# check reached that road.
_ro_fixture()
app.notes = [NO.normalize_note(dict(app.find_note(1), body='SERIES TEXT, the long agenda. ' * 6, _prev={
                 'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-09-08',
                 'recurrence': {'freq': 'weekly'},
                 'overrides': {'2026-09-15': {'body': 'TUESDAY 15 OWN TEXT'}}})),
             app.find_note(2)]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.body_text.delete('1.0', 'end'); app.body_text.insert('1.0', 'x')
app.save_current_note(); app.update()
_bd_made = [(n.get('title'), n.get('body'), n.get('date')) for n in app.notes if n['id'] > 2]
check(f"a big delete over another series' copy makes that copy's days with words notes of their own "
      f"first ({_bd_made})",
      _bd_made == [('Standup (earlier text)', 'TUESDAY 15 OWN TEXT', '2026-09-15')]
      and 'TUESDAY' not in _json5g.dumps(app.find_note(1).get('_prev')))
# A day moved onto a Tuesday, the repeat then made daily: the Tuesday is the
# rule's own day, and the moved day was drawn nowhere until the next start.
# The save drops the move; its words stay where they showed (the
# owner's choice: words never move on their own).
_ro_fixture()
_mh = app.find_note(1)
_mh['moved'] = {'2026-09-14': '2026-09-15'}
_mh['overrides']['2026-09-15'] = _mh['overrides'].pop('2026-09-14')
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['daily']); app.on_recurrence_changed(); app.update()
app._themed_dialog = lambda *a, **k: True
try:
    app.save_current_note(); app.update()
finally:
    app._themed_dialog = _ro_real_dlg
_mh = app.find_note(1)
_mh_seen = (_mh.get('moved'), NO.effective_note(_mh, '2026-09-14').get('body'),
            NO.effective_note(_mh, '2026-09-15').get('body').rstrip('\n'))
check(f"a day moved onto a date the new rule gives loses its move at the save, its words where they "
      f"showed ({_mh_seen})",
      _mh['recurrence']['freq'] == 'daily'
      and _mh_seen == ({}, 'SERIES TEXT', 'DAY TEXT: room 9'))
# The Undo of a deleted moved day drops a dead move onto its date
# (its own date no longer the rule's), as Move this day does: put back beside
# it, the date held two moves, listed twice, and the phone's History threw.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-11-02',
                                'recurrence': {'freq': 'weekly'}, 'exceptions': ['2026-11-16'],
                                'moved': {'2026-11-18': '2026-11-20'}}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app._undo_occurrence_delete(1, '2026-11-20', None, None, '2026-11-16'); app.update()
check(f"the Undo of a deleted moved day drops a dead move onto its date ({app.find_note(1).get('moved')})",
      app.find_note(1).get('moved') == {'2026-11-16': '2026-11-20'}
      and '2026-11-16' not in app.find_note(1).get('exceptions'))
# ...never a live one: within its seconds a Restore previous brought back a
# version with another day moved onto that date, and the Undo dropped that
# move as dead, its words read as this day's.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-11-02',
                                'recurrence': {'freq': 'weekly'}, 'moved': {'2026-11-23': '2026-11-20'},
                                'overrides': {'2026-11-20': {'body': "the 23rd's words"}}}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app._undo_occurrence_delete(1, '2026-11-20', {'body': 'deleted words'}, None, '2026-11-16'); app.update()
_ul = app.find_note(1)
check(f"...but keeps a live move onto that date, and the day stays away ({_ul.get('moved')}, "
      f"{_ul.get('overrides')})",
      _ul.get('moved') == {'2026-11-23': '2026-11-20'}
      and (_ul.get('overrides') or {}).get('2026-11-20', {}).get('body') == "the 23rd's words")
# Reset "The date and the text" of a moved day drops a dead move onto its home
# date too, as Move this day does: left, the date held two moves.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'SERIES TEXT', 'date': '2026-11-02',
                                'recurrence': {'freq': 'weekly'},
                                'moved': {'2026-11-09': '2026-11-11', '2026-11-10': '2026-11-09'},
                                'overrides': {'2026-11-11': {'body': 'moved words'}}}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
_rs_dialog = app._themed_dialog
app._themed_dialog = lambda *a, **k: 'text'
try:
    app._reset_occurrence_override(app.find_note(1), '2026-11-11'); app.update()
finally:
    app._themed_dialog = _rs_dialog
_rs = app.find_note(1)
check(f"Reset of a moved day's date and text drops a dead move onto its home date ({_rs.get('moved')})",
      _rs.get('moved') == {} and '2026-11-11' not in (_rs.get('overrides') or {}))
# ...and an older rule Restore previous brings back drops a move made since
# onto its days at once: a share code made the daily series weekly, a day was
# moved; left till the next start, a delete on the shared date took the hidden
# day and its Undo was refused.
app.new_note(); app.update()
_rp = NO.normalize_note({'id': 1, 'uid': 'rp', 'title': 'Standup', 'body': 'SERIES TEXT',
                         'date': '2026-11-02', 'recurrence': {'freq': 'daily'}})
NO.apply_shared_update(_rp, {'uid': 'rp', 'title': 'Standup', 'body': 'SERIES TEXT',
                             'date': '2026-11-02', 'recurrence': {'freq': 'weekly'}})
_rp['moved'] = {'2026-11-09': '2026-11-11'}
_rp['overrides'] = {'2026-11-11': {'body': 'MOVED DAY WORDS'}}
app.notes = [_rp, NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
_ro_restored()
_rp = app.find_note(1)
_rp_seen = (_rp['recurrence']['freq'], _rp.get('moved'), NO.effective_note(_rp, '2026-11-11').get('body'))
check(f"Restore previous bringing an older rule back drops a move made since onto its days at once "
      f"({_rp_seen})",
      _rp_seen == ('daily', {}, 'MOVED DAY WORDS'))

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
# series no longer had. A day shows neither as a field to change now; what
# reaches them anyway stays as it was, the status line says so, and the
# editor shows them again.
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
check(f'...asking nothing, the status line says so, and the editor shows the '
      f'series\' date again ({_mv_said}; date field {app.date_entry.get()!r}; '
      f'status {app.status_lbl.cget("text")!r})',
      _mv_said == [] and app.date_entry.get() == '07.09.2026'
      and "stay the whole series'" in str(app.status_lbl.cget('text')))
# The repeat turned off on a day, and a date typed the app cannot read: both
# are the series', and a day puts both back on its way out, asking nothing.
# (When a day could end the series, the save filled the editor from the note
# it left and wrote the stored date over the typed one; then leaving asked,
# and Go back kept the typed date.)
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
app.date_entry.insert(0, '31/09/2026')
_lr_asked = []
app._themed_dialog = lambda *a, **k: (_lr_asked.append(a[0]), False)[1]
_lr_left = app.open_note_in_tab(app.find_note(2)); app.update()
app._themed_dialog = _mv_real_dlg
check(f'a repeat turned off and a date the app cannot read, on a day, are put '
      f'back on the way out, asking nothing (asked {_lr_asked}; left: {_lr_left}; '
      f'series {app.find_note(1)["date"]}, {app.find_note(1)["recurrence"]["freq"]})',
      _lr_asked == [] and _lr_left is True and app.selected_note_id == 2
      and app.find_note(1)['date'] == '2026-09-07'
      and app.find_note(1)['recurrence']['freq'] == 'weekly')
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
    app.date_entry.insert(0, '31/09/2026')


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
check(f'a day saved with the repeat off and a date the app cannot read keeps '
      f'the series, asks nothing -- no warning that something was not saved '
      f'-- and shows the series\' date and repeat again (asked '
      f'{[q[0] for q in _lo_asked]}; saved {_lo_saved}; shown '
      f'{_lo_shown}; status {_lo_said!r})',
      _lo_asked == []
      and _lo_saved == ('2026-09-07', 'weekly', True, True)
      and _lo_shown == ('07.09.2026', NO.FREQ_LABELS['weekly'])
      and "stay the whole series'" in _lo_said and 'except' not in _lo_said)
check(f'...and leaving afterwards asks nothing and moves nothing (asked '
      f'{_lo_leave}; {_lo_series()})',
      _lo_leave == [] and _lo_series() == ('2026-09-07', 'weekly', True, True))


def _lo_bad_date_only():
    app.date_entry.delete(0, 'end')
    app.date_entry.insert(0, '32/09/2026')


_lo_asked = _lo_day(_lo_bad_date_only)
check(f'...also when the only change to the schedule is a date the app cannot '
      f'read: the date stays the series\', asking nothing, and the field '
      f'shows it again (asked {_lo_asked}; field {app.date_entry.get()!r})',
      _lo_asked == []
      and app.date_entry.get() == '07.09.2026'
      and _lo_series() == ('2026-09-07', 'weekly', True, True))

# A day's save that puts the series' date and repeat back: writing the
# repeat's fields again asks for an autosave through their traces, and one
# left waiting saved again half a second later, over the save's own words.
# (It was found when a day could end its series: the reload after it dropped
# the words saying where the days went.)
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Standup', 'body': 'series',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14'); app.update()
_lo_repeat_off_and_bad_date()
# Recorded and answered safely through the pause as well: no question is the
# promise, and a broken save asks from the timer too.
_lo_q = []
app._themed_dialog = lambda title, *a, **k: (_lo_q.append(title), None)[1]
try:
    app.save_current_note()
    _lo_said = str(app.status_lbl.cget('text'))
    _lo_waiting = _qa_waiting(app, '_autosave_now')
    app.update(); import time as _t5lo; _t5lo.sleep(0.7); app.update()
finally:
    app._themed_dialog = _mv_real_dlg
check(f'a day saved with its repeat off and a date the app cannot read keeps '
      f'its words in the status line: no autosave is left to say otherwise '
      f'(waiting {_lo_waiting}; then {_lo_said!r}; after a pause '
      f'{app.status_lbl.cget("text")!r}; asked {_lo_q})',
      not _lo_waiting and "stay the whole series'" in _lo_said
      and 'except' not in _lo_said and _lo_q == []
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
app.date_entry.insert(0, '31/09/2026')
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
app.date_entry.insert(0, '31/09/2026')
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
      and app.date_entry.get() == '31/09/2026')
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
app.rec_end_date_var.set('32/12/2027'); app.update()
_rn_said = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'the repeat\'s summary keeps the end date the save keeps, and names '
      f'the one it does not understand ({_rn_said!r})',
      _rn_said.startswith('Every 2 weeks, until 31.12.2026')
      and 'the end date “32/12/2027”' in _rn_said)
# ...and a start date it cannot read is named: "needs a start date" said the
# series had none, while the save keeps the one it starts on.
_rn_series(interval=2)
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')
app.update_recurrence_summary(); app.update()
_rn_said = str(app.rec_summary_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'...and names a start date it does not understand, instead of saying '
      f'the series needs one ({_rn_said!r})',
      'the date “31/09/2026”' in _rn_said
      and 'needs a start date' not in _rn_said)
# The warning wraps inside what its row leaves it instead of running past
# the row's end, where a long one was cut off. In a window narrow enough
# that it has to: the premise is asserted (more than one line), or a wide
# window would let the check pass with no wrapping at all.
_rn_geom = app.geometry()
app.geometry('1000x760'); app.update()
_rn_series(freq='monthly', month_days=[15], end='2026-12-31')
app.rec_end_date_var.set('32/12/2027')
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
app.rec_end_date_var.set('32/12/2027'); app.update()
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
      _rn_box == '32/12/2027' and bool(_rn_left)
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
# Not only what a save leaves out: a readable "Every 3" reaching a day's
# hidden repeat is the series', never the day's, and neither route keeps it.
# Reset this day discards it, as its question says the day's own edits go;
# Restore previous saves the day first, which puts the series' repeat back.
# (When a day did not save itself, the 3 stayed through Restore previous to
# be saved -- and a start date typed there moved the whole series on
# leaving, without a question.)
_rn_kept_ok = []
# Each route's own question is answered Yes; any other is recorded and
# answered safely -- the day's save asks none.
_rn_kept_q = []
_rn_kept_dialog = app._themed_dialog
for _rn_route in ('reset', 'restore'):
    _rr_day()
    app.rec_interval_var.set('3'); app.update()
    app.ask_yes_no = lambda *a, **k: True
    app._themed_dialog = lambda title, *a, **k: (_rn_kept_q.append(title), None)[1]
    try:
        if _rn_route == 'reset':
            app._reset_occurrence_override(app.find_note(1), '2026-09-14')
        else:
            app.restore_previous_version()
        app.update()
    finally:
        app.ask_yes_no = _ro_yes
        app._themed_dialog = _rn_kept_dialog
    _rn_kept_ok.append((_rn_route, app.rec_interval_var.get(),
                        app._date_and_repeat_to_store()[1].get('interval')))
    app._put_back_stored_date_and_repeat()
    app._cancel_pending_autosave()
check(f'...and a readable repeat change reaching a day survives neither Reset '
      f'this day nor Restore previous: the series keeps its own ({_rn_kept_ok}; '
      f'asked {_rn_kept_q})',
      _rn_kept_q == []
      and _rn_kept_ok == [('reset', '1', 1), ('restore', '1', 1)]
      and app.find_note(1)['recurrence']['interval'] == 1)
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
      _rn_reset_date == '07.09.2026')
# ...typed day first too. What a reload carries is judged by the day a date
# names: compared as text, "23.09.2026" differs from the 2026-09-23 a save
# would store, was carried over the reset as if it could not be stored, and
# leaving then moved the whole series to it.
_rr_day()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '23.09.2026')
app.ask_yes_no = lambda *a, **k: True
try:
    app._reset_occurrence_override(app.find_note(1), '2026-09-14')
    app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_reset_date = app.date_entry.get()
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f'...and so is one typed day first ({_rn_reset_date!r})',
      _rn_reset_date == '07.09.2026')
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
app.date_entry.insert(0, '31/09/2026')
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
      'still starts 07.09.2026' in _rn_said_cleared
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


_rn_focus = _rn_date_key('31/09/2026', '6')
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
      _rn_focus and 'the date “31/09/2026”' in _rn_said_bad
      and _rn_said_typed == 'Every week'
      and 'still starts 07.09.2026' in _rn_said_clear)
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
app.date_entry.insert(0, '31/09/2026')
app.save_current_note(auto=True); app.update()
_rn_said_before = str(app.status_lbl.cget('text'))
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
_rn_said_after = str(app.status_lbl.cget('text'))
check(f'putting the stored date back puts the status line right at once '
      f'({_rn_said_before!r} -> {_rn_said_after!r})',
      'except the date' in _rn_said_before and 'except' not in _rn_said_after)
# ...and a day of a series never leaves its date out at all: the date is the
# series', a day puts it back, and its save says so in its own words. (Saved
# to the series from a day, it once left the date out, and a put-right wrote
# that earlier save's words over the day's own; a day no longer saves to the
# series.)
_rr_day()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')
# Every question and warning recorded and answered safely: none is the
# promise (a warning is a question with one answer, asked the same way).
_rn_dialog_real = app._themed_dialog
_rn_warned = []
app._themed_dialog = lambda title, *a, **k: (_rn_warned.append(title), None)[1]
try:
    app.save_current_note(); app.update()
    _rn_first = str(app.status_lbl.cget('text'))
    _rn_first_field = app._typed_date()
    app.body_text.insert('end', ' more')
    app.save_current_note(); app.update()
    _rn_second = str(app.status_lbl.cget('text'))
finally:
    app._themed_dialog = _rn_dialog_real
app._cancel_pending_autosave()
check(f'a date the app cannot read, typed on a day, is put back rather than left '
      f'out, and each save of the day says so in its own words, asking nothing '
      f'({_rn_first!r}; {_rn_first_field!r} -> {_rn_second!r}; {_rn_warned})',
      'except' not in _rn_first and '14.09.2026 only' in _rn_first
      and "stay the whole series'" in _rn_first
      and _rn_first_field == '07.09.2026' and _rn_warned == []
      and _rn_second == 'Saved 14.09.2026 only'
      and app.find_note(1)['date'] == '2026-09-07')

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

# "Does not repeat" picked from the repeat's dropdown asked for no save: the
# summary asks for one when there is a repeat to describe, and there is none
# to describe then.
_rn_series(interval=2)
app._cancel_pending_autosave()


def _rn_walk(w):
    yield w
    for _c in w.winfo_children():
        yield from _rn_walk(_c)


_qa_click(app.rec_freq_menu); app.update()
_rn_rows = ([w for w in _rn_walk(app._mini_popup)
             if isinstance(w, tk.Label)
             and str(w.cget('text')) == NO.FREQ_LABELS['']]
            if app._mini_popup is not None else [])
if _rn_rows:
    _qa_click(_rn_rows[0]); app.update()
_rn_off_freq = app.selected_freq_key()
_rn_off_waiting = _qa_waiting(app, '_autosave_now')
app._cancel_pending_autosave()
check(f'a repeat turned off from its dropdown saves itself like any edit '
      f'({len(_rn_rows)} row; freq {_rn_off_freq!r}; waiting '
      f'{_rn_off_waiting})',
      _rn_rows and _rn_off_freq == '' and bool(_rn_off_waiting))
# ...but not by a timer, on a series whose days hold edits of their own: its
# save moves them all into the rescue copy, and "Does not repeat" picked by
# mistake, put right a second later, brought the series back without them.
# Leaving the note commits it, with the rescue copy, as before.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}},
                       'exceptions': ['2026-09-28']}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()


def _rn_pick(label):
    _qa_click(app.rec_freq_menu); app.update()
    rows = ([w for w in _rn_walk(app._mini_popup)
             if isinstance(w, tk.Label) and str(w.cget('text')) == label]
            if app._mini_popup is not None else [])
    if rows:
        _qa_click(rows[0]); app.update()
    return bool(rows)


def _rn_days():
    n = app.find_note(1)
    if n is None:
        # A note deleted on the way is an answer too, not the end of the
        # suite.
        return ('note gone', [], [])
    return ((n.get('recurrence') or {}).get('freq'),
            sorted(n.get('overrides') or {}), list(n.get('exceptions') or []))


_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app._autosave_now(); app.update()
_rn_waits = str(app.status_lbl.cget('text'))
_rn_mid = _rn_days()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app._autosave_now(); app.update()
_rn_after = _rn_days()
_rn_back_said = str(app.status_lbl.cget('text'))
_rn_ok = _rn_pick(NO.FREQ_LABELS['']) and _rn_ok
app._flush_autosave(); app.update()
_rn_left = _rn_days()
_rn_rescue = sorted((app.find_note(1).get('_prev') or {}).get('overrides') or {})
# The save's own words stay.
app._autosave_now(); app.update()
_rn_left_said = str(app.status_lbl.cget('text'))
app._cancel_pending_autosave()
# A series whose only day of its own is a removed one waits too: turned off,
# the removed day came back on the calendar once the repeat was picked
# again.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'exceptions': ['2026-09-28']}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
_rn_ok = _rn_pick(NO.FREQ_LABELS['']) and _rn_ok
app._autosave_now(); app.update()
_rn_removed = _rn_days()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app._autosave_now(); app.update()
_rn_removed_after = _rn_days()
app._cancel_pending_autosave()
check(f'"Does not repeat" put right before leaving keeps a series\' own days, '
      f'and leaving commits it with its rescue copy ({_rn_mid}; {_rn_after}; '
      f'{_rn_left}; rescue {_rn_rescue}; {_rn_waits!r}; {_rn_left_said!r}; '
      f'{_rn_removed}; {_rn_removed_after})',
      _rn_ok and 'except turning the repeat off' in _rn_waits
      and 'turning the repeat off' not in _rn_back_said
      and _rn_mid == _rn_after == ('weekly', ['2026-09-14'], ['2026-09-28'])
      and _rn_left[0] == '' and _rn_rescue == ['2026-09-14']
      and 'the repeat is off' in _rn_left_said
      and _rn_removed == _rn_removed_after == ('weekly', [], ['2026-09-28']))
# Held back is the turn-off alone, as a value left out is: everything else
# is still saved while it waits. The whole autosave had stopped -- a crash
# lost every word typed meanwhile, Restore previous saved nothing first and
# put an older copy over the newest text, and a route saving on its way to
# something else (deleting another note, one day of this one on the
# Calendar) made the turn-off unasked.
_rn_held = {}
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly',
                       'body': 'NEWEST SERIES TEXT, long enough that wiping '
                               'it is a big change for the rescue copy',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'}),
    NO.normalize_note({'id': 3, 'title': 'Third', 'body': 'z'})]
app.notes[0]['_prev'] = {'title': 'Weekly', 'body': 'OLD TEXT FROM LAST MONTH',
                         'formatting': [], 'paragraphs': [], 'comments': ''}
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.body_text.insert('end', ' typed while waiting')
app._autosave_now(); app.update()
_rn_held['typed'] = ('typed while waiting'
                     in (app.find_note(1) or {}).get('body', ''),
                     _rn_days()[:2])
app.ask_yes_no = lambda *a, **k: True
try:
    app._context_delete_note(app.find_note(3)); app.update()
    _rn_held['other deleted'] = (app.find_note(3) is None, _rn_days()[:2])
    app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
    try:
        app._context_delete_note(app.find_note(1),
                                 occurrence_date='2026-09-21')
        app.update()
    finally:
        app.ask_occurrence_scope = _oc_real_scope
    _rn_held['day deleted'] = _rn_days()
    app.body_text.delete('1.0', 'end')
    app.body_text.insert('1.0', 'x')
    app._autosave_job = app.after(60000, app._autosave_now)
    if app.find_note(1) is not None:
        app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
app._cancel_pending_autosave()
_rn_held['restored'] = ((app.find_note(1) or {}).get('body', '')[:18],
                        _rn_days()[:2])
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
_rn_weekly = ('weekly', ['2026-09-14'])
check(f'a turn-off waiting holds back only itself: typing is saved, routes '
      f'that save on their way leave the series be, and Restore previous '
      f'gives back the newest text ({_rn_held})',
      _rn_ok and _rn_held.get('typed') == (True, _rn_weekly)
      and _rn_held.get('other deleted') == (True, _rn_weekly)
      and _rn_held.get('day deleted') == ('weekly', ['2026-09-14'],
                                          ['2026-09-21'])
      and _rn_held.get('restored') == ('NEWEST SERIES TEXT', _rn_weekly))
# The words a waiting turn-off gives back: a date left out beside it and then
# typed right was still named in the status line once the repeat was picked
# again -- a flag kept from an earlier save said so.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '31/09/2026')
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app._autosave_now(); app.update()
_rn_said = [str(app.status_lbl.cget('text'))]
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '2026-09-07')
app._autosave_now(); app.update()
_rn_said.append(str(app.status_lbl.cget('text')))
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app._autosave_now(); app.update()
_rn_said.append(str(app.status_lbl.cget('text')))
app._cancel_pending_autosave()
check(f'the status line names what is left out as it stands, a waiting '
      f'turn-off and a date put right included ({_rn_said})',
      _rn_ok and '31/09/2026' in _rn_said[0]
      and 'turning the repeat off' in _rn_said[0]
      and '31/09/2026' not in _rn_said[1]
      and 'turning the repeat off' in _rn_said[1]
      and 'except' not in _rn_said[2])


# What waits with a turn-off, and what a delete or an Undo makes of it.
def _rn_fresh(body='series text'):
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': body,
                           'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                           'overrides': {'2026-09-14': {'body': 'DAY 14'}},
                           'exceptions': ['2026-09-28']}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._cancel_pending_autosave()


def _rn_prev():
    return (app.find_note(1) or {}).get('_prev') or {}


_RN_SERIES = ('weekly', ['2026-09-14'], ['2026-09-28'])
# A date typed with the turn-off waits with it. Saved alone, it moved the
# series, still repeating, to the new weekday -- a day's own text on no day
# -- and the rescue copy the turn-off made later held the moved series.
_rn_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '2026-09-10')
app._autosave_now(); app.update()
_rn_dw = [((app.find_note(1) or {}).get('date'), _rn_days()[0],
           '10.09.2026' in str(app.status_lbl.cget('text')))]
app.open_note_in_tab(app.find_note(2)); app.update()
_rn_dw.append(((app.find_note(1) or {}).get('date'), _rn_days()[0],
               _rn_prev().get('date'),
               (_rn_prev().get('recurrence') or {}).get('freq')))
check(f'a date typed with a waiting turn-off waits with it, and the rescue '
      f'copy holds the series where it was ({_rn_dw})',
      _rn_ok and _rn_dw == [('2026-09-07', 'weekly', True),
                            ('2026-09-10', '', '2026-09-07', 'weekly')])
# A big delete made while the turn-off waits keeps its text when the
# turn-off is made: the turn-off's whole-note copy, taken from the note the
# held saves left, replaced the delete's, and the text was in no file.
_RN_LONG = ' '.join(['LONG SERIES TEXT'] * 20)
_rn_fresh(_RN_LONG)
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'short')
app._autosave_now(); app.update()
app.open_note_in_tab(app.find_note(2)); app.update()
_rn_bd = ((app.find_note(1) or {}).get('body'), _rn_days()[0],
          _rn_prev().get('body') == _RN_LONG,
          (_rn_prev().get('recurrence') or {}).get('freq'),
          sorted(_rn_prev().get('overrides') or {}))
check(f'a big delete made while a turn-off waits keeps its text in the '
      f'rescue copy the turn-off makes ({_rn_bd})',
      _rn_ok and _rn_bd == ('short', '', True, 'weekly', ['2026-09-14']))
# ...and outside that wait too: with the repeat picked again in between, a
# later turn-off's copy still keeps the words the delete took, which the
# note does not hold again. Taken as "the note as it stands", the deleted
# words were in no file.
_rn_fresh(_RN_LONG)
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'short')
app._autosave_now(); app.update()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app._autosave_now(); app.update()
_rn_ok = _rn_pick(NO.FREQ_LABELS['']) and _rn_ok
app.open_note_in_tab(app.find_note(2)); app.update()
_rn_bd = (_rn_prev().get('body'), (_rn_prev().get('recurrence') or {}).get('freq'))
check(f'...and outside that wait too: a turn-off made after the repeat was '
      f'picked again keeps the deleted words with the series ({_rn_bd})',
      _rn_ok and _rn_bd == (_RN_LONG, 'weekly'))
# The Undo of one day's delete leaves the series view be: it opened the day,
# which left the series and made its waiting turn-off -- the day just put
# back went with every other.
_rn_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
try:
    app._context_delete_note(app.find_note(1), occurrence_date='2026-09-21')
    app.update()
finally:
    app.ask_occurrence_scope = _oc_real_scope
_rn_un = ['2026-09-21' in ((app.find_note(1) or {}).get('exceptions') or [])]
app._undo_occurrence_delete(1, '2026-09-21', None); app.update()
_rn_un += [_rn_days(), app.selected_note_id, app.current_occurrence_date,
           app.selected_freq_key()]
check(f'the Undo of a day deleted while a turn-off waits puts the day back '
      f'and leaves the turn-off waiting ({_rn_un})',
      _rn_ok and _rn_un == [True, _RN_SERIES, 1, None, ''])
# A delete saves the editor before its question, and that save made a
# waiting turn-off: the day on screen, deleted after "Does not repeat" was
# picked on it, then asked to delete the whole note, and Yes trashed it; a
# Delete or Move to trash answered No kept a turn-off nobody had saved.
_rn_dl = {}
_rn_fresh()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-21')
app.update()
app._cancel_pending_autosave()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
_rn_asked = []
app.ask_occurrence_scope = lambda *a, **k: (_rn_asked.append('scope'),
                                            'occurrence')[1]
app.ask_yes_no = lambda *a, **k: (_rn_asked.append('yes/no'), True)[1]
try:
    app._context_delete_note(app.find_note(1), occurrence_date='2026-09-21')
    app.update()
finally:
    app.ask_occurrence_scope = _oc_real_scope
    app.ask_yes_no = _ro_yes
_rn_dl['day on screen'] = (_rn_asked, _rn_days())
for _rn_route in ('Delete', 'Move to trash'):
    _rn_fresh()
    _rn_ok = _rn_pick(NO.FREQ_LABELS['']) and _rn_ok
    app.ask_yes_no = lambda *a, **k: False
    try:
        if _rn_route == 'Delete':
            app.delete_current_note()
        else:
            app.selected_note_ids = {1}
            app._bulk_move_to_trash()
        app.update()
    finally:
        app.ask_yes_no = _ro_yes
        app.selected_note_ids = set()
    _rn_dl['No: ' + _rn_route] = (_rn_days(), app.selected_freq_key())
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
# ...and so with Settings' deletes: the open note's category, answered
# Cancel or "move to General", and its duplicates, answered No -- or Yes
# with the note on screen the copy that is kept and gains a file, which
# fills the editor from the note again and carries the turn-off across.
_rn_fname = '20261002160000000000_hold5.txt'
_os5.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
with open(_os5.path.join(NO.ATTACHMENTS_DIR, _rn_fname), 'w') as _rn_fh:
    _rn_fh.write('h')
for _rn_route in ('category: Cancel', 'category: move', 'duplicates: No',
                  'duplicates: Yes'):
    # The category exists before the note filed under it, every time: the
    # "move" answer deletes it.
    NO.CATEGORY_COLORS['TempHold5'] = '#336699'
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                           'category': 'TempHold5', 'date': '2026-09-07',
                           'recurrence': {'freq': 'weekly'},
                           'overrides': {'2026-09-14': {'body': 'DAY 14'}},
                           'exceptions': ['2026-09-28']}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'}),
        NO.normalize_note({'id': 3, 'title': 'Weekly', 'body': 'series text',
                           'attachments': [{'name': 'h.txt',
                                            'stored_as': _rn_fname}]})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._cancel_pending_autosave()
    _rn_ok = _rn_pick(NO.FREQ_LABELS['']) and _rn_ok
    _rn_dups = [(_NlVar(False), app.find_note(1),
                 [app.find_note(1), app.find_note(3)]),
                (_NlVar(True), app.find_note(3),
                 [app.find_note(1), app.find_note(3)])]
    app._ask_category_deletion = (
        lambda *a, **k: None if _rn_route == 'category: Cancel' else 'move')
    app.ask_yes_no = lambda *a, **k: _rn_route == 'duplicates: Yes'
    try:
        if _rn_route.startswith('category'):
            app._delete_category('TempHold5', lambda: None)
        else:
            app._cleanup_selected_duplicates(_rn_dups, refresh=lambda: None)
        app.update()
    finally:
        app.__dict__.pop('_ask_category_deletion', None)
        app.ask_yes_no = _ro_yes
    _rn_dl[_rn_route] = (_rn_days(), app.selected_note_id,
                         app.selected_freq_key(),
                         len((app.find_note(1) or {}).get('attachments') or []))
    app._put_back_stored_date_and_repeat()
    app._cancel_pending_autosave()
NO.CATEGORY_COLORS.pop('TempHold5', None)
check(f'a delete asks about what is stored: a waiting turn-off is not made '
      f'before its question ({_rn_dl})',
      _rn_ok
      and _rn_dl.get('day on screen') == (
          ['scope'], ('weekly', ['2026-09-14'], ['2026-09-21', '2026-09-28']))
      and _rn_dl.get('No: Delete') == (_RN_SERIES, '')
      and _rn_dl.get('No: Move to trash') == (_RN_SERIES, '')
      and _rn_dl.get('category: Cancel') == (_RN_SERIES, 1, '', 0)
      and _rn_dl.get('category: move') == (_RN_SERIES, 1, '', 0)
      and _rn_dl.get('duplicates: No') == (_RN_SERIES, 1, '', 0)
      and _rn_dl.get('duplicates: Yes') == (_RN_SERIES, 1, '', 1))
# Deleting a category is not taken back, and with notes in it their filing
# goes too: Enter there is Cancel, as on the question asked of an empty one.
# It fired "Move them to General", the last button.
_cd_q = []
_cd_real_dlg = app._themed_dialog
app._themed_dialog = lambda title, message, *a, **k: (
    _cd_q.append([spec[0] for spec in k.get('buttons', [])][
        app._dialog_focus_index(k.get('buttons', []), k.get('default'))]), None)[1]
try:
    app._ask_category_deletion('Work', 3)
    app._ask_category_deletion('Work', 0)
finally:
    app._themed_dialog = _cd_real_dlg
check(f'deleting a category, with notes in it or none, Enter is Cancel ({_cd_q})',
      _cd_q == ['Cancel', 'Cancel'])
# The duplicates clean-up fills the editor from the kept copy again and
# carries a waiting turn-off across -- but the reload's own repeat cleared
# the record of a big delete's rescue copy, and on leaving the turn-off's
# copy replaced it: the deleted text was in no file.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': _RN_LONG,
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}},
                       'exceptions': ['2026-09-28']}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'}),
    NO.normalize_note({'id': 3, 'title': 'Weekly', 'body': 'short',
                       'attachments': [{'name': 'h.txt',
                                        'stored_as': _rn_fname}]})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'short')
app._autosave_now(); app.update()
app.ask_yes_no = lambda *a, **k: True
try:
    app._cleanup_selected_duplicates(
        [(_NlVar(False), app.find_note(1), [app.find_note(1), app.find_note(3)]),
         (_NlVar(True), app.find_note(3), [app.find_note(1), app.find_note(3)])],
        refresh=lambda: None)
    app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_ok = _rn_ok and app.selected_freq_key() == ''
app.open_note_in_tab(app.find_note(2)); app.update()
_rn_dk = (_rn_prev().get('body') == _RN_LONG,
          (_rn_prev().get('recurrence') or {}).get('freq'))
check(f'a turn-off carried across the duplicates clean-up keeps the text a '
      f'big delete rescued ({_rn_ok}; {_rn_dk})',
      _rn_ok and _rn_dk == (True, 'weekly'))
# On a delete, "Part of this note isn't saved" asked about an unreadable date
# alone and said everything else was saved -- while "Continue without it"
# also took back the "Does not repeat" the delete's save had held.
_rn_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '31/09/2026')
_rn_said = []
app._themed_dialog = lambda *a, **k: (_rn_said.append(a[1] if len(a) > 1
                                                       else ''), True)[1]
app.ask_yes_no = lambda *a, **k: False
try:
    app.delete_current_note()
    app.update()
finally:
    app._themed_dialog = _ro_real_dlg
    app.ask_yes_no = _ro_yes
app._cancel_pending_autosave()
_rn_named = bool(_rn_said) and 'turning the repeat off' in _rn_said[0]
_rn_cn = (_rn_named, '31/09/2026' in (_rn_said or [''])[0],
          app.selected_freq_key(), _rn_days())
check(f'"Continue without it" on a delete names the turn-off it takes back '
      f'({_rn_cn})',
      _rn_ok and _rn_cn == (True, True, 'weekly', _RN_SERIES))
# The Undo of a day's delete once the series it was deleted from is gone --
# its turn-off made by leaving the note within the Undo's seconds -- says
# the day can't come back, and writes nothing. Three designs that put the
# day into a rescue copy were each broken by the next round of breakers: a
# copy made for an Undo never clicked replaced an older one, an older
# series' copy took the day, a copy of the series as the delete left it
# undid what was saved since -- and its words pointed at the Restore
# previous of whatever note was open. Both notes' older copies stay.
_rn_long = 'LONG SERIES TEXT the person wrote ' * 6
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'DAY 14'}},
                       'exceptions': ['2026-09-28'],
                       '_prev': {'title': 'Weekly', 'body': _rn_long}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y',
                       '_prev': {'title': 'Other', 'body': 'OLDER OTHER'}})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
try:
    app._context_delete_note(app.find_note(1), occurrence_date='2026-09-14')
    app.update()
finally:
    app.ask_occurrence_scope = _oc_real_scope
app.open_note_in_tab(app.find_note(2)); app.update()
_rn_ok = _rn_ok and _rn_days()[0] == ''
app._run_toast_action(); app.update()
_rn_ug = (str(app.toast_lbl.cget('text')), _rn_prev().get('body') == _rn_long,
          'recurrence' in _rn_prev(), app.selected_note_id,
          app.find_note(2)['body'], app.find_note(2)['_prev']['body'])
check(f'the Undo of a day whose series was turned off since says it can\'t '
      f'come back, and changes nothing ({_rn_ug})',
      _rn_ok and "no longer repeats, so that day can't come back" in _rn_ug[0]
      and _rn_ug[1:] == (True, False, 2, 'y', 'OLDER OTHER'))


def _rn_day_fresh():
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({'id': 1, 'title': 'Weekly', 'body': 'series text',
                           'date': '2026-09-07', 'recurrence': {'freq': 'weekly'},
                           'overrides': {'2026-09-14': {'body': 'DAY 14'}},
                           'exceptions': ['2026-09-28']}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
    app.save_notes()
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._cancel_pending_autosave()


def _rn_day_delete(day='2026-09-14'):
    app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
    try:
        app._context_delete_note(app.find_note(1), occurrence_date=day)
        app.update()
    finally:
        app.ask_occurrence_scope = _oc_real_scope


def _rn_banner():
    return str(app.occurrence_banner.cget('text'))


# With the repeat turned off and picked anew before the Undo, the series has
# the day again -- without the text it had of its own, which the Undo puts
# back on it (it said "That day is already back" and dropped the text).
_rn_day_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
_rn_day_delete()
app.save_current_note(); app.update()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app.save_current_note(); app.update()
app._run_toast_action(); app.update()
app._cancel_pending_autosave()
_rn_ro = (str(app.status_lbl.cget('text')), (app.find_note(1).get('recurrence')
                                             or {}).get('freq'),
          ((app.find_note(1).get('overrides') or {}).get('2026-09-14')
           or {}).get('body'))
check(f'a repeat picked anew with the day on it gets the day\'s own text back '
      f'from its Undo ({_rn_ro})',
      _rn_ok and _rn_ro == ('Put that day back', 'weekly', 'DAY 14'))
# ...and a repeat picked anew without that day says so: "That day is already
# back" was said of a monthly series with no such day, the day on no
# calendar.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Plain', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
_rn_day_delete()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.save_current_note(); app.update()
_rn_ok = _rn_pick(NO.FREQ_LABELS['monthly']) and _rn_ok
app.save_current_note(); app.update()
app._run_toast_action(); app.update()
app._cancel_pending_autosave()
_rn_mo = (str(app.toast_lbl.cget('text')),
          (app.find_note(1).get('recurrence') or {}).get('freq'))
check(f'a repeat picked anew without the day says the day can\'t come back '
      f'({_rn_mo})',
      _rn_ok and 'no longer has that day' in _rn_mo[0]
      and _rn_mo[1] == 'monthly')
# The text of a day deleted while the turn-off waits is not left in the note
# when the wait ends without it: kept there, the deleted day read as a day
# with its own edits ("✎1" on the card, "1 day keeps its own edits").
_rn_day_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
_rn_day_delete()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app._autosave_now(); app.update()
_rn_kd = (sorted((app.find_note(1) or {}).get('overrides') or {}),
          'own edits' in _rn_banner())
app._cancel_pending_autosave()
check(f'the deleted day of a series whose turn-off was taken back keeps no '
      f'text of its own in the note ({_rn_kd})',
      _rn_ok and _rn_kd == ([], False))
# A turn-off that kept a copy for another day's text keeps it as it was
# when the deleted day's Undo is clicked after it: an older turn-off's copy
# with the same date among its skipped days took the day, and Restore
# previous brought back that older series.
_rn_day_fresh()
app.find_note(1)['overrides']['2026-09-21'] = {'body': 'DAY 21'}
app.save_notes()
_rn_day_delete()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
app.save_current_note(); app.update()
_rn_copy = _mjson.dumps(_rn_prev(), sort_keys=True)
app._run_toast_action(); app.update()
app._cancel_pending_autosave()
_rn_both = sorted((app.find_note(1).get('_prev') or {}).get('overrides') or {})
check(f'the Undo leaves the copy a turn-off kept for another day\'s text as it '
      f'was ({_rn_both})',
      _rn_ok and _mjson.dumps(_rn_prev(), sort_keys=True) == _rn_copy
      and _rn_both == ['2026-09-21'])
# The Undo knows its note by identity, not by id: the series sent to the
# Trash by a route with no toast of its own (its category deleted with its
# notes), and the freed id given to a new note, the Undo wrote the series
# into the NEW note's rescue copy.
NO.CATEGORY_COLORS['TempGym5'] = '#336699'
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Other', 'body': 'y'}),
    NO.normalize_note({'id': 2, 'title': 'Shopping', 'body': 'milk'}),
    NO.normalize_note({'id': 3, 'title': 'Gym', 'body': 'series text',
                       'category': 'TempGym5', 'date': '2026-09-07',
                       'recurrence': {'freq': 'weekly'},
                       'overrides': {'2026-09-14': {'body': 'GYM 14'}}})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
try:
    app._context_delete_note(app.find_note(3), occurrence_date='2026-09-14')
    app.update()
finally:
    app.ask_occurrence_scope = _oc_real_scope
app._ask_category_deletion = lambda *a, **k: 'delete_notes'
try:
    app._delete_category('TempGym5', lambda: None)
    app.update()
finally:
    app.__dict__.pop('_ask_category_deletion', None)
NO.CATEGORY_COLORS.pop('TempGym5', None)
app.new_note(); app.update()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Call mom')
app.body_text.insert('1.0', 'about the trip')
app._autosave_now(); app.update()
_rn_new = app.find_note(3)
app._run_toast_action(); app.update()
app._cancel_pending_autosave()
_rn_id = ((_rn_new or {}).get('title'), str(app.toast_lbl.cget('text')),
          'recurrence' in ((app.find_note(3) or {}).get('_prev') or {}))
check(f'the Undo of a day whose note went to the Trash, its id taken by a new '
      f'note, leaves the new note alone ({_rn_id})',
      _rn_id[0] == 'Call mom' and 'That note is no longer here' in _rn_id[1]
      and not _rn_id[2])
# The category move's Undo knows its notes by identity too: a note that took
# a moved note's freed id, filed in the same category, is not moved back.
NO.CATEGORY_COLORS['TempMove5'] = '#336699'
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 3, 'title': 'New', 'body': 'n',
                                'category': 'TempMove5', 'uid': 'u-new'}),
             NO.normalize_note({'id': 4, 'title': 'Moved', 'body': 'm',
                                'category': 'TempMove5', 'uid': 'u-moved'})]
app.save_notes()
app._undo_bulk_category([(3, 'General', '2026-09-01 08:00:00', 'u-gone'),
                         (4, 'General', '2026-09-01 08:00:00', 'u-moved')],
                        'TempMove5')
app.update()
_rn_cat = (app.find_note(3)['category'], app.find_note(4)['category'])
NO.CATEGORY_COLORS.pop('TempMove5', None)
check(f'the Undo of a category move puts back the notes it moved, not a note '
      f'that took one of their ids ({_rn_cat})',
      _rn_cat == ('TempMove5', 'General'))
# The Undo of the only day a waiting turn-off waited for leaves the turn-off
# waiting: read after the day went back, nothing waited, the Undo opened the
# day, and leaving the series made the turn-off -- "Put that day back", the
# series gone from the calendar.
app.new_note(); app.update()
app.notes = [
    NO.normalize_note({'id': 1, 'title': 'Plain', 'body': 'series text',
                       'date': '2026-09-07', 'recurrence': {'freq': 'weekly'}}),
    NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app._cancel_pending_autosave()
_rn_day_delete()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
# No autosave left to fire meanwhile: the turn-off waits on what the note
# holds, not on a timer.
app._cancel_pending_autosave()
app._run_toast_action(); app.update()
app._cancel_pending_autosave()
_rn_pl = ((app.find_note(1).get('recurrence') or {}).get('freq'),
          app.find_note(1).get('exceptions'), app.selected_note_id,
          app.current_occurrence_date)
check(f'the Undo of the only day a turn-off waited for does not make the '
      f'turn-off ({_rn_pl})',
      _rn_ok and _rn_pl == ('weekly', [], 1, None))
# The open series' banner counts its days' own edits as they are: a day
# deleted, put back or reset from the Calendar left the old count over the
# editor until the next save.
_rn_bn = []
_rn_day_fresh()
_rn_bn.append('1 day keeps' in _rn_banner())
_rn_day_delete()
_rn_bn.append('own edits' in _rn_banner())
_rn_day_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
_rn_day_delete()
app._undo_occurrence_delete(1, '2026-09-14', {'body': 'DAY 14'}); app.update()
_rn_bn.append('1 day keeps' in _rn_banner())
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
_rn_day_fresh()
app.ask_yes_no = lambda *a, **k: True
try:
    app._reset_occurrence_override(app.find_note(1), '2026-09-14')
    app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_bn.append('own edits' in _rn_banner())
app._cancel_pending_autosave()
check(f'an open series\' banner counts its days\' own edits after a day is '
      f'deleted, put back or reset ({_rn_bn})',
      _rn_ok and _rn_bn == [True, False, True, False])
# The series open, holding a date its save cannot store: a day's Undo asks
# about it first, and going back keeps the person on the note -- and the
# Undo with them, the day's own text kept nowhere else. Checked on a day's
# save question until day mode took that question away.
_rn_day_fresh()
_rn_day_delete()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')
app.update()
_rn_asked, _rn_dialog_was = [], app._themed_dialog
app._themed_dialog = lambda title, *a, **k: (_rn_asked.append(title), False)[1]
try:
    # Taken as a click takes it: the delete's own banner cleared first, so
    # a "Day removed" seen after is the offer made again, not the first one.
    app._run_toast_action(); app.update()
finally:
    app._themed_dialog = _rn_dialog_was
_rn_gb = (_rn_asked[:1], str(app.toast_lbl.cget('text')), app._toast_action is not None,
          '2026-09-14' in (app.find_note(1).get('exceptions') or []), app.selected_note_id)
app._put_back_stored_date_and_repeat()
app._cancel_pending_autosave()
check(f"going back on the question a day's Undo asks first keeps the Undo on offer ({_rn_gb})",
      _rn_gb[0] == ["Part of this note isn't saved"] and 'Day removed' in _rn_gb[1]
      and _rn_gb[2] and _rn_gb[3] and _rn_gb[4] == 1)
# A backup's Update wrote over a field this version does not know: Restore
# previous puts the note's own value back, as it puts back its words.
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 1, 'title': 'Mine', 'body': 'b', 'reminder': '10:00'}),
             NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'y'})]
NO.apply_shared_update(app.notes[0], {'title': 'Older', 'body': 'b', 'reminder': '09:00'},
                       NO.UPDATABLE_FROM_BACKUP)
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version(); app.update()
finally:
    app.ask_yes_no = _ro_yes
_rn_own = ((app.find_note(1) or {}).get('title'), (app.find_note(1) or {}).get('reminder'))
app._cancel_pending_autosave()
check(f"Restore previous after a backup's Update puts back a field this version does not know ({_rn_own})",
      _rn_own == ('Mine', '10:00'))
# The Undo of a day clicked with THAT day open -- a repeat picked anew has it
# again, the series' text on it -- saves the editor before it writes the
# day, and opens it without a second save. Saved after, the editor's view
# read as an edit, asked "What should Save apply to?", and every answer but
# Cancel wrote the series' text over the day's own.
_rn_day_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
_rn_day_delete()
app.save_current_note(); app.update()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app.save_current_note(); app.update()
app.open_note_in_tab(app.find_note(1), occurrence_date='2026-09-14')
app.update()
app._cancel_pending_autosave()
_rn_asked = []
app.ask_occurrence_scope = lambda *a, **k: (_rn_asked.append(a), 'occurrence')[1]
try:
    app._run_toast_action(); app.update()
finally:
    app.ask_occurrence_scope = _oc_real_scope
app._cancel_pending_autosave()
_rn_op = (_rn_asked, app.current_occurrence_date,
          app.body_text.get('1.0', 'end-1c'),
          ((app.find_note(1).get('overrides') or {}).get('2026-09-14')
           or {}).get('body'))
check(f'the Undo of a day clicked with that very day open asks nothing and '
      f'shows the day\'s own text ({_rn_op})',
      _rn_ok and _rn_op == ([], '2026-09-14', 'DAY 14', 'DAY 14'))
# Going back on the question the save asks on the way -- a date typed into
# the series that it cannot store -- means stay, and the Undo stays on offer:
# the day's own text is kept nowhere else. (A day typed into once asked a
# question of its own here, whose Cancel did the same; a day now saves to
# itself, asking nothing.)
_rn_real_dialog = app._themed_dialog
_rn_day_fresh()
_rn_ok = _rn_pick(NO.FREQ_LABELS[''])
_rn_day_delete()
app.save_current_note(); app.update()
_rn_ok = _rn_pick(NO.FREQ_LABELS['weekly']) and _rn_ok
app.save_current_note(); app.update()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')
app._cancel_pending_autosave()
app._themed_dialog = lambda *a, **k: False          # "Go back and fix it"
try:
    app._run_toast_action(); app.update()
finally:
    app._themed_dialog = _rn_real_dialog
app._cancel_pending_autosave()
_rn_stay = (app._toast_action is not None, app._typed_date(),
            sorted(app.find_note(1).get('overrides') or {}))
app._themed_dialog = lambda *a, **k: True           # "Continue without it"
try:
    app._run_toast_action(); app.update()
finally:
    app._themed_dialog = _rn_real_dialog
app._cancel_pending_autosave()
_rn_then = (app.find_note(1)['date'],
            ((app.find_note(1).get('overrides') or {}).get('2026-09-14')
             or {}).get('body'))
check(f'going back on the question a day\'s Undo asks first keeps the Undo on '
      f'offer ({_rn_stay}; then {_rn_then})',
      _rn_ok and _rn_stay == (True, '31/09/2026', [])
      and _rn_then == ('2026-09-07', 'DAY 14'))
# ...and the category move's Undo the same: where each note came from is kept
# nowhere else.
NO.CATEGORY_COLORS['TempMove5'] = '#336699'
_rn_day_fresh()
app.find_note(1)['category'] = 'TempMove5'
app.save_notes()
# Brought along, as the move itself does: left showing the old category, the
# editor's next save would put it back.
app._editor_follows_external_change({1})
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '31/09/2026')
app._cancel_pending_autosave()
_rn_mark = [(1, 'General', '2026-09-01 08:00:00', app.find_note(1).get('uid'))]
app._themed_dialog = lambda *a, **k: False          # "Go back and fix it"
try:
    app._undo_bulk_category(_rn_mark, 'TempMove5'); app.update()
finally:
    app._themed_dialog = _rn_real_dialog
_rn_cstay = (app._toast_action is not None, app.find_note(1)['category'])
app._themed_dialog = lambda *a, **k: True           # "Continue without it"
try:
    app._run_toast_action(); app.update()
finally:
    app._themed_dialog = _rn_real_dialog
app._cancel_pending_autosave()
_rn_cthen = app.find_note(1)['category']
NO.CATEGORY_COLORS.pop('TempMove5', None)
check(f'going back on the question a category move\'s Undo asks first keeps the '
      f'Undo on offer ({_rn_cstay}; then {_rn_cthen})',
      _rn_cstay == (True, 'TempMove5') and _rn_cthen == 'General')
# The calendar is asked whether the series has the day whatever the branch:
# with the rule changed since the delete, the day still among the skipped
# ones, the Undo put it back -- and opened it, its own text on it -- on a
# day no calendar showed.
_rn_day_fresh()
_rn_day_delete()
_rn_ok = _rn_pick(NO.FREQ_LABELS['monthly'])
app.save_current_note(); app.update()
app._run_toast_action(); app.update()
app._cancel_pending_autosave()
_rn_rule = (str(app.toast_lbl.cget('text')),
            sorted(app.find_note(1).get('overrides') or {}),
            app.find_note(1).get('exceptions'))
check(f'the Undo of a day whose series\' rule changed since says it can\'t '
      f'come back, and writes nothing ({_rn_rule})',
      _rn_ok and 'no longer has that day' in _rn_rule[0]
      and _rn_rule[1:] == ([], ['2026-09-14', '2026-09-28']))
# The Undo finds its note by identity, not by number: a note restored from the
# Trash comes back under a new number, and looked up by the old one the day's
# Undo said "That note is no longer here" -- the note in the list. (The
# category move's Undo found nothing to put back: below.)
_rn_day_fresh()
_rn_uid = app.find_note(1).get('uid')
app.find_note(1)['overrides'].pop('2026-09-14')
app.find_note(1)['exceptions'] = ['2026-09-14', '2026-09-28']
app.find_note(1)['id'] = 7
app.open_note_in_tab(app.find_note(2)); app.update()
app._undo_occurrence_delete(1, '2026-09-14', {'body': 'DAY 14'}, _rn_uid)
app.update()
app._cancel_pending_autosave()
_rn_back = (str(app.status_lbl.cget('text')), app.selected_note_id,
            ((app.find_note(7).get('overrides') or {}).get('2026-09-14')
             or {}).get('body'))
check(f'the Undo of a day finds its series after it came back from the Trash '
      f'under a new number ({_rn_back})',
      _rn_back == ('Put that day back', 7, 'DAY 14'))
NO.CATEGORY_COLORS['TempMove5'] = '#336699'
app.new_note(); app.update()
app.notes = [NO.normalize_note({'id': 3, 'title': 'Restored', 'body': 'r',
                                'category': 'TempMove5', 'uid': 'u-restored'})]
app.save_notes()
app._undo_bulk_category([(2, 'General', '2026-09-01 08:00:00', 'u-restored')],
                        'TempMove5')
app.update()
_rn_moved_back = app.find_note(3)['category']
NO.CATEGORY_COLORS.pop('TempMove5', None)
check(f'the Undo of a category move finds a note after it came back from the '
      f'Trash under a new number ({_rn_moved_back})',
      _rn_moved_back == 'General')
# A note saved the old way -- bold and italic as two spans over the same
# letters, another span after them -- opens as saved: the fold gave the spans
# back in an order the editor never reads them in, so the untouched note read
# as unsaved and was saved again on leaving, its "Last updated" moved.
app.new_note(); app.update()
app.notes = [NO.normalize_note({
    'id': 1, 'title': 'Old way', 'body': 'one two three four',
    'formatting': [{'start': 4, 'end': 7, 'style': 'bold'},
                   {'start': 4, 'end': 7, 'style': 'italic'},
                   {'start': 8, 'end': 13, 'style': 'underline'}],
    'updated': '2026-09-03 09:00:00'})]
app.save_notes()
app.open_note_in_tab(app.find_note(1)); app.update()
_rn_clean = app.editor_state_matches_saved(app.capture_editor_state())
app.new_note(); app.update()
check(f'a note saved with bold and italic as two spans opens as saved '
      f'(clean {_rn_clean}; updated {app.find_note(1).get("updated")})',
      _rn_clean and app.find_note(1).get('updated') == '2026-09-03 09:00:00')

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

# ---- DAYS OFF THE SCHEDULE: KEPT, AND FOUND ----
# A day saved "only this occurrence" keeps its edit under its date. Moving the
# series' start or changing its rule afterwards left that edit on a date the
# series no longer has: counted on the line above the note as a day keeping
# its edits, on no calendar. The owner's call (2026-10-12): kept, and findable.
from noteorganizer.ui import calendar_view as _os_cv
NO.CATEGORY_COLORS.setdefault('Work', '#4cc9f0')


def _os_seed():
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({
            'id': 1, 'title': 'Stand-up', 'body': 'series text', 'category': 'General',
            # Weekly, now on Tuesdays: the Monday edits are off its schedule.
            'date': '2026-09-08', 'recurrence': {'freq': 'weekly', 'weekdays': [1]},
            'formatting': [{'start': 0, 'end': 6, 'style': 'bold'}],
            'checklist': [{'text': 'agenda', 'done': False}],
            'overrides': {
                '2026-09-15': {'title': 'Stand-up (room 2)'},
                '2026-09-14': {'title': 'Stand-up 10:00', 'body': 'moved to Monday',
                               'category': 'Work'},
                '2026-09-21': {'body': 'series text', 'comments': 'kept'}}}),
        NO.normalize_note({'id': 2, 'title': 'Other', 'body': 'x'})]
    app.save_notes()
    app.trash = []
    NO.save_trash(app.trash)
    app.open_note_in_tab(app.find_note(1)); app.update()
    app._cancel_pending_autosave()


def _os_walk(answers):
    """Press the way in, answering each day's question in turn; returns the
    questions' titles and messages."""
    asked, queue = [], list(answers)
    real = app._themed_dialog
    app._themed_dialog = lambda title, message, *a, **k: (
        asked.append((title, message)), queue.pop(0) if queue else 'keep')[1]
    try:
        app.offschedule_btn.invoke(); app.update()
    finally:
        app._themed_dialog = real
    return asked


_os_seed()
_os_btn = app.offschedule_btn
check(f'the line above a series counts only the days still on its schedule ({_rn_banner()!r})',
      _rn_banner().endswith(' · 1 day keeps its own edits (✎)'))
check(f'...and gives the 2 days off it a way in of their own ({_os_btn.cget("text")!r})',
      bool(_os_btn.winfo_ismapped())
      and str(_os_btn.cget('text')).startswith("✎ 2 days' own edits are off the schedule"))

_os_asked = _os_walk(['note', 'trash'])
check(f'the way in asks about each day in turn ({[t for t, _ in _os_asked]})',
      [t for t, _ in _os_asked] == ['Day 1 of 2 off the schedule', 'Day 2 of 2 off the schedule'])
check('...naming the day, its title and its own text',
      'Monday, 14 September 2026' in _os_asked[0][1]
      and '“Stand-up 10:00”' in _os_asked[0][1]
      and 'moved to Monday' in _os_asked[0][1])
_os_new = next((n for n in app.notes if n.get('title') == 'Stand-up 10:00'), None)
check("a day made a note of its own holds that day's title, text, category and date",
      _os_new is not None and _os_new.get('date') == '2026-09-14'
      and _os_new.get('body') == 'moved to Monday' and _os_new.get('category') == 'Work'
      and not (_os_new.get('recurrence') or {}).get('freq'))
check("...without the series' formatting, which belongs to other text, nor its checklist",
      _os_new is not None and _os_new.get('formatting') == []
      and _os_new.get('checklist') == [] and _os_new.get('uid') != app.find_note(1).get('uid'))
_os_tr = next((e for e in app.trash if e.get('date') == '2026-09-21'), None)
check("a day moved to the Trash goes as a note, with the series' formatting where its text is the series' own",
      _os_tr is not None and _os_tr.get('title') == 'Stand-up'
      and _os_tr.get('comments') == 'kept'
      and _os_tr.get('formatting') == [{'start': 0, 'end': 6, 'style': 'bold'}])
_os_s = app.find_note(1)
check('the series keeps the day still on its schedule, and its checklist',
      sorted(_os_s.get('overrides') or {}) == ['2026-09-15']
      and [i['text'] for i in _os_s.get('checklist') or []] == ['agenda'])
check('...and the way in is gone with the days',
      not _os_btn.winfo_ismapped()
      and _rn_banner().endswith(' · 1 day keeps its own edits (✎)'))
app.cal_year, app.cal_month = 2026, 9
app.render_calendar(); app.update()
check('the new note is on the calendar, on its day',
      _os_new is not None
      and _os_new['id'] in [n.get('id') for n in _os_cv._notes_on_day(app, '2026-09-14')])
check("the editor still holds the series, as saved",
      app.selected_note_id == 1
      and app.editor_state_matches_saved(app.capture_editor_state()))
if _os_tr is not None:
    app._restore_from_trash(_os_tr); app.update()
check('the day moved to the Trash comes back from it as a note on its day',
      any(n.get('date') == '2026-09-21' and n.get('title') == 'Stand-up'
          and n is not app.find_note(1) for n in app.notes))

# The Trash is written before the notes. Stopped between the two, the app
# came back with the day still on the series and its copy in the Trash, and
# moving it to the Trash again put a second copy there.
_os_seed()
_os_walk(['keep', 'trash'])
# Put there twenty days ago: the copy kept must be kept the whole window
# from now, as the question promised, not go in ten.
from noteorganizer.core.storage import STAMP_FORMAT as _os_stamp_format
_os_twenty_ago = (_dt5w.datetime.now() - _dt5w.timedelta(days=20)).strftime(_os_stamp_format)
_os_kept_trash = [dict(e, deleted_at=_os_twenty_ago) if e.get('date') == '2026-09-21' else dict(e)
                  for e in app.trash]
_os_seed()
app.trash = _os_kept_trash
NO.save_trash(app.trash)
check('fixture: the day is on the series again, its copy already in the Trash',
      '2026-09-21' in (app.find_note(1).get('overrides') or {})
      and sum(e.get('date') == '2026-09-21' for e in app.trash) == 1)
_os_walk(['keep', 'trash'])
check(f"moving it to the Trash again leaves one copy there "
      f"({sum(e.get('date') == '2026-09-21' for e in app.trash)})",
      sum(e.get('date') == '2026-09-21' for e in app.trash) == 1
      and '2026-09-21' not in (app.find_note(1).get('overrides') or {}))
_os_left = [NO.core_days_left_in_trash(e.get('deleted_at')) for e in app.trash
            if e.get('date') == '2026-09-21']
_os_left_on_disk = [NO.core_days_left_in_trash(e.get('deleted_at')) for e in NO.load_trash()
                    if isinstance(e, dict) and e.get('date') == '2026-09-21']
check(f"...kept the whole window from now, in the file too ({_os_left}, {_os_left_on_disk}, "
      f"{NO.trash_retention_days()})",
      _os_left == _os_left_on_disk == [NO.trash_retention_days()])

# A day's text of two lines is asked with its lines kept apart, as a card
# shows them: run together, they read as one sentence.
_os_seed()
app.find_note(1)['overrides']['2026-09-14']['body'] = 'moved to Monday\n\n  room 2 '
app.save_notes()
_os_lines = _os_walk(['keep', 'keep'])
check(f'a day off its schedule of two lines is asked with its lines kept apart '
      f'({_os_lines[0][1][:90]!r})',
      'moved to Monday · room 2' in _os_lines[0][1])

# Leaving a day changes nothing, and keeps its way in. And text typed and not
# yet saved goes into the series first, as on every route that writes behind
# the editor: the editor is filled from the note again once a day is made a
# note, and that refill saves nothing (_editor_follows_external_change).
_os_seed()
app.body_text.insert('end', ' typed before')
_os_asked = _os_walk(['note', 'keep'])
check('"Leave it" keeps a day where it was, and its way in',
      len(_os_asked) == 2
      and sorted(app.find_note(1).get('overrides') or {}) == ['2026-09-15', '2026-09-21']
      and bool(app.offschedule_btn.winfo_ismapped())
      and str(app.offschedule_btn.cget('text')).startswith("✎ 1 day's own edits"))
check('...and what was typed before the question is in the series, not lost',
      app.find_note(1).get('body', '').endswith('typed before')
      and app.body_text.get('1.0', 'end-1c').endswith('typed before'))

# The way in is a long-lived widget: every colour it has follows the theme.
_os_seed()
app.set_theme('light'); app.update()
_os_colors = (str(_os_btn.cget('bg')), str(_os_btn.cget('activebackground')),
              str(_os_btn.cget('highlightcolor')), str(_os_btn.cget('fg')))
check(f'the way in takes every colour of a new theme ({_os_colors})',
      _os_colors == (app.colors['bg'], app.colors['bg'], app._focus_ring(),
                     app.colors['accent_text']))
app.set_theme('dark'); app.update()

# At the smallest window the way in wraps within the line it has. (The window
# then scrolls the whole editor sideways, as it always has; this asks only
# that the line itself is not wider than the room it is given.)
_os_geo = app.geometry()
app.geometry('640x600'); app.update()
check(f'at the smallest window the way in wraps within its line '
      f'({_os_btn.winfo_reqwidth()} of {_os_btn.winfo_width()})',
      _os_btn.winfo_reqwidth() <= _os_btn.winfo_width() + 1)
app.geometry(_os_geo); app.update()

# The series line runs long with a long rule; centred and unwrapped it lost
# its first and last words at an ordinary window size (seen at 1200 px).
app.find_note(1)['recurrence'] = NO.normalize_recurrence(
    {'freq': 'weekly', 'weekdays': [0, 1, 2, 3, 4], 'end': '2026-12-31'})
app.save_notes()
# The note is open already, so opening it again draws nothing anew: the line
# is asked for again, as every route that changes a series asks for it.
app._update_occurrence_banner(); app.update()
_os_line = app.occurrence_banner
check(f'the series line wraps within its width rather than cutting its words '
      f'({_os_line.winfo_reqwidth()} of {_os_line.winfo_width()})',
      'Mon, Tue, Wed, Thu, Fri' in _rn_banner()
      and _os_line.winfo_reqwidth() <= _os_line.winfo_width() + 1)

# While a turn-off of the repeat waits, every day goes with it: no way in.
# Asked of the series as seeded -- Tuesdays, with Monday edits. The long rule
# above takes the Mondays back onto the schedule, and with no day off it
# there was no way in to withhold: the check passed with its guard taken
# out (OS08 survived the full catalogue). Placement is asked, not mapping,
# which comes later under Xvfb.
_os_seed()
_os_off = NO.off_schedule_days(app.find_note(1))
check(f'fixture: the series has days off its schedule, and their way in shows '
      f'({_os_off})',
      len(_os_off) == 2 and app._is_placed(_os_btn))
_os_ok = _rn_pick(NO.FREQ_LABELS[''])
app._update_occurrence_banner(); app.update()
check('while a turn-off of the repeat waits, the way in is not offered',
      _os_ok and not app._is_placed(_os_btn))
_rn_pick(NO.FREQ_LABELS['weekly'])
app._cancel_pending_autosave()

# History: a day the series no longer has was listed as one of its days, and
# opened as a day no calendar shows. It is marked, and opens the way in.
_os_seed()
app.notebook.select(app.TAB_CALENDAR); app.update()
app._toggle_calendar_history(); app.update()
app._history_toggle_group(1); app.update()
_os_labels = [str(w.cget('text')) for w in _rn_walk(app._history_rows)
              if isinstance(w, tk.Label)]
# The day rows, not the series row, which counts them ("· 2 off the schedule").
_os_rows = [w for w in _rn_walk(app._history_rows)
            if isinstance(w, tk.Label) and str(w.cget('text')).startswith('✎')
            and 'off the schedule' in str(w.cget('text'))]
check(f'History marks the 2 days off the schedule ({len(_os_rows)})', len(_os_rows) == 2)
check('...and the series row counts them',
      any('🔁' in t and '· 2 off the schedule' in t for t in _os_labels))
_os_asked = []
_os_real = app._themed_dialog
app._themed_dialog = lambda title, message, *a, **k: (_os_asked.append(title), 'keep')[1]
try:
    if _os_rows:
        _qa_click(_os_rows[0]); app.update()
finally:
    app._themed_dialog = _os_real
check(f'...and a click on one opens the way in, not a day the calendar lacks ({_os_asked})',
      _os_asked[:1] == ['Day 1 of 2 off the schedule'])
app._toggle_calendar_history(); app.update()
# Walking ANOTHER note's days leaves the open one as it is: flushed as if left,
# its unreadable date was asked about, and Continue threw it away while the
# note stayed open.
_os_seed()
app.open_note_in_tab(app.find_note(2)); app.update()
app.date_entry.delete(0, 'end'); app.date_entry.insert(0, '31.09.2026')
_os_asked = []
app._themed_dialog = lambda title, message, *a, **k: (_os_asked.append(title), 'keep')[1]
try:
    app._show_off_schedule_days(app.find_note(1)); app.update()
finally:
    app._themed_dialog = _os_real
check(f"walking another note's days off the schedule asks nothing of the open note ({_os_asked})",
      "Part of this note isn't saved" not in _os_asked
      and _os_asked[:1] == ['Day 1 of 2 off the schedule']
      and app.date_entry.get() == '31.09.2026')
app._cancel_pending_autosave()
app.notebook.select(app.TAB_NOTES); app.update()
app.new_note(); app.update()
app.notes = []; app.save_notes()
app.trash = []; NO.save_trash(app.trash)

# ---- ONE DAY OF A SERIES, OPENED ON ITS OWN ----
# Field report (2026-10-12): how to edit just one day of a series could not be
# found -- a day opened under the series' own date and repeat as fields to
# change -- and a category picked for one day seemed to do nothing: a day held
# every edit for a question asked only on leaving, and nothing said it waited.
# The owner's call: a day opened from the calendar is edited on its own and
# saves to itself like any note; the whole series is one click away. Every
# question is recorded and answered safely here: the promise is that none is
# asked, and a broken app must show up as a red check, not a wait.
_dm_asked = []
_dm_real_dialog = app._themed_dialog
_dm_real_scope = app.ask_occurrence_scope
_dm_real_yes = app.ask_yes_no


def _dm_record():
    app._themed_dialog = lambda title, *a, **k: (_dm_asked.append(title), None)[1]
    app.ask_occurrence_scope = lambda *a, **k: (_dm_asked.append('scope'), None)[1]
    app.ask_yes_no = lambda title, *a, **k: (_dm_asked.append(title), False)[1]


_dm_record()


def _dm_seed(body='series text', formatting=None):
    app.new_note(); app.update()
    app.notes = [
        NO.normalize_note({
            'id': 1, 'title': 'Stand-up', 'body': body, 'category': 'General',
            'date': '2026-10-05', 'recurrence': {'freq': 'weekly', 'weekdays': [0]},
            'formatting': ([{'start': 0, 'end': 6, 'style': 'bold'}]
                           if formatting is None else formatting),
            'checklist': [{'text': 'agenda', 'done': False}]}),
        NO.normalize_note({'id': 2, 'title': 'Dentist', 'body': '10:30',
                           'category': 'Personal', 'date': '2026-10-12'})]
    app.save_notes()
    app.refresh_note_list()
    app.notebook.select(app.TAB_CALENDAR)
    app.cal_year, app.cal_month = 2026, 10
    app.render_calendar(); app.update()
    app.open_day_popup('2026-10-12'); app.update()


def _dm_button(text):
    return next((w for w in _rn_walk(app.day_panel)
                 if isinstance(w, tk.Button) and text in str(w.cget('text'))), None)


def _dm_open_day(**seed):
    """Open 12.10.2026 of the series the way a person does: its note in the
    day's panel, then the panel's "Edit this day"."""
    _dm_seed(**seed)
    app.show_day_note(app.find_note(1), '2026-10-12'); app.update()
    door = _dm_button('Edit this day')
    if door is not None:
        door.invoke(); app.update()
    else:
        # A panel without its door is its own red check (the two doors);
        # the day is opened as the door would open it, so every check after
        # it still runs to the footer.
        app._open_note_from_calendar(app.find_note(1), '2026-10-12'); app.update()
    app._cancel_pending_autosave()
    del _dm_asked[:]


def _dm_day():
    return (app.find_note(1).get('overrides') or {}).get('2026-10-12')


def _dm_pick_category(name):
    app._open_category_dropdown(); app.update()
    rows = ([w for w in _rn_walk(app._mini_popup) if isinstance(w, tk.Label)
             and str(w.cget('text')).strip() == name]
            if app._mini_popup is not None else [])
    if rows:
        _qa_click(rows[0]); app.update()
    return bool(rows)


_dm_seed()
app.show_day_note(app.find_note(1), '2026-10-12'); app.update()
_dm_doors = (_dm_button('Edit this day'), _dm_button('Edit the whole series'),
             _dm_button('Open in editor'))
check('a repeating note in a calendar day offers two doors: this day, or the whole series',
      _dm_doors[0] is not None and _dm_doors[1] is not None and _dm_doors[2] is None)
app.show_day_note(app.find_note(2), '2026-10-12'); app.update()
check('...and a note that does not repeat keeps its one "Open in editor"',
      _dm_button('Open in editor') is not None and _dm_button('Edit this day') is None)

_dm_open_day()
_dm_back = getattr(app, '_pending_calendar_return', None) or {}
check('"Edit this day" opens that day on its own, with the way back to the calendar armed',
      app.selected_note_id == 1 and app.current_occurrence_date == '2026-10-12'
      and app._day_mode() and _dm_back.get('date_str') == '2026-10-12')
_dm_strip = str(app.day_strip_lbl.cget('text'))
check(f'a day says which day it is, and that what changes stays on it ({_dm_strip!r})',
      bool(app.day_strip.winfo_ismapped())
      and 'Only this day: Monday, 12 October 2026' in _dm_strip
      and 'stays on this day' in _dm_strip
      and str(app.status_lbl.cget('text')) == 'Only this day: 12.10.2026')
check("...shows its own date as words, not the series' start as a field to change",
      not app._is_placed(app.date_entry)
      and str(app.day_date_lbl.cget('text')) == '12.10.2026'
      and bool(app.day_date_lbl.winfo_ismapped()))
check(f'...and its repeat as a line, not as boxes to change '
      f'({app.day_repeat_lbl.cget("text")!r})',
      not app._is_placed(app.rec_freq_menu) and not app._is_placed(app.rec_details)
      and str(app.day_repeat_lbl.cget('text')).startswith(
          'Every week on Mon, starting 05.10.2026'))
check("...with \"This day:\" beside its category, and the checklist and the files "
      "marked as the whole series'",
      bool(app.day_cat_lbl.winfo_ismapped())
      and str(app.checklist_btn.cget('text')).endswith('· whole series')
      and str(app.attach_label.cget('text')) == '📎 Attachments · whole series')

# The field report's own route: a category from the editor's corner.
_dm_picked = _dm_pick_category('Work')
_dm_waits = bool(_qa_waiting(app, '_autosave_now'))
app._autosave_now(); app.update()
check(f'a category picked for one day is saved to that day, asking nothing '
      f'({_dm_picked}; waits {_dm_waits}; day {_dm_day()}; asked {_dm_asked})',
      _dm_picked and _dm_waits
      and app.find_note(1)['category'] == 'General'
      and (_dm_day() or {}).get('category') == 'Work' and _dm_asked == [])
check(f'...and the status line says so ({app.status_lbl.cget("text")!r})',
      str(app.status_lbl.cget('text')) == 'Auto-saved 12.10.2026 only')
check("the calendar draws that day in its own category, every other day in the series'",
      _os_cv._day_row_parts(app, app.find_note(1), '2026-10-12')[2]
      == NO.CATEGORY_COLORS['Work']
      and _os_cv._day_row_parts(app, app.find_note(1), '2026-10-19')[2]
      == NO.CATEGORY_COLORS['General'])

_dm_pick_category('General')
app._autosave_now(); app.update()
check(f'a day put back to what the series says keeps no copy of its own, and '
      f'follows the series again ({app.find_note(1).get("overrides")}; '
      f'{app.status_lbl.cget("text")!r})',
      '2026-10-12' not in (app.find_note(1).get('overrides') or {})
      and 'follows the series again' in str(app.status_lbl.cget('text')))
app.title_entry.insert('end', 'x'); app._autosave_now(); app.update()
_dm_typed = dict(_dm_day() or {})
app.title_entry.delete(len(app.title_entry.get()) - 1, 'end')
app._autosave_now(); app.update()
check(f'...nor does a letter typed and taken back ({_dm_typed.get("title")!r}; {_dm_day()})',
      _dm_typed.get('title') == 'Stand-upx' and _dm_day() is None)

app.body_text.insert('end', ' (room 2)')
app.open_note_in_tab(app.find_note(2)); app.update()
check(f'leaving a day saves what was typed to that day, asking nothing '
      f'({_dm_day()}; {_dm_asked})',
      (_dm_day() or {}).get('body') == 'series text (room 2)'
      and app.find_note(1)['body'] == 'series text' and _dm_asked == [])

# Ctrl+Z still reaches what was typed after the day saved itself: the save
# does not reload the editor, so the undo history it holds stays.
_dm_open_day()
app.body_text.insert('end-1c', ' undo-me')
app.body_text.edit_separator()
app._autosave_now(); app.update()
_dm_typed_body = (_dm_day() or {}).get('body') or ''
app._body_undo_redo('undo'); app.update()
app._autosave_now(); app.update()
check(f'Ctrl+Z after a day saved itself takes the typing back, and the day '
      f'follows the series again ({_dm_typed_body!r}; {_dm_day()})',
      _dm_typed_body.endswith('undo-me')
      and 'undo-me' not in app.body_text.get('1.0', 'end-1c')
      and _dm_day() is None and _dm_asked == [])

# A tick is the series', and a word made bold beside it is not: a day keeps no
# formatting of its own, and its save no longer writes the editor's to every
# day (it did, on a day with no text of its own, whenever a tick came along).
_dm_open_day()
app.body_text.tag_add('bold', '1.7', '1.11')
for _dm_item in app._working_checklist[:1]:     # the series' one item
    _dm_item['done'] = True
app._autosave_now(); app.update()
_dm_s = app.find_note(1)
check(f'a tick on a day goes to the series, and a word made bold beside it does not '
      f'({_dm_s.get("checklist")}; {_dm_s.get("formatting")}; {_dm_day()})',
      [i['done'] for i in _dm_s.get('checklist') or []] == [True]
      and _dm_s.get('formatting') == [{'start': 0, 'end': 6, 'style': 'bold'}]
      and _dm_day() is None and _dm_asked == [])

# The series' date and repeat are out of sight on a day, still in their
# fields: whatever reaches them is put back, and never moves the series.
_dm_open_day()
app._show_date_in_field('2026-10-19')
app._autosave_now(); app.update()
check(f"a date reaching a day's hidden field never moves the series, and the field "
      f"shows the series' start again ({app.find_note(1)['date']}; {app._typed_date()!r})",
      app.find_note(1)['date'] == '2026-10-05' and app._typed_date() == '05.10.2026'
      and _dm_asked == [])
check("...and the repeat's boxes stay out of sight once it is put back",
      not app._is_placed(app.rec_details) and not app._is_placed(app.rec_freq_menu)
      and app._day_mode())

# The strip's way to the whole series: the day first, then the series.
_dm_open_day()
app.body_text.insert('end', ' (day)')
app.day_series_btn.invoke(); app.update()
app._cancel_pending_autosave()
_dm_back = getattr(app, '_pending_calendar_return', None) or {}
check(f'"Edit the whole series" saves the day to the day, then opens the series, '
      f'asking nothing ({_dm_day()}; {_dm_asked})',
      (_dm_day() or {}).get('body') == 'series text (day)'
      and app.selected_note_id == 1 and app.current_occurrence_date is None
      and _dm_asked == [])
_dm_row = app.date_entry.master.pack_slaves()
check("...the series with its date and repeat to change, in their places, and "
      "nothing of the day's marks",
      app._is_placed(app.date_entry) and app._is_placed(app.rec_freq_menu)
      and app._is_placed(app.rec_details) and not app._is_placed(app.day_strip)
      and not app._is_placed(app.day_cat_lbl) and not app._is_placed(app.day_date_lbl)
      and not app._is_placed(app.day_repeat_lbl)
      and app.date_entry in _dm_row and app._color_label in _dm_row
      and _dm_row.index(app.date_entry) < _dm_row.index(app._color_label)
      and not str(app.checklist_btn.cget('text')).endswith('· whole series')
      and str(app.attach_label.cget('text')) == '📎 Attachments'
      and _rn_banner().startswith('🔁 This note repeats'))
check(f'...and the way back to the calendar still leads to that day ({_dm_back})',
      _dm_back.get('date_str') == '2026-10-12')

# A day kept in the editor's state comes back as a day.
_dm_open_day()
_dm_state = app.capture_editor_state()
app.new_note(); app.update()
_dm_off = (app._day_mode(), app._is_placed(app.day_strip), app._is_placed(app.date_entry))
app.restore_editor_state(_dm_state); app.update()
check(f'a day restored from the editor\'s state comes back as a day, and a new note '
      f'is no day ({_dm_off})',
      _dm_off == (False, False, True)
      and app._day_mode() and app._is_placed(app.day_strip)
      and not app._is_placed(app.date_entry))

# Delete keeps its question: it destroys, and how much is the person's to say.
_dm_open_day()
_dm_q = []
app.ask_occurrence_scope = _dm_real_scope
app._themed_dialog = lambda title, message, *a, **k: (
    _dm_q.append((title, message, [b for b, _v in k.get('buttons', [])])), None)[1]
try:
    app._delete_note(app.find_note(1), '2026-10-12'); app.update()
finally:
    _dm_record()
check(f"Delete on a day still asks, in the day's words ({_dm_q})",
      bool(_dm_q) and 'The day: 12.10.2026' in _dm_q[0][1]
      and _dm_q[0][2] == ['Cancel', 'The whole series', 'Only this day']
      and app.find_note(1) is not None)

# A day whose text ends in a table is saved, and then reads as saved.
_dm_open_day(body='intro\n| a | b |\n| --- | --- |\n| 1 | 2 |', formatting=[])
app.title_entry.insert('end', ' (moved)')
app._autosave_now(); app.update()
check(f'a day ending in a table is saved to the day, and then reads as saved '
      f'({(_dm_day() or {}).get("title")!r})',
      (_dm_day() or {}).get('title') == 'Stand-up (moved)'
      and app.editor_state_matches_saved(app.capture_editor_state()))

# Long-lived widgets: every colour they have follows the theme.
_dm_open_day()
app.set_theme('light'); app.update()
_dm_c = app.colors
_dm_got = tuple(str(v).lower() for v in (
    app.day_strip.cget('bg'), app.day_strip.winfo_children()[0].cget('bg'),
    app.day_strip_lbl.cget('bg'), app.day_strip_lbl.cget('fg'),
    app.day_series_btn.cget('bg'), app.day_series_btn.cget('fg'),
    app.day_series_btn.cget('activebackground'),
    app.day_series_btn.cget('highlightbackground'),
    app.day_cat_lbl.cget('fg'), app.day_date_lbl.cget('fg'),
    app.day_repeat_lbl.cget('fg')))
_dm_want = tuple(str(v).lower() for v in (
    _dm_c['card'], _dm_c['accent'], _dm_c['card'], _dm_c['text'], _dm_c['accent'],
    app._on_fill('accent'), _dm_c['accent_hover'], _dm_c['card'],
    _dm_c['accent_text'], _dm_c['text'], _dm_c['text']))
check(f"every colour of the day's strip and words follows a new theme ({_dm_got})",
      _dm_got == _dm_want)
app.set_theme('dark'); app.update()

# The smallest window: the window scrolls the editor sideways as it always
# has; the day's own lines wrap within the room they are given, and a day
# asks the editor for no more width than its series does.
_dm_geo = app.geometry()
app.geometry('640x600'); app.update(); app.update()
_dm_req_day = app.editor.winfo_reqwidth()
_dm_fits = (app.day_strip_lbl.winfo_reqwidth(), app.day_strip_lbl.winfo_width(),
            app.day_repeat_lbl.winfo_reqwidth(), app.day_repeat_lbl.winfo_width())
check(f"at the smallest window the day's strip and repeat line wrap within their "
      f"room ({_dm_fits})",
      _dm_fits[0] <= _dm_fits[1] + 1 and _dm_fits[2] <= _dm_fits[3] + 1)
app.open_note_in_tab(app.find_note(1)); app.update()
check(f'...and a day asks the editor for no more width than its series '
      f'({_dm_req_day} vs {app.editor.winfo_reqwidth()})',
      _dm_req_day <= app.editor.winfo_reqwidth())
app.geometry(_dm_geo); app.update()
app._cancel_pending_autosave()

# ---- ONE DAY OF A SERIES, HELD ON ANOTHER DATE ----
# Field request (2026-10-13): one day of a series held on another date -- the
# weekly meeting moved to Tuesday one week -- while it stays a day of the
# series. "📅 Move this day…" beside the day's date, an Undo, and a Reset that
# puts it back and asks about its text. One field in the file: `moved`.
import json as _json5mv


def _mv_file_note():
    with open('notes_data.json', encoding='utf-8') as _fmv:
        _data = _json5mv.load(_fmv)
    _rows = _data.get('notes', _data) if isinstance(_data, dict) else _data
    return next((n for n in _rows if n.get('id') == 1), {})


def _mv_on(day):
    return [n['id'] for n in app.notes_on_date(day)]


_dm_open_day()
check('a day offers "Move this day…" beside its date',
      bool(app.day_move_btn.winfo_ismapped()) and _dm_asked == [])
app.body_text.insert('end-1c', ' (room 2)')          # typed, not saved yet
app.day_move_btn.invoke(); app.update()
_mv_pick = (next((w for w in _rn_walk(app._mini_popup) if isinstance(w, tk.Button)
                  and str(w.cget('text')) == '13'), None)
            if app._mini_popup is not None else None)
if _mv_pick is not None:
    _mv_pick.invoke(); app.update()
_mv_s = app.find_note(1)
check(f"a date picked there holds the day on it: drawn there, not on its own date "
      f"({_mv_s.get('moved')}; 12th {_mv_on('2026-10-12')}; 13th {_mv_on('2026-10-13')})",
      _mv_pick is not None and _mv_s.get('moved') == {'2026-10-12': '2026-10-13'}
      and _mv_on('2026-10-12') == [2] and _mv_on('2026-10-13') == [1])
check("...what was typed on the day before goes with it, and the editor follows it",
      (_mv_s.get('overrides') or {}).get('2026-10-13', {}).get('body')
      == 'series text (room 2)'
      and '2026-10-12' not in (_mv_s.get('overrides') or {})
      and app.current_occurrence_date == '2026-10-13' and app._day_mode())
check(f"...the day says where it came from, and the move can be undone "
      f"({app.day_strip_lbl.cget('text')!r})",
      'moved from Monday, 12 October' in str(app.day_strip_lbl.cget('text'))
      and str(app.day_date_lbl.cget('text')) == '13.10.2026'
      and app._toast_action is not None and _dm_asked == [])
_mv_disk = NO.normalize_note(_mv_file_note())
check('...and the file holds the move, so the day is there after a restart',
      _mv_disk.get('moved') == {'2026-10-12': '2026-10-13'}
      and NO.expand_occurrences(_mv_disk, NO.parse_date('2026-10-12'),
                                NO.parse_date('2026-10-13')) == ['2026-10-13'])
check("a share code does not carry it -- a series' days are this notebook's",
      'moved' not in _msharing._shareable_view(_mv_s))

# (This file answers every notice for itself, from its top: this one is read.)
_mv_info = []
_mv_real_info = app.show_info
app.show_info = lambda title, message, **k: (_mv_info.append(title), True)[1]
try:
    app._move_this_day('2026-10-19'); app.update()
finally:
    app.show_info = _mv_real_info
check(f'a date the series already has is refused, saying why, and nothing moves '
      f'({_mv_info}; {_dm_asked})',
      _mv_info == ['That day is taken'] and _dm_asked == []
      and app.find_note(1)['moved'] == {'2026-10-12': '2026-10-13'})

app._run_toast_action(); app.update()
_mv_s = app.find_note(1)
check('Undo puts the day back where it was, its own edit with it, the editor following',
      _mv_s['moved'] == {} and '2026-10-12' in (_mv_s.get('overrides') or {})
      and app.current_occurrence_date == '2026-10-12' and _dm_asked == [])

# A date the series keeps words for though no day of it is drawn there -- a
# day off its schedule -- is taken too: the move wrote over those words, and
# its Undo took the day back without them.
_mv_s['overrides']['2026-10-20'] = {'body': 'off-schedule words'}
app.save_notes()
_mv_info = []
app.show_info = lambda title, message, **k: (_mv_info.append((title, message)), True)[1]
try:
    app._move_this_day('2026-10-20'); app.update()
finally:
    app.show_info = _mv_real_info
_mv_s = app.find_note(1)
check(f"a date that keeps a day's words the calendar no longer shows is refused, saying "
      f"so, and its words stay ({_mv_info})",
      [t for t, _m in _mv_info] == ['That day is taken']
      and 'still keeps text or a colour of its own for a day' in _mv_info[0][1]
      and _mv_s['moved'] == {} and app.current_occurrence_date == '2026-10-12'
      and _mv_s['overrides'].get('2026-10-20') == {'body': 'off-schedule words'})
# ...and a day goes home, by its Reset or the move's Undo, only while no other
# day stands on its date: its return hid that one, and "Only the date" wrote
# over its words (the phone refused it; now both do).
app._move_this_day('2026-10-14'); app.update()
_mv_s = app.find_note(1)
NO.move_day(_mv_s, '2026-10-19', '2026-10-12')
_mv_s['overrides']['2026-10-12'] = {'body': "the 19th's words"}
app.save_notes()
_mv_info = []
app.show_info = lambda title, message, **k: (_mv_info.append((title, message)), True)[1]
_mv_real_dialog = app._themed_dialog
app._themed_dialog = lambda *a, **k: None     # a Reset that asked is cancelled
try:
    app._reset_occurrence_override(app.find_note(1), '2026-10-14'); app.update()
    app._run_toast_action(); app.update()
finally:
    app.show_info = _mv_real_info
    app._themed_dialog = _mv_real_dialog
_mv_s = app.find_note(1)
check(f"a day's Reset and its move's Undo leave it away while another day stands on its "
      f"date, each day keeping its words ({_mv_info}; {_mv_s['moved']})",
      [t for t, _m in _mv_info] == ['Reset this day']
      and _mv_s['moved'] == {'2026-10-12': '2026-10-14', '2026-10-19': '2026-10-12'}
      and _mv_s['overrides'].get('2026-10-12') == {'body': "the 19th's words"}
      and (_mv_s['overrides'].get('2026-10-14') or {}).get('body') == 'series text (room 2)')
# Each with a default: under the check's mutant (DR141) the day came home,
# and a bare pop stopped the suite before its footer, a verdict of NO-RUN.
_mv_s['moved'].pop('2026-10-19', None)
for _mv_day in ('2026-10-12', '2026-10-20'):
    _mv_s['overrides'].pop(_mv_day, None)
app.save_notes()
app._undo_day_move(1, _mv_s.get('uid'), '2026-10-12', '2026-10-14', '2026-10-12'); app.update()
_mv_s = app.find_note(1)
check('...and once its date is free again, the Undo brings it home',
      _mv_s['moved'] == {} and app.current_occurrence_date == '2026-10-12'
      and (_mv_s['overrides'].get('2026-10-12') or {}).get('body') == 'series text (room 2)')

# Reset on a moved day with text of its own: the date always goes back; the
# text is asked about.
app._move_this_day('2026-10-14'); app.update()
_mv_row = app.day_move_btn.master.pack_slaves()
check("a moved day offers its Reset in the day itself, beside Move this day",
      bool(app.day_reset_btn.winfo_ismapped())
      and app.day_reset_btn in _mv_row and app.day_move_btn in _mv_row
      and _mv_row.index(app.day_move_btn) + 1 == _mv_row.index(app.day_reset_btn))
_mv_q = []
app._themed_dialog = lambda title, message, *a, **k: (
    _mv_q.append((title, [b for b, _v in k.get('buttons', [])],
                  app._dialog_focus_index(k.get('buttons', []), k.get('default')))),
    'date')[1]
app.day_reset_btn.invoke(); app.update()
_dm_record()
_mv_s = app.find_note(1)
check(f'Reset on a moved day with text of its own asks: only the date, or the date '
      f'and the text ({_mv_q})',
      [q[:2] for q in _mv_q[:1]] == [('Reset this day',
                                      ['Cancel', 'Only the date', 'The date and the text'])])
check('...and Enter there keeps the text: "Only the date" holds the focus, '
      'since the other answer cannot be taken back',
      _mv_q[:1] and _mv_q[0][2] == 1)
check('..."Only the date" puts the day back and keeps its text',
      _mv_s['moved'] == {}
      and (_mv_s.get('overrides') or {}).get('2026-10-12', {}).get('body')
      == 'series text (room 2)'
      and app.current_occurrence_date == '2026-10-12')
app._move_this_day('2026-10-15'); app.update()
app._themed_dialog = lambda *a, **k: 'text'
app._reset_occurrence_override(app.find_note(1), '2026-10-15'); app.update()
_dm_record()
_mv_s = app.find_note(1)
check('..."The date and the text" puts it back, following the series again',
      _mv_s['moved'] == {} and '2026-10-12' not in (_mv_s.get('overrides') or {})
      and app.current_occurrence_date == '2026-10-12'
      and app.body_text.get('1.0', 'end-1c').startswith('series text')
      and 'room 2' not in app.body_text.get('1.0', 'end-1c'))
check('...and a day with nothing left to reset offers no Reset',
      not app._is_placed(app.day_reset_btn) and bool(app.day_move_btn.winfo_ismapped()))

# The button follows the day as it is edited, never moved: text of its own,
# saved as it is typed, brings it; typed back to the series', it goes. And a
# Reset pressed before the last typing saved asks the menu's question, and the
# typing does not come back when its save comes due.
_mv_title = app.title_entry.get()
app.title_entry.insert('end', ' (typed)')
app._autosave_now(); app.update()
_mv_typed = app._is_placed(app.day_reset_btn)
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, _mv_title)
app._autosave_now(); app.update()
check("...a day's own text, saved as it is typed, brings its Reset; typed back to "
      "the series', it goes",
      _mv_typed and not app._is_placed(app.day_reset_btn)
      and '2026-10-12' not in (app.find_note(1).get('overrides') or {}))
app.title_entry.insert('end', ' (room 3)')
app._autosave_now(); app.update()
app.title_entry.insert('end', ' more')
app._schedule_autosave()
_mv_yn = []
app.ask_yes_no = lambda title, message, *a, **k: (_mv_yn.append(message), True)[1]
app.day_reset_btn.invoke(); app.update()
app._autosave_now(); app.update()
_dm_record()
check(f"...Reset there, pressed mid-typing, asks the menu's question and the "
      f"typing stays gone ({_mv_yn})",
      [m.split('\n')[0] for m in _mv_yn] == ['Return 12.10.2026 to the series content?']
      and '2026-10-12' not in (app.find_note(1).get('overrides') or {})
      and app.title_entry.get() == _mv_title
      and not app._is_placed(app.day_reset_btn))

# Moved with no text of its own: the menu still offers its way back, and its
# Reset only asks to put it back.
app._move_this_day('2026-10-16'); app.update()
_mv_labels = []
_mv_add, _mv_pop = tk.Menu.add_command, tk.Menu.tk_popup
tk.Menu.add_command = lambda _m, **kw: (_mv_labels.append(kw.get('label', '')),
                                        _mv_add(_m, **kw))[1]
tk.Menu.tk_popup = lambda _m, *a, **k: None
try:
    app.show_note_context_menu(type('E', (), {'x_root': 0, 'y_root': 0})(),
                               app.find_note(1), occurrence_date='2026-10-16')
finally:
    tk.Menu.add_command, tk.Menu.tk_popup = _mv_add, _mv_pop
check(f'a moved day with no text of its own still offers its way back in its menu '
      f'({[l for l in _mv_labels if "Reset" in l]})',
      any('Reset this day to the series…' in l for l in _mv_labels))
_mv_yn = []
app.ask_yes_no = lambda title, message, *a, **k: (_mv_yn.append(message), True)[1]
app._reset_occurrence_override(app.find_note(1), '2026-10-16'); app.update()
_dm_record()
check(f'...and its Reset only asks to put it back, and does ({_mv_yn})',
      _mv_yn == ['Put this day back on Monday, 12 October 2026?']
      and app.find_note(1)['moved'] == {})

# Delete a moved day, with text of its own, and its Undo.
app._move_this_day('2026-10-17'); app.update()
app.title_entry.insert('end', ' (Sat)')
app._autosave_now(); app.update()
app.ask_occurrence_scope = lambda *a, **k: 'occurrence'
app._delete_note(app.find_note(1), '2026-10-17'); app.update()
_mv_s = app.find_note(1)
_mv_gone = (_mv_s['moved'], _mv_s['exceptions'], sorted(_mv_s.get('overrides') or {}),
            _mv_on('2026-10-17'), _mv_on('2026-10-12'))
app._run_toast_action(); app.update()
_dm_record()
_mv_s = app.find_note(1)
check(f'deleting a moved day skips the date its rule gives it, and takes the move '
      f'with it ({_mv_gone})',
      _mv_gone == ({}, ['2026-10-12'], [], [], [2]))
check('...and its Undo brings it back moved, with its own text',
      _mv_s['moved'] == {'2026-10-12': '2026-10-17'} and _mv_s['exceptions'] == []
      and ((_mv_s.get('overrides') or {}).get('2026-10-17', {}).get('title') or '')
      .endswith('(Sat)')
      and _mv_on('2026-10-17') == [1])

# A deleted day comes back only onto a date nothing else of the series holds:
# another day moved there since was hidden under it, its words read as the
# deleted day's, and the deleted day's own were lost. Its own series, so the
# editor's above stays as it is.
app.notes.append(NO.normalize_note({
    'id': 78, 'title': 'Two days', 'body': 'x', 'date': '2026-10-05',
    'recurrence': {'freq': 'weekly'},
    'overrides': {'2026-10-12': {'body': 'Mon 12 own'}, '2026-10-19': {'body': 'Mon 19 own'}}}))
_ud = app.find_note(78)
_ud_edit = _ud['overrides'].pop('2026-10-12')       # deleted, as its Undo remembers it
_ud['exceptions'] = ['2026-10-12']
NO.move_day(_ud, '2026-10-19', '2026-10-12')
app.save_notes()
_ud_said = []
_ud_real_toast = app._show_toast
app._show_toast = lambda text, *a, **k: _ud_said.append(text)
try:
    app._undo_occurrence_delete(78, '2026-10-12', _ud_edit, _ud.get('uid')); app.update()
finally:
    app._show_toast = _ud_real_toast
_ud = app.find_note(78)
check(f"a deleted day's Undo leaves it out while another day stands on its date, each "
      f"day keeping its words ({_ud_said})",
      any('Another day of this series is on' in t for t in _ud_said)
      and _ud['exceptions'] == ['2026-10-12'] and _ud['moved'] == {'2026-10-19': '2026-10-12'}
      and _ud['overrides'].get('2026-10-12') == {'body': 'Mon 19 own'})
app.notes = [n for n in app.notes if n.get('id') != 78]
app.save_notes()

# The series counts its moved days; a repeat turned off copies them with the
# days into the rescue copy, keeps them, and Restore previous brings them back.
app.open_note_in_tab(app.find_note(1)); app.update()
check(f'the series counts its moved days above the note ({_rn_banner()!r})',
      '· 1 day moved (↷)' in _rn_banner())
app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
app.save_current_note(); app.update()
_mv_s = app.find_note(1)
_mv_off = (_mv_s['recurrence']['freq'], _mv_s.get('moved'),
           (_mv_s.get('_prev') or {}).get('moved'))
app.ask_yes_no = lambda *a, **k: True
app.restore_previous_version(); app.update()
_dm_record()
_mv_s = app.find_note(1)
check(f"turning the repeat off copies the moves with the days into the rescue copy "
      f"and keeps them ({_mv_off})",
      _mv_off == ('', {'2026-10-12': '2026-10-17'}, {'2026-10-12': '2026-10-17'}))
check('...and Restore previous brings the series back with its day moved',
      _mv_s['recurrence']['freq'] == 'weekly'
      and _mv_s.get('moved') == {'2026-10-12': '2026-10-17'}
      and _mv_on('2026-10-17') == [1])
# A series whose days hold no text of their own leaves no clutter behind:
# its moves go with the repeat.
app.notes.append(NO.normalize_note({
    'id': 77, 'title': 'Plain series', 'body': 'x', 'date': '2026-10-05',
    'recurrence': {'freq': 'weekly'}, 'moved': {'2026-10-12': '2026-10-17'}}))
app.save_notes()
app.open_note_in_tab(app.find_note(77)); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['']); app.on_recurrence_changed(); app.update()
app.save_current_note(); app.update()
_mv_n = app.find_note(77)
check(f"turning off a repeat whose days hold no text of their own leaves no moves "
      f"behind ({_mv_n.get('moved')})",
      _mv_n.get('moved') == {} and not _mv_n['recurrence'].get('freq'))
app.open_note_in_tab(app.find_note(1)); app.update()
app.open_tabs = [t for t in app.open_tabs if t['state'].get('selected_note_id') != 77]
app.notes = [n for n in app.notes if n.get('id') != 77]
app.save_notes()

# The buttons are long-lived: every colour they have follows the theme. And a
# moved day with text of its own -- both buttons, the longest date line -- asks
# the editor for no more width than its series at the smallest window.
_dm_open_day()
app._move_this_day('2026-10-13'); app.update()
app.title_entry.insert('end', ' (room 2)')
app._autosave_now(); app.update()
app.set_theme('light'); app.update()
_mv_c = app.colors
_mv_want = tuple(str(_mv_c[k]).lower() for k in (
    'sidebar', 'text', 'card', 'text', 'bg')) + (app._focus_ring().lower(),)
_mv_opts = ('bg', 'fg', 'activebackground', 'activeforeground',
            'highlightbackground', 'highlightcolor')
_mv_got = tuple(str(app.day_move_btn.cget(o)).lower() for o in _mv_opts)
_mv_got_r = tuple(str(app.day_reset_btn.cget(o)).lower() for o in _mv_opts)
check(f'every colour of "Move this day…" and "Reset this day…" follows a new '
      f'theme ({_mv_got}; {_mv_got_r})',
      _mv_got == _mv_want and _mv_got_r == _mv_want
      and str(app.day_btns.cget('bg')).lower() == str(_mv_c['bg']).lower()
      and bool(app.day_reset_btn.winfo_ismapped()))
app.set_theme('dark'); app.update()

# Every control of the day's title and date rows stays wholly in sight, at any
# width and whatever the rows hold. A packed row given less than it asks for
# drops what was packed last, in silence: a colour cut off in a photograph
# first, then, under CI's fonts, the colour's swatch gone and "This day:" with
# it, and on Windows a long title's counter squeezed to 8 px of its 46.
def _mv_in_sight(cap=3.0):
    """Pump until both rows have every control in sight -- the state this
    layout promises; mapping is asynchronous under Xvfb -- or *cap* seconds
    pass, and say what is still out of sight."""
    end = _t5f.time() + cap
    while True:
        app.update()
        lost = _qa_out_of_sight(app.editor_top_row) + _qa_out_of_sight(app.day_btns.master)
        if not lost or _t5f.time() > end:
            return lost
        _t5f.sleep(0.02)


_mv_geo = app.geometry()
_mv_title = app.title_entry.get()
app.title_entry.insert('end', 'L' * (app.TITLE_MAX_LEN - len(_mv_title) - 5))
app._refresh_title_count()
app.geometry('1100x850')
_mv_lost = _mv_in_sight()
check(f'at an ordinary window Move and Reset sit beside the date, and a long title '
      f'keeps its counter and "This day:" beside it ({_mv_lost})',
      _mv_lost == [] and app._day_btns_wrapped is False
      and app.day_btns.pack_info().get('side') == 'left'
      and app._is_placed(app.title_count_lbl))
app.geometry('640x600')
_mv_lost = _mv_in_sight()
_mv_meta = app.day_btns.master
check(f"at the smallest window every control of the day's title and date rows stays "
      f"in sight ({_mv_lost}; the date row {_mv_meta.winfo_reqwidth()} of "
      f"{_mv_meta.winfo_width()})",
      _mv_lost == [] and _mv_meta.winfo_reqwidth() <= _mv_meta.winfo_width() + 1)
# A row that cannot hold the buttons beside the date puts them under it: a
# wider font, as on a machine without this one, simulated by a date 120 px
# wider -- in pixels, not characters, so that the line left above the buttons
# fits under every font (40 characters more did not, under CI's).
def _mv_under_the_date():
    """Where the buttons' line is: (x, top) against the date's bottom -- a
    line under the date starts at the row's left edge, below it."""
    date = app._date_row_label
    return (app.day_btns.winfo_x(), app.day_btns.winfo_y(),
            date.winfo_y() + date.winfo_height())


app.day_date_lbl.pack_configure(padx=(6, 128))
app._show_day_mode()
_mv_lost = _mv_in_sight()
_mv_at = _mv_under_the_date()
check(f'a date row with no room for Move and Reset puts them on a line under the '
      f'date, every control in sight ({_mv_lost}; x, top, date bottom {_mv_at})',
      _mv_lost == [] and app._day_btns_wrapped is True
      and _mv_at[0] == 0 and _mv_at[1] >= _mv_at[2])
app.day_date_lbl.pack_configure(padx=(6, 8))
app.geometry('1100x850')
_mv_lost = _mv_in_sight()
check(f'...a window made wider puts them back beside the date ({_mv_lost})',
      _mv_lost == [] and app._day_btns_wrapped is False)
# Beside the date again however the step above went, so this step asks only
# whether a narrower window moves them.
app._show_day_mode(); app.update()
_mv_was = app._day_btns_wrapped
app.day_date_lbl.pack_configure(padx=(6, 128))
app.geometry('640x600')
_mv_lost = _mv_in_sight()
_mv_at = _mv_under_the_date()
check(f'...and one made narrower puts them under it again ({_mv_was}; {_mv_lost}; '
      f'{_mv_at})',
      _mv_was is False and _mv_lost == [] and app._day_btns_wrapped is True
      and _mv_at[0] == 0 and _mv_at[1] >= _mv_at[2])
app.day_date_lbl.pack_configure(padx=(6, 8))
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, _mv_title)
app._refresh_title_count()
app._show_day_mode()
app.update()
_mv_req_day = app.editor.winfo_reqwidth()
app.open_note_in_tab(app.find_note(1)); app.update()
check(f'...and the moved day asks the editor for no more width than its series '
      f'({_mv_req_day} vs {app.editor.winfo_reqwidth()})',
      _mv_req_day <= app.editor.winfo_reqwidth())
app.geometry(_mv_geo); app.update()
app._cancel_pending_autosave()

app._themed_dialog = _dm_real_dialog
app.ask_occurrence_scope = _dm_real_scope
app.ask_yes_no = _dm_real_yes
app.notebook.select(app.TAB_NOTES); app.update()
app.new_note(); app.update()
app.notes = []; app.save_notes()

print(f"=== QA5 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
