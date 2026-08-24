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

# ---- BULLET AND NUMBERED LISTS ----
# A list is line-level state: the marker lives in the body text (so it
# survives export, share codes and plain-text copy untouched) while the
# hanging indent is a Tk tag rebuilt from the note's "paragraphs" field.
#
# Enter/Backspace are driven by calling the handlers directly rather than
# by event_generate: this is deep into the script, where body_text can no
# longer reliably take real keyboard focus, and a key event delivered to
# an unfocused widget silently does nothing at all. The bindings
# themselves are asserted separately, so the wiring is still covered.
app.new_note()
app.title_entry.insert(0, 'ListNote')
app.update()

check('list buttons live in their own registry, not among the style toggles',
      set(app._list_buttons.keys()) == {'bullet', 'number'}
      and set(app._fmt_buttons.keys()) == {'bold', 'italic', 'underline', 'strike'})
check('Return and BackSpace are bound on the body text',
      bool(app.body_text.bind('<Return>')) and bool(app.body_text.bind('<BackSpace>')))


def set_body(text):
    app.body_text.delete('1.0', 'end')
    app.body_text.insert('1.0', text)
    app.update()


def select_all_body():
    app.body_text.tag_add('sel', '1.0', 'end-1c')
    app.update()


def clear_selection():
    app.body_text.tag_remove('sel', '1.0', 'end')
    app.update()


def body():
    return app.body_text.get('1.0', 'end-1c')


set_body('milk\neggs\nbread')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
check('clicking the bullet button prefixes every selected line',
      body() == '• milk\n• eggs\n• bread')
check('each bulleted line is tagged, so the indent can be rebuilt on load',
      app._extract_paragraphs(app.body_text)
      == [{'line': 0, 'kind': 'bullet'},
          {'line': 1, 'kind': 'bullet'},
          {'line': 2, 'kind': 'bullet'}])

select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
check('switching a bullet list to numbers replaces the markers and counts up',
      body() == '1. milk\n2. eggs\n3. bread')

select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
check('clicking the same list button again turns the list back off',
      body() == 'milk\neggs\nbread')
check('turning a list off leaves no list tags behind',
      app._extract_paragraphs(app.body_text) == [])

# ---- Enter continues the list; Enter on an empty item leaves it ----
set_body('first')
select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
app.body_text.mark_set('insert', '1.end')
app._on_body_return(None)
app.body_text.insert('insert', 'second')
app.update()
check('Enter at the end of a numbered item starts the next one',
      body() == '1. first\n2. second')

app._on_body_return(None)
app.update()
check('Enter again adds an empty item, ready to type into',
      body() == '1. first\n2. second\n3. ')
app._on_body_return(None)
app.update()
check('Enter on an item you never typed into ends the list instead',
      body() == '1. first\n2. second\n')
check('ending the list leaves only the two real items tagged',
      app._extract_paragraphs(app.body_text)
      == [{'line': 0, 'kind': 'number'}, {'line': 1, 'kind': 'number'}])

# ---- Backspace against the marker ----
set_body('alpha')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.body_text.mark_set('insert', '1.2')  # immediately after "• "
app.update()
check('Backspace just after the marker removes the whole marker',
      app._on_body_backspace(None) == 'break' and body() == 'alpha')
check('removing the marker by Backspace also drops the list tag',
      app._extract_paragraphs(app.body_text) == [])

set_body('aaa')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.body_text.mark_set('insert', '1.4')  # mid-word
app.update()
check('Backspace elsewhere in the item is left to Tk, deleting one character',
      app._on_body_backspace(None) is None)

# ---- Marker and indent tag must not drift apart (regression) ----
# The indent tag first covered each line's trailing newline. Tk hands a tag
# on to text inserted between two characters that both carry it, so the next
# line inherited it: a line with no bullet in it counted as a bullet, was
# saved that way, and clicking the bullet button "did nothing" because the
# app thought it was already one and toggled it off. Fixed by ending the tag
# at .end and reading the marker in the text as the source of truth.
set_body('one\ntwo')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.body_text.insert('end-1c', '\nthree')
app.update()
check('a line added after a list item is not silently treated as an item',
      app._extract_paragraphs(app.body_text) == [{'line': 0, 'kind': 'bullet'},
                                             {'line': 1, 'kind': 'bullet'}])
