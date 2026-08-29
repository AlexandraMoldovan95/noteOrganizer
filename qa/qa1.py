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
import time
import note_organizer as NO, tkinter as tk, json, os, re
from noteorganizer.core import tables as core_tables
fails=[]
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)


def take_focus(widget, attempts=60):
    """Give a widget the keyboard focus, and wait until Tk agrees it has it.

    focus_force() is a request, not an accomplished fact. event_generate()
    for a key combination needs the focus to have actually arrived, and
    under the load of a full-suite run it does not always get there within
    a single update() -- which is why the shortcut checks below have failed
    at random and never once when this file is run on its own.
    """
    widget.focus_force()
    for _ in range(attempts):
        app.update()
        app.update_idletasks()
        if app.focus_get() is widget:
            return True
        time.sleep(0.01)
    return False


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
take_focus(app.body_text)
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
    app._teardown_table_grids()
    app._last_caret_line = None
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

# ---- THE QUOTE BLOCK IS GONE (regression) ----
# Removed on request: it read as a heavy visual device for something a
# note rarely needs, and it was the only paragraph property that carried
# its own colours. Checked rather than merely deleted, so it cannot
# reappear by accident -- and so a note that still carries the old
# block:"quote" key is known to degrade to a plain paragraph rather than
# to anything stranger.
check('the editor exposes no block-style buttons at all',
      not hasattr(app, '_block_buttons'))
check('a paragraph property named block is no longer recognised',
      NO.normalize_paragraphs([{'line': 0, 'block': 'quote'}]) == [])
check('a note saved with the old quote key loads as a plain paragraph',
      NO.normalize_paragraphs(
          [{'line': 0, 'kind': 'bullet', 'block': 'quote'}])
      == [{'line': 0, 'kind': 'bullet'}])

# ---- TOOLBAR TOOLTIPS ----
# Every button on the formatting bar is an icon or a single letter, so each
# one carries a short label on hover.
app.new_note()
app.update()

formatting_buttons = (list(app._fmt_buttons.values())
                      + [app.text_color_btn, app.highlight_btn]
                      + list(app._list_buttons.values())
                      + list(app._align_buttons.values()))
check(f'every formatting button carries a tooltip ({len(formatting_buttons)} of them)',
      all(bool(w.bind('<Enter>')) and bool(w.bind('<Leave>'))
          for w in formatting_buttons))

# Nothing appears at once: sweeping the pointer across the bar on the way
# somewhere else should not flash a row of labels.
app._hide_tooltip()
app._schedule_tooltip(app._list_buttons['bullet'], 'Bullet list', 'detail')
app.update()
check('hovering schedules the tooltip rather than showing it straight away',
      getattr(app, '_tooltip', None) is None
      and getattr(app, '_tooltip_after', None) is not None)

check('leaving before the delay is up cancels it',
      (app._hide_tooltip() or True)
      and getattr(app, '_tooltip_after', None) is None
      and getattr(app, '_tooltip', None) is None)

app._show_tooltip(app._list_buttons['bullet'], 'Bullet list',
                  'Whole lines — click again to turn the list off')
app.update()
tip = getattr(app, '_tooltip', None)
check('the tooltip is a real window once shown',
      tip is not None and tip.winfo_exists())


def tooltip_texts(widget):
    found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            found.append(str(child.cget('text')))
        found.extend(tooltip_texts(child))
    return found


check('it shows both the name and the explanation',
      tip is not None
      and 'Bullet list' in tooltip_texts(tip)
      and any('turn the list off' in t for t in tooltip_texts(tip)))

app._hide_tooltip()
app.update()
check('moving the pointer away takes it down again',
      getattr(app, '_tooltip', None) is None)

# Hovering one button then another must not leave the first one stranded.
app._show_tooltip(app._list_buttons['bullet'], 'Bullet list', 'one')
first_tip = app._tooltip
app._schedule_tooltip(app._list_buttons['number'], 'Numbered list', 'two')
app.update()
check('hovering a second button removes the first tooltip',
      not first_tip.winfo_exists() and getattr(app, '_tooltip', None) is None)
app._hide_tooltip()

# A button that has gone away must not produce a stray window.
ghost = tk.Button(app, text='x')
ghost.destroy()
crashed = False
try:
    app._show_tooltip(ghost, 'Gone', 'detail')
    app.update()
except Exception:
    crashed = True
check('a tooltip for a widget that no longer exists is skipped, not crashed',
      not crashed and getattr(app, '_tooltip', None) is None)

check('hiding when nothing is showing is harmless',
      (app._hide_tooltip() or True) and getattr(app, '_tooltip', None) is None)

# ---- FONT SIZE AND FAMILY ----
# Size and family fight bold and italic over Tk's font option -- two tags
# that set it do not compose, one wins -- so all four are merged into one
# composite tag at render time while staying separate spans in the note.
app.new_note()
app.title_entry.insert(0, 'FontNote')
app.update()


def font_spans():
    return sorted((s['start'], s['end'], s['style'], s.get('value'))
                  for s in app._extract_formatting(app.body_text))


def select(a, z):
    app.body_text.tag_add('sel', a, z)
    app.update()


set_body('hello world again')
select('1.0', '1.5')
app._apply_body_font('font_size', 20)
clear_selection()
check('a size applies to the selected characters only',
      font_spans() == [(0, 5, 'font_size', 20)])
check('applying a size leaves the text itself untouched',
      body() == 'hello world again')

select('1.0', '1.11')
app._apply_body_font('font_family', 'Georgia')
clear_selection()
check('a family can cover a different range from the size',
      font_spans() == [(0, 5, 'font_size', 20),
                       (0, 11, 'font_family', 'Georgia')])

select('1.6', '1.11')
app._toggle_body_style('bold')
clear_selection()
check('bold still records itself separately inside a resized run',
      font_spans() == [(0, 5, 'font_size', 20),
                       (0, 11, 'font_family', 'Georgia'),
                       (6, 11, 'bold', None)])
check('the plain bold tag is still on the text, so the toolbar can see it',
      'bold' in app.body_text.tag_names('1.7'))
check('and a composite font tag sits over it',
      any(NO.parse_font_tag(n) for n in app.body_text.tag_names('1.7')))

# The dropdowns report what is actually there, and refuse to guess.
select('1.0', '1.5')
app._refresh_format_buttons()
check('the dropdowns show the size and family of a uniform selection',
      app.font_size_var.get() == '20'
      and app.font_family_var.get() == 'Georgia')
clear_selection()
select('1.0', '1.17')
app._refresh_format_buttons()
check('a selection spanning two different sizes reads as Default, not the first',
      app.font_size_var.get() == app.DEFAULT_FONT_LABEL)
clear_selection()

select('1.0', '1.5')
app._apply_body_font('font_size', None)
clear_selection()
check('choosing Default removes the size rather than storing one',
      font_spans() == [(0, 11, 'font_family', 'Georgia'), (6, 11, 'bold', None)])

# ---- Round trip ----
app.save_current_note(auto=False)
app.update()
font_note = app.find_note(app.selected_note_id)
check('size and family are saved as ordinary spans',
      sorted((s['start'], s['end'], s['style'], s.get('value'))
             for s in font_note['formatting'])
      == [(0, 11, 'font_family', 'Georgia'), (6, 11, 'bold', None)])
app.new_note()
app.update()
app.load_note(font_note)
app.update()
check('reopening the note puts the font back',
      font_spans() == [(0, 11, 'font_family', 'Georgia'), (6, 11, 'bold', None)])

# A composite tag is split at every bold boundary inside it, so reading it
# back gives pieces; they must be rejoined or the note grows on every save.
once = font_spans()
app._apply_formatting(app.body_text, [dict(s) for s in app._extract_formatting(app.body_text)])
app.update()
check('spans do not fragment further each time the note is saved',
      font_spans() == once)

# ---- A note written before any of this still works ----
set_body('hello world')
app._apply_formatting(app.body_text,
                      [{'start': 0, 'end': 5, 'style': 'bold_italic'},
                       {'start': 6, 'end': 11, 'style': 'strike'}])
app.update()
check('a note using the old bold_italic style is unchanged by the font work',
      font_spans() == [(0, 5, 'bold_italic', None), (6, 11, 'strike', None)])

check('normalize_formatting rejects a size the app does not offer',
      NO.normalize_formatting(
          [{'start': 0, 'end': 4, 'style': 'font_size', 'value': 13}]) == [])
check('normalize_formatting rejects a family the app does not offer',
      NO.normalize_formatting(
          [{'start': 0, 'end': 4, 'style': 'font_family', 'value': 'Comic Sans MS'}]) == [])

# ---- The editor's own default, and what depends on it ----
before_family = app.editor_font_family
before_size = app.editor_font_size
import tkinter.font as _tkfont
set_body('milk\neggs')
select_all_body()
app._list_buttons['bullet'].invoke()
clear_selection()
bullet_tag = [t for t in app.body_text.tag_names('1.0') if t.startswith('para_')][0]
margin_at_12 = int(app.body_text.tag_cget(bullet_tag, 'lmargin2'))

app._set_editor_font(size=24)
app.update()
check('changing the default resizes the editor itself',
      _tkfont.Font(font=app.body_text['font']).actual('size') == 24)
check('the bold tag is rebuilt at the new size, not left at the old one',
      _tkfont.Font(font=app.body_text.tag_cget('bold', 'font')).actual('size') == 24)
check('a list margin scales with it, so a wrapped item still hangs true',
      int(app.body_text.tag_cget(bullet_tag, 'lmargin2')) > margin_at_12)

app._set_editor_font(family=before_family, size=before_size)
app.update()
check('setting it back restores the original size',
      _tkfont.Font(font=app.body_text['font']).actual('size') == before_size
      and int(app.body_text.tag_cget(bullet_tag, 'lmargin2')) == margin_at_12)

# Both runs carry a size here, so "mixed" has to come from comparing two
# sizes rather than from one of them having none -- which is what the check
# above actually exercised.
set_body('hello world')
select('1.0', '1.5')
app._apply_body_font('font_size', 20)
clear_selection()
select('1.5', '1.11')
app._apply_body_font('font_size', 9)
clear_selection()
select('1.0', '1.5')
app._refresh_format_buttons()
check('a run that is uniformly 20pt reports 20', app.font_size_var.get() == '20')
clear_selection()
select('1.0', '1.11')
app._refresh_format_buttons()
check('two runs of different sizes report Default, not whichever came first',
      app.font_size_var.get() == app.DEFAULT_FONT_LABEL)
clear_selection()

# ---- HOW THE TOOLBAR SPLITS INTO ROWS ----
# Checked against widths given directly rather than measured off widgets.
# Which control lands on a row boundary depends entirely on the font, so a
# widget-based check tests whatever font the machine has: the divider bug
# below was invisible here and failed on the CI runner for that reason
# alone.
_D = True          # a divider
_C = False         # a real control


def _rows_of(items, available, max_rows=3):
    return NO.split_toolbar_rows(items, available, max_rows)


def _widths(items, rows):
    return [sum(items[i][0] for i in row) for row in rows]


# A divider that falls where a row breaks is dropped, not carried over.
# Carrying it is what made its row too wide.
_items = [(100, _C), (100, _C), (10, _D), (100, _C), (100, _C)]
_rows = _rows_of(_items, 205)      # 210 would let the divider fit exactly
check(f'a divider at a row break is dropped, not kept on the full row '
      f'(rows {_rows})',
      2 not in [i for row in _rows for i in row])
check(f'no row is wider than the space it has ({_widths(_items, _rows)} in 205)',
      all(w <= 205 for w in _widths(_items, _rows)))
check('every real control is still placed exactly once',
      sorted(i for row in _rows for i in row) == [0, 1, 3, 4])

# A divider mid-row is kept.
_items = [(100, _C), (10, _D), (100, _C)]
_rows = _rows_of(_items, 500)
check('a divider that fits stays where it is',
      _rows == [[0, 1, 2]])

# Exhaustive: many shapes, every width, the invariants must hold.
_shapes = [
    [(60, _C)] * 10,
    [(60, _C), (8, _D)] * 6,
    [(8, _D)] + [(60, _C)] * 6 + [(8, _D)],
    [(200, _C), (8, _D), (30, _C), (30, _C)],
    [(8, _D)] * 4,
]
_faults = []
for _shape in _shapes:
    _total = sum(w for w, _d in _shape)
    for _avail in range(20, _total + 40, 7):
        _rows = _rows_of(_shape, _avail)
        _placed = [i for row in _rows for i in row]
        _controls = [i for i, (_w, d) in enumerate(_shape) if not d]
        # every real control appears exactly once
        if sorted(i for i in _placed if not _shape[i][1]) != _controls:
            _faults.append((_shape, _avail, 'a control went missing'))
            continue
        # no row starts with a divider
        if any(row and _shape[row[0]][1] for row in _rows[1:]):
            _faults.append((_shape, _avail, 'a later row starts with a divider'))
            continue
        # only the last row may exceed the width, and only because there is
        # nowhere else to put what is left
        # A row may exceed the width only when it holds a single control
        # that is wider than the whole bar -- there is nowhere narrower to
        # put it. Any other overflow means two things were packed together
        # that should not have been.
        _over = [n for n, w in enumerate(_widths(_shape, _rows))
                 if w > _avail and n < len(_rows) - 1 and len(_rows[n]) > 1]
        if _over:
            _faults.append((_shape, _avail, 'a row overflowed'))
check(f'the splitter holds its invariants across {len(_shapes)} layouts at '
      f'every width ({len(_faults)} faults)', not _faults)

check('nothing is ever dropped except a divider at a break',
      _rows_of([(50, _C)] * 3, 10) == [[0], [1], [2]])


# ---- NO FORMATTING CONTROL IS EVER OUT OF REACH ----
# The bar once needed 868px against 787px of editor pane, so the last
# group ran off the right-hand edge. Trimming it fixed that on one
# machine, but a width in pixels depends on the font: this suite runs
# under Xvfb with no Segoe UI, where the same bar measures 827px rather
# than 577px. So the bar wraps, and what is checked is the property --
# nothing is out of reach -- rather than a budget.
#
# Swept across a range of widths rather than sampled at a few, because
# which item lands on a row boundary depends on the font, and the bug
# this caught only appeared at the widths where that item was a divider.
app.new_note()
app.update()
app.update_idletasks()

_fmt_controls = [(w, px, fl) for w, px, _ip, fl, _py in app._fmt_bar_items]
_fmt_real = [w for w, _px, fl in _fmt_controls if fl != 'y']


def _fmt_layout_faults(available):
    """Controls missing or past the edge after reflowing to a width."""
    app._reflow_format_bar(available)
    app.update_idletasks()
    faults = []
    for _w, _px, _fl in _fmt_controls:
        if _w.winfo_manager() != 'pack':
            # A divider is deliberately left out where a row breaks;
            # a real control never is.
            if _fl != 'y':
                faults.append(_w)
            continue
    for _row in app._fmt_bar_rows:
        _used = 0
        for _w, _px, _fl in _fmt_controls:
            if _w.winfo_manager() == 'pack' and \
                    str(_w.pack_info().get('in')) == str(_row):
                _used += _w.winfo_reqwidth() + _px[0] + _px[1]
        if _used > available:
            faults.append(_row)
    return faults


