import sys
import note_organizer as NO, tkinter as tk, time, os, tempfile, zipfile, json, shutil
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
card_ids_before = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
typed = ''
for ch in 'Note1':
    typed += ch
    app.search_var.set(typed)
    app.update()
card_ids_immediately_after = {nid: str(info['card']) for nid, info in app._note_card_widgets.items()}
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
texts = find_all_labels(app.list_frame)
check('after the debounce elapses, search correctly filters',
      'Note1' in texts and 'Note2' not in texts)

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

print()
print(f"=== QA8 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