app.body_text.tag_add('sel', '3.0', '3.end')
app.update()
app._list_buttons['bullet'].invoke()
clear_selection()
check('clicking the bullet button on that line adds a bullet, not removes one',
      body() == '\u2022 one\n\u2022 two\n\u2022 three')

# The mirror image: text typed at the END of an item is not inherited either,
# and an untagged wrap point loses the hanging indent, so a long item's
# second display line slid back under its own marker.
set_body('short')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.body_text.mark_set('insert', '1.end')
app.body_text.insert('insert', ' ' + 'word ' * 40)
app._refresh_format_buttons()
app.update()
# Asks the app for the tag name rather than spelling it out: there is one
# margin tag per list kind and depth, so a hard-coded name silently stops
# matching anything the moment that scheme changes, and a test that looks at
# nothing passes for free.
bullet_tag = app._paragraph_tag(app.body_text, 'bullet', 0)
tagged = app.body_text.tag_ranges(bullet_tag)
check('the indent tag grows to cover text typed at the end of an item',
      len(tagged) == 2
      and str(app.body_text.index(tagged[1])) == str(app.body_text.index('1.end')))

# The marker in the text is what makes a line an item -- the tag is only the
# indent drawn over it. Checked directly, because the two halves of that rule
# cover for each other: with the tag no longer reaching the newline, reading
# the tag instead of the marker happens to give the same answer everywhere
# else, so nothing else here would notice the rule being dropped.
set_body('plain line')
app.body_text.tag_add(bullet_tag, '1.0', '1.end')
app.update()
check('a stray indent tag on a line with no marker is not a list item',
      app._extract_paragraphs(app.body_text) == [])

set_body('plain\nlines')
app._apply_paragraphs(app.body_text, [{'line': 0, 'kind': 'bullet'}])
app.update()
check('a stored list line whose text lost its marker does not indent a plain line',
      not app.body_text.tag_ranges(bullet_tag))

# ---- The cursor's own line drives the button's pressed look ----
# Sets up its own list line instead of inheriting one from the checks above,
# so adding a check before this one cannot quietly change what it tests.
set_body('bullet me')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.body_text.mark_set('insert', '1.3')
app._refresh_list_buttons()
app.update()
check('the bullet button reads as pressed while the cursor is in a bullet item',
      str(app._list_buttons['bullet'].cget('relief')) == 'sunken'
      and str(app._list_buttons['number'].cget('relief')) == 'flat')

# ---- Renumbering when the widest marker shrinks (10. -> 9.) ----
# The marker is part of the body, so every character offset after it moves
# when the marker changes width. Formatting spans have to move with it or
# bold text slides sideways onto its neighbours.
set_body('\n'.join('item%d' % i for i in range(1, 11)))
select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
check('a ten-item list numbers past single digits correctly',
      body().split('\n')[9] == '10. item10')
app.body_text.tag_add('sel', '10.4', '10.end')
app.update()
app._fmt_buttons['bold'].invoke()
clear_selection()
check('bold applies to the text of the tenth item',
      app.body_text.get('bold.first', 'bold.last') == 'item10')
app.body_text.delete('1.0', '2.0')  # delete item 1 outright
app._renumber_lists()
app.update()
check('deleting the first item renumbers the rest down',
      body().split('\n')[-1] == '9. item10')
check('bold stays on its own text when the marker in front of it shrinks',
      app.body_text.get('bold.first', 'bold.last') == 'item10')

# ---- Save/reload round trip ----
app.new_note()
app.title_entry.insert(0, 'ListRoundTrip')
set_body('one\ntwo')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.save_current_note(auto=False)
app.update()
list_note = app.find_note(app.selected_note_id)
check('a saved note carries its list lines alongside its formatting',
      list_note.get('paragraphs') == [{'line': 0, 'kind': 'bullet'},
                                  {'line': 1, 'kind': 'bullet'}])
check('the markers themselves are saved as ordinary body text',
      list_note['body'] == '• one\n• two')
app.new_note()
app.update()
app.load_note(list_note)
app.update()
check('reopening the note puts the list tags back on the right lines',
      app._extract_paragraphs(app.body_text) == [{'line': 0, 'kind': 'bullet'},
                                             {'line': 1, 'kind': 'bullet'}])

