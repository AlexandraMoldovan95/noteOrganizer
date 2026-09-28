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
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         pin_popup_visibility as _qa_pin)
_qa_pin(NO)
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


def _walk_widgets(root, klass):
    """Every descendant of `root` that is a `klass`. Defined up here with
    the other helpers because checks in two different sections use it now;
    it used to sit halfway down the file, in front of only one of them."""
    out = []
    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, klass):
                out.append(c)
            walk(c)
    walk(root)
    return out


def focus_settles_on(widget, attempts=60):
    """The assert-only twin of take_focus: wait (WITHOUT forcing) until
    the app's own action has landed the focus on `widget`. Asserting
    focus_get() directly reads the old focus now and then under load —
    the same asynchrony take_focus documents, on the reading side."""
    for _ in range(attempts):
        try:
            if app.focus_get() is widget:
                return True
        except (KeyError, tk.TclError):
            pass
        app.update()
        app.update_idletasks()
        time.sleep(0.01)
    return False


def settled(read, hold=0.5, cap=8.0):
    """Wait until read() holds ONE value for `hold` seconds straight,
    capped, and return it. The settled-BASELINE twin of the
    promised-state wait: every view-restore timer in the app fires
    within 360ms of its trigger, so a value unchanged for 500ms has no
    scheduled mover left behind it. A baseline measured mid-choreography
    makes the later promise target the wrong value -- the push-down
    check failed a fourth time on CI exactly so, with its post-Enter
    wait already promised-state."""
    last = read()
    t0 = time.time()
    cap_t = t0 + cap
    while time.time() - t0 < hold and time.time() < cap_t:
        app.update()
        time.sleep(0.02)
        now = read()
        if now != last:
            last = now
            t0 = time.time()
    return last


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
    ('Calendar: oldest', ['Apple', 'Cherry', 'Banana']),   # 01-05, 02-20, 03-10
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
# Uses an EXACT text match (not find_widget's substring match): several
# short labels ("C" clear, "=", operators) are substrings of longer ones,
# so an exact match is the only reliable way to pick the intended button.
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

# The checklist box is sized to MATCH the calculator beside it, in both
# states: compact equals the calculator closed, expanded equals it with
# history open. A settle loop because winfo_height needs the layout to
# stop moving under a full-suite run's load.
def _stable_h(w):
    last = -1
    for _ in range(40):
        app.update(); app.update_idletasks()
        h = w.winfo_height()
        if h == last and h > 1:
            return h
        last = h
        time.sleep(0.02)
    return last
app.toggle_checklist_section()          # calculator is already open here
_chk_compact = _stable_h(app.checklist_section)
_calc_closed = _stable_h(app.calculator_section)
check(f'checklist compact matches the calculator closed '
      f'({_chk_compact}px vs {_calc_closed}px)',
      abs(_chk_compact - _calc_closed) <= 4)
# Expand the checklist and open the calculator history: still equal.
app._toggle_checklist_expand()
app._toggle_calc_history()
_chk_exp = _stable_h(app.checklist_section)
_calc_open = _stable_h(app.calculator_section)
check(f'checklist expanded matches the calculator with history '
      f'({_chk_exp}px vs {_calc_open}px)',
      abs(_chk_exp - _calc_open) <= 4 and _chk_exp > _chk_compact + 40)
check('the expand button flips to Collapse when expanded',
      'Collapse' in app.checklist_expand_btn.cget('text'))
# The scroll survives the expand -- extra reach, not a replacement.
check('the checklist keeps its own scroll canvas while expanded',
      app._checklist_canvas.winfo_ismapped())
# Back to a clean closed-calc state for the perturbation below.
app._toggle_calc_history()
app._toggle_checklist_expand()
_stable_h(app.checklist_section)

# The size is MEASURED from the calculator at runtime, not a fixed number
# (a fixed one only matched the dev machine and left the box 14px short on
# CI). Prove the re-measure by making the calculator 60px taller and
# reopening: the checklist must track it. On the dev machine the fallback
# constant happens to equal the real size, so only this perturbation tells
# a working match from a dead one here; CI's other platform catches it too.
_spacerP = tk.Frame(app.calculator_section, height=60,
                    bg=app.colors['card'])
_spacerP.pack(fill='x')
app.update_idletasks()
app.toggle_checklist_section()          # close
app.toggle_checklist_section()          # reopen -> re-match to taller calc
_chk_p = _stable_h(app.checklist_section)
_calc_p = _stable_h(app.calculator_section)
check(f'the checklist re-measures the calculator, not a fixed size '
      f'({_chk_p}px vs {_calc_p}px after +60)',
      abs(_chk_p - _calc_p) <= 4 and _chk_p > _chk_compact + 40)
_spacerP.destroy()
app.update_idletasks()
# The note-switch reset path (which does NOT touch the calculator) drops
# the expand back to compact -- a transient view choice, not saved state.
# Expand FIRST, so the reset has something to undo (otherwise a removed
# reset would pass trivially against an already-compact box).
if not app._checklist_expanded:
    app._toggle_checklist_expand()
_stable_h(app.checklist_section)
check('the checklist is expanded before the reset', app._checklist_expanded is True)
app._sync_checklist_open_state()
check('the note-switch reset returns the checklist to compact',
      app._checklist_expanded is False
      and int(app._checklist_list_wrap.cget('height')) == app._checklist_list_compact)
# The calculator is left open with its history closed -- the state the
# checks below expect (the checklist reset above collapsed the checklist).
app.update()

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
# The assertion below is NEGATIVE ("stays disabled"), so a KeyRelease
# dropped by a focus miss would pass it vacuously — force + poll first.
take_focus(app.calculator_display)
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
_qa_click(target_entry)
app.update()
body_after_history_click = app.body_text.get('1.0', 'end')
check('clicking a history entry inserts that exact formula into the note',
      body_after_history_click.count('7×8=56') == body_before_history_click.count('7×8=56') + 1)

find_calc_btn('Clear').invoke()
app.update()
check('the Clear (history) button wipes the history', app._calc_history == [])
check('clearing history does not touch the current expression on display',
      app._calc_display_var.get() == '27')

# The in-panel Close button was removed -- the "🧮 Calculator ▲" bar above
# the panel is the one control that opens and closes it now.
app.calculator_btn.invoke()
app.update()
check('the header bar collapses the calculator', app._calculator_open == False)

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
take_focus(app.body_text)
app.body_text.event_generate('<Control-b>')  # toggle back off for the button test below
app.update()
# Belt for a lost synthetic key under desktop load: the button test
# below MUST start from bold-off, or its toggle reads inverted and
# poisons the compound checks after it (seen: one dropped Ctrl+B
# cascaded into five downstream failures).
app.body_text.tag_remove('bold', bold_start, bold_end)
app.body_text.tag_remove('bold_italic', bold_start, bold_end)

app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '1.0', '1.0+3c')
app.update()
take_focus(app.body_text)
app.body_text.event_generate('<Control-u>')
app.update()
check('Ctrl+U toggles underline via keyboard', 'underline' in app.body_text.tag_names('1.0'))
take_focus(app.body_text)
app.body_text.event_generate('<Control-d>')
app.update()
check('Ctrl+D toggles strikethrough via keyboard', 'strike' in app.body_text.tag_names('1.0'))
take_focus(app.body_text)
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

# ---- THE BATCH OFFSET READ MUST AGREE WITH THE SINGLE ONE ----
# Coverage-ledger C14. `_char_offset` is `len(get("1.0", index))`: it
# re-reads the note from its start for every index it is asked about.
# That is fine for the four callers that ask once, and it was the whole
# cost of opening a heavily styled note -- measured at 14.18s of a 15.5s
# startup with 500 styled pieces on one line, because every piece has two
# ends and the reader runs three times per open. `_char_offsets` answers
# a whole set in one pass instead.
#
# Both still exist, so the fast one is checked directly against the slow
# one it replaced. On its own widget, deliberately: the property needs no
# app state, and this has to run BEFORE the first save below, because
# _extract_formatting is used there — a broken offset read crashes qa1 at
# that line with a traceback, and a traceback is not a named failure.
#
# The fixture holds the two shapes worth holding. Astral characters are
# the real trap: Tk's own count("chars") counts UTF-16 units, so an emoji
# is two — using it here once shifted every span one place right per
# preceding emoji and re-saved the note on every launch. An embedded
# window is not a trap between these two (measured: both skip it), but a
# drawn table puts one in the middle of a note, so walking past one is
# worth witnessing.
_co_probe = NO.tk.Text(app)
_co_probe.insert('1.0', '\U0001F600 first \U0001F680 second\n'
                        'a plain second line\n'
                        '\U0001F914 third with emoji again')
_co_probe.mark_set('insert', '2.0')
_co_probe.window_create('2.5', window=NO.tk.Label(_co_probe, text='x'))
app.update()

_co_indices = []
for _co_line in (1, 2, 3):
    for _co_col in (0, 1, 4, 7, 12):
        _co_idx = _co_probe.index('%d.%d' % (_co_line, _co_col))
        if _co_probe.compare(_co_idx, '<=', 'end-1c'):
            _co_indices.append(_co_idx)
_co_batch = app._char_offsets(_co_probe, _co_indices)
# .get(), not [] : an implementation that answers fewer indices than it
# was asked about must make this check RED, not raise inside it. The
# first version used a subscript and a mutant that answered only the
# first index took qa1 down with a KeyError instead.
check('the batch offset read agrees with the single one it replaced',
      all(_co_batch.get(str(_i)) == app._char_offset(_co_probe, _i)
          for _i in _co_indices))
check('...for every index it was given, not just the first',
      len(_co_batch) == len({str(_i) for _i in _co_indices}))
# Not vacuous: both traps must really be traps here, or the check above
# would pass on implementations that differ in exactly the ways that have
# gone wrong before.
check('...and the emoji really do move the offsets, so agreeing meant '
      'something',
      int(_co_probe.count('1.0', _co_probe.index('1.7'), 'chars')[0])
      != len(_co_probe.get('1.0', _co_probe.index('1.7'))))
# The embedded window is NOT a divergence between the two — measured
# here, `get` and `count("chars")` both skip it, and the comment on
# _char_offset that said otherwise has been corrected. It stays in the
# fixture because walking past one still has to work.
check('...and the fixture really holds an embedded window for the batch '
      'read to walk past', _co_probe.window_names() != ())
_co_probe.destroy()

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

# Saving stores the body EXACTLY as typed - blank lines and leading
# indentation included. It used to .strip() it, which silently deleted the
# user's own first-line indentation and every trailing blank line on each
# save (a pasted code block lost its shape), and needed two adapter methods
# to shift every span and list line back into place. The adapters went with
# the strip; this check now guards the promise that replaced them: what is
# on screen is what lands on disk, line for line.
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
check('blank lines survive the save, and list lines stay where the user put them',
      blank_note['body'] == '\n\n\u2022 milk\n\u2022 eggs'
      and blank_note.get('paragraphs') == [{'line': 2, 'kind': 'bullet'},
                                           {'line': 3, 'kind': 'bullet'}])

# Indentation and trailing blank lines are the user's characters too.
app.new_note()
app.title_entry.insert(0, 'Indented')
set_body('    def f():\n        return 1\n\n')
app.save_current_note(auto=False)
app.update()
_ind = app.find_note(app.selected_note_id)
check('leading indentation and trailing blank lines survive a save',
      _ind['body'] == '    def f():\n        return 1\n\n')

# ...but a body of nothing but whitespace is still "empty": storing the raw
# text must not turn a stray New Note click into a saved note.
app.new_note()
set_body('   \n\n  ')
_before_ws = len(app.notes)
app.save_current_note(auto=True)
app.update()
check('a whitespace-only new note is still refused',
      len(app.notes) == _before_ws)

check('normalize_note drops list lines pointing past the end of the body',
      NO.normalize_note({'body': 'one\ntwo',
                         'paragraphs': [{'line': 0, 'kind': 'bullet'},
                                    {'line': 9, 'kind': 'bullet'}]})['paragraphs']
      == [{'line': 0, 'kind': 'bullet'}])

# ---- Templates carry lists too ----
# Set the editor up explicitly instead of inheriting whatever the block
# above happened to leave in it: these two checks silently became about
# an empty editor the moment a neighbour's last action changed.
app.new_note()
app.title_entry.insert(0, 'ListTemplateSource')
set_body('milk\neggs')
app.body_text.tag_add('sel', '1.0', '2.end')
app.update()
app._list_buttons['bullet'].invoke()
clear_selection()
app.update()
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

# ---- A PASTE ONTO A PLACEHOLDER ----
# The check above calls _on_title_paste() DIRECTLY on a field that was just
# emptied, so it proves the handler and says nothing about the route. Going
# through the route instead found the field glued the pasted text to the
# placeholder still sitting in it: "Note title...My pasted title", and the
# length cap was measured against that, so a paste also lost room to it.
#
# Both routes to a paste were affected. _add_paste_menu's Paste entry fires
# event_generate("<<Paste>>"), which is no keystroke at all, so the
# placeholder's <KeyPress> clear never ran. Ctrl+V went the same way on this
# field, because Tk fires one binding per bindtag and a VIRTUAL event
# outranks a physical one in the same tag -- the title's own <<Paste>>
# handler won and <KeyPress> was never consulted. The suite cannot generate
# a trustworthy Ctrl+V (see _qa_support.fire), so what is asserted here is
# the virtual event the app itself sends; the keystroke's fix is the same
# line.


def _restore_placeholder(entry, placeholder):
    """Put `entry` back in the state a freshly-opened app leaves it in.

    Through the app's OWN mechanism -- empty the field and let <FocusOut>
    refill it -- rather than by inserting the text here, so the fixture is
    the real thing and not a hand-made imitation of it.
    """
    entry.delete(0, 'end')
    entry.event_generate('<FocusOut>')
    app.update()
    return entry.get() == placeholder


_PH_TITLE = 'Note title...'
check('fixture: the title really is showing its placeholder again',
      _restore_placeholder(_title, _PH_TITLE))
app.clipboard_clear(); app.clipboard_append('Pasted Title'); app.update()
_title.event_generate('<<Paste>>')
app.update()
check('pasting onto the title placeholder replaces it, not appends to it',
      _title.get() == 'Pasted Title')

# The second half of the same bug: room was TITLE_MAX_LEN minus whatever the
# placeholder happened to be, so a long paste came back short by 13.
#
# Asserted on the CONTENT, not the length, and the first version of this
# check got that wrong -- it read len(...) == TITLE_MAX_LEN and survived
# both mutants. With the bug the field held "Note title..." plus
# TITLE_MAX_LEN - 13 q's, which is TITLE_MAX_LEN characters exactly, so the
# length was right while every one of the first thirteen was wrong. A length
# is a weaker question than "is this the text the user pasted".
check('fixture: placeholder restored before the long paste',
      _restore_placeholder(_title, _PH_TITLE))
app.clipboard_clear(); app.clipboard_append('q' * 5000); app.update()
_title.event_generate('<<Paste>>')
app.update()
check('and the cap still measures the title alone, not the placeholder too',
      _title.get() == 'q' * NO.NoteOrganizer.TITLE_MAX_LEN)

# THE CONTROL. Without this the two checks above would also pass if the
# clear had become unconditional -- wiping a real title every time someone
# pasted into it, which is a worse bug than the one being fixed.
_title.delete(0, 'end')
_title.insert(0, 'Kept')
_title.icursor('end')
app.update()
check('fixture: the title holds real text, no placeholder',
      _title.get() == 'Kept')
app.clipboard_clear(); app.clipboard_append('More'); app.update()
_title.event_generate('<<Paste>>')
app.update()
check('a paste into a title that has real text leaves that text alone',
      _title.get() == 'KeptMore')

# The date field carries the same placeholder and is the field the register
# wants a paste menu on next; it has no <<Paste>> route a user can reach
# today, so this is the latent half of the same hole, checked so that adding
# the menu cannot re-open it.
_PH_DATE = 'YYYY-MM-DD'
check('fixture: the date field is showing its placeholder',
      _restore_placeholder(app.date_entry, _PH_DATE))
app.clipboard_clear(); app.clipboard_append('2026-10-05'); app.update()
app.date_entry.event_generate('<<Paste>>')
app.update()
check('pasting onto the date placeholder replaces it too',
      app.date_entry.get() == '2026-10-05')
app.date_entry.delete(0, 'end')
app.update()

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


def _stub_clipboard(html=None, text=None, loopback=False):
    # loopback=True serves back whatever the app last WROTE -- the real
    # Windows clipboard behaves exactly like that, and the rich-paste
    # route only sees our own table copies through it. Without this mode
    # the suite never exercised the Windows route order, and the pasted
    # table gluing itself onto the "Sursa:" line shipped unseen.
    if loopback:
        NO.clipboard.read_html = lambda: _written.get('html')
        NO.clipboard.read_text = lambda: _written.get('text')
    else:
        NO.clipboard.read_html = lambda: html
        NO.clipboard.read_text = lambda: text
    _written.clear()

    def _capture(t, h=None, html=None):
        _written['text'], _written['html'] = t, (html if html is not None
                                                 else h)
        # Mirror the text into Tk's clipboard too: on real Windows the
        # CF writer sets both, and the older checks read what a paste
        # would actually see via clipboard_get().
        try:
            app.clipboard_clear()
            app.clipboard_append(t or '')
        except Exception:
            pass
        return _written['html'] is not None

    NO.clipboard.write = _capture


def _menu_entries(m):
    # Recursive through cascades: the table menu grew groups (Rows/
    # Columns/Merge/Table/Align cell), and the checks ask by LABEL,
    # wherever the entries happen to live now.
    out = []
    for i in range(m.index('end') + 1):
        kind = m.type(i)
        if kind == 'command':
            out.append(m.entrycget(i, 'label'))
        elif kind == 'cascade':
            out.append(m.entrycget(i, 'label'))
            try:
                sub = m.nametowidget(m.entrycget(i, 'menu'))
                out.extend(_menu_entries(sub))
            except Exception:
                pass
    return out


def _menu_entry_state(m, label):
    for i in range(m.index('end') + 1):
        kind = m.type(i)
        if kind == 'command' and m.entrycget(i, 'label') == label:
            return str(m.entrycget(i, 'state'))
        if kind == 'cascade':
            try:
                sub = m.nametowidget(m.entrycget(i, 'menu'))
            except Exception:
                continue
            found = _menu_entry_state(sub, label)
            if found is not None:
                return found
    return None



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
# The focus PROMISE is recorded, not polled. focus_settles_on reads an
# asynchronous result inside a bounded loop, so on a loaded machine it
# reports a false red about an app that placed the focus correctly --
# which is how this check went red once in a full-suite run with its name
# lost (COVERAGE_LEDGER C11b). Wrapping focus_set captures the decision
# itself, synchronously, and cannot flake. It wraps the INSERT, because
# opening the editor on the first cell is what inserting a table
# promises; re-opening it here to watch would test something else.
_fs_calls = []
_real_focus_set = tk.Misc.focus_set
tk.Misc.focus_set = (lambda self, *a, **k:
                     (_fs_calls.append(self), _real_focus_set(self, *a, **k))[1])
try:
    app._insert_table(3, 2)
    app.update()          # lets the after_idle re-assert run and be seen
finally:
    tk.Misc.focus_set = _real_focus_set
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
      and (app._cell_editor['r'], app._cell_editor['c']) == (0, 0))
check('...and the app puts the keyboard in it',
      app._cell_editor is not None
      and app._cell_editor['entry'] in _fs_calls)

# Filling in through the editor: type, step, repeat -- the words land in
# the note's own text, cell by cell.
for _word in ('Name', 'Qty', 'Milk', '2', 'Eggs'):
    _e = app._cell_editor['entry']
    _e.delete('1.0', 'end')
    _e.insert('1.0', _word)
    app._editor_step(+1)
    app.update()
_e = app._cell_editor['entry']
_e.delete('1.0', 'end')
_e.insert('1.0', '12')
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
# take_focus, not focus_settles_on: what follows asserts what Shift+Tab
# DOES, so the focus is a precondition to be forced, not a promise to be
# read back. (Where the promise really is the placement, the check above
# records the decision instead.)
take_focus(app._cell_editor['entry'])
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

# Enter now stays IN the cell: it starts a new line inside it (stored
# as markdown's <br>), instead of dumping the caret under the table.
# Leaving the cell is Tab, Escape, or a click elsewhere.
app._editor_newline()
app.update()
check('Enter stays in the cell, adds a line, and the ROW grows live',
      app._cell_editor is not None
      and app._cell_editor['entry'].get('1.0', 'end-1c') == '\n'
      and app._grid_at_line(1)['cells'][
          (app._cell_editor['r'], app._cell_editor['c'])]['h']
      == 2 * app._grid_at_line(1)['row_h'])
# tidy the empty second line back out so the table the following checks
# read is the one they were written against
app._cell_editor['entry'].delete('1.0', 'end')
app._commit_cell_editor()
app.update()
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
_e.delete('1.0', 'end')
_e.insert('1.0', 'a|b')
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
_e.delete('1.0', 'end')
_e.insert('1.0', 'Cablu Nou')
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

# ---- GRID DELETE captures the view BEFORE teardown (audit Z08-F02) ----
# Every other grid op snapshots _grid_saved_view before tearing down so
# the rebuild pins the view the user had; table delete was the one op
# that didn't, and deleting a table yanked the page. The restore itself
# rides after_idle (async), so assert the synchronous decision instead:
# when the delete's render runs, the snapshot must already be there.
set_body('| A | B |\n| C | D |')
app._render_table_grids()
app.update()
_delcap = {}
_del_order = []
_orig_render_del = app._render_table_grids
_orig_teardown_del = app._teardown_table_grids
def _spy_render_del():
    _delcap['had_saved_view'] = getattr(app, '_grid_saved_view', None) is not None
    return _orig_render_del()
def _spy_capture_del():
    _del_order.append('capture')
    return _orig_capture_del()
_orig_capture_del = app._capture_grid_views
def _spy_teardown_del():
    _del_order.append('teardown')
    return _orig_teardown_del()
app._render_table_grids = _spy_render_del
app._capture_grid_views = _spy_capture_del
app._teardown_table_grids = _spy_teardown_del
try:
    _t = app._grid_at_line(1)
    app._grid_delete_table(_t)
finally:
    app._render_table_grids = _orig_render_del
    app._capture_grid_views = _orig_capture_del
    app._teardown_table_grids = _orig_teardown_del
app.update()
check('table delete captures the view before teardown (no scroll jump)',
      _delcap.get('had_saved_view', False))
# Ordering, not just presence: a capture MOVED AFTER the teardown+delete
# would still satisfy the spy above while pinning the already-jumped view
# — the exact bug. The promise is capture-first.
check('and that capture happens BEFORE the teardown',
      'capture' in _del_order and 'teardown' in _del_order
      and _del_order.index('capture') < _del_order.index('teardown'))
check('and that delete still removes the table outright',
      core_tables.find_blocks(body()) == [])

# ---- RESTORE PREVIOUS VERSION redraws what it restores (audit Z09-F07) ----
# It was the one body-loader that skipped the redraw tail: a restored
# table came back as raw pipe rows, and the word count kept describing
# the text that was just replaced.
# The previous block's _grid_delete_table scheduled an autosave whose
# timer calls update_word_count() on its own ~500ms later — under
# full-suite load that made the word-count mutant pass by accident.
# Cancel it so the label below can only come from the restore itself.
if getattr(app, '_autosave_job', None):
    try:
        app.after_cancel(app._autosave_job)
    except Exception:
        pass
    app._autosave_job = None
app.new_note()
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'RestoreGrid')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'one two three four five six')
app.save_current_note(auto=False)
app.update_word_count()
app.update()
_rp_note = app.find_note(app.selected_note_id)
_rp_note['_prev'] = {'title': 'RestoreGrid', 'body': '| P | Q |\n| R | S |',
                     'formatting': [], 'paragraphs': [], 'comments': ''}
_orig_ask_rp = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version()
finally:
    app.ask_yes_no = _orig_ask_rp
app.update()
check('restore previous version draws the restored table as a grid',
      len(app.body_text.window_names()) >= 1
      and core_tables.find_blocks(body()) != [])
check('and the word count describes the restored text, not the replaced one',
      '4 words' in str(app.word_count_lbl.cget('text')))

# ---- ASTRAL EMOJI vs Tk INDEXES (audit Z09-F05/F06) ----
# Tk Text columns count UTF-16 units; Python strings count characters.
# The double-click word-select and the table cell navigation mixed the
# two, so an emoji earlier on the line shifted every offset after it.
check('the Tk<->Python column converters round-trip across an emoji',
      app._py_col('\U0001F600ab', 2) == 1
      and app._py_col('\U0001F600ab', 3) == 2
      and app._py_col('\U0001F600ab', 99) == 3
      and app._tk_col('\U0001F600ab', 1) == 2)

_C4 = core_tables.CELL
_E4 = '\U0001F600'
set_body(f'{_C4} {_E4}{_E4}{_E4}{_E4} {_C4} b {_C4} c {_C4}')
_row4 = app.body_text.get('1.0', '1.end')
_b_tk = app._tk_col(_row4, _row4.index('b'))
_hit4 = app._cell_at(1, _b_tk)
check('the caret is judged into the RIGHT cell across emoji',
      _hit4 is not None and _hit4[0] == 1)
check('tabbing lands the caret and selection on the cell text itself',
      app._move_to_cell(1, 1)
      and app.body_text.get('sel.first', 'sel.last') == 'b')

set_body(f'{_E4}{_E4} hello world')
app.body_text.see('1.0'); app.update()
# Aim at the LAST letter of "hello": the two emoji drift a raw Tk column
# two characters to the right, which from here crosses into "world" — a
# click near the word's start drifts within the same word and hides the
# bug from the check.
_bb4 = app.body_text.bbox(f"1.{app._tk_col(f'{_E4}{_E4} hello world', 7)}")
if not _bb4:
    check('double-click target is on screen', False)
else:
    class _Ev4:
        pass
    _ev4 = _Ev4(); _ev4.widget = app.body_text
    _ev4.x = _bb4[0] + 1; _ev4.y = _bb4[1] + 1
    app._select_word_at_click(_ev4)
    check('double-click selects the whole word after an emoji',
          app.body_text.get('sel.first', 'sel.last') == 'hello')

# ---- A skinny pasted separator no longer clips the drawing (Z08-F03) ----
# Markdown from the wild writes "---" regardless of content; the dash
# count used to be the display width EXACTLY, so the drawn column
# clipped its own text. It is a floor now, never a ceiling.
set_body('| verylongheaderword | b |\n| --- | --- |\n| x | y |')
app._render_table_grids()
app.update()
_sep_t = app._grid_at_line(1)
_hdr_font, _cell_font = app._grid_fonts()
check('a --- separator column still fits its widest content',
      _sep_t is not None
      and _sep_t['cells'][(0, 0)]['w']
      >= _hdr_font.measure('verylongheaderword'))
# ...and the narrowest hand-set width still ROUND-TRIPS as authored: an
# authored 2 used to write "---", which parses back as "no opinion", so
# a fully-left drag snapped the column back to content width.
app._grid_set_col_width(_sep_t, 0, 2)
app.update()
_sep_row = app.body_text.get('2.0', '2.end')
_sep_cols_n = core_tables.parse_separator(_sep_row)
check('the narrowest drag survives the separator round-trip',
      _sep_cols_n and _sep_cols_n[0]['width'] == 4)

