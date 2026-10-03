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
import note_organizer as NO, tkinter as tk
# A generated click is DISCARDED in silence when its widget is not
# viewable, and the app hides popups whenever another program holds the
# Windows foreground -- which a test process never owns. See
# qa/_qa_support.py; _qa_click refuses to click into the void.
from _qa_support import click as _qa_click, pin_popup_visibility as _qa_pin
_qa_pin(NO)


def open_nested_dropdown(application, btn, cap=60):
    """Open a NESTED dropdown and wait until its popup really exists.

    event_generate silently drops the click while the popup hosting the
    button is not viewable yet — under full-suite load that window is
    real, and reading btn._nested_popup right after the click found None
    and CRASHED the run (the suite's one recurring flake, finally caught
    with its traceback). Wait for the button to map, then click-and-poll,
    hard-capped: a genuine regression returns None into a red check."""
    for _ in range(cap):
        if btn.winfo_ismapped():
            break
        application.update()
        time.sleep(0.02)
    for _ in range(cap):
        _qa_click(btn)
        application.update()
        pop = getattr(btn, '_nested_popup', None)
        if pop is not None and pop.winfo_exists():
            for _ in range(cap):
                if pop.winfo_ismapped():
                    break
                application.update()
                time.sleep(0.02)
            return pop
        time.sleep(0.02)
    return None


def pick_nested_option(application, pop, option_widget, cap=60):
    """Click an option inside a nested dropdown until the pick LANDS.

    Same dropped-click physics as above, one level deeper: the pick
    handler destroys the popup, so 'popup gone' is the observable
    promise that the click was delivered. Capped into a red check."""
    for _ in range(cap):
        try:
            if not pop.winfo_exists():
                return True
            _qa_click(option_widget)
        except tk.TclError:
            return True
        application.update()
        time.sleep(0.02)
    return False
fails = []
def check(name, cond):
    print(('PASS' if cond else 'FAIL'), name)
    if not cond: fails.append(name)

app = NO.NoteOrganizer(); app._poll_active_dirty = lambda: None
app.show_info = lambda *a, **k: True
app.show_warning = lambda *a, **k: True
app.geometry('1100x850'); app.update()

NO.CATEGORY_COLORS.setdefault('Work', '#7c5cff')
NO.CATEGORY_COLORS.setdefault('Personal', '#4cafef')


def find_widget(w, cls, text_contains=None):
    for c in w.winfo_children():
        if isinstance(c, cls):
            if text_contains is None or text_contains in str(c.cget('text')):
                return c
        r = find_widget(c, cls, text_contains)
        if r:
            return r
    return None


def find_dropdown_by_label(w, current_label):
    """Finds the themed-dropdown button Frame currently showing current_label."""
    for c in w.winfo_children():
        if isinstance(c, tk.Frame):
            lbl = find_widget(c, tk.Label)
            if lbl and str(lbl.cget('text')) == current_label:
                return c
        r = find_dropdown_by_label(c, current_label)
        if r:
            return r
    return None


# ============================================================
# BUG 1 + 3: New template — category dropdown used to destroy the whole
# editor and anchor to the wrong place once the editor was gone.
# ============================================================
app._edit_template(None, redraw=lambda: None)
app.update()
editor_popup = app._mini_popup
check('template editor opens', editor_popup is not None and editor_popup.winfo_exists())

name_entry = find_widget(editor_popup, tk.Entry)
name_entry.insert(0, 'MyTemplate')

cat_btn = find_dropdown_by_label(editor_popup, 'General')
check('category dropdown button found in the editor', cat_btn is not None)

dropdown_popup = open_nested_dropdown(app, cat_btn)
check('editor stays open after opening the category dropdown (bug 1)', editor_popup.winfo_exists())
check('nested dropdown popup exists', dropdown_popup is not None and dropdown_popup.winfo_exists())

# ---- Escape in a NESTED dropdown closes just the list (audit Z07-F01) ----
# The placement helper used to rebind <Escape> to the shared
# dismiss-mini-popup, clobbering the nested list's own bind — Escape
# then tore down the template EDITOR the list sits inside.
if dropdown_popup is not None:
    dropdown_popup.focus_force(); app.update()
    # Generate-and-poll: a single Escape after an unpolled focus_force is
    # a one-shot bet on where the focus is; regenerating inside the poll
    # makes the ask deterministic while a real regression still times out
    # into a hard red.
    for _ in range(60):
        if not dropdown_popup.winfo_exists():
            break
        dropdown_popup.event_generate('<Escape>')
        app.update()
        time.sleep(0.02)
    check('Escape closes the nested list itself',
          not dropdown_popup.winfo_exists())
    # The popup we focus_force'd is gone — under full-suite load the
    # focus is then NOWHERE and later generated clicks go astray (the
    # documented dropped-click class). Hand it back before moving on.
    app.focus_force(); app.update()
    check('and the editor underneath SURVIVES it',
          editor_popup.winfo_exists() and app._mini_popup is editor_popup)
    if not editor_popup.winfo_exists():
        # Mutant world (Escape tore the editor down): rebuild it so the
        # rest of the suite still runs and the verdict reaches the
        # footer instead of crashing on dead widgets.
        app._edit_template(None, redraw=lambda: None)
        app.update()
        editor_popup = app._mini_popup
        name_entry = find_widget(editor_popup, tk.Entry)
        name_entry.delete(0, 'end')
        name_entry.insert(0, 'MyTemplate')
        cat_btn = find_dropdown_by_label(editor_popup, 'General')
    # Reopen for the docking checks below, which expect an open list.
    dropdown_popup = open_nested_dropdown(app, cat_btn)
    check('the dropdown reopens after the Escape round',
          dropdown_popup is not None and dropdown_popup.winfo_exists())

app.update_idletasks()
btn_x, btn_y = cat_btn.winfo_rootx(), cat_btn.winfo_rooty()
btn_h = cat_btn.winfo_height()
pop_x, pop_y = dropdown_popup.winfo_rootx(), dropdown_popup.winfo_rooty()
pop_h = dropdown_popup.winfo_height() or dropdown_popup.winfo_reqheight()

# The popup must be docked TO THE BUTTON, which means left edges aligned and
# the popup sitting immediately below it — or immediately above, because
# _place_dropdown_popup deliberately flips upward when there isn't room below
# inside the app window. A plain straight-line distance check can't express
# that: a legitimate flip moves the popup by its own height, so the check
# failed on any window short enough to trigger one (reliably on Windows,
# never on the CI runner's geometry) while the app was behaving correctly.
aligned_x = abs(pop_x - btn_x) <= 40
docked_below = 0 <= (pop_y - (btn_y + btn_h)) <= 40
docked_above = 0 <= (btn_y - (pop_y + pop_h)) <= 40
check('dropdown anchors to the button, not top-left of the window (bug 3)',
      aligned_x and (docked_below or docked_above))

work_lbl = find_widget(dropdown_popup, tk.Label, 'Work')
_picked9 = pick_nested_option(app, dropdown_popup, work_lbl)
check('editor still open after picking a category',
      _picked9 and editor_popup.winfo_exists())

# ---- THE TEMPLATE BODY UNDERSTANDS TABLES ----
# Pasting a table from Excel, Word or a web page into this plain box
# used to drop the structure and keep the words.
_texts9 = []
_stack9 = [editor_popup]
while _stack9:
    _w9 = _stack9.pop()
    if isinstance(_w9, tk.Text):
        _texts9.append(_w9)
    _stack9.extend(_w9.winfo_children())
