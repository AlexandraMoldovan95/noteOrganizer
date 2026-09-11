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
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile, time, zipfile, json
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

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.ask_yes_no=lambda *a,**k: True
app.geometry('1100x850'); app.update()

def find_btn(w, txt_contains):
    for c in w.winfo_children():
        if isinstance(c,tk.Button) and txt_contains in str(c.cget('text')): return c
        r=find_btn(c,txt_contains)
        if r: return r
    return None

def find_text_widget(w):
    for c in w.winfo_children():
        if isinstance(c,tk.Text): return c
        r=find_text_widget(c)
        if r: return r
    return None

def click_dialog_button(app, label):
    """Search every currently-placed overlay for the target button, rather
    than assuming the themed dialog is always the LAST one in place_slaves()
    — a lingering toast notification (or any other .place()'d overlay) can
    end up after the real dialog in that list, and blindly grabbing [-1]
    then finds an empty frame with no matching button at all."""
    app.update()
    for frame in app.place_slaves():
        b = find_btn(frame, label)
        if b:
            b.invoke()
            return

# ---- TRASH: pagination ----
app.trash = [{'id':i,'title':f'Deleted{i}','body':'x','category':'General',
             'deleted_at':f'2026-01-{(i%28)+1:02d} 00:00:00'} for i in range(600)]
app.show_settings_page(); app.update()
t0=time.perf_counter()
app.toggle_settings_panel('trash')
app.update()
elapsed=(time.perf_counter()-t0)*1000
check(f'trash panel opens fast with 600 entries ({elapsed:.0f}ms)', elapsed < 500)

def count_rows(w, marker):
    count=[0]
    def walk(x):
        for c in x.winfo_children():
            if isinstance(c,tk.Label) and marker in str(c.cget('text')): count[0]+=1
            walk(c)
    walk(w)
    return count[0]
# Read the page size from the app rather than hardcoding it. What matters
# here is that the panel pages at all and that "Show more" adds exactly one
# more page -- not the specific number, which is a performance tuning knob
# (it went 50 -> 25 when Settings began showing one section at a time, and
# hardcoding it here meant a tuning change looked like a broken feature).
PAGE = app.TRASH_PAGE_SIZE
initial_rows = count_rows(app.settings_trash_panel, 'Deleted')
check(f'trash paginated to {PAGE} initial rows', initial_rows==PAGE)

show_more = find_btn(app.settings_trash_panel, 'Show')
check('Show more button present', show_more is not None)
if show_more:
    show_more.invoke()
    app.update()
    check(f'Show more expands to {PAGE*2} rows',
          count_rows(app.settings_trash_panel, 'Deleted')==PAGE*2)

# restore preserves pagination + moves note back
restore_btn = find_btn(app.settings_trash_panel, 'Restore')
before_trash = len(app.trash)
before_notes = len(app.notes)
if restore_btn:
    restore_btn.invoke()
    app.update()
check('restore removes from trash', len(app.trash)==before_trash-1)
check('restore adds to notes', len(app.notes)==before_notes+1)

# empty trash
app.toggle_settings_panel('trash'); app.update()
app.toggle_settings_panel('trash'); app.update()
empty_btn = find_btn(app.settings_trash_panel, 'Empty trash')
if empty_btn:
    empty_btn.invoke()
    app.update()
check('empty trash clears everything', len(app.trash)==0)

# ---- SHARE CODE (single + multi note) ----
app.notes = [{'id':1,'title':'ShareMe','body':'share body','comments':'','category':'General',
             'date':'','color':'','recurrence':{},'updated':'2026-01-01 00:00',
             'created':'2026-01-01 00:00','checklist':[],'attachments':[]}]
app.save_notes()
app.notebook.select(0); app.update()
app.load_note(app.notes[0])
app.share_current_note_as_code()
app.update()
check('share code area becomes visible', app.editor_code_area.winfo_ismapped())
code_entry = find_text_widget(app.editor_code_area)
check('share code text widget exists', code_entry is not None)

# decode round trip
# Paragraphs travel too: without them a shared note arrived flush
# left with flat lists, and a table lost its place on the page.
_para_note = {'title': 'P', 'body': '| A | B |\n| x | y |',
              'formatting': [],
              'paragraphs': [{'line': 0, 'align': 'center'},
                             {'line': 1, 'align': 'center'}]}
