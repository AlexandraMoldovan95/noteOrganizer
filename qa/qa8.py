# HERMETIC SEED -- BEFORE the note_organizer import below. Building the
# app calls initialise(), which resolves the data directory and runs the
# data MIGRATIONS, so this script's data directory must be its own by
# then; seeding it before the import leaves no step in between.
# hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to run at all
# outside a scratch run, or beside a notebook it cannot prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import note_organizer as NO, tkinter as tk, time, os, tempfile, zipfile, json, shutil
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import click as _qa_click, pin_popup_visibility as _qa_pin
_qa_pin(NO)
from datetime import datetime
fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app = NO.NoteOrganizer(); app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.geometry('1100x850'); app.update()

app.notes = [{'id': i, 'title': f'Note{i}', 'body': 'x', 'category': 'General',
             'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}
             for i in range(50)]
app.save_notes()
app.refresh_note_list()
app.update()

# ---- SEARCH DEBOUNCE: no rebuild while typing, correct filter after the pause ----
# The list is a drawing: a rebuild draws every card anew, and a card drawn
# anew has new canvas items -- so the item behind each card's background
# says whether it was redrawn, as the card widget's name used to.
card_ids_before = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
typed = ''
for ch in 'Note1':
    typed += ch
    app.search_var.set(typed)
    app.update()
card_ids_immediately_after = {nid: rec['items']['bg'] for nid, rec in app._note_cards.items()}
check('rapid typing in search does not rebuild the list immediately',
      card_ids_before == card_ids_immediately_after)

t0 = time.time()
while time.time() - t0 < 0.4:
    app.update()
    time.sleep(0.02)

from _qa_support import find_all_labels, list_texts as _qa_list_texts  # noqa: E402


def list_texts():
    return _qa_list_texts(app)


texts = list_texts()
check('after the debounce elapses, search correctly filters',
      'Note1' in texts and 'Note2' not in texts)

app.search_var.set('')

# ---- SEARCH REACHES INSIDE TABLE CELLS ----
# The design's whole promise is that a table is plain text in the note,
# so a word in a cell is findable like any other word. Asserted both
# ways: the table note is kept, the plain note is filtered out.
# Each with an id of its own: normalize_note gives a note that has none
# id 0, which Note0 above already holds, and the list keeps one card per
# id -- two shown notes sharing one read back as the same title twice.
_tbl_note = {'id': 100, 'title': 'TableNote',
             'body': '| Product | Price |\n| UniqueWordInCell | 3 |'}
_oth_note = {'id': 101, 'title': 'OtherNote', 'body': 'nothing special here'}
app.notes.append(NO.normalize_note(_tbl_note))
app.notes.append(NO.normalize_note(_oth_note))
app.refresh_note_list()
app.update()
app.search_var.set('UniqueWordInCell')
t0 = time.time()
while time.time() - t0 < 0.4:
    app.update()
    time.sleep(0.02)
_texts = list_texts()
check('search finds a word living inside a table cell',
      'TableNote' in _texts)
check('and filters out the note that does not have it',
      'OtherNote' not in _texts)
app.search_var.set('')
app.update()
time.sleep(0.25)
app.update()

# ---- ROBUSTNESS: background pollers and timers survive the window closing ----
app2 = NO.NoteOrganizer(); app2._poll_active_dirty = lambda: None
app2.show_info = lambda *a, **k: True
app2.geometry('1100x850'); app2.update()
app2._export_state = {'current': 1, 'total': 5, 'done': False, 'error': None, 'save_path': ''}
app2.destroy()
try:
    app2._poll_export_progress()
    check('_poll_export_progress does not crash after the window closes', True)
except tk.TclError as e:
    check(f'_poll_export_progress does not crash after the window closes ({e})', False)

app3 = NO.NoteOrganizer(); app3._poll_active_dirty = lambda: None
app3.show_info = lambda *a, **k: True
app3.geometry('1100x850'); app3.update()
app3._import_state = {'phase': 'copying', 'current': 1, 'total': 5, 'done': False}
app3.destroy()
try:
    app3._poll_import_progress()
    check('_poll_import_progress does not crash after the window closes', True)
except tk.TclError as e:
    check(f'_poll_import_progress does not crash after the window closes ({e})', False)

app4 = NO.NoteOrganizer()
app4.show_info = lambda *a, **k: True
app4.geometry('1100x850'); app4.update()
app4.destroy()
try:
    app4._poll_active_dirty()
    check('_poll_active_dirty does not crash after the window closes', True)
except tk.TclError as e:
    check(f'_poll_active_dirty does not crash after the window closes ({e})', False)

app5 = NO.NoteOrganizer()
app5.show_info = lambda *a, **k: True
app5.geometry('1100x850'); app5.update()
app5.search_var.set('test')  # schedules the debounce timer
app5.destroy()  # close before it fires
try:
    app5.refresh_note_list()  # simulate the timer firing anyway
    check('refresh_note_list does not crash if called after the window closes', True)
except tk.TclError as e:
    check(f'refresh_note_list does not crash if called after the window closes ({e})', False)

# ---- Completeness pass: every remaining scheduled callback in the app ----
app6 = NO.NoteOrganizer(); app6._poll_active_dirty = lambda: None
app6.show_info = lambda *a, **k: True
app6.geometry('1100x850'); app6.update()
app6.new_note()
app6.title_entry.insert(0, 'x')
app6.destroy()
try:
    app6._autosave_now()
    check('_autosave_now does not crash after the window closes', True)
except tk.TclError as e:
    check(f'_autosave_now does not crash after the window closes ({e})', False)

app7 = NO.NoteOrganizer(); app7._poll_active_dirty = lambda: None
app7.show_info = lambda *a, **k: True
app7.geometry('1100x850'); app7.update()
app7.destroy()
try:
    app7.announce_startup_changes()
    check('announce_startup_changes does not crash after the window closes', True)
except tk.TclError as e:
    check(f'announce_startup_changes does not crash after the window closes ({e})', False)

app8 = NO.NoteOrganizer(); app8._poll_active_dirty = lambda: None
app8.show_info = lambda *a, **k: True
app8.geometry('1100x850'); app8.update()
app8.notes = [{'id': 1, 'title': 'Today', 'body': 'x', 'category': 'General',
              'date': datetime.now().strftime('%Y-%m-%d'), 'updated': '2026-01-01 00:00',
              'created': '2026-01-01 00:00', 'checklist': [], 'attachments': []}]
app8.destroy()
try:
    app8.maybe_show_reminder()
    check('maybe_show_reminder does not crash after the window closes', True)
except tk.TclError as e:
    check(f'maybe_show_reminder does not crash after the window closes ({e})', False)

# Left open across midnight, or woken from sleep the next day, the app asks
# for the new day's reminder and drops a bar still showing an earlier day.
# It asked only at start: "for today" stayed on yesterday's date.
app8b = NO.NoteOrganizer(); app8b._poll_active_dirty = lambda: None
app8b.geometry('1100x850'); app8b.update()
_md_today = datetime.now().strftime('%Y-%m-%d')
app8b.notes = [NO.normalize_note({'id': 1, 'title': 'Today', 'body': 'x', 'date': _md_today})]
_md_settings = NO.load_settings()
_md_settings.pop('reminder_last_shown', None)
NO.save_settings(_md_settings)
app8b._render_reminder_bar(3, '2026-01-01')
app8b._reminder_day = '2026-01-01'
app8b._watch_the_day(); app8b.update()
_md_said = [str(w.cget('text')) for w in app8b.reminder_bar.winfo_children()
            if isinstance(w, tk.Label)]
check(f"across midnight the new day's reminder replaces the old one ({_md_said})",
      app8b._reminder_bar_day == _md_today and any('1 note for today' in t for t in _md_said))
# ...with Settings open too. Settings unpacks the notebook, Tk refused to put
# the bar before it, the error left the day used up unseen, and the watch
# never looked again.
app8b.dismiss_reminder()
_md_settings = NO.load_settings()
_md_settings.pop('reminder_last_shown', None)
NO.save_settings(_md_settings)
app8b.show_settings_page(); app8b.update()
_md_errors = []
_md_report = app8b.report_callback_exception
app8b.report_callback_exception = lambda *a: _md_errors.append(str(a[1]))
_md_after = app8b.after
_md_rearmed = []
app8b.after = lambda ms, fn=None, *a: (_md_rearmed.append(ms) if fn == app8b._watch_the_day
                                       else None, _md_after(ms, fn, *a))[1]
try:
    app8b._reminder_day = '2026-01-01'
    try:
        app8b._watch_the_day()
    except Exception as _md_exc:   # this check's FAIL, not the suite's end
        _md_errors.append(repr(_md_exc))
    app8b.update()
finally:
    del app8b.after
    app8b.report_callback_exception = _md_report
check(f'with Settings open, the new day\'s reminder shows above it and the '
      f'watch goes on (errors {_md_errors}, re-armed {_md_rearmed})',
      not _md_errors and _md_rearmed == [60_000]
      and app8b.reminder_bar.winfo_manager() == 'pack'
      and NO.load_settings().get('reminder_last_shown') == _md_today)
app8b.hide_settings_page(); app8b.update()
app8b.destroy()
try:
    app8b._watch_the_day()
    check('the day watch does not crash after the window closes', True)
except tk.TclError as e:
    check(f'the day watch does not crash after the window closes ({e})', False)

app9 = NO.NoteOrganizer(); app9._poll_active_dirty = lambda: None
app9.show_info = lambda *a, **k: True
app9.geometry('1100x850'); app9.update()
app9.new_note()
app9.update()
sync_fn = app9._sync_editor_scroll
app9.destroy()
try:
    sync_fn()
    check('_sync_editor_scroll does not crash after the window closes', True)
except tk.TclError as e:
    check(f'_sync_editor_scroll does not crash after the window closes ({e})', False)

# ---- UNEXPECTED CALLBACK EXCEPTIONS: logged and surfaced, not silent ----
import os as _os
app10 = NO.NoteOrganizer(); app10._poll_active_dirty = lambda: None
app10.show_info = lambda *a, **k: True
app10.geometry('1100x850'); app10.update()

log_path = _os.path.join(NO.APP_DIR, 'crash_log.txt')
if _os.path.exists(log_path):
    _os.remove(log_path)

broken_btn = tk.Button(app10, text='Broken', command=lambda: 1 / 0)
broken_btn.pack()
app10.update()
broken_btn.invoke()
app10.update()

check('app does not crash on an unexpected callback exception', app10.winfo_exists())
check('the exception gets logged to crash_log.txt', _os.path.exists(log_path))
if _os.path.exists(log_path):
    with open(log_path) as f:
        log_content = f.read()
    check('the log contains the real error detail', 'ZeroDivisionError' in log_content)
check('a toast tells the user something went wrong', app10.toast_frame.winfo_ismapped())

# ---- BACKGROUND WORKER SAFETY: an unexpected error still resolves state["done"] ----
# Without this, a non-IOError exception mid-export/import used to kill the
# background thread silently, leaving the progress bar polling forever
# against a dict that would never say it was finished.
app11 = NO.NoteOrganizer(); app11._poll_active_dirty = lambda: None
app11.show_info = lambda *a, **k: True
app11.show_error = lambda *a, **k: True
app11.geometry('1100x850'); app11.update()
app11.notes = [{'id': 1, 'title': 'A', 'body': 'x', 'category': 'General',
               'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
               'checklist': [], 'attachments': []}]
app11.save_notes()

original_write = zipfile.ZipFile.write
zipfile.ZipFile.write = lambda self, *a, **k: (_ for _ in ()).throw(
    ValueError('deliberately unexpected, not IOError'))
export_path = os.path.join(tempfile.gettempdir(), 'qa8_export.zip')
import tkinter.filedialog as fd
fd.asksaveasfilename = lambda **k: export_path
app11.export_data()
app11.update()
t0 = time.time()
while app11._export_state is not None and time.time() - t0 < 120:
    app11.update()
    time.sleep(0.05)
zipfile.ZipFile.write = original_write
check('export resolves (not stuck forever) on an unexpected error type',
      app11._export_state is None)

app12 = NO.NoteOrganizer(); app12._poll_active_dirty = lambda: None
app12.show_info = lambda *a, **k: True
app12.show_error = lambda *a, **k: True
app12.ask_yes_no = lambda *a, **k: True
app12.geometry('1100x850'); app12.update()

backup_dir = tempfile.mkdtemp()
with open(os.path.join(backup_dir, 'notes_data.json'), 'w') as f:
    json.dump([{'id': 1, 'title': 'X', 'body': 'x'}], f)
os.makedirs(os.path.join(backup_dir, 'attachments'), exist_ok=True)
with open(os.path.join(backup_dir, 'attachments', 'fake.txt'), 'w') as f:
    f.write('x')
import_zip_path = os.path.join(tempfile.gettempdir(), 'qa8_import.zip')
with zipfile.ZipFile(import_zip_path, 'w') as zf:
    zf.write(os.path.join(backup_dir, 'notes_data.json'), 'notes_data.json')
    zf.write(os.path.join(backup_dir, 'attachments', 'fake.txt'), 'attachments/fake.txt')

original_listdir = os.listdir
def scoped_broken_listdir(path):
    # Narrowly scoped to only this test's own extracted temp path, so the
    # app's own startup/internal os.listdir calls elsewhere are unaffected.
    if 'notes_import_' in str(path) and 'attachments' in str(path):
        raise RuntimeError('deliberately unexpected, not IOError')
    return original_listdir(path)
os.listdir = scoped_broken_listdir
fd.askopenfilename = lambda **k: import_zip_path
app12.import_data()
app12.update()
t0 = time.time()
while app12._import_state is not None and time.time() - t0 < 120:
    app12.update()
    time.sleep(0.05)
os.listdir = original_listdir
check('import resolves (not stuck forever) on an unexpected error type',
      app12._import_state is None)

# ============================================================
# 13. AUTOSAVE IS MUTE: A BACKGROUND TIMER NEVER OPENS A DIALOG
# ============================================================
# The occurrence-scope prompt used to fire from the 500ms debounce while
# editing one day of a repeating series — every pause in typing raised a
# modal question, and one stacked on a manual save's own prompt became a
# frozen "ghost" save (see ISSUES_LOG). The timer then deferred a day's
# save to the next explicit gesture, which asked once -- and nothing said
# the edit waited (field report, 2026-10-12). A day now saves to itself,
# asking nothing, so the timer saves it like any note: still mute, never a
# question. Same contract for the "Empty note" warning on a comments-only
# note.
app13 = NO.NoteOrganizer(); app13._poll_active_dirty = lambda: None
app13.show_info = lambda *a, **k: True
app13.geometry('1100x850'); app13.update()

app13.notes = [{'id': 1, 'title': 'Series', 'body': 'base body', 'category': 'General',
                'date': '2026-07-01', 'recurrence': {'freq': 'daily'},
                'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
                'checklist': [], 'attachments': [], 'exceptions': [], 'overrides': {}}]
app13.save_notes()
app13.refresh_note_list(); app13.update()

scope_calls = []
app13.ask_occurrence_scope = lambda *a, **k: (scope_calls.append(1), 'occurrence')[1]

app13.load_note(app13.notes[0], occurrence_date='2026-07-09')
app13.update()
app13.body_text.insert('end', ' edited-for-the-day')
app13._autosave_now()  # the debounce timer's exact target
app13.update()
check('the background timer asks no occurrence-scope question', len(scope_calls) == 0)
check("the timer saves a day's edit to that day, the series untouched",
      'edited-for-the-day' not in app13.notes[0]['body']
      and 'edited-for-the-day' in
      app13.notes[0].get('overrides', {}).get('2026-07-09', {}).get('body', ''))
check('the edit stays in the editor as typed',
      'edited-for-the-day' in app13.body_text.get('1.0', 'end-1c'))

app13.body_text.insert('end', ' saved-on-purpose')
app13.save_current_note(auto=False)  # the explicit gesture
app13.update()
check('the explicit save asks nothing either', len(scope_calls) == 0)
check("...and lands as that day's own edit",
      'saved-on-purpose' in
      app13.notes[0].get('overrides', {}).get('2026-07-09', {}).get('body', ''))

# The flush gesture (note switch / close) saves too, asking nothing.
app13.body_text.insert('end', ' second-round')
app13._flush_autosave(); app13.update()
check('the flush gesture saves the pending edit, asking nothing',
      len(scope_calls) == 0
      and 'second-round' in app13.notes[0]['overrides']['2026-07-09']['body'])

# Ordinary notes keep the silent background autosave untouched.
app13.notes.append({'id': 2, 'title': 'Plain', 'body': 'plain body', 'category': 'General',
                    'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
                    'checklist': [], 'attachments': []})
app13.save_notes()
app13.load_note(app13.find_note(2)); app13.update()
app13.body_text.insert('end', ' still-autosaves')
app13._autosave_now(); app13.update()
check('a plain note still autosaves silently from the timer',
      'still-autosaves' in app13.find_note(2)['body'] and len(scope_calls) == 0)

# A recurring note opened as the SERIES (no occurrence date) too.
app13.load_note(app13.find_note(1)); app13.update()
app13.body_text.insert('end', ' series-edit')
app13._autosave_now(); app13.update()
check('a series view still autosaves silently from the timer',
      'series-edit' in app13.find_note(1)['body'] and len(scope_calls) == 0)

# Every gesture that empties the editor flushes first — Ctrl+N and the
# calendar's "Add note for this day" once skipped that, silently
# discarding whatever the debounce hadn't caught (and, when a day waited
# for a question, that day's session in full).
app13.load_note(app13.find_note(1), occurrence_date='2026-07-10'); app13.update()
app13.body_text.insert('end', ' ctrl-n-pending')
app13._shortcut_new_note()
app13.update()
check('Ctrl+N saves the pending edit of a day before clearing, asking nothing',
      len(scope_calls) == 0
      and 'ctrl-n-pending' in app13.notes[0]['overrides']['2026-07-10']['body'])
check('Ctrl+N then really starts fresh', app13.selected_note_id is None)

app13.render_calendar(); app13.update()
app13.load_note(app13.find_note(1), occurrence_date='2026-07-11'); app13.update()
app13.body_text.insert('end', ' cal-add-pending')
app13._add_note_for_date('2026-08-15')
app13.update()
check('calendar add-note saves the pending edit of a day before clearing, '
      'asking nothing',
      len(scope_calls) == 0
      and 'cal-add-pending' in app13.notes[0]['overrides']['2026-07-11']['body'])
_ca_ok = False
for _ in range(60):  # settle: a late timer tick may still be landing
    # Shown as every date in the field is, day first.
    if (app13.selected_note_id is None
            and app13.date_entry.get() == '15.08.2026'):
        _ca_ok = True
        break
    app13.update()
    time.sleep(0.02)
check('calendar add-note prefills the chosen date on a fresh editor '
      f'(id={app13.selected_note_id!r}, date={app13.date_entry.get()!r})',
      _ca_ok)

# A comments-only note is REAL CONTENT now (the product review found it
# silently discarded on every route, with a false "Write something" on
# Ctrl+S — the T0-5 family): the timer saves it quietly and the explicit
# Save agrees. The junk guard keeps its ground where it belongs, on a
# truly EMPTY never-saved editor: the timer stays mute and saves
# nothing, and only the explicit Save speaks up.
warned13 = []
app13.show_warning = lambda t, m: warned13.append(t)
app13.open_blank_tab(); app13.update()
app13.comments_text.insert('1.0', 'only a comment')
app13._autosave_now(); app13.update()
check('a comments-only note raises no warning from the timer', warned13 == [])
check('and IS saved now — comments are content, not junk',
      app13.selected_note_id is not None
      and app13.find_note(app13.selected_note_id)['comments'] == 'only a comment')
app13.save_current_note(auto=False); app13.update()
check('the explicit Save agrees: no false "Write something"', warned13 == [])
app13.open_blank_tab(); app13.update()
app13._autosave_now(); app13.update()
check('a truly empty editor still saves nothing from the timer, silently',
      warned13 == [] and app13.selected_note_id is None)
app13.save_current_note(auto=False); app13.update()
check('and the explicit Save still warns about THAT one',
      warned13 == ['Empty note'])

# House rule: un-shadow the real methods rather than leaving section mocks
# behind for a future section 14 to inherit.
del app13.ask_occurrence_scope
del app13.show_warning

# ---- A swallowed autosave exception leaves a TRACE (audit Z02-F04) ----
# The spine's guards used to be bare `pass` — a persistent bug there
# silently stopped autosave with nothing in any log.
_swl_path = os.path.join(NO.APP_DIR, 'crash_log.txt')
_swl_before = (open(_swl_path, encoding='utf-8').read()
               if os.path.exists(_swl_path) else '')
_real_uwc13 = app13.update_word_count
app13.update_word_count = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('autosave probe'))
try:
    app13._schedule_autosave()