_body9 = [w for w in _texts9 if int(w.cget('height')) >= 4][0]
check('the body box carries the table-aware paste binding',
      bool(_body9.bind('<<Paste>>')))
_real_rh9 = NO.clipboard.read_html
NO.clipboard.read_html = lambda: (
    '<table><tr><th>Column1</th><th>Column2</th></tr>'
    '<tr><td>2</td><td>3</td></tr></table>')
_body9.delete('1.0', 'end')
_took9 = app._paste_table_aware(_body9)
_lines9 = [l for l in _body9.get('1.0', 'end-1c').split('\n') if l]
check(f'a pasted Excel/web table lands as pipe rows ({_lines9[:1]})',
      _took9 == 'break' and len(_lines9) == 2
      and _lines9[0].count('|') == 3 and 'Column1' in _lines9[0])
NO.clipboard.read_html = lambda: '<p>just text</p>'
check('a non-table paste falls through to the normal path',
      app._paste_table_aware(_body9) is None)

# ---- AND THE DIALOG DRAWS A LIVE TABLE PREVIEW ----
# The body box stays text (that is the store), but the dialog shows the
# table AS a table underneath -- the same visual language as the editor.
NO.clipboard.read_html = lambda: (
    '<table><tr><th>Day</th><th>Plan</th></tr>'
    '<tr><td>mon</td><td>written</td></tr></table>')
_body9.delete('1.0', 'end')
_body9.event_generate('<<Paste>>')
for _ in range(5):
    app.update()
    app.update_idletasks()
_canv9 = []
_stack9 = [editor_popup]
while _stack9:
    _w9 = _stack9.pop()
    if isinstance(_w9, tk.Canvas):
        _canv9.append(_w9)
    _stack9.extend(_w9.winfo_children())
# winfo_manager, not winfo_ismapped: the packing is synchronous, the OS
# mapping is not -- twice the real-Windows run saw the drawn canvas
# still unmapped and called a healthy preview absent.
_pc9 = [c for c in _canv9 if c.winfo_manager() and c.find_all()]
check(f'pasting a table shows the drawn preview '
      f'({len(_pc9[0].find_all()) if _pc9 else 0} items)',
      len(_pc9) == 1 and len(_pc9[0].find_all()) >= 8)
# The body box HOLDS the table but does not SHOW it -- the preview is
# where tables are seen, and raw pipes with merge markers read as noise.
def _n9(v):
    if v is None:
        return 0
    return v[0] if isinstance(v, tuple) else v
_vis9 = _n9(_body9.count('1.0', 'end', 'displaychars'))
_tot9 = _n9(_body9.count('1.0', 'end', 'chars'))
check(f'the body box hides its table text ({_vis9} of {_tot9} visible)',
      _tot9 > 20 and _vis9 < 5)

# Several tables, merges, and length: EVERYTHING is drawn -- the merged
# header as one spanned cell, every row of every table, with a
# scrollbar once the preview outgrows its budget.
# The refresh rides <<Paste>> (virtual, delivered to the widget);
# <KeyRelease> is a real key event and follows the focus, which this
# box does not hold under test. The multi-table body goes through the
# REAL clipboard so the class paste inserts exactly it.
_multi9 = ('free text\n| Table | < |\n| Food | Source |\n'
           '| Meat | beef |\n\n| Day | Plan |\n| mon | writing |\n'
           '| tue | reading |\n| wed | sport |\n| thu | market |\n'
           '| fri | film |\n| sat | a walk |\n| sun | resting |')
NO.clipboard.read_html = lambda: None
app.clipboard_clear()
app.clipboard_append(_multi9)
_body9.delete('1.0', 'end')
_body9.event_generate('<<Paste>>')
app.update()
app.update()
_items9 = len(_pc9[0].find_all())
check(f'every table and every row is drawn ({_items9} items)',
      _items9 == 42)
check('and the preview scrolls once it outgrows its budget',
      getattr(_pc9[0], '_preview_overflows', False)
      and bool(str(_pc9[0].cget('scrollregion'))))

# A WIDE table needs the sideways scrollbar: every column reachable.
NO.clipboard.read_html = lambda: None
app.clipboard_clear()
app.clipboard_append(
    '| Coloana1 | Coloana2 | Coloana3 | Coloana4 | Coloana5 | Coloana6 |'
    ' Coloana7 | Coloana8 |\n'
    '| unsprezece | doisprezece | treisprezece | paisprezece |'
    ' cincisprezece | saisprezece | saptesprezece | optsprezece |')
_body9.delete('1.0', 'end')
_body9.event_generate('<<Paste>>')
app.update()
app.update()
check('a wide table reports sideways overflow for the h-scrollbar',
      getattr(_pc9[0], '_preview_overflows_x', False))

# ---- THE BODY COMPACTS: blank lines glued to hidden tables hide too ----
NO.clipboard.read_html = lambda: None
app.clipboard_clear()
app.clipboard_append('| T | X |\n| a | b |\n\n| Z | P |\n| c | d |\n\n'
                     'the line of text left over')
_body9.delete('1.0', 'end')
_body9.event_generate('<<Paste>>')
app.update()
app.update()
_visC = _n9(_body9.count('1.0', 'end', 'displaychars'))
check(f'blank lines around hidden tables hide with them '
      f'({_visC} visible)',
      _visC <= len('the line of text left over') + 2)

# ---- A THEMED QUESTION IS NEVER BURIED UNDER A -TOPMOST POPUP ----
# The overlay lives in the main window; the popup floats above it. For
# the dialog's duration the popups step back, then return.
_popQ = app._mini_popup
# int(): on X11 the attribute answers as a STRING ('0' is truthy).
check('the popup starts topmost',
      bool(int(_popQ.attributes('-topmost') or 0)))
_steppedQ = app._popups_step_back()
# The -topmost QUERY is only meaningful where a window manager exists
# to honour it: on the CI's Xvfb (X11, no WM) the answer stays stale
# at 1 even after a successful set-to-False -- measured, not assumed.
# The app's own work (dropped + recorded for restore) asserts anywhere.
check('step-back drops topmost and reports the popup '
      f'(in={_popQ in _steppedQ}, '
      f'top={_popQ.attributes("-topmost")!r}, '
      f'n_stepped={len(_steppedQ)})',
      _popQ in _steppedQ
      and (sys.platform != 'win32'
           or not int(_popQ.attributes('-topmost') or 0)))
app._popups_step_forward(_steppedQ)
check('step-forward restores it',
      bool(int(_popQ.attributes('-topmost') or 0)))

# <KeyRelease> is a REAL key event and follows the focus, which this
# box does not hold under test -- the <<Paste>> virtual event delivers
# to the widget it is generated on, so the hide path rides a plain
# paste instead.
NO.clipboard.read_html = lambda: None
app.clipboard_clear()
app.clipboard_append('just one plain line')
_body9.delete('1.0', 'end')
_body9.event_generate('<<Paste>>')
app.update()
app.update()
check('and a table-less body hides it again',
      not any(c.winfo_ismapped() for c in _pc9))
NO.clipboard.read_html = _real_rh9
_body9.delete('1.0', 'end')



save_btn = find_widget(editor_popup, tk.Button, 'Save')
save_btn.invoke()
app.update()
saved_tpl = app.templates[-1] if app.templates else None
check('template actually saved', saved_tpl is not None)
check('saved with the newly-picked category, not the default (bug 1)',
      saved_tpl and saved_tpl.get('category') == 'Work')

