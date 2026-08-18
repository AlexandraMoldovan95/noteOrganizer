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

# ---- CALCULATOR ----
# Exercises the real button widgets (via .invoke(), like a real click) end
# to end, not just the evaluate_calculator_expression() function directly
# — that pure-logic side is covered separately in test_calculator.py.
# Uses an EXACT text match (not find_widget's substring match): the "C"
# clear button and the "✕ Close" button both live in this section, and
# "C" is a substring of "Close" — a substring search for "C" finds the
# Close button first, since the header (with Close) comes before the
# button grid (with Clear) in the widget tree.
def find_calc_btn(text):
    for c in app.calculator_section.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('text')) == text:
            return c
        for gc in c.winfo_children():
            if isinstance(gc, tk.Button) and str(gc.cget('text')) == text:
                return gc
    return None

app.new_note()
app.title_entry.insert(0,'CalcNote')
app.body_text.insert('1.0','Notes:\n')
app.update()
check('calculator starts closed', app._calculator_open == False)
app.toggle_calculator_section()
app.update()
check('calculator opens', app._calculator_open == True)
check('checklist and calculator sit side by side, not stacked',
      app.calculator_btn.winfo_rootx() > app.checklist_btn.winfo_rootx()
      and abs(app.calculator_btn.winfo_rooty() - app.checklist_btn.winfo_rooty()) < 5)
# The two columns should be genuinely equal width (grid's uniform group),
# not just "both expanding" — pack(expand=True) alone would size each to
# its own content and only split the *leftover* space evenly, which
# still leaves the wider one (the calculator's keypad) visibly bigger.
checklist_col_width = app.checklist_btn.master.winfo_width()
calculator_col_width = app.calculator_btn.master.winfo_width()
check(f'checklist and calculator columns are equal width '
      f'({checklist_col_width}px vs {calculator_col_width}px)',
      abs(checklist_col_width - calculator_col_width) <= 2)

for label in ['7', '×', '8']:  # 7 x 8, no "=" yet
    find_calc_btn(label).invoke()
    app.update()
check('insert into note is disabled mid-expression, before "="',
      str(app.calculator_insert_btn.cget('state')) == 'disabled')
check('typing cursor stays at the end after button presses, not stuck '
      'mid-text (icursor follows programmatic StringVar updates)',
      app.calculator_display.index('insert') == len(app._calc_display_var.get()))

find_calc_btn('=').invoke()
app.update()
check('calculator computes 7x8=56 via real button clicks',
      app._calc_display_var.get() == '56')
check('insert into note becomes enabled right after "="',
      str(app.calculator_insert_btn.cget('state')) == 'normal')
check('history records the calculation', app._calc_history == ['7×8=56'])
check('history stays hidden until the user asks for it',
      app._calc_history_open == False)

app._calc_insert_into_note()
app.update()
body_after_first_insert = app.body_text.get('1.0', 'end')
check('insert into note types the WHOLE formula, not just the result',
      '7×8=56' in body_after_first_insert)

# A second calculation, inserted again — must land on a new line after
# the first insertion, not glued onto it and not wherever the cursor
# happens to be (moved the cursor to the very start on purpose, to prove
# the insertion point is tracked independently of it).
find_calc_btn('C').invoke()
app.update()
check('Clear resets the expression', app._calc_display_var.get() == '')
app.body_text.mark_set('insert', '1.0')
for label in ['9', '−', '4', '=']:  # 9 - 4 =
    find_calc_btn(label).invoke()
    app.update()
app._calc_insert_into_note()
app.update()
body_after_second_insert = app.body_text.get('1.0', 'end')
check('second insertion also has the whole formula',
      '9−4=5' in body_after_second_insert)
first_pos = body_after_second_insert.find('7×8=56')
second_pos = body_after_second_insert.find('9−4=5')
check('second insertion lands on its own line, after the first one — '
      'not glued on, and not at the (moved) cursor position',
      second_pos > first_pos and body_after_second_insert[second_pos - 1] == '\n')
check('history now has both calculations, newest first',
      app._calc_history == ['9−4=5', '7×8=56'])

for label in ['5', '÷', '0', '=']:  # 5 / 0 =
    find_calc_btn(label).invoke()
    app.update()
check('division by zero shows Error via real button clicks',
      app._calc_display_var.get() == 'Error')
