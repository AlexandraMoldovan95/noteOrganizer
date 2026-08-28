import sys
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile, time, zipfile, json
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

code = NO.encode_share_code([app.notes[0]])
decoded = NO.decode_share_code(code)
check('share code round-trips correctly', decoded[0]['title']=='ShareMe' and decoded[0]['body']=='share body')

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

print()
print(f"=== QA3 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