# The floor is the narrowest the bar can actually get: the editor pane
# never goes below EDITOR_MIN_WIDTH, because the app clamps its content to
# SIDEBAR_WIDTH + EDITOR_MIN_WIDTH and scrolls horizontally rather than
# reflowing below that, and the bar sits inside 30px of padding either
# side. Sweeping narrower than that asserts a layout the app cannot
# produce -- which is what failed on CI, where the controls are wider and
# three rows genuinely cannot hold them at 300px.
_fmt_floor = NO.EDITOR_MIN_WIDTH - 60
_swept = list(range(_fmt_floor, 1001, 25))
_bad = [a for a in _swept if _fmt_layout_faults(a)]
check(f'every formatting control stays reachable at all {len(_swept)} widths tried '
      f'from {_swept[0]}px to {_swept[-1]}px (failed at {_bad})', not _bad)

# ...and through the path a real resize takes, without resizing the live
# window. Doing that mid-suite disturbs focus, and later checks here drive
# the editor with focus_force() and event_generate(): a check about
# pending bold, nothing to do with the toolbar, failed once in a full-suite
# run because of it. The binding is what matters, so the binding is what is
# checked, and the handler is called with an event of its own.
check('the bar reflows when its width changes',
      bool(app._fmt_bar.bind('<Configure>')))


class _WidthEvent:
    def __init__(self, width):
        self.width = width


for _w in (1400, 900, 1400):
    app._on_format_bar_resize(_WidthEvent(_w))
    app.update_idletasks()
    _past = [c for c, _px, fl in _fmt_controls
             if fl != 'y' and c.winfo_manager() != 'pack']
    check(f'no control is dropped when the bar is told it has {_w}px '
          f'({len(_past)} were)', not _past)

# The room has to be REAL: a synthetic width event is undone the
# moment update_idletasks() delivers the bar's genuine <Configure>
# with its true width -- which is exactly what happened on the CI,
# where wider faces mean the same window genuinely lacks room for one
# row (and the app wraps, correctly). So: widen the actual window by
# what the controls request beyond what the bar really has, let the
# genuine event reflow, assert, and put the window back.
_fmt_need = sum(w.winfo_reqwidth() + px[0] + px[1]
                for w, px, _ip, _fl, _py in app._fmt_bar_items)
_geo_before = app.geometry()
_bar_now = app._fmt_bar.winfo_width()
if _bar_now < _fmt_need + 60:
    _w_now = app.winfo_width()
    app.geometry(f'{_w_now + (_fmt_need + 60 - _bar_now)}'
                 f'x{app.winfo_height()}')
app.update()
app.update_idletasks()
_rows_state = list(getattr(app, '_fmt_rows_used', []))
check(f'every control is on one row when there is room for one '
      f'(rows={_rows_state}, need={_fmt_need}, '
      f'bar={app._fmt_bar.winfo_width()})',
      _rows_state.count(True) == 1)
app.geometry(_geo_before)
app.update()
check('and all of them are showing',
      all(c.winfo_manager() == 'pack' for c in _fmt_real))
app._reflow_format_bar()
app.update()

check('no group caption is left taking up room',
      not any(isinstance(w, tk.Label) and str(w.cget('text'))
              in ('Style', 'Font', 'Colors', 'Paragraph')
              for w, *_ in app._fmt_bar_items))

# ---- READING ESTIMATE ----
check('an empty note is given no reading estimate',
      NO.reading_time(0) == '' and NO.reading_time(-3) == '')
check('a short note reads as under a minute',
      NO.reading_time(199) == 'under a minute to read')
check('the singular is used at exactly one minute',
      NO.reading_time(200) == 'about 1 minute to read')
check('longer notes are rounded to whole minutes',
      NO.reading_time(450) == 'about 2 minutes to read'
      and NO.reading_time(1000) == 'about 5 minutes to read')
check('a nonsense word count is refused rather than guessed at',
      NO.reading_time('lots') == '' and NO.reading_time(True) == '')

app.new_note()
set_body('word ' * 400)
app.update_word_count()
app.update()
_readout = str(app.word_count_lbl.cget('text'))
check(f'the editor shows the estimate under the counts ({_readout!r})',
      '400 words' in _readout and 'to read' in _readout
      and '\n' in _readout)
set_body('')
app.update_word_count()
app.update()
check('an empty note shows no readout at all',
      str(app.word_count_lbl.cget('text')) == '')

# ---- TITLE LENGTH CAP ----
# Not about storage or layout -- the note list already truncates to 60 for
# display -- but about tk.Entry, which slows roughly with the square of
# what it holds: one keystroke measured 0.5ms at 30 characters, 38ms at
# 10,000 and 3.5 seconds at 100,000. Paste a document into the title by
# accident and the field is frozen with no way to edit it back.
app.new_note()
app.update()
_title = app.title_entry
_title.delete(0, 'end')
app.update()

_title.insert(0, 'x' * NO.NoteOrganizer.TITLE_MAX_LEN)
app.update()
check(f'a title of exactly {NO.NoteOrganizer.TITLE_MAX_LEN} characters is accepted',
      len(_title.get()) == NO.NoteOrganizer.TITLE_MAX_LEN)
_title.insert('end', 'y')
app.update()
check('one character past the cap is refused',
      len(_title.get()) == NO.NoteOrganizer.TITLE_MAX_LEN
      and not _title.get().endswith('y'))

# A validator can only take or refuse a change whole, so a long paste would
# leave the field empty -- which reads as the paste failing, not as it being
# shortened.
_title.delete(0, 'end')
app.update()
app.clipboard_clear()
app.clipboard_append('z' * 5000)
app.update()
app._on_title_paste()
app.update()
check('pasting something too long shortens it instead of refusing it',
      len(_title.get()) == NO.NoteOrganizer.TITLE_MAX_LEN)

# The one that matters: the cap must never shorten a title already saved.
# Validation fires on programmatic inserts too, so loading a note written
# before the cap could have had the widget drop the overflow -- and the next
# autosave would write that shortened title back over the real one.
_LONG = 'L' * 5000
app.notes.append(NO.normalize_note({'id': 8801, 'title': _LONG, 'body': 'b'}))
app.save_notes()
app.load_note(app.find_note(8801))
app.update()
check('a stored title longer than the cap loads in full',
      len(app.title_entry.get()) == len(_LONG))
app.save_current_note(auto=False)
app.update()
check('and saving that note again does not shorten it',
      app.find_note(8801)['title'] == _LONG)

# The counter that warns before the cap is reached. Hidden most of the
# time on purpose: a permanent "12/200" beside a twelve-character title is
# noise about a limit nobody is near.
_CAP = NO.NoteOrganizer.TITLE_MAX_LEN
_FROM = NO.NoteOrganizer.TITLE_COUNT_FROM


def _counter_state(n):
    app.title_entry.delete(0, 'end')
    app.title_entry.insert(0, 'x' * n)
    app._refresh_title_count()
    app.update()
    return (bool(app.title_count_lbl.winfo_ismapped()),
            str(app.title_count_lbl.cget('text')),
            str(app.title_count_lbl.cget('fg')))


check('an ordinary title shows no counter at all',
      _counter_state(50)[0] is False)
check('the counter stays hidden right up to the threshold',
      _counter_state(_CAP - _FROM - 1)[0] is False)
_shown, _text, _fg = _counter_state(_CAP - _FROM)
check(f'it appears {_FROM} characters before the cap, reading '
      f'{_CAP - _FROM}/{_CAP}',
      _shown and _text == f'{_CAP - _FROM}/{_CAP}')
_shown, _text, _fg = _counter_state(_CAP)
check('at the cap it reads full and turns the warning colour',
      _shown and _text == f'{_CAP}/{_CAP}' and _fg == app.colors['danger'])
check('and it goes away again when the title is shortened',
      _counter_state(10)[0] is False)

# Opening a note near the cap must say so without waiting for a keystroke.
app.notes.append(NO.normalize_note(
    {'id': 8802, 'title': 'y' * (_CAP - 3), 'body': 'b'}))
app.save_notes()
app.new_note()
app.update()
check('a new note starts with no counter',
      not app.title_count_lbl.winfo_ismapped())
app.load_note(app.find_note(8802))
app.update()
check('opening a note already near the cap shows the counter straight away',
      app.title_count_lbl.winfo_ismapped()
      and str(app.title_count_lbl.cget('text')) == f'{_CAP - 3}/{_CAP}')
app.new_note()
app.update()
check('starting a new note hides it again',
      not app.title_count_lbl.winfo_ismapped())

app.new_note()
app.update()

# ---- NOTHING BUT THE SWATCH ----
# The colour picker takes swatches only and offers no hex entry, because
# most people do not think in hex. The label beside the swatch printed
# the raw value anyway, then named the state instead -- and naming a
# state the swatch already shows is a second thing to read for nothing.
app.new_note()
app.update()
check('there is no text label beside the colour swatch',
      not hasattr(app, 'color_hint_lbl'))

_swatch_row = app.color_swatch_btn.master
_words = [str(w.cget('text')) for w in _swatch_row.winfo_children()
          if isinstance(w, tk.Label) and str(w.cget('text'))]
check(f'no hex code appears anywhere on that row ({_words})',
      not any('#' in t for t in _words))

app.current_note_color = '#e63946'
app._update_color_swatch()
app.update()
check('the swatch carries the chosen colour',
      str(app.color_swatch_btn.cget('bg')).lower() == '#e63946')
app.current_note_color = ''
app.category_var.set('General')
app._update_color_swatch()
app.update()
check('clearing it falls back to the category colour',
      str(app.color_swatch_btn.cget('bg')).lower()
      == str(NO.CATEGORY_COLORS.get('General', app.colors['accent'])).lower())

# ---- PASTING AND COPYING FORMATTED TEXT ----
# The clipboard is stubbed out here. Rich formats are a Windows facility
# and this suite runs on Linux, and even on Windows the clipboard belongs
# to the whole machine -- a test that reads it is testing whatever was
# copied last. What matters is the wiring either side of it.
app.new_note()
app.update()

_real_read_html = NO.clipboard.read_html
_real_read_text = NO.clipboard.read_text
_real_write = NO.clipboard.write
_written = {}


def _stub_clipboard(html=None, text=None):
    NO.clipboard.read_html = lambda: html
    NO.clipboard.read_text = lambda: text
    _written.clear()

    def _capture(t, h=None):
        _written['text'], _written['html'] = t, h
        return bool(h)

    NO.clipboard.write = _capture


def _body_state():
    return (body(),
            sorted((s['start'], s['end'], s['style'])
                   for s in app._extract_formatting(app.body_text)),
            app._extract_paragraphs(app.body_text))


_stub_clipboard(html="<p>A <b>bold</b> word</p><ul><li>milk</li><li>eggs</li></ul>")
set_body('')
_result = app._on_body_paste()
app.update()
_text, _spans, _paras = _body_state()
check('pasting formatted text takes over from the plain paste',
      _result == 'break')
check(f'the words and list markers arrive ({_text!r})',
      _text == 'A bold word\n\u2022 milk\n\u2022 eggs')
check('the bold comes with them, over the right characters',
      (2, 6, 'bold') in _spans)
check('and the list lines are recorded as list lines',
      _paras == [{'line': 1, 'kind': 'bullet'}, {'line': 2, 'kind': 'bullet'}])
# ...and are actually indented. The marker alone makes _extract_paragraphs
# call a line a list line, so the check above passes whether or not the
# hanging indent was ever applied -- which is the half that can go missing.
check('the pasted list lines get their indent, not just their markers',
      all(any(n.startswith('para_') for n in app.body_text.tag_names(f'{ln}.0'))
          for ln in (2, 3)))

# Pasted formatting has to land where the cursor is, not at the start.
set_body('START END')
app.body_text.mark_set('insert', '1.6')
_stub_clipboard(html='<p><b>mid</b></p>')
app._on_body_paste()
app.update()
_text, _spans, _paras = _body_state()
check(f'pasting into the middle puts the text there ({_text!r})',
      _text == 'START midEND')
check('and its formatting is offset to match',
      _spans == [(6, 9, 'bold')]
      and _text[6:9] == 'mid')

# Same clipboard, asked for plainly.
set_body('')
_stub_clipboard(html='<p>A <b>bold</b> word</p>', text='A bold word')
check('pasting without formatting takes over too',
      app._paste_plain() == 'break')
app.update()
_text, _spans, _paras = _body_state()
check(f'it brings the words and nothing else ({_text!r})',
      _text == 'A bold word' and _spans == [] and _paras == [])

# Both choices have to be reachable from the keyboard, not only by calling
# the methods. Ctrl+V is not bound directly -- Tk turns it into the <<Paste>>
# virtual event, which is what carries the binding -- so the two are checked
# the way a user actually reaches them.
set_body('')
_stub_clipboard(html='<ul><li>milk</li></ul>', text='\u2022 milk')
take_focus(app.body_text)
app.body_text.event_generate('<<Paste>>')
app.update()
check(f'Ctrl+V keeps the list ({body()!r})',
      body() == '\u2022 milk' and app._extract_paragraphs(app.body_text))

set_body('')
take_focus(app.body_text)
app.body_text.event_generate('<Control-Shift-V>')
app.update()
check(f'Ctrl+Shift+V pastes the words with no list ({body()!r})',
      body() == 'milk' and not app._extract_paragraphs(app.body_text))

# Nothing rich on the clipboard: the ordinary paste must still happen.
set_body('')
_stub_clipboard(html=None)
check('with no rich clipboard content, the normal paste is left to run',
      app._on_body_paste() is None)

# ---- Copying ----
set_body('heading\nmilk\neggs')
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
app._toggle_body_style('bold')
clear_selection()
app.body_text.tag_add('sel', '2.0', '3.end')
app.update()
app._list_buttons['bullet'].invoke()
clear_selection()

_stub_clipboard()
app.body_text.tag_add('sel', '1.0', 'end-1c')
app.update()
check('copying a selection writes markup as well as text',
      app._copy_formatted() == 'break')
check(f'the markup carries the bold ({_written.get("html")})',
      '<b>heading</b>' in (_written.get('html') or ''))
check('and the list as a real list rather than bullet characters',
      '<ul><li>milk</li>' in (_written.get('html') or ''))
check('the plain text goes on too, for anything that cannot read markup',
      (_written.get('text') or '').startswith('heading'))

# Half a bold word must copy as half a bold word.
_stub_clipboard()
clear_selection()
app.body_text.tag_add('sel', '1.0', '1.4')
app.update()
app._copy_formatted()
check(f'a partly selected style is clipped to the selection '
      f'({_written.get("html")})',
      _written.get('html') == '<div><b>head</b></div>')

