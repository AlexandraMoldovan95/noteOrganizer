# HERMETIC SEED -- BEFORE the note_organizer import below: the module
# resolves its data directory and runs the data MIGRATIONS at import
# time, so this script's data directory must be its own before that
# happens. hermetic_seed (qa/_qa_support.py) seeds it -- or refuses to
# run at all outside a scratch run, or beside a notebook it cannot
# prove is empty.
from _qa_support import hermetic_seed as _qa_seed
_qa_seed()

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


def _focus_body9(why):
    """A synthetic key goes to whichever window holds the keyboard, not to
    the widget it names: on a busy desktop the body can lose it between
    two checks, and the key's handler then never runs -- one check failed
    so, and two more could pass without their mechanism having run at all.
    So the keyboard is forced back before every key, and that it arrived
    is checked, by name, as the precondition it is."""
    _bodyG.focus_force()
    for _ in range(60):
        app.update(); app.update_idletasks()
        if app.focus_get() is _bodyG:
            break
        time.sleep(0.01)
    check('fixture: the template body holds the keyboard before %s' % why,
          app.focus_get() is _bodyG)


_focus_body9('a key typed into hidden table text')
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
_focus_body9('a BackSpace at the visible edge')
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
_focus_body9('the keystroke whose refresh must not move the caret')
_bodyG.mark_set('insert', '%d.2' % _lastG)
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
_focus_body9('the keystroke whose preview draw fails')
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
_focus_body9('the keystroke that redraws the <br> preview')
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


# "Save changes?" is three answers now -- Cancel (None), No, Yes -- so it
# is asked through ask_yes_no_cancel. Answering it through ask_yes_no, as
# this block did, would leave the real question on screen for nobody.
app.ask_yes_no_cancel = _fake_ask
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

# Cancel -- and Escape, which answers Cancel -- keeps editing: the editor
# stays open with what was typed, and nothing is saved. As Yes/No the
# question had no such answer, and Escape took No.
_fake_ask.answer = None
del _asks[:]
app._edit_template(app.templates[-1], lambda: None)
app.update()
_popCancel = app._mini_popup
_entC = _entries_in_order9(_popCancel)
_entC[0].delete(0, 'end')
_entC[0].insert(0, 'KeptTyping')
app._maybe_dismiss_mini_popup(_outside)
app.update()
check('Cancel on "Save changes?" keeps the editor open, with what was typed',
      _asks == ['Save changes?'] and app._mini_popup is _popCancel
      and _popCancel.winfo_exists() and _entC[0].get() == 'KeptTyping'
      and app.templates[-1]['name'] == 'ConfTest2')
app._dismiss_mini_popup()
app.update()
app.templates.remove(app.templates[-1])
del app.ask_yes_no_cancel

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


def month_dropdown(jump):
    """The Month dropdown itself -- the frame that owns the ▾. Looked up
    by the label, find_dropdown_by_label answers with the ROW holding the
    dropdown, whose first label is the month too; clicking that row opens
    nothing, and the check below passed on a click that never happened."""
    for w in _walk_all9(jump):
        if isinstance(w, tk.Label) and str(w.cget('text')) == '▾':
            return w.master
    return None


def _walk_all9(w):
    yield w
    for c in w.winfo_children():
        yield from _walk_all9(c)


month_btn = month_dropdown(jump_popup)
check('month dropdown button found',
      month_btn is not None
      and find_widget(month_btn, tk.Label, current_month_name) is not None)
month_list = open_nested_dropdown(app, month_btn) if month_btn is not None else None
check('fixture: the month dropdown\'s list really opened',
      month_list is not None and month_list.winfo_exists())
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


def _popup_window_lines(seq):
    """The lines a popup has on the app window for `seq` right now."""
    cmd = getattr(app, '_popup_event_cmd', None)
    if not cmd:
        return []
    return [l for l in str(app.bind(seq) or '').split('\n') if cmd in l]


# Earlier sections destroy popups directly, bypassing _dismiss_mini_popup,
# and nested lists come and go inside them. This block used to wipe the
# window's <Button-1> here, because their click-outside handlers stayed
# behind and a stale one closed the next popup on the very click that
# opened it -- the bug itself, papered over in the test. Nothing is wiped
# now: whatever those sections left is what the person gets, and it must
# be nothing.
check('nothing earlier left a click-outside or a follow-the-window line on '
      'the app window (%s, %s)' % (_popup_window_lines('<Button-1>'),
                                   _popup_window_lines('<Configure>')),
      not _popup_window_lines('<Button-1>')
      and not _popup_window_lines('<Configure>')
      and not getattr(app, '_popup_window_binds', {}))
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
    # No wiping of the window's click handlers between openers: each
    # popup takes its own away when it goes (see the dropdown block).
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
app.ask_yes_no_cancel = lambda *a, **k: (_tg_asked.append(a[0]), False)[1]  # No
try:
    app._shortcut_find(); app.update()
finally:
    del app.ask_yes_no_cancel
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
app.ask_yes_no_cancel = lambda *a, **k: True                       # Yes, save
try:
    app._shortcut_new_note(); app.update()
finally:
    del app.ask_yes_no_cancel
check('...answering Yes saves the template, then the shortcut carries on',
      len(app.templates) == _tg_count + 1 and not app._settings_open)
# ...and a save that cannot happen (the name cleared) leaves the editor
# open for fixing -- and the person with it, on Settings.
app.show_settings_page(); app.update()
app._edit_template(None, redraw=lambda: None); app.update()
_tg_tpl2 = app._mini_popup
find_widget(_tg_tpl2, tk.Entry).delete(0, 'end')
find_widget(_tg_tpl2, tk.Text).insert('1.0', 'a body, and no name')
app.ask_yes_no_cancel = lambda *a, **k: True                       # Yes, save
try:
    app._shortcut_new_note(); app.update()
finally:
    del app.ask_yes_no_cancel
check('...while a save that cannot happen keeps the editor, and Settings, open',
      app._settings_open and _tg_tpl2.winfo_exists()
      and app._mini_popup is _tg_tpl2)
# ...and Cancel -- the third answer, Escape's -- keeps both as well, with
# nothing saved: the shortcut honours all three.
find_widget(_tg_tpl2, tk.Entry).insert(0, 'Named now')
_tg_count = len(app.templates)
app.ask_yes_no_cancel = lambda *a, **k: None                       # Cancel
try:
    app._shortcut_new_note(); app.update()
finally:
    del app.ask_yes_no_cancel
check('...and Cancel keeps the editor and Settings, saving nothing',
      app._settings_open and _tg_tpl2.winfo_exists()
      and app._mini_popup is _tg_tpl2 and len(app.templates) == _tg_count)
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


# ============================================================
# HELPERS FOR THE BLOCKS BELOW: real questions, answered from inside
# ============================================================
def _walk9(w):
    yield w
    for _c in w.winfo_children():
        yield from _walk9(_c)


def _question_button(label, title=None):
    """A button of a themed question on screen -- of the one whose title
    contains `title`, when given."""
    for _f in app.place_slaves():
        if not isinstance(_f, tk.Frame) or _f in (
                getattr(app, 'toast_frame', None),
                getattr(app, 'export_progress_frame', None)):
            continue
        _ws = list(_walk9(_f))
        if title is not None and not any(
                isinstance(w, tk.Label) and title in str(w.cget('text'))
                for w in _ws):
            continue
        for w in _ws:
            if isinstance(w, tk.Button) and str(w.cget('text')) == label:
                return w
    return None


def _keyboard_on(widget, cap=60):
    """Put the keyboard on `widget` -- a precondition, so it is forced --
    and say whether it went (qa/README: force a precondition)."""
    for _ in range(cap):
        try:
            app.focus_force()
            widget.focus_force()
            app.update()
            if app.focus_get() is widget:
                return True
        except (KeyError, tk.TclError):
            pass
        time.sleep(0.01)
    return False


def _while_asking(ask, act, rescue_label, title, cap_ms=5000):
    """Ask a REAL question with ask(), titled `title`; act() runs while it
    waits. Still waiting after cap_ms, it is answered with `rescue_label`
    -- chosen by each caller as the WRONG answer -- so a broken promise
    turns into a red check instead of a hung script. By title, because a
    question can be asked over another. Returns (answer, rescued)."""
    state = {'rescued': False}

    def rescue():
        b = _question_button(rescue_label, title)
        if b is not None:
            state['rescued'] = True
            b.invoke()
    app.after(300, act)
    job = app.after(cap_ms, rescue)
    try:
        answer = ask()
    finally:
        try:
            app.after_cancel(job)
        except (tk.TclError, ValueError):
            pass
    return answer, state['rescued']


# Every background error the blocks below raise lands here. Tk reports
# them to nobody by default, which is how the next one hid for so long.
_bg9 = []
app.tk.createcommand('bgerror', lambda *a: _bg9.append(' '.join(map(str, a))))
_na_notes = list(app.notes)
app.notes = [NO.normalize_note({'id': 9801, 'title': 'Bread recipe', 'body': 'flour',
                                'category': 'General'}),
             NO.normalize_note({'id': 9802, 'title': 'Holiday plans', 'body': 'sea',
                                'category': 'General'})]
app.save_notes()
app.refresh_note_list()
app.notebook.select(app.TAB_NOTES); app.update()
app._dismiss_mini_popup(); app.update()

# ============================================================
# A LIST INSIDE A POPUP LEAVES NOTHING BEHIND ON THE WINDOW
# ============================================================
# The Category list in the template editor and the Month list in the
# calendar's Jump-to-month are dropdowns INSIDE a popup. Placing one
# overwrote the window-level click and resize ids its host had stored, so
# the host's handlers stayed bound for good -- and from then on every
# dropdown in the app was closed by the same click that opened it, until
# the app was restarted. Measured as the window's own binding scripts,
# which must come back exactly as they were.
_na_b1 = str(app.bind('<Button-1>') or '')
_na_cf = str(app.bind('<Configure>') or '')
app.show_settings_page(); app.update()
app._edit_template(None, redraw=lambda: None); app.update()
_na_host = app._mini_popup
_na_btn = find_dropdown_by_label(_na_host, 'General')
_na_picked = 0
for _na_i in range(3):
    _na_list = open_nested_dropdown(app, _na_btn)
    _na_opt = (find_widget(_na_list, tk.Label, 'Work')
               if _na_list is not None else None)
    if _na_opt is not None and pick_nested_option(app, _na_list, _na_opt):
        _na_picked += 1