# ---- THE DIALOG'S HIDDEN TABLE TEXT IS SAFE FROM THE CARET ----
# A click in a table-only body (which LOOKS empty) landed the caret
# inside the elided rows; typing glued letters onto an invisible pipe
# row, broke the block, and its leftovers surfaced as bare pipe lines.
_tplG = NO.normalize_template({
    'name': 'GuardTpl', 'title': '',
    'body': '| Cap | Doi |\n| --- | --- |\n| a | b |',
    'comments': '', 'category': 'General', 'checklist': [],
})
app.templates.append(_tplG)
app._edit_template(_tplG, lambda: None)
app.update()
app.update()
_popG = app._mini_popup
_txtsG = []
def _walkTG(w):
    for ch in w.winfo_children():
        if isinstance(ch, tk.Text):
            _txtsG.append(ch)
        _walkTG(ch)
_walkTG(_popG)
_bodyG = max(_txtsG, key=lambda t: len(t.get('1.0', 'end')))
_bodyG.focus_force()
for _ in range(60):
    app.update(); app.update_idletasks()
    if app.focus_get() is _bodyG:
        break
    time.sleep(0.01)
_bodyG.mark_set('insert', '1.0')
app.update()
# The guard runs on KeyPress; the class inserts at whatever caret the
# guard left. Emulated in two steps because a synthetic key's %A does
# not reliably insert -- the guard binding itself fires fine.
_bodyG.event_generate('<KeyPress>', keysym='z')
app.update()
_bodyG.insert('insert', 'z')
app.update()
check('typing with the caret in hidden table text herds it to visible',
      _bodyG.get('1.0', 'end-1c').startswith('| Cap | Doi |')
      and 'tblhide' not in _bodyG.tag_names('insert - 1c'))
_bodyG.mark_set('insert', '4.0')
app.update()
_beforeG = _bodyG.get('1.0', 'end-1c')
_bodyG.event_generate('<BackSpace>')
app.update()
check('backspace at the visible edge refuses to eat the hidden table',
      _bodyG.get('1.0', 'end-1c') == _beforeG)

# a MID-text caret survives the refresh that every keystroke schedules
# -- the refresh used to park it at the end unconditionally, scattering
# the letters of an edit to the tail.
_bodyG.mark_set('insert', 'end')
_bodyG.insert('insert', 'tail')
app.update()
_lastG = int(_bodyG.index('end-1c').split('.')[0])
_bodyG.mark_set('insert', '%d.2' % _lastG)
app.update()
_bodyG.event_generate('<KeyRelease>', keysym='M')
for _ in range(3):
    app.update()
check('a mid-text caret survives the keystroke refresh un-yanked',
      str(_bodyG.index('insert')) == '%d.2' % _lastG)

# ---- A FAILING PREVIEW DRAW IS CONTAINED ----
# The draw wipes the canvas FIRST; an exception escaping the refresh
# reached Tk's callback handler and left the dialog half-updated.
_origDraw = type(app)._draw_template_table_preview
def _boomDraw(self, *_a, **_k):
    raise ValueError('boom')
type(app)._draw_template_table_preview = _boomDraw
_hidBefore = len(_bodyG.tag_ranges('tblhide'))
_tkerrs9 = []
_origRep9 = app.report_callback_exception
app.report_callback_exception = lambda *a, **k: _tkerrs9.append(1)
_bodyG.event_generate('<KeyRelease>', keysym='q')
app.update()
app.update()
type(app)._draw_template_table_preview = _origDraw
app.report_callback_exception = _origRep9
check('a failing preview draw is contained, hiding intact',
      not _tkerrs9
      and len(_bodyG.tag_ranges('tblhide')) == _hidBefore)


# ---- THE PREVIEW DRAWS A CELL'S <br> LINES AS LINES ----
_bodyG.delete('1.0', 'end')
_bodyG.insert('1.0', '| Cap | Doi |\n| unu<br>doi | x |')
_bodyG.event_generate('<KeyRelease>', keysym='q')
for _ in range(3):
    app.update()
_pvB = None
_sB = [_popG]
while _sB:
    _wB = _sB.pop()
    if isinstance(_wB, tk.Canvas) and _wB.find_all():
        if _pvB is None or len(_wB.find_all()) > len(_pvB.find_all()):
            _pvB = _wB
    _sB.extend(_wB.winfo_children())
_txB = [_pvB.itemcget(i, 'text') for i in (_pvB.find_all() if _pvB else ())
        if _pvB.type(i) == 'text']
check('the template preview splits a <br> cell into its lines',
      'unu' in _txB and 'doi' in _txB and 'unu<br>doi' not in _txB)

# ---- A TAKEN TEMPLATE NAME ASKS, NEVER SILENTLY OVERWRITES ----
app.templates = [NO.normalize_template({
    'name': 'Shopping', 'title': 'T', 'body': 'old content',
    'comments': '', 'category': 'General', 'checklist': []})]
NO.save_templates(app.templates)
app.new_note()
app.update()
app.title_entry.insert(0, 'Another note')
app.body_text.insert('1.0', 'NEW content')
app.update()
def _ents21(w):
    out = []
    for _chE in w.winfo_children():
        if isinstance(_chE, tk.Entry):
            out.append(_chE)
        out.extend(_ents21(_chE))
    return out
_asksC = []
_origAsk9 = app.ask_yes_no
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), False)[1]
app.save_current_as_template()
app.update()
_entC9 = _ents21(app._mini_popup)[0]
_entC9.delete(0, 'end')
_entC9.insert(0, 'Shopping')
# Synthetic KEY events follow FOCUS; under Xvfb nothing had focused
# the box, so the Return sailed past it. Insist first.
for _tryC in range(40):
    _entC9.focus_force()
    app.update()
    try:
        if app.focus_get() is _entC9:
            break
    except (KeyError, tk.TclError):
        pass
_entC9.event_generate('<Return>')
app.update()
check('saving over a taken name from the editor asks, and No keeps both',
      len(_asksC) == 1
      and len(app.templates) == 1
      and app.templates[0]['body'] == 'old content'
      and app._mini_popup is not None and app._mini_popup.winfo_exists())
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), True)[1]
_entC9 = _ents21(app._mini_popup)[0]
_entC9.delete(0, 'end')
_entC9.insert(0, 'Shopping')
# Synthetic KEY events follow FOCUS; under Xvfb nothing had focused
# the box, so the Return sailed past it. Insist first.
for _tryC in range(40):
    _entC9.focus_force()
    app.update()
    try:
        if app.focus_get() is _entC9:
            break
    except (KeyError, tk.TclError):
        pass
_entC9.event_generate('<Return>')
app.update()
check('Yes replaces the old template, one copy of the name remains',
      [t['name'] for t in app.templates].count('Shopping') == 1
      and app.templates[-1]['body'] == 'NEW content')

# renaming a template onto a neighbour in Settings asks the same way
app.templates.append(NO.normalize_template({
    'name': 'Retete', 'title': '', 'body': 'retetele mele',
    'comments': '', 'category': 'General', 'checklist': []}))