_para_back = NO.decode_share_code(
    NO.encode_share_code([_para_note]))[0]
check('a share code carries the paragraphs (table position, indents)',
      _para_back.get('paragraphs') == _para_note['paragraphs'])
check('and an old code without paragraphs still decodes',
      'paragraphs' not in NO.decode_share_code(NO.encode_share_code([
          {'title': 'v', 'body': 'x', 'formatting': []}]))[0])

# ---- Untrusted-import hardening: decode filters to the shareable slice.
# A HAND-CRAFTED code can put anything in the JSON; decode must hand back
# only the fields a genuine code carries — never attachments (which a
# real code never has and whose stored_as could aim a later delete
# outside the attachments folder), never arbitrary keys.
import json as _json3, base64 as _b643, zlib as _zlib3
def _craft_code_list(notes_list):
    raw = _zlib3.compress(_json3.dumps({'v': 1, 'notes': notes_list}).encode())
    return NO.SHARE_CODE_PREFIX + _b643.urlsafe_b64encode(raw).decode()
def _craft_code(note_dict):
    return _craft_code_list([note_dict])
_evil = NO.decode_share_code(_craft_code({
    'title': 'Evil', 'body': 'b', 'category': 'General',
    'attachments': [{'stored_as': '../../secret.txt'}],
    'id': 999, 'pinned': True, 'bogus': 42}))[0]
check('decode drops attachments smuggled into a crafted code',
      'attachments' not in _evil)
check('decode drops arbitrary non-shareable keys (id, pinned, bogus)',
      not ({'id', 'pinned', 'bogus'} & set(_evil.keys())))
check('decode keeps the genuine shareable fields',
      _evil.get('title') == 'Evil' and _evil.get('body') == 'b')
# A crafted code can also put non-dict entries in the notes list; decode
# must survive them (the `else {}` branch), not throw on the projection.
# Guarded so a mutant that drops the branch fails HARD here (the raise
# is the bug's face) instead of crashing the run before its footer.
try:
    _mixed = NO.decode_share_code(_craft_code_list([
        42, None, 'a string', {'title': 'Real', 'body': 'b'}]))
except Exception:
    _mixed = None
check('decode tolerates non-dict note entries without crashing',
      _mixed is not None and len(_mixed) == 4 and _mixed[:3] == [{}, {}, {}]
      and _mixed[3].get('title') == 'Real')

# Sharing a note that holds a lone UTF-16 surrogate (Tk hands an astral
# emoji over unpaired; mend used to run only on disk-save) must not
# crash encode's utf-8 step (audit Z05-F02).
_emoji_note = {'title': 'plan \U0001F600', 'body': 'lone \ud83d half',
               'category': 'General'}
_enc_ok = True
try:
    _emoji_code = NO.encode_share_code(_emoji_note)
    _emoji_back = NO.decode_share_code(_emoji_code)[0]
except Exception:
    _enc_ok = False
    _emoji_back = {}
check('sharing a note with an astral/lone-surrogate emoji does not crash',
      _enc_ok and '\U0001F600' in _emoji_back.get('title', ''))
check('and the encoded code carries no lone surrogate',
      _enc_ok and not any(0xD800 <= ord(c) <= 0xDFFF
                          for c in _emoji_back.get('body', '')))

# The checklist travels too: a shared note used to arrive without it --
# the one piece of content a code silently dropped.
_ck_note = {'title': 'C', 'body': 'b', 'formatting': [],
            'checklist': [{'text': 'pack bags', 'done': True},
                          {'text': 'call venue', 'done': False}]}
_ck_back = NO.decode_share_code(NO.encode_share_code([_ck_note]))[0]
check('a share code carries the checklist, done states included',
      _ck_back.get('checklist') == _ck_note['checklist'])
check('and an old code without a checklist still decodes',
      'checklist' not in NO.decode_share_code(NO.encode_share_code([
          {'title': 'v', 'body': 'x', 'formatting': []}]))[0])

code = NO.encode_share_code([app.notes[0]])
decoded = NO.decode_share_code(code)
check('share code round-trips correctly', decoded[0]['title']=='ShareMe' and decoded[0]['body']=='share body')