finally:
    app13.update_word_count = _real_uwc13
_swl_after = (open(_swl_path, encoding='utf-8').read()
              if os.path.exists(_swl_path) else '')
_swl_new = _swl_after[len(_swl_before):]
check('a swallowed autosave exception lands in crash_log.txt',
      '(swallowed: autosave' in _swl_new and 'autosave probe' in _swl_new)
check('and the schedule itself survived it',
      getattr(app13, '_autosave_job', None) is not None)
if getattr(app13, '_autosave_job', None):
    app13.after_cancel(app13._autosave_job)
    app13._autosave_job = None
# Bounded growth: the SAME spot logs once per session, not per keystroke.
_swl_mid = open(_swl_path, encoding='utf-8').read()
app13.update_word_count = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('again'))
try:
    app13._schedule_autosave()
finally:
    app13.update_word_count = _real_uwc13
check('the same spot logs only once per session (bounded growth)',
      open(_swl_path, encoding='utf-8').read() == _swl_mid)
if getattr(app13, '_autosave_job', None):
    app13.after_cancel(app13._autosave_job)
    app13._autosave_job = None
# The WORST silent spot an audit found: a save failing at flush time
# (note-switch/close) — that trace must exist too.
app13.new_note()
app13.body_text.insert('1.0', 'something to save')
_real_save13 = app13.save_current_note
app13.save_current_note = lambda *a, **k: (_ for _ in ()).throw(
    RuntimeError('flush save probe'))