# The selection above sits wholly inside the bold, so clipping the span or
# leaving it alone produce the same markup. Starting inside the style and
# running past its end is what tells the two apart.
set_body('heading tail')
app.body_text.tag_add('sel', '1.0', '1.7')
app.update()
app._toggle_body_style('bold')
clear_selection()
_stub_clipboard()
app.body_text.tag_add('sel', '1.4', '1.12')
app.update()
app._copy_formatted()
check(f'a style is clipped at the end of the selection too '
      f'({_written.get("html")})',
      _written.get('html') == '<div><b>ing</b> tail</div>')

_stub_clipboard()
clear_selection()
app.update()
check('copying nothing is left to Tk', app._copy_formatted() is None)

# ---- TABLES IN THE EDITOR ----
# A row is drawn in a monospace face, because columns cannot line up in a
# proportional one. The face is derived from the text, exactly like a list's
# margin: the pipes are what make the line a row, and the tag is only how
# that is shown. Nothing about it is stored with the note.
_stub_clipboard(html=('<p>Shopping</p><table>'
                      '<tr><th>Name</th><th>Qty</th></tr>'
                      '<tr><td>Milk</td><td>2</td></tr>'
                      '<tr><td>Eggs and bread</td><td>12</td></tr></table>'
                      '<p>Done</p>'))
set_body('')
app._on_body_paste()
app.update()
_rows = body().split('\n')
# The cells are what matter; the spaces between them follow MIN_COLUMN and
# would have to be rewritten here every time that moved.
check(f'a pasted table keeps its cells apart in the editor ({_rows[1]!r})',
      [_rows[0], _rows[4]] == ['Shopping', 'Done']
      and [core_tables.split_row(r) for r in _rows[1:4]]
      == [['Name', 'Qty'], ['Milk', '2'], ['Eggs and bread', '12']])


def _mono(line_no):
    # Probed at the line's last character: a rendered grid's window sits at
    # column 0 and carries no tags of its own.
    return app.TABLE_TAG in app.body_text.tag_names(f'{line_no}.end -1c')


check('the table rows are drawn in the monospace face',
      _mono(2) and _mono(3) and _mono(4))
check('and a grid is rendered over them',
      app._grid_at_line(2) is not None)
check('whose cells hold the pasted values',
      [[app._grid_at_line(2)['cells'][(r, c)]['value'] for c in range(2)]
       for r in range(3)]
      == [['Name', 'Qty'], ['Milk', '2'], ['Eggs and bread', '12']])
check('the text around the table is not', not _mono(1) and not _mono(5))
_face = NO.tkfont.Font(root=app,
                       font=app.body_text.tag_cget(app.TABLE_TAG, 'font'))
check(f'the face is a monospace one '
      f'({app.body_text.tag_cget(app.TABLE_TAG, "font")!r})',
      _face.measure('i') == _face.measure('W'))

# Typed by hand rather than pasted: the same text has to give the same
# result, since it is the text that decides.
set_body('| a | b |')
app._resync_list_tags()
app.update()
check('a row typed by hand is a row too', _mono(1))

# And a line that stops being a row loses the face -- otherwise a table
# taken apart by hand would leave monospace prose behind it.
app.body_text.delete('1.0', '1.1')
app._resync_list_tags(1)
app.update()
check(f'deleting the opening pipe ends the row ({body()!r})', not _mono(1))

# The face follows the note's own size, or a table would stay at whatever
# size it was built at while the text around it moved.
_before_size = str(app.body_text.tag_cget(app.TABLE_TAG, 'font'))
app._set_editor_font(size=20)
app.update()
_after_size = str(app.body_text.tag_cget(app.TABLE_TAG, 'font'))
check(f'the table face follows the editor font size ({_before_size!r} -> '
      f'{_after_size!r})', _after_size.endswith('20') and _before_size != _after_size)
app._set_editor_font(size=12)
app.update()

# ---- A TABLE IS LINED UP AGAIN ONCE IT IS LEFT ----
# Not on every keystroke: the columns would jump about under the hands of
# whoever is typing, and each keystroke would rewrite characters. Waiting
# until the row is left means one rewrite, at a moment nobody is mid-word.
set_body('before\n| Name | Qty |\n| Milk | 2   |\nafter')
app._resync_list_tags()
app.update()
_cell = app.body_text.search('Name', '1.0', 'end')
app.body_text.tag_add('bold', _cell, _cell + '+4c')
app.update()


def _caret(index):
    """Move the caret and let the app notice, as a key or a click would."""
    app.body_text.mark_set('insert', index)
    app._align_table_on_leaving()
    app.update()


_caret('3.7')
app.body_text.insert('insert', ' and bread')
app.update()
check(f'a table is left alone while it is being typed in '
      f'({lines_now()[2]!r})',
      lines_now()[2] == '| Milk  and bread| 2   |')

_caret('2.3')
check('and while the caret moves between its own rows',
      lines_now()[2] == '| Milk  and bread| 2   |')

_caret('4.0')
_after = lines_now()
check(f'but is lined up once the caret leaves it ({_after[1]!r})',
      [_after[0], _after[3]] == ['before', 'after']
      and len(_after[1]) == len(_after[2])
      and [core_tables.split_row(r) for r in _after[1:3]]
      == [['Name', 'Qty'], ['Milk  and bread', '2']])

# The reason only the spaces are edited: Tk carries a tag along with the
# text around it, so bold inside a cell survives. Rewriting the line would
# have taken its tags with it.
_bold = app.body_text.tag_ranges('bold')
check(f'bold inside a cell survives the re-padding '
      f'({app.body_text.get(_bold[0], _bold[1]) if _bold else None!r})',
      bool(_bold) and app.body_text.get(_bold[0], _bold[1]) == 'Name')
check(f'and the caret is where it was left ({app.body_text.index("insert")})',
      app.body_text.index('insert') == '4.0')

# That check alone cannot fail: re-padding only happens once the caret has
# left the block, and Tk moves an index on another line by itself. What can
# fail is the caret when the block is lined up around it, which is what
# inserting or editing a table will do. Tk keeps the mark beside the
# character it was beside; putting it back to the index it held before would
# drag it to a column that now holds something else -- which an earlier
# version of this did, landing the caret on a space nineteen characters away.
set_body('| a | Z |\n| a much longer cell | b |')
app._resync_list_tags()
app.update()
app.body_text.mark_set('insert', '1.7')
check("the caret starts just after 'Z'", app.body_text.get('insert -1c') == 'Z')
app._align_table_block(1)
app.update()
check(f"and is still just after 'Z' once the columns are widened "
      f"({app.body_text.index('insert')}, after "
      f"{app.body_text.get('insert -1c')!r})",
      app.body_text.get('insert -1c') == 'Z')

# Padding that is no longer needed goes away as well, or a table would only
# ever grow wider as it was edited.
set_body('| Name                    | Qty |\n| Milk                    | 2   |\nafter')
app._resync_list_tags()
_caret('1.5')
_caret('3.0')
check(f'padding left over from deleted text is taken back ({lines_now()[0]!r})',
      len(lines_now()[0]) < 34
      and core_tables.split_row(lines_now()[0]) == ['Name', 'Qty'])

# ---- MAKING A TABLE, AND TABBING THROUGH IT ----
check('the toolbar has a table button', hasattr(app, 'table_btn'))

set_body('')
app._insert_table(3, 2)
app.update()
_blank = lines_now()[:3]
check(f'a blank table is inserted ({_blank[0]!r})',
      all(core_tables.split_row(r) == ['', ''] for r in _blank))
check('its cells are wide enough to look like cells, not specks',
      len(_blank[0]) >= 2 * core_tables.MIN_COLUMN)
check('its rows are drawn in the monospace face', _mono(1))
_made = app._grid_at_line(1)
check('a grid is rendered over the new table', _made is not None)
check('the one floating editor opens on the first cell',
      app._cell_editor is not None
      and (app._cell_editor['r'], app._cell_editor['c']) == (0, 0)
      and app.focus_get() is app._cell_editor['entry'])

# Filling in through the editor: type, step, repeat -- the words land in
# the note's own text, cell by cell.
for _word in ('Name', 'Qty', 'Milk', '2', 'Eggs'):
    _e = app._cell_editor['entry']
    _e.delete(0, 'end')
    _e.insert(0, _word)
    app._editor_step(+1)
    app.update()
_e = app._cell_editor['entry']
_e.delete(0, 'end')
_e.insert(0, '12')
app._commit_cell_editor()
app.update()
check(f'typing through the editor lands in the text ({lines_now()[0]!r})',
      [core_tables.split_row(r) for r in lines_now()[:3]]
      == [['Name', 'Qty'], ['Milk', '2'], ['Eggs', '12']])

# Tab walks the cells; at the very last one it makes a new row, which is
# what lets a whole table be typed without reaching for the mouse.
_made = app._grid_at_line(1)
app._open_cell_editor(_made, 1, 0)
app.update()
app._cell_editor['entry'].event_generate('<Shift-Tab>')
app.update()
check('Shift+Tab goes back to the row above',
      app._cell_editor is not None
      and (app._cell_editor['r'], app._cell_editor['c']) == (0, 1))
_made = app._grid_at_line(1)
app._open_cell_editor(_made, _made['nrows'] - 1, _made['ncols'] - 1)
app.update()
app._cell_editor['entry'].event_generate('<Tab>')
app.update()
check(f'Tab at the last cell makes a new row ({lines_now()[3]!r})',
      core_tables.split_row(lines_now()[3]) == ['', ''])
check('and the editor opens in the new row',
      app._cell_editor is not None
      and (app._cell_editor['r'], app._cell_editor['c']) == (3, 0))

# Enter finishes the cell and puts the caret on the line under the table,
# at the start of the row -- writing continues from the left.
app._cell_editor['entry'].event_generate('<Return>')
app.update()
check(f'Enter leaves the caret under the table '
      f'({app.body_text.index("insert")})',
      app._cell_editor is None
      and app.body_text.index('insert') == '5.0'
      and app.focus_get() is app.body_text)
_made = app._grid_at_line(1)

# The hidden text is still reachable with arrows or a stray click, and
# typing there would edit characters nobody can see -- so the caret is
# walked out of it before anything can land.
app.body_text.mark_set('insert', '2.3')
app._caret_out_of_hidden()
app.update()
_landed = int(app.body_text.index('insert').split('.')[0])
check(f'the caret cannot rest inside the hidden rows (line {_landed})',
      _landed > 4)

# A pipe typed into a cell can never reach the text: it is what holds the
# row together, and one more of it would split the row apart.
app._open_cell_editor(_made, 0, 0)
_e = app._cell_editor['entry']
_e.delete(0, 'end')
_e.insert(0, 'a|b')
app._commit_cell_editor()
app.update()
check(f'a pipe typed into a cell cannot break the row ({lines_now()[0]!r})',
      core_tables.split_row(lines_now()[0])[0] == 'a/b'
      and len(core_tables.split_row(lines_now()[0])) == 2)

# ---- MERGED CELLS, AND A TABLE WIDER THAN THE EDITOR ----
# A source's rowspan/colspan arrives as merge markers in the text and is
# drawn as genuinely spanned cells; a table wider than the editor scrolls
# sideways instead of being cut off at the edge.
set_body('')
_stub_clipboard(html=('<table>'
                      "<tr><th rowspan='2'>Nr</th>"
                      "<th colspan='2'>Cablu</th></tr>"
                      '<tr><th>Vodafone</th><th>Digi</th></tr>'
                      '<tr><td>1.</td><td>da</td><td>nu</td></tr>'
                      '</table>'))
app._on_body_paste()
app.update()
_merged = app._grid_at_line(1)
check('a merged paste renders a grid', _merged is not None)
check(f'the rowspan anchor really spans its rows '
      f"({_merged['cells'][(0, 0)]['rs']})",
      _merged['cells'][(0, 0)]['rs'] == 2)
check(f'the colspan anchor really spans its columns '
      f"({_merged['cells'][(0, 1)]['cs']})",
      _merged['cells'][(0, 1)]['cs'] == 2)
check('covered positions are not cells at all',
      (0, 2) not in _merged['cells'] and (1, 0) not in _merged['cells'])

# Editing the anchor rewrites the anchor cell and nothing else: the markers
# that carry the merge stay exactly where they were.
app._open_cell_editor(_merged, 0, 1)
_e = app._cell_editor['entry']
_e.delete(0, 'end')
_e.insert(0, 'Cablu Nou')
app._commit_cell_editor()
app.update()
check(f'editing a merge anchor keeps the merge ({lines_now()[0]!r})',
      core_tables.split_row(lines_now()[0]) == ['Nr', 'Cablu Nou', '<']
      and core_tables.split_row(lines_now()[1])[0] == '^')

# A narrow table needs no scrollbar; a wide one gets a live one.
check('a narrow table shows no horizontal scrollbar',
      _merged.get('hbar') is None or not _merged['hbar'].winfo_manager())
set_body('')
_stub_clipboard(html=('<table><tr>'
                      + ''.join(f'<th>Column with a long name {i}</th>'
                                for i in range(9))
                      + '</tr><tr>'
                      + ''.join(f'<td>value {i}</td>' for i in range(9))
                      + '</tr></table>'))
app._on_body_paste()
app.update()
app.update_idletasks()
_wide = app._grid_at_line(1)
check(f'a wide table gets a horizontal scrollbar '
      f'(natural {_wide["natural"]}px, shown {_wide["canvas"].cget("width")}px)',
      _wide['hbar'] is not None and bool(_wide['hbar'].winfo_manager())
      and int(float(_wide['canvas'].cget('width'))) < _wide['natural'])

# ---- THE TABLE'S OWN RIGHT-CLICK MENU, THROUGH ITS HANDLERS ----
set_body('')
_stub_clipboard(html='<table><tr><td>A</td><td>B</td></tr>'
                     '<tr><td>C</td><td>D</td></tr></table>')
app._on_body_paste()
app.update()
_t = app._grid_at_line(1)
app._grid_insert_row(_t, 1)
app.update()
_t = app._grid_at_line(1)
check(f'a row can be inserted from the menu ({_t["nrows"]} rows)',
      _t['nrows'] == 3
      and core_tables.split_row(lines_now()[1]) == ['', ''])
app._grid_insert_col(_t, 1)
app.update()
_t = app._grid_at_line(1)
check(f'and a column ({_t["ncols"]} columns)',
      _t['ncols'] == 3
      and core_tables.split_row(lines_now()[0]) == ['A', '', 'B'])
app._grid_set_marker(_t, 0, 1, core_tables.MERGE_LEFT)
app.update()
_t = app._grid_at_line(1)
check('merging from the menu spans the anchor',
      _t['cells'][(0, 0)]['cs'] == 2 and (0, 1) not in _t['cells'])
app._grid_split(_t, 0, 0)
app.update()
_t = app._grid_at_line(1)
check('and splitting undoes it',
      _t['cells'][(0, 0)]['cs'] == 1 and (0, 1) in _t['cells'])