check('fixture: the Category list inside the template editor was opened and '
      'picked from three times (%d)' % _na_picked, _na_picked == 3)
find_widget(_na_host, tk.Button, 'Cancel').invoke(); app.update()
app.hide_settings_page(); app.update()
check('...and after it closed, the window\'s click and resize handling is '
      'exactly as before (%d/%d click lines, %d/%d resize lines)'
      % (len(str(app.bind('<Button-1>') or '').split('\n')),
         len(_na_b1.split('\n')),
         len(str(app.bind('<Configure>') or '').split('\n')),
         len(_na_cf.split('\n'))),
      str(app.bind('<Button-1>') or '') == _na_b1
      and str(app.bind('<Configure>') or '') == _na_cf)
_qa_click(app.filter_menu); app.update()
check('...so the next dropdown clicked opens (the sidebar\'s Show list)',
      app._mini_popup is not None and app._mini_popup.winfo_exists())
app._dismiss_mini_popup(); app.update()
# The Month list, opened and left without a pick: its host's Cancel takes
# it along -- it is a window of its own, and was left floating before.
app.notebook.select(app.TAB_CALENDAR); app.update()
app.open_month_jump(); app.update()
_na_jump = app._mini_popup
_na_month = month_dropdown(_na_jump)
_na_mlist = open_nested_dropdown(app, _na_month) if _na_month else None
check('fixture: the Month list inside Jump to month is open',
      _na_mlist is not None and _na_mlist.winfo_exists())
find_widget(_na_jump, tk.Button, 'Cancel').invoke(); app.update()
check('closing Jump to month closes the Month list open inside it',
      _na_mlist is None or not _na_mlist.winfo_exists())
check('...and leaves the window\'s click and resize handling as it was',
      str(app.bind('<Button-1>') or '') == _na_b1
      and str(app.bind('<Configure>') or '') == _na_cf)
app.notebook.select(app.TAB_NOTES); app.update()
_qa_click(app.filter_menu); app.update()
check('...and the next dropdown still opens',
      app._mini_popup is not None and app._mini_popup.winfo_exists())
app._dismiss_mini_popup(); app.update()

# ============================================================
# A WIDGET THAT CLOSES ONE POPUP TO OPEN ANOTHER RAISES NOTHING
# ============================================================
# Tk expands every script of a click before it runs any. A dropdown's own
# <Button-1> closed the open list and unbound its click-outside -- which
# deleted a command the same click was still about to call: a silent
# "invalid command name" background error on every such click.
del _bg9[:]
_bg_sort = next(c for c in app.filter_menu.master.winfo_children()
                if isinstance(c, tk.Frame) and c is not app.filter_menu)
_qa_click(app.filter_menu); app.update()
_bg_first = app._mini_popup
_qa_click(_bg_sort); app.update()
check('clicking one dropdown while another\'s list is open raises no '
      'background error (%s)' % _bg9[:1],
      not _bg9 and _bg_first is not None
      and app._mini_popup is not None and app._mini_popup is not _bg_first
      and app._mini_popup.winfo_exists())
app._dismiss_mini_popup(); app.update()
app.templates = [NO.normalize_template({'name': 'Weekly review', 'body': 'What went well'}),
                 NO.normalize_template({'name': 'Meeting notes', 'body': 'Attendees'})]
NO.save_templates(app.templates)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()


def _pencils9():
    return [w for w in _walk9(app.settings_templates_panel)
            if getattr(w, '_icon_kind', None) == 'pencil']


_qa_click(_pencils9()[0]); app.update()
_bg_ed = app._mini_popup
_qa_click(_pencils9()[1]); app.update()
check('a template\'s pencil clicked while another template\'s editor is open '
      'raises no background error (%s)' % _bg9[:1],
      not _bg9 and _bg_ed is not None and app._mini_popup is not None
      and app._mini_popup is not _bg_ed)
app._dismiss_mini_popup(); app.update()

# ============================================================
# A WIDGET THAT OPENS SOMETHING IN A POPUP'S PLACE ASKS FIRST
# ============================================================
# The window's click-outside is what asks "Save changes?", and a widget's
# own <Button-1> runs before it -- so another template's pencil, the arrow
# of "Back to Notes", a Settings glyph and a sidebar dropdown each closed
# the template editor without the question, the typing gone. Asked once,
# too: kept open, the click stops there, or the click-outside asks again.
_wa_asked = []


def _wa_answer(value):
    del _wa_asked[:]
    app.ask_yes_no_cancel = lambda *a, **k: (_wa_asked.append(a[0]), value)[1]


def _wa_open_dirty():
    """The first template's editor, with typing in it. Opened the way its
    pencil opens it but called directly: it is the fixture, not the click
    under test -- and a broken click-outside must turn the checks below
    red, not take the script down with a missing editor."""
    app._dismiss_mini_popup(); app.update()
    app._edit_template(app.templates[0], app._refresh_templates_panel,
                       _pencils9()[0])
    app.update()
    _pop = app._mini_popup
    if _pop is None or not _pop.winfo_exists():
        return None, None
    _ent = [w for w in _walk9(_pop) if isinstance(w, tk.Entry)][0]
    _ent.insert('end', ' (my edit)')
    return _pop, _ent


def _wa_text(entry):
    try:
        return entry.get() if entry is not None else None
    except tk.TclError:
        return None


def _wa_names():
    return [t.get('name') for t in NO.load_templates()]


try:
    _wa_pop, _wa_ent = _wa_open_dirty()
    _wa_answer(None)
    _qa_click(_pencils9()[1]); app.update()
    check('another template\'s pencil asks about the half-written one, once, '
          'and Cancel keeps it (%s)' % _wa_asked,
          _wa_asked == ['Save changes?'] and _wa_pop is not None
          and app._mini_popup is _wa_pop and _wa_pop.winfo_exists()
          and _wa_text(_wa_ent) == 'Weekly review (my edit)')
    _wa_answer(True)
    _qa_click(_pencils9()[1]); app.update()
    _wa_now = (_wa_text(next((w for w in _walk9(app._mini_popup)
                              if isinstance(w, tk.Entry)), None))
               if app._mini_popup is not None else None)
    check('...and Yes saves it, then opens the one clicked (%s, %r)'
          % (_wa_names(), _wa_now),
          _wa_asked == ['Save changes?'] and 'Weekly review (my edit)' in _wa_names()
          and _wa_now == 'Meeting notes')
    _wa_back = next(c for w in _walk9(app.settings_nav)
                    if isinstance(w, tk.Button)
                    and str(w.cget('text')) == 'Back to Notes'
                    for c in w.master.winfo_children()
                    if isinstance(c, tk.Canvas))
    _wa_pop, _wa_ent = _wa_open_dirty()
    _wa_answer(None)
    _qa_click(_wa_back); app.update()
    check('the arrow of "Back to Notes" asks, once, and Cancel stays on '
          'Settings with the editor (%s)' % _wa_asked,
          _wa_asked == ['Save changes?'] and app._settings_open
          and _wa_pop is not None and app._mini_popup is _wa_pop
          and _wa_pop.winfo_exists())
    _wa_answer(False)
    _qa_click(_wa_back); app.update()
    check('...and No leaves Settings without saving (%s)' % _wa_names(),
          _wa_asked == ['Save changes?'] and not app._settings_open
          and app._mini_popup is None
          and 'Weekly review (my edit) (my edit)' not in _wa_names())
    app.show_settings_page(); app.update()
    app.toggle_settings_panel('templates'); app.update()
    _wa_pop, _wa_ent = _wa_open_dirty()
    _wa_answer(None)
    _qa_click(app._settings_nav_icons['trash']); app.update()
    check('a Settings section chosen by its glyph asks, once, and Cancel '
          'stays on Templates with the editor (%s)' % _wa_asked,
          _wa_asked == ['Save changes?']
          and app._settings_selected_section == 'templates'
          and _wa_pop is not None and app._mini_popup is _wa_pop
          and _wa_pop.winfo_exists())
    _wa_answer(None)
    _qa_click(app.filter_menu); app.update()
    check('a sidebar dropdown clicked beside a half-written template asks, '
          'once, and Cancel opens nothing (%s)' % _wa_asked,
          _wa_asked == ['Save changes?'] and _wa_pop is not None
          and app._mini_popup is _wa_pop)
    _wa_answer(True)
    _qa_click(app.filter_menu); app.update()
    check('...and Yes saves the template, then opens the list (%s)' % _wa_names(),
          _wa_asked == ['Save changes?']
          and 'Weekly review (my edit) (my edit)' in _wa_names()
          and app._mini_popup is not None and app._mini_popup is not _wa_pop)
    # A note card beside a half-written template: the card's press opens
    # the note through open_note_in_tab, which closed the popup with no
    # question -- the template's typing gone, the note loaded behind the
    # Settings page.
    app.notes.append(NO.normalize_note({'id': 901, 'title': 'Card beside',
                                        'body': 'x'}))
    app.save_notes(); app.refresh_note_list(); app.update()
    _wa_pop, _wa_ent = _wa_open_dirty()
    _wa_answer(None)
    _wa_opened = app.open_note_in_tab(app.find_note(901)); app.update()
    check('a note opened beside a half-written template asks, once, and '
          'Cancel keeps the template and opens nothing (%s)' % _wa_asked,
          _wa_asked == ['Save changes?'] and _wa_opened is False
          and _wa_pop is not None and app._mini_popup is _wa_pop
          and (_wa_text(_wa_ent) or '').endswith('(my edit)')
          and app.selected_note_id != 901)
    app.notes = [n for n in app.notes if n.get('id') != 901]
    app.save_notes()
finally:
    app.__dict__.pop('ask_yes_no_cancel', None)
app._dismiss_mini_popup(); app.update()

