# HERMETIC SEED -- BEFORE the note_organizer import below. Building the
# app calls initialise(), which resolves the data directory and runs the
# data MIGRATIONS, so this script's data directory must be its own by
# then; seeding it before the import leaves no step in between.
# hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to run at all
# outside a scratch run, or beside a notebook it cannot prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

import sys
import time
import note_organizer as NO, tkinter as tk, json, os, re
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import (click as _qa_click, fire as _qa_fire,
                         leaves_nothing_behind as _qa_leaves_nothing_behind,
                         pin_popup_visibility as _qa_pin,
                         waiting_timers as _qa_waiting)
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
# Every copy and paste below goes through the suite's own clipboard: the
# machine's is shared with every program on it, and with its owner.
check('fixture: the clipboard is a stand-in kept in this process',
      bool(app.tk.call('info', 'commands', '::_qa_machine_clipboard'))
      and 'qa_clipboard_selection' in app.tk.eval(
          'info body ::tk::GetSelection')
      and (sys.platform != 'win32'
           or NO.clipboard.write.__name__ == '_write_clipboard'))

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
    return [app.find_note(nid)['title'] for nid in app._card_order()]

for opt, expected in [
    ('Recently updated', ['Cherry', 'Apple', 'Banana']),   # newest updated first
    ('Oldest updated',   ['Banana', 'Apple', 'Cherry']),   # oldest updated first
    ('Title A–Z',        ['Apple', 'Banana', 'Cherry']),
    ('Title Z–A',        ['Cherry', 'Banana', 'Apple']),
    ('Category',         ['Cherry', 'Banana', 'Apple']),   # Alpha, General, Zeta
    ('Calendar: oldest', ['Apple', 'Cherry', 'Banana']),   # 01-05, 02-20, 03-10
    # Nobody has placed these yet: newest made first, where a new note
    # would be looked for.
    ('Custom order',     ['Cherry', 'Apple', 'Banana']),
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
# The value goes into the name: this went red once, in a run while someone
# was typing on the same desktop, and said nothing about what it had found.
check('calculator computes 7x8=56 via real button clicks (display %r)'
      % app._calc_display_var.get(),
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

# The CLICKABLE rows, not every Label in the frame: the list is headed by a
# line of hint text saying what clicking one does, and counting labels
# counted that too. What this check is about is one row per calculation, and
# a row is the thing wired to _calc_insert_formula -- so it is now asked by
# the binding rather than by the widget class, which also stops a second
# explanatory line from breaking it.
history_labels = [w for w in app.calculator_history_frame.winfo_children()
                  if isinstance(w, tk.Label) and '<Button-1>' in w.bind()]
# 5 successful "="es so far this test (7x8, 9-4, 6+6, sqrt9, 3^3) — the
# 5/0 division-by-zero attempt correctly did NOT add an entry.
check('history shows one entry per past calculation', len(history_labels) == 5)
# And the hint itself: a row that inserts into the note on a plain click,
# with nothing saying so, is what this row of the register was about.
_calc_hint = [str(w.cget('text')) for w in
              app.calculator_history_frame.winfo_children()
              if isinstance(w, tk.Label) and '<Button-1>' not in w.bind()]
check('the history says what clicking a line does',
      any('insert' in t.lower() for t in _calc_hint))
# Click the oldest entry (7×8=56) — should insert it, landing after
# whatever's already in the body from earlier insertions in this test.
# A default, so that a missing entry is a red rather than a StopIteration
# that ends qa1 before its footer (it did, once, and took every check
# after it with it).
target_entry = next((w for w in history_labels
                     if str(w.cget('text')) == '7×8=56'), None)
body_before_history_click = app.body_text.get('1.0', 'end')
if target_entry is not None:
    _qa_click(target_entry)
    app.update()
body_after_history_click = app.body_text.get('1.0', 'end')
check('clicking a history entry inserts that exact formula into the note',
      target_entry is not None
      and body_after_history_click.count('7×8=56') == body_before_history_click.count('7×8=56') + 1)

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

# ---- Enter and Backspace where the caret or a selection meets a marker ----
# Home, then Enter, put the new marker in front of the old one ("• • milk").
# Enter over selected words left them in place with a new item cut into
# them. Backspace over a selection ending just after a marker took the
# marker and kept the words. Real keys, pressed and released.
def _list_key(keysym):
    take_focus(app.body_text)
    app.body_text.event_generate(f'<KeyPress-{keysym}>', keysym=keysym,
                                 when='now')
    app.body_text.event_generate(f'<KeyRelease-{keysym}>', keysym=keysym,
                                 when='now')
    app.update()


def _listed(text, kind='bullet'):
    set_body(text)
    select_all_body()
    app._list_buttons[kind].invoke()
    clear_selection()


for _lk_col in (0, 1):
    _listed('milk')
    app.body_text.mark_set('insert', f'1.{_lk_col}')
    _list_key('Return')
    check(f'Enter at column {_lk_col} of a bulleted item leaves an empty item '
          f'above, the words below ({body()!r})',
          body() == '• \n• milk'
          and app._extract_paragraphs(app.body_text)
          == [{'line': 0, 'kind': 'bullet'}, {'line': 1, 'kind': 'bullet'}])
_list_key('Return')
check(f'...and pressed again, a second empty item, no doubled marker ({body()!r})',
      body() == '• \n• \n• milk')
_listed('first', 'number')
app.body_text.mark_set('insert', '1.1')
_list_key('Return')
check(f'Enter inside a number marker: an empty item above, counted ({body()!r})',
      body() == '1. \n2. first')

_listed('milk and eggs')
app.body_text.tag_add('bold', '1.7', '1.11')
app.body_text.edit_reset()
app.body_text.tag_add('sel', '1.7', '1.11')
app.body_text.mark_set('insert', '1.11')
_list_key('Return')
check(f'Enter over selected words in an item replaces them with the new item '
      f'({body()!r})',
      body() == '• milk \n• eggs'
      and not app.body_text.tag_ranges('sel'))
app._body_undo_redo('undo')
app.update()
check(f'...and one Ctrl+Z gives the words back, bold and all ({body()!r})',
      body() == '• milk and eggs'
      and 'bold' in app.body_text.tag_names('1.8'))
_listed('milk')
app.body_text.tag_add('sel', '1.2', '1.6')
app.body_text.mark_set('insert', '1.6')
_list_key('Return')
check(f'Enter over all of an item\'s words keeps its marker: an empty item, '
      f'then the new one ({body()!r})',
      body() == '• \n• ')
_listed('one\ntwo\nthree\nfour', 'number')
app.body_text.tag_add('sel', '2.5', '3.3')
app.body_text.mark_set('insert', '3.3')
_list_key('Return')
check(f'Enter over a selection across numbered items counts them again '
      f'({body()!r})',
      body() == '1. one\n2. tw\n3. three\n4. four')

_listed('milk')
app.body_text.tag_add('sel', '1.2', '1.6')
app.body_text.mark_set('insert', '1.2')
_list_key('BackSpace')
check(f'Backspace over a selection that ends at the marker deletes the words, '
      f'not the marker ({body()!r})',
      body() == '• ')
_listed('milk')
app._set_paragraph_indent(1, 1)
app.body_text.tag_add('sel', '1.2', '1.6')
app.body_text.mark_set('insert', '1.2')
_list_key('BackSpace')
check('...and on a nested item it leaves the depth alone',
      app._paragraph_indent_of(app.body_text, 1) == 1
      and app._list_kind_of(app.body_text, 1) == 'bullet')
_listed('milk\neggs')
app.body_text.mark_set('insert', '1.2')
select_all_body()
_list_key('BackSpace')
check(f'Ctrl+A with the caret after a marker, then Backspace, empties the '
      f'note ({body()!r})', body() == '')

# ---- A delete that reaches a list: renumbered, no marker among the words ----
# Tk's own deletes saw only characters: items 2 and 3 selected and deleted
# left "1. one / 4. four", a letter typed over them "x4. four", BackSpace at
# a line's very start "2. two3. three", a paste over them "zz4. four", and
# nothing renumbered until the next Enter (_list_aware_delete). Each route by
# its real key, and one Ctrl+Z gives the list back for each.
_LD_START = '1. one\n2. two\n3. three\n4. four'


def _ld_list(sel_from, sel_to=None):
    _listed('one\ntwo\nthree\nfour', 'number')
    app.body_text.edit_reset()
    if sel_to:
        app.body_text.tag_add('sel', sel_from, sel_to)
    app.body_text.mark_set('insert', sel_to or sel_from)


def _ld_typed(char):
    take_focus(app.body_text)
    app.body_text.event_generate('<KeyPress>', keysym=char, when='now')
    app.body_text.event_generate('<KeyRelease>', keysym=char, when='now')
    app.update()


def _ld_virtual(name):
    take_focus(app.body_text)
    app.body_text.event_generate(name)
    app.update()


def _ld_clip(text):
    app.body_text.clipboard_clear()
    app.body_text.clipboard_append(text)


for _ld_name, _ld_where, _ld_do, _ld_want in (
        ('BackSpace over items 2 and 3', ('2.0', '4.0'),
         lambda: _list_key('BackSpace'), '1. one\n2. four'),
        ('Delete over items 2 and 3', ('2.0', '4.0'),
         lambda: _list_key('Delete'), '1. one\n2. four'),
        ('Cut over items 2 and 3', ('2.0', '4.0'),
         lambda: _ld_virtual('<<Cut>>'), '1. one\n2. four'),
        ('a letter typed over items 2 and 3', ('2.0', '4.0'),
         lambda: _ld_typed('x'), '1. one\n2. x\n3. four'),
        ('a plain paste over items 2 and 3', ('2.0', '4.0'),
         lambda: (_ld_clip('zz'), _ld_virtual('<<Paste>>')), '1. one\n2. zz\n3. four'),
        ('Ctrl+Shift+V over items 2 and 3', ('2.0', '4.0'),
         lambda: (_ld_clip('zz'), app._paste_plain(), app.update()), '1. one\n2. zz\n3. four'),
        ('BackSpace at the very start of item 3', ('3.0', None),
         lambda: _list_key('BackSpace'), '1. one\n2. twothree\n3. four'),
        ('Delete at the end of item 2', ('2.end', None),
         lambda: _list_key('Delete'), '1. one\n2. twothree\n3. four'),
        ("BackSpace over item 2's marker", ('2.0', '2.3'),
         lambda: _list_key('BackSpace'), '1. one\ntwo\n1. three\n2. four'),
        ("BackSpace from item 2's words into item 3's", ('2.4', '3.5'),
         lambda: _list_key('BackSpace'), '1. one\n2. tree\n3. four'),
        ("BackSpace just after item 3's marker", ('3.3', None),
         lambda: _list_key('BackSpace'), '1. one\n2. two\nthree\n1. four')):
    _ld_list(*_ld_where)
    _ld_do()
    _ld_after = body()
    _ld_paras = app._extract_paragraphs(app.body_text)
    _ld_clipped = app.body_text.clipboard_get() if 'Cut' in _ld_name else None
    app._body_undo_redo('undo')
    app.update()
    check(f'{_ld_name}: renumbered, no marker among the words ({_ld_after!r}), '
          f'and one Ctrl+Z gives the list back ({body()!r})',
          _ld_after == _ld_want and body() == _LD_START
          and [p['line'] for p in _ld_paras]
          == [i for i, line in enumerate(_ld_want.split('\n'))
              if NO.parse_list_marker(line)[0]])
    if _ld_clipped is not None:
        check(f'...and Cut puts on the clipboard what Tk\'s own Cut did '
              f'({_ld_clipped!r})', _ld_clipped == '2. two\n3. three\n')

_ld_list('3.0')
app.body_text.tag_add('bold', '3.3', '3.8')
app.body_text.edit_reset()
_list_key('BackSpace')
_ld_three = body().split('\n')[1].index('three')
check(f'a bold word joined onto the item above stays bold ({body()!r})',
      body() == '1. one\n2. twothree\n3. four'
      and 'bold' in app.body_text.tag_names(f'2.{_ld_three + 1}'))
app._body_undo_redo('undo')
app.update()
check('...and Ctrl+Z puts it back on its own item, still bold',
      body() == _LD_START and 'bold' in app.body_text.tag_names('3.4'))

# The net under every other route: a key that takes lines away renumbers at
# its release. Lines taken by hand between a press and its release stand in
# for a route nobody has named yet.
_ld_list('2.end')
take_focus(app.body_text)
app.body_text.event_generate('<KeyPress-Shift_L>', keysym='Shift_L', when='now')
app.body_text.delete('2.0', '3.0')
app.body_text.event_generate('<KeyRelease-Shift_L>', keysym='Shift_L', when='now')
app.update()
check(f'lines taken away under a key are renumbered at its release ({body()!r})',
      body() == '1. one\n2. three\n3. four')

# ---- A click on a marker puts the caret after it (the owner's call) ----
# Before it, a letter typed made "x2. two", a line that is no item any more.
_ld_list('2.1')
_qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
app.update()
_cm_on = app.body_text.index('insert')
_ld_typed('x')
check(f'a click on a marker puts the caret after it, and what is typed joins the item '
      f'(caret {_cm_on}; {body()!r})',
      _cm_on == '2.3' and body() == '1. one\n2. xtwo\n3. three\n4. four')
_ld_list('2.5')
_qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
app.update()
_cm_words = app.body_text.index('insert')
_ld_list('2.0', '2.2')
_qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
app.update()
check(f'...while a click in the words, or one that selects the marker, stays where it is '
      f'(caret {_cm_words}; selection {[str(i) for i in app.body_text.tag_ranges("sel")]})',
      _cm_words == '2.5' and [str(i) for i in app.body_text.tag_ranges('sel')] == ['2.0', '2.2'])
app.body_text.tag_remove('sel', '1.0', 'end')

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

# A size or a font set under drawn tables lands on the words selected, and
# stays there. The span ends are worked out without the tables' windows
# (_char_offset) and were laid back with "1.0+Nc", which counts each window
# as a character: the run landed one character early per table above it,
# and every later size or font moved the earlier ones again -- saved so.
set_body('AB' + chr(10) + '| a | b |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |' + chr(10) + 'hello world' + chr(10) + '| c | d |'
         + chr(10) + '| --- | --- |' + chr(10) + '| 3 | 4 |' + chr(10)
         + 'tail words')
app._render_table_grids()
app.update()
_ft_windows = len(app.body_text.window_names())
for _ft_word, _ft_style, _ft_value in (('hello', 'font_size', 16),
                                       ('tail', 'font_family', 'Georgia'),
                                       ('hello', 'font_size', 20)):
    _ft_at = app.body_text.search(_ft_word, '1.0', 'end')
    select(_ft_at, f'{_ft_at}+{len(_ft_word)}c')
    app._apply_body_font(_ft_style, _ft_value)
    clear_selection()
_ft_text = app.body_text.get('1.0', 'end-1c')
_ft_got = sorted((_ft_text[s['start']:s['end']], s['style'], s.get('value'))
                 for s in app._extract_formatting(app.body_text))
check(f'a size or a font set under drawn tables lands on the words selected, '
      f'and stays there ({_ft_got})',
      _ft_windows == 2
      and _ft_got == [('hello', 'font_size', 20),
                      ('tail', 'font_family', 'Georgia')])

# The way back from a saved offset to a place in the text, with tables drawn
# at the top, in the middle and at the end, and an emoji in a cell and in
# the prose: every offset comes back as itself (_char_offset), and with no
# table in the text every place is the one "1.0+Nc" gives.
_oi_table = ['| a ' + chr(0x1F600) + ' | b |', '| --- | --- |', '| 1 | 2 |']
_oi_prose = ['H' + chr(233) + 'llo ' + chr(0x1F600) + ' done', '',
             chr(9) + 'Tabbed ' + chr(0x4E2D) + ' line', 'plain']
set_body(chr(10).join(_oi_prose))
_oi_where = app._offset_indices(app.body_text, range(60))
_oi_same = all(app.body_text.index(_oi_where[o])
               == app.body_text.index(f'1.0+{o}c') for o in range(60))
set_body(chr(10).join(_oi_table + _oi_prose + _oi_table + ['mid']
                      + _oi_table))
app._render_table_grids()
app.update()
_oi_len = len(app.body_text.get('1.0', 'end-1c'))
_oi_where = app._offset_indices(app.body_text, range(_oi_len + 1))
_oi_off = [o for o in range(_oi_len + 1)
           if app._char_offset(app.body_text, _oi_where[o]) != o]
check(f'every saved offset finds its own place with no table drawn and with '
      f'three ({len(app.body_text.window_names())} drawn; off at {_oi_off[:5]})',
      _oi_same and len(app.body_text.window_names()) == 3 and not _oi_off)

# Laying a note's spans walks its text once a pass (the plain styles, then
# the font runs), not once a span. Each span end was found with "1.0+Nc"
# from the top of the note, so the walk grew with the note's size times its
# spans: Enter in a numbered list of a note of 8,000 styled words took 3.6 s
# (the renumber lays every span again), and its open 1.4-1.7 s. Counted,
# not timed: every "+Nc" the body is asked for, added up.
_wk_body = chr(10).join('%03d %s' % (i, 'word ' * 10) for i in range(300))
_wk_spans = []
for _wk_i in range(0, len(_wk_body) - 8, 29):
    _wk_spans.append({'start': _wk_i, 'end': _wk_i + 4,
                      'style': ('bold', 'italic', 'underline')[_wk_i % 3]})
    if _wk_i % 5 == 0:
        _wk_spans.append({'start': _wk_i, 'end': _wk_i + 6,
                          'style': 'font_size', 'value': 16})
set_body(_wk_body)
_wk_walked = [0]


def _wk_trace(command, *_op):
    _wk_walked[0] += sum(int(n) for n in re.findall(r'\+(\d+)c', command))


app.tk.createcommand('qa_walk_trace', _wk_trace)
app.tk.call('trace', 'add', 'execution', app.body_text._w, 'enter',
            'qa_walk_trace')
try:
    app._apply_formatting(app.body_text, _wk_spans)
finally:
    app.tk.call('trace', 'remove', 'execution', app.body_text._w, 'enter',
                'qa_walk_trace')
    app.tk.deletecommand('qa_walk_trace')
_wk_back = sorted((s['start'], s['end'], s['style'])
                  for s in app._extract_formatting(app.body_text))
check(f'laying a note of {len(_wk_spans)} spans walks its '
      f'{len(_wk_body)} characters once a pass ({_wk_walked[0]} walked)',
      _wk_walked[0] <= 3 * len(_wk_body)
      and _wk_back == sorted((s['start'], s['end'], s['style'])
                             for s in _wk_spans))
set_body('')

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
_bold_top = app._fmt_bar.winfo_rooty()
set_body('')
app.update_word_count()
app.update()
check('an empty note shows no readout at all',
      str(app.word_count_lbl.cget('text')) == '')
# The readout's two lines set its row's height, and the toolbar under it
# jumped up when they went -- as the note on screen went to the Trash.
check('...and the toolbar under it stays where it was',
      app._fmt_bar.winfo_rooty() == _bold_top)

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
# The field's form, DD.MM.YYYY: the order a typed date is read in.
_PH_DATE = NO.DATE_FORM
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
      _shown and _text == f'{_CAP}/{_CAP}' and _fg == app.colors['danger_text'])
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
    # table gluing itself onto the "Source:" line shipped unseen.
    if loopback:
        # Wrapped as Windows keeps it and cut as read_html cuts it: our own
        # copy is known by its fragment coming back exactly as written.
        NO.clipboard.read_html = lambda: (NO.clipboard.fragment_of(
            NO.clipboard._wrap_html(_written['html']).decode('utf-8'))
            if _written.get('html') else None)
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


def _menu_invoke(m, label):
    """Press the entry a person would, wherever its cascade put it."""
    for i in range(m.index('end') + 1):
        kind = m.type(i)
        if kind == 'command' and m.entrycget(i, 'label') == label:
            m.invoke(i)
            return True
        if kind == 'cascade':
            try:
                sub = m.nametowidget(m.entrycget(i, 'menu'))
            except Exception:
                continue
            if _menu_invoke(sub, label):
                return True
    return False



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

# ---- A PASTE THE CAPS CUT SAYS SO ----
# The formatted paste keeps at most MAX_PASTE_CHARS characters and
# MAX_PASTE_SPANS styles. Past them it cut without a word, and the rest of
# a long article was simply not in the note. The notice comes once the
# paste's own work is done (after idle), and its advice -- Ctrl+Z, then
# Ctrl+Shift+V -- has to really bring all of it in.
_cut_told = []
_cut_real_info = app.show_info
app.show_info = lambda title, message, **k: _cut_told.append((title, message))
try:
    _cut_long = 'x' * (NO.MAX_PASTE_CHARS + 500)
    set_body('before ')
    app.body_text.mark_set('insert', 'end-1c')
    app.body_text.edit_separator()
    _stub_clipboard(html='<p>' + _cut_long + '</p>', text=_cut_long)
    app._on_body_paste()
    _cut_inside = list(_cut_told)
    app.update()
    check(f'a paste cut at the character cap says so, once the paste is done '
          f'({[t for t, _m in _cut_told]}, inside: {len(_cut_inside)})',
          _cut_inside == [] and len(_cut_told) == 1
          and _cut_told[0][0] == 'Pasted in part'
          and f'{NO.MAX_PASTE_CHARS:,}' in _cut_told[0][1]
          and 'a note of its own' in _cut_told[0][1])
    check(f'...and the note holds what it says was pasted ({len(body())} chars)',
          body() == 'before ' + 'x' * NO.MAX_PASTE_CHARS)
    _cut_told.clear()
    app._body_undo_redo('undo'); app.update()
    check(f'Ctrl+Z takes the cut paste back whole ({body()[:12]!r}...)',
          body() == 'before ')
    # Ctrl+Shift+V has the same ceiling (the owner's choice, 2026-10-27):
    # one line of 600,000 characters took ten seconds at every key.
    take_focus(app.body_text)
    app.body_text.event_generate('<Control-Shift-V>')
    app.update()
    check(f'...and Ctrl+Shift+V keeps the same ceiling, and says so '
          f'({len(body())} chars, {[t for t, _m in _cut_told]})',
          body() == 'before ' + 'x' * NO.MAX_PASTE_CHARS
          and [t for t, _m in _cut_told] == ['Pasted in part'])
    _cut_told.clear()

    set_body('')
    _stub_clipboard(html='<p>x</p>' + '<p><b>x</b></p>' * (NO.MAX_PASTE_SPANS + 5))
    app._on_body_paste()
    app.update()
    check(f'a paste whose styles pass their cap says the formatting stops '
          f'({[t for t, _m in _cut_told]})',
          len(_cut_told) == 1 and 'formatting stops' in _cut_told[0][1]
          and f'{NO.MAX_PASTE_SPANS:,}' in _cut_told[0][1])
    _cut_told.clear()

    set_body('')
    _stub_clipboard(html='<p>A <b>bold</b> word</p>')
    app._on_body_paste()
    app.update()
    check(f'an ordinary formatted paste says nothing ({_cut_told})',
          _cut_told == [] and body() == 'A bold word')
finally:
    app.show_info = _cut_real_info
set_body('')

# Bold and italic as a web page writes them reach the note by the real
# paste route (field pass: they arrived plain) -- semibold 600 and an
# oblique slant, the spellings the reader did not know.
_stub_clipboard(html='<p>A <span style="font-weight:600">semi</span> and '
                     '<span style="font-style:oblique">slant</span> word</p>',
                text='A semi and slant word')
app._on_body_paste()
app.update()
_wpS = {(s['style'], s['start'], s['end'])
        for s in app._extract_formatting(app.body_text)}
check(f'bold and italic from a web page arrive by the real paste ({_wpS})',
      body() == 'A semi and slant word'
      and ('bold', 2, 6) in _wpS and ('italic', 11, 16) in _wpS)
_stub_clipboard()
set_body('')

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

# A table past what is drawn stays its text. Drawn, every cell was made at
# once: a 300x300 table froze the app for 40 s, and a 1,000-row one passed
# the 32,767-pixel canvas and killed it on Linux. Either limit keeps it text.
import time as _tb_time
for _tb_rows, _tb_cols, _tb_drawn in ((401, 2, False), (100, 31, False), (40, 5, True)):
    _tb_lines = (['| ' + ' | '.join('h%d' % c for c in range(_tb_cols)) + ' |',
                  '|' + '---|' * _tb_cols]
                 + ['| ' + ' | '.join('%d' % r for _c in range(_tb_cols)) + ' |'
                    for r in range(_tb_rows - 2)])
    _tb_started = _tb_time.time()
    set_body('Big\n' + '\n'.join(_tb_lines) + '\nafter')
    app._render_table_grids(); app.update()
    _tb_took = _tb_time.time() - _tb_started
    check(f'a {_tb_rows}x{_tb_cols} table is {"drawn" if _tb_drawn else "kept as its text"} '
          f'({_tb_took:.2f} s)',
          (app._grid_at_line(2) is not None) == _tb_drawn
          and body().split('\n')[1] == _tb_lines[0])
set_body('')

# What Excel writes: its markers inside the table -- for one row, around the
# cells -- so the fragment alone was cells with no row, and a row copied
# from Excel pasted as loose text, "The" and "app open on the phone." on
# lines of their own (the owner, 2026-10-25). Cut as read_html cuts it.
_xl_doc = ('Version:1.0\r\nStartHTML:0000000105\r\nEndHTML:0000000999\r\n'
           'StartFragment:0000000500\r\nEndFragment:0000000700\r\n\r\n'
           '<html xmlns:x="urn:schemas-microsoft-com:office:excel">\r\n<head>\r\n'
           '<style>\r\n<!--table\r\n\t{mso-displayed-decimal-separator:"\\.";}\r\n'
           '-->\r\n</style>\r\n</head>\r\n<body link=blue vlink=purple>\r\n'
           "<table border=0 cellpadding=0 cellspacing=0 width=308>\r\n"
           " <col width=73 style='width:55pt'>\r\n"
           " <tr height=140 style='height:105.0pt'>\r\n<!--StartFragment-->\r\nCELLS\r\n"
           '<!--EndFragment-->\r\n </tr>\r\n</table>\r\n</body>\r\n</html>')
_stub_clipboard(html=NO.clipboard.fragment_of(_xl_doc.replace(
    'CELLS', "  <td height=140 class=xl66 align=left width=73>High</td>\r\n"
             "  <td class=xl65 align=left width=235 style='border-left:none'>The\r\n"
             "  app open on the phone.</td>")),
    text='High\tThe app open on the phone.\r\n')
set_body('')
app._on_body_paste()
app.update()
_xl_lines = body().split('\n')
check(f'a row copied from Excel pastes as a table row, its words whole ({_xl_lines!r})',
      core_tables.split_row(_xl_lines[0]) == ['High', 'The app open on the phone.']
      and app._grid_at_line(1) is not None)
_stub_clipboard(html=NO.clipboard.fragment_of(_xl_doc.replace(
    'CELLS', "  <td height=140 class=xl66 align=left width=73>rent</td>")), text='rent\r\n')
set_body('')
app._on_body_paste()
app.update()
check(f'one cell copied from Excel pastes as its word, no pipes ({body()!r})',
      body().strip('\n') == 'rent')
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
                      "<tr><th rowspan='2'>No</th>"
                      "<th colspan='2'>Cable</th></tr>"
                      '<tr><th>Vodafone</th><th>Digi</th></tr>'
                      '<tr><td>1.</td><td>yes</td><td>no</td></tr>'
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
_e.insert('1.0', 'New Cable')
app._commit_cell_editor()
app.update()
check(f'editing a merge anchor keeps the merge ({lines_now()[0]!r})',
      core_tables.split_row(lines_now()[0]) == ['No', 'New Cable', '<']
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
app._grid_merge_with(_t, 0, 1, 'left')
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

# ---- MERGE AND INSERT FROM A CELL'S MENU, PRESSED AS A PERSON DOES ----
# "Merge with cell to the left / above" wrote a merge marker over the
# clicked cell, and its text was gone. "Insert row above" on the header
# pushed the header down past the separator, which stopped being one: the
# header became data and the dashes a row of content.
def _press_cell_menu(r, c, label):
    info = app._grid_at_line(1)
    app._grid_clear_selection()
    cell = info['cells'][(r, c)]
    posted = []
    real_popup = NO.tk.Menu.tk_popup
    NO.tk.Menu.tk_popup = lambda _m, *a, **k: posted.append(_m)
    try:
        app._grid_menu(info, type('E', (), {
            'x': int(cell['x'] + 12), 'y': int(cell['y'] + 6),
            'x_root': 0, 'y_root': 0})())
        pressed = bool(posted) and _menu_invoke(posted[-1], label)
    finally:
        NO.tk.Menu.tk_popup = real_popup
    app.update()
    return pressed


_cm_table = chr(10).join(['| Name | Qty | Note |', '| --- | --- | --- |',
                          '| apple | 3 | ripe |', '| pear | 5 | soft |'])
set_body(_cm_table)
app._render_table_grids()
app.update()
app.body_text.edit_reset()
check('the cell menu offers Merge with cell to the left',
      _press_cell_menu(1, 1, 'Merge with cell to the left'))
check(f'merging with the cell to the left keeps both texts ({lines_now()[2]!r})',
      core_tables.split_row(lines_now()[2]) == ['apple 3', '<', 'ripe'])
app._body_undo_redo('undo')
app.update()
check(f'...and one Ctrl+Z gives both cells back ({lines_now()[2]!r})',
      core_tables.split_row(lines_now()[2]) == ['apple', '3', 'ripe'])
check('the cell menu offers Merge with cell above',
      _press_cell_menu(2, 1, 'Merge with cell above'))
check(f'merging with the cell above keeps both texts ({lines_now()[2:4]!r})',
      core_tables.split_row(lines_now()[2]) == ['apple', '3 5', 'ripe']
      and core_tables.split_row(lines_now()[3]) == ['pear', '^', 'soft'])
# A neighbour that is itself merged is swallowed whole, as a selection
# reaching into it would be: merging "pear" up into the wide cell above
# takes in the whole width of that cell.
app._body_undo_redo('undo')
app.update()
_press_cell_menu(1, 1, 'Merge with cell to the left')
_press_cell_menu(2, 0, 'Merge with cell above')
check(f'merging up into a wide cell swallows all of it ({lines_now()[2:4]!r})',
      core_tables.split_row(lines_now()[2]) == ['apple 3 pear 5', '<', 'ripe']
      and core_tables.split_row(lines_now()[3]) == ['^', '<', 'soft'])
# The other door into the same menu: a right-click inside a cell being
# written in, which commits the typed word first. That word was the one
# the old merge wrote over.
set_body(_cm_table)
app._render_table_grids()
app.update()
_cm_info = app._grid_at_line(1)
app._open_cell_editor(_cm_info, 1, 1)
_cm_e = app._cell_editor['entry']
_cm_e.delete('1.0', 'end')
_cm_e.insert('1.0', 'seven')
_cm_posted = []
_cm_real_popup = NO.tk.Menu.tk_popup
NO.tk.Menu.tk_popup = lambda _m, *a, **k: _cm_posted.append(_m)
try:
    app._editor_context_menu(_cm_info, type('E', (), {
        'x': 0, 'y': 0, 'x_root': 0, 'y_root': 0})())
    _cm_pressed = (bool(_cm_posted)
                   and _menu_invoke(_cm_posted[-1], 'Merge with cell to the left'))
finally:
    NO.tk.Menu.tk_popup = _cm_real_popup
app.update()
check(f'typed in a cell, then merged left from its own menu: the typed word '
      f'stays ({lines_now()[2]!r})',
      _cm_pressed
      and core_tables.split_row(lines_now()[2]) == ['apple seven', '<', 'ripe'])
# Enter over words selected in an open cell replaces them, as it does
# anywhere else; the cell's own Enter put the line break in and left them.
set_body(_cm_table)
app._render_table_grids()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 2)
_cm_e = app._cell_editor['entry']
_cm_e.delete('1.0', 'end')
_cm_e.insert('1.0', 'very ripe now')
_cm_e.tag_add('sel', '1.5', '1.10')
_cm_e.mark_set('insert', '1.10')
app._editor_newline()
app._commit_cell_editor()
app.update()
_cm_cell = core_tables.split_row(lines_now()[2])[2]
check(f'Enter over words selected in a cell replaces them with the line '
      f'break ({_cm_cell!r})',
      'ripe' not in _cm_cell and 'very' in _cm_cell and 'now' in _cm_cell
      and '<br>' in _cm_cell)
# Bold over two cells keeps the italic one italic: the cells got one
# answer for both styles, and the italic went.
set_body(_cm_table)
app._render_table_grids()
app.update()
_cm_info = app._grid_at_line(1)
app._grid_apply_style(_cm_info, (1, 1, 1, 1), 'italic')
app.update()
_cm_info = app._grid_at_line(1)
app._grid_apply_style(_cm_info, (1, 0, 1, 1), 'bold')
app.update()
_cm_info = app._grid_at_line(1)
_cm_paint = [(app._grid_cell_paint(_cm_info, 1, c)['bold'],
              app._grid_cell_paint(_cm_info, 1, c)['italic']) for c in (0, 1)]
check(f'Bold over two cells keeps the italic one italic ({_cm_paint})',
      _cm_paint == [(True, False), (True, True)])

set_body(_cm_table)
app._render_table_grids()
app.update()
check('the header\'s menu offers Insert row above',
      _press_cell_menu(0, 0, 'Insert row above'))
_cm_lines = lines_now()
check(f'Insert row above on the header puts the row under it ({_cm_lines[:4]!r})',
      core_tables.split_row(_cm_lines[0]) == ['Name', 'Qty', 'Note']
      and core_tables.separator_index(_cm_lines[:4]) == 1
      and core_tables.split_row(_cm_lines[2]) == ['', '', '']
      and core_tables.split_row(_cm_lines[3]) == ['apple', '3', 'ripe'])
set_body(chr(10).join(['| a | b |', '| c | d |']))
app._render_table_grids()
app.update()
_press_cell_menu(0, 0, 'Insert row above')
check(f'...while a table with no header still gets it on top ({lines_now()[:3]!r})',
      core_tables.split_row(lines_now()[0]) == ['', '']
      and core_tables.split_row(lines_now()[1]) == ['a', 'b'])
set_body('')

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
set_body('see \U0001F600ok maybe')
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

# A highlight given inside an open cell shows at once, over the whole cell,
# and the drawn cell wears it when the editor closes. Field-reported: it
# appeared only after the cell was opened again.
_t = app._grid_at_line(1)
app._open_cell_editor(_t, 1, 0)
_hl_e = app._cell_editor['entry']
_hl_e.tag_add('sel', '1.0', '1.1')
app._apply_body_color('highlight', '#ffe08a')
app.update()
_hl_want = app._blend_hex('#ffe08a', app.colors['card'], 0.45).lower()
_hl_open = str(_hl_e.cget('bg')).lower()
app._commit_cell_editor()
app.update()
_t = app._grid_at_line(1)
_hl_fill = str(_t['canvas'].itemcget(_t['cells'][(1, 0)]['rect'], 'fill')).lower()
check(f'a highlight given in an open cell colours the whole cell at once '
      f'({_hl_open} / {_hl_want})', _hl_open == _hl_want)
check(f'...and the drawn cell wears it as soon as the editor closes, with no '
      f'reopen ({_hl_fill})', _hl_fill == _hl_want)
app._open_cell_editor(_t, 1, 1)
app._cell_editor['entry'].tag_remove('sel', '1.0', 'end')   # it opens selected
app._apply_body_color('highlight', '#c8f0d0')   # nothing selected this time
app.update()
_hl_want = app._blend_hex('#c8f0d0', app.colors['card'], 0.45).lower()
_hl_open = str(app._cell_editor['entry'].cget('bg')).lower()
app._commit_cell_editor()
app.update()
_t = app._grid_at_line(1)
_hl_fill = str(_t['canvas'].itemcget(_t['cells'][(1, 1)]['rect'], 'fill')).lower()
check(f'...with nothing selected too: the whole cell takes it at once and keeps '
      f'it on close ({_hl_open} / {_hl_fill} / {_hl_want})',
      _hl_open == _hl_want and _hl_fill == _hl_want)

# Over a drawn table the pointer is a pointer, not an I-beam.
check(f'the table shows an arrow cursor '
      f'({_t["canvas"].cget("cursor")!r})',
      str(_t['canvas'].cget('cursor')) == 'arrow')

# The right and bottom rules are inside the canvas, not one pixel past it.
check('the outer rules fit inside the drawn area',
      int(_t['canvas'].cget('scrollregion').split()[2]) == _t['natural'] + 1)

# ---- CELL ALIGNMENT, AND THE TABLE THAT JUMPED TO THE MIDDLE ----
set_body('')
_stub_clipboard(html='<table><tr><td>Heading</td><td>B</td></tr>'
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
_e9.insert('1.0', 'Heading')
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
app._grid_cell_clip = [['OLD', 'STALE']]
_t9 = app._grid_at_line(_first9)
app._grid_copy_cell(_t9, 0, 0)
app._grid_paste_cells(_t9, 1, 0)
app.update()
_t9 = app._grid_at_line(_first9)
check(f'a fresh single-cell copy is what pastes '
      f'({_t9["cells"][(1, 0)]["value"]!r})',
      _t9['cells'][(1, 0)]['value'] == 'Heading')
app._grid_cell_clip = [['REMEMBERED']]
app.clipboard_clear()
app.clipboard_append('EXTERNAL\tNEW')
app._grid_paste_cells(_t9, 1, 0)
app.update()
_t9 = app._grid_at_line(_first9)
check('a newer system clipboard outranks the remembered matrix',
      _t9['cells'][(1, 0)]['value'] == 'EXTERNAL'
      and _t9['cells'][(1, 1)]['value'] == 'NEW')

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
app.clipboard_append('OLD FROM LAST WEEK')
_stub_clipboard(html='<table><tr><td>One</td><td>Two</td></tr>'
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
      _tX['cells'][(1, 0)]['value'] == 'One'
      and _tX['cells'][(1, 1)]['value'] == 'Two')
check('nothing lands outside the table',
      len(body().split('\n')) == _linesX
      and 'OLD' not in body())

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
      _tX['cells'][(1, 0)]['value'] == 'One'
      and _tX['cells'][(1, 1)]['value'] == 'Two')

# The editor grows with its content instead of hiding the overflow.
app._open_cell_editor(_tX, 1, 0)
app.update()
take_focus(app._cell_editor['entry'])  # a precondition for the keys below
_edX = app._cell_editor
_w0 = int(float(_tX['canvas'].itemcget(_edX['win'], 'width')))
_edX['entry'].delete('1.0', 'end')
_edX['entry'].insert('1.0', 'a much longer value than the column started out with')
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
_edX['entry'].insert('1.0', 'an edit that visibly widens the column')
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
set_body('a line of text\n' * 30)
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
      f'(found {_lineU.count(chr(0x1F600))})',
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
_eU.insert('1.0', 'neighbour')
app._commit_cell_editor()
app.update()
_tU = app._grid_at_line(1)
check(f'the cell after an emoji is written where it belongs '
      f'({_tU["cells"][(0, 1)]["value"]!r})',
      _tU['cells'][(0, 0)]['value'].count(chr(0x1F600)) == 2
      and _tU['cells'][(0, 1)]['value'] == 'neighbour')

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

# An emoji put into a checkbox cell takes the box's place: beside it, the
# cell stopped being a checkbox and showed "[ ]" (field pass). Both roads
# in -- the cell's own menu item and the toolbar button.
for _cbRoad in ('menu', 'toolbar'):
    set_body('| h1 | h2 |' + chr(10) + '| --- | --- |' + chr(10)
             + '| [ ] | x |')
    app._render_table_grids()
    app.update()
    app._open_cell_editor(app._grid_at_line(1), 1, 0, select=False)
    app.update()
    if _cbRoad == 'menu':
        app._show_emoji_picker(app._cell_editor['entry'])
    else:
        app._insert_emoji_from_toolbar()
    app.update()
    _cbChips = [l for l in _walk_widgets(app._mini_popup, tk.Label)
                if str(l.cget('cursor')) == 'hand2'
                and str(l.cget('text')).strip()]
    _cbEmoji = str(_cbChips[0].cget('text')).strip() if _cbChips else '?'
    if _cbChips:
        _qa_click(_cbChips[0])
        app.update()
    # The open cell shows the emoji alone, never beside brackets.
    _cbShown = app._cell_editor['entry'].get('1.0', 'end-1c')
    app._dismiss_mini_popup()
    app._commit_cell_editor()
    app.update()
    _cbVal = app._grid_at_line(1)['cells'][(1, 0)]['value']
    check(f'an emoji replaces a checkbox, no brackets left ({_cbRoad}: '
          f'{_cbShown!r} -> {_cbVal!r})', _cbVal == _cbEmoji == _cbShown)
    # And deleting it leaves an empty cell, never the old box.
    app._open_cell_editor(app._grid_at_line(1), 1, 0)
    app.update()
    app._cell_editor['entry'].delete('1.0', 'end')
    app._commit_cell_editor()
    app.update()
    _cbVal = app._grid_at_line(1)['cells'][(1, 0)]['value']
    check(f'and deleting the emoji leaves the cell empty ({_cbRoad}: '
          f'{_cbVal!r})', _cbVal == '')
# An open checkbox cell shows no brackets at all, by any way in: it opens
# empty (field pass -- "[ ]" showed until something replaced it). Left
# empty, the box stays, colour and all; a text cell opens with its words.
set_body('| h1 | h2 |' + chr(10) + '| --- | --- |' + chr(10) + '| [x] | word |')
app._render_table_grids()
app.update()
_cbLine = app.body_text.get('3.0', '3.end')
_cbAt = _cbLine.index('[x]')
app.body_text.tag_add(
    app._ensure_color_tag(app.body_text, 'text_color', '#d32f2f'),
    '3.%d' % _cbAt, '3.%d' % (_cbAt + 3))
app._render_table_grids()
app.update()
_cbOpen = {}
app._open_cell_editor(app._grid_at_line(1), 1, 0)     # Edit cell as text
app.update()
_cbOpen['edit as text'] = app._cell_editor['entry'].get('1.0', 'end-1c')
app._commit_cell_editor()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 1)     # then Shift+Tab back
app.update()
_cbOpen['text cell'] = app._cell_editor['entry'].get('1.0', 'end-1c')
app._editor_step(-1)
app.update()
_cbOpen['Shift+Tab'] = (app._cell_editor['entry'].get('1.0', 'end-1c')
                        if app._cell_editor else None)
app._commit_cell_editor()
app.update()
_cbKept = app._grid_at_line(1)['cells'][(1, 0)]['value']
_cbTint = app.body_text.tag_names('3.%d' % (_cbAt + 1))
check(f'a checkbox cell opens empty by every way in, a text cell with its '
      f'words, and a box left empty stays the box it was ({_cbOpen}; '
      f'{_cbKept!r})',
      _cbOpen == {'edit as text': '', 'text cell': 'word', 'Shift+Tab': ''}
      and _cbKept == '[x]' and 'text_color_d32f2f' in _cbTint)
# Whatever goes in takes the box's place, by every road -- Windows' own
# emoji panel (Win+.) and a paste arrive as typed text. A cell that was
# never a box keeps "[ ]" typed into it as the words they are.
_cbRoads = {}
for _cbName, _cbAdd, _cbFrom in (
        ('Win+. emoji', chr(0x1F600), '[x]'),
        ('typed words', ' buy milk', '[ ]')):
    set_body('| h1 | h2 |' + chr(10) + '| --- | --- |' + chr(10)
             + '| %s | x |' % _cbFrom)
    app._render_table_grids()
    app.update()
    app._open_cell_editor(app._grid_at_line(1), 1, 0, select=False)
    app.update()
    _cbE = app._cell_editor['entry']
    _cbE.insert('end', _cbAdd)
    app._commit_cell_editor()
    app.update()
    _cbRoads[_cbName] = app._grid_at_line(1)['cells'][(1, 0)]['value']
set_body('| h1 | h2 |' + chr(10) + '| --- | --- |' + chr(10) + '|   | x |')
app._render_table_grids()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 0)
app.update()
app._cell_editor['entry'].insert('end', '[ ] my words')
app._commit_cell_editor()
app.update()
_cbRoads['typed into a plain cell'] = app._grid_at_line(1)['cells'][(1, 0)]['value']
check(f'whatever goes into a box takes its place, by every road '
      f'({_cbRoads})',
      _cbRoads == {'Win+. emoji': chr(0x1F600), 'typed words': 'buy milk',
                   'typed into a plain cell': '[ ] my words'})
set_body('')

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

# ---- A PASTED MARKDOWN TABLE SIZES TO WHAT IT HOLDS ----
# Markdown spells a right-aligned column "---:", four characters, and the
# app reads a separator cell over three as a width set by hand: a table
# pasted from a chat or a .md file drew its column four wide, the header
# cut to "How...". Every route a paste from elsewhere takes spells the
# separator at markdown's minimum; the app's own copy keeps its widths.
_mdP = '| What | How much |\n| --- | ---: |\n| rent | 1500 |'


def _pasted_widths():
    # The last separator in the note: the pasted table's, where one was
    # being typed above it.
    found = None
    for line in body().split('\n'):
        if core_tables.is_separator_row(line):
            found = [c['width'] for c in core_tables.parse_separator(line)]
    return found


def _drawn_header(first_line):
    app._render_table_grids()
    app.update()
    grid = app._grid_at_line(first_line)
    if grid is None:
        return None
    return ''.join(grid['canvas'].itemcget(t, 'text')
                   for t in grid['cells'][(0, 1)]['texts'])


set_body('')
_stub_clipboard(html=None, text=_mdP)
check('a plain markdown table is pasted by the app, not by Tk',
      app._on_body_paste() == 'break')
app.update()
check(f'...its "---:" keeps the colon and loses the width ({_pasted_widths()}, '
      f'{body().split(chr(10))[1]!r})',
      _pasted_widths() == [None, None] and '--:' in body().split('\n')[1])
check(f'...and its header is drawn whole ({_drawn_header(1)!r})',
      _drawn_header(1) == 'How much')

set_body('')
_stub_clipboard(html=None, text='Costs:\n' + _mdP + '\nThat is all.')
check('a table in the middle of pasted text takes the app\'s route too',
      app._on_body_paste() == 'break')
app.update()
check(f'...the same widths forgotten ({_pasted_widths()}), the words around it kept',
      _pasted_widths() == [None, None] and body().startswith('Costs:\n| What')
      and body().endswith('That is all.'))
app._body_undo_redo('undo'); app.update()
check(f'...and one Ctrl+Z takes the whole paste back ({body()!r})', body() == '')

# Pasted from inside a table still being typed, the app makes the paste
# itself (_paste_text_leaving_table), and forgets the widths there too.
set_body('Intro\n| Item name | Qty |\n| --- | --- |\n| Tea | 2 |\nend line')
app.body_text.mark_set('insert', '4.end')
app._last_caret_line = None
_typedP = app._row_being_typed()
_stub_clipboard(html=None, text='\nPrices:\n' + _mdP + '\nthat is all')
app._on_body_paste()
app.update()
check(f'a paste out of a table being typed forgets them as well '
      f'(typed row {_typedP}, {_pasted_widths()})',
      _typedP == 4 and _pasted_widths() == [None, None]
      and sum(core_tables.is_separator_row(l) for l in body().split('\n')) == 2
      and 'Prices:' in body())

set_body('')
_stub_clipboard(html='<p>| What | How much |</p><p>| :------: | ---: |</p>'
                     '<p>| <b>rent</b> | 1500 |</p>',
                text=_mdP)
app._on_body_paste()
app.update()
_mdS = {(s['style'], body()[s['start']:s['end']])
        for s in app._extract_formatting(app.body_text)}
check(f'a markdown table arriving as a web page\'s text forgets its widths too '
      f'({_pasted_widths()}), its bold kept on its word ({_mdS})',
      _pasted_widths() == [None, None] and ('bold', 'rent') in _mdS)

set_body('')
_stub_clipboard(html='<p>x</p>', text=_mdP)
take_focus(app.body_text)
app.body_text.event_generate('<Control-Shift-V>')
app.update()
check(f'Ctrl+Shift+V forgets them as well ({_pasted_widths()})',
      _pasted_widths() == [None, None] and 'How much' in body())

# The template editor's body is a plain box of its own, with its own paste.
_tplT = NO.tk.Text(app.body_text.winfo_toplevel())
_stub_clipboard(html=None, text=_mdP)
_tplR = app._paste_table_aware(_tplT)
check(f'a template\'s body takes a pasted markdown table the same way '
      f'({_tplT.get("1.0", "end-1c").split(chr(10))[1:2]})',
      _tplR == 'break'
      and _tplT.get('1.0', 'end-1c').split('\n')[1] == '| --- | --: |')
_tplT.destroy()
_stub_clipboard(html=None, text='just words')
_tplT = NO.tk.Text(app.body_text.winfo_toplevel())
check('...and leaves words without a table to the normal paste',
      app._paste_table_aware(_tplT) is None)
_tplT.destroy()

# Our own copy: the dashes are a width set here, and come back as they went.
set_body('| What | How much |\n| ------------ | --------: |\n| rent | 1500 |')
app.update()
_stub_clipboard(loopback=True)
app.body_text.tag_add('sel', '1.0', 'end-1c')
app._copy_formatted()
app.body_text.tag_remove('sel', '1.0', 'end')
set_body('')
app._on_body_paste()
app.update()
check(f'a table copied from a note keeps its set widths ({_pasted_widths()})',
      _pasted_widths() == [12, 9])
set_body('')
NO.clipboard.read_html = lambda: None
app._on_body_paste()
app.update()
check(f'...by the plain route as well ({_pasted_widths()})',
      _pasted_widths() == [12, 9])
_stub_clipboard()
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
    # Every right-click builds its menu anew; none was ever destroyed.
    # The hidden column's stub menu above and these three leave one.
    _left_menus = [w for w in app.winfo_children() if isinstance(w, NO.tk.Menu)]
    check('the table\'s right-click menus leave one menu behind, not one '
          'each (%d)' % len(_left_menus), len(_left_menus) <= 1)
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
app._cell_editor['entry'].insert('1.0', 'a text much wider than the column')
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
      _freshR['cells'][(1, 0)]['value'].startswith('a text'))
app._commit_cell_editor()
app.update()
set_body('')

# ---- THE SCREENSHOT FLOW: AN OPEN EDITOR MUST NOT EAT CTRL+C/V ----
# With an editor open (its text arrives selected), dragging a selection
# and copying used to copy the ENTRY's word and paste it back into the
# entry's own cell. The press now closes the editor and hands the
# keyboard to the grid.
set_body('| Food | X | Y |\n| Fruit | Cheese |  |\n'
         '| Cereal |  |  |\n| Eggs |  |  |')
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
app.clipboard_append('old')
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
app._cell_editor['entry'].insert('1.0', 'text wide enough to move the column')
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
    # On the two window classes: the main window's and every popup's. Not
    # bind_all any more -- Tk sends Deactivate to every widget inside a
    # window, and bind_all ran the handler once per widget (qa4 guards
    # that half).
    check('the foreground watch is armed from startup',
          getattr(app, '_deactivate_bound', False)
          and bool(app.bind_class(app.winfo_class(), '<Deactivate>'))
          and bool(app.bind_class('Toplevel', '<Deactivate>')))
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
set_body('| Head | G | H | I |\n| --- | --- | --- | --- |\n'
         '| one | two |  |  |\n| three | four |  |  |')
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
      app.clipboard_get() == 'one\ttwo')
_select_cells(_tS4, (1, 2), (1, 3))
app.body_text.event_generate('<Control-v>')
app.update()
_tS4 = app._grid_at_line(1)
check('and the horizontal pair lands whole',
      _tS4['cells'][(1, 2)]['value'] == 'one'
      and _tS4['cells'][(1, 3)]['value'] == 'two')

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
set_body('| Head | G | H |\n|  |  |  |\n|  |  |  |')
app._render_table_grids()
app.update()
_tW = app._grid_at_line(1)
_stub_clipboard(
    html='<table><tbody><tr><td>France</td><td>Paris</td></tr>'
         '</tbody></table>',
    text='France\nParis')
app.clipboard_clear()
app.clipboard_append('France\nParis')
app._grid_cell_clip = None
app._grid_paste_cells(_tW, 1, 0)
app.update()
_tW = app._grid_at_line(1)
check(f'two side-by-side web cells paste side by side '
      f'({_tW["cells"][(1, 0)]["value"]!r}, '
      f'{_tW["cells"][(1, 1)]["value"]!r})',
      _tW['cells'][(1, 0)]['value'] == 'France'
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
    html='<table><tr><td>old1</td><td>old2</td></tr></table>',
    text='fresh')
app.clipboard_clear()
app.clipboard_append('fresh')
app._grid_cell_clip = None
app._grid_paste_cells(_tW, 2, 0)
app.update()
_tW = app._grid_at_line(1)
check('stale table HTML never outranks a newer plain copy',
      _tW['cells'][(2, 0)]['value'] == 'fresh'
      and _tW['cells'][(2, 1)]['value'] == 'a2')
set_body('')

# ---- A TEMPLATE CARRYING A TABLE PRODUCES A WORKING GRID ----
# The template store is plain note fields, so a table should ride along
# like any text -- but only a check proves the applied note renders a
# real, editable grid rather than bare pipes.
_tplT = {'name': 'TableTemplate', 'title': 'From template',
         'body': '| Day | Plan |\n| mon | written |',
         'category': 'General', 'checklist': []}
app.templates.append(_tplT)
app.ask_yes_no = lambda *a, **k: True
app._apply_template(_tplT)
app.update()
_gT = app._grid_at_line(1)
check('a template with a table applies as a drawn grid',
      _gT is not None and _gT['data_rows'] == 2 and _gT['ncols'] == 2
      and _gT['cells'][(1, 0)]['value'] == 'mon')
app._open_cell_editor(_gT, 1, 1)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'read')
app._commit_cell_editor()
app.update()
_gT = app._grid_at_line(1)
check('and the grid from the template is editable',
      _gT['cells'][(1, 1)]['value'] == 'read')
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

# ---- ...AND THE TABLES ARE REBUILT ONCE, NOT AGAIN ON THE NEXT KEY ----
# Both gestures move the table under the caret; the caret does not leave
# it. The release of the Enter that pushed it, and the first letter typed
# on the line the menu added, read as leaving the table and rebuilt every
# table in the note a second time (measured 2026-10-12: two rebuilds per
# Enter). Counted on real key events, press AND release: the release is
# where the second rebuild came from, and a direct call has none.
_rbCalls = []
_rbReal = app._render_table_grids
app._render_table_grids = lambda *a, **k: (_rbCalls.append(1), _rbReal(*a, **k))[1]
try:
    set_body('| A | B |\n| x | y |\nbelow')
    _rbReal()
    app.update()
    app.body_text.mark_set('insert', '3.0')
    app._last_caret_line = 3
    take_focus(app.body_text)
    _rbCalls.clear()
    app.body_text.event_generate('<KeyPress-Return>', keysym='Return', when='now')
    app.body_text.event_generate('<KeyRelease-Return>', keysym='Return', when='now')
    for _ in range(4):
        app.update()
    _rbEnter = len(_rbCalls)
    _rbPushed = (app.body_text.get('1.0', '1.end') == ''
                 and app._grid_at_line(2) is not None)
    set_body('| M | N |\n| p | q |')
    _rbReal()
    app.update()
    app.body_text.mark_set('insert', '2.2')
    app._last_caret_line = 2
    app._grid_add_line_above(app._grid_at_line(1))
    app.update()
    take_focus(app.body_text)
    _rbCalls.clear()
    app.body_text.event_generate('<KeyPress-a>', keysym='a', when='now')
    app.body_text.event_generate('<KeyRelease-a>', keysym='a', when='now')
    for _ in range(4):
        app.update()
    _rbTyped = len(_rbCalls)
    _rbLine1 = app.body_text.get('1.0', '1.end')
finally:
    app._render_table_grids = _rbReal
print('  table rebuilds: %d on the Enter, %d on the letter after the menu'
      % (_rbEnter, _rbTyped))
check('fixture: a real Enter under a leading table pushes it down', _rbPushed)
check('one Enter that pushes a table down rebuilds the tables once', _rbEnter == 1)
check('fixture: the letter lands on the line the menu added', _rbLine1 == 'a')
check('...and the first letter typed on the line the menu added rebuilds nothing',
      _rbTyped == 0)
set_body('')

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
set_body('words to highlight')
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
set_body('| Head | G |\n| full |  |')
app._render_table_grids()
app.update()
_gE = app._grid_at_line(1)
app._grid_apply_style(_gE, (1, 1, 1, 1), 'highlight', _pureH)
app.update()
check('an empty cell takes a highlight on its padding',
      app._grid_cell_paint(_gE, 1, 1)['bg'] == _pureH)
app._write_cell(_gE, 1, 1, 'filled')
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
set_body('\U0001f600 hello\n| A | B |\n| c | d |\nwords chosen here')
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
      and _noteE['body'][_spE[0]['start']:_spE[0]['end']] == 'words')
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
app.body_text.insert('end', ' and a bit more')
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
set_body('| Head | Two |\n| :--- | ---: |\n| bold | colored |')
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
set_body('| Head | Two |\n| painted | text |')
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
_edM.insert('insert', 'low')
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
      _cM['value'] == 'painted<br>low'
      and ('painted', '#ff0000') in _runsM
      and ('low', '#00aa00') in _runsM
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
      ('painted', '#ff0000') in _runsM2 and ('low', '#00aa00') in _runsM2
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
app._cell_editor['entry'].insert('1.0', 'plain text')
app._commit_cell_editor()
app.update()
_gM3 = app._grid_at_line(1)
check('overwriting the marker turns the cell back into text',
      _gM3['cells'][(1, 1)]['value'] == 'plain text'
      and core_tables.checkbox_state('plain text') is None)
set_body('')

# ---- TYPING CONTINUES THE STYLE IT LANDS BESIDE ----
# Tk only inherits a tag with it on both sides, so a character typed at
# the END of a blue run arrived plain -- and retyping over the opening
# select-all wiped a coloured cell to plain ink entirely.
set_body('| Head | Two |\n| blue | text |')
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
set_body('| Head | Two |\n| one<br>two | x |\n| low | y |')
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
      and _gR['cells'][(2, 0)]['value'] == 'low<br><br>')
app._grid_set_row_lines(_gR, 2, 1)
app.update()
_gR = app._grid_at_line(1)
check('dragging it back short trims the padding again',
      _gR['cells'][(2, 0)]['h'] == _gR['row_h']
      and _gR['cells'][(2, 0)]['value'] == 'low')
app._grid_set_row_lines(_gR, 1, 1)
app.update()
_gR = app._grid_at_line(1)
check('a drag can never cut real content: two full lines stay two',
      _gR['cells'][(1, 0)]['value'] == 'one<br>two'
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
set_body('| ' + ' | '.join('Heading%d' % i for i in range(12)) + ' |\n'
         + '| ' + ' | '.join('content%d' % i for i in range(12)) + ' |')
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
set_body('| A | B |\n| c | d |\n\nbody to colour')
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
set_body('| Head | Two |\n| one | two |\n| three | four |')
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
      and _rowsV[3] == ['one', 'two'] and _rowsV[4] == ['three', 'four'])
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

set_body('| Head | Two |\n'
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
app.notes = [NO.normalize_note({'id': 9000 + i, 'title': 'Short %d' %i,
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

app.notes = [NO.normalize_note({'id': 9100 + i, 'title': 'Long %d' % i,
                                'body': 'body', 'category': 'General'})
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
         'body': 'body ' * 12, 'category': 'General'}))
for _i24 in range(12):
    _g24.append(NO.normalize_note(
        {'id': 9300 + _i24, 'title': 'Work %d' % _i24,
         'body': 'body ' * 12, 'category': 'Work'}))
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
    # The list's extent as the app states it -- Tk's bbox of a drawing
    # starts at the first row and pads rectangles differently by release.
    _bb24 = app._list_extent()
    _ch24 = _bb24[3] - _bb24[1]
    _max24 = _ch24 - _cv23.winfo_height()
    _st24b = (_st24b + 1
              if _max24 > 100 and abs(_cv23.canvasy(0) - _max24) < 30
              else 0)
_bb24 = app._list_extent()
_ch24 = _bb24[3] - _bb24[1]
_max24 = _ch24 - _cv23.winfo_height()
check('collapsing from deep scroll lands at the end, not a blank view',
      _max24 > 100 and abs(_cv23.canvasy(0) - _max24) < 30)
app.collapsed_groups.discard('General')
app.group_by_category.set(False)
app._on_toggle_group_by_category()

# A new search starts its results at the top, and a rebuild with the same
# search keeps its place. Kept in place, the first matches of a search typed
# with the list scrolled down sat above the screen (the owner's call,
# 2026-10-21). The search box waits 180 ms for a pause in typing.
def _settle25(seconds=0.6):
    _end25 = time.time() + seconds
    while time.time() < _end25:
        app.update()
        time.sleep(0.02)


app.notes = [NO.normalize_note({'id': 9300 + i, 'title': 'Found %d' % i,
                                'body': 'match', 'category': 'General'})
             for i in range(40)]
app.refresh_note_list()
_settle25()
_cv23.yview_moveto(0.6)
app.update()
_before25 = _cv23.canvasy(0)
app.search_var.set('match')
_settle25()
check(f'a new search shows its results from the top ({_before25:.0f} px down '
      f'before, {_cv23.canvasy(0):.0f} after)',
      _before25 > 200 and _cv23.canvasy(0) == 0)
_cv23.yview_moveto(0.5)
app.update()
_px25 = _cv23.canvasy(0)
app.refresh_note_list()
_settle25()
check('...while a rebuild with the same search keeps its place',
      _px25 > 200 and abs(_cv23.canvasy(0) - _px25) < 30)
app.search_var.set('')
_settle25()
check('...and clearing the search starts from the top too',
      _cv23.canvasy(0) == 0)
app.notes = _savedNotes23
app.refresh_note_list()
app.update()

# ---- LIST CARDS HIDE THE PIPE ROWS ----
set_body('| C1 | C2 |\n| a | b |\n\nreadable words')
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'CardTables')
app.save_current_note()
app.update()
_cardT = next(app._card_view(n) for n in app._card_order()
              if 'CardTables' in app._card_view(n)['title'])
check('a card previews the words, not the pipe rows',
      '|' not in _cardT['preview']
      and 'readable words' in _cardT['preview'])
check('the card tags row counts the table',
      '\u25a6 1 table' in _cardT['tags'])

# ---- A NEW TABLE UNDER AN OLD ONE STAYS A TABLE OF ITS OWN ----
# Two adjacent runs of pipe rows read as one block, so a table created
# right under another fused with it: mismatched columns, a garbled grid,
# loose '---' lines on screen.
set_body('| Head | G |\n| --- | --- |\n| one | two |')
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
app.title_entry.insert(0, 'autosave position')
app.body_text.insert('1.0', '| Head | G |\n| one | two |')
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
set_body('| Head | G |\n| one | two |')
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
app._cell_editor['entry'].insert('1.0', 'written while switching')
app.set_theme(_oldT)
app.apply_theme()
app.update()
_tT = app._grid_at_line(1)
check('a theme switch mid-typing keeps the typed text',
      _tT['cells'][(1, 0)]['value'] == 'written while switching'
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
    """Every colour the drawn list shows, row by row in screen order: the
    canvas behind it, each card's fill, stripe, ring and three texts, each
    header's fill, dot, caret and label. The list is a drawing, so this
    reads the drawing rather than widget options."""
    out = [('canvas', str(app.canvas.cget('bg')).lower())]
    for key in app._list_drawn_keys:
        if key[0] == 'note':
            v = app._card_view(key[1])
            out.append(('card', key[1]) + tuple(
                str(v[k]).lower() for k in ('bg', 'stripe', 'ring', 'title_fill',
                                             'preview_fill', 'tags_fill')))
        else:
            items = app._group_headers[key[1]]['items']
            out.append(('header', key[1]) + tuple(
                str(app.canvas.itemcget(items[k], 'fill')).lower()
                for k in ('bg', 'dot', 'caret', 'label')))
    return out

app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Palette clash note')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'body')
# '#4cd9a3' is a preset note colour AND the dark theme's success -- the exact
# case where a colour-swapping pass would wrongly repaint it.
check('fixture: the clash colour is a preset note colour and a dark-theme '
      'palette value',
      '#4cd9a3' in NO.PRESET_NOTE_COLORS
      and '#4cd9a3' in NO.THEMES['dark'].values()
      and '#4cd9a3' not in NO.THEMES['dark_ocean'].values())
app.current_note_color = '#4cd9a3'
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
_info = app._card_view(_clash_id)
check("a note's own colour survives a theme switch that doesn't share it",
      _info is not None
      and str(_info['stripe']).lower()
      == app.get_note_color(app.find_note(_clash_id)).lower())
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
# Forget whatever an earlier render drew, so the check below can only be
# answered by the catch-up itself.
app._cal_cells = {}
app.notebook.select(app.TAB_CALENDAR)
app.update()
check('the deferred calendar rebuild is caught up when the tab is opened',
      getattr(app, '_calendar_needs_render', False) is False)
check('...and the month really was drawn, not merely marked done',
      len(getattr(app, '_cal_cells', {})) > 0)
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
app.clipboard_clear(); app.clipboard_append('just text')
_c.focus_force(); app.update()
_c.event_generate('<<Paste>>')
app.update()
check('comments still accept ordinary pasted text',
      _c.get('1.0', 'end-1c').strip() == 'just text')
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
    'id': 8800, 'title': 'Export <trial>',
    'body': ('first line' + chr(10)
             + chr(0x2022) + ' bullet' + chr(10)
             + '| A | B |' + chr(10) + '| --- | --- |' + chr(10)
             + '| [x] | val |' + chr(10) + 'tail'),
    # Covers exactly the first word, so the export's <b> can be asked for
    # by name below rather than by offset.
    'formatting': [{'start': 0, 'end': 5, 'style': 'bold'}],
    'paragraphs': [{'line': 1, 'kind': 'bullet'}],
    'comments': 'a comment', 'category': 'General',
    'checklist': [{'text': 'done already', 'done': True},
                  {'text': 'to do <more>', 'done': False}]})
# A folder of its own on every run. The bulk export below names its files
# after what the folder already holds (" (2)" beside an existing file), so
# a fixed folder kept from an earlier run in the same place made this run
# read that run's files as its own: the second of three runs in one folder
# went red with nothing wrong in the app.
import tempfile as _tmpX
_exp_dir = _tmpX.mkdtemp(prefix='qa_export_out_', dir=os.getcwd())
_toastsX = []
_origToastX = app._show_toast
app._show_toast = lambda text, kind='success': _toastsX.append(text)
_origAskSaveX = _fdX.asksaveasfilename
_origAskYNX = app.ask_yes_no
_openAsksX = []
app.ask_yes_no = (lambda title, msg, **kw:
                  (_openAsksX.append(title), False)[1])

_pX = os.path.join(_exp_dir, 'note.html')
_fdX.asksaveasfilename = lambda **kw: _pX
app.export_note_as_file(_exp_note, 'html')
_htmlX = _ioX.open(_pX, encoding='utf-8').read() if os.path.exists(_pX) else ''
check('HTML export writes a full document with the table as a table',
      _htmlX.startswith('<!DOCTYPE html>') and '<table>' in _htmlX
      and '&lt;trial&gt;' in _htmlX and '<b>first</b>' in _htmlX)

_pX = os.path.join(_exp_dir, 'note.txt')
_fdX.asksaveasfilename = lambda **kw: _pX
app.export_note_as_file(_exp_note, 'txt')
_txtX = _ioX.open(_pX, encoding='utf-8').read() if os.path.exists(_pX) else ''
check('text export is the body as stored, comments included',
      'first line' in _txtX and 'a comment' in _txtX)
check('the checklist exports in both formats, states kept',
      chr(0x2611) + ' done already' in _htmlX
      and chr(0x2610) + ' to do' in _htmlX
      and '&lt;more&gt;' in _htmlX
      and '[x] done already' in _txtX)
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
      _seenX.get('initialfile') == 'Export _trial.html')
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
    'id': 8801, 'title': 'Export <trial>', 'body': 'another body',
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
      _bulk_files == ['Export _trial (2).txt', 'Export _trial.txt'])
_first = _ioX.open(os.path.join(_bulk_dir, 'Export _trial.txt'),
                   encoding='utf-8').read()
_second = _ioX.open(os.path.join(_bulk_dir, 'Export _trial (2).txt'),
                    encoding='utf-8').read()
check('same-title notes never overwrite each other',
      'first line' in _first and 'another body' in _second)
check('bulk export renders through the same pipeline as single',
      _first == app._note_export_content(_exp_note, 'txt', 'Export <trial>'))
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
    set_body('| blue | green |' + chr(10) + '| --- | --- |' + chr(10)
             + '| bold | full |')
    app._render_table_grids()
    app.update()
    _b = app.body_text
    app._ensure_color_tag(_b, 'text_color', '#e63946')
    app._ensure_color_tag(_b, 'highlight', '#ffff00')
    _l1 = _b.get('1.0', '1.end')
    _b.tag_add('text_color_e63946', '1.%d' % _l1.index('blue'),
               '1.%d' % (_l1.index('blue') + 4))
    _l3 = _b.get('3.0', '3.end')
    _b.tag_add('highlight_ffff00', '3.%d' % _l3.index('full'),
               '3.%d' % (_l3.index('full') + 4))
    _b.tag_add('bold', '3.%d' % _l3.index('bold'),
               '3.%d' % (_l3.index('bold') + 4))
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
set_body('| full | empty | plain |' + chr(10) + '| --- | --- | --- |'
         + chr(10) + '| text |  | other |')
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
_edF.insert('insert', 'new')
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
# The clipboard here is the suite's stand-in, never the machine's
# (_qa_support.pin_the_desktop). On the machine's, this check went red three
# times on a developer machine while Linux stayed green: another program
# holding the clipboard open for an instant made the paste read nothing,
# and a wait for one good read only moved the race to the paste's own.
try:
    _clipG = NO.clipboard.read_text() or app.body_text.clipboard_get()
except tk.TclError:
    _clipG = None
check('fixture: the copied cells really reached the clipboard',
      bool(_clipG) and '\t' in _clipG)
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
set_body('| long content here | x |' + chr(10) + '| --- | --- |'
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
set_body('top' + chr(10) + '| a | b |' + chr(10) + '| --- | --- |'
         + chr(10) + '|   |   |' + chr(10) + ('low ' * 200))
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
def _ty_key(keysym, ch):
    """A typing key pressed and released on the body, as a person does.
    The press notes where typing starts (_note_typing_key), and a release
    with no press of its own spreads no style. A synthetic key's %A does
    not reliably insert (with real focus on Windows it does), so the
    character goes in by hand only when the press typed nothing -- over the
    selection the caret is in, as Tk's class binding puts it."""
    _w = app.body_text
    if not take_focus(_w):
        return False
    _before = _w.get('1.0', 'end-1c')
    _w.event_generate('<KeyPress>', keysym=keysym)
    if _w.get('1.0', 'end-1c') == _before:
        try:
            if (_w.compare('sel.first', '<=', 'insert')
                    and _w.compare('insert', '<=', 'sel.last')):
                _w.delete('sel.first', 'sel.last')
        except tk.TclError:
            pass
        _w.insert('insert', ch)
    _w.event_generate('<KeyRelease>', keysym=keysym)
    app.update()
    return True


set_body('tinted ')
_b = app.body_text
app._ensure_color_tag(_b, 'highlight', '#ffff00')
app._ensure_color_tag(_b, 'text_color', '#e63946')
_b.tag_add('highlight_ffff00', '1.0', '1.6')
_b.tag_add('text_color_e63946', '1.0', '1.6')
_b.mark_set('insert', '1.6')
_tyX = _ty_key('X', 'X')
_tagsXH = sorted(t for t in _b.tag_names('1.6')
                 if 'color' in t or 'highlight' in t)
_b.mark_set('insert', '1.end')
_tyY = _ty_key('space', ' ') and _ty_key('Y', 'Y')
_tagsYH = [t for t in _b.tag_names('1.end-1c')
           if 'color' in t or 'highlight' in t]
check('letters glued onto a coloured word inherit colour AND highlight',
      _tyX and len(_tagsXH) == 2)
check('but a word started after a space stays plain', _tyY and _tagsYH == [])
set_body('')

# Bold, italic or plain given to text under a size or a font is drawn at
# once. A size or a font is drawn by one composite tag with the weight and
# slant folded in, which outranks bold and italic. Each route below changed
# the plain tag alone: the word was saved and lit the toolbar as bold and
# was drawn as before until the note was opened again -- and a letter
# glued onto a bold word at a heading's end lost the heading's size.
def _drawn(index):
    """(size, weight, slant) Tk draws *index* in: the font of the highest
    priority tag there that sets one."""
    _w = app.body_text
    _font = None
    for _t in _w.tag_names(index):
        if _w.tag_cget(_t, 'font'):
            _font = _w.tag_cget(_t, 'font')
    _a = _tkfont.Font(font=_font or _w.cget('font')).actual()
    return _a['size'], _a['weight'], _a['slant']


def _sized_line(*extra, style='font_size', value=20):
    set_body('Big Title here')
    app._apply_formatting(app.body_text, [
        {'start': 0, 'end': 14, 'style': style, 'value': value}] + list(extra))
    app.update()


_bs_seen = {}
_sized_line()
select('1.4', '1.9')
app._toggle_body_style('bold')
clear_selection()
_bs_seen['Ctrl+B'] = _drawn('1.5')
_sized_line({'start': 4, 'end': 9, 'style': 'bold'})
select('1.4', '1.9')
app._toggle_body_style('bold')
clear_selection()
_bs_seen['Ctrl+B off'] = _drawn('1.5')
_sized_line(style='font_family', value='Georgia')
select('1.4', '1.9')
app._toggle_body_style('italic')
clear_selection()
_bs_seen['Ctrl+I in Georgia'] = _drawn('1.5')
_sized_line()
app.body_text.mark_set('insert', '1.4')
app._toggle_body_style('bold')
type_char('N')
app._pending_styles = set()
_bs_seen['Bold on, then typing'] = _drawn('1.4')
_sized_line()
app.body_text.mark_set('insert', '1.4')
_stub_clipboard(html='<p><b>B</b></p>')
app._on_body_paste()
app.update()
_bs_seen['a bold paste'] = _drawn('1.4')
_sized_line({'start': 4, 'end': 9, 'style': 'bold'})
app.body_text.mark_set('insert', '1.9')
_bs_typed = _ty_key('X', 'X')
_bs_seen['a letter glued onto the bold word'] = _drawn('1.9')
check(f'bold, italic or plain given under a size or a font is drawn at once '
      f'({_bs_seen})',
      _bs_typed
      and _bs_seen['Ctrl+B'] == (20, 'bold', 'roman')
      and _bs_seen['Ctrl+B off'] == (20, 'normal', 'roman')
      and _bs_seen['Ctrl+I in Georgia'][1:] == ('normal', 'italic')
      and _bs_seen['Bold on, then typing'] == (20, 'bold', 'roman')
      and _bs_seen['a bold paste'] == (20, 'bold', 'roman')
      and _bs_seen['a letter glued onto the bold word'] == (20, 'bold', 'roman'))


# Ctrl+B or Ctrl+I over a selection keeps each stretch's OTHER style: the
# whole selection got one answer for both, so an italic word in a sentence
# made bold lost its italic. Real Ctrl+B / Ctrl+I.
def _wb_spans():
    return sorted((s['start'], s['end'], s['style'])
                  for s in app._extract_formatting(app.body_text))


def _wb_press(letter):
    select('1.0', '1.end')
    take_focus(app.body_text)
    app.body_text.event_generate(f'<Control-{letter}>')
    app.update()
    clear_selection()


set_body('one two three')
app.body_text.tag_add('italic', '1.4', '1.7')
_wb_press('b')
_wb_on = _wb_spans()
_wb_drawn = _drawn('1.5')
check(f'Ctrl+B over a sentence keeps its italic word italic ({_wb_on}, {_wb_drawn})',
      _wb_on == [(0, 4, 'bold'), (4, 7, 'bold_italic'), (7, 13, 'bold')]
      and _wb_drawn[1:] == ('bold', 'italic'))
_wb_press('b')
check(f'...and Ctrl+B again takes the bold off and leaves the italic '
      f'({_wb_spans()})', _wb_spans() == [(4, 7, 'italic')])
set_body('one two three')
app.body_text.tag_add('bold', '1.4', '1.7')
_wb_press('i')
check(f'Ctrl+I over a sentence keeps its bold word bold ({_wb_spans()})',
      _wb_spans() == [(0, 4, 'italic'), (4, 7, 'bold_italic'),
                      (7, 13, 'italic')])
_sized_line({'start': 4, 'end': 9, 'style': 'italic'})
_wb_press('b')
_wb_sized = (_drawn('1.1'), _drawn('1.5'))
check(f'...under a size too, each stretch drawn with both ({_wb_sized})',
      _wb_sized == ((20, 'bold', 'roman'), (20, 'bold', 'italic')))
set_body('')
# A size picked with nothing selected and typed inside a run of another size
# draws at the size picked: the letters took the run's composite too, and Tk
# drew whichever of the two tags was made later.
_sized_line()
# The bad order made for sure: the picked size's tag exists, and the run's
# was made after it.
app._ensure_font_tag(app.body_text, False, False, 16, None)
app.body_text.tag_raise('font_-_20_00')
app.body_text.mark_set('insert', '1.4')
app._apply_body_font('font_size', 16)
type_char('N')
_bs_pend = _drawn('1.4')
app._pending_font_size = None
app._pending_styles = set()
check(f'a size picked with nothing selected draws at that size inside a run '
      f'of another ({_bs_pend})', _bs_pend[0] == 16)
# ...and keeps the run's font: laid in place of the composite the letters
# inherited, the size took Georgia away with it, saved without it.
_sized_line(style='font_family', value='Georgia')
app.body_text.mark_set('insert', '1.6')
app._apply_body_font('font_size', 16)
for _bs_ch in 'NEW':
    type_char(_bs_ch)
app._pending_font_size = None
app._pending_styles = set()
_bs_spans = app._extract_formatting(app.body_text)
# Every letter typed, not only the first: the first takes the run's
# composite from both its neighbours, the next ones from no one.
_bs_both = [sorted((s['style'], s.get('value')) for s in _bs_spans
                   if s['start'] <= at < s['end']) for at in (6, 7, 8)]
check(f'a size picked inside a run set in a font keeps the font on every '
      f'letter typed ({_bs_both})',
      _bs_both == [[('font_family', 'Georgia'), ('font_size', 16)]] * 3)
# Typed right after a bold word inside a bigger heading -- a space and a
# word -- the text wore neither side's composite and came out at 12 pt.
_sized_line({'start': 4, 'end': 9, 'style': 'bold'})
app.body_text.mark_set('insert', '1.9')
_bs_typed = _ty_key('space', ' ') and _ty_key('b', 'b')
_bs_edge = [_drawn(i)[0] for i in ('1.9', '1.10')]
check(f'text typed at a bold word\'s edge inside a bigger heading keeps the '
      f'heading\'s size ({_bs_edge})', _bs_typed and _bs_edge == [20, 20])
# Bold and italic on the same letters -- a bold italic word pasted, or a note
# saved that way -- were two tags that both set the font, and italic won.
set_body('')
_stub_clipboard(html='<p><b><i>BI</i></b> plain</p>')
app._on_body_paste()
app.update()
_bs_bi = _drawn('1.0')
set_body('one two')
app._apply_formatting(app.body_text,
                      [{'start': 4, 'end': 7, 'style': 'bold'},
                       {'start': 4, 'end': 7, 'style': 'italic'}])
app.update()
_bs_bi_loaded = _drawn('1.5')
check(f'bold italic, pasted or opened, is drawn bold and italic '
      f'({_bs_bi}, {_bs_bi_loaded})',
      _bs_bi[1:] == ('bold', 'italic') and _bs_bi_loaded[1:] == ('bold', 'italic'))
# Ctrl+B on one word in a long note set in a font lays the composites of
# that word, not of the note: laid across the note, it took 250 ms at 8,000
# styled words. Counted, not timed: the body's "tag add" and "tag remove".
_bs_words = ['word%d' % i for i in range(400)]
set_body(' '.join(_bs_words))
app._apply_formatting(app.body_text, [
    {'start': 0, 'end': len(' '.join(_bs_words)), 'style': 'font_family',
     'value': 'Georgia'}] + [
    {'start': 7 * i, 'end': 7 * i + 4, 'style': 'bold'} for i in range(0, 400, 3)])
app.update()
_bs_at = app.body_text.search('word200', '1.0', 'end')
select(_bs_at, f'{_bs_at}+7c')
_bs_calls = [0]


def _bs_trace(command, *_op):
    if ' tag add ' in command or ' tag remove ' in command:
        _bs_calls[0] += 1


app.tk.createcommand('qa_tag_trace', _bs_trace)
app.tk.call('trace', 'add', 'execution', app.body_text._w, 'enter',
            'qa_tag_trace')
try:
    app._toggle_body_style('bold')
finally:
    app.tk.call('trace', 'remove', 'execution', app.body_text._w, 'enter',
                'qa_tag_trace')
    app.tk.deletecommand('qa_tag_trace')
clear_selection()
check(f'Ctrl+B on one word of a long note set in a font lays that word\'s '
      f'composites only ({_bs_calls[0]} tag changes; drawn {_drawn(_bs_at)})',
      _bs_calls[0] <= 20 and _drawn(_bs_at)[1] == 'bold')
# Bold and italic laid over the same letters by typing or a paste -- Italic
# turned on after a bold word and letters typed glued onto it, or bold
# pasted inside an italic word -- were two tags that both set the font:
# drawn italic alone while the toolbar lit both, until the note was opened
# again.
clear_selection()
set_body('one two three')
app.body_text.tag_add('bold', '1.4', '1.7')
app.body_text.mark_set('insert', '1.7')
app._toggle_body_style('italic')
_bs_typed = _ty_key('X', 'X') and _ty_key('Y', 'Y')
app._pending_styles = set()
_bs_fold = {'typed after a bold word, Italic on': _drawn('1.8')}
set_body('one two three')
app.body_text.tag_add('italic', '1.4', '1.7')
app.body_text.mark_set('insert', '1.5')
_stub_clipboard(html='<p><b>XY</b></p>')
app._on_body_paste()
app.update()
_bs_fold['bold pasted inside an italic word'] = _drawn('1.6')
check(f'bold and italic laid over the same letters by typing or a paste are '
      f'drawn bold and italic at once ({_bs_fold})',
      _bs_typed and all(d[1:] == ('bold', 'italic') for d in _bs_fold.values()))
# Put in at a bold word's edge inside a bigger heading by any road, not only
# typed: the text wore neither side's composite (Tk passes on only what both
# sides wear) and came out at the base size, the heading's size split in two
# around it, saved so.
_bs_road = {}


def _bs_edge():
    _sized_line({'start': 4, 'end': 9, 'style': 'bold'})
    app.body_text.mark_set('insert', '1.9')


_bs_edge()
_stub_clipboard(html='<p>XY</p>', text='XY')
app._on_body_paste()
app.update()
_bs_road['Ctrl+V'] = _drawn('1.9')[0]
_bs_edge()
_stub_clipboard(text='XY')
app.clipboard_clear()
app.clipboard_append('XY')
take_focus(app.body_text)
app.body_text.event_generate('<<Paste>>')
for _ in range(3):
    app.update()
    app.update_idletasks()
_bs_road['Tk\'s own paste'] = _drawn('1.9')[0]
_bs_edge()
app._paste_plain()
app.update()
_bs_road['Ctrl+Shift+V'] = _drawn('1.9')[0]
_bs_edge()
app.body_text.mark_unset('calc_insert_end')
app._calc_insert_formula('1+1=2')
app.update()
app.body_text.mark_unset('calc_insert_end')
_bs_road['the calculator'] = _drawn('1.9')[0]
_bs_edge()
app._insert_emoji_from_toolbar()
app.update()
_bs_cells = []


def _bs_find_emoji(w):
    for _c in w.winfo_children():
        if isinstance(_c, tk.Label) and 'Emoji' in str(_c.cget('font')):
            _bs_cells.append(_c)
        _bs_find_emoji(_c)


if getattr(app, '_mini_popup', None) is not None:
    _bs_find_emoji(app._mini_popup)
if _bs_cells:
    _bs_cells[0].event_generate('<Button-1>', x=4, y=4)
    app.update()
    _bs_road['an emoji'] = _drawn('1.9')[0]
app._dismiss_mini_popup()
app.update()
check(f'text put in at a bold word\'s edge inside a bigger heading keeps the '
      f'heading\'s size, by every road ({_bs_road})',
      len(_bs_road) == 5 and all(v == 20 for v in _bs_road.values()))
# A size or a font picked before typing, at a run's edge -- beside a bold
# word inside a run set in Georgia, glued onto its end, or picked again after
# the first letter -- took the base's font (or size) with the pick: those
# letters wore no composite yet when the pick was laid.
_bs_pick = {}


def _bs_typed_with(at, *keys, line=(), style='font_family', value='Georgia',
                   picks=(16,)):
    _sized_line(*line, style=style, value=value)
    clear_selection()
    app.body_text.mark_set('insert', at)
    _ok = True
    for _pick, _ch in zip(picks, keys):
        app._apply_body_font('font_size' if isinstance(_pick, int)
                             else 'font_family', _pick)
        _ok = _ty_key(_ch, _ch) and _ok
    app._pending_font_size = app._pending_font_family = None
    app._pending_styles = set()
    _first = int(at.split('.')[1])
    _spans = app._extract_formatting(app.body_text)
    return _ok, [sorted((s['style'], s.get('value')) for s in _spans
                        if s['start'] <= _first + k < s['end']
                        and s['style'] in ('font_size', 'font_family'))
                 for k in range(len(keys))]


_bs_bold = ({'start': 4, 'end': 9, 'style': 'bold'},)
_bs_pick['after a bold word'] = _bs_typed_with('1.9', 'A', 'B', line=_bs_bold,
                                               picks=(16, 16))
_bs_pick['before a bold word'] = _bs_typed_with('1.4', 'A', 'B', line=_bs_bold,
                                                picks=(16, 16))
_bs_pick['glued onto the run\'s end'] = _bs_typed_with('1.14', 'A', 'B',
                                                       picks=(16, 16))
_bs_pick['picked again'] = _bs_typed_with('1.6', 'A', 'B', picks=(16, 20))
_bs_pick['a font after a size'] = _bs_typed_with(
    '1.6', 'A', 'B', style='font_size', value=20,
    picks=('Georgia', 'Courier New'))
_bs_G = ('font_family', 'Georgia')
check(f'a size or font picked at a run\'s edge keeps the run\'s other property '
      f'({_bs_pick})',
      all(v[0] for v in _bs_pick.values())
      and _bs_pick['after a bold word'][1] == [[_bs_G, ('font_size', 16)]] * 2
      and _bs_pick['before a bold word'][1] == [[_bs_G, ('font_size', 16)]] * 2
      and _bs_pick['glued onto the run\'s end'][1]
      == [[_bs_G, ('font_size', 16)]] * 2
      and _bs_pick['picked again'][1] == [[_bs_G, ('font_size', 16)],
                                          [_bs_G, ('font_size', 20)]]
      and _bs_pick['a font after a size'][1]
      == [[_bs_G, ('font_size', 20)],
          [('font_family', 'Courier New'), ('font_size', 20)]])
# A long paste is fitted by stretches where its tags stay the same, not a
# character at a time: each character cost an index, a reading of its tags
# and a tag laid, and a long paste into a note set in a font took two to
# three times what laying the whole note again had. Counted, not timed: the
# body's "tag names".
_bs_long = 'word ' * 400
set_body(_bs_long)
app._apply_formatting(app.body_text, [
    {'start': 0, 'end': len(_bs_long), 'style': 'font_family',
     'value': 'Georgia'}] + [
    {'start': 50 * i, 'end': 50 * i + 4, 'style': 'bold'} for i in range(10)])
app.update()
_bs_reads = [0]


def _bs_read_trace(command, *_op):
    if ' tag names ' in command:
        _bs_reads[0] += 1


app.tk.createcommand('qa_read_trace', _bs_read_trace)
app.tk.call('trace', 'add', 'execution', app.body_text._w, 'enter',
            'qa_read_trace')
try:
    app._fit_font_tags('1.0', 'end-1c')
finally:
    app.tk.call('trace', 'remove', 'execution', app.body_text._w, 'enter',
                'qa_read_trace')
    app.tk.deletecommand('qa_read_trace')
check(f'a long paste is fitted by stretches, not a character at a time '
      f'({_bs_reads[0]} tag readings for {len(_bs_long)} characters in 21 '
      f'stretches; drawn {_drawn("1.0")})',
      _bs_reads[0] <= 60 and _drawn('1.0')[1] == 'bold')
set_body('')

# On every line, not only the last, and over a selection: a first test of
# "the key typed something" compared where the text ENDED, which an edit
# above the last line never moves -- typing after a styled word spread
# nothing on any other line, nor over the end of a styled word selected.
set_body('Prices: here' + chr(10) + 'Total due' + chr(10) + 'end line')
app._ensure_color_tag(_b, 'text_color', '#d32f2f')
_b.tag_add('bold', '1.0', '1.6')
_b.tag_add('text_color_d32f2f', '2.0', '2.5')
_b.mark_set('insert', '1.6')
_tyL = _ty_key('x', 'x') and _ty_key('y', 'y')
_b.mark_set('insert', '2.5')
_tyL = _ty_key('z', 'z') and _tyL
check(f'typing after a styled word spreads its style on every line, not '
      f'only the last (bold {_b.tag_ranges("bold")}; red '
      f'{_b.tag_ranges("text_color_d32f2f")})',
      _tyL
      and [str(i) for i in _b.tag_ranges('bold')] == ['1.0', '1.8']
      and [str(i) for i in _b.tag_ranges('text_color_d32f2f')]
      == ['2.0', '2.6'])
_tyO = []
for _ty_from, _ty_caret in (('1.4', '1.6'), ('1.4', '1.4')):
    set_body('Prices: here' + chr(10) + 'more')
    _b.tag_add('bold', '1.0', '1.6')
    _b.tag_add('sel', _ty_from, '1.6')
    _b.mark_set('insert', _ty_caret)
    _ty_ok = all(_ty_key(_k, _k) for _k in 'ing')
    _tyO.append((_ty_ok, _b.get('1.0', '1.end'),
                 [str(i) for i in _b.tag_ranges('bold')]))
check(f'typing over the end of a styled word, selected either way, keeps '
      f'its style ({_tyO})',
      all(_ok and _t == 'Pricing: here' and _r == ['1.0', '1.7']
          for _ok, _t, _r in _tyO))


# A key with a binding of its own types nothing to spread a style over:
# Delete, BackSpace, Ctrl+B, Ctrl+Z and a paste without its styling each
# turned the plain ":" glued to a bold word bold (no press of a typing key
# noted them, and the release read the two characters left of the caret).
# Pressed as a person presses them: a modifier goes down first, as a key of
# its own -- one with no binding here, so it reads as a key that may type.
def _own_key(press, release, mods=()):
    if not take_focus(app.body_text):
        return False
    for _m in mods:
        app.body_text.event_generate('<KeyPress-%s>' % _m)
    app.body_text.event_generate(press)
    app.body_text.event_generate(release)
    for _m in reversed(mods):
        app.body_text.event_generate('<KeyRelease-%s>' % _m)
    app.update()
    return True


_ty_real_read = NO.clipboard.read_text
_tyK = []
try:
    NO.clipboard.read_text = lambda: ':'
    for _ty_name, _ty_caret, _ty_do in (
            ('Delete', '1.7',
             lambda: _own_key('<Delete>', '<KeyRelease-Delete>')),
            ('BackSpace', '1.8',
             lambda: _own_key('<BackSpace>', '<KeyRelease-BackSpace>')),
            ('Ctrl+B', '1.7',
             lambda: _own_key('<Control-b>', '<Control-KeyRelease-b>',
                              ('Control_L',))),
            ('typing, then Ctrl+Z', '1.7',
             lambda: (_ty_key('x', 'x')
                      and _own_key('<Control-z>', '<Control-KeyRelease-z>',
                                   ('Control_L',)))),
            ('BackSpace, then Ctrl+Z', '1.7',
             lambda: (_own_key('<BackSpace>', '<KeyRelease-BackSpace>')
                      and _own_key('<Control-z>', '<Control-KeyRelease-z>',
                                   ('Control_L',)))),
            ('Ctrl+Shift+V', '1.6',
             lambda: _own_key('<Control-Shift-KeyPress-V>',
                              '<Control-Shift-KeyRelease-V>',
                              ('Control_L', 'Shift_L')))):
        set_body('Prices: here')
        _b.tag_add('bold', '1.0', '1.6')
        _b.mark_set('insert', _ty_caret)
        app._reset_text_undo()
        _ty_ok = _ty_do()
        app._pending_styles = set()
        _tyK.append((_ty_name, _ty_ok, _b.get('1.0', '1.end'),
                     [str(i) for i in _b.tag_ranges('bold')]))
finally:
    NO.clipboard.read_text = _ty_real_read
check(f'Delete, BackSpace, Ctrl+B, Ctrl+Z and a paste without its styling '
      f'spread no style onto a plain colon ({_tyK})',
      all(_ok and _r == ['1.0', '1.6'] for _n, _ok, _t, _r in _tyK)
      and [_t for _n, _ok, _t, _r in _tyK][3:]
      == ['Prices: here', 'Prices: here', 'Prices:: here'])


# Keys pressed over each other -- the next letter down before the last is
# up, as fast typing goes, or a key held until it repeats: each press set
# the marks again, the first release found two fresh plain letters, and the
# style stayed behind. What a key typed is settled at the next key's press.
def _ty_down(keysym, ch):
    """A typing key's press alone, the character put in by hand when the
    synthetic press typed nothing (see _ty_key)."""
    _w = app.body_text
    _before = _w.get('1.0', 'end-1c')
    _w.event_generate('<KeyPress>', keysym=keysym)
    if _w.get('1.0', 'end-1c') == _before:
        _w.insert('insert', ch)


_tyR = []
for _ty_how in ('rollover', 'held'):
    set_body('Prices: here' + chr(10) + 'second line')
    _b.tag_add('bold', '1.0', '1.6')
    _b.mark_set('insert', '1.6')
    _ty_ok = take_focus(_b)
    if _ty_how == 'rollover':
        _ty_down('x', 'x')
        _ty_down('y', 'y')
        _b.event_generate('<KeyRelease>', keysym='x')
        _b.event_generate('<KeyRelease>', keysym='y')
    else:
        for _ in range(3):
            _ty_down('x', 'x')
        _b.event_generate('<KeyRelease>', keysym='x')
    app.update()
    _tyR.append((_ty_how, _ty_ok, _b.get('1.0', '1.end'),
                 [str(i) for i in _b.tag_ranges('bold')]))
check(f'letters pressed over each other, or a held key, after a styled word '
      f'wear its style ({_tyR})',
      _tyR == [('rollover', True, 'Pricesxy: here', ['1.0', '1.8']),
               ('held', True, 'Pricesxxx: here', ['1.0', '1.9'])])
# A key that types nothing, after a table typed by hand: its release tidies
# the table it left, and the padding goes in where the press set its marks
# -- read as typed, the character before the caret, on the line the key
# went to, took the style of the one before it.
set_body('Intro' + chr(10) + '| Item name | Qty |' + chr(10) + '| --- | --- |'
         + chr(10) + '| Te | 2 |' + chr(10) + 'P: tail')
_b.tag_add('bold', '5.0', '5.1')
_b.mark_set('insert', '4.4')
app._last_caret_line = None
_tyT = _ty_key('a', 'a')
_tyT = take_focus(_b) and _tyT
_b.event_generate('<KeyPress-Down>')
_b.mark_set('insert', '5.2')
_b.event_generate('<KeyRelease-Down>')
app.update()
_tyT_rows = _b.get('2.0', '4.end').split(chr(10))
check(f'a key that types nothing spreads no style after the table it left '
      f'is tidied (bold {_b.tag_ranges("bold")}; rows {_tyT_rows})',
      _tyT and [str(i) for i in _b.tag_ranges('bold')] == ['5.0', '5.1']
      and len({len(r) for r in _tyT_rows}) == 1)
# Tk's own Ctrl+T swaps the two letters at the caret, and the Insert key
# pastes the selection: neither is typing, and a run opened for them gave
# the swapped letters -- or the pasted words -- the word's style.
set_body('Pricesab here' + chr(10) + 'second line')
_b.tag_add('bold', '1.0', '1.6')
_b.mark_set('insert', '1.7')
_tyCT = _own_key('<Control-KeyPress-t>', '<Control-KeyRelease-t>',
                 ('Control_L',))
_tyCT = (_tyCT, _b.get('1.0', '1.end'),
         [str(i) for i in _b.tag_ranges('bold')])
set_body('Prices: here' + chr(10) + 'second line')
_b.tag_add('bold', '1.0', '1.6')
_b.mark_set('insert', '1.6')
app.title_entry.delete(0, 'end')
app.title_entry.insert(0, 'Fresh words')
app.title_entry.selection_range(0, 'end')
_tyIns = _own_key('<KeyPress-Insert>', '<KeyRelease-Insert>')
_tyIns = (_tyIns, _b.get('1.0', '1.end'),
          [str(i) for i in _b.tag_ranges('bold')])
app.title_entry.selection_clear()
app.title_entry.delete(0, 'end')
check(f'Ctrl+T and the Insert key spread no style ({_tyCT}; {_tyIns})',
      _tyCT == (True, 'Pricesba here', ['1.0', '1.6'])
      and _tyIns == (True, 'PricesFresh words: here', ['1.0', '1.6']))
set_body('')

# ---- FIELD ROUND 4 ----
# The view restore after a grid rebuild stays IN FORCE: a late yank
# (the embedded windows' geometry settling) is corrected by the timers
# -- the old one-shot restore stayed scrolled away.
set_body(chr(10).join('| r%d | c%d |' % (i, i) for i in range(8))
         + chr(10) + ('text low' + chr(10)) * 50)
app._render_table_grids()
app.update()
app._grid_view_restore = None
app.body_text.yview_moveto(0.5)
app.update()
_y0J = app.body_text.yview()[0]
_iJ = app._grid_at_line(1)
app._grid_set_alignment(_iJ, (1, 0, 1, 0), core_tables.ALIGN_CENTER)
app.update()
app.body_text.yview_moveto(0.0)      # the late yank, simulated
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
set_body('opening fig2')
app.body_text.mark_set('insert', '1.8')
app.clipboard_clear()
app.clipboard_append('| x | [x] |' + chr(10) + 'caption')
app.update()
# Through _on_body_paste, the REAL route of a Ctrl+V -- a method called
# directly stays green even when its hook disappears (the "dead on
# arrival" lesson).
_stub_clipboard(html=None, text='| x | [x] |' + chr(10) + 'caption')
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

# A table follows its caption, and the caption its table (field pass:
# centring the caption left the table where it was). Only a caption right
# under its table belongs to it; one Ctrl+Z takes both back.
set_body('intro' + chr(10) + '| a | b |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |' + chr(10) + 'tail' + chr(10) + 'Table 9: far away')
app._render_table_grids()
app.update()
app._grid_add_caption(app._grid_at_line(2))
app.update()
app.body_text.tag_remove('sel', '1.0', 'end')


def _tf_where():
    """(table, caption, source, a far 'Table 9:' line) placements."""
    _b = app.body_text.get('1.0', 'end-1c').split(chr(10))
    _far = _b.index('Table 9: far away') + 1
    return (app._grid_table_align_of(2),
            app._paragraph_align_of(app.body_text, 5),
            app._paragraph_align_of(app.body_text, 6),
            app._paragraph_align_of(app.body_text, _far))


_tf = {'start': _tf_where()}
app._reset_text_undo()
app.body_text.mark_set('insert', '5.3')            # on the caption's label
app._set_paragraph_align('center')
app.update()
_tf['caption centred'] = _tf_where()
app._body_undo_redo('undo')
app.update()
_tf['one Ctrl+Z'] = _tf_where()
app.body_text.mark_set('insert', '6.2')            # on its source line
app._set_paragraph_align('right')
app.update()
_tf['source right'] = _tf_where()
app._set_paragraph_align('right')                   # pressed again: back left
app.update()
_tf['pressed again'] = _tf_where()
app._grid_set_table_align(app._grid_at_line(2), 'center')   # the menu's road
app.update()
_tf['table centred'] = _tf_where()
_far = app.body_text.get('1.0', 'end-1c').split(chr(10)).index('Table 9: far away') + 1
app.body_text.mark_set('insert', '%d.2' % _far)
app._set_paragraph_align('right')
app.update()
_tf['far line right'] = _tf_where()
check(f'a table and its caption move together, one Ctrl+Z takes both back, '
      f'and a caption away from its table moves nothing ({_tf})',
      _tf == {'start': ('left', 'left', 'left', 'left'),
              'caption centred': ('center', 'center', 'center', 'left'),
              'one Ctrl+Z': ('left', 'left', 'left', 'left'),
              'source right': ('right', 'right', 'right', 'left'),
              'pressed again': ('left', 'left', 'left', 'left'),
              'table centred': ('center', 'center', 'center', 'left'),
              'far line right': ('center', 'center', 'center', 'right')})
# Every cell selected and centred centres the cells' text, as a spreadsheet
# does, and says how the table itself moves -- in a dialog that waits to be
# read (her re-test: the banner went before she had read it).
_tf_said = []
_tf_real_info = app.show_info
app.show_info = lambda title, message, **k: _tf_said.append((title, message))
try:
    _tfI = app._grid_at_line(2)
    app._grid_select_range(_tfI, (0, 0), (_tfI['data_rows'] - 1, _tfI['ncols'] - 1))
    app.update()
    app._set_paragraph_align('right')
    app.update()
finally:
    app.show_info = _tf_real_info
app._grid_clear_selection()
_tf_cells = core_tables.cell_alignments(app.body_text.get('4.0', '4.end'))
check(f'centring every cell aligns their text and says how to move the table '
      f'({_tf_said}; {_tf_cells}; {app._grid_table_align_of(2)})',
      _tf_cells == [core_tables.ALIGN_RIGHT] * 2
      and app._grid_table_align_of(2) == 'center'
      and len(_tf_said) == 1
      and _tf_said[0][0] == 'The cells moved, not the table'
      and 'Center table on page' in _tf_said[0][1])
set_body('')

# The table's placement travels with the cell copy.
set_body('| p | q |' + chr(10) + '| --- | --- |' + chr(10)
         + '| 1 | 2 |' + chr(10) + chr(10) + 'tail')
app._render_table_grids()
app.update()
_iL = app._grid_at_line(1)
app._grid_set_table_align(_iL, 'center')
app.update()
_iL = app._grid_at_line(1)
app._grid_select_range(_iL, (0, 0), (1, 1))
_stub_clipboard()   # read_text -> None; paste falls back to the real Tk clipboard
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
# tail of the source line ('Source: | fff |...' in the field report, from
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

# ...and pasted by Ctrl+Shift+V (the owner's test case 693, 2026-10-24):
# the plain paste read only the clipboard's text, and our cell copy's text
# is tabs, for a spreadsheet -- the cells came in as tabs, a box as "[x]",
# where Ctrl+V rebuilt the table. Plain, it is the table again, without
# the cells' colours.
set_body('| Done | Item |' + chr(10) + '| --- | --- |' + chr(10) + '| [x] | Milk |')
app._render_table_grids()
app.update()
_kP = app.body_text.get('3.0', '3.end').index('Milk')
app.body_text.tag_add(
    app._ensure_color_tag(app.body_text, 'text_color', '#d32f2f'),
    '3.%d' % (_kP + app._col_base(3)), '3.%d' % (_kP + app._col_base(3) + 4))
_iP = app._grid_at_line(1)
app._grid_select_range(_iP, (0, 0), (1, 1))
_stub_clipboard(loopback=True)
app._grid_copy_selection({'info': _iP, 'box': (0, 0, 1, 1)})
app._grid_clear_selection()
set_body('')
app.update()
app._paste_plain()
app.update()
_bodyP = app.body_text.get('1.0', 'end-1c')
_atP = app.body_text.search('Milk', '1.0', 'end', elide=True)   # under the drawn grid
_tagsP = ([t for t in app.body_text.tag_names(_atP) if t.startswith('text_color')]
          if _atP else ['no Milk'])
check(f"cells copied from a table and pasted by Ctrl+Shift+V come back a table, "
      f"its box a box, without the cells' colours ({_bodyP!r}; {_tagsP})",
      len(core_tables.find_blocks(_bodyP)) == 1 and chr(9) not in _bodyP
      and '[x]' in _bodyP and not _tagsP and len(app._table_grids) == 1)
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

# What a copy of cells carries (field pass): a coloured cell and a word's
# bold, ink and size -- into Word, into a duplicated table below, and into
# another table's cells. All three used to arrive as bare text.
set_body('| h1 | h2 |' + chr(10) + '| --- | --- |' + chr(10)
         + '| aa | big word |' + chr(10) + 'after')
app._render_table_grids()
app.update()
app._grid_apply_style(app._grid_at_line(1), (1, 0, 1, 0), 'highlight',
                      '#c8f7c5')
app.update()
_kS = app.body_text.get('3.0', '3.end').index('big')
app.body_text.tag_add('bold', '3.%d' % _kS, '3.%d' % (_kS + 3))
app.body_text.tag_add(
    app._ensure_color_tag(app.body_text, 'text_color', '#d32f2f'),
    '3.%d' % _kS, '3.%d' % (_kS + 3))
app.body_text.tag_add(
    app._ensure_font_tag(app.body_text, False, False, 20, 'Georgia'),
    '3.%d' % (_kS + 4), '3.%d' % (_kS + 8))
app._render_table_grids()
app.update()
_iS = app._grid_at_line(1)
app._grid_select_range(_iS, (0, 0), (1, 1))
_stub_clipboard(loopback=True)
app._grid_copy_selection({'info': _iS, 'box': (0, 0, 1, 1)})
_htmlS = _written.get('html') or ''
check(f'copied cells leave for Word with their colour, bold, ink and size '
      f'({_htmlS})',
      'background-color:#c8f7c5;' in _htmlS and '<b>big</b>' in _htmlS
      and 'color:#d32f2f;' in _htmlS and 'font-size:20pt;' in _htmlS)


def _cell_recs_of(block_no):
    _blk = core_tables.find_blocks(body())
    if len(_blk) <= block_no:
        return {}
    a, z = _blk[block_no]
    return app._grid_read_cell_styles(a + 1, z - a + 1)


def _carried(recs):
    _runs = (recs.get((1, 1)) or {}).get('runs', [])
    return ((recs.get((1, 0)) or {}).get('paint_bg') == 'highlight_c8f7c5'
            and ('bold', 0, 3) in _runs
            and ('text_color_d32f2f', 0, 3) in _runs
            and any(NO.parse_font_tag(t) and NO.parse_font_tag(t)[2] == 20
                    and (a, z) == (4, 8) for t, a, z in _runs))


app._grid_clear_selection()
app.body_text.mark_set('insert', '4.end')
app.update()
app._on_body_paste()
app.update()
_recS = _cell_recs_of(1)
check(f'a duplicated table keeps each cell\'s colour and its words\' styles '
      f'({_recS})', _carried(_recS))
# Into another table's cells: the copy lands at (1, 0) of a blank one.
set_body('| p | q |' + chr(10) + '| --- | --- |' + chr(10) + '|   |   |'
         + chr(10) + '|   |   |')
app._render_table_grids()
app.update()
app._grid_paste_cells(app._grid_at_line(1), 1, 0)
app.update()
_recS = {(r - 1, c): v for (r, c), v in _cell_recs_of(0).items()}
check(f'cells pasted into a table bring their colour and styles '
      f'({_recS})', _carried(_recS))
# A copy from elsewhere, landing in the same cells, brings none of ours.
set_body('| p | q |' + chr(10) + '| --- | --- |' + chr(10) + '|   |   |'
         + chr(10) + '|   |   |')
app._render_table_grids()
app.update()
app.clipboard_clear()
app.clipboard_append('h1\th2' + chr(10) + 'aa\tother words')
app._grid_paste_cells(app._grid_at_line(1), 1, 0)
app.update()
_recS = _cell_recs_of(0)
check('cells copied from elsewhere bring none of an older copy\'s styles',
      not any(v['runs'] or v['paint_bg'] for v in _recS.values()))
_stub_clipboard()
set_body('')

# The header row is read where its words are: a drawn table's window sits
# at column 0 of that line, and the copy read every style one place to the
# left (audit) -- "Name" red left as "N" plain and "ame" red.
set_body('| Name | Qty |' + chr(10) + '| --- | --- |' + chr(10) + '| a | 1 |')
app._render_table_grids()
app.update()
_kH = app.body_text.get('1.0', '1.end').index('Name')
app.body_text.tag_add(
    app._ensure_color_tag(app.body_text, 'text_color', '#d32f2f'),
    '1.%d' % (_kH + app._col_base(1)), '1.%d' % (_kH + app._col_base(1) + 4))
_iH2 = app._grid_at_line(1)
app._grid_select_range(_iH2, (0, 0), (1, 1))
_stub_clipboard(loopback=True)
app._grid_copy_selection({'info': _iH2, 'box': (0, 0, 1, 1)})
_runsH = (app._grid_cell_clip_styles.get((0, 0)) or {}).get('runs')
check(f'a copied header cell keeps its colour on its own letters ({_runsH}; '
      f'{_written.get("html")})',
      _runsH == [('text_color_d32f2f', 0, 4)]
      and '<span style="color:#d32f2f;">Name</span>' in (_written.get('html') or ''))
app._grid_clear_selection()
_stub_clipboard()

# A highlight given in an open cell reaches the note even when the note is
# left with the cell still open (audit): only closing the cell laid it,
# and leaving a note flushes the cell without closing it.
set_body('| h1 | h2 |' + chr(10) + '| --- | --- |' + chr(10) + '|   | x |')
app._render_table_grids()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 0, select=False)
app.update()
app._apply_body_color('highlight', '#ffe08a')
app._cell_editor['entry'].insert('end', 'abc')
app.update()
_lvState = app.capture_editor_state()
_lvHi = [s for s in _lvState.get('formatting', [])
         if s['style'] == 'highlight' and s.get('value') == '#ffe08a']
_lvRow = _lvState['body'].split(chr(10))[2]
_lvCell = (_lvRow.index('abc'), _lvRow.index('abc') + 3)
_lvAt = len(_lvState['body'].split(chr(10))[0]) + len(
    _lvState['body'].split(chr(10))[1]) + 2
check(f'leaving a note with a highlighted cell still open keeps the '
      f'highlight ({_lvHi}; {_lvRow!r})',
      'abc' in _lvRow and any(s['start'] <= _lvAt + _lvCell[0]
                              and s['end'] >= _lvAt + _lvCell[1]
                              for s in _lvHi))
app._commit_cell_editor()
app.update()

# A copied cell that lands in a column the paste adds keeps its alignment
# (audit): the new column's cells grew, their alignments did not.
set_body('| p | q |' + chr(10) + '| --- | --- |' + chr(10) + '| left | mid |')
app._render_table_grids()
app.update()
app._grid_set_alignment(app._grid_at_line(1), (1, 1, 1, 1),
                        core_tables.ALIGN_CENTER)
app.update()
_iA = app._grid_at_line(1)
app._grid_select_range(_iA, (1, 0), (1, 1))
_stub_clipboard(loopback=True)
app._grid_copy_selection({'info': _iA, 'box': (1, 0, 1, 1)})
app._grid_clear_selection()
app._grid_paste_cells(app._grid_at_line(1), 1, 1)
app.update()
_alA = core_tables.cell_alignments(app.body_text.get('3.0', '3.end'))
check(f'a copied cell pasted into a new column keeps its alignment ({_alA}; '
      f'{body()!r})',
      len(_alA) == 3 and _alA[2] == core_tables.ALIGN_CENTER)
_stub_clipboard()
set_body('')

# A word's size and typeface travel between notes: the HTML carries them
# out to Word, and a paste reads none back (a page's sizes stay behind),
# so our own copy brings them from what it remembered.
set_body('plain big end')
app.body_text.tag_add(
    app._ensure_font_tag(app.body_text, False, False, 20, 'Georgia'),
    '1.6', '1.9')
app.body_text.tag_add('sel', '1.0', '1.end')
app.update()
_stub_clipboard(loopback=True)
app._copy_formatted()
check(f'a sized word leaves with its size and typeface ({_written.get("html")})',
      "font-size:20pt;" in (_written.get('html') or '')
      and "font-family:'Georgia';" in (_written.get('html') or ''))
set_body('')
app._on_body_paste()
app.update()
_fS = [s for s in app._extract_formatting(app.body_text)
       if s['style'] in ('font_size', 'font_family')]
check(f'pasted into a note, it keeps both ({_fS})',
      body() == 'plain big end'
      and {(s['style'], s['value'], s['start'], s['end']) for s in _fS}
      == {('font_size', 20, 6, 9), ('font_family', 'Georgia', 6, 9)})
# The same words from Word bring no size: the remembered copy is ours only.
set_body('')
_stub_clipboard(html='<p>plain <span style="font-size:20pt;'
                     'font-family:Georgia">big</span> end</p>',
                text='plain big end')
app._on_body_paste()
app.update()
check('the same words pasted from elsewhere bring no size or typeface',
      body() == 'plain big end'
      and not [s for s in app._extract_formatting(app.body_text)
               if s['style'] in ('font_size', 'font_family')])
# One word copied from an indented paragraph does not indent the paragraph
# it lands in (audit): the HTML never carried a plain paragraph's indent,
# and the remembered copy must not start to.
set_body('an indented line' + chr(10) + 'plain target here')
app.body_text.mark_set('insert', '1.0')
app.body_text.tag_remove('sel', '1.0', 'end')
app._change_paragraph_indent(+1)
app.body_text.tag_add('sel', '1.3', '1.11')
app.update()
_stub_clipboard(loopback=True)
app._copy_formatted()
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.mark_set('insert', '2.6')
app._on_body_paste()
app.update()
check(f'a word from an indented paragraph pastes without its indent '
      f'({app._paragraph_indent_of(app.body_text, 2)}; {body()!r})',
      app._paragraph_indent_of(app.body_text, 1) == 1
      and app._paragraph_indent_of(app.body_text, 2) == 0
      and 'indented' in app.body_text.get('2.0', '2.end'))
_stub_clipboard()
set_body('')

# The word count counts what the PERSON wrote, not the plumbing: every
# pipe used to count as "a word", an empty 3x3 table claimed twelve.
set_body('two words' + chr(10) + chr(10).join(core_tables.blank_table(3, 3)))
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
app.title_entry.insert(0, 'NoteTableQ')
app.body_text.insert('1.0', '| gergebe | x |' + chr(10)
                     + '| --- | --- |' + chr(10) + '| a | b |')
app.save_current_note(auto=False)
app.update()
_idQ = app.selected_note_id
app.search_var.set('---')
app.refresh_note_list()
app.update()
_hitQ1 = _idQ in app._card_order()
app.search_var.set('gergebe')
app.refresh_note_list()
app.update()
_hitQ2 = _idQ in app._card_order()
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

# ---- THE TWO DROPDOWNS SAY WHAT THEY ARE (C-23) ----
# Both are labelled with their current VALUE -- "Recently updated ▾",
# "All ▾" -- so the words "sort" and "show" appeared nowhere on screen, and
# "All" in particular reads as a state rather than as a control. The
# captions sit ABOVE the row on purpose: the row has 250px for two controls
# and the comments beside it record real clipping fights over exactly that.
_sidebar_captions = [str(w.cget('text'))
                     for w in _walk_widgets(app.sidebar, tk.Label)]
check(f'the sort control is captioned', 'Sort' in _sidebar_captions)
check(f'and the filter control is captioned', 'Show' in _sidebar_captions)
# THE CONTROL that keeps this from being a change of the control text, which
# the register's row explicitly warned against: each control must still SHOW
# its current value, because that is what the sizing was fought over. A
# themed dropdown is a Frame holding a Label wired to the var -- not a
# Button, and cget('text') on it is empty -- so the question is asked of the
# textvariable, which is the thing that makes the label show the value.
_bound_vars = {str(w.cget('textvariable'))
               for w in _walk_widgets(app.sidebar, tk.Label)}
check('and each control still shows its own current value',
      str(app.sort_var) in _bound_vars and str(app.filter_var) in _bound_vars)

# ---- THE TWO CONTROLS REMEMBER, AND THE FILTER STAYS VALID (C-15) ----
# The checkbox a few pixels below them has always been remembered, and so
# have the folded groups beside it. Three controls on one panel, two of them
# remembered: someone who prefers Title A–Z re-picked it at every launch
# with no way to tell why that one preference did not stick.
app.sort_var.set('Title A–Z')
app.filter_var.set(app.FILTER_REPEATING)
app.update()
_stored = NO.load_settings()
check('choosing a sort is written to settings',
      _stored.get('note_sort') == 'Title A–Z')
check('and so is choosing a filter',
      _stored.get('note_filter') == app.FILTER_REPEATING)

# The read side, and the guard on it. A stored value comes off disk and can
# name a sort this version no longer has, or a category this notebook never
# had -- an unknown sort would reach the comparator, and an unknown filter
# would show an empty list with no way to tell why.
NO.save_setting('note_sort', 'Sorted By Moon Phase')
NO.save_setting('note_filter', 'A Category Nobody Has')
_fresh = NO.NoteOrganizer(); _fresh._poll_active_dirty = lambda: None
# Every app a check builds answers its own dialogs before it handles a
# single event. The startup notice is scheduled for 250ms after the window
# and blocks until answered: this notebook holds a note filed under a
# category the settings never had ('Zeta', from the sort checks), which a
# fresh start now brings back and SAYS so -- and an unanswered notice hung
# the script for ten minutes. qa8 has always done this; these three had
# only been lucky that there was nothing to announce.
_fresh.show_info = lambda *a, **k: True
_fresh.update()
check('a stored sort this version does not have falls back to the default',
      _fresh.sort_var.get() == _fresh.SORT_OPTIONS[0])
check('and a stored filter naming an unknown category falls back to All',
      _fresh.filter_var.get() == 'All')
# THE CONTROL: a valid stored pair must actually be restored, or the two
# checks above would pass on an app that simply ignores the file.
NO.save_setting('note_sort', 'Title A–Z')
NO.save_setting('note_filter', app.FILTER_DATED)
_fresh2 = NO.NoteOrganizer(); _fresh2._poll_active_dirty = lambda: None
_fresh2.show_info = lambda *a, **k: True
_fresh2.update()
check('a stored sort that IS on offer comes back',
      _fresh2.sort_var.get() == 'Title A–Z')
check('and so does a stored type filter',
      _fresh2.filter_var.get() == _fresh2.FILTER_DATED)
_fresh.destroy(); _fresh2.destroy()
# The newest type, the same way: a filter left on "📎 With files" is the
# filter found at the next launch.
NO.save_setting('note_filter', app.FILTER_FILES)
_fresh3 = NO.NoteOrganizer(); _fresh3._poll_active_dirty = lambda: None
_fresh3.show_info = lambda *a, **k: True
_fresh3.update()
check('and so does the With files filter',
      _fresh3.filter_var.get() == _fresh3.FILTER_FILES)
_fresh3.destroy()

# ---- TOUCHING A CATEGORY NO LONGER THROWS THE FILTER AWAY ----
# Found by the pre-flight for the row above: the guard that keeps the
# selection valid asked `not in CATEGORY_COLORS`, which is true of BOTH
# type filters -- neither is a category. So filtering to Repeating and then
# adding a category in Settings silently showed everything again. One
# vocabulary now answers both this and the load above.
for _name, _value, _survives in (
        ('the Repeating type filter', app.FILTER_REPEATING, True),
        ('the Dated type filter', app.FILTER_DATED, True),
        ('the With files type filter', app.FILTER_FILES, True),
        ('a category that is gone', 'No Such Category', False)):
    app.filter_var.set(_value)
    app.update()
    check(f'fixture: the filter holds {_name}', app.filter_var.get() == _value)
    app.refresh_category_widgets()
    app.update()
    if _survives:
        check(f'{_name} survives a category being touched',
              app.filter_var.get() == _value)
    else:
        check(f'{_name} is reset to All, as it should be',
              app.filter_var.get() == 'All')
app.filter_var.set('All')
app.sort_var.set(app.SORT_OPTIONS[0])
app.refresh_note_list(); app.update()
# The hint is wired to search_var like everything else in this box, so a
# paste onto it would land glued and then be SEARCHED FOR -- a query of
# "search notes...NoteTableQ" matches nothing and reads as a broken search.
app.search_entry.delete(0, 'end')
app.search_entry.event_generate('<FocusOut>')
app.update()
check('fixture: the search box is showing its hint',
      app.search_entry.get() == NO.NoteOrganizer.SEARCH_PLACEHOLDER)
app.clipboard_clear(); app.clipboard_append('NoteTableQ'); app.update()
app.search_entry.event_generate('<<Paste>>')
app.update()
check('pasting into the search box replaces the hint',
      app.search_entry.get() == 'NoteTableQ')
app.refresh_note_list(); app.update()
check('and the list filters by what was pasted, not by the hint',
      _idQ in app._card_order())

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
      set(app._card_order())
      | {r[1]['id'] for r in app._list_pending if r[0] == 'note'}
      == {n['id'] for n in app.notes})
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
# Cancelled, never just forgotten: a job set to None leaves its timer
# scheduled with nothing tracking it (see _nd_burst).
app._cancel_pending_autosave()
check('fixture: no autosave is pending before the date is pasted',
      not getattr(app, '_autosave_job', None))
app.clipboard_clear(); app.clipboard_append('2026-10-05'); app.update()
# Emptied first rather than selected-then-pasted. Tk's Entry paste deletes
# the selection only on NON-X11 -- on X11 it inserts at the caret and leaves
# the selected text where it is -- so a select_range here passed on Windows
# and failed on the Linux image with the field holding both dates. The app
# ships on Windows, so that difference is the test's problem and not the
# product's; the check is about the date reaching the store either way.
# Watch the SAVE ITSELF, not _schedule_autosave. Replacing the scheduler
# on the instance catches nothing: every binding captured the bound method
# when it was bound, long before any of this, so they still call the
# original. The timer does `self.after(500, self._autosave_now)` and
# captures THAT at schedule time -- which is after this line -- so
# replacing _autosave_now here does get seen.
_pd_fired = {'n': 0}
_pd_real_now = app._autosave_now


def _pd_counting_now(*a, **k):
    _pd_fired['n'] += 1
    return _pd_real_now(*a, **k)


app._autosave_now = _pd_counting_now
try:
    app.date_entry.delete(0, 'end')
    app.date_entry.event_generate('<<Paste>>')
    app.update()
finally:
    app._autosave_now = _pd_real_now
check('the pasted date is in the field', app.date_entry.get() == '2026-10-05')
# THE REQUEST, not the result. The first version of this check called
# _flush_autosave() and then read the store -- and it survived the mutant that
# removed the paste binding entirely, because a forcing call saves whatever
# the editor holds whether anything asked it to or not. That is qa/README's
# own rule, made again here. What this asserts is that the PASTE queued a
# save, which is the thing the binding does.
#
# Counted, not caught pending: a queued job is a fact about a moment, and
# the update() above can outlast the 500ms debounce on a loaded machine --
# a sibling of this shape went red on CI while passing here three times
# running, proved by pausing past the debounce.
#
# "A save is pending OR a save already ran" -- either answers the promise,
# and together they cannot be decided by timing. A pending job alone is a
# fact about a MOMENT: the update() above can outlast the 500ms debounce
# on a loaded machine, the timer fires, the job is cleared, and the check
# reports a missing request about an app that made one. A sibling of that
# shape went red on CI while passing here three times running.
check(f'pasting a date asks for a save, the way typing one does '
      f'(pending={getattr(app, "_autosave_job", None) is not None}, '
      f'fired={_pd_fired["n"]})',
      getattr(app, '_autosave_job', None) is not None or _pd_fired['n'] >= 1)
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
app._cell_editor['entry'].insert('1.0', 'one-new')
app._commit_cell_editor()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 1)
app.update()
app._cell_editor['entry'].delete('1.0', 'end')
app._cell_editor['entry'].insert('1.0', 'two-new')
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
      'one-new' in _txtU0 and 'two-new' in _txtU0
      and 'one-new' in _txtU1 and 'two-new' not in _txtU1)
check('the second Ctrl+Z takes back the edit before it, not the redraw',
      'one-new' not in _txtU2
      and '| 1 | 2 |' in _txtU2.split(chr(10))[2])
_iU2 = app._grid_at_line(1)
check('the drawn grid follows the undone text',
      _iU2 is not None and _iU2['cells'][(1, 0)]['value'] == '1')
app._body_undo_redo('redo')
app.update()
check('redo brings the edit and its drawing back',
      'one-new' in app.body_text.get('1.0', 'end-1c')
      and app._grid_at_line(1)['cells'][(1, 0)]['value'] == 'one-new')

# An inserted table leaves whole on a single undo, drawing included.
set_body('text top')
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
      and 'text top' in _txtU3)
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
# ...and every Ctrl+Z and Ctrl+Y after it changes something. The rewrite is
# split where the tables come down, and their drawing again was left as a
# journal step of its own: in any note with a drawn table, the first Ctrl+Z
# after a renumber changed nothing on screen, and so did the last Ctrl+Y.
set_body('1. one' + chr(10) + '2. two' + chr(10) + '| A | B |'
         + chr(10) + '| --- | --- |' + chr(10) + '| x | y |')
app._render_table_grids()
app.update()
app._reset_text_undo()
app.body_text.mark_set('insert', '1.end')
_rw_start = app.body_text.get('1.0', 'end-1c')
if take_focus(app.body_text):
    app._on_body_return(None)
    app.update()
_rw_after = app.body_text.get('1.0', 'end-1c')
_rw_seen = []
for _rw_k in ('undo', 'undo', 'redo', 'redo'):
    _rw_was = app.body_text.get('1.0', 'end-1c')
    app._body_undo_redo(_rw_k)
    app.update()
    _rw_seen.append(app.body_text.get('1.0', 'end-1c') != _rw_was)
    if len(_rw_seen) == 2:
        _rw_back = app.body_text.get('1.0', 'end-1c') == _rw_start
check(f'every Ctrl+Z and Ctrl+Y after a renumber beside a drawn table '
      f'changes something ({_rw_seen})',
      _rw_after != _rw_start and _rw_seen == [True, True, True, True]
      and _rw_back and app.body_text.get('1.0', 'end-1c') == _rw_after)

# Enter in a numbered list keeps the note where it is being read (field
# pass): the renumber rewrote the whole body, which threw the view to the
# note's first line and tore every drawn table down to draw it again.
for _vk in ('plain', 'with a table above'):
    _vk_lines = ['prose line %d' % _i for _i in range(80)]
    if _vk == 'with a table above':
        _vk_lines = ['| A | B |', '| --- | --- |', '| x | y |'] + _vk_lines
    _vk_lines += (['1. one', '2. two', '3. three']
                  + ['tail %d' % _i for _i in range(60)])
    set_body(chr(10).join(_vk_lines))
    app._render_table_grids()
    app.update()
    _vk_at = _vk_lines.index('1. one') + 1
    app.body_text.yview('%d.0' % (_vk_at - 10))
    app.update()
    _vk_top0 = app.body_text.index('@0,0')
    _vk_wins = app.body_text.window_names()
    app.body_text.mark_set('insert', '%d.end' % _vk_at)
    if take_focus(app.body_text):
        app._on_body_return(None)
        app.update()
    _vk_top1 = app.body_text.index('@0,0')
    check(f'Enter in a numbered list keeps the view where it was ({_vk}: '
          f'{_vk_top0} -> {_vk_top1})',
          _vk_top1 == _vk_top0
          and app.body_text.get('%d.0' % (_vk_at + 1), '%d.end' % (_vk_at + 2))
          == '2. ' + chr(10) + '3. two'
          and app.body_text.index('insert') == '%d.3' % (_vk_at + 1))
    if _vk == 'with a table above':
        check('...and leaves the drawn table standing, not drawn again',
              bool(_vk_wins) and app.body_text.window_names() == _vk_wins)
# A marker that grows (9 -> 10) moves its words, and their styles go with
# them: bold stays on exactly the word it was on.
set_body(chr(10).join('%d. item%d' % (_i, _i) for _i in range(1, 10)))
app.body_text.tag_add('bold', '9.3', '9.8')
app.body_text.mark_set('insert', '1.end')
if take_focus(app.body_text):
    app._on_body_return(None)
    app.update()
check(f'a renumber that grows a marker keeps the bold on its word '
      f'({app.body_text.tag_ranges("bold")})',
      app.body_text.get('10.0', '10.end') == '10. item9'
      and [str(i) for i in app.body_text.tag_ranges('bold')]
      == ['10.4', '10.9']
      and app._list_kind_of(app.body_text, 10) == 'number'
      # ...and the new digits wear the line's list indent like any other
      # item's start does (Tk gives inserted text only tags on both sides).
      and set(app.body_text.tag_names('10.0'))
      == set(app.body_text.tag_names('1.0')))
# A caret at an item's start stays there while its number changes under it.
set_body('1. a' + chr(10) + '2. b' + chr(10) + '3. c')
app.body_text.mark_set('insert', '2.0')
app.body_text.tag_remove('sel', '1.0', 'end')
app._change_paragraph_indent(+1)
app.update()
check(f'indenting an item keeps the caret at its start '
      f'({app.body_text.index("insert")}; {body()!r})',
      app.body_text.index('insert') == '2.0'
      and app.body_text.get('3.0', '3.end') == '2. c')
# A selection across the items stays one piece through the renumber
# (audit): the new digits went in without it, leaving holes.
set_body('1. a' + chr(10) + '2. b' + chr(10) + '3. c' + chr(10) + '4. d')
app.body_text.tag_add('sel', '2.0', '4.end')
app.body_text.mark_set('insert', '4.end')
app._change_paragraph_indent(+1)
app.update()
_selR = [str(i) for i in app.body_text.tag_ranges('sel')]
check(f'a selection across a renumbered list stays whole ({_selR})',
      _selR == ['2.0', '4.end'.replace('end', str(len(
          app.body_text.get('4.0', '4.end'))))])
app.body_text.tag_remove('sel', '1.0', 'end')
set_body('')
# ...also where an alignment meets the table's window: a centred line right
# above the table (its alignment runs through its line break, up to the
# window), or the table placed with "Center table on page" (the drawing
# gives the window its line's alignment). The two sides of the drawing-again
# part were compared by moving one into the other's windows, which put an
# index at a window's column past the window, where Tk does not: the first
# Ctrl+Z and the last Ctrl+Y changed nothing again -- and every such empty
# step took one of the journal's 100, so a long session's deepest Ctrl+Z
# lost the note's bold and colours after half of them.
for _ra_how in ('centred line above it', 'table placed centre'):
    set_body('1. one' + chr(10) + '2. two' + chr(10) + 'Title' + chr(10)
             + '| A | B |' + chr(10) + '| --- | --- |' + chr(10) + '| x | y |')
    app._render_table_grids()
    app.update()
    if _ra_how == 'centred line above it':
        app.body_text.mark_set('insert', '3.2')
        app._set_paragraph_align('center')
    else:
        app._grid_set_table_align(app._table_grids[0], 'center')
        app._render_table_grids()
    app.update()
    # What the case needs: the window is at 4.0, and the alignment reaches it
    # -- ending there (the line above) or on it (the table placed).
    _ra_window = [t for t in app.body_text.tag_names('4.0')
                  if t == 'align_center']
    _ra_pre = (app.body_text.window_names()
               and app.body_text.index(app.body_text.window_names()[0]) == '4.0'
               and (bool(_ra_window) if _ra_how == 'table placed centre' else
                    [str(i) for i in app.body_text.tag_ranges('align_center')]
                    == ['3.0', '4.0']))
    app._reset_text_undo()
    app.body_text.mark_set('insert', '1.end')
    _ra_start = app.body_text.get('1.0', 'end-1c')
    if take_focus(app.body_text):
        app._on_body_return(None)
        app.update()
    _ra_after = app.body_text.get('1.0', 'end-1c')
    _ra_seen = []
    for _ra_k in ('undo', 'undo', 'redo', 'redo'):
        _ra_was = app.body_text.get('1.0', 'end-1c')
        app._body_undo_redo(_ra_k)
        app.update()
        _ra_seen.append(app.body_text.get('1.0', 'end-1c') != _ra_was)
        if len(_ra_seen) == 2:
            _ra_back = app.body_text.get('1.0', 'end-1c') == _ra_start
    check(f'every Ctrl+Z and Ctrl+Y after a renumber beside a drawn table, '
          f'{_ra_how}, changes something ({_ra_seen}; case set up '
          f'{bool(_ra_pre)})',
          _ra_pre and _ra_after != _ra_start
          and _ra_seen == [True, True, True, True]
          and _ra_back and app.body_text.get('1.0', 'end-1c') == _ra_after)
# What "the same once the windows are accounted for" means: a range split
# only by a window's character is one range, and a range over a window's
# character alone is none -- the window's own tags are its line's.
_wf_sig = (1, 1)
check('a range split only by a window reads as one range without it',
      NO._fmt_window_free((_wf_sig, ('4.0',),
                           (('align_center', '3.0 4.0 4.1 7.0'),)))
      == NO._fmt_window_free((_wf_sig, (), (('align_center', '3.0 7.0'),))))
check('a range over a window alone is no range without it',
      NO._fmt_window_free((_wf_sig, ('4.0',),
                           (('align_center', '4.0 4.1'),
                            ('bold', '2.0 2.3'))))
      == NO._fmt_window_free((_wf_sig, (), (('bold', '2.0 2.3'),))))

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

# Tk paints a frame's border in highlightcolor while the keyboard is inside
# it: the find bar's accent was the system grey all the time it was used.
from _qa_support import ring_mismatches as _ring_mismatches
_rm_found = _ring_mismatches(app)
check(f'a bordered frame with a box inside keeps its border colour while the '
      f'keyboard is in the box -- the find bar too ({_rm_found})',
      not _rm_found)
# And a theme with another accent recolours both, the bar being built once.
_rm_theme = app.theme_name
app.set_theme('dark_ocean' if _rm_theme != 'dark_ocean' else 'dark')
app.update()
_rm_colours = {o: str(app._find_bar.cget(o)).lower()
               for o in ('highlightbackground', 'highlightcolor')}
check(f'...and a theme with another accent gives the find bar its border in '
      f'both colours ({_rm_colours}, accent {app.colors["accent"]})',
      set(_rm_colours.values()) == {app.colors['accent'].lower()})
app.set_theme(_rm_theme)
app.update()
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
# Boxed, as a table cell's match is: by its fill alone it was one shade among
# three to a colour-blind eye (all four readers of the simulated screens).
def _find_boxed():
    try:
        return (str(app.body_text.tag_cget('find_current', 'relief')) == 'solid'
                and int(str(app.body_text.tag_cget('find_current', 'borderwidth')
                            or 0)) >= 1)
    except (tk.TclError, ValueError):
        return False
check('find/prose: the current match is boxed, not told apart by colour alone',
      _find_boxed() and not str(app.body_text.tag_cget('find_all', 'relief') or ''))
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
# The Aa box (and opening the bar) rescans directly while a typed query's
# rescan waits. Clearing the job there left the waiting timer scheduled
# with nothing tracking it -- the relay qa1's "a save run directly"
# check describes for the autosave. The waiting rescan stays tracked
# now: it may carry a reveal the direct one does not.
app._open_find()
app.update()
app._find_var.set('beta')              # the typed query's rescan waits
_fd_job = getattr(app, '_find_debounce', None)
app._find_case.set(True)
app._find_rescan(reveal=False)         # what the Aa box runs
_fd_waiting = _qa_waiting(app, '_find_debounce_fire')
check(f'find: a direct rescan leaves the waiting one tracked ({_fd_job} '
      f'-> {getattr(app, "_find_debounce", None)}, waiting {_fd_waiting})',
      _fd_job is not None
      and _fd_waiting == [str(getattr(app, '_find_debounce', None))])
app._find_case.set(False)
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
# The current match is the full accent, and the note's own text colour fell
# below 4.5:1 on it in every theme; its words are the ones for that fill.
check('find/theme: the current match\'s words are the ones that read on the '
      'accent, re-picked for the new theme',
      app.body_text.tag_cget('find_current', 'foreground').lower()
      == app._on_fill('accent').lower())
check('find/theme: the current match stays boxed through the theme switch',
      _find_boxed())
# The "Aa" case checkbox is long-lived (built once with the bar), so it must
# follow the theme. It draws its own well and mark now: Tk painted its mark
# in the words' colour, light on dark themes, on a light well, so a ticked
# box read as empty. The question is that it draws the shared box (redrawn
# with the theme; qa4 judges its pixels on every theme) on the current
# surface.
check('find/theme: the case checkbox draws its own box and follows the theme',
      str(app._find_case_cb.cget('indicatoron')) in ('0', 'false', 'False')
      and str(app._find_case_cb.cget('selectimage')) == str(app._tick_images[1])
      and str(app._find_case_cb.cget('bg')).lower() == app.colors['card'].lower())
# The bar's accent-coloured border is likewise long-lived; changing the
# accent while the bar is open must recolour it, not leave the old accent
# framing the bar.
check('find/theme: the bar border follows the accent',
      str(app._find_bar.cget('highlightbackground')).lower()
      == app.colors['accent'].lower())
app._close_find()
app.update()

# ============================================================
# THE PALETTE: FILLS, THE WORDS ON THEM, AND THE TEXT SHADES
# ============================================================
# Accent, danger and success are fills; the words ON a fill come from
# letters_on (white or near-black, by measured contrast) and words on an
# ordinary surface from the *_text shades. A fill built with its words
# written down by hand reads on some themes and not others -- so every
# widget showing words on a fill is measured, in every theme.
from noteorganizer.core.themes import contrast_ratio as _pl_ratio
_pl_theme = app.theme_name
_pl_roles = ('accent', 'accent_hover', 'danger', 'success')


def _pl_hex(colour):
    """Any Tk colour (a name such as 'white' too) as #rrggbb."""
    return '#%02x%02x%02x' % tuple(v // 256 for v in app.winfo_rgb(colour))


def _pl_unreadable():
    fills = {app.colors[r].lower() for r in _pl_roles}
    bad = []

    def walk(w):
        try:
            bg, fg = str(w.cget('bg')).lower(), str(w.cget('fg'))
            words = str(w.cget('text'))
        except Exception:
            bg = words = None
        if bg in fills and words:
            if _pl_ratio(_pl_hex(fg), bg) < 4.5:
                bad.append((w.winfo_class(), words[:18], fg, bg))
        for c in w.winfo_children():
            walk(c)
    walk(app)
    return bad


def _pl_button(text):
    found = []

    def walk(w):
        for c in w.winfo_children():
            if isinstance(c, NO.tk.Button) and str(c.cget('text')) == text:
                found.append(c)
            walk(c)
    walk(app)
    return found[0] if found else None


app.show_settings_page(); app.update()
_pl_bad = {}
for _pl_t in NO.THEMES:
    app.set_theme(_pl_t); app.update()
    _pl_found = _pl_unreadable()
    if _pl_found:
        _pl_bad[_pl_t] = _pl_found[:4]
app.hide_settings_page()
app.set_theme(_pl_theme); app.update()
check(f'palette: the words on every filled widget read at 4.5:1, in every '
      f'theme ({_pl_bad})', not _pl_bad)

# The editor's row: Save is the one filled button, light with dark words in
# every theme; Delete is quiet with the warning's text shade (the note goes
# to the Trash), and Generate code is quiet, dressed as Duplicate is.
_pl_save, _pl_del, _pl_gen, _pl_dup = (
    _pl_button(t) for t in ('💾 Save', '🗑 Delete', '📋 Generate code',
                            '📄 Duplicate'))
_pl_row = {}
if None in (_pl_save, _pl_del, _pl_gen, _pl_dup):
    _pl_row['missing'] = [b is None for b in (_pl_save, _pl_del, _pl_gen, _pl_dup)]
else:
    for _pl_t in NO.THEMES:
        app.set_theme(_pl_t); app.update()
        _pl_c = app.colors
        _pl_ok = (
            str(_pl_save.cget('bg')).lower() == _pl_c['success'].lower()
            and _pl_hex(_pl_save.cget('fg')) == NO.LETTERS_DARK
            and str(_pl_del.cget('bg')).lower() == _pl_c['sidebar'].lower()
            and str(_pl_del.cget('fg')).lower() == _pl_c['danger_text'].lower()
            and str(_pl_gen.cget('bg')).lower() == _pl_c['sidebar'].lower()
            and str(_pl_gen.cget('fg')).lower() == _pl_c['text'].lower()
            and str(_pl_gen.cget('bg')) == str(_pl_dup.cget('bg')))
        if not _pl_ok:
            _pl_row[_pl_t] = (str(_pl_save.cget('fg')), str(_pl_del.cget('fg')),
                              str(_pl_gen.cget('bg')), str(_pl_gen.cget('fg')))
    app.set_theme(_pl_theme); app.update()
check(f'palette: Save is the one filled button, with dark words; Delete is quiet '
      f'in red words and Generate code quiet like Duplicate, in every theme '
      f'({_pl_row})', not _pl_row)

# A widget no theme switch tracks -- the way the rebuilt panels build
# theirs -- keeps words that read on its fill: the straggler net picks them
# by the fill they sit on, whether written as a value or as Tk's 'white'.
# Words that are not on a fill are not its business.
_pl_white = next((t for t in NO.THEMES
                  if NO.letters_on(NO.THEMES[t]['accent']) == NO.LETTERS_LIGHT),
                 None)
_pl_dark = next((t for t in NO.THEMES
                 if NO.letters_on(NO.THEMES[t]['accent']) == NO.LETTERS_DARK),
                None)
if _pl_white is None or _pl_dark is None:
    check(f'palette fixture: one theme wants white words on its accent and '
          f'another near-black ({_pl_white}, {_pl_dark})', False)
else:
    app.set_theme(_pl_white); app.update()
    _pl_probe = NO.tk.Button(app.editor, text='probe', bg=app.colors['accent'],
                             fg=app._on_fill('accent'))
    _pl_named = NO.tk.Label(app.editor, text='probe', bg=app.colors['danger'],
                            fg='white')
    _pl_plain = NO.tk.Label(app.editor, text='probe', bg=app.colors['sidebar'],
                            fg='white')
    app.set_theme(_pl_dark); app.update()
    _pl_there = (_pl_hex(_pl_probe.cget('fg')), str(_pl_probe.cget('bg')).lower())
    _pl_named_there = _pl_hex(_pl_named.cget('fg'))
    app.set_theme(_pl_white); app.update()
    _pl_back = _pl_hex(_pl_probe.cget('fg'))
    check(f'palette: an untracked button\'s words follow its fill across a theme '
          f'switch, and back ({_pl_white} -> {_pl_dark}: {_pl_there}; back: '
          f'{_pl_back})',
          _pl_there == (NO.LETTERS_DARK, NO.THEMES[_pl_dark]['accent'].lower())
          and _pl_back == NO.LETTERS_LIGHT)
    check(f'palette: Tk\'s own "white" on a fill is re-picked too, and "white" '
          f'off a fill is left alone ({_pl_named_there}, '
          f'{_pl_plain.cget("fg")})',
          _pl_named_there == NO.letters_on(NO.THEMES[_pl_dark]['danger'])
          and str(_pl_plain.cget('fg')) == 'white')
    for _pl_w in (_pl_probe, _pl_named, _pl_plain):
        _pl_w.destroy()

# The safety net above repaints a fill's words at every theme switch, so it
# would hide a button built with its words written down by hand; what a
# check must see is the mechanism -- the tracked fills name their words.
_pl_reg = {}
for _pl_w, _pl_map in app.themed_widgets:
    try:
        _pl_txt = str(_pl_w.cget('text'))
    except Exception:
        continue
    if _pl_txt in ('💾 Save', '🗑 Delete', '+ New Note', '+ Add file', '🗑 Trash',
                   '🗂 Category ▾'):
        _pl_reg[_pl_txt] = (_pl_map.get('bg'), _pl_map.get('fg'))
# The selection bar's Trash, like the editor's Delete, moves notes to the
# Trash: quiet, in the warning's words; its Category menu is quiet, as Export.
check(f'palette: the filled buttons built once name their words for the theme '
      f'switch, not a colour written down; the moves to the Trash are quiet '
      f'({_pl_reg})',
      _pl_reg == {'💾 Save': ('success', 'on_success'),
                  '🗑 Delete': ('sidebar', 'danger_text'),
                  '+ New Note': ('accent', 'on_accent'),
                  '+ Add file': ('accent', 'on_accent'),
                  '🗑 Trash': ('card', 'danger_text'),
                  '🗂 Category ▾': ('card', 'text')})

# The row reads Save, Generate code, Delete -- Save no longer beside Delete --
# and Tab walks it in that order; each button names its pressed colours,
# which Tk otherwise drew in the system's grey with black words.
_pl_press = {}
for _pl_w, _pl_map in app.themed_widgets:
    try:
        _pl_txt = str(_pl_w.cget('text'))
    except Exception:
        continue
    if _pl_txt in ('💾 Save', '📋 Generate code', '🗑 Delete', '📄 Duplicate'):
        _pl_press[_pl_txt] = (_pl_map.get('activebackground'),
                              _pl_map.get('activeforeground'))
check(f'palette: the editor\'s buttons name their pressed colours ({_pl_press})',
      _pl_press == {'💾 Save': ('success_pressed', 'on_success'),
                    '📋 Generate code': ('card', 'text'),
                    '🗑 Delete': ('card', 'danger_text'),
                    '📄 Duplicate': ('card', 'text')})
if None in (_pl_save, _pl_del, _pl_gen):
    check('palette fixture: the editor\'s row was found', False)
else:
    _pl_cells = [(int(b.grid_info().get('row', -1)), int(b.grid_info().get('column', -1)))
                 for b in (_pl_save, _pl_gen, _pl_del)]
    check(f'palette: the row reads Save, Generate code, Delete, and Tab walks it '
          f'so ({_pl_cells})',
          _pl_cells == [(0, 0), (0, 1), (0, 2)]
          and str(_pl_save.tk_focusNext()) == str(_pl_gen)
          and str(_pl_gen.tk_focusNext()) == str(_pl_del))

# Words on an ordinary surface take the role's text shade, not its fill.
_pl_dark = _pl_dark or 'dark'
app.set_theme(_pl_dark); app.update()
_pl_texts = {name: str(getattr(app, name).cget('fg')).lower()
             for name in ('rec_summary_lbl', 'calendar_return_btn',
                          'occurrence_banner')}
app.set_theme(_pl_theme); app.update()
check(f'palette: the repeat summary and the two calendar lines wear the '
      f'accent\'s text shade after a theme switch ({_pl_texts})',
      set(_pl_texts.values())
      == {NO.THEMES[_pl_dark]['accent_text'].lower()})

# A colour the person picks shows whole on a card's stripe; its words in the
# tags row take a shade of it that reads on the card. Both ways a card gets
# its colours are read: drawn by a rebuild, and recoloured by a theme switch.
_pl_cards = [NO.normalize_note(n) for n in (
    {'id': 7701, 'title': 'PaleCategory', 'body': 'x', 'category': 'Personal',
     'created': '2030-01-01 09:00:00', 'updated': '2030-01-01 09:00:00'},
    {'id': 7702, 'title': 'PaleOwn', 'body': 'x', 'category': 'General',
     'color': '#fee440',
     'created': '2030-01-01 09:00:00', 'updated': '2030-01-01 09:00:01'})]
app.notes.extend(_pl_cards)
app.refresh_note_list(); app.update()
_pl_words = {}


def _pl_card_reads(how):
    for _pl_n in _pl_cards:
        _pl_v = app._card_view(_pl_n['id'])
        _pl_want = app.get_note_color(_pl_n).lower()
        if (_pl_v is None or str(_pl_v['stripe']).lower() != _pl_want
                or _pl_ratio(_pl_hex(_pl_v['tags_fill']), app.colors['card']) < 4.6):
            _pl_words[(app.theme_name, how, _pl_n['title'])] = (
                _pl_v and (_pl_v['stripe'], _pl_v['tags_fill']))


for _pl_t in ('light', 'dark_forest'):
    app.set_theme(_pl_t); app.update()
    _pl_card_reads('recoloured')
    app.refresh_note_list(); app.update()
    _pl_card_reads('drawn')
app.notes = [n for n in app.notes if n['id'] not in (7701, 7702)]
app.set_theme(_pl_theme)
app.refresh_note_list(); app.update()
check(f'palette: a picked colour stays whole on the card\'s stripe and its tags '
      f'row reads at 4.6:1, drawn and recoloured ({_pl_words})', not _pl_words)

# The open tab stands taller than the other. clam's own padding for a
# selected tab beat the app's and drew it SMALLER: its shape said the
# opposite of its colour. Read where each tab begins, under two themes.
def _pl_tab_tops():
    nb = app.notebook
    tops = {}
    for y in range(0, 80):
        for x in range(0, max(1, nb.winfo_width()), 3):
            try:
                i = nb.index('@%d,%d' % (x, y))
            except tk.TclError:
                continue
            if isinstance(i, int):
                tops.setdefault(i, y)
        if len(tops) >= 2:
            break
    return tops


_pl_tabs = {}
for _pl_t in (_pl_theme, 'dark_forest' if _pl_theme != 'dark_forest' else 'light'):
    app.set_theme(_pl_t); app.update()
    for _pl_open in (app.TAB_NOTES, app.TAB_CALENDAR):
        app.notebook.select(_pl_open); app.update()
        _pl_i = app.notebook.index(_pl_open)
        _pl_top = _pl_tab_tops()
        _pl_tabs[(_pl_t, _pl_i)] = _pl_top
        if not (len(_pl_top) == 2 and all(
                _pl_top[_pl_i] < y for j, y in _pl_top.items() if j != _pl_i)):
            _pl_tabs[(_pl_t, _pl_i, 'WRONG')] = True
app.set_theme(_pl_theme)
app.notebook.select(app.TAB_NOTES); app.update()
check(f'palette: the open tab stands taller than the other, under both themes '
      f'({_pl_tabs})',
      len(_pl_tabs) == 4 and not any(k[-1] == 'WRONG' for k in _pl_tabs))

# The tabs' focus ring is for the keyboard: after a click it stayed dotted on
# the open tab until the window lost focus. A click hides it (the ring drawn
# in the tab's own fill), the arrow keys or a Tab landing on the tabs show it.
from tkinter import ttk as _rg_ttk


def _rg_ring():
    return str(_rg_ttk.Style().lookup('TNotebook.Tab', 'focuscolor')).lower()


def _rg_on_first_tab(x, y):
    try:
        return app.notebook.index('@%d,%d' % (x, y)) == 0
    except tk.TclError:
        return False


_rg_seen = {}
_rg_xy = next(((x, y) for y in range(2, 40) for x in range(2, 200, 4)
               if _rg_on_first_tab(x, y)), None)
if _rg_xy:
    app.notebook.event_generate('<ButtonPress-1>', x=_rg_xy[0], y=_rg_xy[1])
    app.notebook.event_generate('<ButtonRelease-1>', x=_rg_xy[0], y=_rg_xy[1])
    app.update()
_rg_seen['click'] = _rg_ring()
_rg_other = next(t for t in NO.THEMES if t != app.theme_name)
app.set_theme(_rg_other); app.update()
_rg_seen['theme'] = _rg_ring()
_rg_hidden_ok = (_rg_seen['click'] != app._on_fill('accent').lower()
                 and _rg_seen['theme'] == app.colors['accent'].lower())
app.notebook.event_generate('<Right>'); app.update()
_rg_seen['arrow'] = _rg_ring()
_rg_arrow_ok = _rg_seen['arrow'] == app._on_fill('accent').lower()
app.notebook.select(app.TAB_NOTES); app.update()
app._set_tab_ring(False)
_rg_prev = app.notebook.tk_focusPrev()
if _rg_prev is not None:
    # A generated key goes to the window holding the keyboard, so the Tab
    # starts where a person's would: on the widget before the tabs.
    _rg_prev.focus_force(); app.update()
    _rg_prev.event_generate('<Tab>'); app.update()
_rg_seen['tabbed'] = _rg_ring()
app.set_theme(_pl_theme); app.notebook.select(app.TAB_NOTES); app.update()
check(f'palette: a click on the tabs hides their focus ring, through a theme '
      f'switch too ({_rg_xy}, {_rg_seen})', bool(_rg_xy) and _rg_hidden_ok)
check(f'palette: the arrow keys and a Tab landing on the tabs show the ring again '
      f'({_rg_prev}, {_rg_seen})',
      _rg_arrow_ok and _rg_prev is not None
      and _rg_seen['tabbed'] == app._on_fill('accent').lower())

# The colour palette's tick marks the colour in use -- the only sign of it
# when two swatches look alike to a colour-blind eye -- and was white on 13
# of its 20 colours (1.3:1 on the yellow).
from noteorganizer.core.themes import contrast_ratio as _pk_ratio


def _pk_walk(w):
    yield w
    for child in w.winfo_children():
        yield from _pk_walk(child)


_pk_bad = []
for _pk_c in NO.PALETTE_COLORS:
    app._show_color_palette(app.title_entry, _pk_c, lambda c: None); app.update()
    _pk_pop = getattr(app, '_mini_popup', None)
    _pk_ticks = [(cv, item) for cv in _pk_walk(_pk_pop) if isinstance(cv, tk.Canvas)
                 for item in cv.find_withtag('tick')] if _pk_pop else []
    _pk_fill = (_pk_ticks[0][0].itemcget(_pk_ticks[0][1], 'fill')
                if len(_pk_ticks) == 1 else None)
    # Through Tk's own reading, so a colour NAME ("white") is measured too
    # rather than crashing the measure that only knows #rrggbb.
    try:
        _pk_fill = '#%02x%02x%02x' % tuple(v // 257 for v in app.winfo_rgb(_pk_fill))
    except (tk.TclError, TypeError):
        _pk_fill = None
    if not (_pk_fill and _pk_ratio(_pk_fill, _pk_c) >= 4.1):
        _pk_bad.append((_pk_c, len(_pk_ticks), _pk_fill))
    app._dismiss_mini_popup(); app.update()
check(f'palette: the colour picker\'s tick reads on every colour it can sit on '
      f'({_pk_bad or len(NO.PALETTE_COLORS)})', not _pk_bad)

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

# Her re-test (case 600): the bar belongs to the note. Leaving it -- for
# another note, the Calendar or Settings -- puts it away, and Ctrl+F brings
# back its words; the same note loaded again over itself (a save's reload,
# Restore previous) is the same search and keeps the bar.
_fz_id = next(n['id'] for n in app.notes if n.get('title') == 'FindA')
app.load_note(app.find_note(_fz_id)); app.update()
app._open_find(); app._find_var.set('switchword'); app._find_rescan(reveal=True)
app.update()
app.load_note(app.find_note(_fz_id)); app.update()
_fz_same = (app._find_open, len(app._find_matches))
app.new_note(); app.update()
_fz_new = (app._find_open, app._find_bar.winfo_manager())
app._open_find(); app.update()
_fz_back = (app._find_open, app._find_var.get())
check(f'find/switch: the same note loaded again keeps the bar and its search, '
      f'another note puts it away, and Ctrl+F brings its words back '
      f'({_fz_same}; {_fz_new}; {_fz_back})',
      _fz_same == (True, 2) and _fz_new == (False, '')
      and _fz_back == (True, 'switchword'))
# Words found nowhere: the box takes a tint of the theme's warning colour,
# mixed from the palette -- one fixed dark red served every theme, and on
# a light one the words typed were dark on dark. A theme switched while it
# shows keeps the tint, mixed again (the editor has a theme toggle).
_fz_tint = {}
_fz_theme = app.theme_name
for _fz_t in ('light', 'dark_forest'):
    app.set_theme(_fz_t); app.update()
    _fz_tint[_fz_t] = (str(app._find_entry.cget('bg')).lower()
                       == NO.miss_surface(app.colors).lower())
app.set_theme(_fz_theme); app.update()
app.load_note(app.find_note(_fz_id)); app.update()
app._open_find()
app._find_var.set('zz-nowhere-zz'); app._find_rescan(reveal=False); app.update()
_fz_tint['here'] = (str(app._find_entry.cget('bg')).lower()
                    == NO.miss_surface(app.colors).lower())
app._find_var.set('switchword'); app._find_rescan(reveal=False); app.update()
_fz_found_bg = str(app._find_entry.cget('bg')).lower()
check(f'find/miss: words found nowhere tint the box with the theme\'s warning '
      f'colour, mixed again on a theme switch, and found words take it off '
      f'({_fz_tint}; {_fz_found_bg})',
      all(_fz_tint.values()) and len(_fz_tint) == 3
      and _fz_found_bg == app.colors['sidebar'].lower())
# The Calendar and Settings put it away too; Ctrl+F from either comes back
# to the note first, and the tab change that follows must not close it.
app.notebook.select(app.TAB_CALENDAR); app.update()
_fz_cal = app._find_open
app._shortcut_find(); app.update()
_fz_cal_back = (app.notebook.index('current') == app.TAB_NOTES, app._find_open)
app.show_settings_page(); app.update()
_fz_set = app._find_open
app._shortcut_find(); app.update()
_fz_set_back = (bool(getattr(app, '_settings_open', False)), app._find_open)
check(f'find/leave: the Calendar and Settings put the bar away, and Ctrl+F '
      f'from either brings it back open ({_fz_cal}, {_fz_cal_back}, '
      f'{_fz_set}, {_fz_set_back})',
      _fz_cal is False and _fz_cal_back == (True, True)
      and _fz_set is False and _fz_set_back == (False, True))
# The keyboard: put away from its own box, it goes to the window, not into
# a hidden box; put away while it is elsewhere -- a note card clicked in
# the list -- it stays where it went. Recorded, not polled.
_fz_asked = []
_fz_real_focus_set = tk.Misc.focus_set
tk.Misc.focus_set = lambda w: (_fz_asked.append(w), _fz_real_focus_set(w))[1]
try:
    app.title_entry.focus_set(); app.update()
    del _fz_asked[:]
    app._hide_find()
    _fz_elsewhere = list(_fz_asked)
    app._open_find(); app.update()
    app._find_entry.focus_set(); app.update()
    del _fz_asked[:]
    app._hide_find()
    _fz_own = list(_fz_asked)
finally:
    tk.Misc.focus_set = _fz_real_focus_set
app.update()
check(f'find/leave: put away, the bar takes the keyboard off its own box and '
      f'nowhere else ({_fz_elsewhere}; {_fz_own})',
      _fz_elsewhere == [] and _fz_own == [app])

# ---- LIFT #2: cell styling, raw-row Tab, category dropdown, share panel ----

# Bold/italic INSIDE the cell editor (_editor_apply_style's chars walk).
set_body('| stylecell | b |\n| c | d |')
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
set_body('| one | two | three |')
app.body_text.mark_set('insert', '1.3')
_moved = app._tab_in_table(1)
app.update()
check('Tab advances the caret to the next raw cell and selects it',
      _moved and app.body_text.get('sel.first', 'sel.last') == 'two')
_moved = app._tab_in_table(-1)
app.update()
check('Shift-Tab walks back to the first cell',
      _moved and app.body_text.get('sel.first', 'sel.last') == 'one')

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
app.body_text.insert('1.0', 'something')
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
check('and warns that attachments are not included, naming where they do go',
      any("not attached files" in t and 'Settings → Backup → Export' in t
          for t in _share_lbls))
# Every sentence that sends someone to the backup names a place that exists
# (field pass): three said "Import (ZIP)" / "Export (ZIP)", which no screen
# has, and "use Export for files" left three exports to guess between.
from noteorganizer.core import sharing as _sh_core
import base64 as _sh_b64, zlib as _sh_zlib
_sh_many = _sh_core.SHARE_CODE_PREFIX + _sh_b64.urlsafe_b64encode(_sh_zlib.compress(
    json.dumps({'v': 1, 'notes': [{'title': 'x'}] * (_sh_core.MAX_SHARED_NOTES + 1)}
               ).encode('utf-8'))).decode('ascii')
_sh_said = []
for _sh_code in ('NOTE1:' + 'A' * (_sh_core.MAX_SHARE_CODE_CHARS + 1),
                 _sh_core.SHARE_CODE_PREFIX + 'AAAA' * 10, _sh_many):
    try:
        NO.decode_share_code(_sh_code)
    except ValueError as _sh_exc:
        _sh_said.append(str(_sh_exc))
app.toggle_settings_panel('backup'); app.update()
_sh_export = [w for w in _walk_widgets(app.settings_backup_panel, tk.Widget)
              if w.winfo_class() in ('Button', 'Label')
              and str(w.cget('text')) == 'Export']
check(f'the backup is named as Settings → Backup → Export, which exists '
      f'({_sh_said}; {len(_sh_export)} Export button)',
      len(_sh_said) == 3 and len(_sh_export) == 1
      and all('Settings → Backup → Export' in s and '(ZIP)' not in s
              for s in _sh_said + [NO.NoteOrganizer.SHARE_ATTACHMENT_WARNING])
      and 'Backup' in [s[1] for s in NO.NoteOrganizer.SETTINGS_SECTIONS])
_decoded_share = NO.decode_share_code(
    next(t for t in _share_texts if t.startswith('NOTE1:')))
check('the shown code round-trips to the note',
      _decoded_share and _decoded_share[0].get('title') == 'DeShare')

# ---- ONE SENTENCE, AND AN ✕ ON BOTH CODE AREAS (C-24) ----
# Two surfaces generate a share code, and they warned about attachments in
# two different sentences for one fact -- "Attachments not included" in the
# sidebar, "Attachments aren't included in a code" in the editor. One is
# kept, and it now names where the files DO travel. Asserted against the
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

# ---- AND THE SHARE LIST CAN BE FILLED IN ONE CLICK (C-13) ----
# The selection bar a few centimetres above this panel has had a
# "Select all" since it was built; this list -- the one where a whole
# notebook meant a hundred clicks, then "Show 100 more", then a hundred
# more -- had none. Two tick-box lists in one sidebar, one fillable.
_share_all = next(
    (b for b in _walk_widgets(app.share_panel, tk.Button)
     if str(b.cget('text')) in ('Select all', 'Unselect all')), None)
check('the Share panel offers a select-all', _share_all is not None)
# Asked of the TICK BOXES on screen, not of app.notes: the panel is
# paginated and is not live, so "what it is showing" and "what the notebook
# holds" are two different lists. Taking the second one is how the first
# version of the app's own select-all came to tick ids that had no box on
# screen -- this check found that, by accident, and the button acts on what
# it rendered now.
_share_boxes_all = [b for b in _walk_widgets(app, tk.Checkbutton)
                    if str(b.cget('variable')).startswith('PY_VAR')
                    and b.winfo_toplevel() is app]
_share_shown = [b for b in _share_boxes_all
                if str(b.cget('variable')) in
                {str(v) for v in app._share_vars.values()}]
check(f'fixture: the panel is showing tick boxes ({len(_share_shown)})',
      bool(_share_shown))
if _share_all is not None and _share_shown:
    _share_all.invoke()
    app.update()
    check('pressing it ticks every note the panel is showing',
          all(b.getvar(str(b.cget('variable'))) in (1, '1')
              for b in _share_shown))
    check('and the button then offers to unselect',
          str(_share_all.cget('text')) == 'Unselect all')
    _share_all.invoke()
    app.update()
    check('pressing it again clears them',
          not any(b.getvar(str(b.cget('variable'))) in (1, '1')
                  for b in _share_shown))
    # THE CONTROL: untick one BY PRESSING IT and the label must go back to
    # "Select all", or a button reading "Unselect all" would clear a list
    # that was not full. Pressed rather than set: the label is refreshed by
    # the Checkbutton's own command, and setting the variable behind it is
    # something no person can do -- the first version of this check did
    # exactly that and reported a failure about a route nobody can take.
    _share_all.invoke()
    app.update()
    # Found by the VARIABLE it is wired to, not by being the first
    # Checkbutton in the panel: the first version took the first one and it
    # turned out not to belong to a note at all -- invoking it ticked
    # something rather than unticking, and the check reported a label that
    # was correct for the state it had accidentally produced.
    _share_shown[0].invoke()
    app.update()
    _still_on = [b for b in _share_shown
                 if b.getvar(str(b.cget('variable'))) in (1, '1')]
    check(f'a part-ticked list offers Select all, not Unselect all '
          f'(label={str(_share_all.cget("text"))!r}, '
          f'{len(_still_on)} of {len(_share_shown)} still ticked)',
          str(_share_all.cget('text')) == 'Select all')
    _share_shown[0].invoke()
    app.update()
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

# "Show N more" in the Share panel adds the next page under the boxes
# already there; drawing every box again flickered (field pass), and the
# boxes ticked on the first page must be the same boxes after.
_sm_saved_notes = app.notes
app.notes = [NO.normalize_note({'id': 9000 + _i, 'title': 'Many %d' % _i,
                                'body': 'x'}) for _i in range(130)]
app.toggle_share_panel(); app.update()


def _sm_boxes():
    return [b for b in _walk_widgets(app.share_panel, tk.Checkbutton)
            if str(b.cget('text')).startswith('Many')]


_sm_first = _sm_boxes()
_sm_more = next((b for b in _walk_widgets(app.share_panel, tk.Button)
                 if str(b.cget('text')).startswith('Show 30 more')), None)
check(f'fixture: the Share panel draws a page and offers the rest '
      f'({len(_sm_first)} boxes)', len(_sm_first) == 100 and _sm_more is not None)
if _sm_more is not None:
    _sm_more.invoke()
    app.update()
_sm_after = _sm_boxes()
check(f'Show more in Share adds the rest under the boxes already drawn '
      f'({len(_sm_after)} boxes)',
      len(_sm_after) == 130 and _sm_after[:100] == _sm_first
      and all(b.winfo_exists() for b in _sm_first)
      and bool(_sm_after[-1].bind('<MouseWheel>'))
      and not [b for b in _walk_widgets(app.share_panel, tk.Button)
               if str(b.cget('text')).startswith('Show ')])
app.toggle_share_panel(); app.update()
# A note deleted while the panel is open shifts the list under it: Show
# more then draws every box again, or a note was left with no box (audit).
app.toggle_share_panel(); app.update()
del app.notes[5]
_sm_more = next((b for b in _walk_widgets(app.share_panel, tk.Button)
                 if str(b.cget('text')).startswith('Show ')), None)
if _sm_more is not None:
    _sm_more.invoke()
    app.update()
_sm_titles = [str(b.cget('text')) for b in _sm_boxes()]
check(f'Show more in Share after a delete gives every note one box '
      f'({len(_sm_titles)} boxes)',
      _sm_more is not None and len(_sm_titles) == 129
      and sorted(_sm_titles) == sorted(n['title'] for n in app.notes))
app.toggle_share_panel(); app.update()

# More notes ticked than one code may carry: the panel says so, rather than
# make a code its own import then refuses.
_many_kept = app.notes
app.notes = [NO.normalize_note({'id': 90000 + _i, 'title': 'Over %d' % _i, 'body': 'x'})
             for _i in range(NO.MAX_SHARED_NOTES + 1)]
app.toggle_share_panel(); app.update()
try:
    for _n in app.notes:
        app._share_vars[_n['id']] = tk.BooleanVar(value=True)
    app._generate_inline_share(); app.update()
    _many_lbls = [str(l.cget('text')) for l in _walk_widgets(app.share_code_area, tk.Label)]
    _many_texts = [str(w.get('1.0', 'end-1c'))
                   for w in _walk_widgets(app.share_code_area, tk.Text)]
finally:
    app.toggle_share_panel(); app.update()
    app.notes = _many_kept
check(f'more notes ticked than one code carries: a message, not a code the import '
      f'would refuse ({[l[:40] for l in _many_lbls]})',
      not any(t.startswith('NOTE1:') for t in _many_texts)
      and any('at most %d notes' % NO.MAX_SHARED_NOTES in l for l in _many_lbls))

# ---- THE SHARE PANEL: THE LIST'S ORDER, AND A SEARCH OF ITS OWN ----
# The owner's re-test of 0.84.357 (case 343). The notes came in the order
# they entered the notebook; they come in the order the list shows them
# now, pins first. A search box narrows them by the sidebar search's own
# rule -- a word inside a table counts, a table's plumbing does not --
# and ticks outlive a search, so the panel says how many it is hiding.
_sp_sort = app.sort_var.get()
app.notes = [
    NO.normalize_note({'id': 9301, 'title': 'Banana bread',
                       'body': 'flour and sugar',
                       'created': '2026-01-01 10:00:00',
                       'updated': '2026-01-03 10:00:00'}),
    NO.normalize_note({'id': 9302, 'title': 'Apple pie',
                       'body': '| Item | Qty |\n| --- | --- |\n| cinnamon | 1 |',
                       'created': '2026-01-02 10:00:00',
                       'updated': '2026-01-01 10:00:00'}),
    NO.normalize_note({'id': 9303, 'title': 'Cherry jam', 'body': 'x',
                       'comments': 'from grandma', 'pinned': True,
                       'created': '2026-01-03 10:00:00',
                       'updated': '2026-01-02 10:00:00'})]


def _sp_titles():
    return [str(b.cget('text')) for b in _sm_boxes_any()]


def _sm_boxes_any():
    _vars = {str(v) for v in app._share_vars.values()}
    return [b for b in _walk_widgets(app.share_panel, tk.Checkbutton)
            if str(b.cget('variable')) in _vars]


def _sp_lines():
    return [str(l.cget('text')) for l in _walk_widgets(app.share_panel, tk.Label)
            if 'hidden by' in str(l.cget('text'))
            or 'No notes match' in str(l.cget('text'))]


def _sp_search(text):
    app.share_search_var.set(text)
    _waiting = app._share_search_job is not None
    app._share_refilter()
    app.update()
    return _waiting and app._share_search_job is None


app.sort_var.set('Title A–Z')
app.toggle_share_panel(); app.update()
check(f"share: the panel lists the notes in the list's order, pins first "
      f"({_sp_titles()})", _sp_titles() == ['Cherry jam', 'Apple pie',
                                            'Banana bread'])
app.toggle_share_panel()
app.sort_var.set('Recently updated')
app.toggle_share_panel(); app.update()
_sp_list = [r[1]['title'] for r in app._list_rows() if r[0] == 'note']
check(f'share: and in another sort, the same order as the list '
      f'({_sp_titles()} / {_sp_list})',
      _sp_titles() == ['Cherry jam', 'Banana bread', 'Apple pie']
      and _sp_titles() == _sp_list)
# Her re-test (case 594): with the panel open, a new Sort -- picked the way
# the dropdown picks it -- or a pin shows there at once, ticks kept.
app._share_vars[9303].set(True)
app.sort_var.set('Title A–Z')
app._on_sort_chosen('Title A–Z')
app.update()
_sp_follow_sort = _sp_titles()
app.sort_var.set('Recently updated')
app._on_sort_chosen('Recently updated')
app.update()
app.toggle_pin(app.find_note(9302))
app.update()
_sp_follow_pin = _sp_titles()
app.toggle_pin(app.find_note(9302))
app.update()
check(f'share: an open panel follows a new Sort and a pin at once, ticks '
      f'kept ({_sp_follow_sort}; {_sp_follow_pin})',
      _sp_follow_sort == ['Cherry jam', 'Apple pie', 'Banana bread']
      and _sp_follow_pin == ['Cherry jam', 'Apple pie', 'Banana bread']
      and _sp_titles() == ['Cherry jam', 'Banana bread', 'Apple pie']
      and app._share_vars[9303].get())
app._share_vars[9303].set(False)
app._share_vars[9301].set(True)
check('share: typing waits for a pause before the list is drawn again, and '
      'drawing it now settles that', _sp_search('CINNAMON'))
check(f'share: the search finds a word inside a table, whatever its case '
      f'({_sp_titles()})', _sp_titles() == ['Apple pie'])
check(f'share: and says a picked note is hidden by it ({_sp_lines()})',
      _sp_lines() == ['1 picked note is hidden by this search'])
check('share: its ✕ shows while there is a search',
      app._is_placed(app.share_search_clear))
for _sp_q in ('grandma', 'BREAD', '---', 'pie', 'a'):
    _sp_search(_sp_q)
    _sp_rule = [n['title'] for n in app.notes
                if NO.NoteOrganizer._query_matches_note(_sp_q.lower(), n)]
    check(f"share: {_sp_q!r} finds what the sidebar search's rule finds "
          f"({sorted(_sp_titles())} / {sorted(_sp_rule)})",
          sorted(_sp_titles()) == sorted(_sp_rule))
_sp_search('pie')
_sp_all = next((b for b in _walk_widgets(app.share_panel, tk.Button)
                if str(b.cget('text')) in ('Select all', 'Unselect all')), None)
if _sp_all is not None:
    _sp_all.invoke()
    app.update()
check('share: Select all ticks what the search shows, and nothing it hides',
      app._share_vars[9302].get() and not app._share_vars[9303].get())
app._generate_inline_share(); app.update()
_sp_code = next((str(w.get('1.0', 'end-1c'))
                 for w in _walk_widgets(app.share_code_area, tk.Text)), '')
_sp_shared = (sorted(n.get('title') for n in NO.decode_share_code(_sp_code))
              if _sp_code else [])
check(f'share: Generate code shares the picked note the search hides, as the '
      f'panel said ({_sp_shared})',
      _sp_shared == ['Apple pie', 'Banana bread'])
_sp_search('zzzz')
check(f'share: a search that finds nothing says so ({_sp_lines()})',
      not _sp_titles() and 'No notes match.' in _sp_lines())
app.share_search_clear.invoke()
app._share_refilter(); app.update()
check(f'share: the ✕ takes the search away and every note is back '
      f'({_sp_titles()})',
      _sp_titles() == ['Cherry jam', 'Banana bread', 'Apple pie']
      and not app._is_placed(app.share_search_clear) and not _sp_lines())
app.share_search_var.set('pie')
app.toggle_share_panel(); app.update()
check('share: closing the panel calls off a search still waiting',
      app._share_search_job is None)
for _sp_v in app._share_vars.values():
    _sp_v.set(False)
app.sort_var.set(_sp_sort)
app.notes = _sm_saved_notes

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
# Written as every date in the field is shown, day first: 15.MM.YYYY.
check('picking a day writes the date into the date field',
      app.date_entry.get().startswith('15.')
      and NO.read_date(app.date_entry.get()) is not None
      and app._mini_popup is not _dp)
# ...and the repeat's summary follows the date the picker writes: it went on
# saying "needs a start date" after one was picked.
app._cancel_pending_autosave()
app.new_note(); app.update()
app.rec_freq_var.set(NO.FREQ_LABELS['weekly'])
app.on_recurrence_changed(); app.update()
_pk_before = str(app.rec_summary_lbl.cget('text'))
app.open_date_picker(); app.update()
_pk_btns = [b for b in _walk_widgets(app._mini_popup, tk.Button)
            if str(b.cget('text')).strip() == '15']
if _pk_btns:
    _pk_btns[0].invoke()
    app.update()
app._cancel_pending_autosave()
_pk_after = str(app.rec_summary_lbl.cget('text'))
app.rec_freq_var.set(NO.FREQ_LABELS[''])
app.on_recurrence_changed()
app._cancel_pending_autosave()
app.new_note(); app.update()
check(f'the repeat\'s summary follows a date the picker writes '
      f'({_pk_before!r} -> {_pk_after!r})',
      'needs a start date' in _pk_before and _pk_after == 'Every week')

# Note colour picker: a canvas swatch click colours the open note.
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Colored')
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

# An emoji put into an EMPTY field lands in its grey hint's place (field
# pass): the picker had taken the focus, the hint came back, and the title
# was saved as "Note title..." with the emoji after it.
for _ph_hint in ('Note title...', 'Search notes...'):
    _ph_field = next(e for e, h in app._placeholders if h == _ph_hint)
    _ph_field.delete(0, 'end')
    _ph_field.insert(0, _ph_hint)
    _ph_field.config(fg=app.colors['subtext'])
    take_focus(app.body_text)
    app._show_emoji_picker(_ph_field)
    app.update()
    _ph_chips = [l for l in _walk_widgets(app._mini_popup, tk.Label)
                 if str(l.cget('cursor')) == 'hand2'
                 and str(l.cget('text')).strip()]
    _ph_emoji = str(_ph_chips[0].cget('text')).strip() if _ph_chips else '?'
    if _ph_chips:
        _qa_click(_ph_chips[0])
        app.update()
    _ph_got = _ph_field.get()
    app._dismiss_mini_popup(); app.update()
    check(f'an emoji in an empty field takes its hint\'s place '
          f'({_ph_hint} -> {_ph_got!r})',
          _ph_got == _ph_emoji
          and str(_ph_field.cget('fg')) == app.colors['text'])
    _ph_field.delete(0, 'end')
    take_focus(app.body_text)
    app.update()
app._clear_search()
app.update()

# Template picker: choosing the seeded template fills the editor.
app.templates.append(NO.normalize_template(
    {'name': 'PickerTpl', 'title': 'From template', 'body': 'template body'}))
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
      app.title_entry.get() == 'From template'
      and app.body_text.get('1.0', 'end-1c').startswith('template body'))

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
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'TableAtEnd')
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
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Unrendered')
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
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Title only')
app.title_entry.config(fg='black')
app.save_current_note(auto=False)
app.update()
_fc2 = [n for n in app.notes if n['title'] == 'Title only']
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
    _fc_card = app._card_view(_fc3[0]['id'])
    check('...and the list calls it (untitled)',
          _fc_card is not None and '(untitled)' in _fc_card['title'])

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
app.body_text.insert('end', ' ...text not sent yet')
app.duplicate_note(_fc_note)
app.update()
_fc_copies = [n for n in app.notes
              if n['id'] != _fc_note['id'] and 'Title only' in (n['title'] or '')]
check('duplicating with unsaved edits copies the saved version (plan 11)',
      len(_fc_copies) == 1
      and 'not sent yet' not in (_fc_copies[0]['body'] or ''))

# 19: a very long note saves and comes back whole.
app.new_note()
_fc_long = ('A test line that repeats itself. ' * 1800)[:52000]
app.body_text.insert('1.0', _fc_long)
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Very long')
app.title_entry.config(fg='black')
_fc_t0 = time.perf_counter()
app.save_current_note(auto=False)
app.update()
_fc_elapsed = time.perf_counter() - _fc_t0
_fc_big = next((n for n in app.notes if n['title'] == 'Very long'), None)
check('a 52,000-character note saves (plan 19)',
      _fc_big is not None and len(_fc_big['body']) >= 50000)
app.new_note(); app.update()
app.load_note(_fc_big); app.update()
check('...and reopens with every character of it',
      len(app.body_text.get('1.0', 'end-1c')) >= 50000)
check('...without taking longer than a person would wait (%.1fs)' % _fc_elapsed,
      _fc_elapsed < 5.0)

# 66: a repeat with no date cannot be stored, and the reason names the
# date -- but the note's words are not refused along with it. One field
# the app cannot read used to veto the whole save, and on the automatic
# routes that veto threw the typing away; now the words are saved, the
# repeat is left out, and the warning says why.
_fc_warned = []
app.show_warning = lambda *a, **k: (_fc_warned.append(a), True)[1]
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'Repeating')
app.title_entry.config(fg='black')
app.body_text.insert('1.0', 'something')
app.rec_freq_var.set(NO.FREQ_LABELS['daily'])
app.on_recurrence_changed()
app.date_entry.delete(0, 'end')
app.save_current_note(auto=False)
app.update()
app.show_warning = _fc_real_warning
_fc_rep = next((n for n in app.notes if n['title'] == 'Repeating'), None)
check('a repeating note with no start date keeps its words (plan 66)',
      _fc_rep is not None and _fc_rep['body'].strip() == 'something')
check('...but not a repeat it has no start date for',
      _fc_rep is not None and not _fc_rep['recurrence']['freq'])
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
app._cancel_pending_autosave()
check('fixture: no autosave is pending before the paste',
      not getattr(app, '_autosave_job', None))
app.clipboard_clear(); app.clipboard_append('2027-03-01'); app.update()
_re_fired = {'n': 0}
_re_real_now = app._autosave_now


def _re_counting_now(*a, **k):
    _re_fired['n'] += 1
    return _re_real_now(*a, **k)


app._autosave_now = _re_counting_now
try:
    app.rec_end_date_entry.delete(0, 'end')
    app.rec_end_date_entry.event_generate('<<Paste>>')
    app.update()
finally:
    app._autosave_now = _re_real_now
check('a pasted end-date lands in the box',
      app.rec_end_date_entry.get() == '2027-03-01')
# Pending OR already fired, for the same reason as the date field above.
check(f'and its own trace schedules the save, with no binding of its own '
      f'(pending={getattr(app, "_autosave_job", None) is not None}, '
      f'fired={_re_fired["n"]})',
      getattr(app, '_autosave_job', None) is not None or _re_fired['n'] >= 1)
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
app._working_checklist = [{'text': 'first', 'done': False},
                          {'text': 'second', 'done': True},
                          {'text': 'third', 'done': False}]
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
          [i['text'] for i in app._working_checklist] == ['second', 'third'])

# 41: the card says how far along a checklist is -- and says nothing when
# there is no checklist.
app.save_current_note(auto=False)
app.update()
app.refresh_note_list(); app.update()
_fc_tags = app._card_view(_fc_note['id'])
check('a note with a checklist shows its progress on the card (plan 41)',
      _fc_tags is not None and '1/2' in _fc_tags['tags'])
_fc_plain = next((n for n in app.notes if not n.get('checklist')), None)
if _fc_plain is not None:
    _fc_plain_tags = app._card_view(_fc_plain['id'])
    check('...and a note without one shows no checklist mark at all',
          _fc_plain_tags is not None and '☑' not in _fc_plain_tags['tags'])


# ---- A REMOVED CHECKLIST ITEM CAN COME BACK ----
# It was the one thing that could be taken off a note with no way back at
# all: Ctrl+Z reaches the Text widgets through edit_undo, and a checklist
# is a list of dicts beside them (finding C-2, docs/archive/PRODUCT_FINDINGS.md).
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
       if isinstance(_w, tk.Label) and str(_w.cget('text')) != '▲\n▼']
      == ['milk', 'bread', 'eggs'])

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
# The undo has to ASK for its own save, the way the removal did. Not by
# flushing and reading the file -- a flush saves whatever the editor holds
# whether anything asked it to or not, so the disk check below passes even
# with the scheduling removed.
#
# And not by looking for a queued job either, which is how this was
# written and why it went red on CI while passing here three times out of
# three: a pending timer is a fact about a MOMENT. Between scheduling and
# reading there is an app.update(), and on a loaded runner that can take
# longer than the 500ms debounce -- the timer fires, the job is cleared,
# and the check reports a missing request about an app that made one. The
# call is what the promise is about, so the call is what is counted.
_cu_asked = {'n': 0}
_cu_real_schedule = app._schedule_autosave


def _cu_counting_schedule(*a, **k):
    _cu_asked['n'] += 1
    return _cu_real_schedule(*a, **k)


app._schedule_autosave = _cu_counting_schedule
try:
    # Called only when there is one: with no Undo on offer (a broken app,
    # a mutant) this line raised and ended the suite before its footer,
    # where the check below says so as one red line.
    if callable(getattr(app, '_toast_action', None)):
        app._toast_action()
    app.update()
finally:
    app._schedule_autosave = _cu_real_schedule
check(f'checklist undo: the way back schedules its own save '
      f'({_cu_asked["n"]} request(s))', _cu_asked['n'] >= 1)
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
# The delete schedules its own autosave, and its reassurance banner
# yields only to a live OFFER -- so, landing after the error banner, it
# replaces it. Left pending, that timer fired inside the update() below
# whenever the machine was slow, and this check went red twice under a
# loaded desktop with nothing wrong with what it asks. Settled first, and
# asserted settled, so the reading is about its own promise. (That a
# "Note updated" can cover an error at all is its own question, reported
# with the audit's editor fixes.)
app._flush_autosave()
app.update()
check('checklist undo: the delete\'s own save is settled before the error '
      '(precondition)', getattr(app, '_autosave_job', None) is None
      and app._toast_action is not None)
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
# Restore previous fills the editor from the same note again, and loading
# it gave the checklist a new list: the Undo just offered said "That note is
# no longer open" with the note on screen, and the item could not come
# back. The same note loaded over itself keeps its list.
check('checklist undo: fixture ready for Restore previous',
      _cu_setup(['milk', 'eggs'],
                extra={'_prev': {'title': 'Shopping', 'body': 'an older body',
                                 'formatting': [], 'paragraphs': [],
                                 'comments': ''}}))
_cu_press(1)
_cu_undo = app._toast_action
_cu_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version()
    app.update()
finally:
    app.ask_yes_no = _cu_real_ask
_cu_undo()
app.update()
check(f'checklist undo: Undo after Restore previous puts the item back '
      f'({_cu_texts()}; restored {app.find_note(9100).get("body")!r})',
      _cu_texts() == ['milk', 'eggs']
      and 'older body' in app.find_note(9100).get('body', ''))
# ...but not after a reload that brought ANOTHER checklist -- a rescue copy
# that holds its own, as an import's Update leaves one: the item it brought
# back as a new entry was put back again beside it, and stored twice.
check('checklist undo: fixture ready for a rescue copy with its own checklist',
      _cu_setup(['milk', 'eggs', 'bread'],
                extra={'_prev': {'title': 'Shopping', 'body': 'an older body',
                                 'formatting': [], 'paragraphs': [],
                                 'comments': '',
                                 'checklist': [
                                     {'text': 'milk', 'done': False},
                                     {'text': 'eggs', 'done': False}]}}))
_cu_press(1)
_cu_undo = app._toast_action
app.ask_yes_no = lambda *a, **k: True
try:
    app.restore_previous_version()
    app.update()
finally:
    app.ask_yes_no = _cu_real_ask
_cu_undo()
app.update()
_cu_kept = [i.get('text') for i in app.find_note(9100).get('checklist') or []]
check(f'checklist undo: ...and after Restore previous brings back its own '
      f'checklist, the Undo stores nothing twice ({_cu_texts()}; stored '
      f'{_cu_kept})',
      _cu_texts() == ['milk', 'eggs'] and _cu_kept == ['milk', 'eggs'])

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
    NO.CATEGORY_COLORS['Project'] = '#123456'
    _b3_cat = 'Project'
_b3_was = NO.CATEGORY_COLORS[_b3_cat]
app.notes = [{'id': 5001, 'title': 'Colored', 'body': 'x', 'comments': '',
              'category': _b3_cat, 'date': '', 'color': '', 'recurrence': {},
              'checklist': [], 'attachments': [],
              'created': '2026-01-01 00:00', 'updated': '2026-01-01 00:00'}]
app.save_notes()
NO.CATEGORY_COLORS[_b3_cat] = '#ff00ff'
app.hide_settings_page()
app.refresh_note_list(); app.update()
_b3_tags = app._card_view(5001)
check("a category's new colour reaches the note card (plan 27): whole on its "
      "stripe, and in its tags row as a shade of it that reads on the card",
      _b3_tags is not None and str(_b3_tags['stripe']).lower() == '#ff00ff'
      and str(_b3_tags['tags_fill']).lower()
      == NO.legible_on('#ff00ff', app.colors['card'], app.colors['text']).lower())
check('...because the card reads the one stored colour, not a copy',
      NO.CATEGORY_COLORS[_b3_cat].lower() == '#ff00ff')
NO.CATEGORY_COLORS[_b3_cat] = _b3_was

# 32: a template over unsaved work asks first.
app.notes = list(_b3_saved)
app.save_notes()
app.new_note()
app.body_text.insert('1.0', 'something written and unsaved')
app.update()
_b3_asked = []
_b3_real_ask = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_b3_asked.append(a), False)[1]   # "No"
app._apply_template({'name': 'T', 'title': 'From template', 'body': 'template body',
                     'comments': '', 'category': 'General', 'checklist': []})
app.update()
app.ask_yes_no = _b3_real_ask
check('a template over unsaved content asks before replacing it (plan 32)',
      len(_b3_asked) == 1)
check('...and answering No leaves what was typed exactly where it was',
      'something written and unsaved' in app.body_text.get('1.0', 'end-1c'))

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
# The search_var.set('') above scheduled the search debounce -- a full
# refresh_note_list 180 ms later, which draws every card anew -- and the
# new note left an autosave pending. Whenever this setup ran faster than
# the debounce, the refresh landed between the baseline and the reading
# below and the "without rebuilding" checks went red with nothing wrong
# (3 times in 16 loaded Windows runs, never on Linux; reproduced by
# listing the timers still pending at the baseline). Settled and
# asserted settled, so the reading is about the button alone.
if getattr(app, '_search_debounce_job', None) is not None:
    app.after_cancel(app._search_debounce_job)
    app._search_debounce_job = None
app._flush_autosave()
app.update()
check('select all: no timer left that could redraw the list (precondition)',
      getattr(app, '_search_debounce_job', None) is None
      and getattr(app, '_autosave_job', None) is None)
_btn_text = lambda: str(app._bulk_select_all_btn.cget('text'))


def _box_states():
    """Each drawn card's tick box, as the drawing shows it."""
    out = {}
    for _nid in app._card_order():
        _checked = app._card_view(_nid)['checked']
        if _checked is not None:
            out[_nid] = _checked
    return out


def _card_paths():
    # A card drawn again has new canvas items: the item behind each card's
    # background says whether the list was redrawn.
    return {_nid: _rec['items']['bg'] for _nid, _rec in app._note_cards.items()}


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
_bar_labels = [str(_b.cget('text')) for _b in _bar_btns]
# Asked by NAME rather than by count. The count was five when Pin joined
# the bar, and a number is the one thing that goes stale on every addition
# while telling nobody which action went missing -- which is what this
# check is really about. It was written after Export was drawn 13px
# narrower than it asked for, with its caret cut off.
for _want in ('Select all', 'Trash', 'Category', 'Export', 'Pin'):
    check('the bar offers "%s"' % _want,
          any(_want in t for t in _bar_labels))
for _b in _bar_btns:
    check('...and "%s" is drawn at least as wide as it asks'
          % str(_b.cget('text')),
          _b.winfo_width() >= _b.winfo_reqwidth())
# Two per row is the invariant the bar's own comment records as the fix
# for a layout that once fitted by a single pixel and then did not on the
# other platform. Pin therefore went on a third row rather than beside
# Export, and this is the check that keeps it there.
_bar_rows = [w for w in _bar.winfo_children() if isinstance(w, tk.Frame)]
_per_row = [len([c for c in _r.winfo_children() if isinstance(c, tk.Button)])
            for _r in _bar_rows]
check('no row of the bar carries more than two actions (%s)' % _per_row,
      _per_row and max(_per_row) <= 2)

# ---- PINNING SEVERAL NOTES AT ONCE (C-9, C-17) ----
# Pinning had exactly one route in the whole app: the right-click menu,
# one note at a time. Reordering twenty notes meant opening it twenty
# times, on a bar whose whole purpose is acting on many at once.
_pin_btn = next(b for b in _bar_btns if 'Pin' in str(b.cget('text')))
app.selected_note_ids = {400, 401, 402}
app._update_bulk_selected_label()
app.update()
check('with nothing pinned the button offers to Pin',
      str(_pin_btn.cget('text')).endswith('Pin'))
_pin_btn.invoke()
app.update()
check('it pins every ticked note',
      all(app.find_note(i).get('pinned') for i in (400, 401, 402)))
check('and leaves the rest alone',
      not app.find_note(403).get('pinned'))
# The label flips the way Select all does, so the word is always the
# thing pressing it will do.
check('the button now offers to Unpin',
      str(_pin_btn.cget('text')).endswith('Unpin'))
_pin_btn.invoke()
app.update()
check('and pressing it again unpins them',
      not any(app.find_note(i).get('pinned') for i in (400, 401, 402)))
# THE CONTROL: a MIXED selection must pin rather than unpin, or "Pin" on a
# partly-pinned set would be the one press that does nothing for some of
# the notes it names.
app.find_note(400)['pinned'] = True
app._update_bulk_selected_label()
app.update()
check('a mixed selection still offers Pin',
      str(_pin_btn.cget('text')).endswith('Pin'))
_pin_btn.invoke()
app.update()
check('and pinning a mixed selection pins all of it',
      all(app.find_note(i).get('pinned') for i in (400, 401, 402)))
for _i in (400, 401, 402):
    app.find_note(_i)['pinned'] = False
app.selected_note_ids = set()
app.save_notes()
app._update_bulk_selected_label()
app.update()
# No check for "the shortfall is shared": with the count on its own row
# nothing in the bar is under pressure, so no single edit can starve one.
# Sharing the width is defence in depth against a future font or label,
# not a promise this suite can currently break -- and a check that cannot
# fail proves nothing. Written down rather than left as a passing line.
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
_sg_before = len(app._card_order())
check('the list drew a card per note to begin with', _sg_before == 12)
# The witness. Every check below about "the cards survived" would pass
# just as happily after a full rebuild, which produces correct cards
# too -- so one card's canvas item is remembered. A rebuild deletes it and
# draws a new one under a new number; taking one card off only moves it.
# Without this, nothing here can tell the two apart.
_sg_witness = app._note_cards[400]['items']['bg']

_sg_target = app.find_note(405)
app._delete_note(_sg_target, None)
_sg_settle()
check('the deleted note loses its card',
      405 not in app._card_order())
check('...and every other card is still there',
      len(app._card_order()) == _sg_before - 1)
check('...and the cards were not rebuilt around it',
      all(app.canvas.type(r['items']['bg']) for r in app._note_cards.values()))
check('...and a surviving card is the SAME drawing, not a remade one',
      app._note_cards[400]['items']['bg'] == _sg_witness)
check('...and the list agrees with the notes',
      sorted(app._card_order()) == sorted(n['id'] for n in app.notes))

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
_sg_content = app._list_extent()
_sg_room = app.canvas.winfo_height()
check('the list is long enough to scroll, so the next check means something',
      _sg_content is not None and (_sg_content[3] - _sg_content[1]) > _sg_room + 50)
# The bottom card: deleting it changes nothing above the viewport.
_sg_last_id = app._card_order()[-1]


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
      403 not in app._card_order())
app.open_note_in_tab(app.find_note(402))
app.update()
# Drawn first, the way scrolling to it would draw it: the list draws a
# screenful and the rest as the view comes near, and whether 402 falls in
# the first screenful depends on whether the thirty notes above were made
# in the same second as it (the sort is by that timestamp). And asked of
# the COLOUR: every card wears a two-pixel ring now, so a check of the
# thickness passed for any card at all.
while 402 not in app._note_cards and app._list_pending:
    app._draw_list_rows(app.LIST_DRAW_STEP)
app.update()
_sg_402 = app._card_view(402)
check('...and the next note opened still takes the border',
      _sg_402 is not None
      and str(_sg_402['ring']) == app.colors['accent'])

# A theme switch afterwards recolours what is left, in place, and must
# not trip over the entry that was removed.
app.set_theme('light')
app.update()
check('a theme switch after a delete recolours the surviving cards',
      all(str(app._card_view(n)['bg']).lower() == app.colors['card'].lower()
          for n in app._card_order()))
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
      not app._note_cards)
_sg_texts = [str(app.canvas.itemcget(_i, 'text'))
             for _i in app.canvas.find_withtag('list_empty')]
check('...and the empty list says so, which only a full rebuild writes',
      any('No notes' in t for t in _sg_texts))

# ---- NOTHING ON A CARD IS CUT OFF AT ITS EDGE ----
# The sidebar is a fixed width and a Label with no wraplength draws one
# line as long as its text, so the card simply does not show the end of
# it -- silently. Photographed on an ordinary note: a title lost four
# words, a preview stopped mid-word, and the tags row dropped the
# attachment count, the table mark and the checklist progress outright,
# leaving "1/2" reading as "1/".
#
# Asked as "does any label want more room than it has" rather than "is
# wraplength set", so the check is about what a person sees and survives
# a different fix. Every string here is long enough to have overflowed
# before, which is what makes it able to fail.
app.notes = [NO.normalize_note({
    'id': 7100,
    'title': 'Quarterly planning meeting with the whole team',
    'body': ('Agenda, decisions and the follow-ups we owe each other.'
             + chr(10) + '| Item | Owner |' + chr(10) + '| --- | --- |'
             + chr(10) + '| Budget | Ana |'),
    'category': 'General', 'comments': 'Room 2 is booked',
    'checklist': [{'text': 'send the agenda', 'done': True},
                  {'text': 'book the room', 'done': False}],
    'attachments': [{'name': 'agenda.pdf', 'stored_as': 'agenda.pdf'}],
    'date': '2026-09-15',
    'recurrence': {'freq': 'weekly', 'weekdays': [0]}})]
app.save_notes()
app.refresh_note_list()
app.update()
app.update_idletasks()
_ov_card = app._card_view(7100)
check('the card for a note carrying everything is on screen',
      _ov_card is not None)
# Asked of where each text is DRAWN against the card's own edges: a text
# drawn past the ring is text a person cannot read, whatever the item
# holds.
_ov_names = ('title', 'preview', 'tags')
_ov_wide = []
if _ov_card is not None:
    _ov_x0, _ov_y0, _ov_x1, _ov_y1 = _ov_card['box']
    for _ov_name, _ov_b in zip(_ov_names, _ov_card['text_boxes']):
        if (_ov_b is None or _ov_b[0] < _ov_x0 or _ov_b[2] > _ov_x1 - app.CARD_RING
                or _ov_b[3] > _ov_y1 - app.CARD_RING):
            _ov_wide.append(_ov_name)
check('no text on the card reaches past the card\'s edges '
      '(over: %s)' % _ov_wide,
      _ov_card is not None and _ov_wide == [])
# The tags are the reason this matters most: each one is a separate
# fact, so a row that runs out of room drops whole marks rather than
# the tail of a sentence.
_ov_tags = _ov_card['tags'] if _ov_card is not None else ''
check('...and the checklist progress is whole, not a clipped "1/"',
      '1/2' in _ov_tags)
check('...with the table mark and the attachment count still there',
      '1 table' in _ov_tags and chr(0x00D7) + '1' in _ov_tags)

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
_b3_fresh.show_info = lambda *a, **k: True  # see _fresh above
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
app.body_text.insert('1.0', 'one\ntwo\nthree\nfour')
for _b4_line in range(1, 5):
    app.body_text.mark_set('insert', '%d.0' % _b4_line)
    app._toggle_list('number')
app.update()
_b4_before = app.body_text.get('1.0', 'end-1c')
check('a four-item numbered list is numbered 1-4 (plan 139)',
      _b4_before.startswith('1. one') and '4. four' in _b4_before)
app.body_text.delete('2.0', '3.0')          # the SECOND item, from the middle
app._renumber_lists()
app.update()
_b4_after = app.body_text.get('1.0', 'end-1c')
check('removing a middle item renumbers what follows it (plan 139)',
      '1. one' in _b4_after and '2. three' in _b4_after and '3. four' in _b4_after
      and '4.' not in _b4_after)

# 178: duplicating a note that holds a table gives a real second table,
# not a shared one -- editing the copy must not reach the original.
app.new_note()
app.title_entry.delete(0, 'end'); app.title_entry.insert(0, 'With table')
app.title_entry.config(fg='black')
app.body_text.delete('1.0', 'end')
app.body_text.insert('1.0', '| A | B |\n| --- | --- |\n| 1 | 2 |')
app.save_current_note(auto=False)
app.update()
_b4_orig = next(n for n in app.notes if n['title'] == 'With table')
app.duplicate_note(_b4_orig)
app.update()
_b4_copy = next((n for n in app.notes
                 if n['id'] != _b4_orig['id'] and 'With table' in (n['title'] or '')), None)
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
_b4_tpl = {'name': 'Template', 'title': 'From template', 'body': 'body',
           'comments': '', 'category': 'General',
           'checklist': [{'text': 'first step', 'done': False}]}
app.ask_yes_no = lambda *a, **k: True
app.new_note()
app._apply_template(_b4_tpl)
app.save_current_note(auto=False)
app.update()
_b4_note_a = app.notes[-1]
check('a template brings its checklist into the note it makes (plan 114)',
      [i['text'] for i in (_b4_note_a.get('checklist') or [])] == ['first step'])
_b4_tpl['checklist'] = [{'text': 'changed step', 'done': False},
                        {'text': 'new step', 'done': False}]
app.new_note()
app._apply_template(_b4_tpl)
app.save_current_note(auto=False)
app.update()
_b4_note_b = app.notes[-1]
check('editing the template later leaves the earlier note untouched (plan 114)',
      [i['text'] for i in (app.find_note(_b4_note_a['id']) or {}).get('checklist', [])]
      == ['first step'])
check('...and the next note made from it gets the NEW checklist (plan 114)',
      [i['text'] for i in (_b4_note_b.get('checklist') or [])]
      == ['changed step', 'new step'])

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
NO.CATEGORY_COLORS.setdefault('Job', '#775599')
app.notes = [NO.normalize_note({'id': 7700 + i, 'title': 'Desk %d' % i,
                                'body': 'body %d' % i, 'category': 'General'})
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
# whose label says Job and click IT -- never do its work here, or the
# check passes on its own behaviour instead of the app's.
_bk_row = None
_bk_pop = getattr(app, '_mini_popup', None)


def _bk_find_row(widget):
    global _bk_row
    for child in widget.winfo_children():
        if isinstance(child, tk.Label) and str(child.cget('text')).strip() == 'Job':
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
      == ['Job', 'Job'])
app.body_text.insert('end', ' and I carry on typing')
app._flush_autosave()
app.update()
_bk_stored = json.load(open('notes_data.json', encoding='utf-8'))
_bk_open = next(n for n in _bk_stored if n['id'] == 7700)
_bk_other = next(n for n in _bk_stored if n['id'] == 7701)
check('...and typing afterwards does not revert it on the OPEN note '
      '(audit finding)', _bk_open['category'] == 'Job')
check('...while the note nobody had open was never at risk',
      _bk_other['category'] == 'Job')
check('...and what was typed afterwards is saved too',
      'carry on typing' in _bk_open['body'])

app.notes = list(_bk_saved)
app.save_notes()
app.new_note(); app.update()


# ---- THE BULK CATEGORY CHANGE ASKS, AND OFFERS A WAY BACK ----
# It was the one action in that bar that rewrote stored data with neither
# a question nor an undo, while the button beside it had both -- and the
# categories it overwrote were gone from the file the moment it ran
# (finding C-1, docs/archive/PRODUCT_FINDINGS.md). These checks hold both
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

# A category renamed while the Undo is still on offer. The rename does not
# change what was done, so the Undo puts the notes back all the same -- into
# a renamed category they came from as well -- and its banner says the new
# name. It looked for the old name and said "Nothing left to put back".
# Renamed as Settings renames (its handler is a closure in the row): the
# colours in place first, then every holder of the name.


def _bc_rename(old, new):
    _bc_order = [(new if _bc_k == old else _bc_k, _bc_c)
                 for _bc_k, _bc_c in NO.CATEGORY_COLORS.items()]
    NO.CATEGORY_COLORS.clear()
    NO.CATEGORY_COLORS.update(_bc_order)
    app.rename_category_everywhere(old, new)
    app.save_notes()
    app.update()


NO.CATEGORY_COLORS.setdefault('BcDest', '#3388aa')
_bc_seed([(8130, 'BcRen1', 'Alpha', None), (8131, 'BcRen2', 'Beta', None)])
app.selection_mode = True
app.selected_note_ids = {8130, 8131}
_bc_pick('BcDest')
check('fixture: the move offers its Undo',
      app._toast_action is not None and _bc_cats() == {8130: 'BcDest', 8131: 'BcDest'})
_bc_rename('BcDest', 'BcDest2')
_bc_rename('Alpha', 'Alpha2')
check('bulk category: a rename while the Undo is on offer puts the new name on its banner',
      '“BcDest2”' in str(app.toast_lbl.cget('text'))
      and app._toast_action is not None)
app._run_toast_action()
app.update()
check('bulk category: ...and the Undo still puts the notes back, into a renamed category too',
      _bc_cats() == {8130: 'Alpha2', 8131: 'Beta'})
_bc_rename('Alpha2', 'Alpha')
NO.CATEGORY_COLORS.pop('BcDest2', None)

# The category the notes went into, deleted while its Undo is on offer, the
# way Settings deletes one: the deletion has just decided where they go, so
# the offer goes with it rather than staying up to say "Nothing left".
NO.CATEGORY_COLORS.setdefault('BcGone', '#aa5533')
_bc_seed([(8132, 'BcDel', 'Alpha', None)])
app.selection_mode = True
app.selected_note_ids = {8132}
_bc_pick('BcGone')
check('fixture: the move into the category to delete offers its Undo',
      app._toast_action is not None and _bc_cats() == {8132: 'BcGone'})
_bc_real_deletion_ask = app._ask_category_deletion
app._ask_category_deletion = lambda *a, **k: 'move'
try:
    app._delete_category('BcGone', lambda: None)
finally:
    app._ask_category_deletion = _bc_real_deletion_ask
app.update()
check('bulk category: deleting the category the notes went into withdraws its Undo',
      app._toast_action is None and not app.toast_frame.winfo_ismapped()
      and _bc_cats() == {8132: 'General'})

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

# ---- ESCAPE LEAVES A CELL AND KEEPS WHAT WAS TYPED ----
# The User Guide lists Escape beside Tab and a click elsewhere as the way
# out of a cell. It closed the editor without a commit, and the typing
# reaches the note only through one -- so a quick Escape threw the cell's
# text away while Tab, with the same timing, kept it. Driven through the
# editor's own binding: the focus is a precondition, forced and asserted.
set_body('| Item | Qty |' + chr(10) + '| --- | --- |' + chr(10)
         + '|  |  |' + chr(10) + 'after')
app._render_table_grids()
app.update()
app._open_cell_editor(app._grid_at_line(1), 1, 0)
app.update()
_esc_entry = app._cell_editor['entry']
_esc_entry.delete('1.0', 'end')
_esc_entry.insert('1.0', 'Milk')
check('Escape: the cell editor holds the keyboard (precondition)',
      take_focus(_esc_entry))
_esc_entry.event_generate('<Escape>')
app.update()
check('Escape leaves the cell', app._cell_editor is None)
check('...and keeps what was typed in it (' + repr(
          app.body_text.get('3.0', '3.end')) + ')',
      core_tables.split_row(app.body_text.get('3.0', '3.end'))
      == ['Milk', ''])
set_body('')

# ---- THE KEYS STOP AT A DRAWN TABLE'S EDGE ----
# Delete at the end of the line above a table, or BackSpace at the start
# of the line under it, took the line break between them: the prose was
# glued onto the table's first or last row, which then read as prose,
# fell out of the grid, and was saved that way. The table is one block --
# the boundary the caret guard already keeps -- and the keys stop at its
# edge. Tk's own Ctrl+H (a BackSpace) and Ctrl+K (at a line's end, a
# Delete) join lines too and meet the same guard. Every "nothing
# happened" below has its control: the same key one character away from
# the edge really deletes, so the silence is about the edge, not about a
# key that never arrived.
_edge_body = ('Shopping for Saturday' + chr(10) + '| Item | Qty |' + chr(10)
              + '| --- | --- |' + chr(10) + '| Milk | 2 |' + chr(10)
              + '| Eggs | 12 |' + chr(10) + 'remember the bags')


def _edge_press(index, sequence, body=None):
    """Reset the note, put the caret at *index* and press *sequence* on
    the body through Tk. Returns the text after, or None when the body
    could not get the keyboard (the precondition, asserted by callers)."""
    set_body(_edge_body if body is None else body)
    app._render_table_grids()
    app.update()
    app.body_text.tag_remove('sel', '1.0', 'end')
    app.body_text.mark_set('insert', index)
    if not take_focus(app.body_text):
        return None
    app.body_text.event_generate(sequence)
    app.update()
    return app.body_text.get('1.0', 'end-1c')


def _edge_rows():
    info = app._grid_at_line(2)
    return (None if info is None else
            [info['cells'][(r, 0)]['value'] for r in range(info['data_rows'])])


_edge_after = _edge_press('1.end', '<Delete>')
check('table edge: the body holds the keyboard (precondition)',
      _edge_after is not None)
check('table edge: Delete at the end of the line above a table does nothing',
      _edge_after == _edge_body and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_after = _edge_press('1.20', '<Delete>')
check('table edge: ...while Delete one character earlier still deletes',
      _edge_after == _edge_body.replace('Saturday', 'Saturda', 1))
_edge_after = _edge_press('6.0', '<BackSpace>')
check('table edge: BackSpace at the start of the line under a table does nothing',
      _edge_after == _edge_body and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_after = _edge_press('6.1', '<BackSpace>')
check('table edge: ...while BackSpace one character later still deletes',
      _edge_after == _edge_body.replace('remember', 'emember', 1))
_edge_after = _edge_press('6.0', '<Control-h>')
check('table edge: Ctrl+H (Tk\'s BackSpace) stops at the edge too',
      _edge_after == _edge_body)
_edge_after = _edge_press('6.1', '<Control-h>')
check('table edge: ...and still deletes away from it',
      _edge_after == _edge_body.replace('remember', 'emember', 1))
_edge_after = _edge_press('1.end', '<Control-k>')
check('table edge: Ctrl+K at the end of the line above stops at the edge',
      _edge_after == _edge_body)
_edge_after = _edge_press('6.0', '<Control-k>')
check('table edge: ...and still clears a line away from it',
      _edge_after == _edge_body.replace('remember the bags', '', 1))
# A selection is not a question about the edge: with the caret inside it
# Delete takes the selection, as Tk always has.
set_body(_edge_body)
app._render_table_grids()
app.update()
app.body_text.tag_add('sel', '1.13', '1.21')
app.body_text.mark_set('insert', '1.21')
if take_focus(app.body_text):
    app.body_text.event_generate('<Delete>')
    app.update()
check('table edge: a selection ending at the edge is still deleted whole',
      app.body_text.get('1.0', '1.end') == 'Shopping for '
      and _edge_rows() == ['Item', 'Milk', 'Eggs'])
# The note that ENDS in a table: BackSpace on the writable line under it,
# then typing -- the typing lands on its own line, not on the last row.
_edge_end_body = _edge_body.rsplit(chr(10), 1)[0]
_edge_after = _edge_press('end-1c', '<BackSpace>', body=_edge_end_body)
app.body_text.insert('insert', 'and bread')
app.update()
_edge_lines = app.body_text.get('1.0', 'end-1c').split(chr(10))
check('table edge: BackSpace under a note-ending table keeps the last row whole',
      _edge_after is not None and _edge_lines[4] == '| Eggs | 12 |'
      and _edge_lines[5] == 'and bread')
# Tk's own Ctrl+T swaps the two characters around the caret; at the edge
# one of them was the table's line break, and the last row became
# "| Eggs | 12 |r". A swap removes no line, so even the empty line under
# a table (where BackSpace may go, below) holds it: the swap there was the
# last row's closing pipe and its line break.
_edge_after = _edge_press('6.0', '<Control-t>')
check('table edge: Ctrl+T (Tk\'s transpose) at the start of the line under '
      f'a table does nothing ({_edge_after!r})',
      _edge_after == _edge_body and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_after = _edge_press('6.3', '<Control-t>')
check('table edge: ...while Ctrl+T in the prose under it still transposes',
      _edge_after == _edge_body.replace('remember', 'reemmber', 1))
_edge_after = _edge_press('1.end', '<Control-t>')
check('table edge: ...and so does Ctrl+T at the end of the line above it',
      _edge_after == _edge_body.replace('Saturday', 'Saturdya', 1)
      and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_gap_below = _edge_body.replace('| Eggs | 12 |' + chr(10),
                                     '| Eggs | 12 |' + chr(10) + chr(10), 1)
_edge_after = _edge_press('6.0', '<Control-t>', body=_edge_gap_below)
check('table edge: Ctrl+T on the empty line under a table does nothing '
      f'({_edge_after!r})',
      _edge_after == _edge_gap_below
      and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_after = _edge_press('end-1c', '<Control-t>', body=_edge_end_body)
check('table edge: Ctrl+T on the writable line under a note-ending table '
      f'keeps the last row whole ({_edge_after!r})',
      _edge_after is not None
      and _edge_after.split(chr(10))[4] == '| Eggs | 12 |'
      and _edge_rows() == ['Item', 'Milk', 'Eggs'])
# An EMPTY line beside a table joins nothing onto a row when it goes, and
# the edge guard refused it anyway: Delete on the empty line above, or
# BackSpace on the empty line below, did nothing. It goes now -- but not
# the empty line BETWEEN two tables (they would merge into one block),
# and not the writable line the renderer keeps under a note-ending table
# (checked just above).
_edge_gap_above = _edge_body.replace('Saturday' + chr(10),
                                     'Saturday' + chr(10) + chr(10), 1)
_edge_after = _edge_press('2.0', '<Delete>', body=_edge_gap_above)
check('table edge: Delete on the empty line above a table removes it '
      f'({_edge_after!r})',
      _edge_after == _edge_body and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_after = _edge_press('6.0', '<BackSpace>', body=_edge_gap_below)
check('table edge: BackSpace on the empty line under a table removes it '
      f'({_edge_after!r})',
      _edge_after == _edge_body and _edge_rows() == ['Item', 'Milk', 'Eggs'])
_edge_two = ('| A | B |' + chr(10) + '| --- | --- |' + chr(10) + '| a1 | b1 |'
             + chr(10) + chr(10) + '| C | D |' + chr(10) + '| --- | --- |'
             + chr(10) + '| c1 | d1 |' + chr(10) + 'end')
for _edge_key in ('<Delete>', '<BackSpace>'):
    _edge_after = _edge_press('4.0', _edge_key, body=_edge_two)
    check(f'table edge: {_edge_key} on the empty line between two tables '
          f'does nothing ({_edge_after!r}, {len(app._table_grids)} grids)',
          _edge_after == _edge_two and len(app._table_grids) == 2)
set_body('')

# Drawing a note's tables asks where each grid starts a few times per
# table: every cell asked it of every grid drawn before, and a note of 100
# tables took a quarter of a second to open, growing with the square.
_tq_body = chr(10).join(
    'Part %d' % k + chr(10) + '| Item | Qty |' + chr(10) + '| --- | --- |'
    + chr(10) + '| tea | %d |' % k for k in range(12))
set_body(_tq_body)
_tq_at = _tq_body.rindex('tea') + 1
app._apply_formatting(app.body_text, [
    {'start': _tq_at, 'end': _tq_at + 1, 'style': 'text_color',
     'value': '#e63946'}])
_tq_asks = [0]
_tq_real = NO.NoteOrganizer._grid_first_line


def _tq_counted(self, info):
    _tq_asks[0] += 1
    return _tq_real(self, info)


NO.NoteOrganizer._grid_first_line = _tq_counted
try:
    app._render_table_grids()
finally:
    NO.NoteOrganizer._grid_first_line = _tq_real
app.update()
_tq_last = app._table_grids[-1] if app._table_grids else None
_tq_runs = ([(_tq_last['canvas'].itemcget(t, 'text'),
              _tq_last['canvas'].itemcget(t, 'fill'))
             for t in _tq_last['cells'][(1, 0)]['texts']] if _tq_last else [])
check(f'drawing twelve tables asks where each grid starts a few times per '
      f'table, not for every cell ({_tq_asks[0]} asks)',
      len(app._table_grids) == 12 and _tq_asks[0] <= 3 * 12)
check(f'...and a coloured letter in the last of them still draws as itself '
      f'({_tq_runs})',
      ('e', '#e63946') in _tq_runs and ('t', app.colors['text']) in _tq_runs)
set_body('')

# A theme switch repaints the drawn tables in place. It rebuilt them, and
# each new grid is a window that maps a moment late: the switch flickered
# on a note with tables (field report). The repaint must leave every grid
# exactly as a rebuild in the new theme draws it.
_th_body = chr(10).join(
    'Part %d' % k + chr(10) + '| Item | Qty | Done |' + chr(10)
    + '| --- | --- | --- |' + chr(10)
    + '| tea | %d | %s |' % (k, core_tables.CHECKBOX_DONE) for k in range(8))
set_body(_th_body)
_th_item = _th_body.index('Item')
_th_tea = _th_body.index('tea')
_th_box = _th_body.index(core_tables.CHECKBOX_DONE)
app._apply_formatting(app.body_text, [
    {'start': _th_item, 'end': _th_item + 1, 'style': 'text_color',
     'value': '#e63946'},
    {'start': _th_tea, 'end': _th_tea + 3, 'style': 'highlight',
     'value': '#ffd166'},
    {'start': _th_box, 'end': _th_box + 3, 'style': 'text_color',
     'value': '#2a9d8f'}])
app._render_table_grids()
app.update()
app._grid_hide_col(app._table_grids[1], 1, True)
app.update()


def _th_snap():
    out = []
    for info in app._table_grids:
        cv = info['canvas']
        items = []
        for it in cv.find_all():
            if 'find_flash' in cv.gettags(it):
                continue
            have = cv.itemconfigure(it)
            opts = tuple((k, str(cv.itemcget(it, k))) for k in
                         ('fill', 'outline', 'width', 'text', 'font') if k in have)
            items.append((cv.type(it), tuple(round(v) for v in cv.coords(it)),
                          opts))
        out.append((str(info['frame'].cget('bg')), str(cv.cget('bg')),
                    sorted(items)))
    return out


_th_orig = app.theme_name
_th_info = app._table_grids[0]
app._grid_select_range(_th_info, (1, 0), (1, 1))
_th_names = [str(i['frame']) for i in app._table_grids]
_th_cells = sum(len(i['cells']) for i in app._table_grids)
_th_asks = [0]
_th_real = NO.NoteOrganizer._grid_first_line


def _th_counted(self, info):
    _th_asks[0] += 1
    return _th_real(self, info)


NO.NoteOrganizer._grid_first_line = _th_counted
try:
    app.set_theme('light' if _th_orig in NO.DARK_THEMES else 'dark')
finally:
    NO.NoteOrganizer._grid_first_line = _th_real
app.update()
check('a theme switch keeps every drawn table, repainted in place',
      [str(i['frame']) for i in app._table_grids] == _th_names)
_th_sel = getattr(app, '_grid_sel', None) or {}
check('...its selection outlined in the new accent',
      len(_th_sel.get('cells', [])) == 2 and all(
          str(_th_info['canvas'].itemcget(_th_info['cells'][k]['rect'], 'outline'))
          == app.colors['accent'] for k in _th_sel['cells']))
check(f'...asking where a grid starts a few times per cell, not of every grid '
      f'({_th_asks[0]} asks for {_th_cells} cells)',
      _th_asks[0] <= 6 * _th_cells)
app._grid_clear_selection()
_th_in_place = _th_snap()
app._render_table_grids()
app.update()
check('...and each one drawn exactly as a rebuild in the new theme draws it',
      _th_in_place == _th_snap() and len(_th_in_place) == 8)
# A stale grid (widths that changed under it) is still rebuilt.
app._table_grids[0]['stale'] = True
_th_names = [str(i['frame']) for i in app._table_grids]
app.set_theme(_th_orig)
app.update()
check('...while a stale table is rebuilt at the switch',
      not set(_th_names) & {str(i['frame']) for i in app._table_grids})
set_body('')

# ---- A TABLE OPERATION LEAVES EVERY CELL IT DID NOT TOUCH AS IT WAS ----
# Clearing ONE cell with Delete, dropping a checkbox, deleting a row,
# pasting cells: each rewrote the table's whole text, and every bold word
# and colour in the table died with it -- "the accepted cost of
# reshaping", said the rewrite, while clearing a cell reshapes nothing.
# The styles are carried cell by cell now, and the ops that MOVE cells (a
# row or column in or out, copies at an edge) carry them to where the
# cell went. Asked of the store (the spans a save writes) and, for the
# moved cells, of the drawing too.
_cs_body = ('| Item | Qty | Done |' + chr(10) + '| --- | --- | --- |' + chr(10)
            + '| Milk | 2 | x |' + chr(10) + '| Eggs | 12 | y |')


def _cs_setup():
    set_body(_cs_body)
    _m, _q = _cs_body.index('Milk'), _cs_body.index('12')
    app._apply_formatting(app.body_text, [
        {'start': _m, 'end': _m + 4, 'style': 'bold'},
        {'start': _q, 'end': _q + 2, 'style': 'text_color',
         'value': '#e63946'}])
    app._render_table_grids()
    app.update()
    return app._grid_at_line(1)


def _cs_styles():
    _b = app.body_text.get('1.0', 'end-1c')
    return sorted((s['style'], _b[s['start']:s['end']])
                  for s in app._extract_formatting(app.body_text))


def _cs_paint(r, c):
    _i = app._grid_at_line(1)
    return None if _i is None else app._grid_cell_paint(_i, r, c)


_cs_want = [('bold', 'Milk'), ('text_color', '12')]
_cs_info = _cs_setup()
check('carried styles: the fixture carries the bold and the red',
      _cs_styles() == _cs_want)
app._grid_select_range(_cs_info, (1, 2), (1, 2))
app._on_body_delete_key()
app.update()
check('carried styles: clearing ANOTHER cell with Delete keeps them '
      f'({_cs_styles()})',
      _cs_styles() == _cs_want and 'x' not in app.body_text.get('3.0', '3.end'))
_cs_info = _cs_setup()
app._grid_set_marker(_cs_info, 2, 2, core_tables.CHECKBOX_EMPTY)
app.update()
check(f'carried styles: dropping a checkbox elsewhere keeps them ({_cs_styles()})',
      _cs_styles() == _cs_want)
_cs_info = _cs_setup()
app._grid_insert_row(_cs_info, 3)
app.update()
app._grid_delete_row(app._grid_at_line(1), 3)
app.update()
check(f'carried styles: adding and deleting an empty row keeps them ({_cs_styles()})',
      _cs_styles() == _cs_want)
_cs_info = _cs_setup()
app._grid_delete_row(_cs_info, 1)
app.update()
check('carried styles: deleting the bold row moves the red up with its row '
      f'({_cs_styles()})',
      _cs_styles() == [('text_color', '12')]
      and (_cs_paint(1, 1) or {}).get('fg') == '#e63946')
_cs_info = _cs_setup()
app._grid_insert_col(_cs_info, 0)
app.update()
check('carried styles: a column inserted in front moves both styles right '
      f'({_cs_styles()})',
      _cs_styles() == _cs_want and (_cs_paint(1, 1) or {}).get('bold')
      and (_cs_paint(2, 2) or {}).get('fg') == '#e63946')
_cs_info = _cs_setup()
app._grid_delete_col(_cs_info, 0)
app.update()
check('carried styles: deleting the first column moves the red left '
      f'({_cs_styles()})',
      _cs_styles() == [('text_color', '12')]
      and (_cs_paint(2, 0) or {}).get('fg') == '#e63946')
_cs_info = _cs_setup()
app._grid_append_rows(_cs_info, 1, 1)
app.update()
check(f'carried styles: a row copied to the bottom brings its bold ({_cs_styles()})',
      _cs_styles() == [('bold', 'Milk'), ('bold', 'Milk'), ('text_color', '12')])
_cs_info = _cs_setup()
app._grid_append_cols(_cs_info, 1, 1)
app.update()
check(f'carried styles: a column copied to the edge brings its red ({_cs_styles()})',
      _cs_styles() == [('bold', 'Milk'), ('text_color', '12'),
                       ('text_color', '12')])
_cs_saved_clip = (NO.clipboard.read_html, NO.clipboard.read_text,
                  NO.clipboard.write)
_cs_info = _cs_setup()
_stub_clipboard(text='z')
app._grid_cell_clip = None
app.clipboard_get = lambda **k: 'z'
try:
    app._grid_paste_cells(_cs_info, 1, 2)
    app.update()
finally:
    del app.clipboard_get
check(f'carried styles: pasting into another cell keeps them ({_cs_styles()})',
      _cs_styles() == _cs_want
      and core_tables.split_row(app.body_text.get('3.0', '3.end'))[2] == 'z')
# A merge moves every cell's text into the merged cell ("nothing the merge
# swallows is thrown away") and dropped every style that text carried.
# The red '12' joins 'Eggs' at an offset, so it proves where the style
# lands, not only that one survived.
_cs_info = _cs_setup()
app._grid_merge_selection({'info': _cs_info, 'box': (2, 0, 2, 1)})
app.update()
check('carried styles: merging the red 12 into its row\'s first cell keeps '
      f'it red, on the 12 ({_cs_styles()}, '
      f'{core_tables.split_row(app.body_text.get("4.0", "4.end"))})',
      _cs_styles() == _cs_want
      and core_tables.split_row(app.body_text.get('4.0', '4.end'))[0]
      == 'Eggs 12')
# The same through the cell menu's "Merge with cell to the left", which
# goes the same way now; it used to write over the 12 and its red.
_cs_info = _cs_setup()
app._grid_merge_with(_cs_info, 2, 1, 'left')
app.update()
check('carried styles: Merge with cell to the left keeps the red 12 too '
      f'({_cs_styles()}, '
      f'{core_tables.split_row(app.body_text.get("4.0", "4.end"))})',
      _cs_styles() == _cs_want
      and core_tables.split_row(app.body_text.get('4.0', '4.end'))[0]
      == 'Eggs 12')

# ---- CELLS PASTED WIDER THAN THE TABLE GROW IT ----
# Four columns copied from a spreadsheet into a two-column table: the rows
# grew to fit, the two extra columns were dropped without a word. Columns
# grow now exactly as rows always did (no table has a column cap, so
# nothing is clipped). Pasted through the cell editor's own Ctrl+V.
set_body('| Name | Phone |' + chr(10) + '| --- | --- |' + chr(10) + '|  |  |')
app._render_table_grids()
app.update()
_pw_tsv = (chr(9).join(['Ana', '0722 111 222', 'Bucharest', 'ana@example.com'])
           + chr(10)
           + chr(9).join(['Dan', '0733 444 555', 'Cluj', 'dan@example.com']))
_stub_clipboard(text=_pw_tsv)
app._grid_cell_clip = None
app.clipboard_get = lambda **k: _pw_tsv
try:
    app._open_cell_editor(app._grid_at_line(1), 1, 0)
    app.update()
    check('wide paste: the cell editor holds the keyboard (precondition)',
          take_focus(app._cell_editor['entry']))
    app._cell_editor['entry'].event_generate('<Control-v>')
    app.update()
finally:
    del app.clipboard_get
NO.clipboard.read_html, NO.clipboard.read_text, NO.clipboard.write = \
    _cs_saved_clip
_pw_rows = [core_tables.split_row(_l)
            for _l in app.body_text.get('1.0', 'end-1c').split(chr(10))
            if core_tables.is_table_row(_l)
            and not core_tables.is_separator_row(_l)]
check(f'wide paste: four columns into a two-column table grow it to four ({_pw_rows})',
      _pw_rows == [['Name', 'Phone', '', ''],
                   ['Ana', '0722 111 222', 'Bucharest', 'ana@example.com'],
                   ['Dan', '0733 444 555', 'Cluj', 'dan@example.com']])
check('wide paste: and the drawn grid has the four columns',
      (app._grid_at_line(1) or {}).get('ncols') == 4)
set_body('')

# ---- CTRL+Z TAKES BACK A STYLE CHANGE, AND ONLY IT ----
# Tk's undo stack holds text, never a tag. Bolding a word left nothing
# on it, so Ctrl+Z skipped the bold and took back the last burst of
# typing instead (and the autosave stored that); Ctrl+Y brought the
# typing back without the bold. A formatting journal beside Tk's stack
# now takes the style back first, and the typing on later presses, in
# order. Every sibling formatting action -- a colour, a size, a centred
# line, an indented paragraph, a styled cell -- is checked the same way.
# Keys through Tk: the body's focus is a precondition, forced and asserted.
def _uf_key(sequence):
    if not take_focus(app.body_text):
        return False
    app.body_text.event_generate(sequence)
    app.update()
    return True


def _uf_setup(body, typed=''):
    """A note holding *body*, with *typed* then typed at its end as one
    burst and the pause after it -- the boundary an autosave leaves."""
    set_body(body)
    app._reset_text_undo()
    app.body_text.mark_set('insert', 'end-1c')
    for _ch in typed:
        app.body_text.insert('insert', _ch)
    app._flush_table_grids()


def _uf_select(word):
    _at = app.body_text.search(word, '1.0', 'end')
    app.body_text.tag_remove('sel', '1.0', 'end')
    app.body_text.tag_add('sel', _at, f'{_at}+{len(word)}c')
    app.body_text.mark_set('insert', f'{_at}+{len(word)}c')


_uf_typed = 'the meeting moved to Friday'
_uf_full = 'Dear Ana,' + chr(10) + _uf_typed
_uf_setup('Dear Ana,' + chr(10), _uf_typed)
_uf_select('Friday')
check('style undo: the body holds the keyboard (precondition)',
      _uf_key('<Control-b>'))
check('style undo: Ctrl+B made the word bold (fixture)',
      _cs_styles() == [('bold', 'Friday')])
_uf_key('<Control-z>')
check('style undo: Ctrl+Z right after a bold takes back the bold ONLY '
      f'({app.body_text.get("1.0", "end-1c")!r}, {_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _uf_full and _cs_styles() == [])
_uf_key('<Control-y>')
check(f'style undo: Ctrl+Y gives the bold back ({_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
_uf_key('<Control-z>')
_uf_key('<Control-z>')
check('style undo: the typing goes on the NEXT press, in order '
      f'({app.body_text.get("1.0", "end-1c")!r})',
      app.body_text.get('1.0', 'end-1c') == 'Dear Ana,' + chr(10))
_uf_key('<Control-y>')
_uf_key('<Control-y>')
check(f'style undo: two Ctrl+Y bring the typing AND the bold back ({_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
# Typing AFTER the style is undone first; the style on the press after.
_uf_setup('Dear Ana,' + chr(10), _uf_typed)
_uf_select('Friday')
_uf_key('<Control-b>')
app.body_text.tag_remove('sel', '1.0', 'end')
app.body_text.mark_set('insert', 'end-1c')
app.body_text.edit_separator()
app.body_text.insert('insert', ' at ten')
_uf_key('<Control-z>')
check('style undo: typing after the bold is taken back first '
      f'({app.body_text.get("1.0", "end-1c")!r}, {_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
_uf_key('<Control-z>')
check(f'style undo: ...and the bold on the press after it ({_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _uf_full and _cs_styles() == [])

# The siblings: every other action that changes formatting and no text.
for _uf_name, _uf_do, _uf_read, _uf_before in (
        ('a text colour',
         lambda: app._apply_body_color('text_color', '#e63946'),
         _cs_styles, []),
        ('a font size',
         lambda: app._apply_body_font('font_size', 14),
         _cs_styles, []),
        ('a centred line',
         lambda: app._set_paragraph_align('center'),
         lambda: app._paragraph_align_of(app.body_text, 2), 'left'),
        ('an indented plain paragraph',
         lambda: app._change_paragraph_indent(+1),
         lambda: app._paragraph_indent_of(app.body_text, 2), 0)):
    _uf_setup('Dear Ana,' + chr(10), _uf_typed)
    _uf_select('Friday')
    _uf_do()
    app.update()
    _uf_changed = _uf_read()
    _uf_key('<Control-z>')
    check(f'style undo: Ctrl+Z takes back {_uf_name} and keeps the typing '
          f'({_uf_changed!r} -> {_uf_read()!r})',
          _uf_changed != _uf_before and _uf_read() == _uf_before
          and app.body_text.get('1.0', 'end-1c') == _uf_full)
# A styled cell is the same kind of step.
_uf_info = _cs_setup()
app._reset_text_undo()
app._grid_apply_style(_uf_info, (2, 0, 2, 0), 'bold')
app.update()
_uf_bold = _cs_styles()
_uf_key('<Control-z>')
check(f'style undo: Ctrl+Z takes back a cell made bold ({_uf_bold} -> {_cs_styles()})',
      ('bold', 'Eggs') in _uf_bold and _cs_styles() == _cs_want)

# Caps Lock turns the letter over: Tk reads Ctrl+Z as an upper-case Z,
# which no letter binding of the body matched, so Tk's own <<Undo>>
# walked its stack behind the journal's back -- the bold went with the
# typing. Pressed the way the keyboard sends it: the key's code with
# Control and Lock held (a generated <Control-Lock-Z> pattern is not
# faithful on Windows, where Tk adds Shift to reach an upper-case Z). The
# code is read off a throwaway entry, so the same lines run on X11. A spy
# counts the presses that reach the journal, a tag ahead of the body's
# own records what Tk made of each press.
def _ck_codes(*keysyms):
    _ent = tk.Entry(app)
    _ent.place(x=0, y=0)
    _got = {}
    _ent.bind('<KeyPress>',
              lambda e: (_got.setdefault(e.keysym, e.keycode), 'break')[1])
    try:
        if take_focus(_ent):
            for _k in keysyms:
                _ent.event_generate(f'<KeyPress-{_k}>')
                app.update()
    finally:
        _ent.destroy()
    return [_got.get(_k) for _k in keysyms]


_ck_calls, _ck_seen = [], []
_ck_real = app._body_undo_redo
_ck_tags = app.body_text.bindtags()


def _ck_press(code, state):
    del _ck_calls[:], _ck_seen[:]
    if code is None or not take_focus(app.body_text):
        return False
    app.body_text.event_generate('<KeyPress>', keycode=code, state=state)
    app.body_text.event_generate('<KeyRelease>', keycode=code, state=state)
    app.update()
    return True


app.bind_class('QaKeySeen', '<KeyPress>',
               lambda e: _ck_seen.append((e.keysym, e.state & 0x7)))
app.body_text.bindtags(('QaKeySeen',) + tuple(_ck_tags))
app._body_undo_redo = lambda action: (_ck_calls.append(action),
                                      _ck_real(action))[1]
try:
    _ck_z, _ck_y = _ck_codes('z', 'y')
    check(f'caps lock: the keyboard codes of Z and Y were read ({_ck_z}, {_ck_y}) '
          '(precondition)', _ck_z is not None and _ck_y is not None)
    _uf_setup('Dear Ana,' + chr(10), _uf_typed)
    _uf_select('Friday')
    _uf_key('<Control-b>')
    check('caps lock: the body holds the keyboard (precondition)',
          _ck_press(_ck_z, 0x6))
    check(f'caps lock: the press reads as Ctrl+Z under Caps Lock ({_ck_seen}) '
          '(precondition)', _ck_seen[:1] == [('Z', 0x6)])
    check('caps lock: Ctrl+Z takes back the bold ONLY, through the journal, '
          f'once ({_ck_calls}, {app.body_text.get("1.0", "end-1c")!r}, '
          f'{_cs_styles()})',
          _ck_calls == ['undo'] and _cs_styles() == []
          and app.body_text.get('1.0', 'end-1c') == _uf_full)
    # Ctrl+Y under Caps Lock is a spelling of <<Redo>> on Windows only: X11's
    # <<Redo>> is Ctrl+Shift+Z alone, and there the press reaches nothing.
    if '<Control-Lock-Key-Y>' in app.tk.call('event', 'info', '<<Redo>>'):
        _ck_press(_ck_y, 0x6)
        check(f'caps lock: Ctrl+Y gives the bold back ({_ck_seen}, '
              f'{_ck_calls}, {_cs_styles()})',
              _ck_calls == ['redo'] and _cs_styles() == [('bold', 'Friday')]
              and app.body_text.get('1.0', 'end-1c') == _uf_full)
    else:
        _ck_real('redo')
        app.update()
    # Shift as well turns it back into a lower-case z, which the plain
    # Ctrl+Z binding answered: Ctrl+Shift+Z undid instead of redoing.
    _ck_press(_ck_z, 0x6)
    _ck_press(_ck_z, 0x7)
    check('caps lock: Ctrl+Shift+Z is still a redo '
          f'({_ck_seen}, {_ck_calls}, {_cs_styles()})',
          _ck_calls == ['redo'] and _cs_styles() == [('bold', 'Friday')])
    # Without Caps Lock a press matches a letter AND the virtual event: it
    # still runs once (Tk runs the most specific binding of the tag).
    _ck_press(_ck_z, 0x4)
    check(f'caps lock: a plain Ctrl+Z still undoes exactly once ({_ck_calls})',
          _ck_calls == ['undo'] and _cs_styles() == [])
    del _ck_calls[:]
    app.body_text.event_generate('<<Redo>>')
    app.update()
    check(f'caps lock: Tk\'s <<Redo>> reaches the journal ({_ck_calls}, '
          f'{_cs_styles()})',
          _ck_calls == ['redo'] and _cs_styles() == [('bold', 'Friday')])
    del _ck_calls[:]
    app.body_text.event_generate('<<Undo>>')
    app.update()
    check(f'caps lock: ...and so does <<Undo>> ({_ck_calls}, {_cs_styles()})',
          _ck_calls == ['undo'] and _cs_styles() == []
          and app.body_text.get('1.0', 'end-1c') == _uf_full)
    # The comments box, the same turn of the letter: Ctrl+Shift+Z under
    # Caps Lock arrives as a lower-case z, which its plain Ctrl+Z binding
    # answered -- an undo where a redo was asked for.
    _ck_cm = app.comments_text
    _ck_cm.delete('1.0', 'end')
    _ck_cm.edit_reset()
    _ck_cm.insert('end', 'first')
    _ck_cm.edit_separator()
    _ck_cm.insert('end', ' second')
    _ck_cm.edit_separator()
    _ck_cm.edit_undo()
    _ck_cm_ok = _ck_z is not None and take_focus(_ck_cm)
    if _ck_cm_ok:
        _ck_cm.event_generate('<KeyPress>', keycode=_ck_z, state=0x7)
        _ck_cm.event_generate('<KeyRelease>', keycode=_ck_z, state=0x7)
        app.update()
    check(f'caps lock: Ctrl+Shift+Z in the comments box redoes, not undoes '
          f'({_ck_cm.get("1.0", "end-1c")!r}, keyboard there: {_ck_cm_ok})',
          _ck_cm_ok and _ck_cm.get('1.0', 'end-1c') == 'first second')
    _ck_cm.delete('1.0', 'end')
    _ck_cm.edit_reset()
finally:
    app.body_text.bindtags(_ck_tags)
    del app._body_undo_redo

# ---- THE JOURNAL COSTS WHAT A STEP CHANGED, NOT WHAT THE NOTE HOLDS ----
# Every unit configured the body (autoseparators off, then on), and Tk
# re-lays out every line of the note on any configure: a bold on a long
# note went from 46 to 266 ms. Every unit kept two full copies of the
# note's formatting (+60 MB over 100 cell edits on a heavily styled
# note), a cell click with no cell open took both copies for nothing, and
# Ctrl+Z of one bold stripped and re-laid every style in the note and
# redrew every table -- seconds. Asked of the mechanism, never of a clock:
# what the body was asked to do, which widgets survived, what is shared.
_jc_body = ('Plan the trip' + chr(10) + '| Item | Qty |' + chr(10)
            + '| --- | --- |' + chr(10) + '| Milk | 2 |' + chr(10)
            + 'pack the bags')


def _jc_setup():
    set_body(_jc_body)
    _m = _jc_body.index('Milk')
    app._apply_formatting(app.body_text,
                          [{'start': _m, 'end': _m + 4, 'style': 'bold'}])
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    return app._grid_at_line(2)


def _jc_frame():
    return str(app._table_grids[0]['frame']) if app._table_grids else None


_jc_seps = []
_jc_real_configure = app.body_text.configure


def _jc_configure(*a, **k):
    if 'autoseparators' in k:
        _jc_seps.append(k['autoseparators'])
    return _jc_real_configure(*a, **k)


# Each record is read the moment the action returns, before anything runs
# the event loop: an autosave firing in an update() commits an open cell
# through a unit of its own, and on a slow run its pairs joined the record
# (a full-suite run on Linux read four).
app.body_text.configure = _jc_configure
try:
    _jc_setup()
    _uf_select('trip')
    del _jc_seps[:]
    app._toggle_body_style('bold')
    _jc_seen = list(_jc_seps)
    app.update()
    check('journal: a bold lays no configure on the body, which re-lays out '
          f'the whole note ({_jc_seen}, {_cs_styles()})',
          _jc_seen == [] and ('bold', 'trip') in _cs_styles())
    _jc_info = _jc_setup()
    del _jc_seps[:]
    app._grid_insert_row(_jc_info, 1)
    _jc_seen = list(_jc_seps)
    app.update()
    check(f'journal: ...while a table operation still groups its edits ({_jc_seen})',
          _jc_seen == [False, True])
    # A tags-only action that reaches a text edit after all -- the toolbar's
    # Italic with a cell open commits the typing in it first -- groups it.
    _jc_info = _jc_setup()
    app._open_cell_editor(_jc_info, 1, 1)
    app.update()
    app._cell_editor['entry'].insert('end', '5')
    del _jc_seps[:]
    app._toggle_body_style('italic')
    _jc_seen = list(_jc_seps)
    app.update()
    check('journal: a tags-only action that commits an open cell groups that '
          f'edit ({_jc_seen}, '
          f'{core_tables.split_row(app.body_text.get("4.0", "4.end"))})',
          _jc_seen == [False, True]
          and core_tables.split_row(app.body_text.get('4.0', '4.end'))[1]
          == '25')
    app._commit_cell_editor()
    app.update()
finally:
    del app.body_text.configure
# Ctrl+Z of a bold in the prose touches that word: the table and its own
# bold stay as they are -- the same drawn grid, not a rebuilt one.
_jc_setup()
_uf_select('trip')
app._toggle_body_style('bold')
app.update()
app.body_text.tag_remove('sel', '1.0', 'end')
_jc_before = _jc_frame()
_uf_key('<Control-z>')
check('journal: Ctrl+Z of a bold in the prose leaves the drawn table '
      f'standing ({_jc_before} -> {_jc_frame()}, {_cs_styles()})',
      _jc_before is not None and _jc_frame() == _jc_before
      and _cs_styles() == [('bold', 'Milk')])
_uf_key('<Control-y>')
check(f'journal: ...and Ctrl+Y lays it again ({_cs_styles()})',
      _cs_styles() == [('bold', 'Milk'), ('bold', 'trip')]
      and _jc_frame() == _jc_before)
# A step that restyled a cell does redraw: the drawing shows the cell.
_jc_info = _jc_setup()
app._grid_apply_style(_jc_info, (1, 0, 1, 0), 'bold')
app.update()
_jc_before = _jc_frame()
_uf_key('<Control-z>')
check('journal: Ctrl+Z of a cell made plain draws the table again '
      f'({_jc_before} -> {_jc_frame()}, {_cs_styles()})',
      _jc_frame() is not None and _jc_frame() != _jc_before
      and _cs_styles() == [('bold', 'Milk')])
# Steps share what they did not change: the snapshot after one step IS
# the one before the next, and a tag the step left alone is the same
# string in both of its snapshots.
_jc_setup()
for _jc_word, _jc_style in (('trip', 'bold'), ('pack', 'italic'),
                            ('bags', 'underline')):
    _uf_select(_jc_word)
    app._toggle_body_style(_jc_style)
    app.update()
_jc_steps = list(app._fmt_undo)
_jc_bold = [dict(_s[_side][2]).get('bold') for _s in _jc_steps[1:]
            for _side in ('before', 'after')]
check(f'journal: three styles in a row are three steps sharing their '
      f'snapshots ({len(_jc_steps)} steps)',
      len(_jc_steps) == 3
      and _jc_steps[0]['after'] is _jc_steps[1]['before']
      and _jc_steps[1]['after'] is _jc_steps[2]['before']
      and _jc_bold[0] is not None
      and all(_b is _jc_bold[0] for _b in _jc_bold))
# A commit with no cell open -- every cell click and table operation
# starts with one -- notes nothing.
_jc_setup()
_jc_notes = []
app._fmt_state = lambda: (_jc_notes.append(1),
                          type(app)._fmt_state(app))[1]
try:
    app._commit_cell_editor()
finally:
    del app._fmt_state
check(f'journal: a commit with no cell open takes no snapshot ({len(_jc_notes)})',
      app._cell_editor is None and _jc_notes == [])
set_body('')

# ---- A SAVE RUN DIRECTLY LEAVES NO AUTOSAVE WAITING ----
# _autosave_now set its job to None rather than cancelling it, so a timer
# waiting when the save ran some other way stayed scheduled with nothing
# tracking it -- and on firing it forgot the NEXT job the same way: a
# relay of untracked saves, 28 in one run of this script, one of which
# split a held BackSpace's undo step in the block below. The note id
# points nowhere, so the save itself stops at its first guard.
_as_sel = app.selected_note_id
app._cancel_pending_autosave()
app._schedule_autosave()
_as_before = _qa_waiting(app, '_autosave_now')
app.selected_note_id = 999999
try:
    app._autosave_now()
finally:
    app.selected_note_id = _as_sel
_as_after = _qa_waiting(app, '_autosave_now')
check(f'a save run directly leaves no autosave waiting behind it '
      f'({_as_before} -> {_as_after})',
      len(_as_before) == 1 and not _as_after
      and getattr(app, '_autosave_job', None) is None)

# ---- CTRL+Z GIVES BACK WHAT TK'S OWN DELETES TOOK, WITH ITS FORMATTING ----
# Delete, BackSpace, typing over a selection and Cut are Tk's own
# bindings, and Tk's stack holds no tag: Ctrl+Z gave the text back plain,
# the bold gone. A tag ahead of the body's bindings notes the formatting
# first (_note_styled_delete). <<Clear>> stands for Cut -- the same
# delete, without writing to the clipboard of the machine running this.
def _nd_setup():
    """'Friday' bold in a note just opened: on the text, not on any stack.

    No autosave is left pending: its boundary ends a run of deletes (on
    purpose -- see the check about a pause below), and one firing in the
    middle of a check's key run, on a loaded machine, would split the run
    the check is about."""
    _uf_setup('Dear Ana,' + chr(10), _uf_typed)
    _uf_select('Friday')
    _uf_key('<Control-b>')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.tag_remove('sel', '1.0', 'end')


def _nd_clear():
    app.body_text.event_generate('<<Clear>>')
    app.update()
    return True


def _nd_burst(press, count):
    """*count* presses of a key, each with its release, as one burst: what
    a person sends holding the key down, or tapping it quickly.

    A burst has no pause in it, and a pause is what the 500ms autosave
    measures -- its boundary ends a run of deletes on purpose (the pause
    check below). Two things made one here anyway, on a loaded machine:
    an autosave left waiting from earlier in this script with nothing
    tracking it (its job set to None instead of cancelled -- see
    _autosave_now), and each press's own wait for the keyboard outlasting
    a release's autosave. Either fired between two presses and split the
    run the check is about ('Fr' came back alone on Linux; a 0.7s wait
    between presses does it on any machine). So a burst starts with no
    autosave waiting at all -- asked of Tcl, not of the job the app
    tracks -- and holds the autosave for its length: its target is
    replaced, which is what a timer captures when it is SCHEDULED. The
    dirty poll ends a run too; with one tab it captures nothing."""
    release = press.replace('KeyPress', 'KeyRelease')
    app._cancel_pending_autosave()
    _waiting = _qa_waiting(app, '_autosave_now')
    check(f'native delete: a burst of {press} starts with no autosave '
          f'waiting, tracked or not, and one tab (fixture: {_waiting})',
          not _waiting and len(app.open_tabs) <= 1)
    app._autosave_now = lambda: None
    try:
        for _ in range(count):
            _uf_key(press)
            app.body_text.event_generate(release)
            app.update()
    finally:
        del app._autosave_now
        app._cancel_pending_autosave()


_nd_real_read_text = NO.clipboard.read_text
for _nd_name, _nd_do in (
        ('Delete', lambda: _uf_key('<KeyPress-Delete>')),
        ('BackSpace', lambda: _uf_key('<KeyPress-BackSpace>')),
        ('typing over it', lambda: _uf_key('<KeyPress-x>')),
        ('Cut (as Clear)', _nd_clear),
        ('Paste without formatting', lambda: (app._paste_plain(), app.update(), True)[-1])):
    _nd_setup()
    check(f'native delete: the fixture holds a bold word on no stack ({_cs_styles()})',
          _cs_styles() == [('bold', 'Friday')] and not app._fmt_undo)
    _uf_select('Friday')
    NO.clipboard.read_text = lambda: 'Monday'
    try:
        _nd_done = _nd_do()
    finally:
        NO.clipboard.read_text = _nd_real_read_text
    _nd_gone = 'Friday' not in app.body_text.get('1.0', 'end-1c')
    _uf_key('<Control-z>')
    check(f'native delete: {_nd_name} over a bold word, then Ctrl+Z, gives the '
          f'word back bold (deleted: {_nd_done and _nd_gone}; '
          f'{app.body_text.get("1.0", "end-1c")!r}, {_cs_styles()})',
          _nd_done and _nd_gone
          and app.body_text.get('1.0', 'end-1c') == _uf_full
          and _cs_styles() == [('bold', 'Friday')])
    _uf_key('<Control-y>')
    check(f'native delete: ...and Ctrl+Y takes it away again ({_cs_styles()})',
          'Friday' not in app.body_text.get('1.0', 'end-1c')
          and ('bold', 'Friday') not in _cs_styles())

# BackSpace held through the word: one Ctrl+Z, as Tk merges the run --
# and where the run leaves the bold for plain text, two, each laying the
# formatting it took back on the text it restores.
_nd_setup()
app.body_text.mark_set('insert', 'end-1c')
_nd_burst('<KeyPress-BackSpace>', len('Friday'))
_nd_after_run = app.body_text.get('1.0', 'end-1c')
_uf_key('<Control-z>')
check(f'native delete: six BackSpaces through a bold word are one Ctrl+Z, '
      f'bold again ({_nd_after_run!r} -> {_cs_styles()})',
      _nd_after_run == 'Dear Ana,' + chr(10) + 'the meeting moved to '
      and app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
_nd_setup()
app.body_text.mark_set('insert', 'end-1c')
_nd_burst('<KeyPress-BackSpace>', len(' to Friday'))
_uf_key('<Control-z>')
_nd_first = (app.body_text.get('1.0', 'end-1c'), _cs_styles())
_uf_key('<Control-z>')
check(f'native delete: BackSpace from a bold word into plain text: the '
      f'plain part comes back first, then the word, bold ({_nd_first} -> '
      f'{_cs_styles()})',
      _nd_first == ('Dear Ana,' + chr(10) + 'the meeting moved to ', [])
      and app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
# Undo reached without a key (any caller of _body_undo_redo) closes the
# run the same way the key's own press does.
_nd_setup()
_uf_select('Friday')
_uf_key('<KeyPress-Delete>')
app._body_undo_redo('undo')
check(f'native delete: Undo called without a key gives the bold word back '
      f'too ({_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
# A toolbar operation right after the delete is a step of its own, taken
# back first: the run closes where the operation's unit opens.
_nd_setup()
_uf_select('Friday')
_uf_key('<KeyPress-Delete>')
_uf_select('Dear')
app._toggle_body_style('bold')
app.update()
_uf_key('<Control-z>')
_nd_first = (app.body_text.get('1.0', 'end-1c'), _cs_styles())
_uf_key('<Control-z>')
check(f'native delete: a toolbar bold after the delete is taken back first, '
      f'then the word comes back bold ({_nd_first} -> {_cs_styles()})',
      _nd_first == ('Dear Ana,' + chr(10) + 'the meeting moved to ', [])
      and app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])
# The other way round: plain text first, then the bold word. Tk would
# merge the two into one unit, and the formatting noted at the bold
# word's edge would never meet the text that unit restores.
_nd_setup()
app.body_text.mark_set('insert', 'end-1c')
app.body_text.insert('insert', ' at ten')
app.body_text.edit_separator()
_nd_burst('<KeyPress-BackSpace>', len('Friday at ten'))
_uf_key('<Control-z>')
_nd_first = (app.body_text.get('1.0', 'end-1c'), _cs_styles())
_uf_key('<Control-z>')
check(f'native delete: BackSpace from plain text into a bold word: the word '
      f'comes back bold first, then the plain part ({_nd_first} -> '
      f'{app.body_text.get("1.0", "end-1c")!r})',
      _nd_first == (_uf_full, [('bold', 'Friday')])
      and app.body_text.get('1.0', 'end-1c') == _uf_full + ' at ten'
      and _cs_styles() == [('bold', 'Friday')])
# Plain text is left to Tk entirely: no step of ours, no separator, and
# not even the look at the formatting that a step would cost.
_uf_setup('Dear Ana,' + chr(10), _uf_typed)
app.body_text.mark_set('insert', 'end-1c')
_nd_burst('<KeyPress-BackSpace>', 3)
_nd_open = getattr(app, '_styled_delete_run', None)
_uf_key('<Control-z>')
check(f'native delete: BackSpace through plain text notes nothing and is '
      f'still one Ctrl+Z ({app.body_text.get("1.0", "end-1c")!r}, '
      f'a step opened: {_nd_open is not None})',
      _nd_open is None and app.body_text.get('1.0', 'end-1c') == _uf_full)
# A pause in the middle of the run: the autosave's boundary (one pause, one
# Ctrl+Z, as Tk does for typing) split Tk's unit under the run's single
# step, and both halves came back plain. Each half is a step of its own now.
_nd_setup()
app.body_text.mark_set('insert', 'end-1c')
_nd_burst('<KeyPress-BackSpace>', 3)
app._flush_table_grids()            # what an autosave does at a pause
_nd_burst('<KeyPress-BackSpace>', 3)
_uf_key('<Control-z>')
_nd_first = (app.body_text.get('1.0', 'end-1c'), _cs_styles())
_uf_key('<Control-z>')
check(f'native delete: a pause in a run through a bold word -- each part '
      f'comes back on its own Ctrl+Z, bold ({_nd_first} -> {_cs_styles()})',
      _nd_first == ('Dear Ana,' + chr(10) + 'the meeting moved to Fri',
                    [('bold', 'Fri')])
      and app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])

# The keys a person presses. Ctrl+X and Ctrl+V reach the bindtag's Cut and
# Paste as the key's own press, not as a virtual event, and were read as
# no delete at all; the menu's Paste tried the app's own paste routes
# first, and their undo units ended the run before Tk's paste deleted
# anything; Tk's own Ctrl+H, Ctrl+K and Ctrl+T were unknown to it. Each
# gave the bold back plain. Tcl's clipboard is replaced in this process
# for the block, so the machine's own clipboard is never read or written.
_kp_clip = {'data': 'Monday'}


def _kp_clipboard(*args):
    args = [str(a) for a in args]
    if args and args[0] == 'clear':
        _kp_clip['data'] = ''
    elif args and args[0] == 'append':
        _kp_clip['data'] += args[-1]
    elif args and args[0] == 'get':
        return _kp_clip['data']
    return ''


_kp_real = (NO.clipboard.read_text, NO.clipboard.read_html, NO.clipboard.write)
app.tk.eval('rename clipboard ::_qa1_real_clipboard')
app.tk.createcommand('clipboard', _kp_clipboard)
app.tk.eval('rename ::tk::GetSelection ::tk::_qa1_real_GetSelection')
app.tk.createcommand('::qa1_clip', lambda: _kp_clip['data'])
app.tk.eval('proc ::tk::GetSelection {w {sel PRIMARY}} {'
            ' if {$sel eq "CLIPBOARD"} {return [::qa1_clip]};'
            ' return [::tk::_qa1_real_GetSelection $w $sel] }')
NO.clipboard.read_text = lambda: _kp_clip['data']
NO.clipboard.read_html = lambda: None
NO.clipboard.write = lambda *a, **k: True


def _kp_at(index):
    app.body_text.tag_remove('sel', '1.0', 'end')
    app.body_text.mark_set('insert', index)


try:
    for _kp_name, _kp_do in (
            ('Ctrl+X', lambda: (_uf_select('Friday'),
                                _uf_key('<Control-KeyPress-x>'))),
            ('Ctrl+V', lambda: (_uf_select('Friday'),
                                _uf_key('<Control-KeyPress-v>'))),
            ("the menu's Paste", lambda: (
                _uf_select('Friday'), take_focus(app.body_text),
                app.body_text.event_generate('<<Paste>>'), app.update())),
            ('Ctrl+H six times', lambda: (
                _kp_at('end-1c'),
                _nd_burst('<Control-KeyPress-h>', 6))),
            ('Ctrl+K before it', lambda: (_kp_at('2.21'),
                                          _uf_key('<Control-KeyPress-k>'))),
            ("Ctrl+T at the word's end", lambda: (
                _kp_at('end-1c'), _uf_key('<Control-KeyPress-t>')))):
        _nd_setup()
        _kp_clip['data'] = 'Monday'
        _kp_do()
        _kp_after = app.body_text.get('1.0', 'end-1c')
        _uf_key('<Control-z>')
        check(f'native delete: {_kp_name} over a bold word, then Ctrl+Z, gives '
              f'the word back bold ({_kp_after!r} -> {_cs_styles()})',
              _kp_after != _uf_full
              and app.body_text.get('1.0', 'end-1c') == _uf_full
              and _cs_styles() == [('bold', 'Friday')])
finally:
    app.tk.deletecommand('clipboard')
    app.tk.eval('rename ::_qa1_real_clipboard clipboard')
    app.tk.eval('rename ::tk::GetSelection {}')
    app.tk.eval('rename ::tk::_qa1_real_GetSelection ::tk::GetSelection')
    app.tk.deletecommand('::qa1_clip')
    NO.clipboard.read_text, NO.clipboard.read_html, NO.clipboard.write = _kp_real

# A spreadsheet's cells pasted over selected text: the table takes the
# selection's place, as every other paste does. The selected text used to
# stay, and the table landed under its line.
_nd_setup()
_uf_select('Friday')
_ts_real = (NO.clipboard.read_text, NO.clipboard.read_html)
NO.clipboard.read_text = lambda: 'Day\tTime' + chr(10) + 'Mon\t10:00'
NO.clipboard.read_html = lambda: None
try:
    _ts_done = app._on_body_paste()
    app.update()
finally:
    NO.clipboard.read_text, NO.clipboard.read_html = _ts_real
_ts_after = app.body_text.get('1.0', 'end-1c')
_uf_key('<Control-z>')
check(f'a spreadsheet\'s cells pasted over selected text replace it, and '
      f'Ctrl+Z gives the word back bold ({_ts_after!r} -> {_cs_styles()})',
      _ts_done == 'break' and 'Friday' not in _ts_after and '| Day' in _ts_after
      and app.body_text.get('1.0', 'end-1c') == _uf_full
      and _cs_styles() == [('bold', 'Friday')])

# ---- A SELECTION MEETS A DRAWN TABLE ----
# The caret guard walks the caret under a drawn table, and it left the
# selection's moving end behind. Shift+Down on the line above a table
# selected that line and the table's own line break, caret under the table:
# a letter went in under the table with the line still selected, a paste
# glued its text to the next line, and cells pasted went INTO the table.
# Shift+Up from under a table selected all of it, invisibly -- a grid shows
# no selection -- and the next letter deleted it. A first press now stops at
# the table's edge with the caret; a second press crosses, as before.
_sm_body = ('Prices:' + chr(10) + '| Item | Qty |' + chr(10)
            + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10) + 'after'
            + chr(10) + 'more')
_sm_tsv = 'Day\tTime' + chr(10) + 'Mon\t10:00'


def _sm_fresh(caret, body=None):
    set_body(_sm_body if body is None else body)
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.tag_remove('sel', '1.0', 'end')
    app.body_text.mark_set('insert', caret)
    app._sel_held_at_table = None
    app._last_caret_line = None


def _sm_press(seq):
    """A key pressed and released, as a person does, on the body."""
    if not take_focus(app.body_text):
        return False
    app.body_text.event_generate(seq)
    app.body_text.event_generate(seq.replace('KeyPress', 'KeyRelease'))
    app.update()
    return True


def _sm_where():
    try:
        sel = (app.body_text.index('sel.first'),
               app.body_text.index('sel.last'))
    except tk.TclError:
        sel = None
    return sel, app.body_text.index('insert')


def _sm_table_kept():
    """The old table stands whole, rows and all, as its own block."""
    text = app.body_text.get('1.0', 'end-1c')
    lines = text.split(chr(10))
    want = ['|Item|Qty|', '|---|---|', '|Tea|2|']
    return any([r.replace(' ', '') for r in lines[a:b + 1]] == want
               for a, b in core_tables.find_blocks(text))


_sm_clip = {'data': _sm_tsv}
_sm_real = (NO.clipboard.read_text, NO.clipboard.read_html)
app.tk.eval('rename ::tk::GetSelection ::tk::_qa1_sm_GetSelection')
app.tk.createcommand('::qa1_sm_clip', lambda: _sm_clip['data'])
app.tk.eval('proc ::tk::GetSelection {w {sel PRIMARY}} {'
            ' if {$sel eq "CLIPBOARD"} {return [::qa1_sm_clip]};'
            ' return [::tk::_qa1_sm_GetSelection $w $sel] }')
NO.clipboard.read_text = lambda: _sm_clip['data']
NO.clipboard.read_html = lambda: None
try:
    _sm_fresh('1.0')
    _sm_press('<Shift-KeyPress-Down>')
    _sm_one = _sm_where()
    _sm_press('<KeyPress-x>')
    check(f'selection x table: Shift+Down on the line above a table stops at '
          f'its edge, with the caret ({_sm_one}), and a letter replaces the '
          f'line, the table kept '
          f'({app.body_text.get("1.0", "2.0")!r}, kept {_sm_table_kept()})',
          _sm_one == (('1.0', '1.7'), '1.7')
          and app.body_text.get('1.0', '2.0') == 'x' + chr(10)
          and _sm_table_kept())
    _sm_fresh('1.0')
    _sm_press('<Shift-KeyPress-Down>')
    _sm_press('<Shift-KeyPress-Down>')
    check(f'selection x table: ...and a second Shift+Down crosses the table, '
          f'the caret with the selection ({_sm_where()})',
          _sm_where() == (('1.0', '5.0'), '5.0'))
    _sm_fresh('5.0')
    _sm_press('<Shift-KeyPress-Up>')
    _sm_up = _sm_where()
    _sm_press('<KeyPress-x>')
    check(f'selection x table: Shift+Up from under a table stops at its edge '
          f'({_sm_up}), so a letter typed then deletes nothing of it (kept '
          f'{_sm_table_kept()}, {app.body_text.get("5.0", "5.end")!r})',
          _sm_up == (None, '5.0') and _sm_table_kept()
          and app.body_text.get('5.0', '5.end') == 'xafter')
    _sm_fresh('5.0')
    _sm_press('<Shift-KeyPress-Up>')
    _sm_press('<Shift-KeyPress-Up>')
    check(f'selection x table: ...and a second Shift+Up crosses it '
          f'({_sm_where()})', _sm_where() == (('1.7', '5.0'), '1.7'))
    _sm_fresh('1.5')
    for _sm_i in range(3):
        _sm_press('<Shift-KeyPress-Right>')
    _sm_right = _sm_where()
    _sm_press('<Shift-KeyPress-Right>')
    check(f'selection x table: Shift+Right stops at the end of the line above '
          f'a table ({_sm_right}), then crosses ({_sm_where()})',
          _sm_right == (('1.5', '1.7'), '1.7')
          and _sm_where() == (('1.5', '5.0'), '5.0'))
    # The mouse has no second press: a drag that ends on a table stops at
    # the edge it came from.
    _sm_fresh('1.0')
    app.body_text.tag_add('sel', '1.0', '2.0')
    app.body_text.mark_set('insert', '2.0')
    _qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
    app.update()
    check(f'selection x table: a drag ending on a table stops at its edge '
          f'({_sm_where()}; a crossing armed: '
          f'{app._sel_held_at_table is not None})',
          _sm_where() == (('1.0', '1.7'), '1.7')
          and app._sel_held_at_table is None)
    # Cells pasted over the line Shift+Down selected take its place; the old
    # table stands, one Ctrl+Z gives the line back and one Ctrl+Y the paste.
    _sm_fresh('1.0')
    _sm_press('<Shift-KeyPress-Down>')
    _sm_press('<Control-KeyPress-v>')
    _sm_pasted = app.body_text.get('1.0', 'end-1c')
    _uf_key('<Control-z>')
    _sm_undone = app.body_text.get('1.0', 'end-1c')
    _uf_key('<Control-y>')
    check(f'selection x table: cells pasted over the line Shift+Down selected '
          f'stand above the old table, which is kept whole, and one Ctrl+Z / '
          f'one Ctrl+Y undo and redo the paste ({_sm_pasted!r})',
          _sm_pasted.startswith('| Day') and _sm_table_kept() is True
          and _sm_undone == _sm_body
          and app.body_text.get('1.0', 'end-1c') == _sm_pasted)
    # A whole line replaced by cells: the first Ctrl+Z took back only the
    # padding the tidy gave the new table at the key's release.
    _sm_fresh('1.0', 'one line' + chr(10) + 'two line' + chr(10) + 'three')
    _sm_press('<Shift-KeyPress-End>')
    _sm_press('<Control-KeyPress-v>')
    _sm_pasted = app.body_text.get('1.0', 'end-1c')
    _uf_key('<Control-z>')
    check(f'selection x table: cells pasted over a whole line are one Ctrl+Z '
          f'({app.body_text.get("1.0", "end-1c")!r})',
          _sm_pasted.startswith('| Day')
          and app.body_text.get('1.0', 'end-1c')
          == 'one line' + chr(10) + 'two line' + chr(10) + 'three')
    # Ctrl+A in a note that starts with a table: the paste read the first
    # selected line, a table row, as "inside a table" and left the cells to
    # Tk as raw tabs.
    _sm_fresh('end-1c', '| Item | Qty |' + chr(10) + '| --- | --- |' + chr(10)
              + '| Tea | 2 |' + chr(10) + 'notes after the table')
    take_focus(app.body_text)
    app.body_text.event_generate('<<SelectAll>>')
    app.update()
    _sm_press('<Control-KeyPress-v>')
    _sm_text = app.body_text.get('1.0', 'end-1c')
    check(f'selection x table: Ctrl+A then cells pasted, in a note that starts '
          f'with a table, give a drawn table ({_sm_text!r})',
          chr(9) not in _sm_text and _sm_text.startswith('| Day')
          and app._grid_at_line(1) is not None)
    # Two drawn tables a line apart. Leaving the first draws the second
    # again, and its window, put back at the very index the selection ends
    # on, pushed the caret one column on: the guard missed an exact match,
    # and the third Shift+Down left the selection holding the second
    # table's line break, with the caret under that table.
    _sm_two = ('top' + chr(10) + '| Item | Qty |' + chr(10) + '| --- | --- |'
               + chr(10) + '| Tea | 2 |' + chr(10) + 'mid' + chr(10)
               + '| Day | Time |' + chr(10) + '| --- | --- |' + chr(10)
               + '| Mon | 10 |' + chr(10) + 'end')
    _sm_fresh('1.0', _sm_two)
    for _sm_i in range(3):
        _sm_press('<Shift-KeyPress-Down>')
    check(f'selection x table: with two tables a line apart, the third '
          f'Shift+Down stops at the second table\'s edge ({_sm_where()})',
          _sm_where() == (('1.0', '5.3'), '5.3'))
    # A table on the note's first line: an upward crossing leaves the caret
    # on it, and the next key's guard read that as a first press, dropping
    # the table out of the selection -- a letter kept it, Delete took it.
    _sm_fresh('4.3', '| Item | Qty |' + chr(10) + '| --- | --- |' + chr(10)
              + '| Tea | 2 |' + chr(10) + 'after' + chr(10) + 'more')
    _sm_press('<Shift-KeyPress-Up>')
    _sm_press('<Shift-KeyPress-Up>')
    _sm_crossed = _sm_where()
    _sm_press('<KeyPress-x>')
    check(f'selection x table: a first-line table crossed with Shift+Up stays '
          f'in what the next key acts on ({_sm_crossed}; '
          f'{app.body_text.get("1.0", "end-1c")!r})',
          _sm_crossed == (('1.0', '4.3'), '1.0')
          and app.body_text.get('1.0', 'end-1c') == 'xer' + chr(10) + 'more')
    # Table rows pasted as text onto the line above a table, or the empty
    # line between, joined it: its header read as a data row. Every paste
    # route leaves a blank line now -- Ctrl+V's own, over the line Shift+Down
    # selected too, Ctrl+Shift+V, and a rich paste from another program.
    _sm_rows = '| Day | Time |' + chr(10) + '| --- | --- |' + chr(10) + '| Mon | 10 |'
    _sm_kept = []
    for _sm_how in ('caret', 'selected', 'plain', 'rich'):
        _sm_fresh('1.7')
        if _sm_how == 'selected':
            app.body_text.mark_set('insert', '1.0')
            _sm_press('<Shift-KeyPress-Down>')
        _sm_clip['data'] = _sm_rows
        if _sm_how == 'plain':
            app._paste_plain()
            app.update()
        elif _sm_how == 'rich':
            NO.clipboard.read_html = lambda: (
                '<table><tr><th>Day</th><th>Time</th></tr>'
                '<tr><td>Mon</td><td>10</td></tr></table>')
            try:
                app._on_body_paste()
                app.update()
            finally:
                NO.clipboard.read_html = lambda: None
        else:
            _sm_press('<Control-KeyPress-v>')
        _sm_kept.append((_sm_how, _sm_table_kept()))
    _sm_clip['data'] = _sm_tsv
    check(f'selection x table: table rows pasted onto the line above a table '
          f'stay a table of their own, by every route ({_sm_kept})',
          all(_k for _h, _k in _sm_kept))
    # ...and on lines of their own: after a caption, Ctrl+Shift+V and a
    # table from another program glued the first row onto the caption's
    # line, where it stopped being a row.
    _sm_own = []
    for _sm_how in ('plain', 'rich'):
        _sm_fresh('1.7', 'Prices:' + chr(10) + 'after' + chr(10) + 'more')
        _sm_clip['data'] = _sm_rows
        if _sm_how == 'plain':
            app._paste_plain()
            app.update()
        else:
            NO.clipboard.read_html = lambda: (
                '<table><tr><th>Day</th><th>Time</th></tr>'
                '<tr><td>Mon</td><td>10</td></tr></table>')
            try:
                app._on_body_paste()
                app.update()
            finally:
                NO.clipboard.read_html = lambda: None
        _sm_lines = app.body_text.get('1.0', 'end-1c').split(chr(10))
        _sm_own.append((_sm_how, _sm_lines[0],
                        core_tables.is_table_row(_sm_lines[1])))
    _sm_clip['data'] = _sm_tsv
    check(f'selection x table: rows pasted after a caption start a line of '
          f'their own, by Ctrl+Shift+V and from another program ({_sm_own})',
          all(_first == 'Prices:' and _row for _h, _first, _row in _sm_own))
    # A paste with no selection, in a note that already holds a drawn
    # table: the drawing at the end of the paste's unit split it, and the
    # first Ctrl+Z took back only where the windows sat -- nothing on screen.
    _sm_under = ('Prices:' + chr(10) + '| Item | Qty |' + chr(10)
                 + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
                 + chr(10) + 'more')
    _sm_undone = []
    for _sm_what in (_sm_rows, _sm_tsv, 'rich'):
        _sm_fresh('5.0', _sm_under)
        if _sm_what == 'rich':
            # A table: prose under a table moves no grid, so the drawing
            # leaves nothing to split the unit on.
            NO.clipboard.read_html = lambda: (
                '<table><tr><th>Day</th><th>Time</th></tr>'
                '<tr><td>Mon</td><td>10</td></tr></table>')
            try:
                app._on_body_paste()
                app.update()
            finally:
                NO.clipboard.read_html = lambda: None
        else:
            _sm_clip['data'] = _sm_what
            _sm_press('<Control-KeyPress-v>')
        _sm_pasted = app.body_text.get('1.0', 'end-1c')
        _uf_key('<Control-z>')
        _sm_undone.append((_sm_pasted != _sm_under,
                           app.body_text.get('1.0', 'end-1c') == _sm_under))
    _sm_clip['data'] = _sm_tsv
    check(f'selection x table: rows, cells or rich text pasted under a drawn '
          f'table are one Ctrl+Z ({_sm_undone})',
          _sm_undone == [(True, True), (True, True), (True, True)])
    # After a first Shift+Down stopped at the table's edge: its release had
    # noted the table's line Tk moved the caret to, and the next key's
    # release "left" that table and padded it -- outside that key's undo
    # unit, so a letter, a Delete or a paste over the selection took two
    # Ctrl+Z, the first changing nothing on screen.
    _sm_edge = []
    for _sm_what in ('letter', 'delete', _sm_rows, 'just words', 'plain'):
        _sm_fresh('1.0')
        _sm_press('<Shift-KeyPress-Down>')
        _sm_sel = _sm_where()[0]
        if _sm_what == 'letter':
            _sm_typed = _ty_key('Z', 'Z')
        elif _sm_what == 'delete':
            _sm_typed = _own_key('<Delete>', '<KeyRelease-Delete>')
        elif _sm_what == 'plain':
            # Ctrl+Shift+V, the paste without its styling.
            _sm_clip['data'] = _sm_rows
            _sm_typed = _sm_press('<Control-Shift-KeyPress-V>')
        else:
            _sm_clip['data'] = _sm_what
            _sm_typed = _sm_press('<Control-KeyPress-v>')
        _sm_done = app.body_text.get('1.0', 'end-1c')
        _uf_key('<Control-z>')
        _sm_edge.append((_sm_sel, _sm_typed, _sm_done != _sm_body,
                         app.body_text.get('1.0', 'end-1c') == _sm_body))
    _sm_clip['data'] = _sm_tsv
    check(f'selection x table: after a first Shift+Down stops at a table, a '
          f'letter, a Delete or a paste over the selection is one Ctrl+Z '
          f'({_sm_edge})',
          all(_s == ('1.0', '1.7') and _t and _c and _u
              for _s, _t, _c, _u in _sm_edge))
    # A paste pressed as a person presses it -- Ctrl or Shift first, a key
    # that may type -- never wears the word's style: Ctrl+V and Shift+Insert
    # are <<Paste>> in the bindtag that notes every key, and a virtual event
    # outranks <KeyPress> there, so their press went unnoted and the paste
    # landed in the run Ctrl had opened. Nor does Tk's own Ctrl+O, which
    # puts a line break where the caret stands and stays before it.
    _sm_keys = []
    for _sm_name, _sm_do in (
            ('Ctrl+V', lambda: _own_key('<Control-KeyPress-v>',
                                        '<Control-KeyRelease-v>',
                                        ('Control_L',))),
            ('Shift+Insert', lambda: _own_key('<Shift-KeyPress-Insert>',
                                              '<Shift-KeyRelease-Insert>',
                                              ('Shift_L',))),
            ('Ctrl+O', lambda: _own_key('<Control-KeyPress-o>',
                                        '<Control-KeyRelease-o>',
                                        ('Control_L',)))):
        _sm_fresh('1.6' if _sm_name != 'Ctrl+O' else '1.7',
                  'Prices: here' + chr(10) + 'second line')
        app.body_text.tag_add('bold', '1.0', '1.6')
        _sm_clip['data'] = '!'
        _sm_ok = _sm_do()
        _sm_keys.append((_sm_name, _sm_ok, app.body_text.get('1.0', '1.end'),
                         [str(i) for i in app.body_text.tag_ranges('bold')]))
    _sm_clip['data'] = _sm_tsv
    check(f'a paste pressed after its Ctrl or Shift, and Ctrl+O, spread no '
          f'style ({_sm_keys})',
          [(_n, _ok, _r) for _n, _ok, _t, _r in _sm_keys]
          == [('Ctrl+V', True, ['1.0', '1.6']),
              ('Shift+Insert', True, ['1.0', '1.6']),
              ('Ctrl+O', True, ['1.0', '1.6'])]
          and _sm_keys[0][2] == 'Prices!: here')
    # A table typed by hand, left by a paste: the paste's release no longer
    # reads as leaving a table, so the table was drawn and never tidied --
    # its saved pipe text ragged. The paste tidies it, in its own undo unit.
    _sm_raw = ('Intro' + chr(10) + '| Item name | Qty |' + chr(10)
               + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
               + 'end line')
    set_body(_sm_raw)
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '4.end')
    app._last_caret_line = None
    _sm_clip['data'] = chr(10) + 'After the table'
    _sm_ok = _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>',
                      ('Control_L',))
    _sm_rows4 = app.body_text.get('1.0', 'end-1c').split(chr(10))
    _sm_tidy = (_sm_ok and _sm_rows4[4] == 'After the table'
                and len({len(r) for r in _sm_rows4[1:4]}) == 1)
    _uf_key('<Control-z>')
    _sm_back = app.body_text.get('1.0', 'end-1c') == _sm_raw
    # A paste that leaves the caret on its own line is a letter typed there:
    # the table is tidied when the caret leaves that line, not by the paste.
    set_body(_sm_raw)
    app._reset_text_undo()
    app.body_text.mark_set('insert', '4.end')
    app._last_caret_line = None
    _sm_clip['data'] = '!'
    _sm_ok2 = _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>',
                       ('Control_L',))
    _sm_stay = app.body_text.get('2.0', '2.end')
    _sm_clip['data'] = _sm_tsv
    check(f'a table being typed that a paste leaves is tidied, and one Ctrl+Z '
          f'takes the paste back; a paste that stays on its line leaves it '
          f'for the caret to leave ({_sm_rows4[1:5]}; {_sm_stay!r})',
          _sm_tidy and _sm_back and _sm_ok2
          and _sm_stay == '| Item name | Qty |')
    # Ctrl+Z and Ctrl+Y after a table typed by hand is left: its rows were
    # typed with no window on its first line, and replayed with the drawn
    # grid's window there they landed a column off -- the header lost a
    # letter ("| Item name | Qy  |"), and Ctrl+Y lost more.
    set_body('Intro' + chr(10) + '| Item name | Qt |' + chr(10)
             + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
             + 'end line')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '2.16')
    app._last_caret_line = None
    _sm_start = app.body_text.get('1.0', 'end-1c')
    _sm_ok = _ty_key('y', 'y')
    _sm_typed = app.body_text.get('1.0', 'end-1c')
    for _ in range(3):
        _sm_ok = _sm_press('<KeyPress-Down>') and _sm_ok
    _sm_left = app.body_text.get('1.0', 'end-1c')
    _sm_walk = []
    for _sm_k in ('<Control-z>', '<Control-z>', '<Control-y>', '<Control-y>'):
        _uf_key(_sm_k)
        _sm_walk.append(app.body_text.get('1.0', 'end-1c'))
    check(f'a table typed by hand and left walks back and forth exactly on '
          f'Ctrl+Z and Ctrl+Y ({[w.split(chr(10))[1] for w in _sm_walk]})',
          _sm_ok and _sm_left != _sm_typed
          and _sm_walk == [_sm_typed, _sm_start, _sm_typed, _sm_left])
    # A paste on the first line of a table not yet drawn, in a note with no
    # drawn table: the paste's unit drew the table at its end and was
    # replayed with that window in place -- Ctrl+Z lost letters of the
    # header, Ctrl+Y doubled one. A unit with no table drawn when it begins
    # is replayed with the tables down.
    set_body('Intro' + chr(10) + '| Item name | Qty |' + chr(10)
             + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
             + 'end line')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '2.6')
    _hp_start = app.body_text.get('2.0', '2.end')
    _sm_clip['data'] = 'XY'
    _hp_ok = _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>',
                      ('Control_L',))
    _hp_pasted = app.body_text.get('2.0', '2.end')
    _uf_key('<Control-z>')
    _hp_back = app.body_text.get('2.0', '2.end')
    _uf_key('<Control-y>')
    _hp_fwd = app.body_text.get('2.0', '2.end')
    _sm_clip['data'] = _sm_tsv
    check(f'a paste on the first line of a table not yet drawn walks back and '
          f'forth exactly ({_hp_pasted!r}; {_hp_back!r}; {_hp_fwd!r})',
          _hp_ok and _hp_pasted == '| ItemXY name | Qty |'
          and _hp_back == _hp_start and _hp_fwd == _hp_pasted)
    # Past the formatting journal's reach a unit's step stays as a stub, so
    # Ctrl+Z still knows how it was recorded: dropped, a header cell written
    # with the grid drawn read as typing, was replayed with the grids down,
    # and came back a column off ("| Names| Qty |"); Ctrl+Y doubled a letter.
    # The reach is made short here, as an instance attribute, so a few cell
    # edits carry the header's step past it.
    set_body('Intro' + chr(10) + '| Name | Qty |' + chr(10) + '| --- | --- |'
             + chr(10) + '| Tea | 2 |' + chr(10) + chr(10) + 'end line')
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    _jt_start = app.body_text.get('1.0', 'end-1c')
    app._FMT_JOURNAL_DEPTH = 3
    try:
        for _jt_r, _jt_v in ((0, 'Names'), (1, 'Tea0'), (1, 'Tea1'),
                             (1, 'Tea2'), (1, 'Tea3'), (1, 'Tea4')):
            app._open_cell_editor(app._grid_at_line(2), _jt_r, 0)
            app.update()
            _jt_ed = app._cell_editor['entry']
            _jt_ed.delete('1.0', 'end')
            _jt_ed.insert('1.0', _jt_v)
            app._commit_cell_editor()
            app.update()
        _jt_end = app.body_text.get('1.0', 'end-1c')
        _jt_stubs = sum(1 for _s in app._fmt_undo if _s.get('stub'))
        for _ in range(6):
            _uf_key('<Control-z>')
        _jt_back = app.body_text.get('1.0', 'end-1c')
        for _ in range(6):
            _uf_key('<Control-y>')
        _jt_fwd = app.body_text.get('1.0', 'end-1c')
    finally:
        del app._FMT_JOURNAL_DEPTH
    check(f'past the journal\'s reach, Ctrl+Z and Ctrl+Y walk a header cell '
          f'edit back and forth exactly ({_jt_stubs} stubs; '
          f'{_jt_back.split(chr(10))[1]!r}; {_jt_fwd.split(chr(10))[1]!r})',
          _jt_stubs > 0 and _jt_back == _jt_start and _jt_fwd == _jt_end)
    # A unit that begins with no table drawn is replayed with the tables
    # down; one that goes on to write into a table it drew has the window in
    # place for that write, and is split there (_note_edit_with_window).
    # Driven through the unit's own calls: no route of the app's does this
    # yet, and the next one must not land a column off.
    set_body('Intro' + chr(10) + 'end line')
    app._reset_text_undo()
    _sp_start = app.body_text.get('1.0', 'end-1c')
    app._undo_atom_begin()
    try:
        app.body_text.insert('2.0', '| Name | Qty |' + chr(10) + '| --- | --- |'
                             + chr(10) + '| Tea | 2 |' + chr(10))
        app._render_table_grids()
        app._write_cell(app._grid_at_line(2), 0, 0, 'Names')
    finally:
        app._undo_atom_end()
    app.update()
    _sp_end = app.body_text.get('1.0', 'end-1c')
    for _ in range(2):
        _uf_key('<Control-z>')
    _sp_back = app.body_text.get('1.0', 'end-1c')
    for _ in range(2):
        _uf_key('<Control-y>')
    _sp_fwd = app.body_text.get('1.0', 'end-1c')
    check(f'a unit that writes into a table it drew walks back and forth '
          f'exactly ({_sp_back.split(chr(10))[:2]}; '
          f'{_sp_fwd.split(chr(10))[1:2]})',
          'Names' in _sp_end and _sp_back == _sp_start and _sp_fwd == _sp_end)
    # A run of Tk's own deletes of styled text is noted by the app, and like
    # every step of Tk's it never touches a drawn table's line: it is
    # replayed with the tables down. Unmarked, a bold letter BackSpaced in
    # the header of a table typed by hand came back a column off once the
    # table was drawn.
    set_body('Intro' + chr(10) + '| Item name | Qty |' + chr(10)
             + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
             + 'end line')
    app.body_text.tag_add('bold', '2.14', '2.17')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '2.17')
    app._last_caret_line = None
    _sd_start = app.body_text.get('1.0', 'end-1c')
    _sd_ok = _own_key('<BackSpace>', '<KeyRelease-BackSpace>')
    _sd_deleted = app.body_text.get('2.0', '2.end')
    for _ in range(3):
        _sd_ok = _sm_press('<KeyPress-Down>') and _sd_ok
    _sd_drawn = app._grid_at_line(2) is not None
    for _ in range(2):
        _uf_key('<Control-z>')
    _sd_back = app.body_text.get('1.0', 'end-1c')
    check(f'a bold letter BackSpaced in a table typed by hand comes back '
          f'exactly once the table is drawn ({_sd_deleted!r}; '
          f'{_sd_back.split(chr(10))[1]!r})',
          _sd_ok and _sd_drawn and _sd_deleted == '| Item name | Qt |'
          and _sd_back == _sd_start)
    # ...and once cell edits carry that step past the journal's reach, its
    # stub still says how it was recorded. One that forgot replayed the
    # delete with the drawn table's window in place, a column off.
    set_body('Intro' + chr(10) + '| Item name | Qty |' + chr(10)
             + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
             + 'end line')
    app.body_text.tag_add('bold', '2.14', '2.17')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '2.17')
    app._last_caret_line = None
    _ss_start = app.body_text.get('1.0', 'end-1c')
    _ss_stubs = []
    _ss_end = _ss_back = _ss_fwd = ''
    app._FMT_JOURNAL_DEPTH = 3
    try:
        _ss_ok = _own_key('<BackSpace>', '<KeyRelease-BackSpace>')
        for _ in range(3):
            _ss_ok = _sm_press('<KeyPress-Down>') and _ss_ok
        _ss_ok = _ss_ok and app._grid_at_line(2) is not None
        if _ss_ok:
            for _ss_v in ('Tea0', 'Tea1', 'Tea2', 'Tea3'):
                app._open_cell_editor(app._grid_at_line(2), 1, 0)
                app.update()
                _ss_ed = app._cell_editor['entry']
                _ss_ed.delete('1.0', 'end')
                _ss_ed.insert('1.0', _ss_v)
                app._commit_cell_editor()
                app.update()
            _ss_end = app.body_text.get('1.0', 'end-1c')
            _ss_stubs = [bool(_s.get('grids_down')) for _s in app._fmt_undo
                         if _s.get('stub')]
            for _ in range(6):
                _uf_key('<Control-z>')
            _ss_back = app.body_text.get('1.0', 'end-1c')
            for _ in range(6):
                _uf_key('<Control-y>')
            _ss_fwd = app.body_text.get('1.0', 'end-1c')
    finally:
        del app._FMT_JOURNAL_DEPTH
    check(f'...and so does it once cell edits carry it past the journal\'s '
          f'reach ({_ss_stubs}; {_ss_back.split(chr(10))[1:2]}; '
          f'{_ss_fwd.split(chr(10))[1:2]})',
          _ss_ok and True in _ss_stubs and 'Tea3' in _ss_end
          and _ss_back == _ss_start and _ss_fwd == _ss_end)
    # A style change made after Ctrl+Z puts nothing on Tk's stack, so Tk can
    # still redo what was undone before it, and the journal keeps how each
    # of those steps was recorded. Emptied, Ctrl+Y read a header cell's
    # edit as typing and put it back a column off ("| Name s   |").
    _rf = []
    for _rf_style in ('word', 'cell'):
        set_body('Intro word here' + chr(10) + '| Name | Qty |' + chr(10)
                 + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10)
                 + chr(10) + 'end line')
        app._render_table_grids()
        app.update()
        app._reset_text_undo()
        app._open_cell_editor(app._grid_at_line(2), 0, 0)
        app.update()
        _rf_ed = app._cell_editor['entry']
        _rf_ed.delete('1.0', 'end')
        _rf_ed.insert('1.0', 'Names')
        app._commit_cell_editor()
        app.update()
        _rf_edited = app.body_text.get('2.0', '2.end')
        _uf_key('<Control-z>')
        _rf_undone = app.body_text.get('2.0', '2.end')
        if _rf_style == 'word':
            app.body_text.tag_add('sel', '1.6', '1.10')
            app.body_text.mark_set('insert', '1.10')
            _own_key('<Control-b>', '<Control-KeyRelease-b>', ('Control_L',))
            app.body_text.tag_remove('sel', '1.0', 'end')
        else:
            app._grid_apply_style(app._grid_at_line(2), (1, 1, 1, 1), 'bold')
            app.update()
        _uf_key('<Control-y>')
        _rf.append((_rf_style, _rf_undone == _rf_edited,
                    app.body_text.get('2.0', '2.end') == _rf_edited,
                    app.body_text.get('2.0', '2.end')))
    check(f'Ctrl+Y after a style change gives a header cell edit back exactly '
          f'({_rf})',
          [(s, u, r) for s, u, r, _t in _rf] == [('word', False, True),
                                                 ('cell', False, True)])
    # Tk's own Insert pastes the selection over itself -- the same words,
    # bare -- and a paste of the very words it replaces does the same: a
    # change of style alone, which Ctrl+Z dropped, leaving them plain. On
    # X11 Tk's paste inserts at the caret and leaves the selection where it
    # is (the date field's paste check says the same), so there the paste
    # replaces nothing and Ctrl+Z has only the note to give back; Insert,
    # which deletes the selection the caret is in everywhere, still covers
    # both halves of the fix there.
    _in_x11 = str(app.tk.call('tk', 'windowingsystem')) == 'x11'
    _in = []
    for _in_name, _in_do in (
            ('Insert', lambda: _own_key('<KeyPress-Insert>',
                                        '<KeyRelease-Insert>')),
            ('Shift+Insert', lambda: _own_key('<Shift-KeyPress-Insert>',
                                              '<Shift-KeyRelease-Insert>',
                                              ('Shift_L',)))):
        set_body('Prices: here' + chr(10) + 'second line')
        app.body_text.tag_add('bold', '1.0', '1.6')
        app._reset_text_undo()
        app.body_text.tag_add('sel', '1.0', '1.6')
        app.body_text.mark_set('insert', '1.6')
        _sm_clip['data'] = 'Prices'
        _in_ok = _in_do()
        _in_plain = not app.body_text.tag_ranges('bold') or (
            _in_x11 and _in_name == 'Shift+Insert')
        app.body_text.tag_remove('sel', '1.0', 'end')
        _uf_key('<Control-z>')
        _in.append((_in_name, _in_ok and _in_plain,
                    [str(i) for i in app.body_text.tag_ranges('bold')],
                    app.body_text.get('1.0', '1.end')))
    _sm_clip['data'] = _sm_tsv
    check(f'Ctrl+Z gives a styled selection its style back after Insert, or a '
          f'paste of the same words ({_in})',
          _in == [('Insert', True, ['1.0', '1.6'], 'Prices: here'),
                  ('Shift+Insert', True, ['1.0', '1.6'], 'Prices: here')])
    # A word pasted into a table row still being typed: the row stays a row
    # being typed, the caret after the word, as after a letter typed there.
    # The paste drew it, the caret guard put the caret under the table, and
    # the next letter went to the line below -- by every paste route.
    _pr = []
    _pr_keys = {' ': 'space', '|': 'bar', '-': 'minus'}
    for _pr_route in ('Ctrl+V', 'Ctrl+Shift+V', 'menu', 'rich'):
        set_body('Intro' + chr(10) + chr(10) + 'end line')
        app._reset_text_undo()
        app.body_text.mark_set('insert', '2.0')
        app._last_caret_line = None
        for _pr_ch in '| Item name | Qty |':
            _ty_key(_pr_keys.get(_pr_ch, _pr_ch), _pr_ch)
        for _ in range(13):
            _sm_press('<KeyPress-Left>')
        _sm_clip['data'] = 'XY'
        if _pr_route in ('Ctrl+V', 'rich'):
            # The rich route: the word as a web page puts it on the
            # clipboard, HTML beside the text.
            if _pr_route == 'rich':
                NO.clipboard.read_html = lambda: '<span>XY</span>'
            try:
                _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>',
                         ('Control_L',))
            finally:
                NO.clipboard.read_html = lambda: None
        elif _pr_route == 'Ctrl+Shift+V':
            _own_key('<Control-Shift-KeyPress-V>',
                     '<Control-Shift-KeyRelease-V>',
                     ('Control_L', 'Shift_L'))
        else:
            take_focus(app.body_text)
            app.body_text.event_generate('<<Paste>>')
            app.update()
        app.update()
        _pr_drawn = app._grid_at_line(2) is not None
        _ty_key('Z', 'Z')
        _pr.append((_pr_route, _pr_drawn, app.body_text.get('2.0', '2.end')))
    _sm_clip['data'] = _sm_tsv
    check(f'a word pasted into a table row being typed stays in it, and the '
          f'next letter follows it ({_pr})',
          all(not d and t == '| ItemXYZ name | Qty |' for _r, d, t in _pr))
    # ...and Ctrl+Shift+V there, with another table drawn, walks back and
    # forth exactly: its unit was recorded with the tables up, and once the
    # typed table was drawn Ctrl+Z took letters out of its header.
    set_body('Intro' + chr(10) + '| A | B |' + chr(10) + '| --- | --- |'
             + chr(10) + '| 1 | 2 |' + chr(10) + chr(10) + chr(10)
             + 'end line')
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '6.0')
    app._last_caret_line = None
    _wp_heads = {''}
    _wp_start = app.body_text.get('1.0', 'end-1c')
    for _wp_ch in '| Item name | Qty |':
        _ty_key(_pr_keys.get(_wp_ch, _wp_ch), _wp_ch)
    _wp_heads.add(app.body_text.get('6.0', '6.end'))
    for _ in range(13):
        _sm_press('<KeyPress-Left>')
    _sm_clip['data'] = 'XY'
    _own_key('<Control-Shift-KeyPress-V>', '<Control-Shift-KeyRelease-V>',
             ('Control_L', 'Shift_L'))
    _sm_clip['data'] = _sm_tsv
    _wp_heads.add(app.body_text.get('6.0', '6.end'))
    _sm_press('<KeyPress-End>')
    for _wp_line in ('| --- | --- |', '| Tea | 2 |'):
        _ty_key('Return', chr(10))
        for _wp_ch in _wp_line:
            _ty_key(_pr_keys.get(_wp_ch, _wp_ch), _wp_ch)
        _wp_heads.add(app.body_text.get('6.0', '6.end'))
    for _ in range(2):
        _sm_press('<KeyPress-Down>')
    _wp_heads.add(app.body_text.get('6.0', '6.end'))
    _wp_end = app.body_text.get('1.0', 'end-1c')
    _wp_drawn = app._grid_at_line(6) is not None
    _wp_seen = []
    for _ in range(12):
        _uf_key('<Control-z>')
        _wp_seen.append(app.body_text.get('6.0', '6.end'))
    _wp_back = app.body_text.get('1.0', 'end-1c')
    for _ in range(12):
        _uf_key('<Control-y>')
        _wp_seen.append(app.body_text.get('6.0', '6.end'))
    _wp_fwd = app.body_text.get('1.0', 'end-1c')
    _wp_odd = sorted({h for h in _wp_seen if h not in _wp_heads})
    check(f'Ctrl+Shift+V into a table being typed beside a drawn one walks '
          f'back and forth exactly (headers no step had: {_wp_odd})',
          _wp_drawn and 'ItemXY' in _wp_end and not _wp_odd
          and _wp_back == _wp_start and _wp_fwd == _wp_end)
    # ...and into a later row of a table typed by hand: its header was drawn
    # as the caret left it, the row being typed sits under the grid, and the
    # paste drew it too -- the next letter went under the table.
    _lr = []
    for _lr_route in ('Ctrl+V', 'menu'):
        set_body('Intro' + chr(10) + chr(10) + chr(10) + 'end line')
        app._reset_text_undo()
        app.body_text.mark_set('insert', '2.0')
        app._last_caret_line = None
        for _lr_line in ('| Item name | Qty |', '| --- | --- |'):
            for _lr_ch in _lr_line:
                _ty_key(_pr_keys.get(_lr_ch, _lr_ch), _lr_ch)
            _ty_key('Return', chr(10))
        for _lr_ch in '| Tea | 2 |':
            _ty_key(_pr_keys.get(_lr_ch, _lr_ch), _lr_ch)
        for _ in range(3):
            _sm_press('<KeyPress-Left>')
        _lr_header = app._grid_at_line(2) is not None
        _sm_clip['data'] = 'XY'
        if _lr_route == 'Ctrl+V':
            _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>',
                     ('Control_L',))
        else:
            take_focus(app.body_text)
            app.body_text.event_generate('<<Paste>>')
            app.update()
        app.update()
        _ty_key('Z', 'Z')
        _lr.append((_lr_route, _lr_header, app.body_text.get('4.0', '4.end'),
                    app._grid_at_line(2) is not None
                    and app._grid_at_line(4) is None))
    # ...or a row typed straight above a drawn table, which joins it: the
    # table under the row is drawn as it was.
    set_body('Intro' + chr(10) + chr(10) + '| Item | Qty |' + chr(10)
             + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10) + chr(10)
             + 'end line')
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    app.body_text.mark_set('insert', '2.0')
    app._last_caret_line = None
    for _lr_ch in '| New | Row |':
        _ty_key(_pr_keys.get(_lr_ch, _lr_ch), _lr_ch)
    for _ in range(3):
        _sm_press('<KeyPress-Left>')
    _sm_clip['data'] = 'XY'
    _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>', ('Control_L',))
    app.update()
    _ty_key('Z', 'Z')
    _lr.append(('above', app._grid_at_line(3) is not None,
                app.body_text.get('2.0', '2.end'),
                app._grid_at_line(2) is None))
    _sm_clip['data'] = _sm_tsv
    check(f'...and into a later row of one, under its drawn header, or a row '
          f'typed above one ({_lr})',
          [(r, h, t, d) for r, h, t, d in _lr]
          == [('Ctrl+V', True, '| Tea | XYZ2 |', True),
              ('menu', True, '| Tea | XYZ2 |', True),
              ('above', True, '| New | RoXYZw |', True)])
    # A paste from the menu has no key whose release names the row it
    # leaves the caret on: leaving that row by an arrow or the mouse found
    # no row left, and the table stayed raw and untidied, saved so.
    _ml = []
    for _ml_route in ('Paste', 'Paste without formatting'):
        set_body('Intro' + chr(10) + chr(10) + 'end line')
        app._reset_text_undo()
        app.body_text.mark_set('insert', '2.0')
        app._last_caret_line = None
        for _ml_ch in '| Item name | Qty |':
            _ty_key(_pr_keys.get(_ml_ch, _ml_ch), _ml_ch)
        for _ in range(13):
            _sm_press('<KeyPress-Left>')
        _sm_clip['data'] = 'XY'
        take_focus(app.body_text)
        if _ml_route == 'Paste':
            app.body_text.event_generate('<<Paste>>')
        else:
            app._paste_plain()
        app.update()
        _sm_clip['data'] = _sm_tsv
        _sm_press('<KeyPress-Down>')
        _ml.append((_ml_route, app._grid_at_line(2) is not None,
                    app.body_text.get('2.0', '2.end')))
    check(f'leaving a row a menu paste kept draws and tidies its table '
          f'({_ml})',
          all(d and r == '| ItemXY name | Qty      |' for _n, d, r in _ml))
    # A table at the very end of a note gets a line under it from the
    # drawing, which Tk never records. Ctrl+Z back past the Enter that made
    # the person's own line there, then Ctrl+Y, doubled that line, and from
    # then on a header cell's edit replayed a column off ("| Name s   |").
    set_body('Intro line')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '1.end')
    app._last_caret_line = None
    _ty_key('Return', chr(10))
    for _te_line in ('| Name | Qty |', '| --- | --- |', '| Tea | 2 |'):
        for _te_ch in _te_line:
            _ty_key(_pr_keys.get(_te_ch, _te_ch), _te_ch)
        if _te_line.startswith('| Tea'):
            # The caret moved before the last Enter, as a person's End
            # moves it: that Enter is a step of its own on Tk's stack.
            _sm_press('<KeyPress-End>')
        _ty_key('Return', chr(10))
    app.update()
    _te_ok = app._grid_at_line(2) is not None
    if _te_ok:
        app._open_cell_editor(app._grid_at_line(2), 0, 0)
        app.update()
        _te_ed = app._cell_editor['entry']
        _te_ed.delete('1.0', 'end')
        _te_ed.insert('1.0', 'Names')
        app._commit_cell_editor()
        app.update()
    _te_edited = app.body_text.get('1.0', 'end-1c')
    for _te_k in 'zzzyyy':
        _own_key('<Control-KeyPress-%s>' % _te_k,
                 '<Control-KeyRelease-%s>' % _te_k, ('Control_L',))
    _te_after = app.body_text.get('1.0', 'end-1c')
    check(f'Ctrl+Z and Ctrl+Y past the line under a table at a note\'s end '
          f'give its header back exactly ({_te_after.split(chr(10))[1:2]}; '
          f'{_te_after.count(chr(10))} vs {_te_edited.count(chr(10))} lines)',
          _te_ok and 'Names' in _te_edited and _te_after == _te_edited)
    # ...and a header cell edited while the drawing's own line stands there
    # (Ctrl+Z back past the Enter put it there): the edit was noted with the
    # text as it stood, and the journal must read it so when Ctrl+Z and
    # Ctrl+Y walk it, or the edit replays as typing, a column off.
    set_body('Intro line')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '1.end')
    app._last_caret_line = None
    _ty_key('Return', chr(10))
    for _te_line in ('| Name | Qty |', '| --- | --- |', '| Tea | 2 |'):
        for _te_ch in _te_line:
            _ty_key(_pr_keys.get(_te_ch, _te_ch), _te_ch)
        if _te_line.startswith('| Tea'):
            _sm_press('<KeyPress-End>')
        _ty_key('Return', chr(10))
    app.update()
    for _te_k in 'zz':
        _own_key('<Control-KeyPress-%s>' % _te_k,
                 '<Control-KeyRelease-%s>' % _te_k, ('Control_L',))
    _tb_tail = (getattr(app, '_undo_tail', None) is not None
                and app._grid_at_line(2) is not None)
    if _tb_tail:
        app._open_cell_editor(app._grid_at_line(2), 0, 0)
        app.update()
        _tb_ed = app._cell_editor['entry']
        _tb_ed.delete('1.0', 'end')
        _tb_ed.insert('1.0', 'Names')
        app._commit_cell_editor()
        app.update()
    _tb_edited = app.body_text.get('1.0', 'end-1c')
    for _te_k in 'zy':
        _own_key('<Control-KeyPress-%s>' % _te_k,
                 '<Control-KeyRelease-%s>' % _te_k, ('Control_L',))
    _tb_after = app.body_text.get('1.0', 'end-1c')
    check(f'...and a header cell edited beside the drawing\'s own line walks '
          f'back and forth exactly ({_tb_tail}; '
          f'{_tb_after.split(chr(10))[1:2]})',
          _tb_tail and 'Names' in _tb_edited and _tb_after == _tb_edited)

    # A table typed at a note's very end and left by the mouse: the drawing
    # puts a line of its own under it, which Tk never records.
    def _tl_click(index):
        _w = app.body_text
        _w.see(index)
        app.update()
        _bb = _w.bbox(index)
        if _bb is None or not take_focus(_w):
            return False
        _x, _y = _bb[0] + 1, _bb[1] + max(1, _bb[3] // 2)
        _qa_fire(_w, '<ButtonPress-1>', x=_x, y=_y)
        app.update()
        _qa_fire(_w, '<ButtonRelease-1>', x=_x, y=_y)
        app.update()
        return True

    def _tl_table_at_end(start='Intro line',
                         rows=('| Name | Qty |', '| --- | --- |', '| Tea | 2 |')):
        set_body(start)
        app._reset_text_undo()
        app._cancel_pending_autosave()
        app.body_text.mark_set('insert', 'end-1c')
        app._last_caret_line = None
        _ty_key('Return', chr(10))
        for _tl_i, _tl_row in enumerate(rows):
            for _tl_ch in _tl_row:
                _ty_key(_pr_keys.get(_tl_ch, _tl_ch), _tl_ch)
            if _tl_i < 2:
                _ty_key('Return', chr(10))
        _tl_click('1.3')
        return (app._grid_at_line(start.count(chr(10)) + 2) is not None
                and getattr(app, '_undo_tail', None) is not None)

    def _tl_text():
        return app.body_text.get('1.0', 'end-1c')

    def _tl_keys(keys):
        for _tl_k in keys:
            _own_key('<Control-KeyPress-%s>' % _tl_k,
                     '<Control-KeyRelease-%s>' % _tl_k, ('Control_L',))

    def _tl_on_last_line():
        app.body_text.mark_set('insert', 'end-1c')
        app._last_caret_line = int(app.body_text.index('insert').split('.')[0])

    # Written on and emptied again, that line is the note's: the text reads
    # as before, but Tk has steps on the line now. Taken out before Ctrl+Z,
    # the word Tk gave back landed on the table's last row ("| Tea | 2
    # |abc"), saved so.
    _tl_we = []
    for _tl_how in ('BackSpace', 'select and Delete'):
        _tl_ok = _tl_table_at_end()
        _tl_on_last_line()
        for _tl_ch in 'abc':
            _ty_key(_tl_ch, _tl_ch)
        if _tl_how == 'BackSpace':
            for _ in range(3):
                _own_key('<BackSpace>', '<KeyRelease-BackSpace>')
        else:
            app.body_text.tag_add('sel', 'end-1c linestart', 'end-1c')
            _own_key('<Delete>', '<KeyRelease-Delete>')
        _tl_ok = _tl_ok and _tl_text().endswith('|' + chr(10))
        _tl_keys('z')
        _tl_we.append((_tl_how, _tl_ok, _tl_text().split(chr(10))[-2:]))
    check(f'a word written under a table at a note\'s end and erased comes '
          f'back there on Ctrl+Z ({_tl_we})',
          all(ok and last[0].startswith('| Tea') and last[0].endswith('|')
              and last[1] == 'abc' for _h, ok, last in _tl_we))
    # ...and with a header cell edited before the letter: Ctrl+Z took the
    # letter back, the next skipped the cell, and Ctrl+Y doubled the edit
    # ("| Namess |"), saved so.
    _tl_ok = _tl_table_at_end()
    _tl_start = _tl_text()
    if _tl_ok:
        app._open_cell_editor(app._grid_at_line(2), 0, 0)
        app.update()
        _tl_ed = app._cell_editor['entry']
        _tl_ed.delete('1.0', 'end')
        _tl_ed.insert('1.0', 'Names')
        app._commit_cell_editor()
        app.update()
    _tl_edited = _tl_text()
    _tl_on_last_line()
    _ty_key('x', 'x')
    _tl_typed = _tl_text()
    _tl_walk = []
    for _tl_k in 'zzyy':
        _tl_keys(_tl_k)
        _tl_walk.append(_tl_text())
    check(f'...and with a header cell edited before it, Ctrl+Z and Ctrl+Y '
          f'walk the letter and the cell exactly '
          f'({[w.split(chr(10))[1] for w in _tl_walk]})',
          _tl_ok and 'Names' in _tl_edited
          and _tl_walk == [_tl_edited, _tl_start, _tl_edited, _tl_typed])
    # A cell edit that narrows its column draws the table again inside its
    # own undo step, which splits the step where the tables come down
    # (_undo_atom_grids_coming_down). That split read the step's first
    # snapshot before the line under the table was counted into it: Ctrl+Z
    # gave the cell's text back with half its bold ("Earl Grey" bold,
    # "teapot" plain), and the next Ctrl+Z skipped a step.
    _tl_ok = _tl_table_at_end(rows=('| Name | Qty |', '| --- | --- |',
                                    '| Earl Grey teapot | 2 |'))
    _tl_at = app.body_text.get('4.0', '4.end').find('Earl Grey teapot')
    _tl_ok = _tl_ok and _tl_at > 0
    app.body_text.tag_add('bold', '4.%d' % _tl_at, '4.%d' % (_tl_at + 16))
    _tl_start = _tl_text()
    if _tl_ok:
        app._open_cell_editor(app._grid_at_line(2), 1, 0)
        app.update()
        _tl_ed = app._cell_editor['entry']
        _tl_ed.delete('1.0', 'end')
        _tl_ed.insert('1.0', 'Earl Grey')
        app._commit_cell_editor()
        app.update()
    _tl_ok = _tl_ok and 'teapot' not in _tl_text()
    _tl_keys('z')
    _tl_bold = [str(i) for i in app.body_text.tag_ranges('bold')]
    app.body_text.tag_remove('bold', '1.0', 'end')
    check(f'Ctrl+Z of a cell edit that narrows its column, beside the '
          f'drawing\'s line, gives the cell back with all its bold '
          f'({_tl_ok}; {_tl_bold})',
          _tl_ok and _tl_text() == _tl_start
          and _tl_bold == ['4.%d' % _tl_at, '4.%d' % (_tl_at + 16)])
    # A list renumbered by Enter, in a note whose last table has the
    # drawing's line under it: Ctrl+Z gave the text back bare -- every bold
    # and italic in the note gone, saved so.
    _tl_ok = _tl_table_at_end('Bold words here' + chr(10) + '1. alpha'
                              + chr(10) + '2. beta' + chr(10) + 'end')
    app.body_text.tag_add('bold', '1.0', '1.4')
    app.body_text.tag_add('italic', '2.3', '2.8')
    _tl_start = _tl_text()
    app.body_text.mark_set('insert', '2.end')
    app._last_caret_line = 2
    _sm_press('<KeyPress-End>')
    _ty_key('Return', chr(10))
    _tl_ok = _tl_ok and _tl_text().split(chr(10))[2:4] == ['2. ', '3. beta']
    for _ in range(4):
        if _tl_text() == _tl_start:
            break
        _tl_keys('z')
    _tl_styles = ([str(i) for i in app.body_text.tag_ranges('bold')],
                  [str(i) for i in app.body_text.tag_ranges('italic')])
    check(f'Ctrl+Z of a list renumbered beside the drawing\'s line under a '
          f'table gives the text back with its formatting ({_tl_styles})',
          _tl_ok and _tl_text() == _tl_start
          and _tl_styles == (['1.0', '1.4'], ['2.3', '2.8']))
    # A bold word deleted while that line stands: the run of deletes noted
    # the formatting before the line was the note's, and Ctrl+Z gave the
    # word back plain.
    _tl_ok = _tl_table_at_end('Bold words here')
    app.body_text.tag_add('bold', '1.0', '1.4')
    app.body_text.tag_add('sel', '1.0', '1.4')
    app.body_text.mark_set('insert', '1.4')
    app._last_caret_line = 1
    _own_key('<BackSpace>', '<KeyRelease-BackSpace>')
    _tl_ok = _tl_ok and _tl_text().startswith(' words here')
    _tl_keys('z')
    _tl_bold = [str(i) for i in app.body_text.tag_ranges('bold')]
    check(f'a bold word deleted beside the drawing\'s line under a table '
          f'comes back bold on Ctrl+Z ({_tl_ok}; {_tl_bold})',
          _tl_ok and _tl_text().startswith('Bold words here')
          and _tl_bold == ['1.0', '1.4'])
    # A table at a note's end deleted -- by its grid's Delete table, or
    # selected to the end with its caption -- then Ctrl+Z: the drawing's
    # line was taken for the person's, and the table came back glued onto
    # the line above ("Intro line| Name |"), Ctrl+Y garbling the note. A
    # bold word in a cell comes back with it: the delete is the edit that
    # makes the line the note's, from inside its own undo step.
    _tl_dt = []
    for _tl_how in ('Delete table', 'Delete', 'BackSpace'):
        _tl_ok = _tl_table_at_end('Intro line' + chr(10) + chr(10) + 'Caption')
        app.body_text.tag_add('bold', '6.2', '6.5')
        _tl_ok = _tl_ok and app.body_text.get('6.2', '6.5') == 'Tea'
        _tl_start = _tl_text()
        if _tl_how == 'Delete table':
            app._grid_delete_table(app._grid_at_line(4))
            app.update()
        else:
            app.body_text.tag_add('sel', '3.0', 'end-1c')
            app.body_text.mark_set('insert', 'end-1c')
            _own_key('<%s>' % _tl_how, '<KeyRelease-%s>' % _tl_how)
        _tl_gone = _tl_text()
        _tl_keys('z')
        _tl_back = (_tl_text() == _tl_start
                    and [str(i) for i in app.body_text.tag_ranges('bold')]
                    == ['6.2', '6.5'])
        _tl_keys('y')
        _tl_dt.append((_tl_how, _tl_ok and _tl_gone != _tl_start,
                       _tl_back, _tl_text() == _tl_gone))
    check(f'a table deleted at a note\'s end comes back exactly on Ctrl+Z, '
          f'and goes again on Ctrl+Y ({_tl_dt})',
          all(ok and back and fwd for _h, ok, back, fwd in _tl_dt))
    # The theme switched, or the font size changed, with a table row still
    # being typed: the redraw drew the row, and the next letter typed went
    # under the table.
    _tl_kr = []
    for _tl_by in ('theme', 'font size'):
        for _tl_kind in ('typed', 'pasted'):
            set_body('Intro' + chr(10) + chr(10) + chr(10) + 'end line')
            app._reset_text_undo()
            app.body_text.mark_set('insert', '2.0')
            app._last_caret_line = None
            for _tl_i, _tl_row in enumerate(('| Item name | Qty |',
                                             '| --- | --- |', '| Tea | 2 |')):
                for _tl_ch in _tl_row:
                    _ty_key(_pr_keys.get(_tl_ch, _tl_ch), _tl_ch)
                if _tl_i < 2:
                    _ty_key('Return', chr(10))
            for _ in range(3):
                _sm_press('<KeyPress-Left>')
            if _tl_kind == 'typed':
                for _tl_ch in 'XY':
                    _ty_key(_tl_ch, _tl_ch)
            else:
                _sm_clip['data'] = 'XY'
                _own_key('<Control-KeyPress-v>', '<Control-KeyRelease-v>',
                         ('Control_L',))
                _sm_clip['data'] = _sm_tsv
            if _tl_by == 'theme':
                app.toggle_theme()
            else:
                _tl_size = app.editor_font_size
                app._set_editor_font(size=_tl_size + 1)
            app.update()
            _ty_key('Z', 'Z')
            _tl_kr.append((_tl_by, _tl_kind, app.body_text.get('4.0', '4.end')))
            if _tl_by == 'theme':
                app.toggle_theme()
            else:
                app._set_editor_font(size=_tl_size)
            app.update()
    check(f'a theme switch or a new font size leaves a row being typed as it '
          f'is ({_tl_kr})',
          [r for _b, _k, r in _tl_kr] == ['| Tea | XYZ2 |'] * 4)
    # An older edit of a drawn table's header, walked back past once the
    # line the drawing put under a later table is the note's -- written on,
    # or taken out and drawn again by a theme switch. Tk never recorded the
    # line, so it stays at the end of every older text, which undo noted
    # without it: the edit was replayed with the tables down, a column off.
    _tl_old = []
    for _tl_how in ('a letter', 'drawn again'):
        set_body('| A | B |' + chr(10) + '| --- | --- |' + chr(10) + '| 1 | 2 |'
                 + chr(10) + chr(10) + 'Intro line')
        app._render_table_grids()
        app.update()
        app._reset_text_undo()
        app._cancel_pending_autosave()
        _tl_first = _tl_text()
        _tl_ok = app._grid_at_line(1) is not None
        if _tl_ok:
            app._open_cell_editor(app._grid_at_line(1), 0, 0)
            app.update()
            _tl_ed = app._cell_editor['entry']
            _tl_ed.delete('1.0', 'end')
            _tl_ed.insert('1.0', 'Ax')
            app._commit_cell_editor()
            app.update()
        app.body_text.mark_set('insert', 'end-1c')
        app._last_caret_line = None
        _ty_key('Return', chr(10))
        for _tl_i, _tl_row in enumerate(('| Name | Qty |', '| --- | --- |',
                                         '| Tea | 2 |')):
            for _tl_ch in _tl_row:
                _ty_key(_pr_keys.get(_tl_ch, _tl_ch), _tl_ch)
            if _tl_i < 2:
                _ty_key('Return', chr(10))
        _tl_click('5.3')
        _tl_ok = _tl_ok and getattr(app, '_undo_tail', None) is not None
        if _tl_how == 'a letter':
            app.body_text.mark_set('insert', '5.end')
            app._last_caret_line = 5
            _ty_key('q', 'q')
        else:
            app.body_text.tag_add('sel', 'end-2c', 'end-1c')
            app.body_text.mark_set('insert', 'end-1c')
            _own_key('<Delete>', '<KeyRelease-Delete>')
            app.toggle_theme()
            app.toggle_theme()
            app.update()
            _tl_ok = _tl_ok and getattr(app, '_undo_tail', None) is not None
        for _ in range(12):
            if _tl_text().split(chr(10))[0] == '| A | B |':
                break
            _tl_keys('z')
        _tl_old.append((_tl_how, _tl_ok, _tl_text().split(chr(10))[0],
                        _tl_text() in (_tl_first, _tl_first + chr(10))))
    check(f'an older edit of a drawn table\'s header walks back exactly past '
          f'the drawing\'s line made the note\'s ({_tl_old})',
          all(ok and first == '| A | B |' and whole
              for _h, ok, first, whole in _tl_old))
    # A word made bold in a row still being typed, the table then ending the
    # note with no line under it. Ctrl+Z back past the Enter typed after
    # the row puts the drawing's line there, which Tk does not know: counted,
    # the bold no longer matched, and the next Ctrl+Z took back the row's
    # typing with the bold left on.
    set_body('Intro line')
    app._reset_text_undo()
    app._cancel_pending_autosave()
    app.body_text.mark_set('insert', '1.end')
    app._last_caret_line = None
    _ty_key('Return', chr(10))
    for _tl_i, _tl_row in enumerate(('| Name | Qty |', '| --- | --- |',
                                     '| Tea | 2 |')):
        for _tl_ch in _tl_row:
            _ty_key(_pr_keys.get(_tl_ch, _tl_ch), _tl_ch)
        if _tl_i < 2:
            _ty_key('Return', chr(10))
    app.body_text.tag_add('sel', '4.2', '4.5')
    app.body_text.mark_set('insert', '4.5')
    _own_key('<Control-KeyPress-b>', '<Control-KeyRelease-b>', ('Control_L',))
    app.body_text.tag_remove('sel', '1.0', 'end')
    _tl_bolded = bool(app.body_text.tag_ranges('bold'))
    _sm_press('<KeyPress-End>')
    _ty_key('Return', chr(10))
    _tl_keys('zz')
    _tl_tail = getattr(app, '_undo_tail', None) is not None
    _tl_keys('z')
    _tl_row4 = app.body_text.get('4.0', '4.end')
    check(f'a bold made in a row being typed is taken back on its own past '
          f'the drawing\'s line under the table ({_tl_bolded}; {_tl_tail}; '
          f'{_tl_row4!r}; bold {app.body_text.tag_ranges("bold")})',
          _tl_bolded and _tl_tail and 'Tea' in _tl_row4
          and not app.body_text.tag_ranges('bold'))
    # Insert over a selection holding a drawn table: Tk pastes the
    # selection's text over it, and that text leaves out the table's hidden
    # rows -- the table went. Insert does nothing there.
    set_body('Intro word here' + chr(10) + '| Name | Qty |' + chr(10)
             + '| --- | --- |' + chr(10) + '| Tea | 2 |' + chr(10) + chr(10)
             + 'end line')
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    _it_start = app.body_text.get('1.0', 'end-1c')
    app.body_text.tag_add('sel', '1.6', '5.0')
    app.body_text.mark_set('insert', '5.0')
    _it_ok = _own_key('<KeyPress-Insert>', '<KeyRelease-Insert>')
    app.body_text.tag_remove('sel', '1.0', 'end')
    check('Insert over a selection holding a drawn table keeps the table',
          _it_ok and app.body_text.get('1.0', 'end-1c') == _it_start
          and app._grid_at_line(2) is not None)
finally:
    app.tk.eval('rename ::tk::GetSelection {}')
    app.tk.eval('rename ::tk::_qa1_sm_GetSelection ::tk::GetSelection')
    app.tk.deletecommand('::qa1_sm_clip')
    NO.clipboard.read_text, NO.clipboard.read_html = _sm_real
# A drag from beside one table to beside another: the end the caret was not
# at stayed on the first table's hidden text -- the guard ran only when the
# caret was off every table -- and Delete or a paste, which run no guard of
# their own, glued a row or merged the two tables.
_sm_twos = []
for _sm_from, _sm_to in (('4.end', '8.end'), ('8.end', '4.end')):
    _sm_fresh(_sm_to, _sm_two)
    _sm_a = app.body_text.index(_sm_from)
    _sm_b = app.body_text.index(_sm_to)
    if app.body_text.compare(_sm_a, '>', _sm_b):
        _sm_a, _sm_b = _sm_b, _sm_a
    app.body_text.tag_add('sel', _sm_a, _sm_b)
    _qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
    app.update()
    _sm_twos.append(_sm_where()[0])
check(f'selection x table: a drag from beside one table to beside another '
      f'selects only the line between, either way ({_sm_twos})',
      _sm_twos == [('5.0', '5.3'), ('5.0', '5.3')])
# Select all in a note that begins with a table: its start, at the table's
# top, read as "on the table", and the table was cut out of the selection.
_sm_fresh('4.3', '| Item | Qty |' + chr(10) + '| --- | --- |' + chr(10)
          + '| Tea | 2 |' + chr(10) + 'after' + chr(10) + 'more')
take_focus(app.body_text)
app.body_text.event_generate('<<SelectAll>>')
app.body_text.event_generate('<KeyRelease-a>')
app.update()
check(f'selection x table: select all in a note that begins with a table '
      f'keeps the table ({_sm_where()[0]})',
      _sm_where()[0] is not None and _sm_where()[0][0] == '1.0')
# A key that typed nothing extends no style: the release of an arrow -- or
# the caret guard's own stop at a table under "Prices:" -- found a plain ":"
# glued to a bold word left of the caret, and made it bold.
_sm_fresh('1.6', 'Prices: here')
app.body_text.tag_add('bold', '1.0', '1.6')
_sm_press('<KeyPress-Right>')
check(f'selection x table: an arrow key leaves the bold where it was '
      f'({app.body_text.tag_ranges("bold")})',
      [str(i) for i in app.body_text.tag_ranges('bold')] == ['1.0', '1.6'])
app.body_text.tag_remove('bold', '1.0', 'end')
# A mouse press beside a drawn table lands on its last row's hidden text.
# Dragged down, the selection began inside that row, and the next key glued
# the row onto the paragraph under it; dragged up, it took the whole table.
# The end left on a table goes to the table's edge facing the other end.
_sm_fresh('5.3')
app.body_text.tag_add('sel', '4.end', '5.3')
_qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
app.update()
_sm_down = _sm_where()
_sm_fresh('1.3')
app.body_text.tag_add('sel', '1.3', '4.end')
_qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
app.update()
_sm_up = _sm_where()
_sm_fresh('3.2')
app.body_text.tag_add('sel', '2.3', '3.2')
_qa_fire(app.body_text, '<ButtonRelease-1>', x=2, y=2)
app.update()
check(f'selection x table: a drag that starts beside a table leaves the '
      f'table out, either way ({_sm_down}; {_sm_up}), and one inside a '
      f'table\'s hidden text selects nothing ({_sm_where()})',
      _sm_down == (('5.0', '5.3'), '5.3') and _sm_up == (('1.3', '1.7'), '1.3')
      and _sm_where()[0] is None)
# Our own copied cells: the separator from the copied widths went in
# narrower than its rows, and the tidy padded it as an undo step of its
# own once the caret had been in and out of the table.
_sm_fresh('6.0')
app._grid_cell_clip_text = _sm_tsv
app._grid_cell_clip_widths = [{'width': 12, 'align': None, 'hidden': False},
                              {'width': None, 'align': None, 'hidden': False}]
app._grid_cell_clip_place = None
try:
    app._paste_tsv_as_table(_sm_tsv)
    app.update()
finally:
    app._grid_cell_clip_text = None
    app._grid_cell_clip_widths = None
_sm_all = app.body_text.get('1.0', 'end-1c')
_sm_last = core_tables.find_blocks(_sm_all)[-1]
_sm_block = _sm_all.split(chr(10))[_sm_last[0]:_sm_last[1] + 1]
_sm_aligns = [core_tables.cell_alignments(_l) for _l in _sm_block]
_sm_widths = core_tables.layout_widths(
    [core_tables.split_row(_l) for _l in _sm_block], _sm_aligns)
check(f'selection x table: our own copied cells come back laid out as the '
      f'tidy lays them out, the copied width kept ({_sm_block})',
      len(_sm_block) == 3 and not any(
          core_tables.pad_ops(_l, _sm_widths, _a)
          for _l, _a in zip(_sm_block, _sm_aligns))
      and (core_tables.parse_separator(_sm_block[1])[0] or {}).get('width') == 12)
# The paste itself never puts cells into a table's line, however the
# selection was made: one that holds a table's line break keeps the break.
_sm_fresh('1.0')
app.body_text.tag_add('sel', '1.0', '2.0')
# The line a key's release recorded before the paste: the selection's end.
app._last_caret_line = 2
app._paste_tsv_as_table(_sm_tsv)
app.update()
check(f'selection x table: a selection holding a table\'s line break leaves '
      f'the break, and the table, where they were (kept {_sm_table_kept()}; '
      f'{app.body_text.get("1.0", "end-1c")!r})',
      _sm_table_kept()
      and app.body_text.get('1.0', 'end-1c').startswith('| Day'))
# ...laid out as the tidy would leave it, and the caret's last line
# forgotten: the release of the paste's own key is not the caret leaving a
# table, and read as one it tidied a table as an undo step of its own.
_sm_lines = app.body_text.get('1.0', 'end-1c').split(chr(10))[:3]
_sm_aligns = [core_tables.cell_alignments(_l) for _l in _sm_lines]
_sm_widths = core_tables.layout_widths(
    [core_tables.split_row(_l) for _l in _sm_lines], _sm_aligns)
_sm_ops = [core_tables.pad_ops(_l, _sm_widths, _a)
           for _l, _a in zip(_sm_lines, _sm_aligns)]
check(f'selection x table: pasted cells are laid out as the tidy lays them '
      f'out, and the caret\'s last line is forgotten ({_sm_lines}; '
      f'{app._last_caret_line})',
      not any(_sm_ops) and app._last_caret_line is None)
set_body('')

# ---- CTRL+Z PUTS A TABLE'S FIRST LINE BACK EXACTLY ----
# A drawn table's first line holds the grid's window at column 0, and Tk
# records an edit by its index. Operations that take the grids down, edit,
# and draw them again recorded their edits one column off from where
# Ctrl+Z replayed them with the grids drawn: centring a cell, inserting a
# row below or autofitting a column, then Ctrl+Z, gave the header back as
# "| Ite  | Qt  |". A step recorded with the grids down is replayed with
# them down now (_undo_atom_grids_coming_down).
_tu_body = ('Plan the trip' + chr(10) + '| Item | Qty | Note |' + chr(10)
            + '| --- | --- | --- |' + chr(10) + '| Milk | 2 | x |' + chr(10)
            + '| Eggs | 12 | y |' + chr(10) + 'pack the bags')


def _tu_fresh():
    set_body(_tu_body)
    app._render_table_grids()
    app.update()
    app._reset_text_undo()
    app._cancel_pending_autosave()
    return app._grid_at_line(2)


for _tu_name, _tu_do in (
        ('centring a header cell',
         lambda i: (app._grid_select_range(i, (0, 0), (0, 0)),
                    app._set_paragraph_align('center'))),
        ('centring a data cell',
         lambda i: (app._grid_select_range(i, (1, 1), (1, 1)),
                    app._set_paragraph_align('center'))),
        ('inserting a row below', lambda i: app._grid_insert_row(i, 2)),
        ('inserting a row above the header',
         lambda i: app._grid_insert_row(i, 0)),
        ('merging a cell with the one to its left',
         lambda i: app._grid_merge_with(i, 1, 1, 'left')),
        ('autofitting a column', lambda i: app._grid_autofit_col(i, 0)),
        ('inserting a column at the left', lambda i: app._grid_insert_col(i, 0)),
        ('merging two header cells',
         lambda i: (app._grid_select_range(i, (0, 0), (0, 1)),
                    app._grid_merge_selection(app._grid_sel)))):
    _tu_info = _tu_fresh()
    _tu_t0 = app.body_text.get('1.0', 'end-1c')
    _tu_do(_tu_info)
    app.update()
    _tu_t1 = app.body_text.get('1.0', 'end-1c')
    app._body_undo_redo('undo'); app.update()
    _tu_t2 = app.body_text.get('1.0', 'end-1c')
    app._body_undo_redo('redo'); app.update()
    _tu_t3 = app.body_text.get('1.0', 'end-1c')
    check(f'table undo: {_tu_name}, then Ctrl+Z, puts the table back exactly, '
          f'and Ctrl+Y the operation ({_tu_t2.split(chr(10))[1]!r}, '
          f'{_tu_t3.split(chr(10))[1]!r})',
          _tu_t1 != _tu_t0 and _tu_t2 == _tu_t0 and _tu_t3 == _tu_t1
          and app._grid_at_line(2) is not None)
# One step held a header cell's commit -- made with the grid drawn -- AND
# the toolbar's centre that followed, made with it down: right in neither
# state. The commit is a step of its own now, so the first Ctrl+Z takes
# back the centre and leaves the word whole, the second the word.
_tu_info = _tu_fresh()
_tu_t0 = app.body_text.get('1.0', 'end-1c')
app._open_cell_editor(_tu_info, 0, 0)
app.update()
_tu_ed = getattr(app, '_cell_editor', None)
if _tu_ed is not None:
    _tu_ed['entry'].delete('1.0', 'end')
    _tu_ed['entry'].insert('1.0', 'Food')
_tu_info = app._grid_at_line(2)
app._grid_select_range(_tu_info, (0, 0), (0, 0))
app._set_paragraph_align('center')
app.update()
app._body_undo_redo('undo'); app.update()
_tu_first = app.body_text.get('1.0', 'end-1c').split(chr(10))[1]
app._body_undo_redo('undo'); app.update()
check(f'table undo: a header cell still being edited when the toolbar '
      f'centres it comes back in two whole steps ({_tu_first!r}, then '
      f'{app.body_text.get("1.0", "end-1c").split(chr(10))[1]!r})',
      _tu_ed is not None
      and [c.strip() for c in _tu_first.strip('|').split('|')]
      == ['Food', 'Qty', 'Note']
      and app.body_text.get('1.0', 'end-1c') == _tu_t0)
# Walking back past a table operation on a table narrower than the app
# pads (pasted Markdown keeps its columns until the caret leaves): the
# release of an undo key found the caret "leaving" the table the undo had
# put it in, and padded it as a new recorded edit -- which wiped the redo
# history, so Ctrl+Y brought nothing back.
_rd_body = ('Plan the trip' + chr(10) + '| Item | Qty |' + chr(10)
            + '| --- | --- |' + chr(10) + '| Milk | 2 |' + chr(10)
            + '| Eggs | 12 |' + chr(10) + 'pack the bags')


def _rd_press(keysym):
    """A Control key as the keyboard sends it: its press, then its release."""
    if not take_focus(app.body_text):
        return False
    app.body_text.event_generate(f'<Control-KeyPress-{keysym}>')
    app.body_text.event_generate(f'<Control-KeyRelease-{keysym}>')
    app.update()
    return True


set_body(_rd_body)
app._render_table_grids()
app.update()
app._reset_text_undo()
app._cancel_pending_autosave()
app.body_text.mark_set('insert', 'end-1c')
app.body_text.insert('insert', ' hello')
app._flush_table_grids()            # the pause an autosave leaves
_rd_typed = app.body_text.get('1.0', 'end-1c')
app._grid_insert_row(app._grid_at_line(2), 2)
app.update()
_rd_row = app.body_text.get('1.0', 'end-1c')
_rd_seen = []
for _rd_k in ('z', 'z', 'y', 'y'):
    _rd_press(_rd_k)
    _rd_seen.append(app.body_text.get('1.0', 'end-1c'))
check(f'table undo: Ctrl+Z twice past a row inserted in a narrow table, then '
      f'Ctrl+Y twice, lands on each state exactly -- the redo history '
      f'survives ({[s == w for s, w in zip(_rd_seen, (_rd_typed, _rd_body, _rd_typed, _rd_row))]})',
      _rd_row != _rd_typed
      and _rd_seen == [_rd_typed, _rd_body, _rd_typed, _rd_row])
# Every draw of a table bound its callbacks on the grid, and deleting the
# grid's window took the widget away inside Tk but not in tkinter: each
# redraw left ten Tcl commands and a frame behind, for good.
set_body(_rd_body)
app._render_table_grids()
app.update()
_lk_frames = len(app.body_text.children)
_lk_clean, _lk_said = _qa_leaves_nothing_behind(app, app._render_table_grids, 30)
_lk_frames = len(app.body_text.children) - _lk_frames
check(f'a table drawn again and again leaves no Tcl command or frame behind '
      f'({_lk_said}; frames grown: {_lk_frames})',
      _lk_clean and _lk_frames <= 0 and app._grid_at_line(2) is not None)
set_body('')

# ---- CTRL+Z AFTER A TABLE OPERATION BRINGS THE TABLE'S STYLES BACK ----
# Tk re-inserts the text an undo puts back without its tags, so every
# table operation's Ctrl+Z returned the cells bare. The journal lays the
# styles the table had back on the text Tk restores -- and Ctrl+Y lays
# the operation's own ones back on the way forward.
for _ut_name, _ut_do in (
        ('clearing a cell with Delete',
         lambda i: (app._grid_select_range(i, (1, 2), (1, 2)),
                    app._on_body_delete_key())),
        ('dropping a checkbox',
         lambda i: app._grid_set_marker(i, 2, 2, core_tables.CHECKBOX_EMPTY)),
        ('deleting the bold row',
         lambda i: app._grid_delete_row(i, 1)),
        ('inserting a column',
         lambda i: app._grid_insert_col(i, 0))):
    _ut_info = _cs_setup()
    app._reset_text_undo()
    _ut_text0 = app.body_text.get('1.0', 'end-1c')
    _ut_do(_ut_info)
    app.update()
    _ut_text1, _ut_styles1 = app.body_text.get('1.0', 'end-1c'), _cs_styles()
    _uf_key('<Control-z>')
    check(f'table undo: Ctrl+Z after {_ut_name} brings the text AND the '
          f'styles back ({_cs_styles()})',
          app.body_text.get('1.0', 'end-1c') == _ut_text0
          and _cs_styles() == _cs_want)
    _uf_key('<Control-y>')
    check(f'table undo: ...and Ctrl+Y redoes {_ut_name} with its styles '
          f'({_cs_styles()})',
          app.body_text.get('1.0', 'end-1c') == _ut_text1
          and _cs_styles() == _ut_styles1)

# The whole-body rewrite that renumbers a list is the same mechanism: Tk
# put the old body back bare, every style in the note gone with one press.
set_body('1. one' + chr(10) + '2. two' + chr(10) + 'bold words')
app._apply_formatting(app.body_text, [
    {'start': len('1. one\n2. two\n'), 'end': len('1. one\n2. two\nbold'),
     'style': 'bold'}])
app.update()
app._reset_text_undo()
app.body_text.mark_set('insert', '1.end')
_ut_before = app.body_text.get('1.0', 'end-1c')
app._on_body_return(None)
app.update()
_uf_key('<Control-z>')
_uf_key('<Control-z>')
check('list undo: Ctrl+Z after a renumbering Enter keeps the note\'s bold '
      f'({_cs_styles()})',
      app.body_text.get('1.0', 'end-1c') == _ut_before
      and _cs_styles() == [('bold', 'bold')])
set_body('')

# ---- A CHECKLIST CHANGE TOUCHES ONE ROW, AND A CLOSED LIST BUILDS NONE ----
# Adding or removing ONE item destroyed and rebuilt every row -- four
# widgets each, and a new font per label: 0.3 s at 50 items, over 2 s at
# 200. And every note with a checklist built all its rows on opening, for
# a section a note switch always leaves closed. The rows are built when
# the section opens now, and a change touches only its own row. Asked of
# the widgets themselves: the rows that should stay are the SAME widgets
# afterwards, which is what a rebuild cannot fake.
def _cl_rows():
    return [str(_w) for _w in app.checklist_items_frame.winfo_children()
            if isinstance(_w, tk.Frame)]


def _cl_texts():
    """Each row's item text, in Tab order -- its ▲ ▼ are a Label too."""
    return [str(_c.cget('text'))
            for _r in app.checklist_items_frame.winfo_children()
            if isinstance(_r, tk.Frame)
            for _c in _r.winfo_children() if isinstance(_c, tk.Label)
            and str(_c.cget('text')) != '▲\n▼']


check('checklist rows: fixture opens three items',
      _cu_setup(['milk', 'eggs', 'bread']))
_cl_0 = _cl_rows()
app.checklist_add_var.set('butter')
app._add_checklist_item()
app.update()
_cl_1 = _cl_rows()
check('checklist rows: adding an item builds ONE row and keeps the others',
      _cl_1[:3] == _cl_0 and len(_cl_1) == 4
      and _cl_texts() == ['milk', 'eggs', 'bread', 'butter'])
_cu_press(1)
check('checklist rows: removing an item takes only its own row',
      _cl_rows() == [_cl_1[0], _cl_1[2], _cl_1[3]]
      and _cl_texts() == ['milk', 'bread', 'butter'])
if app._toast_action is not None:
    app._toast_action()
app.update()
_cl_2 = _cl_rows()
check('checklist rows: the Undo puts that one row back in its place',
      _cl_texts() == ['milk', 'eggs', 'bread', 'butter']
      and _cl_2[0] == _cl_1[0] and _cl_2[2:] == [_cl_1[2], _cl_1[3]])
app.toggle_checklist_section()
app.toggle_checklist_section()
app.update()
check('checklist rows: closing and reopening the same list rebuilds nothing',
      _cl_rows() == _cl_2)
# Another note's checklist, then back: loading closes the section, and a
# closed section gets no rows at all until it is opened.
app.open_note_in_tab(app.find_note(9101))
app.update()
app.open_note_in_tab(app.find_note(9100))
app.update()
check('checklist rows: a note opened with the section closed builds no rows '
      f'({_cl_texts()})',
      not app._checklist_open
      and not ({'milk', 'eggs', 'bread', 'butter'} & set(_cl_texts())))
app.toggle_checklist_section()
app.update()
check('checklist rows: opening the section builds them',
      _cl_texts() == ['milk', 'eggs', 'bread', 'butter'])
# Two items that read the same are two items: removing the second must
# leave the row standing tied to the item left in the list, or its tick
# box writes to a dict nothing saves any more.
check('checklist rows: fixture with two items reading the same',
      _cu_setup(['milk', 'milk']))
_cu_press(1)
_cl_box = [_c for _r in app.checklist_items_frame.winfo_children()
           if isinstance(_r, tk.Frame)
           for _c in _r.winfo_children() if isinstance(_c, tk.Checkbutton)]
if len(_cl_box) == 1:
    _cl_box[0].invoke()
    app.update()
check('checklist rows: with two items alike, the row left ticks the item left',
      len(_cl_box) == 1 and len(app._get_checklist()) == 1
      and app._get_checklist()[0]['done'] is True)

# ---- A DOUBLE-CLICK ON A CHECKLIST BIN REMOVES ONE ITEM ----
# Many people double-click every button. The first click removed the row
# and the next row slid up into its place, so the second press landed on
# THAT row's bin and removed it too -- the toast's single Undo offering
# back only the second, the first gone for good. The second press of a
# double-click (Tk's own rule: 500 ms, 5 px) is swallowed now, on
# whichever bin it lands. Delivered the way a pointer delivers it --
# Enter, press, release -- at explicit screen points and event times, so
# the verdict never depends on this desktop's clock or where its pointer
# rests. Each "it removed nothing more" has its control: the same press
# later, or elsewhere, is a click of its own and removes.
def _dc_click(widget, x_root, y_root, t):
    # No bin where one should be (a row too many already gone) is for the
    # checks below to report by what the list holds -- never a crash that
    # ends the script before its FAILURES line.
    if widget is None:
        return
    _qa_fire(widget, '<Enter>')
    _qa_fire(widget, '<ButtonPress-1>', x=5, y=5, rootx=x_root,
             rooty=y_root, time=t)
    _qa_fire(widget, '<ButtonRelease-1>', x=5, y=5, rootx=x_root,
             rooty=y_root, time=t + 60)
    app.update()


check('double-click: fixture opens four items',
      _cu_setup(['milk', 'eggs', 'bread', 'butter']))
_dc_x, _dc_y = 400, 300
_dc_click(_cu_bin(1), _dc_x, _dc_y, 100000)
check('double-click: the first click of it removes the row under it (fixture)',
      _cu_texts() == ['milk', 'bread', 'butter'])
_dc_click(_cu_bin(1), _dc_x, _dc_y, 100250)
check(f'double-click: the second press, on the row slid into place, removes '
      f'nothing ({_cu_texts()})',
      _cu_texts() == ['milk', 'bread', 'butter'])
check('double-click: and the toast still offers back the one it removed',
      'eggs' in str(app.toast_lbl.cget('text')) and app._toast_action is not None)
_dc_click(_cu_bin(1), _dc_x, _dc_y, 100900)
check('double-click: a click after the double-click window removes as usual',
      _cu_texts() == ['milk', 'butter'])
_dc_click(_cu_bin(1), _dc_x, _dc_y + 40, 101000)
check('double-click: a quick click on a bin elsewhere is a click of its own',
      _cu_texts() == ['milk'])

# ---- MOVING A CHECKLIST ITEM ----
# ▲ and ▼ on every row, Alt+Up/Down on its tick box (the owner's re-test of
# 0.84.357, case 306). Only the two rows trade places, and the record of the
# drawn rows trades with them: each row's box, bin and arrows close over
# their own item, so a record left behind makes one act on another's item.
def _mv_rows():
    return [w for w in app.checklist_items_frame.winfo_children()
            if isinstance(w, tk.Frame)]


_MV_ARROWS = '▲\n▼'


def _mv_packed_texts():
    return [str(_c.cget('text'))
            for _r in app.checklist_items_frame.pack_slaves()
            for _c in _r.winfo_children() if isinstance(_c, tk.Label)
            and str(_c.cget('text')) != _MV_ARROWS]


def _mv_in(row, klass, text=None):
    return next((w for w in row.winfo_children() if isinstance(w, klass)
                 and (text is None or str(w.cget('text')) == text)), None)


def _mv_text(row):
    return next((w for w in row.winfo_children() if isinstance(w, tk.Label)
                 and str(w.cget('text')) != _MV_ARROWS), None)


def _mv_arrows(position):
    rows = _mv_rows()
    return (_mv_in(rows[position], tk.Label, _MV_ARROWS)
            if 0 <= position < len(rows) else None)


_mv_clock = {'t': 300000}


def _mv_click(position, glyph, t=None, root=None):
    """A press on a row's ▲ over ▼ -- its top half for ▲, its bottom half
    for ▼ -- each at a moment of its own, so two presses are taken for a
    double-click only when a check asks for one."""
    arrows = _mv_arrows(position)
    if arrows is None:
        return
    app.update_idletasks()
    y = 2 if glyph == '▲' else max(3, arrows.winfo_height() - 2)
    if t is None:
        _mv_clock['t'] += 1000
        t = _mv_clock['t']
    rx, ry = root or (arrows.winfo_rootx() + 4, arrows.winfo_rooty() + y)
    _qa_fire(arrows, '<Enter>')
    _qa_fire(arrows, '<ButtonPress-1>', x=4, y=y, rootx=rx, rooty=ry, time=t)
    _qa_fire(arrows, '<ButtonRelease-1>', x=4, y=y, rootx=rx, rooty=ry,
             time=t + 60)
    # The pointer moves on, as a person's does: the arrows lit under it go
    # back to rest (_light_arrows).
    if arrows.winfo_exists():
        _qa_fire(arrows, '<Leave>')
    app.update()


def _mv_press(position, glyph):
    _mv_click(position, glyph)


def _mv_rings():
    """Which rows wear the keyboard's ring, by position: in both border
    colours, as Tk draws highlightcolor while the focus is inside a row."""
    return [i for i, r in enumerate(_mv_rows())
            if str(r.cget('highlightbackground')).lower()
            == str(r.cget('highlightcolor')).lower()
            == app.colors['accent'].lower()]


def _mv_agree(expected):
    """The list, the rows in Tab order and the rows as packed all say it."""
    return (_cu_texts() == expected and _cl_texts() == expected
            and _mv_packed_texts() == expected)


check('move: fixture opens four items',
      _cu_setup(['milk', 'eggs', 'bread', 'butter']))
_mv_0 = [str(w) for w in _mv_rows()]
_mv_asked = {'n': 0}
_mv_real_schedule = app._schedule_autosave


def _mv_counting(*a, **k):
    _mv_asked['n'] += 1
    return _mv_real_schedule(*a, **k)


app._schedule_autosave = _mv_counting
try:
    _mv_press(2, '▲')
finally:
    del app._schedule_autosave
check(f'move: ▲ takes an item one place up, on screen too ({_cu_texts()})',
      _mv_agree(['milk', 'bread', 'eggs', 'butter']))
check('move: the same two rows trade places -- nothing is rebuilt',
      [str(w) for w in _mv_rows()] == [_mv_0[0], _mv_0[2], _mv_0[1], _mv_0[3]])
check('move: and it asks for its own save', _mv_asked['n'] >= 1)
# Her re-test (case 591): an item could not be chosen for the keyboard as a
# note can. A press on its arrows asks the keyboard for its box -- even where
# nothing moves. Recorded rather than polled: focus_get() answers None when
# this process does not own the desktop's foreground (qa/README, flakes).
_mv_focus_asked = []
_mv_real_focus_set = tk.Misc.focus_set
tk.Misc.focus_set = lambda w: (_mv_focus_asked.append(w),
                               _mv_real_focus_set(w))[1]
try:
    _mv_press(0, '▲')
    _mv_press(3, '▼')
finally:
    tk.Misc.focus_set = _mv_real_focus_set
check('move: ▲ on the first row and ▼ on the last move nothing',
      _mv_agree(['milk', 'bread', 'eggs', 'butter']))
check(f'move: a press on the arrows gives that item the keyboard, even where '
      f'nothing moves ({_mv_focus_asked[-2:]})',
      _mv_focus_asked[-2:] == [_mv_in(_mv_rows()[0], tk.Checkbutton),
                               _mv_in(_mv_rows()[3], tk.Checkbutton)])
# And the row whose box has the keyboard wears a ring, the only one.
take_focus(_mv_in(_mv_rows()[3], tk.Checkbutton))
_mv_ring_3 = _mv_rings()
take_focus(_mv_in(_mv_rows()[1], tk.Checkbutton))
check(f'move: the item with the keyboard has a ring round its row, and only '
      f'that row ({_mv_ring_3}, then {_mv_rings()})',
      _mv_ring_3 == [3] and _mv_rings() == [1])
from _qa_support import ring_mismatches as _mv_ring_mismatches
_mv_bad_rings = _mv_ring_mismatches(app.checklist_items_frame)
check(f'move: every row draws its border in one colour, the keyboard in it '
      f'or not ({_mv_bad_rings})', not _mv_bad_rings)
_mv_r0 = _mv_rows()[0]
_mv_a0, _mv_b0, _mv_t0 = (_mv_in(_mv_r0, tk.Label, _MV_ARROWS),
                          _mv_in(_mv_r0, tk.Checkbutton), _mv_text(_mv_r0))
check('move: the arrows sit at the left of the row, ▲ over ▼, before the '
      'tick box and the text (her re-test, case 593)',
      None not in (_mv_a0, _mv_b0, _mv_t0)
      and _mv_a0.winfo_x() < _mv_b0.winfo_x() < _mv_t0.winfo_x())
_mv_box = _mv_in(_mv_rows()[1], tk.Checkbutton)
if _mv_box is not None:
    _mv_box.invoke()
    app.update()
check("move: the moved row's box ticks its own item",
      [i['done'] for i in app._get_checklist()] == [False, True, False, False])
_cu_press(2)
check("move: the bin of the row it passed removes that row's item",
      _mv_agree(['milk', 'bread', 'butter']))
_mv_undo = app._toast_action
_mv_press(2, '▲')
check('fixture: an item moved while the Undo is still offered',
      _mv_agree(['milk', 'butter', 'bread']) and _mv_undo is not None)
if _mv_undo is not None:
    _mv_undo()
    app.update()
check(f"move: the delete's Undo after a move puts the item back at its place, "
      f"and the rows on screen agree ({_cu_texts()} / {_cl_texts()})",
      _mv_agree(['milk', 'butter', 'eggs', 'bread']))

# The keyboard: Alt+Up/Down on the tick box, which keeps the focus.
_mv_kbox = _mv_in(_mv_rows()[1], tk.Checkbutton)
check('fixture: the moving tick box has the keyboard',
      _mv_kbox is not None and take_focus(_mv_kbox))
if _mv_kbox is not None:
    _mv_kbox.event_generate('<Alt-Down>')
    app.update()
check('move: Alt+Down on a tick box moves its item, and the keyboard stays '
      'on it', _mv_agree(['milk', 'eggs', 'butter', 'bread'])
      and app.focus_get() is _mv_kbox)
if _mv_kbox is not None and take_focus(_mv_kbox):
    _mv_kbox.event_generate('<Alt-Up>')
    app.update()
check('move: Alt+Up takes it back', _mv_agree(['milk', 'butter', 'eggs', 'bread']))
# After a press on its arrows, Alt+Down carries on with the same item: the
# press gave its box the keyboard (her re-test, case 591).
_mv_click(1, '▼')
_mv_kbox = _mv_in(_mv_rows()[2], tk.Checkbutton)
if _mv_kbox is not None and take_focus(_mv_kbox):
    _mv_kbox.event_generate('<Alt-Down>')
    app.update()
check('move: after a press on its arrows, Alt+Down carries on moving the '
      'same item', _mv_agree(['milk', 'eggs', 'bread', 'butter']))
_mv_click(3, '▲')
_mv_click(2, '▲')
check('fixture: back to the order before', _cu_texts() == ['milk', 'butter',
                                                           'eggs', 'bread'])

# A double-click on ▼: the first click moves the item away, and the second
# press lands on the arrows of the row slid into its place.
_mv_click(1, '▼', t=200000, root=(400, 300))
check('double-click on ▼: the first click moves its item (fixture)',
      _cu_texts() == ['milk', 'eggs', 'butter', 'bread'])
_mv_click(1, '▼', t=200250, root=(400, 300))
check(f'double-click on ▼: the second press, on the row slid into place, '
      f'moves nothing ({_cu_texts()})',
      _cu_texts() == ['milk', 'eggs', 'butter', 'bread'])
_mv_click(1, '▼', t=200900, root=(400, 300))
check('double-click on ▼: a click after the window moves as usual',
      _cu_texts() == ['milk', 'butter', 'eggs', 'bread'])
app._flush_autosave()
app.update()
_mv_disk = json.load(open('notes_data.json', encoding='utf-8'))
check('move: the order reaches the file',
      [i['text'] for i in next(n for n in _mv_disk
                               if n['id'] == 9100)['checklist']] == _cu_texts())

# A theme switched while the list is open: the rows are not rebuilt, so the
# arrows and each row's border (the ring, at rest) must take the new theme,
# and the row the keyboard is on keeps its ring (_recolor_checklist_boxes).
_mv_ringed = take_focus(_mv_in(_mv_rows()[2], tk.Checkbutton))
_mv_theme = app.theme_name
app.set_theme('light' if _mv_theme in NO.DARK_THEMES else 'dark')
app.update()
_mv_wrong = [i for i, r in enumerate(_mv_rows())
             for a in [_mv_in(r, tk.Label, _MV_ARROWS)]
             if a is None
             or str(a.cget('bg')).lower() != app.colors['card'].lower()
             or str(a.cget('fg')).lower() != app.colors['subtext'].lower()
             or (i != 2 and any(str(r.cget(o)).lower()
                                != app.colors['card'].lower()
                                for o in ('highlightbackground',
                                          'highlightcolor')))]
check(f'move: the arrows take a theme switched while the list is open '
      f'(rows wrong: {_mv_wrong})', bool(_mv_rows()) and not _mv_wrong)
check(f'move: and the item with the keyboard keeps its ring through the '
      f'switch ({_mv_rings()})', _mv_ringed and _mv_rings() == [2])
# Its rows are not this theme's now, so the move draws them again: the
# keyboard must be put on the new tick box of the item it moved.
_mv_kbox = _mv_in(_mv_rows()[0], tk.Checkbutton)
check('fixture: the first tick box has the keyboard after the switch',
      _mv_kbox is not None and take_focus(_mv_kbox))
if _mv_kbox is not None:
    _mv_kbox.event_generate('<Alt-Down>')
    app.update()
_mv_focus = app.focus_get()
check('move: a move after the switch keeps the rows and the list agreeing',
      _mv_agree(['butter', 'milk', 'eggs', 'bread']))
check(f'move: and the keyboard is on the item it moved, in its new row '
      f'({_mv_focus})',
      isinstance(_mv_focus, tk.Checkbutton) and _mv_focus is not _mv_kbox
      and _mv_focus.master is _mv_rows()[1])
app.set_theme(_mv_theme)
app.update()

# A long item in a narrow window. Its text was packed first and wrapped at
# a fixed 380 px, so at 1024 px and below the bin was squeezed to nothing --
# the item could not be removed -- and the text's last words were cut off.
_mv_geom = app.geometry()
app.geometry('800x600')
app.update()
check('fixture: a long item in a narrow window',
      _cu_setup(['milk', 'a long item that keeps going and going so that it '
                 'has to wrap onto more than one line, the way a real to-do '
                 'sometimes does']))
app.update()
_mv_long = _mv_rows()[1] if len(_mv_rows()) > 1 else None
_mv_btns = ([w for w in _mv_long.winfo_children() if isinstance(w, tk.Button)
             or (isinstance(w, tk.Label) and str(w.cget('text')) == _MV_ARROWS)]
            if _mv_long is not None else [])
_mv_lbl = _mv_text(_mv_long) if _mv_long is not None else None
check(f'narrow: a long item keeps its bin and arrows on its row '
      f'({[(str(b.cget("text")), b.winfo_x(), b.winfo_width()) for b in _mv_btns]}'
      f' in {_mv_long.winfo_width() if _mv_long is not None else 0})',
      len(_mv_btns) == 2
      and all(b.winfo_width() > 5
              and b.winfo_x() + b.winfo_width() <= _mv_long.winfo_width()
              for b in _mv_btns))
check(f'narrow: and its words wrap inside the room it has '
      f'({_mv_lbl.winfo_reqwidth() if _mv_lbl else 0} wanted, '
      f'{_mv_lbl.winfo_width() if _mv_lbl else 0} given)',
      _mv_lbl is not None and _mv_lbl.winfo_reqwidth() <= _mv_lbl.winfo_width())
app.geometry(_mv_geom)
app.update()
app.notes = list(_cu_saved)
app.save_notes()
app.new_note(); app.update()

# ---- A TABLE IS DRAWN ONCE ----
# Building a grid drew every cell plain and then _grid_restyle drew every
# one again, reading all its tags a second time -- half of opening a
# 60-row table. Each cell's text is drawn once now, and its rectangle
# takes its highlight in that same pass: asked of the rectangle's own
# fill, for a highlighted header, a highlighted cell with text and a
# highlighted EMPTY cell (whose colour lives on its padding).
set_body('| Head | Other |' + chr(10) + '| --- | --- |' + chr(10)
         + '| text |  |' + chr(10) + '| more | x |')
_one_hl = [('| Head | Other |', 0, '#ffe066'), ('| text |  |', 0, '#a0e7e5'),
           ('| text |  |', 1, '#c8f7c5')]
_one_body = app.body_text.get('1.0', 'end-1c')
_one_spans = []
for _row, _ci, _hex in _one_hl:
    _at = _one_body.index(_row)
    _pp = [_i for _i, _ch in enumerate(_row) if _ch == '|']
    _one_spans.append({'start': _at + _pp[_ci] + 1, 'end': _at + _pp[_ci + 1],
                       'style': 'highlight', 'value': _hex})
app._apply_formatting(app.body_text, _one_spans)
_one_draws = {'n': 0}
_one_real_draw = app._grid_draw_cell_text


def _one_counting_draw(*a, **k):
    _one_draws['n'] += 1
    return _one_real_draw(*a, **k)


app._grid_draw_cell_text = _one_counting_draw
try:
    app._render_table_grids()
    app.update()
finally:
    del app._grid_draw_cell_text
_one_info = app._grid_at_line(1)
_one_cells = len(_one_info['cells']) if _one_info is not None else -1
check(f'one pass: every cell\'s text is drawn once '
      f'({_one_draws["n"]} draws for {_one_cells} cells)',
      _one_draws['n'] == _one_cells)


def _one_fill(r, c, hex_):
    if _one_info is None or (r, c) not in _one_info['cells']:
        return None
    _surface = (NO.inset_surface(app.colors) if r == 0 else app.colors['card'])
    _fill = str(_one_info['canvas'].itemcget(
        _one_info['cells'][(r, c)]['rect'], 'fill'))
    return _fill if hex_ is None else _fill == app._blend_hex(hex_, _surface,
                                                              0.45)


check('one pass: a highlighted header, text cell and EMPTY cell are washed '
      'in it',
      _one_fill(0, 0, '#ffe066') is True and _one_fill(1, 0, '#a0e7e5') is True
      and _one_fill(1, 1, '#c8f7c5') is True)
check('one pass: and a plain cell keeps its surface',
      _one_fill(2, 1, None) == app.colors['card'])
# The UTF-16 width is counted by the codec now instead of per character;
# the answer must be the rule Tk keeps -- an astral character two units,
# anything else (a lone surrogate half included) one.
check('one pass: the UTF-16 count is still the one Tk keeps',
      all(NO.NoteOrganizer._tk_units(_s)
          == sum(2 if ord(_ch) > 0xFFFF else 1 for _ch in _s)
          for _s in ('', 'abc', 'a' + chr(0x1F600) + 'b', chr(0xD83D),
                     chr(0x65E5) + chr(0x672C),
                     chr(0x1F468) + chr(0x200D) + chr(0x1F469) + ' ok')))
set_body('')

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