check('insert into note is disabled again after an Error',
      str(app.calculator_insert_btn.cget('state')) == 'disabled')

# ---- Direct typing/pasting into the display (not just buttons) ----
find_calc_btn('C').invoke()
app.update()
app._calc_display_var.set('6+6')  # simulates a paste — the StringVar is
                                   # the single source of truth regardless
                                   # of whether buttons or direct edits set it
app.calculator_display.event_generate('<KeyRelease>')
app.update()
check('insert stays disabled after a direct paste, before "=" is pressed',
      str(app.calculator_insert_btn.cget('state')) == 'disabled')
find_calc_btn('=').invoke()
app.update()
check('pressing "=" evaluates a pasted/typed expression correctly',
      app._calc_display_var.get() == '12')
check('insert becomes enabled after evaluating a pasted expression',
      str(app.calculator_insert_btn.cget('state')) == 'normal')

# ---- Extra functions (brackets, root, power, percent) ----
find_calc_btn('C').invoke()
app.update()
check('extra functions are collapsed by default', app._calc_more_open == False)
find_calc_btn('More functions  ▾').invoke()
app.update()
check('More functions opens the extra row', app._calc_more_open == True)
for label in ['√', '9']:  # sqrt(9)
    find_calc_btn(label).invoke()
    app.update()
find_calc_btn('=').invoke()
app.update()
check('square root works via the extra-functions row',
      app._calc_display_var.get() == '3')

find_calc_btn('C').invoke()
app.update()
for label in ['3', '^', '3']:  # 3^3 — a general power, not just a fixed square
    find_calc_btn(label).invoke()
    app.update()
find_calc_btn('=').invoke()
app.update()
check('the power button computes any exponent (3^3=27), not just squaring',
      app._calc_display_var.get() == '27')

# ---- History: hidden by default, toggle to reveal, click an entry to
# insert it, and a button to clear it out ----
hist_wrap_widget = app.calculator_history_section
check('history section is not packed (hidden) before toggling',
      not hist_wrap_widget.winfo_ismapped())
find_calc_btn('History  ▾').invoke()
app.update()
check('history becomes visible after the toggle', app._calc_history_open == True)
check('history section is now actually packed on screen',
      hist_wrap_widget.winfo_ismapped())

history_labels = [w for w in app.calculator_history_frame.winfo_children()
                   if isinstance(w, tk.Label)]
# 5 successful "="es so far this test (7x8, 9-4, 6+6, sqrt9, 3^3) — the
# 5/0 division-by-zero attempt correctly did NOT add an entry.
check('history shows one entry per past calculation', len(history_labels) == 5)
# Click the oldest entry (7×8=56) — should insert it, landing after
# whatever's already in the body from earlier insertions in this test.
target_entry = next(w for w in history_labels if str(w.cget('text')) == '7×8=56')
body_before_history_click = app.body_text.get('1.0', 'end')
target_entry.event_generate('<Button-1>')
app.update()
body_after_history_click = app.body_text.get('1.0', 'end')
check('clicking a history entry inserts that exact formula into the note',
      body_after_history_click.count('7×8=56') == body_before_history_click.count('7×8=56') + 1)

find_calc_btn('Clear').invoke()
app.update()
check('the Clear (history) button wipes the history', app._calc_history == [])
check('clearing history does not touch the current expression on display',
      app._calc_display_var.get() == '27')

find_calc_btn('✕ Close').invoke()
app.update()
check('closing collapses the calculator', app._calculator_open == False)

app.toggle_calculator_section()
find_calc_btn('9').invoke()
app.update()
app.new_note()
app.update()
check('calculator fully resets (collapsed, cleared, history wiped and '
      'hidden, extra row collapsed) when switching to a new note',
      app._calc_display_var.get() == '' and app._calculator_open == False
      and app._calc_history == [] and app._calc_more_open == False
      and app._calc_history_open == False)

# ---- RICH TEXT FORMATTING ----
# Exercises the real toolbar Button widgets (via .invoke(), like a real
# click), not _toggle_body_style() directly — that's already covered by a
# dedicated interactive script during development; this checks the actual
# UI path a user takes. Text "selection" is simulated via tag_add("sel", ..)
# directly on the Text widget, the same standard proxy used elsewhere in
# this file for widget state a real mouse-drag would otherwise set.
app.new_note()
app.title_entry.insert(0, 'FormattingNote')
app.body_text.insert('1.0', 'Hello world, this is bold and this is italic.')
app.update()