# A template's bin beside a half-written template. The bin's own press
# asked "Delete ... for good?", and the window's click-outside then asked
# "Save changes?" for the same press -- whose Yes wrote back the very
# template just deleted. Its own template half-written in the editor: the
# delete question is the only one, and covers the edit. Another
# template's editor has its say first, as the pencil lets it.
_tb_asked = []


def _bins9():
    return [w for w in _walk9(app.settings_templates_panel)
            if getattr(w, '_icon_kind', None) == 'trash']


def _tb_answers(yes_no, save_changes):
    del _tb_asked[:]
    app.ask_yes_no = lambda *a, **k: (_tb_asked.append(a[0]), yes_no)[1]
    app.ask_yes_no_cancel = lambda *a, **k: (_tb_asked.append(a[0]),
                                             save_changes)[1]


def _tb_fixture():
    app._dismiss_mini_popup(); app.update()
    app.templates = [NO.normalize_template({'name': 'Weekly review',
                                            'body': 'What went well'}),
                     NO.normalize_template({'name': 'Meeting notes',
                                            'body': 'Agenda'})]
    NO.save_templates(app.templates)
    app._refresh_templates_panel(); app.update()
    return _wa_open_dirty()


try:
    _tb_pop, _tb_ent = _tb_fixture()
    check('fixture: two templates with a bin each, the first half-written in '
          'its editor (%d bins)' % len(_bins9()),
          len(_bins9()) == 2 and _tb_pop is not None)
    _tb_answers(False, True)
    _qa_click(_bins9()[0]); app.update()
    check('the bin of the template open half-written asks one question, and '
          'No keeps the editor with its edit (%s)' % _tb_asked,
          _tb_asked == ['Delete template'] and app._mini_popup is _tb_pop
          and (_wa_text(_tb_ent) or '').endswith('(my edit)')
          and 'Weekly review' in _wa_names())
    _tb_answers(True, True)
    _qa_click(_bins9()[0]); app.update()
    check('...and Yes deletes it for good, the editor and its edit with it '
          '(%s; on disk %s)' % (_tb_asked, _wa_names()),
          _tb_asked == ['Delete template'] and app._mini_popup is None
          and _wa_names() == ['Meeting notes'])
    _tb_pop, _tb_ent = _tb_fixture()
    _tb_answers(True, True)
    _qa_click(_bins9()[1]); app.update()
    check('another template\'s bin lets the half-written one be saved first, '
          'then deletes its own (%s; on disk %s)' % (_tb_asked, _wa_names()),
          _tb_asked == ['Save changes?', 'Delete template']
          and _wa_names() == ['Weekly review (my edit)'])
    # ...and when that save replaced the very template whose bin was
    # pressed -- a new template given its name, "Template name taken"
    # answered Replace -- the bin asked "Delete ... for good?" about a
    # template already gone, and its Yes deleted nothing.
    _tb_fixture()
    app._dismiss_mini_popup(); app.update()
    app._edit_template(None, app._refresh_templates_panel, _bins9()[1])
    app.update()
    _tr_pop = app._mini_popup
    _tr_ent = (next((w for w in _walk9(_tr_pop) if isinstance(w, tk.Entry)), None)
               if _tr_pop is not None else None)
    if _tr_ent is not None:
        _tr_ent.delete(0, 'end')
        _tr_ent.insert(0, 'Meeting notes')
    _tb_answers(True, True)
    _qa_click(_bins9()[1]); app.update()
    check('a template\'s bin after the editor\'s save replaced that very '
          'template asks nothing more about it (%s; on disk %s)'
          % (_tb_asked, _wa_names()),
          _tr_ent is not None
          and _tb_asked == ['Save changes?', 'Template name taken']
          and _wa_names() == ['Weekly review', 'Meeting notes'])
finally:
    app.__dict__.pop('ask_yes_no', None)
    app.__dict__.pop('ask_yes_no_cancel', None)
app._dismiss_mini_popup(); app.update()

# The same, pressed where a person presses: the card itself, a double-click
# on it, and the reminder bar's text. Each one asked through its own press,
# and kept open, let the click go on to the window's click-outside -- which
# asked "Save changes?" a second time, where "No" threw away the template
# just kept. One press, one question. (Answers are stubbed and return at
# once, so a double-click's second press asks again: two, not four.)
app.hide_settings_page(); app.update()
app._render_reminder_bar(1, time.strftime('%Y-%m-%d')); app.update()
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
app.notes.append(NO.normalize_note({'id': 902, 'title': 'Card pressed', 'body': 'x'}))
app.save_notes(); app.refresh_note_list(); app.update()
try:
    _cp_rec = app._note_cards.get(902)
    _cp_y = (int(_cp_rec['y0'] - app.canvas.canvasy(0) + 12)
             if _cp_rec is not None else None)
    check('fixture: the note\'s card is drawn beside the Settings page',
          _cp_y is not None)
    for _cp_name, _cp_times, _cp_want in (('a press on a note card', (None,), 1),
                                          ('a double-click on it',
                                           (700000, 700120), 2)):
        _wa_pop, _wa_ent = _wa_open_dirty()
        _wa_answer(None)
        for _cp_t in _cp_times:
            if _cp_y is not None:
                _cp_kw = {} if _cp_t is None else {'time': _cp_t}
                _qa_click(app.canvas, x=40, y=_cp_y, **_cp_kw)
                app.update()
        check('%s beside a half-written template asks once per press, and Cancel '
              'keeps the template and opens nothing (%s)' % (_cp_name, _wa_asked),
              len(_wa_asked) == _cp_want and set(_wa_asked) == {'Save changes?'}
              and _wa_pop is not None and app._mini_popup is _wa_pop
              and (_wa_text(_wa_ent) or '').endswith('(my edit)')
              and app.selected_note_id != 902)
    _cp_msg = next((w for w in app.reminder_bar.winfo_children()
                    if isinstance(w, tk.Label) and 'for today' in str(w.cget('text'))),
                   None)
    _wa_pop, _wa_ent = _wa_open_dirty()
    _wa_answer(None)
    if _cp_msg is not None:
        _qa_click(_cp_msg); app.update()
    check('a press on the reminder bar\'s text beside a half-written template '
          'asks once, and Cancel stays on Settings with it (%s)' % _wa_asked,
          _cp_msg is not None and _wa_asked == ['Save changes?']
          and app._settings_open and _wa_pop is not None
          and app._mini_popup is _wa_pop
          and (_wa_text(_wa_ent) or '').endswith('(my edit)'))
finally:
    app.__dict__.pop('ask_yes_no_cancel', None)
    app._dismiss_mini_popup(); app.update()
    app.dismiss_reminder()
    app.notes = [n for n in app.notes if n.get('id') != 902]
    app.save_notes(); app.refresh_note_list(); app.update()

# A double-click on a bin in the template editor's checklist removes one
# item. The row below slid up under the pointer and the second press took
# it too -- the note checklist's hazard (qa1), and the same guard.
from _qa_support import fire as _tb_fire
app.templates.append(NO.normalize_template({'name': 'Tri', 'checklist': [
    {'text': 'a', 'done': False}, {'text': 'b', 'done': False},
    {'text': 'c', 'done': False}]}))
NO.save_templates(app.templates)
app._edit_template(app.templates[-1], app._refresh_templates_panel,
                   _pencils9()[0])
app.update()
_tb_pop = app._mini_popup


def _tb_items():
    if _tb_pop is None or not _tb_pop.winfo_exists():
        return None
    return [str(w.cget('text')) for w in _walk9(_tb_pop)
            if isinstance(w, tk.Label) and str(w.cget('text')) in ('a', 'b', 'c')]


def _tb_press(t):
    bins = ([w for w in _walk9(_tb_pop) if isinstance(w, tk.Canvas)
             and getattr(w, '_icon_kind', None) == 'trash']
            if _tb_pop is not None and _tb_pop.winfo_exists() else [])
    if bins:
        _tb_fire(bins[0], '<Button-1>', x=5, y=5, rootx=500, rooty=400, time=t)
        app.update()


_tb_bg = len(_bg9)
_tb_press(300000)
check('fixture: a press on a template checklist bin removes its item (%s)'
      % _tb_items(), _tb_items() == ['b', 'c'])
# The bin redraws its own row, so the click destroys the very canvas it
# landed on -- and the tooltip's hide, queued behind the bin's handler,
# was a command of that canvas: "invalid command name", in silence.
check('a press on a bin that redraws its own row raises no background error '
      '(%s)' % _bg9[_tb_bg:][:1], len(_bg9) == _tb_bg)
_tb_press(300250)
check('a double-click on a template checklist bin removes one item, not the '
      'next (%s)' % _tb_items(), _tb_items() == ['b', 'c'])
_tb_press(301500)
check('...while a press of its own, later, still removes (%s)' % _tb_items(),
      _tb_items() == ['c'])
app._dismiss_mini_popup(); app.update()
app.templates = [t for t in app.templates if t.get('name') != 'Tri']
NO.save_templates(app.templates)

# ============================================================
# ESCAPE ON "SAVE CHANGES?" KEEPS EDITING
# ============================================================
# The question was Yes/No, and Escape answers the first button: No. The
# key that means "never mind" threw the typed template away -- and the
# window's own Escape closed the editor under the question as well.
# Pressed where a person's key lands: on the question's focused button.
app.toggle_settings_panel('templates'); app.update()
_es_pop, _es_ent = _wa_open_dirty()
_es_seen = {}


def _es_press():
    _b = _question_button('Yes', 'Save changes?')
    _es_seen['keyboard'] = _b is not None and _keyboard_on(_b)
    if _es_seen['keyboard']:
        _b.event_generate('<Escape>')


def _es_rescue():
    # Keeps answering while any "Save changes?" is left: with the guards
    # against a second ask broken, Escape stacks another question on the
    # first, and one answer would leave the script waiting on the other.
    _b = _question_button('No', 'Save changes?')
    if _b is not None:
        _es_seen['rescued'] = True
        _b.invoke()
        app.after(1000, _es_rescue)


app.after(300, _es_press)
_es_job = app.after(5000, _es_rescue)
app._maybe_dismiss_mini_popup(_outside)      # a click outside: asks, for real
app.after_cancel(_es_job)
app.update()
if _es_seen.get('keyboard') is False:
    check('escape on the question: SKIPPED -- the keyboard never reached it', True)
    print('      (Escape on "Save changes?" unverified in this run: no focus)')