NO.save_templates(app.templates)
app._edit_template(app.templates[-1], lambda: None)
app.update()
_entR9 = _ents21(app._mini_popup)[0]
_entR9.delete(0, 'end')
_entR9.insert(0, 'Shopping')
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), False)[1]
find_widget(app._mini_popup, tk.Button, 'Save').invoke()
app.update()
_names9 = [t['name'] for t in app.templates]
check('renaming onto a neighbour asks too; No leaves no duplicate',
      _names9.count('Shopping') == 1 and 'Retete' in _names9)
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), True)[1]
find_widget(app._mini_popup, tk.Button, 'Save').invoke()
app.update()
_names9 = [t['name'] for t in app.templates]
check('Yes removes the neighbour and keeps one template with that name',
      _names9 == ['Shopping']
      and app.templates[0]['body'] == 'retetele mele')
app.ask_yes_no = _origAsk9
_popG._confirm_dismiss = False
app._dismiss_mini_popup()
app.update()

# ============================================================
# BUG 2: editing an EXISTING template's category (e.g. one created via
# "Save as template" from the note editor) — the change used to silently
# not persist, staying as originally saved.
# ============================================================
existing_tpl = NO.normalize_template({
    'name': 'FromEditor', 'title': 'T', 'body': 'B', 'comments': '',
    'category': 'Personal', 'checklist': [],
})
app.templates = [existing_tpl]
NO.save_templates(app.templates)

app._edit_template(existing_tpl, redraw=lambda: None)
app.update()
editor_popup2 = app._mini_popup

cat_btn2 = find_dropdown_by_label(editor_popup2, 'Personal')
check('editing an existing template shows its current category', cat_btn2 is not None)
dropdown_popup2 = open_nested_dropdown(app, cat_btn2)
check('the category dropdown opened for the existing template',
      dropdown_popup2 is not None)
work_lbl2 = (find_widget(dropdown_popup2, tk.Label, 'Work')
             if dropdown_popup2 is not None else None)
check('the Work option is present in it', work_lbl2 is not None)
if work_lbl2 is not None:
    check('the Work pick landed (popup closed itself)',
          pick_nested_option(app, dropdown_popup2, work_lbl2))

save_btn2 = find_widget(editor_popup2, tk.Button, 'Save')
save_btn2.invoke()
app.update()

reloaded = NO.load_templates()
updated = next((t for t in reloaded if t['name'] == 'FromEditor'), None)
check('category change to an EXISTING template persists to disk (bug 2)',
      updated is not None and updated.get('category') == 'Work')

# ---- CLICK-AWAY CLOSES THE EDITOR, ASKING ONLY WHEN DIRTY ----
# A click elsewhere closes the dialog like any dropdown -- but typed
# work is never lost silently: a change raises a small save-ask first.
import types as _types
_outside = _types.SimpleNamespace(widget=app)


def _entries_in_order9(w):
    out = []
    for ch in w.winfo_children():
        if isinstance(ch, tk.Entry):
            out.append(ch)
        out.extend(_entries_in_order9(ch))
    return out
_asks = []


def _fake_ask(*a, **k):
    _asks.append(a[0] if a else '?')
    return _fake_ask.answer


_real_ask9 = app.ask_yes_no
app.ask_yes_no = _fake_ask
_tplC = NO.normalize_template({
    'name': 'ConfTest', 'title': 'x', 'body': 'body',
    'category': 'General', 'checklist': [],
    'formatting': [{'start': 0, 'end': 2, 'style': 'bold'}]})
app.templates.append(_tplC)
app._edit_template(_tplC, lambda: None)
app.update()
app._maybe_dismiss_mini_popup(_outside)
app.update()
check('an unchanged dialog closes on click-away with no questions',
      app._mini_popup is None and len(_asks) == 0)

_fake_ask.answer = False
app._edit_template(_tplC, lambda: None)
app.update()
_entC = _entries_in_order9(app._mini_popup)
_entC[0].delete(0, 'end')
_entC[0].insert(0, 'ConfTest2')
app._maybe_dismiss_mini_popup(_outside)
app.update()
check('a changed dialog asks, and No closes without saving',
      app._mini_popup is None and len(_asks) == 1
      and app.templates[-1]['name'] == 'ConfTest')

_fake_ask.answer = True
app._edit_template(_tplC, lambda: None)
app.update()
_entC = _entries_in_order9(app._mini_popup)
_entC[0].delete(0, 'end')
_entC[0].insert(0, 'ConfTest2')
app._maybe_dismiss_mini_popup(_outside)
app.update()
check('...and Yes saves the change before closing',
      app._mini_popup is None
      and app.templates[-1]['name'] == 'ConfTest2')
check('a save through the dialog keeps formatting it cannot edit',
      app.templates[-1].get('formatting'))

app._edit_template(app.templates[-1], lambda: None)
app.update()
_entC = _entries_in_order9(app._mini_popup)
_entC[0].delete(0, 'end')
app.show_warning = lambda *a, **k: True
app._maybe_dismiss_mini_popup(_outside)
app.update()
check('Yes with an empty name keeps the dialog open for fixing',
      app._mini_popup is not None)
app._dismiss_mini_popup()
app.update()
app.templates.remove(app.templates[-1])
app.ask_yes_no = _real_ask9

# ============================================================
# THE TEMPLATE EDITOR'S DELETE IS A DRAWN GLYPH (C-21)
# ============================================================
# Every other delete in Settings draws its bin on a canvas; this row was the
# last literal emoji. An emoji is a fixed-colour bitmap, so it stayed the same
# red on all eight themes while the shapes beside it followed the palette --
# and it was red at rest, where the drawn ones are faint until hovered.
# _icon_button records which glyph it drew on the canvas, because a canvas has
# no text to search for the way a Button does.
_tplBin = NO.normalize_template({
    'name': 'BinTest', 'title': 't', 'body': 'b', 'category': 'General',
    'checklist': [{'text': 'one', 'done': False},
                  {'text': 'two', 'done': False}]})
app.templates.append(_tplBin)
app._edit_template(_tplBin, lambda: None)
app.update()


def _all_widgets9(w, acc=None):
    if acc is None:
        acc = []
    for c in w.winfo_children():
        acc.append(c)
        _all_widgets9(c, acc)
    return acc


_tplKids = _all_widgets9(app._mini_popup)
_drawnBins = [w for w in _tplKids if getattr(w, '_icon_kind', None) == 'trash']
_emojiBins = [w for w in _tplKids
              if isinstance(w, tk.Button) and str(w.cget('text')) == '🗑']
check(f'the template checklist rows delete with a drawn bin '
      f'({len(_drawnBins)} found, one per item)', len(_drawnBins) == 2)
check('and no literal emoji bin is left in the dialog', not _emojiBins)
# Faint at rest, like the reference: a list of rows must not read as a column
# of red warnings before anyone has reached for anything. The emoji one was
# self.colors["danger"] always.
if _drawnBins:
    _binColours = {str(w.itemcget(i, 'fill'))
                   for w in _drawnBins[:1]
                   for i in w.find_withtag('glyph')}
    check(f'the bin is drawn faint, not danger-red, at rest ({_binColours})',
          str(app.colors['danger']).lower() not in
          {c.lower() for c in _binColours})

# ============================================================
# ONE PLUS CHARACTER IN THE WHOLE INTERFACE (C-20)
# ============================================================
# Add-buttons were spelled with two different plus signs -- ASCII "+" in four
# places and fullwidth U+FF0B in three, which render at noticeably different
# widths, so panels beside each other looked like they came from different
# apps. Asked of the BUILT widgets rather than of the source, so it covers
# what a person actually sees, and so a new button added later is caught.
_fullwidth = []
for _w in _all_widgets9(app) + _all_widgets9(app._mini_popup):
    try:
        _t = str(_w.cget('text'))
    except tk.TclError:
        continue
    if '＋' in _t:
        _fullwidth.append((_w.winfo_class(), _t[:40]))