# ---- THE EDITOR'S OWN SHARE ROUTE, END TO END ----
# The core round-trips above can all pass while the UI still loses
# content: the editor's "Copy code" built its note dict from a
# hand-rolled field list (dropping formatting, paragraphs AND the
# checklist), and the single-note import loader never loaded the
# checklist it received -- found in a field test, both ends. This walks
# the REAL route: editor state -> share_current_note_as_code -> the
# rendered code widget -> the import box -> the opened editor.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'RouteFull')
app.body_text.insert('1.0', 'bold word here\ncentred line')
app.body_text.tag_add('sel', '1.0', '1.4')
app._fmt_buttons['bold'].invoke()
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.mark_set('insert', '2.0')
app._set_paragraph_align('center')
app._working_checklist = [{'text': 'pack bags', 'done': True},
                          {'text': 'call venue', 'done': False}]
app.update()
app.share_current_note_as_code()
app.update()
_rt_code = find_text_widget(app.editor_code_area).get('1.0', 'end-1c')
_rt_saved_notes = list(app.notes)
app.notes = []          # clean notebook: no duplicate dialog in the way
app.save_notes()
app.toggle_import_panel(); app.update()
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _rt_code)
app._do_inline_import()
app.update()
_rt_st = app.capture_editor_state()
check('the editor-shared code arrives with its checklist, done states '
      'included',
      _rt_st.get('checklist') == [{'text': 'pack bags', 'done': True},
                                  {'text': 'call venue', 'done': False}])
check('...and with its character formatting and paragraph alignment',
      any(sp.get('style') == 'bold' for sp in _rt_st.get('formatting', []))
      and any(p.get('align') == 'center'
              for p in _rt_st.get('paragraphs', [])))
check('...and the checklist section opened so the items are visible',
      app._checklist_open)
# State hygiene: the sections below expect the ShareMe note to exist
# (it is the duplicate their dialog path skips).
app.notes = _rt_saved_notes
app.save_notes()
app.new_note(); app.update()

# ---- IMPORT CODE with duplicate detection ----
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', code)
app.wait_variable = lambda var: click_dialog_button(app, 'Skip the 1 duplicate(s)')
before = len(app.notes)
# multi-note code needed to trigger the dialog path; build one with 1 dup + 1 fresh
multi_notes = [
    {'title':'ShareMe','body':'share body','comments':'','category':'General','date':'','color':'','recurrence':{}},
    {'title':'FreshOne','body':'fresh body','comments':'','category':'General','date':'','color':'','recurrence':{}},
]
multi_code = NO.encode_share_code(multi_notes)
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', multi_code)
app._do_inline_import()
app.update()
check('import code with skip-duplicates adds only the fresh note',
      len(app.notes)==before+1 and any(n['title']=='FreshOne' for n in app.notes))

# ---- A TABLE THROUGH A SHARE CODE, END TO END ----
# Not just the text: the separator's hand-set column width and the
# table's place on the page (paragraphs) must arrive AND render -- the
# imported note opens with a real grid built from them.
_tbl_code = NO.encode_share_code([{
    'title': 'TabelPrinCod',
    'body': '| Cap | G |\n| :-------------: | --- |\n| unu | doi |',
    'formatting': [],
    'paragraphs': [{'line': 0, 'align': 'center'},
                   {'line': 1, 'align': 'center'},
                   {'line': 2, 'align': 'center'}],
    'comments': '', 'category': 'General', 'date': '', 'color': '',
    'recurrence': {},
}])
app.import_box.delete('1.0', 'end')
app.import_box.insert('1.0', _tbl_code)
# A single-note code opens straight in the EDITOR (unsaved), it is not
# added to the list -- the check follows the real flow.
app._do_inline_import()
app.update()
check('the table note opens in the editor from the code',
      app.title_entry.get() == 'TabelPrinCod')
_g3 = app._grid_at_line(1)
from noteorganizer.core import tables as _ct
_sep3 = (_ct.parse_separator(app.body_text.get('2.0', '2.end'))
         if _g3 is not None else [])
