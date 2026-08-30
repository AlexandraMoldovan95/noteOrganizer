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
import note_organizer as NO, tkinter as tk
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

cat_btn.event_generate('<Button-1>')
app.update()
check('editor stays open after opening the category dropdown (bug 1)', editor_popup.winfo_exists())

dropdown_popup = getattr(cat_btn, '_nested_popup', None)
check('nested dropdown popup exists', dropdown_popup is not None and dropdown_popup.winfo_exists())

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
work_lbl.event_generate('<Button-1>')
app.update()
check('editor still open after picking a category', editor_popup.winfo_exists())

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
NO.clipboard.read_html = lambda: '<p>doar text</p>'
check('a non-table paste falls through to the normal path',
      app._paste_table_aware(_body9) is None)

# ---- AND THE DIALOG DRAWS A LIVE TABLE PREVIEW ----
# The body box stays text (that is the store), but the dialog shows the
# table AS a table underneath -- the same visual language as the editor.
NO.clipboard.read_html = lambda: (
    '<table><tr><th>Zi</th><th>Plan</th></tr>'
    '<tr><td>luni</td><td>scris</td></tr></table>')
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
_multi9 = ('text liber\n| Tabel | < |\n| Aliment | Sursa |\n'
           '| Carne | vita |\n\n| Zi | Plan |\n| luni | scris |\n'
           '| marti | citit |\n| miercuri | sport |\n| joi | piata |\n'
           '| vineri | film |\n| sambata | drum |\n| duminica | odihna |')
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
                     'randul de text ramas')
_body9.delete('1.0', 'end')
_body9.event_generate('<<Paste>>')
app.update()
app.update()
_visC = _n9(_body9.count('1.0', 'end', 'displaychars'))
check(f'blank lines around hidden tables hide with them '
      f'({_visC} visible)',
      _visC <= len('randul de text ramas') + 2)

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
app.clipboard_append('doar un rand simplu')
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
app.update()
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
_bodyG.insert('insert', 'coada')
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
    'name': 'Cumparaturi', 'title': 'T', 'body': 'continut vechi',
    'comments': '', 'category': 'General', 'checklist': []})]
NO.save_templates(app.templates)
app.new_note()
app.update()
app.title_entry.insert(0, 'Alta nota')
app.body_text.insert('1.0', 'continut NOU')
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
_entC9.insert(0, 'Cumparaturi')
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
      and app.templates[0]['body'] == 'continut vechi'
      and app._mini_popup is not None and app._mini_popup.winfo_exists())
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), True)[1]
_entC9 = _ents21(app._mini_popup)[0]
_entC9.delete(0, 'end')
_entC9.insert(0, 'Cumparaturi')
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
      [t['name'] for t in app.templates].count('Cumparaturi') == 1
      and app.templates[-1]['body'] == 'continut NOU')

# renaming a template onto a neighbour in Settings asks the same way
app.templates.append(NO.normalize_template({
    'name': 'Retete', 'title': '', 'body': 'retetele mele',
    'comments': '', 'category': 'General', 'checklist': []}))
NO.save_templates(app.templates)
app._edit_template(app.templates[-1], lambda: None)
app.update()
_entR9 = _ents21(app._mini_popup)[0]
_entR9.delete(0, 'end')
_entR9.insert(0, 'Cumparaturi')
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), False)[1]
find_widget(app._mini_popup, tk.Button, 'Save').invoke()
app.update()
_names9 = [t['name'] for t in app.templates]
check('renaming onto a neighbour asks too; No leaves no duplicate',
      _names9.count('Cumparaturi') == 1 and 'Retete' in _names9)
app.ask_yes_no = lambda *a, **k: (_asksC.append(1), True)[1]
find_widget(app._mini_popup, tk.Button, 'Save').invoke()
app.update()
_names9 = [t['name'] for t in app.templates]
check('Yes removes the neighbour and keeps one template with that name',
      _names9 == ['Cumparaturi']
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
cat_btn2.event_generate('<Button-1>')
app.update()
dropdown_popup2 = getattr(cat_btn2, '_nested_popup', None)
work_lbl2 = find_widget(dropdown_popup2, tk.Label, 'Work')
work_lbl2.event_generate('<Button-1>')
app.update()

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
    'name': 'ConfTest', 'title': 'x', 'body': 'corp',
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
month_btn.event_generate('<Button-1>')
app.update()
check('Jump-to-month popup stays open after opening the month dropdown',
      jump_popup.winfo_exists())

print()
print(f"=== QA9 FAILURES: {fails if fails else 'NONE'} ===")

sys.exit(1 if fails else 0)