try:
    app13._flush_autosave()
finally:
    app13.save_current_note = _real_save13
_swl_end = open(_swl_path, encoding='utf-8').read()
check('a flush-time save failure leaves a trace',
      '(swallowed: flush: save_current_note' in _swl_end
      and 'flush save probe' in _swl_end)

# The autosave's "Note updated" is only reassurance, and it yields to what
# matters more: an Undo offer, and now an error. A failed action followed
# within the save delay by an autosave had its "something went wrong"
# covered by a green tick, and the one message that mattered was gone.
_tw_app = app13
_tw_app._show_toast("Something went wrong with that", kind="error")
_tw_app._show_toast("Note updated", yield_to_action=True)
_tw_app.update()
check('an error banner is not covered by the autosave\'s reassurance',
      str(_tw_app.toast_lbl.cget('text')).endswith('Something went wrong with that'))
_tw_app._show_toast("A later, deliberate message")
_tw_app.update()
check('...while a message that does not yield still replaces it',
      str(_tw_app.toast_lbl.cget('text')).endswith('A later, deliberate message'))

# ============================================================
# 14. THE READERS OF THE BODY: THE TEXT READ ONCE, NOT ONCE A LINE
# ============================================================
# Tk's get costs about the square of the tag toggles on the line it reads,
# and the find bar's hits, the spelling's underlines and the note's own
# spans all add toggles. A save read each line about seventeen times, and
# one index per styled piece's end: with the find bar open on a long
# paragraph every pause froze the window for seconds. The square is Tk's
# own, inside each read, so the work is COUNTED
# here -- the reads and what they returned -- each shape against its half.
import random as _rd_random
from noteorganizer.core import spelling as _rd_spelling
app14 = NO.NoteOrganizer(); app14._poll_active_dirty = lambda: None
app14.show_info = lambda *a, **k: True
app14.geometry('1100x850'); app14.update()
app14.notes = []
app14.save_notes()