check('formatting toolbar has all four style buttons',
      set(app._fmt_buttons.keys()) == {'bold', 'italic', 'underline', 'strike'})

bold_start = app.body_text.search('bold', '1.0', 'end')
bold_end = f'{bold_start}+4c'

# ---- Keyboard shortcuts (Ctrl+B/I/U/D), same handler as the toolbar ----
# Checked here, right after the note is created, while body_text can still
# reliably take real Tk keyboard focus -- event_generate() needs actual
# focus to dispatch a synthetic key combo correctly (unlike .invoke() on a
# button, a direct call that bypasses focus entirely), and later in this
# script several popups (calculator's dropdowns, history) get opened and
# dismissed, which can leave a stale grab behind that swallows key events.
app.body_text.tag_add('sel', bold_start, bold_end)
app.body_text.focus_force()
app.update()
was_bold = 'bold' in app.body_text.tag_names(bold_start)
app.body_text.event_generate('<Control-b>')
app.update()
check('Ctrl+B toggles bold via keyboard, same handler as the toolbar button',
      ('bold' in app.body_text.tag_names(bold_start)) != was_bold)
app.body_text.event_generate('<Control-b>')  # toggle back off for the button test below
app.update()

app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '1.0', '1.0+3c')
app.update()
app.body_text.event_generate('<Control-u>')
app.update()
check('Ctrl+U toggles underline via keyboard', 'underline' in app.body_text.tag_names('1.0'))
app.body_text.event_generate('<Control-d>')
app.update()
check('Ctrl+D toggles strikethrough via keyboard', 'strike' in app.body_text.tag_names('1.0'))
app.body_text.event_generate('<Control-U>')  # uppercase (shift held) variant
app.update()
check('the uppercase Ctrl+Shift+U variant also fires the underline binding',
      'underline' not in app.body_text.tag_names('1.0'))
app.body_text.tag_remove('underline', '1.0', 'end')
app.body_text.tag_remove('strike', '1.0', 'end')

# ---- Toolbar buttons (real .invoke() clicks) ----
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', bold_start, bold_end)
app.update()
app._fmt_buttons['bold'].invoke()
app.update()
check('clicking the Bold toolbar button applies the bold tag',
      'bold' in app.body_text.tag_names(bold_start))

italic_start = app.body_text.search('italic', '1.0', 'end')
italic_end = f'{italic_start}+6c'
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', italic_start, italic_end)
app.update()
app._fmt_buttons['italic'].invoke()
app.update()
check('clicking the Italic toolbar button applies the italic tag',
      'italic' in app.body_text.tag_names(italic_start))

# Overlap bold + italic on the same word -> Tkinter can't combine two tags
# that both set "font", so this must become the single compound tag.
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', bold_start, bold_end)
app.update()
app._fmt_buttons['italic'].invoke()
app.update()
check('bold + italic together become one compound tag, not two conflicting ones',
      'bold_italic' in app.body_text.tag_names(bold_start)
      and 'bold' not in app.body_text.tag_names(bold_start))
app._fmt_buttons['bold'].invoke()
app.update()
check('un-bolding a bold+italic range correctly falls back to italic-only',
      'italic' in app.body_text.tag_names(bold_start)
      and 'bold_italic' not in app.body_text.tag_names(bold_start))

# Underline + strike are independent tags (no font conflict) and can coexist.
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '1.0', '1.0+5c')
app.update()
app._fmt_buttons['underline'].invoke()
app._fmt_buttons['strike'].invoke()
app.update()
us_names = app.body_text.tag_names('1.0')
check('underline and strikethrough toolbar buttons can both apply at once',
      'underline' in us_names and 'strike' in us_names)

# Toolbar reflects the selection's current style (pressed look), and clears
# once nothing relevant is selected.
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '1.0', '1.0+5c')
app._refresh_format_buttons()
check('toolbar shows Underline pressed while a fully-underlined range is selected',
      str(app._fmt_buttons['underline'].cget('relief')) == 'sunken')
app.body_text.tag_remove('sel', '1.0', 'end')
app._refresh_format_buttons()
check('toolbar buttons release when nothing is selected',
      str(app._fmt_buttons['underline'].cget('relief')) == 'flat')