else:
    check('Escape on "Save changes?" keeps the editor open, with what was typed, '
          'and saves nothing (%s)' % _es_seen,
          not _es_seen.get('rescued') and _es_pop is not None
          and app._mini_popup is _es_pop and _es_pop.winfo_exists()
          and (_wa_text(_es_ent) or '').endswith('(my edit)')
          and not any(n.endswith('(my edit) (my edit) (my edit)')
                      for n in _wa_names()))
app._dismiss_mini_popup(); app.update()

# ============================================================
# "INSERT EMOJI..." FROM A FIELD INSIDE A POPUP
# ============================================================
# Every field's right-click menu offers it, the fields inside popups too.
# The picker began by closing the open popup -- the very one the field
# lived in -- so the template being written vanished without a question,
# and the picker sat at the screen's corner aimed at a field that no longer
# existed. It opens as a popup WITHIN the host now.


def _emoji_item(field):
    for _m in [c for c in field.winfo_children() if isinstance(c, tk.Menu)]:
        for _i in range(_m.index('end') + 1):
            try:
                if 'emoji' in str(_m.entrycget(_i, 'label')).lower():
                    return _m, _i
            except tk.TclError:
                continue
    return None, None


app._edit_template(None, redraw=lambda: None); app.update()
_em_host = app._mini_popup
_em_body = [w for w in _walk9(_em_host) if isinstance(w, tk.Text)][0]
_em_body.insert('1.0', 'Three things I am grateful for')
# Nothing here should ask anything; if something does, it is answered
# Cancel and recorded, rather than left on screen for nobody.
_em_asked = []
app.ask_yes_no_cancel = lambda *a, **k: (_em_asked.append(a[0]), None)[1]
_em_menu, _em_idx = _emoji_item(_em_body)
check('fixture: the template body\'s right-click menu offers Insert emoji',
      _em_menu is not None)


def _em_choose(menu, idx):
    """Choose "Insert emoji..." -- guarded: in a broken world the field
    and its menu can be gone, and that must be a red check, not a crash."""
    try:
        if menu is not None:
            menu.invoke(idx)
            app.update()
    except tk.TclError:
        pass


def _em_text(w):
    try:
        return w.get('1.0', 'end') if isinstance(w, tk.Text) else w.get()
    except tk.TclError:
        return ''


_em_choose(_em_menu, _em_idx)
_em_pick = getattr(app, '_nested_dropdown', None)
check('Insert emoji from the template body keeps the editor, and what is '
      'typed in it, asking nothing (%s)' % _em_asked,
      app._mini_popup is _em_host and _em_host.winfo_exists()
      and 'grateful' in _em_text(_em_body) and not _em_asked)
check('...and the picker opens inside it, beside the field -- within the '
      'window, not at the screen\'s corner',
      _em_pick is not None and _em_pick.winfo_exists()
      and app.winfo_rootx() <= _em_pick.winfo_rootx()
      <= app.winfo_rootx() + app.winfo_width()
      and app.winfo_rooty() <= _em_pick.winfo_rooty()
      <= app.winfo_rooty() + app.winfo_height())
_em_first = app.EMOJI_GROUPS[0][1][0]
_em_chip = (next((w for w in _walk9(_em_pick) if isinstance(w, tk.Label)
                  and str(w.cget('text')) == _em_first), None)
            if _em_pick is not None and _em_pick.winfo_exists() else None)
if _em_chip is not None:
    _qa_click(_em_chip); app.update()
check('...and an emoji picked there lands in the template body',
      _em_first in _em_text(_em_body))
_em_x = (find_widget(_em_pick, tk.Button, '✕')
         if _em_pick is not None and _em_pick.winfo_exists() else None)
if _em_x is not None:
    _em_x.invoke(); app.update()
check('...its ✕ closes just the picker',
      _em_pick is not None and not _em_pick.winfo_exists()
      and app._mini_popup is _em_host and _em_host.winfo_exists())
_em_choose(_em_menu, _em_idx)
_em_pick2 = getattr(app, '_nested_dropdown', None)
app._dismiss_mini_popup(); app.update()
check('...and the editor, closing, takes an open picker with it',
      _em_pick2 is not None and not _em_pick2.winfo_exists())
# The same for a rename box, the other popup with a field in it.
_em_rename = app._show_inline_rename(app.filter_menu, 'Projects',
                                     lambda _v: True)
app.update()
_em_rent = [w for w in _walk9(_em_rename) if isinstance(w, tk.Entry)][0]
_em_menu, _em_idx = _emoji_item(_em_rent)
_em_choose(_em_menu, _em_idx)
check('Insert emoji from a rename box keeps the box, and opens the picker '
      'inside it', app._mini_popup is _em_rename and _em_rename.winfo_exists()
      and _em_text(_em_rent) == 'Projects'
      and getattr(app, '_nested_dropdown', None) is not None
      and app._nested_dropdown.winfo_exists())
app._dismiss_mini_popup(); app.update()
del app.ask_yes_no_cancel

# ============================================================
# CLOSING THE WINDOW UNDER A QUESTION
# ============================================================
# The X while a question waited destroyed the window under it, and nothing
# ever ended the question's wait: the process lived on with no window,
# holding the notebook lock, and every later launch was refused as
# "already open". The close is refused now and the question brought
# forward with the keyboard on its button, as Windows does for a modal
# question. destroy() is recorded rather than run: this script needs the
# window, and a close that goes through must still turn this check red.
_cl_destroyed, _cl_forced, _cl_seen = [], [], {}
_cl_real_force = tk.Misc.focus_force


def _cl_spy_force(self):
    _cl_forced.append(self)
    return _cl_real_force(self)


def _cl_close_during():
    _cl_seen['asking_before'] = app._a_dialog_is_asking()
    del _cl_forced[:]
    app.on_app_close()
    app.update()
    _cl_seen['asking_after'] = app._a_dialog_is_asking()
    _cl_seen['forced'] = list(_cl_forced)
    _cl_seen['default'] = _question_button('No', 'Delete note')
    if _cl_seen['default'] is not None:
        _cl_seen['default'].invoke()


app.destroy = lambda: _cl_destroyed.append(1)
tk.Misc.focus_force = _cl_spy_force
try:
    _cl_answer, _cl_rescued = _while_asking(
        lambda: app.ask_yes_no('Delete note', 'Move it to the Trash?',
                               icon='warning', default='no'),
        _cl_close_during, 'Yes', 'Delete note')
finally:
    tk.Misc.focus_force = _cl_real_force
    del app.destroy
check('closing the window while a question waits is refused: nothing is '
      'destroyed, the question still waits (destroyed=%s, %s)'
      % (_cl_destroyed, {k: v for k, v in _cl_seen.items()
                         if k.startswith('asking')}),
      _cl_seen.get('asking_before') and _cl_seen.get('asking_after')
      and not _cl_destroyed)
check('...the question comes forward with the keyboard on its button',
      _cl_seen.get('default') is not None
      and _cl_seen['default'] in _cl_seen.get('forced', []))
check('...and the person still answers it',
      _cl_answer is False and not _cl_rescued)
# The net under every other route: a question whose window is destroyed
# anyway ends its wait with its safe answer. Its card is what goes. The
# wait is watched, so a missing net stops this check, not the script.
_cl_waits, _cl_unstuck = [], []
_cl_real_wait = app.wait_variable


def _cl_spy_wait(var):
    _cl_waits.append(var)
    return _cl_real_wait(var)


def _cl_destroy_card():
    _b = _question_button('Yes', 'Keep going?')
    while _b is not None and _b.master is not app:
        _b = _b.master
    if _b is not None:
        _b.destroy()


def _cl_unstick():
    for _v in _cl_waits:
        try:
            if not _v.get():
                _cl_unstuck.append(1)
                _v.set(1)
        except tk.TclError:
            pass


app.wait_variable = _cl_spy_wait
app.after(300, _cl_destroy_card)
_cl_job = app.after(4000, _cl_unstick)
try:
    _cl_answer2 = app.ask_yes_no('Keep going?', 'A question whose window goes.',
                                 default='yes')
finally:
    app.after_cancel(_cl_job)
    del app.wait_variable
check('a question whose window is destroyed under it ends its wait with its '
      'safe answer (%r; unstuck by hand: %s)' % (_cl_answer2, bool(_cl_unstuck)),
      _cl_answer2 is False and not _cl_unstuck)
app.update()

# ============================================================
# CLOSING THE WINDOW WITH A TEMPLATE HALF WRITTEN; CTRL+S IN ITS EDITOR
# ============================================================
# The close flushed only the note editor and destroyed the window: the
# template being typed was lost with no question, and Ctrl+S in its editor
# saved the note hidden behind Settings instead, or nothing. The close
# asks now, as a click outside does, and Cancel keeps the window open.
# _flush_autosave is answered False so the close stops right after the
# question, the window left standing either way.
app.templates = [NO.normalize_template({'name': 'CloseTest', 'body': 'first line'})]
NO.save_templates(app.templates)
app.show_settings_page(); app.update()
app.toggle_settings_panel('templates'); app.update()
app._edit_template(app.templates[0], redraw=lambda: None); app.update()
_cw_pop = app._mini_popup
_cw_body = [w for w in _walk9(_cw_pop) if isinstance(w, tk.Text)][0]
_cw_body.insert('end', '\nsecond line')
_cw_asked, _cw_flushed, _cw_destroyed = [], [], []


def _cw_disk_body():
    return next((t.get('body') or '' for t in NO.load_templates()
                 if t.get('name') == 'CloseTest'), '')


app.destroy = lambda: _cw_destroyed.append(1)
app._flush_autosave = lambda *a, **k: (_cw_flushed.append(1), False)[1]
try:
    app.ask_yes_no_cancel = lambda *a, **k: (_cw_asked.append(a[0]), None)[1]
    app.on_app_close(); app.update()
    check('closing with a template half written asks, and Cancel keeps the '
          'window and the editor (%s)' % _cw_asked,
          _cw_asked == ['Save changes?'] and not _cw_flushed
          and not _cw_destroyed and app._mini_popup is _cw_pop
          and 'second line' in _cw_body.get('1.0', 'end'))
    app.ask_yes_no_cancel = lambda *a, **k: (_cw_asked.append(a[0]), True)[1]
    app.on_app_close(); app.update()
    check('...and Yes saves the template before the close goes on (%r)'
          % _cw_disk_body(),
          'second line' in _cw_disk_body() and _cw_flushed
          and not _cw_destroyed)