class _RdCounting:
    """Stands in for the body's interpreter: every call counted, every get
    with the characters it returned, and every search."""

    def __init__(self, real):
        self.real, self.calls, self.gets, self.got = real, 0, 0, 0
        self.searches = 0

    def call(self, *args):
        self.calls += 1
        out = self.real.call(*args)
        # Text.search hands its words over as one tuple, Text.get as
        # arguments: asked as either, a call is the same question.
        words = args[0] if len(args) == 1 and isinstance(args[0], tuple) else args
        if len(words) > 1 and words[1] == 'get':
            self.gets += 1
            self.got += len(out) if isinstance(out, str) else 0
        if len(words) > 1 and words[1] == 'search':
            self.searches += 1
        return out

    def __getattr__(self, name):
        return getattr(self.real, name)


def _rd_counted(fn):
    w = app14.body_text
    real = w.tk
    counting = w.tk = _RdCounting(real)
    try:
        fn()
    finally:
        w.tk = real
    return counting


_rd_ids = iter(range(1, 10 ** 6))


def _rd_open(body, formatting=(), paragraphs=()):
    """A note opened from a blank editor, and the work the opening took."""
    note = NO.normalize_note({'id': next(_rd_ids), 'title': 'reads', 'body': body,
                              'formatting': list(formatting),
                              'paragraphs': list(paragraphs)})
    app14.notes.append(note)
    app14.open_blank_tab(); app14.update()
    work = _rd_counted(lambda: app14.open_note_in_tab(note))
    app14.update()
    return note, work