# Saving over an existing note is a different code path from creating one,
# and the more common one -- a list usually grows after its note exists.
app.body_text.insert('end-1c', '\nthree')
app.body_text.tag_add('sel', '3.0', '3.end')
app.update()
app._list_buttons['bullet'].invoke()
clear_selection()
app.save_current_note(auto=False)
app.update()
grown_note = app.find_note(app.selected_note_id)
check('adding an item to an existing note updates the list lines it saves',
      grown_note['body'] == '\u2022 one\n\u2022 two\n\u2022 three'
      and grown_note.get('paragraphs') == [{'line': 0, 'kind': 'bullet'},
                                       {'line': 1, 'kind': 'bullet'},
                                       {'line': 2, 'kind': 'bullet'}])

# save_current_note() strips the body, so leading blank lines shift every
# line up. Without compensating, the reopened note indents the wrong ones.
app.new_note()
app.title_entry.insert(0, 'LeadingBlanks')
set_body('\n\nmilk\neggs')
app.body_text.tag_add('sel', '3.0', '4.end')
app.update()
app._list_buttons['bullet'].invoke()
clear_selection()
app.save_current_note(auto=False)
app.update()
blank_note = app.find_note(app.selected_note_id)
check('leading blank lines that saving strips also shift the list lines up',
      blank_note['body'] == '• milk\n• eggs'
      and blank_note.get('paragraphs') == [{'line': 0, 'kind': 'bullet'},
                                       {'line': 1, 'kind': 'bullet'}])

check('normalize_note drops list lines pointing past the end of the body',
      NO.normalize_note({'body': 'one\ntwo',
                         'paragraphs': [{'line': 0, 'kind': 'bullet'},
                                    {'line': 9, 'kind': 'bullet'}]})['paragraphs']
      == [{'line': 0, 'kind': 'bullet'}])

# ---- Templates carry lists too ----
st_for_list_tpl = app.capture_editor_state()
list_tpl = NO.normalize_template({
    'name': 'ListTemplate',
    'title': st_for_list_tpl.get('title', ''),
    'body': st_for_list_tpl.get('body', ''),
    'formatting': st_for_list_tpl.get('formatting', []),
    'paragraphs': st_for_list_tpl.get('paragraphs', []),
    'comments': st_for_list_tpl.get('comments', ''),
    'category': st_for_list_tpl.get('category', 'General'),
    'checklist': st_for_list_tpl.get('checklist', []),
})
check('normalize_template keeps list lines from captured editor state',
      bool(list_tpl.get('paragraphs')))
app.new_note()
app.update()
app._apply_template(list_tpl)
app.update()
check('applying a template rebuilds its list indents in the editor',
      bool(app._extract_paragraphs(app.body_text)))

# ---- PARAGRAPH ALIGNMENT ----
# Alignment is the other line-level property, and unlike a list marker it
# leaves nothing behind in the body text -- so it is read from its tag and
# has to be carried through save/reload by the paragraphs record alone.
app.new_note()
app.title_entry.insert(0, 'AlignNote')
app.update()

check('the alignment buttons live in their own registry',
      set(app._align_buttons.keys()) == {'left', 'center', 'right'})

set_body('one\ntwo\nthree')
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._set_paragraph_align('center')
clear_selection()
check('centring a line records it against that line only',
      app._extract_paragraphs(app.body_text) == [{'line': 0, 'align': 'center'}])
check('the body text itself is untouched by alignment',
      body() == 'one\ntwo\nthree')

app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._set_paragraph_align('center')
clear_selection()
check('clicking the alignment a line already has puts it back to left',
      app._extract_paragraphs(app.body_text) == [])

# Alignment must reach the newline: justify applies to a whole display line,
# so a range stopping at .end leaves the caret jumping back left the moment
# Enter is pressed on a centred line.
set_body('heading')
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._set_paragraph_align('center')
clear_selection()
app.body_text.insert('1.end', '\n')      # what pressing Enter there does
app.update()
check('alignment carries onto the new line when Enter ends a centred one',
      'align_center' in app.body_text.tag_names('2.0'))

# A centred bullet keeps both properties: they set different Tk options.
set_body('milk\neggs')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._set_paragraph_align('right')
clear_selection()
check('a line can be both a list item and aligned',
      app._extract_paragraphs(app.body_text)
      == [{'line': 0, 'kind': 'bullet', 'align': 'right'},
          {'line': 1, 'kind': 'bullet'}])

# ---- Alignment round trip ----
app.new_note()
app.title_entry.insert(0, 'AlignRoundTrip')
set_body('title line\nbody line')
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._set_paragraph_align('center')
clear_selection()
app.save_current_note(auto=False)
app.update()
align_note = app.find_note(app.selected_note_id)
check('alignment is saved on a note with no list at all',
      align_note.get('paragraphs') == [{'line': 0, 'align': 'center'}])