# Clicking a style button with no selection must be a safe no-op, not a crash.
try:
    app._fmt_buttons['bold'].invoke()
    no_sel_crash = False
except Exception:
    no_sel_crash = True
check('clicking a formatting button with no selection does not crash', not no_sel_crash)

# ---- Save/reload round trip through the real editor flow ----
app.save_current_note(auto=False)
app.update()
fmt_note = app.find_note(app.selected_note_id)
check('note saved with a non-empty formatting field', bool(fmt_note.get('formatting')))
saved_formatting = fmt_note['formatting']

app.new_note()
app.update()
app.load_note(fmt_note)
app.update()
check('reopening the note reapplies its saved formatting to the editor',
      app._extract_formatting(app.body_text) is not None
      and sorted(app._extract_formatting(app.body_text), key=lambda s: (s['start'], s['style']))
      == sorted(saved_formatting, key=lambda s: (s['start'], s['style'])))

# ---- Template round trip ----
# save_current_as_template()'s actual name-entry step is an inline popup
# (_show_inline_rename), not worth simulating here — what matters is the
# data transformation it performs: capture_editor_state()'s "formatting"
# flowing into normalize_template(). Verified directly, the same way
# save_current_as_template()'s own do_save() callback builds its dict.
st_for_template = app.capture_editor_state()
built_tpl = NO.normalize_template({
    'name': 'FormatTemplate',
    'title': st_for_template.get('title', ''),
    'body': st_for_template.get('body', ''),
    'formatting': st_for_template.get('formatting', []),
    'comments': st_for_template.get('comments', ''),
    'category': st_for_template.get('category', 'General'),
    'checklist': st_for_template.get('checklist', []),
})
check('normalize_template preserves formatting from captured editor state',
      bool(built_tpl.get('formatting')))
app.templates.append(built_tpl)

app.new_note()
app.update()
app._apply_template(built_tpl)
app.update()
check('applying a template reapplies its formatting in the editor',
      bool(app._extract_formatting(app.body_text)))

# ---- Sticky format-at-cursor: toggle a style with NOTHING selected, then
# it applies to whatever gets typed next, until toggled off again. Real
# toolbar button clicks (.invoke()), same as everywhere else in this file.
# Uses a fresh note throughout and calls new_note() itself along the way,
# so it deliberately runs last in this section, after everything above
# that depends on "FormattingNote" still being the open note.
def type_char(ch):
    """Simulate one real keystroke: insert the char (what Tk's own default
    KeyPress binding does for a live keystroke), then fire the matching
    KeyRelease so _apply_pending_style_to_typed_char sees it, same order
    a real keypress produces."""
    app.body_text.insert('insert', ch)
    class _FakeEvent:
        pass
    fe = _FakeEvent()
    fe.char = ch
    fe.state = 0
    app._apply_pending_style_to_typed_char(fe)
    app.update()

app.new_note()
app.title_entry.insert(0, 'PendingStyleNote')
app.update()
check('no pending styles on a fresh note', app._pending_styles == set())

app.body_text.tag_remove('sel', '1.0', 'end')
app.update()
app._fmt_buttons['bold'].invoke()
app.update()
check('clicking Bold with nothing selected queues it as pending, not a no-op',
      app._pending_styles == {'bold'})
check('toolbar shows Bold pressed for the pending state even with no selection',
      str(app._fmt_buttons['bold'].cget('relief')) == 'sunken')

for ch in 'abc':
    type_char(ch)
check('characters typed while Bold is pending are tagged bold',
      all('bold' in app.body_text.tag_names(f'1.{i}') for i in range(3)))

app._fmt_buttons['bold'].invoke()  # toggle back off, still nothing selected
app.update()
check('clicking Bold again with nothing selected clears the pending style',
      app._pending_styles == set())
for ch in 'de':
    type_char(ch)
check('characters typed after turning pending Bold off are not bold',
      all('bold' not in app.body_text.tag_names(f'1.{i}') for i in (3, 4)))
check('earlier bold characters are unaffected by turning pending Bold off',
      all('bold' in app.body_text.tag_names(f'1.{i}') for i in range(3)))

# A real selection still works exactly as before, independent of pending
# state -- "def" here was typed with nothing pending, so this must turn
# bold ON for it (not off, the way it would for the already-bold "abc").
app.body_text.tag_add('sel', '1.3', '1.5')
app.update()
app._fmt_buttons['bold'].invoke()
app.update()
check('selecting text and clicking Bold still works, unaffected by pending-style logic',
      'bold' in app.body_text.tag_names('1.3'))