check(f'no widget uses a fullwidth plus ({_fullwidth})', not _fullwidth)
# THE CONTROL: the ASCII ones are really there, so the check above is not
# passing because nothing has a plus at all.
_ascii_plus = [str(_w.cget('text')) for _w in _all_widgets9(app._mini_popup)
               if _w.winfo_class() == 'Button'
               and str(_w.cget('text')).startswith('+ ')]
check(f'and the template dialog really does have an ASCII add-button '
      f'({_ascii_plus})', any(t.startswith('+ ') for t in _ascii_plus))

# ============================================================
# THE WORDLESS SETTINGS ICONS EXPLAIN THEMSELVES (C-18)
# ============================================================
# Settings had no hover explanations at all, on the screen where the buttons
# are silent AND the actions are permanent -- a pencil and a bin side by
# side, nothing written on either -- while the formatting toolbar in the
# editor has explained every one of its buttons for a long time. The app
# taught the lesson in one place and broke it in the other.
#
# The words are attached inside _icon_button, keyed by glyph, so this asks
# the CLASS: every drawn icon on screen carries them, including the next one
# added. A per-call-site fix would have left that open.
#
# Asked by _icon_tip and NOT by '<Enter>' in bind(): a clickable icon binds
# <Enter> anyway, for its hover colour, so that question is true whether or
# not any words were ever attached. The first version of this check asked it
# that way and survived a mutant that removed every tooltip in the file --
# noticed only by the padlock, the one icon with no command and therefore no
# hover binding. A check has to name the thing it is about.
_icons = [w for w in _tplKids if getattr(w, '_icon_kind', None) is not None]
_silent = [getattr(w, '_icon_kind', '?') for w in _icons
           if not getattr(w, '_icon_tip', None)]
check(f'every drawn icon in the template dialog explains itself '
      f'({len(_icons)} icons, silent: {_silent})', _icons and not _silent)
app._dismiss_mini_popup()
app.update()
app.templates.remove(_tplBin)

# The same question of the category rows, which carry a pencil, a bin and --
# on a built-in category -- a padlock that is not even clickable. "Why can't
# I rename this one" is exactly what a silent indicator raises.
app.toggle_settings_panel('categories')
app.update()
_cat_icons = [w for w in _all_widgets9(app.settings_categories_panel)
              if getattr(w, '_icon_kind', None) is not None]
_cat_silent = [getattr(w, '_icon_kind', '?') for w in _cat_icons
               if not getattr(w, '_icon_tip', None)]
check(f'and so does every icon on the category rows '
      f'({len(_cat_icons)} icons, silent: {_cat_silent})',
      _cat_icons and not _cat_silent)
# And the words really reach the screen, not just the widget: rest on one and
# wait out the 450ms the tooltip deliberately waits before appearing, so this
# is the feature and not an attribute someone set.
_probe = next((w for w in _cat_icons if getattr(w, '_icon_tip', None)), None)
# Guarded rather than assumed: with the words removed this is None, and an
# unguarded probe would CRASH the script instead of failing it -- which the
# runner's summary still reports as a failure, so the difference is invisible
# in a mutant run and costly in a real one.
check('there is an icon with words to rest on', _probe is not None)
if _probe is not None:
    _probe.event_generate('<Enter>')
    for _ in range(80):
        app.update(); app.update_idletasks(); time.sleep(0.01)
        if getattr(app, '_tooltip', None) is not None:
            break
    _shown = getattr(app, '_tooltip', None)
    _tip_texts = ([str(w.cget('text')) for w in _all_widgets9(_shown)
                   if isinstance(w, tk.Label)]
                  if _shown is not None else [])
    check(f'and resting on one really puts the words on screen '
          f'({_tip_texts})',
          _shown is not None
          and any(getattr(_probe, '_icon_tip') in t for t in _tip_texts))
    _probe.event_generate('<Leave>')
    app.update()
# The theme halves at the bottom of the nav do not go through _icon_button,
# so they are the one place a class fix could not reach.
_mode_btns = list(getattr(app, '_settings_mode_buttons', {}).values())
check(f'the light/dark halves explain themselves too '
      f'({len(_mode_btns)} found)',
      _mode_btns and all('<Enter>' in b.bind() for b in _mode_btns))

# ============================================================
# Same class of bug, second location: the calendar's Jump-to-month popup
# ============================================================
app.notebook.select(app.TAB_CALENDAR)
app.update()
app.open_month_jump()
app.update()
jump_popup = app._mini_popup
check('Jump-to-month popup opens', jump_popup is not None and jump_popup.winfo_exists())

import calendar as cal_module
current_month_name = cal_module.month_name[app.cal_month]
month_btn = find_dropdown_by_label(jump_popup, current_month_name)
check('month dropdown button found', month_btn is not None)
_qa_click(month_btn)
app.update()
check('Jump-to-month popup stays open after opening the month dropdown',
      jump_popup.winfo_exists())

# ============================================================
# DROPDOWN BUTTON TOGGLES: SECOND CLICK CLOSES, NO BLINK
# ============================================================
# Field report: clicking the open filter dropdown's own button blinked
# the list (the shared dismiss closed it and the reopen brought it
# straight back); the only way to close it was clicking elsewhere. The
# button is a real toggle now. (The nested template-editor variant
# deliberately keeps the old behaviour — see open_list's comment.)
app._dismiss_mini_popup(); app.update()
# Earlier sections destroy popups directly (bypassing _dismiss), which
# leaves their click-outside handlers accumulated on the toplevel — and
# a stale one dismisses OUR fresh popup on the very same synthetic
# click. Clear the tag: each open re-installs its own handler anyway.
app.unbind('<Button-1>')
app.notebook.select(app.TAB_NOTES); app.update()
_qa_click(app.filter_menu); app.update()
check('first click opens the filter list',
      app._mini_popup is not None and app._mini_popup.winfo_exists())
_qa_click(app.filter_menu); app.update()
check('second click on the button closes it, no reopen blink',
      app._mini_popup is None)
_qa_click(app.filter_menu); app.update()
check('a third click opens it again', app._mini_popup is not None)
app._dismiss_mini_popup(); app.update()

# ============================================================
# ESCAPE BACKS OUT OF A POPUP -- INCLUDING THE NESTED ONE
# ============================================================
# The binding was always there, on the popup Toplevel, and could never
# fire: these windows are borderless and take no keyboard focus, so Tk
# delivered the key to whatever DID hold it -- the app window, which had
# no Escape binding at all while a popup was open. Measured before it was
# fixed: force the focus inside the popup and the old binding closed it at
# once, so the handler was sound and the key simply went elsewhere.
# Finding C-7.
#
# Every Escape below is generated at the FOCUS window, because that is
# where a real keystroke goes -- qa/_qa_support.py refuses to pretend
# otherwise, which is why fire() rejects keyboard sequences.
#
# The nested case is the one this fix could most easily have broken: the
# comment beside the per-popup binding records an attempt that made Escape
# tear down the HOST editor instead of the list inside it.
app.unbind('<Button-1>')
app.notebook.select(app.TAB_NOTES); app.update()


