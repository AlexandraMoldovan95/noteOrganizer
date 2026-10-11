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

def find_all_labels(w, acc=None):
    if acc is None: acc = []
    for c in w.winfo_children():
        if isinstance(c, tk.Label): acc.append(str(c.cget('text')))
        find_all_labels(c, acc)
    return acc


def list_texts():
    """What the note list says: every drawn card's title, and every
    header's label -- the list is a drawing, with no labels to walk."""
    out = [app._card_view(n)['title'] for n in app._card_order()]
    out += [app._header_view(c)['label'] for c in app._group_headers]
    return out


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
while app11._export_state is not None and time.time() - t0 < 8:
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
while app12._import_state is not None and time.time() - t0 < 8:
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
# frozen "ghost" save (see ISSUES_LOG). The timer path now defers that
# save to the next explicit gesture (Save / note switch / close), which
# asks exactly once. Same contract for the "Empty note" warning on a
# comments-only note.
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
check('the deferred edit is not yet in the store',
      'edited-for-the-day' not in app13.notes[0]['body']
      and 'edited-for-the-day' not in
      app13.notes[0].get('overrides', {}).get('2026-07-09', {}).get('body', ''))
check('the edit survives in the editor, waiting for a gesture',
      'edited-for-the-day' in app13.body_text.get('1.0', 'end-1c'))

app13.save_current_note(auto=False)  # the explicit gesture
app13.update()
check('the explicit save asks exactly once', len(scope_calls) == 1)
check("the deferred edit lands as that day's override",
      'edited-for-the-day' in
      app13.notes[0].get('overrides', {}).get('2026-07-09', {}).get('body', ''))

# The flush gesture (note switch / close) also asks and saves.
app13.body_text.insert('end', ' second-round')
app13._autosave_now(); app13.update()
check('the timer stays mute on the second round too', len(scope_calls) == 1)
app13._flush_autosave(); app13.update()
check('the flush gesture asks and saves the pending edit',
      len(scope_calls) == 2
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
      'still-autosaves' in app13.find_note(2)['body'] and len(scope_calls) == 2)

# A recurring note opened as the SERIES (no occurrence date) too.
app13.load_note(app13.find_note(1)); app13.update()
app13.body_text.insert('end', ' series-edit')
app13._autosave_now(); app13.update()
check('a series view still autosaves silently from the timer',
      'series-edit' in app13.find_note(1)['body'] and len(scope_calls) == 2)

# Every gesture that empties the editor flushes first — Ctrl+N and the
# calendar's "Add note for this day" once skipped that, silently
# discarding whatever the debounce hadn't caught (and a deferred
# occurrence session in full).
app13.load_note(app13.find_note(1), occurrence_date='2026-07-10'); app13.update()
app13.body_text.insert('end', ' ctrl-n-pending')
app13._shortcut_new_note()
app13.update()
check('Ctrl+N asks and saves the deferred edit before clearing',
      len(scope_calls) == 3
      and 'ctrl-n-pending' in app13.notes[0]['overrides']['2026-07-10']['body'])
check('Ctrl+N then really starts fresh', app13.selected_note_id is None)

app13.render_calendar(); app13.update()
app13.load_note(app13.find_note(1), occurrence_date='2026-07-11'); app13.update()
app13.body_text.insert('end', ' cal-add-pending')
app13._add_note_for_date('2026-08-15')
app13.update()
check('calendar add-note asks and saves the deferred edit before clearing',
      len(scope_calls) == 4
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
# The audit's WORST silent spot: a save failing at flush time
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

print()
print(f"=== QA8 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