app.new_note()
app.update()
app.load_note(align_note)
app.update()
check('reopening the note re-centres the right line',
      app._paragraph_align_of(app.body_text, 1) == 'center'
      and app._paragraph_align_of(app.body_text, 2) == 'left')

check('normalize_paragraphs drops an entry that says nothing',
      NO.normalize_paragraphs([{'line': 0}, {'line': 1, 'align': 'left'}]) == [])
check('normalize_paragraphs rejects an alignment it does not know',
      NO.normalize_paragraphs([{'line': 0, 'align': 'sideways'}]) == [])

# ---- INDENTATION AND MULTILEVEL LISTS ----
# Depth is one property for both jobs: on a list line it is the nesting
# level, on a plain line it is just a left margin. Numbering restarts per
# level *and* per parent, which is the part worth pinning down.
app.new_note()
app.title_entry.insert(0, 'NestNote')
app.update()


def lines_now():
    return app.body_text.get('1.0', 'end-1c').split('\n')


def depths():
    return [app._paragraph_indent_of(app.body_text, n)
            for n in range(1, len(lines_now()) + 1)]


def indent_range(a, z, delta):
    app.body_text.tag_add('sel', f'{a}.0', f'{z}.end')
    app.update()
    app._change_paragraph_indent(delta)
    clear_selection()


set_body('first\nsub one\nsub two\nsecond\nsub A\nsub B')
select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
indent_range(2, 3, +1)
indent_range(5, 6, +1)
check('a nested numbered run restarts at one under each parent',
      lines_now() == ['1. first', '1. sub one', '2. sub two',
                      '2. second', '1. sub A', '2. sub B'])
check('the outer numbering ignores the nested items',
      depths() == [0, 1, 1, 0, 1, 1])

indent_range(3, 3, +1)
check('going a level deeper again restarts that level too',
      lines_now()[2] == '1. sub two' and depths()[2] == 2)

indent_range(1, 6, -1)
check('outdenting the whole list pulls every line back one step, '
      'clamping the ones already at the margin',
      depths() == [0, 0, 1, 0, 0, 0])

# Bullets show their depth in the glyph, which is what makes a bullet
# recognisable from the text alone at any level.
set_body('top\nalpha\nbeta')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
indent_range(2, 2, +1)
indent_range(3, 3, +1)
indent_range(3, 3, +1)
check('each bullet level gets its own glyph',
      lines_now() == ['\u2022 top', '\u25e6 alpha', '\u25aa beta'])
check('outdenting a bullet puts its glyph back',
      (indent_range(3, 3, -1) or lines_now()[2]) == '\u25e6 beta')

# Depth survives changing the list kind, and survives turning it off.
set_body('item')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
indent_range(1, 1, +1)
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._list_buttons['number'].invoke()
clear_selection()
check('switching a nested bullet to a number keeps it at its depth',
      lines_now() == ['1. item'] and depths() == [1])
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._list_buttons['number'].invoke()
clear_selection()
check('turning the list off leaves the line indented, not snapped left',
      lines_now() == ['item'] and depths() == [1])

# A plain paragraph can be indented with no list involved at all.
set_body('a plain paragraph')
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._change_paragraph_indent(+1)
clear_selection()
check('a plain paragraph records its indent and no list kind',
      app._extract_paragraphs(app.body_text) == [{'line': 0, 'indent': 1}])

check('indent is clamped so it cannot run off the edge',
      NO.normalize_paragraphs([{'line': 0, 'indent': 999}])
      == [{'line': 0, 'indent': NO.MAX_INDENT}])
check('a nonsense indent is discarded rather than repaired',
      NO.normalize_paragraphs([{'line': 0, 'indent': 'deep'}]) == [])

# ---- Keyboard: Tab, Enter and Backspace against depth ----
set_body('one')
select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
app.body_text.mark_set('insert', '1.end')
app._on_body_return(None)
app.body_text.insert('insert', 'two')
app.update()
app._on_body_tab(None, +1)
check('Tab demotes the item the cursor is in',
      lines_now() == ['1. one', '1. two'] and depths() == [0, 1])
app._on_body_tab(None, -1)
check('Shift+Tab promotes it again',
      lines_now() == ['1. one', '2. two'] and depths() == [0, 0])