def _esc_focus_is_on_the_window(cap=60):
    """Put the keyboard on the app window, and say whether it went there.

    Stated rather than assumed, because it is the precondition the whole
    block is about. An earlier section in this file can leave the focus
    inside a leftover Toplevel, and a key delivered there never reaches the
    app window's bindtags at all -- which is how this block failed once and
    passed once with nothing changed but how fast the run happened to be.
    A check whose verdict depends on timing is a bug in the check.
    """
    app.focus_force()
    for _ in range(cap):
        app.update()
        try:
            if app.focus_get() in (None, app):
                return True
        except Exception:
            return False
        time.sleep(0.01)
    try:
        return app.focus_get() in (None, app)
    except Exception:
        return False


def _esc():
    """Press Escape where a person's keystroke lands: the focus window."""
    try:
        _target = app.focus_get()
    except Exception:
        _target = None
    (_target or app).event_generate('<Escape>')
    app.update()


def _esc_labels(widget):
    _found = []

    def _walk(w):
        for _ch in w.winfo_children():
            try:
                _t = str(_ch.cget('text'))
                if _t:
                    _found.append(_t)
            except Exception:
                pass
            _walk(_ch)

    _walk(widget)
    return _found


_esc_notes = list(app.notes)
app.notes = [NO.normalize_note({'id': 9601, 'title': 'EscOne', 'body': 'a'}),
             NO.normalize_note({'id': 9602, 'title': 'EscTwo', 'body': 'b'})]
app.save_notes()
app.refresh_note_list()
app.selection_mode = True
app.selected_note_ids = {9601, 9602}
app._bulk_change_category(); app.update()
check('escape: the bulk category popup opened',
      app._mini_popup is not None and app._mini_popup.winfo_exists())
check('escape: the APP WINDOW carries the binding now, not only the popup',
      bool(app.bind('<Escape>')))
check('escape: the keyboard is on the app window, which is the case under test',
      _esc_focus_is_on_the_window())
_esc()
check('escape: pressing it where the focus is closes the popup',
      app._mini_popup is None)
check('escape: and the app-window binding is taken back off afterwards',
      getattr(app, '_mini_popup_escape_bind', None) is None)

app._bulk_change_category(); app.update()
check('escape: the riskiest popup also has a worded way out now',
      any('Cancel' in _t for _t in _esc_labels(app._mini_popup)))
_esc_cancel = []


def _find_esc_cancel(w):
    for _ch in w.winfo_children():
        try:
            if isinstance(_ch, tk.Button) and 'Cancel' in str(_ch.cget('text')):
                _esc_cancel.append(_ch)
        except Exception:
            pass
        _find_esc_cancel(_ch)


_find_esc_cancel(app._mini_popup)
if _esc_cancel:
    _esc_cancel[0].invoke(); app.update()
check('escape: Cancel closes it and refiles nothing',
      app._mini_popup is None
      and all(_n['category'] == 'General' for _n in app.notes))

app._bulk_export(); app.update()
check('escape: the export popup has a Cancel too',
      app._mini_popup is not None
      and any('Cancel' in _t for _t in _esc_labels(app._mini_popup)))
check('escape: the keyboard is on the window for the export case',
      _esc_focus_is_on_the_window())
_esc()
check('escape: and Escape closes the export popup', app._mini_popup is None)
app.selection_mode = False
app.selected_note_ids = set()

app.open_note_in_tab(app.find_note(9601)); app.update()
app._show_color_palette(app.title_entry, '', lambda c: None); app.update()
check('escape: the colour palette opened', app._mini_popup is not None)
check('escape: the keyboard is on the window for the palette case',
      _esc_focus_is_on_the_window())
_esc()
check('escape: Escape closes the colour palette', app._mini_popup is None)

# The nested case, through the real dropdown and the poller this file
# already uses for the dropped-click physics.
_esc_host = tk.Toplevel(app)
app._mini_popup = _esc_host
_esc_host.wm_overrideredirect(True)
_esc_inner = tk.Frame(_esc_host, bg=app.colors['card'])
_esc_inner.pack()
_esc_var = tk.StringVar(value='General')
_esc_btn = app._build_themed_dropdown(_esc_inner, _esc_var,
                                      ['General', 'Work'],
                                      lambda v: None, nested=True)
_esc_btn.pack()
app._place_dropdown_popup(_esc_host, app.title_entry)
app.update()
check('escape: a host popup with a nested dropdown is up',
      app._mini_popup is _esc_host)
_esc_nested = open_nested_dropdown(app, _esc_btn)
check('escape: the nested list opened', _esc_nested is not None)
check('escape: the host is still what _mini_popup means',
      app._mini_popup is _esc_host)
check('escape: the keyboard is on the window for the nested case',
      _esc_focus_is_on_the_window())
_esc()
check('escape: Escape closes the NESTED list',
      _esc_nested is None or not _esc_nested.winfo_exists())
check('escape: CRITICAL -- and leaves its host standing',
      app._mini_popup is _esc_host and _esc_host.winfo_exists())
check('escape: the keyboard is still on the window for the second press',
      _esc_focus_is_on_the_window())
_esc()
check('escape: a second Escape then closes the host', app._mini_popup is None)

# Escape still belongs to whoever is closer to it: the find bar binds it
# on its own entry and returns "break".
app.open_note_in_tab(app.find_note(9601)); app.update()
app._shortcut_find(); app.update()
check('escape: the find bar is open', getattr(app, '_find_open', False) is True)
app._show_color_palette(app.title_entry, '', lambda c: None); app.update()
check('escape: a popup is open over it', app._mini_popup is not None)
app._find_entry.focus_force()
for _ in range(60):
    app.update()
    if app.focus_get() is app._find_entry:
        break
    time.sleep(0.01)
if app.focus_get() is app._find_entry:
    app._find_entry.event_generate('<Escape>')
    app.update()
    check('escape: with the find entry focused, Escape closes the FIND BAR',
          getattr(app, '_find_open', True) is False)
    check('escape: ...and leaves the popup alone', app._mini_popup is not None)
else:
    # Focus is the one thing a test process cannot demand. Say so rather
    # than pass on a reading that never happened.
    check('escape: SKIPPED -- the find entry never took focus', True)
    print('      (find-bar precedence unverified in this run: no focus)')
app._dismiss_mini_popup(); app.update()
app._close_find() if getattr(app, '_find_open', False) else None
app.notes = list(_esc_notes)
app.save_notes()
app.new_note(); app.update()

# ============================================================
# EVERY BUTTON THAT OPENS A POPUP TOGGLES IT
# ============================================================
# The filter dropdown above was fixed after a field report. Eleven other
# openers had the same shape and never were: a tk.Button acts on the
# RELEASE, the click-outside handler closes the popup on the PRESS, so a
# second click closed the palette and opened a fresh one -- a blink.
def _tg_click(btn):
    """A whole click on a tk.Button as a person makes it: the pointer
    arrives, presses, lets go. A Button runs its command from the release,
    and only for a pointer Tk believes is over it -- hence the Enter
    (qa/README: a bare press+release does not reach the command)."""
    btn.event_generate('<Enter>')
    btn.event_generate('<ButtonPress-1>')
    btn.event_generate('<ButtonRelease-1>')
    app.update()


def _tg_open():
    pop = getattr(app, '_mini_popup', None)
    try:
        return pop is not None and bool(pop.winfo_exists())
    except tk.TclError:
        return False