# ---- A DEAD GRID answers no queries (new_note staleness) ----
# A full-range delete (New note, typing over Ctrl+A) destroys the
# embedded windows WITHOUT a teardown; Tk marks survive it, collapsed
# to 1.0. _grid_first_line answering for that dead grid made
# _caret_out_of_hidden walk a fresh note's caret to its END on the
# next keystroke, and shifted line-1 column math by a phantom window.
set_body('| A | B |\n| C | D |')
app._render_table_grids()
app.update()
app.body_text.delete('1.0', 'end')  # the bare delete new_note performs
app.update()
check('a grid whose windows died answers None, not line 1',
      app._grid_at_line(1) is None and app._col_base(1) == 0)
app.body_text.insert('1.0', 'hello\nworld')
app.body_text.mark_set('insert', '1.0')
app._caret_out_of_hidden()
app.update()
check('the caret guard leaves a fresh note alone after a table note',
      app.body_text.index('insert').split('.')[0] == '1')

# ---- FIND-IN-NOTE match width across an emoji ----
# search -count returns UTF-16 units while "+Nc" counts characters, so
# a matched astral emoji widened the highlight by one character apiece.
set_body('vezi \U0001F600ok maybe')
app._open_find()  # the scan model lives on the find bar's variables
app.update()
_fm = app._find_scan_model('\U0001F600ok')
app._close_find()
app.update()
check('a found emoji match covers exactly the match, no extra character',
      len(_fm) == 1
      and app.body_text.get(_fm[0]['start'], _fm[0]['end']) == '\U0001F600ok')

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
_qa_fire(_t['canvas'], '<Button-1>',
         x=_cell['x'] + 5, y=_cell['y'] + 5)
_qa_fire(_t['canvas'], '<ButtonRelease-1>',
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
_qa_fire(_cv, '<Button-1>', x=int(_a['x'] + 4), y=int(_a['y'] + 4))
_qa_fire(_cv, '<B1-Motion>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
_qa_fire(_cv, '<ButtonRelease-1>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
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
_ck = _t['cells'][(0, 0)]
_ckbb = _t['canvas'].bbox(_ck['texts'][0]) if _ck['texts'] else None
check('a checkmark is drawn centred in its cell',
      _ckbb is not None
      and abs((_ckbb[0] + _ckbb[2]) / 2 - (_ck['x'] + _ck['w'] / 2)) <= 8)

# Merging the selection makes one cell anchored top-left.
_a, _b2 = _t['cells'][(0, 0)], _t['cells'][(0, 1)]
_cv = _t['canvas']
_qa_fire(_cv, '<Button-1>', x=int(_a['x'] + 4), y=int(_a['y'] + 4))
_qa_fire(_cv, '<B1-Motion>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
_qa_fire(_cv, '<ButtonRelease-1>', x=int(_b2['x'] + 4), y=int(_b2['y'] + 4))
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
_cc = _t['cells'][(0, 0)]
_ccbb = _t['canvas'].bbox(_cc['texts'][0]) if _cc['texts'] else None
check('and the cell draws centred',
      _ccbb is not None
      and abs((_ccbb[0] + _ccbb[2]) / 2 - (_cc['x'] + _cc['w'] / 2)) <= 8)
app._open_cell_editor(_t, 0, 0)
check('and its editor justifies to match',
      str(app._cell_editor['entry'].tag_cget('cellalign', 'justify')) == 'center')
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
# The page's scrollregion can still be settling after the 60-line
# set_body under load -- a moveto against the not-yet-grown region
# lands at 0 and the whole check starts from a false floor. Insist
# until the region accepts the scroll (settle pattern, capped).
_setP = time.time() + 1.5
while app.editor_canvas.yview()[0] <= 0.05 and time.time() < _setP:
    app.update()
    time.sleep(0.02)
    app.editor_canvas.yview_moveto(1.0)
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
      f'({app._cell_editor["entry"].get("1.0", "end-1c")!r})',
      app._cell_editor is not None
      and app._cell_editor['entry'].get('1.0', 'end-1c') == '2+2=4'
      and app._cell_editor['entry'].index('insert') == '1.5')
app._commit_cell_editor()
app.update()

# The toolbar alignment buttons mean the open cell while one is open.
_t9 = app._grid_at_line(app._grid_first_line(app._table_grids[0]))
app._open_cell_editor(_t9, 0, 0)
_e9 = app._cell_editor['entry']
_e9.delete('1.0', 'end')
_e9.insert('1.0', 'Titlu')
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
app._cell_editor['entry'].delete('1.0', 'end')
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
    _qa_fire(g['canvas'], '<Button-1>',
             x=int(_ca['x'] + 12), y=int(_ca['y'] + 6))
    _qa_fire(g['canvas'], '<B1-Motion>',
             x=int(_cb['x'] + 12), y=int(_cb['y'] + 6))
    _qa_fire(g['canvas'], '<ButtonRelease-1>',
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
app.update()
take_focus(app._cell_editor['entry'])  # a precondition for the key below
app._cell_editor['entry'].event_generate('<Control-v>')
app.update()
_tX = app._grid_at_line(1)
check('Ctrl+V in a cell spreads the copied block from it',
      _tX['cells'][(1, 0)]['value'] == 'Unu'
      and _tX['cells'][(1, 1)]['value'] == 'Doi')

# The editor grows with its content instead of hiding the overflow.
app._open_cell_editor(_tX, 1, 0)
app.update()
take_focus(app._cell_editor['entry'])  # a precondition for the keys below
_edX = app._cell_editor
_w0 = int(float(_tX['canvas'].itemcget(_edX['win'], 'width')))
_edX['entry'].delete('1.0', 'end')
_edX['entry'].insert('1.0', 'un continut mult mai lung decat coloana initiala')
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
                + ''.join(f'<th>Column with a long name {i}</th>'
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
_edX['entry'].delete('1.0', 'end')
_edX['entry'].insert('1.0', 'modificare care lateste coloana vizibil')
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
# Settled baseline, same reason as the push-down check: measure only
# once the freshly committed grid has stopped moving the mapping.
settled(lambda: int(app.body_text.index('@0,0').split('.')[0]))
_yv0 = app.body_text.yview()[0]
_firstV = app._grid_first_line(app._table_grids[0])
_tV = app._grid_at_line(_firstV)
app._grid_fill_selection({'info': _tV, 'box': (0, 0, 0, 0)}, chr(0x2713),
                         align='center')
app.update()
app.update_idletasks()
app.update()
# X11 maps the fresh grid windows asynchronously, so a fixed number of
# pumps can catch the body mid-reflow -- one CI run measured 0.172
# here while the settled state sits at ~0.07 (its re-run was green).
# Wait for the PROMISED band, not for generic stability: the restore
# choreography re-pins on timers up to 360ms, and a short stable
# stretch can land exactly in the pause between a late yank and the
# re-pin that corrects it (the push-down check flaked that way). This
# stays honest about the regression it pins -- with the op's
# capture/restore removed the view shifts and STAYS shifted 0.15+, so
# the band is never entered and the cap expires into a hard failure.
_yv1 = app.body_text.yview()[0]
_stableV = 0
_settle_cap = time.time() + 8.0
while _stableV < 5 and time.time() < _settle_cap:
    app.update()
    time.sleep(0.02)
    _yv1 = app.body_text.yview()[0]
    _stableV = _stableV + 1 if abs(_yv1 - _yv0) < 0.1 else 0
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
    _edU['entry'].delete('1.0', 'end')
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
      any('Emoji' in str(_tU['canvas'].itemcget(t, 'font'))
          for t in _tU['cells'][(0, 0)]['texts']))

# The neighbouring cell, edited AFTER the emoji, must land in its own cell
# -- this is the write the drifted columns used to cut apart.
app._open_cell_editor(_tU, 0, 1)
app.update()
_eU = app._cell_editor['entry']
_eU.delete('1.0', 'end')
_eU.insert('1.0', 'vecina')
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
_md = ('| Name | Qty |\n|:-----:|---|\n| Cheese | 2 |\n| Bread | 1 |')
set_body(_md)
app._render_table_grids()
app.update()
_tS = app._grid_at_line(1)
check(f'a pasted markdown separator becomes mechanics, not a data row '
      f'({_tS["nrows"]} text rows, {_tS["data_rows"]} drawn)',
      _tS['data_rows'] == 3 and _tS['nrows'] == 4
      and _tS['sep_cols'] is not None
      and _tS['cells'][(1, 0)]['value'] == 'Cheese')
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
# the text keeps every character. The fixture word has to be WIDER than
# the column, in pixels and not in letters -- a five-letter word of narrow
# glyphs fits where a five-letter word of wide ones does not, and this
# check went quietly green that way once.
app._grid_set_col_width(_tS, 0, 4)
app.update()
_tS = app._grid_at_line(1)
_shownS = ''.join(_tS['canvas'].itemcget(t, 'text')
                  for t in _tS['cells'][(1, 0)]['texts'])
check(f'a too-narrow column draws an ellipsis and keeps its text '
      f'({_shownS!r})',
      chr(0x2026) in _shownS and _tS['cells'][(1, 0)]['value'] == 'Cheese')

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
    _del_state = (_menu_entry_state(_posted[-1], 'Delete row')
                  if _posted else None)
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
      # A default (minimum) separator now parses as "no width opinion"
      # (None) — the point stands either way: nothing stolen from the
      # neighbour, which must still read exactly 15.
      (_colsS[1]['width'] is None or _colsS[1]['width'] <= 8)
      and _colsS[2]['width'] == 15)

# Export never carries the mechanics row.
_htmlS = NO.note_to_html(body())
check('exported HTML has no separator row',
      '---' not in _htmlS and _htmlS.count('<tr>') == 3)

# Dragging the first rule resizes column 0 through press/drag/release.
_edgeS = int(_tS['col_x'][1])
_qa_fire(_tS['canvas'], '<Button-1>', x=_edgeS, y=4)
_resS = getattr(app, '_grid_resizing', None)
check('pressing a rule starts a resize, not a selection',
      _resS is not None and _resS['col'] == 0
      and getattr(app, '_grid_pressed', None) is None)
_qa_fire(_tS['canvas'], '<B1-Motion>', x=_edgeS + 70, y=4)
_qa_fire(_tS['canvas'], '<ButtonRelease-1>', x=_edgeS + 70, y=4)
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
_qa_fire(_tS['canvas'], '<Button-1>', x=_edgeS, y=4)
_qa_fire(_tS['canvas'], '<ButtonRelease-1>', x=_edgeS, y=4)
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
set_body('| Name | Qty |\n| Cheese | 2 |')
app._render_table_grids()
app.update()
_tF = app._grid_at_line(1)
app._grid_sel = {'info': _tF, 'box': (1, 0, 1, 1),
                 'cells': [(1, 0), (1, 1)]}
app._toggle_body_style('bold')
app.update()
_tF = app._grid_at_line(1)
_spanF = app._grid_cell_text_range(_tF, 1, 0)
_fontF = ' '.join(str(_tF['canvas'].itemcget(t, 'font'))
                  for t in _tF['cells'][(1, 0)]['texts'])
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
# The model changed on 2026-09-01: a CELL-level highlight covers the
# whole pipe-to-pipe region (pads included), so everything later
# inserted into the cell -- typed text, re-align pads, a checkbox --
# lands inside the tag and inherits it. The span therefore holds the
# text WITH its padding, never crossing the pipes.
check(f'and the saved highlight span covers the whole cell region '
      f'({_sliceF!r})',
      'Name' in _sliceF and '|' not in _sliceF
      and _sliceF.strip() == 'Name')
app._grid_apply_style(_tF, (0, 0, 0, 1), 'highlight', None)
app.update()
_tF = app._grid_at_line(1)
check('Clear highlight restores the exact header surface',
      _tF['canvas'].itemcget(_tF['cells'][(0, 0)]['rect'], 'fill')
      == _surfF)

# An open editor with NO selection: the color becomes the PENDING one
# -- worn by the toolbar button as a swatch, and by whatever is typed
# next in the cell. With a selection inside the editor it styles just
# that (covered by its own check further on).
app._grid_sel = None
app._open_cell_editor(_tF, 1, 1, select=False)
app.update()
_edP = app._cell_editor['entry']
_edP.tag_remove('sel', '1.0', 'end')
app._apply_body_color('text_color', '#ff0000')
app.update()
check('a color picked with the cell open becomes pending, and the '
      'button wears it',
      app._pending_text_color == '#ff0000'
      and str(app.text_color_btn.cget('bg')) == '#ff0000')
_edP.mark_set('insert', 'end-1c')
import types as _typesP
_evP = _typesP.SimpleNamespace(char='Q', keysym='Q')
app._editor_key_press(_evP)
_edP.insert('insert', 'Q')
app._editor_key_release(_evP)
check('the next typed character wears the pending color',
      any(t == 'text_color_ff0000'
          for t in _edP.tag_names('insert -1c')))
app._commit_cell_editor()
app.update()
_tF = app._grid_at_line(1)
check('and the commit carries it into the body and the drawing',
      any(_tF['canvas'].itemcget(t, 'fill') == '#ff0000'
          for t in _tF['cells'][(1, 1)]['texts']))
app._apply_body_color('text_color', None)
app.update()
check('turning the pending color off returns the button to the theme',
      app._pending_text_color is None
      and str(app.text_color_btn.cget('bg')) == app.colors['sidebar'])
app.update()
set_body('')

# ---- A CLICK ACROSS THE COMMIT'S REBUILD ----
# Typing wide in one cell and clicking another: the commit inside the
# click's open rebuilds the grids; the editor must land on the FRESH
# grid, not crash on the dead canvas (the field failure that then broke
# selections and dropped Ctrl+V into the body as literal text).
set_body('| Name | Qty |\n| a | 2 |\n| b | 3 |')
app._render_table_grids()
app.update()
_tR = app._grid_at_line(1)
app._open_cell_editor(_tR, 1, 0)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'un text mult mai lat decat coloana')
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
set_body('| Food | X | Y |\n| Fruit | Cheese |  |\n'
         '| Cereal |  |  |\n| Oua |  |  |')
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
      and focus_settles_on(app.body_text))
app.body_text.event_generate('<Control-c>')
app.update()
check(f'Ctrl+C copies the selected cells, not the entry '
      f'({app.clipboard_get()!r})',
      app.clipboard_get() == 'Fruit\nCereal')

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
_qa_fire(_cvE, '<Button-1>', x=int(_aE['x'] + 12), y=int(_aE['y'] + 6))
_qa_fire(_cvE, '<B1-Motion>', x=int(_bE['x'] + 12), y=int(_bE['y'] + 6))
_qa_fire(_cvE, '<ButtonRelease-1>',
         x=int(_bE['x'] + 12), y=int(_bE['y'] + 6))
app.body_text.event_generate('<Control-c>')
app.update()
check(f'a fast Ctrl+C straight after the drag still means the cells '
      f'({app.clipboard_get()!r})',
      app.clipboard_get() == 'Fruit\nCereal')

# A drag started over an editor whose content WIDENED the column: the
# commit's rebuild kills the gesture's canvas, so the one-gesture drag
# cannot survive -- but it must degrade loudly (the press turns into a
# click on the cell it started at, on the fresh grid), never into a
# selection that flashes and silently vanishes a moment later.
app._open_cell_editor(_tE, 1, 1)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'text destul de lat sa mute coloana')
_tE2 = app._grid_at_line(1)
_aE, _bE = _tE2['cells'][(1, 0)], _tE2['cells'][(2, 0)]
_cvE = _tE2['canvas']
_qa_fire(_cvE, '<Button-1>', x=int(_aE['x'] + 12), y=int(_aE['y'] + 6))
# The press killed this canvas (the commit rebuilt); a real mouse's
# motion and release simply never arrive on it, but SYNTHETIC events on
# a dead widget raise instead -- swallow that to mirror reality.
# Raw event_generate ON PURPOSE: _qa_fire would turn the except
# TclError below into an uncaught EventNotDelivered on a healthy app.
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
# 'Cheese' in that cell.
app._grid_fill_selection({'info': _tE, 'box': (1, 1, 1, 1)}, 'Cheese')
app.update()
_tE = app._grid_at_line(1)
_select_cells(_tE, (1, 2), (2, 2))
app.body_text.event_generate('<Control-v>')
app.update()
_tE = app._grid_at_line(1)
check('a vertical pair lands in the vertical target',
      _tE['cells'][(1, 2)]['value'] == 'Fruit'
      and _tE['cells'][(2, 2)]['value'] == 'Cereal')
check("and the editor's old cell is untouched",
      _tE['cells'][(1, 1)]['value'] == 'Cheese')

# ---- DELETE CLEARS THE SELECTED CELLS ----
_select_cells(_tE, (1, 0), (2, 0))
app.body_text.event_generate('<Delete>')
app.update()
_tE = app._grid_at_line(1)
check('Delete clears exactly the selected cells',
      _tE['cells'][(1, 0)]['value'] == ''
      and _tE['cells'][(2, 0)]['value'] == ''
      and _tE['cells'][(0, 0)]['value'] == 'Food')

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
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'citit')
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
_qa_fire(app.body_text, '<MouseWheel>', delta=-120)
app.update()
check('one wheel notch over a tall table moves the view a little, not a table',
      app.body_text.yview()[0] > 0
      and app.body_text.index('@0,0').split('.')[0] == '1')
# ...and over the drawn grid itself, the forwarded wheel does the same.
app.body_text.yview_moveto(0.0)
app.update()
_gridW = app._grid_at_line(1)
_qa_fire(_gridW['canvas'], '<MouseWheel>', delta=-120)
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
# The mid-note position is CONTENT-addressed, never a fraction: on the
# CI's Xvfb fonts the eight grids are so tall that yview_moveto(0.3)
# still lands INSIDE line 1 -- above the line the Enter edits -- and
# then the +1 promise simply doesn't apply (the app correctly held
# top=1 while the check expected 2). yview('15.0') puts line 15 at the
# top on any font metric, and the precondition the promise depends on
# is asserted outright instead of assumed.
app.body_text.yview('15.0')
# The BASELINE settles first: eight fresh grids' embedded-window
# geometry keeps shifting the mapping for several passes, so a top line
# read after a fixed pump count can be measured mid-settle -- and then
# the post-Enter promise targets the wrong line.
_topP = settled(lambda: int(app.body_text.index('@0,0').split('.')[0]))
check(f'precondition: the push-down view sits below the edit point '
      f'(top {_topP}, editing line 9)', _topP > 9)
app.body_text.mark_set('insert', '9.0')
app._on_body_return(_typesE.SimpleNamespace())
for _ in range(6):
    app.update()
    app.update_idletasks()
# The rebuilt grids' geometry settles over several event-loop passes
# (embedded windows), and a fixed pump count can measure MID-settle
# under load -- the same race the menu-op check fixed. Settle on the
# TOP VISIBLE LINE, not the scroll fraction: adding a line above the
# view changes the total height, so the fraction shifts on its own and
# jitters as the heights settle (that jitter is what flaked this check
# red on CI even at a 4s cap). And settle on the PROMISED line, not on
# any stable line: the restore choreography re-pins on timers up to
# 360ms, so generic five-reads-stable (a 100ms window) can certify the
# pause BETWEEN a late geometry yank and the re-pin that corrects it --
# which is exactly how this check flaked a third time on CI. Waiting
# for the promised line keeps the mutant asymmetry: a real regression
# never reaches it, and the cap expires into a hard failure.
_stableP = 0
_capP = time.time() + 8.0
while _stableP < 5 and time.time() < _capP:
    app.update()
    time.sleep(0.02)
    if int(app.body_text.index('@0,0').split('.')[0]) == _topP + 1:
        _stableP += 1
    else:
        _stableP = 0
# The pinned regression yanked the view nine lines up and KEPT it there
# (0.30 -> 0.14) -- so the top line lands far from _topP + 1, and this
# content-based assertion fails hard on it, with no dependence on a
# sub-pixel fraction that a slow runner never quite settles.
_landP = int(app.body_text.index('@0,0').split('.')[0])
check(f'the push-down keeps a mid-note view on the same content '
      f'(expected top {_topP + 1}, landed {_landP})',
      _landP == _topP + 1)

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
# ---- AND IT SAYS WHAT IT IS (C-22) ----
# The text-colour popup, opened from the button right beside this one, has
# carried "Pick a text color" all along. This one had no title: the header
# was written at the text popup's own call site, inside the branch
# `kind == "highlight"` never takes. It lives in the shared column function
# now, which is why the table's popup below gets the same one.
_hdrH = [str(l.cget('text')) for l in _walk_widgets(app._mini_popup, tk.Label)]
check('the toolbar highlight picker has a title line too',
      'Pick a highlight color' in _hdrH)
app._dismiss_mini_popup()
app.update()
# The other route into the same function: a table cell's highlight popup.
app._open_color_swatch_popup('text_color')
app.update()
_hdrT = [str(l.cget('text')) for l in _walk_widgets(app._mini_popup, tk.Label)]
check('the control holds: the text-colour picker still says its own name',
      'Pick a text color' in _hdrT
      and 'Pick a highlight color' not in _hdrT)
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

# ---- ALIGNING A CELL KEEPS ITS FORMATTING ----
# Alignment went through the wholesale block rewrite, whose accepted
# cost is dropping character styles -- so centering a cell silently
# stripped the bold the user had JUST applied to it. Alignment is a
# padding edit, and padding edits are exactly what pad_ops does with
# the tags left in place.
set_body('| Cap | Doi |\n| :--- | ---: |\n| gros | colorat |')
app._render_table_grids()
app.update()
_gA = app._grid_at_line(1)
app._grid_apply_style(_gA, (1, 0, 1, 0), 'bold')
app._grid_apply_style(_gA, (1, 1, 1, 1), 'highlight',
                      NO.HIGHLIGHT_COLOR_PALETTE[0])
app.update()
app._grid_set_alignment(app._grid_at_line(1), (1, 0, 1, 0),
                        core_tables.ALIGN_CENTER)
app.update()
_gA = app._grid_at_line(1)
_ln3A = app.body_text.get('3.0', '3.end')
check('centering a cell keeps its bold',
      app._grid_cell_paint(_gA, 1, 0)['bold']
      and core_tables.cell_alignments(_ln3A)[0] == core_tables.ALIGN_CENTER)
check("the neighbour cell's highlight rides through untouched",
      app._grid_cell_paint(_gA, 1, 1)['bg'] == NO.HIGHLIGHT_COLOR_PALETTE[0])
set_body('')

# ---- MULTI-LINE CELLS, RUN COLOURS, LIVE EDITOR STYLES, CHECKMARKS ----
set_body('| Cap | Doi |\n| vopsit | text |')
app._render_table_grids()
app.update()
_gM = app._grid_at_line(1)
app._grid_apply_style(_gM, (1, 0, 1, 0), 'text_color', '#ff0000')
app.update()

# the open editor SHOWS the colour it is editing
app._open_cell_editor(_gM, 1, 0, select=False)
app.update()
_edM = app._cell_editor['entry']
check('the cell editor shows the saved colour live',
      any(t.startswith('text_color_')
          for t in _edM.tag_names('1.2')))

# Enter inside the editor makes a second line; styling a SELECTION
# colours just that part -- through the real toolbar routing.
_edM.mark_set('insert', 'end-1c')
app._editor_newline()
# Enter rebuilds the grids and REOPENS the editor in the grown cell --
# the old editor widget is gone; talk to the fresh one.
_edM = app._cell_editor['entry']
_edM.insert('insert', 'sub')
_edM.tag_add('sel', '2.0', '2.3')
app._apply_body_color('text_color', '#00aa00')
app.update()
check('the toolbar colours only the selected part of the open cell',
      any(t == 'text_color_00aa00' for t in _edM.tag_names('2.1'))
      and not any(t == 'text_color_00aa00'
                  for t in _edM.tag_names('1.1')))
app._commit_cell_editor()
app.update()
app._render_table_grids()
app.update()
_gM = app._grid_at_line(1)
_cM = _gM['cells'][(1, 0)]
_runsM = [(_gM['canvas'].itemcget(t, 'text'),
           _gM['canvas'].itemcget(t, 'fill')) for t in _cM['texts']]
check('the committed cell stores the break and draws two coloured runs',
      _cM['value'] == 'vopsit<br>sub'
      and ('vopsit', '#ff0000') in _runsM
      and ('sub', '#00aa00') in _runsM
      and _cM['h'] == 2 * _gM['row_h'])

# a single character coloured in a cell stays a single coloured run
app._open_cell_editor(_gM, 1, 1, select=False)
app.update()
_edN = app._cell_editor['entry']
_edN.tag_add('sel', '1.0', '1.1')
app._apply_body_color('text_color', '#0000ff')
app._commit_cell_editor()
app.update()
_gM = app._grid_at_line(1)
_runsN = [(_gM['canvas'].itemcget(t, 'text'),
           _gM['canvas'].itemcget(t, 'fill'))
          for t in _gM['cells'][(1, 1)]['texts']]
check('one coloured letter is its own run, the rest stay theme ink',
      ('t', '#0000ff') in _runsN
      and ('ext', app.colors['text']) in _runsN)

# save + reload keeps all of it, cleanly
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'MultiCell')
app.save_current_note()
app.update()
_noteM = app.find_note(app.selected_note_id)
app.new_note()
app.update()
app.load_note(_noteM)
app.update()
_gM2 = app._grid_at_line(1)
_runsM2 = [(_gM2['canvas'].itemcget(t, 'text'),
            _gM2['canvas'].itemcget(t, 'fill'))
           for t in _gM2['cells'][(1, 0)]['texts']]
check('the multi-line coloured cell survives save and reload',
      ('vopsit', '#ff0000') in _runsM2 and ('sub', '#00aa00') in _runsM2
      and app.editor_state_matches_saved(app.capture_editor_state()))

# the checkbox palette: an UNCHECKED box lands, wearing the colour
app._grid_checkmark_popup(_gM2, (1, 1, 1, 1), 100, 100)
app.update()
_swK = None
def _findswK(w):
    global _swK
    for ch in w.winfo_children():
        if (isinstance(ch, tk.Button)
                and int(ch.cget('width') or 0) == 3 and _swK is None):
            _swK = ch
        _findswK(ch)
_findswK(app._mini_popup)
_swK.invoke()
app.update()
app.update()
_gM3 = app._grid_at_line(1)
_cK = _gM3['cells'][(1, 1)]
check('the palette drops an UNCHECKED box wearing the picked colour',
      _cK['value'] == core_tables.CHECKBOX_EMPTY
      and len(_cK['texts']) == 1
      and _gM3['canvas'].type(_cK['texts'][0]) == 'rectangle'
      and str(_gM3['canvas'].itemcget(_cK['texts'][0], 'outline'))
      == NO.PRESET_NOTE_COLORS[0])

# a click on the box TICKS it -- no text editor -- and keeps its colour
_cvK = _gM3['canvas']
_qa_fire(_cvK, '<Button-1>', x=int(_cK['x'] + _cK['w'] / 2),
         y=int(_cK['y'] + _cK['h'] / 2))
_qa_fire(_cvK, '<ButtonRelease-1>', x=int(_cK['x'] + _cK['w'] / 2),
         y=int(_cK['y'] + _cK['h'] / 2))
app.update()
_gM3 = app._grid_at_line(1)
_cK = _gM3['cells'][(1, 1)]
check('a click ticks the box, opens no editor, and the colour holds',
      _cK['value'] == core_tables.CHECKBOX_DONE
      and getattr(app, '_cell_editor', None) is None
      and len(_cK['texts']) == 2
      and _gM3['canvas'].type(_cK['texts'][1]) == 'text'
      and str(_gM3['canvas'].itemcget(_cK['texts'][1], 'fill'))
      == NO.PRESET_NOTE_COLORS[0])