app._on_body_tab(None, +1)
app._on_body_return(None)
app.update()
check('Enter starts the next item at the same depth',
      depths() == [0, 1, 1])
app._on_body_return(None)
app.update()
# Both outcomes leave the line at depth 0, so the depth alone cannot tell
# them apart -- what differs is whether it is still a list item.
check('Enter on an empty nested item climbs out one level first',
      depths() == [0, 1, 0] and lines_now()[2].strip() != '')
app._on_body_return(None)
app.update()
check('Enter again on the now-unnested empty item leaves the list',
      lines_now()[2] == '')

# On a bullet, the glyph is what shows the depth, so this is where Enter
# carrying the level can actually be seen -- a numbered marker reads "1. "
# at every depth and would hide the difference.
set_body('parent')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
indent_range(1, 1, +1)
app.body_text.mark_set('insert', '1.end')
app._on_body_return(None)
app.body_text.insert('insert', 'sibling')
app.update()
check("Enter keeps a nested bullet's own glyph on the next item",
      lines_now() == ['\u25e6 parent', '\u25e6 sibling'] and depths() == [1, 1])

set_body('alpha')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
indent_range(1, 1, +1)
app.body_text.mark_set('insert', '1.2')
app.update()
check('Backspace against a nested marker outdents instead of deleting it',
      app._on_body_backspace(None) == 'break'
      and lines_now() == ['\u2022 alpha'] and depths() == [0])

set_body('just prose')
app.body_text.mark_set('insert', '1.4')
app.update()
check('Tab in ordinary prose is left to Tk, so it still types a tab',
      app._on_body_tab(None, +1) is None)

# ---- Nesting round trip ----
app.new_note()
app.title_entry.insert(0, 'NestRoundTrip')
set_body('parent\nchild')
select_all_body()
app._list_buttons['number'].invoke()
clear_selection()
indent_range(2, 2, +1)
app.save_current_note(auto=False)
app.update()
nest_note = app.find_note(app.selected_note_id)
check('depth is saved alongside the list kind',
      nest_note.get('paragraphs') == [{'line': 0, 'kind': 'number'},
                                      {'line': 1, 'kind': 'number', 'indent': 1}])
app.new_note()
app.update()
app.load_note(nest_note)
app.update()
check('reopening the note puts the child back at its own depth',
      depths() == [0, 1] and lines_now() == ['1. parent', '1. child'])

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

# ---- Text color / Highlight (Phase 2): real toolbar button click opens
# the picker popup, then a real swatch button inside it is clicked --
# not calling _apply_body_color() directly, matching how the rest of
# this file exercises real widgets.
def find_swatch_button(widget, bg_color):
    for c in widget.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('bg')) == bg_color:
            return c
        found = find_swatch_button(c, bg_color)
        if found:
            return found
    return None

def find_button_by_text(widget, text):
    for c in widget.winfo_children():
        if isinstance(c, tk.Button) and str(c.cget('text')) == text:
            return c
        found = find_button_by_text(c, text)
        if found:
            return found
    return None

app.new_note()
app.body_text.insert('1.0', 'Colorful text for testing.')
app.update()
color_start = app.body_text.search('Colorful', '1.0', 'end')
color_end = f'{color_start}+8c'
app.body_text.tag_add('sel', color_start, color_end)
app.update()

app.text_color_btn.invoke()
app.update()
check('clicking the text-color toolbar button opens a popup',
      app._mini_popup is not None and app._mini_popup.winfo_exists())
swatch = find_swatch_button(app._mini_popup, NO.PRESET_NOTE_COLORS[0])
check('the popup shows a real, clickable swatch button for the first palette color',
      swatch is not None)
if swatch:
    app.body_text.tag_add('sel', color_start, color_end)
    swatch.invoke()
    app.update()
check('clicking a real swatch button applies that text color to the selection',
      any(n.startswith('text_color_' + NO.PRESET_NOTE_COLORS[0].lstrip('#'))
          for n in app.body_text.tag_names(color_start)))

# Highlight: same real-button-click pattern, different palette/button.
app.body_text.tag_add('sel', color_start, color_end)
app.update()
app.highlight_btn.invoke()
app.update()
hl_swatch = find_swatch_button(app._mini_popup, NO.HIGHLIGHT_COLOR_PALETTE[0])
check('the highlight popup shows a real swatch for the first highlight color',
      hl_swatch is not None)
if hl_swatch:
    app.body_text.tag_add('sel', color_start, color_end)
    hl_swatch.invoke()
    app.update()