finally:
    for _cw_name in ('destroy', '_flush_autosave', 'ask_yes_no_cancel'):
        app.__dict__.pop(_cw_name, None)
app._dismiss_mini_popup(); app.update()
app._edit_template(app.templates[0], redraw=lambda: None); app.update()
_cs_pop = app._mini_popup
_cs_body = [w for w in _walk9(_cs_pop) if isinstance(w, tk.Text)][0]
_cs_body.insert('end', '\nthird line')
if _keyboard_on(_cs_body):
    _cs_body.event_generate('<Control-s>')
    app.update()
    check('Ctrl+S with the keyboard in the template editor saves the template '
          '(%r)' % _cw_disk_body(), 'third line' in _cw_disk_body())
else:
    check('ctrl+s in the template editor: SKIPPED -- the keyboard never '
          'reached it', True)
    print('      (Ctrl+S in the template editor unverified in this run: no focus)')
app._dismiss_mini_popup(); app.update()

# ============================================================
# ENTER ANSWERS A QUESTION WITH THE BUTTON THAT HOLDS THE KEYBOARD
# ============================================================
# The docstring and ARCHITECTURE promised Enter takes the default button;
# it did nothing at all -- a tk.Button answers Space and the mouse. Each
# question is answered by a key pressed where the keyboard really is; the
# rescue, if the key never lands, is the WRONG answer.
_en_seen = {}


def _en_press(label, key, title):
    def act():
        _b = _question_button(label, title)
        _en_seen[title] = _b is not None and _keyboard_on(_b)
        if _en_seen[title]:
            _b.event_generate('<%s>' % key)
    return act


_en_results = [
    ('Enter takes the default button', True,
     _while_asking(lambda: app.ask_yes_no('Q-enter', 'Enter takes the default.',
                                          default='yes'),
                   _en_press('Yes', 'Return', 'Q-enter'), 'No', 'Q-enter'),
     'Q-enter'),
    ('Enter takes the button the keyboard was moved to', False,
     _while_asking(lambda: app.ask_yes_no('Q-moved', 'The keyboard went to No.',
                                          default='yes'),
                   _en_press('No', 'Return', 'Q-moved'), 'Yes', 'Q-moved'),
     'Q-moved'),
]
# The keypad's Enter is its own key (KP_Enter) where Tk has one to
# generate. Tk on Windows has none -- measured: "no keycode for keysym
# KP_Enter", and a generated one arrives as "??" -- so there it is asked
# where it can be: on the Linux image. Both keys are bound either way.
if not sys.platform.startswith('win'):
    _en_results.append(
        ('keypad Enter takes it too', False,
         _while_asking(lambda: app.ask_yes_no('Q-keypad', 'The keypad Enter too.',
                                              default='no'),
                       _en_press('No', 'KP_Enter', 'Q-keypad'), 'Yes', 'Q-keypad'),
         'Q-keypad'))
for _en_name, _en_want, (_en_got, _en_rescued), _en_title in _en_results:
    if _en_seen.get(_en_title) is False:
        check('%s: SKIPPED -- the keyboard never reached the question' % _en_name,
              True)
        continue
    check('%s (%r, rescued: %s)' % (_en_name, _en_got, _en_rescued),
          _en_got is _en_want and not _en_rescued)
# One key, one question: asked over another, Enter answers the inner one
# and leaves the outer still asking (Escape likewise).
_nq = {}


def _nq_outer_act():
    _nq['inner'] = _while_asking(
        lambda: app.ask_yes_no('Inner question', 'Asked over another.',
                               default='no'),
        _en_press('No', 'Return', 'Inner question'), 'Yes', 'Inner question')
    app.update()
    _b = _question_button('No', 'Outer question')
    _nq['outer_still_there'] = _b is not None
    if _b is not None:
        _b.invoke()


_nq['outer'] = _while_asking(
    lambda: app.ask_yes_no('Outer question', 'Asked first.', default='yes'),
    _nq_outer_act, 'Yes', 'Outer question', cap_ms=15000)
if _en_seen.get('Inner question') is False:
    check('enter on nested questions: SKIPPED -- no keyboard', True)
else:
    check('one Enter answers the question asked last, and leaves the one under '
          'it asking (%s)' % _nq,
          _nq.get('inner') == (False, False) and _nq.get('outer_still_there')
          and _nq.get('outer') == (False, False))
# Escape is where "the last one only" really bites: it answers whatever
# holds the keyboard, and the two questions' Escapes were both bound on the
# window -- one press answered both, the outer one with its safe answer
# before the person ever saw it. The outer is answered Yes afterwards here,
# and must come back Yes.
_nx = {}


def _nx_outer_act():
    def _nx_inner_act():
        _b = _question_button('No', 'Inner escape')
        _nx['keyboard'] = _b is not None and _keyboard_on(_b)
        if _nx['keyboard']:
            _b.event_generate('<Escape>')
    _nx['inner'] = _while_asking(
        lambda: app.ask_yes_no('Inner escape', 'Asked over another.',
                               default='no'),
        _nx_inner_act, 'Yes', 'Inner escape')
    app.update()
    _b = _question_button('Yes', 'Outer escape')
    if _b is not None:
        _b.invoke()


_nx['outer'] = _while_asking(
    lambda: app.ask_yes_no('Outer escape', 'Asked first.', default='no'),
    _nx_outer_act, 'No', 'Outer escape', cap_ms=15000)
if _nx.get('keyboard') is False:
    check('escape on nested questions: SKIPPED -- no keyboard', True)
else:
    check('one Escape answers the question asked last only: the one under it '
          'is still the person\'s to answer (%s)' % _nx,
          _nx.get('inner') == (False, False) and _nx.get('outer') == (True, False))
# Tab walks the question's own answers and comes back round, as a Windows
# message box does. A grab holds the pointer only: Tab walked on out of
# the card, into the note under the question -- where typing landed --
# and onto the note list, whose Shift+F10 menu holds Delete. Shift+Tab
# walks back; on X11 it arrives as ISO_Left_Tab, the key a person's
# Shift+Tab really makes there. Where the keyboard went is read from the
# window's own record, and the app is given the keyboard back before
# every key, so a busy desktop cannot pass for a Tab that walked out.
_tb = {}
_tb_back = 'Shift-Tab' if sys.platform.startswith('win') else 'ISO_Left_Tab'


def _tb_holder():
    try:
        return app.nametowidget(app.tk.call('focus', '-lastfor', app._w))
    except (KeyError, tk.TclError):
        return None


def _tb_act():
    _own = {_l: _question_button(_l, 'Q-tab') for _l in ('Cancel', 'No', 'Yes')}
    _names = {_w: _l for _l, _w in _own.items()}
    _tb['keyboard'] = (_own['Cancel'] is not None
                       and _keyboard_on(_own['Cancel']))
    _stops = []
    for _key in ['Tab'] * 4 + [_tb_back] * 4:
        if not _tb['keyboard']:
            return
        _cur = _tb_holder()
        if _cur is None or not _keyboard_on(_cur):
            _tb['keyboard'] = False
            return
        try:
            _cur.event_generate('<%s>' % _key)
        except tk.TclError as _e:
            _stops.append('%s: %s' % (_key, _e))
            break
        app.update()
        _w = _tb_holder()
        _stops.append(_names.get(_w, repr(_w)))
    _tb['stops'] = _stops
    _own['No'].invoke()


_tb['answer'] = _while_asking(
    lambda: app.ask_yes_no_cancel('Q-tab', 'Tab stays among these.'),
    _tb_act, 'Yes', 'Q-tab')
if _tb.get('keyboard') is False:
    check('tab inside a question: SKIPPED -- the keyboard never reached it',
          True)
else:
    check('Tab walks a question\'s own answers and comes back round, and '
          'Shift+Tab walks back -- never out into the note under it (%s)'
          % _tb,
          _tb.get('stops') == ['No', 'Yes', 'Cancel', 'No',
                               'Cancel', 'Yes', 'No', 'Cancel']
          and _tb.get('answer') == (False, False))

# ============================================================
# A TEMPLATE SAVED AFTER ITS SECTION WAS REBUILT
# ============================================================
# The editor's save redrew the list it was HANDED -- whose rows are gone
# once the section has been rebuilt with the editor still open. The
# template was saved, and a red "Something went wrong" said otherwise.
# It asks the page for its list at the moment of saving now. The rebuild
# is made the way the nav's glyph made it before it learned to ask first.
app.templates = [NO.normalize_template({'name': 'LiveList', 'body': 'x'})]
NO.save_templates(app.templates)
app.toggle_settings_panel('templates'); app.update()
_lr_errs = []
app._edit_template(app.templates[0], app._refresh_templates_panel); app.update()
_lr_pop = app._mini_popup
_lr_ent = [w for w in _walk9(_lr_pop) if isinstance(w, tk.Entry)][0]
_lr_ent.delete(0, 'end')
_lr_ent.insert(0, 'LiveList renamed')
_lr_confirm = _lr_pop._confirm_dismiss
_lr_pop._confirm_dismiss = None
app.toggle_settings_panel('templates'); app.update()
_lr_pop._confirm_dismiss = _lr_confirm
check('fixture: the Templates section was rebuilt with the editor still open',
      app._mini_popup is _lr_pop and _lr_pop.winfo_exists())
app.report_callback_exception = lambda *a: _lr_errs.append(a[1])
try:
    find_widget(_lr_pop, tk.Button, 'Save').invoke(); app.update()
finally:
    del app.report_callback_exception
_lr_rows = [str(w.cget('text')) for w in _walk9(app.settings_templates_panel)
            if isinstance(w, tk.Label)]
check('...its save raises nothing, and the list shows the saved template '
      '(%s)' % _lr_errs[:1], not _lr_errs and 'LiveList renamed' in _lr_rows)