# the second of two FAST clicks arrives as a double-click; it unticks
import types as _typesK
app._grid_double(_gM3, _typesK.SimpleNamespace(
    x=int(_cK['x'] + _cK['w'] / 2), y=int(_cK['y'] + _cK['h'] / 2)))
app.update()
_gM3 = app._grid_at_line(1)
check('a fast second click unticks instead of being swallowed',
      _gM3['cells'][(1, 1)]['value'] == core_tables.CHECKBOX_EMPTY)

# delete the marker and type: the cell is ordinary text again
app._open_cell_editor(_gM3, 1, 1, select=True)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'text simplu')
app._commit_cell_editor()
app.update()
_gM3 = app._grid_at_line(1)
check('overwriting the marker turns the cell back into text',
      _gM3['cells'][(1, 1)]['value'] == 'text simplu'
      and core_tables.checkbox_state('text simplu') is None)
set_body('')

# ---- TYPING CONTINUES THE STYLE IT LANDS BESIDE ----
# Tk only inherits a tag with it on both sides, so a character typed at
# the END of a blue run arrived plain -- and retyping over the opening
# select-all wiped a coloured cell to plain ink entirely.
set_body('| Cap | Doi |\n| bleu | text |')
app._render_table_grids()
app.update()
_gT = app._grid_at_line(1)
app._grid_apply_style(_gT, (1, 0, 1, 0), 'text_color', '#0000ff')
app.update()
app._open_cell_editor(_gT, 1, 0, select=False)
app.update()
_edT = app._cell_editor['entry']
import types as _typesT
_edT.mark_set('insert', 'end-1c')
_evT = _typesT.SimpleNamespace(char='X', keysym='X')
app._editor_key_press(_evT)
_edT.insert('insert', 'X')
app._editor_key_release(_evT)
check('a character typed after a blue run stays blue',
      any(t == 'text_color_0000ff'
          for t in _edT.tag_names('insert -1c')))

# retyping over the select-all keeps the colour of what it replaces --
# emulated the way the class binding does it: delete the selection,
# then insert.
_edT.tag_add('sel', '1.0', 'end-1c')
_evT2 = _typesT.SimpleNamespace(char='n', keysym='n')
app._editor_key_press(_evT2)
_edT.delete('sel.first', 'sel.last')
_edT.insert('insert', 'n')
app._editor_key_release(_evT2)
check('retyping over the opening select-all keeps the colour',
      _edT.get('1.0', 'end-1c') == 'n'
      and any(t == 'text_color_0000ff'
              for t in _edT.tag_names('1.0')))
app._commit_cell_editor()
app.update()
_gT = app._grid_at_line(1)
_runsT = [(_gT['canvas'].itemcget(t, 'text'),
           _gT['canvas'].itemcget(t, 'fill'))
          for t in _gT['cells'][(1, 0)]['texts']]
check('the retyped cell commits still coloured, not reset to plain',
      _runsT == [('n', '#0000ff')])
set_body('')

# ---- ROWS DRAG TALLER AND SHORTER; WIDE TABLES SCROLL SIDEWAYS ----
set_body('| Cap | Doi |\n| unu<br>doi | x |\n| jos | y |')
app._render_table_grids()
app.update()
_gR = app._grid_at_line(1)
check('the rule between two rows is grabbable, the middle of a row is not',
      app._grid_row_boundary_at(_gR, _gR['row_y'][1]) == 0
      and app._grid_row_boundary_at(_gR, _gR['row_y'][1] + 20) is None)
app._grid_set_row_lines(_gR, 2, 3)
app.update()
_gR = app._grid_at_line(1)
check('dragging a row taller pads it with empty lines',
      _gR['cells'][(2, 0)]['h'] == 3 * _gR['row_h']
      and _gR['cells'][(2, 0)]['value'] == 'jos<br><br>')
app._grid_set_row_lines(_gR, 2, 1)
app.update()
_gR = app._grid_at_line(1)
check('dragging it back short trims the padding again',
      _gR['cells'][(2, 0)]['h'] == _gR['row_h']
      and _gR['cells'][(2, 0)]['value'] == 'jos')
app._grid_set_row_lines(_gR, 1, 1)
app.update()
_gR = app._grid_at_line(1)
check('a drag can never cut real content: two full lines stay two',
      _gR['cells'][(1, 0)]['value'] == 'unu<br>doi'
      and _gR['cells'][(1, 0)]['h'] == 2 * _gR['row_h'])

# fast typing: press, press, release, release -- BOTH characters must
# come out coloured; the paint used to wait for its own release and the
# next press overwrote its bookkeeping.
app._open_cell_editor(_gR, 2, 1, select=False)
app.update()
import types as _typesR
app._apply_body_color('text_color', '#aa00aa')
_edR = app._cell_editor['entry']
_edR.mark_set('insert', 'end-1c')
_evA = _typesR.SimpleNamespace(char='a', keysym='a')
_evB = _typesR.SimpleNamespace(char='b', keysym='b')
app._editor_key_press(_evA)
_edR.insert('insert', 'a')
app._editor_key_press(_evB)
_edR.insert('insert', 'b')
app._editor_key_release(_evA)
app._editor_key_release(_evB)
check('fast interleaved typing colours every character',
      any(t == 'text_color_aa00aa'
          for t in _edR.tag_names('insert -2c'))
      and any(t == 'text_color_aa00aa'
              for t in _edR.tag_names('insert -1c')))
app._apply_body_color('text_color', None)

# Ctrl+A selects the whole cell, not a line-start jump
take_focus(_edR)
_edR.event_generate('<Control-a>')
app.update()
_selR = None
try:
    _selR = (str(_edR.index('sel.first')), str(_edR.index('sel.last')))
except tk.TclError:
    pass
check('Ctrl+A in the cell editor selects the whole cell',
      _selR == ('1.0', str(_edR.index('end-1c'))))
app._commit_cell_editor()
app.update()

# a table wider than the editor grows its own horizontal scrollbar
set_body('| ' + ' | '.join('Coloana%d' % i for i in range(12)) + ' |\n'
         + '| ' + ' | '.join('valoare%d' % i for i in range(12)) + ' |')
app._render_table_grids()
app.update()
app.update_idletasks()
_gW = app._grid_at_line(1)
check('a wide table shows its own horizontal scrollbar',
      _gW.get('hbar') is not None
      and _gW['hbar'].winfo_manager() == 'pack')
set_body('')

# ---- A CLICK IN THE BODY RELEASES THE TABLE'S CELL SELECTION ----
# A cell selection lingering from an earlier drag silently caught the
# next toolbar colour meant for the body text -- 'coloring stopped
# working' on plain notes that merely FOLLOWED a table interaction.
set_body('| A | B |\n| c | d |\n\ncorp de colorat')
app._render_table_grids()
app.update()
_gS = app._grid_at_line(1)
app._grid_select_range(_gS, (1, 0), (1, 1))
app.update()
_qa_fire(app.body_text, '<Button-1>', x=5, y=5)
app.update()
_lastS = int(app.body_text.index('end-1c').split('.')[0])
app.body_text.tag_add('sel', '%d.0' % _lastS, '%d.4' % _lastS)
take_focus(app.body_text)
app._apply_body_color('text_color', '#ff0000')
app.update()
check('after a body click, the toolbar colour reaches the body again',
      getattr(app, '_grid_sel', None) is None
      and any(t == 'text_color_ff0000'
              for t in app.body_text.tag_names('%d.2' % _lastS)))

# ---- A DRAG INSIDE ONE CELL SELECTS THAT CELL WHOLE ----
# Selection used to begin only when the drag REACHED a second cell, so
# one cell alone could never be selected -- grabbing the checkmark
# meant grabbing its neighbour too.
_cS = _gS['cells'][(1, 1)]
_cvS = _gS['canvas']
_qa_fire(_cvS, '<Button-1>', x=int(_cS['x'] + 12),
         y=int(_cS['y'] + 8))
_qa_fire(_cvS, '<B1-Motion>', x=int(_cS['x'] + 30),
         y=int(_cS['y'] + 20))
_qa_fire(_cvS, '<ButtonRelease-1>', x=int(_cS['x'] + 30),
         y=int(_cS['y'] + 20))
app.update()
check('a real drag inside one cell selects exactly that cell',
      getattr(app, '_grid_sel', None) is not None
      and app._grid_sel['box'] == (1, 1, 1, 1)
      and getattr(app, '_cell_editor', None) is None)
app._grid_clear_selection()
set_body('')

# ---- THE EDITOR'S LIGHT/DARK FLIP ----
_wasT = app.theme_name
check('the editor carries the quick light/dark toggle',
      hasattr(app, 'editor_theme_btn')
      and app.editor_theme_btn.winfo_exists())
app.editor_theme_btn.invoke()
app.update()
_flippedT = app.theme_name
app.editor_theme_btn.invoke()
app.update()
check('one press flips dark/light, the next flips back, glyph follows',
      (_wasT in NO.DARK_THEMES) != (_flippedT in NO.DARK_THEMES)
      and app.theme_name == _wasT
      and str(app.editor_theme_btn.cget('text'))
      == ('\u2600' if app.theme_name in NO.DARK_THEMES else '\U0001f319'))

# ---- WHOLE ROWS COPY TO THE BOTTOM, LIKE COLUMNS COPY TO THE EDGE ----
set_body('| Cap | Doi |\n| unu | doi |\n| trei | patru |')
app._render_table_grids()
app.update()
_gV = app._grid_at_line(1)
app._grid_append_rows(_gV, 1, 2)
app.update()
_gV = app._grid_at_line(1)
_rowsV = [core_tables.split_row(app.body_text.get('%d.0' % n,
                                                  '%d.end' % n))
          for n in range(1, 6)]
check('selected rows are copied again to the bottom, text and all',
      _gV['data_rows'] == 5
      and _rowsV[3] == ['unu', 'doi'] and _rowsV[4] == ['trei', 'patru'])
set_body('| A | B |\n| ^ | c |\n| x | y |')
app._render_table_grids()
app.update()
app._grid_append_rows(app._grid_at_line(1), 1, 1)
app.update()
check('a merge marker pointing above the copied span lands empty',
      core_tables.split_row(app.body_text.get('4.0', '4.end'))
      == ['', 'c'])

# ---- DRAG-SELECTING FOLLOWS THE POINTER PAST THE VIEW ----
# The pointer is faked at the grid's right edge / under the note's
# bottom edge; the autoscroll must pan the grid, scroll the note, and
# stretch the selection to what the pointer now covers.
set_body('| ' + ' | '.join('C%d' % i for i in range(14)) + ' |\n'
         + '| ' + ' | '.join('v%d' % i for i in range(14)) + ' |')
app._render_table_grids()
app.update()
app.update_idletasks()
_gV = app._grid_at_line(1)
_cvV = _gV['canvas']
_c00V = _gV['cells'][(0, 0)]
_qa_fire(_cvV, '<Button-1>', x=int(_c00V['x'] + 20),
         y=int(_c00V['y'] + 8))
_shownV = int(float(_cvV.cget('width')))
_origPtr = app.winfo_pointerxy
app.winfo_pointerxy = lambda: (_cvV.winfo_rootx() + _shownV - 5,
                               _cvV.winfo_rooty() + int(_c00V['y']) + 8)
_xv0 = _cvV.xview()[0]
for _ in range(14):
    app._grid_drag_autoscroll(_gV)
app.update()
check('holding the drag at the right edge pans the grid and grows the '
      'selection to the far columns',
      _cvV.xview()[0] > _xv0
      and getattr(app, '_grid_sel', None) is not None
      and app._grid_sel['box'][3] >= 10)
app.winfo_pointerxy = _origPtr
_qa_fire(_cvV, '<ButtonRelease-1>', x=_shownV - 5,
         y=int(_c00V['y'] + 8))
app.update()

set_body('| Cap | Doi |\n'
         + '\n'.join('| r%02d | v%02d |' % (i, i) for i in range(40)))
app._render_table_grids()
app.update()
app.update_idletasks()
app.body_text.yview_moveto(0.0)
app.update()
_gV = app._grid_at_line(1)
_cvV = _gV['canvas']
_c00V = _gV['cells'][(0, 0)]
_qa_fire(_cvV, '<Button-1>', x=int(_c00V['x'] + 20),
         y=int(_c00V['y'] + 8))
app.winfo_pointerxy = lambda: (
    app.body_text.winfo_rootx() + 60,
    app.body_text.winfo_rooty() + app.body_text.winfo_height() - 4)
_yv0 = app.body_text.yview()[0]
for _ in range(16):
    app._grid_drag_autoscroll(_gV)
app.update()
check('holding the drag under the note scrolls it and grows the '
      'selection downward',
      app.body_text.yview()[0] > _yv0
      and getattr(app, '_grid_sel', None) is not None
      and app._grid_sel['box'][2] >= 5)
app.winfo_pointerxy = _origPtr
# the timer wiring: a motion arms it, the release stops it
_qa_fire(_cvV, '<B1-Motion>', x=int(_c00V['x'] + 25),
         y=int(_c00V['y'] + 9))
app.update()
_armedV = getattr(app, '_grid_autoscroll_job', None) is not None
_qa_fire(_cvV, '<ButtonRelease-1>', x=int(_c00V['x'] + 25),
         y=int(_c00V['y'] + 9))
app.update()
check('the autoscroll timer arms on drag and stops on release',
      _armedV
      and getattr(app, '_grid_autoscroll_job', None) is None)
app._grid_clear_selection()
set_body('')

# ---- THE NOTE LIST'S SCROLL GUARDS ----
# The editor page has pinned short content to the top since 0.32.x;
# the list showed the same family of symptoms (a displaced origin, and
# a rebuild clamping the scroll to the top) without either guard.
_savedNotes23 = app.notes
app.notes = [NO.normalize_note({'id': 9000 + i, 'title': 'Scurt %d' % i,
                                'body': 'x', 'category': 'General'})
             for i in range(2)]
app.refresh_note_list()
app.update()
app.update_idletasks()
_cv23 = app.canvas
_cv23.configure(scrollregion=(0, 0, 250, 1200))
_cv23.yview_moveto(0.3)
app.update()
_disp23 = _cv23.canvasy(0)
app._sync_list_scroll()
app.update()
check('a displaced list origin snaps back to the top',
      _disp23 > 100 and _cv23.canvasy(0) == 0)

app.notes = [NO.normalize_note({'id': 9100 + i, 'title': 'Lung %d' % i,
                                'body': 'corp', 'category': 'General'})
             for i in range(30)]
app.refresh_note_list()
app.update()
app.update_idletasks()
_cv23.yview_moveto(0.6)
app.update()
_px23 = _cv23.canvasy(0)
app.refresh_note_list()
_cv23.yview_moveto(0.0)   # the transient clamp a mid-rebuild Configure does
for _ in range(4):
    app.update()
    app.update_idletasks()
check('a full list rebuild restores the scroll in pixels, clamp or not',
      _px23 > 200 and abs(_cv23.canvasy(0) - _px23) < 30)

# A rebuilt list's geometry settles over several event-loop passes (one
# collapse measured heights 106 -> 276 -> 820 as separate Configure
# events), and a LATER pass can re-clamp the canvas after the idle-time
# restore already ran. The restore stays in force for a short window,
# re-applied on Configure and on timers -- so a second clamp landing on
# its own event-loop pass must lose too.
_cv23.yview_moveto(0.6)
app.update()
# Settled baseline: the app's own restore snapshots the position when
# refresh runs -- our reference must be the value that has stopped
# moving, or the promised band below targets a mid-settle read.
_px24 = settled(lambda: _cv23.canvasy(0))
app.refresh_note_list()
_cv23.yview_moveto(0.0)          # clamp before the idle restore
app.update()
app.update_idletasks()
_cv23.yview_moveto(0.0)          # a later settling pass clamps AGAIN
# Wait for the promised landing (the restore winning), not a fixed
# window -- on a loaded runner the restore timers can land after any
# fixed wait. With the restore gone the canvas stays clamped at 0,
# the band is never entered, and the cap expires into a hard failure.
_t24_end = time.time() + 8.0
_st24 = 0
while _st24 < 5 and time.time() < _t24_end:
    app.update()
    time.sleep(0.02)
    _st24 = _st24 + 1 if abs(_cv23.canvasy(0) - _px24) < 30 else 0
check('the rebuild restore outlives staged re-clamps',
      _px24 > 200 and abs(_cv23.canvasy(0) - _px24) < 30)

# Collapsing a group while scrolled deep below its cards: the content
# shrinks under the canvas, the now off-screen list frame never fires
# Configure, and the stale scrollregion left a blank viewport (the
# canvas parked past the end of the real content). The timed restore
# must land the view at the END of the shorter list, not blank space
# and not the top.
_g24 = []
for _i24 in range(16):
    _g24.append(NO.normalize_note(
        {'id': 9200 + _i24, 'title': 'General %d' % _i24,
         'body': 'corp ' * 12, 'category': 'General'}))
for _i24 in range(12):
    _g24.append(NO.normalize_note(
        {'id': 9300 + _i24, 'title': 'Work %d' % _i24,
         'body': 'corp ' * 12, 'category': 'Work'}))
app.notes = _g24
app.group_by_category.set(True)
app._on_toggle_group_by_category()
app.update()
app.update_idletasks()
_cv23.yview_moveto(1.0)
app.update()
app._toggle_group_collapsed('General')
# Same promised-landing wait: the target (end of the shorter list) is
# recomputed each read because the content height itself settles.
_t24_end = time.time() + 8.0
_st24b = 0
while _st24b < 5 and time.time() < _t24_end:
    app.update()
    time.sleep(0.02)
    _bb24 = _cv23.bbox('all')
    _ch24 = (_bb24[3] - _bb24[1]) if _bb24 else 0
    _max24 = _ch24 - _cv23.winfo_height()
    _st24b = (_st24b + 1
              if _max24 > 100 and abs(_cv23.canvasy(0) - _max24) < 30
              else 0)
_bb24 = _cv23.bbox('all')
_ch24 = (_bb24[3] - _bb24[1]) if _bb24 else 0
_max24 = _ch24 - _cv23.winfo_height()
check('collapsing from deep scroll lands at the end, not a blank view',
      _max24 > 100 and abs(_cv23.canvasy(0) - _max24) < 30)
app.collapsed_groups.discard('General')
app.group_by_category.set(False)
app._on_toggle_group_by_category()
app.notes = _savedNotes23
app.refresh_note_list()
app.update()

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
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'scris in timpul comutarii')
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
# A transition that does NOT bring the calendar into view must leave the
# work deferred rather than do it: _catch_up_deferred_refresh() runs on
# every note switch too, and rebuilding an off-screen month there is the
# same waste in a different place. The promise is not "the flag is
# cleared" -- it is "the calendar is never SEEN stale".
app._catch_up_deferred_refresh()
app.update()
check('a transition that does not show the calendar leaves it deferred',
      getattr(app, '_calendar_needs_render', False) is True)
app.notebook.select(app.TAB_CALENDAR)
app.update()
check('the deferred calendar rebuild is caught up when the tab is opened',
      getattr(app, '_calendar_needs_render', False) is False)
check('...and the month really was drawn, not merely marked done',
      len(app.cal_grid_frame.winfo_children()) > 0)
app.notebook.select(app.TAB_NOTES)
app.update()

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
    _qa_fire(w, '<Button-1>', x=x, y=y, time=t)
    _qa_fire(w, '<ButtonRelease-1>', x=x, y=y, time=t + 10)
    _qa_fire(w, '<Button-1>', x=x, y=y, time=t + 120)
    _qa_fire(w, '<ButtonRelease-1>', x=x, y=y, time=t + 130)
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

# ---- COMMENTS KEEP TABLES OUT ----
# Comments render as plain text (no grid), so a pasted table used to land
# as raw pipe soup. A paste carrying table rows drops them, keeps the
# prose, and says so; a plain paste is untouched.
_toastsCP = []
_origToastCP = app._show_toast
app._show_toast = lambda text, kind='success': _toastsCP.append(text)
_c.delete('1.0', 'end')
app.clipboard_clear()
app.clipboard_append('Before' + chr(10) + '| Name | Qty |' + chr(10)
                     + '| --- | --- |' + chr(10) + '| Cheese | 2 |' + chr(10)
                     + 'After')
_c.focus_force()
app.update()
_c.event_generate('<<Paste>>')
app.update()
_cpTxt = _c.get('1.0', 'end-1c')
check('comments strip a pasted table to its prose, with a note',
      '|' not in _cpTxt and 'Before' in _cpTxt and 'After' in _cpTxt
      and any('text only' in t.lower() or "wasn't added" in t
              for t in _toastsCP))
# A plain paste (no table) still lands untouched.
_c.delete('1.0', 'end')
app.clipboard_clear(); app.clipboard_append('doar text')
_c.focus_force(); app.update()
_c.event_generate('<<Paste>>')
app.update()
check('comments still accept ordinary pasted text',
      _c.get('1.0', 'end-1c').strip() == 'doar text')
app._show_toast = _origToastCP
_c.tag_remove('sel', '1.0', 'end')
_c.delete('1.0', 'end')
app.update()

# ---- PERSISTENCE TO DISK ----
app.save_notes()
disk_path = NO.DATA_FILE
# ---- EXPORT ONE NOTE AS A FILE ----
# The context menu's three formats, driven through the real method with
# the save dialog stubbed. Runs in this script's own scratch directory.
import tkinter.filedialog as _fdX
import io as _ioX
_exp_note = NO.normalize_note({
    'id': 8800, 'title': 'Export <proba>',
    'body': ('linia intai' + chr(10)
             + chr(0x2022) + ' bullet' + chr(10)
             + '| A | B |' + chr(10) + '| --- | --- |' + chr(10)
             + '| [x] | val |' + chr(10) + 'coada'),
    'formatting': [{'start': 0, 'end': 5, 'style': 'bold'}],
    'paragraphs': [{'line': 1, 'kind': 'bullet'}],
    'comments': 'un comentariu', 'category': 'General',
    'checklist': [{'text': 'facut deja', 'done': True},
                  {'text': 'de facut <inca>', 'done': False}]})
_exp_dir = os.path.abspath('qa_export_out')
os.makedirs(_exp_dir, exist_ok=True)
_toastsX = []
_origToastX = app._show_toast
app._show_toast = lambda text, kind='success': _toastsX.append(text)
_origAskSaveX = _fdX.asksaveasfilename
_origAskYNX = app.ask_yes_no
_openAsksX = []
app.ask_yes_no = (lambda title, msg, **kw:
                  (_openAsksX.append(title), False)[1])

_pX = os.path.join(_exp_dir, 'nota.html')
_fdX.asksaveasfilename = lambda **kw: _pX
app.export_note_as_file(_exp_note, 'html')
_htmlX = _ioX.open(_pX, encoding='utf-8').read() if os.path.exists(_pX) else ''
check('HTML export writes a full document with the table as a table',
      _htmlX.startswith('<!DOCTYPE html>') and '<table>' in _htmlX
      and '&lt;proba&gt;' in _htmlX and '<b>linia</b>' in _htmlX)

_pX = os.path.join(_exp_dir, 'nota.txt')
_fdX.asksaveasfilename = lambda **kw: _pX
app.export_note_as_file(_exp_note, 'txt')
_txtX = _ioX.open(_pX, encoding='utf-8').read() if os.path.exists(_pX) else ''
check('text export is the body as stored, comments included',
      'linia intai' in _txtX and 'un comentariu' in _txtX)
check('the checklist exports in both formats, states kept',
      chr(0x2611) + ' facut deja' in _htmlX
      and chr(0x2610) + ' de facut' in _htmlX
      and '&lt;inca&gt;' in _htmlX
      and '[x] facut deja' in _txtX)
check('each export announces itself with a toast',
      len(_toastsX) == 2 and all('Exported to' in t for t in _toastsX))

_before_cancelX = sorted(os.listdir(_exp_dir))
_fdX.asksaveasfilename = lambda **kw: ''
app.export_note_as_file(_exp_note, 'html')
check('cancelling the save dialog writes nothing',
      sorted(os.listdir(_exp_dir)) == _before_cancelX)

_seenX = {}
_fdX.asksaveasfilename = lambda **kw: _seenX.update(kw) or ''
app.export_note_as_file(_exp_note, 'html')
check('the suggested filename is scrubbed of forbidden characters',
      _seenX.get('initialfile') == 'Export _proba.html')
check('each single export offers to open the file',
      len([t for t in _openAsksX if 'Open it now' in t]) == 2)

# ---- EXPORT x EMOJI: a just-typed emoji must not crash the export ----
# Tk hands an astral emoji over as a UTF-16 surrogate pair, and the export
# writes utf-8. Unmended, f.write raised UnicodeEncodeError — a ValueError
# the callers' (IOError, OSError) guards never caught, so the export
# crashed (audit Z05-F02's export sibling). _note_export_content mends at
# the shared choke point: the content must be utf-8-encodable with the
# emoji arriving whole.
_emoji_note = NO.normalize_note({
    'id': 8802, 'title': 'Emoji', 'body': 'x' + chr(0xD83D) + chr(0xDE00),
    'category': 'General'})
try:
    _emo_content = app._note_export_content(_emoji_note, 'txt', 'Emoji')
    _emo_content.encode('utf-8')
    _emo_ok = '\U0001F600' in _emo_content
except Exception:
    _emo_ok = False
check('export content mends a just-typed emoji instead of crashing', _emo_ok)

# ---- BULK EXPORT ----
# Two notes with the SAME title -> the second gets the " (2)" suffix.
_exp_note2 = NO.normalize_note({
    'id': 8801, 'title': 'Export <proba>', 'body': 'alt corp',
    'category': 'General'})
_savedNotesX = app.notes
app.notes = [_exp_note, _exp_note2]
app.selected_note_ids = {8800, 8801}
_bulk_dir = os.path.join(_exp_dir, 'bulk')
os.makedirs(_bulk_dir, exist_ok=True)
_fdX.askdirectory = lambda **kw: _bulk_dir
_toastsX.clear()
app._bulk_export_run('txt')
_bulk_files = sorted(os.listdir(_bulk_dir))
check('bulk export writes one file per note',
      _bulk_files == ['Export _proba (2).txt', 'Export _proba.txt'])
_first = _ioX.open(os.path.join(_bulk_dir, 'Export _proba.txt'),
                   encoding='utf-8').read()
_second = _ioX.open(os.path.join(_bulk_dir, 'Export _proba (2).txt'),
                    encoding='utf-8').read()
check('same-title notes never overwrite each other',
      'linia intai' in _first and 'alt corp' in _second)
check('bulk export renders through the same pipeline as single',
      _first == app._note_export_content(_exp_note, 'txt', 'Export <proba>'))
check('bulk export announces the count',
      any('Exported 2 note(s)' in t for t in _toastsX))
check('bulk export leaves selection mode',
      not app.selection_mode and not app.selected_note_ids)
app._toggle_selection_mode()
app.update()
app.update_idletasks()
_barW1 = app.bulk_action_bar.winfo_reqwidth()
_sbW1 = app.sidebar.winfo_width()
# Windows metrics only: the app ships with Segoe UI on Windows, and
# that is the layout the 280px sidebar was sized against. Xvfb's
# fallback font at size 7 is far wider (407px measured), which says
# nothing about the shipped product -- same reasoning as ISSUES_LOG's
# "The pixel-perfect test that only worked on Windows".
check('the bulk action bar fits the fixed sidebar '
      '(%dpx of %dpx; asserted on Windows only)' % (_barW1, _sbW1),
      _barW1 <= _sbW1 - 8 or sys.platform != 'win32')
app._toggle_selection_mode()
app.update()
app.notes = _savedNotesX
app.refresh_note_list()
app.update()
app.ask_yes_no = _origAskYNX
_fdX.asksaveasfilename = _origAskSaveX
app._show_toast = _origToastX

