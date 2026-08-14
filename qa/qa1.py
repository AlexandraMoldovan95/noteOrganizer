import sys
import note_organizer as NO, tkinter as tk, json, os, re
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

# ---- BASIC NOTE CRUD ----
app.new_note()
app.title_entry.delete(0,'end'); app.title_entry.insert(0,'My First Note'); app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'Hello world body')
app.comments_text.insert('1.0', 'a comment')
app.save_current_note(auto=False)
app.update()
note = app.find_note(app.selected_note_id)
check('note created with correct title', note is not None and note['title']=='My First Note')
check('note body saved', note['body']=='Hello world body')
check('note comments saved', note['comments']=='a comment')

# edit and re-save
app.title_entry.delete(0,'end'); app.title_entry.insert(0,'Edited Title')
app.save_current_note(auto=False)
app.update()
note2 = app.find_note(app.selected_note_id)
check('note edit persists', note2['title']=='Edited Title')
check('same note id (no duplicate on edit)', note2['id']==note['id'])

# regression: 'updated' must include seconds, not just minutes, so two notes
# saved in the same minute still sort correctly by "Recently updated"
check('updated timestamp includes seconds (fixes same-minute sort ties)',
      bool(re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', note2.get('updated') or '')))

# pin / unpin
app.toggle_pin(note2)
check('note pinned', app.find_note(note2['id'])['pinned']==True)
app.toggle_pin(note2)
check('note unpinned', app.find_note(note2['id'])['pinned']==False)

# duplicate
before_count = len(app.notes)
app.duplicate_note(note2)
app.update()
check('duplicate adds a note', len(app.notes)==before_count+1)

# delete (soft, to trash)
target_id = note2['id']
app._move_notes_to_trash([app.find_note(target_id)])
app.notes = [n for n in app.notes if n['id']!=target_id]
app.save_notes()
check('note moved to trash, not in active list', app.find_note(target_id) is None)
check('trash has an entry', len(app.trash)>=1)

# ---- CATEGORIES ----
NO.CATEGORY_COLORS['TestCat'] = '#7c5cff'
NO.persist_categories()
check('category added', 'TestCat' in NO.CATEGORY_COLORS)

app.new_note()
app.title_entry.insert(0,'CatNote')
app.body_text.insert('1.0','x')
app.category_var.set('TestCat')
app.save_current_note(auto=False); app.update()
cn = app.find_note(app.selected_note_id)
check('note saved with custom category', cn['category']=='TestCat')

app.rename_category_everywhere('TestCat','RenamedCat')
app.update()
check('category rename propagates to note', app.find_note(cn['id'])['category']=='RenamedCat')

# ---- TEMPLATES ----
app.templates.append({'name':'MyTemplate','title':'Templated Title','body':'Templated body',
                      'comments':'','category':'General','checklist':[]})
NO.save_templates(app.templates)
check('template saved', any(t['name']=='MyTemplate' for t in app.templates))

app.new_note()
tpl = next(t for t in app.templates if t['name']=='MyTemplate')
app.apply_template(tpl) if hasattr(app,'apply_template') else None
app.update()

# ---- SEARCH ----
app.notes.append({'id':9991,'title':None,'body':'searchable unique body','comments':None,
                  'category':None,'updated':'2026-01-01 00:00','created':'2026-01-01 00:00',
                  'checklist':[],'attachments':[]})
try:
    app.search_var.set('searchable'); app.update()
    check('search survives None-field note', True)
except Exception as e:
    check(f'search survives None-field note ({e})', False)

# ---- SORTING ----
# Uses the app's real sort-option labels (previously this loop used made-up
# strings like 'Newest first' that don't match any real option, so every
# iteration silently no-opped and the test only ever proved "didn't crash",
# never that sorting actually works) and checks the notes render in the
# exact order each option promises, not just that nothing crashed.
app.search_var.set('')
app.filter_var.set('All')
app.group_by_category.set(False)
app.notes = [
    {'id':301,'title':'Banana','body':'x','category':'General','date':'2026-03-10',
     'updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
    {'id':302,'title':'Apple','body':'x','category':'Zeta','date':'2026-01-05',
     'updated':'2026-01-02 00:00','created':'2026-01-02 00:00','checklist':[],'attachments':[]},
    {'id':303,'title':'Cherry','body':'x','category':'Alpha','date':'2026-02-20',
     'updated':'2026-01-03 00:00','created':'2026-01-03 00:00','checklist':[],'attachments':[]},
]

def rendered_order():
    app.refresh_note_list()
    app.update()
    return [app.find_note(nid)['title'] for nid in app._note_card_widgets.keys()]

for opt, expected in [
    ('Recently updated', ['Cherry', 'Apple', 'Banana']),   # newest updated first
    ('Oldest updated',   ['Banana', 'Apple', 'Cherry']),   # oldest updated first
    ('Title A–Z',        ['Apple', 'Banana', 'Cherry']),
    ('Title Z–A',        ['Cherry', 'Banana', 'Apple']),
    ('Category',         ['Cherry', 'Banana', 'Apple']),   # Alpha, General, Zeta
    ('Date (soonest)',   ['Apple', 'Cherry', 'Banana']),   # 01-05, 02-20, 03-10
]:
    try:
        app.sort_var.set(opt)
        actual = rendered_order()
        check(f'sort "{opt}" orders notes correctly ({actual})', actual == expected)
    except Exception as e:
        check(f'sort option {opt} works ({e})', False)

# ---- SORT DROPDOWN WIDTH (regression) ----
# "Recently updated" used to render at exactly its natural text width with
# no margin at all, which is why the last letter looked cut off.
def find_widget(w, cls, text_contains=None):
    for c in w.winfo_children():
        if isinstance(c, cls):
            if text_contains is None or text_contains in str(c.cget('text')):
                return c
        r = find_widget(c, cls, text_contains)
        if r: return r
    return None
app.sort_var.set('Recently updated')
app.update()
sort_lbl = find_widget(app.sidebar, tk.Label, 'Recently updated')
check('sort dropdown label found', sort_lbl is not None)
if sort_lbl:
    import tkinter.font as tkfont
    natural_width = tkfont.Font(family='Segoe UI', size=8).measure('Recently updated')
    check(f'sort dropdown label has room to spare ({sort_lbl.winfo_reqwidth()}px vs {natural_width}px text)',
          sort_lbl.winfo_reqwidth() > natural_width)

# ---- CHECKLIST ----
app.new_note()
app.title_entry.insert(0,'ChecklistNote')
app.body_text.insert('1.0','x')
app._working_checklist = [{'text':'item1','done':False},{'text':'item2','done':True}]
if hasattr(app,'_render_checklist_items'):
    app._render_checklist_items()
app.save_current_note(auto=False); app.update()
clnote = app.find_note(app.selected_note_id)
check('checklist saved with 2 items', len(clnote.get('checklist',[]))==2)
check('checklist done-state preserved', clnote['checklist'][1]['done']==True)

# ---- PERSISTENCE TO DISK ----
app.save_notes()
disk_path = NO.DATA_FILE
check('notes file exists on disk', os.path.exists(disk_path))
with open(disk_path) as f:
    disk_notes = json.load(f)
check('disk note count matches memory', len(disk_notes)==len(app.notes))

# ---- DATA SAFETY: load_notes() backs up before re-reading on a version
# upgrade (regression). Most of this safety net's logic (backup_notes_file,
# detect_version_change, run_migrations) is pure filesystem code tested
# directly in test_data_safety.py — this specifically checks the one part
# that needs a real running app: that load_notes() actually calls the
# backup when VERSION_CHANGE reports an upgrade. ----
_original_version_change = NO.VERSION_CHANGE
NO.VERSION_CHANGE = ('up', '0.0.1', NO.APP_VERSION)
app._version_backup_path = None
app.load_notes()
check('load_notes takes a safety backup when VERSION_CHANGE reports an upgrade',
      app._version_backup_path is not None and os.path.exists(app._version_backup_path))
if app._version_backup_path:
    os.remove(app._version_backup_path)
NO.VERSION_CHANGE = _original_version_change

print()
print(f"=== QA1 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