check('clicking a real highlight swatch applies it, alongside the existing text color',
      any(n.startswith('highlight_' + NO.HIGHLIGHT_COLOR_PALETTE[0].lstrip('#'))
          for n in app.body_text.tag_names(color_start))
      and any(n.startswith('text_color_' + NO.PRESET_NOTE_COLORS[0].lstrip('#'))
              for n in app.body_text.tag_names(color_start)))

# Clear via the popup's real Clear button.
app.body_text.tag_add('sel', color_start, color_end)
app.update()
app.text_color_btn.invoke()
app.update()
clear_btn = find_button_by_text(app._mini_popup, 'Clear')
check('the popup has a real Clear button', clear_btn is not None)
if clear_btn:
    app.body_text.tag_add('sel', color_start, color_end)
    clear_btn.invoke()
    app.update()
check('clicking Clear removes the text color but leaves the highlight',
      not any(n.startswith('text_color_') for n in app.body_text.tag_names(color_start))
      and any(n.startswith('highlight_') for n in app.body_text.tag_names(color_start)))

# Pending color (nothing selected) sticks for future typing, same
# mechanism as the boolean styles.
app.body_text.tag_remove('sel', '1.0', 'end')
app.update()
app._apply_body_color('highlight', NO.HIGHLIGHT_COLOR_PALETTE[1])
app.update()
check('pending highlight queued via the toolbar path',
      app._pending_highlight_color == NO.HIGHLIGHT_COLOR_PALETTE[1])
type_char('Z')
check('a character typed while a highlight is pending picks it up',
      any(n.startswith('highlight_' + NO.HIGHLIGHT_COLOR_PALETTE[1].lstrip('#'))
          for n in app.body_text.tag_names('end-2c')))

# Save/reload round trip.
app.save_current_note(auto=False)
app.update()
color_note = app.find_note(app.selected_note_id)
color_spans = [s for s in color_note.get('formatting', []) if s.get('style') in ('text_color', 'highlight')]
check('color spans were saved with the note', len(color_spans) >= 1)
app.new_note()
app.update()
app.load_note(color_note)
app.update()
reloaded_colors = [s for s in app._extract_formatting(app.body_text)
                   if s.get('style') in ('text_color', 'highlight')]
check('reopening the note reapplies its saved color formatting',
      len(reloaded_colors) == len(color_spans))

# ---- Regression: a highlight covering a line's newline made Tk paint the
# background across the FULL remaining width of that line, so highlighting
# several lines drew full-width bars instead of hugging the words. The tag
# must never sit on a "\n" -- checked on the widget itself, since the
# character range alone looked correct even while it rendered wrong.
app.new_note()
app.update()
app.body_text.insert('1.0', 'alpha\nbeta\ngamma\n')
app.body_text.tag_add('sel', '1.0', '3.3')
app.update()
app._apply_body_color('highlight', NO.HIGHLIGHT_COLOR_PALETTE[0])
app.body_text.tag_remove('sel', '1.0', 'end')
app.update()
hl_tag = app._color_tag_name('highlight', NO.HIGHLIGHT_COLOR_PALETTE[0])
hl_ranges = app.body_text.tag_ranges(hl_tag)
check('a multi-line highlight is applied at all', len(hl_ranges) >= 2)
newline_tagged = []
for i in range(0, len(hl_ranges), 2):
    idx = app.body_text.index(hl_ranges[i])
    while app.body_text.compare(idx, '<', hl_ranges[i + 1]):
        if app.body_text.get(idx) == '\n':
            newline_tagged.append(str(idx))
        idx = app.body_text.index(idx + '+1c')
check('a multi-line highlight never covers a newline (no full-width bleed)',
      not newline_tagged)
# The lines it did cover must still be fully highlighted up to their text end.
check('the fully-covered line is still highlighted across its own text',
      hl_tag in app.body_text.tag_names('1.0')
      and hl_tag in app.body_text.tag_names('1.4'))
# Toolbar preview must still recognise the color despite the untagged newlines.
check('toolbar still previews the highlight color across a multi-line range',
      app._uniform_color_in_selection('highlight', '1.0', '3.3')
      == NO.HIGHLIGHT_COLOR_PALETTE[0])
# An old note whose saved span crosses lines must also load without bleeding.
app.new_note()
app.update()
app.body_text.insert('1.0', 'alpha\nbeta\ngamma\n')
app._apply_formatting(app.body_text,
                      [{'start': 0, 'end': 13, 'style': 'highlight',
                        'value': NO.HIGHLIGHT_COLOR_PALETTE[0]}])