# ---- FIELD ROUND: RESIZE KEEPS STYLES, ALIGNMENT SURVIVES TYPING,
# ---- THE CELL EDITOR WEARS ITS CELL ----

def _table_spans_F():
    _st = app.capture_editor_state()
    return sorted((sp['style'], sp.get('value', ''),
                   _st['body'][sp['start']:sp['end']])
                  for sp in _st['formatting'])


def _styled_table_F():
    set_body('| rosu | verde |' + chr(10) + '| --- | --- |' + chr(10)
             + '| gros | plin |')
    app._render_table_grids()
    app.update()
    _b = app.body_text
    app._ensure_color_tag(_b, 'text_color', '#e63946')
    app._ensure_color_tag(_b, 'highlight', '#ffff00')
    _l1 = _b.get('1.0', '1.end')
    _b.tag_add('text_color_e63946', '1.%d' % _l1.index('rosu'),
               '1.%d' % (_l1.index('rosu') + 4))
    _l3 = _b.get('3.0', '3.end')
    _b.tag_add('highlight_ffff00', '3.%d' % _l3.index('plin'),
               '3.%d' % (_l3.index('plin') + 4))
    _b.tag_add('bold', '3.%d' % _l3.index('gros'),
               '3.%d' % (_l3.index('gros') + 4))
    app.update()
    return app._grid_at_line(1)


# 1. Dragging a column's width no longer burns the whole table's styles.
_infoF = _styled_table_F()
_beforeF = _table_spans_F()
app._grid_set_col_width(_infoF, 0, 20)
app.update()
check('a column-width drag keeps every style in the table',
      len(_beforeF) == 3 and _table_spans_F() == _beforeF)

# 2. Dragging a row's height keeps the anchor cell's styles.
_infoF = _styled_table_F()
_beforeF = _table_spans_F()
app._grid_set_row_lines(_infoF, 1, 3)
app.update()
check('a row-height drag keeps the padded cell styled too',
      len(_beforeF) == 3 and _table_spans_F() == _beforeF)

# 3. Typing on a centred line leaves it centred -- through the REAL
# KeyRelease binding, not a direct call to the handler.
set_body('fig1')
_b = app.body_text
_b.tag_add('align_center', '1.0', '1.end')
take_focus(_b)
_b.mark_set('insert', '1.0')
_b.event_generate('<KeyPress>', keysym='X')
_b.insert('insert', 'X')
_b.event_generate('<KeyRelease>', keysym='X')
app.update()
check('typing at the start of a centred line keeps it centred',
      'align_center' in _b.tag_names('1.0'))
_b.delete('1.0', 'end')
_b.tag_add('align_center', '1.0', '1.end+1c')
take_focus(_b)
_b.mark_set('insert', '1.0')
_b.event_generate('<KeyPress>', keysym='f')
_b.insert('insert', 'f')
_b.event_generate('<KeyRelease>', keysym='f')
app.update()
check('the first character typed into an empty centred line is centred',
      'align_center' in _b.tag_names('1.0'))
set_body('')

# 4. The cell editor wears the cell's background -- full, empty, and
# while typing; an unstyled cell stays on the theme's surface.
set_body('| plin | gol | simplu |' + chr(10) + '| --- | --- | --- |'
         + chr(10) + '| text |  | alt |')
app._render_table_grids()
app.update()
_infoF = app._grid_at_line(1)
_b = app.body_text
app._ensure_color_tag(_b, 'highlight', '#ffff00')
_l3 = _b.get('3.0', '3.end')
_b.tag_add('highlight_ffff00', '3.%d' % _l3.index('text'),
           '3.%d' % (_l3.index('text') + 4))
import re as _reF
_pipesF = [m.start() for m in _reF.finditer(_reF.escape('|'), _l3)]
_b.tag_add('highlight_ffff00', '3.%d' % (_pipesF[1] + 1),
           '3.%d' % _pipesF[2])
app._grid_restyle(_infoF)
app.update()
_wantF = app._blend_hex('#ffff00', app.colors['card'], 0.45)
app._open_cell_editor(_infoF, 1, 0)
_bgFull = str(app._cell_editor['entry'].cget('bg'))
app._commit_cell_editor()
app.update()
_infoF = app._grid_at_line(1)
app._open_cell_editor(_infoF, 1, 1)
_edF = app._cell_editor['entry']
_bgEmpty = str(_edF.cget('bg'))
_edF.insert('insert', 'nou')
app.update()
_bgTyping = str(_edF.cget('bg'))
app._commit_cell_editor()
app.update()
_infoF = app._grid_at_line(1)
app._open_cell_editor(_infoF, 1, 2)
_bgPlain = str(app._cell_editor['entry'].cget('bg'))
app._commit_cell_editor()
check('the cell editor wears a highlighted cell (filled, empty, mid-typing)',
      _bgFull == _wantF and _bgEmpty == _wantF and _bgTyping == _wantF)
check('and stays on the theme surface for an unstyled cell',
      _bgPlain == app.colors['card'])
set_body('')

# ---- FIELD ROUND 2: THE CELL-LEVEL HIGHLIGHT SURVIVES EVERYTHING ----
def _fresh_G(cols=3):
    set_body('|' + '|'.join(['     '] * cols) + '|' + chr(10)
             + '|' + '|'.join([' --- '] * cols) + '|' + chr(10)
             + '|' + '|'.join(['     '] * cols) + '|')
    app._render_table_grids()
    app.update()
    return app._grid_at_line(1)


# The exact chain from the report: colour the empty cell -> type text ->
# commit -> drag the column. The colour died logically at the commit and
# visibly at the drag (the first rebuild).
_infoG = _fresh_G(3)
app._grid_apply_style(_infoG, (1, 0, 1, 0), 'highlight', '#ffff00')
app.update()
app._open_cell_editor(_infoG, 1, 0)
_edG = app._cell_editor['entry']
_edG.delete('1.0', 'end')
_edG.insert('1.0', 'text')
app._commit_cell_editor()
app.update()
_infoG = app._grid_at_line(1)
_bg1G = app._grid_cell_paint(_infoG, 1, 0)['bg']
app._grid_set_col_width(_infoG, 0, 12)
app.update()
_infoG = app._grid_at_line(1)
_bg2G = app._grid_cell_paint(_infoG, 1, 0)['bg']
app._grid_set_alignment(_infoG, (1, 0, 1, 0), 'center')
app.update()
_infoG = app._grid_at_line(1)
_bg3G = app._grid_cell_paint(_infoG, 1, 0)['bg']
check('typing into a coloured cell keeps its colour through commit, '
      'drag and centring',
      _bg1G == _bg2G == _bg3G == '#ffff00')

# The checkbox through the popup path (fill) on a coloured cell.
_infoG = _fresh_G(3)
app._grid_apply_style(_infoG, (1, 1, 1, 1), 'highlight', '#c8f7c5')
app.update()
app._grid_fill_selection({'info': _infoG, 'box': (1, 1, 1, 1)},
                         core_tables.CHECKBOX_EMPTY,
                         align=core_tables.ALIGN_CENTER)
app.update()
_infoG = app._grid_at_line(1)
check('a checkbox dropped into a coloured cell keeps the cell coloured',
      app._grid_cell_paint(_infoG, 1, 1)['bg'] == '#c8f7c5'
      and _infoG['cells'][(1, 1)]['value'] == core_tables.CHECKBOX_EMPTY)

# Duplicating the table: copy cells -> click below the table -> paste.
_infoG = _fresh_G(2)
app._write_cell(_infoG, 1, 1, 'val')
app.update()
_infoG = app._grid_at_line(1)
app._grid_copy_selection({'info': _infoG, 'box': (0, 0, 1, 1)})
app._grid_clear_selection()
app.body_text.mark_set('insert', '4.0')
app.update()
_okG = app._paste_tsv_as_table()
app.update()
_bodyG = app.body_text.get('1.0', 'end-1c')
_blocksG = core_tables.find_blocks(_bodyG)
check('pasting copied cells below the table makes a SECOND table',
      _okG and len(_blocksG) == 2)
_secondG = _bodyG.split(chr(10))[_blocksG[1][0]:_blocksG[1][1] + 1]     if len(_blocksG) == 2 else []
check('and the two tables stay separate blocks with the values intact',
      len(_blocksG) == 2 and any('val' in ln for ln in _secondG))
set_body('')

# ---- FIELD ROUND 3 ----
# Autofit over a selection of columns, in a single pass.
set_body('| lung continut aici | x |' + chr(10) + '| --- | --- |'
         + chr(10) + '| a | b |')
app._render_table_grids()
app.update()
_iH = app._grid_at_line(1)
app._grid_set_col_width(_iH, 0, 40)
app.update()
_iH = app._grid_at_line(1)
_sepH0 = app.body_text.get('2.0', '2.end')
app._grid_autofit_cols(_iH, 0, 1)
app.update()
_sepH1 = app.body_text.get('2.0', '2.end')
check('autofit over a column selection shrinks the set widths',
      len(_sepH1) < len(_sepH0))

# The copy remembers the widths; the paste rebuilds them identically.
_iH = app._grid_at_line(1)
app._grid_set_col_width(_iH, 0, 30)
app.update()
_iH = app._grid_at_line(1)
_sepSrcH = app.body_text.get('2.0', '2.end')
app._grid_select_range(_iH, (0, 0), (1, 1))
app._grid_copy_selection({'info': _iH, 'box': (0, 0, 1, 1)})
app._grid_clear_selection()
app.body_text.mark_set('insert', '4.0')
app.update()
app._paste_tsv_as_table()
app.update()
_bodyH = app.body_text.get('1.0', 'end-1c')
_blkH = core_tables.find_blocks(_bodyH)
_sepNewH = (_bodyH.split(chr(10))[_blkH[1][0] + 1]
            if len(_blkH) == 2 else '')
check('a duplicated table comes back at the SAME column widths',
      len(_blkH) == 2 and _sepSrcH.strip() == _sepNewH.strip())
set_body('')

# The checkbox through the REAL popup: caret and scroll stay put.
set_body('sus' + chr(10) + '| a | b |' + chr(10) + '| --- | --- |'
         + chr(10) + '|   |   |' + chr(10) + ('jos ' * 200))
app._render_table_grids()
app.update()
_iH = app._grid_at_line(2)
app.body_text.mark_set('insert', '1.0')
app.body_text.yview_moveto(0.0)
app.update()
_y0H = app.body_text.yview()[0]
# A mark on the HEADER (a line the surgical writes never touch): the
# old fill deleted and reinserted the whole block, collapsing the mark
# -- exactly the rewrite that expelled the caret and moved the scroll.
app.body_text.mark_set('probeH', '2.3')
app._grid_checkmark_popup(_iH, (1, 0, 1, 0), 200, 200)
app.update()
_btnH = []


def _find_theme_btn(w):
    for ch in w.winfo_children():
        try:
            if (ch.winfo_class() == 'Button'
                    and str(ch.cget('text')) == 'Theme color'):
                _btnH.append(ch)
        except Exception:
            pass
        _find_theme_btn(ch)


_find_theme_btn(app._mini_popup)
_btnH[0].invoke()
app.update()
_iH = app._grid_at_line(2)
check('the checkbox palette writes surgically: value set, caret and '
      'scroll unmoved',
      _iH['cells'][(1, 0)]['value'] == core_tables.CHECKBOX_EMPTY
      and app.body_text.index('insert').split('.')[0] == '1'
      and abs(app.body_text.yview()[0] - _y0H) < 0.02
      and app.body_text.index('probeH') == '2.3')
set_body('')

# Letters glued onto a coloured word wear its colours; after a space, not.
set_body('cuvant ')
_b = app.body_text
app._ensure_color_tag(_b, 'highlight', '#ffff00')
app._ensure_color_tag(_b, 'text_color', '#e63946')
_b.tag_add('highlight_ffff00', '1.0', '1.6')
_b.tag_add('text_color_e63946', '1.0', '1.6')
take_focus(_b)
_b.mark_set('insert', '1.6')
# Insert + KeyRelease, WITHOUT a synthetic KeyPress: with real focus
# on Windows the generated KeyPress itself types the character too
# (the class binding inserts), and the doubled letter becomes the
# untagged neighbour the handler then reads.
_b.insert('insert', 'X')
_b.event_generate('<KeyRelease>', keysym='X')
app.update()
_tagsXH = sorted(t for t in _b.tag_names('1.6')
                 if 'color' in t or 'highlight' in t)
_b.mark_set('insert', '1.end')
_b.insert('insert', ' Y')
_b.event_generate('<KeyRelease>', keysym='Y')
app.update()
_tagsYH = [t for t in _b.tag_names('1.end-1c')
           if 'color' in t or 'highlight' in t]
check('letters glued onto a coloured word inherit colour AND highlight',
      len(_tagsXH) == 2)
check('but a word started after a space stays plain', _tagsYH == [])
set_body('')

# ---- FIELD ROUND 4 ----
# The view restore after a grid rebuild stays IN FORCE: a late yank
# (the embedded windows' geometry settling) is corrected by the timers
# -- the old one-shot restore stayed scrolled away.
set_body(chr(10).join('| r%d | c%d |' % (i, i) for i in range(8))
         + chr(10) + ('text jos' + chr(10)) * 50)
app._render_table_grids()
app.update()
app._grid_view_restore = None
app.body_text.yview_moveto(0.5)
app.update()
_y0J = app.body_text.yview()[0]
_iJ = app._grid_at_line(1)
app._grid_set_alignment(_iJ, (1, 0, 1, 0), core_tables.ALIGN_CENTER)
app.update()
app.body_text.yview_moveto(0.0)      # yank-ul tarziu, simulat
_t_endJ = time.time() + 0.6
while time.time() < _t_endJ:
    app.update()
    time.sleep(0.02)
check('the grid-rebuild view restore outlives a late yank (in force, '
      'not one-shot)',
      abs(app.body_text.yview()[0] - _y0J) < 0.05)

# The scrollbar is a deliberate gesture: it cancels the pending restore.
_iJ = app._grid_at_line(1)
app._grid_set_alignment(_iJ, (2, 0, 2, 0), core_tables.ALIGN_CENTER)
app.update()
app._body_scrollbar_moved('moveto', '0.1')
_t_endJ = time.time() + 0.6
while time.time() < _t_endJ:
    app.update()
    time.sleep(0.02)
check('a deliberate scrollbar drag beats the pending restore',
      abs(app.body_text.yview()[0] - 0.1) < 0.08)
set_body('')

# Pipe text pasted mid-line lands on lines of its own.
set_body('inceput fig2')
app.body_text.mark_set('insert', '1.8')
app.clipboard_clear()
app.clipboard_append('| x | [x] |' + chr(10) + 'legenda')
app.update()
# Through _on_body_paste, the REAL route of a Ctrl+V -- a method called
# directly stays green even when its hook disappears (the "dead on
# arrival" lesson).
_stub_clipboard(html=None, text='| x | [x] |' + chr(10) + 'legenda')
_okJ = app._on_body_paste() == 'break'
app.update()
_linesJ = app.body_text.get('1.0', 'end-1c').split(chr(10))
check('pipe rows pasted mid-line land on their own lines, never '
      'spliced into the caret\'s line',
      _okJ and len(_linesJ) >= 3 and _linesJ[1] == '| x | [x] |'
      and '|fig2' not in app.body_text.get('1.0', 'end-1c'))
set_body('')

# ---- FIELD ROUND 5 ----
# The system-managed caption: numbered, centred, with its source line,
# the placeholder selected for immediate typing.
set_body('| a | b |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |')
app._render_table_grids()
app.update()
_iL = app._grid_at_line(1)
app._grid_set_table_align(_iL, 'center')
app.update()
_iL = app._grid_at_line(1)
# The field footage's precondition, simulated directly: the end of the
# table's last line wears a highlight -- the caption comes out CLEAN.
app._ensure_color_tag(app.body_text, 'highlight', '#c8b8a8')
app.body_text.tag_add('highlight_c8b8a8', '3.0', '4.0')
app._grid_add_caption(_iL)
app.update()
_linesL = app.body_text.get('1.0', 'end-1c').split(chr(10))
check('the caption and its source line both match the table '
      'placement, numbered, placeholder selected',
      _linesL[3] == 'Table 1: description'
      and _linesL[4].startswith('Source:')
      and 'align_center' in app.body_text.tag_names('4.2')
      and 'align_center' in app.body_text.tag_names('5.2')
      and bool(app.body_text.tag_ranges('sel')))
check('and the caption is scrubbed clean of inherited styling '
      '(no full-width bars)',
      not [t for t in app.body_text.tag_names('4.2')
           if t.startswith('highlight')]
      and not [t for t in app.body_text.tag_names('4.end')
               if t.startswith('highlight')]
      and not [t for t in app.body_text.tag_names('5.2')
               if t.startswith('highlight')])
app.body_text.insert('end', chr(10) + '| x | y |' + chr(10)
                     + '| --- | --- |' + chr(10) + '| 3 | 4 |')
app._resync_list_tags()
app._render_table_grids()
app.update()
_blkL = core_tables.find_blocks(app.body_text.get('1.0', 'end-1c'))
_iL2 = app._grid_at_line(_blkL[1][0] + 1)
app._grid_add_caption(_iL2)
app.update()
# The caption is body text: the toolbar's font and size apply to it
# per-selection, like any text, and reach the saved note.
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '4.0', '4.6')
app.update()
app._apply_body_font('font_family', 'Times New Roman')
app.body_text.tag_add('sel', '4.0', '4.6')
app.update()
app._apply_body_font('font_size', 16)
app.update()
_stF5 = app.capture_editor_state()
_capF5 = [sp for sp in _stF5['formatting']
          if sp['style'] in ('font_family', 'font_size')
          and sp['start'] < _stF5['body'].index('description')]
check('the caption takes a font family AND size like any body text',
      any(sp['style'] == 'font_family'
          and sp['value'] == 'Times New Roman' for sp in _capF5)
      and any(sp['style'] == 'font_size' and int(sp['value']) == 16
              for sp in _capF5))

check('a second caption counts on: Table 2',
      'Table 2: description' in app.body_text.get('1.0', 'end-1c'))
set_body('')

# Older notes carry captions with the labels from before the switch to
# English ("Tab. N: ..."); the numbering must count those TOO (otherwise
# a new caption in an old note restarts at 1), but NOT prose that merely
# starts with the word "Table".
set_body('Table of contents idea' + chr(10) + 'Tab. 3: old caption'
         + chr(10) + '| m | n |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 5 | 6 |')
app._render_table_grids()
app.update()
_blkO = core_tables.find_blocks(app.body_text.get('1.0', 'end-1c'))
app._grid_add_caption(app._grid_at_line(_blkO[0][0] + 1))
app.update()
check('numbering counts old-label captions but not prose starting '
      'with "Table"',
      'Table 2: description' in app.body_text.get('1.0', 'end-1c'))
set_body('')

# The table's placement travels with the cell copy.
set_body('| p | q |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |' + chr(10) + chr(10) + 'coada')
app._render_table_grids()
app.update()
_iL = app._grid_at_line(1)
app._grid_set_table_align(_iL, 'center')
app.update()
_iL = app._grid_at_line(1)
app._grid_select_range(_iL, (0, 0), (1, 1))
_stub_clipboard()   # read_text -> None; paste cade pe clipboardul Tk real
app._grid_copy_selection({'info': _iL, 'box': (0, 0, 1, 1)})
app._grid_clear_selection()
app.body_text.mark_set('insert', '6.0')
app.update()
app._paste_tsv_as_table()
app.update()
_blkL = core_tables.find_blocks(app.body_text.get('1.0', 'end-1c'))
check('a duplicated CENTRED table pastes back centred',
      len(_blkL) == 2
      and app._grid_table_align_of(_blkL[1][0] + 1) == 'center')
set_body('')

# THE WINDOWS ROUTE (round 6): our copy also puts HTML on the clipboard,
# and the rich-paste route saw that FIRST -- a copied table pasted back
# generically: no widths, no placement, and the first row landing at the
# tail of the source line ('Sursa: | fff |...' in the field report, from
# when the caption labels were Romanian). The loopback serves back
# exactly what was written, as the Windows clipboard does; our own copy
# must take the TSV route, with all its guards.
set_body('| a | b |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |' + chr(10) + 'Table 1: description' + chr(10)
         + 'Source: ')
app._render_table_grids()
app.update()
_iW = app._grid_at_line(1)
app._grid_select_range(_iW, (0, 0), (1, 1))
_stub_clipboard(loopback=True)
app._grid_copy_selection({'info': _iW, 'box': (0, 0, 1, 1)})
app._grid_clear_selection()
_lnW = app.body_text.get('1.0', 'end-1c').split(chr(10)).index('Source: ') + 1
app.body_text.mark_set('insert', '%d.end' % _lnW)
app.update()
app._on_body_paste()
app.update()
_bodyW = app.body_text.get('1.0', 'end-1c').split(chr(10))
check('our own table copy pastes below the Source line, not into it',
      _bodyW[_lnW - 1] == 'Source: '
      and len(core_tables.find_blocks(chr(10).join(_bodyW))) == 2)
_stub_clipboard()
set_body('')

# The HTML clipboard follows the file export's rules: a <th> header,
# real merges (not literal markers), a hidden column stays home, the
# checkbox leaves as a glyph. The TSV stays complete -- internal
# fidelity.
set_body('| h1 | h2 | h3 | h4 |' + chr(10)
         + '| --- | --- | --- | ~ |' + chr(10)
         + '| wide | < | [x] | secret |')
app._render_table_grids()
app.update()
_iV = app._grid_at_line(1)
app._grid_select_range(_iV, (0, 0), (1, 3))
_stub_clipboard()
app._grid_copy_selection({'info': _iV, 'box': (0, 0, 1, 3)})
_htmlV = _written.get('html') or ''
check('the cell copy HTML wears th, merges, hides and draws the box',
      '>h1</th>' in _htmlV and 'colspan="2"' in _htmlV
      and 'secret' not in _htmlV and 'h4' not in _htmlV
      and chr(0x2611) in _htmlV)
check('while the TSV keeps every column verbatim',
      'secret' in (_written.get('text') or '')
      and '[x]' in (_written.get('text') or ''))
# Without inline borders, Word painted the pasted table INVISIBLE --
# the selectable phantom from field report 8. The checkbox leaves
# centred, exactly as the app draws it.
check('the cell copy pastes with visible borders and a centred box',
      'border-collapse:collapse;' in _htmlV
      and 'border:1px solid #999;' in _htmlV
      and 'text-align:center;border:1px solid #999;' in _htmlV)
app._grid_clear_selection()
set_body('')

# Copying the table as TEXT (a body selection across the pipe lines)
# leaves with the inline borders too -- same road to Word, same
# phantom.
set_body('| c1 | c2 |' + chr(10) + '| --- | --- |' + chr(10)
         + '| v1 | v2 |')
app._render_table_grids()
app.update()
_stub_clipboard()
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.tag_add('sel', '1.0', '3.end')
app.update()
_rF8 = app._copy_formatted()
_htmlF8 = _written.get('html') or ''
check('a text-selection copy of a table carries inline borders too',
      _rF8 == 'break' and '<table' in _htmlF8
      and 'border:1px solid #999;' in _htmlF8)
app.body_text.tag_remove('sel', '1.0', 'end')
set_body('')

# The word count counts what the PERSON wrote, not the plumbing: every
# pipe used to count as "a word", an empty 3x3 table claimed twelve.
set_body('doua vorbe' + chr(10) + chr(10).join(core_tables.blank_table(3, 3)))
app._render_table_grids()
app.update()
app.update_word_count()
check('the word count sees the writing, not the table plumbing',
      app.word_count_lbl.cget('text').startswith('2 words'))
set_body('')

# Search likewise: "---" no longer catches every note holding a table,
# while cell content stays searchable.
app.new_note()
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'NotaTabelQ')
app.body_text.insert('1.0', '| gergebe | x |' + chr(10)
                     + '| --- | --- |' + chr(10) + '| a | b |')
app.save_current_note(auto=False)
app.update()
_idQ = app.selected_note_id
app.search_var.set('---')
app.refresh_note_list()
app.update()
_hitQ1 = _idQ in getattr(app, '_note_card_widgets', {})
app.search_var.set('gergebe')
app.refresh_note_list()
app.update()
_hitQ2 = _idQ in getattr(app, '_note_card_widgets', {})
app.search_var.set('')
app.refresh_note_list()
app.update()
check('search skips table plumbing but still finds cell content',
      not _hitQ1 and _hitQ2)

# ---- THE SEARCH BOX PASTES, AND CAN BE CLEARED (C-11) ----
# It was the only text field in the app with no right-click paste menu, and
# the only search box with no way to empty it but selecting and deleting.
# The checks above drive it through search_var, which steps over the widget;
# these go through the widget, because that is where both gaps were.
check('the search box has a right-click paste menu now',
      '<Button-3>' in app.search_entry.bind())
# The hint is wired to search_var like everything else in this box, so a
# paste onto it would land glued and then be SEARCHED FOR -- a query of
# "search notes...NotaTabelQ" matches nothing and reads as a broken search.
app.search_entry.delete(0, 'end')
app.search_entry.event_generate('<FocusOut>')
app.update()
check('fixture: the search box is showing its hint',
      app.search_entry.get() == NO.NoteOrganizer.SEARCH_PLACEHOLDER)
app.clipboard_clear(); app.clipboard_append('NotaTabelQ'); app.update()
app.search_entry.event_generate('<<Paste>>')
app.update()
check('pasting into the search box replaces the hint',
      app.search_entry.get() == 'NotaTabelQ')
app.refresh_note_list(); app.update()
check('and the list filters by what was pasted, not by the hint',
      _idQ in getattr(app, '_note_card_widgets', {}))

# The ✕. It appears only for a real query: always-there invites clearing an
# empty box, and beside the hint it suggests the hint is removable.
check('the ✕ is showing while a real query is in the box',
      app.search_clear_btn.winfo_ismapped())
app.search_clear_btn.invoke()
app.update()
check('pressing it empties the box', app.search_var.get() == '')
check('and takes the ✕ away with it',
      not app.search_clear_btn.winfo_ismapped())
check('and the full list is back at once, without waiting for the debounce',
      len(getattr(app, '_note_card_widgets', {})) == len(app.notes))
# The hint is not written back by the ✕ -- the box takes the focus instead,
# which is the state add_placeholder gives any box someone clicked into, and
# its own <FocusOut> restores the hint. One mechanism for the hint, not two.
app.search_entry.event_generate('<FocusOut>')
app.update()
check('looking away then restores the hint, through the app own route',
      app.search_entry.get() == NO.NoteOrganizer.SEARCH_PLACEHOLDER)
# THE CONTROL: the hint must not be readable as a query, or the list would
# come back empty at every launch. This is the judgement the three hardcoded
# copies of "search notes..." used to answer separately.
check('the hint is not a query', app._search_query() == '')
app.search_entry.delete(0, 'end')
app.search_var.set('')
app.refresh_note_list(); app.update()

# ---- A PASTED DATE IS SAVED (C-12) ----
# The date field autosaves on <KeyRelease>, and a paste fires none -- so the
# menu it now has would have handed back the silent loss the field's own
# comment says was fixed once for typing.
app.new_note(); app.update()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'PastedDate')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'x')
app.save_current_note(auto=False); app.update()
_idD = app.selected_note_id
check('the date field has a paste menu now',
      '<Button-3>' in app.date_entry.bind())
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '2020-01-01')
app.date_entry.config(fg='black')
app.update()
app._flush_autosave(); app.update()
check('fixture: the stored date is the old one',
      app.find_note(_idD).get('date') == '2020-01-01')