check('and opens as a drawn grid, data rows only',
      _g3 is not None and _g3['data_rows'] == 2 and _g3['ncols'] == 2)
check(f'with the hand-set column width intact '
      f'(W={_sep3[0]["width"] if _sep3 else None})',
      bool(_sep3) and _sep3[0]['width'] == 15)
check('and its place on the page still centred',
      app._grid_table_align_of(1) == 'center')

# ---- IMPORT CODE: single-note duplicate detection (the exact scenario a
# user found by hand: copying a code from a note you already have, then
# re-importing it, used to silently open it for editing with no warning) ----
single_dup_code = NO.encode_share_code([
    {'title':'ShareMe','body':'share body','comments':'','category':'General','date':'','color':'','recurrence':{}}
])
app.open_blank_tab()  # a clean, properly-flushed editor state before each import attempt —
app.update()          # directly clearing title_entry instead risked corrupting/flushing
                       # whatever note was previously open in the editor
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', single_dup_code)
app.wait_variable = lambda var: click_dialog_button(app, 'Cancel')
app._do_inline_import()
app.update()
check('single-note import warns on an exact duplicate and Cancel skips it',
      app.title_entry.get() != 'ShareMe')

app.open_blank_tab()
app.update()
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', single_dup_code)
app.wait_variable = lambda var: click_dialog_button(app, 'Open it anyway')
app._do_inline_import()
app.update()
check('single-note import allows opening the duplicate anyway if chosen',
      app.title_entry.get() == 'ShareMe')

# a genuinely fresh single note still opens directly, no dialog needed
fresh_single_code = NO.encode_share_code([
    {'title':'GenuinelyFresh','body':'zzz','comments':'','category':'General','date':'','color':'','recurrence':{}}
])
app.open_blank_tab()
app.update()
app.import_box.delete('1.0','end')
app.import_box.insert('1.0', fresh_single_code)
app._do_inline_import()
app.update()
check('single-note import with no duplicate opens directly, no dialog needed',
      app.title_entry.get() == 'GenuinelyFresh')

# Clean editor state before the tests that follow, so nothing left over here
# leaks into them the same way.
app.open_blank_tab()
app.update()

# ---- EXPORT: background thread, non-blocking ----
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
for i in range(15):
    with open(os.path.join(NO.ATTACHMENTS_DIR, f'qa3_att{i}.bin'), 'wb') as f:
        f.write(b'x'*200000)  # enough real work that the progress bar is observable
zip_path = os.path.join(tempfile.gettempdir(), 'qa3_export.zip')
# The system temp dir outlives runs: a zip left by a PREVIOUS qa3 run
# made "export produced a real zip file" pass even when this export
# never moved its file into place. Fresh target, every time.
if os.path.exists(zip_path):
    os.remove(zip_path)
fd.asksaveasfilename = lambda **k: zip_path
app.export_data()
app.update()
panel_visible_at_start = app.export_progress_frame.winfo_ismapped()
t0=time.time()
interactions=0
while app._export_state is not None and time.time()-t0 < 5:
    app.update()
    interactions+=1
check('export progress bar appears', panel_visible_at_start)
check('export completes on its own', app._export_state is None)
check('export produced a real zip file', os.path.exists(zip_path))
check('progress bar hides after export completes', not app.export_progress_frame.winfo_ismapped())

# ---- IMPORT (zip, threaded) with duplicate detection ----
backup_notes = [
    {'title':'FreshOne','body':'fresh body','comments':'','category':'General','date':'','color':'','recurrence':{}},  # dup of what we have
    {'title':'BrandNewImport','body':'zzz','comments':'','category':'General','date':'','color':'','recurrence':{}},
]
backup_dir = tempfile.mkdtemp()
with open(os.path.join(backup_dir,'notes_data.json'),'w') as f:
    json.dump(backup_notes, f)
import_zip_path = os.path.join(tempfile.gettempdir(), 'qa3_import.zip')
with zipfile.ZipFile(import_zip_path,'w') as zf:
    zf.write(os.path.join(backup_dir,'notes_data.json'), 'notes_data.json')
fd.askopenfilename = lambda **k: import_zip_path