app.update()
legacy_ranges = app.body_text.tag_ranges(hl_tag)
legacy_newlines = []
for i in range(0, len(legacy_ranges), 2):
    idx = app.body_text.index(legacy_ranges[i])
    while app.body_text.compare(idx, '<', legacy_ranges[i + 1]):
        if app.body_text.get(idx) == '\n':
            legacy_newlines.append(str(idx))
        idx = app.body_text.index(idx + '+1c')
check('a legacy saved span crossing lines also loads without covering newlines',
      len(legacy_ranges) >= 2 and not legacy_newlines)

# ---- Regression: a placeholder-registered widget (self._placeholders)
# that gets destroyed before the next theme switch used to crash with
# "invalid command name" -- the widget is long gone by the time
# _refresh_placeholder_colors tries to read it. This used to be exercised
# via the color picker's hex-code entry, since destroyed on every popup
# close; that entry was removed (swatches only now, no hex input), so this
# drives the same self._placeholders/_refresh_placeholder_colors mechanism
# directly with a throwaway widget instead of relying on incidental popup
# structure that can change independently of this regression.
# Track THIS specific entry by identity, not a raw list count -- earlier
# parts of this same test run (template editor, category pickers, ...)
# may already have left their own stale, not-yet-pruned entries sitting
# in self._placeholders, so comparing counts would be thrown off by
# however many of THOSE also get swept up by the same theme switch.
entries_before = {id(e) for e, _ in app._placeholders}
throwaway = NO.tk.Entry(app)
app.add_placeholder(throwaway, 'throwaway placeholder')
app.update()
new_entries = [e for e, _ in app._placeholders if id(e) not in entries_before]
check('add_placeholder registers the widget in self._placeholders', len(new_entries) == 1)
my_entry = new_entries[0] if new_entries else None
throwaway.destroy()
app.update()
try:
    app.set_theme('light' if app.theme_name != 'light' else 'dark')
    app.update()
    theme_switch_ok = True
except Exception as e:
    print('  exception:', e)
    theme_switch_ok = False
check('switching themes after the widget is destroyed does not crash', theme_switch_ok)
check('the destroyed entry is pruned from self._placeholders, not left dangling',
      my_entry is not None and all(e is not my_entry for e, _ in app._placeholders))

# ---- A theme switch recolours the note cards in place instead of destroying
# and rebuilding every one of them (that rebuild was the bulk of the switch's
# cost, and made the list visibly empty and refill). Two things must hold:
# the result has to be identical to what a real rebuild produces, and a note's
# OWN colour must survive -- _recolor_stragglers would otherwise swap out a
# custom colour that happens to match another theme's palette entry.
_theme_opts = ('bg', 'fg', 'highlightbackground', 'highlightcolor')

def _card_colors():
    out = []
    def walk(w):
        row = [w.__class__.__name__]
        for o in _theme_opts:
            try:
                row.append(str(w.cget(o)).lower())
            except Exception:
                pass
        out.append(tuple(row))
        for ch in w.winfo_children():
            walk(ch)
    walk(app.list_frame)
    return out

app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Palette clash note')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'body')
# '#7c5cff' is a preset note colour AND the dark theme's accent -- the exact
# case where a colour-swapping pass would wrongly repaint it.
app.current_note_color = '#7c5cff'
app.save_current_note(auto=False)
app.update()

app.set_theme('dark')
app.update()
_clash_id = app.selected_note_id
for _theme in ('dark_ocean', 'light_sky', 'light', 'dark'):
    app.set_theme(_theme)
    app.update()
    _in_place = _card_colors()
    app.refresh_note_list()
    app.update()
    check(f'theme switch to {_theme}: in-place card recolour matches a full rebuild',
          _in_place == _card_colors())

app.set_theme('dark_ocean')
app.update()
_info = app._note_card_widgets.get(_clash_id)
check("a note's own colour survives a theme switch that doesn't share it",
      _info is not None
      and str(_info['stripe'].cget('bg')).lower()
      == app.get_note_color(_info['note']).lower())
app.set_theme('dark')
app.update()

# ---- A theme switch shouldn't rebuild the calendar while it's off screen
# (that was ~19ms of pointless churn per switch). It must still be caught up
# before it becomes visible, so it can never be left showing stale colours.
app._calendar_needs_render = False
app.set_theme('light')
app.update()
check('a theme switch defers the calendar rebuild while it is off screen',
      getattr(app, '_calendar_needs_render', False) is True)