app._grid_delete_col(_t, 1)
app.update()
_t = app._grid_at_line(1)
app._grid_delete_row(_t, 1)
app.update()
_t = app._grid_at_line(1)
check(f'deleting the inserted row and column restores the shape '
      f'({_t["nrows"]}x{_t["ncols"]})',
      (_t['nrows'], _t['ncols']) == (2, 2)
      and core_tables.split_row(lines_now()[0]) == ['A', 'B'])
# Two columns is the floor -- a one-column row would read as prose, not
# as a table -- so at two, deleting a column empties it instead.
app._grid_delete_col(_t, 1)
app.update()
_t = app._grid_at_line(1)
check(f'at two columns, deleting empties the chosen one '
      f'({core_tables.split_row(lines_now()[0])})',
      _t is not None and _t['ncols'] == 2
      and core_tables.split_row(lines_now()[0]) == ['A', '']
      and core_tables.split_row(lines_now()[1]) == ['C', ''])
app._grid_delete_col(_t, 0)
app.update()
_t = app._grid_at_line(1)
check('and the table itself is never dissolved by column deletes',
      _t is not None and _t['ncols'] == 2
      and core_tables.split_row(lines_now()[0]) == ['', ''])
app._grid_delete_table(_t)
app.update()
check('and deleting the table removes it outright',
      app._grid_at_line(1) is None and core_tables.find_blocks(body()) == [])

# The window line itself is off-limits: the caret walks to the line under
# the table, so writing continues from the start of a real row.
set_body('')
_stub_clipboard(html='<table><tr><td>A</td><td>B</td></tr></table>')
app._on_body_paste()
app.update()
app.body_text.mark_set('insert', '1.0')
app._caret_out_of_hidden()
app.update()
check(f'the window line itself is off-limits '
      f'({app.body_text.index("insert")})',
      app.body_text.index('insert').split('.')[0] == '2')
check('and there is always a line under the last table to land on',
      int(app.body_text.index('end-1c').split('.')[0]) >= 2)

# A click on a drawn cell opens the editor exactly there.
_t = app._grid_at_line(1)
_cell = _t['cells'][(0, 1)]
# A click is a press AND a release now that dragging selects; the editor
# opens on the release, so a drag can end without one.
_t['canvas'].event_generate('<Button-1>',
                            x=_cell['x'] + 5, y=_cell['y'] + 5)
_t['canvas'].event_generate('<ButtonRelease-1>',
                            x=_cell['x'] + 5, y=_cell['y'] + 5)
app.update()
check(f'clicking a cell opens the editor on it '
      f'({app._cell_editor and (app._cell_editor["r"], app._cell_editor["c"])})',
      app._cell_editor is not None
      and (app._cell_editor['r'], app._cell_editor['c']) == (0, 1))
app._commit_cell_editor()
app.update()

# ---- ENTER BESIDE A TABLE, AND THE SELECTION MODEL ----
# A specific binding beats the general <KeyPress> the caret guard rides on:
# Enter beside a table used to write into the hidden text, split the block
# in two, and surface the caret at the table's right edge.
set_body('')
_stub_clipboard(html='<table><tr><td>A</td><td>B</td></tr>'
                     '<tr><td>C</td><td>D</td></tr></table>')
app._on_body_paste()
app.update()
take_focus(app.body_text)
app.body_text.mark_set('insert', '1.end')
app.body_text.event_generate('<Return>')
app.update()
check(f'Enter beside a LEADING table pushes it down in one block '
      f'({core_tables.find_blocks(body())})',
      core_tables.find_blocks(body()) == [(1, 2)]
      and app.body_text.get('1.0', '1.end') == '')
check(f'and the caret takes the fresh first line '
      f'({app.body_text.index("insert")})',
      str(app.body_text.index('insert')) == '1.0')
# The sections below were written against the table at line 1; take the
# fresh empty first line back out.
app._teardown_table_grids()
app.body_text.delete('1.0', '2.0')
app._render_table_grids()
app.update()

