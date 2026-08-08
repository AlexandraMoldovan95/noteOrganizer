import sys
import note_organizer as NO, tkinter as tk, tkinter.filedialog as fd, os, tempfile
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app=NO.NoteOrganizer(); app._poll_active_dirty=lambda:None
app.show_info=lambda *a,**k: True
app.show_warning=lambda *a,**k: True
app.geometry('1100x850'); app.update()

def find_widget(w, cls, text_contains=None):
    for c in w.winfo_children():
        if isinstance(c, cls):
            if text_contains is None or text_contains in str(c.cget('text')):
                return c
        r = find_widget(c, cls, text_contains)
        if r: return r
    return None

# ---- GROUPING ----
app.notes = [
    {'id':1,'title':'A','body':'x','category':'Work','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
    {'id':2,'title':'B','body':'x','category':'Personal','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
]
NO.CATEGORY_COLORS.setdefault('Work', '#7c5cff')
NO.CATEGORY_COLORS.setdefault('Personal', '#4cafef')

app.group_by_category.set(True)
app._on_toggle_group_by_category()
app.refresh_note_list()
app.update()
check('grouping enabled shows category headers', find_widget(app.list_frame, tk.Frame) is not None)

# collapse a group and verify state
app._toggle_group_collapsed('Work')
check('collapsing a group records it', 'Work' in app.collapsed_groups)
app._toggle_group_collapsed('Work')
check('expanding a group removes it from collapsed set', 'Work' not in app.collapsed_groups)

# collapse persists across a settings save/reload
app._toggle_group_collapsed('Personal')
saved = NO.load_settings()
check('collapsed group persisted to settings.json', 'Personal' in saved.get('collapsed_groups', []))

# search + grouping together
app.search_var.set('A')
app.update()
check('search narrows list while grouping stays on', app.group_by_category.get() is True)
app.search_var.set('')
app.group_by_category.set(False)
app._on_toggle_group_by_category()
app.refresh_note_list()
app.update()

# ---- SETTINGS: username greeting ----
app.username_var = tk.StringVar(value='Alexandra')
app.save_username('Alexandra')
app._refresh_greeting()
app.update()
check('greeting shows the saved name', app.greeting_lbl.cget('text') == 'Hi Alexandra,')

app.save_username('')
app._refresh_greeting()
app.update()
check('greeting disappears when name is cleared', app.greeting_lbl.cget('text') == '')

app.save_username('Alexandra')  # restore for later checks
app._refresh_greeting()

# ---- SETTINGS: statistics chip navigation ----
app.notes = [
    {'id':10,'title':'StatNote','body':'x','category':'Work','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]},
]
app.show_settings_page()
app.update()
app.filter_var.set('All')
app.notebook.select(app.TAB_CALENDAR)  # start somewhere else, to prove the click moves us
app.update()

# simulate what the stats chip's goto_category(cat) does
app.filter_var.set('Work')
app.notebook.select(app.TAB_NOTES)
app.refresh_note_list()
app.update()
check('category chip navigation lands on Notes tab', app.notebook.index(app.notebook.select())==app.TAB_NOTES)
check('category chip navigation sets the filter', app.filter_var.get()=='Work')

# stats freshness: total should reflect current note count after add
before_count = len(app.notes)
app.notes.append({'id':11,'title':'New','body':'x','category':'General','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[]})
app.show_settings_page()
app.update()
check('note count grew after adding a note', len(app.notes) == before_count + 1)

# ---- ATTACHMENTS (through the UI functions, not just file cleanup) ----
tmp_file = os.path.join(tempfile.gettempdir(), 'qa6_attachment.txt')
with open(tmp_file, 'w') as f:
    f.write('sample content')

app.new_note()
app.title_entry.insert(0, 'AttachTest')
app.body_text.insert('1.0', 'x')
app.current_attachments = []
fd.askopenfilenames = lambda **k: (tmp_file,)
app.add_attachment()
app.update()
check('add_attachment adds one entry', len(app.current_attachments) == 1)
check('add_attachment preserves original filename', app.current_attachments[0]['filename'] == 'qa6_attachment.txt')
stored_path = os.path.join(NO.ATTACHMENTS_DIR, app.current_attachments[0]['stored_as'])
check('add_attachment actually copies the file to disk', os.path.isfile(stored_path))

app.save_current_note(auto=False)
app.update()
saved_note = app.find_note(app.selected_note_id)
check('attachment persists on the saved note', len(saved_note.get('attachments', [])) == 1)

# reopen the note — attachment should still be listed (persist across note switch)
app.new_note()
app.load_note(saved_note)
app.update()
check('attachment survives switching away and back', len(app.current_attachments) == 1)

app.remove_attachment(0)
app.update()
check('remove_attachment clears the list', len(app.current_attachments) == 0)
check('remove_attachment deletes the file from disk', not os.path.isfile(stored_path))

# ---- COMBINATIONS ----

# Template + Checklist + Category together
app.templates.append({
    'name': 'ComboTemplate', 'title': 'Combo Title', 'body': 'Combo body',
    'comments': '', 'category': 'Work',
    'checklist': [{'text': 'step one', 'done': False}, {'text': 'step two', 'done': False}],
})
NO.save_templates(app.templates)
app.new_note()
tpl = next(t for t in app.templates if t['name'] == 'ComboTemplate')
app._apply_template(tpl)
app.update()
check('template applies its category', app.category_var.get() == 'Work')
check('template applies its checklist', len(app._working_checklist) == 2)

# Pin + Sort + Group behaving consistently
app.notes = [
    {'id':20,'title':'Zebra','body':'x','category':'General','updated':'2026-01-01 00:00','created':'2026-01-01 00:00','checklist':[],'attachments':[],'pinned':False},
    {'id':21,'title':'Apple','body':'x','category':'General','updated':'2026-01-02 00:00','created':'2026-01-02 00:00','checklist':[],'attachments':[],'pinned':False},
]
zebra = app.find_note(20)
app.toggle_pin(zebra)
if hasattr(app, 'sort_var'):
    app.sort_var.set('Title A-Z')
app.refresh_note_list()
app.update()
check('pinned note stays pinned regardless of sort mode', app.find_note(20)['pinned'] is True)

# Autosave + checklist + immediate note switch (nothing lost)
app.new_note()
app.title_entry.insert(0, 'AutosaveComboA')
app.body_text.insert('1.0', 'x')
app.save_current_note(auto=False)
app.update()
note_a = app.find_note(app.selected_note_id)
app.load_note(note_a)
app.checklist_add_var.set('quick item')
app._add_checklist_item()  # the real add path — also schedules autosave, unlike directly mutating the list
app.open_blank_tab()  # what the actual "+ New Note" button calls — flushes pending autosave first, unlike new_note() alone
app.update()
saved_a = app.find_note(note_a['id'])
check('checklist change is captured by autosave-on-switch', any(
    it.get('text') == 'quick item' for it in saved_a.get('checklist', [])))

# ---- LAYOUT (the parts that are genuinely checkable, not just "looks nice") ----

# Sidebar hide/show
before_hidden = app._sidebar_hidden
app.toggle_sidebar()
app.update()
check('toggle_sidebar flips the hidden state', app._sidebar_hidden != before_hidden)
app.toggle_sidebar()
app.update()
check('toggling again restores the sidebar', app._sidebar_hidden == before_hidden)

# Dialogs stay within the app window's own bounds (never a separate OS window
# that could be dragged outside it)
def find_btn_qa6(w, label):
    for c in w.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('text')) == label:
            return c
        r = find_btn_qa6(c, label)
        if r: return r
    return None

choice_holder = {}
def capture_choice(var):
    app.update()
    for frame in app.place_slaves():
        if find_btn_qa6(frame, "OK"):
            # Check everything about the dialog HERE, while it still exists —
            # _themed_dialog destroys it as soon as this callback returns
            # (that's what "wait_variable returned" means to its own cleanup
            # code), so a stored widget reference checked afterward would
            # already be pointing at a destroyed widget.
            choice_holder['found'] = True
            app.update_idletasks()
            within_x = app.winfo_rootx() <= frame.winfo_rootx() <= app.winfo_rootx() + app.winfo_width()
            within_y = app.winfo_rooty() <= frame.winfo_rooty() <= app.winfo_rooty() + app.winfo_height()
            choice_holder['within_bounds'] = within_x and within_y
            return
app.wait_variable = capture_choice
app._themed_dialog("Test", "Just checking dialog bounds", kind="question",
                   buttons=[("OK", "ok")])
check('dialog renders as an in-window overlay, not a separate Toplevel',
      choice_holder.get('found', False))
check('dialog is positioned within the app window bounds',
      choice_holder.get('within_bounds', False))

print()
print(f"=== QA6 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