app._autosave_job = None
check('fixture: no autosave is pending before the date is pasted',
      not getattr(app, '_autosave_job', None))
app.clipboard_clear(); app.clipboard_append('2026-10-05'); app.update()
# Emptied first rather than selected-then-pasted. Tk's Entry paste deletes
# the selection only on NON-X11 -- on X11 it inserts at the caret and leaves
# the selected text where it is -- so a select_range here passed on Windows
# and failed on the Linux image with the field holding both dates. The app
# ships on Windows, so that difference is the test's problem and not the
# product's; the check is about the date reaching the store either way.
app.date_entry.delete(0, 'end')
app.date_entry.event_generate('<<Paste>>')
app.update()
check('the pasted date is in the field', app.date_entry.get() == '2026-10-05')
# THE REQUEST, not the result. The first version of this check called
# _flush_autosave() and then read the store -- and it survived the mutant that
# removed the paste binding entirely, because a forcing call saves whatever
# the editor holds whether anything asked it to or not. That is qa/README's
# own rule, made again here. What this asserts is that the PASTE queued a
# save, which is the thing the binding does.
check('pasting a date asks for a save, the way typing one does',
      bool(getattr(app, '_autosave_job', None)))
# And the outcome, through the app's own timer rather than a forced flush --
# waiting for the promised state, with a ceiling, so a slow machine is slow
# rather than red.
for _ in range(200):
    if app.find_note(_idD).get('date') == '2026-10-05':
        break
    app.update(); app.update_idletasks(); time.sleep(0.01)
check('and the note ends up with the date that was pasted',
      app.find_note(_idD).get('date') == '2026-10-05')

# A one-column table cannot exist as a row (is_table_row wants two
# cells) -- the insert raises it to two, else dead pipe text came out.
set_body('')
app._insert_table(2, 1)
app.update()
check('a one-column insert becomes a real two-column grid',
      len(app._table_grids) == 1 and app._table_grids[0]['ncols'] == 2)
if getattr(app, '_cell_editor', None):
    app._commit_cell_editor()
app.update()
set_body('')

# ---- UNDO x TABLES: one operation = one single Ctrl+Z ----
# A cell commit is a burst of small edits; without the undo unit, one
# Ctrl+Z stopped halfway -- the old value lost, the padding collapsed
# ('|  | 2 |' in the audit's probe).
set_body('| a | b |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |' + chr(10) + 'final')
app._render_table_grids()
app.update()
app.body_text.edit_reset()
_iU = app._grid_at_line(1)
app._open_cell_editor(_iU, 1, 0)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'unu-nou')
app._commit_cell_editor()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 1)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'doi-nou')
app._commit_cell_editor()
app.update()
_txtU0 = app.body_text.get('1.0', 'end-1c')
app._body_undo_redo('undo')
app.update()
_txtU1 = app.body_text.get('1.0', 'end-1c')
app._body_undo_redo('undo')
app.update()
_txtU2 = app.body_text.get('1.0', 'end-1c')
check('one Ctrl+Z takes back one whole cell edit',
      'unu-nou' in _txtU0 and 'doi-nou' in _txtU0
      and 'unu-nou' in _txtU1 and 'doi-nou' not in _txtU1)
check('the second Ctrl+Z takes back the edit before it, not the redraw',
      'unu-nou' not in _txtU2
      and '| 1 | 2 |' in _txtU2.split(chr(10))[2])
_iU2 = app._grid_at_line(1)
check('the drawn grid follows the undone text',
      _iU2 is not None and _iU2['cells'][(1, 0)]['value'] == '1')
app._body_undo_redo('redo')
app.update()
check('redo brings the edit and its drawing back',
      'unu-nou' in app.body_text.get('1.0', 'end-1c')
      and app._grid_at_line(1)['cells'][(1, 0)]['value'] == 'unu-nou')

# An inserted table leaves whole on a single undo, drawing included.
set_body('text sus')
app.update()
app.body_text.edit_reset()
app.body_text.mark_set('insert', 'end -1c')
app._insert_table(2, 3)
app.update()
if getattr(app, '_cell_editor', None):
    app._commit_cell_editor()
app.update()
check('the inserted table is there before the undo',
      len(app._table_grids) == 1)
app._body_undo_redo('undo')
app.update()
_txtU3 = app.body_text.get('1.0', 'end-1c')
check('one undo removes the whole inserted table, drawing included',
      '|' not in _txtU3 and len(app._table_grids) == 0
      and 'text sus' in _txtU3)
set_body('')

# ---- UNDO x LISTS/GRID: one operation = one Ctrl+Z, never an empty note ----
# The list ops rewrite the WHOLE body (delete all + reinsert to renumber);
# unbracketed, one Ctrl+Z undid the reinsert but not the delete and the
# note showed EMPTY (audit Z09-F01). And a numbered list ABOVE a table:
# the whole-body rewrite tore out the drawn grid and never redrew it, so
# the table dissolved into raw pipe rows (Z09-F00). And the grid trio
# (checkbox toggle, append rows/cols) lacked the undo unit (Z08-F01).

# Toggling a list on is ONE undo unit, and undo restores the text — not "".
set_body('alpha' + chr(10) + 'beta' + chr(10) + 'gamma')
app.update()
app.body_text.edit_reset()
app.body_text.tag_add('sel', '1.0', 'end-1c')
app._toggle_list('number')
app.update()
_listed = app.body_text.get('1.0', 'end-1c')
app._body_undo_redo('undo')
app.update()
_after = app.body_text.get('1.0', 'end-1c')
check('toggling a numbered list on is one Ctrl+Z, and undo is not empty',
      _listed.startswith('1. alpha') and _after == 'alpha' + chr(10)
      + 'beta' + chr(10) + 'gamma')

# Enter that ACTUALLY renumbers (a new item mid-list shifts the numbers
# below) rewrites the whole body — the path that tore the table out.
# Caret at end of item 1: the new item is 2, the old 2 becomes 3, so
# renumber genuinely rewrites (its no-change early-return does NOT fire).
set_body('1. one' + chr(10) + '2. two' + chr(10) + '| A | B |'
         + chr(10) + '| --- | --- |' + chr(10) + '| x | y |')
app._render_table_grids()
app.update()
app.body_text.edit_reset()
app.body_text.mark_set('insert', '1.end')
if take_focus(app.body_text):
    app._on_body_return(None)
    app.update()
    import time as _t1u
    _t1u.sleep(0.2)
    app.update()
_body_after = app.body_text.get('1.0', 'end-1c')
# Assert on the REAL embedded windows, not the _table_grids dict: the
# whole-body delete tears the windows out of the widget while the dict
# can keep a stale entry, so window_names() is what proves the grid is
# actually drawn (the dict count fooled the first cut of this check).
check('Enter that renumbers a list above a table keeps the table drawn',
      len(app.body_text.window_names()) == 1
      and len(core_tables.find_blocks(_body_after)) == 1)

# The whole-body renumber rewrite (delete-all + reinsert) on the key
# path is ONE undo unit: one Ctrl+Z after such an Enter must never leave
# the note EMPTY (the audit's Z09-F01 catastrophe). _on_body_return is
# not itself wrapped, so this exercises _renumber_lists' own atom.
set_body('1. one' + chr(10) + '2. two')
app.update()
app.body_text.edit_reset()
app.body_text.mark_set('insert', '1.end')
if take_focus(app.body_text):
    app._on_body_return(None)
    app.update()
app._body_undo_redo('undo')
app.update()
check('one Ctrl+Z after a renumbering Enter never empties the note',
      app.body_text.get('1.0', 'end-1c').strip() != '')

# The checkbox grid op is one undo unit: toggling a cell's checkbox and a
# single undo restores the prior marker, drawing intact.
set_body('| task | done |' + chr(10) + '| --- | --- |' + chr(10)
         + '| a | [ ] |')
app._render_table_grids()
app.update()
app.body_text.edit_reset()
_gi = app._grid_at_line(1)
app._grid_set_marker(_gi, 1, 1, '[x]')
app.update()
_checked = app.body_text.get('1.0', 'end-1c')
app._body_undo_redo('undo')
app.update()
_unchecked = app.body_text.get('1.0', 'end-1c')
check('a checkbox toggle is one Ctrl+Z that restores the prior state',
      '[x]' in _checked and '[x]' not in _unchecked
      and len(app._table_grids) == 1)
set_body('')

# ---- OLD TEETH, SHARPENED (the 2026-08-31 audit) ----
# 1. The 0.32.x editor guard (short content stays at the top) was pinned
# by nothing: removed, everything stayed green. winfo_height is stubbed
# huge so "it fits" holds regardless of the window and the platform's
# font -- the check aims at the PIN itself, deterministically.
_ecT = app.editor_canvas
_ecT.configure(scrollregion=(0, 0, 500, 5000))
_ecT.yview_moveto(0.3)
app.update()
_dispT = _ecT.canvasy(0)
_ecT.winfo_height = lambda: 10 ** 6
app._sync_editor_scroll()
del _ecT.winfo_height
app.update()
check('editor content that fits pins back to the top (the 0.32.x guard)',
      _dispT > 300 and _ecT.canvasy(0) == 0)

# 2. Autosave over a vanished note: the guard exists, but the mutant
# without it HUNG the suite in the modal dialog instead of failing a
# named check.
_errsT = []
_origErrT = app.show_error
app.show_error = lambda *a, **k: _errsT.append(a)
_savedSelT = app.selected_note_id
app.selected_note_id = 999999          # an id that does not exist
app._autosave_now()
app._flush_autosave()
app.show_error = _origErrT
app.selected_note_id = _savedSelT
check('autosave over a vanished note stays silent -- no Note missing dialog',
      _errsT == [])

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

# ---- APP-WIDE SHORTCUTS: Ctrl+N / Ctrl+S / Ctrl+F (bind_all) ----
# Verified through the real bindings on the app, not just the handlers.
check('Ctrl+N, Ctrl+S and Ctrl+F are bound app-wide',
      all(app.bind_all(c) for c in ('<Control-n>', '<Control-s>', '<Control-f>')))
_sc_groups = dict((g[0], [c for c, _d in g[1]]) for g in app.SHORTCUT_GROUPS)
check('the shortcuts reference lists them under an App group',
      _sc_groups.get('App') == ['Ctrl+N', 'Ctrl+S', 'Ctrl+F'])

# Ctrl+N: a fresh, unsaved note, through the real binding.
app.new_note()
app.title_entry.insert(0, 'BeforeCtrlN')
app.body_text.insert('1.0', 'body')
app.save_current_note(auto=False)
app.update()
take_focus(app.body_text)
app.body_text.event_generate('<Control-n>')
app.update()
check('Ctrl+N starts a new, unsaved note',
      app.selected_note_id is None
      and app.title_entry.get().strip() in ('', 'Note title...'))

# Ctrl+S: saves the note being edited.
app.new_note()
app.title_entry.insert(0, 'SavedByCtrlS')
app.body_text.insert('1.0', 'content here')
take_focus(app.body_text)
app.body_text.event_generate('<Control-s>')
app.update()
check('Ctrl+S saves the note being edited',
      any(n.get('title') == 'SavedByCtrlS' for n in app.notes))

# ...but a blank new note saves nothing, and pops no warning.
_warnedS = []
_origWS = app.show_warning
app.show_warning = lambda *a, **k: _warnedS.append(a)
app.new_note()
_nS = len(app.notes)
take_focus(app.body_text)
app.body_text.event_generate('<Control-s>')
app.update()
app.show_warning = _origWS
check('Ctrl+S on a blank note saves nothing and warns nothing',
      len(app.notes) == _nS and _warnedS == [])

# ---- FIND IN THE CURRENT NOTE (Ctrl+F) ----
# Covers BOTH prose and table cells, the in-window popup bar, reveal without
# flicker, and every seam the feature crosses (theme, save/dirty, edits,
# note switches). See _find_* in note_organizer.py.
def _frow(*cells):
    return '| ' + ' | '.join(cells) + ' |'
_FSEP = '| --- | --- |'
_FLB = core_tables.LINE_BREAK

# The real Ctrl+F binding switches to Notes, opens an in-window bar, and
# focuses its entry -- from anywhere in the app (here, the Calendar tab).
app.new_note()
app.notebook.select(app.TAB_CALENDAR)
app.update()
# Generate-and-poll: a synthetic key event on the toplevel can be
# DROPPED under full-suite load (the same physics as qa9's dropped
# clicks on unmapped popups) — retry until the promise lands, capped
# so a genuinely broken binding still fails red.
#
# The focus PROMISE is recorded, not polled — the same C11b lesson the
# table-insert check above carries, and this is the sibling it was never
# applied to. focus_settles_on reads a result the test process cannot
# demand: focus_get() needs the app to own the desktop foreground, which
# a test run never does, so it reports a false red about an app that
# placed the focus correctly. Wrapping focus_set captures the decision
# itself, synchronously, and cannot flake. Measured: focus_get() answers
# 100/100 when the window happens to hold the foreground and nothing at
# all when it does not, while the recorded call is always there.
_ff_focused = []
_ff_real_focus_set = tk.Misc.focus_set
tk.Misc.focus_set = (lambda self, *a, **k:
                     (_ff_focused.append(self),
                      _ff_real_focus_set(self, *a, **k))[1])
try:
    for _ in range(60):
        app.event_generate('<Control-f>')
        app.update()
        if app.notebook.index('current') == app.TAB_NOTES:
            break
        time.sleep(0.02)
finally:
    tk.Misc.focus_set = _ff_real_focus_set
check('Ctrl+F switches back to the Notes tab',
      app.notebook.index('current') == app.TAB_NOTES)
check('Ctrl+F opens the in-window find bar (a placed Frame, not a Toplevel)',
      app._find_open is True and app._find_bar is not None
      and app._find_bar.winfo_manager() == 'place'
      and isinstance(app._find_bar, tk.Frame))
check('Ctrl+F puts the focus in the find entry',
      app._find_entry in _ff_focused)
app._close_find()
app.update()
check('the X (close) hides the bar and drops the find tags',
      app._find_open is False
      and not app.body_text.tag_ranges('find_all'))

# Prose: nocase by default, navigation wraps, a miss reddens to 0/0.
app.new_note()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'alpha beta alpha gamma ALPHA')
app.update()
app._open_find()
app._find_var.set('alpha')
app._find_rescan(reveal=True)
app.update()
check('find/prose: nocase finds all three (incl ALPHA)',
      len(app._find_matches) == 3
      and all(x['kind'] == 'prose' for x in app._find_matches))
check('find/prose: the current match carries the find_current tag',
      bool(app.body_text.tag_ranges('find_current')))
app._find_nav(1); app._find_nav(1); app._find_nav(1)
app.update()
check('find/prose: Next wraps back to the first match', app._find_index == 0)
app._find_case.set(True)
app._find_rescan(reveal=False)
app.update()
check('find/prose: case-sensitive drops ALPHA -> two', len(app._find_matches) == 2)
app._find_case.set(False)
app._find_var.set('nowhere-zzz')
app._find_rescan(reveal=True)
app.update()
check('find/prose: a miss shows 0/0 and clears the highlight',
      app._find_count_lbl.cget('text') == '0/0'
      and not app.body_text.tag_ranges('find_all'))
app._close_find()
app.update()

# Table cells: header counts as data row 0, separator excluded; a <br>
# reads as a space; checkbox and merge cells are never words.
app.new_note()
set_body('\n'.join([
    _frow('Fruit', 'Note'),                 # data row 0
    _FSEP,                                   # separator (skipped)
    _frow('Milk', 'fresh today'),           # data row 1
    _frow('Bread%sloaf' % _FLB, 'plain'),   # data row 2: <br> in col 0
    _frow('[x]', 'done'),                    # data row 3: checkbox col 0
]))
app._render_table_grids()
app.update()
_finfo = app._grid_at_line(1)
check('find/cell: the grid rendered for the search table', _finfo is not None)
app._open_find()
app._find_var.set('fresh')
app._find_rescan(reveal=True)
app.update()
_fcm = [x for x in app._find_matches if x['kind'] == 'cell']
check('find/cell: a data cell match maps to (data-row 1, col 1)',
      len(_fcm) == 1 and _fcm
      and (_fcm[0]['row'], _fcm[0]['col']) == (1, 1)
      and (1, 1) in _finfo['cells'])
app._find_var.set('bread loaf')
app._find_rescan(reveal=True)
app.update()
_fcm = [x for x in app._find_matches if x['kind'] == 'cell']
check('find/cell: a <br> reads as a space ("bread loaf" hits row2 col0)',
      len(_fcm) == 1 and _fcm and (_fcm[0]['row'], _fcm[0]['col']) == (2, 0))
app._find_var.set('[x]')
app._find_rescan(reveal=True)
app.update()
check('find/cell: a checkbox cell is never a match',
      not any(x['kind'] == 'cell' for x in app._find_matches))
app._close_find()
app.update()

# One matching cell = one stop even if the needle repeats inside it.
app.new_note()
set_body('\n'.join([_frow('X', 'Y'), _FSEP, _frow('foo foo foo', 'bar')]))
app._render_table_grids()
app.update()
app._open_find()
app._find_var.set('foo')
app._find_rescan(reveal=True)
app.update()
check('find/cell: a repeated needle in one cell counts as a single stop',
      len([x for x in app._find_matches if x['kind'] == 'cell']) == 1)
app._close_find()
app.update()

# Reveal: a match 40+ lines down scrolls the body's own inner viewport.
app.new_note()
_ffill = '\n'.join('line %d' % i for i in range(40))
set_body(_ffill + '\n' + '\n'.join(
    [_frow('NeedleCell', 'Z'), _FSEP, _frow('target', 'v')]))
app._render_table_grids()
app.update()
app.body_text.yview_moveto(0.0)
app.update()
app._open_find()
app._find_var.set('target')
app._find_rescan(reveal=True)
app.update(); app.update_idletasks()
check('find/reveal: revealing a far cell scrolls the body viewport to it',
      app.body_text.yview()[0] > 0.0
      and any(x['kind'] == 'cell' for x in app._find_matches))
app._close_find()
app.update()

# The feature is read-only: it never dirties the note nor serializes a tag.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'FindClean')
app.title_entry.config(fg=app.colors['text'])
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'needle here and needle there')
app.save_current_note(auto=False)
app.update()
app._open_find()
app._find_var.set('needle')
app._find_rescan(reveal=True)
app.update()
app._find_nav(1)
app.update()
_ffmt = {f.get('style') for f in app._extract_formatting(app.body_text)}
check('find: its tags never leak into the serialized formatting',
      'find_all' not in _ffmt and 'find_current' not in _ffmt)
check('find: an open search leaves the note clean (no phantom edit)',
      app.editor_state_matches_saved(app.capture_editor_state()))
app._close_find()
app.update()

# Editing while the bar is open: the model goes stale, nav is gated until a
# debounced rescan, and the rescan does NOT twitch the view.
app.new_note()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'cat cat cat')
app.update()
app._open_find()
app._find_var.set('cat')
app._find_rescan(reveal=True)
app.update()
app.body_text.insert('end', ' cat')
app._find_on_body_edit()
_fidx = app._find_index
app._find_nav(1)
check('find/edit: an edit marks the model dirty and gates navigation',
      app._find_model_dirty is True and app._find_index == _fidx)
for _ in range(60):
    app.update(); app.update_idletasks(); time.sleep(0.01)
    if not app._find_model_dirty:
        break
check('find/edit: the debounced rescan clears dirty and re-counts (4)',
      app._find_model_dirty is False and len(app._find_matches) == 4)
app._close_find()
app.update()

# Theme switch with the bar open on a CELL match: survives, and the find
# highlight follows the new palette (the theme x tables seam).
app.new_note()
set_body('\n'.join([_frow('Col', 'Val'), _FSEP, _frow('phantom', 'x')]))
app._render_table_grids()
app.update()
app._open_find()
app._find_var.set('phantom')
app._find_rescan(reveal=True)
app.update()
_fother = [t for t in NO.THEMES if t != app.theme_name]
if _fother:
    app.set_theme(_fother[0])
app.update(); app.update_idletasks()
check('find/theme: a theme switch keeps the open cell search alive',
      app._find_open is True
      and len([x for x in app._find_matches if x['kind'] == 'cell']) == 1)
check('find/theme: the find highlight is re-tinted to the new accent',
      app.body_text.tag_cget('find_current', 'background').lower()
      == app.colors['accent'].lower())
# The "Aa" case checkbox is long-lived (built once with the bar); its
# selectcolor -- the box's own fill -- must follow the theme too, or a
# switch leaves a stuck box you can't read as checked.
#
# It used to be asked for the SIDEBAR colour by name, which made this
# check agree with the defect beside it: a well the same value as the
# surface behind it passed happily, and on every dark theme a ticked box
# therefore looked exactly like an empty one. The well has its own
# palette entry now, so the question is the one that was always meant --
# is it still the palette's, and is it still not the surface it sits on?
check('find/theme: the case checkbox well follows the theme and stays readable',
      str(app._find_case_cb.cget('selectcolor')).lower()
      == app.colors['check_well'].lower()
      and str(app._find_case_cb.cget('selectcolor')).lower()
      != str(app._find_case_cb.cget('bg')).lower())
# The bar's accent-coloured border is likewise long-lived; changing the
# accent while the bar is open must recolour it, not leave the old accent
# framing the bar.
check('find/theme: the bar border follows the accent',
      str(app._find_bar.cget('highlightbackground')).lower()
      == app.colors['accent'].lower())
app._close_find()
app.update()

# Switching notes clears the model so no navigation runs on stale indices.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'FindA')
app.title_entry.config(fg=app.colors['text'])
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'switchword switchword')
app.save_current_note(auto=False)
app.update()
app._open_find()
app._find_var.set('switchword')
app._find_rescan(reveal=True)
app.update()
_fbefore = len(app._find_matches)
app.new_note()  # fires _find_on_context_switch
app.update()
check('find/switch: opening another note clears the match model',
      _fbefore == 2 and len(app._find_matches) == 0 and app._find_index == -1)
check('find/switch: no stale find highlight survives the switch',
      not app.body_text.tag_ranges('find_all'))
app._close_find()
app.update()

# ---- LIFT #2: cell styling, raw-row Tab, category dropdown, share panel ----

# Bold/italic INSIDE the cell editor (_editor_apply_style's chars walk).
set_body('| stilcel | b |\n| c | d |')
app._render_table_grids(); app.update()
_t2 = app._grid_at_line(1)
app._open_cell_editor(_t2, 0, 0)
_ed2 = app._cell_editor['entry']
_ed2.tag_remove('sel', '1.0', 'end')  # open() pre-selects everything
_ed2.tag_add('sel', '1.0', '1.4')
app._editor_apply_style('bold')
app.update()
check('cell-editor bold tags exactly the selected characters',
      any('bold' in _ed2.tag_names(f'1.{i}') for i in range(4))
      and not any('bold' in t for t in _ed2.tag_names('1.5')))
app._editor_apply_style('bold')
app.update()
check('a second toggle takes the bold off again',
      not any('bold' in _ed2.tag_names(f'1.{i}') for i in range(4)))
app._commit_cell_editor(); app.update()

# Tab through a RAW (never-rendered) pipe row: the un-rendered branch of
# _tab_in_table walks cell to cell without a grid.
set_body('| unu | doi | trei |')
app.body_text.mark_set('insert', '1.3')
_moved = app._tab_in_table(1)
app.update()
check('Tab advances the caret to the next raw cell and selects it',
      _moved and app.body_text.get('sel.first', 'sel.last') == 'doi')
_moved = app._tab_in_table(-1)
app.update()
check('Shift-Tab walks back to the first cell',
      _moved and app.body_text.get('sel.first', 'sel.last') == 'unu')

# The editor's category dropdown: open it, pick a category by row.
app.new_note(); app.update()
NO.CATEGORY_COLORS.setdefault('Work', '#3b82f6')
app._open_category_dropdown()
app.update()
_cat_pop = app._mini_popup
_rows_cat = [l for l in _walk_widgets(_cat_pop, tk.Label)
             if str(l.cget('text')) == 'Work']
check('the category dropdown lists Work', len(_rows_cat) >= 1)
_qa_click(_rows_cat[0])
app.update()
check('picking a row sets the editor category',
      app.category_var.get() == 'Work')

# The inline share panel: code box + the attachments warning.
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'DeShare')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'ceva')
app.save_current_note(auto=False); app.update()
app.current_attachments = [{'filename': 'f.txt', 'stored_as': 'x_f.txt'}]
app.share_current_note_as_code()
app.update()
_share_texts = [str(w.get('1.0', 'end-1c'))
                for w in _walk_widgets(app.editor_code_area, tk.Text)]
_share_lbls = [str(l.cget('text'))
               for l in _walk_widgets(app.editor_code_area, tk.Label)]
check('the inline share panel shows a real NOTE1 code',
      any(t.startswith('NOTE1:') for t in _share_texts))
check('and warns that attachments are not included',
      any("Attachments aren't included" in t for t in _share_lbls))
_decoded_share = NO.decode_share_code(
    next(t for t in _share_texts if t.startswith('NOTE1:')))
check('the shown code round-trips to the note',
      _decoded_share and _decoded_share[0].get('title') == 'DeShare')

# ---- ONE SENTENCE, AND AN ✕ ON BOTH CODE AREAS (C-24) ----
# Two surfaces generate a share code, and they warned about attachments in
# two different sentences for one fact -- "Attachments not included" in the
# sidebar, "Attachments aren't included in a code" in the editor. The
# editor's is the one kept: it names WHICH mechanism leaves them out, which
# is what tells a reader Export does include them. Asserted against the
# constant rather than a copy of the string, so a reworded sentence moves
# both places or fails here.
check('the editor code area uses the shared attachments sentence',
      any(t == NO.NoteOrganizer.SHARE_ATTACHMENT_WARNING for t in _share_lbls))
# The editor area could always be dismissed; the sidebar's could not, except
# by closing the whole Share panel.
_editor_closers = [b for b in _walk_widgets(app.editor_code_area, tk.Button)
                   if str(b.cget('text')) == '✕']
check('the editor code area has its ✕', len(_editor_closers) == 1)

app.toggle_share_panel(); app.update()
_first_id = app.notes[0]['id']
app._share_vars[_first_id] = tk.BooleanVar(value=True)
app.notes[0]['attachments'] = [{'filename': 'f.txt', 'stored_as': 'x_f.txt'}]
app._generate_inline_share(); app.update()
_side_lbls = [str(l.cget('text'))
              for l in _walk_widgets(app.share_code_area, tk.Label)]
_side_texts = [str(w.get('1.0', 'end-1c'))
               for w in _walk_widgets(app.share_code_area, tk.Text)]
check('fixture: the sidebar really generated a code',
      any(t.startswith('NOTE1:') for t in _side_texts))
check('and the sidebar uses the SAME sentence as the editor',
      any(t == NO.NoteOrganizer.SHARE_ATTACHMENT_WARNING for t in _side_lbls))
_side_closers = [b for b in _walk_widgets(app.share_code_area, tk.Button)
                 if str(b.cget('text')) == '✕']