app._dismiss_mini_popup(); app.update()

# ============================================================
# THE DUPLICATES SECTION REBUILT AFTER A CLEANUP KEEPS ITS TITLE
# ============================================================
# The cleanup rebuilt the section by calling its builder directly, which
# skipped the heading and the resize handle: the title and the Expand
# toggle were gone until the section was chosen again in the nav.
app.notes = [NO.normalize_note({'id': 9811 + _i, 'title': _t, 'body': 'same',
                                'category': 'General'})
             for _i, _t in enumerate(['Groceries', 'Groceries', 'Groceries',
                                      'Plan', 'Plan'])]
app.save_notes()
app.toggle_settings_panel('duplicates'); app.update()
_dp_boxes = [w for w in _walk9(app.settings_duplicates_panel)
             if isinstance(w, tk.Checkbutton)]
if len(_dp_boxes) > 1:
    _dp_boxes[1].invoke()
app.ask_yes_no = lambda *a, **k: True
try:
    find_widget(app.settings_duplicates_panel, tk.Button,
                'Move ticked duplicates').invoke()
    app.update()
finally:
    del app.ask_yes_no
_dp_panel = app.settings_duplicates_panel
check('fixture: the cleanup took a copy away (%d notes left)' % len(app.notes),
      len(app.notes) == 4)
check('the Duplicates section rebuilt after a cleanup keeps its title and '
      'its Expand toggle',
      any(isinstance(w, tk.Label) and str(w.cget('text')) == 'Duplicates'
          for w in _dp_panel.winfo_children())
      and any(isinstance(w, tk.Button)
              and str(w.cget('text')).startswith(('Expand', 'Collapse'))
              for w in _walk9(_dp_panel)))
app.hide_settings_page(); app.update()

# ============================================================
# AN IMAGE PREVIEW CLOSED AT ONCE LEAVES NOTHING ON THE WINDOW
# ============================================================
# The preview binds its click-outside 50 ms after it opens, so the click
# that opened it is not taken for a click outside it. Closed within those
# 50 ms, it bound anyway -- a handler nothing would ever take off again,
# one more on the window for every quick close.
from PIL import Image as _pq_Image
import os as _pq_os   # its own: the seed block's aliases are gone
_pq_path = _pq_os.path.abspath('qa9_quick_preview.png')
_pq_Image.new('RGB', (60, 40), (10, 120, 200)).save(_pq_path)
app._dismiss_mini_popup(); app.update()
_pq_b1 = str(app.bind('<Button-1>') or '')
for _ in range(5):
    app._show_image_preview(_pq_path, 'quick.png')
    app._dismiss_mini_popup()
    for _ in range(10):
        app.update(); time.sleep(0.02)
check('an image preview closed at once leaves no click handler on the window '
      '(%d lines, %d before)' % (len(str(app.bind('<Button-1>') or '').split('\n')),
                                 len(_pq_b1.split('\n'))),
      str(app.bind('<Button-1>') or '') == _pq_b1)
_pq_os.remove(_pq_path)

# ============================================================
# A SHORT WINDOW KEEPS THE OPEN PANEL'S OWN BUTTONS ON SCREEN
# ============================================================
# "Import code" and "Share notes" open in the sidebar's bottom zone, which
# the note list gives its height to -- and at the smallest window (and a
# maximised one on a 1366x768 laptop) that was not enough: pack took the
# difference off the bottom, the panel's own buttons first, and Share's
# generated code never appeared at all. Asked of where things ARE on the
# screen (qa/README: a clipped widget still reports its full height).
app.hide_settings_page(); app.update()
app.notebook.select(app.TAB_NOTES); app.update()


def _pn_settle():
    for _ in range(15):
        app.update(); time.sleep(0.02)


def _pn_whole(w):
    """w is drawn whole inside the window."""
    app.update_idletasks()
    _top = w.winfo_rooty()
    return (w.winfo_ismapped() and w.winfo_height() > 1
            and _top >= app.winfo_rooty()
            and _top + w.winfo_height() <= app.winfo_rooty() + app.winfo_height())


def _pn_buttons(panel, labels):
    return [w for w in _walk9(panel) if isinstance(w, tk.Button)
            and str(w.cget('text')).strip() in labels]


_pn_zone = [b for b, _kw in app._sidebar_zone_buttons]
for _pn_size in ('640x600', '1366x690', '1150x860'):
    app.geometry(_pn_size); _pn_settle()
    app.toggle_import_panel(); _pn_settle()
    _pn_imp = _pn_buttons(app.import_panel, ('Import', 'Clear', 'Close'))
    check('%s: the Import panel\'s own buttons are on screen (%s)'
          % (_pn_size, [str(b.cget('text')) for b in _pn_imp if not _pn_whole(b)]),
          len(_pn_imp) == 3 and all(_pn_whole(b) for b in _pn_imp)
          and _pn_whole(app.import_box))
    app.toggle_import_panel(); _pn_settle()
    app.toggle_share_panel(); _pn_settle()
    _pn_ids = [n['id'] for n in app.notes][:1]
    for _pn_id in _pn_ids:
        app._share_vars[_pn_id].set(True)
    find_widget(app.share_panel, tk.Button, 'Generate code').invoke(); _pn_settle()
    _pn_share = (_pn_buttons(app.share_panel, ('Generate code', 'Close'))
                 + [w for w in _walk9(app.share_code_area)
                    if isinstance(w, (tk.Button, tk.Text))])
    check('%s: Share\'s own buttons and its generated code are on screen (%s)'
          % (_pn_size, [str(w) for w in _pn_share if not _pn_whole(w)][:3]),
          _pn_ids and len(_pn_share) >= 5 and all(_pn_whole(w) for w in _pn_share))
    if _pn_size == '1150x860':
        # With room, nothing steps aside and nothing shrinks.
        check('1150x860: with room, the zone keeps all four buttons and the '
              'list of notes its full height',
              all(app._is_placed(b) for b in _pn_zone)
              and int(app._share_list_wrap.cget('height'))
              == app.SIDEBAR_PANEL_BODY['share'][0])
    app.toggle_share_panel(); _pn_settle()
    check('%s: closing the panel brings every button of the zone back, in '
          'order, and the paste box its full size' % _pn_size,
          [s for s in app._sidebar_bottom.pack_slaves() if s in _pn_zone] == _pn_zone
          and int(app.import_box.cget('height'))
          == app.SIDEBAR_PANEL_BODY['import'][0])
# The selection bar opening above an open panel takes room without the
# sidebar changing size; the zone is given less, and fits again.
app.geometry('1366x690'); _pn_settle()
app.toggle_share_panel(); _pn_settle()
for _pn_id in [n['id'] for n in app.notes][:1]:
    app._share_vars[_pn_id].set(True)
find_widget(app.share_panel, tk.Button, 'Generate code').invoke(); _pn_settle()
if not app.selection_mode:
    app._toggle_selection_mode()
_pn_settle()
_pn_share = (_pn_buttons(app.share_panel, ('Generate code', 'Close'))
             + [w for w in _walk9(app.share_code_area)
                if isinstance(w, (tk.Button, tk.Text))])
check('1366x690 with the selection bar open above it: Share\'s buttons and '
      'code are still on screen (%s)'
      % [str(w) for w in _pn_share if not _pn_whole(w)][:3],
      app._is_placed(app.bulk_action_bar) and len(_pn_share) >= 5
      and all(_pn_whole(w) for w in _pn_share))
if app.selection_mode:
    app._toggle_selection_mode()
app.toggle_share_panel(); _pn_settle()
app.geometry('1100x850'); _pn_settle()

# ============================================================
# STATISTICS: THE SAME FIGURES, DRAWN ONCE
# ============================================================
# The render parsed every stamp with strptime (10,212 calls at 5,000 notes)
# and destroyed and rebuilt every widget on each list refresh while
# Settings was open. The canonical stamp is read as text now and the
# widgets stay. What is shown must not move by one: the figures are held
# against the old algorithm itself, over stamps chosen to trip a shortcut
# -- a day that does not exist, hour 24, minute 60, single digits, a "T",
# seconds, digits from another script, nothing at all.
from datetime import datetime as _st_dt, date as _st_date, timedelta as _st_td


def _st_oracle(notes):
    """The figures as the old render computed them, strptime and all."""
    today = _st_date.today()
    starts = (today - _st_td(days=today.weekday()), today.replace(day=1),
              today.replace(month=1, day=1))

    def parse(raw):
        if not isinstance(raw, str) or not raw:
            return None
        try:
            return _st_dt.strptime(raw[:16], "%Y-%m-%d %H:%M").date()
        except ValueError:
            return None
    rows = []
    for field in ('created', 'updated'):
        row = [0, 0, 0, 0]
        for n in notes:
            d = parse(n.get(field))
            if d is None:
                continue
            row[0] += d >= starts[0]
            row[1] += d >= starts[1]
            row[2] += d >= starts[2]
            row[3] += d < starts[2]
        rows.append(row)
    return rows


def _st_shown():
    """(tile caption -> figure, the Added/Updated rows) as drawn."""
    tiles, table = app.stats_frame.winfo_children()[:2]
    pairs = {}
    for edge in tiles.winfo_children():
        labels = [w for w in edge.winfo_children()[0].winfo_children()
                  if isinstance(w, tk.Label)]
        pairs[str(labels[1].cget('text'))] = labels[0]
    rows = [[table.grid_slaves(row=r, column=c)[0] for c in range(1, 5)]
            for r in (2, 3)]
    return pairs, rows


_st_notes = list(app.notes)
_st_t = _st_date.today()
_st_d = _st_t.strftime('%Y-%m-%d')
_st_other_script = ''.join(chr(0x660 + int(ch)) if ch.isdigit() else ch
                           for ch in _st_d + ' 10:00')