app._catch_up_deferred_refresh()
app.update()
check('the deferred calendar rebuild is caught up at the next transition',
      getattr(app, '_calendar_needs_render', False) is False)

# Statistics is no longer rebuilt on a theme switch either (nothing about a
# statistic changes when only the palette does), so it must be left with no
# colour from the previous theme.
def _stale_colors(root):
    _cur = {v.lower() for v in app.colors.values()
            if isinstance(v, str) and v.startswith('#')}
    _other = set()
    for _n, _p in NO.THEMES.items():
        if _n == app.theme_name:
            continue
        for _v in _p.values():
            if isinstance(_v, str) and _v.startswith('#'):
                _other.add(_v.lower())
    _suspect = _other - _cur
    _bad = []
    def _walk(w):
        for _o in ('bg', 'fg'):
            try:
                if str(w.cget(_o)).lower() in _suspect:
                    _bad.append((w.__class__.__name__, _o))
            except Exception:
                pass
        for _c in w.winfo_children():
            _walk(_c)
    _walk(root)
    return _bad

for _theme in ('dark_ocean', 'light', 'dark'):
    app.set_theme(_theme)
    app.update()
    check(f'statistics carries no stale colour after switching to {_theme}',
          not _stale_colors(app.stats_frame))

# ---- Right-click menu labels must all be plain text, so every entry starts
# at the same x. They used to carry a mix of astral math letters, combining
# underline/strike marks and emoji, which render at different widths and left
# the words after them lining up with nothing.
def _menu_labels(widget):
    menus = [w for w in widget.winfo_children() if isinstance(w, NO.tk.Menu)]
    if not menus:
        return []
    m = menus[0]
    return [m.entrycget(i, 'label') for i in range(m.index('end') + 1)
            if m.type(i) == 'command']

def _is_plain(s):
    return all(not (ord(c) > 0x2100 or 0x0300 <= ord(c) <= 0x036F) for c in s)

_body_menu = _menu_labels(app.body_text)
check('every right-click menu label is plain text (aligned, no glyph prefixes)',
      bool(_body_menu) and all(_is_plain(l) for l in _body_menu))
check('no right-click menu label is indented relative to the others',
      all(l == l.lstrip() for l in _body_menu))
check('the formatting entries are still present in the body menu',
      {'Bold', 'Italic', 'Underline', 'Strikethrough'} <= set(_body_menu))

# ---- Regression: the comments box had none of the note body's selection
# fixes, so double-clicking a row with no words in it grabbed that row's
# invisible newline and painted a full-width selection over an empty line.
def _dbl_xy(w, x, y, t):
    w.event_generate('<Button-1>', x=x, y=y, time=t)
    w.event_generate('<ButtonRelease-1>', x=x, y=y, time=t + 10)
    w.event_generate('<Button-1>', x=x, y=y, time=t + 120)
    w.event_generate('<ButtonRelease-1>', x=x, y=y, time=t + 130)
    app.update()
    r = w.tag_ranges('sel')
    return w.get(r[0], r[1]) if r else None

app.new_note()
app.update()
_c = app.comments_text
_c.delete('1.0', 'end')
_c.insert('1.0', 'hello world\n\nfoo.bar\n')
app.update()
_bb = _c.bbox('2.0')
check('comments: double-clicking an empty row selects nothing',
      _bb is not None
      and _dbl_xy(_c, _bb[0] + 2, _bb[1] + _bb[3] // 2, 41000) is None)
_c.tag_remove('sel', '1.0', 'end')
app.update()
_bbw = _c.bbox('1.2')
check('comments: double-clicking a word selects just that word',
      _bbw is not None
      and _dbl_xy(_c, _bbw[0] + _bbw[2] // 2, _bbw[1] + _bbw[3] // 2, 42000) == 'hello')
_c.tag_remove('sel', '1.0', 'end')
app.update()
_bbp = _c.bbox('3.1')
check('comments: punctuation breaks a double-clicked word, same as the body',
      _bbp is not None
      and _dbl_xy(_c, _bbp[0] + _bbp[2] // 2, _bbp[1] + _bbp[3] // 2, 43000) == 'foo')
_c.tag_remove('sel', '1.0', 'end')
_c.delete('1.0', 'end')
app.update()

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