_tg_saved_notes = list(app.notes)
_tg_saved_templates = list(app.templates)
app.notes = [NO.normalize_note({'id': 9701, 'title': 'Toggle me',
                                'body': 'hello', 'category': 'General'})]
app.templates = [NO.normalize_template({'name': 'A template', 'body': 'x'})]
app.save_notes()
app.refresh_note_list(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()
app.open_note_in_tab(app.notes[0]); app.update()


def _tg_calendar():
    app.notebook.select(app.TAB_CALENDAR); app.update()


def _tg_selecting():
    app.notebook.select(app.TAB_NOTES); app.update()
    if not app.selection_mode:
        app._toggle_selection_mode()
    app.selected_note_ids = {9701}
    app._update_bulk_selected_label()
    app.update()


_tg_buttons = [
    ('the text colour button (A)', lambda: app.text_color_btn, None),
    ('the highlight button (H)', lambda: app.highlight_btn, None),
    ('the emoji button', lambda: app.emoji_btn, None),
    ('the table button', lambda: app.table_btn, None),
    ("the note's date picker", lambda: app.pick_date_btn, None),
    ("the note's colour", lambda: app.color_swatch_btn, None),
    ('Use template', lambda: find_widget(app, tk.Button, 'Use template'), None),
    ("the calendar's month", lambda: app.cal_month_lbl, _tg_calendar),
    ("the selection bar's Category", lambda: app._bulk_category_btn, _tg_selecting),
    ("the selection bar's Export", lambda: app._bulk_export_btn, _tg_selecting),
]
for _tg_label, _tg_get, _tg_setup in _tg_buttons:
    app._dismiss_mini_popup(); app.update()
    # Stale click-outside handlers from earlier sections, cleared the way
    # the dropdown block above does: each open installs its own.
    app.unbind('<Button-1>')
    if _tg_setup is not None:
        _tg_setup()
    _tg_btn = _tg_get()
    if _tg_btn is None or not _tg_btn.winfo_viewable():
        check('toggle: fixture -- %s is on screen' % _tg_label, False)
        continue
    _tg_click(_tg_btn)
    _tg_opened = _tg_open()
    _tg_click(_tg_btn)
    _tg_closed = not _tg_open()
    check('a second click on %s closes its popup instead of reopening it'
          % _tg_label, _tg_opened and _tg_closed)
app._dismiss_mini_popup(); app.update()
if app.selection_mode:
    app._toggle_selection_mode()
app.notebook.select(app.TAB_NOTES); app.update()

# ============================================================
# CTRL+N AND CTRL+F ON THE SETTINGS PAGE
# ============================================================
# Settings is a page swapped in place of the notebook, so the shortcuts
# selected the Notes tab of a notebook that was not on screen: nothing
# visible happened, the hidden editor was cleared or grew an invisible find
# bar, and the keys typed next went nowhere.
app.show_settings_page(); app.update()
app._shortcut_new_note(); app.update()
check('Ctrl+N on the Settings page leaves it for the editor',
      not app._settings_open and app.notebook.winfo_manager() == 'pack'
      and app.settings_page.winfo_manager() == '')
app.show_settings_page(); app.update()
app._shortcut_find(); app.update()
check('Ctrl+F on the Settings page leaves it and opens the find bar',
      not app._settings_open and getattr(app, '_find_open', False))
if getattr(app, '_find_open', False):
    app._close_find()
    app.update()

# ...and a half-written template is asked about, not thrown away. With the
# Calendar tab underneath, the shortcut's tab change dismissed the template
# editor directly -- the text gone without the question a click outside it
# asks.
_tg_asked = []
app.notebook.select(app.TAB_CALENDAR); app.update()
app.show_settings_page(); app.update()
app._edit_template(None, redraw=lambda: None); app.update()
_tg_tpl = app._mini_popup
find_widget(_tg_tpl, tk.Entry).insert(0, 'Half written')
app.ask_yes_no = lambda *a, **k: (_tg_asked.append(a[0]), False)[1]  # No
try:
    app._shortcut_find(); app.update()
finally:
    del app.ask_yes_no
check('a half-written template is asked about before a shortcut takes it away',
      _tg_asked == ['Save changes?'])
check('...and after the answer the shortcut still does its job',
      not app._settings_open and getattr(app, '_find_open', False))
if getattr(app, '_find_open', False):
    app._close_find()
    app.update()
# "Yes, save": the template is kept, and the shortcut carries on. (A new
# template starts out named "Untitled template", so this save succeeds.)
app.show_settings_page(); app.update()
app._edit_template(None, redraw=lambda: None); app.update()
find_widget(app._mini_popup, tk.Text).insert('1.0', 'kept by answering yes')
_tg_count = len(app.templates)
app.ask_yes_no = lambda *a, **k: True                              # Yes, save
try:
    app._shortcut_new_note(); app.update()
finally:
    del app.ask_yes_no
check('...answering Yes saves the template, then the shortcut carries on',
      len(app.templates) == _tg_count + 1 and not app._settings_open)
# ...and a save that cannot happen (the name cleared) leaves the editor
# open for fixing -- and the person with it, on Settings.
app.show_settings_page(); app.update()
app._edit_template(None, redraw=lambda: None); app.update()
_tg_tpl2 = app._mini_popup
find_widget(_tg_tpl2, tk.Entry).delete(0, 'end')
find_widget(_tg_tpl2, tk.Text).insert('1.0', 'a body, and no name')
app.ask_yes_no = lambda *a, **k: True                              # Yes, save
try:
    app._shortcut_new_note(); app.update()
finally:
    del app.ask_yes_no
check('...while a save that cannot happen keeps the editor, and Settings, open',
      app._settings_open and _tg_tpl2.winfo_exists()
      and app._mini_popup is _tg_tpl2)
app._dismiss_mini_popup(); app.update()
app.hide_settings_page(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()

# ============================================================
# THE SMALLEST WINDOW STILL SHOWS A NOTE
# ============================================================
# The sidebar's fixed parts take about 496 pixels of height, so at the old
# minimum (500x400) the list had no room at all: a window with no notes in
# it. Measured and photographed; the minimum now leaves room for a card.
app.notes = [NO.normalize_note({'id': 9702, 'title': 'Still here',
                                'body': 'a note that must be visible',
                                'category': 'General'})]
app.save_notes()
app.refresh_note_list(); app.update()
_ms_w, _ms_h = app.minsize()
app.geometry('%dx%d' % (_ms_w, _ms_h))
for _ in range(30):
    app.update(); time.sleep(0.02)
_ms_order = app._card_order()
_ms_view = app._card_view(_ms_order[0]) if _ms_order else None
_ms_new = find_widget(app, tk.Button, 'New Note')
# Asked of where things ARE, in screen coordinates. The list's own height
# cannot answer it: at the old 500x400 the list still reported 354px,
# running past the bottom of the window, while the New Note button was
# drawn over the card (measured: card 482-571, button from 487). A card
# is visible when it ends above the first button below the list and
# inside the window. The card is a drawing on the list's canvas, so its
# place on screen is the canvas's place plus the card's own, less however
# far the list is scrolled.
_ms_card_bottom = (app.canvas.winfo_rooty()
                   + int(_ms_view['y1'] - app.canvas.canvasy(0))
                   if _ms_view else 10 ** 6)
_ms_limit = min(_ms_new.winfo_rooty() if _ms_new is not None else 10 ** 6,
                app.winfo_rooty() + app.winfo_height())
check('at the smallest size the window allows, a whole note card is on screen '
      '(card ends at %d, room ends at %d)' % (_ms_card_bottom, _ms_limit),
      _ms_view is not None and _ms_new is not None
      and _ms_view['y1'] - _ms_view['y0'] > 1 and _ms_card_bottom <= _ms_limit)
app.geometry('1100x850')
for _ in range(10):
    app.update(); time.sleep(0.02)

# ============================================================
# A DRAG OF THE WINDOW'S EDGE LAYS THE WINDOW OUT ONCE
# ============================================================
# Laying the window out costs more than a step of a drag lasts (measured:
# 260 ms a step on the Calendar), so while the mouse button holds the edge
# the content waits, and is laid out when the drag pauses or the button is
# let go. A script cannot hold the edge -- the drag belongs to Windows --
# so the button is answered for the app, and each promise is asked of the
# layout itself: the width the content was given.
def _rz_width():
    return int(float(app.main_canvas.itemcget(app._main_window_item, 'width')))


def _rz_window():
    return max(app.main_canvas.winfo_width(), app._main_min_width)


# Asked of the real method: the suite pins the answer to "not held" for
# every app it builds (_qa_support.pin_the_desktop), because a click held
# in another program while the tests run would otherwise freeze layouts.
_rz_real = NO.NoteOrganizer._desktop_pointer_button_held
check('the mouse button can be asked, and says no when nobody holds it',
      _rz_real(app) in (False, True)
      and (sys.platform.startswith('win') or _rz_real(app) is False))
_rz_held = {'now': True}
app._pointer_button_held = lambda: _rz_held['now']
# The pause must not land by accident between two steps of the check.
app.RESIZE_PAUSE_MS = 60000
try:
    _rz_before = _rz_width()
    app.geometry('1180x850')
    for _ in range(5):
        app.update_idletasks(); app.update()
    check(f'while the mouse holds the window\'s edge, the layout waits '
          f'({_rz_before} kept, the window is {_rz_window()})',
          _rz_width() == _rz_before != _rz_window()
          and app._resize_watch_job is not None)

    def _rz_wait_for_layout():
        """Until the content has the window's width, or five seconds."""
        _rz_end = time.time() + 5
        while time.time() < _rz_end and _rz_width() != _rz_window():
            app.update(); time.sleep(0.02)

    # The release, as the watch sees it on its next look -- the pause is out
    # of reach, so nothing else can lay the window out.
    _rz_held['now'] = False
    _rz_wait_for_layout()
    check(f'...and letting go lays it out at the new size '
          f'({_rz_width()} for {_rz_window()})',
          _rz_width() == _rz_window())
    # A drag that pauses with the button still down is laid out too. The
    # fixture first: a held step whose layout visibly waits -- a wait that
    # starts before the window has changed is over before it begins, which
    # is how the first version of this check passed with the pause removed.
    _rz_held['now'] = True
    app.geometry('1060x850')
    for _ in range(5):
        app.update_idletasks(); app.update()
    _rz_waiting = _rz_width() != _rz_window()
    app.RESIZE_PAUSE_MS = 50
    app.geometry('1040x850')      # the next step arms the (now short) pause
    for _ in range(2):
        app.update_idletasks(); app.update()
    _rz_wait_for_layout()
    check(f'...and a pause in a held drag lays it out without the release '
          f'({_rz_width()} for {_rz_window()}; it waited first: {_rz_waiting})',
          _rz_waiting and _rz_width() == _rz_window())
    # No button: a maximise, a snap or the keyboard -- at once, as always.
    # Neither timer may stand in for "at once": both are put out of reach.
    _rz_held['now'] = False
    app.RESIZE_PAUSE_MS = 60000
    app.RESIZE_WATCH_MS = 60000
    app.geometry('1120x850')
    app.update_idletasks(); app.update()
    check(f'a resize with no button held is laid out at once '
          f'({_rz_width()} for {_rz_window()})',
          _rz_width() == _rz_window())
    # The calendar's month is one drawing, quick enough to follow the drag
    # (under 40 ms a step), so with it showing a held step is laid out at
    # once -- and the month drawn to the new width. The History register is
    # rows of widgets, and waits with the other pages. Both timers are
    # still out of reach, so neither can stand in for "at once".
    app.notebook.select(app.TAB_CALENDAR)
    for _ in range(5):
        app.update_idletasks(); app.update()
    _rz_held['now'] = True
    app.geometry('1080x850')
    for _ in range(5):
        app.update_idletasks(); app.update()
    _rz_cal_right = max((r['x1'] for r in app._cal_cells.values()), default=0)
    check(f'with the calendar showing, a held drag is laid out at every step '
          f'({_rz_width()} for {_rz_window()}; the month drawn to '
          f'{_rz_cal_right} of {app.cal_canvas.winfo_width()})',
          _rz_width() == _rz_window()
          and abs(_rz_cal_right
                  - (app.cal_canvas.winfo_width() - app.CAL_CELL_PAD)) <= 1)
    app._toggle_calendar_history()
    for _ in range(5):
        app.update_idletasks(); app.update()
    _rz_before = _rz_width()
    app.geometry('1140x850')
    for _ in range(5):
        app.update_idletasks(); app.update()
    check(f'...but the History register waits for the drag, like the other '
          f'pages ({_rz_before} kept, the window is {_rz_window()})',
          app._history_visible and _rz_width() == _rz_before != _rz_window())
    app._toggle_calendar_history()
    _rz_held['now'] = False
    app._lay_out_at_window_size()
    app.notebook.select(app.TAB_NOTES)
    for _ in range(5):
        app.update_idletasks(); app.update()
finally:
    for _rz_attr in ('_pointer_button_held', 'RESIZE_PAUSE_MS', 'RESIZE_WATCH_MS'):
        app.__dict__.pop(_rz_attr, None)
    app._lay_out_at_window_size()

# Tk's window classes come with CS_HREDRAW and CS_VREDRAW, which made
# Windows repaint the whole window on every change of size -- 72 ms a step
# of a drag with nothing even laid out, 10 without. Asked of Windows
# itself, on the classes of the real window and of a widget in it.
if sys.platform.startswith('win'):
    import ctypes as _ws_ct
    _ws_u = _ws_ct.windll.user32
    _ws_u.GetClassLongPtrW.restype = _ws_ct.c_size_t
    _ws_u.GetClassLongPtrW.argtypes = [_ws_ct.c_void_p, _ws_ct.c_int]
    _ws_styles = {}
    for _ws_h in (int(app.wm_frame(), 16), app.main_canvas.winfo_id()):
        _ws_n = _ws_ct.create_unicode_buffer(64)
        _ws_u.GetClassNameW(_ws_ct.c_void_p(_ws_h), _ws_n, 64)
        _ws_styles[_ws_n.value] = _ws_u.GetClassLongPtrW(_ws_h, -26)
    check('Windows no longer repaints the whole window on every change of size '
          '(%s)' % {k: hex(v) for k, v in _ws_styles.items()},
          set(_ws_styles) == {'TkTopLevel', 'TkChild'}
          and all(not (v & 0x3) for v in _ws_styles.values()))
else:
    check('elsewhere the repaint styles are left alone, and asking does not fail',
          app._stop_whole_repaints() is None)
app.geometry('1100x850')
for _ in range(10):
    app.update(); time.sleep(0.02)

app.notes = list(_tg_saved_notes)
app.templates = list(_tg_saved_templates)
app.save_notes()
app.new_note(); app.update()

print()
print(f"=== QA9 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