app.wait_variable = lambda var: click_dialog_button(app, 'Skip the 1 duplicate(s)')
before2 = len(app.notes)
app.import_data()
t0=time.time()
while app._import_state is not None and time.time()-t0 < 5:
    app.update()
app.update()
check('threaded zip import completes', app._import_state is None)
check('zip import with skip adds only the fresh note',
      len(app.notes)==before2+1 and any(n['title']=='BrandNewImport' for n in app.notes))

# ---- EXPORT is atomic: a failed export never destroys the old backup ----
# (audit Z05-F00) The zip used to be opened ON the target, so a mid-write
# failure — or the app dying — truncated the very backup being replaced.
# Now it writes save_path+".tmp" and moves it into place only when whole.
app.show_error = lambda *a, **k: True  # the failed export reports; don't block
_atomic_zip = os.path.join(tempfile.gettempdir(), 'qa3_atomic.zip')
with open(_atomic_zip, 'wb') as f:
    f.write(b'OLD-BACKUP-BYTES')
class _FailingZip(zipfile.ZipFile):
    def write(self, *a, **k):
        raise IOError('disk exploded (test)')
_real_zipfile_cls = NO.zipfile.ZipFile
NO.zipfile.ZipFile = _FailingZip
fd.asksaveasfilename = lambda **k: _atomic_zip
try:
    app.export_data()
    t0 = time.time()
    while app._export_state is not None and time.time() - t0 < 5:
        app.update()
finally:
    NO.zipfile.ZipFile = _real_zipfile_cls
check('a failed export leaves the existing backup byte-identical',
      open(_atomic_zip, 'rb').read() == b'OLD-BACKUP-BYTES')
check('and leaves no .tmp litter behind',
      not os.path.exists(_atomic_zip + '.tmp'))
if os.path.exists(_atomic_zip):
    os.remove(_atomic_zip)

# The single-note export is the same class (it wrote straight onto the
# chosen file): a write failure must leave the existing file intact.
_se_path = os.path.join(tempfile.gettempdir(), 'qa3_single.txt')
with open(_se_path, 'w', encoding='utf-8') as f:
    f.write('OLD-NOTE')
_builtin_open = open
def _fail_write_open(p, mode='r', *a, **k):
    if isinstance(p, str) and p.startswith(_se_path) and 'w' in str(mode):
        # Open for real first — a genuine 'w' open TRUNCATES the target
        # before any write, which is exactly the damage the tmp protocol
        # exists to keep away from the user's file. A fake handle that
        # never touched the disk let the direct-write mutant survive.
        _fh = _builtin_open(p, mode, *a, **k)
        class _FW:
            def __enter__(s): return s
            def __exit__(s, *e):
                _fh.close()
                return False
            def write(s, d): raise IOError('disk exploded (test)')
        return _FW()
    return _builtin_open(p, mode, *a, **k)
fd.asksaveasfilename = lambda **k: _se_path
NO.open = _fail_write_open
try:
    app.export_note_as_file(app.notes[0], 'txt')
finally:
    del NO.open
check('a failed single-note export leaves the existing file intact',
      open(_se_path, encoding='utf-8').read() == 'OLD-NOTE'
      and not os.path.exists(_se_path + '.tmp'))
os.remove(_se_path)
app.show_error = NO.NoteOrganizer.show_error.__get__(app)  # restore the real one

# ---- CLOSE waits for an in-flight worker (audit Z05-F01) ----
# destroy() used to kill a daemon export/import thread mid-file. The app
# now remembers its I/O workers and on_app_close waits (capped) for them.
# Both checks use the DEFAULT cap on purpose: passing an explicit cap
# here let a mutant gut the default (cap_s=0) — "closing waits" fully
# broken — while the checks stayed green.
_slow_done = {'flag': False}
def _slow_worker():
    time.sleep(0.6)
    _slow_done['flag'] = True
app._start_io_worker(_slow_worker)
app._wait_for_io_workers()
check('the close-time wait lets an in-flight I/O worker finish',
      _slow_done['flag'])

# End-to-end: the REAL on_app_close (destroy stubbed) must let a live
# worker finish — this also fails if the call site shrinks the cap.
_slow_done2 = {'flag': False}
def _slow_worker2():
    time.sleep(0.6)
    _slow_done2['flag'] = True