# Dragging across cells selects a rectangle; releasing without a drag is
# still just a click that opens the editor.
_t = app._grid_at_line(1)
_a, _b2 = _t['cells'][(0, 0)], _t['cells'][(1, 1)]
_cv = _t['canvas']
_cv.event_generate('<Button-1>', x=int(_a['x'] + 4), y=int(_a['y'] + 4))
_cv.event_generate('<B1-Motion>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
_cv.event_generate('<ButtonRelease-1>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
app.update()
check(f'dragging selects the spanned rectangle '
      f'({app._grid_sel and app._grid_sel["box"]})',
      app._grid_sel is not None and app._grid_sel['box'] == (0, 0, 1, 1))
check('and a drag does not open the editor',
      getattr(app, '_cell_editor', None) is None)

# Copy cells: tab-separated lines for a spreadsheet, remembered exactly.
app._grid_copy_selection(app._grid_sel)
check(f'copied cells reach the clipboard as rows of tabs '
      f'({app.clipboard_get()!r})',
      app.clipboard_get() == 'A\tB\nC\tD'
      and app._grid_cell_clip == [['A', 'B'], ['C', 'D']])

# Checkmarks fill the selection, and a checkmark draws centred.
_sel = app._grid_sel
app._grid_fill_selection(_sel, '\u2713', align=core_tables.ALIGN_CENTER)
app.update()
check(f'checkmarks fill every selected cell ({lines_now()[0]!r})',
      all(core_tables.split_row(l) == ['\u2713', '\u2713']
          for l in lines_now()[:2]))
_t = app._grid_at_line(1)
check('a checkmark is drawn centred in its cell',
      str(_t['canvas'].itemcget(_t['cells'][(0, 0)]['text'], 'anchor'))
      in ('c', 'center'))

# Merging the selection makes one cell anchored top-left.
_a, _b2 = _t['cells'][(0, 0)], _t['cells'][(0, 1)]
_cv = _t['canvas']
_cv.event_generate('<Button-1>', x=int(_a['x'] + 4), y=int(_a['y'] + 4))
_cv.event_generate('<B1-Motion>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
_cv.event_generate('<ButtonRelease-1>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
app.update()
app._grid_merge_selection(app._grid_sel)
app.update()
_t = app._grid_at_line(1)
check(f'merging the selection spans the anchor ({lines_now()[0]!r})',
      _t['cells'][(0, 0)]['cs'] == 2
      and core_tables.split_row(lines_now()[0])[1] == core_tables.MERGE_LEFT)

# Pasting copied cells lands them as a block, growing the table downward.
app._grid_paste_cells(_t, 1, 0)
app.update()
_t = app._grid_at_line(1)
check(f'pasted cells land as a block and grow the table '
      f'({_t["nrows"]} rows)',
      _t['nrows'] == 3
      and core_tables.split_row(lines_now()[1]) == ['A', 'B']
      and core_tables.split_row(lines_now()[2]) == ['C', 'D'])

# The cell being edited still answers a right-click.
app._open_cell_editor(_t, 1, 0)
check('the floating editor forwards a right-click to the menu',
      bool(app._cell_editor['entry'].bind('<Button-3>')))
app._commit_cell_editor()
app.update()

# Over a drawn table the pointer is a pointer, not an I-beam.
check(f'the table shows an arrow cursor '
      f'({_t["canvas"].cget("cursor")!r})',
      str(_t['canvas'].cget('cursor')) == 'arrow')

# The right and bottom rules are inside the canvas, not one pixel past it.
check('the outer rules fit inside the drawn area',
      int(_t['canvas'].cget('scrollregion').split()[2]) == _t['natural'] + 1)

# ---- CELL ALIGNMENT, AND THE TABLE THAT JUMPED TO THE MIDDLE ----
set_body('')
_stub_clipboard(html='<table><tr><td>Titlu</td><td>B</td></tr>'
                     '<tr><td>C</td><td>D</td></tr></table>')
app._on_body_paste()
app.update()
_t = app._grid_at_line(1)
app._grid_set_alignment(_t, (0, 0, 0, 0), core_tables.ALIGN_CENTER)
app.update()
check(f'centring a cell writes balanced padding ({lines_now()[0]!r})',
      core_tables.cell_alignments(lines_now()[0])[0] == 'center')
_t = app._grid_at_line(1)
check('and the cell draws centred',
      str(_t['canvas'].itemcget(_t['cells'][(0, 0)]['text'], 'anchor'))
      in ('c', 'center'))
app._open_cell_editor(_t, 0, 0)
check('and its editor justifies to match',
      str(app._cell_editor['entry'].cget('justify')) == 'center')
app._commit_cell_editor()
app.update()
check('committing an unchanged cell keeps the alignment',
      core_tables.cell_alignments(lines_now()[0])[0] == 'center')

# An alignment tag on a table's line positions the embedded window --
# a FEATURE now (Center table on page). The accidental path is pasted
# alignment, scrubbed as it enters; and the tag's spill over the newline
# is trimmed so a line typed under the table inherits nothing.
app.body_text.tag_add('align_center', '1.0', '1.end+1c')
app._resync_list_tags()
app.update()
check('a deliberate table position survives the resync',
      app._grid_table_align_of(1) == 'center')
check('but never bleeds past the newline onto the next line',
      not any(str(t) == 'align_center'
              for t in app.body_text.tag_names('1.end')))
app.body_text.tag_remove('align_center', '1.0', '2.0')
app._apply_paragraphs(app.body_text, [{'line': 0, 'align': 'center'}],
                      scrub_table_align=True)
check('pasted alignment on a table row is scrubbed to the left',
      app._grid_table_align_of(1) == 'left')
app._apply_paragraphs(app.body_text, [{'line': 0, 'align': 'center'}])
check('while a loaded note keeps its deliberate position',
      app._grid_table_align_of(1) == 'center')
app.body_text.tag_remove('align_center', '1.0', '2.0')

# ---- THE SCROLL STAYS PUT, AND EVERYTHING LANDS IN THE OPEN CELL ----
# Tearing the grids down shrinks the editor page for a moment, and the
# page's keep-short-content-at-top handler snapped the scroll to the top on
# every insert and every re-rendering commit.
set_body('filler line\n' * 60)
app.body_text.mark_set('insert', 'end -1c')
app.update()
app.editor_canvas.yview_moveto(1.0)
app.update()
_scroll_before = app.editor_canvas.yview()[0]
app._insert_table(2, 2)
# The snap this guards against comes from a queued handler, which a
# headless run may never fire -- so the snap is forced here, between the
# insert and the idle restore the render scheduled. If the restore is
# gone, the page stays snapped and this fails.
app.editor_canvas.yview_moveto(0.0)
app.update()
app.update_idletasks()
app.update()
_scroll_after = app.editor_canvas.yview()[0]
check(f'inserting a table keeps the page where it was '
      f'({_scroll_before:.3f} -> {_scroll_after:.3f})',
      abs(_scroll_after - _scroll_before) < 0.1 and _scroll_after > 0.05)

# Tk counts UTF-16 units, so an astral emoji is two steps wide; advancing
# by len() parked the caret inside the emoji, and the next insert speared
# it apart into what the mend then turned into replacement diamonds.
check('an astral character is two Tk units wide',
      app._tk_units(chr(0xD83D) + chr(0xDE00)) == 2
      and app._tk_units(chr(0x1F600)) == 2 and app._tk_units('ab') == 2)

# The calculator's insert lands in the open cell, cursor past what landed.
_t9 = app._grid_at_line(app._grid_first_line(app._table_grids[0]))
app._open_cell_editor(_t9, 1, 1)
app._calc_insert_formula('2+2=4')
check(f'the calculator lands in the open cell '
      f'({app._cell_editor["entry"].get()!r})',
      app._cell_editor is not None
      and app._cell_editor['entry'].get() == '2+2=4'
      and int(app._cell_editor['entry'].index('insert')) == 5)
app._commit_cell_editor()
app.update()

# The toolbar alignment buttons mean the open cell while one is open.
_t9 = app._grid_at_line(app._grid_first_line(app._table_grids[0]))
app._open_cell_editor(_t9, 0, 0)
_e9 = app._cell_editor['entry']
_e9.delete(0, 'end')
_e9.insert(0, 'Titlu')
app._set_paragraph_align('center')
app.update()
_first9 = app._grid_first_line(app._table_grids[0])
check('the toolbar centre button centres the open cell',
      core_tables.cell_alignments(
          app.body_text.get(f'{_first9}.0', f'{_first9}.end'))[0] == 'center')
check('and the editor reopens on that same cell',
      app._cell_editor is not None
      and (app._cell_editor['r'], app._cell_editor['c']) == (0, 0))
app._commit_cell_editor()
app.update()

# Copy cell remembers like copy cells, and the system clipboard outranks a
# stale remembered matrix -- a fresh copy used to paste older content.
app._grid_cell_clip = [['VECHI', 'STALE']]
_t9 = app._grid_at_line(_first9)
app._grid_copy_cell(_t9, 0, 0)
app._grid_paste_cells(_t9, 1, 0)
app.update()
_t9 = app._grid_at_line(_first9)
check(f'a fresh single-cell copy is what pastes '
      f'({_t9["cells"][(1, 0)]["value"]!r})',
      _t9['cells'][(1, 0)]['value'] == 'Titlu')
app._grid_cell_clip = [['MEMORAT']]
app.clipboard_clear()
app.clipboard_append('EXTERN\tNOU')
app._grid_paste_cells(_t9, 1, 0)
app.update()
_t9 = app._grid_at_line(_first9)
check('a newer system clipboard outranks the remembered matrix',
      _t9['cells'][(1, 0)]['value'] == 'EXTERN'
      and _t9['cells'][(1, 1)]['value'] == 'NOU')

# The remembered matrix earns its keep on the one copy the clipboard
# cannot describe: an empty cell. Its clipboard text is '', which a parser
# reads as nothing to paste -- only the matrix knows a cell was copied.
app._open_cell_editor(_t9, 0, 1)
app._cell_editor['entry'].delete(0, 'end')
app._commit_cell_editor()
app.update()
_t9 = app._grid_at_line(_first9)
app._grid_copy_cell(_t9, 0, 1)
app._grid_paste_cells(_t9, 1, 1)
app.update()
_t9 = app._grid_at_line(_first9)
check(f'copying an empty cell pastes emptiness, not nothing '
      f'({_t9["cells"][(1, 1)]["value"]!r})',
      _t9['cells'][(1, 1)]['value'] == '')
set_body('')

# ---- CTRL+C / CTRL+V SPEAK THE CELL SELECTION ----
# The exact reported flow: select two cells, Ctrl+C, select two other
# cells, Ctrl+V. It used to copy the empty TEXT selection -- leaving last
# week's clipboard in charge -- and paste into the body beside the table.
set_body('')
app.clipboard_clear()
app.clipboard_append('VECHI DE SAPTAMANA TRECUTA')
_stub_clipboard(html='<table><tr><td>Unu</td><td>Doi</td></tr>'
                     '<tr><td></td><td></td></tr></table>')
app._on_body_paste()
app.update()
_tX = app._grid_at_line(1)
_linesX = len(body().split('\n'))


def _select_cells(g, a, bcell):
    # 12px in from the corner: pressing within 4px of a vertical rule is
    # (by design) a grab of the rule, not the start of a selection.
    _ca, _cb = g['cells'][a], g['cells'][bcell]
    g['canvas'].event_generate('<Button-1>',
                               x=int(_ca['x'] + 12), y=int(_ca['y'] + 6))
    g['canvas'].event_generate('<B1-Motion>',
                               x=int(_cb['x'] + 12), y=int(_cb['y'] + 6))
    g['canvas'].event_generate('<ButtonRelease-1>',
                               x=int(_cb['x'] + 12), y=int(_cb['y'] + 6))
    app.update()


_select_cells(_tX, (0, 0), (0, 1))
take_focus(app.body_text)
app.body_text.event_generate('<Control-c>')
app.update()
_select_cells(_tX, (1, 0), (1, 1))
app.body_text.event_generate('<Control-v>')
app.update()
_tX = app._grid_at_line(1)
check(f'Ctrl+C/Ctrl+V move the selected cells '
      f'({_tX["cells"][(1, 0)]["value"]!r}, {_tX["cells"][(1, 1)]["value"]!r})',
      _tX['cells'][(1, 0)]['value'] == 'Unu'
      and _tX['cells'][(1, 1)]['value'] == 'Doi')
check('nothing lands outside the table',
      len(body().split('\n')) == _linesX
      and 'VECHI' not in body())

# Ctrl+V inside an open cell spreads a copied block from that cell. The
# target row is cleared first: it already held these values from the check
# above, and a spread that did nothing would have passed unnoticed.
app._grid_copy_selection({'info': _tX, 'box': (0, 0, 0, 1),
                          'cells': [(0, 0), (0, 1)]})
app._grid_fill_selection({'info': _tX, 'box': (1, 0, 1, 1)}, '')
app.update()
_tX = app._grid_at_line(1)
check('the target row really is empty before the spread',
      _tX['cells'][(1, 0)]['value'] == ''
      and _tX['cells'][(1, 1)]['value'] == '')
app._open_cell_editor(_tX, 1, 0)
app.update()          # focus settles; synthetic key events follow focus
app._cell_editor['entry'].event_generate('<Control-v>')
app.update()
_tX = app._grid_at_line(1)
check('Ctrl+V in a cell spreads the copied block from it',
      _tX['cells'][(1, 0)]['value'] == 'Unu'
      and _tX['cells'][(1, 1)]['value'] == 'Doi')

# The editor grows with its content instead of hiding the overflow.
app._open_cell_editor(_tX, 1, 0)
app.update()          # focus settles; synthetic key events follow focus
_edX = app._cell_editor
_w0 = int(float(_tX['canvas'].itemcget(_edX['win'], 'width')))
_edX['entry'].delete(0, 'end')
_edX['entry'].insert(0, 'un continut mult mai lung decat coloana initiala')
_edX['entry'].event_generate('<KeyRelease>')
app.update()
_w1 = int(float(_tX['canvas'].itemcget(_edX['win'], 'width')))
check(f'the editor grows while typing ({_w0} -> {_w1})', _w1 > _w0 + 40)
app._commit_cell_editor()
app.update()

# A wide table keeps its sideways place through the rebuild a commit
# triggers, and the body keeps its own scroll through any rebuild.
set_body('')
_stub_clipboard(html='<table><tr>'
                + ''.join(f'<th>Coloana cu nume lung {i}</th>'
                          for i in range(9))
                + '</tr><tr>'
                + ''.join(f'<td>v{i}</td>' for i in range(9))
                + '</tr></table>')
app._on_body_paste()
app.update()
app.update_idletasks()
_tX = app._grid_at_line(1)
_tX['canvas'].xview_moveto(0.5)
app.update()
_x0 = _tX['canvas'].xview()[0]
app._open_cell_editor(_tX, 1, 5)
_edX = app._cell_editor
_edX['entry'].delete(0, 'end')
_edX['entry'].insert(0, 'modificare care lateste coloana vizibil')
app._commit_cell_editor()
app.update()
app.update()
_tX = app._grid_at_line(1)
_x1 = _tX['canvas'].xview()[0]
check(f'a wide table keeps its sideways place through a commit '
      f'({_x0:.3f} -> {_x1:.3f})',
      abs(_x1 - _x0) < 0.15 and _x1 > 0.1)

# A MENU operation is different: it tears the grids down before render
# runs, and deleting the window characters shifts body_text's scroll on
# the spot -- so this one IS reproducible headless, and was: 0.316 became
# 0.164 on a checkmark. The op context captures the views first, and the
# restore waits for the queue so the fresh windows are mapped when the
# fraction is reapplied.
set_body('rand de text\n' * 30)
app.body_text.mark_set('insert', 'end -1c')
app.update()
app._insert_table(3, 3)
app._commit_cell_editor()
app.update()
app.body_text.yview_moveto(1.0)
app.update()
_yv0 = app.body_text.yview()[0]
_firstV = app._grid_first_line(app._table_grids[0])
_tV = app._grid_at_line(_firstV)
app._grid_fill_selection({'info': _tV, 'box': (0, 0, 0, 0)}, chr(0x2713),
                         align='center')
app.update()
app.update_idletasks()
app.update()
_yv1 = app.body_text.yview()[0]
# The broken behaviour drifted 0.15+ (0.316 became 0.164); the fixed
# one stays under ~0.03 on Windows and ~0.07 under the CI's Linux font
# metrics -- the threshold sits between the two regimes, not inside
# one platform's noise.
check(f'a menu op keeps the body scrolled where it was '
      f'({_yv0:.3f} -> {_yv1:.3f})', abs(_yv1 - _yv0) < 0.1)
set_body('')

# ---- EMOJI IN CELLS: TK COLUMNS ARE UTF-16 UNITS ----
# Every surgical edit addressed the text by Python character offsets, but a
# Tk Text column is a UTF-16 unit -- one astral emoji in a cell shifted
# every later cut, and each flush re-cut at the drifted position, which is
# how one emoji multiplied into squares and diamonds.
set_body('')
app._insert_table(2, 2)
app.update()
_edU = app._cell_editor
_pairU = chr(0xD83D) + chr(0xDE00)
try:
    # Windows Tk hands text over in UTF-16, so an Entry there really can
    # hold a severed pair -- the exact form that once multiplied into
    # squares and killed a save. Linux Tcl refuses lone surrogates at
    # the door, so the CI exercises the same two-in-two-out path with
    # the real character instead.
    _edU['entry'].insert('end', _pairU)
    _edU['entry'].insert('end', _pairU)
except (tk.TclError, UnicodeEncodeError):
    _edU['entry'].delete(0, 'end')
    _edU['entry'].insert('end', chr(0x1F600))
    _edU['entry'].insert('end', chr(0x1F600))
for _i in range(3):
    app._flush_table_grids()
    app.update()
app._commit_cell_editor()
app.update()
_lineU = app.body_text.get('1.0', '1.end')
check(f'two emoji land as two, through three flushes '
      f'(gasit {_lineU.count(chr(0x1F600))})',
      _lineU.count(chr(0x1F600)) == 2
      and chr(0xFFFD) not in _lineU
      and not any(0xD800 <= ord(ch) <= 0xDFFF for ch in _lineU))
_tU = app._grid_at_line(1)
check('and the drawn cell wears the emoji face at commit',
      'Emoji' in str(_tU['canvas'].itemcget(
          _tU['cells'][(0, 0)]['text'], 'font')))

# The neighbouring cell, edited AFTER the emoji, must land in its own cell
# -- this is the write the drifted columns used to cut apart.
app._open_cell_editor(_tU, 0, 1)
app.update()
_eU = app._cell_editor['entry']
_eU.delete(0, 'end')
_eU.insert(0, 'vecina')
app._commit_cell_editor()
app.update()
_tU = app._grid_at_line(1)
check(f'the cell after an emoji is written where it belongs '
      f'({_tU["cells"][(0, 1)]["value"]!r})',
      _tU['cells'][(0, 0)]['value'].count(chr(0x1F600)) == 2
      and _tU['cells'][(0, 1)]['value'] == 'vecina')

# Clear cell, from the single-cell menu's handler.
app._grid_fill_selection({'info': _tU, 'box': (0, 1, 0, 1)}, '')
app.update()
_tU = app._grid_at_line(1)
check('Clear cell empties exactly that cell',
      _tU['cells'][(0, 1)]['value'] == ''
      and _tU['cells'][(0, 0)]['value'].count(chr(0x1F600)) == 2)
set_body('')

# The toolbar has an emoji button, and it knows about open cells.
check('the toolbar has an emoji button', hasattr(app, 'emoji_btn'))

# And outside a table Tab still types a tab, as it always did.
clear_selection()
set_body('ordinary prose')
app.body_text.mark_set('insert', '1.8')
take_focus(app.body_text)
app.body_text.event_generate('<Tab>')
app.update()
check(f'Tab in ordinary prose still types a tab ({body()!r})',
      '\t' in body())

set_body('')

# ---- THE SEPARATOR ROW: |---|:---:|~| IS MECHANICS, NOT DATA ----
# Markdown's own separator line carries per-column width (the dash count),
# alignment (the colons) and hiding (~). It must never be drawn as a row
# of dashes, never counted when measuring, and never exported.
_md = ('| Nume | Cant |\n|:-----:|---|\n| Lapte | 2 |\n| Paine | 1 |')
set_body(_md)
app._render_table_grids()
app.update()
_tS = app._grid_at_line(1)
check(f'a pasted markdown separator becomes mechanics, not a data row '
      f'({_tS["nrows"]} text rows, {_tS["data_rows"]} drawn)',
      _tS['data_rows'] == 3 and _tS['nrows'] == 4
      and _tS['sep_cols'] is not None
      and _tS['cells'][(1, 0)]['value'] == 'Lapte')
check('no drawn cell wears the dashes',
      not any('---' in c['value'] for c in _tS['cells'].values()))

# Widening a column pads the data rows out to the dash count.
app._grid_set_col_width(_tS, 0, 24)
app.update()
_tS = app._grid_at_line(1)
_dataS = app.body_text.get('3.0', '3.end')
check(f'a hand-widened column pads its data cells ({len(_dataS)} chars)',
      len(_dataS.split('|')[1]) >= 24
      and core_tables.parse_separator(
          app.body_text.get('2.0', '2.end'))[0]['width'] == 24)

# Narrowing below the content is display-only: the drawn cell ellipsizes,
# the text keeps every character.
app._grid_set_col_width(_tS, 0, 4)
app.update()
_tS = app._grid_at_line(1)
_shownS = _tS['canvas'].itemcget(_tS['cells'][(1, 0)]['text'], 'text')
check(f'a too-narrow column draws an ellipsis and keeps its text '
      f'({_shownS!r})',
      chr(0x2026) in _shownS and _tS['cells'][(1, 0)]['value'] == 'Lapte')

# Hiding draws a stub and takes the cells out of play; unhide restores.
app._grid_hide_col(_tS, 1)
app.update()
_tS = app._grid_at_line(1)
check('a hidden column is a stub with no cells',
      1 in _tS['hidden_cols']
      and not any(c == 1 for (_r, c) in _tS['cells']))
app._grid_unhide_all(_tS)
app.update()
_tS = app._grid_at_line(1)
check('unhide brings the column back',
      not _tS['hidden_cols'] and _tS['cells'][(1, 1)]['value'] == '2')

# A stub has no cells, so the cell menu cannot open on it -- with every
# column hidden that would lock Unhide away for good. The sliver answers
# with its own menu instead.
app._grid_hide_col(_tS, 1)
app.update()
_tS = app._grid_at_line(1)
_posted = []
_real_popup = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _posted.append(_m)
try:
    _stub_x = (_tS['col_x'][1] + _tS['col_x'][2]) / 2
    app._grid_menu(_tS, type('E', (), {
        'x': int(_stub_x), 'y': 4, 'x_root': 0, 'y_root': 0})())
    _stub_labels = ([_posted[-1].entrycget(i, 'label')
                     for i in range(_posted[-1].index('end') + 1)]
                    if _posted else [])
    check(f'right-clicking a hidden stub offers Unhide ({_stub_labels})',
          'Unhide column' in _stub_labels
          and 'Unhide all columns' in _stub_labels)
    if _posted:
        _posted[-1].invoke('Unhide column')
        app.update()
    _tS = app._grid_at_line(1)
    check('and invoking it brings the column back',
          not _tS['hidden_cols'])

    # Delete row answers to DATA rows: a table of header + separator has
    # one data row, and deleting it must be off the table.
    set_body('| a | b |\n| --- | --- |')
    app._render_table_grids()
    app.update()
    _t1 = app._grid_at_line(1)
    _posted.clear()
    _c00 = _t1['cells'][(0, 0)]
    app._grid_menu(_t1, type('E', (), {
        'x': int(_c00['x'] + 4), 'y': int(_c00['y'] + 4),
        'x_root': 0, 'y_root': 0})())
    _del_state = None
    if _posted:
        _m = _posted[-1]
        for i in range(_m.index('end') + 1):
            if (_m.type(i) == 'command'
                    and _m.entrycget(i, 'label') == 'Delete row'):
                _del_state = str(_m.entrycget(i, 'state'))
    check(f'Delete row is disabled at one data row ({_del_state})',
          _del_state == 'disabled')
finally:
    NO.tk.Menu.tk_popup = _real_popup
set_body(_md)
app._render_table_grids()
app.update()
_tS = app._grid_at_line(1)
app._grid_set_col_width(_tS, 0, 4)
app.update()
_tS = app._grid_at_line(1)

# The separator survives a structural op, and the inserted column takes
# a default of its own -- its neighbour's hand-set width must MOVE, not
# be stolen. (replace_block pads a short separator at the end, so a
# forgotten middle insert would leave the old width on the wrong column.)
app._grid_set_col_width(_tS, 1, 15)
app.update()
_tS = app._grid_at_line(1)
app._grid_insert_col(_tS, 1)
app.update()
_tS = app._grid_at_line(1)
_sepS = app.body_text.get('2.0', '2.end')
_colsS = core_tables.parse_separator(_sepS)
check(f'insert-column keeps the separator a separator ({_sepS!r})',
      core_tables.is_separator_row(_sepS)
      and len(_colsS) == _tS['ncols'])
check('the inserted column is default and its neighbour keeps its width',
      _colsS[1]['width'] <= 8 and _colsS[2]['width'] == 15)

# Export never carries the mechanics row.
_htmlS = NO.note_to_html(body())
check('exported HTML has no separator row',
      '---' not in _htmlS and _htmlS.count('<tr>') == 3)

# Dragging the first rule resizes column 0 through press/drag/release.
_edgeS = int(_tS['col_x'][1])
_tS['canvas'].event_generate('<Button-1>', x=_edgeS, y=4)
_resS = getattr(app, '_grid_resizing', None)
check('pressing a rule starts a resize, not a selection',
      _resS is not None and _resS['col'] == 0
      and getattr(app, '_grid_pressed', None) is None)
_tS['canvas'].event_generate('<B1-Motion>', x=_edgeS + 70, y=4)
_tS['canvas'].event_generate('<ButtonRelease-1>', x=_edgeS + 70, y=4)
app.update()
_tS = app._grid_at_line(1)
_wS = core_tables.parse_separator(
    app.body_text.get('2.0', '2.end'))[0]['width']
check(f'releasing the drag stores the new width in the separator '
      f'(W={_wS})', _wS is not None and _wS >= 8)

# A click ON a rule that never moves is not a drag: the width must not
# shift. (At the default font a motionless click could not cross the
# rounding boundary anyway -- the release-side guard matters at small
# fonts, where a char is narrower than the 4px grab tolerance. This
# check pins the user-visible invariant, whichever layer provides it.)
_tS = app._grid_at_line(1)
_edgeS = int(_tS['col_x'][1])
_tS['canvas'].event_generate('<Button-1>', x=_edgeS, y=4)
_tS['canvas'].event_generate('<ButtonRelease-1>', x=_edgeS, y=4)
app.update()
_wS2 = core_tables.parse_separator(
    app.body_text.get('2.0', '2.end'))[0]['width']
check(f'a motionless click on a rule changes nothing (W={_wS2})',
      _wS2 == _wS)
set_body('')

# ---- MERGE KEEPS THE TEXT IT SWALLOWS ----
# Merging 'A' with an empty neighbour used to keep whichever cell was the
# anchor -- and lose the text when the anchor was the empty one.
# The text sits in the NON-anchor cell -- the case that actually lost
# it: the anchor was empty, and the merge kept the anchor.
set_body('|  | A |\n| x | y |')
app._render_table_grids()
app.update()
_tF = app._grid_at_line(1)
app._grid_merge_selection({'info': _tF, 'box': (0, 0, 0, 1)})
app.update()
_tF = app._grid_at_line(1)
check(f"merging an empty anchor with 'A' keeps the A "
      f"({_tF['cells'][(0, 0)]['value']!r})",
      _tF['cells'][(0, 0)]['value'] == 'A')
set_body('| A | B |\n| x | y |')
app._render_table_grids()
app.update()
_tF = app._grid_at_line(1)
app._grid_merge_selection({'info': _tF, 'box': (0, 0, 0, 1)})
app.update()
_tF = app._grid_at_line(1)
check(f"merging two texts joins them ({_tF['cells'][(0, 0)]['value']!r})",
      _tF['cells'][(0, 0)]['value'] == 'A B')
set_body('')

# ---- A LIST CAN START ON AN EMPTY LINE ----
app.body_text.mark_set('insert', '1.0')
app._toggle_list('bullet')
app.update()
check(f'a bullet lands on the empty line the caret is on '
      f'({body()!r})', body().startswith(chr(0x2022)))
set_body('')
app.body_text.mark_set('insert', '1.0')
app._toggle_list('number')
app.update()
check(f'and so does numbering ({body()!r})', body().startswith('1.'))
set_body('')

# ---- HIDE ONLY FROM A WHOLE-COLUMN SELECTION ----
# Right-clicking one cell must not offer Hide -- the user cannot see what
# would disappear. A column selected top to bottom can.
set_body('| a | b |\n| c | d |\n| e | f |')
app._render_table_grids()
app.update()
_tF = app._grid_at_line(1)
_posted = []
_real_popup = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _posted.append(_m)


def _menu_entries(m):
    out = []
    for i in range(m.index('end') + 1):
        if m.type(i) in ('command', 'cascade'):
            out.append(m.entrycget(i, 'label'))
    return out


try:
    _cF = _tF['cells'][(1, 0)]
    app._grid_clear_selection()
    app._grid_menu(_tF, type('E', (), {
        'x': int(_cF['x'] + 4), 'y': int(_cF['y'] + 4),
        'x_root': 0, 'y_root': 0})())
    _labels = _menu_entries(_posted[-1]) if _posted else []
    check(f'the cell menu no longer offers a blind Hide ({len(_labels)} entries)',
          'Hide column' not in _labels
          and 'Autofit column width' in _labels)
    check('the cell menu highlights a single cell',
          'Highlight cell…' in _labels)

    # A whole-column selection (all three data rows) offers Hide...
    _select_cells(_tF, (0, 1), (2, 1))
    _posted.clear()
    _cSel = _tF['cells'][(1, 1)]
    app._grid_menu(_tF, type('E', (), {
        'x': int(_cSel['x'] + 4), 'y': int(_cSel['y'] + 4),
        'x_root': 0, 'y_root': 0})())
    _labels = _menu_entries(_posted[-1]) if _posted else []
    check('a whole-column selection offers Hide column',
          'Hide column' in _labels)
    check('and the selection menu carries Highlight cells',
          'Highlight cells…' in _labels)

    # ...and a partial selection does not.
    _select_cells(_tF, (0, 0), (1, 0))
    _posted.clear()
    _cSel = _tF['cells'][(0, 0)]
    app._grid_menu(_tF, type('E', (), {
        'x': int(_cSel['x'] + 4), 'y': int(_cSel['y'] + 4),
        'x_root': 0, 'y_root': 0})())
    _labels = _menu_entries(_posted[-1]) if _posted else []
    check('a partial selection does not offer Hide',
          'Hide column' not in _labels and 'Merge cells' in _labels)
finally:
    NO.tk.Menu.tk_popup = _real_popup
app._grid_clear_selection()
set_body('')

# ---- TOOLBAR FORMATTING REACHES THE CELLS ----
# With cells selected, Bold means THOSE cells -- not a pending style for
# the body. The tag lands on the cell's text (so save and export carry
# it) and the drawn cell repaints.
set_body('| Nume | Cant |\n| Lapte | 2 |')
app._render_table_grids()
app.update()
_tF = app._grid_at_line(1)
app._grid_sel = {'info': _tF, 'box': (1, 0, 1, 1),
                 'cells': [(1, 0), (1, 1)]}
app._toggle_body_style('bold')
app.update()
_tF = app._grid_at_line(1)
_spanF = app._grid_cell_text_range(_tF, 1, 0)
_fontF = str(_tF['canvas'].itemcget(_tF['cells'][(1, 0)]['text'], 'font'))
check(f'Bold on selected cells tags the text and repaints ({_fontF!r})',
      'bold' in app.body_text.tag_names(_spanF[0])
      and 'bold' in _fontF and not app._pending_styles)
app._toggle_body_style('bold')
app.update()
_tF = app._grid_at_line(1)
_spanF = app._grid_cell_text_range(_tF, 1, 0)
check('a second press turns it back off',
      'bold' not in app.body_text.tag_names(_spanF[0]))

# Highlight from the selection menu paints the drawn header and lands in
# the saved formatting.
_hexF = NO.HIGHLIGHT_COLOR_PALETTE[0]
app._grid_apply_style(_tF, (0, 0, 0, 1), 'highlight', _hexF)
app.update()
_tF = app._grid_at_line(1)
_fillF = _tF['canvas'].itemcget(_tF['cells'][(0, 0)]['rect'], 'fill')
_surfF = NO.inset_surface(app.colors)
_blendF = app._blend_hex(_hexF, _surfF, 0.45)
_spansF = app._extract_formatting(app.body_text)
check(f'a highlighted header cell is drawn as a 45% blend ({_fillF!r})',
      _fillF == _blendF and _fillF != _hexF)
check('every selected cell takes the paint, not just the last',
      _tF['canvas'].itemcget(_tF['cells'][(0, 0)]['rect'], 'fill')
      == _blendF
      and _tF['canvas'].itemcget(_tF['cells'][(0, 1)]['rect'], 'fill')
      == _blendF)
# Exact offsets, not mere existence: the tag writer and reader share any
# off-by-one (the first line's embedded window), so only the SAVED span's
# slice of the body can prove the range is right.
_hlF = [s for s in _spansF if 'highlight' in str(s)]
_sliceF = (body()[_hlF[0]['start']:_hlF[0]['end']] if _hlF else '')
check(f'and the saved highlight span covers exactly the cell text '
      f'({_sliceF!r})', _sliceF == 'Nume')
app._grid_apply_style(_tF, (0, 0, 0, 1), 'highlight', None)
app.update()
_tF = app._grid_at_line(1)
check('Clear highlight restores the exact header surface',
      _tF['canvas'].itemcget(_tF['cells'][(0, 0)]['rect'], 'fill')
      == _surfF)

# An open editor is a target too: the color button means that cell.
app._grid_sel = None
app._open_cell_editor(_tF, 1, 1)
app.update()
app._apply_body_color('text_color', '#ff0000')
app.update()
_tF = app._grid_at_line(1)
_spanF = app._grid_cell_text_range(_tF, 1, 1)
check('a color aimed at the open cell colors it, not a pending choice',
      _spanF is not None
      and any(t.startswith('text_color_')
              for t in app.body_text.tag_names(_spanF[0]))
      and not app._pending_text_color
      and _tF['canvas'].itemcget(_tF['cells'][(1, 1)]['text'],
                                 'fill') == '#ff0000')
app._commit_cell_editor()
app.update()
set_body('')

# ---- A CLICK ACROSS THE COMMIT'S REBUILD ----
# Typing wide in one cell and clicking another: the commit inside the
# click's open rebuilds the grids; the editor must land on the FRESH
# grid, not crash on the dead canvas (the field failure that then broke
# selections and dropped Ctrl+V into the body as literal text).
set_body('| Nume | Cant |\n| a | 2 |\n| b | 3 |')
app._render_table_grids()
app.update()
_tR = app._grid_at_line(1)
app._open_cell_editor(_tR, 1, 0)
app.update()
app._cell_editor['entry'].delete(0, 'end')
app._cell_editor['entry'].insert(0, 'un text mult mai lat decat coloana')
_oldR = _tR['canvas']
_cellR = _tR['cells'][(2, 0)]
_evR = type('E', (), {'x': int(_cellR['x'] + 30),
                      'y': int(_cellR['y'] + 6)})()
_crashR = None
try:
    app._grid_press(_tR, _evR)
    app._grid_release(_tR, _evR)
    app.update()
except NO.tk.TclError as exc:
    _crashR = exc
_freshR = app._grid_at_line(1)
check(f'a click across the rebuild opens the editor on the fresh grid '
      f'(crash={_crashR!r})',
      _crashR is None and not int(_oldR.winfo_exists())
      and app._cell_editor is not None
      and app._cell_editor['info'] is _freshR
      and (app._cell_editor['r'], app._cell_editor['c']) == (2, 0))
check('and the wide value was committed on the way',
      _freshR['cells'][(1, 0)]['value'].startswith('un text'))
app._commit_cell_editor()
app.update()
set_body('')

# ---- THE SCREENSHOT FLOW: AN OPEN EDITOR MUST NOT EAT CTRL+C/V ----
# With an editor open (its text arrives selected), dragging a selection
# and copying used to copy the ENTRY's word and paste it back into the
# entry's own cell. The press now closes the editor and hands the
# keyboard to the grid.
set_body('| Aliment | X | Y |\n| Fructe | Lapte |  |\n'
         '| Cereale |  |  |\n| Oua |  |  |')
app._render_table_grids()
app.update()
take_focus(app.body_text)   # the window must own the desktop focus first
_tE = app._grid_at_line(1)
app._open_cell_editor(_tE, 1, 1)
app.update()
_tE = app._grid_at_line(1)
_select_cells(_tE, (1, 0), (2, 0))
take_focus(app.body_text)   # under a suite run focus_set alone may lag
check('the press closes the open editor and keeps the drag selection',
      app._cell_editor is None
      and app._grid_sel is not None
      and app._grid_sel['box'] == (1, 0, 2, 0)
      and app.focus_get() is app.body_text)
app.body_text.event_generate('<Control-c>')
app.update()
check(f'Ctrl+C copies the selected cells, not the entry '
      f'({app.clipboard_get()!r})',
      app.clipboard_get() == 'Fructe\nCereale')

# The same, in one breath: a FAST Ctrl+C right on the heels of the
# release, before the event queue settles. The press must have taken
# the keyboard already -- a deferred, FocusOut-time close would leave
# this copy to the entry.
app.clipboard_clear()
app.clipboard_append('vechi')
app._open_cell_editor(_tE, 1, 1)
app.update()
_tE = app._grid_at_line(1)
_aE, _bE = _tE['cells'][(1, 0)], _tE['cells'][(2, 0)]
_cvE = _tE['canvas']
_cvE.event_generate('<Button-1>', x=int(_aE['x'] + 12), y=int(_aE['y'] + 6))
_cvE.event_generate('<B1-Motion>', x=int(_bE['x'] + 12), y=int(_bE['y'] + 6))
_cvE.event_generate('<ButtonRelease-1>',
                    x=int(_bE['x'] + 12), y=int(_bE['y'] + 6))
app.body_text.event_generate('<Control-c>')
app.update()
check(f'a fast Ctrl+C straight after the drag still means the cells '
      f'({app.clipboard_get()!r})',
      app.clipboard_get() == 'Fructe\nCereale')

# A drag started over an editor whose content WIDENED the column: the
# commit's rebuild kills the gesture's canvas, so the one-gesture drag
# cannot survive -- but it must degrade loudly (the press turns into a
# click on the cell it started at, on the fresh grid), never into a
# selection that flashes and silently vanishes a moment later.
app._open_cell_editor(_tE, 1, 1)
app.update()
app._cell_editor['entry'].delete(0, 'end')
app._cell_editor['entry'].insert(0, 'text destul de lat sa mute coloana')
_tE2 = app._grid_at_line(1)
_aE, _bE = _tE2['cells'][(1, 0)], _tE2['cells'][(2, 0)]
_cvE = _tE2['canvas']
_cvE.event_generate('<Button-1>', x=int(_aE['x'] + 12), y=int(_aE['y'] + 6))
# The press killed this canvas (the commit rebuilt); a real mouse's
# motion and release simply never arrive on it, but SYNTHETIC events on
# a dead widget raise instead -- swallow that to mirror reality.
try:
    _cvE.event_generate('<B1-Motion>',
                        x=int(_bE['x'] + 12), y=int(_bE['y'] + 6))
    _cvE.event_generate('<ButtonRelease-1>',
                        x=int(_bE['x'] + 12), y=int(_bE['y'] + 6))
except NO.tk.TclError:
    pass
app.update()
app.update()
_tE = app._grid_at_line(1)
check('a drag across a widening commit degrades to a click, not a '
      'vanishing selection',
      app._cell_editor is not None
      and app._cell_editor['info'] is _tE
      and (app._cell_editor['r'], app._cell_editor['c']) == (1, 0))
app._commit_cell_editor()
app.update()
_tE = app._grid_at_line(1)
# The widened text served its purpose; the flow below still expects
# 'Lapte' in that cell.
app._grid_fill_selection({'info': _tE, 'box': (1, 1, 1, 1)}, 'Lapte')
app.update()
_tE = app._grid_at_line(1)
_select_cells(_tE, (1, 2), (2, 2))
app.body_text.event_generate('<Control-v>')
app.update()
_tE = app._grid_at_line(1)
check('a vertical pair lands in the vertical target',
      _tE['cells'][(1, 2)]['value'] == 'Fructe'
      and _tE['cells'][(2, 2)]['value'] == 'Cereale')
check("and the editor's old cell is untouched",
      _tE['cells'][(1, 1)]['value'] == 'Lapte')

# ---- DELETE CLEARS THE SELECTED CELLS ----
_select_cells(_tE, (1, 0), (2, 0))
app.body_text.event_generate('<Delete>')
app.update()
_tE = app._grid_at_line(1)
check('Delete clears exactly the selected cells',
      _tE['cells'][(1, 0)]['value'] == ''
      and _tE['cells'][(2, 0)]['value'] == ''
      and _tE['cells'][(0, 0)]['value'] == 'Aliment')

# ---- THE ALIGN BUTTONS FOLLOW THE CELL ----
app._grid_set_alignment(_tE, (0, 1, 0, 1), core_tables.ALIGN_CENTER)
app.update()
_tE = app._grid_at_line(1)
app._open_cell_editor(_tE, 0, 1)
app.update()
_accent = app.colors['accent']
check('the centre button reads pressed while a centred cell is open',
      str(app._align_buttons['center'].cget('bg')) == _accent
      and str(app._align_buttons['left'].cget('bg')) != _accent)
app._commit_cell_editor()
app.update()

# ---- ADD SEVERAL COLUMNS AT ONCE, AT THE END ----
_tE = app._grid_at_line(1)
_posted = []
_real_popup = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _posted.append(_m)
try:
    _select_cells(_tE, (0, 1), (3, 2))
    _cSel = _tE['cells'][(1, 1)]
    app._grid_menu(_tE, type('E', (), {
        'x': int(_cSel['x'] + 12), 'y': int(_cSel['y'] + 6),
        'x_root': 0, 'y_root': 0})())
    _labels = _menu_entries(_posted[-1]) if _posted else []
    check('two whole columns selected offer copying two to the end',
          'Copy 2 columns to the end' in _labels)
    _ncolsE = _tE['ncols']
    if _posted:
        _posted[-1].invoke('Copy 2 columns to the end')
        app.update()
    _tE = app._grid_at_line(1)
    check(f'and invoking it appends them ({_ncolsE} -> {_tE["ncols"]})',
          _tE['ncols'] == _ncolsE + 2)
    check('the copied columns carry their text, empties staying empty',
          _tE['cells'][(0, _ncolsE)]['value'] == 'X'
          and _tE['cells'][(0, _ncolsE + 1)]['value'] == 'Y'
          and _tE['cells'][(2, _ncolsE)]['value'] == '')

    # The palette is the app's own themed popup now: swatches parted
    # by one-pixel hairlines in the theme's rule colour (a tk.Menu's
    # separators are the OS's and looked nothing like the app).
    _posted.clear()
    _select_cells(_tE, (0, 0), (0, 1))
    _cSel = _tE['cells'][(0, 0)]
    app._grid_menu(_tE, type('E', (), {
        'x': int(_cSel['x'] + 12), 'y': int(_cSel['y'] + 6),
        'x_root': 0, 'y_root': 0})())
    _labels = _menu_entries(_posted[-1]) if _posted else []
    check('the selection menu opens the highlight popup',
          'Highlight cells\u2026' in _labels)
    app._grid_highlight_popup(_tE, (0, 0, 0, 1), 0, 0)
    app.update()
    _pop = app._mini_popup
    _colF = [w for w in _pop.winfo_children()[0].winfo_children()
             if isinstance(w, NO.tk.Frame)][0]
    _swF = [w for w in _colF.winfo_children()
            if isinstance(w, NO.tk.Button)]
    check(f'the popup holds every swatch over the softened accent '
          f'({len(_swF)})',
          len(_swF) == len(NO.HIGHLIGHT_COLOR_PALETTE)
          and str(_colF.cget('bg')) == app._blend_hex(
              app.colors['accent'], app.colors['card'], 0.35))
    # ---- POPUPS HIDE WITH THE APP AND COME BACK WITH IT ----
    # They are -topmost by design (the app's own focus shuffles must not
    # bury them), so they floated over OTHER applications too. The OS is
    # the only honest witness (a popup holding the activation receives
    # no Deactivate at all), so a heartbeat asks who is in front:
    # another program's window -> popups WITHDRAW, data intact; the
    # app's own -> they come back. Never destroyed -- a half-typed
    # dialog must survive a trip to the browser.
    check('the foreground watch is armed from startup',
          getattr(app, '_deactivate_bound', False)
          and bool(app.bind_all('<Deactivate>')))
    _popD = app._mini_popup
    _real_ours = app._foreground_is_ours
    app._foreground_is_ours = lambda: True     # the app holds the front
    app._popup_watch_step()
    app.update()
    check('while the app is in front, the popup stays',
          app._mini_popup is _popD and bool(_popD.winfo_viewable()))
    app._foreground_is_ours = lambda: False    # another program takes it
    app._popup_watch_step()
    app.update()
    check('another program in front hides the popup, data intact',
          app._mini_popup is _popD and not _popD.winfo_viewable()
          and _popD.winfo_exists())
    app._popup_watch_step()
    app.update()
    check('and it stays hidden while the user is away',
          not _popD.winfo_viewable())
    app._foreground_is_ours = lambda: True     # the user clicks back
    app._popup_watch_step()
    app.update()
    check('coming back to the app brings the popup back',
          bool(_popD.winfo_viewable()))
    app._foreground_is_ours = _real_ours
    app._dismiss_mini_popup()
    app.update()
    app._grid_highlight_popup(_tE, (0, 0, 0, 1), 0, 0)
    app.update()
    _swF = [w for w in [c for c in app._mini_popup.winfo_children()[0]
                        .winfo_children() if isinstance(c, NO.tk.Frame)][0]
            .winfo_children() if isinstance(w, NO.tk.Button)]

    _swF[0].invoke()
    app.update()
    _tE = app._grid_at_line(1)
    check('a swatch click paints the selected cells',
          _tE['canvas'].itemcget(_tE['cells'][(0, 0)]['rect'], 'fill')
          == app._blend_hex(NO.HIGHLIGHT_COLOR_PALETTE[0],
                            NO.inset_surface(app.colors), 0.45))
    app._grid_apply_style(_tE, (0, 0, 0, 1), 'highlight', None)
    app.update()
    _tE = app._grid_at_line(1)
finally:
    NO.tk.Menu.tk_popup = _real_popup
app._grid_clear_selection()
set_body('')

# ---- WITH A SEPARATOR, COPY READS THE ROW THE USER SEES ----
# The selection matrix read TEXT rows, so in any resized table (which
# has a separator) every copy took the line ABOVE the one on screen --
# the phantom values that haunted the field tests.
set_body('| Cap | G | H | I |\n| --- | --- | --- | --- |\n'
         '| unu | doi |  |  |\n| trei | patru |  |  |')
app._render_table_grids()
app.update()
take_focus(app.body_text)
_tS4 = app._grid_at_line(1)
_select_cells(_tS4, (1, 0), (1, 1))
take_focus(app.body_text)
app.body_text.event_generate('<Control-c>')
app.update()
check(f'with a separator, Ctrl+C copies the row on screen '
      f'({app.clipboard_get()!r})',
      app.clipboard_get() == 'unu\tdoi')
_select_cells(_tS4, (1, 2), (1, 3))
app.body_text.event_generate('<Control-v>')
app.update()
_tS4 = app._grid_at_line(1)
check('and the horizontal pair lands whole',
      _tS4['cells'][(1, 2)]['value'] == 'unu'
      and _tS4['cells'][(1, 3)]['value'] == 'doi')

# ---- THE TOOLBAR CENTRE MEANS THE SELECTED CELLS ----
# The paragraph path applied an alignment the table lines shed at once,
# which read as "it snaps back to the left".
_select_cells(_tS4, (0, 0), (2, 3))
app._set_paragraph_align('center')
app.update()
_tS4 = app._grid_at_line(1)
check('the toolbar centre centres the selected cells, and it sticks',
      core_tables.cell_alignments(
          app.body_text.get('3.0', '3.end'))[0] == 'center'
      and core_tables.cell_alignments(
          app.body_text.get('1.0', '1.end'))[0] == 'center')

# ---- THE LIST BUTTONS REFUSE A TABLE ----
_select_cells(_tS4, (0, 0), (1, 1))
_beforeS4 = body()
app._toggle_list('number')
app.update()
check('numbering declines a cell selection, leaving the table intact',
      body() == _beforeS4)
app._grid_clear_selection()
app.body_text.mark_set('insert', '1.2')
app._toggle_list('bullet')
app.update()
check('and a caret parked inside the table adds no marker either',
      body() == _beforeS4)
set_body('')

# ---- CELLS COPIED FROM A WEB TABLE KEEP THEIR SHAPE ----
# A browser's plain text stacks every copied cell on its own line, so
# two SIDE-BY-SIDE cells pasted one UNDER the other. The clipboard's
# HTML knows the true rows and columns; the cell paste reads it.
set_body('| Cap | G | H |\n|  |  |  |\n|  |  |  |')
app._render_table_grids()
app.update()
_tW = app._grid_at_line(1)
_stub_clipboard(
    html='<table><tbody><tr><td>Franta</td><td>Paris</td></tr>'
         '</tbody></table>',
    text='Franta\nParis')
app.clipboard_clear()
app.clipboard_append('Franta\nParis')
app._grid_cell_clip = None
app._grid_paste_cells(_tW, 1, 0)
app.update()
_tW = app._grid_at_line(1)
check(f'two side-by-side web cells paste side by side '
      f'({_tW["cells"][(1, 0)]["value"]!r}, '
      f'{_tW["cells"][(1, 1)]["value"]!r})',
      _tW['cells'][(1, 0)]['value'] == 'Franta'
      and _tW['cells'][(1, 1)]['value'] == 'Paris'
      and _tW['cells'][(2, 0)]['value'] == '')

# ...and a 2x2 web block keeps both its rows and its columns.
_stub_clipboard(
    html='<table><tr><td>a1</td><td>b1</td></tr>'
         '<tr><td>a2</td><td>b2</td></tr></table>',
    text='a1\nb1\na2\nb2')
app.clipboard_clear()
app.clipboard_append('a1\nb1\na2\nb2')
app._grid_cell_clip = None
app._grid_paste_cells(_tW, 1, 1)
app.update()
_tW = app._grid_at_line(1)
check('a 2x2 web block lands as 2x2',
      _tW['cells'][(1, 1)]['value'] == 'a1'
      and _tW['cells'][(1, 2)]['value'] == 'b1'
      and _tW['cells'][(2, 1)]['value'] == 'a2'
      and _tW['cells'][(2, 2)]['value'] == 'b2')

# Freshness still belongs to the plain clipboard: stale table HTML with
# a NEWER, unrelated plain copy must not shape the paste.
_stub_clipboard(
    html='<table><tr><td>vechi1</td><td>vechi2</td></tr></table>',
    text='proaspat')
app.clipboard_clear()
app.clipboard_append('proaspat')
app._grid_cell_clip = None
app._grid_paste_cells(_tW, 2, 0)
app.update()
_tW = app._grid_at_line(1)
check('stale table HTML never outranks a newer plain copy',
      _tW['cells'][(2, 0)]['value'] == 'proaspat'
      and _tW['cells'][(2, 1)]['value'] == 'a2')
set_body('')

# ---- A TEMPLATE CARRYING A TABLE PRODUCES A WORKING GRID ----
# The template store is plain note fields, so a table should ride along
# like any text -- but only a check proves the applied note renders a
# real, editable grid rather than bare pipes.
_tplT = {'name': 'SablonTabel', 'title': 'Din sablon',
         'body': '| Zi | Plan |\n| luni | scris |',
         'category': 'General', 'checklist': []}
app.templates.append(_tplT)
app.ask_yes_no = lambda *a, **k: True
app._apply_template(_tplT)
app.update()
_gT = app._grid_at_line(1)
check('a template with a table applies as a drawn grid',
      _gT is not None and _gT['data_rows'] == 2 and _gT['ncols'] == 2
      and _gT['cells'][(1, 0)]['value'] == 'luni')
app._open_cell_editor(_gT, 1, 1)
app.update()
app._cell_editor['entry'].delete(0, 'end')
app._cell_editor['entry'].insert(0, 'citit')
app._commit_cell_editor()
app.update()
_gT = app._grid_at_line(1)
check('and the grid from the template is editable',
      _gT['cells'][(1, 1)]['value'] == 'citit')
app.templates.remove(_tplT)
set_body('')

# ---- ENTER BELOW A LEADING TABLE PUSHES IT DOWN ----
# A note that BEGINS with a table has nowhere to type above it; Enter
# on the line below (where clicking beside the table parks the caret)
# pushes the table down and takes the fresh first line.
import types as _typesE
set_body('| A | B |\n| x | y |')
app._render_table_grids()
app.update()
app.body_text.mark_set('insert', '3.0')
app._on_body_return(_typesE.SimpleNamespace())
app.update()
check('Enter below a leading table pushes the table down',
      app.body_text.get('1.0', '1.end') == ''
      and app._grid_at_line(2) is not None
      and str(app.body_text.index('insert')) == '1.0')
# ...but between two ADJACENT tables the same key means what it always
# did -- the gesture belongs to the FIRST block alone.
set_body('| A | B |\n| x | y |\n\n| C | D |\n| z | w |')
app._render_table_grids()
app.update()
app.body_text.mark_set('insert', '3.0')
_resE = app._on_body_return(_typesE.SimpleNamespace())
app.update()
check('Enter on the line BETWEEN two tables does not hijack the push-down',
      _resE != 'break'
      and app.body_text.get('1.0', '1.end') != '')
set_body('')

# ---- THE WHEEL GLIDES IN PIXELS OVER TABLES ----
# A drawn table is ONE text line as tall as the whole grid, so a units
# scroll leapt from table to table instead of gliding.
set_body(('| W | X |\n| a | b |\n| c | d |\n| e | f |\n\n' * 3)
         + 'plain\n' * 20)
app._render_table_grids()
app.update()
app.body_text.yview_moveto(0.0)
app.update()
# A REAL event, through the binding chain: the first pixel handler sat
# on a direct binding that _bind_text_wheel silently replaced, so real
# wheels kept leaping while a direct method call stayed green.
take_focus(app.body_text)
app.body_text.event_generate('<MouseWheel>', delta=-120)
app.update()
check('one wheel notch over a tall table moves the view a little, not a table',
      app.body_text.yview()[0] > 0
      and app.body_text.index('@0,0').split('.')[0] == '1')
# ...and over the drawn grid itself, the forwarded wheel does the same.
app.body_text.yview_moveto(0.0)
app.update()
_gridW = app._grid_at_line(1)
_gridW['canvas'].event_generate('<MouseWheel>', delta=-120)
app.update()
check('one wheel notch over the grid glides the note the same way',
      app.body_text.yview()[0] > 0
      and app.body_text.index('@0,0').split('.')[0] == '1')

# ---- THE PUSH-DOWN KEEPS THE VIEW ON THE SAME CONTENT ----
# The edit lands at line 1, far above a mid-note view, and the Text
# keeps the view on its content by itself. A snapshot restored against
# the fresh grids' ESTIMATED heights was measured yanking the view nine
# lines up (0.30 to 0.14) -- this check pins the no-snapshot behaviour.
set_body('\n'.join('| r%d | c%d |' % (i, i) for i in range(8))
         + '\n' + 'below\n' * 40)
app._render_table_grids()
app.update()
app.update_idletasks()
app.body_text.yview_moveto(0.3)
app.update()
_vwP = app.body_text.yview()[0]
_topP = int(app.body_text.index('@0,0').split('.')[0])
app.body_text.mark_set('insert', '9.0')
app._on_body_return(_typesE.SimpleNamespace())
for _ in range(3):
    app.update()
    app.update_idletasks()
check('the push-down keeps a mid-note view on the same content',
      int(app.body_text.index('@0,0').split('.')[0]) == _topP + 1
      and abs(app.body_text.yview()[0] - _vwP) < 0.05)

# ---- THE MENU TWIN: ADD A LINE ABOVE THE TABLE ----
set_body('| M | N |\n| p | q |')
app._render_table_grids()
app.update()
app._grid_add_line_above(app._grid_at_line(1))
app.update()
check('the table menu adds a blank first line above a leading table',
      app.body_text.get('1.0', '1.end') == ''
      and app._grid_at_line(2) is not None
      and str(app.body_text.index('insert')) == '1.0')

# ---- PASTE FOLLOWS THE CARET ----
# The body kept its old view, leaving the freshly pasted end below the
# fold -- the user read that as the scroll jumping away from the text.
set_body('start\n' * 3)
app.body_text.mark_set('insert', 'end-1c')
app.clipboard_clear()
app.clipboard_append('pasted line\n' * 80)
_origHtmlP = NO.clipboard.read_html
NO.clipboard.read_html = lambda: None
take_focus(app.body_text)
app.body_text.event_generate('<<Paste>>')
for _ in range(4):
    app.update()
    app.update_idletasks()
NO.clipboard.read_html = _origHtmlP
check('a long paste scrolls the note to the pasted end',
      app.body_text.dlineinfo('insert') is not None)
set_body('')

# ---- ONE HIGHLIGHT LOOK EVERYWHERE ----
# The toolbar and right-click picker show the table popup's hairline
# column -- full-width flat swatches plus Clear -- not the old grid.
app._open_color_swatch_popup('highlight')
app.update()
_barsH, _clearH = 0, 0
def _walkH(w):
    global _barsH, _clearH
    for ch in w.winfo_children():
        if isinstance(ch, tk.Button):
            if ch.cget('text') == 'Clear highlight':
                _clearH += 1
            elif int(ch.cget('width') or 0) == 14:
                _barsH += 1
        _walkH(ch)
_walkH(app._mini_popup)
check('the toolbar highlight picker is the hairline column, Clear included',
      _barsH == len(NO.HIGHLIGHT_COLOR_PALETTE) and _clearH == 1)
app._dismiss_mini_popup()
app.update()

# ---- HIGHLIGHT INK IS BLENDED, AND FOLLOWS THE THEME ----
# The applied tag paints the swatch colour blended toward the theme's
# surface (the table cells' own recipe) -- the raw palette fill buried
# the text under it. The tag NAME keeps the pure colour, so the stored
# data never changes; a theme switch re-blends the ink.
set_body('cuvinte de evidentiat')
app.body_text.tag_add('sel', '1.0', '1.7')
_pureH = NO.HIGHLIGHT_COLOR_PALETTE[0]
app._apply_body_color('highlight', _pureH)
app.update()
_tagH = [t for t in app.body_text.tag_names('1.2')
         if t.startswith('highlight_')][0]
check('a text highlight paints blended toward the surface, name stays pure',
      app.body_text.tag_cget(_tagH, 'background')
      == app._blend_hex(_pureH, app.colors['card'], 0.45)
      and _tagH == 'highlight_' + _pureH.lstrip('#'))
_themeH = app.theme_name
app.set_theme('light' if 'dark' in str(_themeH) else 'dark')
app.apply_theme()
app.update()
check('a theme switch re-blends the highlight ink toward the NEW surface',
      app.body_text.tag_cget(_tagH, 'background')
      == app._blend_hex(_pureH, app.colors['card'], 0.45))
app.set_theme(_themeH)
app.apply_theme()
app.update()

# ---- AN EMPTY CELL TAKES A HIGHLIGHT, AND KEEPS IT WHEN FILLED ----
set_body('| Cap | G |\n| plin |  |')
app._render_table_grids()
app.update()
_gE = app._grid_at_line(1)
app._grid_apply_style(_gE, (1, 1, 1, 1), 'highlight', _pureH)
app.update()
check('an empty cell takes a highlight on its padding',
      app._grid_cell_paint(_gE, 1, 1)['bg'] == _pureH)
app._write_cell(_gE, 1, 1, 'umplut')
app.update()
_gE2 = app._grid_at_line(1)
check('the highlight survives the cell being filled in',
      app._grid_cell_paint(_gE2, 1, 1)['bg'] == _pureH
      and (app._grid_cell_text_range(_gE2, 1, 1) is not None))
app._grid_apply_style(_gE2, (1, 1, 1, 1), 'highlight', None)
app.update()
check('clear takes it back off',
      app._grid_cell_paint(app._grid_at_line(1), 1, 1)['bg'] is None)
set_body('')

# ---- EMOJI DO NOT SHIFT SAVED FORMATTING (the startup ghost) ----
# Extraction counted UTF-16 units (an emoji = two) while application
# counted characters (an emoji = one): every save of a formatted note
# with an emoji stored its spans one further right per emoji, the note
# read as 'changed' on every startup with no edit anywhere, autosave
# rewrote it, and the span walked another character each launch.
set_body('\U0001f600 salut\n| A | B |\n| c | d |\nvorbe alese aici')
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'EmojiSpan')
app._render_table_grids()
app.update()
_lnE = int(app.body_text.index('end-1c').split('.')[0])
app.body_text.tag_add('bold', '%d.0' % _lnE, '%d.5' % _lnE)
app.save_current_note()
app.update()
_noteE = app.find_note(app.selected_note_id)
_spE = [s for s in _noteE.get('formatting', [])
        if s.get('style') == 'bold']
check('a bold span behind an emoji saves at its true character offsets',
      len(_spE) == 1
      and _noteE['body'][_spE[0]['start']:_spE[0]['end']] == 'vorbe')
app.load_note(_noteE)
app.update()
check('reloading an emoji-and-table note reads clean, not phantom-dirty',
      app.editor_state_matches_saved(app.capture_editor_state()))
import copy as _copyE
_fmtBeforeE = _copyE.deepcopy(_noteE.get('formatting'))
app.save_current_note()
app.update()
check('a second save moves nothing (span drift is dead)',
      app.find_note(app.selected_note_id).get('formatting') == _fmtBeforeE)

# ---- AND A REAL EDIT STILL ANNOUNCES ITSELF ----
_toastsE = []
_origToastE = app._show_toast
app._show_toast = lambda msg, *a, **k: _toastsE.append(str(msg))
app.body_text.insert('end', ' si inca ceva')
app._schedule_autosave()
app._flush_autosave()
app.update()
app._show_toast = _origToastE
check('a real edit still toasts Note updated',
      any('updated' in t.lower() for t in _toastsE))

# ---- LIST CARDS HIDE THE PIPE ROWS ----
set_body('| C1 | C2 |\n| a | b |\n\nreadable words')
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'CardTables')
app.save_current_note()
app.update()
_cardT = next(i for i in app._note_card_widgets.values()
              if 'CardTables' in i['title'].cget('text'))
check('a card previews the words, not the pipe rows',
      '|' not in _cardT['preview'].cget('text')
      and 'readable words' in _cardT['preview'].cget('text'))
check('the card tags row counts the table',
      '\u25a6 1 table' in _cardT['tags'].cget('text'))

# ---- A NEW TABLE UNDER AN OLD ONE STAYS A TABLE OF ITS OWN ----
# Two adjacent runs of pipe rows read as one block, so a table created
# right under another fused with it: mismatched columns, a garbled grid,
# loose '---' lines on screen.
set_body('| Cap | G |\n| --- | --- |\n| unu | doi |')
app._render_table_grids()
app.update()
app.body_text.mark_set('insert', 'end')
app.update()
app._insert_table(2, 3)
app.update()
app._commit_cell_editor()
app.update()
check(f'a table inserted under another gets a block of its own '
      f'({len(app._table_grids)} grids)',
      len(app._table_grids) == 2
      and app.body_text.get('4.0', '4.end').strip() == '')

# ---- THE TABLE TAKES A PLACE ON THE PAGE, AND KEEPS IT ----
_tP = app._grid_at_line(1)
_posted = []
_real_popup = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _posted.append(_m)
try:
    _c00 = _tP['cells'][(0, 0)]
    app._grid_menu(_tP, type('E', (), {
        'x': int(_c00['x'] + 12), 'y': int(_c00['y'] + 6),
        'x_root': 0, 'y_root': 0})())
    _labels = _menu_entries(_posted[-1]) if _posted else []
    check('the table menu offers a place on the page',
          'Center table on page' in _labels
          and 'Table right on page' in _labels)
finally:
    NO.tk.Menu.tk_popup = _real_popup
app._grid_set_table_align(_tP, 'center')
app.update()
app.update_idletasks()
_bboxL = app.body_text.bbox('1.0')
check('a centred table really moves right on the page',
      _bboxL is not None and _bboxL[0] > 40)
app._grid_insert_row(_tP, 1)
app.update()
_tP = app._grid_at_line(1)
# A WHOLESALE rewrite too (fill goes through replace_block, which
# deletes the tagged text): the position must be read before the delete
# and put back after -- and the freshly rebuilt WINDOW character must
# carry the tag itself, because Tk justifies the display line by its
# first character; without that the read said center while the table
# visibly snapped left.
app._grid_fill_selection({'info': _tP, 'box': (1, 0, 1, 0)}, 'x')
app.update()
app.update_idletasks()
check('and an op on the table does not shake it loose',
      app._grid_table_align_of(1) == 'center'
      and any(str(t) == 'align_center'
              for t in app.body_text.tag_names('1.0')))
check('the position is saved with the note',
      any(p.get('align') == 'center'
          for p in app._extract_paragraphs(app.body_text)))
_tP = app._grid_at_line(1)
app._grid_set_table_align(_tP, 'left')
app.update()
check('and Table left on page brings it back',
      app._grid_table_align_of(1) == 'left')
set_body('')

# ---- A TAG-ONLY CHANGE COUNTS AS A CHANGE ----
# Centring the table touches no text, and the dirty comparison skipped
# 'paragraphs' -- so the autosave decided nothing happened, and leaving
# the note lost the position unless Save was pressed by hand.
app.new_note()
app.update()
app.title_entry.insert(0, 'autosave pozitie')
app.body_text.insert('1.0', '| Cap | G |\n| unu | doi |')
app._render_table_grids()
app.update()
app.save_current_note()
app.update()
_tA = app._grid_at_line(1)
check('a freshly saved table note reads clean',
      app.editor_state_matches_saved(app.capture_editor_state()))
app._grid_set_table_align(_tA, 'center')
app.update()
check('centring the table alone makes the note dirty',
      not app.editor_state_matches_saved(app.capture_editor_state()))
app._autosave_now()
app.update()
check('and the autosave banks it',
      app.editor_state_matches_saved(app.capture_editor_state()))
# The phantom only hatches on RELOAD: the loaded tag used to cover the
# newline, so the writable line the renderer keeps under the table was
# born centred -- an entry that kept the note dirty forever (an
# autosave every half second, and stray centred typing under the table).
_idA = app.selected_note_id
app.open_note_in_tab(app.notes[0])
app.update()
app.open_note_in_tab(app.find_note(_idA))
app.update()
_stA = app.capture_editor_state()
check(f'the reloaded note is clean, with no phantom centred line below '
      f'the table ({_stA.get("paragraphs")})',
      app.editor_state_matches_saved(_stA)
      and len(_stA.get('paragraphs', [])) == 2)
set_body('')

# ---- THE THEME SWITCH REPAINTS THE DRAWN TABLES ----
set_body('| Cap | G |\n| unu | doi |')
app._render_table_grids()
app.update()
_oldT = app.theme_name
app.set_theme('light' if 'dark' in str(_oldT) else 'dark')
app.apply_theme()
app.update()
_tT = app._grid_at_line(1)
check('the theme switch repaints the drawn header',
      _tT is not None
      and _tT['canvas'].itemcget(_tT['cells'][(0, 0)]['rect'], 'fill')
      == NO.inset_surface(app.colors))

# ...and a theme switched MID-TYPING banks the keystrokes first: the
# rebuild used to destroy the editor's canvas under it, losing the text
# and leaving a zombie editor over a dead widget.
app._open_cell_editor(_tT, 1, 0)
app.update()
app._cell_editor['entry'].delete(0, 'end')
app._cell_editor['entry'].insert(0, 'scris in timpul comutarii')
app.set_theme(_oldT)
app.apply_theme()
app.update()
_tT = app._grid_at_line(1)
check('a theme switch mid-typing keeps the typed text',
      _tT['cells'][(1, 0)]['value'] == 'scris in timpul comutarii'
      and app._cell_editor is None)
set_body('')

NO.clipboard.read_html = _real_read_html
NO.clipboard.read_text = _real_read_text
NO.clipboard.write = _real_write

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
take_focus(app.body_text)
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
take_focus(app.body_text)
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
take_focus(app.body_text)
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

# ---- CLOSING SAVES SILENTLY (dead last: it destroys the app) ----
# The quit-time "Unsaved notes" ask could only ever cover the last
# half-second of typing; the app now trusts its own autosave and closes
# the way it switches notes -- saving, without a question.
app.new_note()
app.update()
app.title_entry.insert(0, 'CloseSilent')
app.body_text.insert('1.0', 'typed and never flushed')
_askedC = []
app.ask_yes_no_cancel = lambda *a, **k: _askedC.append(1) or None
# The flush is silenced so a genuinely dirty tab reaches the close
# itself -- the case the old dialog fired on -- proving the close's own
# save loop does the saving, with no question asked.
app._flush_autosave = lambda *a, **k: None
app.on_app_close()
import io as _ioC
_notesC = json.load(_ioC.open('notes_data.json', encoding='utf-8'))
check('closing asks no unsaved-notes question', not _askedC)
check('closing saved the unflushed note on its way out',
      any(n.get('title') == 'CloseSilent' for n in _notesC))

print()
print(f"=== QA1 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