check('the sidebar code area now has an ✕ too', len(_side_closers) == 1)
# It clears the area's children rather than pack_forget()ing the frame: that
# frame is packed once when the panel is built and is part of its layout, so
# forgetting it would take the panel's own space with it.
if _side_closers:
    # invoke(), the suite's idiom for a real tk.Button: a generated click
    # depends on the widget being viewable and this one is a few pixels wide
    # in a sidebar. The ✕ being ON SCREEN is asserted separately above; what
    # this presses is its command.
    # invoke(), not a generated click: _qa_click fires <Button-1>, and a
    # tk.Button runs its command from <ButtonRelease-1> -- which is why this
    # file presses buttons with invoke() everywhere else. Measured while
    # writing this check: neither a bare release nor a generated
    # press+release reaches it either. The ✕ being ON SCREEN is asserted
    # separately above; this presses its command.
    _side_closers[0].invoke()
    # The clear is deferred (the ✕ sits inside the frame it empties), so the
    # idle queue has to run before the result can be read.
    app.update_idletasks(); app.update()
    check('and pressing it clears the code away',
          not [w for w in _walk_widgets(app.share_code_area, tk.Text)])
    check('while the area itself stays in the panel',
          app.share_code_area.winfo_ismapped())
app.notes[0].pop('attachments', None)
app.toggle_share_panel(); app.update()

app.current_attachments = []
app.update()

# ---- THE PICKERS (coverage-lift C14) ----
# The date, colour, emoji, template and table-size pickers were never
# opened by any script — the date picker alone was a 64-line hole.
# Each: open through the real entry point, choose through the real
# widget, assert the choice LANDED where the user would see it.

# Date picker: pick day 15, the entry gets the date; ▶ shifts the month.
app.new_note(); app.update()
app.open_date_picker()
app.update()
_dp = app._mini_popup
_day_btns = [b for b in _walk_widgets(_dp, tk.Button)
             if str(b.cget('text')).strip() == '15']
check('the date picker opens with a clickable day grid',
      _dp is not None and len(_day_btns) == 1)
_next = [b for b in _walk_widgets(_dp, tk.Button)
         if str(b.cget('text')) == '▶']
_month_lbls = [l for l in _walk_widgets(_dp, tk.Label)
               if any(m in str(l.cget('text')) for m in
                      ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul',
                       'Aug', 'Sep', 'Oct', 'Nov', 'Dec'))]
_before_month = str(_month_lbls[0].cget('text')) if _month_lbls else ''
if _next:
    _next[0].invoke(); app.update()
check('the ▶ arrow moves the picker one month',
      _month_lbls and str(_month_lbls[0].cget('text')) != _before_month)
_day_btns = [b for b in _walk_widgets(_dp, tk.Button)
             if str(b.cget('text')).strip() == '15']
_day_btns[0].invoke()
app.update()
check('picking a day writes the date into the date field',
      app.date_entry.get().endswith('-15')
      and app._mini_popup is not _dp)

# Note colour picker: a canvas swatch click colours the open note.
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Colorata')
app.title_entry.config(fg='black')
app.save_current_note(auto=False); app.update()
app.open_color_picker()
app.update()
# The NOTE palette is Buttons wearing their colour as bg (the day
# palette uses drawn canvases — different builder, same idea).
_swatches = [b for b in _walk_widgets(app._mini_popup, tk.Button)
             if str(b.cget('bg')).startswith('#')]
check('the note colour palette offers swatches', len(_swatches) >= 5)
_pick_col = str(_swatches[1].cget('bg'))
_swatches[1].invoke()
app.update()
app.save_current_note(auto=False)
app.update()
_colored = app.find_note(app.selected_note_id)
check('a swatch click colours the note itself',
      app.current_note_color == _pick_col
      and _colored.get('color') == _pick_col)

# Emoji picker: the first chip lands in the body at the caret.
set_body('')
app._show_emoji_picker(app.body_text)
app.update()
_chips = [l for l in _walk_widgets(app._mini_popup, tk.Label)
          if str(l.cget('cursor')) == 'hand2'
          and len(str(l.cget('text'))) <= 3
          and str(l.cget('text')).strip()]
check('the emoji picker offers chips', len(_chips) >= 8)
_first_emoji = str(_chips[0].cget('text')).strip()
_qa_click(_chips[0])
app.update()
check('a chip click inserts that emoji into the body',
      _first_emoji in app.body_text.get('1.0', 'end-1c'))
app._dismiss_mini_popup(); app.update()

# Template picker: choosing the seeded template fills the editor.
app.templates.append(NO.normalize_template(
    {'name': 'PickerTpl', 'title': 'Din sablon', 'body': 'corp de sablon'}))
NO.save_templates(app.templates)
app.new_note(); app.update()
app.show_template_picker()
app.update()
_tpl_btns = [w for w in
             _walk_widgets(app._mini_popup, (tk.Button, tk.Label))
             if 'PickerTpl' in str(w.cget('text'))]
check('the template picker lists the template', len(_tpl_btns) >= 1)
_w = _tpl_btns[0]
if isinstance(_w, tk.Button):
    _w.invoke()
else:
    _qa_click(_w)
app.update()
check('choosing it fills the editor from the template',
      app.title_entry.get() == 'Din sablon'
      and app.body_text.get('1.0', 'end-1c').startswith('corp de sablon'))

# Table-size popup: clicking a size cell inserts a real drawn table.
set_body('')
app._open_table_size_popup()
app.update()
_size_pop = [w for w in app.winfo_children()
             if isinstance(w, tk.Toplevel) and w.winfo_exists()]
check('the insert-table popup opens', bool(_size_pop))
_cells14 = []
for topl in _size_pop:
    _cells14 += [c for c in _walk_widgets(topl, (tk.Frame, tk.Label))
                 if str(c.cget('cursor')) == 'hand2']
picked = False
for c in _cells14:
    _qa_fire(c, '<Enter>')
    _qa_click(c)
    app.update()
    if core_tables.find_blocks(body()):
        picked = True
        break
check('clicking a size cell inserts a drawn table',
      picked and len(app.body_text.window_names()) >= 1)
for topl in _size_pop:
    if topl.winfo_exists():
        topl.destroy()
app.update()

# ---- The helper's own repair, witnessed ----
# _qa_fire asks winfo_id() (Tk_MakeWindowExist) before aiming an event,
# because Tk DISCARDS a generated pointer event at a widget with no
# native window -- silently, which is what made a whole class of checks
# answer by luck. Delete that one line and every suite stays green,
# because every other site happens to run against mapped widgets: the
# repair was load-bearing and guarded by nothing. This builds the case
# it exists for.
_fw_top = tk.Toplevel(app)
_fw_top.wm_overrideredirect(True)
_fw_top.wm_geometry('+50+50')
_fw_raw = tk.Label(_fw_top, text='raw', bg='#ff0000', cursor='hand2')
_fw_raw.pack()
_fw_fired = tk.Label(_fw_top, text='fired', bg='#00ff00', cursor='hand2')
_fw_fired.pack()
_fw_hits = []
_fw_raw.bind('<Button-1>', lambda e: _fw_hits.append('raw'))
_fw_fired.bind('<Button-1>', lambda e: _fw_hits.append('fired'))
# NO update() anywhere in this block, in either direction: Tk dispatches
# a generated event immediately, so the bindings record without one --
# and a single update() here would MAP the toplevel, leaving the helper
# nothing to repair and the second check passing with the repair deleted.
_fw_raw.event_generate('<Button-1>')
_qa_fire(_fw_fired, '<Button-1>')
check('a raw generated click at a windowless widget is DISCARDED',
      'raw' not in _fw_hits)
check('...while the helper delivers it, which is the whole repair',
      'fired' in _fw_hits)
_fw_top.destroy()
app.update()

# ---- "Save as template" asks a question that matches what it stores ----
# The eighth hand-rolled emptiness gate: it enumerated title|body|comments
# and refused a checklist-only note with "This note is empty" -- about a
# note the app had just saved, and whose template WOULD have carried the
# checklist (do_save stores it). Deliberately narrower than the shared
# predicate, because a template carries nothing else: an attachment or a
# repeat rule alone really would make an empty template.
_tpl_before = len(app.templates)
app.open_blank_tab(); app.update()
app._working_checklist = [{'text': 'to buy', 'done': False}]
app.update()
_tpl_said = []
_real_info_tpl = app.show_info
app.show_info = lambda t, m, **k: (_tpl_said.append((t, m)), True)[1]
_real_ask_tpl = app.ask_text if hasattr(app, 'ask_text') else None
try:
    app.save_current_as_template()
    app.update()
finally:
    app.show_info = _real_info_tpl
check('a checklist-only note is not called empty by Save-as-template',
      not any('empty' in m.lower() for _t, m in _tpl_said))
# The behaviour, not the wording: the mutated gate refuses with a message
# that also lacks the word "empty", so the check above alone passed while
# the bug was live. What matters is whether the editor was ALLOWED to
# become a template at all.
check('...and it is actually offered as one (the gate let it through)',
      _tpl_said == [])

# And the teeth stay: an editor holding ONLY an attachment really would
# make an empty template, so that one is still refused -- with a message
# that says what a template keeps.
app.open_blank_tab(); app.update()
app.current_attachments = [{'filename': 'x.pdf', 'stored_as': 'x.pdf'}]
app.update()
_tpl_said2 = []
app.show_info = lambda t, m, **k: (_tpl_said2.append((t, m)), True)[1]
try:
    app.save_current_as_template()
    app.update()
finally:
    app.show_info = _real_info_tpl
check('an attachment-only editor is still refused as a template',
      len(_tpl_said2) == 1)
check('...and told what a template actually keeps',
      _tpl_said2 and 'checklist' in _tpl_said2[0][1]
      and 'this note is empty' not in _tpl_said2[0][1].lower())
app.current_attachments = []
app.templates = app.templates[:_tpl_before]
app.open_blank_tab(); app.update()

# ---- A note ending in a table is not permanently "unsaved" ----
# The editor always draws a line under a trailing table (the caret needs
# somewhere to live), so the body as SHOWN carries one newline the body
# as typed does not. While every save ran .strip() that difference was
# invisible; storing the body exactly as typed (T0-4) surfaced it, and
# every table-ending note then read as changed forever: an autosave
# rewrite on every note switch, a dirty dot that lied, and a recurring
# note asking its save-scope question unprompted.
# The render is the FEATURE here -- these checks pin the reconciliation
# on the other side, and the last one pins the feature itself so a
# future "fix" cannot quietly delete the caret line instead.
_TBL_Q = '| a | b |\n| --- | --- |\n| 1 | 2 |'

app.open_blank_tab(); app.update()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'TabelLaFinal')
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'intro\n' + _TBL_Q)
app.update()
app.save_current_note(auto=False); app.update()
_tq_id = app.selected_note_id
app.open_note_in_tab(app.find_note(_tq_id)); app.update()
_tq_st = app.capture_editor_state()
check('a note ending in a table reads as SAVED after a reopen',
      app.editor_state_matches_saved(_tq_st))
check('...because stored and shown agree exactly',
      app.find_note(_tq_id)['body'] == _tq_st['body'])
# Idempotent: drawing it again must not grow another line.
app.open_note_in_tab(app.find_note(_tq_id)); app.update()
check('...and reopening again neither dirties it nor grows the body',
      app.editor_state_matches_saved(app.capture_editor_state())
      and app.find_note(_tq_id)['body'].count('\n')
      == ('intro\n' + _TBL_Q + '\n').count('\n'))

# A note stored by an OLDER version (no caret line) heals on LOAD, with
# no rewrite: it must read clean the first time it is opened.
_legacy_tq = NO.normalize_note(
    {'id': 4242, 'title': 'Legacy', 'body': 'intro\n' + _TBL_Q,
     'category': 'General', 'updated': '2026-01-01 00:00',
     'created': '2026-01-01 00:00'})
check('a table-ending note from an older version is canonical on load',
      _legacy_tq['body'] == 'intro\n' + _TBL_Q + '\n')
app.notes.append(_legacy_tq)
app.save_notes()
app.open_note_in_tab(app.find_note(4242)); app.update()
check('...and opens clean, with no silent rewrite behind the user',
      app.editor_state_matches_saved(app.capture_editor_state()))

# The feature the reconciliation exists to serve: the caret CAN go below
# the table. Assert the line is really there in the widget.
_tq_lines = app.body_text.get('1.0', 'end-1c').split('\n')
# Indexed defensively: with the caret line gone there may be no [-2] at
# all, and an IndexError here would take the run down before its
# FAILURES footer -- a mutant that crashes reads as "survived nothing".
check('the editor still draws a line under the trailing table',
      len(_tq_lines) >= 2 and _tq_lines[-1] == ''
      and NO.is_table_row(_tq_lines[-2]))

# BEFORE any render, the widget genuinely lacks the caret line -- which
# is the only moment the canonicalisation at the save and capture read
# points does any work. Every case above runs after a render, where the
# widget already holds it, so without these two the mechanism at those
# points was asserted by nothing.
app.open_blank_tab(); app.update()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Nerandat')
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'intro\n' + _TBL_Q)   # no update(): no render
check('the widget itself has no caret line yet (the precondition)',
      app.body_text.get('1.0', 'end-1c') == 'intro\n' + _TBL_Q)
check('capture canonicalises a body read before the render',
      app.capture_editor_state()['body'] == 'intro\n' + _TBL_Q + '\n')
app.save_current_note(auto=False)
_pre_id = app.selected_note_id
check('and the save stores the canonical form, not the short one',
      app.find_note(_pre_id)['body'] == 'intro\n' + _TBL_Q + '\n')
# The same, on the EXISTING-note branch -- which is where the save's own
# canonicalisation actually earns its keep: a new note is built through
# normalize_note (which canonicalises anyway), while an update writes
# note['body'] straight onto the dict.
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'alt intro\n' + _TBL_Q)   # again: no render
check('an existing note also has the short body in the widget',
      app.body_text.get('1.0', 'end-1c') == 'alt intro\n' + _TBL_Q)
app.save_current_note(auto=False)
check('...and updating it stores the canonical form too',
      app.find_note(_pre_id)['body'] == 'alt intro\n' + _TBL_Q + '\n')
app.notes = [n for n in app.notes if n.get('id') != _pre_id]
app.save_notes()

check('with_caret_line adds the line exactly once, and is idempotent',
      NO.with_caret_line(_TBL_Q) == _TBL_Q + '\n'
      and NO.with_caret_line(NO.with_caret_line(_TBL_Q)) == _TBL_Q + '\n')

# And a body that does NOT end in a table is untouched by any of this.
check('with_caret_line leaves every other body exactly alone',
      NO.with_caret_line('abc') == 'abc'
      and NO.with_caret_line('') == ''
      and NO.with_caret_line(_TBL_Q + '\nafter') == _TBL_Q + '\nafter'
      and NO.with_caret_line(_TBL_Q + '\n') == _TBL_Q + '\n')
for _nm in (_tq_id, 4242):
    app.notes = [n for n in app.notes if n.get('id') != _nm]
app.save_notes()
app.open_blank_tab(); app.update()

# ---- Closing an abandoned "+ note for this day" leaves no junk ----
# The calendar's add-note-for-a-day flow PREFILLS the date, so a day
# clicked and then thought better of leaves an editor holding nothing
# but a date. The junk-note guard counted the date as content on every
# route -- including this close sweep, which saves with auto=True -- so
# the abandoned click was persisted as a blank dated note. The date is
# deliberate only when the user presses Save; the automatic routes agree
# with _editor_state_has_content, which leaves it out.
app.notes = []
app.save_notes()
app.open_blank_tab(); app.update()
app.date_entry.delete(0, 'end')
app.date_entry.insert(0, '2030-05-05')
app.update()
_jd_before = len(app.notes)
# The timer and the flush both stop earlier than the guard under test:
# their shared content gate already excludes the date, so neither ever
# reaches save_current_note. The route that DOES is the window-close
# sweep, which calls save_current_note(auto=True) for every tab that
# reads dirty -- and a date-only editor reads dirty by design, so the
# date must not count as content THERE.
app._flush_autosave(); app._autosave_now(); app.update()
check('neither the timer nor the flush touches an abandoned day-click',
      len(app.notes) == _jd_before)
app.save_current_note(auto=True)   # exactly what on_app_close does
app.update()
check('an abandoned day-click is not autosaved as a junk note',
      len(app.notes) == _jd_before)
# ...but pressing Save on it IS deliberate: a bare dated reminder is a
# real thing a person can want, and the explicit gesture is what says so.
app.save_current_note(auto=False)
app.update()
check('while pressing Save on the same editor does create the reminder',
      len(app.notes) == _jd_before + 1
      and app.notes[-1].get('date') == '2030-05-05')
app.notes = []
app.save_notes()
app.open_blank_tab(); app.update()

# ---- SELECT ALL, THEN TYPE, OVER A NOTE THAT HOLDS A TABLE ----
# Coverage-ledger C10: the caret guard's MECHANISM around tables is
# covered several times above, but this particular gesture had never been
# executed -- and it is the one that replaces a table with a single
# character in one stroke, which is the most violent thing a keystroke
# can do to the body.
#
# Driven through the VIRTUAL event rather than a literal Ctrl+A on
# purpose: Tk maps <<SelectAll>> to Ctrl+A on Windows and to Ctrl+/ on
# X11, so a check written to the Windows keystroke would go red on the
# Linux CI leg for a reason that has nothing to do with the app.
app.new_note()
app.update()
app.body_text.insert('1.0', 'Above the table\n')
app._insert_table(2, 2)
app.update()
app.body_text.insert('end-1c', '\nBelow the table')
app.update()
_sa_before = app.body_text.get('1.0', 'end-1c')
check('the fixture really holds a table to type over',
      any(core_tables.is_table_row(ln) for ln in _sa_before.split('\n'))
      and len(getattr(app, '_table_grids', [])) >= 1)

take_focus(app.body_text)
app.body_text.event_generate('<<SelectAll>>')
app.update()
_sa_sel = app.body_text.tag_ranges('sel')
# Tk's select-all runs to "end", which is one character past the last --
# so the selected text is the body plus its trailing newline. Asserted as
# a span rather than as string equality, because equality here was the
# first version of this check and it went red for that reason alone.
check('select-all really takes the whole note, table and all',
      len(_sa_sel) == 2 and str(_sa_sel[0]) == '1.0'
      and app.body_text.compare(str(_sa_sel[1]), '>=', 'end-1c')
      and _sa_before in app.body_text.get(str(_sa_sel[0]), str(_sa_sel[1])))

app.body_text.event_generate('<KeyPress>', keysym='x')
app.update()
_sa_after = app.body_text.get('1.0', 'end-1c')
check('typing over it leaves what was typed, not a half-eaten table',
      _sa_after.startswith('x'))
check('...and not one table row survives',
      not any(core_tables.is_table_row(ln) for ln in _sa_after.split('\n')))
# The grids are real child widgets laid INTO the text as embedded
# windows. Asked of the text widget, not of the app's own bookkeeping:
# `_table_grids` still holds one dead entry here (its frame is already
# destroyed, and the next render rebuilds the list), and asserting on
# that list was this check's other first-version mistake -- it would have
# reported a leak the user cannot see, while saying nothing about the one
# they could.
check('...and nothing is left drawn over the text where the table was',
      app.body_text.window_names() == ())
# Caret sanity, which is what the ledger row actually asked for: the
# insert mark must still resolve, and inside the text that is left.
_sa_insert = app.body_text.index('insert')
check('...and the caret is still somewhere real in what remains',
      app.body_text.compare(_sa_insert, '<=', 'end-1c')
      and app.body_text.compare(_sa_insert, '>=', '1.0'))
# It must also survive the round trip: a note whose table was typed over
# is saved as plain text, and comes back as plain text.
#
# Asserted as an EQUALITY against the whole stored body, and only after
# the save is proven to have happened. The first version of this check
# asked "does the saved body contain no table row" of `app.notes[-1]`
# with an autosave that never fired -- so it read an empty dict, found no
# table in nothing, and passed. A mutant that stored a ghost table row
# walked straight through it.
# Proved by IDENTITY, not by the count going up. Counting assumed the
# explicit save must CREATE the note, which is true only while the 500ms
# autosave has not got there first -- and on a loaded machine it does.
# The save then UPDATES instead, the count never moves, and the check
# goes red about an app that saved correctly. CI found it; reproduced
# here by pausing long enough for the timer to fire, which is all a
# loaded runner does.
#
# The original point stands and is kept: the first version read
# app.notes[-1] with an autosave that never fired, found no table in an
# empty dict and passed vacuously. Asking for the note the editor points
# at still fails outright when nothing was saved -- find_note(None)
# answers None.
app.save_current_note(auto=False)
app.update()
_sa_saved = app.find_note(app.selected_note_id)
check('...the overtyped note really was saved', _sa_saved is not None)
# The guard above is only worth having while an unsaved editor really
# does find nothing, so that is pinned rather than assumed. It has no
# mutant of its own: every way of stopping the save outright kills qa1 at
# its first save, two seconds in, long before this line runs -- so the
# behaviour claim here is the equality below, which is mutation-proven,
# and this is the guard that keeps it from passing over an empty store.
check('...and that proof is not vacuous: an unsaved editor finds nothing',
      app.find_note(None) is None)
check('...and what is stored is exactly what was typed — no table, no '
      'leftover line',
      _sa_saved is not None and _sa_saved.get('body') == 'x')
app.notes = []
app.save_notes()
app.open_blank_tab(); app.update()

# ---- FIELD CASES AUTOMATED (test plan 2, 3, 4, 9, 11, 19, 36, 39, 41, 66) ----
# Rows that had sat in the plan as "automation candidate" -- hours of her
# time each pass, for answers a script can give in milliseconds. Moved
# here so her hours go to the cases that need a human instead.
_fc_saved = list(app.notes)
# The trash travels with the notebook, and it holds entries from earlier
# sections with the same ids these fresh notes are about to be given --
# which read as "this note was deleted" when it was another one entirely.
_fc_saved_trash = list(app.trash)
app.notes = []
app.trash = []
app.save_notes()

# 2: a note with a title and no body is a real note.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Doar titlu')
app.title_entry.config(fg='black')
app.save_current_note(auto=False)
app.update()
_fc2 = [n for n in app.notes if n['title'] == 'Doar titlu']
check('a note with a title and no body saves (plan 2)',
      len(_fc2) == 1 and _fc2[0]['body'].strip() == '')

# 3: and one with a body and no title, which the list calls (untitled).
app.new_note()
app.body_text.insert('1.0', 'body with no title')
app.save_current_note(auto=False)
app.update()
_fc3 = [n for n in app.notes if n['body'].startswith('body with no title')]
check('a note with a body and no title saves (plan 3)', len(_fc3) == 1)
if _fc3:
    _fc_card = (app._note_card_widgets.get(_fc3[0]['id']) or {}).get('title')
    check('...and the list calls it (untitled)',
          _fc_card is not None and '(untitled)' in str(_fc_card.cget('text')))

# 4: an empty note is refused, and says so.
_fc_warned = []
_fc_real_warning = app.show_warning
app.show_warning = lambda *a, **k: (_fc_warned.append(a), True)[1]
app.new_note()
_fc_before = len(app.notes)
app.save_current_note(auto=False)
app.update()
app.show_warning = _fc_real_warning
check('an empty note is refused rather than created (plan 4)',
      len(app.notes) == _fc_before)
check('...and the refusal is explained, not silent',
      any('Empty note' in str(a[0]) for a in _fc_warned))

# 9: a delete the user cancels changes nothing.
_fc_note = _fc2[0]
app.load_note(_fc_note); app.update()
_fc_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: False          # "No"
app.delete_current_note()
app.update()
app.ask_yes_no = _fc_real_ask
check('a cancelled delete leaves the note exactly where it was (plan 9)',
      any(n['id'] == _fc_note['id'] for n in app.notes)
      and not any(e.get('id') == _fc_note['id'] for e in app.trash))

# 11: duplicating with unsaved edits copies the SAVED version, not the
# half-typed one -- the copy is a note that existed, never a draft.
app.load_note(_fc_note); app.update()
app.body_text.insert('end', ' ...text netrimis inca')
app.duplicate_note(_fc_note)
app.update()
_fc_copies = [n for n in app.notes
              if n['id'] != _fc_note['id'] and 'Doar titlu' in (n['title'] or '')]
check('duplicating with unsaved edits copies the saved version (plan 11)',
      len(_fc_copies) == 1
      and 'netrimis' not in (_fc_copies[0]['body'] or ''))

# 19: a very long note saves and comes back whole.
app.new_note()
_fc_long = ('Un rand de test care se repeta. ' * 1800)[:52000]
app.body_text.insert('1.0', _fc_long)
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Foarte lunga')
app.title_entry.config(fg='black')
_fc_t0 = time.perf_counter()
app.save_current_note(auto=False)
app.update()
_fc_elapsed = time.perf_counter() - _fc_t0
_fc_big = next((n for n in app.notes if n['title'] == 'Foarte lunga'), None)
check('a 52,000-character note saves (plan 19)',
      _fc_big is not None and len(_fc_big['body']) >= 50000)
app.new_note(); app.update()
app.load_note(_fc_big); app.update()
check('...and reopens with every character of it',
      len(app.body_text.get('1.0', 'end-1c')) >= 50000)
check('...without taking longer than a person would wait (%.1fs)' % _fc_elapsed,
      _fc_elapsed < 5.0)

# 66: a repeat with no date is refused, and the reason names the date.
_fc_warned = []
app.show_warning = lambda *a, **k: (_fc_warned.append(a), True)[1]
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Repetitiva')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'ceva')
app.rec_freq_var.set(NO.FREQ_LABELS['daily'])
app.on_recurrence_changed()
app.date_entry.delete(0, 'end')
_fc_before = len(app.notes)
app.save_current_note(auto=False)
app.update()
app.show_warning = _fc_real_warning
check('a repeating note with no start date is refused (plan 66)',
      len(app.notes) == _fc_before)
check('...and the warning says a start date is what is missing',
      any('start date' in str(a[1]).lower() or 'start date' in str(a[0]).lower()
          for a in _fc_warned))

# ---- THE REPEAT PANEL'S BOXES PASTE TOO (C-12) ----
# The register's row waved these away as "single digits, reasonable to
# leave". Two of the four are not: the end-date is a date, the same shape as
# the note's own, and the day list holds something like "1,15". All four have
# the menu now, and they need no save binding of their own -- each var traces
# to update_recurrence_summary, which schedules the autosave. That is the
# difference from the date field above, and it is asserted rather than
# assumed.
app.rec_freq_var.set(NO.FREQ_LABELS['monthly'])
app.on_recurrence_changed()
app.update()
# Asked as an INVARIANT over the whole editor rather than field by field: two
# of the four Repeat boxes are locals with no attribute to name them, and a
# check that walks the tree also catches the next editor field added without a
# menu. This is the shape the register's rows were about -- "the only field in
# the app that behaves differently" is a question about a set.
_editor_entries = _walk_widgets(app.editor, tk.Entry)
_no_menu = [e for e in _editor_entries if '<Button-3>' not in e.bind()]
check(f'every text box in the editor has a right-click paste menu '
      f'({len(_editor_entries)} boxes, {len(_no_menu)} without)',
      _editor_entries and not _no_menu)

# The end-date is the box the row's own reasoning got wrong -- it called these
# "single digits" -- so it is the one driven end to end. It is disabled until
# the end mode says "On date", which is correct: a paste into a greyed-out
# field should do nothing.
check('fixture: the end-date box is disabled while the repeat never ends',
      str(app.rec_end_date_entry.cget('state')) == 'disabled')
app.rec_end_mode_var.set('on')
app.on_end_mode_changed()
app.update()
check('fixture: choosing "On date" enables it',
      str(app.rec_end_date_entry.cget('state')) == 'normal')
app._autosave_job = None
check('fixture: no autosave is pending before the paste',
      not getattr(app, '_autosave_job', None))
app.clipboard_clear(); app.clipboard_append('2027-03-01'); app.update()
app.rec_end_date_entry.delete(0, 'end')
app.rec_end_date_entry.event_generate('<<Paste>>')
app.update()
check('a pasted end-date lands in the box',
      app.rec_end_date_entry.get() == '2027-03-01')
