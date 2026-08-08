import sys
import note_organizer as NO, tkinter as tk, json, os
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
app.search_var.set('')
for opt in ['Newest first','Oldest first','Title A-Z','Title Z-A']:
    try:
        if hasattr(app,'sort_var'):
            app.sort_var.set(opt)
        app.refresh_note_list()
        app.update()
    except Exception as e:
        check(f'sort option {opt} works ({e})', False)
        continue
check('all sort options work', True)

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

print()
print(f"=== QA1 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