_real_destroy3 = app.destroy
app.destroy = lambda: None
try:
    app._start_io_worker(_slow_worker2)
    app.on_app_close()
finally:
    app.destroy = _real_destroy3
check('on_app_close itself waits for an in-flight worker before destroy',
      _slow_done2['flag'])

# ---- The write-failure callback reaches the SCREEN (audit Z01-F06) ----
# The core half (return + crash log + callback) lives in
# test_data_safety; this is the UI half: the app registers the callback
# at startup and a failure shows the error toast naming the file.
from noteorganizer.core import storage as _st3
check('the app registers core storage\'s write-failure callback',
      _st3.on_write_failure is not None)
if _st3.on_write_failure is not None:
    _st3.on_write_failure(os.path.join('x', 'trash.json'), OSError('disk full'))
    t0 = time.time()
    while time.time() - t0 < 2:
        app.update()
        if 'trash.json' in str(app.toast_lbl.cget('text')):
            break
    check('a failed write shows the toast naming the file',
          'trash.json' in str(app.toast_lbl.cget('text')))

# ---- The backup carries the WHOLE notebook (audit Z05-F07) ----
# templates.json and trash.json were silently left out of the export and
# never read on import — moving devices lost both. Full round-trip:
# export with a template and a trashed note, wipe them locally, import,
# and both come back (additively — nothing local replaced).
app.templates.append(NO.normalize_template(
    {'name': 'RoundTripTpl', 'title': 'T', 'body': 'tpl body'}))
NO.save_templates(app.templates)
app.trash.append({'id': 900, 'title': 'TrashedRT', 'body': 'rt',
                  'category': 'General', 'deleted_at': '2026-01-01 00:00:00',
                  'attachments': []})
NO.save_trash(app.trash)
_rt_zip = os.path.join(tempfile.gettempdir(), 'qa3_fullrt.zip')
if os.path.exists(_rt_zip):
    os.remove(_rt_zip)
fd.asksaveasfilename = lambda **k: _rt_zip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 5:
    app.update()
check('full-notebook export completes', os.path.exists(_rt_zip))
# Wipe the two locally, then import the backup back.
app.templates = [t for t in app.templates if t.get('name') != 'RoundTripTpl']
NO.save_templates(app.templates)
app.trash = [e for e in app.trash if e.get('title') != 'TrashedRT']
NO.save_trash(app.trash)
app.ask_yes_no = lambda *a, **k: True
app._themed_dialog = lambda *a, **k: 'all'
fd.askopenfilename = lambda **k: _rt_zip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 8:
    app.update()
check('the template comes back from the backup',
      any(t.get('name') == 'RoundTripTpl' for t in app.templates))
check('the trashed note comes back from the backup',
      any(e.get('title') == 'TrashedRT' for e in app.trash))
# Re-importing the SAME backup must not double the trash.
_trash_count_rt = len(app.trash)
fd.askopenfilename = lambda **k: _rt_zip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 8:
    app.update()
check('re-importing the same backup does not double the trash',
      len(app.trash) == _trash_count_rt)
os.remove(_rt_zip)

# A CRAFTED backup: trash.json with a non-string deleted_at and an
# attachment pointing at a file an ACTIVE note owns. The entry must
# arrive normalized (the Trash panel's sort crashed on deleted_at=5)
# and with its OWN copy of the file (delete-forever on the import must
# never destroy the active note's attachment).
os.makedirs(NO.ATTACHMENTS_DIR, exist_ok=True)
_own_att = '20260202020202020202_own.txt'
with open(os.path.join(NO.ATTACHMENTS_DIR, _own_att), 'w') as f:
    f.write('mine')
# The file's owner is a LOCAL TRASH entry — the exact hole the review
# found: claimed was built from active notes only, so an imported twin
# shared a trashed note's file and delete-forever on either destroyed
# the other's attachment.
app.trash.append({'id': 951, 'title': 'TrashOwner', 'body': 'to',
                  'category': 'General',
                  'deleted_at': '2026-01-02 00:00:00',
                  'attachments': [{'filename': 'own.txt',
                                   'stored_as': _own_att}]})