check('and its own trace schedules the save, with no binding of its own',
      bool(getattr(app, '_autosave_job', None)))
check("and the field's <<Paste>> really is unbound, so the trace is what did "
      "it -- unlike the date field, which needed one",
      '<<Paste>>' not in app.rec_end_date_entry.bind()
      and '<<Paste>>' in app.date_entry.bind())
app.rec_end_date_entry.delete(0, 'end')
app.rec_end_mode_var.set('never')
app.on_end_mode_changed()
app.update()

app.rec_freq_var.set(NO.FREQ_LABELS[''] if '' in NO.FREQ_LABELS
                     else 'Does not repeat')
app.on_recurrence_changed()
app.new_note(); app.update()

# 36: the checklist section opens and closes on its own button.
app.load_note(_fc_note); app.update()
_fc_was_open = app._checklist_open
if _fc_was_open:
    app.toggle_checklist_section(); app.update()
app.toggle_checklist_section(); app.update()
check('the checklist section opens when asked (plan 36)',
      app._checklist_open and app.checklist_section.winfo_ismapped())
app.toggle_checklist_section(); app.update()
check('...and closes again on the same button',
      not app._checklist_open and not app.checklist_section.winfo_ismapped())

# 39: a checklist row is removed by its own bin, immediately.
app.toggle_checklist_section(); app.update()
app._working_checklist = [{'text': 'primul', 'done': False},
                          {'text': 'al doilea', 'done': True},
                          {'text': 'al treilea', 'done': False}]
app._render_checklist_items(); app.update()
_fc_bin = None
for _row in app.checklist_items_frame.winfo_children():
    for _w in _row.winfo_children():
        if isinstance(_w, tk.Button) and '🗑' in str(_w.cget('text')):
            _fc_bin = _w
            break
    if _fc_bin is not None:
        break
check('a checklist row carries its own delete (plan 39)', _fc_bin is not None)
if _fc_bin is not None:
    _fc_bin.invoke()
    app.update()
    check('...and using it removes that row straight away',
          [i['text'] for i in app._working_checklist] == ['al doilea', 'al treilea'])

# 41: the card says how far along a checklist is -- and says nothing when
# there is no checklist.
app.save_current_note(auto=False)
app.update()
app.refresh_note_list(); app.update()
_fc_tags = (app._note_card_widgets.get(_fc_note['id']) or {}).get('tags')
check('a note with a checklist shows its progress on the card (plan 41)',
      _fc_tags is not None and '1/2' in str(_fc_tags.cget('text')))
_fc_plain = next((n for n in app.notes if not n.get('checklist')), None)
if _fc_plain is not None:
    _fc_plain_tags = (app._note_card_widgets.get(_fc_plain['id']) or {}).get('tags')
    check('...and a note without one shows no checklist mark at all',
          _fc_plain_tags is not None and '☑' not in str(_fc_plain_tags.cget('text')))


# ---- A REMOVED CHECKLIST ITEM CAN COME BACK ----
# It was the one thing that could be taken off a note with no way back at
# all: Ctrl+Z reaches the Text widgets through edit_undo, and a checklist
# is a list of dicts beside them (finding C-2 in docs/PRODUCT_FINDINGS.md).
# A toast rather than a confirmation, because a question in front of every
# tick-list tidy-up would be worse than the risk it guards.
#
# The offer is guarded by the IDENTITY of the working list: five routes
# rebind _working_checklist to a fresh list (another note, another
# occurrence, a template, a new note, an imported note), and writing into
# whatever list is current would drop the item into somebody else's note.
_cu_saved = list(app.notes)


def _cu_setup(items, note_id=9100, extra=None):
    """Load a note through the real route and open the checklist, then say
    what was set up -- a click at an unmapped row is discarded in silence,
    and loading a note CLOSES the section."""
    if getattr(app, '_autosave_job', None) is not None:
        app.after_cancel(app._autosave_job)
        app._autosave_job = None
    app._hide_toast()
    _cu_raw = {'id': note_id, 'title': 'Shopping', 'body': 'a body',
               'checklist': [{'text': t, 'done': False} for t in items]}
    _cu_raw.update(extra or {})
    app.notes = [NO.normalize_note(_cu_raw),
                 NO.normalize_note({'id': note_id + 1, 'title': 'Elsewhere',
                                    'body': 'other body',
                                    'checklist': [{'text': 'their item',
                                                   'done': False}]})]
    app.save_notes()
    # Leave first: opening the note that is already open does not reload
    # the editor, which is right for the app and wrong for a fixture
    # re-seeding the same id.
    app.new_note(); app.update()
    app.open_note_in_tab(app.find_note(note_id)); app.update()
    if not app._checklist_open:
        app.toggle_checklist_section()
    app.update()
    return (app._checklist_open
            and [i['text'] for i in app._get_checklist()] == list(items))


def _cu_texts():
    return [i.get('text') for i in app._get_checklist()]


def _cu_bin(position):
    _cu_rows = [w for w in app.checklist_items_frame.winfo_children()
                if isinstance(w, tk.Frame)]
    if not (0 <= position < len(_cu_rows)):
        return None
    for _cu_w in _cu_rows[position].winfo_children():
        if isinstance(_cu_w, tk.Button) and '🗑' in str(_cu_w.cget('text')):
            return _cu_w
    return None


def _cu_press(position):
    """Press the row's bin through the button itself.

    invoke(), not a generated <Button-1>: Tk runs a real tk.Button's
    command from its ButtonRelease binding, and neither a synthetic press
    nor press-then-release puts the widget in the state that binding needs
    -- measured, the item simply stayed. _qa_click remains right for the
    Label-bound handlers it was written for."""
    _cu_b = _cu_bin(position)
    if _cu_b is None:
        return False
    _cu_b.invoke()
    app.update()
    return True


check('checklist undo: the fixture opens the section with three items',
      _cu_setup(['milk', 'bread', 'eggs']))
check('checklist undo: the middle row has a bin', _cu_bin(1) is not None)
_cu_press(1)
check('checklist undo: the item is removed straight away',
      _cu_texts() == ['milk', 'eggs'])
_cu_undo = app._toast_action
check('checklist undo: removing an item now offers a way back',
      _cu_undo is not None)
if _cu_undo is not None:
    _cu_undo()
    app.update()
check('checklist undo: it comes back in the MIDDLE, not appended',
      _cu_texts() == ['milk', 'bread', 'eggs'])
check('checklist undo: the rows on screen come back with it',
      [str(_w.cget('text'))
       for _r in app.checklist_items_frame.winfo_children()
       for _w in _r.winfo_children()
       if isinstance(_w, tk.Label)] == ['milk', 'bread', 'eggs'])

# The offer must survive the save the deletion itself scheduled. A plain
# banner replaces _toast_action with None, so the autosave's own "Note
# updated" used to wipe the Undo about a second after it appeared.
check('checklist undo: fixture ready for the autosave case',
      _cu_setup(['milk', 'bread']))
_cu_press(0)
app._flush_autosave()
app.update()
check('checklist undo: the autosave does not wipe the Undo it triggered',
      app._toast_action is not None)
check('checklist undo: and the autosave still reports itself on the status line',
      'Auto-saved' in str(app.status_lbl.cget('text')))
_cu_stored = json.load(open('notes_data.json', encoding='utf-8'))
check('checklist undo: the removal really did reach disk',
      [i['text'] for i in next(n for n in _cu_stored
                               if n['id'] == 9100)['checklist']] == ['bread'])
app._toast_action()
app.update()
# The undo has to schedule its OWN save, the way the removal did. Checked
# by looking for the queued job, not by flushing and reading the file: a
# flush saves whatever the editor holds whether anything asked it to or
# not, so the disk check below passes even with the scheduling removed.
check('checklist undo: the way back schedules its own save',
      getattr(app, '_autosave_job', None) is not None)
app._flush_autosave()
app.update()
_cu_stored = json.load(open('notes_data.json', encoding='utf-8'))
check('checklist undo: and the way back reaches disk too',
      [i['text'] for i in next(n for n in _cu_stored
                               if n['id'] == 9100)['checklist']]
      == ['milk', 'bread'])

# The yielding is conditional, not a mute button, and bad news never yields.
check('checklist undo: fixture ready for the conditional case',
      _cu_setup(['milk', 'bread']))
app._hide_toast()
app.body_text.insert('end', ' more words')
app._flush_autosave()
app.update()
check('checklist undo: with no offer up, the autosave banner still shows',
      'Note updated' in str(app.toast_lbl.cget('text')))
check('checklist undo: fixture ready for the error case',
      _cu_setup(['milk', 'bread']))
_cu_press(0)
app._show_toast('a failure the user must see', kind='error')
app.update()
check('checklist undo: an error is never held back by a live offer',
      'a failure the user must see' in str(app.toast_lbl.cget('text')))

# A second click on a toast that has not faded, and an offer whose
# remembered position no longer exists.
check('checklist undo: fixture ready for the second click',
      _cu_setup(['milk', 'bread', 'eggs']))
_cu_press(0)
_cu_undo = app._toast_action
_cu_undo()
app.update()
_cu_toasts = []
_cu_real_toast = app._show_toast
app._show_toast = (
    lambda _t, kind='success', action=None, action_text='Undo',
    yield_to_action=False: (
        _cu_toasts.append((str(_t), kind)),
        _cu_real_toast(_t, kind=kind, action=action, action_text=action_text,
                       yield_to_action=yield_to_action))[1])
_cu_undo()
app.update()
app._show_toast = _cu_real_toast
check('checklist undo: a second click does not add the item twice',
      _cu_texts() == ['milk', 'bread', 'eggs'])
check('checklist undo: a second click says the item is already back',
      any('already back' in _t and _k == 'info' for _t, _k in _cu_toasts))

check('checklist undo: fixture ready for the shrunken list',
      _cu_setup(['milk', 'bread', 'eggs']))
_cu_press(2)
_cu_stale = app._toast_action
_cu_press(0)
_cu_stale()
app.update()
check('checklist undo: a stale offer still lands instead of raising',
      _cu_texts() == ['bread', 'eggs'])

# The guard, on the two routes most likely to be taken inside eight
# seconds: another note, and a template.
check('checklist undo: fixture ready for the note switch',
      _cu_setup(['milk', 'bread']))
_cu_press(0)
_cu_undo = app._toast_action
app.open_note_in_tab(app.find_note(9101))
app.update()
_cu_toasts = []
app._show_toast = (
    lambda _t, kind='success', action=None, action_text='Undo',
    yield_to_action=False: (
        _cu_toasts.append((str(_t), kind)),
        _cu_real_toast(_t, kind=kind, action=action, action_text=action_text,
                       yield_to_action=yield_to_action))[1])
_cu_undo()
app.update()
app._show_toast = _cu_real_toast
check('checklist undo: Undo after switching notes refuses',
      any('no longer open' in _t for _t, _k in _cu_toasts))
check("checklist undo: and the other note's list is untouched",
      _cu_texts() == ['their item'])
# The damage without the guard is not contamination -- the insert goes
# into the captured list, which nothing reads once the editor has moved
# on. It is the CLAIM: a redraw of somebody else's checklist and a status
# line saying the item was put back. Measured: a check watching the other
# note's list cannot see this, so watch what the app says instead.
check('checklist undo: and it does not claim to have put anything back',
      'put back' not in str(app.status_lbl.cget('text')))

check('checklist undo: fixture ready for the template',
      _cu_setup(['milk', 'bread']))
_cu_press(0)
_cu_undo = app._toast_action
app._apply_template({'title': 'T', 'body': 'template body',
                     'checklist': [{'text': 'from the template',
                                    'done': False}]})
app.update()
_cu_undo()
app.update()
check('checklist undo: Undo after a template leaves the template list alone',
      _cu_texts() == ['from the template'])

# Any alphabet, and a day of a repeating note.
check('checklist undo: fixture ready for the astral item',
      _cu_setup(['milk', 'cafe \U0001F600 اختبار',
                 'eggs']))
_cu_press(1)
app._toast_action()
app.update()
check('checklist undo: an astral-emoji item comes back unchanged',
      _cu_texts() == ['milk',
                      'cafe \U0001F600 اختبار',
                      'eggs'])

check('checklist undo: fixture ready for the series',
      _cu_setup(['milk', 'bread'],
                extra={'date': '2026-09-01',
                       'recurrence': {'freq': 'daily', 'interval': 1}}))
app.open_note_in_tab(app.find_note(9100), '2026-09-03')
app.update()
if not app._checklist_open:
    app.toggle_checklist_section()
app.update()
check('checklist undo: a day of a series shows the series checklist',
      _cu_texts() == ['milk', 'bread'])
_cu_press(0)
app._toast_action()
app.update()
app._flush_autosave()
app.update()
check('checklist undo: delete and undo on one day land on the series',
      [i['text'] for i in app.find_note(9100)['checklist']] == ['milk', 'bread'])
check('checklist undo: and no per-day checklist override is invented',
      'checklist' not in (app.find_note(9100).get('overrides') or {})
      .get('2026-09-03', {}))

app.notes = list(_cu_saved)
app.save_notes()
app.new_note(); app.update()

app.notes = list(_fc_saved)
app.trash = list(_fc_saved_trash)
app.save_notes()
app.new_note(); app.update()



# ---- FIELD CASES AUTOMATED (test plan 25, 27, 32, 45, 46) ----
_b3_saved = list(app.notes)

# 25: "General" is the one category nothing can delete -- the row offers
# a lock where the others offer a bin.
app.show_settings_page(); app.update()
app.toggle_settings_panel('categories'); app.update()


def _b3_rows(widget, found=None):
    if found is None:
        found = []
    for child in widget.winfo_children():
        if isinstance(child, tk.Label):
            # The row's label reads 'Name   (3)', so the name is what stands
            # before the count -- matching the whole text found nothing.
            _name = str(child.cget('text')).split('   (')[0]
            if _name in NO.CATEGORY_COLORS:
                found.append((_name, child.master))
        _b3_rows(child, found)
    return found


def _b3_buttons(row):
    out = []
    for child in row.winfo_children():
        if isinstance(child, (tk.Button, tk.Canvas)):
            out.append(child)
    return out


_b3_seen = dict(_b3_rows(app.settings_categories_panel))
check('the categories panel lists General (plan 25)', 'General' in _b3_seen)
if 'General' in _b3_seen:
    _b3_general_controls = len(_b3_buttons(_b3_seen['General']))
    _b3_other = next((n for n in _b3_seen if n != 'General'), None)
    if _b3_other:
        check('General carries fewer controls than a category you may edit '
              '(plan 25)',
              _b3_general_controls < len(_b3_buttons(_b3_seen[_b3_other])))
check('and the code protects it by name, not by hoping (plan 25)',
      NO.PROTECTED_CATEGORY == 'General')

# 27: a category's colour is one value, read everywhere it is shown.
_b3_cat = next((c for c in NO.CATEGORY_COLORS if c != 'General'), None)
if _b3_cat is None:
    NO.CATEGORY_COLORS['Proiect'] = '#123456'
    _b3_cat = 'Proiect'
_b3_was = NO.CATEGORY_COLORS[_b3_cat]
app.notes = [{'id': 5001, 'title': 'Colorata', 'body': 'x', 'comments': '',
              'category': _b3_cat, 'date': '', 'color': '', 'recurrence': {},
              'checklist': [], 'attachments': [],
              'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'}]
app.save_notes()
NO.CATEGORY_COLORS[_b3_cat] = '#ff00ff'
app.hide_settings_page()
app.refresh_note_list(); app.update()
_b3_tags = (app._note_card_widgets.get(5001) or {}).get('tags')
check("a category's new colour reaches the note card (plan 27)",
      _b3_tags is not None and str(_b3_tags.cget('fg')).lower() == '#ff00ff')
check('...because the card reads the one stored colour, not a copy',
      NO.CATEGORY_COLORS[_b3_cat].lower() == '#ff00ff')
NO.CATEGORY_COLORS[_b3_cat] = _b3_was

# 32: a template over unsaved work asks first.
app.notes = list(_b3_saved)
app.save_notes()
app.new_note()
app.body_text.insert('1.0', 'ceva scris si nesalvat')
app.update()
_b3_asked = []
_b3_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_b3_asked.append(a), False)[1]   # "No"
app._apply_template({'name': 'T', 'title': 'Din sablon', 'body': 'corp de sablon',
                     'comments': '', 'category': 'General', 'checklist': []})
app.update()
app.ask_yes_no = _b3_real_ask
check('a template over unsaved content asks before replacing it (plan 32)',
      len(_b3_asked) == 1)
check('...and answering No leaves what was typed exactly where it was',
      'ceva scris si nesalvat' in app.body_text.get('1.0', 'end-1c'))

# ---------------------------------------------------------------------
# Select all turns into Unselect all once everything on screen is
# selected. One button rather than two, because the second is only ever
# wanted straight after the first -- a mis-aimed press used to mean
# leaving selection mode and starting over, since nothing else clears a
# selection in one gesture.
#
# The trap this is walking past: "which notes are on screen" is now
# asked by BOTH the press and the word on the button. The project has
# already paid once for that question being answered in two places (see
# _query_matches_note), so the checks below make the filter disagree
# with the whole notebook on purpose.
# ---------------------------------------------------------------------
app.search_var.set('')
if hasattr(app, 'filter_var'):
    app.filter_var.set('All')
app.notes = [NO.normalize_note(
    {'id': 470 + i, 'title': 'Pick%d' % i, 'body': 'body %d' % i,
     'category': 'General'}) for i in range(6)]
app.notes[0]['title'] = 'PickOdd'
app.save_notes()
app.new_note()
app.refresh_note_list()
app.update()
if not app.selection_mode:
    app._toggle_selection_mode()
app.update()
_btn_text = lambda: str(app._bulk_select_all_btn.cget('text'))


def _box_states():
    """Each drawn card's tick box, as the widget itself believes it."""
    out = {}
    for _nid, _info in app._note_card_widgets.items():
        _cb = _info.get('checkbox')
        if _cb is None:
            continue
        out[_nid] = str(app.getvar(str(_cb.cget('variable')))) in ('1', 'True')
    return out


def _card_paths():
    return {_nid: str(_info['card'])
            for _nid, _info in app._note_card_widgets.items()}


check('the button offers to select everything to begin with',
      _btn_text() == 'Select all')
_sel_paths_before = _card_paths()
app._bulk_select_all()
app.update()
check('pressing it selects every note on screen',
      app.selected_note_ids == {n['id'] for n in app.notes})
check('...and the button now offers to let them go', _btn_text() == 'Unselect all')
# The boxes themselves, not just the set behind them: they carry their
# own variables, so a selection changed without touching them leaves
# every card looking untouched.
check('...and every tick box on screen shows it',
      _box_states() and all(_box_states().values()))
# And without rebuilding the list to do it. Moving a tick used to cost
# 140 widgets and ~170ms -- reported as "the list rebuilds and takes a
# moment", and twice as often once the button could also let go.
check('...without rebuilding a single card to move a tick',
      _card_paths() == _sel_paths_before)
app._bulk_select_all()
app.update()
check('pressing it again clears the selection', app.selected_note_ids == set())
check('...and clears every tick box with it',
      _box_states() and not any(_box_states().values()))
check('...still without rebuilding the list',
      _card_paths() == _sel_paths_before)
check('...without leaving selection mode, which is the whole point',
      app.selection_mode is True)
check('...and the button offers to select again', _btn_text() == 'Select all')

# Half-selected is not all-selected: the button must still offer to
# finish the job rather than to undo it.
app._toggle_note_selected(470, True)
app.update()
check('one note selected still reads as Select all', _btn_text() == 'Select all')
app._bulk_select_all()
app.update()
check('...and pressing it takes the rest, rather than dropping the one',
      app.selected_note_ids == {n['id'] for n in app.notes})

# The filter changes what "all" means. Select everything, then narrow the
# search: the notes on screen are still all selected, so the button must
# still say Unselect all -- and widening it again must put the offer back.
app.selected_note_ids = set()
app._update_bulk_selected_label()
app.search_var.set('PickOdd')
app.refresh_note_list()
app.update()
check('a narrowed list with nothing selected offers Select all',
      _btn_text() == 'Select all')
app._bulk_select_all()
app.update()
# The discriminating case, and the reason "what is on screen" has one
# definition: ONE note of six is selected here, so a button that asked
# the whole notebook would still be offering to select. It has to answer
# for the list, which is where the word "all" was read.
check('...and taking the one visible note reads as Unselect all',
      _btn_text() == 'Unselect all' and len(app.selected_note_ids) == 1)
app._bulk_select_all()
app.update()
check('...and Unselect there clears the selection', app.selected_note_ids == set())
app.search_var.set('')
app.refresh_note_list()
app.update()
check('widening the search offers Select all again', _btn_text() == 'Select all')
app._bulk_select_all()
app.update()
check('...and it takes every note, not just the ones the filter had shown',
      app.selected_note_ids == {n['id'] for n in app.notes})
app.selected_note_ids = set()
app._update_bulk_selected_label()
app.update()

if app.selection_mode:
    app._toggle_selection_mode()
app.update()


# ---------------------------------------------------------------------
# Deleting a note takes ONE card off the list instead of rebuilding it.
#
# Field-reported as "the picture breaks a little and rebuilds itself".
# Measured: 264 widgets and 185ms per delete, of which the list was 169
# and 129. The surgical path is the fourth of its family here, and the
# rule it lives by is that any doubt falls back to the full rebuild --
# so these checks are as much about the FALLBACK firing as about the
# fast path working.
# ---------------------------------------------------------------------
app.group_by_category.set(False)
app.search_var.set('')
if hasattr(app, 'filter_var'):
    app.filter_var.set('All')
app.notes = [NO.normalize_note(
    {'id': 400 + i, 'title': 'Surgical%d' % i, 'body': 'b%d' % i,
     'category': 'General'}) for i in range(12)]
app.save_notes()
app.new_note()
app.refresh_note_list()
app.update()
# ---------------------------------------------------------------------
# The selection bar fits in the sidebar it lives in.
#
# It used to be one line of five controls across a fixed 280px sidebar,
# which meant it could not fit and had no way to say so: the packer
# gives each control what it asks for in order, and the last one lives
# on the remainder. Measured, Export asked 40px and was drawn at 27 --
# the word against the edge with its caret cut off, reported from the
# field. Everything before it got exactly what it asked for, which is
# why nothing looked wrong until the end of the row.
# ---------------------------------------------------------------------
if not app.selection_mode:
    app._toggle_selection_mode()
app.update()
app.update_idletasks()
_bar = app.bulk_action_bar
check('the selection bar asks for no more room than it is given',
      _bar.winfo_reqwidth() <= _bar.winfo_width())


def _bar_buttons(widget, out=None):
    out = [] if out is None else out
    for child in widget.winfo_children():
        if isinstance(child, tk.Button):
            out.append(child)
        _bar_buttons(child, out)
    return out


_bar_btns = _bar_buttons(_bar)
check('the bar has its four actions', len(_bar_btns) == 4)
for _b in _bar_btns:
    check('...and "%s" is drawn at least as wide as it asks'
          % str(_b.cget('text')),
          _b.winfo_width() >= _b.winfo_reqwidth())
# No check for "the shortfall is shared": with the count on its own row
# the four actions ask 193px of the 250 they are given, so nothing is
# under pressure and no single edit can starve one. Sharing the width is
# defence in depth against a future font or label, not a promise this
# suite can currently break -- and a check that cannot fail proves
# nothing. Written down rather than left as a passing line.
def _sg_settle():
    """Stop anything that rebuilds the list on a timer of its own.

    The sidebar search debounces with after(180, refresh_note_list). A
    full rebuild produces correct cards, so a timer landing between a
    surgical removal and the reading below would repair whatever the
    removal got wrong and report it as right. Once deleting stopped
    costing 185ms there is no longer enough slack for that timer to have
    always fired already, which is how a sibling check in qa7 turned red
    without anything being wrong with it.
    """
    app._flush_autosave()
    if getattr(app, '_search_debounce_job', None) is not None:
        app.after_cancel(app._search_debounce_job)
        app._search_debounce_job = None
    app.update()


_sg_settle()
_sg_before = len(app._note_card_widgets)
check('the list drew a card per note to begin with', _sg_before == 12)
# The witness. Every check below about "the cards survived" would pass
# just as happily after a full rebuild, which produces correct cards
# too -- so one card's Tk path is remembered. A rebuild destroys and
# recreates it under a new name; taking one card off does not touch it.
# Without this, nothing here can tell the two apart.
_sg_witness = str(app._note_card_widgets[400]['card'])

_sg_target = app.find_note(405)
app._delete_note(_sg_target, None)
_sg_settle()
check('the deleted note loses its card',
      405 not in app._note_card_widgets)
check('...and every other card is still there',
      len(app._note_card_widgets) == _sg_before - 1)
check('...and the cards were not rebuilt around it',
      all(w['card'].winfo_exists() for w in app._note_card_widgets.values()))
check('...and a surviving card is the SAME widget, not a remade one',
      str(app._note_card_widgets[400]['card']) == _sg_witness)
check('...and the list agrees with the notes',
      sorted(app._note_card_widgets) == sorted(n['id'] for n in app.notes))

# The scroll guards exist because a REBUILD empties the frame and a
# Configure landing in that window clamps the canvas to the top -- the
# "the list jumps back to the top" report. Taking one card off empties
# nothing, so the position should simply stay.
#
# Two things this check got wrong the first time, and both are written
# down because each would have passed for the wrong reason:
#
#   * it scrolled to the BOTTOM. Deleting a card makes the content
#     shorter, so Tk must scroll up to keep the view inside the
#     scrollregion -- correct behaviour that the check called a defect.
#     It reads from the middle now, and deletes the note at the very
#     END of the list, so nothing above the viewport changes.
#   * it never made sure the list was scrollable at all. With twelve
#     cards in a tall window there was nothing to scroll, canvasy(0)
#     was 0 before and after, and the check passed on a tautology --
#     locally. On CI, where the geometry differs, the list DID scroll
#     and the first mistake showed. So scrollability is asserted before
#     anything is measured, rather than assumed.
_sg_settle()
for _i in range(30):
    app.notes.append(NO.normalize_note(
        {'id': 450 + _i, 'title': 'Scrolls%d' % _i, 'body': 'b',
         'category': 'General'}))
app.save_notes()
app.new_note()
app.refresh_note_list()
_sg_settle()
_sg_content = app.canvas.bbox('all')
_sg_room = app.canvas.winfo_height()
check('the list is long enough to scroll, so the next check means something',
      _sg_content is not None and (_sg_content[3] - _sg_content[1]) > _sg_room + 50)
# The bottom card: deleting it changes nothing above the viewport.
_sg_last_id = list(app._note_card_widgets)[-1]


def _sg_quiet():
    """Let the list settle WITHOUT provoking a new refresh.

    _sg_settle() flushes the autosave, and a flush that saves calls
    refresh_note_list(), which remembers the current scroll and puts it
    back on after_idle. Used after positioning the view, that pending
    restore lands on top of the move and undoes it -- measured: yview
    was bit-for-bit identical before and after yview_moveto(0.4), and
    canvasy sat at the 10px the earlier refresh had memorised. The
    search debounce still gets cancelled; nothing here starts anything.
    """
    if getattr(app, '_search_debounce_job', None) is not None:
        app.after_cancel(app._search_debounce_job)
        app._search_debounce_job = None
    for _ in range(3):
        app.update()
        app.update_idletasks()