check('using the selection-based toggle does not touch _pending_styles',
      app._pending_styles == set())

app.body_text.tag_remove('sel', '1.0', 'end')
app._fmt_buttons['italic'].invoke()
app.update()
check('a pending style is queued right before switching notes',
      app._pending_styles == {'italic'})
app.new_note()
app.update()
check('starting a new note clears any pending style', app._pending_styles == set())

app.title_entry.insert(0, 'PendingSaveNote')
app.body_text.insert('1.0', 'plain text, nothing pending')
app.save_current_note(auto=False)
app.update()
pending_save_note = app.find_note(app.selected_note_id)
check('pending_styles is a live-editing concept only, never saved to the note',
      'pending_styles' not in pending_save_note)

# ---- Fast typing (regression): a first version tagged only "the one
# character right before the cursor" on each KeyRelease, which silently
# missed characters typed in a fast real burst -- Tk can queue several
# KeyPress insertions before dispatching the KeyRelease callbacks for
# them, so "before the cursor right now" can already be past more than
# one new character by the time a callback runs. Fixed by tagging the
# whole span from a tracked anchor mark to the cursor instead of just one
# character, so however many piled up before a callback's turn, the next
# one covers all of them. Reproduced here with when='tail' (queues events
# instead of processing them immediately) and NO update() between
# keystrokes, then a single update() to flush the whole burst at once --
# the same shape as a fast typist outrunning a naive per-keystroke
# handler.
app.new_note()
app.body_text.focus_force()
app.update()
app._fmt_buttons['bold'].invoke()
app.update()
check('bold queued as pending before the fast-typing burst', app._pending_styles == {'bold'})

fast_word = 'abcdefghijklmnopqrstuvwxyz1234'
for ch in fast_word:
    app.body_text.event_generate(f'<KeyPress-{ch}>', when='tail')
    app.body_text.event_generate(f'<KeyRelease-{ch}>', when='tail')
app.update()  # flushes the whole queued burst at once

check(f'all {len(fast_word)} fast-typed characters landed in the note',
      app.body_text.get('1.0', 'end-1c') == fast_word)
bold_ranges = app.body_text.tag_ranges('bold')
fully_bold = (len(bold_ranges) == 2
              and app._char_offset(app.body_text, bold_ranges[0]) == 0
              and app._char_offset(app.body_text, bold_ranges[1]) == len(fast_word))
check('every fast-typed character is bold, not just some of them '
      '(a single continuous tag range, not gaps and fragments)', fully_bold)

# ---- Moving the cursor without typing must resync the anchor, not let a
# later keystroke retroactively bold a stretch of older, unrelated text.
app._fmt_buttons['bold'].invoke()  # off
app.update()
app.new_note()
app.body_text.focus_force()
app.body_text.insert('1.0', 'existing text here')
app.body_text.mark_set('insert', '1.0')
app.update()
app._fmt_buttons['bold'].invoke()  # pending bold queued AT position 0
app.update()
app.body_text.mark_set('insert', 'end')
app.body_text.event_generate('<KeyRelease-End>')  # cursor moved, nothing typed
app.update()
type_char('X')
check('moving the cursor away before typing does not retroactively bold the older text',
      'bold' not in app.body_text.tag_names('1.0'))
check('the character actually typed after the cursor move is correctly bold',
      'bold' in app.body_text.tag_names('end-2c'))

# ---- A paste must never pick up a pending style, even though a paste
# also grows the character count (the same signal used to detect real
# typing) -- excluded via a dedicated <<Paste>> resync, not by inspecting
# the KeyRelease event that happens to follow it.
app.new_note()
app.body_text.focus_force()
app.update()
app._fmt_buttons['bold'].invoke()
app.update()
app.clipboard_clear()
app.clipboard_append('PASTED TEXT')
app.update()
app.body_text.event_generate('<<Paste>>')
app.update()
check('pasted text does not pick up the pending style',
      'bold' not in app.body_text.tag_names('1.0'))
check('pasted text lands correctly', app.body_text.get('1.0', 'end-1c') == 'PASTED TEXT')
type_char('Y')
check('typing right after a paste correctly resumes picking up the pending style',
      'bold' in app.body_text.tag_names('end-2c'))

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