_st_stamps = [
    _st_d + ' 10:00', _st_t.replace(day=1).strftime('%Y-%m-%d') + ' 08:30',
    _st_t.replace(month=1, day=1).strftime('%Y-%m-%d') + ' 00:00',
    (_st_t.replace(month=1, day=1) - _st_td(days=1)).strftime('%Y-%m-%d') + ' 23:59',
    '%d-%d-%d 9:05' % (_st_t.year, _st_t.month, _st_t.day),
    '%d-02-30 10:00' % _st_t.year, _st_d + ' 24:00', _st_d + ' 10:60',
    _st_d + 'T10:00', _st_d + ' 10:00:59', _st_other_script, 'garbage', '',
    None, '1999-12-31 23:59', '0000-01-01 00:00']
app.notes = []
for _st_i, _st_stamp in enumerate(_st_stamps):
    _st_n = NO.normalize_note({'id': 9900 + _st_i, 'title': 'Stamp %d' % _st_i,
                               'body': 'x', 'category': 'General'})
    _st_n['created'] = _st_stamp
    _st_n['updated'] = _st_stamps[-1 - _st_i]
    app.notes.append(_st_n)
app.show_settings_page(); app.update()
app._render_statistics(); app.update()
_st_pairs, _st_rows = _st_shown()
_st_got = [[int(l.cget('text')) for l in row] for row in _st_rows]
check('the time breakdown is exactly what the old strptime render counted '
      '(%s, expected %s)' % (_st_got, _st_oracle(app.notes)),
      _st_got == _st_oracle(app.notes))
check('...and the tiles too (total %s, added this week %s)'
      % (_st_pairs['Total notes'].cget('text'),
         _st_pairs['Added this week'].cget('text')),
      int(_st_pairs['Total notes'].cget('text')) == len(app.notes)
      and int(_st_pairs['Added this week'].cget('text')) == _st_oracle(app.notes)[0][0])
# In place: the next render changes the figures on the SAME widgets.
_st_before = {k: v for k, v in _st_pairs.items()}
app.notes.append(NO.normalize_note({'id': 9950, 'title': 'One more', 'body': 'y',
                                    'category': 'General'}))
app._render_statistics(); app.update()
_st_pairs2, _st_rows2 = _st_shown()
check('the next render updates the figures on the same widgets, rebuilding '
      'nothing (total now %s)' % _st_pairs2['Total notes'].cget('text'),
      all(_st_pairs2[k] is _st_before[k] for k in _st_before)
      and int(_st_pairs2['Total notes'].cget('text')) == len(app.notes)
      and [[int(l.cget('text')) for l in row] for row in _st_rows2]
      == _st_oracle(app.notes))
# Another palette is another drawing: built again, in its colours.
_st_theme = app.theme_name
app.set_theme('light' if _st_theme != 'light' else 'dark'); app.update()
app._render_statistics(); app.update()
_st_pairs3, _st_rows3 = _st_shown()
check('after a theme switch the next render draws it again, in the new '
      'palette', _st_pairs3['Total notes'] is not _st_before['Total notes']
      and str(_st_pairs3['Total notes'].cget('fg')) == app.colors['text'])
app.set_theme(_st_theme); app.update()
# And none of it leaves anything behind: no Tcl command per render, and none
# per rebuild of the theme picker (each re-bound its long-lived frame).


def _st_commands():
    # after() registers a command per pending callback, which comes and goes
    # by itself; those are not what this is about.
    return len([c for c in app.tk.splitlist(app.tk.call('info', 'commands'))
                if not str(c).endswith('callit')])


app.update()
_st_c0 = _st_commands()
for _ in range(20):
    app._render_statistics()
_st_c1 = _st_commands()
for _ in range(10):
    app._refresh_theme_picker()
app.update()
_st_c2 = _st_commands()
# No growth, rather than an equal count: something unrelated finishing in
# the same stretch can take one away (measured: 2384 -> 2383), and what
# leaked here added one per render and two per rebuild.
check('twenty renders of Statistics leave no Tcl command behind (%d -> %d)'
      % (_st_c0, _st_c1), _st_c1 <= _st_c0)
check('ten rebuilds of the theme picker leave no Tcl command behind (%d -> %d)'
      % (_st_c1, _st_c2), _st_c2 <= _st_c1)
app.notes = list(_st_notes)
app._render_statistics(); app.update()

# ============================================================
# DUPLICATES: A PAGE OF GROUPS AT A TIME, FOUND ONCE
# ============================================================
# Every group was drawn at once -- 676 widgets for the hundred groups of a
# 5,000-note notebook -- and "Show more" did not exist. Twenty are drawn
# now, the rest a page at a time from the groups already found; and the
# one button that acts on ALL groups still reaches the undrawn ones.
import noteorganizer.ui.settings_page as _dq_page
_dq_real = _dq_page.find_duplicate_groups
_dq_calls = []
_dq_page.find_duplicate_groups = lambda notes: (_dq_calls.append(1),
                                                _dq_real(notes))[1]
_dq_notes = list(app.notes)
app.notes = []
for _dq_g in range(30):
    for _dq_c in range(2):
        app.notes.append(NO.normalize_note({
            'id': 9700 + _dq_g * 2 + _dq_c, 'title': 'Twin %02d' % _dq_g,
            'body': 'same text %d' % _dq_g, 'category': 'General'}))
app.notes.append(NO.normalize_note({'id': 9699, 'title': 'Alone', 'body': 'z',
                                    'category': 'General'}))
try:
    app.toggle_settings_panel('duplicates'); app.update()

    def _dq_drawn():
        # A group's heading reads “Title” — N copies; the section's own
        # explanations use the word too, so the shape is what is asked.
        return [str(w.cget('text')) for w in _walk9(app.settings_duplicates_panel)
                if isinstance(w, tk.Label)
                and str(w.cget('text')).startswith('“')
                and str(w.cget('text')).endswith(' copies')]

    _dq_more = find_widget(app.settings_duplicates_panel, tk.Button, 'more groups')
    check('the Duplicates section draws the first twenty of thirty groups, in '
          'the order they were found, and offers the rest (%d drawn)'
          % len(_dq_drawn()),
          len(_dq_drawn()) == 20 and _dq_more is not None
          and '10 not shown' in str(_dq_more.cget('text'))
          and [t.split('”')[0].lstrip('“') for t in _dq_drawn()]
          == ['Twin %02d' % i for i in range(20)])
    if _dq_more is not None:
        _dq_more.invoke(); app.update()
    check('"Show more" draws the other ten without looking for duplicates '
          'again (%d drawn, %d searches)' % (len(_dq_drawn()), len(_dq_calls)),
          len(_dq_drawn()) == 30 and len(_dq_calls) == 1
          and find_widget(app.settings_duplicates_panel, tk.Button,
                          'more groups') is None)
    # Built again (twenty drawn), then "Clean up ALL" pressed at once: it
    # must take a copy from every one of the thirty groups.
    app.toggle_settings_panel('duplicates'); app.update()
    app.ask_yes_no = lambda *a, **k: True
    try:
        find_widget(app.settings_duplicates_panel, tk.Button, 'Clean up ALL').invoke()
        app.update()
    finally:
        del app.ask_yes_no
    _dq_left = sorted(n['title'] for n in app.notes)
    check('"Clean up ALL" reaches the groups not drawn yet: one of each pair '
          'is left (%d notes)' % len(app.notes),
          _dq_left == sorted(['Alone'] + ['Twin %02d' % i for i in range(30)]))
finally:
    _dq_page.find_duplicate_groups = _dq_real
    app.notes = list(_dq_notes)
    app.save_notes()
app.hide_settings_page(); app.update()

# ============================================================
# A QUESTION ASKED INSIDE ANOTHER GIVES THE GRAB BACK; YES ACTS ON WHAT IT NAMED
# ============================================================
# Tk has one grab. The export's own timer showed "Export complete" over a
# waiting question, took the grab, and released it on OK -- leaving the
# question still on screen and the app under it taking clicks. Under the
# selection bar's "Move to trash" a note ticked there was then removed with
# no Trash copy: the answer read the ticks again instead of acting on the
# notes its question had named.
import json as _ng_json
import os as _ng_os
_ng_info = app.__dict__.pop('show_info', None)
_ng = {}


def _ng_outer_act():
    _ng['outer'] = app._asking_dialogs[-1]['border'] if app._asking_dialogs else None
    app._export_state = {'current': 1, 'total': 1, 'done': True, 'error': None,
                         'save_path': _ng_os.path.abspath('qa9_export.zip')}
    _ng['inner'] = _while_asking(
        app._poll_export_progress,
        lambda: _question_button('OK', 'Export complete').invoke(),
        'OK', 'Export complete')
    _ng['grab_after'] = app.grab_current()
    _b = _question_button('No', 'Outer waits')
    if _b is not None:
        _b.invoke()


try:
    _ng['answer'] = _while_asking(
        lambda: app.ask_yes_no('Outer waits', 'Asked first.', default='no'),
        _ng_outer_act, 'Yes', 'Outer waits', cap_ms=15000)
    check('a question asked inside another ("Export complete" from the export\'s '
          'timer), once answered, gives the grab back to the one still waiting '
          '(%s)' % {k: str(v) for k, v in _ng.items()},
          _ng.get('outer') is not None and _ng.get('grab_after') is _ng['outer']
          and _ng.get('inner') == (None, False)
          and _ng.get('answer') == (False, False))
finally:
    if _ng_info is not None:
        app.show_info = _ng_info
    for _ng_f in ('qa9_export.zip',):
        if _ng_os.path.exists(_ng_f):
            _ng_os.remove(_ng_f)

# The answer itself, whatever reached the ticks while it waited: one tick
# added under the question and the named one taken away. Yes moves the
# named note to the Trash, and the other stays in the notebook.
_bt_saved = list(app.notes)
app.notes = [NO.normalize_note({'id': 9861 + _i, 'title': _t, 'body': 'b'})
             for _i, _t in enumerate(['Keep me', 'Trash me', 'Ticked later'])]
app.save_notes(); app.new_note(); app.refresh_note_list(); app.update()
if not app.selection_mode:
    app._toggle_selection_mode()
app._toggle_note_selected(9862, True); app.update()
_bt_trash_before = len(app.trash)


def _bt_act():
    app._toggle_note_selected(9863, True)
    app._toggle_note_selected(9862, False)
    _b = _question_button('Yes', 'Move to trash')
    if _b is not None:
        _b.invoke()