def _rd_bold_words(line_starts, words):
    return [{'start': base + 10 * i, 'end': base + 10 * i + 4, 'style': 'bold'}
            for base in line_starts for i in range(words)]


def _rd_saved(fn):
    """One edit at the end of line 1 and *fn* to save it: the work, and
    whether the edit reached the note."""
    app14.body_text.insert('1.end', 'Q')
    work = _rd_counted(fn)
    body = app14.find_note(app14.selected_note_id)['body']
    return work, body.split('\n')[0].endswith('Q')


def _rd_find_open_save(words):
    """The find bar over styled words: one paragraph of "word " repeated,
    every other word bold, the find bar open on "word", and one pause's
    save."""
    _rd_open('word ' * words, _rd_bold_words([0], words // 2))
    app14._open_find()
    app14._find_case.set(False)
    app14._find_var.set('word')
    app14._find_rescan(reveal=False)
    app14.update()
    hits = len(app14._find_matches)
    work, saved = _rd_saved(app14._autosave_now)
    length = len(app14.body_text.get('1.0', 'end-1c'))
    app14._close_find()
    app14.update()
    return hits, work, length, saved


_rd_h = _rd_find_open_save(1000)
_rd_w = _rd_find_open_save(2000)
check(f'a pause\'s save, the find bar open on a long paragraph, reads the note '
      f'twice whatever its hits ({_rd_h[0]} hits: {_rd_h[1].gets} reads, '
      f'{_rd_h[1].got:,} characters of {_rd_h[2]:,}; {_rd_w[0]} hits: '
      f'{_rd_w[1].gets} reads, {_rd_w[1].got:,} of {_rd_w[2]:,})',
      _rd_h[0] == 1000 and _rd_w[0] == 2000 and _rd_h[3] and _rd_w[3]
      and _rd_h[1].gets == _rd_w[1].gets == 2
      and _rd_w[1].got <= 2 * _rd_w[2] + 2)
check(f'...and asks Tk as many questions for twice the hits '
      f'({_rd_h[1].calls}, {_rd_w[1].calls})',
      _rd_h[1].calls == _rd_w[1].calls)


def _rd_lines_at_ceiling(lines):
    """*lines* lines, each with 200 bold words on it and centred."""
    line = ('word ' * 400).rstrip()
    starts = [i * (len(line) + 1) for i in range(lines)]
    _note, opened = _rd_open('\n'.join([line] * lines), _rd_bold_words(starts, 200),
                             [{'line': i, 'align': 'center'} for i in range(lines)])
    saved = _rd_saved(app14._autosave_now)
    leaving = _rd_saved(lambda: app14._flush_autosave(leaving=False))
    bold = len(app14.body_text.tag_ranges('bold')) // 2
    # Every line selected: the bullet button, then Tab.
    app14.body_text.tag_add('sel', '1.0', 'end-1c')
    listed = _rd_counted(lambda: app14._toggle_list('bullet'))
    indented = _rd_counted(lambda: app14._change_paragraph_indent(1))
    app14.body_text.tag_remove('sel', '1.0', 'end')
    made = [(app14._list_kind_of(app14.body_text, n), app14._paragraph_indent_of(app14.body_text, n))
            for n in range(1, lines + 1)]
    return opened, saved, leaving, bold, listed, indented, made


_rd_4 = _rd_lines_at_ceiling(4)
_rd_8 = _rd_lines_at_ceiling(8)
check(f'opening a note reads it the same few times however many styled lines it '
      f'holds ({_rd_4[3]} bold words: {_rd_4[0].gets} reads, {_rd_8[3]}: '
      f'{_rd_8[0].gets})',
      _rd_4[3] == 800 and _rd_8[3] == 1600 and _rd_4[0].gets == _rd_8[0].gets <= 6)
check(f'...and saving it twice, at a pause and on the way out, whatever its lines '
      f'({_rd_4[1][0].gets} and {_rd_4[2][0].gets} reads; {_rd_8[1][0].gets} and '
      f'{_rd_8[2][0].gets})',
      _rd_4[1][0].gets == _rd_8[1][0].gets == 2 and _rd_4[1][1] and _rd_8[1][1]
      and _rd_4[2][0].gets == _rd_8[2][0].gets == 2 and _rd_4[2][1] and _rd_8[2][1])
check(f'the bullet button and Tab over every line read them in one piece '
      f'({_rd_4[4].gets} and {_rd_4[5].gets} reads for 4 lines, {_rd_8[4].gets} and '
      f'{_rd_8[5].gets} for 8)',
      _rd_4[4].gets == _rd_8[4].gets and _rd_4[5].gets == _rd_8[5].gets
      and _rd_8[6] == [('bullet', 1)] * 8)
# A paste, an Enter or a Ctrl+Z puts every line's list margin right again,
# and a list's numbers; Ctrl+C reads the styles of what it copies.
_rd_tags = _rd_counted(app14._resync_list_tags)
_rd_numbers = _rd_counted(app14._renumber_lists)
app14.body_text.tag_add('sel', '2.0', '6.10')
_rd_copy = _rd_counted(app14._copy_formatted)
app14.body_text.tag_remove('sel', '1.0', 'end')
check(f'every line\'s list margin, the numbers, and a copy\'s styles each come from '
      f'one read of the note ({_rd_tags.gets}, {_rd_numbers.gets}, {_rd_copy.gets} '
      f'with the selection\'s own)',
      _rd_tags.gets == 1 and _rd_numbers.gets == 1 and _rd_copy.gets == 2)

# A key or a click runs the format buttons' refresh: the caret's line once,
# and only as far as a list marker or a table row is told from it.
_rd_open('word ' * 2000, _rd_bold_words([0], 500))
app14.body_text.mark_set('insert', '1.5000')
_rd_key = _rd_counted(app14._refresh_format_buttons)
check(f'a key or a click reads the caret\'s line once, and only its start '
      f'({_rd_key.gets} reads, {_rd_key.got} characters of 10,000)',
      _rd_key.gets == 1 and _rd_key.got <= app14._LINE_HEAD)
_rd_heads = ['• ' + 'word ' * 30, '12. ' + 'word ' * 30, '7' * 70 + '. after',
             '7' * 63 + '. after', ' ' * 70 + '| a | b |', '| ' + 'cell ' * 20 + '| b |',
             '| ' + 'cell ' * 20 + 'no end', '▪ x', 'short', '', ' ' * 80]
app14.open_blank_tab(); app14.update()
app14.body_text.insert('1.0', '\n'.join(_rd_heads))
_rd_wrong = []
for _n in range(1, len(_rd_heads) + 1):
    _full = app14.body_text.get(f'{_n}.0', f'{_n}.end')
    _head = app14._line_head(_n)
    if (NO.parse_list_marker(_head)[0] != NO.parse_list_marker(_full)[0]
            or NO.is_table_row(_head) != NO.is_table_row(_full)
            or app14._bullet_depth(_head) != app14._bullet_depth(_full)):
        _rd_wrong.append((_n, _head[:12], _full[:12], len(_head), len(_full)))
check(f'a line\'s start tells its list marker, depth and table row as the whole '
      f'line does, a long run of digits or spaces read whole ({_rd_wrong})',
      not _rd_wrong and NO.is_table_row(app14.body_text.get('5.0', '5.end'))
      and NO.is_table_row(app14.body_text.get('6.0', '6.end'))
      and NO.parse_list_marker(app14.body_text.get('3.0', '3.end'))[0] == 'number'
      and NO.parse_list_marker(app14.body_text.get('4.0', '4.end'))[0] == 'number')
app14.body_text.delete('1.0', 'end')

# A key's word count waits for the pause while the find bar shows hits: its
# read of the note cost each key a quarter of a second on row 9. The pause's
# save counts from its own read, and closing the bar counts at once.
_rd_open('word ' * 2000, _rd_bold_words([0], 500))
app14._open_find()
app14._find_case.set(False)
app14._find_var.set('word')
app14._find_rescan(reveal=False)
app14.update()
app14.body_text.mark_set('insert', '1.end')


def _rd_type(text):
    app14.body_text.insert('insert', text)
    app14._schedule_autosave()
    app14._refresh_format_buttons()


def _rd_count_says():
    words = len(app14.body_text.get('1.0', 'end-1c').split())
    return str(app14.word_count_lbl.cget('text')).startswith(f'{words} words')


_rd_typed = _rd_counted(lambda: _rd_type('Q'))
_rd_waited = not _rd_count_says()
app14._cancel_pending_autosave()
app14._autosave_now()
_rd_at_pause = _rd_count_says()
_rd_type(' new')
_rd_before_close = _rd_count_says()
app14._cancel_pending_autosave()
app14._close_find()
app14.update()
_rd_at_close = _rd_count_says()
_rd_type(' more')
_rd_closed_live = _rd_count_says()
app14._cancel_pending_autosave()
check(f'a key with the find bar open on a long paragraph reads no more of the note than '
      f'its caret line\'s start ({_rd_typed.gets} reads, {_rd_typed.got} characters)',
      _rd_typed.got <= app14._LINE_HEAD and _rd_waited)
check(f'...and the word count is right after the pause, and the moment the bar closes '
      f'(pause {_rd_at_pause}, before closing {_rd_before_close}, closed '
      f'{_rd_at_close}, typing with it closed {_rd_closed_live})',
      _rd_at_pause and not _rd_before_close and _rd_at_close and _rd_closed_live)

# Letters typed onto a bold word wear its bold up to a space typed with them,
# the space found among the letters typed: Tk's search for it read the whole
# line, 0.29 s a key with the find bar open on row 9.
_rd_open('word ' * 2000, _rd_bold_words([0], 500))
app14._open_find()
app14._find_case.set(False)
app14._find_var.set('word')
app14._find_rescan(reveal=False)
app14.update()
_rd_b = app14.body_text
_rd_b.mark_set('insert', '1.4')
_rd_b.mark_set(app14._TYPED_FROM, 'insert')
_rd_b.mark_gravity(app14._TYPED_FROM, 'left')
_rd_b.mark_set(app14._TYPED_TO, 'insert')
_rd_b.mark_gravity(app14._TYPED_TO, 'right')
app14._typed_run_open = True
_rd_b.insert('insert', 'er x')
_rd_spread = _rd_counted(app14._spread_typed_run)
_rd_spread_bold = ['bold' in _rd_b.tag_names(f'1.{c}') for c in range(4, 8)]
app14._close_find()
app14.update()
check(f'letters typed onto a bold word, the find bar open on row 9, are styled up to '
      f'the space typed with them, asking Tk nothing over the whole line '
      f'({_rd_spread.searches} searches, {_rd_spread.got} characters read; bold {_rd_spread_bold})',
      _rd_spread.searches == 0 and _rd_spread.got <= 8
      and _rd_spread_bold == [True, True, False, False])


def _rd_uniform(words):
    """One paragraph set bold in one size, colour and highlight, all selected."""
    body = ('word ' * words).rstrip()
    _rd_open(body, [{'start': 0, 'end': len(body), 'style': 'bold'},
                    {'start': 0, 'end': len(body), 'style': 'font_size', 'value': 14},
                    {'start': 0, 'end': len(body), 'style': 'text_color', 'value': '#aa0000'},
                    {'start': 0, 'end': len(body), 'style': 'highlight', 'value': '#ffff00'}])
    app14.body_text.tag_add('sel', '1.0', 'end-1c')
    work = _rd_counted(app14._refresh_format_buttons)
    shown = (app14.font_size_var.get(),
             str(app14.text_color_btn.cget('bg')).lower(),
             str(app14.highlight_btn.cget('bg')).lower())
    app14.body_text.tag_remove('sel', '1.0', 'end')
    return work, shown


_rd_u1 = _rd_uniform(400)
_rd_u2 = _rd_uniform(800)
check(f'the format buttons read a selection by its styles\' ranges, not its '
      f'characters ({_rd_u1[0].calls} questions for 400 words, {_rd_u2[0].calls} '
      f'for 800)', _rd_u1[0].calls == _rd_u2[0].calls)
check(f'...and still show its size and colours ({_rd_u2[1]})',
      _rd_u1[1] == _rd_u2[1] == ('14', '#aa0000', '#ffff00'))


# The answers by ranges, against the character walk they replaced (its
# own code, here as the oracle), on styles laid every way a note lays them.
def _rd_walk_has(w, styles, start, end):
    idx = start
    while w.compare(idx, '<', end):
        if not (set(w.tag_names(idx)) & styles):
            return False
        idx = w.index(f'{idx}+1c')
    return True


def _rd_walk_font(w, style, start, end):
    wanted, idx = None, start
    while w.compare(idx, '<', end):
        found = None
        for name in w.tag_names(idx):
            parsed = NO.parse_font_tag(name)
            if parsed:
                found = parsed[2] if style == 'font_size' else parsed[3]
                break
        if found is None:
            return None
        if wanted is None:
            wanted = found
        elif wanted != found:
            return None
        idx = w.index(f'{idx}+1c')
    return wanted


def _rd_walk_colour(w, kind, start, end):
    prefix, color, idx = kind + '_', None, start
    while w.compare(idx, '<', end):
        if w.get(idx) == '\n':
            idx = w.index(f'{idx}+1c')
            continue
        names = [n for n in w.tag_names(idx) if n.startswith(prefix)]
        if not names:
            return None
        if color is None:
            color = '#' + names[0][len(prefix):]
        elif color != '#' + names[0][len(prefix):]:
            return None
        idx = w.index(f'{idx}+1c')
    return color


_rd_r = _rd_random.Random(14)
_rd_lines = ['short line', '', 'a longer line of plain words', '\U0001F600 an emoji here',
             'bold and italic mixed', '', '', 'last words']
_rd_body = '\n'.join(_rd_lines)
_rd_head = len('\n'.join(_rd_lines[:4]))
_rd_spans = []
for _ in range(40):
    _s = _rd_r.randint(0, _rd_head - 1)
    _e = min(_rd_head, _s + _rd_r.randint(1, 25))
    _rd_spans.append(_rd_r.choice([
        {'start': _s, 'end': _e, 'style': 'bold'},
        {'start': _s, 'end': _e, 'style': 'italic'},
        {'start': _s, 'end': _e, 'style': 'underline'},
        {'start': _s, 'end': _e, 'style': 'font_size', 'value': _rd_r.choice([12, 18])},
        {'start': _s, 'end': _e, 'style': 'font_family', 'value': 'Georgia'},
        {'start': _s, 'end': _e, 'style': 'text_color', 'value': '#aa0000'},
        {'start': _s, 'end': _e, 'style': 'highlight', 'value': '#00ff00'}]))
_rd_open(_rd_body, _rd_spans)
_rd_b = app14.body_text
# Over the random styles of lines 1-4: a colour across lines, covering their
# breaks, and a find hit. On lines 5-8, nothing random: a highlight across
# lines, which leaves their breaks bare, and two sizes laid over one
# stretch, where the one lower in priority speaks for it.
_rd_b.tag_add(app14._ensure_color_tag(_rd_b, 'text_color', '#0000cc'), '1.0', '4.5')
_rd_b.tag_add('find_all', '3.0', '3.6')
app14._tag_add_no_newline(_rd_b, app14._ensure_color_tag(_rd_b, 'highlight', '#ffff00'),
                          '5.0', '8.4')
_rd_b.tag_add(app14._ensure_font_tag(_rd_b, False, False, 20, None), '5.2', '5.20')
_rd_b.tag_add(app14._ensure_font_tag(_rd_b, True, False, 16, 'Georgia'), '5.10', '5.21')
_rd_text = _rd_b.get('1.0', 'end-1c')
_rd_bad = []
for _ in range(300):
    _s = _rd_r.randint(0, len(_rd_text))
    _e = min(len(_rd_text), _s + _rd_r.choice([0, 1, 2, 5, 12, 40, 200]))
    _si, _ei = _rd_b.index(f'1.0+{_s}c'), _rd_b.index(f'1.0+{_e}c')
    for _styles in ({'bold', 'bold_italic'}, {'italic', 'bold_italic'}, {'underline'}):
        if app14._selection_has_style(_rd_b, _styles, _si, _ei) != _rd_walk_has(
                _rd_b, _styles, _si, _ei):
            _rd_bad.append(('has', sorted(_styles), _si, _ei))
    for _style in ('font_size', 'font_family'):
        if app14._uniform_font_in_selection(_style, _si, _ei) != _rd_walk_font(
                _rd_b, _style, _si, _ei):
            _rd_bad.append(('font', _style, _si, _ei))
    for _kind in ('text_color', 'highlight'):
        if app14._uniform_color_in_selection(_kind, _si, _ei) != _rd_walk_colour(
                _rd_b, _kind, _si, _ei):
            _rd_bad.append(('colour', _kind, _si, _ei))
check(f'the format buttons answer as the character walk did, over 300 selections '
      f'({len(_rd_bad)} differ: {_rd_bad[:3]})', not _rd_bad)
check('...among them a highlight across lines and two sizes over one stretch',
      app14._uniform_color_in_selection('highlight', '5.0', '8.4') == '#ffff00'
      and app14._uniform_font_in_selection('font_size', '5.12', '5.18')
      == _rd_walk_font(_rd_b, 'font_size', '5.12', '5.18') == 20)

# Lists, depths and alignments read from each tag once agree with the line
# by line answers they replaced, a margin tag lost or doubled included.
_rd_open('\n'.join(['• one', '◦ two', '1. three', 'plain', '', '▪ four',
                    'centred', '2. five', 'last']),
         paragraphs=[{'line': 0, 'kind': 'bullet'}, {'line': 1, 'kind': 'bullet', 'indent': 1},
                     {'line': 2, 'kind': 'number', 'indent': 2, 'align': 'right'},
                     {'line': 3, 'indent': 3}, {'line': 4, 'align': 'center'},
                     {'line': 6, 'align': 'center'}, {'line': 7, 'kind': 'number'},
                     {'line': 8, 'align': 'right'}])
_rd_b.tag_add(app14._paragraph_tag(_rd_b, None, 1), '4.0', '4.end')
_rd_b.tag_add(app14._paragraph_tag(_rd_b, 'bullet', 3), '4.0', '4.end')
for _name in _rd_b.tag_names('6.0'):
    if _name.startswith('para_'):
        _rd_b.tag_remove(_name, '6.0', '6.end+1c')
_rd_by_line = []
for _n in range(1, int(_rd_b.index('end-1c').split('.')[0]) + 1):
    _kind = app14._list_kind_of(_rd_b, _n)
    _align = app14._paragraph_align_of(_rd_b, _n)
    _indent = app14._paragraph_indent_of(_rd_b, _n)
    if _kind or _align != 'left' or _indent:
        _entry = {'line': _n - 1}
        if _kind:
            _entry['kind'] = _kind
        if _indent:
            _entry['indent'] = _indent
        if _align != 'left':
            _entry['align'] = _align
        _rd_by_line.append(_entry)
_rd_paras = app14._extract_paragraphs(_rd_b)
check(f'a note\'s lists and alignments read from each tag once are the line by line '
      f'answers ({_rd_paras})',
      _rd_paras == _rd_by_line and len(_rd_paras) >= 8)

# Offsets counted in Python are len(get("1.0", index)) at every column, past
# an emoji, a drawn table's window and the tags no save reads.
_rd_probe = NO.tk.Text(app14)
_rd_probe.insert('1.0', '\U0001F600a\U0001F680 two\nplain line\n\U0001F914\U0001F914 x\n\nend')
_rd_probe.window_create('2.3', window=NO.tk.Label(_rd_probe, text='x'))
_rd_probe.window_create('3.0', window=NO.tk.Label(_rd_probe, text='y'))
_rd_probe.tag_add('find_all', '1.0', '2.6')
_rd_all = [_rd_probe.index(f'{_l}.{_c}') for _l in range(1, 7) for _c in range(0, 16)]
_rd_all.append(_rd_probe.index('end'))
_rd_off = app14._char_offsets(_rd_probe, _rd_all)
_rd_odd = [(i, _rd_off.get(str(i)), app14._char_offset(_rd_probe, i)) for i in _rd_all
           if _rd_off.get(str(i)) != app14._char_offset(_rd_probe, i)]
check(f'offsets counted on one read are the ones each index read gives, at every '
      f'column ({len(_rd_odd)} differ: {_rd_odd[:3]})', not _rd_odd)
_rd_probe.destroy()


# The spelling's underlines: no more than a line, and a box, may hold --
# those nearest the caret -- and a save beside them reads the note twice.
class _RdSpeller:
    tag = 'en-US'

    def errors(self, text):
        out, at = [], text.find('teh')
        while at != -1:
            out.append((_rd_spelling.utf16_units(text[:at]), 3))
            at = text.find('teh', at + 1)
        return out

    def suggest(self, word, limit=5):
        return []

    def add(self, word):
        return True


def _rd_look():
    w = app14.body_text
    app14._spell_run(w)
    for _ in range(2000):
        if getattr(w, '_spell_job', None) is None:
            break
        app14.update()
    ranges = w.tag_ranges(app14.SPELL_TAG)
    return [(str(a), str(b)) for a, b in zip(ranges[::2], ranges[1::2])]


app14._spellers_found = [_RdSpeller()]
_rd_on = NO.get_setting(_rd_spelling.SPELLING_SETTING, True)
NO.save_setting(_rd_spelling.SPELLING_SETTING, True)
try:
    _rd_open('The cat sat on teh mat. ' * 1200)
    app14.body_text.mark_set('insert', '1.end')
    _rd_marks = _rd_look()
    _rd_last = int(_rd_marks[-1][0].split('.')[1]) if _rd_marks else -1
    check(f'a long line of typos is underlined no more than a line may hold, those '
          f'nearest the caret ({len(_rd_marks)} underlines, the last at {_rd_last})',
          len(_rd_marks) == _rd_spelling.MAX_UNDERLINES_PER_LINE
          and _rd_last == len('The cat sat on teh mat. ') * 1199 + len('The cat sat on '))
    _rd_spell_save = _rd_saved(app14._autosave_now)
    check(f'...and a pause\'s save beside them reads the note twice '
          f'({_rd_spell_save[0].gets} reads)',
          _rd_spell_save[0].gets == 2 and _rd_spell_save[1])
    _rd_open('\n'.join(['Teh cat sat on teh mat. ' * 400] * 6))
    app14.body_text.mark_set('insert', '1.0')
    _rd_marks = _rd_look()
    _rd_per = {}
    for _a, _b in _rd_marks:
        _rd_per[_a.split('.')[0]] = _rd_per.get(_a.split('.')[0], 0) + 1
    check(f'...and a note of such lines no more than a box may hold in all '
          f'({len(_rd_marks)} underlines, {_rd_per})',
          len(_rd_marks) == _rd_spelling.MAX_UNDERLINES
          and max(_rd_per.values()) <= _rd_spelling.MAX_UNDERLINES_PER_LINE
          and sorted(_rd_per) == ['1', '2', '3', '4', '5'])
finally:
    app14._spellers_found = []
    NO.save_setting(_rd_spelling.SPELLING_SETTING, _rd_on)
    app14.body_text.tag_remove(app14.SPELL_TAG, '1.0', 'end')

print()
print(f"=== QA8 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