# Every pending refresh-and-restore from the seeding above has to land
# BEFORE the view is positioned, or it lands on top of it afterwards.
_sg_settle()
_sg_quiet()
app.canvas.yview_moveto(0.4)
# A rebuild's restore is not a single event: it stays in force for 400ms
# and re-applies itself at 60, 160 and 360 -- because a rebuilt list's
# geometry settles over several passes and each one re-clamps the canvas
# (see _restore_list_scroll). Any move made inside that window is simply
# put back, which is what happened here: yview read bit-for-bit
# identical before and after the moveto.
#
# The app already says what beats it. _list_scrollbar_moved clears the
# pending restore because "a deliberate drag beats a rebuild's
# still-pending restore" -- and moving the view here is that same
# gesture without a mouse, so it clears it the same way.
app._list_restore_px = None
_sg_quiet()
_sg_scroll = app.canvas.canvasy(0)
check('...and the view really is away from the top before the delete',
      _sg_scroll > 10)
app._delete_note(app.find_note(_sg_last_id), None)
_sg_quiet()
check('a delete leaves the list scrolled where it was',
      abs(app.canvas.canvasy(0) - _sg_scroll) < 2)
app.canvas.yview_moveto(0.0)
_sg_quiet()

# The open-note border is moved by _update_open_highlight, which reads
# the same registry. A card removed from under it must not leave it
# pointing at something that no longer exists.
app.open_note_in_tab(app.find_note(403))
app.update()
app._delete_note(app.find_note(403), None)
_sg_settle()
check('deleting the OPEN note leaves the highlight with nothing stale',
      403 not in app._note_card_widgets)
app.open_note_in_tab(app.find_note(402))
app.update()
check('...and the next note opened still takes the border',
      app._note_card_widgets[402]['card'].cget('highlightthickness') == 2)

# A theme switch afterwards recolours what is left, in place, and must
# not trip over the entry that was removed.
app.set_theme('light')
app.update()
check('a theme switch after a delete recolours the surviving cards',
      all(str(w['card'].cget('bg')).lower() == app.colors['card'].lower()
          for w in app._note_card_widgets.values()))
app.set_theme('dark')
app.update()

# THE FALLBACK. Deleting the last note on screen must hand over to the
# full rebuild, because an empty list is not "no cards" -- it carries a
# message, and which message depends on whether anything is filtered.
app.notes = [NO.normalize_note({'id': 500, 'title': 'LastOne', 'body': 'b',
                                'category': 'General'})]
app.save_notes()
app.new_note()
app.refresh_note_list()
app.update()
app._delete_note(app.find_note(500), None)
_sg_settle()
check('deleting the last note empties the card registry',
      not app._note_card_widgets)
_sg_texts = []
for _w in app.list_frame.winfo_children():
    try:
        _sg_texts.append(str(_w.cget('text')))
    except tk.TclError:
        pass
check('...and the empty list says so, which only a full rebuild writes',
      any('No notes' in t for t in _sg_texts))

app.notes = []
app.trash = []
app.save_notes()
NO.save_trash(app.trash)
app.new_note()
app.refresh_note_list()
app.update()

# 45: the theme picker offers the variants of the mode you are in.
check('dark and light are separate lists, not one (plan 45)',
      set(NO.DARK_THEMES).isdisjoint(NO.LIGHT_THEMES)
      and len(NO.DARK_THEMES) >= 2 and len(NO.LIGHT_THEMES) >= 2)
_b3_dark = NO.DARK_THEMES[0]
app.theme_name = _b3_dark
check('...and the app knows which list the current theme belongs to',
      _b3_dark in NO.DARK_THEMES and _b3_dark not in NO.LIGHT_THEMES)

# 46: the chosen theme is remembered, and a fresh start reads it back.
_b3_pick = NO.LIGHT_THEMES[-1]
app.set_theme(_b3_pick)
app.update()
check('choosing a theme writes it down (plan 46)',
      NO.load_settings().get('theme') == _b3_pick)
_b3_fresh = NO.NoteOrganizer()
_b3_fresh.update()
check('...and a fresh start opens in it, not in the default (plan 46)',
      _b3_fresh.theme_name == _b3_pick)
_b3_fresh.destroy()
app.set_theme(_b3_dark)
app.update()

app.notes = list(_b3_saved)
app.save_notes()
app.new_note(); app.update()



# ---- FIELD CASES AUTOMATED (test plan 114, 139, 178) ----
_b4_saved = list(app.notes)

# 139: removing an item from the MIDDLE of a numbered list renumbers what
# follows -- the first-item case was already covered, and the middle is
# where an off-by-one hides.
app.notes = []
app.save_notes()
app.new_note()
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', 'unu\ndoi\ntrei\npatru')
for _b4_line in range(1, 5):
    app.body_text.mark_set('insert', '%d.0' % _b4_line)
    app._toggle_list('number')
app.update()
_b4_before = app.body_text.get('1.0', 'end-1c')
check('a four-item numbered list is numbered 1-4 (plan 139)',
      _b4_before.startswith('1. unu') and '4. patru' in _b4_before)
app.body_text.delete('2.0', '3.0')          # the SECOND item, from the middle
app._renumber_lists()
app.update()
_b4_after = app.body_text.get('1.0', 'end-1c')
check('removing a middle item renumbers what follows it (plan 139)',
      '1. unu' in _b4_after and '2. trei' in _b4_after and '3. patru' in _b4_after
      and '4.' not in _b4_after)

# 178: duplicating a note that holds a table gives a real second table,
# not a shared one -- editing the copy must not reach the original.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Cu tabel')
app.title_entry.config(fg='black')
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', '| A | B |\n| --- | --- |\n| 1 | 2 |')
app.save_current_note(auto=False)
app.update()
_b4_orig = next(n for n in app.notes if n['title'] == 'Cu tabel')
app.duplicate_note(_b4_orig)
app.update()
_b4_copy = next((n for n in app.notes
                 if n['id'] != _b4_orig['id'] and 'Cu tabel' in (n['title'] or '')), None)
check('a note with a table can be duplicated (plan 178)', _b4_copy is not None)
if _b4_copy is not None:
    check('...and the copy carries the table, drawn as rows not as pipes',
          '| 1 | 2 |' in (_b4_copy['body'] or ''))
    _b4_copy['body'] = _b4_copy['body'].replace('| 1 | 2 |', '| 9 | 9 |')
    check('...and editing the copy leaves the original alone (plan 178)',
          '| 1 | 2 |' in _b4_orig['body'])

# 114: a template edited after it was used does not reach back into the
# note it already made.
app.notes = []
app.save_notes()
_b4_tpl = {'name': 'Sablon', 'title': 'Din sablon', 'body': 'corp',
           'comments': '', 'category': 'General',
           'checklist': [{'text': 'primul pas', 'done': False}]}
app.ask_yes_no = lambda *a, **k: True
app.new_note()
app._apply_template(_b4_tpl)
app.save_current_note(auto=False)
app.update()
_b4_note_a = app.notes[-1]
check('a template brings its checklist into the note it makes (plan 114)',
      [i['text'] for i in (_b4_note_a.get('checklist') or [])] == ['primul pas'])
_b4_tpl['checklist'] = [{'text': 'pas schimbat', 'done': False},
                        {'text': 'pas nou', 'done': False}]
app.new_note()
app._apply_template(_b4_tpl)
app.save_current_note(auto=False)
app.update()
_b4_note_b = app.notes[-1]
check('editing the template later leaves the earlier note untouched (plan 114)',
      [i['text'] for i in (app.find_note(_b4_note_a['id']) or {}).get('checklist', [])]
      == ['primul pas'])
check('...and the next note made from it gets the NEW checklist (plan 114)',
      [i['text'] for i in (_b4_note_b.get('checklist') or [])]
      == ['pas schimbat', 'pas nou'])

app.notes = list(_b4_saved)
app.save_notes()
app.new_note(); app.update()


# ---- A BULK CHANGE MUST SURVIVE WHAT THE USER TYPES NEXT ----
# Found by qa/story_audit.py, walking a shape nothing else walked: do a
# bulk action, then carry on typing. The editor was still holding the
# note's OLD category in its dropdown, and its next save wrote that back
# -- the bulk change reverted, silently, for the one note that happened
# to be open. The note nobody had open kept the new category, which is
# what makes it so easy to miss.
_bk_saved = list(app.notes)
NO.CATEGORY_COLORS.setdefault('Munca', '#775599')
app.notes = [NO.normalize_note({'id': 7700 + i, 'title': 'Masa %d' % i,
                                'body': 'corp %d' % i, 'category': 'General'})
             for i in range(3)]
app.save_notes()
app.refresh_note_list(); app.update()
app.open_note_in_tab(app.notes[0]); app.update()
app.selection_mode = True
app.selected_note_ids = {7700, 7701}
app._bulk_change_category()
app.update()
# The popup is a Toplevel kept as app._mini_popup, one row per
# category, each bound to the handler a click reaches. Find the row
# whose label says Munca and click IT -- never do its work here, or the
# check passes on its own behaviour instead of the app's.
_bk_row = None
_bk_pop = getattr(app, '_mini_popup', None)


def _bk_find_row(widget):
    global _bk_row
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and str(child.cget('text')).strip() == 'Munca':
            _bk_row = child
            return
        _bk_find_row(child)


if _bk_pop is not None and _bk_pop.winfo_exists():
    _bk_find_row(_bk_pop)
check('the bulk category popup offers the category by name (audit finding)',
      _bk_row is not None)
if _bk_row is not None:
    _qa_click(_bk_row)
    app.update()

check('a bulk category change reaches the notes (audit finding)',
      [n['category'] for n in app.notes if n['id'] in (7700, 7701)]
      == ['Munca', 'Munca'])
app.body_text.insert('end', ' si scriu mai departe')
app._flush_autosave()
app.update()
_bk_stored = json.load(open('notes_data.json', encoding='utf-8'))
_bk_open = next(n for n in _bk_stored if n['id'] == 7700)
_bk_other = next(n for n in _bk_stored if n['id'] == 7701)
check('...and typing afterwards does not revert it on the OPEN note '
      '(audit finding)', _bk_open['category'] == 'Munca')
check('...while the note nobody had open was never at risk',
      _bk_other['category'] == 'Munca')
check('...and what was typed afterwards is saved too',
      'mai departe' in _bk_open['body'])

app.notes = list(_bk_saved)
app.save_notes()
app.new_note(); app.update()


# ---- THE BULK CATEGORY CHANGE ASKS, AND OFFERS A WAY BACK ----
# It was the one action in that bar that rewrote stored data with neither
# a question nor an undo, while the button beside it had both -- and the
# categories it overwrote were gone from the file the moment it ran
# (finding C-1 in docs/PRODUCT_FINDINGS.md). These checks hold both
# halves of the promise, and every seam the interaction pass marked
# risky: a MIXED selection, the editor holding one of the notes, a
# table-ending note, a series with a day of its own, a filtered list,
# and a second click on a toast that has not faded.
_bc_saved = list(app.notes)
for _bc_name, _bc_colour in (('Alpha', '#4488cc'), ('Beta', '#775599'),
                             ('Gamma', '#cc8844'), ('Target', '#44aa88')):
    NO.CATEGORY_COLORS.setdefault(_bc_name, _bc_colour)
_bc_real_ask = app.ask_yes_no
_bc_asked = {}
_BC_TABLE_BODY = ('Before the table.\n'
                  '\n'
                  '| Item | Qty |\n'
                  '| --- | --- |\n'
                  '| Nails | 40 |\n'
                  '| Screws | 12 |')
_BC_HEAVY_FIELDS = ('body', 'checklist', 'formatting', 'paragraphs',
                    'attachments')


def _bc_seed(spec):
    """(id, title, category, extra) per note.

    Each scenario starts from a state this file STATES rather than one it
    inherits from whatever ran above -- a fixture that does not say what
    it set turns the reading that follows into a rumour.
    """
    app.notes = []
    for _bc_id, _bc_title, _bc_cat, _bc_extra in spec:
        # An explicit OLD stamp, not whatever normalize_note puts on a
        # note made now. With a fresh stamp the change's own stamp is the
        # same string to the second, so an undo that never restores
        # `updated` looks identical to one that does -- the mutant for
        # that check survived until this line existed.
        _bc_raw = {'id': _bc_id, 'title': _bc_title, 'category': _bc_cat,
                   'body': 'body of %s' % _bc_title,
                   'updated': '2020-01-01 00:00:00'}
        _bc_raw.update(_bc_extra or {})
        app.notes.append(NO.normalize_note(_bc_raw))
    app.save_notes()
    app.new_note()
    app.refresh_note_list()
    # The search debounce can rebuild the list under a later reading and
    # repair whatever a surgical update got wrong -- settle it here so
    # every check below is about its own subject (qa/README house rules).
    if getattr(app, '_search_debounce_job', None) is not None:
        app.after_cancel(app._search_debounce_job)
        app._search_debounce_job = None
    app.update()


def _bc_pick(label_text):
    """Open the popup and click the row named `label_text`.

    Never calls apply_category from here: a check that does the app's own
    work reports on its own behaviour instead of the app's, which is how
    chapter 4 of qa/story_audit.py went on reporting a bug for an hour
    after it had been fixed.
    """
    app._bulk_change_category()
    app.update()
    _bc_hit = []

    def _bc_walk(widget):
        for _bc_child in widget.winfo_children():
            if isinstance(_bc_child, tk.Label) and \
                    str(_bc_child.cget('text')).strip() == label_text:
                _bc_hit.append(_bc_child)
                return
            _bc_walk(_bc_child)

    _bc_pop = getattr(app, '_mini_popup', None)
    if _bc_pop is None or not _bc_pop.winfo_exists():
        return False
    _bc_walk(_bc_pop)
    if not _bc_hit:
        return False
    _qa_click(_bc_hit[0])
    app.update()
    return True


def _bc_cats():
    return {n['id']: n['category'] for n in app.notes}


def _bc_heavy(note_id):
    _bc_note = app.find_note(note_id)
    return {_bc_k: json.dumps(_bc_note.get(_bc_k), sort_keys=True,
                              ensure_ascii=False)
            for _bc_k in _BC_HEAVY_FIELDS}


# The question is recorded, not merely answered: what it SAYS is half the
# fix. It also reports whether the borderless category popup was still on
# screen at the moment a modal opened -- the popup takes no focus, so one
# left up floats over the very question it is asking.
#
# A named function rather than a lambda, and reinstated by name after the
# "No" scenario borrows the slot: the first version of this block put a
# plain `lambda: True` back afterwards, so the last two checks read a
# _bc_asked nobody had written to since -- they failed on the fixture, not
# on the app.
def _bc_ask_recording(_bc_title, _bc_msg, **_bc_kw):
    _bc_asked.clear()
    _bc_asked.update({
        'msg': _bc_msg,
        'popup_alive': bool(getattr(app, '_mini_popup', None)
                            and app._mini_popup.winfo_exists())})
    return True


app.ask_yes_no = _bc_ask_recording

# A MIXED selection: three notes in three different categories. One
# remembered "old category" for the batch would file all three back under
# whichever was read first, and would pass a single-category check.
_bc_seed([(8100, 'BcOne', 'Alpha', None), (8101, 'BcTwo', 'Beta', None),
          (8102, 'BcThree', 'Gamma', None)])
_bc_before = _bc_cats()
_bc_stamps = {n['id']: n['updated'] for n in app.notes}
# State what the fixture prepared, rather than assuming it: the stamp
# check below is only meaningful because these are OLD stamps, so a
# change that rewrites them is visible.
check('bulk category: the fixture starts from old updated stamps',
      set(_bc_stamps.values()) == {'2020-01-01 00:00:00'})
app.selection_mode = True
app.selected_note_ids = {8100, 8101, 8102}
check('bulk category: the popup offers the target by name', _bc_pick('Target'))
check('bulk category: it asks first, naming the count and the target',
      '3 selected notes' in _bc_asked.get('msg', '')
      and '“Target”' in _bc_asked.get('msg', ''))
check('bulk category: the question says how many categories it overwrites',
      'They sit in 3 different categories today.' in _bc_asked.get('msg', ''))
check('bulk category: the popup is gone before the question is asked',
      _bc_asked.get('popup_alive') is False)
check('bulk category: the change reaches every ticked note',
      set(_bc_cats().values()) == {'Target'})
check('bulk category: selection mode is left behind',
      not app.selection_mode and not app.selected_note_ids)
# The other end of the stamp check: if the change never moved the stamp,
# "the undo restored it" would be true of nothing.
check('bulk category: the change moves the updated stamp forward',
      all(n['updated'] != '2020-01-01 00:00:00' for n in app.notes
          if n['id'] in (8100, 8101, 8102)))
_bc_undo = app._toast_action
check('bulk category: the toast carries an Undo', _bc_undo is not None)
if _bc_undo is not None:
    _bc_undo()
    app.update()
check('bulk category: Undo puts each note back in ITS OWN category',
      _bc_cats() == _bc_before)
check('bulk category: Undo restores the old updated stamps too',
      {n['id']: n['updated'] for n in app.notes} == _bc_stamps)
check('bulk category: Undo does not re-enter selection mode',
      not app.selection_mode)

# Saying No has to cost nothing at all -- not the category, not the stamp.
_bc_seed([(8110, 'BcNo', 'Alpha', None), (8111, 'BcNo2', 'Beta', None)])
_bc_untouched = _bc_cats()
_bc_untouched_stamps = {n['id']: n['updated'] for n in app.notes}
app.ask_yes_no = lambda *_a, **_k: False
app.selection_mode = True
app.selected_note_ids = {8110, 8111}
_bc_pick('Target')
check('bulk category: answering No leaves the categories alone',
      _bc_cats() == _bc_untouched)
check('bulk category: answering No leaves the stamps alone too',
      {n['id']: n['updated'] for n in app.notes} == _bc_untouched_stamps)
app.ask_yes_no = _bc_ask_recording

# A second click on a toast that has not faded, with one note filed by
# hand in between: a stale memory of what used to be there must not win.
_bc_seed([(8120, 'BcTwice', 'Alpha', None), (8121, 'BcTwice2', 'Beta', None)])
app.selection_mode = True
app.selected_note_ids = {8120, 8121}
_bc_pick('Target')
_bc_undo = app._toast_action
_bc_undo()
app.update()
app.find_note(8120)['category'] = 'Gamma'
app.save_notes()
_bc_toasts = []
_bc_real_toast = app._show_toast
app._show_toast = (
    lambda _bc_text, kind='success', action=None, action_text='Undo': (
        _bc_toasts.append((str(_bc_text), kind)),
        _bc_real_toast(_bc_text, kind=kind, action=action,
                       action_text=action_text))[1])
_bc_undo()
app.update()
app._show_toast = _bc_real_toast
check('bulk category: a second Undo does not clobber a category set by hand',
      app.find_note(8120)['category'] == 'Gamma')
check('bulk category: a second Undo says so instead of claiming success',
      any('Nothing left to put back' in _bc_t and _bc_k == 'info'
          for _bc_t, _bc_k in _bc_toasts))

# The editor holding one of the ticked notes, and that note ending in a
# table -- the shape that once made every table-ending note read as
# permanently unsaved. Both directions, and nothing but the category may
# move.
_bc_seed([(8130, 'BcHeavy', 'Alpha', {
               'body': _BC_TABLE_BODY,
               'checklist': [{'text': 'buy nails', 'done': False},
                             {'text': 'buy screws', 'done': True}],
               'formatting': [{'start': 0, 'end': 6, 'tags': ['bold']}],
               'paragraphs': {'0': {'align': 'center'}},
               'attachments': [{'name': 'plan.txt',
                                'path': 'attachments/plan.txt', 'size': 12}]}),
          (8131, 'BcPlain', 'Beta', None)])
_bc_heavy_before = _bc_heavy(8130)
app.open_note_in_tab(app.find_note(8130))
app.update()
check('bulk category: a table-ending note opens clean before any of this',
      app.editor_state_matches_saved(app.capture_editor_state()))
check('bulk category: the editor starts on the stored category',
      app.category_var.get() == 'Alpha')
app.selection_mode = True
app.selected_note_ids = {8130, 8131}
_bc_pick('Target')
check('bulk category: the editor follows the change',
      app.category_var.get() == 'Target')
check('bulk category: the changed note does not read as unsaved',
      app.editor_state_matches_saved(app.capture_editor_state()))
check('bulk category: the change moves the category and nothing else',
      _bc_heavy(8130) == _bc_heavy_before)
_bc_undo = app._toast_action
_bc_undo()
app.update()
check('bulk category: the editor follows the Undo back',
      app.category_var.get() == 'Alpha')
check('bulk category: the Undo does not leave the note reading as unsaved',
      app.editor_state_matches_saved(app.capture_editor_state()))
check('bulk category: the Undo moves the category and nothing else',
      _bc_heavy(8130) == _bc_heavy_before)

# A series with one day given a category by hand. The change writes the
# series' own category and leaves that day alone -- so the question must
# not promise it replaces the category "on each of them" full stop.
_bc_seed([(8140, 'BcSeries', 'Alpha', {
               'date': '2026-09-01',
               'recurrence': {'freq': 'daily', 'interval': 1},
               'overrides': {'2026-09-03': {'category': 'Gamma'}}}),
          (8141, 'BcSeriesPlain', 'Beta', None)])
app.selection_mode = True
app.selected_note_ids = {8140, 8141}
_bc_pick('Target')
check('bulk category: the question warns a day keeps its own category',
      'has a day with its own category' in _bc_asked.get('msg', ''))
check("bulk category: the series' own category moves",
      app.find_note(8140)['category'] == 'Target')
check('bulk category: the overridden day keeps its category',
      app.find_note(8140)['overrides']['2026-09-03']['category'] == 'Gamma')
_bc_undo = app._toast_action
_bc_undo()
app.update()
check('bulk category: Undo puts the series back',
      app.find_note(8140)['category'] == 'Alpha')
check('bulk category: Undo still leaves the overridden day alone',
      app.find_note(8140)['overrides']['2026-09-03']['category'] == 'Gamma')

# The bulk route acts on a list that was filtered by whatever was typed
# in the search box at the time -- the easiest one to regret, and the
# reason the undo is here at all.
_bc_seed([(8150, 'BcFindMe', 'Alpha', None),
          (8151, 'BcHidden', 'Beta', None)])
app.search_var.set('BcFindMe')
if getattr(app, '_search_debounce_job', None) is not None:
    app.after_cancel(app._search_debounce_job)
    app._search_debounce_job = None
app.refresh_note_list()
app.update()
check('bulk category: the filtered list shows only the match',
      set(app._visible_note_ids()) == {8150})
app.selection_mode = True
app.selected_note_ids = {8150}
_bc_pick('Target')
check('bulk category: a single note is asked about in the singular',
      '1 selected note' in _bc_asked.get('msg', '')
      and 'This replaces the category on it.' in _bc_asked.get('msg', ''))
check('bulk category: only the ticked note moved out of the filtered list',
      app.find_note(8150)['category'] == 'Target'
      and app.find_note(8151)['category'] == 'Beta')
_bc_undo = app._toast_action
_bc_undo()
app.update()
check('bulk category: Undo works from a filtered list too',
      app.find_note(8150)['category'] == 'Alpha')
app.search_var.set('')
if getattr(app, '_search_debounce_job', None) is not None:
    app.after_cancel(app._search_debounce_job)
    app._search_debounce_job = None
app.refresh_note_list()
app.update()

# The old category is deleted while the toast is still up. There is
# nowhere to put the note back into, and inventing a destination is worse
# than admitting it.
_bc_seed([(8160, 'BcGone', 'Alpha', None), (8161, 'BcGone2', 'Beta', None)])
app.selection_mode = True
app.selected_note_ids = {8160, 8161}
_bc_pick('Target')
_bc_undo = app._toast_action
_bc_dropped = NO.CATEGORY_COLORS.pop('Beta')
_bc_undo()
app.update()
NO.CATEGORY_COLORS['Beta'] = _bc_dropped
check('bulk category: a note whose old category is gone stays where it is',
      app.find_note(8161)['category'] == 'Target')
check('bulk category: the note whose category still exists goes back',
      app.find_note(8160)['category'] == 'Alpha')
check('bulk category: the status line admits the one it could not place',
      'could not go back' in str(app.status_lbl.cget('text')))

app.ask_yes_no = _bc_real_ask
app.notes = list(_bc_saved)
app.save_notes()
app.new_note(); app.update()

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

# ============================================================
# ASTRAL EMOJI SURVIVE BACKSPACE/DELETE IN THE ENTRY FAMILY
# ============================================================
# Tk Entry counts UTF-16 units and its stock BackSpace/Delete remove
# exactly one — half an astral emoji. The torn remnant rendered as a
# box, and the save's surrogate mend turned its bytes into question
# marks after a restart (field report). The guarded entries delete the
# whole character; everything else about them stays stock.
_eapp = NO.NoteOrganizer(); _eapp._poll_active_dirty = lambda: None
_eapp.show_info = lambda *a, **k: True
_eapp.geometry('1100x850'); _eapp.update()


def _torn(s):
    return any(0xD800 <= ord(c) <= 0xDFFF for c in s)


_eapp.title_entry.delete(0, 'end')
_eapp.title_entry.insert(0, 'hi \U0001F600')
_eapp.title_entry.icursor('end')
_eapp.title_entry.focus_force()
for _ in range(60):
    _eapp.update(); _eapp.update_idletasks()
    if _eapp.focus_get() is _eapp.title_entry:
        break
    time.sleep(0.01)
_eapp.title_entry.event_generate('<BackSpace>'); _eapp.update()
_t1 = _eapp.title_entry.get()
check('BackSpace after a title emoji removes the whole character',
      _t1 == 'hi ' and not _torn(_t1))

_eapp.title_entry.delete(0, 'end')
_eapp.title_entry.insert(0, '\U0001F600 hi')
_eapp.title_entry.icursor(0)
_eapp.update()
_eapp.title_entry.event_generate('<Delete>'); _eapp.update()
_t2 = _eapp.title_entry.get()
check('Delete before a title emoji removes the whole character',
      _t2 == ' hi' and not _torn(_t2))

_eapp.title_entry.delete(0, 'end')
_eapp.title_entry.insert(0, 'abc')
_eapp.title_entry.icursor('end')
_eapp.update()
_eapp.title_entry.event_generate('<BackSpace>'); _eapp.update()
check('plain characters still delete one at a time',
      _eapp.title_entry.get() == 'ab')

_eapp.title_entry.delete(0, 'end')
_eapp.title_entry.insert(0, 'x\U0001F600y')
_eapp.title_entry.selection_range(0, 'end')
_eapp.update()
_eapp.title_entry.event_generate('<BackSpace>'); _eapp.update()
check('selection deletion is left to stock Tk and clears whole',
      _eapp.title_entry.get() == '')

# Breadth: the same guard arms the sidebar search box (one more member
# of the free-text Entry family; all nine bind the same handlers).
_eapp.search_var.set('')
_se = None
def _find_search(w):
    global _se
    for c in w.winfo_children():
        if isinstance(c, NO.tk.Entry) and str(c.cget('textvariable')) == str(_eapp.search_var):
            _se = c
        _find_search(c)
_find_search(_eapp.sidebar)
if _se is None:
    check('the sidebar search entry was found for the astral check', False)
else:
    _se.delete(0, 'end')
    _se.insert(0, '\U0001F600')
    _se.icursor('end')
    _se.focus_force()
    for _ in range(60):
        _eapp.update(); _eapp.update_idletasks()
        if _eapp.focus_get() is _se:
            break
        time.sleep(0.01)
    _se.event_generate('<BackSpace>'); _eapp.update()
    check('the search box deletes a whole emoji too',
          _se.get() == '' and not _torn(_se.get()))
_eapp.destroy()


print()
print(f"=== QA1 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