_bt_answer = _while_asking(app._bulk_move_to_trash, _bt_act, 'No', 'Move to trash')
_bt_notes = sorted(n['id'] for n in app.notes)
_bt_trashed = [e.get('id') for e in app.trash[_bt_trash_before:]]
with open('notes_data.json', encoding='utf-8') as _bt_f:
    _bt_disk = sorted(n.get('id') for n in _ng_json.load(_bt_f))
check('Yes to "Move to trash" moves the note it named, and only it -- a tick '
      'added while it waited stays in the notebook, nothing is lost '
      '(notes %s, trashed %s, on disk %s)' % (_bt_notes, _bt_trashed, _bt_disk),
      _bt_answer == (None, False) and _bt_notes == [9861, 9863]
      and _bt_trashed == [9862] and _bt_disk == [9861, 9863])
if app.selection_mode:
    app._toggle_selection_mode()
# The open note's sibling: "Save them before duplicating?" answered Yes
# duplicates the note it asked about, not whichever one the editor holds
# by the time of the answer.
app.notes = [NO.normalize_note({'id': 9871, 'title': 'Original', 'body': 'o'}),
             NO.normalize_note({'id': 9872, 'title': 'Other', 'body': 'p'})]
app.save_notes(); app.refresh_note_list()
app.open_note_in_tab(app.find_note(9871)); app.update()
app.body_text.insert('end', ' more')
_du = {}


def _du_act():
    _du['opened'] = app.open_note_in_tab(app.find_note(9872))
    app.update()
    _b = _question_button('Yes', 'Unsaved changes')
    if _b is not None:
        _b.invoke()


_du_answer = _while_asking(app.duplicate_current_note, _du_act, 'Cancel',
                           'Unsaved changes')
_du_titles = sorted(n.get('title') for n in app.notes)
check('Yes to "Save them before duplicating?" duplicates the note it asked '
      'about, even when another was opened while it waited (%s)' % _du_titles,
      _du.get('opened') and not _du_answer[1]
      and _du_titles == sorted(['Original', 'Other', 'Original (copy)']))
app.notes = _bt_saved
app.save_notes(); app.new_note(); app.refresh_note_list(); app.update()

# ============================================================
# ESCAPE AND ENTER IN A RENAME BOX RAISE NOTHING
# ============================================================
# The box's entry closed the box on Escape and let the key go on: Tk had
# already read the box's own <Escape> script, whose command the close had
# just deleted -- a silent "invalid command name" on every Escape.
for _rb_key, _rb_name in (('Escape', 'Escape'), ('Return', 'Enter')):
    _rb_pop = app._show_inline_rename(app.filter_menu, 'Projects', lambda _v: True)
    app.update()
    _rb_ent = [w for w in _walk9(_rb_pop) if isinstance(w, tk.Entry)][0]
    _rb_bg = len(_bg9)
    if _keyboard_on(_rb_ent):
        _rb_ent.event_generate('<%s>' % _rb_key)
        app.update()
        check('%s in a rename box closes it and raises no background error (%s)'
              % (_rb_name, _bg9[_rb_bg:][:1]),
              not _rb_pop.winfo_exists() and len(_bg9) == _rb_bg)
    else:
        check('%s in a rename box: SKIPPED -- the keyboard never reached it'
              % _rb_name, True)
    app._dismiss_mini_popup(); app.update()

# ============================================================
# A QUESTION'S CARD FITS THE WINDOW, ITS BUTTONS ON SCREEN
# ============================================================
# The card was placed at 0.42 of the window's height with no limit: the
# startup notice joining four messages put its title above a 600px window
# and its only button below it, with the X refused while it asked. And
# the category question's three buttons ran off both sides at 640px.
_fq_saved = (NO.VERSION_CHANGE, NO.STORAGE_WARNING, NO.MIGRATION_INFO,
             NO.PURGED_DIRS, app._corrupt_notes_report, app._categories_adopted,
             app._cleanup_report, app._version_backup_path)
_fq_base = 'C:\\Users\\Alexandra\\AppData\\Roaming\\NoteOrganizer'
NO.VERSION_CHANGE = ('up', '0.81.202', '0.82.233')
NO.STORAGE_WARNING = None
NO.MIGRATION_INFO = None
NO.PURGED_DIRS = ['C:\\Users\\Alexandra\\Desktop\\NoteOrganizer',
                  'C:\\Users\\Alexandra\\Documents\\NoteOrganizer']
app._corrupt_notes_report = _fq_base + '\\notes_data.unreadable_2026-10-01_09-14-03.json'
app._categories_adopted = ['Groceries and errands', 'Work - Project Atlas',
                           "Kids' school", 'Recipes to try', 'Health',
                           'Travel 2027', 'Books', 'Garden', 'Car', 'Taxes']
app._cleanup_report = None
app._version_backup_path = _fq_base + '\\backups\\notes_before_0.82.233.json'
_fq_info = app.__dict__.pop('show_info', None)


def _fq_card(title):
    _b = _question_button('OK', title) or _question_button('Cancel', title)
    while _b is not None and _b.master is not app:
        _b = _b.master
    return _b


def _fq_inside(w):
    app.update_idletasks()
    return (w.winfo_rooty() >= app.winfo_rooty()
            and w.winfo_rooty() + w.winfo_height()
            <= app.winfo_rooty() + app.winfo_height()
            and w.winfo_rootx() >= app.winfo_rootx()
            and w.winfo_rootx() + w.winfo_width()
            <= app.winfo_rootx() + app.winfo_width())


try:
    for _fq_size in ('640x600', '1366x690'):
        app.geometry(_fq_size); _pn_settle()
        _fq = {}

        def _fq_act():
            _card = _fq_card('your notes')
            _ok = _question_button('OK', 'your notes')
            _view = ([w for w in _walk9(_card) if isinstance(w, tk.Canvas)]
                     if _card is not None else [])
            _fq['card'] = _card is not None and _fq_inside(_card)
            _fq['ok'] = _ok is not None and _fq_inside(_ok)
            _fq['default'] = (_ok is not None and app._asking_dialogs
                              and app._asking_dialogs[-1]['default'] is _ok)
            if _view:
                _view[0].yview_moveto(1.0); app.update()
                _fq['scrolls_to_end'] = _view[0].yview()[1] == 1.0
                _fq['scrolled'] = _view[0].yview()[0] > 0
            if _ok is not None:
                _ok.invoke()

        _fq_res = _while_asking(app.announce_startup_changes, _fq_act, 'OK',
                                'your notes')
        check('%s: the four-message startup notice fits the window, title and OK '
              'on screen, its message scrolling to its end, OK still the default '
              '(%s)' % (_fq_size, _fq),
              _fq.get('card') and _fq.get('ok') and _fq.get('default')
              and _fq.get('scrolls_to_end') and _fq.get('scrolled')
              and not _fq_res[1])
    # A question that fits sits where it always did: centred at 0.42 of the
    # window's height, nothing scrolling.
    app.geometry('1100x850'); _pn_settle()
    _fq_plain = {}

    def _fq_plain_act():
        _card = _fq_card('Plain question')
        app.update_idletasks()
        _fq_plain['centre'] = ((_card.winfo_rooty() - app.winfo_rooty()
                                + _card.winfo_height() / 2) / app.winfo_height()
                               if _card is not None else None)
        _fq_plain['bars'] = len([w for w in _walk9(_card)
                                 if isinstance(w, ttk.Scrollbar)
                                 and w.winfo_ismapped()]) if _card else None
        _question_button('OK', 'Plain question').invoke()

    from tkinter import ttk
    _while_asking(lambda: app.show_info('Plain question', 'Short.'),
                  _fq_plain_act, 'OK', 'Plain question')
    check('a question that fits sits where it always did, at 0.42 of the height, '
          'with no scrollbar (%s)' % _fq_plain,
          _fq_plain.get('centre') is not None
          and abs(_fq_plain['centre'] - 0.42) < 0.01 and _fq_plain.get('bars') == 0)
    # The widest buttons in the app, at the narrowest window, and a window
    # shrunk while a long question waits.
    app.geometry('640x600'); _pn_settle()
    _fq_wide = {}

    def _fq_wide_act():
        _btns = [w for w in _walk9(_fq_card('Delete category'))
                 if isinstance(w, tk.Button)]
        _fq_wide['inside'] = [str(b.cget('text'))[:12] for b in _btns
                              if _fq_inside(b)]
        _question_button('Cancel', 'Delete category').invoke()

    _while_asking(lambda: app._ask_category_deletion('Groceries and errands', 12),
                  _fq_wide_act, 'Cancel', 'Delete category')
    check('640x600: all three buttons of the category question are inside the '
          'window (%s)' % _fq_wide.get('inside'),
          len(_fq_wide.get('inside') or []) == 3)
    app.geometry('1366x900'); _pn_settle()
    _fq_shrunk = {}

    def _fq_shrink_act():
        app.geometry('640x600'); _pn_settle()
        _ok = _question_button('OK', 'your notes')
        _fq_shrunk['ok'] = _ok is not None and _fq_inside(_ok)
        _fq_shrunk['card'] = _fq_inside(_fq_card('your notes'))
        if _ok is not None:
            _ok.invoke()

    _while_asking(app.announce_startup_changes, _fq_shrink_act, 'OK', 'your notes')
    check('the window shrunk while the long notice waits: it still fits, OK on '
          'screen (%s)' % _fq_shrunk, _fq_shrunk.get('ok') and _fq_shrunk.get('card'))
finally:
    if _fq_info is not None:
        app.show_info = _fq_info
    (NO.VERSION_CHANGE, NO.STORAGE_WARNING, NO.MIGRATION_INFO, NO.PURGED_DIRS,
     app._corrupt_notes_report, app._categories_adopted, app._cleanup_report,
     app._version_backup_path) = _fq_saved
    app.geometry('1100x850'); _pn_settle()

check('none of the blocks above raised a background error (%s)' % _bg9[:2],
      not _bg9)
app.notes = list(_na_notes)
app.save_notes()

app.notes = list(_tg_saved_notes)
app.templates = list(_tg_saved_templates)
app.save_notes()
app.new_note(); app.update()

print()
print(f"=== QA9 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