NO.save_trash(app.trash)
_cz = os.path.join(tempfile.gettempdir(), 'qa3_crafted_trash.zip')
with zipfile.ZipFile(_cz, 'w') as zf:
    zf.writestr('notes_data.json', '[]')
    zf.writestr('trash.json', json.dumps([
        {'id': 1, 'title': 'ForeignTrash', 'body': 'ft',
         'category': 'General', 'deleted_at': 5,
         'attachments': [{'filename': 'own.txt',
                          'stored_as': _own_att}]}]))
    zf.writestr('attachments/' + _own_att, 'mine')
fd.askopenfilename = lambda **k: _cz
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 8:
    app.update()
_ft = next((e for e in app.trash if e.get('title') == 'ForeignTrash'), None)
check('a foreign trash entry arrives normalized (deleted_at is a str)',
      _ft is not None and isinstance(_ft.get('deleted_at'), str))
check('an imported trash attachment never shares a LOCAL TRASH file',
      _ft is not None and _ft.get('attachments')
      and _ft['attachments'][0]['stored_as'] != _own_att
      and os.path.isfile(os.path.join(
          NO.ATTACHMENTS_DIR, _ft['attachments'][0]['stored_as'])))
os.remove(_cz)

# ---- SHARE-CODE decode: every refusal branch (coverage-lift C16) ----
# Each malformed-input class must raise ValueError with a HUMAN message
# (the UI shows it verbatim) — never a raw exception, never success.
from noteorganizer.core import sharing as _sh
_bad_inputs = [
    ('not a string', 12345),
    ('empty after whitespace', '  \n  '),
    ('absurd length', 'NOTE1:' + 'A' * (_sh.MAX_SHARE_CODE_CHARS + 1)),
    ('wrong prefix', 'XYZ:abcdef'),
    ('broken base64', 'NOTE1:@@@not-base64@@@'),
    ('valid b64, broken zlib', 'NOTE1:' + __import__('base64').urlsafe_b64encode(b'not zlib data').decode()),
    ('valid zlib, broken json', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{broken')).decode()),
    ('json but no notes key', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{"v":1}')).decode()),
    ('newer version', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{"v":9,"notes":[{}]}')).decode()),
    ('empty notes list', 'NOTE1:' + __import__('base64').urlsafe_b64encode(__import__('zlib').compress(b'{"v":1,"notes":[]}')).decode()),
]
_all_refused = True
for _why, _code in _bad_inputs:
    try:
        _sh.decode_share_code(_code)
        _all_refused = False
        print('    (decode ACCEPTED the %s case!)' % _why)
    except ValueError as e:
        if not str(e).strip():
            _all_refused = False
            print('    (%s: empty message)' % _why)
    except Exception as e:
        _all_refused = False
        print('    (%s: raw %s escaped)' % (_why, type(e).__name__))
check('every malformed share code is refused with a human ValueError',
      _all_refused)
_over = {'v': 1, 'notes': [{'title': 'x'}] * (_sh.MAX_SHARED_NOTES + 1)}
_over_code = 'NOTE1:' + __import__('base64').urlsafe_b64encode(
    __import__('zlib').compress(__import__('json').dumps(_over).encode())).decode()
try:
    _sh.decode_share_code(_over_code)
    _cap_ok = False
except ValueError as e:
    _cap_ok = str(_sh.MAX_SHARED_NOTES) in str(e)
check('a code over the note cap names the cap in its refusal', _cap_ok)

# ---- A restored backup keeps its categories (product review T0-3) ----
# settings.json - where the categories live - was always written INTO the
# zip and never read back out, so on a new machine every imported note
# whose category did not exist yet was silently re-filed under "General"
# by normalize_note. The whole filing system of a restored notebook, gone.
NO.CATEGORY_COLORS['Proiecte Mari'] = '#ff8800'
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Planul', 'body': 'x',
              'category': 'Proiecte Mari', 'updated': '2026-01-01 00:00',
              'created': '2026-01-01 00:00', 'checklist': [],
              'attachments': []}]
app.save_notes()
# Calendar day decor rides the same settings.json: two valid entries
# and one garbage colour a hand-editor (or hostile zip) could carry.
NO.save_setting('day_colors', {'2026-03-03': '#112233',
                               '2026-03-05': '#zzzzzz'})
NO.save_setting('day_emoji', {'2026-03-04': ['\u2b50']})
app.day_colors = {'2026-03-03': '#112233'}
app.day_emoji = {'2026-03-04': ['\u2b50']}
_catzip = os.path.join(tempfile.gettempdir(), 'qa3_categories.zip')
if os.path.exists(_catzip):
    os.remove(_catzip)
fd.asksaveasfilename = lambda **k: _catzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 5:
    app.update()
check('the backup zip carries settings.json', os.path.exists(_catzip))

# Now become a device that has never heard of that category.
del NO.CATEGORY_COLORS['Proiecte Mari']
NO.persist_categories()
NO.save_setting('day_colors', {})
NO.save_setting('day_emoji', {})
app.day_colors = {}
app.day_emoji = {}
app.notes = []
app.save_notes()
app.ask_yes_no = lambda *a, **k: True
app._themed_dialog = lambda *a, **k: 'all'
fd.askopenfilename = lambda **k: _catzip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 8:
    app.update()
check('importing the backup brings the category back',
      'Proiecte Mari' in NO.CATEGORY_COLORS
      and NO.get_setting('categories', {}).get('Proiecte Mari') == '#ff8800')
check('and the note keeps its filing instead of falling to General',
      any(n.get('category') == 'Proiecte Mari' for n in app.notes))
# The calendar decor is user data the backup has always carried and the
# import used to drop wholesale -- and its colours are as untrusted as
# any other imported value: the garbage one must NOT come back.
check('day colours and markers come back with the backup',
      app.day_colors.get('2026-03-03') == '#112233'
      and app.day_emoji.get('2026-03-04') == ['\u2b50']
      and NO.get_setting('day_colors', {}).get('2026-03-03') == '#112233')
check('a garbage day colour from the backup is refused at the door',
      '2026-03-05' not in app.day_colors
      and '2026-03-05' not in NO.get_setting('day_colors', {}))
os.remove(_catzip)
NO.CATEGORY_COLORS.pop('Proiecte Mari', None)
NO.persist_categories()
NO.save_setting('day_colors', {})
NO.save_setting('day_emoji', {})
app.day_colors = {}
app.day_emoji = {}

# ---- The category merge runs BEFORE the duplicate scan ----
# The scan normalizes each incoming note, and normalize re-files an
# unknown category to General. Scanned in that state, a distinct note
# read as a duplicate of a local General twin and the import offered to
# skip it -- while the dialog claimed its category matched. With the
# merge first, the same import must sail through with no question.
NO.CATEGORY_COLORS['Ordine'] = '#123456'
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Same', 'body': 'y', 'category': 'Ordine',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
_ordzip = os.path.join(tempfile.gettempdir(), 'qa3_order.zip')
if os.path.exists(_ordzip):
    os.remove(_ordzip)
fd.asksaveasfilename = lambda **k: _ordzip
app.export_data()
t0 = time.time()
while app._export_state is not None and time.time() - t0 < 5:
    app.update()
# The amnesiac device again -- but THIS one already owns a General note
# with the identical text, the collision the old order manufactured.
NO.CATEGORY_COLORS.pop('Ordine', None)
NO.persist_categories()
app.notes = [{'id': 1, 'title': 'Same', 'body': 'y', 'category': 'General',
              'updated': '2026-01-01 00:00', 'created': '2026-01-01 00:00',
              'checklist': [], 'attachments': []}]
app.save_notes()
_dlg_asked = []
_real_dlg3 = app._themed_dialog
app._themed_dialog = lambda *a, **k: (_dlg_asked.append(a), 'all')[1]
fd.askopenfilename = lambda **k: _ordzip
app.import_data()
t0 = time.time()
while app._import_state is not None and time.time() - t0 < 8:
    app.update()
app._themed_dialog = _real_dlg3
check('with categories merged first, the twin is no duplicate: no dialog',
      _dlg_asked == [])
check('and it lands under its own category, alongside the local twin',
      len(app.notes) == 2
      and any(n.get('category') == 'Ordine' for n in app.notes))
os.remove(_ordzip)
NO.CATEGORY_COLORS.pop('Ordine', None)
NO.persist_categories()

print()
print(f"=== QA3 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
